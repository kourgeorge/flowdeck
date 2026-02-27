"""PayPal payment processing - super simple version."""

import os
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


def create_payment(user_id: int, package_id: str) -> dict:
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
            "custom": f"{user_id}:{package_id}:{package['tokens']}"  # Store user_id and tokens
        }]
    })
    
    if payment.create():
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


def execute_payment(payment_id: str, payer_id: str, db: Session) -> dict:
    """Execute the payment and credit tokens."""
    payment = paypalrestsdk.Payment.find(payment_id)
    
    if payment.execute({"payer_id": payer_id}):
        # Payment successful - credit tokens
        custom_data = payment.transactions[0].custom
        user_id, package_id, tokens = custom_data.split(":")
        user_id = int(user_id)
        tokens = int(tokens)
        
        # Credit tokens to user
        token_service.top_up(user_id, tokens, db)
        
        return {
            "success": True,
            "tokens_credited": tokens,
            "amount": payment.transactions[0].amount.total
        }
    else:
        raise Exception(f"Payment execution failed: {payment.error}")


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

# Made with Bob
