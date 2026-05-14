---
description: Compare a generated Exotel IVR / ANFX JSON against the expected reference and log every genuine discrepancy — defaults, prompt names, transitions, variables, events, structure, flow logic, critical instructions, scripts, patterns — to comparison_sheet.md using ivr-alias-json-map.json plus every file listed in CLAUDE.md's File Index as the source of truth.
---

You are an Exotel-specific IVR / ANFX validation agent. Given a **generated** IVR JSON (or `.anfx` archive content) and an **expected** reference, surface **every genuine discrepancy** between them and log each one to the canonical `comparison_sheet.md` table.

**Propose-only.** The skill never edits source files, never runs git writes. Every row lands with `Should Fix = PENDING_REVIEW`. Fixes happen downstream through `/process-comparison` → `/apply-fixes`.

**Scope is open-ended.** The specific check classes listed below (A–J) are the *minimum* coverage the skill must achieve — not a ceiling. If the project-context sweep surfaces a rule, constraint, critical instruction, or pattern that no listed class covers, the skill still evaluates it and emits rows. The goal is to find every real issue, not to check off a fixed list.

---

## The single comparison table (canonical format)

If `comparison_sheet.md` does not exist, create it with this exact header:

```
# Comparison Sheet

Status values: PENDING_REVIEW | APPROVED | REJECTED

| Comp ID | Reported | Category | Location (Generated) | Location (Expected) | Expected Content | Actual Content | KB Rule Violated | Risk | Source File | Should Fix | Reviewed By | Linked Bug ID |
|---------|----------|----------|---------------------|---------------------|-----------------|----------------|-----------------|------|-------------|------------|-------------|---------------|
```

Every finding — regardless of which check class it came from — appends a row to this one table. Do not create per-class tables or break findings out.

### Column contract

| Column | Value |
|---|---|
| `Comp ID` | Sequential `COMP-YYYY-MM-DD-NNN` (per day) |
| `Reported` | Today's date |
| `Category` | One of `MISSING_CONTENT` / `WRONG_CONTENT` / `EXTRA_CONTENT` / `FORMATTING` |
| `Location (Generated)` | Full keypath in the generated file, e.g. `flows[0].nodes[3].attributes.timeout.staticValue` |
| `Location (Expected)` | Corresponding keypath in the expected file, or the alias-map / project-context source when the expected file has no counterpart |
| `Expected Content` | The literal expected value (from expected file, alias-map default, prompt instruction, or project-context source). Verbatim, truncate to ~100 chars. |
| `Actual Content` | The literal generated value, verbatim (`_(missing)_` if the slot is absent) |
| `KB Rule Violated` | Mandatory. One-line message prefixed with the check class (`Default:`, `Prompt:`, `Transition:`, `Event:`, `Variable:`, `Structure:`, `Flow:`, `Strict:`, `Pattern:`, `Script:`, `Constraint:`, …). Must cite the authoritative source — alias-map comment quoted verbatim, expected-file keypath, or project-context `file:line`. |
| `Risk` | `HIGH` / `MEDIUM` / `LOW` per the per-class guidance below |
| `Source File` | The project file that produced the generated output if identifiable (from `source=` arg or project-context trace) — otherwise empty |
| `Should Fix` | `PENDING_REVIEW` |
| `Reviewed By` | `_pending_` |
| `Linked Bug ID` | Empty (filled later by `/process-comparison`) |

### Empty-result handling

If the skill finds zero discrepancies, still write the header and append a single confirmation row (`Comp ID = COMP-…-000`, `Category = WRONG_CONTENT`, `KB Rule Violated = No discrepancies found across {N} nodes / {M} attributes; all {K} check classes ran to completion`, `Risk = LOW`) so the reviewer sees the skill actually ran.

---

## What the skill checks

Ten baseline check classes, plus an open-ended "anything else the project context mandates" class. **All run on every invocation.** Each class emits rows into the single canonical table.

### A — `staticValue` default mismatch (alias-map comment driven)

For every attribute carried as `staticValue: Y` on a generated node, look up the attribute's `#` comment in `ivr-alias-json-map.json` under the node's alias. If the comment contains `use default value: X` (or `default: X` / `else use default value: X`) and `Y != X` → row. `Category = WRONG_CONTENT`, `Risk = HIGH` for required attrs, `MEDIUM` otherwise. `KB Rule Violated = Default: {alias}.{attr} — alias map comment "{verbatim snippet}" (source: ivr-alias-json-map.json → {alias} → {attr})`.

