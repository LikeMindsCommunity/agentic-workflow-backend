---
description: Read a client's KB (from /platform-kb) and generate a complete standalone find-bugs-{client}.md skill — all checks, rules, and execution logic baked in, KB as sole source of truth.
---

You are a skill-generation agent. Given a client's Knowledge Base directory (produced by `/platform-kb`), produce a **complete, standalone** `find-bugs-{client}.md` command file that can compare generated vs expected files for this client and surface all discrepancies to `comparison_sheet.md`.

**User-provided context:** $ARGUMENTS

---

## Step 1 — Parse Arguments & Read KB Directory

Parse `$ARGUMENTS` for:
- `client=<name>` — REQUIRED. The client identifier (lowercase, no spaces). Used for skill filename.
- `kb=<path>` — REQUIRED. Path to the KB directory (e.g., `outputs/{client}/kb/`).

If either is missing, print usage and STOP:
```
Usage: /generate-find-bugs-skill client=<name> kb=<path>

Example: /generate-find-bugs-skill client=acme kb=outputs/acme/kb/
```

List all `.md` files in the KB directory. Read EVERY file completely — no skipping, no partial reads. For large files, read in chunks using offset/limit until the entire file is consumed.

Print:
```
KB directory: {path}
Files found: {N}
  {filename} ({lines} lines)
  ...
```

---

## Step 2 — Classify KB Sections

For each KB file, classify it by matching filename patterns AND reading H1/H2 headings:

| File Pattern | Section ID | Content Type |
|---|---|---|
| `00-overview*` | `CORE-A` | Domain context, glossary, use-case, architecture |
| `*building-block*` or `*component*` | `UC-1` | Entity types, attribute schemas, event catalogs |
| `*composition*` or `*wiring*` or `*connection*` | `UC-2` | Transitions, conditions, ports, parent-child |
| `*artifact-schema*` or `*output-schema*` or `*document-structure*` or `*brd-structure*` | `UC-3` | Top-level structure, field/section classification |
| `*variable*` or `*data-flow*` or `*scripting*` | `UC-4` | Variables, scripting language, expressions |
| `*api-reference*` or `*endpoint*` | `UC-5` | API endpoints, parameters, schemas |
| `*auth*` | `UC-6` | Authentication methods, credentials |
| `*data-model*` or `*entit*` or `*master*` or `*taxonomy*` | `UC-7` | Entities, relationships, lifecycle, master data |
| `*event*` or `*webhook*` | `UC-8` | Event catalog, payload schemas |
| `*config*` | `UC-9` | Configuration hierarchy, options |
| `*layout*` or `*visual*` or `*coordinate*` | `UC-10` | Visual/coordinate rules |
| `*pattern*` | `CORE-B` | Named patterns, required elements, anti-patterns |
| `*constraint*` | `CORE-C` | Numbered rules (C1, C2...) |
| `*input-checklist*` | `CORE-D` | Per-instance fields, tier classification |
| `*gap*` | `CORE-E` | Known gaps, assumptions |
| `*catalog*` or `*capability*` or `*module*` | `DOMAIN-CATALOG` | Feature/module catalogs, capability listings |

Files that don't match any pattern → classify as `CUSTOM` and note their H1 heading.

If a file matches multiple patterns (e.g., `01-brd-structure.md` could be UC-3 and also contains module ordering), assign the BEST match and note secondary relevance. A single file can contribute to multiple check classes.

Print:
```
KB sections detected:
  CORE-A: 00-overview.md
  UC-1:   01-building-blocks.md
  UC-2:   02-composition-rules.md
  ...
  Not found: UC-5, UC-6, UC-8
  Custom: {filename} — "{H1 heading}"
```

---

## Step 3 — Extract Platform Metadata

### 3.1 — From CORE-A (overview)

Extract:
- **Platform name**: from H1 heading or first paragraph
- **Use-case classification**: search for `component-flow`, `api-sdk`, `artifact-generator`, `event-driven`, `data-platform`, `config-system`. If not explicit, infer from which UC sections exist.
- **Primary file format**: what format does the platform generate/consume? (JSON, YAML, XML, PDF, DOCX, XLSX, etc.)
- **Domain vocabulary**:
  - `primary_entity`: the main thing being compared (section, record, entity, component, resource, row...)
  - `entity_plural`: plural form
  - `discriminator_field`: field or marker that tells you what type an entity is (type, kind, category, className, sectionTitle, heading...)
  - `container_path`: where entities live in the generated file (e.g., `items[]`, `sections[]`, `records[]`, top-level array, or page sequence for documents)
