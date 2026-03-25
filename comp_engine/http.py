from __future__ import annotations

import json
import logging
import ssl
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

import certifi


LOGGER = logging.getLogger(__name__)


class RateLimiter:
    def __init__(self, min_interval_seconds: float = 0.0) -> None:
        self.min_interval_seconds = min_interval_seconds
        self._lock = threading.Lock()
        self._next_allowed = 0.0

    def wait(self) -> None:
        if self.min_interval_seconds <= 0:
            return
        with self._lock:
            now = time.monotonic()
            delay = self._next_allowed - now
            if delay > 0:
                time.sleep(delay)
            self._next_allowed = time.monotonic() + self.min_interval_seconds


class HttpClient:
    def __init__(self, timeout_seconds: int = 20, retry_count: int = 2) -> None:
        self.timeout_seconds = timeout_seconds
        self.retry_count = retry_count
        self.ssl_context = ssl.create_default_context(cafile=certifi.where())
        self.default_headers = {
            "User-Agent": "Mozilla/5.0 (compatible; AidenCarResellAnalyzer/1.0)",
            "Accept": "*/*",
        }
        self._rate_limiters: dict[str, RateLimiter] = {}

    def register_rate_limiter(self, key: str, min_interval_seconds: float) -> None:
        self._rate_limiters[key] = RateLimiter(min_interval_seconds=min_interval_seconds)

    def request(
        self,
        method: str,
        url: str,
        *,
        params: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
        data: bytes | None = None,
        json_body: dict[str, Any] | None = None,
        source_key: str = "",
        timeout_seconds: int | None = None,
    ) -> tuple[int, bytes, dict[str, str]]:
        if params:
            query = urllib.parse.urlencode(
                {key: value for key, value in params.items() if value not in (None, "", [])},
                doseq=True,
            )
            if query:
                separator = "&" if "?" in url else "?"
                url = f"{url}{separator}{query}"

        payload = data
        request_headers = dict(self.default_headers)
        if headers:
            request_headers.update(headers)
        if json_body is not None:
            payload = json.dumps(json_body).encode("utf-8")
            request_headers.setdefault("Content-Type", "application/json")

        attempts = max(1, self.retry_count + 1)
        last_error: Exception | None = None
        limiter = self._rate_limiters.get(source_key)
        for attempt in range(attempts):
            if limiter:
                limiter.wait()
            request = urllib.request.Request(
                url,
                data=payload,
                headers=request_headers,
                method=method.upper(),
            )
            try:
                with urllib.request.urlopen(
                    request,
                    context=self.ssl_context,
                    timeout=timeout_seconds or self.timeout_seconds,
                ) as response:
                    body = response.read()
                    response_headers = {key.lower(): value for key, value in response.headers.items()}
                    return response.status, body, response_headers
            except urllib.error.HTTPError as exc:
                body = exc.read() if exc.fp else b""
                response_headers = (
                    {key.lower(): value for key, value in exc.headers.items()}
                    if exc.headers
                    else {}
                )
                if exc.code < 500 or attempt == attempts - 1:
                    return exc.code, body, response_headers
                last_error = exc
            except Exception as exc:  # noqa: BLE001
                last_error = exc
                if attempt == attempts - 1:
                    break
            time.sleep(min(2.5, 0.35 * (attempt + 1)))

        raise RuntimeError(f"HTTP request failed for {url}: {last_error}") from last_error

    def get_text(
        self,
        url: str,
        *,
        params: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
        source_key: str = "",
    ) -> str:
        status, body, _ = self.request(
            "GET",
            url,
            params=params,
            headers=headers,
            source_key=source_key,
        )
        if status >= 400:
            raise RuntimeError(f"GET {url} failed with {status}")
        return body.decode("utf-8", "ignore")

    def get_json(
        self,
        url: str,
        *,
        params: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
        source_key: str = "",
        timeout_seconds: int | None = None,
    ) -> dict[str, Any]:
        status, body, _ = self.request(
            "GET",
            url,
            params=params,
            headers=headers,
            source_key=source_key,
            timeout_seconds=timeout_seconds,
        )
        if status >= 400:
            raise RuntimeError(f"GET {url} failed with {status}: {body.decode('utf-8', 'ignore')}")
        return json.loads(body.decode("utf-8"))
