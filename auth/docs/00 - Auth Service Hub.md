# Auth Service — Hub

> The **central node** for understanding the auth service. It owns JWT lifecycle, OTP flow, token rotation, and cookie management. It never touches MongoDB directly — all user data comes from Core over HTTP.

---

## What Does This Service Do?

The auth service sits between the frontend and the core service. It handles everything related to identity — issuing tokens, verifying them on every request, rotating them on refresh, and invalidating them on logout.

| Responsibility | Handled Here | Handled Elsewhere |
|---|---|---|
| OTP rate limiting | Yes (Redis) | — |
| Sending OTP to user | No | Core → Gupshup |
| JWT creation and signing | Yes | — |
| Cookie setting | Yes | — |
| User data storage | No | Core → MongoDB |
| Token blacklisting on logout | Yes (Redis) | — |

---

## The Big Picture Flow

```
Frontend
  │
  ▼
POST /user/otp
  Rate-limit check (Redis) → proxy to Core POST /user/otp
  │
  ▼
POST /user/otp/verify
  Rate-limit check → proxy to Core POST /user/otp/verify
  Core returns user_id
  Auth creates VTM + RTM tokens
  Sets httpOnly cookies on response
  │
  ▼
GET /user  (or any protected route)
  VTM cookie extracted → AES-decrypted → JWT verified
  X-User-Id forwarded to Core → user data returned
  │
  ▼
POST /user/refresh
  RTM cookie extracted and verified
  New VTM issued, access cookie rotated
  │
  ▼
POST /user/logout
  VTM + RTM UUIDs blacklisted in Redis
  Both cookies cleared
```

---

## Explore Each Topic

- [[01 - Routes and Endpoints]] — Every route, method, auth requirement, and what it does
- [[02 - JWT and Token System]] — How VTM and RTM tokens are created, encrypted, and verified
- [[03 - OTP Flow]] — Step-by-step: request OTP, verify OTP, get tokens
- [[04 - Middleware and Auth Guards]] — How protected routes validate the access token
- [[05 - Redis Rate Limiting and Blacklisting]] — OTP throttle and logout invalidation
- [[06 - Running and Testing]] — How to start the service and test every endpoint

---

## Key Systems This Talks To

| System | Purpose |
|---|---|
| **Core Service** (port 8001) | Sends OTP, verifies OTP, fetches user profile |
| **Redis** | Token blacklist + OTP rate limiting |
| **Frontend** | Receives httpOnly cookies, sends them on every request |
