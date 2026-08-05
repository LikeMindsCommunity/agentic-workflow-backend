# LikeMinds Agentic Workflow Backend

A local MCP server (`likeminds_mcp`) that exposes a library of **Claude Code Agent Skills** over HTTP, letting any Claude client run multi-step pipelines - build a knowledge base, generate structured configs, write SOW/BRD documents, run live API workflows, or apply automated bug fixes - through simple `@likeminds` messages, with pause/resume round-trips for questions.

Every skill is **platform-agnostic**: it learns what to do from a knowledge base (KB) built once from a client's own artifacts. Same skill, any platform.

---

## Folder structure

```
agentic-workflow-backend/
├── .claude/
│   ├── skills/                       # Agent Skills invoked by the server
│   │   ├── kb-builder/               #   raw artifacts → knowledge base
│   │   ├── config-agent/             #   KB + SOW → structured config
│   │   ├── code-agent/               #   KB + SOW → integration code
│   │   ├── api-agent/                #   KB + SOW → LLD / execution document
│   │   ├── runner-agent/             #   execute an LLD live
│   │   ├── document-generator/       #   KB + MOM → finished document (PDF or DOCX)
│   │   ├── find-bugs/                #   generated + expected → comparison sheet
│   │   ├── diagnose-bug/             #   bug report → fix proposal
│   │   ├── process-comparison/       #   approved comparisons → fix proposals (with RCA)
│   │   └── apply-fixes/              #   apply APPROVED fixes + git commit
│   ├── pipelines.json                # pipeline definitions (sequences of skills)
│   └── settings.json                 # Claude Code settings
├── likeminds_mcp/                    # MCP server package
│   ├── server.py                     #   FastMCP HTTP server, tools, pipeline driver
│   ├── engine.py                     #   spawns one `claude -p` turn, parses signal markers
│   ├── harness.py                    #   skill-agnostic I/O envelope (appended to system prompt)
│   ├── pipeline.py                   #   pipeline session state + disk persistence
│   ├── sessions.py                   #   in-process session records + sandbox purge
│   ├── registry.py                   #   indexes .claude/skills so any skill is runnable
│   ├── config.py                     #   all env vars and path constants
│   └── __main__.py                   #   `python -m likeminds_mcp` entrypoint
├── inputs/                           # drop client artifacts here (gitignored)
├── outputs/                          # deliverables land here (gitignored)
├── .mcp.json                         # registers likeminds for the Claude Code CLI
├── .env / .env.example               # credentials and config (.env is gitignored)
├── Dockerfile / docker-compose.yml   # container setup
└── requirements.txt                  # server dependencies
```

`.sessions/` (per-run sandboxes) and `venv/` are created locally and are gitignored.

---

## Setup

**1. Clone and install**

```bash
git clone https://github.com/LikeMindsCommunity/agentic-workflow-backend.git
cd agentic-workflow-backend

python3 -m venv venv
venv/bin/pip install -r requirements.txt
```

The server drives **Claude Code CLI** as a subprocess, so `claude` must be on your `PATH`.

**2. Configure credentials**

Copy `.env.example` to `.env` and fill in the values you need:

```bash
cp .env.example .env
```

Minimum for local use (pick one auth method):

```bash
# Option A: use your Claude subscription
claude setup-token          # prints a token
# paste it as CLAUDE_TOKEN=... in .env

# Option B: use an Anthropic API key
# set ANTHROPIC_API_KEY=... in .env
```

**3. Start the server**

```bash
venv/bin/python -m likeminds_mcp      # serves http://127.0.0.1:8787/mcp
```

---

## Connect from Claude Code (CLI)

`.mcp.json` in the project root already registers the server. To use it:

1. Start the server (above) in its own terminal.
2. Open `claude` in this repo - it reads `.mcp.json` automatically.
3. Run `/mcp` - `likeminds` should show as **connected**.

To reach `likeminds` from **any directory**, register it once at user scope:

```bash
claude mcp add --transport http --scope user likeminds http://127.0.0.1:8787/mcp
```

**Bring your own Anthropic key (BYOK):** To bill inference to your own account, add a header:

```bash
claude mcp add --transport http --scope user likeminds http://127.0.0.1:8787/mcp \
    --header "x-api-key: sk-ant-api03-YOURKEY"
```

The key is injected per request into the spawned subprocess and never stored.

---

## Connect from Claude Desktop

Claude Desktop requires a stdio bridge (`mcp-remote`) to reach an HTTP server. Node.js must be installed.

Add `likeminds` under `mcpServers` in Claude Desktop settings:

```json
"mcpServers": {
  "likeminds": {
    "command": "npx",
    "args": ["-y", "mcp-remote", "http://127.0.0.1:8787/mcp"]
  }
}
```

Save and restart Claude Desktop.

---

## Using the Server

Prefix any message with `@likeminds` to invoke the server. Claude calls `list_pipelines` to discover available pipelines, then `run_pipeline` with the right one.

```
@likeminds build a knowledge base from these files
@likeminds generate a SOW from these reference documents
@likeminds the document you produced was wrong, fix it
```

