from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

from werkzeug.security import check_password_hash, generate_password_hash

from comp_engine.bulk_parser import parse_bulk_vehicle_text
from comp_engine.query_parser import parse_vehicle_query
from comp_engine.storage import SQLiteRepository


INDIVIDUAL_COST = 1
BULK_COST = 5
DETAILED_REPORT_COST = 1
CARVANA_PAYOUT_COST = 1
FREE_TIER_REFILL_HOURS = 24

TIER_RULES = {
    1: {
        "label": "Tier 1",
        "default_credits": 1,
        "has_bulk_access": False,
        "is_unlimited": False,
    },
    2: {
        "label": "Tier 2",
        "default_credits": 25,
        "has_bulk_access": True,
        "is_unlimited": False,
    },
    3: {
        "label": "Tier 3",
        "default_credits": 500,
        "has_bulk_access": True,
        "is_unlimited": False,
    },
    4: {
        "label": "Tier 4",
        "default_credits": 0,
        "has_bulk_access": True,
        "is_unlimited": True,
    },
}


@dataclass(slots=True)
class PermissionDecision:
    allowed: bool
    message: str = ""
    cost: int = 0
    status_code: int = 200
    user: dict[str, Any] | None = None


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _utc_now_iso() -> str:
    return _utc_now().isoformat()


