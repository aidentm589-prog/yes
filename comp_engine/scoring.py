from __future__ import annotations

import math
import re
from statistics import median
from typing import Any

from .models import NormalizedListing, VehicleQuery


def normalized_token_set(value: str) -> set[str]:
    return {
        token
        for token in re.split(r"[\s/,_()-]+", value.lower())
        if token and token not in {"the", "and", "with"}
    }


def trim_similarity(left: str, right: str) -> float:
    left_tokens = normalized_token_set(left)
    right_tokens = normalized_token_set(right)
    if not left_tokens or not right_tokens:
        return 0.0
    union = left_tokens | right_tokens
    if not union:
        return 0.0
    return len(left_tokens & right_tokens) / len(union)


def critical_trim_tokens(value: str) -> set[str]:
    tokens = normalized_token_set(value)
    critical: set[str] = set()
    for token in tokens:
        if re.search(r"\d", token):
            critical.add(token)
            continue
        if token in {"amg", "rs", "sline", "quattro", "xdrive", "hellcat", "stype", "type-s"}:
            critical.add(token)
    return critical


def score_listing(query: VehicleQuery, listing: NormalizedListing) -> tuple[float, str, list[str]]:
    reasons: list[str] = []
    score = 0.0

    if listing.make.lower() != query.make.lower() or listing.model.lower() != query.model.lower():
        return -999.0, "Excluded", ["make/model mismatch"]

    score += 45.0
    reasons.append("exact make/model")

    if listing.year and query.year:
        year_gap = abs(listing.year - query.year)
        score += {0: 20.0, 1: 10.0, 2: 4.0}.get(year_gap, -8.0)
        reasons.append(f"year gap {year_gap}")

    if query.trim and listing.trim:
        query_critical = critical_trim_tokens(query.trim)
        listing_critical = critical_trim_tokens(listing.trim)
        if query_critical and listing_critical and query_critical.isdisjoint(listing_critical):
            return -999.0, "Excluded", ["critical trim mismatch"]
        similarity = trim_similarity(query.trim, listing.trim)
        score += similarity * 18.0
        if similarity >= 0.65:
            reasons.append("strong trim match")
        elif similarity >= 0.35:
            reasons.append("partial trim match")
        elif query_critical:
            score -= 18.0
            reasons.append("weak trim match")
    elif query.trim:
        if critical_trim_tokens(query.trim):
            score -= 14.0
            reasons.append("missing trim detail on listing")

    if query.drivetrain and listing.drivetrain:
        if query.drivetrain.lower() == listing.drivetrain.lower():
            score += 8.0
            reasons.append("drivetrain match")
        else:
            score -= 5.0

    if query.body_style and listing.body_style:
        if query.body_style.lower() == listing.body_style.lower():
            score += 5.0
            reasons.append("body style match")

    if query.mileage and listing.mileage:
        mileage_gap = abs(listing.mileage - query.mileage)
        score += max(-4.0, 18.0 - (mileage_gap / 5000))
        reasons.append(f"mileage gap {mileage_gap:,}")

    if query.state and listing.location.get("state"):
        if query.state.upper() == str(listing.location.get("state", "")).upper():
            score += 4.0
            reasons.append("same state")

    if query.title_status and listing.title_status:
        if query.title_status.lower() == listing.title_status.lower():
            score += 4.0
        else:
            score -= 7.0

    if listing.title_status.lower() in {"salvage", "rebuilt", "flood"}:
        score -= 14.0
        reasons.append("title penalty")

    if query.seller_type and listing.seller_type:
        if query.seller_type.lower() == listing.seller_type.lower():
            score += 2.0

    if listing.listing_age_days is not None:
        if listing.listing_age_days <= 14:
            score += 4.0
        elif listing.listing_age_days <= 45:
            score += 2.0
        elif listing.listing_age_days >= 90:
            score -= 4.0

    score += listing.spec_confidence * 8.0

    tier = "Tier 3"
    if score >= 78:
        tier = "Tier 1"
    elif score >= 58:
        tier = "Tier 2"
    return score, tier, reasons


def infer_mileage_adjustment_rate(listings: list[NormalizedListing]) -> float:
    mileage_pairs = [
        (listing.mileage, listing.price)
        for listing in listings
        if listing.mileage is not None and listing.price is not None
    ]
    if len(mileage_pairs) < 4:
        return 0.08
    mileages = sorted(pair[0] for pair in mileage_pairs)
    prices = sorted(pair[1] for pair in mileage_pairs)
    mileage_spread = max(1, percentile(mileages, 0.75) - percentile(mileages, 0.25))
    price_spread = max(1.0, percentile(prices, 0.75) - percentile(prices, 0.25))
    return max(0.02, min(0.35, price_spread / mileage_spread))


