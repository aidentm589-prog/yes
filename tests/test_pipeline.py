from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from typing import Any

from comp_engine.config import EngineConfig
from comp_engine.engine import VehicleCompsEngine
from comp_engine.models import NormalizedListing, VehicleQuery
from comp_engine.sources.base import SourceAdapter


class FakeAdapter(SourceAdapter):
    key = "fake_source"
    label = "Fake Source"
    official = True
    fragile = False
    fields = ["year", "make", "model", "trim", "price", "mileage"]

    def is_enabled(self) -> bool:
        return True

    def search_listings(self, query: VehicleQuery) -> list[dict[str, Any]]:
        return [
            {"id": "1", "year": 2014, "make": "Audi", "model": "A4", "trim": "Premium Plus", "price": 8200, "mileage": 104000},
            {"id": "2", "year": 2014, "make": "Audi", "model": "A4", "trim": "Premium Plus", "price": 8600, "mileage": 101000},
            {"id": "3", "year": 2014, "make": "Audi", "model": "A4", "trim": "Premium", "price": 7800, "mileage": 110000},
        ]

    def normalize_listing(self, raw: dict[str, Any], query: VehicleQuery) -> NormalizedListing | None:
        return NormalizedListing(
            source=self.key,
            source_listing_id=str(raw["id"]),
            source_label=self.label,
            url="",
            fetched_at="2026-03-23T00:00:00+00:00",
            year=int(raw["year"]),
            make=str(raw["make"]),
            model=str(raw["model"]),
            trim=str(raw["trim"]),
            mileage=int(raw["mileage"]),
            price=float(raw["price"]),
            seller_type="private",
        )


class FakeEngine(VehicleCompsEngine):
    def _build_adapters(self) -> list[Any]:
        return [FakeAdapter(self.config, self.http_client, self.repository)]


class PipelineTests(unittest.TestCase):
    def test_pipeline_returns_buy_price_and_comps(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            config = EngineConfig.from_env(Path(temp_dir))
            config.sqlite_path = Path(temp_dir) / "comps.db"
            engine = FakeEngine(config)
            result = engine.evaluate({"vehicle_input": "2014 audi a4 premium plus 105000 miles"})
            self.assertEqual(result["status"], "complete")
            self.assertEqual(result["comparable_count"], 3)
            self.assertIn("safe_buy_value", result["overall_range"])
            self.assertTrue(result["sample_listings"][0]["price"].startswith("$"))

    def test_bulk_pipeline_evaluates_multiple_cars(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            config = EngineConfig.from_env(Path(temp_dir))
            config.sqlite_path = Path(temp_dir) / "comps.db"
            engine = FakeEngine(config)
            bulk_text = """
$4,995
2014 Audi A4 Premium Plus Sedan 4D
Boston, MA
105K miles

$4,500
2014 Audi A4 Premium Sedan 4D
Providence, RI
110K miles
            """.strip()
            result = engine.evaluate({"evaluation_mode": "bulk", "vehicle_input": bulk_text})
            self.assertEqual(result["mode"], "bulk")
            self.assertEqual(result["summary"]["total_entries"], 2)
            self.assertEqual(result["summary"]["evaluated_entries"], 2)
            self.assertEqual(len(result["items"]), 2)
            self.assertEqual(result["items"][0]["status"], "complete")
            self.assertIn("safe_buy_value", result["items"][0])


if __name__ == "__main__":
    unittest.main()
