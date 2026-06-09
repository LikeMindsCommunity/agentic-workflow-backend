# Core Service — Hub

> The **central node** for understanding the core service. Core owns the database, user records, and OTP communication with Gupshup. It is never called directly by the frontend — only the auth service calls it.

---

## What Does This Service Do?

Core is the only service allowed to touch MongoDB. It handles user creation, OTP delivery and verification, and user profile reads. Auth proxies every user-facing request through here.

| Responsibility | Handled Here | Handled Elsewhere |
|---|---|---|
| MongoDB read / write | Yes (Beanie ODM) | — |
| Sending OTP via Gupshup | Yes | — |
| Verifying OTP with Gupshup | Yes | — |
| Creating user on first login | Yes | — |
| JWT creation | No | Auth service |
| Cookie management | No | Auth service |
| Rate limiting | No | Auth service (Redis) |

---

## The Big Picture Flow

```
Auth Service
  │
  ├── POST /user/otp
  │     Core: find or create user in MongoDB
  │     Core: call Gupshup → send OTP
  │
  ├── POST /user/otp/verify
  │     Core: call Gupshup verify API
  │     Correct → mark user.is_verified=True, update last_login_at
  │     Return { user_id }
  │
  └── GET /user/  (X-User-Id header)
        Core: find user by ID in MongoDB
        Return full user object
```

---

## Explore Each Topic

- [[01 - Routes and Endpoints]] — Every route, request shape, and response shape
- [[02 - User Model and Repository]] — MongoDB schema, Beanie document, and data access methods
- [[03 - OTP Service (Gupshup)]] — How OTPs are sent and verified via Gupshup API
- [[04 - Database Setup]] — How Beanie and Motor connect to MongoDB at startup
- [[05 - Running and Testing]] — How to start the service and test every endpoint

---

## Key Systems This Talks To

| System | Purpose |
|---|---|
| **MongoDB** | Stores all user records |
| **Gupshup** | External OTP delivery and verification API |
| **Auth Service** | The only caller — forwards all requests with auth context stripped |
