---
description: Read a client's KB (from /platform-kb) and generate a complete standalone find-bugs-{client}.md skill — all checks, rules, and execution logic baked in, KB as sole source of truth.
---

You are a skill-generation agent. Given a client's Knowledge Base directory (produced by `/platform-kb`), produce a **complete, standalone** `find-bugs-{client}.md` command file that can compare generated vs expected files for this client and surface every genuine discrepancy to `comparison_sheet.md`.

**User-provided context:** $ARGUMENTS

---

## Step 1 — Parse Arguments & Read KB

Parse `$ARGUMENTS` for:
- `client=<name>` — REQUIRED. Client identifier (lowercase, no spaces). Used for skill filename.
- `kb=<path>` — REQUIRED. Path to the KB directory (e.g., `outputs/{client}/kb/`).

If either is missing, print usage and STOP.

List all `.md` files in the KB directory. Read EVERY file completely — no skipping, no partial reads. For large files, read in chunks until fully consumed.

---

## Step 2 — Classify KB Sections

Classify each KB file by matching filename patterns AND reading H1/H2 headings:

| File Pattern | Section ID | Content Type |
|---|---|---|
| `00-overview*` | `CORE-A` | Domain context, glossary, architecture |
| `*building-block*` or `*component*` | `UC-1` | Entity/component types, property definitions, behavioral triggers |
| `*composition*` or `*wiring*` or `*connection*` | `UC-2` | Relationships, references, dependencies, hierarchy |
| `*artifact-schema*` or `*output-schema*` or `*document-structure*` | `UC-3` | Top-level structure, field/section classification |
| `*variable*` or `*data-flow*` or `*scripting*` | `UC-4` | Variables, expressions, data flow |
| `*api-reference*` or `*endpoint*` | `UC-5` | API endpoints, parameters, schemas |
| `*auth*` | `UC-6` | Authentication methods |
| `*data-model*` or `*entit*` or `*master*` | `UC-7` | Entities, relationships, master data |
| `*event*` or `*webhook*` | `UC-8` | Event catalog, payload schemas |
| `*config*` | `UC-9` | Configuration hierarchy |
| `*layout*` or `*visual*` or `*coordinate*` | `UC-10` | Visual/coordinate rules |
| `*pattern*` | `CORE-B` | Named patterns, required elements, anti-patterns |
| `*constraint*` | `CORE-C` | Numbered rules (C1, C2...) |
| `*input-checklist*` | `CORE-D` | Per-instance fields, tier classification |
| `*gap*` | `CORE-E` | Known gaps, assumptions |
| `*catalog*` or `*capability*` or `*module*` | `DOMAIN-CATALOG` | Feature/module catalogs |

Files that don't match → classify as `CUSTOM` and note their H1 heading. Only generate check classes for sections that actually exist.

---

## Step 3 — Extract Platform Metadata

From CORE-A (overview), extract:

- **Platform name** and **use-case classification** (`component-flow`, `api-sdk`, `artifact-generator`, `event-driven`, `data-platform`, `config-system`)
- **Primary file format** → determines comparison mode: `structured` (JSON/YAML/XML), `document` (PDF/DOCX/MD/HTML), `tabular` (XLSX/CSV)
- **Domain vocabulary**: `primary_entity`, `entity_plural`, `discriminator_field`, `container_path`
- **Authority file** (if any): a config/mapping/schema file referenced as "source of truth"
- **Archive formats** (if any): custom extensions wrapping standard formats
- **Entity matching strategy**: Match entities by their **discriminator field** (type/kind/alias — the field that classifies what an entity IS). NEVER use auto-generated UUIDs or cosmetic display names as matching keys. Matching rules:
  - **Unique discriminator**: if both files have exactly one entity of a type → direct match
  - **Duplicate discriminator**: if both files have multiple entities of the same type → match by graph position (predecessors/successors in the relationship/transition graph)
  - **MISSING**: only when generated has zero entities of a discriminator value that expected has — not when names differ
  - **EXTRA**: only when generated has entities of a type not present anywhere in expected
  - Display names, labels, cosmetic identifiers → excluded from matching and comparison

---

## Step 4 — Derive Check Classes

For each detected KB section, derive check classes. Extract CONCRETE data — specific field names, constraint IDs, pattern names, property lists. Never produce vague descriptions.

### Universal checks (always included)

