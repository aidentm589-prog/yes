from __future__ import annotations

import html
import json
import os
import re
from typing import Any

from .http import HttpClient


URL_PATTERN = re.compile(r"https?://[^\s]+", re.I)
META_PATTERN = re.compile(
    r"""<meta[^>]+(?:property|name)=["'](?P<name>og:title|og:description|twitter:title|twitter:description|description)["'][^>]+content=["'](?P<content>.*?)["']""",
    re.I | re.S,
)
JSON_LD_PATTERN = re.compile(
    r"""<script[^>]+type=["']application/ld\+json["'][^>]*>(?P<payload>.*?)</script>""",
    re.I | re.S,
)
TAG_PATTERN = re.compile(r"<[^>]+>")
WHITESPACE_PATTERN = re.compile(r"\s+")


class ListingLinkExtractor:
    def __init__(self, http_client: HttpClient) -> None:
        self.http_client = http_client
        self.openai_api_key = os.getenv("OPENAI_API_KEY", "").strip()
        self.openai_model = os.getenv("OPENAI_LINK_SUMMARY_MODEL", "gpt-4.1-mini").strip()
        self.http_client.register_rate_limiter("link_extract_llm", 0.3)

    def augment_vehicle_input(self, text: str) -> tuple[str, list[dict[str, Any]]]:
        urls = URL_PATTERN.findall(text or "")
        if not urls:
            return text, []

        clean_text = URL_PATTERN.sub(" ", text).strip()
        extracted_payloads: list[dict[str, Any]] = []
        extracted_texts: list[str] = []
        for url in urls[:3]:
            extracted = self._extract_from_url(url)
            if not extracted:
                continue
            extracted_payloads.append(extracted)
            structured_excerpt = self._structured_data_excerpt(extracted.get("structured_data") or [])
            snippet = " ".join(
                part for part in [
                    extracted.get("title", ""),
                    extracted.get("description", ""),
                    extracted.get("body_excerpt", ""),
                    structured_excerpt,
                    extracted.get("llm_summary", ""),
                ]
                if part
            ).strip()
            if snippet:
                extracted_texts.append(snippet)

        augmented = " ".join(part for part in [clean_text, *extracted_texts] if part).strip()
        return augmented or clean_text or text, extracted_payloads

    def _extract_from_url(self, url: str) -> dict[str, Any] | None:
        try:
            html_text = self.http_client.get_text(url, source_key="link_extract")
        except Exception:
            return None

        title = self._extract_meta_value(html_text, {"og:title", "twitter:title"}) or self._extract_title_tag(html_text)
        raw_description = self._extract_meta_value(
            html_text,
            {"og:description", "twitter:description", "description"},
        )
        description = self._filter_description(raw_description, title)
        body_excerpt = self._extract_body_excerpt(html_text) if not raw_description else ""
        json_ld = self._extract_json_ld(html_text)
        page_text = self._clean(TAG_PATTERN.sub(" ", html_text))
        asking_price = self._extract_listing_price(title, description, body_excerpt, json_ld, page_text)
        llm_summary = self._summarize_vehicle_text(title, description, body_excerpt, json_ld, page_text)
        return {
            "url": url,
            "title": title or "",
            "description": description or "",
            "body_excerpt": body_excerpt or "",
            "structured_data": json_ld,
            "asking_price": asking_price,
            "llm_summary": llm_summary or "",
        }

    def _extract_meta_value(self, html_text: str, names: set[str]) -> str:
        for match in META_PATTERN.finditer(html_text):
            name = match.group("name").lower()
            if name not in names:
                continue
            content = self._clean(match.group("content"))
            if content:
                return content
        return ""

    def _extract_title_tag(self, html_text: str) -> str:
        match = re.search(r"<title[^>]*>(.*?)</title>", html_text, re.I | re.S)
        return self._clean(match.group(1)) if match else ""

    def _extract_body_excerpt(self, html_text: str) -> str:
        stripped = TAG_PATTERN.sub(" ", html_text)
        stripped = self._clean(stripped)
        interesting_lines = [
            line.strip()
            for line in stripped.split("  ")
            if any(keyword in line.lower() for keyword in [
                "miles",
                "transmission",
                "exterior",
                "interior",
                "rebuilt",
                "salvage",
                "clean title",
                "vin",
                "vehicle",
                "sedan",
                "coupe",
            ])
        ]
        excerpt = " ".join(interesting_lines[:12]).strip()
        return excerpt[:900]

    def _extract_json_ld(self, html_text: str) -> list[dict[str, Any]]:
        payloads: list[dict[str, Any]] = []
        for match in JSON_LD_PATTERN.finditer(html_text):
            raw_payload = html.unescape(match.group("payload")).strip()
            if not raw_payload:
                continue
            try:
                parsed = json.loads(raw_payload)
            except json.JSONDecodeError:
                continue
            if isinstance(parsed, dict):
                payloads.append(parsed)
            elif isinstance(parsed, list):
                payloads.extend(item for item in parsed if isinstance(item, dict))
        return payloads[:5]

    def _clean(self, value: str) -> str:
        cleaned = html.unescape(value or "").replace("·", " ").replace("•", " ")
        return WHITESPACE_PATTERN.sub(" ", cleaned).strip()

    def _filter_description(self, description: str, title: str) -> str:
        cleaned_description = description or ""
        cleaned_title = self._clean(title)
        if cleaned_title:
            cleaned_description = re.sub(
                re.escape(cleaned_title),
                " ",
                cleaned_description,
                flags=re.I,
            )
            title_tokens = cleaned_title.split()
            if len(title_tokens) >= 3:
                prefix = r"\s+".join(re.escape(token) for token in title_tokens[:3])
                cleaned_description = re.sub(
                    rf"\b{prefix}\b(?:\s+[A-Za-z][\w-]*){{0,4}}",
                    " ",
                    cleaned_description,
                    flags=re.I,
                )
        cleaned_description = re.sub(r"\bno trades?\b", " ", cleaned_description, flags=re.I)
        cleaned_description = re.sub(r"\bvery low\b", " ", cleaned_description, flags=re.I)
        cleaned_description = re.sub(r"\bmarketplace\b", " ", cleaned_description, flags=re.I)
        lines = [
            self._clean(line)
            for line in re.split(r"[\r\n]+", cleaned_description)
            if self._clean(line)
        ]
        title_tokens = set(self._clean(title).lower().split())
        kept: list[str] = []
        for line in lines:
            lower = line.lower()
            if lower == self._clean(title).lower():
                continue
            if re.fullmatch(r"(about this vehicle|seller['’]s description)", lower):
                continue
            if "miles" in lower or "transmission" in lower or "exterior" in lower or "interior" in lower:
                kept.append(line)
                continue
            if "vin" in lower:
                kept.append(line)
                continue
            if "rebuilt" in lower or "salvage" in lower or "clean title" in lower or "title" in lower:
                kept.append(line)
                continue
            overlap = len(title_tokens & set(lower.split()))
            if overlap >= max(3, len(title_tokens) // 2):
                continue
        return " ".join(kept[:4]).strip()

    def _structured_data_excerpt(self, payloads: list[dict[str, Any]]) -> str:
        snippets: list[str] = []
        for payload in payloads[:5]:
            snippets.extend(self._collect_structured_strings(payload))
        unique: list[str] = []
        for snippet in snippets:
            if snippet and snippet not in unique:
                unique.append(snippet)
        return " ".join(unique[:6]).strip()

    def _collect_structured_strings(self, value: Any) -> list[str]:
        found: list[str] = []
        if isinstance(value, dict):
            for key, child in value.items():
                lower_key = str(key).lower()
                if lower_key in {"vin", "vehicleidentificationnumber"} and child:
                    found.append(self._clean(f"VIN {child}"))
                elif lower_key in {"mileagefromodometer", "mileage", "mileagefromodometervalue"} and child:
                    found.append(self._clean(f"{child} miles"))
                elif lower_key in {"name", "model", "brand"} and child:
                    found.append(self._clean(str(child)))
                found.extend(self._collect_structured_strings(child))
        elif isinstance(value, list):
            for child in value:
                found.extend(self._collect_structured_strings(child))
        return found

    def _summarize_vehicle_text(
        self,
        title: str,
        description: str,
        body_excerpt: str,
        json_ld: list[dict[str, Any]],
        page_text: str,
    ) -> str:
        heuristic_summary = self._heuristic_vehicle_summary(title, description, body_excerpt, json_ld, page_text)
        if not self.openai_api_key:
            return heuristic_summary

        prompt = (
            "Extract a concise used-car summary from this listing text. "
            "Return only JSON with keys year, make, model, trim, mileage, transmission, exterior_color, "
            "interior_color, title_status, vin, asking_price, notable_attributes. "
            "Only include facts that are explicitly supported by the text.\n\n"
            f"Title: {title}\n"
            f"Description: {description}\n"
            f"Body excerpt: {body_excerpt}\n"
            f"Structured data: {json.dumps(json_ld, ensure_ascii=True)}\n"
            f"Page text excerpt: {page_text[:12000]}"
        )

        try:
            status, body, _ = self.http_client.request(
                "POST",
                "https://api.openai.com/v1/responses",
                headers={
                    "Authorization": f"Bearer {self.openai_api_key}",
                },
                json_body={
                    "model": self.openai_model,
                    "input": prompt,
                },
                source_key="link_extract_llm",
                timeout_seconds=18,
            )
            if status >= 400:
                return heuristic_summary
            payload = json.loads(body.decode("utf-8"))
            response_text = self._extract_response_text(payload)
            parsed = self._parse_summary_json(response_text)
            if not parsed:
                return heuristic_summary
            llm_summary = self._compose_vehicle_summary(parsed)
            return llm_summary or heuristic_summary
        except Exception:
            return heuristic_summary

    def _extract_response_text(self, payload: dict[str, Any]) -> str:
        output_text = payload.get("output_text")
        if isinstance(output_text, str) and output_text.strip():
            return output_text.strip()
        output = payload.get("output") or []
        chunks: list[str] = []
        for item in output:
            if not isinstance(item, dict):
                continue
            for content in item.get("content") or []:
                if not isinstance(content, dict):
                    continue
                text = content.get("text")
                if isinstance(text, str) and text.strip():
                    chunks.append(text.strip())
        return "\n".join(chunks).strip()

    def _parse_summary_json(self, text: str) -> dict[str, Any]:
        if not text:
            return {}
        candidates = [text]
        match = re.search(r"\{.*\}", text, re.S)
        if match:
            candidates.insert(0, match.group(0))
        for candidate in candidates:
            try:
                parsed = json.loads(candidate)
            except json.JSONDecodeError:
                continue
            if isinstance(parsed, dict):
                return parsed
        return {}

    def _heuristic_vehicle_summary(
        self,
        title: str,
        description: str,
        body_excerpt: str,
        json_ld: list[dict[str, Any]],
        page_text: str,
    ) -> str:
        combined = " ".join(
            part for part in [
                title,
                description,
                body_excerpt,
                self._structured_data_excerpt(json_ld),
                page_text,
            ]
            if part
        )
        normalized = self._clean(combined)
        mileage = self._first_match(
            normalized,
            [
                r"\bdriven\s+([\d,]{1,7})\s*miles?\b",
                r"\bodometer(?:\s+reading)?[^\d]{0,16}([\d,]{1,7})\b",
                r"\bmileage[^\d]{0,16}([\d,]{1,7})\b",
                r"\b([\d,]{1,7})\s*miles?\b",
            ],
        )
        transmission = self._first_match(
            normalized,
            [
                r"\b(automatic transmission|manual transmission|automatic|manual|cvt)\b",
            ],
        )
        exterior_color = self._first_match(
            normalized,
            [
                r"\bexterior color[:\s]+([a-z]+)\b",
                r"\bcolor[:\s]+([a-z]+)\b",
            ],
        )
        interior_color = self._first_match(
            normalized,
            [
                r"\binterior color[:\s]+([a-z]+)\b",
            ],
        )
        vin = self._first_match(normalized.upper(), [r"\b([A-HJ-NPR-Z0-9]{17})\b"])
        asking_price = self._extract_listing_price(title, description, body_excerpt, json_ld, page_text)
        title_status = ""
        lowered = normalized.lower()
        for candidate in ("rebuilt", "reconstructed", "salvage", "clean title"):
            if candidate in lowered:
                title_status = candidate
                break

        return self._compose_vehicle_summary(
            {
                "title": title,
                "mileage": mileage.replace(",", "") if mileage else "",
                "transmission": transmission,
                "exterior_color": exterior_color,
                "interior_color": interior_color,
                "vin": vin,
                "asking_price": asking_price,
                "title_status": title_status,
            }
        )

    def _extract_listing_price(
        self,
        title: str,
        description: str,
        body_excerpt: str,
        json_ld: list[dict[str, Any]],
        page_text: str,
    ) -> str:
        structured_price = self._structured_price(json_ld)
        if structured_price:
            return structured_price

        combined = self._clean(" ".join(part for part in [title, description, body_excerpt, page_text] if part))
        patterns = [
            r"\b(?:price|asking price|listing price|listed at)\b[^\d$]{0,12}\$?\s*([\d,]{3,8})\b",
            r"\$\s*([\d,]{3,8})\b",
        ]
        for pattern in patterns:
            match = re.search(pattern, combined, re.I)
            if not match:
                continue
            digits = re.sub(r"[^\d]", "", match.group(1))
            if digits:
                return digits
        return ""

    def _structured_price(self, payloads: list[dict[str, Any]]) -> str:
        for payload in payloads[:5]:
            price = self._find_structured_price(payload)
            if price:
                return price
        return ""

    def _find_structured_price(self, value: Any) -> str:
        if isinstance(value, dict):
            for key, child in value.items():
                lower_key = str(key).lower()
                if lower_key in {"price", "offers", "pricecurrency", "lowprice", "highprice"}:
                    digits = re.sub(r"[^\d]", "", self._clean(str(child)))
                    if digits:
                        return digits
                found = self._find_structured_price(child)
                if found:
                    return found
        elif isinstance(value, list):
            for child in value:
                found = self._find_structured_price(child)
                if found:
                    return found
        return ""

    def _first_match(self, text: str, patterns: list[str]) -> str:
        for pattern in patterns:
            match = re.search(pattern, text, re.I)
            if match:
                return self._clean(match.group(1))
        return ""

    def _compose_vehicle_summary(self, data: dict[str, Any]) -> str:
        parts = []
        for key in ("year", "make", "model", "trim"):
            value = self._clean(str(data.get(key) or ""))
            if value:
                parts.append(value)
        mileage = self._clean(str(data.get("mileage") or ""))
        if mileage:
            digits = re.sub(r"[^\d]", "", mileage)
            if digits:
                parts.append(f"{digits} miles")
        asking_price = self._clean(str(data.get("asking_price") or ""))
        if asking_price:
            digits = re.sub(r"[^\d]", "", asking_price)
            if digits:
                parts.append(f"asking price ${int(digits):,}")
        for key in ("transmission", "exterior_color", "interior_color", "vin", "title_status"):
            value = self._clean(str(data.get(key) or ""))
            if value:
                parts.append(value)
        notable = data.get("notable_attributes") or []
        if isinstance(notable, list):
            for item in notable[:4]:
                cleaned = self._clean(str(item))
                if cleaned:
                    parts.append(cleaned)
        return " ".join(parts).strip()
