from __future__ import annotations

from typing import Any

from account_service import AccountService, PermissionDecision
from carvana_payout import CarvanaPayoutService
from comp_engine import VehicleCompsEngine
from software_chat import SoftwareChatService


class VehicleApiError(Exception):
    pass


class VehicleValueService:
    def __init__(self) -> None:
        self.engine = VehicleCompsEngine()
        self.accounts = AccountService(self.engine.repository)
        self.carvana_payout = CarvanaPayoutService(self.engine.repository)
        self.software_chat = SoftwareChatService()

    def run_condition_sweep(self, payload: dict[str, Any]) -> dict[str, Any]:
        try:
            return self.engine.evaluate(payload)
        except Exception as exc:  # noqa: BLE001
            raise VehicleApiError(str(exc)) from exc

    def save_evaluation(
        self,
        user_id: int | None,
        vehicle_title: str,
        vehicle_input: str,
        preview_payload: dict[str, Any],
        snapshot_payload: dict[str, Any],
    ) -> int:
        return self.engine.repository.save_evaluation(
            user_id=user_id,
            vehicle_title=vehicle_title,
            vehicle_input=vehicle_input,
            preview_payload=preview_payload,
            snapshot_payload=snapshot_payload,
        )

    def list_saved_evaluations(self, user_id: int | None = None) -> list[dict[str, Any]]:
        return self.engine.repository.list_saved_evaluations(user_id=user_id)

    def get_saved_evaluation(self, evaluation_id: int, user_id: int | None = None) -> dict[str, Any] | None:
        return self.engine.repository.get_saved_evaluation(evaluation_id, user_id=user_id)

    def update_saved_evaluation(
        self,
        evaluation_id: int,
        user_id: int | None,
        vehicle_title: str,
        preview_payload: dict[str, Any],
        snapshot_payload: dict[str, Any],
    ) -> bool:
        return self.engine.repository.update_saved_evaluation(
            evaluation_id=evaluation_id,
            user_id=user_id,
            vehicle_title=vehicle_title,
            preview_payload=preview_payload,
            snapshot_payload=snapshot_payload,
        )

    def delete_saved_evaluation(self, evaluation_id: int, user_id: int | None = None) -> bool:
        return self.engine.repository.delete_saved_evaluation(evaluation_id, user_id=user_id)

    def admin_overview(self) -> dict[str, Any]:
        return self.engine.admin_overview()

    def software_chat_reply(self, messages: list[dict[str, Any]]) -> dict[str, Any]:
        try:
            return self.software_chat.reply(messages)
        except Exception as exc:  # noqa: BLE001
            raise VehicleApiError(str(exc)) from exc

    def create_user_account(self, first_name: str, email: str, password: str) -> dict[str, Any]:
        try:
            return self.accounts.create_user_account(first_name, email, password)
        except Exception as exc:  # noqa: BLE001
            raise VehicleApiError(str(exc)) from exc

    def login_user(self, email: str, password: str) -> dict[str, Any]:
        try:
            return self.accounts.login_user(email, password)
        except Exception as exc:  # noqa: BLE001
            raise VehicleApiError(str(exc)) from exc

    def get_user(self, user_id: int | None) -> dict[str, Any] | None:
        return self.accounts.get_user_by_id(user_id)

    def get_account_status(self, user_id: int | None) -> dict[str, Any] | None:
        return self.accounts.get_user_subscription_status(user_id)

    def consume_credits(self, user_id: int | None, cost: int) -> dict[str, Any] | None:
        return self.accounts.consume_credits(user_id, cost)

    def authorize_evaluation_start(self, user_id: int | None, mode: str, payload: dict[str, Any]) -> PermissionDecision:
        return self.accounts.authorize_evaluation_start(user_id, mode, payload)

    def authorize_carvana_payout_start(self, user_id: int | None) -> PermissionDecision:
        return self.accounts.authorize_carvana_payout_start(user_id)

    def list_users(self) -> list[dict[str, Any]]:
        return self.accounts.list_users()

    def list_subscription_tiers(self) -> list[dict[str, Any]]:
        return self.accounts.list_subscription_tiers()

    def list_public_subscription_tiers(self) -> list[dict[str, Any]]:
        return self.accounts.get_public_subscription_tiers()

    def update_subscription_tier(self, tier: int, payload: dict[str, Any]) -> dict[str, Any]:
        try:
            return self.accounts.update_subscription_tier(tier, payload)
        except Exception as exc:  # noqa: BLE001
            raise VehicleApiError(str(exc)) from exc

    def update_user_tier(self, user_id: int, tier: int, credit_balance: int | None = None) -> dict[str, Any] | None:
        try:
            return self.accounts.update_user_tier(user_id, tier, credit_balance)
        except Exception as exc:  # noqa: BLE001
            raise VehicleApiError(str(exc)) from exc

    def update_user_credits(self, user_id: int, credit_balance: int) -> dict[str, Any] | None:
        try:
            return self.accounts.update_user_credits(user_id, credit_balance)
        except Exception as exc:  # noqa: BLE001
            raise VehicleApiError(str(exc)) from exc

    def update_user_profile(self, user_id: int, first_name: str) -> dict[str, Any] | None:
        try:
            return self.accounts.update_user_profile(user_id, first_name)
        except Exception as exc:  # noqa: BLE001
            raise VehicleApiError(str(exc)) from exc

    def update_user_role(self, user_id: int, role: str, actor_user_id: int | None = None) -> dict[str, Any] | None:
        try:
            return self.accounts.update_user_role(user_id, role, actor_user_id=actor_user_id)
        except Exception as exc:  # noqa: BLE001
            raise VehicleApiError(str(exc)) from exc

    def update_user_status(self, user_id: int, status: str, actor_user_id: int | None = None) -> dict[str, Any] | None:
        try:
            return self.accounts.update_user_status(user_id, status, actor_user_id=actor_user_id)
        except Exception as exc:  # noqa: BLE001
            raise VehicleApiError(str(exc)) from exc

    def delete_user_account(self, user_id: int, actor_user_id: int | None = None) -> bool:
        try:
            return self.accounts.delete_user_account(user_id, actor_user_id=actor_user_id)
        except Exception as exc:  # noqa: BLE001
            raise VehicleApiError(str(exc)) from exc

    def is_admin_user(self, user: dict[str, Any] | None) -> bool:
        return self.accounts.is_admin_user(user)

    def test_admin_credentials(self) -> dict[str, str]:
        return {
            "email": self.accounts.test_admin_email,
            "password": self.accounts.test_admin_password,
        }

    def ensure_background_workers(self) -> None:
        self.carvana_payout.start_worker()

    def create_carvana_payout_job(self, user_id: int, payload: dict[str, Any]) -> dict[str, Any]:
        try:
            return self.carvana_payout.create_carvana_payout_job(user_id, payload)
        except Exception as exc:  # noqa: BLE001
            raise VehicleApiError(str(exc)) from exc

    def validate_carvana_payout_payload(self, payload: dict[str, Any]) -> dict[str, Any]:
        try:
            return self.carvana_payout.validate_carvana_payout_payload(payload)
        except Exception as exc:  # noqa: BLE001
            raise VehicleApiError(str(exc)) from exc

    def get_carvana_payout_job(self, job_id: int, user_id: int | None = None) -> dict[str, Any] | None:
        return self.carvana_payout.get_carvana_payout_job(job_id, user_id=user_id)

    def list_carvana_payout_jobs(self, user_id: int | None = None, limit: int = 15) -> list[dict[str, Any]]:
        return self.carvana_payout.list_carvana_payout_jobs(user_id=user_id, limit=limit)

    def retry_carvana_payout_job(self, job_id: int, user_id: int | None = None) -> dict[str, Any] | None:
        try:
            return self.carvana_payout.retry_carvana_payout_job(job_id, user_id=user_id)
        except Exception as exc:  # noqa: BLE001
            raise VehicleApiError(str(exc)) from exc

    def build_final_buy_offer(self, user_id: int | None, evaluation: dict[str, Any]) -> dict[str, Any]:
        try:
            return self.accounts.build_final_buy_offer(user_id, evaluation)
        except Exception as exc:  # noqa: BLE001
            raise VehicleApiError(str(exc)) from exc
