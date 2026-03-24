from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from comp_engine.config import EngineConfig
from comp_engine.http import HttpClient
from comp_engine.sources.craigslist import CraigslistAdapter
from comp_engine.storage import SQLiteRepository


class CraigslistAdapterTests(unittest.TestCase):
    def test_extracts_detail_fields_from_fixture(self) -> None:
        fixture = (
            Path(__file__).resolve().parent / "fixtures" / "craigslist_detail.html"
        ).read_text()
        with tempfile.TemporaryDirectory() as temp_dir:
            config = EngineConfig.from_env(Path(temp_dir))
            repository = SQLiteRepository(Path(temp_dir) / "comp.db")
            adapter = CraigslistAdapter(config, HttpClient(), repository)
            self.assertEqual(adapter._extract_detail_mileage(fixture), 105000)
            self.assertEqual(adapter._extract_attr(fixture, "condition"), "good")
            self.assertEqual(adapter._extract_attr(fixture, "title status"), "clean")
            self.assertEqual(adapter._extract_attr(fixture, "transmission"), "automatic")


if __name__ == "__main__":
    unittest.main()
