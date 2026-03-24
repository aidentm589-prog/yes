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


if __name__ == "__main__":
    unittest.main()
