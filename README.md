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
│   │   ├── document-generator/       #   KB + MOM → the finished document (PDF or DOCX)
│   │   ├── find-bugs/                #   KB + generated + expected → comparison sheet
│   │   ├── diagnose-bug/             #   validate a bug report → PENDING row in the approval sheet
│   │   ├── process-comparison/       #   approved comparison findings → approval sheet (with RCA)
│   │   └── apply-fixes/              #   apply APPROVED fixes to source + one git commit
│   ├── playbook-library/             # archetype advice kb-builder draws on (read-only, not invoked directly)
│   │   └── playbooks/                #   api-integration, document-from-template, nodeflow, fallback
│   └── settings.json                 # Claude Code settings
├── likeminds_mcp/                    # local MCP server that exposes every skill over HTTP
│   ├── server.py                     #   FastMCP HTTP server + 2 tools + background driver
│   ├── engine.py                     #   runs one `claude -p` turn, parses the signal markers
│   ├── harness.py                    #   skill-agnostic I/O envelope (appended to the system prompt)
│   ├── sessions.py                   #   in-process session records + sandbox/transcript purge
│   ├── registry.py                   #   indexes .claude/skills so any skill is runnable
│   ├── pipeline.py                   #   multi-step skill chains + resumable pipeline state
│   ├── config.py                     #   paths, host/port, model, markers, safety bounds
│   ├── __main__.py                   #   `python -m likeminds_mcp` entrypoint

├── inputs/                           # drop client artifacts here (gitignored)
├── outputs/                          # deliverables (gitignored)
│   ├── {client}/                     #   per client: kb/, approval_sheet.md, comparisons/
│   └── mcp/<result_id>/              #   deliverables from MCP skill runs
├── .mcp.json                         # registers the likeminds server for the Claude Code CLI
├── .env / .env.example               # CLAUDE_TOKEN and other env (.env is gitignored)
├── requirements.txt                  # MCP server deps: mcp + python-dotenv
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
2. **Through the MCP server** — start `likeminds_mcp` and call `run_pipeline` from any
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

The same `kb-builder` → agent split as everywhere else in this repo: one builds the KB once,
the other reads it on every run. Nothing is compiled, so improving the KB improves every
document from that point on.

```
# once per team
kb-builder         inputs=<reference docs>/ client=acme     ->  outputs/acme/kb/

# once per document
document-generator kb=outputs/acme/kb/ mom=inputs/contoso-call.md
                                                            ->  outputs/acme/documents/
```

`kb-builder` measures the format from the team's reference document — pixel-sampling the
palette, typography, page geometry and table styles — and bundles that document plus its
assets into the KB, so the generator has both the numbers and the diff target at run time.
Per-deal briefs handed in alongside the references are set aside, never ingested.

#### `document-generator` — KB + MOM → the finished document

Reads a team's KB plus a MOM/brief for one deal and writes the finished document in that
team's measured format. Every format fact — palette, typography, page geometry, table
styles, heading strings, boilerplate, section and render order, flowchart vocabulary —
is read from the KB as measured, never re-derived. Delivers PDF or DOCX, asking which
unless the KB policy or the request already says, and either draws the flow diagrams or
leaves marked placeholders, asking the same way. Verifies the result page by page against
the reference the KB bundles.

|              |                                                                                                     |
| ------------ | --------------------------------------------------------------------------------------------------- |
| **Triggers** | *"generate the SOW for {recipient} from this KB and brief"*, *"draft the BRD as a Word doc"*        |
| **Inputs**   | `kb=<dir>` · `mom=<brief>` · optional `format=pdf\|docx` / `diagrams=draw\|placeholder` / `output`  |
| **Output**   | `<recipient>_<DOC_TYPE>.<pdf\|docx>` under `outputs/{client}/documents/`                            |


### Automated bug-fix loop

Four skills form a review-gated loop that finds discrepancies, proposes fixes for human
approval, and applies them. The approval sheet and comparison sheets live per client
under `outputs/{client}/`; project context (file index, architecture layers,
constraints) is read from a `CLAUDE.md` in the **target** project.

```
find-bugs ─────────────────────────────────► outputs/{client}/comparisons/*.md
  (KB + generated + expected, every run)              │
                                                      ▼  (review, mark APPROVED)
bug report ─► diagnose-bug ─┐              process-comparison  (RCA)
                            └────────────►  outputs/{client}/approval_sheet.md
                                                         │  (review, mark APPROVED)
                                                         ▼
                                                    apply-fixes ─► source edits + git commit
```


