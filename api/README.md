# Skill API (FastAPI + Claude Agent SDK + SSE)

Exposes Claude Code skills (`/platform-kb`, `/generate-document`, etc.) over HTTP. Each session is a long-lived `ClaudeSDKClient`; user replies and tool/text events flow through SSE.

## Install

```bash
pip install -r requirements.txt
```

## Run

```bash
python -m api.main
# or with reload:
API_RELOAD=1 python -m api.main
```

Defaults: `0.0.0.0:8000`. Override with `API_HOST` / `API_PORT`. Pick the model with `CLAUDE_AGENT_MODEL` (passed straight to `ClaudeAgentOptions`).

## Routes

| Method | Path | Description |
|---|---|---|
| `POST` | `/sessions` | Multipart: `skill`, `prompt`, `files[]`. Spawns the agent, returns `session_id` + URLs. |
| `GET` | `/sessions/{id}` | State snapshot (`status`, `turns`, `last_pending_question`, `error`). |
| `GET` | `/sessions/{id}/stream` | SSE stream — replays past events then streams live. Events: `turn_start`, `assistant_text`, `tool_use`, `tool_result`, `thinking`, `result`, `turn_end`, `error`, `session_closed`. |
| `POST` | `/sessions/{id}/messages` | JSON `{text}` or multipart `text` + `files[]`. Forwards reply into the running agent. |
| `POST` | `/sessions/{id}/done` | Stop the agent loop (idempotent). |
| `GET` | `/sessions/{id}/result?format=zip\|json` | Fetch the KB output. `zip` streams a download; `json` returns `{files:[{path,content}]}`. |
| `DELETE` | `/sessions/{id}` | Stop + delete files. |

`status` transitions: `running → awaiting_user → running → ... → done|closed|error`.

## End-to-end (curl)

```bash
# 1. Start
curl -X POST http://localhost:8000/sessions \
  -F "skill=platform-kb" \
  -F "prompt=Acme IVR builder; focus on node types and transitions." \
  -F "files=@flow1.json" \
  -F "files=@flow2.json" \
  -F "files=@acme-docs.pdf"
# → { "session_id": "7f3a...", "stream_url": ".../stream", ... }

# 2. Watch live (separate terminal)
curl -N http://localhost:8000/sessions/7f3a.../stream

# 3. Reply to gap questions
curl -X POST http://localhost:8000/sessions/7f3a.../messages \
  -H "Content-Type: application/json" \
  -d '{"text":"G1: 6 node types total — also condition + webhook. G2: session-scoped only."}'

# 4. Or upload more files mid-session
curl -X POST http://localhost:8000/sessions/7f3a.../messages \
  -F "text=Postman collection answers G3 and G4." \
  -F "files=@acme-postman.json"

# 5. Finish
curl -X POST http://localhost:8000/sessions/7f3a.../messages \
  -H "Content-Type: application/json" \
  -d '{"text":"done"}'

# 6. Pull result
curl -OJ http://localhost:8000/sessions/7f3a.../result?format=zip
# or:
curl http://localhost:8000/sessions/7f3a.../result?format=json | jq

# 7. Clean up
curl -X DELETE http://localhost:8000/sessions/7f3a...
```

## SSE event shape

Each SSE frame uses the event-type as the SSE `event:` field, the JSON payload as `data:`. Examples:

```
event: turn_start
data: {"turn":1,"user_text":"/platform-kb inputs/sessions/7f3a..."}

event: tool_use
data: {"id":"toolu_...","name":"Read","input":{"file_path":".../flow1.json"}}

event: assistant_text
data: {"text":"I found 6 knowledge gaps..."}

event: turn_end
data: {"turn":1,"pending_question":"I found 6 knowledge gaps..."}
```

Browser:

```js
const es = new EventSource(`/sessions/${id}/stream`);
es.addEventListener("assistant_text", e => append(JSON.parse(e.data).text));
es.addEventListener("tool_use",       e => showCall(JSON.parse(e.data)));
es.addEventListener("turn_end",       e => enableInput(JSON.parse(e.data).pending_question));
```

The stream replays the full event log on connect, so reconnects don't lose context.

## File layout

```
inputs/sessions/<sid>/        # uploaded files
outputs/sessions/<sid>/kb/    # generated KB (the value passed to the skill)
```

The first user message sent to the agent is:
```
/<skill> inputs/sessions/<sid>

Save all output files to outputs/sessions/<sid>/kb (override the default output path).

Additional context from the user:
<your prompt>
```

## Notes

- One asyncio task per session, one `ClaudeSDKClient` per task. No multi-worker support yet — run a single uvicorn worker.
- Idle sessions are swept after 6h (`SESSION_TTL_SECONDS` in `sessions.py`).
- The agent uses `bypassPermissions` and the same allowed-tool set as `claude_agent/cli.py`. Keep that in mind for the deployment environment.
