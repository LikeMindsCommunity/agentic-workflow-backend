# LikeMinds Agentic Workflow Backend

A library of **Claude Code Agent Skills** that take a client from raw platform
artifacts to a finished deliverable — a knowledge base, a structured config,
integration code, a Scope-of-Work document, a live API run, or an automated
bug-fix loop — plus a **local MCP server** (`likeminds_mcp`) that exposes every
skill over HTTP so any Claude client (Claude Code or the Claude Desktop app) can
run them and answer their questions through pause/resume round-trips.

Every skill learns its platform entirely from a **KB** (knowledge base) built from
the client's own artifacts — nothing is hardcoded, so the same skill works for any
platform once its KB exists.

---

## Folder structure

```
agentic-workflow-backend/
├── .claude/
│   ├── skills/                       # the Agent Skills — invoke by describing the task in plain English
│   │   ├── kb-builder/               #   raw artifacts → knowledge base (KB)
│   │   ├── config-agent/             #   KB + SOW → structured config (JSON/XML/YAML/NodeFlow)
│   │   ├── code-agent/               #   KB + SOW → integration code, wired into your repo
│   │   ├── api-agent/                #   KB + SOW → LLD / execution document
│   │   ├── runner-agent/             #   execute an LLD live (HTTP calls or browser actions)
│   │   ├── create-document-generator/ #   one call: artifacts → KB → per-client generator
│   │   ├── document-generator/       #   compile a per-client document generator from a KB + one sample
│   │   ├── generate-find-bugs-skill/ #   KB → a per-client find-bugs-{client} checker skill
│   │   ├── diagnose-bug/             #   validate a bug report → PENDING row in the approval sheet
│   │   ├── process-comparison/       #   approved comparison findings → approval sheet (with RCA)
│   │   └── apply-fixes/              #   apply APPROVED fixes to source + one git commit
│   ├── playbook-library/             # archetype advice kb-builder draws on (read-only, not invoked directly)
│   │   └── playbooks/                #   api-integration, document-from-template, nodeflow, fallback
│   └── settings.json                 # Claude Code settings
├── likeminds_mcp/                    # local MCP server that exposes every skill over HTTP
│   ├── server.py                     #   FastMCP HTTP server + 4 tools + background driver
│   ├── engine.py                     #   runs one `claude -p` turn, parses the signal markers
│   ├── harness.py                    #   skill-agnostic I/O envelope (appended to the system prompt)
│   ├── sessions.py                   #   in-process session records + sandbox/transcript purge
│   ├── registry.py                   #   indexes .claude/skills so any skill is runnable
│   ├── storage.py                    #   Cloudflare R2 integration: upload inputs, deliver outputs
│   ├── config.py                     #   paths, host/port, model, markers, safety bounds, R2 config
│   ├── __main__.py                   #   `python -m likeminds_mcp` entrypoint

├── inputs/                           # drop client artifacts here (gitignored)
├── outputs/                          # deliverables (gitignored)
│   ├── {client}/                     #   per client: kb/, approval_sheet.md, comparisons/
│   └── mcp/<result_id>/              #   local copy of deliverables from MCP skill runs
├── .mcp.json                         # registers the likeminds server for the Claude Code CLI
├── .env / .env.example               # CLAUDE_TOKEN + R2 creds and other env (.env is gitignored)
├── requirements.txt                  # MCP server deps: mcp + python-dotenv + boto3
└── README.md                         # this file
```

`.sessions/` (per-run MCP sandboxes) and `venv/` are also created locally and are
gitignored.

---

## Install and setup

```bash
git clone https://github.com/LikeMindsCommunity/claude-skill-auto-bugfix.git
cd claude-skill-auto-bugfix

python3 -m venv venv
venv/bin/pip install -r requirements.txt      # mcp + python-dotenv
```

The skills run inside **Claude Code**, so a working `claude` CLI must be on your
`PATH`. You can use the skills two ways:

1. **Directly in Claude Code** — open `claude` in this repo and describe the task;
  the trigger phrases in each skill activate the right one.
2. **Through the MCP server** — start `likeminds_mcp` and call `run_skill` from any
  connected Claude client.

Drop a client's artifacts into a folder under `inputs/`; deliverables land under
`outputs/{client}/` (both gitignored).

---

## Skills

The skills form three families. All are **platform-agnostic**: they read a KB (built
once per client) and act on it. The KB carries the platform's grammar and rules; a
short **SOW** (solution doc / prompt) says *what* to build.

> **KB = how, SOW = what.** Build the KB once with `kb-builder`, then run the
> deliverable skills as many times as you have things to build.

### KB to deliverable pipeline

```
raw artifacts ─► kb-builder ─► KB ─┬─► config-agent ─► structured config
  (docs,                           │
   samples,                        ├─► code-agent   ─► integration code (wired into your repo)
   transcripts)                    │
                                   ├─► api-agent    ─► LLD ─► runner-agent ─► live run
                                   │
                                   └─► (config / code / LLD, all from the same KB)
```

