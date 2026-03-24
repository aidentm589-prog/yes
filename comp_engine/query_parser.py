from __future__ import annotations

import re
from typing import Any

from .models import VehicleQuery


US_STATES = {
    "AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DC", "DE", "FL", "GA", "HI", "IA",
    "ID", "IL", "IN", "KS", "KY", "LA", "MA", "MD", "ME", "MI", "MN", "MO", "MS",
    "MT", "NC", "ND", "NE", "NH", "NJ", "NM", "NV", "NY", "OH", "OK", "OR", "PA",
    "RI", "SC", "SD", "TN", "TX", "UT", "VA", "VT", "WA", "WI", "WV", "WY",
}

COMMON_COLORS = {
    "black", "white", "silver", "gray", "grey", "red", "blue", "green", "brown",
    "beige", "gold", "yellow", "orange", "purple",
}

MODEL_JOIN_WORDS = {"series", "class"}
TOKEN_ALIASES = {
    "slime": "sline",
    "s-line": "sline",
}
DRIVETRAIN_TOKENS = {
    "awd": "AWD",
    "fwd": "FWD",
    "rwd": "RWD",
    "4wd": "4WD",
    "4x4": "4x4",
    "2wd": "2WD",
    "quattro": "quattro",
    "xdrive": "xDrive",
}
BODY_STYLE_TOKENS = {
    "sedan": "Sedan",
    "coupe": "Coupe",
    "hatchback": "Hatchback",
    "wagon": "Wagon",
    "suv": "SUV",
    "truck": "Truck",
    "pickup": "Pickup",
    "convertible": "Convertible",
    "van": "Van",
}
CONDITION_TOKENS = {
    "awful": "Awful",
    "rough": "Awful",
    "fair": "Fair",
    "good": "Good",
    "great": "Great",
    "amazing": "Amazing",
    "excellent": "Amazing",
    "clean": "Good",
}
TITLE_STATUS_TOKENS = {
    "clean": "clean",
    "salvage": "salvage",
    "rebuilt": "rebuilt",
    "flood": "flood",
    "lien": "lien",
}
SELLER_TYPE_TOKENS = {
    "dealer": "dealer",
    "private": "private",
    "owner": "private",
}
TRANSMISSION_TOKENS = {
    "automatic": "Automatic",
    "manual": "Manual",
    "cvt": "CVT",
}
NOISE_TOKENS = {
    ".",
    "about",
    "vehicle",
    "driven",
    "exterior",
    "interior",
    "color",
    "colors",
    "seller",
    "description",
    "details",
    "listing",
    "listed",
    "var",
    "marketplace",
    "facebook",
    "trade",
    "trades",
}

MAKE_TOKEN_OVERRIDES = {
    "bmw": "BMW",
    "gmc": "GMC",
}


def _clean_number(value: Any) -> int | None:
    digits = "".join(ch for ch in str(value or "") if ch.isdigit())
    return int(digits) if digits else None


def _parse_mileage_value(value: Any) -> int | None:
    text = str(value or "").strip()
    if not text:
        return None
    normalized = text.replace(",", "").strip().lower()
    match = re.search(r"(\d+(?:\.\d+)?)\s*k\b", normalized)
    if match:
        return int(float(match.group(1)) * 1000)
    digits = re.sub(r"[^\d]", "", normalized)
    return int(digits) if digits else None


def _clean_price(value: Any) -> float | None:
    cleaned = re.sub(r"[^\d.]", "", str(value or ""))
    if not cleaned:
        return None
    try:
        return float(cleaned)
    except ValueError:
        return None


