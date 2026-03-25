from __future__ import annotations

import hashlib
import json
import logging
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from statistics import median
from typing import Any

from .bulk_parser import ParsedBulkVehicle, parse_bulk_vehicle_text
from .config import EngineConfig
from .http import HttpClient
from .detailed_report import DetailedVehicleReportService
from .llm import LlmClient
from .models import NormalizedListing, SourceRunResult, VehicleQuery
from .link_extract import ListingLinkExtractor
from .query_parser import parse_vehicle_query
from .scoring import (
    apply_adjustments,
    compute_confidence,
    infer_mileage_adjustment_rate,
    money,
    percentile,
    score_listing,
    weighted_median,
)
from .sources import (
    AutoDevAdapter,
    CraigslistAdapter,
    CustomSourceAdapter,
    EbayMotorsAdapter,
    ManualImportAdapter,
    MarketCheckDealerAdapter,
    MarketCheckPrivatePartyAdapter,
    OneAutoAdapter,
    build_future_source_stubs,
)
from .storage import SQLiteRepository
from .vin_decode import NHTSAVinDecoder


LOGGER = logging.getLogger(__name__)


class VehicleCompsEngine:
    def __init__(self, config: EngineConfig | None = None) -> None:
        self.config = config or EngineConfig.from_env()
        self.repository = SQLiteRepository(self.config.sqlite_path)
        self.http_client = HttpClient(
            timeout_seconds=self.config.http_timeout_seconds,
            retry_count=self.config.http_retry_count,
        )
        self.link_extractor = ListingLinkExtractor(self.http_client)
        self.vin_decoder = NHTSAVinDecoder(self.http_client)
        self.llm = LlmClient(self.http_client)
        self.detailed_reports = DetailedVehicleReportService(self.http_client)
        self.adapters = self._build_adapters()

    def evaluate(self, payload: dict[str, Any]) -> dict[str, Any]:
        payload = dict(payload)
        engine_type = str(payload.get("evaluation_engine", "resell") or "resell").strip().lower()
        if engine_type == "personal":
            return self._evaluate_personal_value(payload)
        mode = str(payload.get("evaluation_mode", "")).strip().lower()
        if mode == "bulk":
            return self.run_bulk_evaluation(payload)
        if mode == "zippy":
            return self._evaluate_zippy(payload)
        return self._evaluate_single(payload)

    def _evaluate_single(self, payload: dict[str, Any]) -> dict[str, Any]:
        payload = dict(payload)
        vin_only_lookup = self._is_vin_only_lookup(payload)
        include_detailed_report = self.detailed_reports.should_generate_detailed_vehicle_report(payload)
        vehicle_input = str(payload.get("vehicle_input", "")).strip()
        if vehicle_input:
            augmented_input, extracted_pages = self.link_extractor.augment_vehicle_input(vehicle_input)
            payload["vehicle_input"] = augmented_input
            if extracted_pages:
                payload["custom_listings"] = payload.get("custom_listings") or []
                if not payload.get("asking_price"):
                    for extracted in extracted_pages:
                        asking_price = extracted.get("asking_price")
                        if asking_price:
                            payload["asking_price"] = asking_price
                            break
        query = parse_vehicle_query(payload)
        self._apply_vin_decode(query)
        enabled_source_keys = [
            adapter.key
            for adapter in self.adapters
            if adapter.is_enabled()
        ]

        if not query.minimum_details_present():
            return self._build_needs_more_data_response(query, enabled_source_keys)

        cache_key = query.cache_key(enabled_source_keys)
        if include_detailed_report:
            cache_key = f"{cache_key}:detailed"
        use_cache = not include_detailed_report and not payload.get("force_refresh")
        if use_cache:
            cached = self.repository.get_cache_json(cache_key)
            if cached:
                return cached

        source_results = self._run_sources(query, preferred_keys=self._preferred_source_keys_for_query(vin_only_lookup))
        deduped = self._dedupe_listings(
            [
                listing
                for result in source_results
                for listing in result.normalized_listings
            ]
        )
        deduped = self._decode_listing_vins(query, deduped)
        included, excluded = self._score_and_filter(query, deduped)
        included = self._enrich_top_listings(query, included)
        included = self._decode_listing_vins(query, included)
        included, more_excluded = self._score_and_filter(query, included)
        excluded.extend(more_excluded)

        if len(included) < 3:
            response = self._build_low_data_response(query, source_results, included, excluded, enabled_source_keys)
            if use_cache:
                self.repository.set_cache_json(cache_key, response, ttl_seconds=self.config.cache_ttl_seconds)
            return response

        response = self._build_success_response(query, source_results, included, excluded)
        if include_detailed_report:
            response["detailed_vehicle_report"] = self.detailed_reports.get_detailed_vehicle_report(query, response, included)
        if use_cache:
            self.repository.set_cache_json(cache_key, response, ttl_seconds=self.config.cache_ttl_seconds)
        return response

    def _evaluate_zippy(self, payload: dict[str, Any]) -> dict[str, Any]:
        payload = dict(payload)
        vin_only_lookup = self._is_vin_only_lookup(payload)
        vehicle_input = str(payload.get("vehicle_input", "")).strip()
        if vehicle_input:
            augmented_input, extracted_pages = self.link_extractor.augment_vehicle_input(vehicle_input)
            payload["vehicle_input"] = augmented_input
            if extracted_pages and not payload.get("asking_price"):
                for extracted in extracted_pages:
                    asking_price = extracted.get("asking_price")
                    if asking_price:
                        payload["asking_price"] = asking_price
                        break
        query = parse_vehicle_query(payload)
        self._apply_vin_decode(query)
        enabled_source_keys = [adapter.key for adapter in self.adapters if adapter.is_enabled()]

        if not (query.year and query.make and query.model):
            return {
                "mode": "zippy",
                "status": "needs_more_data",
                "provider": "Multi-source vehicle comps engine",
                "vehicle_summary": self._vehicle_summary(query),
                "parsed_details": self._query_dict(query),
                "comparable_count": 0,
                "source_breakdown": [],
                "matched_comps": [],
                "values": {},
                "message": "Include at least the year, make, and model to run Zippy.",
                "assumptions": self._assumptions(query, enabled_source_keys),
            }

        source_results = self._run_sources(query, preferred_keys=self._preferred_source_keys_for_query(vin_only_lookup))
        deduped = self._dedupe_listings([
            listing
            for result in source_results
            for listing in result.normalized_listings
        ])
        valid = [
            listing for listing in deduped
            if self._listing_market_price(listing) is not None
        ]
        if not valid:
            return {
                "mode": "zippy",
                "status": "needs_more_data",
                "provider": "Multi-source vehicle comps engine",
                "vehicle_summary": self._vehicle_summary(query),
                "parsed_details": self._query_dict(query),
                "comparable_count": 0,
                "source_breakdown": [],
                "matched_comps": [],
                "values": {},
                "message": "Zippy did not find enough priced comps yet.",
                "assumptions": self._assumptions(query, enabled_source_keys),
            }

        avg_all = self.calculate_market_value(valid)
        avg_closest = self._average_price_of_closest_mileage(valid, query.mileage, 20) if query.mileage else avg_all
        anchor = avg_closest or avg_all
        craigslist_average = self._craigslist_average(valid)
        full_price_range = self._build_full_price_range(valid)
        zippy_values = {
            "average_all_comps": money(avg_all),
            "average_20_closest_mileage_comps": money(avg_closest) if avg_closest else "",
            "craigslist_average": craigslist_average,
            "full_price_range": full_price_range,
            "very_poor_buy_price": money(anchor * 0.55) if anchor else "",
            "good_buy_price": money(anchor * 0.72) if anchor else "",
            "excellent_buy_price": money(anchor * 0.84) if anchor else "",
        }
        return {
            "evaluation_engine": "resell",
            "mode": "zippy",
            "status": "complete",
            "provider": "Multi-source vehicle comps engine",
            "vehicle_summary": self._vehicle_summary(query),
            "parsed_details": self._query_dict(query),
            "comparable_count": len(valid),
            "source_breakdown": self._source_breakdown(valid),
            "matched_comps": [self._listing_public_dict(listing) for listing in valid[:20]],
            "values": zippy_values,
            "message": "Zippy scraped comps, averaged the market, and generated fast buy bands.",
            "assumptions": self._assumptions(query, enabled_source_keys),
        }

    def _evaluate_personal_value(self, payload: dict[str, Any]) -> dict[str, Any]:
        payload = dict(payload)
        vin_only_lookup = self._is_vin_only_lookup(payload)
        include_detailed_report = self.detailed_reports.should_generate_detailed_vehicle_report(payload)
        vehicle_input = str(payload.get("vehicle_input", "")).strip()
        if vehicle_input:
            augmented_input, extracted_pages = self.link_extractor.augment_vehicle_input(vehicle_input)
            payload["vehicle_input"] = augmented_input
            if extracted_pages:
                payload["custom_listings"] = payload.get("custom_listings") or []
                if not payload.get("asking_price"):
                    for extracted in extracted_pages:
                        asking_price = extracted.get("asking_price")
                        if asking_price:
                            payload["asking_price"] = asking_price
                            break
        query = parse_vehicle_query(payload)
        self._apply_vin_decode(query)
        enabled_source_keys = [adapter.key for adapter in self.adapters if adapter.is_enabled()]

        if not query.minimum_details_present():
            return {
                "evaluation_engine": "personal",
                "mode": "beta_v1",
                "status": "needs_more_data",
                "provider": "Multi-source vehicle comps engine",
                "vehicle_summary": self._vehicle_summary(query),
                "parsed_details": self._query_dict(query),
                "personal_value": {},
                "comparable_count": 0,
                "matched_comps": [],
                "sample_listings": [],
                "source_breakdown": [],
                "source_health": [],
                "message": "Please include the year, make, model, and mileage to value what your car should realistically sell for.",
                "assumptions": self._assumptions(query, enabled_source_keys),
            }

        source_results = self._run_sources(query, preferred_keys=self._preferred_source_keys_for_query(vin_only_lookup))
        deduped = self._dedupe_listings([
            listing
            for result in source_results
            for listing in result.normalized_listings
        ])
        deduped = self._decode_listing_vins(query, deduped)
        included, excluded = self._score_and_filter(query, deduped)
        included = self._enrich_top_listings(query, included)
        included = self._decode_listing_vins(query, included)
        included, more_excluded = self._score_and_filter(query, included)
        excluded.extend(more_excluded)

        valid = [
            listing for listing in included
            if listing.mileage is not None and self._listing_market_price(listing) is not None
        ]
        if not valid:
            fallback_priced = [
                listing for listing in included
                if self._listing_market_price(listing) is not None
            ]
            fallback_average = self.calculate_market_value(fallback_priced)
            return {
                "evaluation_engine": "personal",
                "mode": "beta_v1",
                "status": "complete",
                "provider": "Multi-source vehicle comps engine",
                "vehicle_summary": self._vehicle_summary(query),
                "parsed_details": self._query_dict(query),
                "personal_value": {
                    "estimated_personal_market_value": money(fallback_average) if fallback_average else "",
                    "average_price_of_10_closest_mileage_comps": money(fallback_average) if fallback_average else "",
                    "comp_count_used": len(fallback_priced),
                    "craigslist_average": self._craigslist_average(fallback_priced),
                    "clean_title_benchmark": money(fallback_average) if fallback_average else "",
                    "full_price_range": self._build_full_price_range(fallback_priced),
                },
                "comparable_count": len(included),
                "matched_comps": [self._listing_public_dict(listing) for listing in fallback_priced[:10]],
                "sample_listings": self._serialize_sample_listings(fallback_priced[:10]),
                "source_breakdown": self._source_breakdown(included),
                "source_health": [result.to_health_dict() for result in source_results],
                "message": "Returned the best available market comps found, even though mileage-matched comps were limited.",
                "upgrade_baseline_value": money(fallback_average) if fallback_average else "",
                "assumptions": self._assumptions(query, enabled_source_keys),
            }

        closest = sorted(
            valid,
            key=lambda listing: abs(int(listing.mileage or 0) - int(query.mileage or 0)),
        )[:10]
        closest_average = self.calculate_expected_resale_value(query.mileage or 0, valid)
        all_comps_average = self.calculate_market_value(included)
        craigslist_average = self._craigslist_average(included)
        personal_value = {
            "estimated_personal_market_value": money(all_comps_average) if all_comps_average else "",
            "average_price_of_10_closest_mileage_comps": money(closest_average),
            "comp_count_used": len(included),
            "craigslist_average": craigslist_average,
            "clean_title_benchmark": money(all_comps_average) if all_comps_average else "",
            "full_price_range": self._build_full_price_range(included),
        }
        response = {
            "evaluation_engine": "personal",
            "mode": "beta_v1",
            "status": "complete",
            "provider": "Multi-source vehicle comps engine",
            "vehicle_summary": self._vehicle_summary(query),
            "parsed_details": self._query_dict(query),
            "personal_value": personal_value,
            "comparable_count": len(included),
            "matched_comps": [self._listing_public_dict(listing) for listing in closest],
            "sample_listings": self._serialize_sample_listings(closest[:10]),
            "source_breakdown": self._source_breakdown(included),
            "source_health": [result.to_health_dict() for result in source_results],
            "message": "Personal Value Beta V1 priced your car from all valid comps found in the current market, with closest-mileage comps shown separately below.",
            "upgrade_baseline_value": money(all_comps_average) if all_comps_average else money(closest_average),
            "assumptions": self._assumptions(query, enabled_source_keys),
        }
        if include_detailed_report:
            response["detailed_vehicle_report"] = self.detailed_reports.get_detailed_vehicle_report(query, response, included)
        return response

    def run_bulk_evaluation(self, payload: dict[str, Any]) -> dict[str, Any]:
        raw_text = str(payload.get("vehicle_input", "") or payload.get("bulk_vehicle_input", "")).strip()
        if not raw_text:
            return {
                "mode": "bulk",
                "status": "needs_more_data",
                "provider": "Multi-source vehicle comps engine",
                "summary": {
                    "total_entries": 0,
                    "parsed_entries": 0,
                    "evaluated_entries": 0,
                    "skipped_entries": 0,
                    "failed_entries": 0,
                },
                "items": [],
                "notes": [],
                "message": "Paste the cars you want evaluated.",
            }

        parsed_entries = parse_bulk_vehicle_text(raw_text)
        total_entries = len(parsed_entries)
        valid_entries = [entry for entry in parsed_entries if entry.status == "parsed"]
        structured_entries_count = sum(1 for entry in parsed_entries if entry.year and entry.make and entry.model)
        skipped_items = [self._bulk_item_from_parsed_skip(entry) for entry in parsed_entries if entry.status != "parsed"]
        completed_items: list[dict[str, Any]] = []
        failed_items: list[dict[str, Any]] = []

        worker_count = min(4, len(valid_entries) or 1)
        with ThreadPoolExecutor(max_workers=worker_count) as pool:
            futures = {
                pool.submit(self._evaluate_single_vehicle_job, entry, payload): entry
                for entry in valid_entries
            }
            for future in as_completed(futures):
                entry = futures[future]
                try:
                    item = future.result()
                except Exception as exc:  # noqa: BLE001
                    LOGGER.exception("Bulk evaluation failed for %s", entry.raw_block[:120])
                    failed_items.append(
                        self._bulk_item_from_failure(entry, f"evaluation failed: {exc}")
                    )
                    continue
                if item.get("status") == "complete":
                    completed_items.append(item)
                else:
                    failed_items.append(item)

        ranked_completed = self.rank_bulk_results(completed_items)
        items = ranked_completed + failed_items + skipped_items
        summary = {
            "total_entries": total_entries,
            "parsed_entries": structured_entries_count,
            "evaluated_entries": len(ranked_completed),
            "skipped_entries": len(skipped_items),
            "failed_entries": len(failed_items),
        }
        return {
            "mode": "bulk",
            "evaluation_engine": "resell",
            "status": self._bulk_status_from_counts(summary),
            "provider": "Multi-source vehicle comps engine",
            "summary": summary,
            "items": items,
            "notes": [],
            "message": self._bulk_status_message(summary),
        }

    def _build_adapters(self) -> list[Any]:
        shared_args = (self.config, self.http_client, self.repository)
        adapters = [
            CraigslistAdapter(*shared_args),
            AutoDevAdapter(*shared_args),
            OneAutoAdapter(*shared_args),
            EbayMotorsAdapter(*shared_args),
            MarketCheckDealerAdapter(*shared_args),
            ManualImportAdapter(*shared_args),
            CustomSourceAdapter(*shared_args),
        ]
        adapters.extend(build_future_source_stubs(*shared_args))
        return adapters

    def _apply_vin_decode(self, query: VehicleQuery) -> None:
        if not query.vin or not self.vin_decoder.is_valid_vin(query.vin):
            return
        try:
            decoded = self.vin_decoder.decode(query.vin, model_year=query.year)
        except Exception as exc:  # noqa: BLE001
            LOGGER.warning("VIN decode failed for %s: %s", query.vin, exc)
            return
        if not decoded:
            return
        query.vin_decode_data = decoded
        if decoded.get("year"):
            query.year = int(decoded["year"])
        if decoded.get("make"):
            query.make = str(decoded["make"])
        if decoded.get("model"):
            query.model = str(decoded["model"])
        if decoded.get("trim"):
            query.trim = str(decoded["trim"])
        elif decoded.get("series"):
            query.trim = str(decoded["series"])
        if decoded.get("body_style"):
            query.body_style = str(decoded["body_style"])
        if decoded.get("drivetrain"):
            query.drivetrain = str(decoded["drivetrain"])
        if decoded.get("engine"):
            query.engine = str(decoded["engine"])
        if decoded.get("transmission"):
            query.transmission = str(decoded["transmission"])
        if decoded.get("fuel_type"):
            query.fuel_type = str(decoded["fuel_type"])
        query.vin_decoded_used = True
        query.vin_decode_summary = self._summarize_vin_decode(decoded)

    def _summarize_vin_decode(self, decoded: dict[str, Any]) -> dict[str, Any]:
        compact = {
            "year": decoded.get("year") or "",
            "make": decoded.get("make") or "",
            "model": decoded.get("model") or "",
            "trim": decoded.get("trim") or decoded.get("series") or "",
            "body_style": decoded.get("body_style") or "",
            "drivetrain": decoded.get("drivetrain") or "",
            "engine": decoded.get("engine") or "",
            "transmission": decoded.get("transmission") or "",
            "fuel_type": decoded.get("fuel_type") or "",
            "engine_hp": decoded.get("engine_hp") or "",
        }
        fallback_summary = " ".join(
            part for part in [
                str(compact.get("year") or ""),
                compact.get("make") or "",
                compact.get("model") or "",
                compact.get("trim") or "",
            ] if part
        ).strip()
        fallback_summary = (
            f"NHTSA decoded this VIN as {fallback_summary or 'this vehicle'}."
            f" {compact.get('engine') or 'Engine data was limited.'}"
            f" {compact.get('transmission') or ''}".strip()
        )
        prompt = (
            "You are summarizing decoded VIN data for a vehicle evaluation. "
            "Return only JSON with keys summary and highlights. "
            "summary should be one short sentence that explains what NHTSA identified. "
            "highlights should be an array of 2 to 4 short strings with the most useful specs for the evaluator. "
            f"Decoded VIN data: {json.dumps(compact, ensure_ascii=True)}"
        )
        try:
            payload = self.llm.complete_json(
                prompt=prompt,
                openai_model=os.getenv("OPENAI_SOFTWARE_CHAT_MODEL", "gpt-5.4-mini").strip() or "gpt-5.4-mini",
                source_key="vin_decode_summary",
                timeout_seconds=15,
            )
            return {
                "summary": str(payload.get("summary") or fallback_summary).strip(),
                "highlights": [
                    str(item).strip()
                    for item in (payload.get("highlights") or [])
                    if str(item).strip()
                ][:4],
            }
        except Exception:
            highlights = [
                compact.get("engine") or "",
                compact.get("drivetrain") or "",
                compact.get("transmission") or "",
                compact.get("fuel_type") or "",
            ]
            return {
                "summary": fallback_summary,
                "highlights": [item for item in highlights if item][:4],
            }

    def _run_sources(self, query: VehicleQuery, preferred_keys: list[str] | None = None) -> list[SourceRunResult]:
        source_results: list[SourceRunResult] = []
        preferred_key_set = set(preferred_keys or [])
        considered_adapters = [
            adapter for adapter in self.adapters
            if not preferred_key_set or adapter.key in preferred_key_set
        ]
        enabled_adapters = [adapter for adapter in considered_adapters if adapter.is_enabled()]
        disabled_adapters = [adapter for adapter in considered_adapters if not adapter.is_enabled()]

        for adapter in disabled_adapters:
            metadata = adapter.get_source_metadata()
            source_results.append(
                SourceRunResult(
                    metadata=metadata,
                    status="disabled",
                    message=adapter.health_check().get("message", ""),
                )
            )

        with ThreadPoolExecutor(max_workers=min(self.config.max_source_workers, len(enabled_adapters) or 1)) as pool:
            futures = {
                pool.submit(self._run_single_source, adapter, query): adapter
                for adapter in enabled_adapters
            }
            for future in as_completed(futures):
                source_results.append(future.result())

        source_results.sort(key=lambda result: result.metadata.label.lower())
        return source_results

    def _preferred_source_keys_for_query(self, vin_only_lookup: bool) -> list[str] | None:
        if not vin_only_lookup:
            return None
        return ["autodev", "marketcheck"]

    def _is_vin_only_lookup(self, payload: dict[str, Any]) -> bool:
        vehicle_input = str(payload.get("vehicle_input", "") or "").strip().upper()
        payload_vin = str(payload.get("vin", "") or "").strip().upper()
        if payload_vin and self.vin_decoder.is_valid_vin(payload_vin):
            raw_without_vin = vehicle_input.replace(payload_vin, "").strip()
            no_structured_identity = not any(
                str(payload.get(field, "") or "").strip()
                for field in ("year", "make", "model", "trim", "mileage")
            )
            return no_structured_identity and not raw_without_vin
        return bool(vehicle_input and self.vin_decoder.is_valid_vin(vehicle_input))

    def _run_single_source(self, adapter: Any, query: VehicleQuery) -> SourceRunResult:
        metadata = adapter.get_source_metadata()
        raw_listings: list[dict[str, Any]] = []
        normalized: list[NormalizedListing] = []
        status = "ok"
        message = ""
        errors: list[str] = []
        try:
            raw_listings = adapter.search_listings(query)
            for raw in raw_listings:
                listing = adapter.normalize_listing(raw, query)
                if listing is not None:
                    normalized.append(listing)
            message = f"Fetched {len(normalized)} listing(s)"
        except Exception as exc:  # noqa: BLE001
            LOGGER.exception("Source %s failed", adapter.key)
            status = "error"
            message = str(exc)
            errors.append(str(exc))

        query_hash = hashlib.sha256(query.cache_key([metadata.key]).encode("utf-8")).hexdigest()
        self.repository.store_source_run(
            query_hash=query_hash,
            source_key=metadata.key,
            status=status,
            message=message,
            raw_listings=raw_listings,
            normalized_listings=normalized,
        )
        return SourceRunResult(
            metadata=metadata,
            raw_listings=raw_listings,
            normalized_listings=normalized,
            errors=errors,
            status=status,
            message=message,
        )

    def _dedupe_listings(self, listings: list[NormalizedListing]) -> list[NormalizedListing]:
        by_key: dict[str, NormalizedListing] = {}
        for listing in listings:
            key = listing.dedupe_key()
            current = by_key.get(key)
            if current is None:
                by_key[key] = listing
                continue
            preferred = current
            alternate = listing
            if alternate.completeness_score() > current.completeness_score():
                preferred, alternate = alternate, current
            for field_name in (
                "trim", "body_style", "drivetrain", "engine", "transmission",
                "fuel_type", "mileage", "vin", "title_status", "condition",
                "dealer_name", "listing_age_days",
            ):
                if not getattr(preferred, field_name) and getattr(alternate, field_name):
                    setattr(preferred, field_name, getattr(alternate, field_name))
            preferred.image_urls = preferred.image_urls or alternate.image_urls
            preferred.metadata = {**alternate.metadata, **preferred.metadata}
            by_key[key] = preferred
        return list(by_key.values())

    def _enrich_top_listings(
        self,
        query: VehicleQuery,
        listings: list[NormalizedListing],
    ) -> list[NormalizedListing]:
        by_source: dict[str, list[NormalizedListing]] = {}
        for listing in listings:
            by_source.setdefault(listing.source, []).append(listing)
        adapter_map = {adapter.key: adapter for adapter in self.adapters}
        enriched: list[NormalizedListing] = []
        for source_key, source_listings in by_source.items():
            adapter = adapter_map.get(source_key)
            if adapter is None:
                enriched.extend(source_listings)
                continue
            try:
                enriched.extend(adapter.enrich_listings(source_listings, query))
            except Exception as exc:  # noqa: BLE001
                LOGGER.warning("Enrichment failed for %s: %s", source_key, exc)
                enriched.extend(source_listings)
        return enriched

    def _decode_listing_vins(
        self,
        query: VehicleQuery,
        listings: list[NormalizedListing],
    ) -> list[NormalizedListing]:
        candidates = [
            listing
            for listing in listings
            if listing.vin
            and self.vin_decoder.is_valid_vin(listing.vin)
            and not listing.metadata.get("vin_decoded")
            and (
                listing.spec_confidence < 0.93
                or not listing.trim
                or not listing.engine
                or not listing.transmission
                or not listing.fuel_type
                or bool(query.trim)
            )
        ][: self.config.max_vin_decodes]

        if not candidates:
            return listings

        decoded_by_vin: dict[str, dict[str, Any]] = {}
        with ThreadPoolExecutor(max_workers=min(6, len(candidates) or 1)) as pool:
            futures = {
                pool.submit(self.vin_decoder.decode, listing.vin, listing.year or query.year): listing.vin
                for listing in candidates
            }
            for future in as_completed(futures):
                vin = futures[future]
                try:
                    decoded = future.result()
                except Exception as exc:  # noqa: BLE001
                    LOGGER.warning("Listing VIN decode failed for %s: %s", vin, exc)
                    continue
                if decoded:
                    decoded_by_vin[vin] = decoded

        for listing in listings:
            decoded = decoded_by_vin.get(listing.vin)
            if not decoded:
                continue
            self._merge_decoded_listing(listing, decoded)

        return listings

    def _merge_decoded_listing(self, listing: NormalizedListing, decoded: dict[str, Any]) -> None:
        for field_name in (
            "year",
            "make",
            "model",
            "trim",
            "body_style",
            "drivetrain",
            "engine",
            "transmission",
            "fuel_type",
        ):
            value = decoded.get(field_name)
            if value in ("", None):
                continue
            setattr(listing, field_name, value)
        listing.metadata["vin_decoded"] = True
        if decoded.get("error_code") not in {"", None, "0"}:
            listing.metadata["vin_decode_warning"] = decoded.get("error_code")
        listing.spec_confidence = max(listing.spec_confidence, 0.98)

    def _score_and_filter(
        self,
        query: VehicleQuery,
        listings: list[NormalizedListing],
    ) -> tuple[list[NormalizedListing], list[dict[str, Any]]]:
        excluded: list[dict[str, Any]] = []
        scored: list[NormalizedListing] = []
        for listing in listings:
            if listing.price is None or listing.price < 500:
                excluded.append(self._excluded_listing(listing, "invalid or missing price"))
                continue
            score, tier, reasons = score_listing(query, listing)
            listing.relevance_score = score
            listing.match_tier = tier
            listing.metadata["match_reasons"] = reasons
            if score < 38:
                excluded.append(self._excluded_listing(listing, "relevance score too low"))
                continue
            scored.append(listing)

        if not scored:
            return [], excluded

        mileage_rate = infer_mileage_adjustment_rate(scored)
        for listing in scored:
            listing.adjusted_price, listing.adjustment_notes = apply_adjustments(query, listing, mileage_rate)

        adjusted_prices = sorted(
            listing.adjusted_price for listing in scored if listing.adjusted_price is not None
        )
        if len(adjusted_prices) >= 6:
            middle = percentile(adjusted_prices, 0.5)
            low_cut = max(1000.0, middle * 0.4)
            high_cut = middle * 1.9
            kept: list[NormalizedListing] = []
            for listing in scored:
                adjusted_price = listing.adjusted_price or 0.0
                if low_cut <= adjusted_price <= high_cut:
                    kept.append(listing)
                else:
                    excluded.append(self._excluded_listing(listing, "price outlier after adjustments"))
            scored = kept

        scored.sort(key=lambda listing: (listing.adjusted_price or listing.price or 0.0))
        return scored, excluded

    def _build_needs_more_data_response(
        self,
        query: VehicleQuery,
        enabled_sources: list[str],
    ) -> dict[str, Any]:
        return {
            "evaluation_engine": "resell",
            "status": "needs_more_data",
            "provider": "Multi-source vehicle comps engine",
            "vehicle_summary": self._vehicle_summary(query),
            "parsed_details": self._query_dict(query),
            "values": {},
            "title_adjustment": self._empty_title_adjustment(query),
            "listing_price_analysis": self._empty_listing_price_analysis(query, insufficient_data=True),
            "overall_range": {},
            "sample_listings": [],
            "comparable_count": 0,
            "matched_comps": [],
            "normalized_comps": [],
            "excluded_comps": [],
            "price_distribution": {},
            "average_price_near_mileage": self._average_price_near_mileage(query, []),
            "recommended_max_buy_price": "",
            "recommended_target_resale_range": {},
            "gross_spread_estimate": "",
            "confidence_score": 5,
            "source_breakdown": [],
            "source_adapter_breakdown": [{"label": key, "count": 0} for key in enabled_sources],
            "source_health": [adapter.health_check() for adapter in self.adapters],
            "assumptions": self._assumptions(query, enabled_sources),
            "message": "Please make sure you include the year, make, model, and mileage so the engine knows what vehicle to evaluate.",
        }

    def _build_low_data_response(
        self,
        query: VehicleQuery,
        source_results: list[SourceRunResult],
        included: list[NormalizedListing],
        excluded: list[dict[str, Any]],
        enabled_sources: list[str],
    ) -> dict[str, Any]:
        market_value = self.calculate_market_value(included)
        safe_buy_value = self.calculate_safe_buy_value(included) if included else 0.0
        expected_resale_value = self.calculate_expected_resale_value(query.mileage or 0, included) if included else 0.0
        estimated_profit = self.calculate_estimated_profit(expected_resale_value, safe_buy_value) if included else 0.0
        title_adjustment = self._build_title_adjustment_projection(
            market_value=market_value,
            expected_resale_low=expected_resale_value or market_value,
            expected_resale_high=expected_resale_value or market_value,
        ) if market_value else self._empty_title_adjustment(query)
        return {
            "evaluation_engine": "resell",
            "status": "complete",
            "provider": "Multi-source vehicle comps engine",
            "vehicle_summary": self._vehicle_summary(query),
            "parsed_details": self._query_dict(query),
            "values": {},
            "title_adjustment": title_adjustment,
            "listing_price_analysis": self._build_listing_price_analysis(
                query,
                market_value=market_value,
                safe_buy_price=safe_buy_value,
                expected_resale_low=expected_resale_value or market_value,
                expected_resale_high=expected_resale_value or market_value,
            ) if market_value else self._empty_listing_price_analysis(query, insufficient_data=True),
            "overall_range": self._build_overall_range(
                {},
                included,
                market_value,
                safe_buy_value,
                expected_resale_value or market_value,
                estimated_profit,
                query.mileage,
                title_adjustment.get("rebuilt_title_average", "") if isinstance(title_adjustment, dict) else "",
            ) if market_value else {},
            "craigslist_average": self._craigslist_average(included),
            "sample_listings": self._serialize_sample_listings(included[:8]),
            "comparable_count": len(included),
            "matched_comps": [self._listing_public_dict(listing) for listing in included],
            "normalized_comps": [self._listing_public_dict(listing) for listing in included],
            "excluded_comps": excluded[:25],
            "price_distribution": {},
            "average_price_near_mileage": self._average_price_near_mileage(query, included),
            "recommended_max_buy_price": "",
            "recommended_target_resale_range": {},
            "gross_spread_estimate": "",
            "confidence_score": compute_confidence(included, self._active_source_count(source_results)),
            "source_breakdown": self._source_breakdown(included),
            "source_adapter_breakdown": self._source_adapter_breakdown(included),
            "source_health": [result.to_health_dict() for result in source_results],
            "assumptions": self._assumptions(query, enabled_sources),
            "message": (
                "Returned the best available comp data from the sources found, even though mileage alignment was lighter than ideal."
            ),
        }

    def _build_success_response(
        self,
        query: VehicleQuery,
        source_results: list[SourceRunResult],
        listings: list[NormalizedListing],
        excluded: list[dict[str, Any]],
    ) -> dict[str, Any]:
        raw_prices = [listing.price for listing in listings if listing.price is not None]
        adjusted_prices = [self._listing_market_price(listing) for listing in listings if self._listing_market_price(listing) is not None]
        valid_mileage_comps = [
            listing for listing in listings
            if listing.mileage is not None and self._listing_market_price(listing) is not None
        ]
        if not raw_prices or not adjusted_prices or not valid_mileage_comps:
            return self._build_low_data_response(
                query,
                source_results,
                listings,
                excluded,
                [adapter.key for adapter in self.adapters if adapter.is_enabled()],
            )
        raw_median = median(raw_prices)
        trimmed_adjusted = adjusted_prices[:]
        if len(trimmed_adjusted) > 6:
            trimmed_adjusted = sorted(trimmed_adjusted)[1:-1]
        trimmed_median = median(trimmed_adjusted)
        market_value = self.calculate_market_value(listings)
        safe_buy_value = self.calculate_safe_buy_value(listings)
        expected_resale_value = self.calculate_expected_resale_value(query.mileage or 0, listings)
        estimated_profit = self.calculate_estimated_profit(expected_resale_value, safe_buy_value)
        confidence = compute_confidence(listings, self._active_source_count(source_results))

        condition_values = self._build_condition_ranges(listings)
        title_adjustment = self._build_title_adjustment_projection(
            market_value=market_value,
            expected_resale_low=expected_resale_value,
            expected_resale_high=expected_resale_value,
        )
        response = {
            "evaluation_engine": "resell",
            "status": "complete",
            "provider": "Multi-source vehicle comps engine",
            "vehicle_summary": self._vehicle_summary(query),
            "parsed_details": self._query_dict(query),
            "values": condition_values,
            "title_adjustment": title_adjustment,
            "listing_price_analysis": self._build_listing_price_analysis(
                query,
                market_value=market_value,
                safe_buy_price=safe_buy_value,
                expected_resale_low=expected_resale_value,
                expected_resale_high=expected_resale_value,
            ),
            "overall_range": self._build_overall_range(
                condition_values,
                listings,
                market_value,
                safe_buy_value,
                expected_resale_value,
                estimated_profit,
                query.mileage,
                title_adjustment.get("rebuilt_title_average", ""),
            ),
            "craigslist_average": self._craigslist_average(listings),
            "sample_listings": self._serialize_sample_listings(listings[:8]),
            "comparable_count": len(listings),
            "matched_comps": [self._listing_public_dict(listing) for listing in listings],
            "normalized_comps": [self._listing_public_dict(listing) for listing in listings],
            "excluded_comps": excluded[:25],
            "price_distribution": {
                "raw_median": money(raw_median),
                "trimmed_median": money(trimmed_median),
                "weighted_median": money(market_value),
                "histogram": self._histogram(adjusted_prices),
                "price_vs_mileage": self._price_vs_mileage(listings),
            },
            "average_price_near_mileage": self._average_price_near_mileage(query, listings),
            "mileage_price_bands": self._mileage_price_bands(listings),
            "adjusted_price_estimate": {
                "weighted_median": money(market_value),
                "trimmed_median": money(expected_resale_value),
            },
            "recommended_max_buy_price": money(safe_buy_value),
            "recommended_target_resale_range": {
                "low": money(expected_resale_value),
                "high": money(expected_resale_value),
            },
            "gross_spread_estimate": money(estimated_profit),
            "confidence_score": confidence,
            "source_breakdown": self._source_breakdown(listings),
            "source_adapter_breakdown": self._source_adapter_breakdown(listings),
            "source_health": [result.to_health_dict() for result in source_results],
            "assumptions": self._assumptions(
                query,
                [adapter.key for adapter in self.adapters if adapter.is_enabled()],
            ),
            "message": self._success_message(source_results),
        }
        if self._is_rebuilt_title(query):
            response = self._apply_rebuilt_title_adjustment(response)
        return response

    def get_potential_upgrade_candidates(
        self,
        *,
        baseline_value: float,
        body_style: str = "",
        focus: str = "",
        vehicle_context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        min_price = max(1000, int(baseline_value // 500) * 500)
        max_price = min_price + 10000
        context = self._sanitize_upgrade_context(vehicle_context or {})
        class_specs = self._upgrade_class_specs()
        inferred_focus = focus or self._preferred_upgrade_focus(context)
        preferred_classes = self._preferred_upgrade_classes(context)
        grouped_candidates: dict[str, list[NormalizedListing]] = {}

        for class_key, class_spec in class_specs.items():
            candidates = self._fetch_marketcheck_upgrade_candidates(
                min_price=min_price,
                max_price=max_price,
                vehicle_context=context,
                class_key=class_key,
                body_variants=class_spec["body_variants"],
            )
            if inferred_focus:
                candidates = [
                    listing for listing in candidates
                    if inferred_focus.lower() in self._upgrade_focus_tags(listing)
                ]
            grouped_candidates[class_key] = self._rank_upgrade_candidates(
                candidates,
                baseline_value=baseline_value,
                vehicle_context=context,
                class_key=class_key,
            )[:10]

        visible_class_keys = [body_style.lower()] if body_style and body_style.lower() in class_specs else preferred_classes
        classes = []
        for class_key in visible_class_keys:
            ranked = grouped_candidates.get(class_key, [])
            class_spec = class_specs[class_key]
            classes.append({
                "key": class_key,
                "label": class_spec["label"],
                "items": [self._upgrade_candidate_dict(listing, index + 1) for index, listing in enumerate(ranked)],
            })

        available_body_styles = list(class_specs.keys())
        available_focuses = ["sporty", "luxury", "spacious", "transporting space"]

        return {
            "baseline_value": money(baseline_value),
            "price_range": {"low": money(min_price), "high": money(max_price)},
            "vehicle_context": context,
            "filters": {
                "body_styles": available_body_styles,
                "focuses": available_focuses,
                "selected_body_style": body_style.lower() if body_style else "",
                "selected_focus": inferred_focus,
            },
            "classes": classes,
        }

    def _upgrade_class_specs(self) -> dict[str, dict[str, Any]]:
        return {
            "sedan": {"label": "Sedan", "body_variants": ["sedan"]},
            "coupe": {"label": "Coupe", "body_variants": ["coupe", "convertible", "hatchback"]},
            "suv": {"label": "SUV", "body_variants": ["suv", "wagon", "crossover"]},
            "truck": {"label": "Truck", "body_variants": ["truck", "pickup"]},
        }

    def _sanitize_upgrade_context(self, vehicle_context: dict[str, Any]) -> dict[str, Any]:
        return {
            "year": int(vehicle_context.get("year")) if str(vehicle_context.get("year") or "").isdigit() else None,
            "make": str(vehicle_context.get("make") or "").strip(),
            "model": str(vehicle_context.get("model") or "").strip(),
            "trim": str(vehicle_context.get("trim") or "").strip(),
            "body_style": str(vehicle_context.get("body_style") or "").strip().lower(),
            "state": str(vehicle_context.get("state") or "").strip().upper(),
            "zip_code": str(vehicle_context.get("zip_code") or "").strip(),
        }

    def _preferred_upgrade_focus(self, vehicle_context: dict[str, Any]) -> str:
        current_text = " ".join(
            [
                str(vehicle_context.get("make") or ""),
                str(vehicle_context.get("model") or ""),
                str(vehicle_context.get("trim") or ""),
                str(vehicle_context.get("body_style") or ""),
            ]
        ).lower()
        if any(token in current_text for token in ["m340", "m240", "m3", "m4", "m5", "rs", "amg", "s-line", "type r", "gti", "wrx", "sti", "ss"]):
            return "sporty"
        if any(token in current_text for token in ["audi", "bmw", "mercedes", "lexus", "acura", "genesis", "infiniti", "cadillac", "lincoln", "porsche"]):
            return "luxury"
        body = str(vehicle_context.get("body_style") or "").lower()
        if body in {"suv", "crossover", "wagon", "van"} or any(token in current_text for token in ["kicks", "rogue", "cr-v", "rav4", "cx-5", "explorer", "pilot", "highlander"]):
            return "spacious"
        if body in {"truck", "pickup"}:
            return "transporting space"
        return ""

    def _preferred_upgrade_classes(self, vehicle_context: dict[str, Any]) -> list[str]:
        current_text = " ".join(
            [
                str(vehicle_context.get("make") or ""),
                str(vehicle_context.get("model") or ""),
                str(vehicle_context.get("trim") or ""),
                str(vehicle_context.get("body_style") or ""),
            ]
        ).lower()
        body = str(vehicle_context.get("body_style") or "").lower()
        if any(token in current_text for token in ["m340", "m240", "m3", "m4", "m5", "rs", "amg", "gti", "wrx", "sti", "type r", "ss"]):
            return ["sedan", "coupe"]
        if body in {"truck", "pickup"}:
            return ["truck", "suv"]
        if body in {"suv", "crossover", "wagon", "van"} or any(token in current_text for token in ["kicks", "rogue", "cr-v", "rav4", "cx-5", "explorer", "pilot", "highlander"]):
            return ["suv"]
        return ["sedan", "coupe", "suv"]

    def _fetch_marketcheck_upgrade_candidates(
        self,
        *,
        min_price: int,
        max_price: int,
        vehicle_context: dict[str, Any],
        class_key: str,
        body_variants: list[str],
    ) -> list[NormalizedListing]:
        marketcheck_adapter = next((adapter for adapter in self.adapters if adapter.key == "marketcheck" and adapter.is_enabled()), None)

        variants: list[dict[str, Any]] = []
        base = {
            "api_key": self.config.marketcheck_api_key,
            "rows": 90,
            "car_type": "used",
            "price_range": f"{min_price}-{max_price}",
        }
        for body_variant in body_variants:
            params = {**base, "body_type": body_variant}
            if vehicle_context.get("zip_code"):
                params["zip"] = vehicle_context["zip_code"]
                params["radius"] = 75
            elif vehicle_context.get("state"):
                params["state"] = vehicle_context["state"]
            variants.append(params)
            if "zip" in params:
                broader = dict(params)
                broader.pop("zip", None)
                broader.pop("radius", None)
                variants.append(broader)
        variants.append(base)

        normalized: list[NormalizedListing] = []
        seen_params: set[str] = set()
        dummy_query = VehicleQuery()
        for params in variants:
            signature = json.dumps(params, sort_keys=True)
            if signature in seen_params:
                continue
            seen_params.add(signature)
            if marketcheck_adapter is None:
                break
            try:
                payload = self.http_client.get_json(
                    "https://api.marketcheck.com/v2/search/car/active",
                    params=params,
                    source_key="marketcheck",
                )
            except Exception as exc:  # noqa: BLE001
                LOGGER.warning("Potential upgrades MarketCheck fetch failed for %s: %s", class_key, exc)
                continue
            listings = payload.get("listings") or payload.get("data") or []
            for raw in listings:
                if not isinstance(raw, dict):
                    continue
                item = marketcheck_adapter.normalize_listing(raw, dummy_query)
                if item is None:
                    continue
                normalized.append(item)
            if len(normalized) >= 30:
                break

        cached_payloads = self.repository.get_upgrade_candidate_payloads(
            min_price=min_price,
            max_price=max_price,
            body_variants=body_variants,
            state=str(vehicle_context.get("state") or ""),
            exclude_make=str(vehicle_context.get("make") or ""),
            exclude_model=str(vehicle_context.get("model") or ""),
            limit=220,
        )
        if len(cached_payloads) < 24:
            cached_payloads.extend(
                self.repository.get_upgrade_candidate_payloads(
                    min_price=min_price,
                    max_price=max_price,
                    body_variants=body_variants,
                    state="",
                    exclude_make=str(vehicle_context.get("make") or ""),
                    exclude_model=str(vehicle_context.get("model") or ""),
                    limit=220,
                )
            )
        for raw in cached_payloads:
            if not isinstance(raw, dict):
                continue
            item = marketcheck_adapter.normalize_listing(raw, dummy_query) if marketcheck_adapter is not None else None
            if item is None:
                item = self._listing_from_payload(raw)
            if item is None:
                continue
            normalized.append(item)

        deduped = self._dedupe_listings(normalized)
        current_make = str(vehicle_context.get("make") or "").lower()
        current_model = str(vehicle_context.get("model") or "").lower()
        return [
            listing for listing in deduped
            if self._listing_market_price(listing) is not None
            and min_price <= (self._listing_market_price(listing) or 0) <= max_price
            and self._classify_upgrade_body(listing) == class_key
            and not (
                current_make
                and current_model
                and str(listing.make or "").lower() == current_make
                and str(listing.model or "").lower() == current_model
            )
        ]

    def _rank_upgrade_candidates(
        self,
        listings: list[NormalizedListing],
        *,
        baseline_value: float,
        vehicle_context: dict[str, Any],
        class_key: str,
    ) -> list[NormalizedListing]:
        scored: list[tuple[float, NormalizedListing]] = []
        price_cap = baseline_value + 10000
        for listing in listings:
            score_breakdown = self._upgrade_score_breakdown(listing, baseline_value, price_cap, vehicle_context, class_key)
            listing.metadata["upgrade_scores"] = score_breakdown
            listing.metadata["upgrade_focus_tags"] = sorted(self._upgrade_focus_tags(listing))
            listing.metadata["upgrade_blurb"] = self._upgrade_blurb(listing, score_breakdown)
            scored.append((score_breakdown["total"], listing))

        ranked = [listing for _, listing in sorted(scored, key=lambda item: (-item[0], self._listing_market_price(item[1]) or 0.0))]
        reranked = self._llm_rerank_upgrade_candidates(ranked[:14], vehicle_context, class_key)
        return reranked + [listing for listing in ranked if listing not in reranked]

    def _upgrade_score_breakdown(
        self,
        listing: NormalizedListing,
        baseline_value: float,
        price_cap: float,
        vehicle_context: dict[str, Any],
        class_key: str,
    ) -> dict[str, float]:
        market_price = self._listing_market_price(listing) or 0.0
        price_span = max(price_cap - baseline_value, 1.0)
        price_position = max(0.0, min(1.0, (market_price - baseline_value) / price_span))
        value_score = max(45.0, 100.0 - (price_position * 55.0))
        performance_score = self._upgrade_performance_score(listing)
        luxury_score = self._upgrade_luxury_score(listing)
        reliability_score = self._upgrade_reliability_score(listing)
        upgrade_bonus = self._upgrade_bonus(listing, vehicle_context, class_key, price_position)
        total = (
            value_score * 0.27
            + performance_score * 0.24
            + luxury_score * 0.18
            + reliability_score * 0.17
            + upgrade_bonus * 0.14
        )
        return {
            "price": round(value_score, 1),
            "value": round(value_score, 1),
            "performance": round(performance_score, 1),
            "luxury": round(luxury_score, 1),
            "reliability": round(reliability_score, 1),
            "upgrade_fit": round(upgrade_bonus, 1),
            "total": round(total, 1),
        }

    def _upgrade_performance_score(self, listing: NormalizedListing) -> float:
        text = " ".join([str(listing.make or ""), str(listing.model or ""), str(listing.trim or ""), str(listing.engine or "")]).lower()
        score = 40.0
        if any(token in text for token in ["turbo", "twin turbo", "v6", "v8", "hybrid max", "ecoboost"]):
            score += 18
        if any(token in text for token in ["rs", "amg", "m ", "m3", "m340", "stype", "s-line", "type r", "sti", "wrx", "gti", "gt", "ss", "zl1", "trx", "raptor"]):
            score += 28
        if self._classify_upgrade_body(listing) in {"coupe", "sedan"}:
            score += 6
        return min(score, 100.0)

    def _upgrade_luxury_score(self, listing: NormalizedListing) -> float:
        make = str(listing.make or "").lower()
        text = " ".join([make, str(listing.model or ""), str(listing.trim or "")]).lower()
        premium_makes = {"audi", "bmw", "mercedes-benz", "mercedes", "lexus", "genesis", "acura", "infiniti", "cadillac", "lincoln", "land rover", "porsche"}
        near_premium = {"mazda", "volvo", "buick"}
        score = 35.0
        if make in premium_makes:
            score += 42
        elif make in near_premium:
            score += 20
        if any(token in text for token in ["platinum", "premium", "prestige", "signature", "limited", "touring", "reserve", "denali"]):
            score += 16
        return min(score, 100.0)

    def _upgrade_reliability_score(self, listing: NormalizedListing) -> float:
        make = str(listing.make or "").lower()
        ratings = {
            "toyota": 92,
            "lexus": 92,
            "honda": 89,
            "acura": 86,
            "mazda": 86,
            "subaru": 81,
            "hyundai": 78,
            "kia": 78,
            "nissan": 72,
            "ford": 70,
            "chevrolet": 69,
            "gmc": 68,
            "audi": 64,
            "bmw": 63,
            "mercedes-benz": 60,
            "mercedes": 60,
            "volkswagen": 62,
            "porsche": 67,
            "jeep": 56,
            "land rover": 48,
            "ram": 63,
        }
        return float(ratings.get(make, 66))

    def _upgrade_bonus(
        self,
        listing: NormalizedListing,
        vehicle_context: dict[str, Any],
        class_key: str,
        price_position: float,
    ) -> float:
        current_text = " ".join(
            [
                str(vehicle_context.get("make") or ""),
                str(vehicle_context.get("model") or ""),
                str(vehicle_context.get("trim") or ""),
                str(vehicle_context.get("body_style") or ""),
            ]
        ).lower()
        current_is_sporty = any(token in current_text for token in ["m", "rs", "amg", "type r", "si", "wrx", "gti", "gt"])
        current_is_luxury = any(token in current_text for token in ["audi", "bmw", "mercedes", "lexus", "acura", "genesis", "infiniti", "cadillac"])
        listing_focuses = self._upgrade_focus_tags(listing)
        score = 52.0
        if current_is_sporty and "sporty" in listing_focuses:
            score += 20
        if current_is_sporty and "sporty" not in listing_focuses:
            score -= 18
        if current_is_luxury and "luxury" in listing_focuses:
            score += 18
        if current_is_luxury and "luxury" not in listing_focuses:
            score -= 10
        if current_is_sporty and self._upgrade_performance_score(listing) >= 78:
            score += 12
        if current_is_luxury and self._upgrade_luxury_score(listing) >= 78:
            score += 10
        if not current_is_sporty and not current_is_luxury and class_key == "suv" and "spacious" in listing_focuses:
            score += 14
        if not current_is_sporty and not current_is_luxury and class_key != "suv" and "spacious" in listing_focuses:
            score -= 8
        if not current_is_sporty and class_key == "truck" and "transporting space" in listing_focuses:
            score += 12
        current_body = str(vehicle_context.get("body_style") or "").lower()
        if current_body and current_body != class_key:
            score += 5
        current_year = vehicle_context.get("year")
        if isinstance(current_year, int) and listing.year and listing.year >= current_year:
            score += min(8, (listing.year - current_year) * 2)
        score += min(8, price_position * 10)
        sticker_text = " ".join([str(listing.make or ""), str(listing.model or ""), str(listing.trim or ""), str(listing.engine or "")]).lower()
        if any(token in sticker_text for token in ["rs", "amg", "m5", "m3", "m4", "c63", "ct4-v", "ct5-v", "s4", "s5", "s6", "s7", "s8", "sq5", "macan", "x3 m40", "x5", "trackhawk", "trx", "raptor", "hellcat"]):
            score += 14
        if current_is_sporty and any(token in sticker_text for token in ["rs3", "rs5", "c63", "m5", "m3", "m4", "ct4-v", "ct5-v", "s4", "s5", "s7", "x3 m40", "macan", "giulia quadrifoglio"]):
            score += 18
        if not current_is_sporty and not current_is_luxury and any(token in sticker_text for token in ["explorer", "pilot", "highlander", "telluride", "palisade", "grand cherokee", "q7", "x5", "mdx"]):
            score += 14
        return min(score, 100.0)

    def _classify_upgrade_body(self, listing: NormalizedListing) -> str:
        body = str(listing.body_style or "").lower()
        if any(token in body for token in ["truck", "pickup"]):
            return "truck"
        if any(token in body for token in ["suv", "crossover", "wagon"]):
            return "suv"
        if any(token in body for token in ["coupe", "convertible", "hatchback"]):
            return "coupe"
        return "sedan"

    def _upgrade_blurb(self, listing: NormalizedListing, score_breakdown: dict[str, float]) -> str:
        focuses = self._upgrade_focus_tags(listing)
        if "sporty" in focuses and "luxury" in focuses:
            return "Blends premium feel with real performance upside in this price band."
        if "sporty" in focuses:
            return "Leans performance-first while still staying in a realistic used-market range."
        if "luxury" in focuses:
            return "Feels like a clear luxury step up without jumping far outside the value band."
        if "spacious" in focuses:
            return "Adds room and everyday utility while still landing as an upgrade for the money."
        if score_breakdown.get("reliability", 0) >= 80:
            return "Scores as a safer long-term step up with strong reliability value."
        return "Looks like a practical next-step upgrade for this budget window."

    def _llm_rerank_upgrade_candidates(
        self,
        listings: list[NormalizedListing],
        vehicle_context: dict[str, Any],
        class_key: str,
    ) -> list[NormalizedListing]:
        if not listings:
            return []
        model = os.getenv("OPENAI_SOFTWARE_CHAT_MODEL", "gpt-5.4-mini").strip() or "gpt-5.4-mini"
        payload_items = []
        for index, listing in enumerate(listings, start=1):
            payload_items.append({
                "id": index,
                "vehicle": " ".join(part for part in [str(listing.year or ""), listing.make, listing.model, listing.trim] if part).strip(),
                "price": self._listing_market_price(listing) or 0.0,
                "body_style": listing.body_style,
                "scores": listing.metadata.get("upgrade_scores") or {},
                "focus_tags": sorted(self._upgrade_focus_tags(listing)),
            })
        prompt = (
            "You are ranking used-car upgrade recommendations. "
            "Return only JSON with shape {\"ordered_ids\":[...]} using the candidate ids in best-upgrade order. "
            "Favor realistic upgrades for the current car owner using price, value, performance, luxury, and reliability. "
            f"Current vehicle: {json.dumps(vehicle_context, ensure_ascii=True)}. "
            f"Class: {class_key}. Candidates: {json.dumps(payload_items, ensure_ascii=True)}"
        )
        try:
            data = self.llm.complete_json(
                prompt=prompt,
                openai_model=model,
                source_key="upgrade_ranking_llm",
                timeout_seconds=20,
            )
            ordered_ids = [int(value) for value in data.get("ordered_ids") or [] if str(value).isdigit()]
        except Exception as exc:  # noqa: BLE001
            LOGGER.warning("Upgrade reranking LLM fallback triggered: %s", exc)
            return []
        by_id = {index: listing for index, listing in enumerate(listings, start=1)}
        return [by_id[item_id] for item_id in ordered_ids if item_id in by_id]

    def _upgrade_focus_tags(self, listing: NormalizedListing) -> set[str]:
        tags: set[str] = set()
        text = " ".join(
            str(value or "").lower()
            for value in [listing.make, listing.model, listing.trim, listing.body_style]
        )
        body_style = str(listing.body_style or "").lower()
        if body_style in {"coupe", "convertible", "hatchback"} or any(token in text for token in ["sport", "gt", "si", "type r", "st", "rs", "m ", "amg", "s-line"]):
            tags.add("sporty")
        if any(token in text for token in ["audi", "bmw", "mercedes", "lexus", "acura", "infiniti", "cadillac", "genesis", "lincoln"]):
            tags.add("luxury")
        if body_style in {"suv", "wagon", "van"}:
            tags.add("spacious")
        if body_style in {"suv", "truck", "wagon", "van", "hatchback"}:
            tags.add("transporting space")
        return tags

    def _upgrade_candidate_dict(self, listing: NormalizedListing, rank: int) -> dict[str, Any]:
        return {
            **self._listing_public_dict(listing),
            "rank": rank,
            "focus_tags": sorted(self._upgrade_focus_tags(listing)),
            "upgrade_scores": listing.metadata.get("upgrade_scores") or {},
            "upgrade_blurb": listing.metadata.get("upgrade_blurb") or "",
        }

    def _listing_from_payload(self, payload: dict[str, Any]) -> NormalizedListing | None:
        try:
            return NormalizedListing(
                source=str(payload.get("source") or "cached"),
                source_listing_id=str(payload.get("source_listing_id") or payload.get("vin") or payload.get("url") or ""),
                source_label=str(payload.get("source_label") or payload.get("source") or "Cached Market"),
                url=str(payload.get("url") or "").strip(),
                fetched_at=str(payload.get("fetched_at") or datetime.now(timezone.utc).isoformat()),
                year=self._payload_to_int(payload.get("year")),
                make=str(payload.get("make") or "").strip(),
                model=str(payload.get("model") or "").strip(),
                trim=str(payload.get("trim") or "").strip(),
                body_style=str(payload.get("body_style") or "").strip(),
                drivetrain=str(payload.get("drivetrain") or "").strip(),
                engine=str(payload.get("engine") or "").strip(),
                transmission=str(payload.get("transmission") or "").strip(),
                fuel_type=str(payload.get("fuel_type") or "").strip(),
                exterior_color=str(payload.get("exterior_color") or "").strip(),
                mileage=self._payload_to_int(payload.get("mileage")),
                price=self._payload_to_float(payload.get("price")),
                seller_type=str(payload.get("seller_type") or "").strip(),
                location=payload.get("location") if isinstance(payload.get("location"), dict) else {},
                vin=str(payload.get("vin") or "").strip().upper(),
                title_status=str(payload.get("title_status") or "").strip(),
                condition=str(payload.get("condition") or "").strip(),
                listing_age_days=self._payload_to_int(payload.get("listing_age_days")),
                dealer_name=str(payload.get("dealer_name") or "").strip(),
                image_urls=list(payload.get("image_urls") or []),
                raw_payload=payload,
                spec_confidence=float(payload.get("spec_confidence") or 0.0),
                relevance_score=float(payload.get("relevance_score") or 0.0),
                match_tier=str(payload.get("match_tier") or "Tier 3"),
                adjusted_price=self._payload_to_float(payload.get("adjusted_price")),
                adjustment_notes=list(payload.get("adjustment_notes") or []),
                exclude_reason=str(payload.get("exclude_reason") or ""),
                metadata=payload.get("metadata") if isinstance(payload.get("metadata"), dict) else {},
            )
        except Exception:
            return None

    def _payload_to_int(self, value: Any) -> int | None:
        try:
            if value in (None, ""):
                return None
            return int(float(str(value)))
        except Exception:
            return None

    def _payload_to_float(self, value: Any) -> float | None:
        try:
            if value in (None, ""):
                return None
            return float(str(value).replace("$", "").replace(",", ""))
        except Exception:
            return None

    def _evaluate_single_vehicle_job(
        self,
        entry: ParsedBulkVehicle,
        bulk_payload: dict[str, Any],
    ) -> dict[str, Any]:
        payload = {
            **entry.to_payload(),
            "force_refresh": bool(bulk_payload.get("force_refresh")),
            "evaluation_mode": "individual",
            "detailed_vehicle_report": bulk_payload.get("detailed_vehicle_report", ""),
        }
        result = self._evaluate_single(payload)
        if result.get("status") != "complete":
            message = str(result.get("message") or "evaluation failed").strip()
            return self._bulk_item_from_failure(entry, message)
        return self._bulk_item_from_result(entry, result)

    def rank_bulk_results(self, items: list[dict[str, Any]]) -> list[dict[str, Any]]:
        ranked = []
        for item in items:
            score = self._bulk_rank_score(item)
            updated = dict(item)
            updated["bulk_rank_score"] = round(score, 2)
            ranked.append(updated)
        ranked.sort(
            key=lambda item: (
                -(item.get("bulk_rank_score") or 0.0),
                -self._money_to_float(item.get("estimated_profit", "")),
                -float(item.get("confidence_score") or 0),
                item.get("vehicle_name", ""),
            )
        )
        for index, item in enumerate(ranked, start=1):
            item["rank"] = index
        return ranked

    def _bulk_item_from_result(self, entry: ParsedBulkVehicle, result: dict[str, Any]) -> dict[str, Any]:
        parsed_details = result.get("parsed_details") or {}
        overall = result.get("overall_range") or {}
        resale_range = result.get("recommended_target_resale_range") or {}
        risk = self._bulk_risk_label(float(result.get("confidence_score") or 0))
        vehicle_name = " ".join(
            part
            for part in [
                str(parsed_details.get("year") or ""),
                str(parsed_details.get("make") or ""),
                str(parsed_details.get("model") or ""),
                str(parsed_details.get("trim") or ""),
            ]
            if part
        ).strip() or self._vehicle_summary_from_entry(entry)
        listed_price = parsed_details.get("asking_price")
        if listed_price in ("", None):
            listed_price = entry.listed_price
        listed_price_text = money(float(listed_price)) if isinstance(listed_price, (int, float)) else (
            money(float(listed_price)) if str(listed_price or "").replace(".", "", 1).isdigit() else ""
        )
        return {
            "status": "complete",
            "vehicle_name": vehicle_name,
            "listed_price": listed_price_text,
            "market_value": overall.get("market_value", ""),
            "craigslist_average": result.get("craigslist_average", ""),
            "full_price_range": overall.get("full_price_range", ""),
            "safe_buy_value": overall.get("safe_buy_value", ""),
            "expected_resale_value": overall.get("expected_resale_value", "") or resale_range.get("low", ""),
            "estimated_profit": overall.get("estimated_profit", "") or result.get("gross_spread_estimate", ""),
            "confidence": f'{int(result.get("confidence_score") or 0)}%',
            "confidence_score": int(result.get("confidence_score") or 0),
            "risk": risk,
            "comp_count": int(result.get("comparable_count") or 0),
            "location": entry.area or self._location_from_result(result),
            "reason": "",
            "raw_input": entry.raw_block,
            "detailed_vehicle_report": result.get("detailed_vehicle_report") or {},
        }

    def _bulk_item_from_parsed_skip(self, entry: ParsedBulkVehicle) -> dict[str, Any]:
        return {
            "status": "skipped",
            "vehicle_name": self._vehicle_summary_from_entry(entry),
            "listed_price": money(entry.listed_price) if isinstance(entry.listed_price, (int, float)) else "",
            "market_value": "",
            "safe_buy_value": "",
            "expected_resale_value": "",
            "estimated_profit": "",
            "confidence": "",
            "confidence_score": 0,
            "risk": "",
            "comp_count": 0,
            "location": entry.area,
            "reason": entry.reason or "parsing failed",
            "raw_input": entry.raw_block,
        }

    def _bulk_item_from_failure(self, entry: ParsedBulkVehicle, reason: str) -> dict[str, Any]:
        return {
            "status": "failed",
            "vehicle_name": self._vehicle_summary_from_entry(entry),
            "listed_price": money(entry.listed_price) if isinstance(entry.listed_price, (int, float)) else "",
            "market_value": "",
            "safe_buy_value": "",
            "expected_resale_value": "",
            "estimated_profit": "",
            "confidence": "",
            "confidence_score": 0,
            "risk": "",
            "comp_count": 0,
            "location": entry.area,
            "reason": reason,
            "raw_input": entry.raw_block,
        }

    def _vehicle_summary_from_entry(self, entry: ParsedBulkVehicle) -> str:
        return " ".join(
            part
            for part in [str(entry.year or ""), entry.make, entry.model, entry.trim]
            if part
        ).strip() or "Unparsed vehicle"

    def _location_from_result(self, result: dict[str, Any]) -> str:
        parsed_details = result.get("parsed_details") or {}
        location_parts = [
            str(parsed_details.get("zip_code") or "").strip(),
            str(parsed_details.get("state") or "").strip(),
        ]
        return " ".join(part for part in location_parts if part).strip()

    def _bulk_rank_score(self, item: dict[str, Any]) -> float:
        estimated_profit = self._money_to_float(item.get("estimated_profit", ""))
        safe_buy = self._money_to_float(item.get("safe_buy_value", ""))
        listed_price = self._money_to_float(item.get("listed_price", ""))
        confidence = float(item.get("confidence_score") or 0.0)
        risk_penalty = {"Low": 0.0, "Medium": 10.0, "High": 22.0}.get(str(item.get("risk") or ""), 12.0)

        profit_ratio = (estimated_profit / safe_buy * 100.0) if safe_buy > 0 else 0.0
        buy_gap_ratio = ((safe_buy - listed_price) / safe_buy * 100.0) if safe_buy > 0 and listed_price > 0 else 0.0
        return (profit_ratio * 0.55) + (confidence * 0.45) + (buy_gap_ratio * 0.35) - risk_penalty

    def _bulk_risk_label(self, confidence: float) -> str:
        if confidence >= 80:
            return "Low"
        if confidence >= 62:
            return "Medium"
        return "High"

    def _bulk_status_from_counts(self, summary: dict[str, int]) -> str:
        if summary["evaluated_entries"] and not summary["failed_entries"] and not summary["skipped_entries"]:
            return "complete"
        if summary["evaluated_entries"] or summary["parsed_entries"]:
            return "partial"
        return "needs_more_data"

    def _bulk_status_message(self, summary: dict[str, int]) -> str:
        return (
            f'Parsed {summary["parsed_entries"]} of {summary["total_entries"]} vehicles and '
            f'evaluated {summary["evaluated_entries"]}. '
            f'Skipped {summary["skipped_entries"]}, failed {summary["failed_entries"]}.'
        )

    def _average_price_near_mileage(
        self,
        query: VehicleQuery,
        listings: list[NormalizedListing],
        max_results: int = 6,
        max_mileage_delta: int = 20_000,
    ) -> dict[str, Any]:
        target_mileage = query.mileage
        if not isinstance(target_mileage, int) or target_mileage <= 0:
            return {
                "label": "Average Price Near This Mileage",
                "value": "",
                "comps_used": 0,
                "range": "",
                "message": "Not enough nearby mileage comps",
            }

        nearby: list[tuple[int, float]] = []
        for listing in listings:
            if listing.mileage is None:
                continue
            price = listing.adjusted_price if listing.adjusted_price is not None else listing.price
            if price is None or price <= 0:
                continue
            mileage_delta = abs(int(listing.mileage) - target_mileage)
            if mileage_delta > max_mileage_delta:
                continue
            nearby.append((mileage_delta, float(price)))

        if not nearby:
            return {
                "label": "Average Price Near This Mileage",
                "value": "",
                "comps_used": 0,
                "range": f"{max(0, target_mileage - max_mileage_delta):,} to {target_mileage + max_mileage_delta:,} miles",
                "message": "Not enough nearby mileage comps",
            }

        selected = sorted(nearby, key=lambda item: item[0])[:max_results]
        average_price = sum(price for _, price in selected) / len(selected)
        return {
            "label": "Average Price Near This Mileage",
            "value": money(average_price),
            "comps_used": len(selected),
            "range": f"{max(0, target_mileage - max_mileage_delta):,} to {target_mileage + max_mileage_delta:,} miles",
            "message": "",
        }

    def _average_price_of_closest_mileage(
        self,
        listings: list[NormalizedListing],
        target_mileage: int | None,
        limit: int = 20,
    ) -> float:
        if not target_mileage:
            return self.calculate_market_value(listings)
        valid = [
            listing for listing in listings
            if listing.mileage is not None and self._listing_market_price(listing) is not None
        ]
        if not valid:
            return self.calculate_market_value(listings)
        selected = sorted(
            valid,
            key=lambda listing: abs(int(listing.mileage or 0) - int(target_mileage or 0)),
        )[:limit]
        if not selected:
            return self.calculate_market_value(listings)
        return sum(self._listing_market_price(listing) or 0.0 for listing in selected) / len(selected)

    def _listing_public_dict(self, listing: NormalizedListing) -> dict[str, Any]:
        return {
            "source": listing.source,
            "source_label": listing.source_label,
            "source_listing_id": listing.source_listing_id,
            "url": listing.url,
            "year": listing.year,
            "make": listing.make,
            "model": listing.model,
            "trim": listing.trim,
            "body_style": listing.body_style,
            "drivetrain": listing.drivetrain,
            "engine": listing.engine,
            "transmission": listing.transmission,
            "fuel_type": listing.fuel_type,
            "exterior_color": listing.exterior_color,
            "mileage": listing.mileage,
            "price": money(listing.price or 0.0),
            "adjusted_price": money(listing.adjusted_price or listing.price or 0.0),
            "seller_type": listing.seller_type,
            "location": listing.location,
            "location_label": self._listing_location_text(listing),
            "vin": listing.vin,
            "title_status": listing.title_status,
            "condition": listing.condition,
            "listing_age_days": listing.listing_age_days,
            "dealer_name": listing.dealer_name,
            "image_urls": listing.image_urls,
            "match_tier": listing.match_tier,
            "relevance_score": round(listing.relevance_score, 2),
            "adjustment_notes": listing.adjustment_notes,
        }

    def _listing_location_text(self, listing: NormalizedListing) -> str:
        location = listing.location or {}
        parts = [
            str(location.get("city") or "").strip(),
            str(location.get("state") or "").strip(),
            str(location.get("zip") or "").strip(),
        ]
        location_text = ", ".join(part for part in parts[:2] if part)
        if not location_text:
            location_text = " ".join(part for part in parts if part)
        if location_text:
            return location_text
        return str(listing.dealer_name or "").strip()

    def _excluded_listing(self, listing: NormalizedListing, reason: str) -> dict[str, Any]:
        return {
            "source": listing.source_label,
            "title": " ".join(part for part in [str(listing.year or ""), listing.make, listing.model, listing.trim] if part).strip(),
            "price": money(listing.price or 0.0) if listing.price else "",
            "reason": reason,
        }

    def _build_condition_ranges(self, listings: list[NormalizedListing]) -> dict[str, dict[str, str]]:
        adjusted_prices = [
            listing.adjusted_price
            for listing in listings
            if listing.adjusted_price is not None
        ]
        if not adjusted_prices:
            return {}

        p10 = percentile(adjusted_prices, 0.10)
        p20 = percentile(adjusted_prices, 0.20)
        p35 = percentile(adjusted_prices, 0.35)
        p50 = percentile(adjusted_prices, 0.50)
        p60 = percentile(adjusted_prices, 0.60)
        p70 = percentile(adjusted_prices, 0.70)
        anchors = {
            "Awful": p10,
            "Fair": p20,
            "Good": p35,
            "Great": p50,
            "Amazing": p60,
        }
        mileage_by_condition = self._condition_mileage_breakdown(listings)
        values: dict[str, dict[str, str]] = {}
        for label, anchor in anchors.items():
            spread = max(500.0, anchor * 0.035)
            values[label] = {
                "estimated_range": f"{money(anchor - spread)} to {money(anchor + spread)}",
                "anchor_price": money(anchor),
                "average_mileage": mileage_by_condition.get(label, ""),
                "pricing_note": self._pricing_note(label, p10, p20, p35, p50, p60, p70),
            }
        values["Live Market"] = {
            "estimated_range": f"{money(p10)} to {money(p70)}",
            "anchor_price": money(p35),
            "average_mileage": mileage_by_condition.get("Live Market", ""),
            "pricing_note": "Current normalized asking-price spread from matched comps",
        }
        return values

    def _condition_mileage_breakdown(self, listings: list[NormalizedListing]) -> dict[str, str]:
        sorted_listings = sorted(
            [listing for listing in listings if listing.adjusted_price is not None],
            key=lambda listing: listing.adjusted_price or 0.0,
        )
        if not sorted_listings:
            return {}

        bands = {
            "Awful": (0.00, 0.20),
            "Fair": (0.12, 0.36),
            "Good": (0.28, 0.56),
            "Great": (0.44, 0.74),
            "Amazing": (0.62, 1.00),
            "Live Market": (0.00, 1.00),
        }
        output: dict[str, str] = {}
        count = len(sorted_listings)
        for label, (start_pct, end_pct) in bands.items():
            start = min(count - 1, int(count * start_pct))
            end = max(start + 1, int(count * end_pct))
            subset = sorted_listings[start:end]
            mileages = [listing.mileage for listing in subset if listing.mileage is not None]
            if not mileages:
                output[label] = ""
                continue
            output[label] = f"{int(round(sum(mileages) / len(mileages))):,} miles"
        return output

    def _build_overall_range(
        self,
        values: dict[str, dict[str, str]],
        listings: list[NormalizedListing],
        market_value: float,
        safe_buy_value: float,
        expected_resale_value: float,
        estimated_profit: float,
        target_mileage: int | None = None,
        imperfect_title_value: str = "",
    ) -> dict[str, Any]:
        ranges: list[tuple[float, float]] = []
        anchors: list[float] = []
        for payload in values.values():
            range_value = payload.get("estimated_range", "")
            if " to " in range_value:
                low, high = range_value.split(" to ", 1)
                ranges.append((self._money_to_float(low), self._money_to_float(high)))
            anchor = payload.get("anchor_price")
            if anchor:
                anchors.append(self._money_to_float(anchor))
        result: dict[str, Any] = {}
        result["market_value"] = money(market_value)
        result["safe_buy_value"] = money(safe_buy_value)
        result["expected_resale_value"] = money(expected_resale_value)
        result["estimated_profit"] = money(estimated_profit)
        result["full_price_range"] = self._build_full_price_range(listings)
        if imperfect_title_value:
            result["imperfect_title_value"] = imperfect_title_value
        if ranges:
            result["condition_range"] = {
                "low": money(min(low for low, _ in ranges)),
                "high": money(max(high for _, high in ranges)),
            }
        return result

    def _build_title_adjustment_projection(
        self,
        *,
        market_value: float,
        expected_resale_low: float,
        expected_resale_high: float,
    ) -> dict[str, Any]:
        rebuilt_average = market_value * 0.70
        rebuilt_low = market_value * 0.60
        rebuilt_high = market_value * 0.80
        safe_buy_low = market_value * 0.50
        safe_buy_high = market_value * 0.65
        return {
            "active": True,
            "title_status": "clean",
            "clean_title_value": money(market_value),
            "clean_title_range": {
                "low": money(expected_resale_low),
                "high": money(expected_resale_high),
            },
            "rebuilt_title_range": {
                "low": money(rebuilt_low),
                "high": money(rebuilt_high),
            },
            "rebuilt_title_average": money(rebuilt_average),
            "safe_buy_range": {
                "low": money(safe_buy_low),
                "high": money(safe_buy_high),
            },
            "value_difference": {
                "low": money(market_value * 0.20),
                "high": money(market_value * 0.40),
                "average": money(market_value * 0.30),
            },
            "damage_factor_range": "20% to 40%",
            "note": "Projected imperfect-title values are shown using the rebuilt-title pricing model.",
        }

    def _listing_market_price(self, listing: NormalizedListing) -> float | None:
        price = listing.adjusted_price if listing.adjusted_price is not None else listing.price
        if price is None or price <= 0:
            return None
        return float(price)

    def calculate_market_value(self, comps: list[NormalizedListing]) -> float:
        valid_prices = [
            price
            for price in (self._listing_market_price(listing) for listing in comps)
            if price is not None
        ]
        if not valid_prices:
            return 0.0
        return sum(valid_prices) / len(valid_prices)

    def _target_mileage_from_listings(self, listings: list[NormalizedListing]) -> int | None:
        valid_mileages = [int(listing.mileage) for listing in listings if listing.mileage is not None]
        if not valid_mileages:
            return None
        return int(round(sum(valid_mileages) / len(valid_mileages)))

    def _is_craigslist_listing(self, listing: NormalizedListing) -> bool:
        source = f"{listing.source} {listing.source_label}".lower()
        return "craigslist" in source

    def _craigslist_average(self, listings: list[NormalizedListing]) -> str:
        craigslist_listings = [listing for listing in listings if self._is_craigslist_listing(listing)]
        if not craigslist_listings:
            return ""
        return money(self.calculate_market_value(craigslist_listings))

    def _build_kbb_adjuster(
        self,
        market_value: float,
        target_mileage: int | None,
        comps: list[NormalizedListing],
    ) -> dict[str, Any]:
        if not market_value:
            return {"value": "", "percent": 0.0}

        valid_mileages = sorted(int(listing.mileage) for listing in comps if listing.mileage is not None)
        if target_mileage is None or not valid_mileages:
            percent = 0.21
        else:
            target = int(target_mileage)
            if len(valid_mileages) >= 2 and target >= valid_mileages[-2]:
                percent = 0.24
            elif len(valid_mileages) >= 2 and target <= valid_mileages[1]:
                percent = 0.18
            else:
                rank = sum(1 for mileage in valid_mileages if mileage <= target)
                denominator = max(len(valid_mileages) - 1, 1)
                percentile = min(max((rank - 1) / denominator, 0.0), 1.0)
                percent = 0.18 + (0.06 * percentile)

        adjusted_value = market_value * (1.0 - percent)
        return {
            "value": money(adjusted_value),
            "percent": round(percent * 100, 1),
        }

    def calculateSafeBuyValue(self, comps: list[NormalizedListing]) -> float:
        return self.calculate_safe_buy_value(comps)

    def calculate_safe_buy_value(self, comps: list[NormalizedListing]) -> float:
        valid = [
            listing for listing in comps
            if listing.mileage is not None and self._listing_market_price(listing) is not None
        ]
        if not valid:
            fallback_market = self.calculate_market_value(comps)
            return fallback_market * 0.80 if fallback_market else 0.0
        selected = sorted(valid, key=lambda listing: int(listing.mileage or 0), reverse=True)[:5]
        average_price = sum(self._listing_market_price(listing) or 0.0 for listing in selected) / len(selected)
        return average_price * 0.80

    def calculateExpectedResaleValue(self, target_mileage: int, comps: list[NormalizedListing]) -> float:
        return self.calculate_expected_resale_value(target_mileage, comps)

    def calculate_expected_resale_value(self, target_mileage: int, comps: list[NormalizedListing]) -> float:
        valid = [
            listing for listing in comps
            if listing.mileage is not None and self._listing_market_price(listing) is not None
        ]
        if not valid:
            return self.calculate_market_value(comps)
        selected = sorted(
            valid,
            key=lambda listing: abs(int(listing.mileage or 0) - int(target_mileage or 0)),
        )[:10]
        if not selected:
            return self.calculate_market_value(comps)
        return sum(self._listing_market_price(listing) or 0.0 for listing in selected) / len(selected)

    def calculateEstimatedProfit(self, expected_resale_value: float, safe_buy_value: float) -> float:
        return self.calculate_estimated_profit(expected_resale_value, safe_buy_value)

    def calculate_estimated_profit(self, expected_resale_value: float, safe_buy_value: float) -> float:
        if expected_resale_value <= 0 or safe_buy_value <= 0:
            return 0.0
        return expected_resale_value - safe_buy_value

    def _empty_title_adjustment(self, query: VehicleQuery) -> dict[str, Any]:
        return {
            "active": False,
            "title_status": query.title_status or "clean",
            "clean_title_value": "",
            "clean_title_range": {"low": "", "high": ""},
            "rebuilt_title_range": {"low": "", "high": ""},
            "rebuilt_title_average": "",
            "safe_buy_range": {"low": "", "high": ""},
            "value_difference": {"low": "", "high": "", "average": ""},
            "damage_factor_range": "20% to 40%",
            "note": "",
        }

    def _empty_listing_price_analysis(
        self,
        query: VehicleQuery,
        insufficient_data: bool = False,
    ) -> dict[str, Any]:
        asking_price = money(query.asking_price) if query.asking_price else ""
        return {
            "active": bool(query.asking_price),
            "provided_price": asking_price,
            "market_value": "",
            "safe_buy_price": "",
            "expected_resale": "",
            "difference_to_market": "",
            "difference_percent": "",
            "estimated_profit_at_asking": "",
            "position_label": "",
            "recommended_action": "",
            "recommended_target_price": "",
            "price_adjustment": "",
            "price_adjustment_percent": "",
            "negotiation_window": "",
            "note": (
                "The listing price was provided, but the engine needs more clean market comps before it can rate how well the car is priced."
                if insufficient_data and query.asking_price
                else ""
            ),
        }

    def _build_listing_price_analysis(
        self,
        query: VehicleQuery,
        *,
        market_value: float,
        safe_buy_price: float,
        expected_resale_low: float,
        expected_resale_high: float,
    ) -> dict[str, Any]:
        if not query.asking_price:
            return self._empty_listing_price_analysis(query)

        asking_price = float(query.asking_price)
        expected_resale_mid = (expected_resale_low + expected_resale_high) / 2
        delta = asking_price - market_value
        delta_percent = (delta / market_value * 100) if market_value else 0.0
        estimated_profit = expected_resale_mid - asking_price
        target_price = min(market_value, expected_resale_mid * 0.94)
        target_price = max(target_price, safe_buy_price)
        adjustment = target_price - asking_price
        adjustment_percent = (adjustment / asking_price * 100) if asking_price else 0.0

        if delta_percent <= -5:
            position_label = "Priced below market"
        elif delta_percent >= 5:
            position_label = "Priced above market"
        else:
            position_label = "Priced near market"

        safe_buy_gap = asking_price - safe_buy_price
        if adjustment >= 750:
            recommended_action = "Raise the listing price"
            note = (
                f"The current ask looks conservative against the comp set. "
                f"You likely have room to move it up by about {money(adjustment)}."
            )
        elif adjustment <= -750:
            recommended_action = "Lower the listing price"
            note = (
                f"The current ask looks rich relative to market. "
                f"Dropping it by about {money(abs(adjustment))} should make it more competitive."
            )
        elif safe_buy_gap <= 0:
            recommended_action = "Hold or slightly raise the listing price"
            note = "This asking price is at or below the safe-buy level from the current comp set."
        else:
            recommended_action = "Hold near the current listing price"
            note = f"This asking price is about {money(safe_buy_gap)} above the current safe-buy level."

        negotiation_low = min(target_price, asking_price)
        negotiation_high = max(target_price, asking_price)

        return {
            "active": True,
            "provided_price": money(asking_price),
            "market_value": money(market_value),
            "safe_buy_price": money(safe_buy_price),
            "expected_resale": f"{money(expected_resale_low)} to {money(expected_resale_high)}",
            "difference_to_market": money(abs(delta)),
            "difference_percent": f"{abs(delta_percent):.1f}%",
            "estimated_profit_at_asking": money(estimated_profit),
            "position_label": position_label,
            "recommended_action": recommended_action,
            "recommended_target_price": money(target_price),
            "price_adjustment": money(abs(adjustment)),
            "price_adjustment_percent": f"{abs(adjustment_percent):.1f}%",
            "negotiation_window": f"{money(negotiation_low)} to {money(negotiation_high)}",
            "note": note,
        }

    def _is_rebuilt_title(self, query: VehicleQuery) -> bool:
        return query.title_status.strip().lower() in {"rebuilt", "reconstructed", "recon"}

    def _apply_rebuilt_title_adjustment(self, response: dict[str, Any]) -> dict[str, Any]:
        clean_value = self._money_to_float(response.get("adjusted_price_estimate", {}).get("weighted_median", "$0"))
        clean_resale_range = response.get("recommended_target_resale_range") or {}
        clean_low = self._money_to_float(clean_resale_range.get("low", "$0"))
        clean_high = self._money_to_float(clean_resale_range.get("high", "$0"))
        rebuilt_average = clean_value * 0.70
        rebuilt_low = clean_value * 0.60
        rebuilt_high = clean_value * 0.80
        safe_buy_low = clean_value * 0.50
        safe_buy_high = clean_value * 0.65
        recommended_buy = (safe_buy_low + safe_buy_high) / 2
        response["title_adjustment"] = {
            "active": True,
            "title_status": response.get("parsed_details", {}).get("title_status") or "rebuilt",
            "clean_title_value": money(clean_value),
            "clean_title_range": {
                "low": money(clean_low),
                "high": money(clean_high),
            },
            "rebuilt_title_range": {
                "low": money(rebuilt_low),
                "high": money(rebuilt_high),
            },
            "rebuilt_title_average": money(rebuilt_average),
            "safe_buy_range": {
                "low": money(safe_buy_low),
                "high": money(safe_buy_high),
            },
            "value_difference": {
                "low": money(clean_value * 0.20),
                "high": money(clean_value * 0.40),
                "average": money(clean_value * 0.30),
            },
            "damage_factor_range": "20% to 40%",
            "note": "Rebuilt title pricing is adjusted from the clean-title benchmark using a 20% to 40% damage factor.",
        }
        response["values"] = self._scale_condition_values_for_rebuilt(response.get("values") or {})
        response["overall_range"] = self._scale_overall_range_for_rebuilt(response.get("overall_range") or {})
        adjusted_price_estimate = response.get("adjusted_price_estimate") or {}
        if adjusted_price_estimate.get("weighted_median"):
            adjusted_price_estimate["weighted_median"] = money(rebuilt_average)
        if adjusted_price_estimate.get("trimmed_median"):
            adjusted_price_estimate["trimmed_median"] = money(self._money_to_float(adjusted_price_estimate["trimmed_median"]) * 0.70)
        response["adjusted_price_estimate"] = adjusted_price_estimate
        response["recommended_max_buy_price"] = money(recommended_buy)
        response["recommended_target_resale_range"] = {
            "low": money(clean_low * 0.60),
            "high": money(clean_high * 0.80),
        }
        response["gross_spread_estimate"] = money(max(0.0, (clean_low * 0.60) - recommended_buy))
        response["confidence_score"] = max(5, int(response.get("confidence_score", 0)) - 8)
        response["message"] = (
            f"{response.get('message', '').strip()} "
            "Rebuilt title adjustments are now applied against the clean-title market benchmark."
        ).strip()
        return response

    def _scale_condition_values_for_rebuilt(self, values: dict[str, dict[str, str]]) -> dict[str, dict[str, str]]:
        scaled: dict[str, dict[str, str]] = {}
        for label, payload in values.items():
            updated = dict(payload)
            anchor = payload.get("anchor_price")
            range_value = payload.get("estimated_range", "")
            if anchor:
                updated["anchor_price"] = money(self._money_to_float(anchor) * 0.70)
            if " to " in range_value:
                low_text, high_text = range_value.split(" to ", 1)
                updated["estimated_range"] = f"{money(self._money_to_float(low_text) * 0.70)} to {money(self._money_to_float(high_text) * 0.70)}"
            note = str(payload.get("pricing_note") or "").strip()
            updated["pricing_note"] = (
                f"{note} Rebuilt-title pricing is shown at roughly 70% of the clean-title benchmark."
            ).strip()
            scaled[label] = updated
        return scaled

    def _scale_overall_range_for_rebuilt(self, overall_range: dict[str, Any]) -> dict[str, Any]:
        rebuilt = dict(overall_range)
        for key in ("market_value", "safe_buy_value", "expected_resale_value", "estimated_profit"):
            value = overall_range.get(key)
            if value:
                rebuilt[key] = money(self._money_to_float(value) * 0.70)
        condition_range = overall_range.get("condition_range")
        if isinstance(condition_range, dict):
            rebuilt["condition_range"] = {
                "low": money(self._money_to_float(condition_range.get("low", "$0")) * 0.70),
                "high": money(self._money_to_float(condition_range.get("high", "$0")) * 0.70),
            }
        return rebuilt

    def _build_full_price_range(self, listings: list[NormalizedListing]) -> str:
        prices = [
            self._listing_market_price(listing)
            for listing in listings
            if self._listing_market_price(listing) is not None
        ]
        if not prices:
            return ""
        return f"{money(min(prices))} - {money(max(prices))}"

    def _serialize_sample_listings(self, listings: list[NormalizedListing]) -> list[dict[str, str]]:
        return [
            {
                "title": " ".join(
                    part for part in [
                        str(listing.year or ""),
                        listing.make,
                        listing.model,
                        listing.trim,
                    ] if part
                ).strip(),
                "price": money(listing.price or 0.0),
                "miles": f"{listing.mileage:,} mi" if listing.mileage is not None else "",
                "trim": listing.trim,
                "dealer": listing.source_label,
                "location_label": self._listing_location_text(listing),
                "source_url": listing.url,
                "url": listing.url,
                "image_urls": listing.image_urls,
                "mileage": listing.mileage,
            }
            for listing in listings
        ]

    def _success_message(self, source_results: list[SourceRunResult]) -> str:
        active = [
            result.metadata.label
            for result in source_results
            if result.status == "ok" and result.normalized_listings
        ]
        if active:
            return (
                "These ranges are generated by the new multi-source comps engine using "
                + ", ".join(active)
                + ". Official adapters stay enabled when credentials are present, and fragile sources are isolated so they cannot break the run."
            )
        return "These ranges are generated by the multi-source comps engine."

    def _source_breakdown(self, listings: list[NormalizedListing]) -> list[dict[str, Any]]:
        counts: dict[str, int] = {}
        for listing in listings:
            counts[listing.source_label] = counts.get(listing.source_label, 0) + 1
        return [
            {"label": label, "count": count}
            for label, count in sorted(counts.items(), key=lambda item: (-item[1], item[0]))
        ]

    def _source_adapter_breakdown(self, listings: list[NormalizedListing]) -> list[dict[str, Any]]:
        counts: dict[str, int] = {}
        for listing in listings:
            counts[listing.source] = counts.get(listing.source, 0) + 1
        return [
            {"label": label, "count": count}
            for label, count in sorted(counts.items(), key=lambda item: (-item[1], item[0]))
        ]

    def _vehicle_summary(self, query: VehicleQuery) -> str:
        summary = " ".join(
            part
            for part in [str(query.year or "").strip(), query.make.strip(), query.model.strip(), query.trim.strip()]
            if part
        ).strip()
        extras = []
        if query.mileage:
            extras.append(f"{query.mileage:,} miles")
        if query.zip_code:
            extras.append(f"ZIP {query.zip_code}")
        if extras:
            summary = f"{summary} ({', '.join(extras)})" if summary else ", ".join(extras)
        return summary or query.raw_input or "Vehicle valuation"

    def _query_dict(self, query: VehicleQuery) -> dict[str, Any]:
        payload = query.as_dict()
        payload.pop("manual_csv", None)
        payload.pop("manual_urls", None)
        payload.pop("manual_listings", None)
        payload.pop("custom_listings", None)
        payload["vehicle_input"] = payload.pop("raw_input", "")
        return payload

    def _assumptions(self, query: VehicleQuery, enabled_sources: list[str]) -> list[str]:
        assumptions = []
        if not query.zip_code and not query.state:
            assumptions.append("No ZIP or state was provided, so the engine used a broader national comps basket.")
        if not query.trim:
            assumptions.append("No trim was provided, so matching broadened toward similar-config trims when needed.")
        if query.vin_decoded_used:
            assumptions.append("VIN-based normalization was used where possible to tighten the spec match.")
        return assumptions

    def _recommended_max_buy(
        self,
        query: VehicleQuery,
        target_resale_low: float,
        weighted_price: float,
        confidence: int,
    ) -> float:
        condition_buffers = {
            "awful": 3200.0,
            "fair": 2400.0,
            "good": 1800.0,
            "great": 1400.0,
            "amazing": 1000.0,
        }
        condition_key = query.condition.lower()
        base_buffer = condition_buffers.get(condition_key, 1800.0)
        confidence_penalty = max(0.0, (70 - confidence) * 18.0)
        profit_reserve = max(base_buffer + confidence_penalty, weighted_price * 0.18)
        return max(500.0, target_resale_low - profit_reserve)

    def _active_source_count(self, source_results: list[SourceRunResult]) -> int:
        return sum(1 for result in source_results if result.status == "ok" and result.normalized_listings)

    def _histogram(self, prices: list[float]) -> list[dict[str, Any]]:
        if not prices:
            return []
        sorted_prices = sorted(prices)
        min_price = sorted_prices[0]
        max_price = sorted_prices[-1]
        if min_price == max_price:
            return [{"label": money(min_price), "count": len(sorted_prices)}]
        bucket_count = min(6, max(3, len(sorted_prices) // 4))
        width = max(1.0, (max_price - min_price) / bucket_count)
        buckets: list[dict[str, Any]] = []
        for index in range(bucket_count):
            low = min_price + (width * index)
            high = max_price if index == bucket_count - 1 else min_price + (width * (index + 1))
            if index == bucket_count - 1:
                count = sum(1 for price in sorted_prices if low <= price <= high)
            else:
                count = sum(1 for price in sorted_prices if low <= price < high)
            buckets.append({"label": f"{money(low)}-{money(high)}", "count": count})
        return buckets

    def _price_vs_mileage(self, listings: list[NormalizedListing]) -> list[dict[str, Any]]:
        points = []
        for listing in listings:
            if listing.mileage is None:
                continue
            points.append(
                {
                    "mileage": listing.mileage,
                    "price": round(listing.adjusted_price or listing.price or 0.0, 2),
                    "source": listing.source_label,
                }
            )
        return points

    def _mileage_price_bands(self, listings: list[NormalizedListing]) -> list[dict[str, Any]]:
        buckets: dict[tuple[int, int], list[float]] = {}
        counts: dict[tuple[int, int], int] = {}
        for listing in listings:
            if listing.mileage is None or listing.price is None:
                continue
            band_low = (listing.mileage // 10000) * 10000
            band_high = band_low + 10000
            key = (band_low, band_high)
            buckets.setdefault(key, []).append(listing.price)
            counts[key] = counts.get(key, 0) + 1

        bands: list[dict[str, Any]] = []
        for (band_low, band_high), prices in sorted(buckets.items()):
            average_price = sum(prices) / len(prices)
            bands.append(
                {
                    "label": f"{band_low // 1000}k-{band_high // 1000}k mi",
                    "count": counts[(band_low, band_high)],
                    "average_price": money(average_price),
                }
            )
        return bands

    def _pricing_note(
        self,
        label: str,
        p10: float,
        p20: float,
        p35: float,
        p50: float,
        p60: float,
        p70: float,
    ) -> str:
        notes = {
            "Awful": f"Priced deep under market, near the bottom band around {money(p10)}",
            "Fair": f"Entry-level band, roughly {money(p10)} to {money(p20)}",
            "Good": f"Resale-safe middle band, roughly {money(p20)} to {money(p35)}",
            "Great": f"Healthy retail band, roughly {money(p35)} to {money(p50)}",
            "Amazing": f"Strong current market band, capped below the hottest listings near {money(p60)}",
        }
        return notes.get(label, f"Live spread about {money(p10)} to {money(p70)}")

    def _money_to_float(self, value: str) -> float:
        return float(value.replace("$", "").replace(",", ""))

    def admin_overview(self) -> dict[str, Any]:
        source_health = [adapter.health_check() for adapter in self.adapters]
        source_metadata = [adapter.get_source_metadata().to_dict() for adapter in self.adapters]
        return {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "portfolio_count": len(self.repository.list_saved_evaluations()),
            "cache_db_path": str(self.config.sqlite_path),
            "sources": source_metadata,
            "source_health": source_health,
            "enabled_source_count": sum(1 for item in source_health if item.get("enabled")),
        }