- **`structural_completeness`**: Every entity in expected must exist in generated (matched by discriminator field per Step 3). Every non-free-form property must be present.
- **`strict_instructions`**: Scan ALL KB files for STRICT/CRITICAL/MUST/NEVER/ALWAYS directives. Extract exact text, translate each into a concrete predicate.
- **`pattern_compliance`** (if CORE-B exists): Extract every named pattern with its required elements, anti-patterns, and content placement rules.
- **`numbered_constraints`** (if CORE-C exists): Extract every constraint with FULL rule text verbatim.
- **`open_ended`**: Safety net for any KB rule not covered by named classes.

### Per-section checks (only for sections that exist)

| KB Section | Check Class | What to Extract |
|---|---|---|
| UC-1 | `property_validation` | Per-entity-type property registry: name, type, required, default, allowed values, fixed values. Extract whatever format the KB uses (tables, lists, nested). Must include: (1) **numeric attribute strict comparison** — attributes with numeric values (timeouts, counts, limits, thresholds) always compare generated vs expected values, never treat as free-form (exclude: auto-generated IDs, timestamps, sequence numbers, coordinates/positions), (2) **default value validation** — for every matched entity, compare each property's value against the KB-documented default for that entity type; if the value differs from expected AND violates a KB default/constraint → WRONG_CONTENT with KB rule citation. |
| UC-1 | `behavior_validation` | **Only if KB documents behavioral triggers/events.** Per-entity-type behavior catalog: name, trigger, outcomes, required handling. |
| UC-2 | `relationship_validation` | Relationship mechanism, schema, cardinality (scalar vs array), conditional rules, reference integrity, parent-child rules. Derive numbered structural predicates. Must include **transition multiplicity**: if an outcome/event has >1 outgoing transition from an entity, ALL transitions on that outcome MUST be conditional — one unconditional + any conditional from the same outcome = INVALID. |
| UC-3 | `schema_conformance` | Top-level required structure, field/section classification, fixed fields with exact values. |
| UC-4 | `variable_validation` | **Only if UC-4 exists.** Variable declaration mechanism, built-in variables, binding patterns, naming/uniqueness rules. Must include: (1) every variable referenced in expressions must exist in declared or built-in list, (2) **cross-scope name collision** — if two entities declare variables with the same name in different scopes, flag unless it's a platform/global variable (exclude: stable identifiers, auto-generated IDs, display names), (3) **variable-to-attribute cross-reference** — if a variable holds a value that is assigned to an attribute on another entity, the stored value must match the assigned value, (4) **variant-specific initialization** — if the flow branches by a discriminator (language, region, tier), each branch must initialize its variant-specific variables (exclude: shared/global variables that don't vary per branch). |
| UC-4 | `code_validation` | **Only if UC-4 documents coding conventions.** Extract whatever conventions the KB documents: preamble, wrappers, prohibited constructs, expression syntax rules. |
| UC-5 | `api_conformance` | API endpoints, parameters, schemas. |
| UC-7 | `entity_integrity` | Entity relationships, lifecycle, master data rules. |
| UC-8 | `event_system_validation` | Event catalog, payload schemas. |
| UC-9 | `config_validation` | Configuration hierarchy, option rules. |
| UC-10 | `layout_validation` | Visual/coordinate rules. |
| CORE-D | `content_accuracy` | **Document mode only.** Tier 1/2/3 field classification. |
| DOMAIN-CATALOG | `catalog_completeness` | Module/feature catalog with required vs optional items. |

### Cross-entity checks (structured mode)

