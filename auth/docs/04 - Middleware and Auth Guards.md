# 04 — Middleware and Auth Guards

> How protected routes verify the caller's identity before doing any real work. Auth has two guard functions — one for the access token (VTM) and one for the refresh token (RTM).

← Back to [[00 - Auth Service Hub]]
← Requires: [[02 - JWT and Token System]]

---

## Two Guard Functions

Auth does not use FastAPI middleware for token checks. Instead each route calls a guard function directly and returns early if it fails. This makes the auth requirement explicit and easy to read in the route file.

| Guard | Cookie Read | Used By |
|---|---|---|
| `vtm_required(request)` | `access_token` | `/user`, all protected routes |
| `rtm_required(request)` | `refresh_token` | `/user/refresh` |

Both functions return a `(meta, error)` tuple. If `error` is not `None` the route returns it immediately:

```python
vtm, err = await vtm_required(request)
if err:
    return err   # JSONResponse with 401
```

---

## vtm_required — Step by Step

```
1. Read cookie: request.cookies.get("access_token")
   └── Missing? → return 401 "Missing access token"

2. JWT decode with ACCESS_SECRET
   └── Expired or bad signature? → return 401 "Invalid VTM"

3. AES decrypt payload["data"]
   └── Decryption fails? → return 401 "Invalid VTM"

4. Parse claims → { user_id, access_uuid, expires_at }

5. Redis: EXISTS access_uuid
   └── Key found? → return 401 "Device logged out! Please login again"

6. Return (VerifyTokenMeta(user_id, access_uuid), None)
```

The handler then reads `vtm.user_id` to know who is making the request.

---

## rtm_required — Step by Step

```
1. Read cookie: request.cookies.get("refresh_token")
   └── Missing? → return 401 "Missing refresh token"

2. JWT decode with ACCESS_SECRET

3. AES decrypt payload["data"]

4. Parse claims → { user_id, refresh_uuid, expires_at }

5. Redis: EXISTS refresh_uuid
   └── Key found? → return 401 "Invalid RTM"

6. Return (RefreshTokenMeta(user_id, refresh_uuid, expires_at), None)
```

---

## CORS Middleware

Configured globally in `main.py`:

```python
CORSMiddleware(
    allow_origins=["http://localhost:3000", "http://localhost:5173"],
    allow_credentials=True,   # Required — cookies need this to be True
    allow_methods=["*"],
    allow_headers=["*"],
)
```

`allow_credentials=True` is critical. Without it, the browser strips the `Set-Cookie` header and cookies never save.

The `CORS_ALLOWED_ORIGINS` env var controls which origins are allowed. In production this must be set to the exact frontend domain.

---

## Error Response Format

All guard failures return the same shape:

```json
{
  "success": false,
  "data": null,
  "error_message": "Device logged out! Please login again"
}
```

HTTP status is always `401` for auth failures.

---

## Relevant Files

- `app/middleware/auth_middleware.py` — `vtm_required()`, `rtm_required()`
- `app/utils/token_utils.py` — `extract_vtm()`, `extract_rtm()`
- `app/utils/redis_client.py` — `is_vtm_blacklisted()`, `is_rtm_blacklisted()`
- `app/utils/response.py` — `error_response()`
- `main.py` — CORS middleware setup
