# Google OAuth Setup Guide

This guide explains how to set up Google OAuth authentication for Flowdeck.

## Prerequisites

- A Google Cloud Platform account
- Access to your production server (https://flowdeck.biz)
- Backend and frontend deployed

## Step 1: Create Google Cloud Project

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project or select an existing one
3. Note your project ID

## Step 2: Enable Google+ API

1. In the Google Cloud Console, go to **APIs & Services** > **Library**
2. Search for "Google+ API" or "Google Identity Services"
3. Click **Enable**

## Step 3: Configure OAuth Consent Screen

1. Go to **APIs & Services** > **OAuth consent screen**
2. Choose **External** user type (unless you have a Google Workspace)
3. Fill in the required information:
   - **App name**: Flowdeck
   - **User support email**: Your email
   - **Developer contact email**: Your email
   - **App domain**: https://flowdeck.biz
   - **Authorized domains**: flowdeck.biz
4. Add scopes:
   - `openid`
   - `email`
   - `profile`
5. Save and continue

## Step 4: Create OAuth 2.0 Credentials

1. Go to **APIs & Services** > **Credentials**
2. Click **Create Credentials** > **OAuth 2.0 Client ID**
3. Choose **Web application**
4. Configure:
   - **Name**: Flowdeck Production
   - **Authorized JavaScript origins**:
     - `https://flowdeck.biz`
   - **Authorized redirect URIs**:
     - `https://flowdeck.biz/api/auth/google/callback`
5. Click **Create**
6. Copy your **Client ID** and **Client Secret**

## Step 5: Configure Backend Environment

1. SSH into your server
2. Edit the backend `.env` file:

```bash
cd /path/to/flowdeck/backend
nano .env
```

3. Add the following variables:

```bash
# Google OAuth Configuration
GOOGLE_CLIENT_ID=your_client_id_here
GOOGLE_CLIENT_SECRET=your_client_secret_here
GOOGLE_REDIRECT_URI=https://flowdeck.biz/api/auth/google/callback

# Frontend URL (for OAuth redirects)
FRONTEND_URL=https://flowdeck.biz
```

4. Save and exit

## Step 6: Install Required Python Package

The Google OAuth implementation requires the `google-auth` package:

```bash
cd /path/to/flowdeck
source venv/bin/activate  # or: conda activate flowdeck
pip install google-auth google-auth-oauthlib google-auth-httplib2
```

## Step 7: Update Database Schema

The database needs to be updated to support Google OAuth users:

```bash
cd /path/to/flowdeck/backend
python -c "
from database import engine, Base
from models.db_models import User
# This will add the new columns if they don't exist
Base.metadata.create_all(bind=engine)
print('Database schema updated successfully')
"
```

Or manually run SQL migration:

```sql
-- Add google_id column
ALTER TABLE users ADD COLUMN google_id VARCHAR(255);
CREATE UNIQUE INDEX idx_users_google_id ON users(google_id);

-- Make hashed_password nullable for Google OAuth users
ALTER TABLE users ALTER COLUMN hashed_password DROP NOT NULL;
```

## Step 8: Restart Backend

```bash
# If using systemd
sudo systemctl restart flowdeck-backend

# Or if running manually
cd /path/to/flowdeck/backend
pkill -f "python main.py"
python main.py
```

## Step 9: Test the Integration

1. Open https://flowdeck.biz in your browser
2. Click on any "Sign in" or "Log in" button
3. Click "Continue with Google" in the auth modal
4. You should be redirected to Google's login page
5. After signing in with Google, you should be redirected back to Flowdeck and logged in

## Troubleshooting

### "redirect_uri_mismatch" Error

- Verify that the redirect URI in Google Cloud Console exactly matches: `https://flowdeck.biz/api/auth/google/callback`
- Check that there are no trailing slashes
- Ensure the protocol is `https://` not `http://`

### "invalid_client" Error

- Double-check your `GOOGLE_CLIENT_ID` and `GOOGLE_CLIENT_SECRET` in `.env`
- Ensure there are no extra spaces or quotes around the values

### Users Can't Sign In

- Check backend logs: `tail -f /path/to/flowdeck/backend/backend.log`
- Verify the `FRONTEND_URL` is set correctly in `.env`
- Ensure the OAuth consent screen is published (not in testing mode)

### Database Errors

- Verify the database schema was updated with the new columns
- Check that `hashed_password` is nullable
- Ensure `google_id` column exists and has a unique index

## Development/Testing Setup

For local development, add an additional redirect URI in Google Cloud Console:

- `http://localhost:8002/api/auth/google/callback`

And update your local `.env`:

```bash
GOOGLE_REDIRECT_URI=http://localhost:8002/api/auth/google/callback
FRONTEND_URL=http://localhost:5173
```

## Security Notes

1. **Never commit** your `GOOGLE_CLIENT_SECRET` to version control
2. Keep your `.env` file secure with proper file permissions: `chmod 600 .env`
3. Regularly rotate your OAuth credentials
4. Monitor the OAuth consent screen for any suspicious activity
5. Use HTTPS in production (already configured for flowdeck.biz)

## Additional Resources

- [Google OAuth 2.0 Documentation](https://developers.google.com/identity/protocols/oauth2)
- [Google Cloud Console](https://console.cloud.google.com/)
- [OAuth 2.0 Best Practices](https://tools.ietf.org/html/rfc6749)