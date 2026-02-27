# PayPal Billing Integration - Super Simple Guide

## Why PayPal?

- ✅ **15-minute setup** - Fastest integration
- ✅ **No database table needed** - Just credit tokens on return
- ✅ **Most users have accounts** - Higher conversion
- ✅ **Simple API** - Just redirect to PayPal
- ✅ **Works globally** - 200+ countries

## How It Works

```
User clicks "Buy 500 tokens" 
    ↓
Backend creates PayPal payment link
    ↓
User redirected to PayPal
    ↓
User pays with PayPal account or card
    ↓
PayPal redirects back to your site
    ↓
Backend verifies payment and credits tokens
    ↓
Done!
```

## Quick Setup (15 minutes)

### Step 1: Get PayPal Credentials (5 min)

1. Go to https://developer.paypal.com/
2. Log in (or create account)
3. Go to "My Apps & Credentials"
4. Under "Sandbox", create a new app
5. Copy your **Client ID** and **Secret**

### Step 2: Backend Setup (5 min)

#### 2.1 Install PayPal SDK

```bash
cd backend
echo "paypalrestsdk>=1.13.1" >> requirements.txt
pip install paypalrestsdk
```

#### 2.2 Add Environment Variables

Add to `backend/.env`:
```bash
# PayPal Sandbox (for testing)
PAYPAL_MODE=sandbox
PAYPAL_CLIENT_ID=your_sandbox_client_id
PAYPAL_CLIENT_SECRET=your_sandbox_secret

# For production, change to:
# PAYPAL_MODE=live
# PAYPAL_CLIENT_ID=your_live_client_id
# PAYPAL_CLIENT_SECRET=your_live_secret

FRONTEND_URL=http://localhost:5173
```

#### 2.3 Create Payment Service

Create `backend/services/paypal_service.py`:

```python
"""PayPal payment processing - super simple version."""

import os
import paypalrestsdk
from sqlalchemy.orm import Session
from services import token_service

# Configure PayPal
paypalrestsdk.configure({
    "mode": os.environ.get("PAYPAL_MODE", "sandbox"),
    "client_id": os.environ.get("PAYPAL_CLIENT_ID"),
    "client_secret": os.environ.get("PAYPAL_CLIENT_SECRET")
})

# Token packages
TOKEN_PACKAGES = {
    "starter": {"tokens": 500, "price": "5.00", "name": "Starter Pack"},
    "popular": {"tokens": 1000, "price": "9.00", "name": "Popular Pack"},
    "best_value": {"tokens": 2500, "price": "20.00", "name": "Best Value Pack"},
}

def create_payment(user_id: int, package_id: str) -> dict:
    """Create a PayPal payment and return approval URL."""
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
```

#### 2.4 Create API Endpoints

Create `backend/routers/payments.py`:

```python
"""PayPal payment endpoints."""

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from auth import get_current_user
from database import get_db
from services import paypal_service

router = APIRouter(prefix="/api/payments", tags=["payments"])

class CreatePaymentRequest(BaseModel):
    package_id: str

class CreatePaymentResponse(BaseModel):
    payment_id: str
    approval_url: str

@router.post("/create", response_model=CreatePaymentResponse)
async def create_payment(
    body: CreatePaymentRequest,
    current_user=Depends(get_current_user),
):
    """Create a PayPal payment."""
    try:
        result = paypal_service.create_payment(current_user.id, body.package_id)
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create payment: {str(e)}")

@router.post("/execute")
async def execute_payment(
    payment_id: str = Query(...),
    payer_id: str = Query(..., alias="PayerID"),
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Execute PayPal payment and credit tokens."""
    try:
        result = paypal_service.execute_payment(payment_id, payer_id, db)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to execute payment: {str(e)}")

@router.get("/packages")
async def get_packages():
    """Get available token packages."""
    return paypal_service.get_packages()
```

#### 2.5 Register Router

Add to `backend/main.py`:

```python
from routers.payments import router as payments_router

app.include_router(payments_router)
```

### Step 3: Frontend Setup (5 min)

#### 3.1 Create Payment API Service

Create `frontend/src/services/paymentApi.ts`:

```typescript
import axios from 'axios';
import { API_BASE_URL } from '../config';

export interface TokenPackage {
  id: string;
  name: string;
  tokens: number;
  price: number;
  currency: string;
  badge?: string;
}

export const paymentApi = {
  async getPackages(): Promise<{ packages: TokenPackage[] }> {
    const response = await axios.get(`${API_BASE_URL}/api/payments/packages`);
    return response.data;
  },

  async createPayment(packageId: string): Promise<{ payment_id: string; approval_url: string }> {
    const token = localStorage.getItem('token');
    const response = await axios.post(
      `${API_BASE_URL}/api/payments/create`,
      { package_id: packageId },
      { headers: { Authorization: `Bearer ${token}` } }
    );
    return response.data;
  },

  async executePayment(paymentId: string, payerId: string): Promise<any> {
    const token = localStorage.getItem('token');
    const response = await axios.post(
      `${API_BASE_URL}/api/payments/execute?payment_id=${paymentId}&PayerID=${payerId}`,
      {},
      { headers: { Authorization: `Bearer ${token}` } }
    );
    return response.data;
  },
};
```

