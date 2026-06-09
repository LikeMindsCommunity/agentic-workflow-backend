# 06 — Running and Testing

> How to get the auth service running locally and how to verify every endpoint works correctly using curl.

← Back to [[00 - Auth Service Hub]]

---

## Prerequisites

Before starting auth, make sure these are running:

| Dependency | Check Command | Start Command |
|---|---|---|
| Core service (port 8001) | `curl http://localhost:8001/` | See Core service docs |
| Redis | `redis-cli ping` → PONG | `brew services start redis` |

Auth will start without Redis and Core, but all routes will fail until they are available.

---

## Environment Variables

File: `auth/.env`

| Variable | Value | Notes |
|---|---|---|
| `ACCESS_SECRET` | `6900db61d6c997d7f388e936` | JWT signing key — keep secret in prod |
| `SECRET_KEY` | `6900db61d6c997d7f388e936` | AES encryption key — keep secret in prod |
| `SERVER_ENVIRONMENT` | `beta` | Use `production` in prod — affects cookie secure flag |
| `CORE_BASE_URL` | `http://localhost:8001` | URL of the running core service |
| `REDIS_DSN` | `localhost:6379` | Redis host:port |
| `REDIS_PASSWORD` | (empty) | Set if Redis has auth enabled |
| `CORS_ALLOWED_ORIGINS` | `http://localhost:3000,...` | Comma-separated frontend origins |

---

## Starting the Service

```bash
cd /Users/likeminds/cep-tracking-plan/agentic-workflow-backend/auth

# First time only
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Every time
source .venv/bin/activate
python -m uvicorn main:app --port 8000 --reload
```

Expected output:
```
INFO:     Application startup complete.
INFO:     Uvicorn running on http://127.0.0.1:8000 (Press CTRL+C to quit)
```

---

## Testing with curl

### 1. Health check

```bash
curl http://localhost:8000/
```
Expected: `{"success": true, "service": "auth"}`

---

### 2. Request OTP

```bash
curl -X POST http://localhost:8000/user/otp \
  -H "Content-Type: application/json" \
  -d '{"email": "your@email.com"}'
```
Expected: `{"success": true, "data": null, "error_message": ""}`

Check the core service logs — you should see it proxied the request to Gupshup.

---

### 3. Verify OTP (saves cookies to file)

```bash
curl -X POST http://localhost:8000/user/otp/verify \
  -H "Content-Type: application/json" \
  -d '{"email": "your@email.com", "otp": "123456"}' \
  -c cookies.txt -v
```

In the `-v` output look for:
```
< Set-Cookie: access_token=eyJ...; HttpOnly; Path=/; SameSite=strict
< Set-Cookie: refresh_token=eyJ...; HttpOnly; Path=/; SameSite=strict
```

The `cookies.txt` file now holds both tokens for subsequent requests.

---

### 4. Get user profile (authenticated)

```bash
curl http://localhost:8000/user \
  -b cookies.txt
```
Expected: user object from Core with id, email, name, is_verified, etc.

---

### 5. Refresh access token

```bash
curl -X POST http://localhost:8000/user/refresh \
  -b cookies.txt -c cookies.txt -v
```
Look for a new `Set-Cookie: access_token=...` header. The refresh token stays the same.

---

### 6. Logout

```bash
curl -X POST http://localhost:8000/user/logout \
  -b cookies.txt -v
```
Look for:
```
< Set-Cookie: access_token=; Max-Age=0
< Set-Cookie: refresh_token=; Max-Age=0
```

After logout, the old cookies.txt tokens are blacklisted. Verify:

```bash
curl http://localhost:8000/user -b cookies.txt
```
Expected: `401 Device logged out! Please login again`

---

## Testing Error Cases

### Rate limit (run 6 times with wrong OTP)

```bash
for i in {1..6}; do
  curl -X POST http://localhost:8000/user/otp/verify \
    -H "Content-Type: application/json" \
    -d '{"email": "your@email.com", "otp": "000000"}'
  echo ""
done
```
The 6th call should return `429 Too many OTP attempts. Please try again after 30 minutes.`

---

### Access with no cookie

```bash
curl http://localhost:8000/user
```
Expected: `401 Missing access token`

---

## Interactive API Docs

FastAPI generates Swagger UI automatically:

```
http://localhost:8000/docs
```

You can test all endpoints directly in the browser there.

---

## Relevant Files

- `main.py` — App entry point, CORS setup, router registration
- `app/config/settings.py` — All environment variable definitions
- `auth/.env` — Actual env values for local development
