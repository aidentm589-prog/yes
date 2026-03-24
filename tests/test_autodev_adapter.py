from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from comp_engine.config import EngineConfig
from comp_engine.http import HttpClient
from comp_engine.query_parser import parse_vehicle_query
from comp_engine.sources.autodev import AutoDevAdapter
from comp_engine.storage import SQLiteRepository


class AutoDevAdapterTests(unittest.TestCase):
    def test_normalizes_retail_listing(self) -> None:
        raw = {
            "@id": "https://api.auto.dev/listings/WAUAFAFL1EA078621",
            "vin": "WAUAFAFL1EA078621",
            "createdAt": "2026-03-08 00:10:31",
            "location": [-122.97491, 44.93801],
            "vehicle": {
                "confidence": 0.995,
                "drivetrain": "FWD",
                "engine": "2.0L 4Cyl premium unleaded (required)",
                "exteriorColor": "Black",
                "fuel": "Premium Unleaded (Required)",
                "make": "Audi",
                "model": "A4",
                "style": "Sedan",
                "transmission": "Automatic",
                "trim": "2.0T Premium",
                "year": 2014,
            },
            "retailListing": {
                "dealer": "Honda of Salem",
                "city": "Salem",
                "state": "OR",
                "zip": "97301",
                "miles": 124279,
                "price": 9995,
                "primaryImage": "https://retail.photos.vin/WAUAFAFL1EA078621-1.jpg",
                "carfaxUrl": "https://www.carfax.com/VehicleHistory/p/Report.cfx?vin=WAUAFAFL1EA078621",
                "used": True,
            },
        }
        with tempfile.TemporaryDirectory() as temp_dir:
            config = EngineConfig.from_env(Path(temp_dir))
            config.enable_autodev = True
            config.autodev_api_key = "test-key"
            repository = SQLiteRepository(Path(temp_dir) / "comp.db")
            adapter = AutoDevAdapter(config, HttpClient(), repository)
            query = parse_vehicle_query({"vehicle_input": "2014 audi a4 105000 miles"})
            listing = adapter.normalize_listing(raw, query)

        self.assertIsNotNone(listing)
        assert listing is not None
        self.assertEqual(listing.source_label, "auto.dev")
        self.assertEqual(listing.vin, "WAUAFAFL1EA078621")
        self.assertEqual(listing.trim, "2.0T Premium")
        self.assertEqual(listing.mileage, 124279)
        self.assertEqual(listing.price, 9995.0)
        self.assertEqual(listing.location["city"], "Salem")
        self.assertEqual(listing.location["state"], "OR")
        self.assertEqual(listing.dealer_name, "Honda of Salem")
        self.assertTrue(listing.image_urls)

    def test_falls_back_to_x_api_key_header_on_auth_error(self) -> None:
        class StubHttpClient:
            def __init__(self) -> None:
                self.calls: list[dict[str, str]] = []

            def register_rate_limiter(self, key: str, min_interval_seconds: float) -> None:
                return None

            def get_json(self, url: str, *, params=None, headers=None, source_key=""):
                self.calls.append(headers or {})
                if headers and headers.get("Authorization"):
                    raise RuntimeError("GET https://api.auto.dev/listings failed with 401: unauthorized")
                return {
                    "data": [
                        {
                            "@id": "listing-1",
                            "vin": "19XFA16509L005583",
                            "vehicle": {
                                "year": 2009,
                                "make": "Honda",
                                "model": "Civic",
                                "trim": "LX",
                            },
                            "retailListing": {
                                "miles": 111917,
                                "price": 6595,
                            },
                        }
                    ]
                }

        with tempfile.TemporaryDirectory() as temp_dir:
            config = EngineConfig.from_env(Path(temp_dir))
            config.enable_autodev = True
            config.autodev_api_key = "test-key"
            repository = SQLiteRepository(Path(temp_dir) / "comp.db")
            adapter = AutoDevAdapter(config, StubHttpClient(), repository)
            query = parse_vehicle_query({"vehicle_input": "2009 honda civic 145000 miles"})
            listings = adapter.search_listings(query)

        self.assertEqual(len(listings), 1)
        self.assertGreaterEqual(len(adapter.http_client.calls), 2)
        self.assertIn("Authorization", adapter.http_client.calls[0])
        self.assertTrue(
            any("x-api-key" in call or "X-API-Key" in call for call in adapter.http_client.calls[1:])
        )


if __name__ == "__main__":
    unittest.main()