#### 3.2 Create Token Purchase Component

Create `frontend/src/components/TokenPurchase.tsx`:

```typescript
import { useState, useEffect } from 'react';
import { paymentApi, type TokenPackage } from '../services/paymentApi';

export default function TokenPurchase() {
  const [packages, setPackages] = useState<TokenPackage[]>([]);
  const [loading, setLoading] = useState(true);
  const [purchasing, setPurchasing] = useState<string | null>(null);

  useEffect(() => {
    paymentApi.getPackages().then((data) => {
      setPackages(data.packages);
      setLoading(false);
    });
  }, []);

  const handlePurchase = async (packageId: string) => {
    setPurchasing(packageId);
    try {
      const { approval_url } = await paymentApi.createPayment(packageId);
      window.location.href = approval_url; // Redirect to PayPal
    } catch (error) {
      alert('Failed to start payment. Please try again.');
      setPurchasing(null);
    }
  };

  if (loading) return <div className="text-gray-400">Loading packages...</div>;

  return (
    <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
      {packages.map((pkg) => (
        <div
          key={pkg.id}
          className="bg-gray-800 border border-gray-700 rounded-xl p-6 relative hover:border-blue-500 transition-colors"
        >
          {pkg.badge && (
            <div className="absolute top-4 right-4 bg-blue-600 text-white text-xs px-2 py-1 rounded">
              {pkg.badge}
            </div>
          )}
          <h3 className="text-xl font-bold text-white mb-2">{pkg.name}</h3>
          <div className="text-3xl font-bold text-white mb-1">
            {pkg.tokens.toLocaleString()}
            <span className="text-lg text-gray-400 ml-1">tokens</span>
          </div>
          <div className="text-2xl font-semibold text-blue-400 mb-4">
            ${pkg.price.toFixed(2)}
          </div>
          <button
            onClick={() => handlePurchase(pkg.id)}
            disabled={purchasing === pkg.id}
            className="w-full px-4 py-3 bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white rounded-lg font-medium transition-colors flex items-center justify-center gap-2"
          >
            {purchasing === pkg.id ? (
              'Processing...'
            ) : (
              <>
                <span>Pay with PayPal</span>
                <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 24 24">
                  <path d="M20.067 8.478c.492.88.556 2.014.3 3.327-.74 3.806-3.276 5.12-6.514 5.12h-.5a.805.805 0 00-.794.68l-.04.22-.63 3.993-.028.15a.805.805 0 01-.793.68H8.032c-.356 0-.623-.29-.623-.645 0-.054.005-.108.016-.161l1.176-7.45a.805.805 0 01.793-.68h2.374c3.238 0 5.774-1.314 6.514-5.12.256-1.313.192-2.447-.3-3.327z"/>
                </svg>
              </>
            )}
          </button>
        </div>
      ))}
    </div>
  );
}
```

#### 3.3 Create Success Page

Create `frontend/src/pages/PaymentSuccessPage.tsx`:

```typescript
import { useEffect, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { paymentApi } from '../services/paymentApi';

export default function PaymentSuccessPage() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const { refreshUser } = useAuth();
  const [processing, setProcessing] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const paymentId = searchParams.get('paymentId');
    const payerId = searchParams.get('PayerID');

    if (!paymentId || !payerId) {
      setError('Missing payment information');
      setProcessing(false);
      return;
    }

    // Execute the payment
    paymentApi
      .executePayment(paymentId, payerId)
      .then(() => {
        // Refresh user data to get updated token balance
        refreshUser();
        setProcessing(false);
        
        // Redirect to profile after 2 seconds
        setTimeout(() => {
          navigate('/profile');
        }, 2000);
      })
      .catch((err) => {
        setError('Failed to process payment. Please contact support.');
        setProcessing(false);
      });
  }, [searchParams, navigate, refreshUser]);

  if (processing) {
    return (
      <div className="min-h-screen flex items-center justify-center p-8">
        <div className="max-w-md text-center">
          <div className="text-6xl mb-4">⏳</div>
          <h1 className="text-2xl font-bold text-white mb-2">Processing Payment...</h1>
          <p className="text-gray-400">Please wait while we confirm your payment.</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="min-h-screen flex items-center justify-center p-8">
        <div className="max-w-md text-center">
          <div className="text-6xl mb-4">❌</div>
          <h1 className="text-2xl font-bold text-white mb-2">Payment Error</h1>
          <p className="text-gray-400 mb-6">{error}</p>
          <button
            onClick={() => navigate('/profile')}
            className="px-6 py-3 bg-blue-600 hover:bg-blue-700 text-white rounded-lg font-medium"
          >
            Back to Profile
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen flex items-center justify-center p-8">
      <div className="max-w-md text-center">
        <div className="text-6xl mb-4">✅</div>
        <h1 className="text-2xl font-bold text-white mb-2">Payment Successful!</h1>
        <p className="text-gray-400 mb-6">
          Your tokens have been added to your account.
        </p>
        <button
          onClick={() => navigate('/profile')}
          className="px-6 py-3 bg-blue-600 hover:bg-blue-700 text-white rounded-lg font-medium"
        >
          Go to Profile
        </button>
      </div>
    </div>
  );
}
```