- **Architecture**: top-level structure of the generated artifact

### 3.2 — Comparison mode detection

Based on the primary file format:
- `.json`, `.yaml`, `.yml`, `.xml` → `structured`
- `.pdf`, `.docx`, `.pptx`, `.html`, `.md` → `document`
- `.xlsx`, `.xlsm`, `.csv`, `.tsv` → `tabular`

Also check if the KB mentions any special archive/container formats (e.g., zip archives containing the actual comparison file, custom extensions wrapping standard formats). Record these for archive handling.

### 3.3 — Authority file detection

Search ALL KB files for references to a primary config/mapping/schema file:
- Look for: "source of truth", "authority", "mapping file", "schema file", "registry", "reference file"
- Look for specific filenames referenced as authoritative sources
- Record: file name, whether mandatory, how defaults are encoded

If no authority file mentioned: the KB itself is the sole authority. Most clients will NOT have one.

### 3.4 — Entity matching strategy

Search the KB for how entities should be matched between generated and expected:
- **By stable ID**: if KB says IDs are "stable", "user-defined", "from input", "deterministic"
- **By discriminator + position**: if KB says IDs are "generated at runtime", "UUID", "unique per instance"
- **By heading/title**: for document mode, match by section title/heading hierarchy
- **By parent-child path**: for nested/hierarchical structures, match by full path from root
- **Default if unclear**: match by discriminator field + position (structured) or by heading hierarchy (document)

Print:
```
Platform: {name}
Use-case: {classification}
Format: {format} → {comparison_mode} mode
Authority file: {name or "none — KB is sole authority"}
Entity matching: {strategy}
Archive formats: {list or "none"}
```

---

## Step 4 — Derive Check Classes from KB Sections

For each detected KB section, derive check classes. **Only generate classes for sections that actually exist.** Read each file thoroughly and extract CONCRETE data — specific field names, constraint IDs, pattern names, attribute lists. Never produce vague descriptions.

### 4.1 — From UC-1 (Building Blocks) → `attribute_validation` + `event_validation`

Read the entire file. For each entity type documented:

**Extract attribute schemas:**
- Every attribute table row: `Attribute | Type | Required | Default | Allowed Values | Dynamic | Description`
- Build a complete attribute registry: `{entity_type: [{attr_name, type, required, default, allowed_values}]}`
- Note which attributes carry scripts/code/expressions
- Note which attributes are prompt/file references

**Extract event catalogs:**
- Every event table row: `Event Name | Trigger | Typical Next | Required Handling`
- Note which events are REQUIRED

Record extracted data:
```
Attribute registry: {N} entity types, {M} total attributes
  {type_1}: {count} attributes ({required_count} required)
  {type_2}: {count} attributes ({required_count} required)
Event catalog: {N} entity types, {M} total events ({R} required)
```

### 4.2 — From UC-2 (Composition Rules) → `wiring_validation` [+ `composition_validation`]

Extract:
- Connection mechanism (transitions, edges, event chains, section ordering...)
- Connection schema (fields on each connection)
- Condition expression language syntax rules (if documented)
- Parent-child composition rules (if documented)

### 4.3 — From UC-3 (Artifact Schema / Document Structure) → `schema_conformance`

Extract:
- Top-level required structure (keys or sections, required status)
- Field/section classification (Fixed, Identity, Configurable, Computed, Mandatory, Optional)
- Fixed fields/sections with exact required values or ordering

For **document mode**: extract section ordering rules, mandatory sections, ToC requirements.

### 4.4 — From UC-4 (Variables & Data Flow) → `variable_validation` [+ `script_validation`]

Extract:
- Variable declaration mechanism and format
- All platform-provided / built-in variables (names + types)
- Variable binding patterns
- Scripting language details (engine, built-ins, required patterns, prohibited methods)
- Condition expression syntax rules

### 4.5-4.8 — From UC-5 through UC-9

Generate check classes only for sections that exist:
- UC-5 → `api_conformance`
- UC-7 → `entity_integrity`
- UC-8 → `event_system_validation`
- UC-9 → `config_validation`
- UC-10 → `layout_validation`

### 4.9 — From CORE-B (Patterns) → `pattern_compliance` [ALWAYS if CORE-B exists]

