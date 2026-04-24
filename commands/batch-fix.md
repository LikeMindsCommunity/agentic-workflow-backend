---
description: Process multiple bugs in batch mode with interaction analysis
---

You are a batch bug-fix agent. Process the bug list in $ARGUMENTS.
If $ARGUMENTS is "sheet", read all PENDING/APPROVED rows from approval_sheet.md instead.

## Scope — batch-fix inherits the propose-only contract from `/fix-bug`

For every bug in the list, write exactly one row to `approval_sheet.md` with `Status = PENDING`. Do NOT use `Edit` / `Write` / `NotebookEdit` on any source file, do NOT run git writes, and do NOT mark any row as `APPROVED` or `APPLIED`. The interaction analysis in Step 3 is *advisory only* — it reports conflicts and ordering, it does not act on them. Source files are modified only by `/apply-fixes`, and only after the user approves the rows.

## Step 1 — Parse Bug List
Extract individual bug descriptions from $ARGUMENTS (split on numbering pattern \d+\.)
If input is `sheet`, use existing PENDING/APPROVED rows from `approval_sheet.md` — skip to Step 3.

## Step 2 — Process Each Bug
For each bug description, run the full `/fix-bug` workflow:
- Read CLAUDE.md for project context
- Classify against Architecture Layers or Pipeline Steps from CLAUDE.md
- Locate code files using File Index from CLAUDE.md
- If `## Prompt/Template Mapping` exists in CLAUDE.md: run dual-layer analysis (code + prompt)
- If not: pure code analysis only
- Root cause analysis (Risk + Confidence)
- Write PENDING row to approval_sheet.md — and stop there for that bug, no source-file edits

Assign sequential Bug IDs within the same date: BUG-YYYY-MM-DD-001, BUG-YYYY-MM-DD-002, etc.

## Step 3 — Interaction Analysis
After ALL bugs are processed, analyze interactions across all fixes:

### Check 1 — Same File Conflict (no project knowledge needed)
- Collect all (file, line_start, line_end) tuples from every fix's Affected Files column
- Group by file path
- If two fixes target overlapping OR adjacent (≤20 lines apart) ranges in the same file → flag as CONFLICT
- Action: apply one at a time, re-run /fix-bug for the second after the first is applied

### Check 2 — Dependency Order (read from CLAUDE.md)
- Read `## Architecture Layers` or `## Pipeline Steps` from CLAUDE.md
- If Fix A is at an earlier layer and Fix B is at a later layer AND both touch the same data object → B depends on A
- Also check: does Fix A create a function or variable that Fix B assumes exists?
- Action: flag recommended apply order (apply A before B)

### Check 3 — Cross-Effect Risk (read from CLAUDE.md)
- Read `## File Index` from CLAUDE.md to identify files imported by many modules
- If any fix touches a high-import shared file → HIGH cross-effect risk
- If two fixes affect adjacent layers that share a data contract → flag for combined testing
- Action: flag and recommend testing all affected layers after applying

## Step 4 — Summary Table
Print:

| Bug ID | Risk | Confidence | Affected Files | Interactions |
|--------|------|------------|----------------|--------------|

Then print:
- Total bugs analyzed
- Interaction warnings with specific recommendations
- Recommended apply order (dependencies first, then HIGH risk, then by confidence)
- Reminder to review `approval_sheet.md`

## Step 5 — Pre-Deploy Check (only when input is "sheet")
Read all APPLIED rows from the last 7 days.
If any PENDING fix targets code already changed by a recent APPLIED fix → flag as potentially stale.
Print: `WARNING — BUG-XXX targets code already changed by BUG-YYY applied on YYYY-MM-DD`
Recommend re-running /fix-bug for stale entries to get a fresh analysis.
