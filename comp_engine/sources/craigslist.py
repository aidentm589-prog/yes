from __future__ import annotations

import json
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from typing import Any

from .base import SourceAdapter
from ..models import NormalizedListing, VehicleQuery


DEFAULT_SITES = [
    "newyork",
    "philadelphia",
    "boston",
    "sfbay",
    "losangeles",
    "chicago",
    "atlanta",
    "miami",
    "dallas",
    "seattle",
    "washingtondc",
    "orangecounty",
    "sandiego",
    "phoenix",
    "houston",
    "austin",
    "sanantonio",
    "denver",
    "lasvegas",
    "portland",
    "sacramento",
    "detroit",
    "minneapolis",
    "charlotte",
    "nashville",
    "orlando",
    "tampa",
    "stlouis",
    "kansascity",
    "pittsburgh",
    "cleveland",
    "indianapolis",
]

SITE_LABELS = {
    "newyork": "New York",
    "philadelphia": "Philadelphia",
    "boston": "Boston",
    "sfbay": "San Francisco Bay",
    "losangeles": "Los Angeles",
    "chicago": "Chicago",
    "atlanta": "Atlanta",
    "miami": "Miami",
    "dallas": "Dallas",
    "seattle": "Seattle",
    "washingtondc": "Washington DC",
    "orangecounty": "Orange County",
    "sandiego": "San Diego",
    "phoenix": "Phoenix",
    "houston": "Houston",
    "austin": "Austin",
    "sanantonio": "San Antonio",
    "denver": "Denver",
    "lasvegas": "Las Vegas",
    "portland": "Portland",
    "sacramento": "Sacramento",
    "detroit": "Detroit",
    "minneapolis": "Minneapolis",
    "charlotte": "Charlotte",
    "nashville": "Nashville",
    "orlando": "Orlando",
    "tampa": "Tampa",
    "stlouis": "St. Louis",
    "kansascity": "Kansas City",
    "pittsburgh": "Pittsburgh",
    "cleveland": "Cleveland",
    "indianapolis": "Indianapolis",
    "providence": "Providence",
    "hartford": "Hartford",
    "worcester": "Worcester",
    "southcoast": "South Coast",
    "newhaven": "New Haven",
    "longisland": "Long Island",
    "newjersey": "New Jersey",
    "albany": "Albany",
    "buffalo": "Buffalo",
    "allentown": "Allentown",
    "jacksonville": "Jacksonville",
}