#### `kb-builder` — build & maintain the KB

**Use it when** you have a client's raw artifacts and need the KB built, or extended.


|              |                                                                                                 |
| ------------ | ----------------------------------------------------------------------------------------------- |
| **Triggers** | *"build the KB for {client}"*, *"update {client}'s KB"*, *"generate a KB from these artifacts"* |
| **Inputs**   | `inputs=<dir>` (required) · `prompt` (optional context) · `output=<dir>` (optional)             |
| **Output**   | `outputs/{client}/kb/`                                                                          |


```
build the KB for exotel from the artifacts in inputs/exotel/
```

The first run drafts the KB; later runs extend it in place. It picks the archetype
itself and asks any gap questions interactively, grouped **BLOCKING / IMPORTANT /
VERIFY ASSUMPTION**. It draws on the read-only **playbook library**
(`.claude/playbook-library/playbooks/*.md`: `nodeflow`, `api-integration`,
`document-from-template`, `fallback`) for archetype advice.

#### `config-agent` — KB → structured config

**Use it when** you want a structured config the platform ingests (JSON / XML / YAML /
NodeFlow), validated against the KB's own rules. **Nothing is executed.**


|              |                                                                                                          |
| ------------ | -------------------------------------------------------------------------------------------------------- |
| **Triggers** | *"generate the config / nodeflow from this KB + SOW"*, *"build the {platform} config"*, *"config-agent"* |
| **Inputs**   | `kb=<dir>` · `sow=<path>` · `prompt` (optional) · `output=<dir>` (optional)                              |
| **Output**   | `outputs/<client>/generated/`                                                                            |


```
config-agent kb=outputs/exotel/kb/ sow=inputs/exotel/billing-ivr.md
```

#### `code-agent` — KB → integration code

**Use it when** you want code — an SDK integration, function, handler, or glue snippet
(*not* a whole project) — generated from the KB's API surface, verified (parse /
compile / lint), and **wired into your codebase.**


|              |                                                                                                      |
| ------------ | ---------------------------------------------------------------------------------------------------- |
| **Triggers** | *"write the SDK code from this KB + SOW"*, *"integrate the {platform} code into **"*, *"code-agent"* |
| **Inputs**   | `kb=<dir>` · `sow=<path>` · `target=<dir-in-your-project>` · `prompt` (optional)                     |
| **Output**   | code written into your `target` directory                                                            |


```
code-agent kb=outputs/razorpay/kb/ sow=inputs/razorpay/create-order.md target=src/payments/
```

If you omit `target` and the SOW doesn't name a path, it **asks where to integrate
before writing** — it never guesses where to land code.

#### `api-agent` — KB → execution document (LLD)

**Use it when** you want the **runbook before running it**: an ordered, fully-specified,
self-contained LLD / Execution Document that `runner-agent` later carries out. It only
*designs* — no auth, no secrets, no live calls.


|              |                                                                                                              |
| ------------ | ------------------------------------------------------------------------------------------------------------ |
| **Triggers** | *"create the LLD / execution doc from this KB + SOW"*, *"design the {platform} API workflow"*, *"api-agent"* |
| **Inputs**   | `kb=<dir>` · `sow=<path>` · `prompt` (optional) · `output=<dir>` (optional)                                  |
| **Output**   | `outputs/<client>/lld/`                                                                                      |


The KB's shape decides the step type automatically — a REST-API KB yields HTTP-call
steps; a web-flow KB yields browser-agent steps. There is no mode to pass.

#### `runner-agent` — execute the LLD live

**Use it when** an `api-agent` LLD is ready and you want it run for real, exactly as
written, from the document alone.


|              |                                                                                            |
| ------------ | ------------------------------------------------------------------------------------------ |
| **Triggers** | *"run / execute this LLD"*, *"execute the execution document"*, *"runner-agent"*           |
| **Inputs**   | `lld=<path>` (required) · `secrets=<file>` · `env=` / `mode=` · `dry_run=true` · `output=` |
| **Output**   | a run directory with `run.log` + a redacted `result.json`                                  |


It **defaults to non-prod** (going live is an explicit choice), sources its own
credential values by the names the LLD lists — **never from the document** — and honors
the LLD's safety gates: confirm before any state change, double-confirm anything
destructive. Add `dry_run=true` to rehearse without firing calls.

**End-to-end:**

```
# 1. Build the KB once from the client's artifacts
build the KB for getstream from inputs/getstream/            ->  outputs/getstream/kb/

# 2a. Generate a config ...
config-agent kb=outputs/getstream/kb/ sow=inputs/feed.md     ->  outputs/getstream/generated/
# 2b. ... or integration code ...
code-agent   kb=outputs/getstream/kb/ sow=inputs/feed.md target=src/feed/
# 2c. ... or design + run a live API workflow
api-agent    kb=outputs/getstream/kb/ sow=inputs/feed.md     ->  outputs/getstream/lld/
runner-agent lld=outputs/getstream/lld/feed.md               ->  live run + run record
```

