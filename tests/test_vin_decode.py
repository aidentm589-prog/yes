from __future__ import annotations

import unittest

from comp_engine.http import HttpClient
from comp_engine.vin_decode import NHTSAVinDecoder


class VinDecodeTests(unittest.TestCase):
    def test_vin_validator_accepts_real_shape(self) -> None:
        decoder = NHTSAVinDecoder(HttpClient())
        self.assertTrue(decoder.is_valid_vin("1HGCM82633A004352"))

    def test_vin_validator_rejects_invalid_or_placeholder_vins(self) -> None:
        decoder = NHTSAVinDecoder(HttpClient())
        self.assertFalse(decoder.is_valid_vin(""))
        self.assertFalse(decoder.is_valid_vin("123"))
        self.assertFalse(decoder.is_valid_vin("{VIN}"))
        self.assertFalse(decoder.is_valid_vin("1HGCM82633A00I352"))


if __name__ == "__main__":
    unittest.main()
