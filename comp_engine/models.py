from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any


CACHE_SCHEMA_VERSION = "7"


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(slots=True)
class VehicleQuery:
    raw_input: str = ""
    year: int | None = None
    make: str = ""
    model: str = ""
    trim: str = ""
    mileage: int | None = None
    asking_price: float | None = None
    drivetrain: str = ""
    body_style: str = ""
    engine: str = ""
    transmission: str = ""
    fuel_type: str = ""
    exterior_color: str = ""
    title_status: str = ""
    condition: str = ""
    zip_code: str = ""
    state: str = ""
    seller_type: str = ""
    vin: str = ""
    latitude: float | None = None
    longitude: float | None = None
    manual_csv: str = ""
    manual_urls: list[str] = field(default_factory=list)
    manual_listings: list[dict[str, Any]] = field(default_factory=list)
    custom_listings: list[dict[str, Any]] = field(default_factory=list)

    def minimum_details_present(self) -> bool:
        return bool(self.year and self.make and self.model and self.mileage)

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        return payload

    def cache_key(self, enabled_sources: list[str]) -> str:
        payload = self.as_dict()
        payload["enabled_sources"] = enabled_sources
        payload["cache_schema_version"] = CACHE_SCHEMA_VERSION
        digest = hashlib.sha256(
            json.dumps(payload, sort_keys=True, default=str).encode("utf-8")
        ).hexdigest()
        return f"valuation:{digest}"


@dataclass(slots=True)
class NormalizedListing:
    source: str
    source_listing_id: str
    source_label: str
    url: str
    fetched_at: str
    year: int | None = None
    make: str = ""
    model: str = ""
    trim: str = ""
    body_style: str = ""
    drivetrain: str = ""
    engine: str = ""
    transmission: str = ""
    fuel_type: str = ""
    exterior_color: str = ""
    mileage: int | None = None
    price: float | None = None
    seller_type: str = ""
    location: dict[str, Any] = field(default_factory=dict)
    vin: str = ""
    title_status: str = ""
    condition: str = ""
    accident_history_known: bool | None = None
    clean_title_likely: bool | None = None
    listing_age_days: int | None = None
    dealer_name: str = ""
    image_urls: list[str] = field(default_factory=list)
    raw_payload: dict[str, Any] = field(default_factory=dict)
    spec_confidence: float = 0.0
    relevance_score: float = 0.0
    match_tier: str = "Tier 3"
    adjusted_price: float | None = None
    adjustment_notes: list[str] = field(default_factory=list)
    exclude_reason: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def dedupe_key(self) -> str:
        if self.vin:
            return f"vin:{self.vin}"
        if self.url:
            return f"url:{self.url}"
        return f"{self.source}:{self.source_listing_id}:{self.year}:{self.price}"

    def completeness_score(self) -> int:
        score = 0
        for field_name in (
            "vin",
            "mileage",
            "trim",
            "body_style",
            "drivetrain",
            "title_status",
            "condition",
            "dealer_name",
        ):
            if getattr(self, field_name):
                score += 1
        score += len(self.image_urls)
        return score

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class SourceMetadata:
    key: str
    label: str
    official: bool
    fragile: bool
    enabled: bool
    fields: list[str]
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class SourceRunResult:
    metadata: SourceMetadata
    raw_listings: list[dict[str, Any]] = field(default_factory=list)
    normalized_listings: list[NormalizedListing] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    status: str = "ok"
    message: str = ""

    def to_health_dict(self) -> dict[str, Any]:
        return {
            "key": self.metadata.key,
            "label": self.metadata.label,
            "official": self.metadata.official,
            "fragile": self.metadata.fragile,
            "enabled": self.metadata.enabled,
            "status": self.status,
            "message": self.message,
            "count": len(self.normalized_listings),
            "errors": self.errors,
        }
