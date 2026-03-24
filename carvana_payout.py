from __future__ import annotations

import asyncio
import json
import os
import re
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from comp_engine.http import HttpClient
from comp_engine.storage import SQLiteRepository


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(slots=True)
class CarvanaPayoutJobResult:
    status: str
    offer_amount: float | None
    offer_currency: str
    offer_text_raw: str
    result_summary: str
    result_json: dict[str, Any]
    screenshot_url_or_path: str
    page_text_capture: str
    error_message: str = ""


class BrowserAutomationProvider:
    def run_job(self, job: dict[str, Any]) -> CarvanaPayoutJobResult:
        raise NotImplementedError


class PlaywrightProvider(BrowserAutomationProvider):
    def run_job(self, job: dict[str, Any]) -> CarvanaPayoutJobResult:
        raise RuntimeError("Playwright provider is not configured yet. Set BROWSER_AUTOMATION_PROVIDER=browser_use.")


class BrowserUseProvider(BrowserAutomationProvider):
    def __init__(self, http_client: HttpClient, api_key: str) -> None:
        self.http_client = http_client
        self.api_key = api_key.strip()

    def run_job(self, job: dict[str, Any]) -> CarvanaPayoutJobResult:
        if not self.api_key:
            raise RuntimeError("BROWSER_USE_API_KEY is not configured.")
        return asyncio.run(self._run_job_async(job))

    async def _run_job_async(self, job: dict[str, Any]) -> CarvanaPayoutJobResult:
        try:
            from browser_use_sdk.v3 import AsyncBrowserUse
            from pydantic import BaseModel
        except Exception as exc:  # noqa: BLE001
            raise RuntimeError(
                "browser-use-sdk and pydantic are required for Carvana automation. "
                "Install the app requirements to enable this feature."
            ) from exc

        os.environ.setdefault("BROWSER_USE_API_KEY", self.api_key)

        class OfferSchema(BaseModel):
            offer_amount: str = ""
            offer_currency: str = "USD"
            offer_text_raw: str = ""
            result_summary: str = ""
            page_text_capture: str = ""
            vehicle_summary: str = ""

        client = AsyncBrowserUse()
        session = await client.sessions.create(proxy_country_code="us")
        share_url = ""
        try:
            try:
                share = await client.sessions.create_share(session.id)
                share_url = str(getattr(share, "url", "") or "")
            except Exception:
                share_url = ""

            result = await client.run(
                self._task_prompt(job),
                session_id=session.id,
                output_schema=OfferSchema,
            )
            messages = []
            try:
                messages = await client.sessions.messages(session.id)
            except Exception:
                messages = []

            output = getattr(result, "output", None) or {}
            if hasattr(output, "model_dump"):
                output_payload = output.model_dump()
            elif isinstance(output, dict):
                output_payload = output
            else:
                output_payload = {}

            output_text = self._collect_output_text(result, messages, output_payload)
            offer_amount = self._extract_offer_amount(output_payload.get("offer_amount") or output_text)
            status = "completed" if offer_amount is not None else ("requires_review" if output_text else "failed")
            summary = str(output_payload.get("result_summary") or "").strip() or (
                f"Carvana offer captured: ${offer_amount:,.0f}" if offer_amount is not None else "Carvana returned partial output that needs review."
            )

            return CarvanaPayoutJobResult(
                status=status,
                offer_amount=offer_amount,
                offer_currency=str(output_payload.get("offer_currency") or "USD").strip() or "USD",
                offer_text_raw=str(output_payload.get("offer_text_raw") or output_text).strip(),
                result_summary=summary,
                result_json={
                    "provider": "browser_use",
                    "session_id": getattr(session, "id", ""),
                    "live_url": str(getattr(session, "live_url", "") or ""),
                    "share_url": share_url,
                    "output": output_payload,
                },
                screenshot_url_or_path=share_url or str(getattr(session, "live_url", "") or ""),
                page_text_capture=str(output_payload.get("page_text_capture") or output_text).strip(),
                error_message="" if status != "failed" else "Carvana offer amount could not be captured.",
            )
        finally:
            try:
                await client.sessions.stop(session.id)
            except Exception:
                pass

    def _task_prompt(self, job: dict[str, Any]) -> str:
        vin = str(job.get("vin") or "").strip()
        license_plate = str(job.get("license_plate") or "").strip()
        plate_state = str(job.get("plate_state") or "").strip()
        title_status = "rebuilt/reconstructed title" if job.get("rebuilt_title") else "clean title"
        condition = str(job.get("condition") or "Good").strip()
        notes = str(job.get("notes") or "").strip()
        lookup_line = f"Use VIN {vin}." if vin else f"Use license plate {license_plate} in {plate_state}."

        prompt = f"""
You are completing a Carvana sell/trade offer lookup for a used vehicle.
Go to Carvana's sell or trade offer flow and obtain the current payout offer for this vehicle.

Vehicle details:
- {lookup_line}
- Mileage: {job.get("mileage")}
- Condition: {condition}
- Title status: {title_status}
- ZIP code: {job.get("zip_code") or "not provided"}
- Exterior color: {job.get("exterior_color") or "not provided"}
- Interior color: {job.get("interior_color") or "not provided"}
- Notes: {notes or "none"}

Rules:
- Complete only the steps needed to reach the offer result.
- Answer condition questions truthfully based on the provided fields.
- If Carvana asks about title problems, reflect the supplied title status.
- When you reach the final offer, capture the exact visible amount and nearby context text.
- If the flow fails or blocks, return the best partial result and explain what happened.
- Return a structured response using the requested schema only.
""".strip()
        return prompt

    def _collect_output_text(
        self,
        result: Any,
        messages: list[Any],
        output_payload: dict[str, Any],
    ) -> str:
        pieces: list[str] = []
        raw_output_text = getattr(result, "output_text", None)
        if isinstance(raw_output_text, str) and raw_output_text.strip():
            pieces.append(raw_output_text.strip())
        for key in ("offer_text_raw", "page_text_capture", "result_summary"):
            value = str(output_payload.get(key) or "").strip()
            if value:
                pieces.append(value)
        for message in messages[-8:]:
            text = ""
            if isinstance(message, dict):
                text = str(message.get("content") or message.get("text") or "").strip()
            else:
                text = str(getattr(message, "content", "") or getattr(message, "text", "")).strip()
            if text:
                pieces.append(text)
        return "\n".join(piece for piece in pieces if piece).strip()

    def _extract_offer_amount(self, text: str) -> float | None:
        normalized = str(text or "")
        matches = re.findall(r"\$[\s]*([\d,]{3,9})(?:\.\d{2})?", normalized)
        if not matches:
            return None
        try:
            return float(matches[-1].replace(",", ""))
        except ValueError:
            return None