Create `frontend/src/pages/PaymentCancelPage.tsx`:

```typescript
import { useNavigate } from 'react-router-dom';

export default function PaymentCancelPage() {
  const navigate = useNavigate();

  return (
    <div className="min-h-screen flex items-center justify-center p-8">
      <div className="max-w-md text-center">
        <div className="text-6xl mb-4">❌</div>
        <h1 className="text-2xl font-bold text-white mb-2">Payment Cancelled</h1>
        <p className="text-gray-400 mb-6">
          Your payment was cancelled. No charges were made.
        </p>
        <button
          onClick={() => navigate('/profile')}
          className="px-6 py-3 bg-blue-600 hover:bg-blue-700 text-white rounded-lg font-medium"
        >
          Back to Profile
        </button>
      </div>
    </div>
  );
}
```

#### 3.4 Add Routes

Update `frontend/src/App.tsx`:

```typescript
import PaymentSuccessPage from './pages/PaymentSuccessPage';
import PaymentCancelPage from './pages/PaymentCancelPage';

// Add these routes:
<Route path="/payment/success" element={<PaymentSuccessPage />} />
<Route path="/payment/cancel" element={<PaymentCancelPage />} />
```

#### 3.5 Update Profile Page

Add to `frontend/src/pages/ProfilePage.tsx` (after token balance section):

```typescript
import TokenPurchase from '../components/TokenPurchase';

// Add this section:
<section className="bg-gray-800 border border-gray-700 rounded-xl p-6 mb-6">
  <h2 className="text-lg font-semibold text-white mb-4">Purchase Tokens</h2>
  <p className="text-sm text-gray-400 mb-6">
    Need more tokens? Choose a package below to top up your account with PayPal.
  </p>
  <TokenPurchase />
</section>
```

## Testing (5 minutes)

### Test with PayPal Sandbox

1. Start your servers:
```bash
# Terminal 1 - Backend
cd backend
python run.py

# Terminal 2 - Frontend
cd frontend
npm run dev
```

2. Go to http://localhost:5173/profile

3. Click "Pay with PayPal" on any package

4. You'll be redirected to PayPal Sandbox

5. Use these test credentials:
   - **Email**: sb-buyer@personal.example.com (or create your own in PayPal Developer Dashboard)
   - **Password**: (provided in PayPal Developer Dashboard)

6. Complete the payment

7. You'll be redirected back and tokens will be credited!

## Production Deployment

### Switch to Live Mode

1. Get live credentials from https://developer.paypal.com/
2. Update `backend/.env`:
```bash
PAYPAL_MODE=live
PAYPAL_CLIENT_ID=your_live_client_id
PAYPAL_CLIENT_SECRET=your_live_secret
```

3. Test with a real payment (small amount)
4. Monitor PayPal dashboard for transactions

## Advantages of This Approach

✅ **No database table needed** - Tokens credited immediately on return
✅ **No webhooks** - Simpler than Stripe
✅ **15-minute setup** - Fastest integration
✅ **High conversion** - Most users have PayPal
✅ **Global support** - Works in 200+ countries
✅ **Mobile-friendly** - PayPal app integration

## Troubleshooting

### "Payment creation failed"
- Check PayPal credentials in `.env`
- Verify you're using sandbox mode for testing
- Check backend logs for detailed error

### "Payment execution failed"
- Check that payment_id and PayerID are in URL
- Verify user is logged in
- Check backend logs

### "Tokens not credited"
- Check that `execute_payment` endpoint was called
- Verify `token_service.top_up()` is working
- Check database for updated token_balance

## Next Steps

Once working:
1. Add email receipts
2. Add payment logging (optional)
3. Add admin dashboard to see revenue
4. Consider adding more payment methods

## Resources

- [PayPal Developer Docs](https://developer.paypal.com/docs/)
- [PayPal REST API](https://developer.paypal.com/docs/api/overview/)
- [PayPal Sandbox Testing](https://developer.paypal.com/docs/api-basics/sandbox/)