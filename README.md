# Claude Code Bug-Fix System

Automated bug diagnosis and fix tracking using Claude Code.
Works with any project, any tech stack.

## Install

Clone and run:

```
git clone https://github.com/LikeMindsCommunity/claude-skill-auto-bugfix.git
cd claude-skill-auto-bugfix
./install.sh
```

## Setup

Add the following to your project's `.gitignore` to keep generated files out of version control:

```
# Claude Code worktrees (transient, auto-generated)
.claude/*

# Claude bug-fix mechanism (local only, not for version control)
bug_backlog.md
approval_sheet.md
comparison_sheet.md
CLAUDE.md

# Comparison inputs (user-specific, not for version control)
inputs/*
```

## Usage

In any project:

```
cd /path/to/your-project
claude
> /init-project                # one-time setup, generates CLAUDE.md, bug_backlog.md and approval_sheet.md
> /triage-bug <desc>           # enrich a vague bug report and add to bug_backlog.md
> /process-backlog             # move approved backlog bugs into approval_sheet.md
> /fix-bug <bug desc>          # diagnose a single bug and propose fix
> /batch-fix                   # process multiple bugs with interaction analysis
> /find-bugs                   # compare generated vs expected files (generic)
> /find-bugs-exotel            # Exotel IVR JSON comparison (wraps /find-bugs + Exotel KB checks)
> /process-comparison          # process approved comparisons into fix proposals
> /review-approval-sheet       # summarize approval sheet status
> /apply-fixes                 # apply all approved fixes and create a git commit
```

## Commands


| Command                  | What it does                                                                       |
| ------------------------ | ---------------------------------------------------------------------------------- |
| `/init-project`          | Scans repo, generates `CLAUDE.md` and `approval_sheet.md`                          |
| `/triage-bug`            | Enriches a vague bug report and adds it to `bug_backlog.md`                        |
| `/process-backlog`       | Moves all APPROVED bugs from backlog into approval sheet                           |
| `/fix-bug`               | Diagnoses a bug, proposes fix, writes to approval sheet                            |
| `/batch-fix`             | Processes multiple bugs with interaction analysis                                  |
| `/find-bugs`             | Compares generated vs expected file, writes discrepancies to `comparison_sheet.md` |
| `/find-bugs-exotel`      | Exotel IVR JSON comparison — wraps `/find-bugs` and adds per-node schema, default, alias, composition, script, pattern, and numbered-constraint checks using Exotel KB sections in `CLAUDE.md` |
| `/process-comparison`    | Processes approved comparison items into `approval_sheet.md` with full RCA         |
| `/review-approval-sheet` | Summarizes current approval sheet status                                           |
| `/apply-fixes`           | Applies all APPROVED fixes and creates a git commit                                |

## File Comparison (`/find-bugs`)

Compare a generated file against an expected file to find all discrepancies. Works with any file format (PDF, JSON, DOCX, XLSX, PPTX, images, text, etc.).

### Input files

Drop files into the comparison folders:

```
inputs/
  compare/
    generated/    # The generated/actual output file
    expected/     # The expected/reference file
```

Or pass paths directly:

```
/find-bugs generated=path/to/actual.pdf expected=path/to/reference.pdf source=path/to/template.html
```

The optional `source=` parameter tells the system which file (HTML template, JSON config, code file, etc.) produced the generated output, so fixes can target that source instead of the binary output.

### Workflow

```
/find-bugs              # compare files → writes to comparison_sheet.md
                        # review comparison_sheet.md, mark APPROVED / REJECTED
/process-comparison     # runs full RCA on approved items → writes to approval_sheet.md
                        # review approval_sheet.md, mark APPROVED / REJECTED
/apply-fixes            # applies all approved fixes
```

## Exotel IVR Comparison (`/find-bugs-exotel`)

A sub-skill of `/find-bugs` specialised for Exotel IVR flow JSONs. It runs every generic check first, then layers Exotel-specific checks on top using the Exotel KB inline in `CLAUDE.md`.

**What it adds on top of `/find-bugs`:**

- **Per-node schema validation** — every node's type resolved via the bidirectional Alias Map; every attribute checked against the KB Attribute Schema (type, required, allowed values, dynamic-flag).
- **Per-key default-value verification** — if the KB documents `retryCount` default as `5` and the generated JSON has `5000`, a row is logged with `Expected Content = 5`, `Actual Content = 5000`. Conditional defaults (e.g. "`timeout` defaults to 0 when `nodeType = HANGUP`") are honoured.
- **Value-form validation** — every attribute passes through a literal-vs-dynamic-vs-`staticValue`-struct check. Variable references (`{{var}}`, `$var`, `context.var`) must resolve to a declared variable (Built-in, upstream output, or upstream `preScript`/`script` assignment).
- **Exhaustive script walk** — `script`, `preScript`, `postScript`, `preFunction`, `postFunction`, `expression`, `handler`, `onEnter`, `onExit`, `onError`, any `staticValue.value` marked as script/json, and any heuristically-detected code string — all parsed for syntax, unknown built-ins, unresolved variables, missing error handling, and cross-script type inconsistency.
- **JSON-in-string** — when a script body or `staticValue.value` contains a JSON literal, it is `JSON.parse`d and walked key-by-key against any KB-declared schema.
- **Composition & wiring** — broken transitions, unknown events, missing required event handlers, invalid ports, unmet parent-child back-references, invalid condition expressions.
- **Pattern compliance** — named patterns from `## Exotel Patterns` verified; anti-patterns scanned.
- **Numbered constraints** — every `C1, C2, …` in `## Exotel Constraints` checked; citations like `Exotel C7` in `KB Rule Violated`.
- **Strict instructions** — global invariants from `## Exotel Strict Instructions` applied across the flow.

