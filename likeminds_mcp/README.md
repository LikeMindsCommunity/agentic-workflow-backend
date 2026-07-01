# likeminds_mcp — local MCP server (MVP)

Exposes the skills in `.claude/commands/` behind one `run_skill` dispatch tool
over local HTTP, so a Claude Code client can invoke a skill and answer its
runtime questions through pause/resume round-trips — without seeing the skill
prompt. The skill runs server-side via the Claude Agent SDK.

This is the local-test MVP: no OAuth, no Redis, single in-process session store,
single worker. Sessions are live SDK clients parked in memory between rounds.

## Layout

- `server.py` — FastMCP HTTP server; `run_skill` + `list_skills`.
- `engine_sdk.py` — drives a live `ClaudeSDKClient` until it hits a signal tool.
- `signals.py` — the two in-process signal tools: `ask_user`, `emit_result`.
- `harness.py` — system-prompt append that remaps the skill's I/O edges
  (inputs dir / `ask_user` / `emit_result`). Command files stay untouched.
- `sessions.py` — in-process session store + per-session sandbox.
- `registry.py` — indexes `.claude/commands/` for `list_skills`.
- `config.py` — paths, host/port, signal tool names.

## One-time setup

```bash
python3.11 -m venv .venv          # SDK needs Python >= 3.10
.venv/bin/pip install claude-agent-sdk "mcp>=1.2.0" python-dotenv
```

## Run

Launch from a **plain terminal** (Terminal.app / iTerm), NOT from inside a
Claude Code/desktop session's shell:

```bash
cd "<this project>"
.venv/bin/python -m likeminds_mcp      # serves http://127.0.0.1:8787/mcp
```

`server.py` loads `.env` automatically. Credentials follow `.env`:
- Azure Foundry: `CLAUDE_CODE_USE_FOUNDRY=1` + `ANTHROPIC_FOUNDRY_API_KEY` +
  `ANTHROPIC_FOUNDRY_BASE_URL`. The server auto-selects `AZURE_AI_DEPLOYMENT`
  (e.g. `claude-sonnet-4-5`) since the CLI's default model may not be deployed.
- Direct Anthropic: set `ANTHROPIC_API_KEY` instead.
- Override the model anytime with `CLAUDE_AGENT_MODEL`.

> Why a plain terminal: the Claude **desktop app** injects `ANTHROPIC_BASE_URL`
> and OAuth env vars into its own shells. A separately-spawned `claude` CLI can't
> use that OAuth token, so launching the server from inside that environment
> yields "Not logged in". A normal terminal is clean and `.env` routing works.

## Connect from Claude Code

`.mcp.json` already registers it:

```json
"likeminds": { "type": "http", "url": "http://127.0.0.1:8787/mcp" }
```

With the server running, restart Claude Code, run `/mcp` (shows `likeminds`),
then ask it to use the skill, e.g. *"Use the likeminds platform-kb skill to
onboard this platform"* and attach/paste artifacts. The model calls
`mcp__likeminds__run_skill`; on `need_input` it relays the questions, you answer,
it continues; on `onboarded` the KB lands in `kb/<kb_id>/` (not in chat).

Heavy skills take minutes per turn — raise the client tool timeout if needed:
`export MCP_TOOL_TIMEOUT=600000`.

## Protocol

`run_skill(skill, artifacts?, urls?, context?)` →
- `{status:"need_input", session_id, questions[], next_step}` — relay verbatim,
  then call `run_skill(session_id, response, files?)`.
- `{status:"onboarded", kb_id, summary}` — deliverable stored server-side.
- `{status:"expired"|"error", message}`.