def parse_vehicle_query(payload: dict[str, Any]) -> VehicleQuery:
    text = str(payload.get("vehicle_input", "")).strip()
    query = _parse_freeform_vehicle_input(text)
    query.raw_input = text

    overrides = {
        "year": _clean_number(payload.get("year")),
        "make": str(payload.get("make", "")).strip(),
        "model": str(payload.get("model", "")).strip(),
        "trim": str(payload.get("trim", "")).strip(),
        "mileage": _parse_mileage_value(payload.get("mileage")),
        "asking_price": _clean_price(payload.get("asking_price") or payload.get("listing_price")),
        "drivetrain": str(payload.get("drivetrain", "")).strip(),
        "body_style": str(payload.get("body_style", "")).strip(),
        "engine": str(payload.get("engine", "")).strip(),
        "transmission": str(payload.get("transmission", "")).strip(),
        "fuel_type": str(payload.get("fuel_type", "")).strip(),
        "exterior_color": str(payload.get("color", "")).strip(),
        "title_status": str(payload.get("title_status", "")).strip(),
        "condition": str(payload.get("condition", "")).strip(),
        "zip_code": str(payload.get("zip_code", "")).strip(),
        "state": str(payload.get("state", "")).strip(),
        "seller_type": str(payload.get("seller_type", "")).strip(),
        "vin": str(payload.get("vin", "")).strip().upper(),
    }
    for key, value in overrides.items():
        if value not in ("", None):
            setattr(query, key, value)

    manual_csv = str(payload.get("manual_csv", "") or payload.get("manual_import_csv", "")).strip()
    if manual_csv:
        query.manual_csv = manual_csv

    rebuilt_title = str(payload.get("rebuilt_title", "")).strip().lower()
    if rebuilt_title in {"1", "true", "yes", "on"}:
        query.title_status = "rebuilt"

    for field_name in ("manual_urls", "manual_listings", "custom_listings"):
        value = payload.get(field_name)
        if isinstance(value, list):
            setattr(query, field_name, value)

    return query


def _parse_freeform_vehicle_input(text: str) -> VehicleQuery:
    query = VehicleQuery()
    working = f" {text.strip()} "
    working = re.sub(r"\b(\d{2,3})\s+(\d{3})\b", r"\1,\2", working)

    year_match = re.search(r"\b(19\d{2}|20\d{2})\b", working)
    if year_match:
        query.year = int(year_match.group(1))
        working = working.replace(year_match.group(0), " ", 1)

    mileage_match = re.search(r"\b([\d,]+(?:\.\d+)?)\s*(k)?\s*(miles?|mi)\b", working, re.I)
    if mileage_match:
        base_value = float(mileage_match.group(1).replace(",", ""))
        query.mileage = int(base_value * 1000) if mileage_match.group(2) else int(base_value)
        working = working.replace(mileage_match.group(0), " ", 1)

    if query.mileage is None:
        standalone_mileage_match = re.search(r"\b(\d{2,3},\d{3}|\d{5,6})\b(?=[^\d]*$)", working)
        if standalone_mileage_match:
            query.mileage = int(standalone_mileage_match.group(1).replace(",", ""))
            working = working.replace(standalone_mileage_match.group(0), " ", 1)

    price_match = re.search(
        r"\b(?:price|asking price|listed at|listing price)\b[^\d$]{0,12}\$?\s*([\d,]{3,8})\b",
        working,
        re.I,
    )
    if not price_match:
        price_match = re.search(r"\$\s*([\d,]{3,8})\b", working)
    if price_match:
        query.asking_price = float(price_match.group(1).replace(",", ""))
        working = working.replace(price_match.group(0), " ", 1)

    for zip_match in re.finditer(r"\b(\d{5})\b", working):
        digits = zip_match.group(1)
        if query.mileage and digits == str(query.mileage):
            continue
        query.zip_code = digits
        working = working.replace(zip_match.group(0), " ", 1)
        break

    vin_match = re.search(r"\b([A-HJ-NPR-Z0-9]{17})\b", working, re.I)
    if vin_match:
        query.vin = vin_match.group(1).upper()
        working = working.replace(vin_match.group(0), " ", 1)

    tokens = [token for token in re.split(r"[\s,]+", working.lower()) if token]
    remaining: list[str] = []
    for token in tokens:
        token = TOKEN_ALIASES.get(token, token)
        upper = token.upper()
        if upper in US_STATES and not query.state:
            query.state = upper
            continue
        if token in COMMON_COLORS and not query.exterior_color:
            query.exterior_color = token.title()
            continue
        if token in DRIVETRAIN_TOKENS and not query.drivetrain:
            query.drivetrain = DRIVETRAIN_TOKENS[token]
            continue
        if token in BODY_STYLE_TOKENS and not query.body_style:
            query.body_style = BODY_STYLE_TOKENS[token]
            continue
        if token in CONDITION_TOKENS and not query.condition:
            query.condition = CONDITION_TOKENS[token]
            continue
        if token in TITLE_STATUS_TOKENS and not query.title_status:
            query.title_status = TITLE_STATUS_TOKENS[token]
            continue
        if token in {"title", "tittle"}:
            continue
        if token in NOISE_TOKENS:
            continue
        if token in SELLER_TYPE_TOKENS and not query.seller_type:
            query.seller_type = SELLER_TYPE_TOKENS[token]
            continue
        if token in TRANSMISSION_TOKENS and not query.transmission:
            query.transmission = TRANSMISSION_TOKENS[token]
            continue
        remaining.append(token)

    if remaining:
        query.make = _format_make_token(remaining[0])
    if len(remaining) > 1:
        if len(remaining) > 2 and remaining[2] in MODEL_JOIN_WORDS:
            query.model = " ".join(
                token.upper() if any(char.isdigit() for char in token) else token.title()
                for token in remaining[1:3]
            )
            if len(remaining) > 3:
                query.trim = " ".join(word.title() for word in remaining[3:])
        else:
            model_token = remaining[1]
            query.model = model_token.upper() if any(char.isdigit() for char in model_token) else model_token.title()
            if len(remaining) > 2:
                query.trim = " ".join(word.title() for word in remaining[2:])

    _refine_make_model_trim(query, remaining)

    return query