class CarvanaPayoutService:
    def __init__(self, repository: SQLiteRepository) -> None:
        self.repository = repository
        self.enabled = os.getenv("CARVANA_PAYOUT_ENABLED", "true").strip().lower() in {"1", "true", "yes", "on"}
        self.provider_name = os.getenv("BROWSER_AUTOMATION_PROVIDER", "browser_use").strip().lower() or "browser_use"
        self.http_client = HttpClient(timeout_seconds=30, retry_count=1)
        self._worker_lock = threading.Lock()
        self._worker_started = False
        self._stop_event = threading.Event()

    def start_worker(self) -> None:
        if not self.enabled:
            return
        with self._worker_lock:
            if self._worker_started:
                return
            thread = threading.Thread(target=self._worker_loop, name="carvana-payout-worker", daemon=True)
            thread.start()
            self._worker_started = True

    def create_carvana_payout_job(self, user_id: int, payload: dict[str, Any]) -> dict[str, Any]:
        if not self.enabled:
            raise ValueError("Carvana payout is not enabled.")
        cleaned = self._validate_payload(payload)
        job_id = self.repository.create_carvana_payout_job(user_id=user_id, payload=cleaned)
        job = self.repository.get_carvana_payout_job(job_id, user_id=user_id)
        return job or {}

    def validate_carvana_payout_payload(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self._validate_payload(payload)

    def get_carvana_payout_job(self, job_id: int, user_id: int | None = None) -> dict[str, Any] | None:
        return self.repository.get_carvana_payout_job(job_id, user_id=user_id)

    def list_carvana_payout_jobs(
        self,
        user_id: int | None = None,
        limit: int = 15,
    ) -> list[dict[str, Any]]:
        return self.repository.list_carvana_payout_jobs(user_id=user_id, limit=limit)

    def retry_carvana_payout_job(
        self,
        job_id: int,
        user_id: int | None = None,
    ) -> dict[str, Any] | None:
        updated = self.repository.retry_carvana_payout_job(job_id, user_id=user_id)
        if not updated:
            return None
        return self.repository.get_carvana_payout_job(job_id, user_id=user_id)

    def _validate_payload(self, payload: dict[str, Any]) -> dict[str, Any]:
        vin = str(payload.get("vin") or "").strip().upper()
        license_plate = str(payload.get("license_plate") or payload.get("plate") or "").strip().upper()
        plate_state = str(payload.get("plate_state") or payload.get("state") or "").strip().upper()
        mileage_text = str(payload.get("mileage") or "").strip()
        zip_code = str(payload.get("zip_code") or "").strip()
        condition = str(payload.get("condition") or "").strip()
        rebuilt_title = str(payload.get("rebuilt_title") or "").strip().lower() in {"1", "true", "yes", "on"}
        exterior_color = str(payload.get("exterior_color") or "").strip()
        interior_color = str(payload.get("interior_color") or "").strip()
        notes = str(payload.get("notes") or "").strip()

        if not vin and not license_plate:
            raise ValueError("Enter either a VIN or a license plate.")
        if license_plate and not plate_state:
            raise ValueError("State is required when using a license plate.")
        if vin and len(vin) != 17:
            raise ValueError("VIN must be 17 characters.")
        if not mileage_text.isdigit():
            raise ValueError("Mileage is required and must be numeric.")
        mileage = int(mileage_text)
        if mileage < 0:
            raise ValueError("Mileage must be zero or greater.")
        if condition not in {"Excellent", "Good", "Fair", "Poor"}:
            raise ValueError("Choose a valid condition.")

        return {
            "vin": vin,
            "license_plate": license_plate,
            "plate_state": plate_state,
            "mileage": mileage,
            "zip_code": zip_code,
            "condition": condition,
            "rebuilt_title": rebuilt_title,
            "exterior_color": exterior_color,
            "interior_color": interior_color,
            "notes": notes,
        }

    def _worker_loop(self) -> None:
        while not self._stop_event.is_set():
            job = self.repository.claim_next_carvana_payout_job()
            if not job:
                time.sleep(2.0)
                continue
            try:
                result = self._provider().run_job(job)
            except Exception as exc:  # noqa: BLE001
                self.repository.fail_carvana_payout_job(job["id"], str(exc))
                time.sleep(0.2)
                continue

            if result.status == "failed":
                self.repository.fail_carvana_payout_job(
                    job["id"],
                    result.error_message or "Carvana payout lookup failed.",
                    partial_result={
                        "offer_amount": result.offer_amount,
                        "offer_currency": result.offer_currency,
                        "offer_text_raw": result.offer_text_raw,
                        "result_summary": result.result_summary,
                        "result_json": result.result_json,
                        "screenshot_url_or_path": result.screenshot_url_or_path,
                        "page_text_capture": result.page_text_capture,
                    },
                )
            else:
                self.repository.complete_carvana_payout_job(
                    job["id"],
                    status=result.status,
                    offer_amount=result.offer_amount,
                    offer_currency=result.offer_currency,
                    offer_text_raw=result.offer_text_raw,
                    result_summary=result.result_summary,
                    result_json=result.result_json,
                    screenshot_url_or_path=result.screenshot_url_or_path,
                    page_text_capture=result.page_text_capture,
                    error_message=result.error_message,
                )
            time.sleep(0.2)

    def _provider(self) -> BrowserAutomationProvider:
        if self.provider_name == "playwright":
            return PlaywrightProvider()
        return BrowserUseProvider(self.http_client, os.getenv("BROWSER_USE_API_KEY", "").strip())
