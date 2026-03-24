from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from .base import SourceAdapter
from ..models import NormalizedListing, VehicleQuery


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class OneAutoAdapter(SourceAdapter):
    key = "oneauto"
    label = "One Auto API"
    official = True
    fragile = False
    fields = [
        "year", "make", "model", "trim", "bodyStyle", "drivetrain", "engine",
        "transmission", "fuelType", "exteriorColor", "mileage", "price",
        "sellerType", "location", "dealerName", "imageUrls", "listingAgeDays",
    ]
    notes = (
        "Official One Auto API wrapper over Marketcheck inventory search. "
        "Enabled when ONEAUTO_API_KEY is configured. The current live service uses GBP/postcode-oriented inventory search."
    )
    endpoint = "https://api.oneautoapi.com/marketcheck/inventorysearch/v2"

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.http_client.register_rate_limiter(self.key, 0.2)

    def is_enabled(self) -> bool:
        return self.config.enable_oneauto and bool(self.config.oneauto_api_key)

    def search_listings(self, query: VehicleQuery) -> list[dict[str, Any]]:
        if not self.is_enabled():
            return []

        params = {
            "price_to_gbp": 100000,
            "required_manufacturers": query.make,
            "advert_qty": min(self.config.max_source_results, 50),
            "page": 1,
        }
        if query.mileage:
            params["current_mileage_from"] = max(0, query.mileage - 40000)
            params["current_mileage_to"] = query.mileage + 40000

        payload = self.http_client.get_json(
            self.endpoint,
            params=params,
            headers={"x-api-key": self.config.oneauto_api_key},
            source_key=self.key,
        )
        if not payload.get("success"):
            error_message = str((payload.get("result") or {}).get("error") or payload.get("error") or "One Auto API request failed.")
            raise RuntimeError(error_message)

        adverts = ((payload.get("result") or {}).get("advert_list") or [])
        results = [advert for advert in adverts if isinstance(advert, dict)]
        filtered: list[dict[str, Any]] = []
        for advert in results:
            normalized = self.normalize_listing(advert, query)
            if normalized is None:
                continue
            if normalized.year and query.year and abs(normalized.year - query.year) > 2:
                continue
            if normalized.model and query.model and query.model.lower() not in normalized.model.lower():
                heading = str(advert.get("advert_heading") or "").lower()
                if query.model.lower() not in heading:
                    continue
            filtered.append(advert)
        return filtered[: self.config.max_source_results]

    def normalize_listing(self, raw: dict[str, Any], query: VehicleQuery) -> NormalizedListing | None:
        vehicle = raw.get("vehicle_data") or {}
        dealer = raw.get("dealer_details") or {}
        location = raw.get("vehicle_location_details") or {}
        listing_url = str(raw.get("vehicle_details_page_url") or "").strip()
        source_url = str(raw.get("source_url") or "").strip()
        trim = " ".join(
            part
            for part in [
                str(vehicle.get("trim_desc") or "").strip(),
                str(vehicle.get("variant_desc") or "").strip(),
            ]
            if part
        ).strip()
        if not trim:
            trim = str(raw.get("advert_heading") or "").strip()

        source_listing_id = str(raw.get("advert_id") or listing_url or source_url).strip()
        if not source_listing_id:
            return None

        return NormalizedListing(
            source=self.key,
            source_listing_id=source_listing_id,
            source_label=self.label,
            url=listing_url or source_url,
            fetched_at=_now_iso(),
            year=self._to_int(vehicle.get("first_registration_year")),
            make=str(vehicle.get("manufacturer_desc") or query.make or "").strip(),
            model=str(vehicle.get("model_range_desc") or query.model or "").strip(),
            trim=trim,
            body_style=str(vehicle.get("body_type_desc") or "").strip(),
            drivetrain=str(vehicle.get("drivetrain_desc") or "").strip(),
            engine=str(vehicle.get("engine_data") or "").strip(),
            transmission=str(vehicle.get("transmission_desc") or "").strip(),
            fuel_type=str(vehicle.get("fuel_type_desc") or "").strip(),
            exterior_color=str(raw.get("colour") or "").strip(),
            mileage=self._to_int(raw.get("mileage_observed")),
            price=self._to_float(raw.get("advertised_price_gbp")),
            seller_type=str(raw.get("seller_type") or "dealer").strip().lower(),
            location={
                "city": str(location.get("city") or dealer.get("city") or "").strip(),
                "state": str(location.get("county") or dealer.get("country") or "").strip(),
                "zip": str(location.get("post_code") or dealer.get("post_code") or "").strip(),
                "lat": self._to_float(location.get("latitude") or dealer.get("latitude")),
                "lng": self._to_float(location.get("longitude") or dealer.get("longitude")),
            },
            listing_age_days=self._to_int(raw.get("days_on_market")),
            dealer_name=str(dealer.get("dealer_name") or location.get("seller_name") or "").strip(),
            image_urls=[str(link) for link in (raw.get("image_links") or []) if link],
            raw_payload=raw,
            spec_confidence=0.78,
            metadata={
                "currency": "GBP",
                "source_url": source_url,
            },
        )

    def health_check(self) -> dict[str, Any]:
        health = super().health_check()
        if not self.is_enabled():
            return health
        try:
            self.http_client.get_json(
                self.endpoint,
                params={
                    "price_to_gbp": 50000,
                    "required_manufacturers": "BMW",
                    "advert_qty": 1,
                    "page": 1,
                },
                headers={"x-api-key": self.config.oneauto_api_key},
                source_key=self.key,
            )
            health["status"] = "ok"
            health["message"] = "API key validated"
        except Exception as exc:  # noqa: BLE001
            health["status"] = "error"
            health["message"] = str(exc)
        return health

    def _to_int(self, value: Any) -> int | None:
        digits = "".join(ch for ch in str(value or "") if ch.isdigit())
        return int(digits) if digits else None

    def _to_float(self, value: Any) -> float | None:
        try:
            if value in (None, ""):
                return None
            return float(str(value))
        except ValueError:
            return None
