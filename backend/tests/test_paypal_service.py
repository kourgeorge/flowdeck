from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
import sys
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services.paypal_service import execute_payment


class _FakePayment:
    def __init__(self, custom: str) -> None:
        self.transactions = [
            SimpleNamespace(custom=custom, amount=SimpleNamespace(total="9.00"))
        ]
        self.executed_with = None

    def execute(self, payload: dict) -> bool:
        self.executed_with = payload
        return True


class TestPaypalService(unittest.TestCase):
    def test_execute_payment_rejects_authenticated_user_mismatch_before_capture(self) -> None:
        payment = _FakePayment("1:popular:1000")
        db = Mock()

        with patch("services.paypal_service.paypalrestsdk.Payment.find", return_value=payment), patch(
            "services.paypal_service.token_service.top_up"
        ) as top_up:
            with self.assertRaises(PermissionError):
                execute_payment("PAY-1", "PAYER-1", current_user_id=2, db=db)

        self.assertIsNone(payment.executed_with)
        top_up.assert_not_called()

    def test_execute_payment_credits_authenticated_owner_after_capture(self) -> None:
        payment = _FakePayment("1:popular:1000")
        db = Mock()

        with patch("services.paypal_service.paypalrestsdk.Payment.find", return_value=payment), patch(
            "services.paypal_service.token_service.top_up",
            return_value=True,
        ) as top_up:
            result = execute_payment("PAY-1", "PAYER-1", current_user_id=1, db=db)

        self.assertEqual(payment.executed_with, {"payer_id": "PAYER-1"})
        top_up.assert_called_once_with(
            1,
            1000,
            db,
            metadata={"package_id": "popular", "payment_id": "PAY-1"},
        )
        self.assertEqual(result["tokens_credited"], 1000)


if __name__ == "__main__":
    unittest.main()