| Skill                | Role                                                        | Writes                                         |
| -------------------- | ----------------------------------------------------------- | ---------------------------------------------- |
| `find-bugs`          | Compare a generated file against an expected one, judged by the KB | `outputs/{client}/comparisons/<name>.md` |
| `process-comparison` | Root-cause the APPROVED comparison items and propose fixes  | `outputs/{client}/approval_sheet.md` (PENDING) |
| `diagnose-bug`       | Validate one or more bug reports and propose fixes          | `outputs/{client}/approval_sheet.md` (PENDING) |
| `apply-fixes`        | Apply every APPROVED row to source and commit               | source files + one git commit                  |

`find-bugs` reads the KB on every run rather than being compiled per client, so a constraint
kb-builder added yesterday is checked today. A frozen checker would keep reporting *"all check
classes ran to completion"* against rules it had never seen — clean, authoritative, and wrong.


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

Exposes **pipelines** defined in `.claude/pipelines.json` via `run_pipeline` over local
HTTP, so a Claude client (Claude Code or Claude Desktop) can run multi-step skill chains
and answer their runtime questions through pause/resume round-trips, **without ever seeing
the skill prompts**. Each turn runs server-side as a fresh `claude -p` subprocess
(resume-per-turn); Claude Code's own on-disk session store carries state between turns,
so nothing is parked in memory while a human answers.

### Quick start

**1. Install** (once):

```bash
python3 -m venv venv
venv/bin/pip install -r requirements.txt      # mcp + python-dotenv
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
set `CLAUDE_AGENT_MODEL` to a model it can serve (e.g. `sonnet`). The header is optional —
with none sent, the server falls back to the `.env` credential above.

**3. Run the server** from a plain terminal (it loads `.env` automatically):

```bash
venv/bin/python -m likeminds_mcp      # serves http://127.0.0.1:8787/mcp
```

### Or run it in Docker

The image bundles the `claude` CLI and the headless-render toolchain (Chromium, poppler,
fonts, `python-docx`) the document skills need, so this is the quicker path if you would
rather not install those yourself:

```bash
docker compose up --build -d          # serves http://127.0.0.1:8787/mcp
```

`.env` is read for the Claude credential; `./inputs` and `./outputs` are bind-mounted
into the container.

**One caveat worth knowing up front:** `input_paths` is resolved **inside** the
container, so a host path like `/Users/me/brief.pdf` means nothing to it. Copy artifacts
into `./inputs` and pass them as `/app/inputs/brief.pdf`. Deliverables come back to
`./outputs` on the host. Running the server directly on the host avoids this translation
entirely — that is the simpler option when you already have the `claude` CLI.

The container runs as uid 1000. If your host user is not uid 1000 (`id -u`), `chown` the
two mounted directories to 1000 or the run cannot write its output.

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

### Triggering pipelines

Prefix any message with `@likeminds` to invoke the LikeMinds MCP server. Claude will
call `list_pipelines` to discover available pipelines and their trigger phrases, then
call `run_pipeline` with the right pipeline for your intent.

```
@likeminds build a knowledge base from these files
@likeminds generate a SOW from these reference documents
@likeminds the document you produced was wrong, fix it for next time
```

### Tools exposed

| Tool             | What it does |
| ---------------- | ------------ |
| `list_pipelines` | Returns all available pipelines with names, descriptions, steps, and trigger phrases. Always called before `run_pipeline` to pick the right pipeline. |
| `run_pipeline`   | Runs a named pipeline (sequence of skills). Returns `running` / `need_input` / `done`; poll with `session_id`. On `done`, `output_dir` is the folder holding every output file. |

**Passing files.** The server runs on your own machine, so files move by path — nothing is
uploaded anywhere. Use `input_paths` (absolute paths to files *or* folders; the only way to
send binaries like PDF/DOCX), `artifacts` (inline `[{name, content}]` text), or `urls`.

### Pipeline flows

#### `build-kb` — build a knowledge base

```
@likeminds build the KB
@likeminds create a KB from these artifacts
@likeminds onboard this client from these artifacts

list_pipelines()
run_pipeline(pipeline_name="build-kb", input_paths=[...], context="...")
  └── 00_kb-builder
        reads the reference files
        builds KB
        saves to outputs/mcp/pipeline_<id>/00_kb-builder/
→ done: KB files + session_id
```

#### `document-agent` — build KB then generate document

```
@likeminds generate a SOW from these reference documents
@likeminds create BRD from sample documents
@likeminds generate a document end to end

list_pipelines()
run_pipeline(pipeline_name="document-agent", input_paths=[...], context="...")
  └── 00_kb-builder   → builds KB from reference files
  └── 01_document-generator → reads KB, generates PDF or DOCX
