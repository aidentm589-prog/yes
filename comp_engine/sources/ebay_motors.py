from __future__ import annotations

import base64
import json
import re
import urllib.parse
from datetime import datetime, timedelta, timezone
from typing import Any

from .base import SourceAdapter
from ..models import NormalizedListing, VehicleQuery


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class EbayMotorsAdapter(SourceAdapter):
    key = "ebay_motors"
    label = "eBay Motors"
    official = True
    fragile = False
    fields = [
        "year", "make", "model", "trim", "price", "mileage", "condition",
        "sellerType", "location", "imageUrls", "url",
    ]
    notes = "Official eBay Browse API adapter. Requires EBAY_CLIENT_ID and EBAY_CLIENT_SECRET."

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.http_client.register_rate_limiter(self.key, 0.25)
        self._token: str = ""
        self._token_expires_at = datetime.now(timezone.utc)

    def is_enabled(self) -> bool:
        return (
            self.config.enable_ebay_motors
            and bool(self.config.ebay_client_id)
            and bool(self.config.ebay_client_secret)
        )

    def search_listings(self, query: VehicleQuery) -> list[dict[str, Any]]:
        if not self.is_enabled():
            return []
        access_token = self._ensure_access_token()
        params = {
            "q": " ".join(
                part for part in [
                    str(query.year or "").strip(),
                    query.make,
                    query.model,
                    query.trim,
                ] if part
            ).strip(),
            "limit": min(self.config.max_source_results, 50),
            "category_ids": "6001",
            "filter": "conditions:{USED|CERTIFIED_PRE_OWNED}",
        }
        payload = self.http_client.get_json(
            "https://api.ebay.com/buy/browse/v1/item_summary/search",
            params=params,
            headers={
                "Authorization": f"Bearer {access_token}",
                "X-EBAY-C-MARKETPLACE-ID": self.config.ebay_marketplace_id,
                "Accept": "application/json",
            },
            source_key=self.key,
        )
        return payload.get("itemSummaries", [])

    def normalize_listing(self, raw: dict[str, Any], query: VehicleQuery) -> NormalizedListing | None:
        title = str(raw.get("title") or "").strip()
        year = self._extract_year(title)
        make, model, trim = self._extract_make_model_trim(title, query)
        price_block = raw.get("price") or {}
        location = raw.get("itemLocation") or {}
        image = raw.get("image") or {}
        return NormalizedListing(
            source=self.key,
            source_listing_id=str(raw.get("itemId") or raw.get("legacyItemId") or title),
            source_label=self.label,
            url=str(raw.get("itemWebUrl") or raw.get("itemHref") or "").strip(),
            fetched_at=_now_iso(),
            year=year,
            make=make,
            model=model,
            trim=trim,
            mileage=self._extract_mileage(title + " " + str(raw.get("shortDescription") or "")),
            price=self._to_float(price_block.get("value")),
            seller_type="private",
            location={
                "city": str(location.get("city") or "").strip(),
                "state": str(location.get("stateOrProvince") or "").strip().upper(),
                "zip": str(location.get("postalCode") or "").strip(),
                "country": str(location.get("country") or "").strip(),
            },
            condition=str(raw.get("condition") or "").strip(),
            image_urls=[str(image.get("imageUrl"))] if image.get("imageUrl") else [],
            raw_payload=raw,
            spec_confidence=0.55,
        )

    def health_check(self) -> dict[str, Any]:
        health = super().health_check()
        if not self.is_enabled():
            return health
        try:
            self._ensure_access_token()
            health["status"] = "ok"
            health["message"] = "OAuth credentials validated"
        except Exception as exc:  # noqa: BLE001
            health["status"] = "error"
            health["message"] = str(exc)
        return health

    def _ensure_access_token(self) -> str:
        if self._token and datetime.now(timezone.utc) < self._token_expires_at:
            return self._token

        basic = base64.b64encode(
            f"{self.config.ebay_client_id}:{self.config.ebay_client_secret}".encode("utf-8")
        ).decode("utf-8")
        body = urllib.parse.urlencode(
            {
                "grant_type": "client_credentials",
                "scope": self.config.ebay_scope,
            }
        ).encode("utf-8")
        status, response_body, _ = self.http_client.request(
            "POST",
            "https://api.ebay.com/identity/v1/oauth2/token",
            data=body,
            headers={
                "Authorization": f"Basic {basic}",
                "Content-Type": "application/x-www-form-urlencoded",
                "Accept": "application/json",
            },
            source_key=self.key,
        )
        if status >= 400:
            raise RuntimeError(
                f"eBay token request failed with {status}: {response_body.decode('utf-8', 'ignore')}"
            )
        payload = json.loads(response_body.decode("utf-8"))
        self._token = str(payload.get("access_token") or "")
        expires_in = int(payload.get("expires_in") or 3000)
        self._token_expires_at = datetime.now(timezone.utc) + timedelta(seconds=max(60, expires_in - 60))
        return self._token

    def _extract_year(self, text: str) -> int | None:
        match = re.search(r"\b(19\d{2}|20\d{2})\b", text)
        return int(match.group(1)) if match else None

    def _extract_make_model_trim(self, title: str, query: VehicleQuery) -> tuple[str, str, str]:
        lowered = title.lower()
        make = query.make if query.make.lower() in lowered else ""
        model = query.model if query.model.lower() in lowered else ""
        trim = ""
        if make and model:
            pattern = re.escape(query.model.lower())
            parts = re.split(pattern, lowered, maxsplit=1)
            if len(parts) == 2:
                trim = parts[1].strip(" -").title()
        return make or query.make, model or query.model, trim

    def _extract_mileage(self, text: str) -> int | None:
        match = re.search(r"\b(\d{1,3}(?:[,\s]\d{3})+)\s*(?:miles?|mi)\b", text, re.I)
        if not match:
            return None
        return int(match.group(1).replace(",", "").replace(" ", ""))

    def _to_float(self, value: Any) -> float | None:
        try:
            if value in (None, ""):
                return None
            return float(str(value))
        except ValueError:
            return None
