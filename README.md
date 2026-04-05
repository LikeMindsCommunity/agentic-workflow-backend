# LikeMinds Layer 1 — Platform Knowledge Base Builder

Builds a structured markdown knowledge base (KB) from a client's platform artifacts and documentation. The KB captures everything a downstream system needs to automatically generate valid configuration files, integrations, or workflows for that platform from natural language.

**Example:** Given sample Exotel IVR JSON files and API docs, the system produces a KB documenting every node type, field, transition event, and validation rule — so a Layer 2 agent can generate new IVR flows from plain English.

---

## Setup

### 1. Install dependencies

```bash
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
```

### 2. Configure credentials

Copy `.env.example` to `.env` and fill in your credentials:

```bash
cp .env.example .env
```

**Option A — Direct Anthropic API:**
```
ANTHROPIC_API_KEY=sk-ant-...
```

**Option B — Azure AI Foundry:**
```
CLAUDE_CODE_USE_FOUNDRY=1
ANTHROPIC_FOUNDRY_API_KEY=<your-foundry-key>
ANTHROPIC_FOUNDRY_RESOURCE=<your-foundry-resource>
```

### 3. Configure your task

Edit `inputs/input_config.yaml`:

```yaml
prompt: |
  I want to automate the creation of IVR workflows for the Exotel platform.
  The final artifact is a JSON file representing a complete IVR call flow.
  Documentation: https://developer.exotel.com/api/nodeflows
```

Write naturally — include the platform name, what you want to automate, and any documentation URLs. The agent infers the rest.

### 4. Add optional inputs

| Folder | What to put here |
|---|---|
| `inputs/sample_artifacts/` | Sample/reference output files (JSON, XML, config files) |
| `inputs/docs/` | Local documentation (markdown, PDF, YAML, HTML) |

Both folders are optional. The agent adapts based on what's present. Files can be added mid-run.

---

## Running

### Python SDK

```bash
python main.py
```

### Claude Code

Open the project in Claude Code and run:

```
/build-kb
```

Playwright MCP (for accessing bot-protected docs) is pre-configured in `.mcp.json` and activates automatically when Claude Code starts in this directory.

---

## How It Works

The pipeline runs three phases in a loop:

```
Phase 1 — DRAFT
  Read input_config.yaml + detect input mode
  Read all artifacts and local docs
  Fetch any URLs from the prompt (Playwright fallback for 403-protected sites)
  Write the initial KB markdown file

Phase 2 — GAP ANALYSIS
  Read the current KB
  Identify up to 5 knowledge areas still missing
  Present gaps grouped by priority: BLOCKING / IMPORTANT / NICE TO HAVE

Phase 3 — ENRICHMENT  (loops back to Phase 2)
  User provides: a URL, "file", or plain text explanation
  Rewrite the KB incorporating the new info
  Loop back to Gap Analysis until ready or user types "done"
```

### Responding to gaps

After each gap analysis round you can:

| Input | What happens |
|---|---|
| A URL | Agent fetches and reads it (Playwright used if blocked) |
| `file` | Agent re-reads `inputs/docs/` for anything newly added |
| Text explanation | Used directly to fill the gaps |
| `done` | Ends the loop, saves the final KB |

One response per round — URLs, files, and text can all be combined in one message.

---

## Input Modes

The agent auto-detects what you provided and adapts accordingly:

| Mode | Inputs available | Agent approach |
|---|---|---|
| `artifacts_and_docs` | Artifacts + docs/URLs | Maps every artifact element to docs; writes with authority |
| `artifacts_only` | Artifacts, no docs | Reverse-engineers structure; liberal "Needs Verification" callouts |
| `docs_only` | Docs/URLs, no artifacts | Extracts schema from docs; notes no artifact was validated |
| `prompt_only` | Prompt only | Fetches any URLs in prompt; writes skeleton with gaps if none |

---

## Output

Each run produces versioned `.md` files in `outputs/`:

```
outputs/
  kb_<platform>_draft.md         ← initial draft
  kb_<platform>_r1.md            ← after round 1 enrichment
  kb_<platform>_r2.md            ← after round 2 enrichment
  kb_<platform>_FINAL.md         ← final deliverable
```

---

## Project Structure

