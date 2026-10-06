"""Durable PayPal capture verification and idempotent token settlement."""

import os
from decimal import Decimal
from datetime import datetime, timedelta
from models.db_models import PaymentOrder, User
from sqlalchemy.exc import IntegrityError
import paypalrestsdk
from sqlalchemy.orm import Session
from services import token_service

# Get PayPal configuration
PAYPAL_MODE = os.environ.get("PAYPAL_MODE", "sandbox")
PAYPAL_CLIENT_ID = os.environ.get("PAYPAL_CLIENT_ID")
PAYPAL_CLIENT_SECRET = os.environ.get("PAYPAL_CLIENT_SECRET")

# Check if PayPal is configured
if not PAYPAL_CLIENT_ID or not PAYPAL_CLIENT_SECRET:
    print("WARNING: PayPal credentials not configured. Set PAYPAL_CLIENT_ID and PAYPAL_CLIENT_SECRET in .env")

# Configure PayPal
paypalrestsdk.configure({
    "mode": PAYPAL_MODE,
    "client_id": PAYPAL_CLIENT_ID,
    "client_secret": PAYPAL_CLIENT_SECRET
})

# Token packages
TOKEN_PACKAGES = {
    "starter": {"tokens": 500, "price": "5.00", "name": "Starter Pack"},
    "popular": {"tokens": 1000, "price": "9.00", "name": "Popular Pack"},
    "best_value": {"tokens": 2500, "price": "20.00", "name": "Best Value Pack"},
}


def create_payment(user_id: int, package_id: str, db: Session) -> dict:
    """Create a PayPal payment and return approval URL."""
    # Check if PayPal is configured
    if not PAYPAL_CLIENT_ID or not PAYPAL_CLIENT_SECRET:
        raise ValueError(
            "PayPal is not configured. Please set PAYPAL_CLIENT_ID and PAYPAL_CLIENT_SECRET "
            "in your .env file. See docs/PAYPAL_SETUP_GUIDE.md for instructions."
        )
    
    if package_id not in TOKEN_PACKAGES:
        raise ValueError(f"Invalid package: {package_id}")
    
    package = TOKEN_PACKAGES[package_id]
    frontend_url = os.environ.get("FRONTEND_URL", "http://localhost:5173")
    
    payment = paypalrestsdk.Payment({
        "intent": "sale",
        "payer": {"payment_method": "paypal"},
        "redirect_urls": {
            "return_url": f"{frontend_url}/payment/success",
            "cancel_url": f"{frontend_url}/payment/cancel"
        },
        "transactions": [{
            "item_list": {
                "items": [{
                    "name": f"{package['name']} - {package['tokens']} Tokens",
                    "sku": package_id,
                    "price": package["price"],
                    "currency": "USD",
                    "quantity": 1
                }]
            },
            "amount": {
                "total": package["price"],
                "currency": "USD"
            },
            "description": f"Purchase {package['tokens']} tokens for Flowdeck",
            "custom": f"{db.get(User, user_id).auth_subject}:{package_id}:{package['tokens']}"
        }]
    })
    
    if payment.create():
        db.add(PaymentOrder(payment_id=payment.id, user_id=user_id, package_id=package_id,
                            tokens=package['tokens'], amount=package['price']))
        db.commit()
        # Find approval URL
        for link in payment.links:
            if link.rel == "approval_url":
                return {
                    "payment_id": payment.id,
                    "approval_url": link.href
                }
        raise Exception("No approval URL found")
    else:
        raise Exception(f"Payment creation failed: {payment.error}")


def _order_from_payment(payment, user_id: int, db: Session):
    user = db.get(User, user_id)
    if not user or len(payment.transactions) != 1:
        raise ValueError("Invalid payment owner or transaction")
    transaction = payment.transactions[0]
    subject, package_id, tokens = transaction.custom.split(":")
    order = db.get(PaymentOrder, payment.id)
    package = ({'tokens': order.tokens, 'price': order.amount}
               if order is not None else TOKEN_PACKAGES.get(package_id))
    if subject != user.auth_subject or not package or int(tokens) != package['tokens']:
        raise ValueError("Payment does not match the signed-in account and package")
    if transaction.amount.currency != 'USD' or Decimal(transaction.amount.total) != Decimal(package['price']):
        raise ValueError("Payment amount does not match package")
    if order is None:
        order = PaymentOrder(payment_id=payment.id, user_id=user_id, package_id=package_id,
                             tokens=package['tokens'], amount=package['price'])
        db.add(order)
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            order = db.get(PaymentOrder, payment.id)
    if order.user_id != user_id or order.tokens != package['tokens'] or order.package_id != package_id:
        raise ValueError("Payment order mismatch")
    return order