### B — `promptName` missing / inappropriate

For every `*PromptName` attribute (`promptName`, `playFilePromptName`, `retryFilePromptName`, `invalidDigitsRetryFilePromptName`, any `*PromptName`):

- Both `staticValue` and `from.variableName` null / empty / missing → `MISSING_CONTENT`, `Risk = HIGH`.
- Generated value contradicts the slot's role from the alias-map comment (e.g. `retryFilePromptName` = `welcomeMenu`) → `WRONG_CONTENT`, `Risk = MEDIUM`.
- Generated value matches a `nodeId` / `node.name` / UUIDv4 → `WRONG_CONTENT`, `Risk = HIGH`.
- `from.variableName` resolved value (via upstream `digitVariable` / `script` / `variables` block) fails any of the above → same row with dual citation.

### C — Transitions & events

- Missing transition target (ref points at a non-existent node) → `WRONG_CONTENT`, HIGH.
- Duplicate event entries inside a single node's `events[]` (same event name more than once) → `WRONG_CONTENT`, HIGH.
- Required event handler missing (present in expected, absent in generated) → `MISSING_CONTENT`, HIGH.
- Extra events (in generated, not in expected) → `EXTRA_CONTENT`, MEDIUM.
- Transition ID reused across different events → `WRONG_CONTENT`, HIGH.

### D — Variables & data flow

Build a flow-wide variable registry from `variables` blocks, `digitVariable` / `ttsVariable` / `storeVariable` outputs, and assignments inside populated scripts. Then:

- Undeclared variable reference (`from.variableName` / condition RHS / `{{var}}` interpolation pointing at a name that's never declared) → `WRONG_CONTENT`, HIGH.
- Duplicate `digitVariable` across multiple `node.digit.collection` nodes → `WRONG_CONTENT`, HIGH.
- Unreferenced declaration → `EXTRA_CONTENT`, LOW.
- Variable used with inconsistent types across scripts → `WRONG_CONTENT`, MEDIUM.

### E — Structural completeness (generated vs expected)

- Node present in expected, missing in generated → `MISSING_CONTENT`, HIGH.
- Node present in generated, no counterpart in expected (structural support nodes like `node.hangup` / entry / error-handler exempt) → `EXTRA_CONTENT`, MEDIUM.
- Non-free-form attribute present in one file but not the other → `MISSING_CONTENT` / `EXTRA_CONTENT`, HIGH.
- Sub-flow / child nodeflow missing → `MISSING_CONTENT`, HIGH.

### F — Flow / wiring sequence

- Transition order mismatch (expected `A → B → C`, generated `A → C → B`) → `WRONG_CONTENT`, HIGH. `KB Rule Violated = Flow: expected {A → B → C}, generated {A → C → B}`.
- Unreachable node (no transition points at it, not an entry) → `EXTRA_CONTENT`, MEDIUM.
- Broken parent→child back-references → `MISSING_CONTENT`, HIGH.

### G — Critical / strict instructions (from prompt files + agent code)

During the project-context sweep, the skill extracts every directive tagged with any of: `STRICT INSTRUCTIONS`, `CRITICAL`, `CRITICAL INSTRUCTIONS`, `IMPORTANT`, `MUST`, `MUST NOT`, `DO NOT`, `NEVER`, `ALWAYS`, `REQUIRED`; inline `**CRITICAL:**` / `**MUST:**` / `⚠️` / `❗` / `NOTE:`; `assert` statements with explanatory messages; `raise` calls with `CRITICAL`/`MUST`/`INVARIANT` prefixes; `CRITICAL:` / `IMPORTANT:` / `STRICT:` / `INVARIANT:` comments; docstring `Raises:` / `Invariants:` sections.

For each extracted directive:
1. Translate it into a concrete predicate over the generated file (node types, attribute presence/values, transition wiring, script bodies).
2. Evaluate. Violation → `WRONG_CONTENT`, `Risk = HIGH`, `KB Rule Violated = Strict: {verbatim directive} (source: {file}:{line})`.
3. If the directive is ambiguous and cannot be mechanically evaluated, emit an **advisory row**: `Risk = MEDIUM`, `KB Rule Violated = Strict (manual check): {directive} — could not evaluate automatically`.

The evaluated count plus advisory count must equal the total extracted count, or the skill has a bug.

### H — Pattern compliance (from `llm_docs/ivr-default-nodeflow-patterns.md` and prompt patterns)

During the sweep, extract named patterns with Required Elements and Anti-patterns. For each pattern the generated flow matches (by node-type signature + wiring shape):

- Required Element missing → `MISSING_CONTENT`, HIGH. `KB Rule Violated = Pattern "{name}": missing required element "{element}" (source: {file})`.
- Anti-pattern hit → `WRONG_CONTENT` or `EXTRA_CONTENT` depending on the anti-pattern, HIGH.

### I — Embedded scripts (`script` / `preScript` / `postScript` / `expression` / `handler` / `onEnter` / `onExit` / `onError`)

For every populated script body on a generated node:

- Syntax errors (unbalanced `{} () []`, unterminated strings, stray `;;`, missing `return` where one is required) → `WRONG_CONTENT`, HIGH.
- Undeclared variable reference inside the body → `WRONG_CONTENT`, HIGH.
- Unknown built-in function call (not in the scripting language reference found in project context) → `WRONG_CONTENT`, HIGH.
- Logic on the wrong node type (e.g. `hangup()` / `terminate()` on a non-hangup node, digit-branching on a node that isn't `node.digit.collection`) → `WRONG_CONTENT`, HIGH.
- Redundant / dead code (unreachable after `return`, duplicate adjacent statements) → `EXTRA_CONTENT`, MEDIUM.
- Duplicate script body across multiple keypaths (variable-name drift collapses to same fingerprint) → `EXTRA_CONTENT`, MEDIUM.
- Missing error handling where the scripting language reference mandates it → `WRONG_CONTENT`, MEDIUM.

If ≥50% of inventoried script bodies are empty (an upstream pipeline failure), emit a single high-risk banner row plus the per-body rows: `KB Rule Violated = Upstream: {N}/{total} script bodies are empty — orchestrator/pipeline did not populate them`. This unlocks the reviewer to fix the generator before re-running.

### J — Numbered / named constraints (from validator code + prompt STRICT blocks + doc rule tables)

During the sweep, extract every validator rule, `assert` invariant, schema `required` block, and numbered doc constraint. Each becomes a rule with a stable ID (`C1, C2, …`) if the source numbers it, otherwise a synthesized ID. Run each against the generated file. Violations → `WRONG_CONTENT`, HIGH. `KB Rule Violated = Constraint {id}: {rule} (source: {file}:{line})`.

### K — Open-ended ("anything else the project context mandates")

If the project-context sweep surfaces a rule or expectation that doesn't fit classes A–J — e.g. a prompt file mandates "every flow must have a `node.hangup` at the terminal" and the generated file doesn't — still evaluate it and emit a row. Use the most appropriate `Category` + prefix the `KB Rule Violated` with `Other: {rule-summary}`. Cite the `file:line`. This is the safety net that keeps the skill open-ended rather than fixed-scope.

### L — Verbatim string-content comparison for body-bearing attributes

**This class exists because earlier runs reported "preScript / postScript / script / columnNames attributes exist" without ever extracting their actual string values.** That is wrong. For certain attributes, the *content itself* is the thing being compared — describing that content in prose loses the comparison.

**Body-bearing attribute list** (case-insensitive, matched by attribute name anywhere in the generated / expected tree):
- `script`, `preScript`, `postScript`, `preFunction`, `postFunction`
- `expression`, `handler`, `onEnter`, `onExit`, `onError`
- `columnNames`, `columnNamesList`, `headers`, `headerList`
- `payload`, `body`, `requestBody`, `queryParams`
- `conditionExpression`, `filterExpression`
- Any attribute whose alias-map `#` comment describes it as "script" / "code" / "expression" / "payload" / "body" / "list of column names" / "comma-separated list"

**Mandatory behaviour for every body-bearing attribute on every node:**

1. **Extract the actual string value** from both the generated and expected files. Do NOT summarise, do NOT paraphrase, do NOT describe ("a script that handles X"). Copy the full string verbatim — `staticValue` literal, `from.variableName` reference, or nested `staticValue.value` body. If the string exceeds 2 KB, truncate to the first 1 KB plus an explicit `… [truncated, original {N} bytes]` marker, but never omit.
2. **Compare the two verbatim strings.** If they differ — any character difference outside free-form fields (whitespace-only differences are NOT flagged; everything else is) — emit a row:
   - `Category = WRONG_CONTENT` for value drift, `MISSING_CONTENT` when the attribute is populated in expected but empty/missing in generated, `EXTRA_CONTENT` when populated in generated but absent in expected.
   - `Expected Content` = the verbatim expected string (truncated as above with marker).
   - `Actual Content` = the verbatim generated string (same truncation rule).
   - `KB Rule Violated = Body: {alias}.{attr} — verbatim string content differs between generated and expected`.
   - `Risk = HIGH` for `script` / `preScript` / `postScript` / `expression` / `handler` (logic-carrying). `MEDIUM` for `columnNames` / `headers` / `payload` / `body` (data-carrying).
3. **Empty-in-generated, non-empty-in-expected** is a separate `MISSING_CONTENT` row with `Actual Content = _(empty)_` and `KB Rule Violated = Body: {alias}.{attr} — expected has a populated {attr} body, generated is empty (upstream generation likely failed)`.
4. **Per-row content sanity checks** (run in addition to the verbatim comparison):
   - Script body contains `==` where the expected body uses `===` (or vice versa) → separate row, `Risk = MEDIUM`, `KB Rule Violated = Body: {alias}.{attr} — equality-operator drift (== vs ===)`.
   - Script body references a variable name that is not declared anywhere in the flow (cross-reference with class D's registry) → row, `Risk = HIGH`.
   - `columnNames` / `headers` differ in element count → row, `Risk = HIGH`, with both arrays rendered in `Expected` / `Actual`.
   - `columnNames` differ in order only → `FORMATTING`, `Risk = LOW`, only if the KB or expected comment marks ordering as significant.
5. **No summarisation clause** — any time the skill would otherwise say "preScript contains logic to …" or "columnNames lists roughly N entries", it must instead emit the row with the verbatim string. Description is forbidden for body-bearing attributes; extraction is mandatory.

### Free-form exclusions (never flagged)

The following are never discrepancies regardless of value differences:
- Node / flow / nodeflow display names (`name`, `displayName`, `label`, `description`, `comments`).
- Timestamps (`createdAt`, `updatedAt`), actor fields (`createdBy`, `updatedBy`).
- Regenerated identifiers (any `id` / `nodeId` / `flowId` / `uuid` / `revisionId` freshly minted per build — recognised by the alias-map `# To be created by agent at runtime` directive or UUIDv4 shape).
- Node coordinates / layout positions (`x`, `y`, `position.*`, `coordinates`, `layout`, `canvasX/Y`, `gridX/Y`, `left`, `top`).
- Attributes marked `# Fixed.` in the alias map that are structural metadata only (`alias`, `type`, `version`, `visible`, `basePath`, `isConfigruationsValid`, `uiProps.*`, `rendererType`).

---

## Execution order

1. **Locate inputs.** Generated JSON from `inputs/compare/generated/` (or `generated=<path>` arg). Expected JSON from `inputs/compare/expected/` (or `expected=<path>`). If the generated input ends in `.anfx`, treat as a zip archive — extract in-memory and use the inner `nodeflow.json`. `source=<path>` optional.

2. **Load `ivr-alias-json-map.json`.** Search `agentic_core/llm_docs/`, repo root, `inputs/`, `config/`, `data/`, `kb/`, or adjacent to generator code. If missing, STOP: `❌ ivr-alias-json-map.json not found`.

3. **Exhaustive CLAUDE.md File Index sweep.** Walk `CLAUDE.md`'s `## File Index` and open every entry:

   - **Small files (<50 KB, no `⚠️ LARGE FILE` flag)** → read end-to-end. This covers every prompt under `agentic_core/llm_docs/prompts/`, every IVR domain doc (`ivr-nodeflow.md`, `ivr-nodes.md`, `ivr-transition.md`, `ivr-variables.md`, `ivr-child-nodeflow.md`, `ivr-coordinates.md`, `ivr-default-nodeflow-patterns.md`), every small agent file (`ivr_flow_generator.py`, `add_variables_agent.py`, `add_coordinates_agent.py`, `child_nodeflow_merge_agent.py`, `diff_sow_extractor_agent.py`, `document_analyzer_agent.py`, `project_name_extractor_agent.py`), all utils, and the whole `app/` tree.
   - **`⚠️ LARGE FILE`** (`orchestrator.py`, `nodes_generation.py`, `add_transitions_agent.py`, `validation_agent.py`, `output_generation_agent.py`) → grep-scan with the full rule-extraction pattern set: `default|DEFAULT|prompt|promptName|playFilePrompt|retryFilePrompt|invalidDigit|staticValue|from\.variableName|alias|node\.|transition|event|variable|digitVariable|STRICT|CRITICAL|IMPORTANT|MUST|MUST NOT|NEVER|ALWAYS|REQUIRED|INVARIANT|raise |assert |pattern|anti-pattern|validator`. Capture matches with `file:line`.
   - **Binary** (`.pdf`, `.docx`, `.xlsx`, `.pptx`, images) → dispatch to `/docx`, `/xlsx`, `/pptx`, or the PDF reader.
   - **Unreadable / unsupported** → record skip reason; no silent omissions.

   Build a single `projectContext` cache of `{path, classification, read_mode, extracted_rules}`. The extracted rules feed classes **G (strict)**, **H (patterns)**, **I (scripting language)**, **J (constraints)**, and **K (other)** — and also supplement classes A–F when the alias map is silent.

   Print the coverage:
   ```
   File Index coverage: {A} full / {B} grep / {C} readers / {D} skipped / total {N}
     Skipped:
       - {path} ({reason})
   ```
   The totals must add up. No silent omissions.

4. **Parse the alias map.** `defaultMap[alias][attr]` from `use default value: X` comments; `roleMap[attr]` from role descriptions. When a default is absent, consult `projectContext` for a supplementary default.

5. **Walk the generated JSON node-by-node**, in parallel with the expected JSON. For each node, run **every** check class A–L. Match nodes structurally (alias + position in flow, not by ID). Append one row per finding.

   **Body-bearing attribute rule (applies to every node walk):** whenever the walker touches an attribute whose name matches the class-L body-bearing list (`script`, `preScript`, `postScript`, `preFunction`, `postFunction`, `expression`, `handler`, `onEnter`, `onExit`, `onError`, `columnNames`, `columnNamesList`, `headers`, `headerList`, `payload`, `body`, `requestBody`, `queryParams`, `conditionExpression`, `filterExpression`), it MUST:
   - Dereference the `staticValue` literal or `from.variableName` wrapper and extract the **actual string value** (or JSON literal) into the in-memory finding record.
   - Never record a summary, paraphrase, or description in place of the extracted content.
   - If the value exceeds 2 KB, truncate to the first 1 KB with an explicit `… [truncated, original {N} bytes]` marker but retain the truncated prefix verbatim.
   - Compare the extracted string against the expected file's string at the same slot and emit a class-L row on any character-level difference (excluding whitespace-only noise).

   This rule is mandatory. Any finding from a body-bearing attribute that lacks the verbatim string content in `Expected Content` / `Actual Content` is invalid.

6. **Plausibility check.** Before concluding, verify:
   - Every File Index entry was touched (totals add up).
   - Every extracted `strict` directive was either evaluated (row emitted on violation) or recorded as advisory.
   - No check class was silently skipped.
   - For every node that has a body-bearing attribute (script / preScript / postScript / columnNames / etc.), at least one class-L record exists in the in-memory findings pool — pass or flag. If a body-bearing attribute appears on a generated node and the walk produced zero class-L records for it, that's a walker bug; re-run the class-L walk for that node before writing the sheet.
   If any of the above fails, re-run the missing part before writing the sheet.

7. **Print the summary:**
   ```
   /find-bugs-exotel complete.
     File Index coverage:         {A} full / {B} grep / {C} readers / {D} skipped
     Nodes checked:               {N}
     Attributes checked:          {M}
     Findings by category:
       MISSING_CONTENT  {a}
       WRONG_CONTENT    {b}
       EXTRA_CONTENT    {c}
       FORMATTING       {d}
     Findings by check class:
       A staticValue defaults:     {a1}
       B promptName issues:        {b1}
       C transitions & events:     {c1}
       D variables:                {d1}
       E structural completeness:  {e1}
       F flow sequence:            {f1}
       G critical instructions:    {g1} evaluated, {g2} advisory of {gt} total
       H pattern compliance:       {h1}
       I embedded scripts:         {i1}
       J constraints:              {j1}
       K other project-context:    {k1}
       L body-bearing attrs:       {l1} verbatim comparisons ({lok} ok / {ldiff} differ / {lempty} empty-in-generated)
     Body-bearing attributes extracted verbatim: {total body attrs touched}
     Rows written to comparison_sheet.md: {total}
   ```

---

## Important Rules

1. **Canonical single-table format.** Every finding goes in the one 13-column table. Never split tables. Downstream (`/process-comparison`, `/apply-fixes`) depends on the exact schema.

2. **All check classes run on every invocation.** A through K — minimum. Classes may emit zero rows if a category has no applicable data, but must still run to completion. Silently skipping a class is a skill-side bug.

3. **Open-ended scope via class K.** Rules, constraints, patterns, and critical instructions surfaced by the project-context sweep that don't fit A–J still get evaluated and emit rows under class K. The listed classes are the floor, not the ceiling.

4. **Alias map is the primary authority.** `ivr-alias-json-map.json` comments are authoritative for defaults and `*PromptName` slot roles. Hard-fail if the file is missing.

5. **Exhaustive File Index read.** Every file listed in CLAUDE.md's `## File Index` is opened (full / grep / reader). Every prompt, IVR doc, agent module, util, app-layer file, and root file. The coverage arithmetic must hold: `full + grep + readers + skipped == total`. No silent omissions.

6. **Free-form fields are never flagged.** Display names, timestamps, regenerated UUIDs, coordinates, and structural metadata (`alias`, `type`, `version`, `visible`, `uiProps.*`) are never discrepancies.

7. **Every row cites a source.** `KB Rule Violated` must name the authority: alias-map comment (verbatim quote), expected-file keypath, or `file:line` from project context. Never leave it empty.

8. **Generated vs expected parity.** The skill walks BOTH files in parallel, matching nodes by alias + position, not by ID. A discrepancy can be flagged from either direction.

9. **`.anfx` input is a zip.** Unpack in-memory and use the inner `nodeflow.json`.

10. **Propose-only.** No source edits, no git writes, `PENDING_REVIEW` only.

11. **No SOW.** Never reads, looks for, or requests a Statement of Work file. The expected JSON is the reference for what the flow should contain.

12. **Empty-result sanity.** "No discrepancies found" is valid only when every check class A–K ran to completion and every project-context directive was either evaluated or recorded as advisory. Never silently under-report.

13. **Every extracted strict / constraint / pattern must be processed.** Not sampled. Not skipped for verbosity. The total evaluated-plus-advisory count must equal the total extracted count printed in the summary.

14. **Body-bearing attributes are extracted verbatim, never summarised.** For every attribute whose name is in the body-bearing list (`script`, `preScript`, `postScript`, `preFunction`, `postFunction`, `expression`, `handler`, `onEnter`, `onExit`, `onError`, `columnNames`, `columnNamesList`, `headers`, `headerList`, `payload`, `body`, `requestBody`, `queryParams`, `conditionExpression`, `filterExpression`), the skill must copy the literal string value (or JSON literal, or resolved `from.variableName` value) into the finding record, compare it character-for-character against the expected file's corresponding slot, and emit class-L rows on any drift. Descriptions like "preScript contains logic to …" or "columnNames lists approximately N entries" are forbidden — they are always replaced by a row carrying the verbatim content in `Expected Content` / `Actual Content`. Truncation at 2 KB is permitted but the truncated prefix must still be verbatim.

15. **Body-bearing attribute coverage is audited.** The Step 6 plausibility check counts the body-bearing attributes present on generated nodes and verifies that each one produced at least one class-L record in the in-memory findings pool. A gap here means the walker silently summarised; re-run class L for the missing nodes before writing the sheet.
