from __future__ import annotations

from typing import Any

from .http import HttpClient


class NHTSAVinDecoder:
    BASE_URL = "https://vpic.nhtsa.dot.gov/api/vehicles/DecodeVinValuesExtended/"

    def __init__(self, http_client: HttpClient) -> None:
        self.http_client = http_client
        self.http_client.register_rate_limiter("nhtsa_vin", 0.2)

    def is_valid_vin(self, vin: str) -> bool:
        normalized = str(vin or "").strip().upper()
        if len(normalized) != 17:
            return False
        if "{" in normalized or "}" in normalized:
            return False
        return all(char in "0123456789ABCDEFGHJKLMNPRSTUVWXYZ" for char in normalized)

    def decode(self, vin: str, model_year: int | None = None) -> dict[str, Any]:
        normalized_vin = str(vin or "").strip().upper()
        if not self.is_valid_vin(normalized_vin):
            return {}
        params = {"format": "json"}
        if model_year:
            params["modelyear"] = model_year
        payload = self.http_client.get_json(
            f"{self.BASE_URL}{normalized_vin}",
            params=params,
            source_key="nhtsa_vin",
        )
        results = payload.get("Results") or payload.get("results") or []
        if not results:
            return {}
        row = results[0]
        error_code = str(row.get("ErrorCode", "")).strip()
        if error_code not in {"", "0"}:
            return {}
        trim = " ".join(
            part
            for part in [
                str(row.get("Series", "")).strip(),
                str(row.get("Trim", "")).strip(),
            ]
            if part
        ).strip()
        transmission = " ".join(
            part
            for part in [
                str(row.get("TransmissionStyle", "")).strip(),
                str(row.get("TransmissionSpeeds", "")).strip() and f"{row.get('TransmissionSpeeds')}spd",
            ]
            if part
        ).strip()
        engine_bits = [
            str(row.get("EngineModel", "")).strip(),
            str(row.get("DisplacementL", "")).strip() and f"{row.get('DisplacementL')}L",
            str(row.get("EngineCylinders", "")).strip() and f"{row.get('EngineCylinders')}cyl",
        ]
        if str(row.get("Turbo", "")).strip().lower() == "yes":
            engine_bits.append("Turbo")
        elif str(row.get("Supercharger", "")).strip().lower() == "yes":
            engine_bits.append("Supercharged")
        return {
            "vin": str(row.get("VIN", "")).strip(),
            "year": self._to_int(row.get("ModelYear")),
            "make": str(row.get("Make", "")).strip(),
            "model": str(row.get("Model", "")).strip(),
            "trim": trim,
            "series": str(row.get("Series", "")).strip(),
            "body_style": str(row.get("BodyClass", "")).strip(),
            "drivetrain": str(row.get("DriveType", "")).strip(),
            "engine": " ".join(part for part in engine_bits if part).strip(),
            "transmission": transmission,
            "fuel_type": str(row.get("FuelTypePrimary", "")).strip(),
            "displacement_l": str(row.get("DisplacementL", "")).strip(),
            "engine_cylinders": str(row.get("EngineCylinders", "")).strip(),
            "engine_hp": str(row.get("EngineHP", "")).strip(),
            "transmission_style": str(row.get("TransmissionStyle", "")).strip(),
            "transmission_speeds": str(row.get("TransmissionSpeeds", "")).strip(),
            "aspiration": "Turbo" if str(row.get("Turbo", "")).strip().lower() == "yes" else ("Supercharged" if str(row.get("Supercharger", "")).strip().lower() == "yes" else ""),
            "error_code": error_code,
        }

    def _to_int(self, value: Any) -> int | None:
        try:
            if value in (None, ""):
                return None
            return int(str(value))
        except ValueError:
            return None
