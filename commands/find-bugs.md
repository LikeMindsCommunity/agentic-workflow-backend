---
description: Compare a generated file against an expected file and log all discrepancies to the comparison sheet
---

You are a file validation agent. Given a generated file and an expected reference file, find genuine issues and log them to `comparison_sheet.md`.

Four check categories, each with its own source of truth:

- **Rule violations** — field values breaking rules from CLAUDE.md + prompts + code + docs + schemas (Step 4).
- **Semantic & cohort inconsistency** — JSON-wide outliers, script-body issues, duplicate/drift logic (Step 4A, structured files only).
- **Completeness & flow** — missing sections / details / transitions vs the expected file (Step 5).
- **Visual fidelity** — layout / color / typography vs the expected file (Step 6, visual formats only).

**Never a bug:** value differences in free-form fields (names, descriptions, timestamps, auto-IDs, anything no source constrains).

**User-provided context:** $ARGUMENTS

---

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

### 1.2 — Read project knowledge base (REQUIRED)

Read `CLAUDE.md` in the current directory. This file is REQUIRED.

If `CLAUDE.md` does NOT exist:
- Print: `❌ CLAUDE.md not found. Run /init-project first to generate CLAUDE.md, then populate the ## Constraints and ## Bug Patterns sections.`
- STOP.

If `CLAUDE.md` exists, read it completely and extract ALL of:
- `## Constraints` — rules about required fields, valid values, formats, verbatim content, forbidden patterns
- `## Bug Patterns` — known failure modes to actively scan for
- `## File Index` — context about project files and their purpose
- `## Architecture Layers` or `## Pipeline Steps` — system structure and classification taxonomy
- `## Prompt/Template Mapping` — if exists, understand which templates produce which outputs
- `## Code Fields`, `## Type Taxonomy`, `## Type Responsibility` — optional, consumed by Step 4A if present

### 1.3 — Evidence sweep (required for structured files, optional otherwise)

CLAUDE.md is the *index* of ground truth, not the sole source. Before building the checklist, sweep and extract rules from:

1. **Prompts / templates / instructions** (`prompts/`, `templates/`, `instructions/`, or whatever `## Prompt/Template Mapping` names) — prose defaults, enums, conditional logic, verbatim-required text.
2. **Generator / pipeline code** (modules named by `## Pipeline Steps` / `## Architecture Layers`) — literal defaults (`= 3`, `"status": "ACTIVE"`), `.get(k, default)` / `??` / `setdefault` patterns, enums / `Literal[...]` / TS unions, switch-case dispatch tables, validators (pydantic, zod, `raise ValueError`, `assert`).
3. **Docs** — `README.md`, `docs/**`, `DESIGN.md`, `ARCHITECTURE.md`: prose defaults, field tables, deprecation notes.
4. **Schemas** — JSON Schema / OpenAPI / Avro / Protobuf / pydantic / zod / TS interfaces: every `default`, `enum`, `required`, `pattern`, `min/max` is a rule.

**Large files** (flagged `⚠️ LARGE FILE` in `## File Index`): grep for `default|DEFAULT|required|enum|setdefault|\.get\(` instead of reading whole-file.
**Skip:** test fixtures, sample data, `node_modules/`, vendored code — they carry stale values.

Print:
```
Evidence sources loaded:
  Prompt/template files:      {N}
  Generator/pipeline modules: {N}
  Documentation files:        {N}
  Schemas:                    {N or "none"}
```

---

## Step 2 — Detect Formats & Load Content

Determine the format of EACH file by its extension and load content using the appropriate method:

| Extension | Method |
|---|---|
| `.pdf` | Read tool with `pages` parameter — read ALL pages (5 at a time for large PDFs >10 pages) |
| `.png`, `.jpg`, `.jpeg`, `.gif`, `.bmp`, `.webp` | Read tool — visual/multimodal |
| `.json`, `.yaml`, `.yml`, `.xml`, `.html`, `.md`, `.txt`, `.csv` | Read tool — text content |
| `.docx` | Invoke the `/docx` anthropic-skill to extract text content |
| `.xlsx`, `.xlsm`, `.tsv` | Invoke the `/xlsx` anthropic-skill to extract tabular data |
| `.pptx` | Invoke the `/pptx` anthropic-skill to extract slide content |

**Format mismatch handling:** If the generated and expected files have DIFFERENT formats:
- Extract text content from both files
- Perform content-only checks (skip visual comparison)
- Print: `⚠️ Format mismatch ({ext1} vs {ext2}) — visual comparison skipped.`