def _refine_make_model_trim(query: VehicleQuery, remaining: list[str]) -> None:
    if query.make.lower() == "bmw" and len(remaining) >= 2:
        shorthand = remaining[1]
        if re.fullmatch(r"m?\d{3}(?:i|xi|d)?", shorthand):
            series_digit = next((char for char in shorthand if char.isdigit()), "")
            if series_digit:
                query.model = f"{series_digit} Series"
                query.trim = _format_trim_token(shorthand)

    if query.trim:
        query.trim = " ".join(_format_trim_token(token) for token in query.trim.split())
        query.trim = _strip_mileage_suffix(query.trim, query.mileage)


def _format_make_token(token: str) -> str:
    lower = token.lower()
    if lower in MAKE_TOKEN_OVERRIDES:
        return MAKE_TOKEN_OVERRIDES[lower]
    return token.title()


def _format_trim_token(token: str) -> str:
    lower = token.lower()
    if lower == "sline":
        return "S-Line"
    if re.fullmatch(r"m?\d{3}(?:i|xi|d)?", lower):
        if lower.startswith("m"):
            return f"M{lower[1:-1]}{lower[-1]}"
        return f"{lower[:-1]}{lower[-1]}"
    return token.title()


def _strip_mileage_suffix(trim: str, mileage: int | None) -> str:
    if not trim or not mileage:
        return trim.strip()

    mileage_digits = str(mileage)
    tokens = trim.split()
    while tokens:
        removed = False
        for size in (3, 2, 1):
            if len(tokens) < size:
                continue
            suffix = tokens[-size:]
            suffix_digits = "".join(
                "".join(character for character in token if character.isdigit())
                for token in suffix
            )
            if suffix_digits == mileage_digits:
                tokens = tokens[:-size]
                removed = True
                break
        if not removed:
            break
    return " ".join(tokens).strip()