- **`cross_entity_consistency`**: Variable uniqueness across scopes (if UC-4), cross-reference consistency (values in one entity must match related entity), duplicate content detection (>80% similar body-bearing fields), dependency completeness (entity type X requires companion entity type Y). Must include **cross-entity code duplication**: if >80% similar body-bearing content (scripts, expressions, logic blocks) appears across different entities' fields, flag as likely copy-paste error. Exclude: boilerplate that KB documents as intentionally repeated (standard initialization, platform-required wrappers).
- **`content_placement_validation`** (if UC-1 + CORE-B document placement rules): Validates that content appears in the correct field on the correct entity type. Must include **logic-to-entity-type enforcement**: if KB defines that specific logic (tracking, cleanup, initialization) belongs on specific entity types or specific fields of those entities, enforce that — logic appearing on the wrong entity type, even in a valid body-bearing field, is WRONG_CONTENT. Exclude: shared utility logic that KB allows on any entity.
- **`empty_body_detection`** (if body-bearing fields exist): If ≥50% of body-bearing fields are empty in generated but populated in expected, flag systematic omission.
- **`source_compliance`** (if `source=` argument provided): Compare generated against the source requirements document. Must include: (1) **entity coverage** — every requirement in source → at least one entity in generated; every entity in generated → traceable to a source requirement; unmatched generated entities → EXTRA_CONTENT, (2) **requirement fulfillment** — each stated requirement must be implemented as described, not reinterpreted; if source says "dump inputs" and generated dumps names → WRONG_CONTENT, (3) **no hallucinated features** — entities, properties, or logic in generated that have no backing in the source document → EXTRA_CONTENT. Exclude: infrastructure/boilerplate entities that KB documents as always required regardless of source.

### Extraction rules

For every check class:
1. Extract CONCRETE data from the KB — actual field names, constraint texts, pattern elements, default values
2. The generated skill must be self-contained: embed all rules inline, not references back to KB files
3. Preserve KB wording — keep "MUST", "NEVER", "ALWAYS" language
4. Count everything (constraints, patterns, directives, properties, entity types) for the plausibility check

---

## Step 5 — Free-Form Exclusions

A field is free-form (NEVER flagged for value differences) if any of:
- UC-3 classifies it as `Identity` (UUIDs, auto-incremented IDs)
- UC-1 marks it as auto-generated or runtime-created
- It's the entity display name field (cosmetic — identity determined by discriminator field)
- Timestamps, actor fields, auto-generated IDs, UI/layout metadata, user-authored free text
- Coordinates, positions, sequence numbers (layout/ordering metadata)
- KB explicitly says "do not compare" / "varies per build" / "cosmetic"

**Critical:** Auto-generated instance IDs (UUIDs, sequence IDs) are ALWAYS free-form — never used as matching keys, never compared for value differences. Entity display names and labels are cosmetic — never used for matching, never flagged for differences.

Free-form fields must also be excluded from: cross-scope name collision checks, numeric strict comparison, and duplication detection. Only non-free-form, non-identity fields participate in these checks.

The generated skill must embed the COMPLETE exclusion list with reasons. Incomplete exclusions = false positives.

---

## Step 6 — Body-Bearing Fields (Structured Mode Only)

A field is body-bearing (must be extracted verbatim, never summarized) if UC-1 or UC-4 indicate it holds executable content, expressions, queries, templates, payloads, or structured data. Classify as `logic_carrying` (code, expressions, conditions) or `data_carrying` (payloads, headers, templates). The KB's property definitions are the primary source for identifying these.

---

## Step 7 — Assemble the Skill File

Write the complete skill at `.claude/commands/find-bugs-{client}.md`. The output must be a COMPLETE, SELF-CONTAINED prompt. The executing LLM needs NOTHING beyond this skill file, the KB files, and the two comparison files.

The generated skill file must contain these sections:

1. **Header**: description, comparison mode, file format, `$ARGUMENTS` — must accept `generated=<path>`, `expected=<path>`, `kb=<path>` (all required), and `source=<path>` (optional). The generated skill must parse `kb=` and read all KB `.md` files at runtime for supplementary context.
2. **Comparison sheet format**: embed the full 13-column `comparison_sheet.md` schema below into the generated skill so it knows where to write findings and in what format.
3. **Important rules**: KB-only knowledge source, all check classes must run, every row cites KB source, free-form fields never flagged, entity matching by discriminator field (never UUIDs or display names), body-bearing fields extracted verbatim, grouping repeated issues. KB files from `kb=` provide supplementary context — baked-in check classes are the primary validation, KB files help resolve ambiguities and provide evidence for KB Rule Violated citations.
4. **Execution pipeline**: parse arguments → read all KB `.md` files from `kb=` path for runtime context → format-specific comparison walk → run all check classes (baked-in rules + KB context) → deduplicate/group → plausibility check → write comparison_sheet.md → print summary
5. **Check classes**: every check class derived in Step 4, with all concrete extracted data embedded inline
6. **Free-form exclusion list**: complete list from Step 5
7. **Body-bearing field list**: complete list from Step 6 (structured mode)

### Comparison Sheet Schema (embed in every generated skill)

