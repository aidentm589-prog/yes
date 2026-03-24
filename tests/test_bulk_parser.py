from __future__ import annotations

import unittest

from comp_engine.bulk_parser import parse_bulk_vehicle_text


class BulkParserTests(unittest.TestCase):
    def test_bulk_parser_extracts_multiple_vehicle_blocks(self) -> None:
        raw = """
$4,995
2013 MINI hardtop 2 door Cooper Hatchback 2D
Groveland, MA
4.9K miles · Dealership

$3,000
2012 MINI countryman Cooper S ALL4 Hatchback 4D
Dorchester Center, MA
129K miles
        """.strip()

        parsed = parse_bulk_vehicle_text(raw)

        self.assertEqual(len(parsed), 2)
        self.assertEqual(parsed[0].year, 2013)
        self.assertEqual(parsed[0].make, "Mini")
        self.assertEqual(parsed[0].model, "Hardtop")
        self.assertEqual(parsed[0].mileage, 4900)
        self.assertEqual(parsed[0].listed_price, 4995.0)
        self.assertEqual(parsed[0].area, "Groveland, MA")
        self.assertEqual(parsed[1].mileage, 129000)

    def test_bulk_parser_marks_missing_mileage_as_skipped(self) -> None:
        raw = """
$4,500
2009 Honda civic DX Sedan 4D
Boston, MA
        """.strip()

        parsed = parse_bulk_vehicle_text(raw)

        self.assertEqual(len(parsed), 1)
        self.assertEqual(parsed[0].status, "skipped")
        self.assertEqual(parsed[0].reason, "missing mileage")


if __name__ == "__main__":
    unittest.main()
