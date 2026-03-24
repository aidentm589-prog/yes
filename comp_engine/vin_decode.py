from __future__ import annotations

from typing import Any

from .http import HttpClient


class NHTSAVinDecoder:
    BASE_URL = "https://vpic.nhtsa.dot.gov/api/vehicles/DecodeVinValuesExtended/"

    def __init__(self, http_client: HttpClient) -> None:
        self.http_client = http_client
        self.http_client.register_rate_limiter("nhtsa_vin", 0.2)

    def decode(self, vin: str, model_year: int | None = None) -> dict[str, Any]:
        if len(vin.strip()) != 17:
            return {}
        params = {"format": "json"}
        if model_year:
            params["modelyear"] = model_year
        payload = self.http_client.get_json(
            f"{self.BASE_URL}{vin}",
            params=params,
            source_key="nhtsa_vin",
        )
        results = payload.get("Results") or payload.get("results") or []
        if not results:
            return {}
        row = results[0]
        trim = " ".join(
            part
            for part in [
                str(row.get("Series", "")).strip(),
                str(row.get("Trim", "")).strip(),
            ]
            if part
        ).strip()
        return {
            "vin": str(row.get("VIN", "")).strip(),
            "year": self._to_int(row.get("ModelYear")),
            "make": str(row.get("Make", "")).strip(),
            "model": str(row.get("Model", "")).strip(),
            "trim": trim,
            "body_style": str(row.get("BodyClass", "")).strip(),
            "drivetrain": str(row.get("DriveType", "")).strip(),
            "engine": " ".join(
                part for part in [
                    str(row.get("EngineModel", "")).strip(),
                    str(row.get("DisplacementL", "")).strip() and f"{row.get('DisplacementL')}L",
                ] if part
            ).strip(),
            "transmission": str(row.get("TransmissionStyle", "")).strip(),
            "fuel_type": str(row.get("FuelTypePrimary", "")).strip(),
            "error_code": str(row.get("ErrorCode", "")).strip(),
        }

    def _to_int(self, value: Any) -> int | None:
        try:
            if value in (None, ""):
                return None
            return int(str(value))
        except ValueError:
            return None
