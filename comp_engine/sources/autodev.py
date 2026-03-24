from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from .base import SourceAdapter
from ..models import NormalizedListing, VehicleQuery


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class AutoDevAdapter(SourceAdapter):
    key = "autodev"
    label = "auto.dev"
    official = True
    fragile = False
    fields = [
        "year", "make", "model", "trim", "bodyStyle", "drivetrain", "engine",
        "transmission", "fuelType", "exteriorColor", "mileage", "price",
        "sellerType", "location", "vin", "dealerName", "imageUrls", "listingAgeDays",
    ]
    notes = "Official auto.dev vehicle listings API adapter. Enabled when AUTODEV_API_KEY is configured."

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.http_client.register_rate_limiter(self.key, 0.15)

    def is_enabled(self) -> bool:
        return self.config.enable_autodev and bool(self.config.autodev_api_key)

    def search_listings(self, query: VehicleQuery) -> list[dict[str, Any]]:
        if not self.is_enabled():
            return []
        headers = {
            "Authorization": f"Bearer {self.config.autodev_api_key}",
            "Accept": "application/json",
        }
        params_candidates = [
            {
                "vehicle.year": query.year,
                "vehicle.make": query.make.lower() or None,
                "vehicle.model": query.model.lower() or None,
                "vehicle.trim": query.trim or None,
                "zip": query.zip_code or None,
                "distance": 150 if query.zip_code else 500,
                "limit": min(self.config.max_source_results, 100),
            },
            {
                "vehicle.year": query.year,
                "vehicle.make": query.make.lower() or None,
                "vehicle.model": query.model.lower() or None,
                "zip": query.zip_code or None,
                "distance": 200 if query.zip_code else 500,
                "limit": min(self.config.max_source_results, 100),
            },
            {
                "vehicle.year": query.year,
                "vehicle.make": query.make.lower() or None,
                "vehicle.model": query.model.lower() or None,
                "limit": min(self.config.max_source_results, 100),
            },
        ]
        deduped: dict[str, dict[str, Any]] = {}
        for params in params_candidates:
            payload = self.http_client.get_json(
                "https://api.auto.dev/listings",
                params=params,
                headers=headers,
                source_key=self.key,
            )
            listings = payload.get("data") or []
            for listing in listings:
                if not isinstance(listing, dict):
                    continue
                vin = str(listing.get("vin") or listing.get("vehicle", {}).get("vin") or "").strip().upper()
                listing_id = vin or str(listing.get("@id") or "")
                if not listing_id:
                    continue
                deduped.setdefault(listing_id, listing)
            if len(deduped) >= 12:
                break
        return list(deduped.values())

    def normalize_listing(self, raw: dict[str, Any], query: VehicleQuery) -> NormalizedListing | None:
        vehicle = raw.get("vehicle") or {}
        retail = raw.get("retailListing") or {}
        wholesale = raw.get("wholesaleListing") or {}
        location = raw.get("location") or []
        seller_payload = retail or wholesale
        price = retail.get("price") or wholesale.get("price")
        mileage = retail.get("miles") or wholesale.get("miles")
        vin = str(raw.get("vin") or vehicle.get("vin") or "").strip().upper()
        source_listing_id = vin or str(raw.get("@id") or "")
        if not source_listing_id:
            return None
        listing_url = self._listing_url(raw, vin, retail)
        dealer_name = str(retail.get("dealer") or wholesale.get("dealer") or "").strip()
        city = str(seller_payload.get("city") or "").strip()
        state = str(seller_payload.get("state") or "").strip().upper()
        zip_code = str(seller_payload.get("zip") or "").strip()
        carfax_url = str(retail.get("carfaxUrl") or "").strip()
        metadata: dict[str, Any] = {}
        if carfax_url:
            metadata["carfax_url"] = carfax_url
        if raw.get("history") is not None:
            metadata["history"] = raw.get("history")
        return NormalizedListing(
            source=self.key,
            source_listing_id=source_listing_id,
            source_label=self.label,
            url=listing_url,
            fetched_at=_now_iso(),
            year=self._to_int(vehicle.get("year")),
            make=str(vehicle.get("make") or "").strip(),
            model=str(vehicle.get("model") or "").strip(),
            trim=str(vehicle.get("trim") or vehicle.get("series") or "").strip(),
            body_style=str(vehicle.get("style") or vehicle.get("bodyStyle") or "").strip(),
            drivetrain=str(vehicle.get("drivetrain") or "").strip(),
            engine=str(vehicle.get("engine") or "").strip(),
            transmission=str(vehicle.get("transmission") or "").strip(),
            fuel_type=str(vehicle.get("fuel") or "").strip(),
            exterior_color=str(vehicle.get("exteriorColor") or "").strip(),
            mileage=self._to_int(mileage),
            price=self._to_float(price),
            seller_type="dealer" if retail else "wholesale",
            location={
                "city": city,
                "state": state,
                "zip": zip_code,
                "lat": self._coord(location, 1),
                "lng": self._coord(location, 0),
            },
            vin=vin,
            condition="used" if retail.get("used") else "",
            accident_history_known=bool(raw.get("history")) if raw.get("history") is not None else None,
            clean_title_likely=None,
            listing_age_days=self._listing_age_days(raw.get("createdAt")),
            dealer_name=dealer_name,
            image_urls=[str(retail.get("primaryImage"))] if retail.get("primaryImage") else [],
            raw_payload=raw,
            spec_confidence=self._to_float(vehicle.get("confidence")) or 0.92,
            metadata=metadata,
        )

    def health_check(self) -> dict[str, Any]:
        health = super().health_check()
        if not self.is_enabled():
            return health
        try:
            self.http_client.get_json(
                "https://api.auto.dev/listings",
                params={"limit": 1},
                headers={
                    "Authorization": f"Bearer {self.config.autodev_api_key}",
                    "Accept": "application/json",
                },
                source_key=self.key,
            )
            health["status"] = "ok"
            health["message"] = "API key validated"
        except Exception as exc:  # noqa: BLE001
            health["status"] = "error"
            health["message"] = str(exc)
        return health

    def _listing_url(self, raw: dict[str, Any], vin: str, retail: dict[str, Any]) -> str:
        vdp = str(retail.get("vdp") or "").strip()
        if (
            (vdp.startswith("http://") or vdp.startswith("https://"))
            and "details.vast.com" not in vdp
        ):
            return vdp
        carfax_url = str(retail.get("carfaxUrl") or "").strip()
        if carfax_url.startswith("http://") or carfax_url.startswith("https://"):
            return carfax_url
        if vdp.startswith("http://") or vdp.startswith("https://"):
            return vdp
        return ""

    def _coord(self, location: list[Any], index: int) -> float | None:
        if not isinstance(location, list) or len(location) <= index:
            return None
        return self._to_float(location[index])

    def _listing_age_days(self, created_at: Any) -> int | None:
        raw = str(created_at or "").strip()
        if not raw:
            return None
        try:
            created = datetime.fromisoformat(raw.replace(" ", "T"))
            if created.tzinfo is None:
                created = created.replace(tzinfo=timezone.utc)
            delta = datetime.now(timezone.utc) - created.astimezone(timezone.utc)
            return max(0, delta.days)
        except ValueError:
            return None

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