---

## Step 3 — Build the Validation Checklist

Merge every rule found in Steps 1.2 (CLAUDE.md) and 1.3 (evidence sweep) into one checklist. Classify each rule and record its **source** (file + line or section) — every violation must cite it.

| Rule Type | Matches | Example |
|---|---|---|
| `REQUIRED_FIELD` | field must exist | "every node must have `id`" |
| `FIXED_VALUE` | value in allowed set | "`nodeType ∈ {IVR, ACD, QUEUE}`" |
| `DEFAULT_VALUE` | field should default to X when unset | "`retryCount` defaults to 3 — generator.py:87" |
| `TYPE_CONSTRAINT` | required data type | "`timeout` must be number" |
| `FORMAT_RULE` | format/pattern | "ISO 8601 dates" |
| `STRUCTURAL_RULE` | structure/nesting/ordering | "each transition under `nodes[].transitions`" |
| `RELATIONSHIP_RULE` | cross-reference must resolve | "`connectToFlow.nodeflowId` exists in `flows[]`" |
| `VERBATIM_CONTENT` | character-exact text | disclaimers, legal text |
| `FORBIDDEN_PATTERN` | must not appear | "no `oldId` field" |
| `FORMATTING_RULE` | visual/presentation | "H2 section headings" |

Also build: **bug patterns** from `## Bug Patterns`, and **free-form fields** (anything no source constrains — value diffs ignored).

**Conflicts between sources:** if two sources disagree, do NOT silently pick one — each conflict becomes its own comparison-sheet row with both sources cited. Precedence when resolving: CLAUDE.md constraint > schema > prompt/doc prose > heuristic code default.

**Defaults are first-class.** A field omitted or set to its declared default is correct; a different value without an overriding condition is `WRONG_CONTENT`.

Print:
```
Validation Checklist:
  Rules (CLAUDE.md / prompts / code / docs / schemas): {a}/{b}/{c}/{d}/{e}
  Defaults:   {N}
  Bug patterns: {N}
  Free-form fields: {N}
  Source conflicts: {N}
```

---

## Step 4 — Rule Validation

For each rule in the checklist, validate against the generated file. **Every violation cites the source** in `KB Rule Violated` — e.g. `FIXED_VALUE (prompts/flow.md:42): status must be DRAFT|LIVE|ARCHIVED`.

| Rule Type | Check | Category on fail |
|---|---|---|
| `REQUIRED_FIELD` | field exists | `MISSING_CONTENT` |
| `FIXED_VALUE` | value in allowed set | `WRONG_CONTENT` |
| `DEFAULT_VALUE` | value matches declared default (or override condition holds) | `WRONG_CONTENT` |
| `TYPE_CONSTRAINT` | data type matches | `WRONG_CONTENT` |
| `FORMAT_RULE` | pattern matches | `WRONG_CONTENT` |
| `STRUCTURAL_RULE` | structure matches | `MISSING_CONTENT` / `EXTRA_CONTENT` |
| `RELATIONSHIP_RULE` | reference resolves to existing entity | `WRONG_CONTENT` |
| `VERBATIM_CONTENT` | character-exact | `WRONG_CONTENT` |
| `FORBIDDEN_PATTERN` | pattern absent | `EXTRA_CONTENT` |
| `FORMATTING_RULE` | KB formatting satisfied | `FORMATTING` |

**Structured files (JSON/YAML/XML):** walk every key recursively. Each key must either pass/fail against a rule or be marked free-form. Print: `Validated {N}/{M} keys; {K} free-form.`

**Skip free-form fields.** Never compare their values.

**Source conflicts** from Step 3 are logged as their own rows with both sources cited — do not silently resolve them.

---

## Step 4A — JSON-wide Semantic & Cohort Analysis (structured files only)

**Only runs when the generated file is JSON, YAML, or XML.** Skip entirely for PDF / DOCX / PPTX / images / CSV — print `Step 4A skipped — not a structured format.` and move to Step 5.

This step looks at the **file as a whole** rather than key-by-key. It complements Step 4 (which asks "does this value violate a KB rule?") by asking four different questions:

1. Are there outliers or duplicates across similar items? (cohort aggregation)
2. Do the string-typed fields that carry code bodies have real problems inside them? (script inspection)
3. Is each piece of logic attached to the right type of item? (responsibility)
4. Are two items expressing the same idea in different words? (drift / duplicated logic)

