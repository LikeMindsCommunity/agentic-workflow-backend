# 01 — Routes and Endpoints

> Every route the auth service exposes, what auth it requires, what it does internally, and what the frontend gets back.

← Back to [[00 - Auth Service Hub]]
→ Next: [[02 - JWT and Token System]]

---

## Route Table

| Route | Method | Auth Required | Action |
|---|---|---|---|
| `/` | GET | None | Health check |
| `/user/otp` | POST | None | Request OTP |
| `/user/otp/verify` | POST | None | Verify OTP, receive cookies |
| `/user/refresh` | POST | RTM cookie | Rotate access token |
| `/user/logout` | POST | VTM + RTM cookies | Invalidate tokens, clear cookies |
| `/user` | GET | VTM cookie | Fetch logged-in user profile |

---

## Route Details

### POST /user/otp

No authentication needed. Used to trigger an OTP to the user's email.

**Request body:**
```json
{ "email": "user@example.com" }
```

**What happens internally:**
1. Checks Redis — if this email has hit 5 failed OTP attempts in 30 minutes, returns 429
2. Calls `Core POST /user/otp` with the same email
3. Core sends the OTP via Gupshup and creates the user record if it doesn't exist
4. Returns success to frontend

**Success response:**
```json
{ "success": true, "data": null, "error_message": "" }
```

**Error responses:**

| Status | Reason |
|---|---|
| 429 | Too many OTP requests — rate limit hit |
| 500 | Gupshup API failed or Core unreachable |

---

### POST /user/otp/verify

No authentication needed. The critical route — verifying the OTP issues the JWT cookies.

**Request body:**
```json
{ "email": "user@example.com", "otp": "123456" }
```

**What happens internally:**
1. Checks Redis rate limit — same 5-attempt / 30-minute window
2. Calls `Core POST /user/otp/verify`
3. If OTP is wrong: increments the Redis attempt counter, returns 400
4. If OTP is correct: resets attempt counter
5. Extracts `user_id` from Core's response
6. Creates VTM (access token) and RTM (refresh token)
7. Sets both as httpOnly cookies on the response

**Success response:**
```json
{ "success": true, "data": { "user_id": "abc123" }, "error_message": "" }
```
Plus two `Set-Cookie` headers — `access_token` and `refresh_token`.

**Error responses:**

| Status | Reason |
|---|---|
| 400 | Wrong OTP |
| 429 | Too many failed attempts |
| 404 | User not found in Core |

---

### POST /user/refresh

Requires a valid `refresh_token` cookie. Used when the access token expires.

**Request body:** None

**What happens internally:**
1. Reads `refresh_token` cookie
2. Decrypts AES payload, verifies JWT signature
3. Checks Redis — if this RTM UUID is blacklisted (already logged out), returns 401
4. Issues a brand new VTM (access token) with a fresh expiry
5. Sets the new `access_token` cookie

**Success response:**
```json
{ "success": true, "data": null, "error_message": "" }
```
Plus a new `Set-Cookie: access_token` header.

**Error responses:**

| Status | Reason |
|---|---|
| 401 | Missing refresh token cookie |
| 401 | RTM is blacklisted (user already logged out) |
| 401 | RTM is expired or signature invalid |

---

### POST /user/logout

Requires both `access_token` and `refresh_token` cookies. Immediately invalidates both.

**Request body:** None

**What happens internally:**
1. Reads both cookies (blank strings if missing — logout still proceeds)
2. Extracts the UUIDs from both tokens
3. Writes both UUIDs to Redis with their remaining TTL as the key expiry
4. Clears both cookies by setting them with `Max-Age=0`

**Success response:**
```json
{ "success": true, "data": null, "error_message": "" }
```

Note: logout never returns an error even if tokens are already invalid. It always clears the cookies.

---

### GET /user

Requires a valid `access_token` cookie.

**What happens internally:**
1. Reads `access_token` cookie
2. Decrypts AES payload, verifies JWT
3. Checks Redis — if UUID is blacklisted, returns 401
4. Extracts `user_id` from the token claims
5. Calls `Core GET /user/` with `X-User-Id: {user_id}` header
6. Returns Core's user object directly

**Success response:**
```json
{
  "success": true,
  "data": {
    "user": {
      "id": "abc123",
      "email": "user@example.com",
      "name": "John",
      "is_verified": true,
      "created_at": "2025-01-01T00:00:00",
      "last_login_at": "2025-06-09T10:00:00"
    }
  }
}
```

**Error responses:**

| Status | Reason |
|---|---|
| 401 | Missing access token |
| 401 | Token blacklisted or expired |
| 404 | User not found in Core |

---

## Standard Response Shape

Every response from auth follows this structure:

```json
{
  "success": true | false,
  "data": { ... } | null,
  "error_message": "" | "human readable error"
}
```

On errors, `success` is `false`, `data` is `null`, and `error_message` explains what went wrong.

---

## Relevant Files

- `app/routes/user_routes.py` — All route definitions
- `app/handlers/otp_handler.py` — `handle_request_otp`, `handle_verify_otp`
- `app/handlers/auth_handler.py` — `handle_refresh`, `handle_logout`
- `app/utils/core_client.py` — `call_core(method, path, **kwargs)` — HTTP proxy to Core
- `app/utils/response.py` — `success_response()`, `error_response()`
