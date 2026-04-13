# LikeMinds Layer 1 — Platform Knowledge Base Builder

Builds a structured markdown knowledge base (KB) from a client's platform artifacts and documentation. The KB captures everything a downstream system needs to automatically generate valid configuration files, integrations, or workflows for that platform from natural language.

**Example:** Given sample Exotel IVR JSON files and API docs, the system produces a KB documenting every node type, field, transition event, and validation rule — so a Layer 2 agent can generate new IVR flows from plain English.

---

## Quick Start (Claude Code)

The primary way to use this tool is the **`/platform-kb`** skill in Claude Code.

### 1. Open the project in Claude Code

```bash
cd agentic-workflow-backend
claude
```

### 2. Drop your input materials

| Folder | What to put here |
|---|---|
| `inputs/sample_artifacts/` | Platform-generated files (JSON, XML, YAML, config files, etc.) |
| `inputs/docs/` | Documentation in any format (markdown, PDF, Word, Excel, PowerPoint, HTML, images) |

Both folders are optional. You can also pass file paths, URLs, or context directly as arguments.

### 3. Run the skill

```
/platform-kb
```

Or with arguments:

```
/platform-kb Here are Exotel IVR flow JSONs in inputs/sample_artifacts/ and API docs at https://developer.exotel.com/api/nodeflows
```

That's it. The skill handles everything from there.

---

## What `/platform-kb` Does

The skill runs a self-contained loop inside a single Claude Code session:

```
Phase 1 — INVENTORY & ANALYSIS
  Catalog all provided materials (artifacts, docs, URLs, screenshots, transcripts)
  Auto-detect mode (artifacts+docs, artifacts-only, docs-only, prompt-only)
  Classify use case (component-flow, api-sdk, artifact-generator, event-driven, etc.)
  Deep structural analysis of artifacts (fields, enums, ID chains, relationships)
  Cross-reference across all materials
  Fetch any provided URLs (WebFetch → Playwright fallback for JS/protected sites)

Phase 2 — DRAFT KB
  Write the full structured KB markdown file to outputs/

Phase 3 — GAP ANALYSIS
  Identify up to 5 missing knowledge areas
  Present gaps grouped by priority: BLOCKING / IMPORTANT / NICE TO HAVE

Phase 4 — ENRICHMENT  (loops back to Phase 3)
  User provides: a URL, "file", or plain text explanation
  Rewrite the KB incorporating the new info
  Loop back to Gap Analysis until ready or user types "done"
```

### Supported input formats

The skill reads everything natively — no conversion needed:

- **Structured files:** JSON, XML, YAML, HTML
- **Documents:** PDF, Word (.docx), Excel (.xlsx/.csv), PowerPoint (.pptx), plain text, markdown
- **Images:** PNG, JPG, GIF, WebP (screenshots, architecture diagrams, flow charts)
- **Specs:** OpenAPI/Swagger, Postman collections
- **Other:** Call transcripts, SOW documents, meeting notes

### Use-case classification

The skill auto-detects what kind of platform you're working with:

| Use Case | Signals | Examples |
|---|---|---|
| `component-flow` | Nodes, steps, blocks, transitions, visual flows | IVR builders, workflow engines, no-code tools |
| `api-sdk` | REST/GraphQL endpoints, SDK methods, auth tokens | Twilio, Stripe, Salesforce API |
| `artifact-generator` | Output files with strict schemas, validation rules | Config generators, template engines |
| `event-driven` | Webhooks, callbacks, event payloads, triggers | Event buses, notification systems |
| `data-platform` | Entities, relationships, CRUD, data models | CRMs, databases, analytics platforms |
| `config-system` | Config hierarchies, feature flags, env-specific settings | Infrastructure platforms, deployment tools |

A platform can match multiple use cases (e.g., an IVR builder is both `component-flow` and `artifact-generator`).

### Responding to gaps

After each gap analysis round you can:

