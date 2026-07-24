---
name: find-bugs
description: Compare a GENERATED artifact against the EXPECTED one for a platform whose Knowledge Base (KB) documents what "correct" means, and record every genuine discrepancy as a row in that client's comparison sheet under `outputs/<client>/comparisons/`. The KB is the sole authority: entity types, properties, defaults, relationships, variables, patterns, numbered constraints, and every STRICT/MUST/NEVER directive are read from it at run time, so a KB that gained a rule yesterday is checked against today. Works on structured artifacts (JSON/YAML/XML/NodeFlow), documents (PDF/DOCX/MD/HTML), and tabular files, detecting the mode from the KB. Matches entities by their discriminator field, never by UUIDs or display names, and never flags free-form fields. Optionally checks the generated artifact against the source requirements document that produced it. Use when an operator has a generated artifact and a known-good counterpart and wants the differences that actually matter. Inputs: kb=<dir>, generated=<path>, expected=<path> (all required), source=<path>, comparison=<name>, output=<dir>. Triggers: "find the bugs in this generated file", "compare generated vs expected for {client}", "find-bugs", "check this output against the KB".
---

# find-bugs

Compare a **generated** artifact against the **expected** one, judged by what the **KB** says correct looks like, and write the genuine discrepancies to that client's comparison sheet.

```
   KB        (what this platform's artifacts must look like) ─┐
   generated (what was produced)                              ├─► compare ─► outputs/<client>/comparisons/<name>.md
   expected  (the known-good counterpart)                    ─┘
```

The skill is a **generic engine**. It knows nothing about any platform and hardcodes no domain vocabulary — no entity type, no property name, no constraint. It learns the platform entirely from the KB at run time. Point it at a different KB and it checks a different platform, with no change to the skill.

**Why it reads the KB every run rather than being compiled per client.** A checker whose rules were frozen at compile time keeps reporting *"no discrepancies found; all check classes ran to completion"* long after the KB gained constraints it has never heard of. That is worse than no checker: it reports clean, with authority, on artifacts nobody has actually validated. Reading the KB live costs a few file reads and removes the entire failure mode.

## Inputs

| Input | Meaning | Required |
|---|---|---|
| `kb=<dir>` | The platform KB (e.g. `outputs/<client>/kb/`). The sole authority on what correct means. | **Yes** |
| `generated=<path>` | The artifact under test. | **Yes** |
| `expected=<path>` | The known-good counterpart. | **Yes** |
| `source=<path>` | The requirements document (SOW/brief) the generated artifact was produced from. Activates `source_compliance`. | No |
| `comparison=<name>` | Sheet name. Defaults to the `generated=` file's basename. | No |
| `output=<dir>` | Where the sheet is written. **Default fallback: `outputs/<client>/comparisons/`**, where `<client>` is the parent of `kb`. | No |

A client accumulates many comparison sheets in that folder — one per run — so `process-comparison` can pick them up together.

## Core principles

1. **The KB is the only source of knowledge.** Every rule you check comes from it. No CLAUDE.md, no codebase access, no general knowledge about what the platform "usually" does. If the KB does not say a thing is required, it is not a finding.
2. **Read every KB file completely.** Partial reads produce a checker that silently skips whole classes of defect. For large files, read in chunks until fully consumed.
3. **Only check what exists.** Derive check classes for the KB sections this client actually has. Never invent a check for an absent section — a `variable_validation` run against a KB that documents no variables produces nothing but noise.
4. **Concrete, never vague.** Extract actual field names, constraint texts, pattern elements, default values. "Validate properties against the schema" is not a check; "`timeoutMs` on `waitNode` must be 5000 per constraint C7" is.
5. **Every row cites its KB source.** A finding whose `KB Rule Violated` cell is empty, or says something the KB does not, is a false positive by construction.
6. **When in doubt, exclude.** A false positive costs a reviewer's trust in every other row on the sheet. Exhaustive exclusions are what make the sheet worth reading.

---

## PHASE 1 — Learn the platform from the KB

Read every `.md` file in `kb` completely, then classify what you found. Match on filename patterns *and* on the H1/H2 headings inside — filenames vary between clients, headings are more reliable.

