# LikeMinds Agentic Workflow Backend

A self-hosted MCP server that gives any Claude client a library of multi-step agent pipelines - build knowledge bases, generate structured documents and configs, run live API workflows, and apply automated bug fixes - through simple `@likeminds` messages.

Every pipeline pauses and asks clarifying questions when it needs them, then resumes where it left off. No babysitting required.

---

## How it works

```
Claude client  →  @likeminds message
                       ↓
              MCP server (this repo)
                       ↓
         Runs a pipeline of Agent Skills
         (each skill = one Claude Code turn)
                       ↓
          Outputs land in outputs/ locally
          (or R2 presigned URLs if configured)
```

The server drives **Claude Code CLI** as a subprocess. Each pipeline is a sequence of skills defined in `.claude/pipelines.json`. Skills are Claude Code Agent Skills - plain markdown instruction files in `.claude/skills/`. The engine is skill-agnostic: the same server runs any skill you drop in, whether built-in or custom.

---

## Prerequisites

- **Python 3.10+**
- **Claude Code CLI** installed and on your `PATH` - [install guide](https://docs.anthropic.com/en/docs/claude-code)
- An Anthropic API key **or** a Claude subscription token (Max or Pro)

---

## Quickstart

```bash
# 1. Clone and install
git clone https://github.com/LikeMindsCommunity/agentic-workflow-backend.git
cd agentic-workflow-backend

python3 -m venv venv
venv/bin/pip install -r requirements.txt

# 2. Configure credentials
cp .env.example .env
# Edit .env - set either ANTHROPIC_API_KEY or CLAUDE_TOKEN (see below)

# 3. Start the server
venv/bin/python -m likeminds_mcp
# → serving on http://127.0.0.1:8787/mcp

# 4. Connect Claude Code (in a new terminal)
claude mcp add --transport http --scope user likeminds http://127.0.0.1:8787/mcp
```

Then open Claude Code from any directory and run `@likeminds build a knowledge base from these files`.

---

## Auth

The server spawns Claude Code CLI per turn. Set one of the following in `.env`:

```bash
# Option A - Claude subscription (Max or Pro)
# Run `claude setup-token` to generate the token, then paste it here:
CLAUDE_TOKEN=sk-ant-oat01-...

# Option B - Anthropic API key
ANTHROPIC_API_KEY=sk-ant-api03-...
```

If both are set, the API key takes precedence.

**Bring your own key (BYOK):** Callers can also pass an Anthropic key per request so inference bills to their account instead of yours:

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

Prefix any message with `@likeminds` to route it through the server. Claude discovers available pipelines automatically and picks the right one.

```
@likeminds build a knowledge base from these files
@likeminds generate a SOW from these reference documents
@likeminds the document you produced was wrong, fix it
```

Attach files directly to the message, or pass public URLs. Add free-text instructions to guide the output:

```
@likeminds generate a SOW for TechCorp - 3 month engagement, 2 engineers, focus on cloud migration
[attach: techcorp-brief.pdf, sample-sow-1.pdf]
```

### Available pipelines

| Pipeline | What it does | Example trigger |
| -------- | ------------ | --------------- |
| `build-kb` | Extract format and product knowledge from reference files into a reusable KB | `build the KB`, `onboard this client` |
| `document-agent` | Build KB then generate a finished document (PDF/DOCX) end to end | `generate a SOW from these reference docs` |
| `document-from-kb` | Generate a document from an already-built KB - skips the KB step | `generate another SOW, use KB from session <id>` |
| `config-generator` | Build KB then generate a structured config (JSON/XML/YAML) end to end | `generate a config from these reference files` |
| `config-from-kb` | Generate a config from an already-built KB - skips the KB step | `generate another config, use KB from session <id>` |
| `output-feedback` | Fix the KB when a generated output was wrong | `the document from session <id> was wrong, fix it` |

### Session IDs

Every run produces a `session_id`. Claude reports it when the run finishes - **save it**.

Pass it as `seed_session_id` on any follow-up run to reuse the KB from that session without re-uploading files. This is how you generate multiple documents or configs for different deals from the same KB.

```
@likeminds generate a SOW for Acme Corp's mobile phase, use KB from session abc-123
[attach: acme-mobile-brief.pdf]
```

---

## Configuration

All env vars - set persistent ones in `.env`:

| Variable | Description | Default |
| -------- | ----------- | ------- |
| `CLAUDE_TOKEN` | Subscription token (`claude setup-token`) → `CLAUDE_CODE_OAUTH_TOKEN` | required unless API key |
| `ANTHROPIC_API_KEY` | API key fallback (takes precedence over `CLAUDE_TOKEN`) | unset |
| `LIKEMINDS_MCP_KEY_HEADER` | Header to read the caller's BYOK key from | `x-api-key` |
| `CLAUDE_AGENT_MODEL` | Model for spawned turns | `opus[1m]` |
| `CLAUDE_BIN` | Path to the `claude` CLI | resolved from `PATH` |
| `LIKEMINDS_MCP_HOST` | Bind address | `127.0.0.1` |
| `LIKEMINDS_MCP_PORT` | Port | `8787` |
| `LIKEMINDS_MCP_TURN_TIMEOUT` | Per-turn timeout, seconds | `1800` (30 min) |
| `LIKEMINDS_MCP_REPLY_TIMEOUT` | Wait-for-user-reply timeout, seconds | `3600` (1 h) |
| `LIKEMINDS_MCP_DISABLED_SKILLS` | Comma-separated skill names to disable globally | unset |
| `R2_BUCKET` | Cloudflare R2 bucket name (remote deployments only) | R2 disabled if unset |
| `R2_ACCESS_KEY_ID` | R2 access key | |
| `R2_SECRET_ACCESS_KEY` | R2 secret key | |
| `R2_ENDPOINT` | R2 endpoint URL | |
| `R2_URL_EXPIRY` | Presigned GET URL TTL for downloads, seconds | `3600` (1 h) |

---

## Production Deployment

To expose the server to remote clients, bind it to `0.0.0.0` and set up Cloudflare R2 for file transfers:

```bash
# .env
LIKEMINDS_MCP_HOST=0.0.0.0
R2_BUCKET=your-bucket
R2_ACCESS_KEY_ID=...
R2_SECRET_ACCESS_KEY=...
R2_ENDPOINT=https://<account_id>.r2.cloudflarestorage.com
```

Start with Python or Docker:

```bash
# Python
venv/bin/python -m likeminds_mcp

# Docker
docker compose up -d
```

Point clients at the public URL:

```bash
claude mcp add --transport http --scope user likeminds https://<your-host>/mcp
```

**Remote file input flow:** Upload files to R2 first, then pass the keys to `run_pipeline`:

```bash
# 1. Get a presigned upload URL
get_upload_url("brief.pdf") → {upload_url, r2_key}

# 2. Upload
curl -X PUT <upload_url> --data-binary @brief.pdf

# 3. Run the pipeline
run_pipeline(pipeline_name="build-kb", r2_keys=["<r2_key>"], context="...")
```

On `done`, `download_urls` maps each output filename to a presigned R2 GET URL. Re-poll with the same `session_id` for fresh links after they expire.

**R2 is optional for local use.** Without it, `get_upload_url` is unavailable and deliverables land in `outputs/mcp/pipeline_<id>/` on disk.

---

## Adding Custom Skills

Drop a new skill folder under `.claude/skills/<skill-name>/` with a `SKILL.md` file. The server picks it up automatically on restart - no code changes needed. Add it to a pipeline in `.claude/pipelines.json` to make it reachable via `@likeminds`.

---

## Project Structure

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

## License

Licensed under the Apache License, Version 2.0. See [LICENSE](LICENSE) for details.