STATE_SITE_HINTS = {
    "RI": ["providence", "boston", "hartford", "newyork"],
    "MA": ["boston", "worcester", "southcoast", "hartford"],
    "CT": ["hartford", "newhaven", "providence", "newyork"],
    "NY": ["newyork", "longisland", "newjersey", "albany", "buffalo"],
    "NJ": ["newjersey", "newyork", "philadelphia"],
    "PA": ["philadelphia", "pittsburgh", "allentown", "newyork"],
    "CA": ["losangeles", "sfbay", "sandiego", "sacramento", "orangecounty"],
    "FL": ["miami", "orlando", "tampa", "jacksonville"],
    "TX": ["dallas", "houston", "austin", "sanantonio"],
}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class CraigslistAdapter(SourceAdapter):
    key = "craigslist"
    label = "Craigslist"
    official = False
    fragile = True
    fields = [
        "year", "make", "model", "trim", "bodyStyle", "drivetrain", "mileage",
        "price", "sellerType", "titleStatus", "condition", "location", "imageUrls", "url",
    ]
    notes = "Searches publicly available listing pages and enriches comps from listing-detail pages when URLs are available."

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.http_client.register_rate_limiter(self.key, 0.15)

    def is_enabled(self) -> bool:
        return self.config.enable_craigslist

    def search_listings(self, query: VehicleQuery) -> list[dict[str, Any]]:
        if not self.is_enabled():
            return []

        required_tokens = [
            str(query.year or "").lower(),
            query.make.lower(),
            query.model.lower(),
        ]
        search_terms = self._search_terms(query)
        sites = self._sites_for_query(query)
        seen: set[str] = set()
        results: list[dict[str, Any]] = []

        with ThreadPoolExecutor(max_workers=min(self.config.max_source_workers, len(sites) or 1)) as pool:
            futures = [
                pool.submit(self._fetch_site_results, site, term)
                for site in sites
                for term in search_terms
            ]
            for future in as_completed(futures):
                for raw in future.result():
                    normalized_title = str(raw.get("title", "")).lower()
                    if not all(token in normalized_title for token in required_tokens if token):
                        continue
                    dedupe_key = "|".join(
                        [
                            str(raw.get("source_region", "")),
                            str(raw.get("url", "")),
                            str(raw.get("title", "")),
                            str(raw.get("price", "")),
                        ]
                    )
                    if dedupe_key in seen:
                        continue
                    seen.add(dedupe_key)
                    results.append(raw)

        results.sort(key=lambda row: float(row.get("price") or 0.0))
        return results[: self.config.max_source_results]

    def normalize_listing(self, raw: dict[str, Any], query: VehicleQuery) -> NormalizedListing | None:
        title = str(raw.get("title") or "").strip()
        price = self._to_float(raw.get("price"))
        if not title or price is None:
            return None

        city = str(raw.get("city", "")).strip()
        state = str(raw.get("state", "")).strip().upper()
        listing = NormalizedListing(
            source=self.key,
            source_listing_id=str(raw.get("source_listing_id") or raw.get("url") or title),
            source_label=f"Craigslist {SITE_LABELS.get(str(raw.get('source_region', '')), str(raw.get('source_region', '')).title())}",
            url=str(raw.get("url") or "").strip(),
            fetched_at=_now_iso(),
            year=self._extract_year(title),
            make=query.make,
            model=query.model,
            trim=self._extract_trim(title, query),
            mileage=self._to_int(raw.get("mileage")) or self._extract_mileage(title),
            price=price,
            seller_type="dealer" if "/ctd/" in str(raw.get("url", "")) else "private",
            location={
                "city": city,
                "state": state,
                "zip": str(raw.get("postal_code") or "").strip(),
                "lat": self._to_float(raw.get("latitude")),
                "lng": self._to_float(raw.get("longitude")),
            },
            image_urls=self._image_urls(raw.get("images")),
            raw_payload=raw,
            spec_confidence=0.5,
        )
        return listing

    def enrich_listings(
        self,
        listings: list[NormalizedListing],
        query: VehicleQuery,
    ) -> list[NormalizedListing]:
        enriched: list[NormalizedListing] = []
        targets = [
            listing
            for listing in listings[: self.config.max_detail_enrichment]
            if listing.url and (
                listing.mileage is None
                or not listing.title_status
                or not listing.condition
                or not listing.body_style
                or not listing.drivetrain
                or not listing.transmission
            )
        ]
        details_by_url = {listing.url: self._fetch_listing_detail(listing.url) for listing in targets}
        for listing in listings:
            detail = details_by_url.get(listing.url) or {}
            if detail:
                if listing.mileage is None and detail.get("mileage") is not None:
                    listing.mileage = detail["mileage"]
                listing.title_status = listing.title_status or str(detail.get("title_status") or "")
                listing.condition = listing.condition or str(detail.get("condition") or "")
                listing.body_style = listing.body_style or str(detail.get("body_style") or "")
                listing.drivetrain = listing.drivetrain or str(detail.get("drivetrain") or "")
                listing.transmission = listing.transmission or str(detail.get("transmission") or "")
                listing.fuel_type = listing.fuel_type or str(detail.get("fuel_type") or "")
                listing.vin = listing.vin or str(detail.get("vin") or "")
                listing.location = {
                    **listing.location,
                    "city": listing.location.get("city") or detail.get("city"),
                    "state": listing.location.get("state") or detail.get("state"),
                    "lat": listing.location.get("lat") or detail.get("lat"),
                    "lng": listing.location.get("lng") or detail.get("lng"),
                }
                listing.image_urls = listing.image_urls or self._image_urls(detail.get("images"))
                listing.raw_payload["detail"] = detail
                listing.clean_title_likely = self._clean_title_likely(listing.title_status)
                listing.spec_confidence = max(listing.spec_confidence, 0.75)
                if detail.get("listing_age_days") is not None:
                    listing.listing_age_days = detail["listing_age_days"]
            enriched.append(listing)
        return enriched

    def _sites_for_query(self, query: VehicleQuery) -> list[str]:
        sites = list(STATE_SITE_HINTS.get(query.state.upper() if query.state else "", []))
        for site in DEFAULT_SITES:
            if site not in sites:
                sites.append(site)
        return sites

    def _search_terms(self, query: VehicleQuery) -> list[str]:
        base = " ".join(part for part in [str(query.year or ""), query.make, query.model] if part).strip()
        terms = [base]
        if query.trim:
            terms.insert(0, f"{base} {query.trim}".strip())
        if query.year:
            for year in (query.year - 1, query.year + 1):
                if 1990 <= year <= 2035:
                    terms.append(f"{year} {query.make} {query.model}")
        deduped: list[str] = []
        for term in terms:
            if term and term not in deduped:
                deduped.append(term)
        return deduped

    def _fetch_site_results(self, site: str, term: str) -> list[dict[str, Any]]:
        url = f"https://{site}.craigslist.org/search/cta"
        try:
            html = self.http_client.get_text(
                url,
                params={"query": term},
                source_key=self.key,
            )
        except Exception:  # noqa: BLE001
            return []
        ld_match = re.search(
            r'<script type="application/ld\+json" id="ld_searchpage_results" >\s*(\{.*?\})\s*</script>',
            html,
            re.S,
        )
        if not ld_match:
            return []
        try:
            payload = json.loads(ld_match.group(1))
        except json.JSONDecodeError:
            return []

        urls = self._extract_listing_urls(html, site)
        items = payload.get("itemListElement") or []
        results: list[dict[str, Any]] = []
        for index, item in enumerate(items):
            product = item.get("item", {})
            offer = product.get("offers", {})
            address = offer.get("availableAtOrFrom", {}).get("address", {})
            geo = offer.get("availableAtOrFrom", {}).get("geo", {})
            images = product.get("image") or []
            results.append(
                {
                    "source_listing_id": str(index),
                    "source_region": site,
                    "title": str(product.get("name") or "").strip(),
                    "price": self._to_float(offer.get("price")),
                    "url": urls[index] if index < len(urls) else "",
                    "images": images,
                    "city": str(address.get("addressLocality") or "").strip(),
                    "state": str(address.get("addressRegion") or "").strip(),
                    "postal_code": str(address.get("postalCode") or "").strip(),
                    "latitude": self._to_float(geo.get("latitude")),
                    "longitude": self._to_float(geo.get("longitude")),
                }
            )
        return results

    def _extract_listing_urls(self, html: str, site: str) -> list[str]:
        absolute_pattern = re.compile(
            rf"https://{re.escape(site)}\.craigslist\.org/[^\"]+/d/[^\"]+?\.html"
        )
        relative_pattern = re.compile(r'href="(/[^"]+/d/[^"]+?\.html)"')
        urls: list[str] = []
        seen: set[str] = set()
        for url in absolute_pattern.findall(html):
            if url in seen:
                continue
            seen.add(url)
            urls.append(url)
        for relative_url in relative_pattern.findall(html):
            url = f"https://{site}.craigslist.org{relative_url}"
            if url in seen:
                continue
            seen.add(url)
            urls.append(url)
        return urls

    def _fetch_listing_detail(self, url: str) -> dict[str, Any]:
        cache_key = f"craigslist_detail:{url}"
        cached = self.repository.get_cache_json(cache_key)
        if cached:
            return cached

        try:
            html = self.http_client.get_text(url, source_key=self.key)
        except Exception:  # noqa: BLE001
            return {}
        detail = {
            "mileage": self._extract_detail_mileage(html),
            "condition": self._extract_attr(html, "condition"),
            "fuel_type": self._extract_attr(html, "fuel"),
            "title_status": self._extract_attr(html, "title status"),
            "transmission": self._extract_attr(html, "transmission"),
            "body_style": self._extract_attr(html, "type"),
            "drivetrain": self._extract_attr(html, "drive"),
            "vin": self._extract_attr(html, "VIN"),
            "images": re.findall(r'<meta property="og:image" content="([^"]+)"', html),
            "city": self._extract_meta(html, "geo.placename"),
            "state": self._extract_state(html),
            "lat": self._to_float(self._extract_meta(html, "geo.position").split(";")[0]) if self._extract_meta(html, "geo.position") else None,  # noqa: E501
            "lng": self._to_float(self._extract_meta(html, "geo.position").split(";")[1]) if self._extract_meta(html, "geo.position") and ";" in self._extract_meta(html, "geo.position") else None,  # noqa: E501
            "listing_age_days": self._extract_listing_age_days(html),
        }
        self.repository.set_cache_json(cache_key, detail, ttl_seconds=self.config.cache_ttl_seconds)
        return detail

    def _extract_attr(self, html: str, label: str) -> str:
        pattern = re.compile(
            rf'<span class="labl">{re.escape(label)}:</span>\s*<span class="valu">(?:\s*<a [^>]+>)?([^<]+)',
            re.I,
        )
        match = pattern.search(html)
        return match.group(1).strip() if match else ""

    def _extract_meta(self, html: str, name: str) -> str:
        pattern = re.compile(rf'<meta name="{re.escape(name)}" content="([^"]+)"', re.I)
        match = pattern.search(html)
        return match.group(1).strip() if match else ""

    def _extract_state(self, html: str) -> str:
        region = self._extract_meta(html, "geo.region")
        if region.startswith("US-"):
            return region.split("-", 1)[1].upper()
        return ""

    def _extract_listing_age_days(self, html: str) -> int | None:
        match = re.search(r'<time class="date timeago"[^>]*datetime="([^"]+)"', html)
        if not match:
            return None
        try:
            posted_at = datetime.fromisoformat(match.group(1))
        except ValueError:
            return None
        now = datetime.now(posted_at.tzinfo or timezone.utc)
        return max(0, int((now - posted_at).days))

    def _extract_detail_mileage(self, html: str) -> int | None:
        match = re.search(
            r'<div class="attr auto_miles">\s*<span class="labl">odometer:</span>\s*<span class="valu">([^<]+)</span>',
            html,
            re.I,
        )
        return self._to_int(match.group(1)) if match else None

    def _extract_year(self, text: str) -> int | None:
        match = re.search(r"\b(19\d{2}|20\d{2})\b", text)
        return int(match.group(1)) if match else None

    def _extract_trim(self, title: str, query: VehicleQuery) -> str:
        lowered = title.lower()
        anchor = f"{query.make} {query.model}".lower()
        if anchor not in lowered:
            return ""
        return lowered.split(anchor, 1)[1].strip(" -").title()

    def _extract_mileage(self, text: str) -> int | None:
        match = re.search(r"\b(\d{1,3}(?:[,\s]\d{3})+)\s*(?:miles?|mi)\b", text, re.I)
        if not match:
            return None
        return int(match.group(1).replace(",", "").replace(" ", ""))

    def _image_urls(self, value: Any) -> list[str]:
        if isinstance(value, list):
            return [str(item) for item in value if item]
        return []

    def _clean_title_likely(self, title_status: str) -> bool | None:
        lowered = title_status.lower()
        if not lowered:
            return None
        if lowered == "clean":
            return True
        if lowered in {"salvage", "rebuilt", "flood"}:
            return False
        return None

    def _to_float(self, value: Any) -> float | None:
        try:
            if value in (None, ""):
                return None
            return float(str(value))
        except ValueError:
            return None

    def _to_int(self, value: Any) -> int | None:
        digits = "".join(ch for ch in str(value or "") if ch.isdigit())
        return int(digits) if digits else None