### Document generators

#### `create-document-generator` — one call: KB + compiled generator

The one-time entry point. Runs `kb-builder` then `document-generator` in a single session:
builds (or extends) the client KB from raw artifacts, then compiles a reusable
`generate-<client>-<doctype>` skill from that KB plus one sample document. After it finishes,
call the generated skill with a MOM/brief to produce each document.

|              |                                                                                                     |
| ------------ | --------------------------------------------------------------------------------------------------- |
| **Triggers** | *"set up a document generator for {client}"*, *"onboard {client} from these artifacts"*             |
| **Inputs**   | `inputs=<artifacts dir>` · `sample=<format-reference doc>` · optional `customer` / `prompt`         |
| **Output**   | the client KB + a reusable `generate-<client>-<doctype>` skill                                      |

#### `document-generator` — compile a per-client document skill

Reads an organisation's KB plus **one sample document** (a SOW, BRD, HLD, proposal, or any
structured deliverable, used as a pixel-level visual format reference) and writes a
self-contained skill that turns a new MOM/brief into a complete document matching the
sample's exact format.


|              |                                                                                                     |
| ------------ | --------------------------------------------------------------------------------------------------- |
| **Triggers** | *"build a document generator for {customer}"*, *"compile a document skill from this KB and sample"* |
| **Output**   | a new `.claude/skills/generate-<customer>-<doc-type>/` skill                                        |


### Automated bug-fix loop

Four skills form a review-gated loop that finds discrepancies, proposes fixes for human
approval, and applies them. The approval sheet and comparison sheets live per client
under `outputs/{client}/`; project context (file index, architecture layers,
constraints) is read from a `CLAUDE.md` in the **target** project.

```
generate-find-bugs-skill ─► find-bugs-{client} ─► outputs/{client}/comparisons/*.md
   (once, from the KB)         (compare gen vs expected)          │
                                                                  ▼  (review, mark APPROVED)
bug report ─► diagnose-bug ─┐                          process-comparison  (RCA)
                            └────────────►  outputs/{client}/approval_sheet.md
                                                         │  (review, mark APPROVED)
                                                         ▼
                                                    apply-fixes ─► source edits + git commit
```


| Skill                            | Role                                                           | Writes                                         |
| -------------------------------- | -------------------------------------------------------------- | ---------------------------------------------- |
| `generate-find-bugs-skill`       | Compile a per-client generated-vs-expected checker from the KB | `.claude/skills/find-bugs-{client}/SKILL.md`   |
| *find-bugs-{client}* (generated) | Compare a generated file against an expected file              | `outputs/{client}/comparisons/<name>.md`       |
| `process-comparison`             | Root-cause the APPROVED comparison items and propose fixes     | `outputs/{client}/approval_sheet.md` (PENDING) |
| `diagnose-bug`                   | Validate one or more bug reports and propose fixes             | `outputs/{client}/approval_sheet.md` (PENDING) |
| `apply-fixes`                    | Apply every APPROVED row to source and commit                  | source files + one git commit                  |


Only `apply-fixes` edits source or touches git; `diagnose-bug` and `process-comparison`
are propose-only. A reviewer flips each row's `Status` from `PENDING` to `APPROVED` /
`REJECTED` in between. `{client}` is resolved from an explicit `client=<name>` argument,
an `output=<dir>` override, or inferred from context (the skill asks if ambiguous).

```
diagnose-bug client=acme "transitions render out of order AND variables missing on step 5"
process-comparison client=acme
apply-fixes client=acme
```

---

## Local MCP server

Exposes **every** skill in `.claude/skills/` behind a single `run_skill` tool over
local HTTP, so a Claude client — or the regular Claude chat — can invoke any skill and
answer its runtime questions through pause/resume round-trips, **without ever seeing the
skill prompt**. Each turn runs server-side as a fresh `claude -p` subprocess
(resume-per-turn); Claude Code's own on-disk session store carries state between turns,
so nothing is parked in memory while a human answers.

### Quick start

**1. Install** (once):

```bash
python3 -m venv venv
venv/bin/pip install -r requirements.txt      # mcp + python-dotenv + boto3
```

The server drives the **Claude Code CLI** as a subprocess, so a working `claude` must be
on your `PATH` (override with `CLAUDE_BIN`).

**2. Authenticate** — per request the spawned Claude uses the **first credential
available**, in order: (1) a caller's **own key** sent in a request header (BYOK, below),
(2) a server **`ANTHROPIC_API_KEY`** in `.env`, (3) your **Claude subscription** (Max/Pro).
Set whichever server fallback you want:

