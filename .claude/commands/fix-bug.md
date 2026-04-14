---
description: Diagnose a bug and propose a fix with approval tracking
---

You are a generic bug-fix agent. Given the bug report in $ARGUMENTS, do the following:

## Step 1 — Read Project Context
Read `CLAUDE.md` in the current directory. Extract:
- `## Architecture Layers` or `## Pipeline Steps` section → use as classification taxonomy
- `## File Index` section → use to locate relevant files and identify large files
- `## Prompt/Template Mapping` section → use for dual-layer analysis (skip entirely if this section is absent)
- `## Constraints` section → rules to follow during analysis and fix proposal

## Step 2 — Classify the Bug
Using the Architecture Layers or Pipeline Steps from CLAUDE.md, classify this bug into the layer or step most likely responsible.
Do NOT use a hardcoded category list. Use whatever layers THIS project has defined in CLAUDE.md.

## Step 3 — Locate Relevant Code AND Prompts
- Use the File Index from CLAUDE.md to locate the relevant file(s)
- For any file flagged as LARGE FILE in CLAUDE.md, grep for the specific function or class rather than reading the full file
- IF `## Prompt/Template Mapping` section exists in CLAUDE.md:
    Also read the corresponding prompt or template file for the affected module (dual-layer analysis)
  ELSE:
    Pure code analysis only — skip prompt layer entirely

## Step 4 — Root Cause Analysis
Determine the bug layer:
- **Code bug**: Logic is wrong regardless of any template or LLM output
- **Prompt/template bug**: Instructions are missing or misleading (only applicable if Prompt/Template Mapping exists in CLAUDE.md)
- **Both**: Template produces wrong output AND code has no safeguard

Assign **Risk**:
- LOW — isolated to one function, no other layer affected
- MEDIUM — one architecture layer affected, may ripple to adjacent layer
- HIGH — multiple layers affected or shared data structure involved

Assign **Confidence**:
- LOW — hypothesis only, cannot confirm from code alone
- MEDIUM — likely root cause, has caveats or edge cases
- HIGH — root cause confirmed, fix is deterministic

## Step 5 — Propose Fix
For each affected file: provide the file path, line range, and a plain text description of what to change.
No before/after code blocks. If both code and prompt/template files need changes, list both separately with their own file paths and line ranges.
Respect ALL rules listed in the `## Constraints` section of CLAUDE.md.

## Step 6 — Write to approval_sheet.md
Read existing Bug IDs in `approval_sheet.md` to determine the next sequential ID.
Format: `BUG-YYYY-MM-DD-NNN` (sequential per day, e.g. BUG-2026-03-25-001, BUG-2026-03-25-002)

Append a new row to the table with these columns:

| Bug ID | Reported | Bug Summary | Risk | Confidence | Root Cause | Affected Files | Fix Description | Testing Notes | Status | Reviewed By |

- Bug ID = generated sequential ID
- Reported = today's date
- Bug Summary = exact bug text from $ARGUMENTS, verbatim — do not summarize or rephrase
- Risk = LOW / MEDIUM / HIGH
- Confidence = LOW / MEDIUM / HIGH
- Root Cause = what is wrong and why (note if code, prompt, or both)
- Affected Files = file paths with line numbers, e.g. `validation_agent.py L752-792` — separate multiple files with `<br>`
- Fix Description = plain text description of the change, no code blocks
- Testing Notes = how to verify the fix works
- Status = `PENDING`
- Reviewed By = `_pending_`

## Step 7 — Print Summary
Print: Bug ID assigned, classification (which layer from CLAUDE.md), risk, confidence, affected files with line numbers.
Remind the user: open `approval_sheet.md` and change Status to `APPROVED` or `REJECTED`.
