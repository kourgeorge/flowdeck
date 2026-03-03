# API Key Authentication for FlowDeck

## Overview

FlowDeck supports API key authentication for programmatic access to the platform. API keys provide a secure, long-lived alternative to JWT tokens for bots, scripts, and integrations.

## Key Features

- **Persistent Authentication**: API keys don't expire by default (optional expiration supported)
- **Secure Storage**: Keys are hashed with SHA-256 before storage
- **One-Time Display**: Full key shown only once during creation
- **Activity Tracking**: Last used timestamp updated on each request
- **Granular Control**: Activate/deactivate keys without deletion
- **User-Scoped**: Each key is tied to a specific user account

## Creating an API Key

### 1. Authenticate with JWT

First, log in to get a JWT token:

```bash
POST /api/auth/login
Content-Type: application/json

{
  "email": "your@email.com",
  "password": "your_password"
}

Response:
{
  "access_token": "eyJhbGc...",
  "token_type": "bearer",
  "user_id": 123,
  "email": "your@email.com"
}
```

### 2. Create API Key

Use your JWT token to create an API key:

```bash
POST /api/api-keys
Authorization: Bearer <your_jwt_token>
Content-Type: application/json

{
  "name": "Production Bot",
  "expires_at": "2027-12-31T23:59:59Z"  // Optional
}

Response:
{
  "id": 1,
  "name": "Production Bot",
  "key": "fd_live_xK9mP2nQ7vR4sT8wY3zA1bC5dE6fG0hI",  // SAVE THIS!
  "key_prefix": "fd_live_xK9mP2nQ",
  "is_active": true,
  "created_at": "2026-03-03T07:00:00Z",
  "expires_at": "2027-12-31T23:59:59Z",
  "warning": "Save this key now - it won't be shown again!"
}
```

**⚠️ IMPORTANT**: The full key is only shown once. Save it securely!

## Using API Keys

### Authentication Header

Use API keys exactly like JWT tokens in the `Authorization` header:

```bash
GET /api/me
Authorization: Bearer fd_live_xK9mP2nQ7vR4sT8wY3zA1bC5dE6fG0hI
```

### Example: Python

```python
import requests

API_KEY = "fd_live_xK9mP2nQ7vR4sT8wY3zA1bC5dE6fG0hI"
BASE_URL = "https://api.flowdeck.com"

headers = {
    "Authorization": f"Bearer {API_KEY}"
}

# Get user profile
response = requests.get(f"{BASE_URL}/api/me", headers=headers)
print(response.json())

# Chat with AI
chat_data = {
    "messages": [{"role": "user", "content": "Analyze AAPL"}]
}
response = requests.post(
    f"{BASE_URL}/api/chat",
    headers=headers,
    json=chat_data
)
print(response.json())

# Get AI reports
response = requests.get(
    f"{BASE_URL}/api/data/reports/AAPL",
    headers=headers
)
print(response.json())
```

### Example: cURL

```bash
# Get stock quote (public endpoint - no auth needed)
curl "https://api.flowdeck.com/api/data/quote/AAPL"

# Get AI reports (requires auth)
curl -H "Authorization: Bearer fd_live_xK9mP2nQ7vR4sT8wY3zA1bC5dE6fG0hI" \
  "https://api.flowdeck.com/api/data/reports/AAPL"

# Chat with AI (requires auth, costs tokens)
curl -X POST \
  -H "Authorization: Bearer fd_live_xK9mP2nQ7vR4sT8wY3zA1bC5dE6fG0hI" \
  -H "Content-Type: application/json" \
  -d '{"messages":[{"role":"user","content":"What is the outlook for TSLA?"}]}' \
  "https://api.flowdeck.com/api/chat"
```

### Example: JavaScript/Node.js

```javascript
const API_KEY = "fd_live_xK9mP2nQ7vR4sT8wY3zA1bC5dE6fG0hI";
const BASE_URL = "https://api.flowdeck.com";

async function getAIReports(ticker) {
  const response = await fetch(`${BASE_URL}/api/data/reports/${ticker}`, {
    headers: {
      "Authorization": `Bearer ${API_KEY}`
    }
  });
  return response.json();
}

async function chatWithAI(message) {
  const response = await fetch(`${BASE_URL}/api/chat`, {
    method: "POST",
    headers: {
      "Authorization": `Bearer ${API_KEY}`,
      "Content-Type": "application/json"
    },
    body: JSON.stringify({
      messages: [{ role: "user", content: message }]
    })
  });
  return response.json();
}

// Usage
const reports = await getAIReports("AAPL");
console.log(reports);

const chatResponse = await chatWithAI("Analyze MSFT");
console.log(chatResponse.reply);
```

## Managing API Keys

### List All Keys

```bash
GET /api/api-keys
Authorization: Bearer <jwt_or_api_key>

Response:
[
  {
    "id": 1,
    "name": "Production Bot",
    "key_prefix": "fd_live_xK9mP2nQ",
    "is_active": true,
    "created_at": "2026-03-03T07:00:00Z",
    "last_used_at": "2026-03-03T09:30:00Z",
    "expires_at": "2027-12-31T23:59:59Z"
  },
  {
    "id": 2,
    "name": "Dev Testing",
    "key_prefix": "fd_live_aB1cD2eF",
    "is_active": false,
    "created_at": "2026-02-15T10:00:00Z",
    "last_used_at": null,
    "expires_at": null
  }
]
```