```bash
claude setup-token          # subscription: prints a token for CLAUDE_TOKEN
```

Put the token in `.env` as `CLAUDE_TOKEN=…` (the server maps it to the
`CLAUDE_CODE_OAUTH_TOKEN` the CLI reads), or log in once with the `claude` CLI and skip the
token. To bill against an **Anthropic API key** instead, set `ANTHROPIC_API_KEY=…` in
`.env` — when present it takes precedence over the subscription. On startup the server
strips `CLAUDE_CODE_USE_FOUNDRY` / `ANTHROPIC_FOUNDRY_*` / `ANTHROPIC_AUTH_TOKEN` so they
can't outrank these.

**Per-request BYOK (bring-your-own-key).** The `.env` creds above are the server's own
fallback. A caller can instead supply **their own Anthropic key per request** in a header;
the server reads it fresh on each request and injects it into the spawned CLI for that
turn only — so the caller's job authenticates and **bills to their account**, and nothing
is stored (no disk, no logs). This is the header shortcut that works on **Claude Code**,
which attaches configured headers on every request:

```bash
claude mcp add --transport http --scope user likeminds http://127.0.0.1:8787/mcp \
    --header "x-api-key: sk-ant-api03-YOURKEY"
```

For a client that reaches the server through the **`mcp-remote`** stdio bridge (Claude
Desktop, Cursor, and other stdio-only clients), pass the same header as `mcp-remote` args:

```json
"likeminds": {
  "command": "npx",
  "args": [
    "-y", "mcp-remote", "http://127.0.0.1:8787/mcp",
    "--header", "x-api-key:${ANTHROPIC_KEY}"
  ],
  "env": { "ANTHROPIC_KEY": "sk-ant-api03-YOURKEY" }
}
```

Keep the header arg **space-free** (`x-api-key:${VAR}` — no space after the colon) and put
the key in `env`: some clients (Cursor, Claude Desktop on Windows) split `args` on spaces,
which would mangle a `"x-api-key: value"` header.

The header defaults to `x-api-key` (override with `LIKEMINDS_MCP_KEY_HEADER`; an
`Authorization: Bearer <key>` value is also accepted). A request key overrides the `.env`
fallback; with no header key the server uses its own creds — a `.env` `ANTHROPIC_API_KEY`
if set, else the subscription.
Note: a raw API key only reaches 1M-context Opus if the account has that access; otherwise
set `CLAUDE_AGENT_MODEL` to a model it can serve (e.g. `sonnet`). This header path is a
Claude Code convenience; claude.ai and the Claude Desktop connector UI accept only OAuth or
authless servers, so use OAuth there.

**3. Run the server** from a plain terminal (it loads `.env` automatically):

```bash
venv/bin/python -m likeminds_mcp      # serves http://127.0.0.1:8787/mcp
```

### Connect from Claude Code (CLI)

`.mcp.json` in the project root **already registers the server**:

```json
"likeminds": { "type": "http", "url": "http://127.0.0.1:8787/mcp" }
```

1. Start the server (Quick start step 3) in its own terminal and leave it running.
2. (Re)start `claude` in this project so it reads `.mcp.json`.
3. Run `/mcp` — `likeminds` should show as **connected**.
4. Ask it to use a skill (e.g. *"use the kb-builder skill on inputs/exotel/"*).

**Running the CLI from another directory?** Project `.mcp.json` only loads when `claude`
runs inside this repo. To reach `likeminds` from anywhere, register it once at user
scope:

```bash
claude mcp add --transport http likeminds http://127.0.0.1:8787/mcp --scope user
```

The skills are served from this repo (server-side), so the client's working directory
doesn't change what's available, and deliverables still land in this repo's
`outputs/mcp/`.

### Connect from the Claude Desktop app

Claude Desktop takes only `command`-based (stdio) servers, so reach the HTTP server
through the `mcp-remote` bridge (`npx` fetches it — Node.js required).

1. Start the server and leave it running.
2. Open **Claude Desktop → Settings → Connectors → Edit Config**.
3. Add `likeminds` under `mcpServers`:
  ```json
   "mcpServers": {
     "likeminds": {
       "command": "npx",
       "args": ["-y", "mcp-remote", "http://127.0.0.1:8787/mcp"]
     }
   }
  ```
4. Save and **restart Claude Desktop**.

To have jobs bill to **your own** Anthropic key instead of the server's creds, add a
`--header` arg to `args` (e.g. `"--header", "x-api-key:${ANTHROPIC_KEY}"` with the key in
`env`) — see **Per-request BYOK** above.

### Tools exposed


