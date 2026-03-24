from __future__ import annotations

import csv
import io
import re
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlparse

from .base import SourceAdapter
from ..models import NormalizedListing, VehicleQuery
from ..query_parser import parse_vehicle_query


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class ManualImportAdapter(SourceAdapter):
    key = "manual_import"
    label = "Manual Import"
    official = True
    fragile = False
    fields = ["year", "make", "model", "trim", "price", "mileage", "url", "sellerType"]
    notes = "Supports pasted CSV rows or listing URLs you already have."

    def is_enabled(self) -> bool:
        return self.config.enable_manual_import

    def search_listings(self, query: VehicleQuery) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        if query.manual_csv:
            reader = csv.DictReader(io.StringIO(query.manual_csv))
            for index, row in enumerate(reader):
                row["source_listing_id"] = row.get("source_listing_id") or f"csv-{index}"
                results.append(row)
        for index, url in enumerate(query.manual_urls):
            results.append(
                {
                    "source_listing_id": f"url-{index}",
                    "url": url,
                    "title": self._title_from_url(url),
                    "raw_url": url,
                }
            )
        for index, row in enumerate(query.manual_listings):
            payload = dict(row)
            payload["source_listing_id"] = payload.get("source_listing_id") or f"manual-{index}"
            results.append(payload)
        return results

    def normalize_listing(self, raw: dict[str, Any], query: VehicleQuery) -> NormalizedListing | None:
        parsed_from_title = parse_vehicle_query({"vehicle_input": raw.get("title", "")})
        price = self._to_float(raw.get("price"))
        mileage = self._to_int(raw.get("mileage") or raw.get("miles"))
        seller_type = str(raw.get("seller_type") or raw.get("sellerType") or "").strip().lower()
        url = str(raw.get("url", "")).strip()
        location = {
            "city": str(raw.get("city", "")).strip(),
            "state": str(raw.get("state", "")).strip().upper(),
            "zip": str(raw.get("zip", "")).strip(),
        }
        return NormalizedListing(
            source=self.key,
            source_listing_id=str(raw.get("source_listing_id", "")),
            source_label=self.label,
            url=url,
            fetched_at=_now_iso(),
            year=self._to_int(raw.get("year")) or parsed_from_title.year,
            make=str(raw.get("make", "")).strip() or parsed_from_title.make,
            model=str(raw.get("model", "")).strip() or parsed_from_title.model,
            trim=str(raw.get("trim", "")).strip() or parsed_from_title.trim,
            body_style=str(raw.get("body_style", "")).strip() or parsed_from_title.body_style,
            drivetrain=str(raw.get("drivetrain", "")).strip() or parsed_from_title.drivetrain,
            engine=str(raw.get("engine", "")).strip(),
            transmission=str(raw.get("transmission", "")).strip() or parsed_from_title.transmission,
            fuel_type=str(raw.get("fuel_type", "")).strip(),
            exterior_color=str(raw.get("exterior_color", "")).strip() or parsed_from_title.exterior_color,
            mileage=mileage or parsed_from_title.mileage,
            price=price,
            seller_type=seller_type,
            location=location,
            vin=str(raw.get("vin", "")).strip().upper(),
            title_status=str(raw.get("title_status", "")).strip(),
            condition=str(raw.get("condition", "")).strip(),
            listing_age_days=self._to_int(raw.get("listing_age_days")),
            dealer_name=str(raw.get("dealer_name", "")).strip(),
            image_urls=self._extract_list(raw.get("image_urls")),
            raw_payload=raw,
            spec_confidence=0.45,
        )

    def _to_float(self, value: Any) -> float | None:
        try:
            digits = re.sub(r"[^\d.]", "", str(value or ""))
            return float(digits) if digits else None
        except ValueError:
            return None

    def _to_int(self, value: Any) -> int | None:
        digits = "".join(ch for ch in str(value or "") if ch.isdigit())
        return int(digits) if digits else None

    def _extract_list(self, value: Any) -> list[str]:
        if isinstance(value, list):
            return [str(item) for item in value if item]
        if isinstance(value, str) and value.strip():
            return [item.strip() for item in value.split(",") if item.strip()]
        return []

    def _title_from_url(self, url: str) -> str:
        parsed = urlparse(url)
        slug = parsed.path.rsplit("/", 1)[-1]
        slug = slug.rsplit(".", 1)[0]
        return slug.replace("-", " ").strip()


class CustomSourceAdapter(ManualImportAdapter):
    key = "custom_source"
    label = "Custom Source"
    notes = "Internal adapter for trusted custom listing payloads or future integrations."

    def is_enabled(self) -> bool:
        return self.config.enable_custom_source

    def search_listings(self, query: VehicleQuery) -> list[dict[str, Any]]:
        results = []
        for index, row in enumerate(query.custom_listings):
            payload = dict(row)
            payload["source_listing_id"] = payload.get("source_listing_id") or f"custom-{index}"
            results.append(payload)
        return results
