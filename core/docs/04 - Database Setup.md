# 04 — Database Setup

> How MongoDB is connected at startup, how Beanie is initialised, and what happens if the connection fails.

← Back to [[00 - Core Service Hub]]
→ Feeds into: [[02 - User Model and Repository]]

---

## Stack

| Layer | Library | Purpose |
|---|---|---|
| Driver | **Motor** | Async MongoDB driver for Python |
| ODM | **Beanie** | Document mapper on top of Motor — gives typed models and query helpers |
| Connection string | `MONGO_URI` env var | Points to local or Atlas instance |

---

## Startup Sequence

FastAPI's lifespan context manager runs `init_db()` before the app accepts any requests:

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()   # runs before first request
    yield
    await close_db()  # runs on shutdown
```

`init_db()`:
```python
_client = AsyncIOMotorClient(MONGO_URI)
await init_beanie(
    database=_client[MONGO_DB_NAME],
    document_models=[User],
)
```

Beanie scans the `User` model, creates indexes if they don't exist, and makes the collection ready for async queries.

---

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `MONGO_URI` | `mongodb://localhost:27017` | Full MongoDB connection string |
| `MONGO_DB_NAME` | `skill_db` | Database name inside MongoDB |

For local development both defaults work with a standard MongoDB install.

For production (MongoDB Atlas):
```
MONGO_URI=mongodb+srv://username:password@cluster.mongodb.net/?retryWrites=true&w=majority
MONGO_DB_NAME=skill_db
```

---

## Collections Created

Beanie creates collections automatically when the first document is inserted.

| Collection | Model | Created On |
|---|---|---|
| `users` | `User` | First OTP request for a new email |

---

## Graceful Shutdown

`close_db()` closes the Motor client connection cleanly:

```python
async def close_db():
    if _client:
        _client.close()
```

This runs automatically when uvicorn receives a shutdown signal (Ctrl+C or SIGTERM).

---

## Connection Failure

If MongoDB is not running when core starts, `init_beanie()` will raise an exception and the process will exit with a traceback. There is no retry logic — start MongoDB before starting core.

To verify MongoDB is running:
```bash
mongosh --eval "db.runCommand({ping: 1})"
# or
brew services list | grep mongodb
```

---

## Relevant Files

- `app/database/mongodb.py` — `init_db()`, `close_db()`
- `app/models/user.py` — `User` document class registered with Beanie
- `app/config/settings.py` — `MONGO_URI`, `MONGO_DB_NAME`
- `core/.env` — actual values for local development
- `main.py` — lifespan context that calls `init_db` / `close_db`
