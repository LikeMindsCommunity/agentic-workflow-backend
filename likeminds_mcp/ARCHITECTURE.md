# likeminds_mcp — architecture

How the server works internally. For setup/usage see [README.md](./README.md); this
doc is the design, the flow, and the reasoning behind the non-obvious choices.

## What it is, in one line

A local MCP server that lets a Claude client (Claude Code or Desktop) **run a
private `.claude/` skill without seeing the skill's prompt** — the skill executes
server-side inside a real `claude -p` process, pausing to ask the user questions and
returning finished files by reference.

## Big-picture flow

```
Claude client ──run_skill──▶  likeminds server  ──spawns──▶  claude -p  (runs the skill)
      ▲                            │  (background task)          │
      │◀──── poll / questions ─────┤                             │ reads inputs, writes output
      │────── answers ─────────────▶  ──resume──▶  claude -p  ◀──┘
      │◀──── result_id (done) ──────┘         (same session, next turn)
```

1. **Kick off** — client calls `run_skill(skill, files, context)`. The server makes a
  private sandbox, drops the inputs in, starts a background task, and returns a
   `session_id` immediately (never blocks for a whole turn).
2. **Run** — the task spawns `claude -p`, telling it to run the skill, read inputs
  from the sandbox, and write the deliverable to the sandbox. The skill prompt stays
   server-side.
3. **Poll** — a turn takes minutes, so the client keeps calling with just the
  `session_id` and gets a live `progress` line until the state changes.
4. **Ask (if needed)** — the skill writes an `<<<LM_ASK>>>` marker + a question and
  stops. The server surfaces the question; the user answers; the server **resumes
   the same Claude session** with that answer. Repeats as needed.
5. **Finish** — the skill writes `<<<LM_DONE>>>`. The server copies the output files
  to `outputs/mcp/<result_id>/`, purges the sandbox, and returns `status: done`.

## Components


| Module           | Responsibility                                                                                                                                                   |
| ---------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `server.py`      | FastMCP HTTP server + the 3 tools (`run_skill` / `upload_file` / `list_skills`); the background driver `_drive`; output harvest/promote; auth config; long-poll. |
| `engine.py`      | Runs ONE turn: builds the `claude -p` argv, spawns it, reads the stream-json, parses the signal markers.                                                         |
| `harness.py`     | The system-prompt append that binds a skill's I/O edges to the engine (inputs dir / output dir / markers).                                                       |
| `sessions.py`    | Lightweight in-process session records + sandbox/transcript purge + record GC.                                                                                   |
| `registry.py`    | Indexes `.claude/commands/*.md` and `.claude/skills/*/SKILL.md` so any skill is runnable.                                                                        |
| `config.py`      | Paths, host/port, CLI binary, model, markers, safety bounds.                                                                                                     |
| `__main__.py`    | `python -m likeminds_mcp` entrypoint (streamable-HTTP).                                                                                                          |
| `test_client.py` | Terminal client to drive a skill end-to-end without a Claude client.                                                                                             |


## Session lifecycle (state machine)

```
            ┌───────────────────────────────────────┐
            ▼                                         │ (user replies)
  running ──┬──▶ need_input ──────────────────────────┘
            │        │ (no reply within REPLY_TIMEOUT)
            │        ▼
            ├──▶ done      (LM_DONE → harvest → purge)
            └──▶ error     (crash / turn timeout / nudged out)
```

- `running` — a turn is executing; client should poll.
- `need_input` — the skill asked; relay the `questions`, then call again with
`session_id` + `response`.
- `done` — deliverable in `outputs/mcp/<result_id>/`.
- `error` — the run failed (and was purged).

`run_skill` **long-polls**: each call waits up to `POLL_WAIT` (~4s) for the state to
change, then returns a snapshot. The background `_drive` task owns the real work; the
tool handlers only read `sess.*` state to answer polls.

## A turn, in detail (`engine.run_turn`)

1. Build argv (`_build_argv`): `claude -p  --output-format stream-json
  --verbose --permission-mode bypassPermissions --append-system-prompt 
   --mcp-config  --strict-mcp-config --model `plus` --session-id `(turn 1) or`--resume ` (later turns).
2. Spawn it (cwd = project root) and read stdout line by line. Each line is one
  stream-json event; `assistant` events drive the `progress` line, the final
   `result` event flags errors.
3. When the process exits, `_interpret` scans the accumulated assistant text for a
  marker at the start of a line and returns `ask` / `emit` / `None`.
4. A `finally` **kills the subprocess** on every exit path (normal, exception,
  cancellation) so a child is never orphaned.

## Resume-per-turn & retention

Each turn is a **fresh `claude -p` process that runs one turn and exits.** Continuity
between turns comes from Claude Code's own on-disk session store via `--resume`, not
from anything held in the server's memory. Consequences:

- Nothing runs while a human is answering — no parked process, no worker thread.
- State survives a server restart (it's on disk in CC's store).
- **Retention:** on every terminal path, `sessions.purge` deletes the sandbox
(`.sessions/<uuid>`, the raw caller inputs) **and** best-effort deletes the CC
transcript (`~/.claude/projects/<slug>/<uuid>.jsonl`). Only a tiny status record is
kept in memory so the client's final poll can read the result.

## Safety rails


| Rail                | What it does                                                                                                                                                                 | Where                         |
| ------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------- |
| **Nudges**          | If a turn ends with no marker (model stopped on prose), resume it with a canned "ask or finish" message. Bounded by `MAX_CONTINUES` (12) → then `error`.                     | `engine.NUDGE`, `_drive`      |
| **Turn timeout**    | `TURN_TIMEOUT` wraps each `run_turn`; on timeout the turn is aborted (subprocess killed) and the session `error`s + purges. Stops a hung `claude` pinning `running` forever. | `config`, `_drive`            |
| **Reply timeout**   | `REPLY_TIMEOUT` wraps the wait for the user's answer; an abandoned `need_input` session is closed + purged instead of leaking.                                               | `config`, `_drive`            |
| **Subprocess kill** | `run_turn`'s `finally` kills the child on any exit/cancel — no orphans.                                                                                                      | `engine.run_turn`             |
| **Record caps**     | `MAX_SESSIONS` evicts oldest FINISHED records; `MAX_UPLOADS` evicts oldest un-consumed uploads. Keeps the in-memory stores bounded.                                          | `sessions._gc`, `upload_file` |


> Note: `TURN_TIMEOUT` / `REPLY_TIMEOUT` are passed to `asyncio.wait_for`, which is in
> **seconds**. Set them accordingly (e.g. `1800` = 30 min, `3600` = 1 h) via
> `LIKEMINDS_MCP_TURN_TIMEOUT` / `LIKEMINDS_MCP_REPLY_TIMEOUT`.

## Auth & model

- **Auth** (`server._configure_auth`): maps `CLAUDE_TOKEN` → `CLAUDE_CODE_OAUTH_TOKEN`
(the var the CLI reads for a subscription token) and strips
`CLAUDE_CODE_USE_FOUNDRY` / `ANTHROPIC_FOUNDRY_*` / `ANTHROPIC_API_KEY` /
`ANTHROPIC_AUTH_TOKEN` so they can't outrank the OAuth token. `LIKEMINDS_MCP_AUTH=api`
keeps the env creds instead.
- **Model**: `config.MODEL` defaults to `opus[1m]` — latest Opus at the 1M-token
context window (the `[1m]` suffix opts into 1M). Verified against the API's own
`modelUsage` report (`claude-opus-4-8[1m]`, `contextWindow: 1000000`). Override with
`CLAUDE_AGENT_MODEL`. `--model` is passed on **every** turn, resume included.

## Inputs & outputs

- **Inputs** land in the session's `inputs/` dir via one of: `input_paths` (local
paths, copied byte-for-byte — best for a local client), `upload_refs` (from
`upload_file`, for clients with no filesystem), or inline `artifacts`/`files`.
- **Output** is whatever the skill writes to the session's `output/` dir. On finish,
`_harvest` reads it as bytes (binaries survive) and `_promote` copies it to
`outputs/mcp/<result_id>/`. The deliverable is never dumped into chat.

## MCP isolation

Every spawned turn uses `--strict-mcp-config` with the server's own `--mcp-config`
(empty, or the optional `extra_mcp.json`). This keeps the spawned `claude` **off the
project `.mcp.json`** — otherwise it would try to connect back to *this* server
(recursion) and spawn every other project MCP server each turn. A skill that needs a
real MCP server (e.g. playwright) opts in via `extra_mcp.json`.

## Design decisions at a glance


| Decision                                                   | Why                                                                                        |
| ---------------------------------------------------------- | ------------------------------------------------------------------------------------------ |
| Drive the `claude` CLI as a subprocess (not the Agent SDK) | Uses the exact same binary; lets us own the process lifecycle and drop the SDK dependency. |
| Resume-per-turn (process exits between turns)              | No parked client/thread; crash-resilient; nothing held during a human wait.                |
| Text markers, not MCP signal tools                         | stdio MCP tools race the start of a `-p` turn and go missing; markers can't.               |
| Harvest deliverable from disk                              | The skill writes real files; no need to pass content through the protocol.                 |
| Skill-agnostic harness                                     | Binds only the 3 I/O edges; any skill's own logic runs unchanged.                          |
| Purge sandbox + transcript on every terminal path          | Retention guarantee — no raw inputs or conversation linger after a run.                    |


