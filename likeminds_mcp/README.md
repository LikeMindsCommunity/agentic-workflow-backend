# likeminds_mcp — local MCP server

Exposes **every** skill in `.claude/` (both `.claude/commands/*.md` slash commands
and `.claude/skills/*/SKILL.md` Agent Skills) behind one `run_skill` dispatch tool
over local HTTP, so a Claude Code client can invoke any skill and answer its runtime
questions through pause/resume round-trips — without ever seeing the skill prompt.

Each turn runs server-side as a fresh **`claude -p` subprocess** (resume-per-turn):
Claude Code's own on-disk session store carries the conversation between rounds, so
nothing is parked in memory while a human answers. The engine is **skill-agnostic**
— it only binds three I/O edges; the skill's own logic decides everything else.

## How it works

- **Resume-per-turn.** Turn 1 spawns `claude -p … --session-id <uuid>`; every later
  turn spawns `claude -p … --resume <uuid>`. The process runs one turn and exits, so
  there is no long-lived client, no worker thread, and nothing running while a human
  is answering. State survives a server restart.
- **Text-marker signalling (no signal tool).** The harness tells the skill to write
  `<<<LM_ASK>>>` (then the question) to pause for the user, and `<<<LM_DONE>>>` to
  finish. The engine watches the turn's streamed text for these markers. We do NOT
  use an MCP tool for this: a stdio MCP server is not guaranteed to finish connecting
  before a `claude -p` turn begins (its `init` event fires "pending" with zero
  tools), so a signal *tool* races and goes missing — a marker never does.
- **Harness = skill-agnostic envelope.** Appended via `--append-system-prompt`, it
  remaps only the I/O edges (inputs dir / `<<<LM_ASK>>>` / `<<<LM_DONE>>>` + the
  authoritative output dir). The skill file itself is never edited.
- **Deliverable harvested from disk.** On `<<<LM_DONE>>>` the engine copies the
  output directory (byte-for-byte, so PDFs/DOCX/XLSX survive) to
  `outputs/mcp/<result_id>/`, then purges the session sandbox and its transcript.

## Layout

- `server.py` — FastMCP HTTP server; `run_skill` / `upload_file` / `list_skills`,
  background asyncio driver + long-poll, output harvesting, auth config.
- `engine.py` — spawns one `claude -p` turn and reads its stream for a marker.
- `harness.py` — the system-prompt append that binds the I/O edges.
- `sessions.py` — lightweight in-process session records + sandbox/transcript purge.
- `registry.py` — indexes `.claude/commands/` and `.claude/skills/`.
- `config.py` — paths, host/port, CLI binary, model, markers.

## One-time setup

```bash
python3 -m venv venv
venv/bin/pip install "mcp>=1.2.0" python-dotenv
```

The package drives the **Claude Code CLI** as a subprocess (it no longer uses the
`claude-agent-sdk`), so a working `claude` on PATH is required (override with
`CLAUDE_BIN`).

## Auth — use your Claude subscription (Max/Pro)

The server routes the spawned Claude at your subscription, not the API/Foundry creds
in `.env`. Provide a long-lived subscription token:

```bash
claude setup-token        # requires a Claude subscription; prints a token
```

Put it in `.env` as `CLAUDE_TOKEN=…` (the server maps it to the `CLAUDE_CODE_OAUTH_TOKEN`
the CLI reads) — or log in once with `claude auth login` (keychain) and skip the token.
On startup the server strips `CLAUDE_CODE_USE_FOUNDRY` / `ANTHROPIC_FOUNDRY_*` /
`ANTHROPIC_API_KEY` / `ANTHROPIC_AUTH_TOKEN` from the environment so they can't
outrank the subscription token. To keep the `.env` API/Foundry creds instead, set
`LIKEMINDS_MCP_AUTH=api`.

**Model:** defaults to `opus[1m]` — the latest Opus with the 1M-token context window
(the `[1m]` suffix opts into 1M context). Override with `CLAUDE_AGENT_MODEL`.

## Run

Launch from a **plain terminal** (Terminal.app / iTerm):

```bash
cd "<this project>"
venv/bin/python -m likeminds_mcp      # serves http://127.0.0.1:8787/mcp
```

`server.py` loads `.env` automatically.

## Connect from Claude Code

`.mcp.json` already registers it:

```json
"likeminds": { "type": "http", "url": "http://127.0.0.1:8787/mcp" }
```

With the server running, restart Claude Code, run `/mcp` (shows `likeminds`), then
ask it to use a skill. Heavy skills take minutes per turn — raise the client tool
timeout if needed: `export MCP_TOOL_TIMEOUT=600000`.

## Inputs — passing files

Since the server is local, the primary way to give a skill files is a **local path**:

- `input_paths` — absolute local paths; copied (byte-for-byte, binaries included)
  into the session inputs dir. Best for same-machine clients (Claude Code).
- `upload_refs` — for clients with no local filesystem (the regular chat): call
  `upload_file(name, content)` first, then pass the returned id.
- `artifacts` / `files` — inline `[{name, content}]` text.

Extra MCP servers a skill needs (e.g. playwright for a browser skill) can be added
via an optional `likeminds_mcp/extra_mcp.json` shaped like `{"mcpServers": {…}}`.

## Test client (no Claude Code needed)

```bash
venv/bin/python -m likeminds_mcp.test_client list
venv/bin/python -m likeminds_mcp.test_client run kb-builder path/to/artifact.json
venv/bin/python -m likeminds_mcp.test_client run config-agent --context "Build the X config"
```

## Protocol

`run_skill(skill, artifacts?, input_paths?, upload_refs?, urls?, context?)` →
- `{status:"running", session_id, progress, files_written, next_step}` — poll again
  with ONLY `session_id`.
- `{status:"need_input", session_id, questions[], next_step}` — relay verbatim, then
  call `run_skill(session_id, response, input_paths?/upload_refs?)`.
- `{status:"done", result_id, summary}` — deliverable stored at `outputs/mcp/<result_id>/`.
- `{status:"expired"|"error", message}`.
