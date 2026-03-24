from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from typing import Any

from .query_parser import parse_vehicle_query


PRICE_RE = re.compile(r"\$\s*([\d,]+(?:\.\d{2})?)")
YEAR_RE = re.compile(r"\b(19\d{2}|20\d{2})\b")
LOCATION_RE = re.compile(r"^[A-Za-z .'-]+,\s*[A-Z]{2}$")
MILEAGE_K_RE = re.compile(r"(\d+(?:\.\d+)?)\s*k\s*miles?\b", re.I)


@dataclass(slots=True)
class ParsedBulkVehicle:
    raw_block: str
    normalized_text: str
    year: int | None = None
    make: str = ""
    model: str = ""
    trim: str = ""
    mileage: int | None = None
    area: str = ""
    listed_price: float | None = None
    seller_type: str = ""
    status: str = "parsed"
    reason: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_payload(self) -> dict[str, Any]:
        return {
            "vehicle_input": self.normalized_text,
            "year": self.year,
            "make": self.make,
            "model": self.model,
            "trim": self.trim,
            "mileage": self.mileage,
            "asking_price": self.listed_price,
            "seller_type": self.seller_type,
        }


def parse_bulk_vehicle_text(raw_text: str) -> list[ParsedBulkVehicle]:
    blocks = _split_vehicle_blocks(raw_text)
    return [normalize_parsed_bulk_vehicle(block) for block in blocks]


def normalize_parsed_bulk_vehicle(block: str) -> ParsedBulkVehicle:
    raw_block = block.strip()
    normalized_text = _normalize_block_text(raw_block)
    listed_price = _extract_relevant_price(raw_block)
    area = _extract_area(raw_block)
    seller_type = _extract_seller_type(raw_block)
    query = parse_vehicle_query(
        {
            "vehicle_input": normalized_text,
            "asking_price": listed_price,
            "seller_type": seller_type,
        }
    )

    parsed = ParsedBulkVehicle(
        raw_block=raw_block,
        normalized_text=normalized_text,
        year=query.year,
        make=query.make,
        model=query.model,
        trim=query.trim,
        mileage=query.mileage,
        area=area,
        listed_price=query.asking_price or listed_price,
        seller_type=query.seller_type or seller_type,
    )

    if not (parsed.year and parsed.make and parsed.model):
        parsed.status = "skipped"
        parsed.reason = "missing year/make/model"
        return parsed

    if not parsed.mileage:
        parsed.status = "skipped"
        parsed.reason = "missing mileage"
        return parsed

    return parsed


def _split_vehicle_blocks(raw_text: str) -> list[str]:
    lines = [line.strip() for line in str(raw_text or "").splitlines()]
    blocks: list[list[str]] = []
    current: list[str] = []
    current_has_title = False

    for line in lines:
        if not line:
            if current:
                blocks.append(current)
                current = []
                current_has_title = False
            continue

        is_price = bool(PRICE_RE.search(line))
        is_title = bool(YEAR_RE.search(line))
        starts_new = current and current_has_title and (is_price or is_title)

        if starts_new:
            blocks.append(current)
            current = [line]
            current_has_title = is_title
            continue

        current.append(line)
        current_has_title = current_has_title or is_title

    if current:
        blocks.append(current)

    return ["\n".join(block).strip() for block in blocks if any(part.strip() for part in block)]


def _normalize_block_text(block: str) -> str:
    text = MILEAGE_K_RE.sub(lambda match: f"{int(float(match.group(1)) * 1000)} miles", block)
    return re.sub(r"\s+", " ", text).strip()


def _extract_relevant_price(block: str) -> float | None:
    matches = [float(price.replace(",", "")) for price in PRICE_RE.findall(block)]
    if not matches:
        return None
    if len(matches) == 1:
        return matches[0]

    lines = [line.strip() for line in block.splitlines() if line.strip()]
    title_index = next((index for index, line in enumerate(lines) if YEAR_RE.search(line)), None)
    if title_index is None:
        return matches[-1]

    best_distance = None
    best_price: float | None = None
    for index, line in enumerate(lines):
        line_matches = PRICE_RE.findall(line)
        for match in line_matches:
            price_value = float(match.replace(",", ""))
            distance = abs(title_index - index)
            if best_distance is None or distance < best_distance or (distance == best_distance and index >= title_index):
                best_distance = distance
                best_price = price_value
    return best_price if best_price is not None else matches[-1]


def _extract_area(block: str) -> str:
    for line in block.splitlines():
        candidate = line.strip()
        if LOCATION_RE.match(candidate):
            return candidate
    return ""


def _extract_seller_type(block: str) -> str:
    lowered = block.lower()
    if "dealership" in lowered or "dealer" in lowered:
        return "dealer"
    if "private seller" in lowered or "owner" in lowered:
        return "private"
    return ""
