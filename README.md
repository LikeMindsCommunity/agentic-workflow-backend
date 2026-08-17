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
          Outputs land in outputs/ on disk
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
| `document-from-kb` † | Generate a document from an already-built KB - skips the KB step | `generate another SOW, use KB from session <id>` |
| `config-generator` | Build KB then generate a structured config (JSON/XML/YAML/NodeFlow) end to end | `generate a config from these reference files` |
| `config-from-kb` † | Generate a config from an already-built KB - skips the KB step | `generate another config, use KB from session <id>` |
| `code-integration` | Build KB from a platform's SDK/API docs then write the integration code for your project | `here are the SDK docs, integrate this into my app` |
| `code-from-kb` † | Write integration code from an already-built KB | `wire the SDK into this repo, KB from session <id>` |
| `map-website-kb` | Drive a real browser over a live site and map its screens, locators, and flows into a KB - nothing is executed | `map this website so we can automate it later` |
| `browser-automation` | Map the site then carry out the SOW's workflow live in a browser | `there's no API, do these tasks on the site for me` |
| `browser-run-from-kb` † | Run a workflow live in the browser against an already-mapped site | `run this SOW against the site we mapped` |
| `design-api-lld` | Build KB from API docs then design an LLD (execution document) - nothing is called | `turn this OpenAPI spec into an execution plan` |
| `api-automation` | Build KB, design the LLD, then execute it as live API calls | `read these API docs and run the workflow` |
| `api-lld-from-kb` † | Design another LLD from an already-built API KB | `design another workflow, KB from session <id>` |
| `run-lld` | Execute an LLD live - pass the LLD itself as a file, not a session id | `run this LLD against sandbox` |
| `output-feedback` † | Fix the KB when a generated output was wrong | `the document from session <id> was wrong, fix it` |

† Needs a `seed_session_id` - the session ID of the earlier run that built the KB. See [Session IDs](#session-ids).

Code, browser, and API pipelines are interactive: they pause to ask for credentials, one-time codes, an environment choice, or a go-ahead before anything that changes state.

### Session IDs

Every run produces a `session_id`. Claude reports it when the run finishes - **save it**.

Pass it as `seed_session_id` on any follow-up run to reuse the KB from that session without re-uploading files. This is how you generate multiple documents or configs for different deals from the same KB.

```
@likeminds generate a SOW for Acme Corp's mobile phase, use KB from session abc-123
[attach: acme-mobile-brief.pdf]
```

### Example prompts

**Build a knowledge base** - `build-kb`, `map-website-kb`

```
@likeminds build the KB for Acme Corp from these reference SOWs
[attach: acme-sow-1.pdf, acme-playbook.docx]

@likeminds map https://portal.example.com into a KB - walk the journeys in this SOW, don't run anything yet
[attach: portal-sow.pdf]
```

**Documents** - `document-agent`, `document-from-kb`

```
@likeminds generate a SOW for TechCorp - 3 month engagement, 2 engineers, cloud migration
[attach: techcorp-brief.pdf, sample-sow-1.pdf, sample-sow-2.pdf]

@likeminds generate a SOW for Acme's mobile phase, use KB from session abc-123
[attach: acme-mobile-brief.pdf]
```

**Configs** - `config-generator`, `config-from-kb`

```
@likeminds generate a JSON config for the campaign flow from these reference configs
[attach: sample-config-1.json, nodeflow-schema.pdf]

@likeminds generate the config for the re-engagement campaign, use KB from session xyz-456
[attach: re-engagement-brief.pdf]
```

**Integration code** - `code-integration`, `code-from-kb`

```
@likeminds here are the payments SDK docs - add checkout to my Next.js app at ~/work/storefront
[attach: payments-sdk-guide.pdf]

@likeminds wire that SDK into this repo, use KB from session def-789
```

The server has no access to your project. It returns the code plus an `integration.json` manifest saying where each file goes, and your client applies it.

**Browser workflows** - `browser-automation`, `browser-run-from-kb`

```
@likeminds no API for this portal - map https://portal.example.com and run the tasks in this SOW
[attach: portal-sow.pdf]

@likeminds run this SOW against the site we mapped in session ghi-012
[attach: weekly-upload-sow.pdf]
```

**API workflows** - `design-api-lld`, `api-automation`, `api-lld-from-kb`, `run-lld`

```
@likeminds turn this OpenAPI spec and SOW into an execution document - I want to review it before anything runs
[attach: openapi.yaml, integration-sow.pdf]

@likeminds read these API docs and run the workflow in the SOW against sandbox
[attach: api-reference.pdf, integration-sow.pdf]

@likeminds the plan looks good, run this LLD
[attach: lld.md, sandbox.env]
```

**Fix a bad output** - `output-feedback`

```
@likeminds the SOW from session abc-123 used the wrong pricing format and missed the payment schedule - fix it for next time
```

Then generate again with the same session ID and the output reflects the fix.


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

---

## Production Deployment

To expose the server to remote clients, bind it to `0.0.0.0` in `.env`:

```bash
LIKEMINDS_MCP_HOST=0.0.0.0
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

Deliverables land in `outputs/` on the server.

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
│   │   ├── browser-agent/            #   execute a web-flow SOW live in a browser
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
