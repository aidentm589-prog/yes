from __future__ import annotations

import copy
import json
import re
import sqlite3
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from .models import NormalizedListing
from .query_parser import parse_vehicle_query


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class SQLiteRepository:
    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._migrate()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        return connection

    def _migrate(self) -> None:
        migration_dir = Path(__file__).resolve().parents[1] / "migrations"
        sql_files = sorted(migration_dir.glob("*.sql"))
        with self._lock, self._connect() as connection:
            connection.execute(
                "CREATE TABLE IF NOT EXISTS schema_migrations (filename TEXT PRIMARY KEY, applied_at TEXT NOT NULL)"
            )
            applied = {
                row["filename"]
                for row in connection.execute("SELECT filename FROM schema_migrations")
            }
            for sql_file in sql_files:
                if sql_file.name in applied:
                    continue
                connection.executescript(sql_file.read_text())
                connection.execute(
                    "INSERT INTO schema_migrations (filename, applied_at) VALUES (?, ?)",
                    (sql_file.name, _utc_now_iso()),
                )
            connection.commit()

    def get_cache_json(self, cache_key: str) -> dict[str, Any] | None:
        with self._lock, self._connect() as connection:
            row = connection.execute(
                "SELECT payload, expires_at FROM cache_entries WHERE cache_key = ?",
                (cache_key,),
            ).fetchone()
        if not row:
            return None
        expires_at = datetime.fromisoformat(row["expires_at"])
        if expires_at <= datetime.now(timezone.utc):
            return None
        return json.loads(row["payload"])

    def set_cache_json(self, cache_key: str, payload: dict[str, Any], ttl_seconds: int) -> None:
        expires_at = datetime.now(timezone.utc) + timedelta(seconds=ttl_seconds)
        with self._lock, self._connect() as connection:
            connection.execute(
                """
                INSERT INTO cache_entries (cache_key, payload, created_at, expires_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(cache_key) DO UPDATE SET
                    payload = excluded.payload,
                    created_at = excluded.created_at,
                    expires_at = excluded.expires_at
                """,
                (
                    cache_key,
                    json.dumps(payload, sort_keys=False, default=str),
                    _utc_now_iso(),
                    expires_at.isoformat(),
                ),
            )
            connection.commit()

    def store_source_run(
        self,
        query_hash: str,
        source_key: str,
        status: str,
        message: str,
        raw_listings: list[dict[str, Any]],
        normalized_listings: list[NormalizedListing],
    ) -> None:
        fetched_at = _utc_now_iso()
        with self._lock, self._connect() as connection:
            cursor = connection.execute(
                """
                INSERT INTO source_runs (query_hash, source, status, message, fetched_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (query_hash, source_key, status, message, fetched_at),
            )
            source_run_id = cursor.lastrowid
            for raw in raw_listings:
                connection.execute(
                    """
                    INSERT INTO raw_listings
                    (source_run_id, source, source_listing_id, url, fetched_at, payload)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        source_run_id,
                        source_key,
                        str(raw.get("source_listing_id", "")),
                        str(raw.get("url", "")),
                        fetched_at,
                        json.dumps(raw, default=str),
                    ),
                )
            for listing in normalized_listings:
                connection.execute(
                    """
                    INSERT INTO normalized_listings
                    (source_run_id, source, source_listing_id, dedupe_key, url, fetched_at, payload)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        source_run_id,
                        listing.source,
                        listing.source_listing_id,
                        listing.dedupe_key(),
                        listing.url,
                        listing.fetched_at,
                        json.dumps(listing.to_dict(), default=str),
                    ),
                )
            connection.commit()

    def save_evaluation(
        self,
        user_id: int | None,
        vehicle_title: str,
        vehicle_input: str,
        preview_payload: dict[str, Any],
        snapshot_payload: dict[str, Any],
    ) -> int:
        normalized_snapshot = self._normalize_saved_snapshot(vehicle_input, snapshot_payload)
        normalized_preview = self._normalize_saved_preview(preview_payload, normalized_snapshot)
        now = _utc_now_iso()
        with self._lock, self._connect() as connection:
            cursor = connection.execute(
                """
                INSERT INTO saved_evaluations
                (user_id, vehicle_title, vehicle_input, created_at, updated_at, preview_payload, snapshot_payload)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    user_id,
                    vehicle_title,
                    vehicle_input,
                    now,
                    now,
                    json.dumps(normalized_preview, sort_keys=False, default=str),
                    json.dumps(normalized_snapshot, sort_keys=False, default=str),
                ),
            )
            connection.commit()
            return int(cursor.lastrowid)

    def list_saved_evaluations(self, user_id: int | None = None) -> list[dict[str, Any]]:
        where_clause = ""
        params: list[Any] = []
        if user_id is not None:
            where_clause = "WHERE user_id = ?"
            params.append(user_id)
        with self._lock, self._connect() as connection:
            rows = connection.execute(
                """
                SELECT id, user_id, vehicle_title, vehicle_input, created_at, updated_at, preview_payload, snapshot_payload
                FROM saved_evaluations
                """
                + where_clause
                + """
                ORDER BY updated_at DESC, id DESC
                """,
                params,
            ).fetchall()
        items: list[dict[str, Any]] = []
        for row in rows:
            snapshot_payload = self._normalize_saved_snapshot(
                row["vehicle_input"],
                json.loads(row["snapshot_payload"]),
            )
            preview_payload = self._normalize_saved_preview(
                json.loads(row["preview_payload"]),
                snapshot_payload,
            )
            items.append(
                {
                    "id": int(row["id"]),
                    "user_id": row["user_id"],
                    "vehicle_title": self._display_vehicle_title(
                        row["vehicle_title"],
                        row["vehicle_input"],
                        snapshot_payload,
                    ),
                    "vehicle_input": row["vehicle_input"],
                    "created_at": row["created_at"],
                    "updated_at": row["updated_at"],
                    "preview": preview_payload,
                }
            )
        return items

    def get_saved_evaluation(self, evaluation_id: int, user_id: int | None = None) -> dict[str, Any] | None:
        where_clause = "WHERE id = ?"
        params: list[Any] = [evaluation_id]
        if user_id is not None:
            where_clause += " AND user_id = ?"
            params.append(user_id)
        with self._lock, self._connect() as connection:
            row = connection.execute(
                """
                SELECT id, user_id, vehicle_title, vehicle_input, created_at, updated_at, preview_payload, snapshot_payload
                FROM saved_evaluations
                """
                + where_clause,
                params,
            ).fetchone()
        if not row:
            return None
        snapshot_payload = self._normalize_saved_snapshot(
            row["vehicle_input"],
            json.loads(row["snapshot_payload"]),
        )
        preview_payload = self._normalize_saved_preview(
            json.loads(row["preview_payload"]),
            snapshot_payload,
        )
        return {
            "id": int(row["id"]),
            "user_id": row["user_id"],
            "vehicle_title": self._display_vehicle_title(
                row["vehicle_title"],
                row["vehicle_input"],
                snapshot_payload,
            ),
            "vehicle_input": row["vehicle_input"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
            "preview": preview_payload,
            "snapshot": snapshot_payload,
        }

    def update_saved_evaluation(
        self,
        evaluation_id: int,
        user_id: int | None,
        vehicle_title: str,
        preview_payload: dict[str, Any],
        snapshot_payload: dict[str, Any],
    ) -> bool:
        normalized_snapshot = self._normalize_saved_snapshot("", snapshot_payload)
        normalized_preview = self._normalize_saved_preview(preview_payload, normalized_snapshot)
        now = _utc_now_iso()
        where_clause = "WHERE id = ?"
        params: list[Any] = [
            vehicle_title,
            now,
            json.dumps(normalized_preview, sort_keys=False, default=str),
            json.dumps(normalized_snapshot, sort_keys=False, default=str),
            evaluation_id,
        ]
        if user_id is not None:
            where_clause += " AND user_id = ?"
            params.append(user_id)
        with self._lock, self._connect() as connection:
            cursor = connection.execute(
                """
                UPDATE saved_evaluations
                SET vehicle_title = ?, updated_at = ?, preview_payload = ?, snapshot_payload = ?
                """
                + where_clause,
                params,
            )
            connection.commit()
            return cursor.rowcount > 0

    def delete_saved_evaluation(self, evaluation_id: int, user_id: int | None = None) -> bool:
        where_clause = "WHERE id = ?"
        params: list[Any] = [evaluation_id]
        if user_id is not None:
            where_clause += " AND user_id = ?"
            params.append(user_id)
        with self._lock, self._connect() as connection:
            cursor = connection.execute(
                "DELETE FROM saved_evaluations " + where_clause,
                params,
            )
            connection.commit()
            return cursor.rowcount > 0

    def create_user_account(
        self,
        *,
        first_name: str,
        email: str,
        password_hash: str,
        role: str,
        tier: int,
        credit_balance: int,
        has_bulk_access: bool,
        is_unlimited: bool,
        status: str,
        last_free_credit_at: str | None = None,
        last_login_at: str | None = None,
    ) -> int:
        now = _utc_now_iso()
        with self._lock, self._connect() as connection:
            cursor = connection.execute(
                """
                INSERT INTO user_accounts
                (first_name, email, password_hash, role, tier, credit_balance, has_bulk_access, is_unlimited, created_at, updated_at, last_free_credit_at, last_login_at, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    first_name,
                    email,
                    password_hash,
                    role,
                    tier,
                    credit_balance,
                    1 if has_bulk_access else 0,
                    1 if is_unlimited else 0,
                    now,
                    now,
                    last_free_credit_at,
                    last_login_at,
                    status,
                ),
            )
            connection.commit()
            return int(cursor.lastrowid)

    def get_user_by_email(self, email: str) -> dict[str, Any] | None:
        with self._lock, self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM user_accounts WHERE lower(email) = lower(?)",
                (email,),
            ).fetchone()
        return self._serialize_user_row(row)

    def get_user_by_id(self, user_id: int) -> dict[str, Any] | None:
        with self._lock, self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM user_accounts WHERE id = ?",
                (user_id,),
            ).fetchone()
        return self._serialize_user_row(row)

    def list_user_accounts(self) -> list[dict[str, Any]]:
        with self._lock, self._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM user_accounts ORDER BY created_at DESC, id DESC"
            ).fetchall()
        return [self._serialize_user_row(row) for row in rows if row]

    def update_user_account(self, user_id: int, **fields: Any) -> bool:
        if not fields:
            return False
        allowed = {
            "first_name",
            "email",
            "password_hash",
            "role",
            "tier",
            "credit_balance",
            "has_bulk_access",
            "is_unlimited",
            "last_free_credit_at",
            "last_login_at",
            "status",
        }
        updates: list[str] = []
        params: list[Any] = []
        for key, value in fields.items():
            if key not in allowed:
                continue
            if key in {"has_bulk_access", "is_unlimited"}:
                value = 1 if value else 0
            updates.append(f"{key} = ?")
            params.append(value)
        if not updates:
            return False
        updates.append("updated_at = ?")
        params.append(_utc_now_iso())
        params.append(user_id)
        with self._lock, self._connect() as connection:
            cursor = connection.execute(
                f"UPDATE user_accounts SET {', '.join(updates)} WHERE id = ?",
                params,
            )
            connection.commit()
            return cursor.rowcount > 0

    def delete_user_account(self, user_id: int) -> bool:
        with self._lock, self._connect() as connection:
            connection.execute("DELETE FROM saved_evaluations WHERE user_id = ?", (user_id,))
            connection.execute("DELETE FROM carvana_payout_jobs WHERE user_id = ?", (user_id,))
            cursor = connection.execute("DELETE FROM user_accounts WHERE id = ?", (user_id,))
            connection.commit()
            return cursor.rowcount > 0

    def list_subscription_tiers(self) -> list[dict[str, Any]]:
        with self._lock, self._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM subscription_tiers ORDER BY tier ASC"
            ).fetchall()
        return [self._serialize_subscription_tier_row(row) for row in rows if row]

    def get_subscription_tier(self, tier: int) -> dict[str, Any] | None:
        with self._lock, self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM subscription_tiers WHERE tier = ?",
                (tier,),
            ).fetchone()
        return self._serialize_subscription_tier_row(row)

    def upsert_subscription_tier(
        self,
        *,
        tier: int,
        display_name: str,
        credits_granted: int,
        monthly_price: str,
        yearly_price: str,
        marketing_copy: str,
        has_bulk_access: bool,
        is_unlimited: bool,
    ) -> dict[str, Any]:
        now = _utc_now_iso()
        with self._lock, self._connect() as connection:
            connection.execute(
                """
                INSERT INTO subscription_tiers
                (tier, display_name, credits_granted, monthly_price, yearly_price, marketing_copy, has_bulk_access, is_unlimited, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(tier) DO UPDATE SET
                    display_name = excluded.display_name,
                    credits_granted = excluded.credits_granted,
                    monthly_price = excluded.monthly_price,
                    yearly_price = excluded.yearly_price,
                    marketing_copy = excluded.marketing_copy,
                    has_bulk_access = excluded.has_bulk_access,
                    is_unlimited = excluded.is_unlimited,
                    updated_at = excluded.updated_at
                """,
                (
                    tier,
                    display_name,
                    credits_granted,
                    monthly_price,
                    yearly_price,
                    marketing_copy,
                    1 if has_bulk_access else 0,
                    1 if is_unlimited else 0,
                    now,
                    now,
                ),
            )
            connection.commit()
        return self.get_subscription_tier(tier) or {}

    def create_carvana_payout_job(self, user_id: int | None, payload: dict[str, Any]) -> int:
        now = _utc_now_iso()
        submitted_payload_json = json.dumps(payload, sort_keys=False, default=str)
        with self._lock, self._connect() as connection:
            cursor = connection.execute(
                """
                INSERT INTO carvana_payout_jobs
                (user_id, source, status, vin, license_plate, plate_state, mileage, zip_code, condition, rebuilt_title,
                 exterior_color, interior_color, notes, submitted_payload_json, created_at, updated_at)
                VALUES (?, 'carvana', 'queued', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    user_id,
                    str(payload.get("vin") or ""),
                    str(payload.get("license_plate") or ""),
                    str(payload.get("plate_state") or ""),
                    int(payload.get("mileage") or 0),
                    str(payload.get("zip_code") or ""),
                    str(payload.get("condition") or ""),
                    1 if payload.get("rebuilt_title") else 0,
                    str(payload.get("exterior_color") or ""),
                    str(payload.get("interior_color") or ""),
                    str(payload.get("notes") or ""),
                    submitted_payload_json,
                    now,
                    now,
                ),
            )
            connection.commit()
            return int(cursor.lastrowid)

    def list_carvana_payout_jobs(
        self,
        user_id: int | None = None,
        limit: int = 15,
    ) -> list[dict[str, Any]]:
        where_clause = ""
        params: list[Any] = []
        if user_id is not None:
            where_clause = "WHERE user_id = ?"
            params.append(user_id)
        params.append(max(1, int(limit)))
        with self._lock, self._connect() as connection:
            rows = connection.execute(
                """
                SELECT *
                FROM carvana_payout_jobs
                """
                + where_clause
                + """
                ORDER BY created_at DESC, id DESC
                LIMIT ?
                """,
                params,
            ).fetchall()
        return [self._serialize_carvana_payout_job(row) for row in rows if row]

    def get_carvana_payout_job(self, job_id: int, user_id: int | None = None) -> dict[str, Any] | None:
        where_clause = "WHERE id = ?"
        params: list[Any] = [job_id]
        if user_id is not None:
            where_clause += " AND user_id = ?"
            params.append(user_id)
        with self._lock, self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM carvana_payout_jobs " + where_clause,
                params,
            ).fetchone()
        return self._serialize_carvana_payout_job(row)

    def claim_next_carvana_payout_job(self) -> dict[str, Any] | None:
        now = _utc_now_iso()
        with self._lock, self._connect() as connection:
            row = connection.execute(
                """
                SELECT id
                FROM carvana_payout_jobs
                WHERE status = 'queued'
                ORDER BY created_at ASC, id ASC
                LIMIT 1
                """
            ).fetchone()
            if not row:
                return None
            connection.execute(
                """
                UPDATE carvana_payout_jobs
                SET status = 'running', started_at = ?, updated_at = ?, failed_at = NULL, error_message = ''
                WHERE id = ?
                """,
                (now, now, int(row["id"])),
            )
            connection.commit()
        return self.get_carvana_payout_job(int(row["id"]))

    def complete_carvana_payout_job(
        self,
        job_id: int,
        *,
        status: str,
        offer_amount: float | None,
        offer_currency: str,
        offer_text_raw: str,
        result_summary: str,
        result_json: dict[str, Any],
        screenshot_url_or_path: str,
        page_text_capture: str,
        error_message: str = "",
    ) -> bool:
        now = _utc_now_iso()
        with self._lock, self._connect() as connection:
            cursor = connection.execute(
                """
                UPDATE carvana_payout_jobs
                SET status = ?, completed_at = ?, updated_at = ?, offer_amount = ?, offer_currency = ?, offer_text_raw = ?,
                    result_summary = ?, result_json = ?, screenshot_url_or_path = ?, page_text_capture = ?, error_message = ?, failed_at = NULL
                WHERE id = ?
                """,
                (
                    status,
                    now,
                    now,
                    offer_amount,
                    offer_currency,
                    offer_text_raw,
                    result_summary,
                    json.dumps(result_json, sort_keys=False, default=str),
                    screenshot_url_or_path,
                    page_text_capture,
                    error_message,
                    job_id,
                ),
            )
            connection.commit()
            return cursor.rowcount > 0

    def fail_carvana_payout_job(
        self,
        job_id: int,
        error_message: str,
        partial_result: dict[str, Any] | None = None,
    ) -> bool:
        now = _utc_now_iso()
        partial_result = partial_result or {}
        status = "requires_review" if any(partial_result.values()) else "failed"
        with self._lock, self._connect() as connection:
            cursor = connection.execute(
                """
                UPDATE carvana_payout_jobs
                SET status = ?, failed_at = ?, updated_at = ?, offer_amount = ?, offer_currency = ?, offer_text_raw = ?,
                    result_summary = ?, result_json = ?, screenshot_url_or_path = ?, page_text_capture = ?, error_message = ?
                WHERE id = ?
                """,
                (
                    status,
                    now,
                    now,
                    partial_result.get("offer_amount"),
                    partial_result.get("offer_currency", "USD"),
                    partial_result.get("offer_text_raw", ""),
                    partial_result.get("result_summary", ""),
                    json.dumps(partial_result.get("result_json") or {}, sort_keys=False, default=str),
                    partial_result.get("screenshot_url_or_path", ""),
                    partial_result.get("page_text_capture", ""),
                    error_message,
                    job_id,
                ),
            )
            connection.commit()
            return cursor.rowcount > 0

    def retry_carvana_payout_job(self, job_id: int, user_id: int | None = None) -> bool:
        where_clause = "WHERE id = ?"
        params: list[Any] = [job_id]
        if user_id is not None:
            where_clause += " AND user_id = ?"
            params.append(user_id)
        now = _utc_now_iso()
        with self._lock, self._connect() as connection:
            cursor = connection.execute(
                """
                UPDATE carvana_payout_jobs
                SET status = 'queued', started_at = NULL, completed_at = NULL, failed_at = NULL,
                    offer_amount = NULL, offer_currency = NULL, offer_text_raw = '', result_summary = '',
                    result_json = '', screenshot_url_or_path = '', page_text_capture = '', error_message = '',
                    updated_at = ?
                """
                + where_clause,
                [now, *params],
            )
            connection.commit()
            return cursor.rowcount > 0

    def _serialize_user_row(self, row: sqlite3.Row | None) -> dict[str, Any] | None:
        if not row:
            return None
        return {
            "id": int(row["id"]),
            "first_name": str(row["first_name"] or ""),
            "email": row["email"],
            "password_hash": row["password_hash"],
            "role": row["role"],
            "tier": int(row["tier"]),
            "credit_balance": int(row["credit_balance"]),
            "has_bulk_access": bool(row["has_bulk_access"]),
            "is_unlimited": bool(row["is_unlimited"]),
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
            "last_free_credit_at": row["last_free_credit_at"],
            "last_login_at": row["last_login_at"],
            "status": row["status"],
        }

    def _serialize_subscription_tier_row(self, row: sqlite3.Row | None) -> dict[str, Any] | None:
        if not row:
            return None
        return {
            "tier": int(row["tier"]),
            "display_name": str(row["display_name"] or ""),
            "credits_granted": int(row["credits_granted"] or 0),
            "monthly_price": str(row["monthly_price"] or ""),
            "yearly_price": str(row["yearly_price"] or ""),
            "marketing_copy": str(row["marketing_copy"] or ""),
            "has_bulk_access": bool(row["has_bulk_access"]),
            "is_unlimited": bool(row["is_unlimited"]),
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }

    def _serialize_carvana_payout_job(self, row: sqlite3.Row | None) -> dict[str, Any] | None:
        if not row:
            return None
        submitted_payload = self._safe_json_loads(row["submitted_payload_json"])
        result_json = self._safe_json_loads(row["result_json"])
        vin = str(row["vin"] or "").strip()
        plate = str(row["license_plate"] or "").strip()
        identifier = vin or plate or f"Job {row['id']}"
        return {
            "id": int(row["id"]),
            "user_id": row["user_id"],
            "source": row["source"],
            "status": row["status"],
            "vehicle_identifier": identifier,
            "vin": vin,
            "license_plate": plate,
            "plate_state": str(row["plate_state"] or ""),
            "mileage": int(row["mileage"] or 0),
            "zip_code": str(row["zip_code"] or ""),
            "condition": str(row["condition"] or ""),
            "rebuilt_title": bool(row["rebuilt_title"]),
            "exterior_color": str(row["exterior_color"] or ""),
            "interior_color": str(row["interior_color"] or ""),
            "notes": str(row["notes"] or ""),
            "submitted_payload": submitted_payload,
            "started_at": row["started_at"],
            "completed_at": row["completed_at"],
            "failed_at": row["failed_at"],
            "offer_amount": float(row["offer_amount"]) if row["offer_amount"] is not None else None,
            "offer_amount_display": self._money_or_blank(row["offer_amount"]),
            "offer_currency": str(row["offer_currency"] or "USD"),
            "offer_text_raw": str(row["offer_text_raw"] or ""),
            "result_summary": str(row["result_summary"] or ""),
            "result_json": result_json,
            "screenshot_url_or_path": str(row["screenshot_url_or_path"] or ""),
            "page_text_capture": str(row["page_text_capture"] or ""),
            "error_message": str(row["error_message"] or ""),
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }

    def _safe_json_loads(self, value: Any) -> dict[str, Any]:
        if not value:
            return {}
        try:
            parsed = json.loads(str(value))
        except Exception:
            return {}
        return parsed if isinstance(parsed, dict) else {}

    def _money_or_blank(self, value: Any) -> str:
        try:
            if value in (None, ""):
                return ""
            amount = float(value)
        except (TypeError, ValueError):
            return ""
        return "${:,.0f}".format(amount)

    def _display_vehicle_title(self, fallback: str, vehicle_input: str, snapshot_payload: dict[str, Any]) -> str:
        front = snapshot_payload.get("front_evaluation") or {}
        parsed = front.get("parsed_details") or {}
        parts = [
            parsed.get("year"),
            parsed.get("make"),
            parsed.get("model"),
            self._clean_trim(parsed.get("trim")),
        ]
        base = " ".join(str(part).strip() for part in parts if part).strip()
        return base or fallback

    def _normalize_saved_snapshot(self, vehicle_input: str, snapshot_payload: dict[str, Any]) -> dict[str, Any]:
        normalized = copy.deepcopy(snapshot_payload or {})
        front = normalized.get("front_evaluation")
        if not isinstance(front, dict):
            return normalized

        parsed = dict(front.get("parsed_details") or {})
        lookup_input = str(vehicle_input or parsed.get("vehicle_input") or "").strip()
        if lookup_input:
            reparsed = parse_vehicle_query({"vehicle_input": lookup_input})
            reparsed_payload = reparsed.as_dict()
            reparsed_payload["vehicle_input"] = reparsed_payload.pop("raw_input", lookup_input)
            for key, value in reparsed_payload.items():
                if value in ("", None, [], {}):
                    continue
                if key.startswith("manual_") or key == "custom_listings":
                    continue
                parsed[key] = value
        elif parsed.get("vehicle_input"):
            lookup_input = str(parsed.get("vehicle_input") or "").strip()

        if lookup_input:
            parsed["vehicle_input"] = lookup_input

        front["parsed_details"] = parsed
        front["vehicle_summary"] = self._summary_from_parsed(parsed, front.get("vehicle_summary", ""))

        full = normalized.get("full_evaluation")
        if isinstance(full, dict) and front.get("vehicle_summary"):
            full["vehicle_summary"] = front["vehicle_summary"]

        return normalized

    def _normalize_saved_preview(
        self,
        preview_payload: dict[str, Any],
        snapshot_payload: dict[str, Any],
    ) -> dict[str, Any]:
        preview = dict(preview_payload or {})
        front = snapshot_payload.get("front_evaluation") or {}
        full = snapshot_payload.get("full_evaluation") or {}

        comparable_count = front.get("comparable_count")
        if comparable_count and not preview.get("comparable_count"):
            preview["comparable_count"] = f"{comparable_count} comps"

        if full.get("final_buy_price") and not preview.get("final_buy_price"):
            preview["final_buy_price"] = full.get("final_buy_price", "")

        suggested_buy_price = full.get("suggested_buy_price") or front.get("recommended_max_buy_price") or ""
        if suggested_buy_price and not preview.get("suggested_buy_price"):
            preview["suggested_buy_price"] = suggested_buy_price

        expected_resale_range = full.get("expected_resale_range") or ""
        if not expected_resale_range:
            resale_range = front.get("recommended_target_resale_range") or {}
            if resale_range.get("low") and resale_range.get("high"):
                expected_resale_range = (
                    resale_range["low"]
                    if resale_range["low"] == resale_range["high"]
                    else f"{resale_range['low']} - {resale_range['high']}"
                )
        if expected_resale_range and not preview.get("expected_resale_range"):
            preview["expected_resale_range"] = expected_resale_range

        confidence = full.get("confidence") or ""
        if not confidence and front.get("confidence_score") is not None:
            confidence = f"{int(front.get('confidence_score') or 0)}%"
        if confidence and not preview.get("confidence"):
            preview["confidence"] = confidence

        risk = full.get("risk") or ""
        if risk and not preview.get("risk"):
            preview["risk"] = risk

        nearby_mileage = front.get("average_price_near_mileage") or {}
        if nearby_mileage.get("value") and not preview.get("average_price_near_mileage"):
            preview["average_price_near_mileage"] = nearby_mileage.get("value", "")
        elif nearby_mileage.get("message") and not preview.get("average_price_near_mileage"):
            preview["average_price_near_mileage"] = nearby_mileage.get("message", "")

        return preview

    def _summary_from_parsed(self, parsed: dict[str, Any], fallback: str) -> str:
        summary = " ".join(
            str(part).strip()
            for part in [
                parsed.get("year"),
                parsed.get("make"),
                parsed.get("model"),
                self._clean_trim(parsed.get("trim")),
            ]
            if part
        ).strip()
        mileage = parsed.get("mileage")
        if mileage:
            summary = f"{summary} ({int(mileage):,} miles)".strip()
        return summary or fallback

    def _clean_trim(self, value: Any) -> str:
        text = str(value or "").strip()
        if not text:
            return ""
        text = re.split(r"\s[-|]\s|•|\u00b7|\(", text, maxsplit=1)[0].strip()
        text = re.sub(
            r"\b(all wheel drive|awd|fwd|rwd|quattro|xdrive|clean|new tires?|carplay|tint(?:ed)?|windows?)\b.*",
            "",
            text,
            flags=re.I,
        ).strip()
        text = re.sub(r"\b(sedan|coupe|hatchback|wagon|convertible|suv|truck|4d|4dr|4-door|4 door)\b.*", "", text, flags=re.I).strip()
        tokens = [token for token in text.split() if token]
        if len(tokens) > 3:
            tokens = tokens[:3]
        return " ".join(tokens).strip()
