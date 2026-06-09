# 05 — Running and Testing

> How to get the core service running locally and how to verify every endpoint works. Note that most routes require an `X-User-Id` header — in production this comes from auth, but in testing you set it manually.

← Back to [[00 - Core Service Hub]]

---

## Prerequisites

| Dependency | Check Command | Start Command |
|---|---|---|
| MongoDB | `mongosh --eval "db.runCommand({ping:1})"` | `brew services start mongodb-community` |

Core does not need Redis or Auth to start, but the auth service needs core running before it can forward OTP requests.

---

## Environment Variables

File: `core/.env`

| Variable | Value | Notes |
|---|---|---|
| `MONGO_URI` | `mongodb://localhost:27017` | Local MongoDB |
| `MONGO_DB_NAME` | `skill_db` | Database name |
| `EMAIL_GHUPSHAP_KEY` | `341707ec53b5ecb822862aff20681358` | Gupshup API key |
| `SERVER_ENVIRONMENT` | `beta` | Environment label |

---

## Starting the Service

```bash
cd /Users/likeminds/cep-tracking-plan/agentic-workflow-backend/core

# First time only
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Every time
source .venv/bin/activate
python -m uvicorn main:app --port 8001 --reload
```

Expected output:
```
INFO:     Application startup complete.
INFO:     Uvicorn running on http://127.0.0.1:8001 (Press CTRL+C to quit)
```

---

## Testing with curl

### 1. Health check

```bash
curl http://localhost:8001/
```
Expected: `{"success": true, "service": "core"}`

---

### 2. Send OTP

```bash
curl -X POST http://localhost:8001/user/otp \
  -H "Content-Type: application/json" \
  -d '{"email": "your@email.com"}'
```

Expected: `{"success": true, "data": null, "error_message": ""}`

Check MongoDB — a new document should appear in the `users` collection:
```bash
mongosh skill_db --eval 'db.users.find({email: "your@email.com"}).pretty()'
```

---

### 3. Verify OTP

```bash
curl -X POST http://localhost:8001/user/otp/verify \
  -H "Content-Type: application/json" \
  -d '{"email": "your@email.com", "otp": "123456"}'
```

Expected:
```json
{
  "success": true,
  "data": { "user_id": "664f2a3b..." },
  "error_message": ""
}
```

Copy the `user_id` for the next step.

---

### 4. Fetch user profile

Core requires `X-User-Id` — in production auth sets this from the JWT. In testing you pass it manually:

```bash
curl http://localhost:8001/user/ \
  -H "X-User-Id: 664f2a3b..."
```

Expected: full user object with email, is_verified, last_login_at, etc.

---

## Testing the Full Flow via Auth

The intended path for end-to-end testing is always through auth (port 8000), which proxies to core automatically. See [[06 - Running and Testing]] in the Auth docs for the full flow with cookie handling.

---

## Inspecting MongoDB Directly

```bash
# Connect to the database
mongosh skill_db

# List all users
db.users.find().pretty()

# Find a specific user
db.users.findOne({ email: "your@email.com" })

# Check is_verified was set
db.users.findOne({ email: "your@email.com" }, { is_verified: 1, last_login_at: 1 })
```

---

## Interactive API Docs

FastAPI generates Swagger UI automatically:

```
http://localhost:8001/docs
```

You can test all endpoints there and set the `X-User-Id` header via the Authorize button or the request editor.

---

## Relevant Files

- `main.py` — App entry point, lifespan, router registration
- `app/config/settings.py` — All environment variable definitions
- `core/.env` — Actual env values for local development
- `app/database/mongodb.py` — MongoDB connection management
