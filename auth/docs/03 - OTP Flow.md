# 03 — OTP Flow

> End-to-end walk-through of how a user goes from entering their email to holding a valid session. Auth orchestrates the flow; Core and Gupshup do the actual OTP work.

← Back to [[00 - Auth Service Hub]]
→ Next: [[02 - JWT and Token System]]

---

## Full Flow Diagram

```
User enters email
  │
  ▼
POST /user/otp  (Auth)
  │
  ├── Redis: attempts(email) >= 5? → 429 Too Many Requests
  │
  └── call Core POST /user/otp
        │
        ├── Core: user exists? No → create user record in MongoDB
        └── Core: call Gupshup API → send OTP SMS/email
              │
              └── Gupshup responds "success|..." → Core returns 200
  │
  ▼
User receives OTP code
  │
  ▼
POST /user/otp/verify  (Auth)
  │
  ├── Redis: attempts(email) >= 5? → 429
  │
  └── call Core POST /user/otp/verify
        │
        ├── Core: call Gupshup verify API
        │
        ├── Wrong OTP → Core returns failure
        │     Auth: Redis.increment_attempts(email)
        │     Auth: return 400
        │
        └── Correct OTP → Core: mark user.is_verified=True, set last_login_at
              Core returns { user_id: "abc123" }
              Auth: Redis.reset_attempts(email)
              Auth: create_tokens(user_id) → VTM + RTM
              Auth: set_auth_cookies(response, ...)
              Auth: return 200 with user_id
  │
  ▼
Frontend now holds access_token + refresh_token cookies
```

---

## Rate Limiting Detail

The rate limit is checked in **both** `request_otp` and `verify_otp`:

- Key in Redis: `otp_attempts:{email}`
- Max attempts: **5**
- Block window: **30 minutes** (1800 seconds)
- Counter increments only on **failed verifications**, not on OTP requests
- Counter resets to 0 on **successful verification**

This means a user can request multiple OTPs (to retry delivery) without hitting the limit. The limit only triggers after 5 wrong codes.

---

## What Auth Sends to Core

**Request OTP:**
```python
POST /user/otp
Body: { "email": "user@example.com" }
```

**Verify OTP:**
```python
POST /user/otp/verify
Body: { "email": "user@example.com", "otp": "123456" }
```

Auth does not add any headers for these two routes — they are unauthenticated calls to Core.

---

## What Core Returns on Successful Verify

```json
{
  "success": true,
  "data": { "user_id": "664f2a..." },
  "error_message": ""
}
```

Auth extracts `data.user_id` and uses it to create both tokens:

```python
user_id = data["data"]["user_id"]
vtm, rtm = create_tokens(user_id)
```

---

## New User vs Returning User

Auth does not know or care whether the user is new. Core handles this transparently:

| Condition | Core Behaviour |
|---|---|
| Email not in DB | Creates user record with `is_verified=False` before sending OTP |
| Email exists, not verified | Sends OTP, marks verified on success |
| Email exists, already verified | Sends OTP, updates `last_login_at` on success |

From Auth's perspective the flow is identical in all three cases.

---

## Relevant Files

- `app/handlers/otp_handler.py` — `handle_request_otp()`, `handle_verify_otp()`
- `app/utils/redis_client.py` — `get_otp_attempts()`, `increment_otp_attempts()`, `reset_otp_attempts()`
- `app/utils/core_client.py` — `call_core(method, path, **kwargs)`
- `app/utils/token_utils.py` — `create_tokens(user_id)`
- `app/utils/cookies.py` — `set_auth_cookies(response, ...)`