**What it never flags (free-form, identity, or auto-generated):**

`nodeflow.name`, `flow.name`, `node.name`, `node.displayName`, `node.label`, `node.description`, `node.comments`, `createdAt`, `updatedAt`, `createdBy`, `updatedBy`, any regenerated `id` / `nodeId` / `flowId` / `uuid` / `revisionId`, plus any attribute whose KB Attribute Schema row is absent.

### Setup

`/find-bugs-exotel` auto-derives the Exotel KB from your project's own prompts, generator code, schemas, and docs — the same artefacts `/find-bugs` already sweeps in Step 1.3. Node types, per-node defaults, alias maps, event catalog, composition rules, scripting language, and numbered constraints are extracted directly from your code. **No manual KB population is needed.** Just run `/find-bugs-exotel` right after `/init-project`.

If the skill's derivation is sparse (e.g., your code doesn't name every node type explicitly), you can optionally pin overrides or add rules the code doesn't encode by filling in any of the `## Exotel *` sections of `CLAUDE.md`:

- `## Exotel Node Taxonomy`, `## Exotel Alias Map`, `## Exotel Node Attribute Schema`, `## Exotel Event Catalog`, `## Exotel Composition Rules`, `## Exotel Constraints` — augment the derived KB.
- Optional: `## Exotel Universal Attributes`, `## Exotel Scripting Language`, `## Exotel Patterns`, `## Exotel Strict Instructions`, `## Exotel Layout Rules`.
- Or use `## Exotel KB Reference` (or a `See: path/to/file.md` inside any section) to point at an external file.

Every section is optional. If the derived KB and an override disagree, both sources are cited in the resulting comparison-sheet row — no silent resolution.

### Workflow

```
/find-bugs-exotel       # runs /find-bugs + Exotel KB checks → comparison_sheet.md
                        # review rows, mark APPROVED / REJECTED
/process-comparison     # RCA on approved items → approval_sheet.md
/apply-fixes            # apply all approved fixes
```

# LikeMinds Layer 1 — Platform Knowledge Base Builder

Builds a structured markdown knowledge base (KB) from a client's platform artifacts and documentation. The KB captures everything a downstream system needs to automatically generate valid configuration files, integrations, or workflows for that platform from natural language.

**Example:** Given sample Exotel IVR JSON files and API docs, the system produces a KB documenting every node type, field, transition event, and validation rule — so a Layer 2 agent can generate new IVR flows from plain English.

---

## Quick Start (Claude Code)

The primary way to use this tool is the `**/platform-kb`** skill in Claude Code.

### 1. Open the project in Claude Code

```bash
cd agentic-workflow-backend
claude
```

### 2. Drop your input materials


| Folder                     | What to put here                                                                   |
| -------------------------- | ---------------------------------------------------------------------------------- |
| `inputs/sample_artifacts/` | Platform-generated files (JSON, XML, YAML, config files, etc.)                     |
| `inputs/docs/`             | Documentation in any format (markdown, PDF, Word, Excel, PowerPoint, HTML, images) |


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


| Use Case             | Signals                                                  | Examples                                      |
| -------------------- | -------------------------------------------------------- | --------------------------------------------- |
| `component-flow`     | Nodes, steps, blocks, transitions, visual flows          | IVR builders, workflow engines, no-code tools |
| `api-sdk`            | REST/GraphQL endpoints, SDK methods, auth tokens         | Twilio, Stripe, Salesforce API                |
| `artifact-generator` | Output files with strict schemas, validation rules       | Config generators, template engines           |
| `event-driven`       | Webhooks, callbacks, event payloads, triggers            | Event buses, notification systems             |
| `data-platform`      | Entities, relationships, CRUD, data models               | CRMs, databases, analytics platforms          |
| `config-system`      | Config hierarchies, feature flags, env-specific settings | Infrastructure platforms, deployment tools    |


A platform can match multiple use cases (e.g., an IVR builder is both `component-flow` and `artifact-generator`).

### Responding to gaps

After each gap analysis round you can:


| Input            | What happens                                            |
| ---------------- | ------------------------------------------------------- |
| A URL            | Agent fetches and reads it (Playwright used if blocked) |
| `file`           | Agent re-reads `inputs/docs/` for anything newly added  |
| Text explanation | Used directly to fill the gaps                          |
| `done`           | Ends the loop, saves the final KB                       |


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


| Mode                 | Inputs available        | Agent approach                                                     |
| -------------------- | ----------------------- | ------------------------------------------------------------------ |
| `artifacts_and_docs` | Artifacts + docs/URLs   | Maps every artifact element to docs; writes with authority         |
| `artifacts_only`     | Artifacts, no docs      | Reverse-engineers structure; liberal "Needs Verification" callouts |
| `docs_only`          | Docs/URLs, no artifacts | Extracts schema from docs; notes no artifact was validated         |
| `prompt_only`        | Prompt only             | Fetches any URLs in prompt; writes skeleton with gaps if none      |


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


| Skill                   | Purpose                                                     |
| ----------------------- | ----------------------------------------------------------- |
| `/build-kb`             | Orchestrator — older version, drives the same pipeline loop |
| `/build-kb-draft`       | Draft sub-agent only                                        |
| `/build-kb-interrogate` | Gap analysis sub-agent only (read-only)                     |
| `/build-kb-enrich`      | Enrichment sub-agent only                                   |


---