### Deactivate a Key

Temporarily disable a key without deleting it:

```bash
PATCH /api/api-keys/{key_id}/deactivate
Authorization: Bearer <jwt_or_api_key>

Response: 204 No Content
```

### Reactivate a Key

Re-enable a deactivated key:

```bash
PATCH /api/api-keys/{key_id}/activate
Authorization: Bearer <jwt_or_api_key>

Response: 204 No Content
```

### Delete a Key

Permanently delete an API key (irreversible):

```bash
DELETE /api/api-keys/{key_id}
Authorization: Bearer <jwt_or_api_key>

Response: 204 No Content
```

## Security Best Practices

### 1. **Store Keys Securely**
- Never commit API keys to version control
- Use environment variables or secure vaults
- Rotate keys periodically

```bash
# .env file (add to .gitignore)
FLOWDECK_API_KEY=fd_live_xK9mP2nQ7vR4sT8wY3zA1bC5dE6fG0hI
```

### 2. **Use Descriptive Names**
- Name keys by their purpose: "Production Bot", "CI/CD Pipeline", "Dev Testing"
- Makes it easier to identify and manage keys

### 3. **Set Expiration Dates**
- For temporary integrations, set an expiration date
- Reduces risk if a key is compromised

### 4. **Monitor Usage**
- Check `last_used_at` timestamps regularly
- Delete unused keys

### 5. **Deactivate Instead of Delete**
- Deactivate keys when not in use
- Can reactivate later if needed

### 6. **One Key Per Integration**
- Don't share keys across multiple services
- Makes it easier to revoke access

## API Key Format

FlowDeck API keys follow this format:

```
fd_live_<43_character_base64_string>
```

- **Prefix**: `fd_live_` identifies it as a FlowDeck live API key
- **Secret**: 43 URL-safe base64 characters (256 bits of entropy)
- **Total Length**: 51 characters

Example: `fd_live_xK9mP2nQ7vR4sT8wY3zA1bC5dE6fG0hI1jK2lM3nO`

## Authentication Flow

```
1. User creates API key via POST /api/api-keys (requires JWT)
2. System generates key: fd_live_<random>
3. System hashes key with SHA-256 and stores hash
4. Full key returned to user (only time it's shown)
5. User stores key securely

6. User makes API request with key in Authorization header
7. System hashes provided key
8. System looks up hash in database
9. If found and active: authenticate as that user
10. Update last_used_at timestamp
11. Process request with user's permissions and token balance
```

## Limitations & Quotas

- **Token Economy**: API keys use the same token balance as JWT auth
- **Rate Limits**: Same rate limits apply to API keys and JWT tokens
- **Permissions**: API keys have the same permissions as the user who created them
- **Max Keys**: No hard limit, but recommend <10 keys per user

## Migration from JWT to API Keys

If you're currently using JWT tokens, migrating to API keys is simple:

### Before (JWT):
```python
# Login to get JWT
response = requests.post(f"{BASE_URL}/api/auth/login", json={
    "email": "bot@example.com",
    "password": "password"
})
jwt_token = response.json()["access_token"]

# Use JWT (expires in 7 days)
headers = {"Authorization": f"Bearer {jwt_token}"}
```

### After (API Key):
```python
# Create API key once (via web UI or API)
api_key = "fd_live_xK9mP2nQ7vR4sT8wY3zA1bC5dE6fG0hI"

# Use API key (never expires unless you set expiration)
headers = {"Authorization": f"Bearer {api_key}"}
```

**Benefits**:
- No need to re-authenticate every 7 days
- Simpler code (no login flow)
- Better for long-running bots and services

## Troubleshooting

### 401 Unauthorized
- **Cause**: Invalid or expired API key
- **Solution**: Check key is correct, active, and not expired

### 402 Payment Required
- **Cause**: Insufficient token balance
- **Solution**: Purchase more tokens or wait for token rewards

### 403 Forbidden
- **Cause**: Endpoint requires admin access
- **Solution**: Use an admin account's API key

### Key Not Working After Creation
- **Cause**: Using key_prefix instead of full key
- **Solution**: Use the full 51-character key shown during creation

## Database Schema

For reference, API keys are stored with this schema:

```sql
CREATE TABLE api_keys (
    id INTEGER PRIMARY KEY,
    user_id INTEGER NOT NULL,
    key_hash VARCHAR(255) UNIQUE NOT NULL,  -- SHA-256 hash
    key_prefix VARCHAR(16) NOT NULL,         -- First 16 chars for display
    name VARCHAR(255) NOT NULL,
    last_used_at DATETIME,
    is_active BOOLEAN NOT NULL DEFAULT 1,
    created_at DATETIME NOT NULL,
    expires_at DATETIME,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);
```

## Support

For issues or questions about API keys:
- Check this documentation
- Review error messages carefully
- Contact support with your key_prefix (never share the full key!)

---

**Last Updated**: 2026-03-03