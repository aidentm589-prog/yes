from __future__ import annotations

import json
import os
import re
from typing import Any

from .http import HttpClient
from .models import NormalizedListing, VehicleQuery


class DetailedVehicleReportService:
    def __init__(self, http_client: HttpClient) -> None:
        self.http_client = http_client
        self.api_key = os.getenv("OPENAI_API_KEY", "").strip()
        self.model = os.getenv("OPENAI_DETAILED_REPORT_MODEL", "gpt-5.4-mini").strip()

    def should_generate_detailed_vehicle_report(self, payload: dict[str, Any]) -> bool:
        raw = str(payload.get("detailed_vehicle_report") or payload.get("include_detailed_vehicle_report") or "").strip().lower()
        return raw in {"1", "true", "yes", "on", "enabled"}

    def is_sports_car(self, query: VehicleQuery, base_report: dict[str, Any] | None = None) -> bool:
        haystack = " ".join(
            [
                str(query.make or ""),
                str(query.model or ""),
                str(query.trim or ""),
                str(base_report.get("engine_spec") or "") if isinstance(base_report, dict) else "",
            ]
        ).lower()
        keywords = {
            "amg", "m3", "m4", "m5", "m340", "m240", "rs", "s4", "s5", "s6", "s7", "s8",
            "type r", "type-r", "sti", "wrx", "hellcat", "trackhawk", "z06", "zl1", "ss",
            "gt", "gti", "gti", "gtr", "supra", "gr86", "brz", "corvette", "mustang",
            "camaro", "911", "c63", "e63", "cla45", "m2", "m8", "cts-v", "blackwing",
            "v8", "twin turbo", "twin-turbo", "supercharged",
        }
        return any(keyword in haystack for keyword in keywords)

    def get_detailed_vehicle_report(
        self,
        query: VehicleQuery,
        result: dict[str, Any],
        listings: list[NormalizedListing],
    ) -> dict[str, Any]:
        base = self._build_base_report(query, result, listings)
        enriched = {}
        if self.api_key and query.year and query.make and query.model:
            try:
                enriched = self._generate_llm_report(base)
            except Exception:
                enriched = {}
        merged = self._merge_report(base, enriched)
        return self.format_detailed_vehicle_report(merged)

    def format_detailed_vehicle_report(self, report: dict[str, Any]) -> dict[str, Any]:
        vehicle_specs = self._section(
            "Vehicle Specs",
            [
                ("Engine Spec", report.get("engine_spec")),
                ("Transmission Spec", report.get("transmission_spec")),
                ("Drivetrain", report.get("drivetrain")),
                ("MPG", report.get("mpg")),
                ("Aspiration", report.get("aspiration")),
            ],
        )
        market_value = self._section(
            "Market / Value",
            [
                ("MSRP", report.get("msrp")),
                ("Market Value", report.get("market_value")),
            ],
        )
        reliability = self._section(
            "Reliability / Ownership",
            [
                ("Common Problems", report.get("common_problems")),
                ("Reliability Rating", report.get("reliability_rating")),
                ("Maintenance Cost Estimate", report.get("maintenance_cost_estimate")),
                ("Typical Lifespan (Miles)", report.get("typical_lifespan_miles")),
                ("Insurance Estimate", report.get("insurance_estimate")),
            ],
        )
        performance = self._section(
            "Performance",
            [
                ("Horsepower", report.get("horsepower")),
                ("Torque", report.get("torque")),
                ("0-60", report.get("zero_to_sixty")),
            ],
        )

        sections = [section for section in [vehicle_specs, market_value, reliability] if section["items"]]
        if report.get("sports_car") and performance["items"]:
            sections.append(performance)

        compact_summary = [
            item
            for item in [
                self._summary_item("Reliability", report.get("reliability_rating")),
                self._summary_item("Maintenance", report.get("maintenance_cost_estimate")),
                self._summary_item("Lifespan", report.get("typical_lifespan_miles")),
                self._summary_item("Engine", report.get("engine_spec")),
                self._summary_item("Performance", self._performance_summary(report) if report.get("sports_car") else ""),
            ]
            if item
        ][:4]

        available_count = sum(len(section["items"]) for section in sections)
        return {
            "requested": True,
            "status": "complete" if available_count >= 6 else ("partial" if available_count else "unavailable"),
            "sports_car": bool(report.get("sports_car")),
            "source": report.get("source", "fallback"),
            "sections": sections,
            "compact_summary": compact_summary,
        }

    def _build_base_report(
        self,
        query: VehicleQuery,
        result: dict[str, Any],
        listings: list[NormalizedListing],
    ) -> dict[str, Any]:
        consensus = self._resolve_comp_specs(listings)
        engine_spec = consensus.get("engine_spec") or query.engine or ""
        transmission_spec = consensus.get("transmission_spec") or query.transmission or ""
        drivetrain = consensus.get("drivetrain") or query.drivetrain or ""
        fuel_type = consensus.get("fuel_type") or query.fuel_type or ""
        body_style = consensus.get("body_style") or query.body_style or ""
        base = {
            "year": query.year,
            "make": query.make,
            "model": query.model,
            "trim": query.trim,
            "body_style": body_style,
            "engine_spec": engine_spec,
            "transmission_spec": transmission_spec,
            "drivetrain": drivetrain,
            "fuel_type": fuel_type,
            "market_value": ((result.get("overall_range") or {}).get("market_value") or ""),
            "msrp": "",
            "mpg": consensus.get("mpg") or "",
            "aspiration": self._infer_aspiration(engine_spec, query.trim),
            "common_problems": self._fallback_common_problems(query, engine_spec),
            "reliability_rating": self._fallback_reliability(query),
            "maintenance_cost_estimate": self._fallback_maintenance_cost(query),
            "typical_lifespan_miles": self._fallback_lifespan(query),
            "insurance_estimate": self._fallback_insurance(query),
            "horsepower": "",
            "torque": "",
            "zero_to_sixty": "",
            "sports_car": self.is_sports_car(query, {"engine_spec": engine_spec}),
            "source": consensus.get("source") or "fallback",
            "spec_confidence": consensus.get("spec_confidence", 0.0),
        }
        return base

    def _generate_llm_report(self, base: dict[str, Any]) -> dict[str, Any]:
        prompt = (
            "Return only valid JSON for a used-car vehicle report. "
            "Use the provided vehicle identity and known facts. "
            "If a field is uncertain, return an empty string. "
            "For common_problems return a short semicolon-separated string, not a list. "
            "For reliability_rating return only Low, Medium, or High. "
            "For maintenance_cost_estimate and insurance_estimate return concise ranges like '$1,200-$1,800/yr' or '$180-$260/mo'. "
            "For typical_lifespan_miles return a range like '180,000-240,000'. "
            "For MPG return a concise combined or city/highway style string. "
            "For horsepower and torque include units, for 0-60 include seconds. "
            "If the vehicle is not performance-oriented, leave horsepower, torque, and zero_to_sixty empty.\n\n"
            f"Vehicle facts:\n{json.dumps(base, ensure_ascii=True)}\n\n"
            "Return JSON with keys: "
            "engine_spec, transmission_spec, drivetrain, msrp, market_value, mpg, aspiration, "
            "common_problems, reliability_rating, maintenance_cost_estimate, typical_lifespan_miles, insurance_estimate, "
            "horsepower, torque, zero_to_sixty."
        )
        status, body, _ = self.http_client.request(
            "POST",
            "https://api.openai.com/v1/responses",
            headers={"Authorization": f"Bearer {self.api_key}"},
            json_body={"model": self.model, "input": prompt},
            source_key="detailed_vehicle_report",
            timeout_seconds=30,
        )
        if status >= 400:
            raise RuntimeError(body.decode("utf-8", "ignore"))
        payload = json.loads(body.decode("utf-8"))
        text = self._extract_response_text(payload)
        parsed = self._extract_json(text)
        parsed["source"] = "llm"
        return parsed

    def _merge_report(self, base: dict[str, Any], enriched: dict[str, Any]) -> dict[str, Any]:
        merged = dict(base)
        hard_spec_keys = {
            "engine_spec",
            "transmission_spec",
            "drivetrain",
            "fuel_type",
            "body_style",
            "mpg",
            "aspiration",
        }
        for key, value in enriched.items():
            if value in ("", None, [], {}):
                continue
            if key in hard_spec_keys and str(base.get(key) or "").strip() and float(base.get("spec_confidence") or 0.0) >= 0.65:
                continue
            merged[key] = value
        merged["sports_car"] = bool(merged.get("sports_car") or self.is_sports_car(
            VehicleQuery(
                year=merged.get("year"),
                make=str(merged.get("make") or ""),
                model=str(merged.get("model") or ""),
                trim=str(merged.get("trim") or ""),
                engine=str(merged.get("engine_spec") or ""),
            ),
            merged,
        ))
        return merged

    def _resolve_comp_specs(self, listings: list[NormalizedListing]) -> dict[str, Any]:
        if not listings:
            return {}
        engine = self._consensus_value(listings, "engine", self._normalize_engine_text)
        transmission = self._consensus_value(listings, "transmission", self._normalize_plain_spec)
        drivetrain = self._consensus_value(listings, "drivetrain", self._normalize_plain_spec)
        fuel_type = self._consensus_value(listings, "fuel_type", self._normalize_plain_spec)
        body_style = self._consensus_value(listings, "body_style", self._normalize_plain_spec)
        mpg = self._consensus_mpg(listings)
        strengths = [value["confidence"] for value in (engine, transmission, drivetrain, fuel_type, body_style) if value["value"]]
        return {
            "engine_spec": engine["value"],
            "transmission_spec": transmission["value"],
            "drivetrain": drivetrain["value"],
            "fuel_type": fuel_type["value"],
            "body_style": body_style["value"],
            "mpg": mpg,
            "spec_confidence": max(strengths) if strengths else 0.0,
            "source": "comp_consensus" if strengths else "fallback",
        }

    def _consensus_value(
        self,
        listings: list[NormalizedListing],
        field_name: str,
        normalizer,
    ) -> dict[str, Any]:
        scores: dict[str, float] = {}
        display: dict[str, str] = {}
        total = 0.0
        for listing in listings:
            raw_value = getattr(listing, field_name, "")
            normalized = normalizer(raw_value)
            if not normalized:
                continue
            weight = max(0.4, float(getattr(listing, "spec_confidence", 0.0) or 0.0))
            weight += max(0.0, float(getattr(listing, "relevance_score", 0.0) or 0.0)) * 0.5
            weight += 0.08 * float(listing.completeness_score())
            total += weight
            scores[normalized] = scores.get(normalized, 0.0) + weight
            if normalized not in display or len(str(raw_value).strip()) > len(display[normalized]):
                display[normalized] = str(raw_value).strip()
        if not scores or total <= 0:
            return {"value": "", "confidence": 0.0}
        winner = max(scores.items(), key=lambda item: item[1])[0]
        confidence = min(1.0, scores[winner] / total)
        return {"value": display.get(winner, winner), "confidence": confidence}

    def _consensus_mpg(self, listings: list[NormalizedListing]) -> str:
        values = []
        for listing in listings:
            raw = listing.raw_payload if isinstance(listing.raw_payload, dict) else {}
            candidates = [
                raw.get("mpg"),
                raw.get("combined_mpg"),
                raw.get("highway_mpg"),
                listing.metadata.get("mpg") if isinstance(listing.metadata, dict) else "",
            ]
            for candidate in candidates:
                if not candidate:
                    continue
                text = str(candidate).strip()
                if text:
                    values.append(text)
                    break
        if not values:
            return ""
        counts: dict[str, int] = {}
        for value in values:
            counts[value] = counts.get(value, 0) + 1
        return max(counts.items(), key=lambda item: item[1])[0]

    def _normalize_engine_text(self, value: Any) -> str:
        text = str(value or "").strip().lower()
        text = re.sub(r"\s+", " ", text)
        text = text.replace("liter", "l").replace(" litre", "l")
        text = text.replace("automatic transmission", "automatic")
        return text

    def _normalize_plain_spec(self, value: Any) -> str:
        text = str(value or "").strip().lower()
        return re.sub(r"\s+", " ", text)

    def _best_spec_listing(self, listings: list[NormalizedListing]) -> NormalizedListing | None:
        if not listings:
            return None
        return max(
            listings,
            key=lambda listing: (
                bool(listing.engine),
                bool(listing.transmission),
                bool(listing.drivetrain),
                bool(listing.fuel_type),
                bool(listing.body_style),
                bool(listing.trim),
                listing.completeness_score(),
            ),
        )

    def _section(self, title: str, pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        return {
            "title": title,
            "items": [
                {"label": label, "value": str(value).strip()}
                for label, value in pairs
                if str(value or "").strip()
            ],
        }

    def _summary_item(self, label: str, value: Any) -> dict[str, str] | None:
        if not str(value or "").strip():
            return None
        return {"label": label, "value": str(value).strip()}

    def _performance_summary(self, report: dict[str, Any]) -> str:
        parts = [str(report.get("horsepower") or "").strip(), str(report.get("zero_to_sixty") or "").strip()]
        return " • ".join(part for part in parts if part)

    def _infer_aspiration(self, engine_spec: str, trim: str) -> str:
        text = f"{engine_spec} {trim}".lower()
        if "supercharg" in text:
            return "Supercharged"
        if "turbo" in text:
            return "Turbocharged"
        if any(token in text for token in ["naturally aspirated", "na "]):
            return "Naturally Aspirated"
        if engine_spec:
            return "Naturally Aspirated"
        return ""

    def _fallback_reliability(self, query: VehicleQuery) -> str:
        make = str(query.make or "").lower()
        performance = self.is_sports_car(query)
        if make in {"toyota", "honda", "lexus", "acura", "mazda"} and not performance:
            return "High"
        if make in {"audi", "bmw", "mercedes", "mercedes-benz", "jaguar", "land rover", "mini", "porsche"}:
            return "Low" if performance else "Medium"
        if performance:
            return "Medium"
        return "Medium"

    def _fallback_maintenance_cost(self, query: VehicleQuery) -> str:
        make = str(query.make or "").lower()
        performance = self.is_sports_car(query)
        if make in {"toyota", "honda", "lexus", "acura", "mazda"} and not performance:
            return "$700-$1,000/yr"
        if make in {"audi", "bmw", "mercedes", "mercedes-benz", "porsche", "mini", "jaguar", "land rover"}:
            return "$1,400-$2,400/yr" if not performance else "$1,800-$3,000/yr"
        return "$900-$1,500/yr" if not performance else "$1,300-$2,200/yr"

    def _fallback_lifespan(self, query: VehicleQuery) -> str:
        make = str(query.make or "").lower()
        performance = self.is_sports_car(query)
        if make in {"toyota", "honda", "lexus", "acura", "mazda"} and not performance:
            return "200,000-280,000"
        if performance:
            return "140,000-220,000"
        return "160,000-240,000"

    def _fallback_insurance(self, query: VehicleQuery) -> str:
        make = str(query.make or "").lower()
        performance = self.is_sports_car(query)
        if performance:
            return "$220-$380/mo"
        if make in {"audi", "bmw", "mercedes", "mercedes-benz", "porsche", "lexus"}:
            return "$170-$280/mo"
        return "$120-$220/mo"

    def _fallback_common_problems(self, query: VehicleQuery, engine_spec: str) -> str:
        make = str(query.make or "").lower()
        performance = self.is_sports_car(query, {"engine_spec": engine_spec})
        if make in {"audi", "bmw", "mercedes", "mercedes-benz"}:
            return "Oil leaks; cooling-system wear; suspension or electronics issues"
        if make in {"mini"}:
            return "Cooling leaks; oil leaks; carbon buildup"
        if make in {"nissan", "infiniti"}:
            return "Turbo or cooling wear; suspension wear; electronics issues"
        if make in {"toyota", "honda", "lexus", "acura"}:
            return "Suspension wear; AC issues; deferred-maintenance oil consumption"
        if performance:
            return "Faster tire and brake wear; ignition or cooling stress; driveline wear"
        return "Suspension wear; aging electronics; cooling-system service"

    def _extract_response_text(self, payload: dict[str, Any]) -> str:
        output_text = payload.get("output_text")
        if isinstance(output_text, str) and output_text.strip():
            return output_text.strip()
        chunks: list[str] = []
        for item in payload.get("output") or []:
            if not isinstance(item, dict):
                continue
            for content in item.get("content") or []:
                if not isinstance(content, dict):
                    continue
                text = content.get("text")
                if isinstance(text, str) and text.strip():
                    chunks.append(text.strip())
        return "\n".join(chunks).strip()

    def _extract_json(self, text: str) -> dict[str, Any]:
        stripped = text.strip()
        try:
            return json.loads(stripped)
        except Exception:
            pass
        match = re.search(r"\{.*\}", stripped, re.S)
        if not match:
            return {}
        try:
            return json.loads(match.group(0))
        except Exception:
            return {}
