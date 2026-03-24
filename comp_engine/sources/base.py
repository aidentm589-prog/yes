from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from ..config import EngineConfig
from ..http import HttpClient
from ..models import NormalizedListing, SourceMetadata, VehicleQuery
from ..storage import SQLiteRepository


class SourceAdapter(ABC):
    key = "base"
    label = "Base"
    official = False
    fragile = False
    fields: list[str] = []
    notes = ""

    def __init__(
        self,
        config: EngineConfig,
        http_client: HttpClient,
        repository: SQLiteRepository,
    ) -> None:
        self.config = config
        self.http_client = http_client
        self.repository = repository

    @abstractmethod
    def is_enabled(self) -> bool:
        raise NotImplementedError

    @abstractmethod
    def search_listings(self, query: VehicleQuery) -> list[dict[str, Any]]:
        raise NotImplementedError

    @abstractmethod
    def normalize_listing(self, raw: dict[str, Any], query: VehicleQuery) -> NormalizedListing | None:
        raise NotImplementedError

    def enrich_listings(
        self,
        listings: list[NormalizedListing],
        query: VehicleQuery,
    ) -> list[NormalizedListing]:
        return listings

    def get_source_metadata(self) -> SourceMetadata:
        return SourceMetadata(
            key=self.key,
            label=self.label,
            official=self.official,
            fragile=self.fragile,
            enabled=self.is_enabled(),
            fields=list(self.fields),
            notes=self.notes,
        )

    def health_check(self) -> dict[str, Any]:
        metadata = self.get_source_metadata()
        status = "ok" if metadata.enabled else "disabled"
        message = "" if metadata.enabled else "source disabled by config or missing credentials"
        return {
            "key": metadata.key,
            "label": metadata.label,
            "official": metadata.official,
            "fragile": metadata.fragile,
            "enabled": metadata.enabled,
            "status": status,
            "message": message,
        }

    # Compatibility aliases to match the requested adapter contract.
    def searchListings(self, query: VehicleQuery) -> list[dict[str, Any]]:  # noqa: N802
        return self.search_listings(query)

    def normalizeListing(self, raw: dict[str, Any], query: VehicleQuery) -> NormalizedListing | None:  # noqa: N802,E501
        return self.normalize_listing(raw, query)

    def getSourceMetadata(self) -> SourceMetadata:  # noqa: N802
        return self.get_source_metadata()

    def healthCheck(self) -> dict[str, Any]:  # noqa: N802
        return self.health_check()
