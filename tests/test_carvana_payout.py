from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from carvana_payout import CarvanaPayoutService
from comp_engine.storage import SQLiteRepository


class CarvanaPayoutTests(unittest.TestCase):
    def create_service(self) -> CarvanaPayoutService:
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)
        repository = SQLiteRepository(Path(temp_dir.name) / "carvana.db")
        service = CarvanaPayoutService(repository)
        return service

    def test_create_job_requires_vin_or_plate(self) -> None:
        service = self.create_service()
        with self.assertRaises(ValueError):
            service.create_carvana_payout_job(
                1,
                {"mileage": "120000", "condition": "Good"},
            )

    def test_create_and_list_job(self) -> None:
        service = self.create_service()
        job = service.create_carvana_payout_job(
            1,
            {
                "vin": "WAUBFAFL1EN000001",
                "mileage": "120000",
                "condition": "Good",
                "rebuilt_title": "1",
            },
        )

        self.assertEqual(job["status"], "queued")
        self.assertEqual(job["mileage"], 120000)
        self.assertTrue(job["rebuilt_title"])
        jobs = service.list_carvana_payout_jobs(user_id=1)
        self.assertEqual(len(jobs), 1)
        self.assertEqual(jobs[0]["vehicle_identifier"], "WAUBFAFL1EN000001")


if __name__ == "__main__":
    unittest.main()