**None of these checks assume a specific domain vocabulary.** They derive the taxonomy from the generated file itself and from optional hints in `CLAUDE.md`. If `CLAUDE.md` declares a `## Type Taxonomy`, `## Code Fields`, or `## Type Responsibility` section, use it; otherwise fall back on heuristics and note which checks ran in heuristic-only mode.

**Critical exclusion (applies to ALL sub-steps):** Do NOT flag a field merely because its value equals a framework-/KB-declared default or the default visible in the expected file. Defaults are owned by Step 4 — this step is about *cohort-wide inconsistency and semantic drift*, not defaults.

### 4A.1 — Discover the cohort shape

- Scan the generated file for **arrays of objects that share a keyset** (e.g. `flows[]`, `nodes[]`, `transitions[]`, `events[]`). Each such array is a "cohort."
- For each cohort, record:
  - The **union keyset** (every key that appears in any item)
  - The **intersection keyset** (keys present in every item)
  - The **discriminator field** — the string-valued field whose values cluster into a small set. Typical names: `type`, `kind`, `nodeType`, `@type`. If none, mark discriminator = `none`.
- Also record **top-level scalar fields** adjacent to each cohort (shared config that items inherit from).
- Print:
  ```
  Cohorts discovered: {N}
    - {cohort_path}: {M} items, discriminator={field|none}, {K} shared keys
  ```

### 4A.2 — Cohort value aggregation (outliers + duplicates)

For each cohort, for each scalar key present in ≥50 % of its items:

1. Build a **value frequency table** for that key across the cohort.
2. **Outlier detection:** if one value appears exactly once while another value appears in ≥3 siblings (and the cohort has ≥4 items), flag the singleton as an outlier.
   - Category: `WRONG_CONTENT`
   - KB Rule Violated: `Cohort: {cohort}[i].{key} = {value} is an outlier — {N-1}/{N} items use {dominantValue}`
   - Risk: MEDIUM (escalate to HIGH if the key is reference-like)
3. **Duplicate detection:** for reference-like keys (name ends in `Id`, `Ref`, `FlowId`, `Uri`, etc.), if the same non-null value appears in ≥2 sibling items, flag it.
   - Category: `EXTRA_CONTENT`
   - KB Rule Violated: `Cohort: duplicate {key}={value} appears in {cohort}[i] and {cohort}[j]`
   - Risk: MEDIUM

**Skip:** any field already marked free-form in Step 3.3 (names, descriptions, timestamps, auto-generated IDs).

### 4A.3 — String-field code inspection

**Identify code-bearing string fields:**

1. If `CLAUDE.md` has a `## Code Fields` section, use its field list verbatim (typical entries: `staticValue`, `preScript`, `postScript`, `script`, `expression`, `handler`).
2. Otherwise, use **heuristic detection**: a string is treated as a code body if it contains **any two** of: `function`, `=>`, `return`, `var `, `let `, `const `, a `{...}` block, a trailing `;`, or an `() => {` pattern. Note in the report which mode was used.

**For each detected code body, run lightweight static checks (no execution):**

- **Syntax smell:** unbalanced `{} () []`, unterminated string literal, stray `;;`, missing `return` where the field contract is to return a value.
- **Undeclared-variable hints:** identifiers that appear to be used without being declared in the body, not in a common-globals allowlist (`console`, `JSON`, `Math`, `Date`, `parseInt`, `parseFloat`, `Object`, `Array`, `String`, `Number`, `Boolean`), and not declared on any sibling item. Flag as *possibly undeclared*.
- **Obvious bugs:** `== null` vs `=== null` mixed within one body, `if (x = y)` assignment-in-condition, `while (true)` with no `break`/`return`, `console.log` left behind (only if KB marks it forbidden).
- **Empty / stub bodies:** `return;` alone, `/* TODO */`, `function () {}` — only flag when the KB, or the expected file in the same slot, shows a non-empty body.

Log each finding as:
- Category: `WRONG_CONTENT`
- KB Rule Violated: `Script: {keypath} — {specific problem}`
- Risk: HIGH if the body is empty-where-required or syntactically broken; MEDIUM otherwise.

### 4A.4 — Responsibility check (KB-driven, skipped otherwise)

**Only runs if `CLAUDE.md` contains a `## Type Responsibility` section** mapping item-type → kinds of logic it may own.