def _credit_captured_payment(payment, order, db: Session):
    # Approval alone does not prove that the sale has settled.
    sales = [r.sale for r in (getattr(payment.transactions[0], 'related_resources', None) or [])
             if getattr(r, 'sale', None)]
    if payment.state != 'approved' or len(sales) != 1 or sales[0].state != 'completed':
        raise ValueError("Payment has not completed; reconciliation will retry")
    if sales[0].amount.currency != order.currency or Decimal(sales[0].amount.total) != Decimal(order.amount):
        raise ValueError("Captured amount does not match order")
    order.status = 'captured'
    db.commit()  # durable recovery point before local credit
    tx = token_service.record_transaction(
        order.user_id, order.tokens, 'purchase', db, commit=False,
        operation_key=f"paypal:{payment.id}",
        metadata={'payment_id': payment.id, 'sale_id': sales[0].id, 'package_id': order.package_id},
        description=f"PayPal purchase: {order.tokens} tokens",
    )
    if tx is None:
        db.rollback()
        raise RuntimeError("Payment captured but credit is pending reconciliation")
    order.status = 'credited'
    order.error_message = None
    db.commit()
    return {'success': True, 'tokens_credited': order.tokens, 'amount': order.amount}


def execute_payment(payment_id: str, payer_id: str, db: Session, *, user_id: int) -> dict:
    """Verify remote settlement and commit one credit, including retry after a crash."""
    payment = paypalrestsdk.Payment.find(payment_id)
    order = _order_from_payment(payment, user_id, db)
    if order.status == 'credited':
        return {'success': True, 'tokens_credited': order.tokens, 'amount': order.amount}
    order.payer_id = payer_id
    db.commit()
    if payment.state != 'approved':
        try:
            executed = payment.execute({'payer_id': payer_id})
        except Exception:
            executed = False  # a timeout can occur after successful remote capture
        payment = paypalrestsdk.Payment.find(payment_id)
        if not executed and payment.state != 'approved':
            raise RuntimeError("Payment is not captured; retry payment confirmation")
    return _credit_captured_payment(payment, order, db)


def reconcile_payments():
    """Recover pending credits. Never initiate an unapproved remote sale."""
    if not PAYPAL_CLIENT_ID or not PAYPAL_CLIENT_SECRET:
        return
    import logging
    from database import SessionLocal
    with SessionLocal() as db:
        ids = [row[0] for row in db.query(PaymentOrder.payment_id)
               .filter(PaymentOrder.status.in_(['created', 'captured']))
               .order_by(PaymentOrder.updated_at).limit(100).all()]
    for payment_id in ids:
        with SessionLocal() as db:
            order = None
            try:
                order = db.get(PaymentOrder, payment_id)
                if order is None or order.status == 'credited':
                    continue
                payment = paypalrestsdk.Payment.find(payment_id)
                if payment.state == 'approved':
                    order = _order_from_payment(payment, order.user_id, db)
                    _credit_captured_payment(payment, order, db)
                elif order.status == 'created' and order.created_at < datetime.utcnow() - timedelta(days=30):
                    order.status = 'expired'
            except Exception as exc:
                db.rollback()
                order = db.get(PaymentOrder, payment_id)
                if order is not None:
                    order.error_message = str(exc)[:1000]
                logging.getLogger(__name__).exception("Payment reconciliation pending for %s", payment_id)
            finally:
                if order is not None:
                    order.updated_at = datetime.utcnow()
                    db.commit()


def get_packages():
    """Get available token packages."""
    return {
        "packages": [
            {
                "id": "starter",
                "name": "Starter Pack",
                "tokens": 500,
                "price": 5.00,
                "currency": "USD",
            },
            {
                "id": "popular",
                "name": "Popular Pack",
                "tokens": 1000,
                "price": 9.00,
                "currency": "USD",
                "badge": "Most Popular",
            },
            {
                "id": "best_value",
                "name": "Best Value Pack",
                "tokens": 2500,
                "price": 20.00,
                "currency": "USD",
                "badge": "Best Value",
            },
        ]
    }
