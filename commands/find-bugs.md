---
description: Compare a generated file against an expected file and log all discrepancies to the comparison sheet
---

You are a generic file comparison agent. Given two files — a generated (actual) output and an expected (reference) output — compare them thoroughly using the project's knowledge base and log all discrepancies to `comparison_sheet.md`.

**User-provided context:** $ARGUMENTS

## Step 1 — Parse Inputs & Read Project Context

### 1.1 — Resolve file paths

Parse `$ARGUMENTS` for optional overrides:
- `generated=<path>` — path to the generated/actual file
- `expected=<path>` — path to the expected/reference file
- `source=<path>` — path to the source file that produced the generated output (optional — used for fix targeting)

If no paths provided, auto-detect:
1. List files in `inputs/compare/generated/` — pick the first file found
2. List files in `inputs/compare/expected/` — pick the first file found

If neither arguments nor default folder files exist, print this error and STOP:
```
Error: No files found to compare.

Usage:
  /find-bugs generated=<path> expected=<path> [source=<path>]

Or drop files into:
  inputs/compare/generated/   ← the generated/actual output
  inputs/compare/expected/    ← the expected/reference output
```

Validate both files exist. Print the resolved paths:
```
Files resolved:
  Generated: {path}
  Expected:  {path}
  Source:    {path or "not provided"}
```

### 1.2 — Read project knowledge base

Read `CLAUDE.md` in the current directory if it exists. Extract ALL of:
- `## Constraints` — rules about what matters, what's verbatim, what can vary, what formatting rules apply
- `## File Index` — context about project files and their purpose
- `## Architecture Layers` or `## Pipeline Steps` — system structure and classification taxonomy
- `## Bug Patterns` — known failure modes to actively watch for
- `## Prompt/Template Mapping` — if exists, understand which templates produce which outputs (for dual-layer analysis)

If no `CLAUDE.md` exists:
- Print: `⚠️ No CLAUDE.md found — run /init-project first for KB-aware comparison. Proceeding with raw comparison.`
- Continue with raw comparison (no KB filtering or requirements checking)

---

## Step 2 — Detect Formats & Load Content

Determine the format of EACH file by its extension and load content using the appropriate method:

| Extension | Method |
|---|---|
| `.pdf` | Read tool with `pages` parameter — read 5 pages at a time for large PDFs (>10 pages) |
| `.png`, `.jpg`, `.jpeg`, `.gif`, `.bmp`, `.webp` | Read tool — visual/multimodal comparison |
| `.json`, `.yaml`, `.yml`, `.xml`, `.html`, `.md`, `.txt`, `.csv` | Read tool — text content |
| `.docx` | Invoke the `/docx` anthropic-skill to extract text content |
| `.xlsx`, `.xlsm`, `.tsv` | Invoke the `/xlsx` anthropic-skill to extract tabular data |
| `.pptx` | Invoke the `/pptx` anthropic-skill to extract slide content |

**Format mismatch handling:** If the generated and expected files have DIFFERENT formats (e.g., generated=PDF, expected=DOCX):
- Extract text content from both files
- Perform content-only comparison
- Print: `⚠️ Format mismatch ({ext1} vs {ext2}) — visual/formatting comparison skipped, content-only comparison.`

---

## Step 3 — KB-Driven Requirements Extraction

**This step is what differentiates this from a raw diff.** Before comparing, use CLAUDE.md to build a requirements checklist that becomes the primary comparison lens.

IF CLAUDE.md was loaded:

1. **From `## Constraints`**: Extract rules about:
   - What content must be verbatim (character-exact)
   - What fields are allowed to vary (dates, version numbers, dynamic values)
   - What formatting rules apply (pixel-perfect, flexible, etc.)
   - What must never be changed

2. **From `## Bug Patterns`**: Extract known failure modes. These are patterns to ACTIVELY look for in the generated file — not just passive filtering but proactive checking.

3. **From `## Prompt/Template Mapping`** (if exists): Understand what template or prompt produced the generated file. This tells you what the output SHOULD contain and what structure to expect.

4. **From `## Architecture Layers` or `## Pipeline Steps`**: Understand which layer the generated file belongs to. This determines what upstream/downstream expectations exist.

5. **From any KB-defined validation rules**: Build a checklist of requirements the generated file MUST satisfy.

Store this checklist — discrepancies are not just "these two files differ" but "the generated file violates requirement X from the KB."

IF CLAUDE.md was NOT loaded: Skip this step entirely. All comparisons will be raw diffs.

