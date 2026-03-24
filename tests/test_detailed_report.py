from __future__ import annotations

import unittest

from comp_engine.detailed_report import DetailedVehicleReportService
from comp_engine.http import HttpClient
from comp_engine.models import VehicleQuery


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


if __name__ == "__main__":
    unittest.main()
