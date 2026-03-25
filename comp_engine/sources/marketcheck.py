from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from .base import SourceAdapter
from ..models import NormalizedListing, VehicleQuery


LOGGER = logging.getLogger(__name__)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class MarketCheckBaseAdapter(SourceAdapter):
    official = True
    fragile = False
    fields = [
        "year", "make", "model", "trim", "bodyStyle", "drivetrain", "mileage",
        "price", "sellerType", "vin", "location", "dealerName", "imageUrls",
    ]
    endpoint = ""
    seller_type = "dealer"

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.http_client.register_rate_limiter(self.key, 0.25)

    def is_enabled(self) -> bool:
        return bool(self.config.marketcheck_api_key and self.config.enable_marketcheck)

    def search_listings(self, query: VehicleQuery) -> list[dict[str, Any]]:
        if not self.is_enabled() or not self.endpoint:
            LOGGER.info(
                "MarketCheck skipped: enabled=%s key_present=%s",
                bool(getattr(self.config, "enable_marketcheck", False)),
                bool(self.config.marketcheck_api_key),
            )
            return []
        params = {
            "api_key": self.config.marketcheck_api_key,
            "year": query.year,
            "make": query.make,
            "model": query.model,
            "trim": query.trim or None,
            "zip": query.zip_code or None,
            "state": query.state or None,
            "radius": 250 if query.zip_code else 500,
            "rows": min(self.config.max_source_results, 50),
            "car_type": "used",
        }
        LOGGER.info(
            "MarketCheck request: enabled=%s key_present=%s year=%s make=%s model=%s trim=%s zip=%s state=%s rows=%s",
            bool(getattr(self.config, "enable_marketcheck", False)),
            bool(self.config.marketcheck_api_key),
            query.year,
            query.make,
            query.model,
            query.trim,
            query.zip_code,
            query.state,
            params["rows"],
        )
        payload = self.http_client.get_json(self.endpoint, params=params, source_key=self.key)
        listings = payload.get("listings") or payload.get("data") or []
        normalized = [listing for listing in listings if isinstance(listing, dict)]
        LOGGER.info("MarketCheck response: status=ok results=%s", len(normalized))
        return normalized

    def health_check(self) -> dict[str, Any]:
        health = super().health_check()
        if not self.is_enabled():
            return health
        try:
            payload = self.http_client.get_json(
                self.endpoint,
                params={
                    "api_key": self.config.marketcheck_api_key,
                    "rows": 1,
                    "car_type": "used",
                },
                source_key=self.key,
            )
        except Exception as exc:  # noqa: BLE001
            message = str(exc).lower()
            health["status"] = "error"
            if "401" in message or "403" in message or "auth" in message or "invalid" in message:
                health["message"] = "auth failed"
            elif "timeout" in message:
                health["message"] = "timeout"
            else:
                health["message"] = f"bad response: {exc}"
            return health

        listings = payload.get("listings") or payload.get("data") or []
        if isinstance(listings, list) and listings:
            health["status"] = "ok"
            health["message"] = "API key validated"
        else:
            health["status"] = "ok"
            health["message"] = "no listings returned"
        return health

    def normalize_listing(self, raw: dict[str, Any], query: VehicleQuery) -> NormalizedListing | None:
        dealer = raw.get("dealer") or {}
        build = raw.get("build") or {}
        media = raw.get("media") or {}
        location = raw.get("car_location") or {}
        raw_zip = (
            location.get("zip")
            or dealer.get("zip")
            or raw.get("zip")
        )
        listing_age_days = raw.get("dom_active") or raw.get("dom")
        return NormalizedListing(
            source=self.key,
            source_listing_id=str(raw.get("id") or raw.get("vin") or raw.get("heading", "")),
            source_label=self.label,
            url=str(raw.get("vdp_url") or raw.get("url") or "").strip(),
            fetched_at=_now_iso(),
            year=self._to_int(raw.get("year") or build.get("year")),
            make=str(raw.get("make") or build.get("make") or "").strip(),
            model=str(raw.get("model") or build.get("model") or "").strip(),
            trim=str(raw.get("trim") or build.get("trim") or "").strip(),
            body_style=str(raw.get("body_type") or build.get("body_type") or build.get("body_style") or "").strip(),
            drivetrain=str(raw.get("drivetrain") or build.get("drivetrain") or "").strip(),
            engine=str(raw.get("engine") or build.get("engine") or "").strip(),
            transmission=str(raw.get("transmission") or build.get("transmission") or "").strip(),
            fuel_type=str(raw.get("fuel_type") or build.get("fuel_type") or "").strip(),
            exterior_color=str(raw.get("exterior_color") or "").strip(),
            mileage=self._to_int(raw.get("miles") or raw.get("mileage")),
            price=self._to_float(raw.get("price")),
            seller_type=self.seller_type,
            location={
                "city": str(location.get("city") or dealer.get("city") or "").strip(),
                "state": str(location.get("state") or dealer.get("state") or "").strip().upper(),
                "zip": str(raw_zip or "").strip(),
                "lat": self._to_float(location.get("lat") or dealer.get("latitude")),
                "lng": self._to_float(location.get("lng") or dealer.get("longitude")),
            },
            vin=str(raw.get("vin") or "").strip().upper(),
            title_status=str(raw.get("title_status") or "").strip(),
            condition=str(raw.get("condition") or "").strip(),
            listing_age_days=self._to_int(listing_age_days),
            dealer_name=str(dealer.get("name") or raw.get("seller_name") or "").strip(),
            image_urls=self._image_urls(media),
            raw_payload=raw,
            spec_confidence=0.9,
        )

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

    def _image_urls(self, media: dict[str, Any]) -> list[str]:
        links = media.get("photo_links") or media.get("photo_links_cached") or []
        return [str(link) for link in links if link]


class MarketCheckDealerAdapter(MarketCheckBaseAdapter):
    key = "marketcheck"
    label = "MarketCheck"
    notes = "Official MarketCheck active used-car search adapter. Enabled only when COMP_ENABLE_MARKETCHECK=true and MARKETCHECK_API_KEY is configured."
    endpoint = "https://api.marketcheck.com/v2/search/car/active"
    seller_type = "dealer"

    def is_enabled(self) -> bool:
        return self.config.enable_marketcheck_dealer and super().is_enabled()


class MarketCheckPrivatePartyAdapter(MarketCheckBaseAdapter):
    key = "marketcheck_private"
    label = "MarketCheck Private Party"
    notes = "Official private-party inventory adapter. Enabled only when MARKETCHECK_API_KEY is configured."
    endpoint = "https://api.marketcheck.com/v2/search/car/fsbo/active"
    seller_type = "private"

    def is_enabled(self) -> bool:
        return self.config.enable_marketcheck_private and super().is_enabled()
