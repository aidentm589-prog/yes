from __future__ import annotations

import unittest

from comp_engine.models import NormalizedListing, VehicleQuery
from comp_engine.scoring import apply_adjustments, infer_mileage_adjustment_rate, score_listing


class ScoringTests(unittest.TestCase):
    def test_scores_exact_trim_higher(self) -> None:
        query = VehicleQuery(year=2014, make="Audi", model="A4", trim="Premium Plus", mileage=105000)
        exact = NormalizedListing(
            source="manual",
            source_listing_id="1",
            source_label="Manual",
            url="",
            fetched_at="2026-03-23T00:00:00+00:00",
            year=2014,
            make="Audi",
            model="A4",
            trim="Premium Plus",
            mileage=104000,
            price=8200,
        )
        fallback = NormalizedListing(
            source="manual",
            source_listing_id="2",
            source_label="Manual",
            url="",
            fetched_at="2026-03-23T00:00:00+00:00",
            year=2015,
            make="Audi",
            model="A4",
            trim="Base",
            mileage=120000,
            price=7900,
        )
        exact_score, _, _ = score_listing(query, exact)
        fallback_score, _, _ = score_listing(query, fallback)
        self.assertGreater(exact_score, fallback_score)

    def test_adjustments_respect_mileage_delta(self) -> None:
        query = VehicleQuery(year=2014, make="Audi", model="A4", mileage=80000)
        listing = NormalizedListing(
            source="manual",
            source_listing_id="1",
            source_label="Manual",
            url="",
            fetched_at="2026-03-23T00:00:00+00:00",
            year=2014,
            make="Audi",
            model="A4",
            trim="Premium Plus",
            mileage=100000,
            price=8000,
        )
        adjusted, _ = apply_adjustments(query, listing, infer_mileage_adjustment_rate([listing]))
        self.assertIsNotNone(adjusted)
        self.assertGreater(adjusted or 0, listing.price or 0)


if __name__ == "__main__":
    unittest.main()
