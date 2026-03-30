# LikeMinds Layer 1 — Platform Knowledge Base Builder

Builds a structured markdown knowledge base (KB) from a client's platform artifacts and documentation. The KB captures everything a downstream "Layer 2" system needs to automatically generate valid configuration files for that platform from natural language.

**Concrete example:** Given sample Exotel IVR JSON files and API docs, the system produces a KB documenting every node type, field, transition event, and validation rule — so Layer 2 can generate new IVR flows from plain English.

---

## Setup

```bash
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
```

Set your API key in `.env`:

```
ANTHROPIC_API_KEY=your-key-here
```

---

## Usage

**1. Describe your task in `inputs/input_config.yaml`:**

```yaml
prompt: |
  I want to automate the creation of IVR workflows for the Exotel platform.
  The final artifact is a JSON file that represents a complete IVR call flow.
  The system should generate these JSON files from natural language descriptions.
  Documentation: https://developer.exotel.com/api/nodeflows
```

Write naturally — include the platform name, what you want to automate, and any documentation URLs. The agent infers the rest.

**2. Drop your inputs:**

- **Sample artifacts** → `inputs/sample_artifacts/` (JSON, XML, or any config files)
- **Local docs** → `inputs/docs/` (markdown, text, YAML, HTML — can add mid-run)

**3. Run:**

```bash
python main.py
```

**4. Respond to knowledge gaps.** After the draft is written, the system identifies up to 5 knowledge areas that need filling. For each round you can:

- Paste a **URL** → agent fetches and reads it immediately
- Type **`file`** → agent re-reads `inputs/docs/` for anything newly added
- Type a **text explanation** → multi-line supported, empty line to finish
- Type **`done`** → end early with what you have

One response per round — the enrichment agent handles URLs, files, and text all at once.

---

## How It Works

The pipeline has three phases that loop until the KB is ready:

```
Phase 1 — DRAFT
  Read input_config.yaml + detect input mode
  Read all artifacts, local docs, and fetch any URLs from the prompt
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

---

## Input Modes

The system auto-detects what you provided and adapts agent behaviour:

| Mode | What you have | Agent approach |
|---|---|---|
| `artifacts_and_docs` | Artifacts + docs/URLs | Maps every artifact element to docs; writes with authority |
| `artifacts_only` | Artifacts, no docs | Reverse-engineers structure; liberal "Needs Verification" callouts |
| `docs_only` | Docs/URLs, no artifacts | Extracts schema from docs; notes no artifact was validated |
| `prompt_only` | Prompt text only | Fetches any URLs found in prompt; writes skeleton if none |

---

## Output

Each run produces versioned `.md` files in `outputs/`:

```
outputs/
  kb_<platform>_draft_<timestamp>.md    ← initial draft
  kb_<platform>_r1_<timestamp>.md       ← after round 1 enrichment
  kb_<platform>_r2_<timestamp>.md       ← after round 2 enrichment
  kb_<platform>_FINAL_<timestamp>.md    ← final deliverable
```

---

## Project Structure

```
agentic-workflow-backend/
  main.py                    # orchestrator: three agent functions + CLI loop
  config.py                  # paths, model settings, loop limits

  agents/
    prompts.py               # all system prompts and KB structure constants

  utils/
    file_loader.py           # input loading and input mode detection

  inputs/
    input_config.yaml        # edit this before each run
    sample_artifacts/        # drop client artifact files here
    docs/                    # drop client doc files here (can add mid-run)

  outputs/                   # generated KB files (gitignored)

  .claude/
    commands/build-kb.md     # equivalent Claude Code slash command implementation
```

---

## Two Implementations

The same pipeline exists in two forms. Both produce identical KB output using the same structure, writing rules, and scope boundaries.

### Approach 1 — Claude Code Slash Command

**Entry point:** `/build-kb` inside Claude Code
**File:** `.claude/commands/build-kb.md`

The entire pipeline is a single markdown prompt. Claude Code runs it as one continuous conversational session — Claude itself transitions between Draft, Gap Analysis, and Enrichment by following natural language instructions in the prompt. There is one "agent": Claude running the full command file.

| Phase | What Claude does |
|---|---|
| Draft | Reads config, globs artifacts, fetches URLs, writes KB |
| Gap Analysis | Re-reads KB, presents gap areas as prose, waits for user reply |
| Enrichment | Parses user response, rewrites KB, loops back immediately |

Loop control is conversational — the prompt instructs Claude to proceed without confirmation between phases.

**Best for:** Quick iteration, exploratory runs, no setup needed.

---

### Approach 2 — Python SDK Pipeline

**Entry point:** `python main.py`
**Files:** `main.py`, `agents/prompts.py`

Python owns the loop. Three separate agents are called in sequence via `claude_agent_sdk`. Each agent is a single `query()` call with its own system prompt and tool set. Python handles phase transitions, CLI display, output file naming, and JSON parsing.

#### Agent 1 — Draft Agent

**Tools:** `Read`, `Glob`, `Write`, `WebFetch`
**Prompt:** `ANALYZER_SYSTEM_PROMPT` — KB structure spec and writing rules

Reads all inputs and writes the initial KB. Embeds `<!-- PLATFORM: Name -->` at the top so Python can parse the platform name and derive the output filename.

#### Agent 2 — Interrogator Agent

**Tools:** `Read`, `Grep` (read-only — never writes)
**Prompt:** `INTERROGATOR_SYSTEM_PROMPT` — scope boundary table, readiness threshold, JSON output format

Reviews the KB and returns a structured JSON object identifying knowledge gaps. Only flags gaps that would cause a wrong or missing value in the artifact file — operational concerns (CDN, rate limits, OAuth) are explicitly excluded. Python parses the JSON and decides whether to loop or exit.

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

#### Agent 3 — Enrichment Agent

**Tools:** `Read`, `Glob`, `Write`, `WebFetch`
**Prompt:** `ENRICHMENT_SYSTEM_PROMPT` — same KB structure as draft agent, framed for updating an existing document

Takes the user's response (URL, file, or text), processes it, and rewrites the KB. Removes confirmed `> **Needs Verification:**` callouts, adds new subsections, and updates `## Known Gaps`. Python immediately passes the new KB path back to the Interrogator for the next round.

#### Loop flow

```
Python
  ↓ run_draft_agent()          → Agent 1 writes KB
  ↓ run_interrogator_agent()   → Agent 2 returns JSON gaps
  ↓ display gaps (Python CLI)
  ← user input
  ↓ run_enrichment_agent()     → Agent 3 rewrites KB
  ↓ run_interrogator_agent()   → Agent 2 re-reviews
  (repeat until ready_for_generation: true or user types "done")
  ↓ copy latest → kb_FINAL_<ts>.md
```

**Best for:** Reliable runs, token visibility, building into a larger system.

---

### Comparison

| | Slash Command | Python SDK |
|---|---|---|
| **Entry point** | `/build-kb` in Claude Code | `python main.py` |
| **Number of agents** | 1 (Claude, full session) | 3 (Draft, Interrogator, Enrichment) |
| **Loop control** | Claude (conversational) | Python (`while True` + async agents) |
| **Gap output** | Prose in chat | JSON parsed and formatted by Python |
| **Observability** | What you see in chat | Token counts, timing, tool call logs |
| **Setup** | None | Python + virtualenv + dependencies |
| **Testability** | Not practical | Individual agent functions |