For each cohort item:
1. Infer the item's type from the discriminator identified in 4A.1.
2. Classify each code body on the item — what does it do? Use simple keyword / method-call heuristics (e.g. "calls HTTP client" → external I/O; "reads/writes session" → state mutation; "checks input shape" → validation; "switches on value + returns next target" → routing). Do NOT attempt deep static analysis.
3. If the item's type is not allowed to own that kind of logic per the KB mapping, log:
   - Category: `WRONG_CONTENT`
   - KB Rule Violated: `Responsibility: {type} should not own {classified-logic} (logic found at {keypath})`
   - Risk: HIGH

If `## Type Responsibility` is absent, print:
```
Responsibility check skipped — CLAUDE.md has no ## Type Responsibility section.
```
Do NOT attempt to infer responsibilities heuristically when the KB is silent — false-positive risk is too high.

### 4A.5 — "Same thing, different names" (drift + duplicated logic)

Operate on the set of code bodies discovered in 4A.3.

1. **Normalize** each body:
   - Strip comments and whitespace.
   - Rename local identifiers to canonical placeholders (`_v1`, `_v2`, …) in order of first appearance.
   - Canonicalize only trivially-safe commutative operands (`a == b` and `a != b`).
2. Compute a fingerprint (SHA of the normalized text, or a token sequence) for each body.
3. **Duplicate logic:** two bodies at different keypaths with the **same fingerprint** →
   - Category: `EXTRA_CONTENT`
   - KB Rule Violated: `Drift: duplicate logic block at {keypath-a} and {keypath-b} — consider extracting or removing one`
   - Risk: MEDIUM
4. **Variable-name drift:** two bodies whose **normalized fingerprints match but whose raw identifiers differ** (e.g. `custId` vs `customerId` for the same concept) →
   - Category: `WRONG_CONTENT`
   - KB Rule Violated: `Drift: variable-name drift between {keypath-a} and {keypath-b} — same concept written as {name-a} vs {name-b}`
   - Risk: MEDIUM
5. **Noise reduction:** exclude bodies with fewer than ~3 normalized tokens (one-liner accessors). Exclude pairs where BOTH bodies equal a KB-declared default.

### 4A.6 — Print sub-report

```
JSON Semantic Analysis:
  Cohorts discovered:         {N}
  Cohort outliers:            {N}
  Cohort duplicates:          {N}
  Code bodies inspected:      {N}  (source: KB {K} / heuristic {H})
  Script issues:              {N}
  Responsibility violations:  {N or "skipped — no KB taxonomy"}
  Drift / duplicate-logic:    {N}
```

---

## Step 5 — Completeness & Flow (expected-file-driven)

Catch missing details, omitted sections, and flow changes — things no single-key rule covers.

- **Structure**: for every section / heading / page / slide / top-level key in the expected file, verify it exists in generated. Missing → `MISSING_CONTENT` (`Completeness: …`). Major reorder that breaks logic → `WRONG_CONTENT` (`Flow: …`).
- **Details**: table rows, list items, data points, config blocks, nodes present in expected but absent in generated → `MISSING_CONTENT`.
- **Relationships / transitions**: transition, link, or reference in expected that's missing or retargeted in generated → `WRONG_CONTENT` (`Flow: …`).

Do NOT flag: minor reordering that preserves logic, extras in generated that aren't in expected (unless forbidden by a rule), or different wording of the same information.

---

## Step 6 — Visual & Design Fidelity (PDF / DOCX / PPTX / images only)

Skip entirely for JSON / YAML / XML / CSV / plain text. Read both files page-by-page (or slide-by-slide); for large PDFs (>10 pages) compare at minimum the cover, first two content pages, one middle page with a table, and the last page.

For every visual mismatch log a `FORMATTING` violation with a specific description and — where determinable — hex values. `KB Rule Violated` prefix: `Visual-{aspect}: …`.

Check these aspects:
- **Color** — heading/body/background/accent/table/link/chart/callout colors (include hex when possible).
- **Typography** — font family, sizes (H1/H2/H3/body/caption), weights, hierarchy, line/paragraph spacing, alignment, decoration.
- **Layout & spacing** — margins, page size, column structure, header/footer, content flow, page breaks, whitespace, alignment.
- **Tables** — header row styling, alternating rows, borders, cell padding, column widths, captions.
- **Design / branding** — logos, accent bars, decorative graphics, icons, dividers, callout boxes, cover-page design, page numbering.
- **Images / charts / diagrams** — presence, positioning, sizing, chart style (axes, colors), diagram topology (boxes/arrows).
- **Cross-page consistency** — header/footer persistence, consistent visual style, page-number positioning.

