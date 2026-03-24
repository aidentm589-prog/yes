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
FINAL_BUY_ADDON_COST = 1
FREE_TIER_REFILL_HOURS = 24

DEFAULT_TIER_RULES = {
    1: {
        "label": "Tier 1",
        "default_credits": 1,
        "has_bulk_access": False,
        "has_addon_access": False,
        "is_unlimited": False,
        "monthly_price": "$0",
        "yearly_price": "$0",
        "marketing_copy": "One individual evaluation every 24 hours.",
    },
    2: {
        "label": "Tier 2",
        "default_credits": 50,
        "has_bulk_access": True,
        "has_addon_access": True,
        "is_unlimited": False,
        "monthly_price": "$29",
        "yearly_price": "$290",
        "marketing_copy": "Batch model access and 50 credits for active scouting.",
    },
    3: {
        "label": "Tier 3",
        "default_credits": 500,
        "has_bulk_access": True,
        "has_addon_access": True,
        "is_unlimited": False,
        "monthly_price": "$99",
        "yearly_price": "$990",
        "marketing_copy": "High-volume flips with 500 credits and faster decision flow.",
    },
    4: {
        "label": "Tier 4",
        "default_credits": 0,
        "has_bulk_access": True,
        "has_addon_access": True,
        "is_unlimited": True,
        "monthly_price": "$249",
        "yearly_price": "$2,490",
        "marketing_copy": "Unlimited usage for operators and partners.",
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
        self.ensure_subscription_tiers()
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
        rule = self.tier_rule(tier)
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
        user = self._sync_user_entitlements(user)
        return self.refill_free_tier_credit_if_eligible(user)

    def get_user_subscription_status(self, user_id: int | None) -> dict[str, Any] | None:
        user = self.get_user_by_id(user_id)
        if not user:
            return None
        return self.serialize_account_status(user)

    def serialize_account_status(self, user: dict[str, Any]) -> dict[str, Any]:
        rule = self.tier_rule(int(user["tier"]))
        is_admin_access = self.is_admin_user(user)
        tier_label = "ADMIN" if is_admin_access else rule["label"]
        permissions = []
        if user.get("is_unlimited"):
            permissions.append("Unlimited evaluations")
        else:
            permissions.append(f'{user.get("credit_balance", 0)} credit{"s" if user.get("credit_balance", 0) != 1 else ""}')
        permissions.append("Bulk enabled" if user.get("has_bulk_access") else "Bulk blocked")
        permissions.append("Add-ons enabled" if self.tier_rule(int(user["tier"])).get("has_addon_access") else "Add-ons blocked")
        if is_admin_access:
            permissions.append("Admin access")
        return {
            "id": user["id"],
            "first_name": str(user.get("first_name") or ""),
            "email": user["email"],
            "role": user["role"],
            "tier": user["tier"],
            "tier_label": tier_label,
            "tier_name": tier_label,
            "credit_balance": user["credit_balance"],
            "credits_label": "Unlimited" if user.get("is_unlimited") else str(user.get("credit_balance", 0)),
            "has_bulk_access": bool(user.get("has_bulk_access")),
            "has_addon_access": bool(rule.get("has_addon_access")),
            "is_unlimited": bool(user.get("is_unlimited")),
            "monthly_price": rule.get("monthly_price", ""),
            "yearly_price": rule.get("yearly_price", ""),
            "marketing_copy": rule.get("marketing_copy", ""),
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
            user = self._sync_user_entitlements(user)
            current = self.refill_free_tier_credit_if_eligible(user)
            users.append(self.serialize_account_status(current))
        return users

    def list_subscription_tiers(self) -> list[dict[str, Any]]:
        self.ensure_subscription_tiers()
        return self.repository.list_subscription_tiers()

    def get_public_subscription_tiers(self) -> list[dict[str, Any]]:
        tiers = []
        for item in self.list_subscription_tiers():
            tier = {
                **item,
                "is_free": int(item.get("tier") or 0) == 1,
                "cta_label": "Current Free Access" if int(item.get("tier") or 0) == 1 else "Choose This Plan",
            }
            tiers.append(tier)
        return tiers

    def update_subscription_tier(self, tier: int, payload: dict[str, Any]) -> dict[str, Any]:
        current = self.tier_rule(tier)
        display_name = str(payload.get("display_name") or current["label"]).strip() or current["label"]
        credits_granted = max(0, int(payload.get("credits_granted", current["default_credits"])))
        monthly_price = str(payload.get("monthly_price") or current.get("monthly_price") or "").strip()
        yearly_price = str(payload.get("yearly_price") or current.get("yearly_price") or "").strip()
        marketing_copy = str(payload.get("marketing_copy") or current.get("marketing_copy") or "").strip()
        has_bulk_access = bool(payload.get("has_bulk_access", current["has_bulk_access"]))
        has_addon_access = bool(payload.get("has_addon_access", current["has_addon_access"]))
        is_unlimited = bool(payload.get("is_unlimited", current["is_unlimited"]))
        return self.repository.upsert_subscription_tier(
            tier=tier,
            display_name=display_name,
            credits_granted=credits_granted,
            monthly_price=monthly_price,
            yearly_price=yearly_price,
            marketing_copy=marketing_copy,
            has_bulk_access=has_bulk_access,
            has_addon_access=has_addon_access,
            is_unlimited=is_unlimited,
        )

    def update_user_tier(self, user_id: int, tier: int, credit_balance: int | None = None) -> dict[str, Any] | None:
        tier = int(tier)
        if tier not in {1, 2, 3, 4}:
            raise ValueError("Invalid tier selected.")
        rule = self.tier_rule(tier)
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

    def assign_admin_subscription(self, user_id: int) -> dict[str, Any] | None:
        updated = self.repository.update_user_account(
            user_id,
            role="admin",
            tier=4,
            credit_balance=0,
            has_bulk_access=True,
            is_unlimited=True,
            status="active",
        )
        return self.get_user_subscription_status(user_id) if updated else None

    def update_user_credits(self, user_id: int, credit_balance: int) -> dict[str, Any] | None:
        updated = self.repository.update_user_account(user_id, credit_balance=max(0, int(credit_balance)))
        return self.get_user_subscription_status(user_id) if updated else None

    def update_user_profile(self, user_id: int, first_name: str) -> dict[str, Any] | None:
        first_name = str(first_name or "").strip()
        if len(first_name) < 2:
            raise ValueError("Enter a valid first name.")
        updated = self.repository.update_user_account(user_id, first_name=first_name)
        return self.get_user_subscription_status(user_id) if updated else None

    def build_final_buy_offer(self, user_id: int | None, evaluation: dict[str, Any]) -> dict[str, Any]:
        decision = self.authorize_final_buy_calculation(user_id)
        if not decision.allowed:
            raise ValueError(decision.message or "This premium buy calculation is unavailable.")

        safe_buy = self._money_to_float(evaluation.get("recommended_max_buy_price"))
        average_near = self._money_to_float((evaluation.get("average_price_near_mileage") or {}).get("value"))
        market_value = self._money_to_float((evaluation.get("overall_range") or {}).get("market_value"))
        resale_range = evaluation.get("recommended_target_resale_range") or {}
        resale_low = self._money_to_float(resale_range.get("low"))
        resale_high = self._money_to_float(resale_range.get("high"))
        confidence = float(evaluation.get("confidence_score") or 0.0)
        title_adjustment = evaluation.get("title_adjustment") or {}
        title_average = self._money_to_float(title_adjustment.get("rebuilt_title_average"))

        anchor_candidates = [value for value in (safe_buy, average_near, market_value, title_average) if value and value > 0]
        if not anchor_candidates:
            raise ValueError("A premium buy target is unavailable for this evaluation.")

        anchor = min(anchor_candidates)
        resale_anchor = min(
            [value for value in (resale_low, resale_high, market_value) if value and value > 0] or [anchor]
        )
        confidence_factor = max(0.82, min(0.96, 0.90 - ((confidence - 60.0) / 400.0)))
        target_floor = min(anchor * 0.92, resale_anchor * 0.68)
        lowest_buy_point_value = max(0.0, min(anchor, target_floor) * confidence_factor)
        starting_offer_value = max(0.0, lowest_buy_point_value * 0.90)

        lowest_buy_point = self._round_money(lowest_buy_point_value)
        starting_offer = min(lowest_buy_point, self._round_money(starting_offer_value))
        self.consume_credits(user_id, FINAL_BUY_ADDON_COST)
        return {
            "starting_offer": self._format_money(starting_offer),
            "lowest_buy_point": self._format_money(lowest_buy_point),
            "account_status": self.get_user_subscription_status(user_id),
        }

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
        if not self.tier_rule(int(user["tier"])).get("has_addon_access"):
            return PermissionDecision(
                allowed=False,
                message="Your current tier does not include juicy add-ons yet.",
                status_code=403,
                user=user,
            )
        decision.user = self.get_user_by_id(user["id"]) or user
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
        decision.user = self.get_user_by_id(user["id"]) or user
        return decision

    def authorize_final_buy_calculation(self, user_id: int | None) -> PermissionDecision:
        user = self.get_user_by_id(user_id)
        if not user:
            return PermissionDecision(
                allowed=False,
                message="Please log in to calculate a premium buy target.",
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
            FINAL_BUY_ADDON_COST,
            "You need 1 available credit to run this premium buy calculation.",
        )
        if not self.tier_rule(int(user["tier"])).get("has_addon_access"):
            return PermissionDecision(
                allowed=False,
                message="Your current tier does not include juicy add-ons yet.",
                status_code=403,
                user=user,
            )
        decision.user = self.get_user_by_id(user["id"]) or user
        return decision

    def consume_credits(self, user_id: int | None, cost: int) -> dict[str, Any] | None:
        if not user_id or cost <= 0:
            return self.get_user_by_id(user_id)
        user = self.get_user_by_id(user_id)
        if not user:
            return None
        if user.get("is_unlimited"):
            return user
        updated_balance = max(0, int(user["credit_balance"]) - cost)
        self.repository.update_user_account(user["id"], credit_balance=updated_balance)
        return self.get_user_by_id(user["id"])

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

    def ensure_subscription_tiers(self) -> None:
        existing = {item["tier"]: item for item in self.repository.list_subscription_tiers()}
        for tier, rule in DEFAULT_TIER_RULES.items():
            if tier in existing:
                continue
            self.repository.upsert_subscription_tier(
                tier=tier,
                display_name=rule["label"],
                credits_granted=rule["default_credits"],
                monthly_price=rule["monthly_price"],
                yearly_price=rule["yearly_price"],
                marketing_copy=rule["marketing_copy"],
                has_bulk_access=rule["has_bulk_access"],
                has_addon_access=rule["has_addon_access"],
                is_unlimited=rule["is_unlimited"],
            )

    def tier_rule(self, tier: int) -> dict[str, Any]:
        persisted = self.repository.get_subscription_tier(int(tier))
        if persisted:
            return {
                "label": persisted["display_name"],
                "default_credits": persisted["credits_granted"],
                "has_bulk_access": persisted["has_bulk_access"],
                "has_addon_access": persisted.get("has_addon_access", False),
                "is_unlimited": persisted["is_unlimited"],
                "monthly_price": persisted["monthly_price"],
                "yearly_price": persisted["yearly_price"],
                "marketing_copy": persisted["marketing_copy"],
            }
        default = DEFAULT_TIER_RULES.get(int(tier), DEFAULT_TIER_RULES[1])
        return {
            "label": default["label"],
            "default_credits": default["default_credits"],
            "has_bulk_access": default["has_bulk_access"],
            "has_addon_access": default["has_addon_access"],
            "is_unlimited": default["is_unlimited"],
            "monthly_price": default["monthly_price"],
            "yearly_price": default["yearly_price"],
            "marketing_copy": default["marketing_copy"],
        }

    def _sync_user_entitlements(self, user: dict[str, Any]) -> dict[str, Any]:
        rule = self.tier_rule(int(user.get("tier") or 1))
        needs_update = (
            bool(user.get("has_bulk_access")) != bool(rule["has_bulk_access"])
            or bool(user.get("is_unlimited")) != bool(rule["is_unlimited"])
        )
        if not needs_update:
            return user
        self.repository.update_user_account(
            int(user["id"]),
            has_bulk_access=rule["has_bulk_access"],
            is_unlimited=rule["is_unlimited"],
        )
        refreshed = self.repository.get_user_by_id(int(user["id"]))
        return refreshed or user

    def tier_choices(self) -> list[dict[str, Any]]:
        return [
            {
                "tier": item["tier"],
                "label": item["display_name"],
                "credits_granted": item["credits_granted"],
                "monthly_price": item["monthly_price"],
                "yearly_price": item["yearly_price"],
                "marketing_copy": item["marketing_copy"],
                "has_bulk_access": item["has_bulk_access"],
                "has_addon_access": item.get("has_addon_access", False),
                "is_unlimited": item["is_unlimited"],
            }
            for item in self.list_subscription_tiers()
        ]

    def _permission_for_mode(self, user: dict[str, Any], mode: str, payload: dict[str, Any] | None = None) -> PermissionDecision:
        payload = payload or {}
        cost = BULK_COST if mode == "bulk" else INDIVIDUAL_COST
        if self._detailed_report_enabled(payload):
            if not self.tier_rule(int(user["tier"])).get("has_addon_access"):
                return PermissionDecision(
                    allowed=False,
                    message="Your current tier does not include juicy add-ons yet.",
                    status_code=403,
                    user=user,
                )
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

    def _money_to_float(self, value: Any) -> float | None:
        digits = "".join(ch for ch in str(value or "") if ch.isdigit() or ch in ".-")
        if not digits:
            return None
        try:
            parsed = float(digits)
        except ValueError:
            return None
        return parsed if parsed > 0 else None

    def _round_money(self, value: float) -> float:
        return max(0.0, round(value / 50.0) * 50.0)

    def _format_money(self, value: float) -> str:
        return "${:,.0f}".format(max(0.0, value))
