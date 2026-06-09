# 05 — Redis Rate Limiting and Blacklisting

> Redis serves two purposes in auth: throttling OTP attempts to prevent abuse, and blacklisting token UUIDs so logged-out tokens are rejected immediately even before they expire.

← Back to [[00 - Auth Service Hub]]
← Requires: [[03 - OTP Flow]]

---

## Two Redis Use Cases

| Use Case | Key Pattern | TTL | Set When |
|---|---|---|---|
| OTP attempt counter | `otp_attempts:{email}` | 1800s (30 min) | First failed OTP verify |
| Access token blacklist | `{access_uuid}` | Remaining token TTL | Logout |
| Refresh token blacklist | `{refresh_uuid}` | Remaining token TTL | Logout |

---

## OTP Rate Limiting

**Key:** `otp_attempts:{email}` (e.g. `otp_attempts:user@example.com`)

**Flow:**
```
On /user/otp or /user/otp/verify:
  GET otp_attempts:{email}
    └── value >= 5 → block, return 429

On failed OTP verify:
  INCR otp_attempts:{email}
  If key did not exist before: SET EX 1800  (start the 30-min window)

On successful OTP verify:
  DEL otp_attempts:{email}  (reset the counter)
```

The 30-minute window starts from the **first failed attempt**, not from the first OTP request. A user who enters the wrong code at 10:00 has until 10:30 to succeed before being locked out.

---

## Token Blacklisting on Logout

When `POST /user/logout` is called:

```python
# Extract UUID and expiry from each token
access_uuid, access_ttl = extract_from_vtm(access_token)
refresh_uuid, refresh_ttl = extract_from_rtm(refresh_token)

# Write to Redis with the token's remaining life as TTL
SETEX {access_uuid}  {access_ttl_seconds}  "blacklisted"
SETEX {refresh_uuid} {refresh_ttl_seconds} "blacklisted"
```

Using the remaining TTL (not the full token lifetime) keeps Redis lean — keys auto-expire exactly when the token would have expired naturally. There is no need to clean them up manually.

---

## Why UUID Not Token Hash

Blacklisting the UUID (a small 36-char string) instead of the full encrypted token avoids storing a large value and makes the Redis lookup O(1) with just a key existence check (`EXISTS`).

---

## Redis Connection

```python
# Redis DSN format: host:port
# From env: REDIS_DSN=localhost:6379

host, port = REDIS_DSN.split(":")
redis_client = aioredis.Redis(
    host=host,
    port=int(port),
    password=REDIS_PASSWORD or None,
    decode_responses=True,
)
```

If Redis is unavailable, the service starts but any route touching Redis will fail. Token blacklisting silently degrades — logged-out tokens remain valid until natural expiry.

---

## Relevant Files

- `app/utils/redis_client.py`
  - `get_otp_attempts(email)` — returns current attempt count
  - `increment_otp_attempts(email)` — increments counter, sets 30-min TTL on first call
  - `reset_otp_attempts(email)` — deletes the key
  - `blacklist_tokens(vtm_meta, rtm_meta)` — sets both UUID keys with TTL
  - `is_vtm_blacklisted(uuid)` — returns True if key exists
  - `is_rtm_blacklisted(uuid)` — returns True if key exists
- `app/config/settings.py` — `REDIS_DSN`, `REDIS_PASSWORD`