| Tool             | What it does                                                                                                                                                 |
| ---------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `run_skill`      | Run any `.claude/` skill. Returns `running` / `need_input` / `done`; poll or answer with the returned `session_id`. On `done`, `download_urls` has presigned R2 URLs for every output file. |
| `get_upload_url` | Get a presigned PUT URL to upload a file directly to R2. Returns `{upload_url, r2_key}`. Use for Claude Code / any client that can make HTTP requests. PUT the file to `upload_url`, then pass `r2_key` to `run_skill` via `r2_keys`. |
| `upload_file`    | Upload file content through the server to R2. Returns `{r2_key, name, bytes}`. Use for Claude Desktop and claude.ai chat (no HTTP client available). Pass `r2_key` to `run_skill` via `r2_keys`. |
| `list_skills`    | List every Agent Skill the server can run.                                                                                                                   |


**Passing files to a skill — choose by client type:**

| Method | Best for | How |
| --- | --- | --- |
| `get_upload_url` + HTTP PUT → `r2_keys` | Claude Code CLI (can run `curl`) | Call `get_upload_url(filename)`, PUT file bytes to `upload_url`, pass `r2_key` in `run_skill(r2_keys=[…])` |
| `upload_file(name, content)` → `r2_keys` | Claude Desktop, claude.ai chat (no HTTP client) | Call `upload_file(name, content, encoding="utf-8"\|"base64")`, pass returned `r2_key` in `run_skill(r2_keys=[…])` |
| `input_paths` | Claude Code on the **same machine** as the server | Pass absolute local paths; server copies them into the session |
| `artifacts` / `files` | Any client, small text content only | Inline `[{name, content}]` — no R2 needed |

**`run_skill` protocol:**

```
# First call — start the skill
run_skill(skill, context?, r2_keys?, artifacts?, input_paths?, urls?) →
  {status:"running",    session_id, progress, files_written, next_step}  # keep polling

# Poll calls — ONLY session_id, no other args
run_skill(session_id) →
  {status:"running",    session_id, progress, files_written, next_step}  # keep polling
  {status:"need_input", session_id, questions[], next_step}              # relay questions verbatim, wait for user reply

# Answer call — session_id + response (optionally add r2_keys/artifacts/files for file attachments)
run_skill(session_id, response, r2_keys?) →
  {status:"running", …}   # resume polling
  {status:"done",    result_id, summary:{files:[…]}, download_urls:{filename: presigned_url, …}}
  {status:"expired"|"error", message}
```

**Receiving outputs:** When `status` is `done`, `download_urls` maps each output filename to a presigned R2 GET URL (valid 1 hour by default). The client fetches them directly from R2. A local copy also lands in `outputs/mcp/<result_id>/` on the server.

---

## How the MCP server works

A local MCP server that lets a Claude client run a private `.claude/` skill **without
seeing the skill's prompt** — the skill executes server-side inside a real `claude -p`
process, pausing to ask the user questions and returning finished files by reference.

```
Claude client ──run_skill──▶  likeminds server  ──spawns──▶  claude -p  (runs the skill)
      ▲                            │  (background task)          │
      │◀──── poll / questions ─────┤                             │ reads inputs/, writes output/
      │────── answers ─────────────▶  ──resume──▶  claude -p  ◀──┘
      │◀──── download_urls (done) ──┘         (same session, next turn)
                                          ▲           │
              Cloudflare R2 ─────────────┘           │ upload_outputs → presigned GET URLs
              (inputs PUT by client,                  ▼
               downloaded into sandbox,    outputs/ uploaded → r2, sandbox purged
               outputs uploaded on done)
```

**Core ideas:**

