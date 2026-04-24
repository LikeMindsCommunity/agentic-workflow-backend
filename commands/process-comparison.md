---
description: Process approved comparison items into the approval sheet with full RCA
---

You are a comparison-to-fix processing agent. Read all APPROVED items from `comparison_sheet.md`, perform full root cause analysis for each, and write fix proposals to `approval_sheet.md`.

## Step 1 — Read Comparison Sheet

Read `comparison_sheet.md` from the repository root. Parse the table rows.
Find all rows with Should Fix = `APPROVED`.

If no APPROVED rows found, print:
```
No APPROVED items in comparison_sheet.md.
Open comparison_sheet.md and change Should Fix to APPROVED for items you want analyzed, then re-run /process-comparison.
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

## Step 4 — Write to approval_sheet.md

Read existing Bug IDs in `approval_sheet.md` to determine the next sequential ID.
Format: `BUG-YYYY-MM-DD-NNN` (sequential per day)

For each analyzed comparison item, append a new row to the approval_sheet.md table:

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
| Testing Notes | "Re-run `/find-bugs` with same generated and expected files to verify this discrepancy is resolved" |
| Status | `PENDING` |
| Reviewed By | `_pending_` |

---

## Step 5 — Update comparison_sheet.md

For each processed APPROVED row in `comparison_sheet.md`:
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
    1. Open approval_sheet.md — review the new PENDING rows
    2. Change Status to APPROVED or REJECTED
    3. Run /apply-fixes to apply all approved fixes
```

---

## Important Rules

1. **One BUG ID per COMP ID.** Each approved comparison item becomes exactly one row in approval_sheet.md. Do not merge or split.

2. **Traceability is mandatory.** Always fill in the Linked Bug ID column in comparison_sheet.md after writing to approval_sheet.md.

3. **Respect the approval_sheet.md format exactly.** The downstream `/apply-fixes` command depends on parsing this table. Use the same column format as `/fix-bug`.

4. **Don't skip items.** Process ALL APPROVED rows, even if you cannot identify the source. For those, set Confidence = LOW and describe what manual investigation is needed.

5. **Read before proposing.** Always read the actual source file before proposing a fix. Never propose changes based on assumptions about file contents.

6. **Follow CLAUDE.md constraints.** All fix proposals must respect the rules in the `## Constraints` section. If a proposed fix would violate a constraint, find an alternative approach.
