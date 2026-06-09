# 02 — JWT and Token System

> Auth issues two tokens on every successful login: a short-lived VTM (access token) and a long-lived RTM (refresh token). Both are AES-encrypted before being placed in the JWT, and both live in httpOnly cookies.

← Back to [[00 - Auth Service Hub]]
← Requires: [[03 - OTP Flow]]
→ Next: [[04 - Middleware and Auth Guards]]

---

## Two Token Types

| Token | Cookie Name | Lifespan (beta) | Lifespan (prod) | Purpose |
|---|---|---|---|---|
| **VTM** (Verify Token Meta) | `access_token` | 30 minutes | 15 minutes | Authenticates every API request |
| **RTM** (Refresh Token Meta) | `refresh_token` | 30 days | 30 days | Issues new VTMs without re-login |

---

## Why Tokens Are Encrypted Inside the JWT

A standard JWT has a base64-encoded payload that anyone can decode. To prevent exposing `user_id` and internal UUIDs in the browser, the claims are AES-256-GCM encrypted before being put inside the JWT.

```
What goes into the cookie:

eyJ...  ← JWT (signed with ACCESS_SECRET)
         └─ payload.data = AES-GCM-encrypted blob
                            └─ { user_id, access_uuid, expires_at }
```

The AES key is derived from the `SECRET_KEY` env var:
```python
key = MD5(SECRET_KEY).hexdigest().encode()  # 32-byte hex string
```

This means even if someone extracts the JWT, they cannot read the claims without the server's `SECRET_KEY`.

---

## Token Creation Flow

```
verify_otp succeeds
  │
  ▼
create_tokens(user_id)
  │
  ├── generate access_uuid (UUID4)
  ├── generate refresh_uuid (UUID4)
  │
  ├── VTM claims = { user_id, access_uuid, expires_at }
  │     └── AES-encrypt claims → encrypted_blob
  │     └── JWT sign { data: encrypted_blob } with ACCESS_SECRET
  │     └── → access_token string
  │
  └── RTM claims = { user_id, refresh_uuid, expires_at }
        └── AES-encrypt claims → encrypted_blob
        └── JWT sign { data: encrypted_blob } with ACCESS_SECRET
        └── → refresh_token string
```

---

## AES-256-GCM Encryption

```python
# Key derivation
key = MD5(SECRET_KEY).hexdigest().encode()  # 32 bytes

# Encrypt
nonce = os.urandom(12)                      # 12-byte random nonce
cipher = AESGCM(key)
ciphertext = cipher.encrypt(nonce, plaintext_bytes, None)
result = base64(nonce + ciphertext)         # nonce prepended for decryption

# Decrypt
raw = base64decode(encrypted_string)
nonce = raw[:12]
ciphertext = raw[12:]
plaintext = cipher.decrypt(nonce, ciphertext, None)
```

The nonce is unique per encryption so two identical payloads produce different ciphertexts.

---

## Cookie Settings

Both cookies are set with security-first defaults:

| Setting | Value | Why |
|---|---|---|
| `httpOnly` | True | JavaScript cannot read the cookie |
| `secure` | True in prod | Cookie only sent over HTTPS |
| `samesite` | `strict` | Not sent on cross-site requests |
| `path` | `/` | Available on all routes |
| `max_age` | Token TTL in seconds | Browser auto-expires the cookie |

In beta (`SERVER_ENVIRONMENT=beta`) the `secure` flag is set to `False` so the cookie works over plain HTTP localhost.

---

## Token Extraction (Middleware)

When a protected route receives a request:

```
1. Read cookie: request.cookies.get("access_token")
2. JWT decode with ACCESS_SECRET → get payload["data"]
3. AES decrypt payload["data"] → get { user_id, access_uuid, expires_at }
4. Check Redis: is access_uuid blacklisted?
5. If any step fails → return 401
6. If all pass → attach user_id to request.state for the handler to use
```

---

## Token Rotation on Refresh

On `POST /user/refresh`:

```
RTM cookie read
  │
  ▼
RTM decrypted and verified
  │
  ▼
Redis check: is refresh_uuid blacklisted?
  │
  ▼
New VTM created (new access_uuid, new expiry)
  │
  ▼
New access_token cookie set
  │
  ▼
RTM cookie unchanged (refresh token stays the same until logout)
```

The refresh token is **not rotated** on every refresh. It stays valid until its 30-day expiry or until logout explicitly blacklists it.

---

## Relevant Files

- `app/utils/token_utils.py` — `create_tokens()`, `extract_vtm()`, `extract_rtm()`
- `app/utils/crypto.py` — `aes_encrypt()`, `aes_decrypt()`
- `app/utils/cookies.py` — `set_auth_cookies()`, `clear_auth_cookies()`
- `app/constants/token_constants.py` — Cookie names, TTL values, claim key names
- `app/config/settings.py` — `ACCESS_SECRET`, `SECRET_KEY`, `SERVER_ENVIRONMENT`