| Input | What happens |
|---|---|
| A URL | Agent fetches and reads it (Playwright used if blocked) |
| `file` | Agent re-reads `inputs/docs/` for anything newly added |
| Text explanation | Used directly to fill the gaps |
| `done` | Ends the loop, saves the final KB |

### Web research

When you provide URLs, the skill follows a smart fetch pipeline:

1. **Check for AI-friendly indexes** — `llms-full.txt`, `llms.txt`, `sitemap.xml` at the docs origin
2. **WebFetch** — try direct fetch first
3. **Playwright stealth browser** — fallback for JS-rendered sites, 403s, Cloudflare challenges, SPAs that 404 on direct requests
4. **WebSearch** — last resort if the page is genuinely dead

Playwright MCP is pre-configured in `.mcp.json` and activates automatically when Claude Code starts in this directory.

---

## Input Modes

The skill auto-detects what you provided and adapts accordingly:

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
  <platform>/
    kb/
      kb_<platform>_draft.md         <- initial draft
      kb_<platform>_r1.md            <- after round 1 enrichment
      kb_<platform>_r2.md            <- after round 2 enrichment
      kb_<platform>_FINAL.md         <- final deliverable
```

---

## Related Skills

The `/platform-kb` skill is the all-in-one workflow. These sub-skills exist for advanced use but are normally called internally:

| Skill | Purpose |
|---|---|
| `/build-kb` | Orchestrator — older version, drives the same pipeline loop |
| `/build-kb-draft` | Draft sub-agent only |
| `/build-kb-interrogate` | Gap analysis sub-agent only (read-only) |
| `/build-kb-enrich` | Enrichment sub-agent only |

---

## Python SDK (Alternative)

The same pipeline is also available as a Python SDK implementation for embedding in larger pipelines or when you need programmatic control.

### Setup

```bash
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
```

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

### Configure your task

Edit `inputs/input_config.yaml`:

```yaml
prompt: |
  I want to automate the creation of IVR workflows for the Exotel platform.
  The final artifact is a JSON file representing a complete IVR call flow.
  Documentation: https://developer.exotel.com/api/nodeflows
```

### Run

```bash
python main.py
```

### How the SDK works

Python owns the loop. Three agents are called in sequence via `claude_agent_sdk`. Each is a single `query()` call with its own system prompt and tool set.

```
orchestrator.py
  | run_draft_agent()          -> writes KB to outputs/
  | run_interrogator_agent()   -> returns JSON gap report
  | display gaps (CLI)
  <- user input
  | run_enrichment_agent()     -> rewrites KB
  | run_interrogator_agent()   -> re-reviews
  (repeat until ready or user types "done")
  | copy latest -> kb_FINAL.md
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

## Project Structure

```
agentic-workflow-backend/
  main.py                        # Python SDK entrypoint (anyio.run)
  orchestrator.py                # Python loop: draft -> gap analysis -> enrich
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
      platform-kb.md             # Primary skill — full KB generation workflow
      build-kb.md                # Orchestrator — drives the pipeline loop
      build-kb-draft.md          # Draft sub-agent instructions
      build-kb-interrogate.md    # Interrogator sub-agent instructions
      build-kb-enrich.md         # Enrichment sub-agent instructions
```

---

## Comparison

| | `/platform-kb` (Claude Code) | Python SDK |
|---|---|---|
| **Entry point** | `/platform-kb` | `python main.py` |
| **How it runs** | Single self-contained Claude session | Python orchestrator + 3 agent calls |
| **Input formats** | All (PDF, DOCX, XLSX, PPTX, images, etc.) | Text-based formats |
| **Web research** | WebFetch + Playwright + WebSearch | WebFetch + Playwright |
| **Loop control** | Skill drives the loop internally | Python `while True` |
| **Gap output** | Prose presented inline | JSON parsed by Python |
| **Observability** | Chat transcript | Token counts, timing, tool logs |
| **Setup** | Claude Code only | Python + virtualenv + `.env` |