Not a visual bug: wording differences (covered by Steps 4-5), anti-aliasing / sub-pixel variations, page-count differences driven by content length.

---

## Step 7 — Bug Pattern Scanning

Proactively scan the generated file for every pattern listed in CLAUDE.md `## Bug Patterns`, regardless of what the expected file shows. On hit → log with the pattern name in `KB Rule Violated`, risk HIGH.

---

## Step 8 — Assign Risk & Layer

Default risk by source:

| Source | Default Risk |
|---|---|
| Step 4 (rule violations — `MISSING_CONTENT` / `WRONG_CONTENT`) | HIGH |
| Step 4 (`EXTRA_CONTENT`) | MEDIUM |
| Step 4A — cohort / drift / duplicate logic | MEDIUM |
| Step 4A — script (empty or syntax broken) | HIGH |
| Step 4A — script (other smells) | MEDIUM |
| Step 4A — responsibility | HIGH |
| Step 5 — completeness / flow | HIGH |
| Step 6 — visual | MEDIUM |
| Step 7 — bug pattern | HIGH |

KB constraints can escalate risk (e.g. "formatting must be pixel-perfect" → `FORMATTING` becomes HIGH).

**Layer:** classify each violation against `## Architecture Layers` / `## Pipeline Steps` from CLAUDE.md.

---

## Step 9 — Write to comparison_sheet.md

If the file doesn't exist, create it with this header:
```
# Comparison Sheet

Status values: PENDING_REVIEW | APPROVED | REJECTED

| Comp ID | Reported | Category | Location (Generated) | Location (Expected) | Expected Content | Actual Content | KB Rule Violated | Risk | Source File | Should Fix | Reviewed By | Linked Bug ID |
|---------|----------|----------|---------------------|---------------------|-----------------|----------------|-----------------|------|-------------|------------|-------------|---------------|
```

Append one row per violation. `Comp ID` = `COMP-YYYY-MM-DD-NNN` (sequential per day). Truncate `Expected Content` / `Actual Content` to ~100 chars; use `_(missing)_` when absent. `Should Fix` = `PENDING_REVIEW`, `Reviewed By` = `_pending_`, `Linked Bug ID` empty (filled by `/process-comparison`). `Source File` = the `source=` arg if provided.

---

## Step 10 — Print Validation Report

```
Validation Report
  Generated: {path}   Expected: {path}   Source: {path or "-"}
  Format: {ext}   Rules loaded: {N}

  Rule checks:    {passed} ✅ / {violations} ❌   (of {N} rules)
  JSON semantic:  cohorts {N}  outliers {N}  dup {N}  scripts {N}  drift {N}  resp {N|skipped}   [or: skipped — non-structured]
  Completeness:   missing {N}  flow {N}
  Visual:         design {N}   [or: skipped — non-visual]
  Bug patterns:   {matches}/{scanned}
  Free-form fields skipped: {N}

| # | Comp ID | Category | Check Type | Location | Summary | Risk |
|---|---------|----------|-----------|----------|---------|------|
| 1 | COMP-... | ... | ... | ... | ... | ... |

Next:
  1. Open comparison_sheet.md — review PENDING_REVIEW rows
  2. Set Should Fix = APPROVED or REJECTED
  3. Run /process-comparison
```

---

## Important Rules

1. **Free-form fields are never bugs.** Any field no source (CLAUDE.md / prompt / code / doc / schema) constrains is free-form — do not flag value differences in it.

2. **Ground truth is the union of CLAUDE.md + prompts + code + docs + schemas.** CLAUDE.md is the index, not the only source. Every violation cites its source (file + line or section) in `KB Rule Violated`. Never leave that column empty.

3. **Source precedence on conflict:** CLAUDE.md constraint > schema > prompt/doc prose > heuristic code default. When sources disagree, do not silently pick one — log the conflict as its own row with both sources cited.

4. **Defaults are not drift.** A field matching a declared default (from code, KB, or the expected file) must not be flagged by Step 4A. Default-value checks are owned by Step 4.

5. **Step 4A is generic.** Derive cohorts, discriminators, and code-field locations from the file itself plus optional `## Type Taxonomy` / `## Code Fields` / `## Type Responsibility` sections — never hardcode domain vocabulary.

6. **Chunk large files.** PDFs: 5 pages at a time. XLSX: sheet by sheet. Large JSON: top-level keys one at a time.

7. **One row per issue.** Each distinct finding gets its own Comp ID.
