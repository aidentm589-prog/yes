from __future__ import annotations

import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from account_service import AccountService
from comp_engine.storage import SQLiteRepository


class AccountServiceTests(unittest.TestCase):
    def create_service(self) -> AccountService:
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)
        repository = SQLiteRepository(Path(temp_dir.name) / "accounts.db")
        return AccountService(repository)

    def test_signup_creates_free_tier_account(self) -> None:
        service = self.create_service()
        user = service.create_user_account("Aiden", "friend@example.com", "password123")

        self.assertEqual(user["first_name"], "Aiden")
        self.assertEqual(user["tier"], 1)
        self.assertEqual(user["credit_balance"], 1)
        self.assertFalse(user["has_bulk_access"])
        self.assertFalse(user["is_unlimited"])

    def test_tier_one_consumes_one_credit_and_blocks_bulk(self) -> None:
        service = self.create_service()
        user = service.create_user_account("Tier", "tier1@example.com", "password123")
        payload = {"vehicle_input": "2014 audi a4 105000 miles"}

        first = service.authorize_evaluation_start(user["id"], "individual", payload)
        service.consume_credits(user["id"], first.cost)
        second = service.authorize_evaluation_start(user["id"], "individual", payload)
        bulk = service.authorize_evaluation_start(
            user["id"],
            "bulk",
            {"vehicle_input": "$4,995\n2014 Audi A4 Premium Plus\nBoston, MA\n105K miles"},
        )

        self.assertTrue(first.allowed)
        self.assertEqual(first.cost, 1)
        self.assertFalse(second.allowed)
        self.assertEqual(second.status_code, 403)
        self.assertIn("1 available credit", second.message)
        self.assertFalse(bulk.allowed)
        self.assertIn("does not include Bulk Evaluation", bulk.message)

    def test_free_tier_refills_after_24_hours_without_accumulating(self) -> None:
        service = self.create_service()
        user = service.create_user_account("Refill", "refill@example.com", "password123")
        decision = service.authorize_evaluation_start(user["id"], "individual", {"vehicle_input": "2014 audi a4 105000 miles"})
        service.consume_credits(user["id"], decision.cost)

        old_time = (datetime.now(timezone.utc) - timedelta(hours=25)).isoformat()
        service.repository.update_user_account(
            user["id"],
            credit_balance=0,
            last_free_credit_at=old_time,
        )

        refreshed = service.get_user_by_id(user["id"])

        self.assertIsNotNone(refreshed)
        self.assertEqual(refreshed["credit_balance"], 1)

    def test_higher_tiers_get_expected_credits_and_permissions(self) -> None:
        service = self.create_service()
        user = service.create_user_account("Tiered", "tiered@example.com", "password123")

        tier2 = service.update_user_tier(user["id"], 2)
        tier3 = service.update_user_tier(user["id"], 3)
        tier4 = service.update_user_tier(user["id"], 4)

        self.assertEqual(tier2["credit_balance"], 50)
        self.assertTrue(tier2["has_bulk_access"])
        self.assertEqual(tier3["credit_balance"], 500)
        self.assertTrue(tier3["has_bulk_access"])
        self.assertTrue(tier4["is_unlimited"])

    def test_bulk_consumes_five_credits_for_paid_tiers(self) -> None:
        service = self.create_service()
        user = service.create_user_account("Bulk", "bulk@example.com", "password123")
        service.update_user_tier(user["id"], 2)

        decision = service.authorize_evaluation_start(
            user["id"],
            "bulk",
            {"vehicle_input": "$4,995\n2014 Audi A4 Premium Plus\nBoston, MA\n105K miles"},
        )
        service.consume_credits(user["id"], decision.cost)
        updated = service.get_user_by_id(user["id"])

        self.assertTrue(decision.allowed)
        self.assertEqual(decision.cost, 5)
        self.assertEqual(updated["credit_balance"], 45)

    def test_subscription_tier_updates_change_live_defaults(self) -> None:
        service = self.create_service()
        service.update_subscription_tier(2, {
            "display_name": "Scout Plus",
            "credits_granted": 88,
            "monthly_price": "$44",
            "yearly_price": "$440",
            "marketing_copy": "Updated live",
            "has_bulk_access": True,
            "is_unlimited": False,
        })
        user = service.create_user_account("Live", "live@example.com", "password123")
        upgraded = service.update_user_tier(user["id"], 2)

        self.assertEqual(upgraded["tier_label"], "Scout Plus")
        self.assertEqual(upgraded["credit_balance"], 88)

    def test_final_buy_add_on_consumes_one_credit_on_success(self) -> None:
        service = self.create_service()
        user = service.create_user_account("Closer", "closer@example.com", "password123")
        service.update_user_tier(user["id"], 2)

        result = service.build_final_buy_offer(user["id"], {
            "recommended_max_buy_price": "$10,000",
            "overall_range": {"market_value": "$12,000"},
            "average_price_near_mileage": {"value": "$11,000"},
            "recommended_target_resale_range": {"low": "$11,500", "high": "$12,500"},
            "confidence_score": 72,
        })
        refreshed = service.get_user_by_id(user["id"])

        self.assertIn("starting_offer", result)
        self.assertIn("lowest_buy_point", result)
        self.assertEqual(refreshed["credit_balance"], 49)

    def test_admin_can_ban_client_account(self) -> None:
        service = self.create_service()
        user = service.create_user_account("Ban", "banme@example.com", "password123")

        updated = service.update_user_status(user["id"], "banned", actor_user_id=999)

        self.assertIsNotNone(updated)
        self.assertEqual(updated["status"], "banned")

    def test_admin_can_delete_client_account(self) -> None:
        service = self.create_service()
        user = service.create_user_account("Delete", "deleteme@example.com", "password123")

        deleted = service.delete_user_account(user["id"], actor_user_id=999)

        self.assertTrue(deleted)
        self.assertIsNone(service.get_user_by_id(user["id"]))

    def test_admin_can_grant_and_remove_admin_role(self) -> None:
        service = self.create_service()
        user = service.create_user_account("Partner", "partner@example.com", "password123")

        promoted = service.update_user_role(user["id"], "admin", actor_user_id=999)
        demoted = service.update_user_role(user["id"], "client", actor_user_id=999)

        self.assertIsNotNone(promoted)
        self.assertEqual(promoted["role"], "admin")
        self.assertIsNotNone(demoted)
        self.assertEqual(demoted["role"], "client")


if __name__ == "__main__":
    unittest.main()