```
agentic-workflow-backend/
  main.py                        # thin entrypoint (anyio.run)
  orchestrator.py                # main loop: draft → gap analysis → enrich
  config.py                      # paths, model, MCP server config, env vars

  agents/
    draft.py                     # Draft agent — writes the initial KB
    interrogator.py              # Interrogator agent — identifies gaps (read-only)
    enrichment.py                # Enrichment agent — updates KB with new info
    scraper.py                   # Standalone scraper — web research utility
    prompts.py                   # All system prompts and shared KB structure

  utils/
    file_loader.py               # Loads input_config.yaml; detects input mode
    kb_utils.py                  # KB file path helpers
    cli.py                       # Terminal display and user input collection
    logging.py                   # Agent message/tool call logging

  inputs/
    input_config.yaml            # Edit this before each run
    sample_artifacts/            # Drop client artifact files here
    docs/                        # Drop client doc files here (can add mid-run)

  outputs/                       # Generated KB files (gitignored)

  .mcp.json                      # Playwright MCP server config (Claude Code)

  .claude/
    settings.json                # Claude Code model settings
    commands/
      build-kb.md                # Orchestrator — drives the full pipeline loop
      build-kb-draft.md          # Draft sub-agent instructions
      build-kb-interrogate.md    # Interrogator sub-agent instructions
      build-kb-enrich.md         # Enrichment sub-agent instructions
```

---

## Two Implementations

The same pipeline runs in two forms. Both produce identical KB output using the same structure, writing rules, and scope boundaries.

### Claude Code (`/build-kb`)

**Entry point:** `/build-kb` in Claude Code
**Files:** `.claude/commands/build-kb*.md`

The orchestrator (`build-kb.md`) spawns focused sub-agents for each phase using the Agent tool. Each sub-agent reads its own command file and runs in isolation:

| Sub-agent | Command file | Tools |
|---|---|---|
| Draft | `build-kb-draft.md` | Read, Glob, Write, WebFetch, WebSearch, Playwright MCP |
| Interrogator | `build-kb-interrogate.md` | Read, Grep (read-only) |
| Enrichment | `build-kb-enrich.md` | Read, Glob, Write, WebFetch, WebSearch |

The orchestrator parses each sub-agent's output, displays results, collects user input, and drives the loop.

**Playwright MCP** is registered via `.mcp.json` and available to sub-agents for accessing bot-protected documentation sites.

**Best for:** Interactive use, no Python setup needed.

---

### Python SDK (`python main.py`)

**Entry point:** `python main.py` → `orchestrator.py`
**Files:** `orchestrator.py`, `agents/*.py`, `agents/prompts.py`

Python owns the loop. Three agents are called in sequence via `claude_agent_sdk`. Each is a single `query()` call with its own system prompt and tool set.

```
orchestrator.py
  ↓ run_draft_agent()          → writes KB to outputs/
  ↓ run_interrogator_agent()   → returns JSON gap report
  ↓ display gaps (CLI)
  ← user input
  ↓ run_enrichment_agent()     → rewrites KB
  ↓ run_interrogator_agent()   → re-reviews
  (repeat until ready or user types "done")
  ↓ copy latest → kb_FINAL.md
```

The Interrogator returns structured JSON which Python parses to drive loop control:

```json
{
  "summary": "...",
  "ready_for_generation": false,
  "areas": [
    {
      "id": "a1",
      "priority": "blocking",
      "title": "...",
      "what_we_have": "...",
      "what_we_need": "...",
      "suggested_sources": "..."
    }
  ]
}
```

**Best for:** Reliable runs, token/timing visibility, embedding in a larger pipeline.

---

### Comparison

| | Claude Code | Python SDK |
|---|---|---|
| **Entry point** | `/build-kb` | `python main.py` |
| **Agent model** | Orchestrator + 3 sub-agents | 3 dedicated agent functions |
| **Loop control** | Orchestrator agent | Python `while True` |
| **Playwright MCP** | Available (via `.mcp.json`) | Available (via `config.py`) |
| **Gap output** | Prose formatted by orchestrator | JSON parsed by Python |
| **Observability** | Chat transcript | Token counts, timing, tool logs |
| **Setup** | Claude Code only | Python + virtualenv + `.env` |