---

## Step 4 — Structural Comparison

Identify the structural skeleton of EACH file based on its format:

| Format | Structural elements |
|---|---|
| Markdown / Text | Headings, sections, paragraphs, lists |
| JSON / YAML / XML | Keys, nested objects, arrays, attributes |
| PDF / DOCX | Pages, sections, headings, tables, paragraphs |
| XLSX / CSV | Sheets, rows, columns, headers |
| PPTX | Slides, titles, content blocks |
| Images | Regions, text blocks, charts, visual elements |

Compare structural elements between the two files:
- **Missing elements** (present in expected, absent in generated) → category `MISSING_CONTENT`
- **Extra elements** (present in generated, absent in expected) → category `EXTRA_CONTENT`
- **Reordered elements** (same content, different position — if KB or expected implies specific ordering) → category `WRONG_CONTENT`

If CLAUDE.md was loaded: also check if any KB-required elements are missing from BOTH files — flag as a warning but do not write to comparison sheet.

---

## Step 5 — Content Comparison

For each MATCHING structural element (present in both files), compare the content:

1. **Text content**:
   - Default: semantic comparison — paraphrased sentences conveying the same meaning are NOT bugs
   - If CLAUDE.md Constraints say "verbatim" for this content: character-exact comparison
   - If no KB: default to semantic comparison

2. **Numerical content**:
   - Default: exact match required
   - If KB specifies tolerance (e.g., "rounding to 2 decimal places is acceptable"): apply tolerance

3. **Tabular data** (tables, spreadsheets):
   - Cell-by-cell comparison
   - Check column headers match
   - Check row count matches
   - Check data types are consistent

4. **Structured data** (JSON, YAML, XML):
   - Key-by-key comparison
   - Type checking (string vs number vs boolean)
   - Value matching
   - Array ordering (if KB specifies order matters)

5. **Boolean/categorical values**:
   - Exact match required

Each content discrepancy → category `WRONG_CONTENT`

---

## Step 6 — Visual/Formatting Comparison

### For visual formats (PDF, images, DOCX, PPTX):
Compare these visual properties:
- Page layout and margins
- Font families, sizes, weights, and colors
- Table styling (borders, header colors, row striping)
- Heading hierarchy and styling
- Spacing and alignment
- Color scheme consistency
- Logo/branding placement
- Header/footer consistency

### For structured data (JSON, YAML, XML):
- Compare nesting depth and structure
- Ignore whitespace and formatting differences (these are not bugs)
- Check schema consistency (same keys at same levels)

### For plain text / markdown:
- Compare heading levels and structure
- Check list formatting consistency
- Ignore trailing whitespace

Each formatting discrepancy → category `FORMATTING`

If CLAUDE.md defines formatting rules (e.g., "formatting must be pixel-perfect"), apply those rules and elevate FORMATTING risk accordingly.

---

## Step 7 — KB-Aware Classification & Filtering

For EACH discrepancy found in Steps 4-6, apply these filters in order:

### 7.1 — Suppression Check
Read `## Constraints` from CLAUDE.md. If a discrepancy is explicitly permitted by a constraint (e.g., "date fields may vary between runs", "version numbers are dynamic"), then:
- SUPPRESS the discrepancy
- Log it internally as: `Suppressed: {description} — KB rule: {constraint text}`
- Do NOT write it to comparison_sheet.md

### 7.2 — Bug Pattern Matching
Read `## Bug Patterns` from CLAUDE.md. If a discrepancy matches a known failure pattern:
- Flag it with the pattern name in the KB Rule Violated column
- This increases confidence in the finding

### 7.3 — Risk Assignment
Assign risk based on category, with KB overrides:

| Category | Default Risk |
|---|---|
| `MISSING_CONTENT` | HIGH |
| `WRONG_CONTENT` | MEDIUM |
| `EXTRA_CONTENT` | MEDIUM |
| `FORMATTING` | LOW |

KB can override these defaults. For example:
- If Constraints say "formatting must be pixel-perfect" → `FORMATTING` becomes HIGH
- If Constraints say "boilerplate text must be verbatim" and text differs → `WRONG_CONTENT` becomes HIGH
- If a known Bug Pattern is matched → increase risk by one level

### 7.4 — Layer Classification
Using `## Architecture Layers` or `## Pipeline Steps` from CLAUDE.md, classify which layer or step each discrepancy belongs to. This helps `/process-comparison` with RCA later.