→ done: document + session_id
```

#### `document-from-kb` — generate document from existing KB

Use when the KB was already built by an earlier run. Pass that run's `session_id` as
`seed_session_id` — the server recovers the KB bucket from it automatically.

```
@likeminds generate another SOW from the same KB
@likeminds the KB is ready, generate the document

list_pipelines()
run_pipeline(pipeline_name="document-from-kb", seed_session_id="<prior-session-id>",
             input_paths=[MOM/brief], context="...")
  └── 00_document-generator
        reads KB from seed (in place, no copy)
        reads the new MOM/brief
        generates document
→ done: document + session_id
```

#### `config-generator` — build KB then generate config

```
@likeminds generate config from these reference files
@likeminds generate JSON config
@likeminds build configuration file

list_pipelines()
run_pipeline(pipeline_name="config-generator", input_paths=[...], context="...")
  └── 00_kb-builder   → builds KB from reference files
  └── 01_config-agent → reads KB, generates config (JSON/XML/YAML/NodeFlow)
→ done: config file + session_id
```

#### `config-from-kb` — generate config from existing KB

```
@likeminds generate another config from the same KB
@likeminds the KB is ready, generate the config

list_pipelines()
run_pipeline(pipeline_name="config-from-kb", seed_session_id="<prior-session-id>",
             input_paths=[brief], context="...")
  └── 00_config-agent
        reads KB from seed (in place, no copy)
        reads the new brief
        generates config
→ done: config file + session_id
```

#### `output-feedback` — fix the KB when a generated output was wrong

Points at the run whose output was wrong via `seed_session_id`. Analyses the KB against
the complaint, proposes amendments for human review, then writes the approved changes
back into the KB in place. The next generation run picks up the improved KB automatically.

```
@likeminds the SOW you generated was wrong
@likeminds the document you produced is off-brand or incomplete
@likeminds fix whatever caused this bad output

list_pipelines()
run_pipeline(pipeline_name="output-feedback", seed_session_id="<prior-session-id>",
             context="the SOW missed the pricing table and used the wrong brand colour")
  └── 00_diagnose-bug (target=kb)
        reads KB + complaint
        proposes amendments → approval_sheet.md
        ← need_input: "please review and approve these amendments"
        (customer reviews, replies "approved")
  └── 01_apply-fixes (target=kb)
        applies approved amendments
        writes updated KB back into seed bucket in place
→ done: amended KB (same session_id — KB updated in place)
```

### `run_pipeline` protocol

```
# First call — start a pipeline
run_pipeline(pipeline_name, context?, input_paths?, artifacts?, urls?, seed_session_id?) →
  {status:"running", session_id, current_step, total_steps, step_name, progress}

# Poll — ONLY session_id, no other args
run_pipeline(session_id) →
  {status:"running",    session_id, current_step, total_steps, progress}
  {status:"need_input", session_id, questions[], next_step}   # relay questions verbatim

# Answer a need_input
run_pipeline(session_id, response, input_paths?) →
  {status:"running", …}   # resume polling

# Done
→ {status:"done", session_id, result_id, output_dir,
   summary:{files:[…]}, how_to_continue}

# Resume a failed pipeline from the failed step
run_pipeline(session_id, pipeline_name) →
  resumes from failed_step, completed steps are not re-run
```

**Receiving outputs:** On `done`, the deliverable is on disk at `output_dir`
(`outputs/mcp/pipeline_<id>/<NN>_<skill>/`) and `summary.files` names every file in it.
Save the `session_id` — pass it as `seed_session_id` on a future `run_pipeline` call to
build on this run's output.

---

## How the MCP server works

A local MCP server that lets a Claude client run multi-step pipelines **without seeing
the skill prompts** — each step executes server-side inside a real `claude -p` process,
pausing to ask the user questions and returning finished files by reference.

```
Claude client ──run_pipeline──▶  likeminds server  ──spawns──▶  claude -p  (runs step N)
      ▲                               │  (background task)           │
      │◀──── poll / questions ────────┤                              │ reads inputs/, writes output/
      │────── answers ────────────────▶  ──resume──▶  claude -p  ◀──┘
      │◀──── output_dir (done) ────────┘         (same session, next turn)
                                                          │
        input_paths / artifacts ──▶ .sessions/<uuid>/inputs/
                                                          ▼
                                    outputs/mcp/pipeline_<id>/, sandbox purged
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
file byte-for-byte (so PDFs/DOCX/XLSX survive), promotes it to
`outputs/mcp/<result_id>/`, and returns that path plus the file list in the `done`
snapshot. The session sandbox and its Claude Code transcript are then purged.

