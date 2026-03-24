from __future__ import annotations

import unittest

from comp_engine.query_parser import parse_vehicle_query


class QueryParserTests(unittest.TestCase):
    def test_parses_freeform_vehicle_input(self) -> None:
        query = parse_vehicle_query(
            {"vehicle_input": "2014 audi a4 premium plus 105000 miles 02893 ri awd good"}
        )
        self.assertEqual(query.year, 2014)
        self.assertEqual(query.make, "Audi")
        self.assertEqual(query.model, "A4")
        self.assertEqual(query.trim, "Premium Plus")
        self.assertEqual(query.mileage, 105000)
        self.assertEqual(query.zip_code, "02893")
        self.assertEqual(query.state, "RI")
        self.assertEqual(query.drivetrain, "AWD")
        self.assertEqual(query.condition, "Good")


if __name__ == "__main__":
    unittest.main()