| File pattern | Section | Content |
|---|---|---|
| `00-overview*` | `CORE-A` | Domain context, glossary, architecture |
| `*building-block*`, `*component*` | `UC-1` | Entity/component types, property definitions, behavioral triggers |
| `*composition*`, `*wiring*`, `*connection*` | `UC-2` | Relationships, references, dependencies, hierarchy |
| `*artifact-schema*`, `*output-schema*`, `*document-structure*` | `UC-3` | Top-level structure, field/section classification |
| `*variable*`, `*data-flow*`, `*scripting*` | `UC-4` | Variables, expressions, data flow |
| `*api-reference*`, `*endpoint*` | `UC-5` | API endpoints, parameters, schemas |
| `*auth*` | `UC-6` | Authentication methods |
| `*data-model*`, `*entit*`, `*master*` | `UC-7` | Entities, relationships, master data |
| `*event*`, `*webhook*` | `UC-8` | Event catalog, payload schemas |
| `*config*` | `UC-9` | Configuration hierarchy |
| `*layout*`, `*visual*`, `*coordinate*` | `UC-10` | Visual/coordinate rules |
| `*pattern*` | `CORE-B` | Named patterns, required elements, anti-patterns |
| `*constraint*` | `CORE-C` | Numbered rules |
| `*input-checklist*` | `CORE-D` | Per-instance fields, tier classification |
| `*gap*` | `CORE-E` | Known gaps, assumptions |
| `*catalog*`, `*capability*`, `*module*` | `DOMAIN-CATALOG` | Feature/module catalogs |

Anything unmatched is `CUSTOM` — note its H1 and treat its rules as `open_ended` material.

### Platform metadata

From `CORE-A`, establish:

- **Platform name** and **use-case class** (`component-flow`, `api-sdk`, `artifact-generator`, `event-driven`, `data-platform`, `config-system`)
- **Primary file format** → the comparison mode: `structured` (JSON/YAML/XML), `document` (PDF/DOCX/MD/HTML), `tabular` (XLSX/CSV)
- **Domain vocabulary**: `primary_entity`, `entity_plural`, `discriminator_field`, `container_path`
- **Authority file**, if the KB names a config/mapping/schema as its source of truth
- **Archive formats**, if custom extensions wrap standard ones

### Entity matching strategy

Match entities by their **discriminator field** — the field that classifies what an entity *is* (type / kind / alias). Never by auto-generated UUIDs, never by cosmetic display names.

- **Unique discriminator** — both files have exactly one entity of that type → direct match.
- **Duplicate discriminator** — both have several of the same type → match by graph position (predecessors/successors in the relationship or transition graph).
- **MISSING** — only when generated has *zero* entities of a discriminator value that expected has. Not when names differ.
- **EXTRA** — only when generated has entities of a type absent from expected entirely.
- Display names, labels, and cosmetic identifiers are excluded from matching and from comparison.

If the KB does not state the discriminator field outright, infer it and **say which field you chose and why** in the run summary — it is the single most load-bearing decision in the comparison, and a wrong choice turns every entity into a false MISSING/EXTRA pair.

---

## PHASE 2 — Derive the check classes

For each section the KB actually has, derive checks with concrete extracted data.

### Universal — always run

- **`structural_completeness`** — every entity in expected exists in generated, matched by discriminator. Every non-free-form property is present.
- **`strict_instructions`** — scan **all** KB files for STRICT / CRITICAL / MUST / NEVER / ALWAYS directives. Extract the exact text and turn each into a concrete predicate.
- **`pattern_compliance`** *(if CORE-B)* — every named pattern with its required elements, anti-patterns, and content-placement rules.
- **`numbered_constraints`** *(if CORE-C)* — every constraint, with full rule text verbatim.
- **`open_ended`** — the safety net for any KB rule no named class covers.

### Per-section — only where the section exists