class AccountService:
    def __init__(self, repository: SQLiteRepository) -> None:
        self.repository = repository
        self.test_admin_email = os.getenv("TEST_ADMIN_EMAIL", "admin@carflip.local").strip().lower()
        self.test_admin_password = os.getenv("TEST_ADMIN_PASSWORD", "admin12345").strip()
        self.ensure_test_admin()

    def normalize_email(self, email: str) -> str:
        return str(email or "").strip().lower()

    def create_user_account(self, first_name: str, email: str, password: str) -> dict[str, Any]:
        first_name = str(first_name or "").strip()
        email = self.normalize_email(email)
        if len(first_name) < 2:
            raise ValueError("Enter your first name.")
        if not email or "@" not in email:
            raise ValueError("Enter a valid email address.")
        if len(password or "") < 8:
            raise ValueError("Password must be at least 8 characters.")
        if self.repository.get_user_by_email(email):
            raise ValueError("An account with that email already exists.")
        tier = 1
        rule = TIER_RULES[tier]
        last_free_credit_at = _utc_now_iso()
        user_id = self.repository.create_user_account(
            first_name=first_name,
            email=email,
            password_hash=generate_password_hash(password),
            role="client",
            tier=tier,
            credit_balance=rule["default_credits"],
            has_bulk_access=rule["has_bulk_access"],
            is_unlimited=rule["is_unlimited"],
            status="active",
            last_free_credit_at=last_free_credit_at,
            last_login_at=_utc_now_iso(),
        )
        return self.get_user_by_id(user_id) or {}

    def login_user(self, email: str, password: str) -> dict[str, Any]:
        email = self.normalize_email(email)
        user = self.repository.get_user_by_email(email)
        if not user or not check_password_hash(user["password_hash"], password or ""):
            raise ValueError("Invalid email or password.")
        self.repository.update_user_account(user["id"], last_login_at=_utc_now_iso())
        return self.get_user_by_id(user["id"]) or {}

    def get_user_by_id(self, user_id: int | None) -> dict[str, Any] | None:
        if not user_id:
            return None
        user = self.repository.get_user_by_id(int(user_id))
        if not user:
            return None
        return self.refill_free_tier_credit_if_eligible(user)

    def get_user_subscription_status(self, user_id: int | None) -> dict[str, Any] | None:
        user = self.get_user_by_id(user_id)
        if not user:
            return None
        return self.serialize_account_status(user)

    def serialize_account_status(self, user: dict[str, Any]) -> dict[str, Any]:
        permissions = []
        if user.get("is_unlimited"):
            permissions.append("Unlimited evaluations")
        else:
            permissions.append(f'{user.get("credit_balance", 0)} credit{"s" if user.get("credit_balance", 0) != 1 else ""}')
        permissions.append("Bulk enabled" if user.get("has_bulk_access") else "Bulk blocked")
        if self.is_admin_user(user):
            permissions.append("Admin access")
        return {
            "id": user["id"],
            "first_name": str(user.get("first_name") or ""),
            "email": user["email"],
            "role": user["role"],
            "tier": user["tier"],
            "tier_label": TIER_RULES.get(user["tier"], TIER_RULES[1])["label"],
            "credit_balance": user["credit_balance"],
            "credits_label": "Unlimited" if user.get("is_unlimited") else str(user.get("credit_balance", 0)),
            "has_bulk_access": bool(user.get("has_bulk_access")),
            "is_unlimited": bool(user.get("is_unlimited")),
            "created_at": user["created_at"],
            "updated_at": user["updated_at"],
            "last_free_credit_at": user.get("last_free_credit_at"),
            "last_login_at": user.get("last_login_at"),
            "status": user.get("status", "active"),
            "permissions_summary": " • ".join(permissions),
        }

    def list_users(self) -> list[dict[str, Any]]:
        users = []
        for user in self.repository.list_user_accounts():
            current = self.refill_free_tier_credit_if_eligible(user)
            users.append(self.serialize_account_status(current))
        return users

    def update_user_tier(self, user_id: int, tier: int, credit_balance: int | None = None) -> dict[str, Any] | None:
        tier = int(tier)
        if tier not in TIER_RULES:
            raise ValueError("Invalid tier selected.")
        rule = TIER_RULES[tier]
        update_fields: dict[str, Any] = {
            "tier": tier,
            "has_bulk_access": rule["has_bulk_access"],
            "is_unlimited": rule["is_unlimited"],
        }
        if credit_balance is None:
            update_fields["credit_balance"] = int(rule["default_credits"])
        else:
            update_fields["credit_balance"] = max(0, int(credit_balance))
        if tier == 1 and update_fields["credit_balance"] >= 1:
            update_fields["last_free_credit_at"] = _utc_now_iso()
        updated = self.repository.update_user_account(user_id, **update_fields)
        return self.get_user_subscription_status(user_id) if updated else None

    def update_user_credits(self, user_id: int, credit_balance: int) -> dict[str, Any] | None:
        updated = self.repository.update_user_account(user_id, credit_balance=max(0, int(credit_balance)))
        return self.get_user_subscription_status(user_id) if updated else None

    def update_user_role(self, target_user_id: int, role: str, actor_user_id: int | None = None) -> dict[str, Any] | None:
        user = self.repository.get_user_by_id(int(target_user_id))
        if not user:
            return None
        normalized_role = str(role or "").strip().lower()
        if normalized_role not in {"client", "admin"}:
            raise ValueError("Invalid role.")
        if actor_user_id and int(actor_user_id) == int(target_user_id):
            raise ValueError("You cannot change your own admin access.")
        if str(user.get("role") or "").strip().lower() == "test_admin":
            raise ValueError("Test admin access cannot be changed from the client list.")
        updated = self.repository.update_user_account(user["id"], role=normalized_role)
        return self.get_user_subscription_status(user["id"]) if updated else None

    def update_user_status(self, target_user_id: int, status: str, actor_user_id: int | None = None) -> dict[str, Any] | None:
        user = self.repository.get_user_by_id(int(target_user_id))
        if not user:
            return None
        if actor_user_id and int(actor_user_id) == int(target_user_id):
            raise ValueError("You cannot ban or reactivate your own account.")
        if self.is_admin_user(user):
            raise ValueError("Admin accounts cannot be banned from the client list.")
        normalized_status = str(status or "").strip().lower()
        if normalized_status not in {"active", "banned"}:
            raise ValueError("Invalid account status.")
        updated = self.repository.update_user_account(user["id"], status=normalized_status)
        return self.get_user_subscription_status(user["id"]) if updated else None

    def delete_user_account(self, target_user_id: int, actor_user_id: int | None = None) -> bool:
        user = self.repository.get_user_by_id(int(target_user_id))
        if not user:
            return False
        if actor_user_id and int(actor_user_id) == int(target_user_id):
            raise ValueError("You cannot delete your own account.")
        if self.is_admin_user(user):
            raise ValueError("Admin accounts cannot be deleted from the client list.")
        return self.repository.delete_user_account(user["id"])

    def is_admin_user(self, user: dict[str, Any] | None) -> bool:
        if not user:
            return False
        return str(user.get("role") or "").strip().lower() in {"admin", "test_admin"}

    def refill_free_tier_credit_if_eligible(self, user: dict[str, Any]) -> dict[str, Any]:
        if int(user.get("tier") or 0) != 1:
            return user
        current_balance = int(user.get("credit_balance") or 0)
        if current_balance >= 1:
            return user
        last_refill_raw = user.get("last_free_credit_at")
        if last_refill_raw:
            try:
                last_refill = datetime.fromisoformat(last_refill_raw)
            except ValueError:
                last_refill = _utc_now() - timedelta(hours=FREE_TIER_REFILL_HOURS + 1)
        else:
            last_refill = _utc_now() - timedelta(hours=FREE_TIER_REFILL_HOURS + 1)
        if _utc_now() - last_refill < timedelta(hours=FREE_TIER_REFILL_HOURS):
            return user
        self.repository.update_user_account(
            user["id"],
            credit_balance=1,
            last_free_credit_at=_utc_now_iso(),
        )
        refreshed = self.repository.get_user_by_id(user["id"])
        return refreshed or user

    def can_run_individual_evaluation(self, user: dict[str, Any], payload: dict[str, Any]) -> PermissionDecision:
        query = parse_vehicle_query(payload)
        if not query.minimum_details_present():
            return PermissionDecision(
                allowed=False,
                message="Please include the year, make, model, and mileage before running an evaluation.",
                status_code=400,
                user=user,
            )
        return self._permission_for_mode(user, "individual", payload)

    def can_run_bulk_evaluation(self, user: dict[str, Any], payload: dict[str, Any]) -> PermissionDecision:
        raw_text = str(payload.get("vehicle_input", "") or "").strip()
        parsed = parse_bulk_vehicle_text(raw_text)
        valid_entries = [entry for entry in parsed if entry.status == "parsed"]
        if not valid_entries:
            return PermissionDecision(
                allowed=False,
                message="Paste at least one vehicle with year, make, model, and mileage to run Bulk Evaluation.",
                status_code=400,
                user=user,
            )
        return self._permission_for_mode(user, "bulk", payload)

    def authorize_carvana_payout_start(self, user_id: int | None) -> PermissionDecision:
        user = self.get_user_by_id(user_id)
        if not user:
            return PermissionDecision(
                allowed=False,
                message="Please log in to use Carvana Payout.",
                status_code=401,
            )
        if str(user.get("status") or "").lower() != "active":
            return PermissionDecision(
                allowed=False,
                message="This account is not active.",
                status_code=403,
                user=user,
            )
        decision = self._permission_for_cost(
            user,
            CARVANA_PAYOUT_COST,
            "You need 1 available credit to run Carvana Payout.",
        )
        if not decision.allowed:
            decision.user = self.get_user_by_id(user["id"]) or user
            return decision
        if decision.cost > 0:
            updated_balance = max(0, int(user["credit_balance"]) - decision.cost)
            self.repository.update_user_account(user["id"], credit_balance=updated_balance)
            user = self.get_user_by_id(user["id"]) or user
        decision.user = user
        return decision

    def authorize_evaluation_start(self, user_id: int | None, mode: str, payload: dict[str, Any]) -> PermissionDecision:
        user = self.get_user_by_id(user_id)
        if not user:
            return PermissionDecision(
                allowed=False,
                message="Please log in to run evaluations.",
                status_code=401,
            )
        if str(user.get("status") or "").lower() != "active":
            return PermissionDecision(
                allowed=False,
                message="This account is not active.",
                status_code=403,
                user=user,
            )
        decision = self.can_run_bulk_evaluation(user, payload) if mode == "bulk" else self.can_run_individual_evaluation(user, payload)
        if not decision.allowed:
            decision.user = self.get_user_by_id(user["id"]) or user
            return decision
        if decision.cost > 0:
            updated_balance = max(0, int(user["credit_balance"]) - decision.cost)
            self.repository.update_user_account(user["id"], credit_balance=updated_balance)
            user = self.get_user_by_id(user["id"]) or user
        decision.user = user
        return decision

    def ensure_test_admin(self) -> None:
        existing = self.repository.get_user_by_email(self.test_admin_email)
        password_hash = generate_password_hash(self.test_admin_password)
        if not existing:
            self.repository.create_user_account(
                first_name="Admin",
                email=self.test_admin_email,
                password_hash=password_hash,
                role="test_admin",
                tier=4,
                credit_balance=0,
                has_bulk_access=True,
                is_unlimited=True,
                status="active",
                last_free_credit_at=None,
                last_login_at=None,
            )
            return
        self.repository.update_user_account(
            existing["id"],
            password_hash=password_hash,
            role="test_admin",
            tier=4,
            credit_balance=0,
            has_bulk_access=True,
            is_unlimited=True,
            status="active",
        )

    def _permission_for_mode(self, user: dict[str, Any], mode: str, payload: dict[str, Any] | None = None) -> PermissionDecision:
        payload = payload or {}
        cost = BULK_COST if mode == "bulk" else INDIVIDUAL_COST
        if self._detailed_report_enabled(payload):
            cost += DETAILED_REPORT_COST
        if mode == "bulk" and not user.get("has_bulk_access"):
            return PermissionDecision(
                allowed=False,
                message="Your current tier does not include Bulk Evaluation.",
                status_code=403,
                user=user,
            )
        if mode == "bulk":
            message = (
                "You need at least 5 credits for Bulk Evaluation"
                + (" plus 1 more credit for Detailed Vehicle Report." if self._detailed_report_enabled(payload) else ".")
            )
        else:
            message = (
                "You need 1 available credit for Individual Evaluation"
                + (" plus 1 more credit for Detailed Vehicle Report." if self._detailed_report_enabled(payload) else ".")
            )
        return self._permission_for_cost(user, cost, message)

    def _permission_for_cost(self, user: dict[str, Any], cost: int, insufficient_message: str) -> PermissionDecision:
        if user.get("is_unlimited"):
            return PermissionDecision(allowed=True, cost=0, user=user)
        credits = int(user.get("credit_balance") or 0)
        if credits < cost:
            return PermissionDecision(
                allowed=False,
                message=insufficient_message,
                status_code=403,
                user=user,
            )
        return PermissionDecision(allowed=True, cost=cost, user=user)

    def _detailed_report_enabled(self, payload: dict[str, Any]) -> bool:
        raw = str(payload.get("detailed_vehicle_report") or payload.get("include_detailed_vehicle_report") or "").strip().lower()
        return raw in {"1", "true", "yes", "on", "enabled"}
