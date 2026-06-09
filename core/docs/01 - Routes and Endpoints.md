# 01 — Routes and Endpoints

> Every route the core service exposes, who calls it, what it expects, and what it returns.

← Back to [[00 - Core Service Hub]]
→ Next: [[02 - User Model and Repository]]

---

## Important: Core Is Internal Only

Core runs on port **8001** and should never be exposed to the internet. The frontend always goes through auth (port 8000). Auth strips JWT cookies, extracts the user ID, and forwards it to core as an `X-User-Id` header.

---

## Route Table

| Route | Method | Caller | Auth Header |
|---|---|---|---|
| `/` | GET | Anyone | None |
| `/user/otp` | POST | Auth | None |
| `/user/otp/verify` | POST | Auth | None |
| `/user/` | GET | Auth | `X-User-Id` |

---

## Route Details

### GET /

Health check. Returns immediately.

```json
{ "success": true, "service": "core" }
```

---

### POST /user/otp

Called by auth when the frontend requests an OTP.

**Request body:**
```json
{ "email": "user@example.com" }
```

**What happens internally:**
1. Calls Gupshup API to send the OTP to the email address
2. Checks if a user with that email already exists in MongoDB
3. If no user exists: creates a new user record with `is_verified=False`
4. If user exists: proceeds without modification (OTP is still sent)

**Success response:**
```json
{ "success": true, "data": null, "error_message": "" }
```

**Error responses:**

| Status | Reason |
|---|---|
| 400 | Gupshup returned failure — OTP not sent |
| 500 | Gupshup API unreachable or unexpected error |

---

### POST /user/otp/verify

Called by auth after the user enters their OTP code.

**Request body:**
```json
{ "email": "user@example.com", "otp": "123456" }
```

**What happens internally:**
1. Calls Gupshup verify API with email + otp
2. Gupshup responds with success or failure
3. On failure: returns error — auth will increment the Redis attempt counter
4. On success:
   - Fetches user from MongoDB by email
   - If `is_verified` is False: sets it to True
   - Updates `last_login_at` to now
   - Returns `user_id`

**Success response:**
```json
{
  "success": true,
  "data": { "user_id": "664f2a3b..." },
  "error_message": ""
}
```

**Error responses:**

| Status | Reason |
|---|---|
| 400 | OTP wrong or expired — Gupshup rejected it |
| 404 | User not found after OTP verification (should not happen) |
| 500 | Gupshup API unreachable |

---

### GET /user/

Called by auth after validating the access token. Fetches the full user profile.

**Required header:**
```
X-User-Id: 664f2a3b...
```

**What happens internally:**
1. Reads `X-User-Id` header
2. Queries MongoDB for user with that ID
3. Returns the user object

**Success response:**
```json
{
  "success": true,
  "data": {
    "user": {
      "id": "664f2a3b...",
      "email": "user@example.com",
      "name": "",
      "kind": "",
      "tenant_id": "",
      "is_verified": true,
      "created_at": "2025-06-09T10:00:00",
      "last_login_at": "2025-06-09T12:00:00"
    }
  }
}
```

**Error responses:**

| Status | Reason |
|---|---|
| 404 | No user found with that ID |

---

## Standard Response Shape

All core responses use this structure:

```json
{
  "success": true | false,
  "data": { ... } | null,
  "error_message": "" | "explanation"
}
```

---

## Relevant Files

- `app/routes/user_routes.py` — Route definitions and FastAPI bindings
- `app/handlers/user_handler.py` — `handle_send_otp()`, `handle_verify_otp()`, `handle_fetch_user()`
- `app/utils/response.py` — `success_response()`, `error_response()`
