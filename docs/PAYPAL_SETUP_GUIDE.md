# PayPal Billing Setup Guide

## Quick Start (15 minutes)

### Step 1: Get PayPal Sandbox Credentials (5 min)

1. Go to https://developer.paypal.com/
2. Log in with your PayPal account (or create one)
3. Click "Dashboard" in the top menu
4. Go to "My Apps & Credentials"
5. Under "Sandbox" tab, click "Create App"
6. Give it a name (e.g., "Flowdeck Sandbox")
7. Copy your **Client ID** and **Secret**

### Step 2: Configure Backend (3 min)

1. Install PayPal SDK:
```bash
cd backend
pip install -r requirements.txt
```

2. Create or update `backend/.env`:
```bash
# PayPal Sandbox (for testing)
PAYPAL_MODE=sandbox
PAYPAL_CLIENT_ID=your_sandbox_client_id_here
PAYPAL_CLIENT_SECRET=your_sandbox_secret_here

# Frontend URL (for redirects)
FRONTEND_URL=http://localhost:5173
```

3. Start the backend:
```bash
python run.py
```

### Step 3: Start Frontend (2 min)

```bash
cd frontend
npm install  # if you haven't already
npm run dev
```

### Step 4: Test It! (5 min)

1. Open http://localhost:5173
2. Log in or create an account
3. Go to your Profile page
4. Scroll to "Purchase Tokens" section
5. Click "Pay with PayPal" on any package
6. You'll be redirected to PayPal Sandbox
7. Use these test credentials:
   - **Email**: Create a test buyer account in PayPal Developer Dashboard
   - Or use the default sandbox buyer account shown in your dashboard
8. Complete the payment
9. You'll be redirected back and tokens will be credited!

## Creating Test Buyer Account

1. In PayPal Developer Dashboard, go to "Sandbox" → "Accounts"
2. Click "Create Account"
3. Select "Personal" account type
4. Fill in details (use any fake data)
5. Click "Create Account"
6. Use these credentials to test payments

## Troubleshooting

### "Payment creation failed"
- Check that `PAYPAL_CLIENT_ID` and `PAYPAL_CLIENT_SECRET` are set correctly
- Verify you're using sandbox credentials (not live)
- Check backend logs for detailed error

### "Failed to execute payment"
- Check that payment was completed in PayPal
- Verify `paymentId` and `PayerID` are in the return URL
- Check backend logs

### Tokens not credited
- Check backend logs for errors in `execute_payment`
- Verify user is logged in
- Check database to see if `token_balance` was updated

## Production Deployment

### Step 1: Get Live Credentials

1. Go to https://developer.paypal.com/
2. Go to "My Apps & Credentials"
3. Switch to "Live" tab
4. Create a new app or use existing
5. Copy **Live Client ID** and **Secret**

### Step 2: Update Environment Variables

Update `backend/.env`:
```bash
# PayPal Live (production)
PAYPAL_MODE=live
PAYPAL_CLIENT_ID=your_live_client_id
PAYPAL_CLIENT_SECRET=your_live_secret

# Production frontend URL
FRONTEND_URL=https://yourdomain.com
```

### Step 3: Test with Real Payment

1. Make a small test purchase ($5)
2. Verify tokens are credited
3. Check PayPal dashboard for transaction

### Step 4: Monitor

- Check PayPal Dashboard regularly
- Monitor backend logs for errors
- Set up email alerts for failed payments

## Security Best Practices

✅ **Never commit credentials** - Keep `.env` in `.gitignore`
✅ **Use environment variables** - Don't hardcode keys
✅ **Test in sandbox first** - Always test before going live
✅ **Monitor transactions** - Check PayPal dashboard regularly
✅ **Log errors** - Keep logs for debugging
✅ **Use HTTPS in production** - Required for PayPal

## Package Pricing

Current packages:
- **Starter Pack**: 500 tokens for $5.00
- **Popular Pack**: 1,000 tokens for $9.00 (10% discount)
- **Best Value Pack**: 2,500 tokens for $20.00 (20% discount)

To change pricing, edit `backend/services/paypal_service.py`:
```python
TOKEN_PACKAGES = {
    "starter": {"tokens": 500, "price": "5.00", "name": "Starter Pack"},
    "popular": {"tokens": 1000, "price": "9.00", "name": "Popular Pack"},
    "best_value": {"tokens": 2500, "price": "20.00", "name": "Best Value Pack"},
}
```

## Support

- **PayPal Developer Docs**: https://developer.paypal.com/docs/
- **PayPal Support**: https://www.paypal.com/us/smarthelp/contact-us
- **Sandbox Testing**: https://developer.paypal.com/docs/api-basics/sandbox/

## Next Steps

Once basic integration is working:

1. **Add email receipts** - Send confirmation emails after purchases
2. **Add payment history** - Show past purchases in profile
3. **Add refund handling** - Handle refund requests
4. **Add analytics** - Track revenue and conversion rates
5. **Add promotions** - Offer discounts or bonus tokens

## Files Created

Backend:
- `backend/services/paypal_service.py` - Payment processing logic
- `backend/routers/payments.py` - API endpoints
- `backend/.env.example` - Environment variable template

Frontend:
- `frontend/src/services/paymentApi.ts` - API client
- `frontend/src/components/TokenPurchase.tsx` - Purchase UI
- `frontend/src/pages/PaymentSuccessPage.tsx` - Success page
- `frontend/src/pages/PaymentCancelPage.tsx` - Cancel page

Documentation:
- `docs/PAYPAL_BILLING_INTEGRATION.md` - Detailed integration guide
- `docs/PAYPAL_SETUP_GUIDE.md` - This quick setup guide