| Section | Check class | What to extract |
|---|---|---|
| UC-1 | `property_validation` | Per-entity-type property registry: name, type, required, default, allowed values, fixed values. Must include **(1) numeric strict comparison** — numeric attributes (timeouts, counts, limits, thresholds) always compare generated vs expected, never treated as free-form (excluding auto-generated IDs, timestamps, sequence numbers, coordinates); **(2) default validation** — compare each property against the KB-documented default for that entity type; a value that differs from expected *and* violates a KB default/constraint is `WRONG_CONTENT` with the rule cited. |
| UC-1 | `behavior_validation` | *Only if the KB documents behavioral triggers/events.* Per-entity-type behaviour catalog: name, trigger, outcomes, required handling. |
| UC-2 | `relationship_validation` | Mechanism, schema, cardinality (scalar vs array), conditional rules, reference integrity, parent-child rules. Must include **transition multiplicity**: if an outcome has more than one outgoing transition from an entity, *all* of them must be conditional — one unconditional plus any conditional from the same outcome is invalid. |
| UC-3 | `schema_conformance` | Top-level required structure, field/section classification, fixed fields with exact values. |
| UC-4 | `variable_validation` | Declaration mechanism, built-ins, binding patterns, naming/uniqueness. Must include **(1)** every variable referenced in an expression exists in the declared or built-in list; **(2) cross-scope collision** — two entities declaring the same variable name in different scopes is flagged unless it is a platform/global (excluding stable identifiers, auto-generated IDs, display names); **(3) variable-to-attribute cross-reference** — where a variable's value is assigned to an attribute on another entity, the stored value must match; **(4) variant-specific initialisation** — where the flow branches on a discriminator (language, region, tier), each branch initialises its variant-specific variables (excluding shared globals). |
| UC-4 | `code_validation` | *Only if the KB documents coding conventions.* Preamble, wrappers, prohibited constructs, expression syntax. |
| UC-5 | `api_conformance` | Endpoints, parameters, schemas. |
| UC-7 | `entity_integrity` | Entity relationships, lifecycle, master-data rules. |
| UC-8 | `event_system_validation` | Event catalog, payload schemas. |
| UC-9 | `config_validation` | Configuration hierarchy, option rules. |
| UC-10 | `layout_validation` | Visual/coordinate rules. |
| CORE-D | `content_accuracy` | *Document mode only.* Tier 1/2/3 field classification. |
| DOMAIN-CATALOG | `catalog_completeness` | Module/feature catalog, required vs optional. |

### Cross-entity — structured mode

- **`cross_entity_consistency`** — variable uniqueness across scopes (if UC-4), cross-reference consistency, duplicate-content detection, dependency completeness (type X requires companion type Y). Must include **cross-entity code duplication**: content over ~80% similar appearing across different entities' body-bearing fields is flagged as likely copy-paste. Exclude boilerplate the KB documents as intentionally repeated.
- **`content_placement_validation`** *(if UC-1 + CORE-B document placement)* — content appears in the correct field on the correct entity type. Must include **logic-to-entity-type enforcement**: where the KB assigns specific logic (tracking, cleanup, initialisation) to specific entity types or fields, logic on the wrong entity type is `WRONG_CONTENT` even in an otherwise valid body-bearing field. Exclude shared utility logic the KB permits anywhere.
- **`empty_body_detection`** — if ≥50% of body-bearing fields are empty in generated but populated in expected, flag systematic omission.
- **`source_compliance`** *(only with `source=`)* — **(1) entity coverage**: every requirement maps to at least one entity, every entity traces back to a requirement, untraceable entities are `EXTRA_CONTENT`; **(2) requirement fulfilment**: each requirement implemented as described, not reinterpreted — if the source says "dump inputs" and the artifact dumps names, that is `WRONG_CONTENT`; **(3) no hallucinated features**: entities, properties, or logic with no backing in the source are `EXTRA_CONTENT`. Exclude infrastructure the KB documents as always required.

---

## PHASE 3 — Establish the exclusions

Get this wrong and the sheet fills with noise nobody trusts.

### Free-form fields — never flagged for value differences

A field is free-form if any of these hold:

- UC-3 classifies it as identity (UUIDs, auto-incremented IDs)
- UC-1 marks it auto-generated or runtime-created
- it is the entity display-name field (cosmetic — identity comes from the discriminator)
- it is a timestamp, actor field, auto-generated ID, UI/layout metadata, or user-authored free text
- it is a coordinate, position, or sequence number
- the KB says "do not compare", "varies per build", or "cosmetic"

**Auto-generated instance IDs are always free-form** — never a matching key, never compared. Display names and labels are cosmetic — never a matching key, never flagged.

Free-form fields are also excluded from cross-scope collision checks, numeric strict comparison, and duplication detection. Only non-free-form, non-identity fields take part in those.

### Body-bearing fields — structured mode

A field is body-bearing if UC-1 or UC-4 indicate it holds executable content, expressions, queries, templates, payloads, or structured data. Classify each as `logic_carrying` (code, expressions, conditions) or `data_carrying` (payloads, headers, templates). The KB's property definitions are the primary source. **Body-bearing content is extracted verbatim, never summarised** — a summarised diff hides the defect.

---

## PHASE 4 — Compare

Walk the two artifacts in the mode the KB implies — structured (keypath walk), document (section/paragraph walk), or tabular (row/column walk) — matching entities by discriminator. Run every derived check class. Then:

- **Deduplicate and group.** When the same issue affects multiple entities — same check class, same KB rule, same category, same expected value or same kind of deviation — merge into **one** row with the multi-location format, carrying the **highest** risk among the grouped instances. A sheet with forty rows of one underlying defect gets abandoned.
- **Plausibility check.** Compare your finding count against what you extracted: entity types, constraints, patterns, directives, properties. Zero findings on an artifact with hundreds of properties is a claim that needs to survive a second look, not a result to ship.

## PHASE 5 — Self-check before writing

1. Every KB section detected produced at least one check class.
2. The free-form exclusion list is non-empty and includes the display-name field.
3. The body-bearing field list is non-empty (structured mode).
4. Cross-entity checks ran (structured mode).
5. Conditional checks were properly guarded — `variable_validation` only where UC-4 exists, `behavior_validation` only where behaviours are documented, and so on.
6. Every row cites a KB source.

Anything that fails here is reported, not quietly dropped.

## PHASE 6 — Write the sheet and report

Write to `outputs/<client>/comparisons/<name>.md` (or `output=`), where `<name>` is `comparison=` or the `generated=` basename. **Create the sheet and its directory if absent**, with the header row below; **if it already exists, append — never overwrite.**

Then print: platform name, comparison mode, discriminator field chosen, check classes run (count + names), constraint/pattern/directive counts, exclusion count, body-bearing field count, findings by risk, and the sheet path.

### Comparison sheet schema

| Comp ID | Reported | Category | Location (Generated) | Location (Expected) | Expected Content | Actual Content | KB Rule Violated | Risk | Source File | Should Fix | Reviewed By | Linked Bug ID |
|---------|----------|----------|---------------------|---------------------|-----------------|----------------|-----------------|------|-------------|------------|-------------|---------------|

| Column | Format | Notes |
|---|---|---|
| Comp ID | `COMP-YYYY-MM-DD-NNN` | Sequential per day |
| Reported | `YYYY-MM-DD` | Date recorded |
| Category | enum | `MISSING_CONTENT` / `WRONG_CONTENT` / `EXTRA_CONTENT` / `FORMATTING` |
| Location (Generated) | keypath or section ref | Full keypath (structured) or section+paragraph (document). Grouped: comma-separated with `({N} total)` |
| Location (Expected) | keypath or section ref | Counterpart location, or the KB source where there is none. Grouped: `all {N} instances` |
| Expected Content | literal | Verbatim, truncated to ~100 chars. Grouped: common value or `varies — see locations` |
| Actual Content | literal | Verbatim; `_(missing)_` if absent. Grouped: `{N} entities have {value} instead of {expected}` |
| KB Rule Violated | text | **Mandatory.** Prefixed with the check class, citing a KB source (file:section, constraint ID, pattern name). Never empty. |
| Risk | enum | `HIGH` / `MEDIUM` / `LOW` |
| Source File | path or empty | From `source=`; empty if not given |
| Should Fix | enum | Always `PENDING_REVIEW` on first write |
| Reviewed By | text | `_pending_` on first write |
| Linked Bug ID | text | Empty on first write — `process-comparison` fills it |

**Empty result.** Zero discrepancies still writes a sheet: header plus one confirmation row with Comp ID `COMP-...-000`, Category `WRONG_CONTENT`, Risk `LOW`, and a `KB Rule Violated` reading `No discrepancies found across {N} entities / {M} properties; all {K} check classes ran to completion`. State the real counts — that sentence is the evidence the run actually happened.

This 13-column format is a contract with `process-comparison`, which reads every sheet under `outputs/<client>/comparisons/`. Do not add, drop, or reorder columns.

---

## Never do this

- Never check a rule that is not in the KB, and never skip one that is because it looks unimportant.
- Never match entities by UUID or display name. Never flag a free-form field for a value difference.
- Never summarise body-bearing content — extract it verbatim or the diff hides the defect.
- Never invent check classes for KB sections this client does not have.
- Never write a row with an empty `KB Rule Violated`, and never cite a rule the KB does not contain.
- Never emit forty rows for one underlying defect; group them.
- Never overwrite an existing comparison sheet — append.
- Never report zero findings without the plausibility check and the stated counts behind it.

## Folder layout

```
.claude/skills/find-bugs/
└── SKILL.md              ← this file

outputs/<client>/
├── kb/                   ← the KB (input — produced and maintained by kb-builder)
├── comparisons/          ← sheets are written/appended here, one per run
└── approval_sheet.md     ← downstream, written by process-comparison
```