Attach files directly to the message (or pass public URLs). Add free-text instructions to guide the output:

```
@likeminds generate a SOW for TechCorp - 3 month engagement, 2 engineers, focus on cloud migration
[attach: techcorp-brief.pdf, sample-sow-1.pdf]
```

### Tools exposed

| Tool | What it does |
| ---- | ------------ |
| `list_pipelines` | Returns all available pipelines with names, descriptions, steps, and trigger phrases. Always called before `run_pipeline`. |
| `run_pipeline` | Runs a named pipeline. Returns `running` / `need_input` / `done`. Poll with `session_id`. On `done`, download links are returned for every output file. |
| `get_upload_url` | Get a presigned PUT URL to upload a file directly to R2 (when R2 is configured). Returns `{upload_url, r2_key}`. PUT file bytes to `upload_url`, then pass `r2_key` to `run_pipeline` via `r2_keys`. |

### Available pipelines

| Pipeline | What it does | Trigger phrase examples |
| -------- | ------------ | ----------------------- |
| `build-kb` | Build a knowledge base from uploaded reference files | `build the KB`, `onboard this client` |
| `document-agent` | Build KB then generate a finished document (PDF/DOCX) | `generate a SOW from these reference docs` |
| `document-from-kb` | Generate a document from an already-built KB (pass `seed_session_id`) | `generate another SOW from the same KB` |
| `config-generator` | Build KB then generate a structured config (JSON/XML/YAML) | `generate config from these reference files` |
| `config-from-kb` | Generate a config from an already-built KB (pass `seed_session_id`) | `generate another config from the same KB` |
| `output-feedback` | Fix the KB when a generated output was wrong (pass `seed_session_id`) | `the document you produced was wrong, fix it` |

**Save your session ID.** After a run finishes, Claude reports the `session_id`. Pass it as `seed_session_id` on the next `run_pipeline` call to build on that run's KB without re-uploading files.

---

## Configuration

All env vars; persistent ones go in `.env`:

| Variable | Description | Default |
| -------- | ----------- | ------- |
| `CLAUDE_TOKEN` | Subscription token → `CLAUDE_CODE_OAUTH_TOKEN` | required unless API key or CLI login |
| `ANTHROPIC_API_KEY` | Server API key fallback (takes precedence over subscription) | unset |
| `LIKEMINDS_MCP_KEY_HEADER` | Header to read the caller's BYOK Anthropic key from | `x-api-key` |
| `CLAUDE_AGENT_MODEL` | Model for spawned turns | `opus[1m]` |
| `CLAUDE_BIN` | Path to the `claude` CLI | resolved from `PATH` |
| `LIKEMINDS_MCP_HOST` | Bind address | `127.0.0.1` (set `0.0.0.0` for remote) |
| `LIKEMINDS_MCP_PORT` | Port | `8787` |
| `LIKEMINDS_MCP_TURN_TIMEOUT` | Per-turn timeout, seconds | `1800` (30 min) |
| `LIKEMINDS_MCP_REPLY_TIMEOUT` | Wait-for-user-reply timeout, seconds | `3600` (1 h) |
| `R2_BUCKET` | Cloudflare R2 bucket name | (R2 disabled if any R2 var is missing) |
| `R2_ACCESS_KEY_ID` | R2 access key | |
| `R2_SECRET_ACCESS_KEY` | R2 secret key | |
| `R2_ENDPOINT` | R2 endpoint (`https://<account_id>.r2.cloudflarestorage.com`) | |
| `R2_URL_EXPIRY` | Presigned GET URL TTL for downloads, seconds | `3600` (1 h) |
| `LIKEMINDS_MCP_DISABLED_SKILLS` | Comma-separated skill names to disable globally | unset |

**R2 is optional.** Without R2, `get_upload_url` returns an error and `run_pipeline` does not return `download_urls`. Deliverables still land in `outputs/mcp/pipeline_<id>/` on the server.

---

## Production Deployment

```bash
# 1. Set host + R2 in .env
LIKEMINDS_MCP_HOST=0.0.0.0
R2_BUCKET=...
R2_ACCESS_KEY_ID=...
R2_SECRET_ACCESS_KEY=...
R2_ENDPOINT=https://<account_id>.r2.cloudflarestorage.com

# 2. Start the server
venv/bin/python -m likeminds_mcp

# 3. Point clients at the public URL
claude mcp add --transport http --scope user likeminds https://<your-host>/mcp
```

Or use Docker:

```bash
docker compose up -d
```

**File input flow for remote clients:**

```bash
# Upload files to R2 first
get_upload_url("brief.pdf") → {upload_url, r2_key}
curl -X PUT upload_url --data-binary @brief.pdf

# Then start the pipeline
run_pipeline(pipeline_name="build-kb", r2_keys=["<r2_key>"], context="...")
```

On `done`, `download_urls` maps each output filename to a presigned R2 GET URL (valid for `R2_URL_EXPIRY` seconds). Re-poll the same `session_id` to get fresh links after they expire.

---

## License

Licensed under the Apache License, Version 2.0. See [LICENSE](LICENSE) for details.
