# Skill API · Console (frontend)

React + Vite + Tailwind v4 client for the FastAPI Skill API in [`../api/`](../api/).

## Run

```bash
cd frontend
npm install
npm run dev
# → http://localhost:5173
```

In a separate terminal, start the API:

```bash
cd ..
source venv/bin/activate
python -m api.main
# → http://localhost:8000
```

The Vite dev server proxies `/api/*` to `http://localhost:8000`, so you can also point the in-app "API base" field at `/api` if you want same-origin requests instead of CORS.

## What it does

- **Start session**: pick a skill (`platform-kb`, `generate-document`, or any custom one), optional prompt, drop in source files. Posts multipart to `POST /sessions`.
- **Live feed**: subscribes to `GET /sessions/{id}/stream` (SSE) and renders each event type with its own color and shape — assistant text, tool calls, tool results, thinking, turn boundaries.
- **Status pill** flips between `running` (agent working) and `awaiting reply` (turn ended).
- **Reply box** sends to `POST /sessions/{id}/messages` as JSON. Attach extra files to send multipart instead.
- **Result tab** fetches `GET /sessions/{id}/result?format=json`, renders a tree + content viewer. **Download zip** button hits `?format=zip`.
- **Delete** cleans up uploaded + generated files via `DELETE /sessions/{id}`.

## File layout

```
frontend/
  index.html
  vite.config.js
  src/
    main.jsx          — entry
    App.jsx           — top-level shell
    index.css         — tailwind import
    lib/api.js        — fetch wrappers + SSE URL
    hooks/useSession.js — owns the EventSource subscription
    components/
      SessionForm.jsx
      SessionView.jsx
      StatusPill.jsx
      EventFeed.jsx     — filterable, auto-scrolls
      EventCard.jsx     — per-type styling
      MessageInput.jsx  — reply + file attach, ⌘/Ctrl+Enter to send
      ResultViewer.jsx  — KB file tree + viewer
```

## Build

```bash
npm run build       # → dist/
npm run preview
```

The built `dist/` is a static bundle — serve it from any static host or behind the FastAPI app via `app.mount`.