---

## Step 8 — Write to comparison_sheet.md

### 8.1 — Create sheet if needed
If `comparison_sheet.md` does not exist in the repo root, create it:

```
# Comparison Sheet

Status values: PENDING_REVIEW | APPROVED | REJECTED

| Comp ID | Reported | Category | Location (Generated) | Location (Expected) | Expected Content | Actual Content | KB Rule Violated | Risk | Source File | Should Fix | Reviewed By | Linked Bug ID |
|---------|----------|----------|---------------------|---------------------|-----------------|----------------|-----------------|------|-------------|------------|-------------|---------------|
```

### 8.2 — Assign Comp IDs
Read existing Comp IDs in `comparison_sheet.md` to determine the next sequential ID.
Format: `COMP-YYYY-MM-DD-NNN` (sequential per day, e.g. COMP-2026-04-14-001, COMP-2026-04-14-002)

### 8.3 — Append rows
For each NON-SUPPRESSED discrepancy, append a row:

| Column | Value |
|---|---|
| Comp ID | Sequential `COMP-YYYY-MM-DD-NNN` |
| Reported | Today's date |
| Category | `MISSING_CONTENT` / `WRONG_CONTENT` / `EXTRA_CONTENT` / `FORMATTING` |
| Location (Generated) | Where in the generated file: page N, section X, line N, cell A3, slide N, key path, etc. |
| Location (Expected) | Corresponding location in the expected file |
| Expected Content | What the expected file has at this location (truncate to ~100 chars if longer, append `...`) |
| Actual Content | What the generated file has (or `_(missing)_` if absent). Truncate similarly. |
| KB Rule Violated | Which CLAUDE.md constraint or bug pattern this violates. Empty if pure diff with no KB match. |
| Risk | HIGH / MEDIUM / LOW |
| Source File | Value of `source=` argument if provided, otherwise empty |
| Should Fix | `PENDING_REVIEW` |
| Reviewed By | `_pending_` |
| Linked Bug ID | _(empty — filled later by `/process-comparison`)_ |

---

## Step 9 — Print Comparison Report

Print a complete summary:

```
═══════════════════════════════════════════
  Comparison Report
═══════════════════════════════════════════

  Generated: {generated_path}
  Expected:  {expected_path}
  Source:    {source_path or "not provided"}
  KB:        {CLAUDE.md loaded / not found}
  Format:    {detected format(s)}

───────────────────────────────────────────

| # | Comp ID | Category | Location | Summary | Risk |
|---|---------|----------|----------|---------|------|
| 1 | COMP-... | MISSING_CONTENT | ... | ... | HIGH |
| 2 | COMP-... | WRONG_CONTENT | ... | ... | MEDIUM |
...

───────────────────────────────────────────

  Totals:
    MISSING_CONTENT:  {N}
    WRONG_CONTENT:    {N}
    EXTRA_CONTENT:    {N}
    FORMATTING:       {N}
    Suppressed by KB: {N}
    ─────────────────
    Total written:    {N}

───────────────────────────────────────────

  Next steps:
    1. Open comparison_sheet.md — review each PENDING_REVIEW row
    2. Change Should Fix to APPROVED or REJECTED
    3. Run /process-comparison to analyze approved issues and create fix proposals
```

---

## Important Rules

1. **KB is the primary lens.** When CLAUDE.md exists, use it to understand WHAT the generated file should look like — not just HOW it differs from expected. A discrepancy that violates a KB constraint is more important than one that doesn't.

2. **Never suppress without a KB rule.** Only suppress discrepancies that are explicitly permitted by a constraint in CLAUDE.md. If unsure, write the row to comparison_sheet.md and let the user decide.

3. **Truncate content in cells.** Comparison sheet cells should be scannable. Truncate Expected Content and Actual Content to ~100 characters. The full context can be found by reading the files at the listed locations.

4. **Handle large files in chunks.** For PDFs over 10 pages, read 5 pages at a time. For large XLSX files, process sheet by sheet. For large JSON files, process top-level keys one at a time.

5. **Be format-agnostic.** The same comparison logic applies regardless of format. The format only determines HOW content is loaded (Step 2), not how it is compared.

6. **One row per discrepancy.** Do not group multiple discrepancies into a single row. Each distinct issue gets its own Comp ID and row.

7. **Respect the comparison_sheet.md format exactly.** The downstream `/process-comparison` command depends on parsing this table. Do not add extra columns or change column names.