**Creation rule:** If `comparison_sheet.md` does not exist, create it with the header row below, then append all findings as data rows. If it already exists, append rows — never overwrite existing content.

**Table header:**

| Comp ID | Reported | Category | Location (Generated) | Location (Expected) | Expected Content | Actual Content | KB Rule Violated | Risk | Source File | Should Fix | Reviewed By | Linked Bug ID |
|---------|----------|----------|---------------------|---------------------|-----------------|----------------|-----------------|------|-------------|------------|-------------|---------------|

**Column contract:**

| Column | Format | Notes |
|---|---|---|
| Comp ID | `COMP-YYYY-MM-DD-NNN` | Sequential per day, incrementing NNN |
| Reported | `YYYY-MM-DD` | Date the finding was recorded |
| Category | enum | `MISSING_CONTENT` / `WRONG_CONTENT` / `EXTRA_CONTENT` / `FORMATTING` |
| Location (Generated) | keypath or section ref | Full keypath (structured) or section+paragraph (document). For grouped issues: comma-separated list with `({N} total)` |
| Location (Expected) | keypath or section ref | Corresponding location in expected file, or KB source if no counterpart. For grouped: `all {N} instances` |
| Expected Content | literal value | Verbatim expected value, truncate to ~100 chars. For grouped: common value or `varies — see locations` |
| Actual Content | literal value | Verbatim generated value; `_(missing)_` if absent. For grouped: `{N} entities have {value} instead of {expected}` |
| KB Rule Violated | text | **Mandatory.** One-line message prefixed with check class. Must cite KB source (file:section, constraint ID, pattern name). Never empty. |
| Risk | enum | `HIGH` / `MEDIUM` / `LOW` |
| Source File | path or empty | Source document that produced the generated output (from `source=` arg); empty if not provided |
| Should Fix | enum | Always `PENDING_REVIEW` when first written |
| Reviewed By | text | `_pending_` when first written |
| Linked Bug ID | text | Empty when first written (filled by `/process-comparison`) |

**Grouping rules:** When the SAME issue affects MULTIPLE entities (same check class, same KB rule, same category, same expected value or same type of deviation), merge into ONE row with multi-location format. Use the HIGHEST risk among grouped instances.

**Empty-result handling:** If zero discrepancies found, write the header + a single confirmation row with Comp ID `COMP-...-000`, Category `WRONG_CONTENT`, KB Rule Violated `No discrepancies found across {N} entities / {M} properties; all {K} check classes ran to completion`, Risk `LOW`.

### Assembly rules

- Only include check classes for existing KB sections
- Format-appropriate checks only (don't generate structured-mode checks for document-mode clients)
- The comparison sheet format above must be embedded verbatim in the generated skill
- Entity matching must use the discriminator field from Step 3, never UUIDs or display names. The structural_completeness check must use discriminator-based matching.
- Entity matching rule must appear in: important rules, comparison walk, structural_completeness check, free-form exclusion list

---

## Step 8 — Validate

Before saving, verify:
1. Every detected KB section produced at least one check class ✓
2. Free-form exclusions list is non-empty and includes display name field ✓
3. Body-bearing fields list is non-empty (structured mode) ✓
4. Comparison sheet matches 13-column format ✓
5. Cross-entity checks present (structured mode) ✓
6. All conditional checks properly guarded (variable_validation only if UC-4, behavior_validation only if behaviors documented, etc.) ✓

Print summary: platform name, comparison mode, check classes embedded (count + names), patterns/constraints/directives counts, free-form exclusions count, body-bearing fields count.

---

## Important Rules

1. **Read every KB file completely.** Partial reads produce incomplete skills.
2. **Only generate check classes for sections that exist.** Do not invent checks for absent KB sections.
3. **Extract concrete data, not vague descriptions.** Actual field names, constraint texts, pattern elements, default values — not "validate properties against the schema."
4. **The output skill must be self-contained.** No CLAUDE.md, no codebase access, no File Index. Only KB files + comparison files.
5. **No client-specific keywords in the generator.** All domain vocabulary comes from the KB at runtime. The generator stays generic.
6. **Exhaustive free-form exclusions prevent false positives.** When in doubt, EXCLUDE.
7. **Downstream compatibility.** The generated skill MUST output the exact 13-column `comparison_sheet.md` format that `/process-comparison` expects.
