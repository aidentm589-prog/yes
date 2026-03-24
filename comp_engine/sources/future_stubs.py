from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .base import SourceAdapter
from ..models import NormalizedListing, VehicleQuery


@dataclass(slots=True)
class FutureStubDefinition:
    key: str
    label: str
    official: bool
    fragile: bool
    notes: str


class FutureSourceStubAdapter(SourceAdapter):
    def __init__(
        self,
        *args: Any,
        definition: FutureStubDefinition,
        **kwargs: Any,
    ) -> None:
        super().__init__(*args, **kwargs)
        self.key = definition.key
        self.label = definition.label
        self.official = definition.official
        self.fragile = definition.fragile
        self.notes = definition.notes

    def is_enabled(self) -> bool:
        return False

    def search_listings(self, query: VehicleQuery) -> list[dict[str, Any]]:
        return []

    def normalize_listing(self, raw: dict[str, Any], query: VehicleQuery) -> NormalizedListing | None:
        return None


def build_future_source_stubs(*args: Any, **kwargs: Any) -> list[FutureSourceStubAdapter]:
    definitions = [
        FutureStubDefinition(
            key="cars_com",
            label="Cars.com",
            official=False,
            fragile=True,
            notes="Placeholder only. No compliant automated integration is enabled by default.",
        ),
        FutureStubDefinition(
            key="autotrader",
            label="Autotrader",
            official=False,
            fragile=True,
            notes="Placeholder only. No compliant automated integration is enabled by default.",
        ),
        FutureStubDefinition(
            key="cargurus",
            label="CarGurus",
            official=False,
            fragile=True,
            notes="Placeholder only. No compliant automated integration is enabled by default.",
        ),
        FutureStubDefinition(
            key="facebook_marketplace",
            label="Facebook Marketplace",
            official=False,
            fragile=True,
            notes="Unsupported by default unless a compliant approved integration path is available.",
        ),
    ]
    return [
        FutureSourceStubAdapter(*args, **kwargs, definition=definition)
        for definition in definitions
    ]