Extract EVERY named pattern:
- Pattern name
- When to use / frequency / trigger condition
- Required Elements (complete list)
- Anti-patterns (complete list with what's WRONG)

Record: `{N} patterns extracted, {M} total required elements, {A} total anti-patterns`

### 4.10 — From CORE-C (Constraints) → `numbered_constraints` [ALWAYS if CORE-C exists]

Extract EVERY numbered constraint:
- Constraint ID (C1, C2, ...)
- Rule text (verbatim)
- Category (structural, identity, fixed-value, relationship, scripting, content, ordering, etc.)

Record: `{N} constraints extracted: {structural} structural, {identity} identity, ...`

### 4.11 — From CORE-D (Input Checklist) → `content_accuracy` [DOCUMENT MODE]

Only for document comparison mode. Extract:
- Tier 1 fields (critical — must match exactly)
- Tier 2 fields (important — should match)
- Tier 3 fields (optional — cosmetic)

### 4.12 — From DOMAIN-CATALOG → `catalog_completeness`

If a catalog/capability/module KB file exists, extract:
- All documented modules/features/capabilities
- Required vs optional items
- Hierarchical grouping

### 4.13 — `strict_instructions` [ALWAYS]

Scan ALL KB files for directives containing: STRICT, CRITICAL, MUST, MUST NOT, NEVER, ALWAYS, REQUIRED, IMPORTANT, DO NOT, INVARIANT, or bold-tagged **CRITICAL:**/**MUST:**

Count and record each with source file and section context.

Record: `{N} strict directives across {F} files`

### 4.14 — `open_ended` [ALWAYS]

Safety net for any KB rule not covered by above classes. The listed classes are the FLOOR, not the ceiling.

Print complete check class summary:
```
Check classes derived: {N}
  {id}: {name} (from {section}) — {concrete_count} rules
  ...
```

---

## Step 5 — Extract Free-Form Exclusions

A field/section is free-form (never flagged for value differences) if ANY of:

1. **UC-3** classifies it as `Identity` (regenerated per build)
2. **UC-1** marks it as auto-generated or runtime-created
3. **CORE-C** says it's a fixed structural field checked by constraints (not by comparison)
4. The KB or general conventions indicate the field is cosmetic or non-deterministic:
   - Display-only labels or descriptions that are user-authored and not constrained by the KB
   - Timestamps, dates of generation, or actor fields (who created/modified)
   - Auto-generated identifiers (UUIDs, sequential IDs regenerated per build)
   - Layout/positioning data (coordinates, visual placement) unless the KB explicitly constrains them
   - Any field the KB classifies as "cosmetic", "informational", or "non-functional"
5. The KB explicitly says "do not compare" / "varies per build" / "cosmetic only" / "user-defined"

Also identify FIXED structural fields — these have required values but are checked by constraints, not by comparison against expected. Mark separately.

Print:
```
Free-form exclusions: {N} fields
  {field_name} — {reason}
  ...
Fixed structural (checked by constraints): {N}
  {field_name} = {value} — {constraint_id}
```

---

## Step 6 — Extract Body-Bearing Attributes (Structured Mode Only)

Skip this step if comparison_mode is NOT `structured`.

A field is body-bearing (must be extracted verbatim, never summarized) if ANY of:

1. **UC-1 attribute schema** has Type = `script`, `expression`, `code`, `payload`, `body`, `query`, `template`, `markup` or Description contains those keywords + "comma-separated", "list of"
2. **UC-4** names specific fields as script-bearing or expression-bearing
3. The field name matches common body-bearing patterns (check against KB — these are EXAMPLES, not a fixed list):
   - Script/code: any field whose name or KB description indicates it holds executable code or logic
   - Expression/condition: any field holding filter expressions, condition logic, formulas
   - Handler/hook: any field holding event handlers, callbacks, lifecycle hooks
   - Data payload: any field holding structured data payloads, column definitions, header lists
   - Template/markup: any field holding HTML, email bodies, message templates, rich text
   - Query: any field holding SQL, API queries, search expressions

   **The KB's attribute schemas are the primary source for identifying these — not a hardcoded list of field names.** Read the KB's attribute tables and identify fields by their Type and Description columns.

Classify each as:
- `logic_carrying` (HIGH risk): scripts, expressions, handlers, conditions
- `data_carrying` (MEDIUM risk): payloads, headers, column names, templates

Print:
```
Body-bearing attributes: {N}
  Logic-carrying (HIGH): {list}
  Data-carrying (MEDIUM): {list}
```

---

## Step 7 — Assemble & Write the Skill File

Now write the complete skill file at: `.claude/commands/find-bugs-{client}.md`

The output file must be a COMPLETE, SELF-CONTAINED skill prompt. It must contain ALL the knowledge needed to perform the comparison — the executing LLM should need NOTHING beyond this skill file, the KB files, and the two comparison files (generated + expected).

### Output file structure:

```markdown
---
description: Compare generated vs expected {format} files for {Client} — surfaces all discrepancies to comparison_sheet.md
---

You are a {Client} file comparison agent. Your job is to compare a generated {format} file against an expected reference file and surface every genuine discrepancy to `comparison_sheet.md`.

**Comparison mode:** {comparison_mode}
**Primary file format:** {format}
**User-provided context:** $ARGUMENTS

---

## Canonical Comparison Sheet Format

{If comparison_sheet.md does not exist, create it with this header. If it exists, APPEND rows — never overwrite.}

| Comp ID | Reported | Category | Location (Generated) | Location (Expected) | Expected Content | Actual Content | KB Rule Violated | Risk | Source File | Should Fix | Reviewed By | Linked Bug ID |
|---------|----------|----------|---------------------|---------------------|-----------------|----------------|-----------------|------|-------------|------------|-------------|---------------|

**Column contract:**
- `Comp ID`: Sequential `COMP-YYYY-MM-DD-NNN` (per day, incrementing NNN)
- `Reported`: Today's date
- `Category`: One of: `MISSING_CONTENT` / `WRONG_CONTENT` / `EXTRA_CONTENT` / `FORMATTING`
- `Location (Generated)`: Full keypath (structured) or section+paragraph (document) in generated file
- `Location (Expected)`: Corresponding location in expected file, or KB source if no counterpart
- `Expected Content`: Literal expected value, verbatim, truncate to ~100 chars
- `Actual Content`: Literal generated value, verbatim; `_(missing)_` if absent
- `KB Rule Violated`: **Mandatory.** One-line message prefixed with check class. Must cite KB source — KB file:section, constraint ID, pattern name. Never empty.
- `Risk`: `HIGH` / `MEDIUM` / `LOW`
- `Source File`: The source that produced the generated output if identifiable (from `source=` arg); otherwise empty
- `Should Fix`: Always `PENDING_REVIEW`
- `Reviewed By`: `_pending_`
- `Linked Bug ID`: Empty (filled later by `/process-comparison`)

---

## Important Rules

1. **KB is the ONLY knowledge source.** Read ONLY the KB files at {kb_path}, the generated file, and the expected file. Do NOT read CLAUDE.md. Do NOT grep the codebase. Do NOT do a File Index sweep. All domain knowledge is in the KB.

2. **Canonical single-table format.** Every finding goes in the one 13-column table. Never split into multiple tables or formats. Downstream `/process-comparison` and `/apply-fixes` depend on this exact schema.

3. **All check classes run on every invocation.** Every listed check class must run to completion. Silently skipping any is a skill-side bug.

4. **Open-ended scope.** The listed check classes are the FLOOR, not the ceiling. Any KB rule not covered by named classes still gets evaluated under `open_ended`.

5. **Every row cites a KB source.** `KB Rule Violated` must name the authority: KB file:section, constraint ID (e.g., "C12"), pattern name, or specific KB rule text. Never empty.

6. **Free-form fields never flagged.** The following fields are NEVER discrepancies regardless of value differences:
   {paste the complete free-form exclusion list from Step 5}

7. **Propose-only.** No source edits, no git writes. Every finding is `PENDING_REVIEW`.

{8. IF comparison_mode == structured:}
8. **Body-bearing attributes extracted verbatim, never summarized.** For every attribute in this list:
   Logic-carrying (HIGH): {list from Step 6}
   Data-carrying (MEDIUM): {list from Step 6}
   Copy the literal string value from BOTH generated and expected. Compare character-for-character (whitespace-only differences excluded). Descriptions like "script contains logic to..." are FORBIDDEN — always extract the actual content. Truncate at 2 KB with `... [truncated, original {N} bytes]` marker if needed.

{9. IF archive formats exist:}
9. **Archive handling.** {archive_extension} files are {archive_type} archives. Unpack in-memory and use the inner {inner_file} for comparison.

10. **Empty-result handling.** If zero discrepancies found, write header + single confirmation row:
    - `Comp ID = COMP-...-000`
    - `Category = WRONG_CONTENT`
    - `KB Rule Violated = No discrepancies found across {N} {primary_entity_plural} / {M} attributes; all {K} check classes ran to completion`
    - `Risk = LOW`

11. **Plausibility check before writing.** Verify:
    - Every check class ran (no silent skips)
    - Every constraint was evaluated or recorded as advisory
    - Every strict directive was processed
    {IF structured mode:} - Every body-bearing attribute on every entity produced at least one comparison record

12. **Matching strategy: {strategy description}.** {E.g., "Match entities by type + position, NOT by ID. IDs are regenerated per build." OR "Match sections by heading text and hierarchy." OR "Match records by stable ID field."}

---

## Execution Pipeline

### Step 1 — Parse arguments & locate inputs

Parse `$ARGUMENTS` for:
- `kb=<path>` — REQUIRED. Path to the KB directory containing all KB files.
- `generated=<path>` — path to the generated file(s). Fallback: `inputs/compare/generated/`
- `expected=<path>` — path to the expected/reference file(s). Fallback: `inputs/compare/expected/`
- `source=<path>` — optional, the source file that produced the generated output

If `kb=` is missing, print usage and STOP:
```
Usage: /find-bugs-{client} kb=<kb-path> generated=<path> expected=<path>

Example: /find-bugs-{client} kb=outputs/{client}/kb/ generated=outputs/gen.{ext} expected=inputs/exp.{ext}
```

If `generated=` / `expected=` not provided, look in convention directories:
- `inputs/compare/generated/` for generated files
- `inputs/compare/expected/` for expected files

{IF archive formats:}
If a file has extension {archive_extension}, treat it as a {archive_type} archive. Unpack in-memory and use the inner `{inner_file}` as the comparison input.

Detect file format from extension. Use {comparison_mode} mode.

### Step 2 — Load KB

Read ALL `.md` files from the KB directory provided via the `kb=` argument.
{list each expected KB file with its section classification}

This is the ONLY knowledge source. Do NOT read CLAUDE.md. Do NOT grep the codebase. Do NOT do a File Index sweep.

{IF authority_file exists:}
Also load the authority file `{authority_file_name}` if it exists alongside the KB or at {search_paths}. If not found: {hard_fail_or_fallback}.

### Step 3 — {Format-specific comparison walk}

{FOR structured mode:}
Walk the generated {format} file {primary_entity} by {primary_entity} in parallel with the expected file.

**Matching:** {matching_strategy_details}

For each {primary_entity}:
1. Look up its type from the `{discriminator_field}` field
2. Find the corresponding {primary_entity} in the expected file using the matching strategy
3. Run every check class (Step 4) on this pair
4. For body-bearing attributes: extract verbatim content from BOTH files, compare character-for-character

Also check:
- {primary_entity_plural} present in expected but missing in generated → MISSING_CONTENT, HIGH
- {primary_entity_plural} present in generated but missing in expected → EXTRA_CONTENT, MEDIUM

{FOR document mode:}
Extract text content from both generated and expected files.
Identify sections by headings, structural markers, or page breaks.
Match sections between the two files by heading text and hierarchy.

For each matched section pair:
1. Run every check class (Step 4) on this pair
2. For verbatim sections (boilerplate, legal): compare character-for-character
3. For content sections: verify against KB rules (accuracy, completeness, ordering)

Also check:
- Sections present in expected but missing in generated → MISSING_CONTENT, HIGH
- Sections present in generated but missing in expected → EXTRA_CONTENT, MEDIUM
- Section ordering: verify against KB-documented ordering rules

{FOR tabular mode:}
Extract tabular data sheet-by-sheet from both files.
Compare headers, row counts, data types, and computed columns.

### Step 4 — Check Classes

Run ALL of the following check classes. Each must run to completion.

{GENERATE ONE SUBSECTION PER CHECK CLASS, using this template:}

#### {check_id}: {check_name}
**Source:** {KB file} — {section description}
**Risk default:** {HIGH/MEDIUM/LOW}
**KB Rule prefix:** "{prefix}:"

{Complete description of what to check, with CONCRETE extracted data:}
- Specific attribute names, constraint IDs, pattern names
- Exact values for defaults, fixed fields
- Complete lists of required elements

{Risk assignment rules for this class:}
- {category} → {RISK} when {condition}

---

{LIST ALL CHECK CLASSES HERE. The specific classes depend on which KB sections were detected:}

{UNIVERSAL CHECKS — always included:}

#### structural_completeness: Structural Completeness
**Source:** Generated + expected files
**Risk default:** HIGH
**KB Rule prefix:** "Structure:"

Every {primary_entity} in the expected file must exist in the generated file. Every non-free-form attribute on each {primary_entity} must be present. Missing → MISSING_CONTENT, HIGH. Extra {primary_entity_plural} → EXTRA_CONTENT, MEDIUM (unless they are structural-support entities documented in the KB).

#### strict_instructions: Strict Instruction Evaluation
**Source:** All KB files
**Risk default:** HIGH
**KB Rule prefix:** "Strict:"

{N} strict/critical directives found across KB files:
{list each directive with source file}

For each: translate into a concrete predicate over the generated file. Evaluate.
- Violation → WRONG_CONTENT, HIGH
- Ambiguous / cannot evaluate mechanically → advisory row at MEDIUM
- Total evaluated + advisory MUST equal {N}

#### pattern_compliance: Pattern Compliance
**Source:** {patterns_kb_file}
**Risk default:** HIGH
**KB Rule prefix:** "Pattern:"

{N} patterns to check:
{for each pattern:}
- **{Pattern Name}**: Required Elements: {list}. Anti-patterns: {list}.

For each pattern whose trigger condition matches the generated file:
(a) ALL Required Elements must be present → Missing = MISSING_CONTENT, HIGH
(b) ALL Anti-patterns scanned → Hit = WRONG_CONTENT, HIGH

#### numbered_constraints: Numbered Constraint Evaluation
**Source:** {constraints_kb_file}
**Risk default:** HIGH
**KB Rule prefix:** "Constraint:"

{N} constraints to evaluate:
{for each constraint:}
- **{ID}**: {rule text}

Evaluate EVERY constraint. On violation: WRONG_CONTENT, HIGH, citing constraint ID and rule text.

#### open_ended: Other KB-Mandated Checks
**Source:** All KB files
**Risk default:** MEDIUM
**KB Rule prefix:** "Other:"

Safety net for any KB rule not covered by the above classes.

{CLIENT-SPECIFIC CHECKS — only those derived from existing KB sections:}

{Paste each check class with its full concrete data}

---

{IF structured mode, add:}

#### verbatim_body_comparison: Body-Bearing Attribute Verbatim Comparison
**Source:** UC-1, UC-4
**Risk default:** HIGH (logic-carrying), MEDIUM (data-carrying)
**KB Rule prefix:** "Body:"

Body-bearing attributes (MUST be extracted verbatim, never summarized):

Logic-carrying (HIGH): {list}
Data-carrying (MEDIUM): {list}

For every body-bearing attribute on every {primary_entity}:
1. Extract the actual string value from BOTH generated and expected files
2. Compare character-for-character (whitespace-only differences excluded)
3. Any character difference → emit row
4. Empty in generated, non-empty in expected → MISSING_CONTENT, HIGH
5. Truncate at 2 KB with `... [truncated, original {N} bytes]` marker

Descriptions forbidden. Always extract actual content.

---

### Step 5 — Plausibility Check

Before writing comparison_sheet.md, verify:
1. Every check class ran (no silent skips)
2. Every numbered constraint ({N} total) was evaluated or recorded as advisory
3. Every strict directive ({N} total) was processed: evaluated + advisory = total
{IF structured mode:}
4. Every body-bearing attribute on every {primary_entity} produced at least one comparison record
5. If gaps found, re-run missing checks before writing

### Step 6 — Print Summary

```
/find-bugs-{client} complete.
  {primary_entity_plural} checked:        {N}
  Attributes/sections checked:   {M}
  Findings by category:
    MISSING_CONTENT  {a}
    WRONG_CONTENT    {b}
    EXTRA_CONTENT    {c}
    FORMATTING       {d}
  Findings by check class:
    {id_1}: {count}
    {id_2}: {count}
    ...
  Constraints evaluated:   {evaluated} of {total} ({advisory} advisory)
  Strict directives:       {evaluated} of {total} ({advisory} advisory)
  Patterns checked:        {N}
  {IF structured:} Body-bearing verbatim comparisons: {total} ({ok} ok / {differ} differ / {empty} empty-in-generated)
  Rows written to comparison_sheet.md: {total}
```

{END OF OUTPUT FILE}
```

### Key assembly rules:

1. **Embed ALL concrete data inline.** The generated skill file must contain actual attribute names, constraint texts, pattern required-elements, default values, exclusion lists — NOT references back to KB files. The skill should be self-contained for the LLM reading it.

2. **Only include check classes for existing KB sections.** If UC-5 doesn't exist, there is no `api_conformance` section.

3. **Only include body-bearing and verbatim rules for the correct mode.** Document mode gets `section_ordering` and `verbatim_section_comparison`, not `verbatim_body_comparison`. Structured mode gets the reverse.

4. **Format-specific sections.** Step 3 (comparison walk) must use the correct approach for the detected mode.

5. **Free-form exclusion list must be complete.** Every excluded field with its reason, directly in the skill file.

6. **Important Rules section reflects the actual configuration.** If there's no archive format, omit the archive rule. If it's document mode, body-bearing rules become verbatim-section rules.

---

## Step 8 — Validate & Print Summary

Before saving the skill file, validate:
1. Every detected KB section produced at least one check class in the output ✓
2. `pattern_compliance` has at least one pattern (if CORE-B exists) ✓
3. `numbered_constraints` has at least one constraint (if CORE-C exists) ✓
4. `strict_instructions` has total_directives > 0 ✓
5. Free-form exclusions list is non-empty ✓
6. Body-bearing attributes list is non-empty (for structured mode) ✓
7. The comparison sheet column contract matches the 13-column format ✓
8. The execution pipeline covers all check classes ✓

Print:
```
Skill generated: .claude/commands/find-bugs-{client}.md

  Platform: {display_name}
  Comparison mode: {mode} ({format})
  Authority file: {name or "none — KB is sole authority"}
  Matching strategy: {method}

  Check classes embedded: {N}
    {id}: {name} (from {section}) — {rule_count} rules
    ...

  Patterns embedded: {N} (from CORE-B)
  Constraints embedded: {N} (from CORE-C)
  Strict directives embedded: {N}

  Free-form exclusions: {N} fields
  Body-bearing attributes: {N} ({logic} logic / {data} data)

  Output skill lines: ~{estimated_lines}

Next steps:
  1. Review the generated skill: .claude/commands/find-bugs-{client}.md
  2. Run: /find-bugs-{client} kb={kb_path} generated=<path> expected=<path>
  3. Review comparison_sheet.md
  4. Run: /process-comparison → /apply-fixes
```

---

## Important Rules

1. **Read every KB file completely.** Partial reads produce incomplete skills. Large files must be read in chunks — no skipping.

2. **Only generate check classes for sections that exist.** Do not invent checks for absent KB sections.

3. **Extract concrete data, not vague descriptions.** The output skill must contain actual attribute names, constraint IDs and rule texts, pattern names and required elements, variable lists, default values — not "validate attributes against the schema." The more specific the embedded data, the more accurate the comparison.

4. **Count everything.** Total constraints, total patterns, total strict directives, total attributes, total entity types. These counts are embedded in the skill for the plausibility check.

5. **Preserve KB wording.** When the KB says "MUST", "NEVER", "ALWAYS" — keep that language in the skill. When it gives examples — embed them.

6. **Free-form vs Fixed is not the same thing.** A field with a REQUIRED value (Fixed) is NOT free-form. Free-form means "any value is acceptable, do not compare."

7. **Body-bearing classification matters for risk.** Script/expression = logic-carrying (HIGH). Payload/header/column = data-carrying (MEDIUM).

8. **The output skill must be self-contained.** An LLM reading the generated `find-bugs-{client}.md` should need NOTHING beyond: (a) the skill itself, (b) KB files at the documented path, (c) the generated file, (d) the expected file. No CLAUDE.md, no codebase access, no File Index.

9. **Format-appropriate checks only.** Don't generate structured-mode checks (body-bearing verbatim, key-by-key walk) for document-mode clients. Don't generate document-mode checks (section ordering, ToC validation, visual fidelity) for structured-mode clients.

10. **Downstream compatibility.** The generated skill MUST output the exact 13-column `comparison_sheet.md` format that `/process-comparison` expects. No extra columns, no missing columns, no format changes.
