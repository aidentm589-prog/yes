from __future__ import annotations

import json
import os
from typing import Any

from .http import HttpClient


class LlmClient:
    def __init__(self, http_client: HttpClient) -> None:
        self.http_client = http_client
        self.ollama_base_url = os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434").strip().rstrip("/")
        self.ollama_model = os.getenv("OLLAMA_MODEL", "qwen2.5:7b-instruct").strip() or "qwen2.5:7b-instruct"
        self.ollama_enabled = os.getenv("OLLAMA_ENABLED", "").strip().lower() in {"1", "true", "yes", "on"}
        self.openai_api_key = os.getenv("OPENAI_API_KEY", "").strip()

    def is_ollama_available(self) -> bool:
        if not self.ollama_enabled:
            return False
        try:
            status, _, _ = self.http_client.request(
                "GET",
                f"{self.ollama_base_url}/api/tags",
                source_key="ollama_health",
                timeout_seconds=4,
            )
            return status < 400
        except Exception:
            return False

    def complete_json(
        self,
        *,
        prompt: str,
        openai_model: str,
        source_key: str,
        timeout_seconds: int = 30,
    ) -> dict[str, Any]:
        if self.is_ollama_available():
            data = self._complete_with_ollama(prompt, source_key=source_key, timeout_seconds=timeout_seconds)
            if data:
                return data
        if self.openai_api_key:
            data = self._complete_with_openai(
                prompt,
                model=openai_model,
                source_key=source_key,
                timeout_seconds=timeout_seconds,
            )
            if data:
                return data
        raise RuntimeError("No available LLM provider returned JSON.")

    def _complete_with_ollama(
        self,
        prompt: str,
        *,
        source_key: str,
        timeout_seconds: int,
    ) -> dict[str, Any]:
        status, body, _ = self.http_client.request(
            "POST",
            f"{self.ollama_base_url}/api/generate",
            json_body={
                "model": self.ollama_model,
                "prompt": (
                    "Return only valid JSON. Do not include markdown fences, commentary, or prose.\n\n"
                    f"{prompt}"
                ),
                "stream": False,
                "options": {
                    "temperature": 0.2,
                },
            },
            source_key=f"{source_key}_ollama",
            timeout_seconds=timeout_seconds,
        )
        if status >= 400:
            raise RuntimeError(body.decode("utf-8", "ignore"))
        payload = json.loads(body.decode("utf-8"))
        response_text = str(payload.get("response") or "").strip()
        return self._extract_json_object(response_text)

    def _complete_with_openai(
        self,
        prompt: str,
        *,
        model: str,
        source_key: str,
        timeout_seconds: int,
    ) -> dict[str, Any]:
        status, body, _ = self.http_client.request(
            "POST",
            "https://api.openai.com/v1/responses",
            headers={"Authorization": f"Bearer {self.openai_api_key}"},
            json_body={"model": model, "input": prompt},
            source_key=source_key,
            timeout_seconds=timeout_seconds,
        )
        if status >= 400:
            raise RuntimeError(body.decode("utf-8", "ignore"))
        payload = json.loads(body.decode("utf-8"))
        response_text = self._extract_openai_response_text(payload)
        return self._extract_json_object(response_text)

    def _extract_openai_response_text(self, payload: dict[str, Any]) -> str:
        output = payload.get("output") or []
        collected: list[str] = []
        for item in output:
            for content in item.get("content") or []:
                text = content.get("text")
                if text:
                    collected.append(str(text))
        return "\n".join(collected).strip()

    def _extract_json_object(self, text: str) -> dict[str, Any]:
        start = text.find("{")
        end = text.rfind("}")
        if start == -1 or end == -1 or end <= start:
            raise RuntimeError("LLM did not return a JSON object.")
        return json.loads(text[start:end + 1])
