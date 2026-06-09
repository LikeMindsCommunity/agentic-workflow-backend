# 03 — OTP Service (Gupshup)

> How OTPs are sent and verified using the Gupshup two-factor authentication API. Core is the only service that talks to Gupshup directly.

← Back to [[00 - Core Service Hub]]
→ Next: [[02 - User Model and Repository]]

---

## Gupshup API

Gupshup is the SMS/OTP gateway. Core calls two endpoints on it:

| Action | Gupshup Endpoint | Called By |
|---|---|---|
| Send OTP | `GET /apps/TwoFactorAuth/incoming.php` with `method=sendOTP` | `handle_send_otp()` |
| Verify OTP | `GET /apps/TwoFactorAuth/incoming.php` with `method=verifyOTP` | `handle_verify_otp()` |

Base URL:
```
https://enterprise.smsgupshup.com/apps/TwoFactorAuth/incoming.php
```

---

## Sending an OTP

```
Request to Gupshup:
  GET /apps/TwoFactorAuth/incoming.php
  params:
    method=sendOTP
    send_to={email}
    msg_type=TEXT
    auth_scheme=plain
    userid={EMAIL_GHUPSHAP_KEY}
    password={EMAIL_GHUPSHAP_KEY}
    msg=Your OTP is %%OTP%%
    v=1.1
    format=text

Gupshup Response:
  "success|<otp_session_id>"   → OTP sent
  "error|..."                  → failure
```

The response is plain text, not JSON. Core parses it by splitting on `|` and checking if the first part is `"success"`.

---

## Verifying an OTP

```
Request to Gupshup:
  GET /apps/TwoFactorAuth/incoming.php
  params:
    method=verifyOTP
    send_to={email}
    otp={user_entered_code}
    userid={EMAIL_GHUPSHAP_KEY}
    password={EMAIL_GHUPSHAP_KEY}
    v=1.1
    format=text

Gupshup Response:
  "success|..."   → OTP correct and not expired
  "error|..."     → wrong OTP or expired
```

---

## Response Parsing

```python
response_text = "success|abc123"
parts = response_text.split("|")
ok = parts[0].lower() == "success"
```

If `ok` is True, OTP was sent / verified successfully. Anything else is treated as failure.

---

## API Key

The Gupshup key is stored in the env var `EMAIL_GHUPSHAP_KEY` (note spelling: GHUPSHAP, not GUPSHUP — matches the key name from the reference Go backend).

It is used as both the `userid` and `password` parameters in every Gupshup request.

**Current value (from reference backend):**
```
EMAIL_GHUPSHAP_KEY=341707ec53b5ecb822862aff20681358
```

---

## Error Handling

| Scenario | Core Response |
|---|---|
| Gupshup returns `"error|..."` | 400 with `"Failed to send OTP"` |
| Gupshup API is unreachable (timeout, network error) | 500 with `"Failed to send OTP"` |
| OTP verify fails (`"error|..."`) | 400 with `"Invalid or expired OTP"` |
| OTP verify API is unreachable | 500 with `"OTP verification failed"` |

---

## Relevant Files

- `app/utils/otp_service.py`
  - `send_otp(email)` → `bool` — returns True if Gupshup accepted the request
  - `verify_otp(email, otp)` → `bool` — returns True if OTP is correct
- `app/config/settings.py` — `EMAIL_GHUPSHAP_KEY`
- `core/.env` — actual key value for local development