**Modules:**


| Module        | Responsibility                                                                                                     |
| ------------- | ------------------------------------------------------------------------------------------------------------------ |
| `server.py`   | FastMCP HTTP server + 2 tools (`run_pipeline`, `list_pipelines`); background pipeline driver; input staging; output harvest/promote; credential config; long-poll. |
| `engine.py`   | Runs ONE turn: builds the `claude -p` argv, spawns it, reads the stream-json, parses the signal markers.           |
| `harness.py`  | The system-prompt append that binds a skill's I/O edges to the engine.                                             |
| `sessions.py` | Lightweight in-process session records + sandbox/transcript purge + record GC.                                     |
| `registry.py` | Indexes `.claude/skills/*/SKILL.md` so any skill is runnable.                                                      |
| `pipeline.py` | Pipeline definitions from `.claude/pipelines.json`, pipeline session state, disk persistence + resume.             |
| `config.py`   | Paths, host/port, CLI binary, model, markers, safety bounds.                                                       |
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

`run_pipeline` **long-polls**: each call waits up to `POLL_WAIT` (~4s) for the state to
change, then returns a snapshot. The background `_drive_pipeline` task owns the real work;
the tool handlers only read session state to answer polls.

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
| **Record caps**     | `MAX_SESSIONS` evicts oldest FINISHED session records so the in-memory store can't grow without bound; live sessions are never evicted.                                                                                                                                        |
| **MCP isolation**   | Every turn uses `--strict-mcp-config` with the server's own empty `--mcp-config`, keeping the spawned `claude` off the project `.mcp.json` — otherwise it would connect back to *this* server (recursion) and spawn every project MCP server each turn. |


> `TURN_TIMEOUT` / `REPLY_TIMEOUT` are passed to `asyncio.wait_for`, which is in
> **seconds** (e.g. `1800` = 30 min, `3600` = 1 h), set via `LIKEMINDS_MCP_TURN_TIMEOUT`
> / `LIKEMINDS_MCP_REPLY_TIMEOUT`.

---

## Skills and the kill-switch

The server runs every Agent Skill in `.claude/skills/` — the built-ins shipped here plus
any skill a run generated and the server installed. The folder name is the skill name;
there are no accounts, no per-caller scoping, and no private copies, because the server
runs on your machine and serves you.

**Generated skills.** If a run produces a `<skill-name>/SKILL.md` folder in its output,
the server copies it into `.claude/skills/<skill-name>/` (rewriting the SKILL.md `name:`
to match the folder) and appends that path to `.gitignore`. It is then runnable as a
pipeline step by that name. Registration is a COPY — the generated files also stay in the
run's output bucket, so you always get to inspect and keep what a run produced.

**Disabling a skill.** To stop a skill being listed or run, add its name to
`disabled_skills.json` at the project root:

```json
{ "disabled": ["some-skill", "another-skill"] }
```

The file is read fresh on each call, so changes take effect with no restart. You can also
set `LIKEMINDS_MCP_DISABLED_SKILLS=a,b` as an env override, merged with the file.

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

### File I/O

The server and the client share a filesystem — that is the design. Inputs arrive as
**local paths** and outputs are **left on disk**; there is no object store and nothing
leaves the machine except the model calls themselves.

**Input:**

```
# a file, a whole folder, or both
run_pipeline(pipeline_name="build-kb",
             input_paths=["/abs/path/sow.pdf", "/abs/path/samples/"], context="…")

# text you already have in the conversation
run_pipeline(pipeline_name="build-kb",
             artifacts=[{"name":"mom.txt","content":"…"}], context="…")
```

Each path is copied into that run's sandbox at `.sessions/<uuid>/inputs/` (a folder keeps
its layout), so the skill reads a stable snapshot and the originals are never touched. The
sandbox is deleted when the run ends.

**Output:**

```
run_pipeline(session_id) →
  {status:"done",
   session_id: "abc12345",
   result_id: "pipeline_abc12345/00_kb-builder",
   output_dir: "/path/to/repo/outputs/mcp/pipeline_abc12345/00_kb-builder",
   summary:{files:["01-overview.md", "02-visual-style.md"]},
   how_to_continue: "To generate a document from this KB, call run_pipeline with seed_session_id='abc12345'…"}
```

`next_step` tells the calling client to report every file with its path and, when the user
wants them elsewhere (their project directory, say), to copy them there too. Save the
`session_id` — pass it as `seed_session_id` on a future `run_pipeline` call to build on this
run's output without re-supplying the source files.


