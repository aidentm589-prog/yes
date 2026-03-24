from __future__ import annotations

import json
import os
from typing import Any

from comp_engine.http import HttpClient


SYSTEM_PROMPT = """
You are the built-in Car Flip Analyzer assistant for this software.
Your job is to help users understand, use, and improve the app.

Current product context:
- The app evaluates used cars for resale opportunities.
- It supports individual evaluations and bulk evaluations.
- It computes market value, safe buy value, expected resale value, estimated profit, confidence, and risk.
- It has comparable listings, condition sweep, title impact, full evaluation, portfolio, and admin areas.

Behavior rules:
- Be concise, helpful, and product-aware.
- Answer questions about how the software works in plain English.
- If the user asks for feature ideas or programming changes, give practical implementation guidance.
- Do not claim code was changed unless the user is clearly chatting inside the built-in support assistant about planning or usage.
- If something is unknown, say so instead of inventing details.
- Keep responses short and easy to scan.
""".strip()


class SoftwareChatService:
    def __init__(self) -> None:
        self.api_key = os.getenv("OPENAI_API_KEY", "").strip()
        self.model = os.getenv("OPENAI_SOFTWARE_CHAT_MODEL", "gpt-5.4").strip()
        self.http_client = HttpClient(timeout_seconds=20, retry_count=1)

    def reply(self, messages: list[dict[str, Any]]) -> dict[str, Any]:
        cleaned_messages = self._clean_messages(messages)
        if not cleaned_messages:
            return {"message": "Ask me anything about Car Flip Analyzer and I’ll help."}

        if not self.api_key:
            return {
                "message": (
                    "The software chat is installed, but `OPENAI_API_KEY` is not set yet. "
                    "Add that key to enable live assistant replies."
                )
            }

        prompt = self._build_prompt(cleaned_messages)
        status, body, _ = self.http_client.request(
            "POST",
            "https://api.openai.com/v1/responses",
            headers={
                "Authorization": f"Bearer {self.api_key}",
            },
            json_body={
                "model": self.model,
                "input": prompt,
            },
            source_key="software_chat",
            timeout_seconds=24,
        )
        if status >= 400:
            raise RuntimeError(f"Software chat failed with {status}: {body.decode('utf-8', 'ignore')}")

        payload = json.loads(body.decode("utf-8"))
        message = self._extract_response_text(payload).strip()
        if not message:
            message = "I’m here, but I didn’t get a usable response back from the model."
        return {"message": message}

    def _clean_messages(self, messages: list[dict[str, Any]]) -> list[dict[str, str]]:
        cleaned: list[dict[str, str]] = []
        for item in messages[-12:]:
            if not isinstance(item, dict):
                continue
            role = str(item.get("role") or "").strip().lower()
            content = str(item.get("content") or "").strip()
            if role not in {"user", "assistant"} or not content:
                continue
            cleaned.append({"role": role, "content": content[:4000]})
        return cleaned

    def _build_prompt(self, messages: list[dict[str, str]]) -> str:
        transcript = []
        for item in messages:
            prefix = "User" if item["role"] == "user" else "Assistant"
            transcript.append(f"{prefix}: {item['content']}")
        return f"{SYSTEM_PROMPT}\n\nConversation:\n" + "\n\n".join(transcript)

    def _extract_response_text(self, payload: dict[str, Any]) -> str:
        output_text = payload.get("output_text")
        if isinstance(output_text, str) and output_text.strip():
            return output_text.strip()
        chunks: list[str] = []
        for item in payload.get("output") or []:
            if not isinstance(item, dict):
                continue
            for content in item.get("content") or []:
                if not isinstance(content, dict):
                    continue
                text = content.get("text")
                if isinstance(text, str) and text.strip():
                    chunks.append(text.strip())
        return "\n".join(chunks).strip()