def apply_adjustments(
    query: VehicleQuery,
    listing: NormalizedListing,
    mileage_rate: float,
) -> tuple[float | None, list[str]]:
    if listing.price is None:
        return None, []

    adjusted = listing.price
    notes: list[str] = []

    if query.mileage and listing.mileage is not None:
        mileage_delta = listing.mileage - query.mileage
        cap = listing.price * 0.18
        adjustment = max(-cap, min(cap, mileage_delta * mileage_rate))
        adjusted += adjustment
        if adjustment:
            direction = "up" if adjustment > 0 else "down"
            notes.append(f"mileage adjusted {direction} {money(abs(adjustment))}")

    if query.trim and listing.trim:
        query_critical = critical_trim_tokens(query.trim)
        listing_critical = critical_trim_tokens(listing.trim)
        if query_critical and listing_critical and query_critical.isdisjoint(listing_critical):
            adjusted *= 0.86
            notes.append("critical trim mismatch discount")
        similarity = trim_similarity(query.trim, listing.trim)
        if 0 < similarity < 0.45:
            adjusted *= 0.97
            notes.append("trim mismatch discount")

    if query.drivetrain and listing.drivetrain and query.drivetrain.lower() != listing.drivetrain.lower():
        adjusted *= 0.96
        notes.append("drivetrain mismatch discount")

    if listing.title_status.lower() == "salvage":
        adjusted *= 0.68
        notes.append("salvage title penalty")
    elif listing.title_status.lower() == "rebuilt":
        adjusted *= 0.78
        notes.append("rebuilt title penalty")
    elif listing.title_status.lower() == "flood":
        adjusted *= 0.65
        notes.append("flood title penalty")

    condition = listing.condition.lower()
    if condition in {"fair", "rough", "poor", "awful"}:
        adjusted *= 0.92
        notes.append("condition penalty")
    elif condition in {"excellent", "like new"}:
        adjusted *= 1.02
        notes.append("condition premium")

    if listing.seller_type.lower() == "dealer":
        adjusted *= 0.95
        notes.append("dealer asking-price normalization")

    if listing.listing_age_days is not None:
        if listing.listing_age_days > 60:
            adjusted *= 0.95
            notes.append("stale listing discount")
        elif listing.listing_age_days > 30:
            adjusted *= 0.98
            notes.append("aged listing discount")

    if query.state and listing.location.get("state") and query.state.upper() != str(listing.location["state"]).upper():
        adjusted *= 0.99
        notes.append("cross-market normalization")

    return max(500.0, adjusted), notes


def percentile(values: list[float], pct: float) -> float:
    if not values:
        return 0.0
    if len(values) == 1:
        return values[0]
    index = (len(values) - 1) * pct
    low = math.floor(index)
    high = math.ceil(index)
    if low == high:
        return values[low]
    weight = index - low
    return values[low] * (1 - weight) + values[high] * weight


def weighted_median(values: list[float], weights: list[float]) -> float:
    if not values:
        return 0.0
    pairs = sorted(zip(values, weights), key=lambda pair: pair[0])
    total_weight = sum(weight for _, weight in pairs)
    cumulative = 0.0
    for value, weight in pairs:
        cumulative += weight
        if cumulative >= total_weight / 2:
            return value
    return pairs[-1][0]


def compute_confidence(
    listings: list[NormalizedListing],
    source_count: int,
) -> int:
    if not listings:
        return 5
    comp_count = len(listings)
    tier_one_count = sum(1 for listing in listings if listing.match_tier == "Tier 1")
    mileage_known_ratio = sum(1 for listing in listings if listing.mileage is not None) / comp_count
    prices = [listing.adjusted_price or listing.price or 0.0 for listing in listings]
    price_dispersion = 0.0
    if len(prices) >= 3 and median(prices) > 0:
        price_dispersion = (max(prices) - min(prices)) / median(prices)

    score = 25
    score += min(30, comp_count * 1.6)
    score += min(15, source_count * 8)
    score += min(15, tier_one_count * 4)
    score += int(mileage_known_ratio * 10)
    score -= min(18, int(price_dispersion * 12))
    return max(5, min(95, score))


def money(value: float) -> str:
    return f"${int(round(value)):,}"
