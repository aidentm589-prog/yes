from __future__ import annotations

import unittest

from comp_engine.detailed_report import DetailedVehicleReportService
from comp_engine.http import HttpClient
from comp_engine.models import NormalizedListing, VehicleQuery


class DetailedVehicleReportTests(unittest.TestCase):
    def test_should_generate_detailed_vehicle_report(self) -> None:
        service = DetailedVehicleReportService(HttpClient())
        self.assertTrue(service.should_generate_detailed_vehicle_report({"detailed_vehicle_report": "on"}))
        self.assertFalse(service.should_generate_detailed_vehicle_report({"detailed_vehicle_report": "off"}))

    def test_fallback_report_formats_sections(self) -> None:
        service = DetailedVehicleReportService(HttpClient())
        query = VehicleQuery(
            year=2021,
            make="BMW",
            model="3 Series",
            trim="M340i xDrive",
            mileage=80000,
            engine="3.0L Turbo I6",
            transmission="Automatic",
            drivetrain="AWD",
        )
        result = {
            "overall_range": {"market_value": "$39,000"},
        }

        report = service.get_detailed_vehicle_report(query, result, [])

        self.assertTrue(report["requested"])
        self.assertIn(report["status"], {"complete", "partial"})
        self.assertTrue(any(section["title"] == "Vehicle Specs" for section in report["sections"]))
        self.assertTrue(report["sports_car"])

    def test_comp_consensus_drives_hard_specs(self) -> None:
        service = DetailedVehicleReportService(HttpClient())
        query = VehicleQuery(year=2018, make="BMW", model="3 Series", trim="330i", mileage=60000)
        listings = [
            NormalizedListing(
                source="autodev",
                source_listing_id="1",
                source_label="auto.dev",
                url="https://example.com/1",
                fetched_at="2026-01-01T00:00:00+00:00",
                engine="2.0L Turbo I4",
                transmission="Automatic",
                drivetrain="RWD",
                fuel_type="Gasoline",
                spec_confidence=0.95,
            ),
            NormalizedListing(
                source="autodev",
                source_listing_id="2",
                source_label="auto.dev",
                url="https://example.com/2",
                fetched_at="2026-01-01T00:00:00+00:00",
                engine="2.0L Turbo I4",
                transmission="Automatic",
                drivetrain="RWD",
                fuel_type="Gasoline",
                spec_confidence=0.88,
            ),
            NormalizedListing(
                source="craigslist",
                source_listing_id="3",
                source_label="Craigslist",
                url="https://example.com/3",
                fetched_at="2026-01-01T00:00:00+00:00",
                engine="3.0L I6",
                transmission="Manual",
                drivetrain="AWD",
                fuel_type="Gasoline",
                spec_confidence=0.35,
            ),
        ]

        report = service.get_detailed_vehicle_report(query, {"overall_range": {"market_value": "$24,000"}}, listings)
        specs = next(section for section in report["sections"] if section["title"] == "Vehicle Specs")
        values = {item["label"]: item["value"] for item in specs["items"]}

        self.assertEqual(values.get("Engine Spec"), "2.0L Turbo I4")
        self.assertEqual(values.get("Transmission Spec"), "Automatic")
        self.assertEqual(values.get("Drivetrain"), "RWD")


if __name__ == "__main__":
    unittest.main()
