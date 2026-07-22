---
name: process-comparison
description: Read every APPROVED item from a client's comparison sheets (outputs/{client}/comparisons/*.md), run full root-cause analysis against the codebase and CLAUDE.md, and write each as a PENDING fix proposal in the client's approval sheet (outputs/{client}/approval_sheet.md), with COMP-to-BUG traceability. Proposes only; never edits source. Use to turn reviewed comparison findings into reviewable fix proposals. Triggers: "process the approved comparisons", "process-comparison", "run RCA on {client}'s approved comparison items".
---

You are a comparison-to-fix processing agent. Read all APPROVED items from this client's comparison sheets under `outputs/{client}/comparisons/`, perform full root cause analysis for each, and write fix proposals to `outputs/{client}/approval_sheet.md`.

## Inputs & Paths — resolve the client first
Sheets are stored per client under `outputs/{client}/`. Resolve `{client}` before anything else:
1. `client=<name>` in $ARGUMENTS → use it.
2. `output=<dir>` in $ARGUMENTS → use that directory as the client folder directly (skip inference).
3. Otherwise infer `{client}` from context: an inputs/artifacts folder name or a client name in $ARGUMENTS or the prompt, or the parent folder of a `kb=<dir>` if one is given.
4. Still unresolved → if exactly one `outputs/*/` client directory exists, use it; otherwise ASK the user which client and STOP. Never guess.

Resolved paths (create parents if missing):
- **Comparison sheets (read):** `outputs/{client}/comparisons/*.md` — a client can have many. Process APPROVED items across all of them, unless a `comparison=<path>` argument names a single sheet.
- **Approval sheet (write):** `outputs/{client}/approval_sheet.md` — one per client.

With `output=<dir>`, use `<dir>/comparisons/*.md` and `<dir>/approval_sheet.md`.

## Step 1 — Read Comparison Sheet

Read every comparison sheet for this client — all `.md` files under `outputs/{client}/comparisons/` (or only the sheet named by a `comparison=<path>` argument, if given). Parse the table rows in each.
Find all rows with Should Fix = `APPROVED` across them, and remember which sheet file each APPROVED row came from (needed for Step 5).

If no APPROVED rows found in any sheet, print:
```
No APPROVED items in outputs/{client}/comparisons/.
Open a comparison sheet under outputs/{client}/comparisons/ and change Should Fix to APPROVED for items you want analyzed, then re-run the process-comparison skill.
```
Then STOP.

If APPROVED rows found, print:
```
Found {N} APPROVED comparison items to process.
```

---

## Step 2 — Read Project Context

Read `CLAUDE.md` in the current directory. Extract:
- `## Architecture Layers` or `## Pipeline Steps` → use as classification taxonomy
- `## File Index` → use to locate relevant source files
- `## Prompt/Template Mapping` → use for dual-layer analysis (skip if absent)
- `## Constraints` → rules to follow during analysis and fix proposal
- `## Bug Patterns` → known failure modes that may explain the discrepancy

If no CLAUDE.md exists, print a warning but continue — RCA will be based on the comparison data and codebase search only.

---

## Step 3 — For Each APPROVED Row, Run Full RCA

Process each APPROVED comparison item one at a time. For each row:

### 3.1 — Announce
Print: `Analyzing COMP-XXX: {Category} — {Expected Content vs Actual Content summary}`

### 3.2 — Classify the Discrepancy
Using the Architecture Layers or Pipeline Steps from CLAUDE.md, classify this discrepancy into the layer or step most likely responsible.
Do NOT use a hardcoded category list. Use whatever layers THIS project has defined in CLAUDE.md.

### 3.3 — Locate Relevant Source Code or Templates

**If Source File column is populated:**
- Read that source file
- Locate the specific section, function, template block, or configuration that produces the output matching "Location (Generated)"
- Note the exact line range responsible

**If Source File column is empty:**
- Use the File Index from CLAUDE.md to identify candidate files
- Grep the codebase for strings, function names, or patterns related to the discrepancy
- Search for code that generates or transforms the content described in "Expected Content" / "Actual Content"
- If found: note the file path and line range
- If not found: note "Source not identified — manual investigation needed"

**If `## Prompt/Template Mapping` exists in CLAUDE.md:**
- Also read the corresponding prompt or template file for the affected module
- Check if the prompt/template is responsible for the discrepancy (dual-layer analysis)

**For any file flagged as LARGE FILE in CLAUDE.md:**
- Grep for the specific function or class rather than reading the full file

### 3.4 — Root Cause Analysis

Determine the root cause:

**Bug Layer:**
- **Code bug** — Logic is wrong regardless of any template or LLM output
- **Prompt/template bug** — Instructions are missing or misleading (only applicable if Prompt/Template Mapping exists)
- **Configuration bug** — A config value, parameter, or setting is wrong
- **Data bug** — Input data is malformed or missing
- **Both** — Template produces wrong output AND code has no safeguard

**Risk** (inherit from comparison sheet, adjust based on RCA):
- LOW — isolated to one function/section, no other layer affected
- MEDIUM — one architecture layer affected, may ripple to adjacent layer
- HIGH — multiple layers affected or shared data structure involved

**Confidence:**
- LOW — hypothesis only, cannot confirm root cause from code alone
- MEDIUM — likely root cause, has caveats or edge cases
- HIGH — root cause confirmed, fix is deterministic

### 3.5 — Propose Fix

For each affected file, provide:
- File path and line range
- Plain text description of what to change
- No before/after code blocks

**For text-editable source files** (code, templates, config, JSON, YAML, etc.):
- Describe the exact change: what to replace, add, or remove at which lines

**For binary format sources** (if the source is a DOCX, PPTX, etc.):
- Describe what content to change and where
- Add: "Regenerate the output after making this change"

**If source was not identified:**
- Fix Description = "Source not identified. Manual investigation needed. The generated output at {location} shows {actual} but should show {expected}."
- Confidence = LOW

Respect ALL rules listed in the `## Constraints` section of CLAUDE.md.

---

## Step 4 — Write to outputs/{client}/approval_sheet.md

Read existing Bug IDs in `outputs/{client}/approval_sheet.md` to determine the next sequential ID.
Format: `BUG-YYYY-MM-DD-NNN` (sequential per day)

For each analyzed comparison item, append a new row to the outputs/{client}/approval_sheet.md table:

| Column | Value |
|---|---|
| Bug ID | Sequential `BUG-YYYY-MM-DD-NNN` |
| Reported | Today's date |
| Bug Summary | From comparison sheet: `Expected: {Expected Content}` vs `Actual: {Actual Content}` — include the Comp ID for traceability |
| Risk | From RCA (Step 3.4) |
| Confidence | From RCA (Step 3.4) |
| Root Cause | What is wrong in the source and why — note if code, prompt/template, config, data, or both |
| Affected Files | Source file(s) with line ranges. If source not identified: generated file location for reference. Separate multiple files with `<br>` |
| Fix Description | Plain text description of the change. For binary sources: include "Regenerate output after fix" |
| Testing Notes | "Re-run find-bugs with the same kb, generated and expected files to verify this discrepancy is resolved" |
| Status | `PENDING` |
| Reviewed By | `_pending_` |

---

## Step 5 — Update the source comparison sheet

For each processed APPROVED row, go back to the comparison sheet under `outputs/{client}/comparisons/` that it came from (tracked in Step 1) and:
- Fill in the `Linked Bug ID` column with the assigned BUG ID (e.g., `BUG-2026-04-14-003`)

This creates traceability: `COMP-XXX → BUG-YYY`

---

## Step 6 — Print Summary

Print a complete summary:

```
═══════════════════════════════════════════
  Comparison Processing Complete
═══════════════════════════════════════════

  Processed: {N} approved comparison items

| Comp ID | → Bug ID | Layer | Risk | Confidence | Root Cause Summary |
|---------|----------|-------|------|------------|-------------------|
| COMP-... | BUG-... | ... | HIGH | HIGH | ... |
| COMP-... | BUG-... | ... | MEDIUM | MEDIUM | ... |
...

  Source identified:     {N} / {total}
  Source not identified: {N} / {total}

───────────────────────────────────────────

  Next steps:
    1. Open outputs/{client}/approval_sheet.md — review the new PENDING rows
    2. Change Status to APPROVED or REJECTED
    3. Run the apply-fixes skill to apply all approved fixes
```

---

## Important Rules

1. **One BUG ID per COMP ID.** Each approved comparison item becomes exactly one row in outputs/{client}/approval_sheet.md. Do not merge or split.

2. **Traceability is mandatory.** Always fill in the Linked Bug ID column in the source comparison sheet (under `outputs/{client}/comparisons/`) after writing to `outputs/{client}/approval_sheet.md`.

3. **Respect the outputs/{client}/approval_sheet.md format exactly.** The downstream apply-fixes skill depends on parsing this table. Use the same column format as diagnose-bug.

4. **Don't skip items.** Process ALL APPROVED rows, even if you cannot identify the source. For those, set Confidence = LOW and describe what manual investigation is needed.

5. **Read before proposing.** Always read the actual source file before proposing a fix. Never propose changes based on assumptions about file contents.

6. **Follow CLAUDE.md constraints.** All fix proposals must respect the rules in the `## Constraints` section. If a proposed fix would violate a constraint, find an alternative approach.