- **Resume-per-turn.** Turn 1 spawns `claude -p … --session-id <uuid>`; every later turn
spawns `claude -p … --resume <uuid>`. The process runs one turn and exits, so there's
no long-lived client, no worker thread, and nothing running while a human answers.
State survives a server restart (it lives in Claude Code's on-disk session store).
- **Text-marker signalling (no signal tool).** The harness tells the skill to write
`<<<LM_ASK>>>` (then the question) to pause for the user, and `<<<LM_DONE>>>` to finish;
the engine watches the turn's streamed text for these markers. An MCP *tool* isn't used
for this because a stdio MCP server isn't guaranteed to finish connecting before a
`claude -p` turn begins (its `init` fires "pending" with zero tools), so a signal tool
races and goes missing — a marker never does.
- **Skill-agnostic harness.** Appended via `--append-system-prompt`, it remaps only the
I/O edges (inputs dir / `<<<LM_ASK>>>` / `<<<LM_DONE>>>` / the authoritative output
dir). The skill file itself is never edited.
- **Deliverable harvested from disk.** On `<<<LM_DONE>>>` the server reads every output
file byte-for-byte (so PDFs/DOCX/XLSX survive), promotes a local copy to
`outputs/mcp/<result_id>/`, uploads each file to R2, and returns presigned GET URLs in
the `done` snapshot. The session sandbox and its Claude Code transcript are then purged.

**Modules:**


| Module        | Responsibility                                                                                                     |
| ------------- | ------------------------------------------------------------------------------------------------------------------ |
| `server.py`   | FastMCP HTTP server + 4 tools (`run_skill`, `get_upload_url`, `upload_file`, `list_skills`); background driver `_drive`; output harvest/promote; auth config; long-poll. |
| `storage.py`  | Cloudflare R2 integration: presigned PUT URLs for direct client uploads, server-side `upload_bytes`, `download_inputs` into session sandbox, `upload_outputs` after `<<<LM_DONE>>>`. |
| `engine.py`   | Runs ONE turn: builds the `claude -p` argv, spawns it, reads the stream-json, parses the signal markers.           |
| `harness.py`  | The system-prompt append that binds a skill's I/O edges to the engine.                                             |
| `sessions.py` | Lightweight in-process session records + sandbox/transcript purge + record GC.                                     |
| `registry.py` | Indexes `.claude/skills/*/SKILL.md` so any skill is runnable.                                                      |
| `config.py`   | Paths, host/port, CLI binary, model, markers, safety bounds, R2 config.                                            |
| `__main__.py` | `python -m likeminds_mcp` entrypoint (streamable-HTTP).                                                            |


**Session state machine:**

```
            ┌───────────────────────────────────────┐
            ▼                                         │ (user replies)
  running ──┬──▶ need_input ──────────────────────────┘
            │        │ (no reply within REPLY_TIMEOUT)
            │        ▼
            ├──▶ done      (LM_DONE → harvest → purge)
            └──▶ error     (crash / turn timeout / nudged out)
```

`run_skill` **long-polls**: each call waits up to `POLL_WAIT` (~4s) for the state to
change, then returns a snapshot. The background `_drive` task owns the real work; the
tool handlers only read `sess.`* state to answer polls.

**Retention.** On every terminal path, `sessions.purge` deletes the sandbox
(`.sessions/<uuid>`, the raw caller inputs) **and** best-effort deletes the Claude Code
transcript (`~/.claude/projects/<slug>/<uuid>.jsonl`). Only a tiny status record is kept
in memory so the client's final poll can read the result.

**Safety rails:**


| Rail                | What it does                                                                                                                                                                                                                                                                   |
| ------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| **Nudges**          | A turn that ends with no marker (model stopped on prose) is resumed with a canned "ask or finish" message, bounded by `MAX_CONTINUES` (12) → then `error`.                                                                                                                     |
| **Turn timeout**    | `TURN_TIMEOUT` wraps each turn; on timeout the subprocess is killed and the session `error`s + purges. Stops a hung `claude` pinning `running` forever.                                                                                                                        |
| **Reply timeout**   | `REPLY_TIMEOUT` wraps the wait for the user's answer; an abandoned `need_input` session is closed + purged.                                                                                                                                                                    |
| **Subprocess kill** | `run_turn`'s `finally` kills the child on any exit/cancel — no orphans.                                                                                                                                                                                                        |
| **Record caps**     | `MAX_SESSIONS` evicts oldest FINISHED records; `MAX_UPLOADS` evicts oldest un-consumed uploads.                                                                                                                                                                                |
| **MCP isolation**   | Every turn uses `--strict-mcp-config` with the server's own empty `--mcp-config`, keeping the spawned `claude` off the project `.mcp.json` — otherwise it would connect back to *this* server (recursion) and spawn every project MCP server each turn. |


> `TURN_TIMEOUT` / `REPLY_TIMEOUT` are passed to `asyncio.wait_for`, which is in
> **seconds** (e.g. `1800` = 30 min, `3600` = 1 h), set via `LIKEMINDS_MCP_TURN_TIMEOUT`
> / `LIKEMINDS_MCP_REPLY_TIMEOUT`.

---

## Accounts, login & skill privacy

By default every skill the server exposes is shared. Multi-tenant mode adds a stable
per-user token so that **custom skills a user generates stay private to that user**,
while the shared built-in skills stay visible to everyone.

### Signing in

1. Open `https://<your-host>/login` in a browser.
2. Enter your work email → a one-time code is emailed (via Gupshup's hosted OTP service).
3. Enter the code → the page returns your **access token** (stable, reusable) and a
   ready-to-paste MCP config.
4. Add the token to your MCP client so it is sent on every request in the `x-user-id`
   header:

   ```
   claude mcp add --transport http --scope user likeminds https://<your-host>/mcp \
       --header "x-user-id: <your-token>"
   ```

The token is the user's id in the Mongo registry; the code is generated, emailed, and
verified by Gupshup, so the server never stores OTPs. This header is orthogonal to the
BYOK `x-api-key` header: **`x-user-id` says who you are; `x-api-key` says who pays.**

### What isolation you get

- `list_skills` and `run_skill` are **scoped to the caller's token**: the built-in
  skills plus only that caller's own generated skills. Another user's custom skills are
  never listed or runnable.
- A generated skill is stored on the server as `<skill-name>__u_<token>` and
  auto-registered **only** for the tenant that created it (its `SKILL.md` name is
  rewritten to match, so the right tenant's copy always resolves even if two tenants
  pick the same skill name). An anonymous caller (no / unverified token) can still run
  built-ins, but a skill it generates is returned as a downloadable deliverable rather
  than installed.
- Isolation here is a **registry filter** — skills are co-located on disk and filtered
  by token — which is enough to keep tenants from seeing or running each other's skills.

**No database?** If `MONGODB_URI` is unset the server still runs: there is no `/login`
page, and any `x-user-id` value is trusted opaquely as a tenant key (fine for local dev
or a trusted network). Set Mongo + `EMAIL_GHUPSHAP_KEY` in production to require verified
login.

### Disabling a skill for everyone

To hide a skill from **all** users — both `list_skills` and `run_skill` — add its name
to `disabled_skills.json` at the project root:

```json
{ "disabled": ["some-skill", "another-skill"] }
```

The file is read fresh on each call, so changes take effect with no restart. A disabled
skill can be neither listed nor run by anyone (including its owner). You can also set
`LIKEMINDS_MCP_DISABLED_SKILLS=a,b` as an env override, merged with the file.

### Automatic login (OAuth 2.1) — recommended

Instead of pasting a token, let the MCP client run the login for you. When
`MCP_OAUTH_ENABLED=true`, the server is a full OAuth 2.1 authorization server and Claude
(claude.ai, Desktop, Claude Code) does the browser handshake itself — **no token is ever
copied by hand**:

```
1. Client calls /mcp with no token  →  401 + WWW-Authenticate (points at the metadata)
2. Client discovers the auth server and AUTO-OPENS the browser to /authorize
3. User verifies email via the SAME Gupshup OTP page (it doubles as the login UI)
4. Browser redirects back to the client with a code → client swaps it for a token (PKCE)
5. Client stores + auto-refreshes the token, sends `Authorization: Bearer` on every call
```

The user just clicks **Connect** (or, on Claude Code, runs `claude mcp add <url>` with no
`--header`) and enters their email + code. The access token maps to the Mongo user id =
the same tenant as the header path, so private skills carry over.

The MCP SDK mounts everything except identity: `/authorize`, `/token`, `/register` (dynamic
client registration), `/revoke`, and both `/.well-known/*` metadata documents. We supply
only the storage + the OTP login. Requires `MONGODB_URI` and a **real, reachable**
`PUBLIC_BASE_URL` (the OAuth issuer — use `https://…` in production; `http://localhost:8787`
for local, never `0.0.0.0`).

**`x-api-key` still works alongside OAuth.** `Authorization` now carries the OAuth token
(identity); your own Anthropic key (billing/BYOK) rides on the separate `x-api-key` header,
which you can still attach on Claude Code. The two never collide.

When OAuth is **on**, every `/mcp` call requires a valid token (no anonymous access). When
**off**, the server uses the header-based `x-user-id` path described above. Flip it with a
single env var, so you can cut over when ready.

| Variable | Description | Default |
| --- | --- | --- |
| `MCP_OAUTH_ENABLED` | Turn the OAuth authorization server + bearer enforcement on | `false` |
| `MCP_OAUTH_ACCESS_TTL` | Access-token lifetime, seconds | `3600` |
| `MCP_OAUTH_REFRESH_TTL` | Refresh-token lifetime, seconds | `2592000` (30d) |
| `MCP_OAUTH_CODE_TTL` | Auth-code / pending-login lifetime, seconds | `600` |
| `MCP_OAUTH_SCOPE` | The single scope issued/required | `mcp` |

### Login / tenancy env vars

| Variable                             | Description                                                                                  | Default                          |
| ------------------------------------ | -------------------------------------------------------------------------------------------- | -------------------------------- |
| `LIKEMINDS_MCP_USER_HEADER`          | Header the caller's login token (tenant id) is read from; scopes custom skills               | `x-user-id`                      |
| `MONGODB_URI`                        | Mongo connection string for the user/tenant registry; enables verified login                 | unset (login off; opaque tokens) |
| `MONGODB_DB_NAME`                    | Mongo database name                                                                          | unset                            |
| `MONGODB_USERS_COLLECTION`           | Collection holding user rows                                                                  | `users`                          |
| `EMAIL_GHUPSHAP_KEY`                 | Gupshup TwoFactorAuth key used to email + verify OTPs                                         | unset (login off)                |
| `PUBLIC_BASE_URL`                    | Public origin shown in the `/login` copy-paste config (set behind a proxy)                   | derived from the request         |
| `LIKEMINDS_MCP_TENANT_CACHE_TTL`     | Seconds to cache a token→verified lookup so polls don't hit Mongo each call                   | `300`                            |
| `LIKEMINDS_MCP_DISABLED_SKILLS_FILE` | JSON file of skills hidden globally from list + run                                           | `disabled_skills.json`           |
| `LIKEMINDS_MCP_DISABLED_SKILLS`      | Comma-separated skills to disable globally (merged with the file)                            | unset                            |

## Configuration

Server env vars (put persistent ones in `.env`):


| Variable                      | Description                                                                            | Default                                               |
| ----------------------------- | -------------------------------------------------------------------------------------- | ----------------------------------------------------- |
| `CLAUDE_TOKEN`                | Subscription token, mapped to `CLAUDE_CODE_OAUTH_TOKEN`                                | required unless `ANTHROPIC_API_KEY` or CLI login     |
| `ANTHROPIC_API_KEY`           | Server API-key fallback; used when a request sends no header key, ahead of the subscription | unset                                            |
| `LIKEMINDS_MCP_KEY_HEADER`    | Header a caller's own Anthropic key (BYOK) is read from; injected into the spawned CLI  | `x-api-key`                                           |
| `CLAUDE_AGENT_MODEL`          | Model for spawned turns                                                                | `opus[1m]` (latest Opus, 1M context)                  |
| `CLAUDE_BIN`                  | Path to the `claude` CLI                                                               | resolved from `PATH`                                  |
| `LIKEMINDS_MCP_HOST`          | Bind address for the HTTP server                                                       | `127.0.0.1` (loopback; set `0.0.0.0` for remote)     |
| `LIKEMINDS_MCP_PORT`          | Port for the HTTP server                                                               | `8787`                                                |
| `LIKEMINDS_MCP_TURN_TIMEOUT`  | Per-turn timeout, seconds                                                              | `1800`                                                |
| `LIKEMINDS_MCP_REPLY_TIMEOUT` | Wait-for-user-reply timeout, seconds                                                   | `3600`                                                |
| `MCP_TOOL_TIMEOUT`            | Client-side tool-call timeout in ms (raise for long-running skills; set on the client) | client default                                        |
| `R2_BUCKET`                   | Cloudflare R2 bucket name                                                              | (R2 disabled if any R2 var is missing)                |
| `R2_ACCESS_KEY_ID`            | R2 access key                                                                          |                                                       |
| `R2_SECRET_ACCESS_KEY`        | R2 secret key                                                                          |                                                       |
| `R2_ENDPOINT`                 | R2 account endpoint (`https://<account_id>.r2.cloudflarestorage.com`)                 |                                                       |
| `R2_URL_EXPIRY`               | Presigned GET URL TTL for output downloads, seconds                                    | `3600` (1 hour)                                       |

**R2 is optional** — if any R2 variable is missing the server falls back to local-only mode: `get_upload_url` and `upload_file` return an error, and `run_skill` does not return `download_urls`. Deliverables are still written to `outputs/mcp/<result_id>/` on the server.

### Production deployment

To run the server on a remote machine so any client can reach it:

1. Set `LIKEMINDS_MCP_HOST=0.0.0.0` (or the specific bind IP) and `LIKEMINDS_MCP_PORT` in `.env`.
2. Set all four `R2_*` variables. All file I/O goes through R2 — inputs are uploaded to R2 by the client before `run_skill` and downloaded into the session sandbox by the server; outputs are uploaded to R2 after `<<<LM_DONE>>>` and presigned GET URLs are returned to the client.
3. Set `CLAUDE_TOKEN` (or log the CLI in on the server machine with `claude setup-token`).
4. Start the server: `venv/bin/python -m likeminds_mcp`.
5. Point clients at the public URL instead of `127.0.0.1:8787`:
   - Claude Code: `claude mcp add --transport http likeminds https://<your-host>/mcp --scope user`
   - Claude Desktop: replace `http://127.0.0.1:8787/mcp` with the public URL in `mcp-remote` args.

**File input flow (remote clients):**

```
# Claude Code (has curl)
1. get_upload_url("file.pdf") → {upload_url, r2_key}
2. curl -X PUT upload_url --data-binary @file.pdf
3. run_skill(skill="kb-builder", r2_keys=["<r2_key>"], context="…")

# Claude Desktop / claude.ai chat (no HTTP client)
1. upload_file("file.txt", "<content>", encoding="utf-8") → {r2_key, …}
   # or for binary:
   upload_file("file.bin", "<base64>", encoding="base64") → {r2_key, …}
2. run_skill(skill="kb-builder", r2_keys=["<r2_key>"], context="…")
```

**Output delivery:**

```
run_skill(session_id) →
  {status:"done", result_id:"kb-builder_abc12345",
   summary:{files:["kb.md","playbook.md"]},
   download_urls:{
     "kb.md":      "https://<account>.r2.cloudflarestorage.com/outputs/…?X-Amz-Expires=3600&…",
     "playbook.md":"https://…"
   }}
```


