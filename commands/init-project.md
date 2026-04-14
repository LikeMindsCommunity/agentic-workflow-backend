---
description: Bootstrap the bug-fix system for any project — scans the repo and generates CLAUDE.md and approval_sheet.md
---

You are a project bootstrap agent. Scan the current repository and generate a complete `CLAUDE.md` and `approval_sheet.md`. Do the following autonomously:

## Stage 1 — Tech Stack Detection
Read whichever of these files exist in the repo root:
`requirements.txt`, `pyproject.toml`, `package.json`, `go.mod`, `pom.xml`, `Cargo.toml`, `Gemfile`, `composer.json`

Extract: primary language, framework (FastAPI / Express / Django / Rails / Gin / Spring etc.), key dependencies, runtime version.

## Stage 2 — Directory Structure Scan
List all top-level directories. Identify purpose by name:
- `agents/`, `services/`, `controllers/`, `handlers/` → core logic layer
- `workers/`, `jobs/`, `tasks/` → background processing layer
- `prompts/`, `templates/`, `instructions/` → LLM/template layer (flag if found — important for Stage 6)
- `migrations/`, `db/`, `database/` → data layer
- `tests/`, `spec/`, `__tests__/`, `test/` → test suite
- `proto/`, `grpc/` → contract layer
- `cmd/` → multi-binary (Go pattern)
- `app/`, `src/`, `lib/` → main source root
- `scripts/`, `bin/` → utility scripts

## Stage 3 — Entry Point Discovery
Look for files that start the application:
`main.py`, `index.js`, `app.py`, `server.go`, `manage.py`, `Program.cs`, `cmd/main.go`, `server.js`
Note what each one starts and how.

## Stage 4 — File Index
List every significant file (exclude: node_modules/, __pycache__/, .git/, dist/, build/, venv/).
For each file note its purpose in one line.
Flag any file over 50KB with: ⚠️ LARGE FILE — read in sections only, use grep to locate specific functions.

## Stage 5 — Pipeline/Orchestrator Detection
Look for a file that imports and calls multiple other modules in sequence.
Common names: orchestrator.py, pipeline.py, workflow.py, coordinator.py, runner.py, chain.py
If found: map the sequence as numbered steps with agent/module file name and purpose.
If not found: skip — use Architecture Layers instead.

## Stage 6 — Prompt/Template Mapping
ONLY run this stage if Stage 2 found a `prompts/`, `templates/`, or `instructions/` folder.
For each template file found, search the codebase for which module loads it:
- Search for `open()` calls referencing the file path
- Search for file path strings in import or config sections
Build the mapping: `module_file.py → template_file.md`
If no template folder was found in Stage 2: skip this stage entirely. Do NOT create the Prompt/Template Mapping section in CLAUDE.md.

## Stage 7 — Test Setup
Identify the test framework from config files (pytest.ini, jest.config.js, go.mod test imports, .rspec etc.)
Note the command to run all tests.

## Stage 8 — Dev Commands
Check for: Makefile, scripts/ folder, package.json `scripts` section, docker-compose.yml.
List the most common commands: start server, run worker, run tests, docker compose up.

## Stage 9 — Write CLAUDE.md
Generate `CLAUDE.md` at the repo root. Use EXACTLY these section names in this order:

```
## Project Identity
[project name, purpose, one paragraph description]

## Tech Stack
[language, framework, key dependencies from Stage 1]

## Directory Structure
[top-level folder map with purposes from Stage 2]

## Entry Points
[list from Stage 3]

## File Index
[all significant files with purposes and ⚠️ LARGE FILE flags from Stage 4]

## Pipeline Steps        ← use this name if Stage 5 found an orchestrator
[OR]
## Architecture Layers   ← use this name if no orchestrator found
[numbered steps from Stage 5, OR layer structure from Stage 2]

## Prompt/Template Mapping   ← ONLY include this section if Stage 6 ran (templates exist)
[module → template mapping from Stage 6]

## Test Setup
[framework and run command from Stage 7]

## Dev Commands
[commands from Stage 8]

## Bug Patterns
# Add known failure modes here — e.g.:
# - Pattern name: description of what causes it and which files are involved

## Constraints
# Add rules here — e.g.:
# - Never modify X file without explicit instruction
# - Never change the LLM provider
# - Always run tests before committing
```

IMPORTANT: Use the EXACT section heading names above (## Pipeline Steps, ## Architecture Layers, ## Prompt/Template Mapping, ## File Index, ## Constraints, ## Bug Patterns). The generic commands look for these exact names.

## Stage 10 — Write approval_sheet.md and bug_backlog.md
If `approval_sheet.md` already exists, do NOT overwrite it.
If it does not exist, create it at the repo root:

```
# Bug Fix Approval Sheet

Status values: PENDING | APPROVED | APPLIED | REJECTED | CONFLICT

| Bug ID | Reported | Bug Summary | Risk | Confidence | Root Cause | Affected Files | Fix Description | Testing Notes | Status | Reviewed By |
|--------|----------|-------------|------|------------|------------|----------------|-----------------|---------------|--------|-------------|
```

If `bug_backlog.md` already exists, do NOT overwrite it.
If it does not exist, create it at the repo root:

```
# Bug Backlog

Status values: PENDING_REVIEW | APPROVED | REJECTED

| Ref ID | Reported | Raw Report | Enriched Description | Affected Area | Evidence | Should Fix | Reviewed By | Linked Bug ID |
|--------|----------|------------|----------------------|---------------|----------|------------|-------------|---------------|
```

If `comparison_sheet.md` already exists, do NOT overwrite it.
If it does not exist, create it at the repo root:

```
# Comparison Sheet

Status values: PENDING_REVIEW | APPROVED | REJECTED

| Comp ID | Reported | Category | Location (Generated) | Location (Expected) | Expected Content | Actual Content | KB Rule Violated | Risk | Source File | Should Fix | Reviewed By | Linked Bug ID |
|---------|----------|----------|---------------------|---------------------|-----------------|----------------|-----------------|------|-------------|------------|-------------|---------------|
```

## Stage 11 — Create comparison input folders
Create the following directories if they do not already exist:
```
inputs/compare/generated/
inputs/compare/expected/
```
These are used by `/find-bugs` to store files for comparison.

## Stage 12 — Update .gitignore
Read `.gitignore`. If `.claude/worktrees/` is not already listed, append:
```
# Claude Code worktrees (transient, auto-generated)
.claude/worktrees/
```

## Stage 13 — Print Completion Summary
Print exactly:

```
✅ Setup complete for [project name]

Generated:
  → CLAUDE.md ([N] sections)
  → approval_sheet.md [created / already existed — skipped]
  → bug_backlog.md [created / already existed — skipped]
  → comparison_sheet.md [created / already existed — skipped]
  → inputs/compare/generated/ [created / already existed]
  → inputs/compare/expected/ [created / already existed]
  → .gitignore updated [or: already had .claude/worktrees/]

Next steps:
  1. Open CLAUDE.md and fill in the ## Bug Patterns section with known failure modes
  2. Fill in the ## Constraints section with files/APIs that should never be modified
  3. For vague bugs: /triage-bug <vague description> → review bug_backlog.md → /process-backlog
  4. For clear bugs:  /fix-bug <specific description> → review approval_sheet.md → /apply-fixes
  5. For file comparison: /find-bugs → review comparison_sheet.md → /process-comparison → /apply-fixes
```
