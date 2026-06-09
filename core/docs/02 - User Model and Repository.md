# 02 — User Model and Repository

> How user data is structured in MongoDB, what Beanie does for us, and the exact functions available for reading and writing user records.

← Back to [[00 - Core Service Hub]]
← Requires: [[04 - Database Setup]]
→ Next: [[03 - OTP Service (Gupshup)]]

---

## MongoDB Collection

Collection name: **`users`**

Every document in this collection maps to a `User` Beanie document object in Python.

---

## User Schema

| Field | Type | Default | Description |
|---|---|---|---|
| `_id` | ObjectId | Auto | MongoDB document ID |
| `email` | str | Required | User's email address — used as login identifier |
| `name` | str | `""` | Display name — not collected at signup |
| `kind` | str | `""` | User type — reserved for future use |
| `tenant_id` | str | `""` | Multi-tenant identifier — reserved for future use |
| `password_hash` | str | `""` | Not used — auth is OTP only |
| `google_sub` | str | `""` | Google OAuth subject — reserved for future use |
| `is_verified` | bool | `False` | Set to True after first successful OTP verification |
| `created_at` | datetime | utcnow | When the user record was first created |
| `updated_at` | datetime | utcnow | Last modification timestamp |
| `is_deleted` | bool | `False` | Soft delete flag |
| `last_login_at` | datetime | `None` | Updated on every successful OTP verify |
| `connectors` | list | `[]` | Reserved for third-party integrations |

---

## Python Model (Beanie Document)

```python
class User(Document):
    email: str
    name: str = ""
    kind: str = ""
    tenant_id: str = ""
    is_verified: bool = False
    created_at: datetime
    updated_at: datetime
    is_deleted: bool = False
    last_login_at: Optional[datetime] = None

    class Settings:
        collection = "users"
```

Beanie wraps Motor (async MongoDB driver). Every instance of `User` can be saved, updated, or queried using async calls with no raw pymongo needed.

---

## Repository Functions

All database access goes through `user_repository.py`. No handler talks to MongoDB directly.

### `find_by_email(email: str) → Optional[User]`

```python
User.find_one(User.email == email)
```

Used before sending OTP to check if the user exists already.

---

### `find_by_id(user_id: str) → Optional[User]`

```python
User.get(PydanticObjectId(user_id))
```

Used by `GET /user/` to fetch the profile by the ID extracted from the JWT.

---

### `create(email: str) → User`

```python
user = User(
    email=email,
    created_at=datetime.utcnow(),
    updated_at=datetime.utcnow(),
)
await user.insert()
```

Called when OTP is requested for an email that has never been seen before.

---

### `set_verified(user: User) → None`

```python
await user.set({"is_verified": True, "updated_at": datetime.utcnow()})
```

Called once — on the user's first successful OTP verification.

---

### `set_last_login(user: User) → None`

```python
await user.set({"last_login_at": datetime.utcnow(), "updated_at": datetime.utcnow()})
```

Called on every successful OTP verification including subsequent logins.

---

## New User vs Returning User Handling

```
POST /user/otp received
  │
  └── find_by_email(email)
        │
        ├── None → create(email)   [is_verified=False]
        └── exists → do nothing

POST /user/otp/verify — OTP correct
  │
  └── find_by_email(email)
        │
        ├── user.is_verified == False → set_verified(user)
        └── always → set_last_login(user)
        └── return { user_id: str(user.id) }
```

---

## Relevant Files

- `app/models/user.py` — `User` Beanie document class
- `app/repositories/user_repository.py` — All read/write functions
- `app/database/mongodb.py` — Beanie initialisation (registers the User model)
