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

Twelve baseline check classes (A–L) plus the manifest-driven open-ended class K. Class G builds the rule manifest exhaustively from every KB file; every other class consumes it. **All classes run on every invocation.** Each class emits rows into the single canonical table.

### A — `staticValue` default mismatch (alias-map comment driven, exhaustive)

After step 4 builds `defaultMap[alias][attr]`, the skill MUST iterate every generated node and, for every attribute whose alias-map entry carries a `# use default value: X` (or `# default: X` / `# else use default value: X`) comment, compare the generated `staticValue` to X. Any difference → row.

The defaultMap walk is exhaustive across the whole alias map first (no per-attribute branching by relevance), so the skill is forced to enumerate every defaulted attribute and confirm whether each generated node carries the expected value, the explicit override, or nothing. Print:

```
Class A coverage: {default-bearing attrs} × {nodes touched} = {checks run}
```

`KB Rule Violated = Default: {alias}.{attr} — alias map comment "{verbatim snippet}" → expected "{X}", generated "{Y}" (source: ivr-alias-json-map.json → {alias} → {attr})`.

`Category = WRONG_CONTENT` for value drift, `MISSING_CONTENT` if the defaulted attribute is absent on the generated node. `Risk = HIGH` for required attrs (no `# Optional` marker), `MEDIUM` otherwise.

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

### D — Variables & data flow (conditions-block aware)

Build a flow-wide variable registry from:
- `nodeflowInfo.variables` declarations (name → declaration site)
- `digitVariable` / `ttsVariable` / `storeVariable` outputs from node attributes
- assignments inside populated script bodies (`var X = …`, bare `X = …`)
- platform defaults (`srcPhone`, `dstPhone`, `campaignId`, `callResult`, `systemDisposition`, `talkTime`, `ivrTime`, `userAssociations`) — always available

Then walk:

1. **Conditions block** — for every entry in `conditions{}`, tokenise the condition expression and resolve every identifier on LHS/RHS. Any identifier not in the registry → `WRONG_CONTENT`, HIGH. KB cite from the variable-scope rule in `ivr-variables.md` and the conditional-transition instructions in step2 prompt.
2. **`from.variableName`** references — same check on every attribute.
3. **`{{var}}` interpolations** in any body-bearing string — same check.
4. **Same name declared multiple times** in `nodeflowInfo.variables` (different `variableId`s) → `WRONG_CONTENT`, HIGH.
5. **Same name reused for semantically different purposes** — heuristic: identifier assigned in two distinct script bodies whose surrounding node names indicate different menus → `WRONG_CONTENT`, MEDIUM.
6. **Duplicate `digitVariable` across `node.digit.collection` nodes** → `WRONG_CONTENT`, HIGH.
7. **Unreferenced declaration** → `EXTRA_CONTENT`, LOW.
8. **Variable used with inconsistent types across scripts** → `WRONG_CONTENT`, MEDIUM.

The conditions-block walk MUST run on every flow even if zero conditions exist (in which case it emits `0 conditions evaluated` in the summary).

### E — Structural completeness (generated vs expected)

- Node present in expected, missing in generated → `MISSING_CONTENT`, HIGH.
- Node present in generated, no counterpart in expected (structural support nodes like `node.hangup` / entry / error-handler exempt) → `EXTRA_CONTENT`, MEDIUM.
- Non-free-form attribute present in one file but not the other → `MISSING_CONTENT` / `EXTRA_CONTENT`, HIGH.
- Sub-flow / child nodeflow missing → `MISSING_CONTENT`, HIGH.

### F — Flow / wiring sequence

- Transition order mismatch (expected `A → B → C`, generated `A → C → B`) → `WRONG_CONTENT`, HIGH. `KB Rule Violated = Flow: expected {A → B → C}, generated {A → C → B}`.
- Unreachable node (no transition points at it, not an entry) → `EXTRA_CONTENT`, MEDIUM.
- Broken parent→child back-references → `MISSING_CONTENT`, HIGH.

### G — Rule manifest (exhaustive extraction across the entire project context)

Before any per-node check runs, the skill builds a single in-memory **rule manifest** by walking every file collected in step 3 and emitting one entry per discoverable rule. A "rule" is any sentence, bullet, numbered item, table row, alias-map comment, schema constraint, `assert`, `raise`-with-message, or docstring requirement that constrains what the generated IVR JSON may or may not contain. Tag words (CRITICAL / STRICT / MUST / NEVER / etc.) are HINTS that elevate priority — they are NOT prerequisites for extraction.

**Extraction sources (every one mandatory):**

1. **Numbered/lettered instructions** in every prompt file — e.g. `prompts/ivr-prompt-nodes-generation-step2.md` items 1–32. Each numbered item becomes one or more manifest entries (a single item may carry multiple sub-rules).
2. **Bulleted sub-rules** under any numbered item. Each bullet is its own entry.
3. **Section-introduced rules** in IVR docs (`ivr-nodes.md`, `ivr-transition.md`, `ivr-variables.md`, `ivr-child-nodeflow.md`, `ivr-coordinates.md`, `ivr-default-nodeflow-patterns.md`). Walk every `### ` and `#### ` section; any sentence that says "must" / "should" / "only" / "never" / "always" / "required to" / "expected to" or that describes default behaviour becomes an entry.
4. **Alias-map `#` comments** — every `# use default value: X` becomes a Class A default-check entry. Every other comment that constrains the attribute ("must be …", "comma-separated list of …", "expects a variable with the SAME name", "fixed", "to be created by agent", etc.) becomes a Class K semantic-check entry.
5. **Pattern definitions** in `ivr-default-nodeflow-patterns.md` — every named pattern becomes a Class H entry with its Required Elements list and Anti-patterns list.
6. **Validator agent prompt** (`prompts/ivr-prompt-validation.md`) — every invariant the validator is supposed to enforce becomes a Class J entry.
7. **Embedded prompt strings inside agent `.py` files** — multi-line string literals in `add_transitions_agent.py`, `nodes_generation.py`, `validation_agent.py`, `output_generation_agent.py` often contain rule text the same shape as the prompt files. Read the strings (do NOT just grep keyword lines) and extract entries from them too.
8. **`raise` / `assert` calls with messages** in any code file — each one is a constraint entry.

Each manifest entry has the shape:

```
{
  rule_id: "{file-stem}-{seq}",       # e.g. "step2-26", "ivr-vars-12"
  source: "{path}:{line}",
  text: "{verbatim sentence or block}",
  tag_priority: HIGH | MEDIUM | LOW,  # HIGH if any of CRITICAL/MUST/NEVER tags
                                       # are present, else MEDIUM, LOW for advisories
  predicate: "{plain-language spec of what to check on the generated JSON}",
  evaluable: true | false              # false → emits an advisory row, not a
                                       #   gated finding
}
```

The model writes the manifest in-memory and prints the count by file in the step-3 coverage block:

```
Rule manifest extracted:
  prompts/ivr-prompt-nodes-generation-step2.md       → {N} rules
  prompts/ivr-prompt-validation.md                   → {N} rules
  ivr-transition.md                                  → {N} rules
  ivr-variables.md                                   → {N} rules
  ivr-nodes.md                                       → {N} rules
  ivr-default-nodeflow-patterns.md                   → {N} patterns / {M} anti-patterns
  ivr-alias-json-map.json                            → {N} default-checks, {M} semantic-checks
  agents/add_transitions_agent.py                    → {N} embedded-rule entries
  ...
  TOTAL                                              → {grand total}
```

If any KB file produces fewer than 5 rules, the skill flags it: `⚠️ low extraction count from {file} — re-read and extract` and re-runs the extractor for that file. (A 798-line `ivr-variables.md` returning 3 rules means extraction is broken; force re-read.)

Then run **every** manifest entry against the generated JSON. The accounting arithmetic must hold:

```
total = evaluated_pass + evaluated_violation + advisory + skipped_with_reason
```

`skipped_with_reason` must be 0 in normal runs; non-zero here is a skill bug.

**Per-entry execution:**
1. Translate the entry's `predicate` into a concrete check over the generated file (node types, attribute presence/values, transition wiring, script bodies, condition expressions).
2. Evaluate. Violation → `WRONG_CONTENT` (or appropriate Category), `Risk` per `tag_priority`, `KB Rule Violated = {class-prefix}: {verbatim text snippet} (source: {file}:{line})`. The `class-prefix` is `Strict`, `Default`, `Variable`, `Transition`, `Pattern`, `Constraint`, `Other`, etc. — pick whichever class the rule semantically belongs to (manifest entries flow into A–L + K open-ended).
3. If the predicate is ambiguous and cannot be mechanically evaluated, emit an **advisory row**: `Risk = MEDIUM`, `KB Rule Violated = {class-prefix} (manual check): {text} — could not evaluate automatically (source: {file}:{line})`.

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

### Bundling — collapse duplicate findings before writing the sheet

After every check class has populated the in-memory findings pool but BEFORE writing `comparison_sheet.md`, run a bundling pass.

**Group by `(rule_id from manifest, Expected Content, Actual Content shape, Category, Risk)`.** Two findings bundle iff:
- Same originating manifest rule (same `rule_id`).
- Same `Expected Content` value (or same expected pattern when expected is a default like "valid UUIDv4").
- Same `Actual Content` kind (e.g. both "non-hex chars", both "duplicate digitVariable", both "staticValue populated for prompt-name slot when language menu present").
- Same `Category` and same `Risk`.

When a group has N≥2 entries, emit ONE bundled row:
- `Comp ID` — next sequential ID.
- `Location (Generated)` — up to 5 representative locations followed by `+ {N-5} more` if N>5. Format: `path1; path2; …; +{X} more`.
- `Location (Expected)` — mirrors the same.
- `Expected Content` and `Actual Content` keep their canonical values.
- `KB Rule Violated` keeps the rule citation and gains a suffix `[bundled: {N} occurrences]` so the reviewer knows.
- `Risk` — max of the group.

When a group has N=1, emit the row as today.

**Do NOT bundle across distinct manifest rules** (a Class A default mismatch never merges with a Class C transition row, even if the messages look similar).

**Do NOT bundle when `Actual Content` differs in substantive content** — e.g. two undeclared-variable references with different variable names ARE separate rows (the variable name is the actionable detail). Two UUID-format violations both saying "contains non-hex chars" with different IDs CAN bundle because the rule and the remediation are identical and the IDs go into `Location`.

The summary gains:

```
Bundling: {raw} raw findings collapsed to {bundled} rows ({groups} groups bundled, {singletons} singletons)
```

---

## Execution order

1. **Locate inputs.** Generated JSON from `inputs/compare/generated/` (or `generated=<path>` arg). Expected JSON from `inputs/compare/expected/` (or `expected=<path>`). If the generated input ends in `.anfx`, treat as a zip archive — extract in-memory and use the inner `nodeflow.json`. `source=<path>` optional.

2. **Load `ivr-alias-json-map.json`.** Search `agentic_core/llm_docs/`, repo root, `inputs/`, `config/`, `data/`, `kb/`, or adjacent to generator code. If missing, STOP: `❌ ivr-alias-json-map.json not found`.

3. **Exhaustive CLAUDE.md File Index sweep.** Walk `CLAUDE.md`'s `## File Index` and open every entry. Read mode is decided by **content type**, not by file size:

   - **KB documentation files** — every file under `agentic_core/llm_docs/` and `agentic_core/llm_docs/prompts/` MUST be read end-to-end, regardless of size. Grep-scan is FORBIDDEN for these files. The KB is the source of truth for what counts as a bug; the skill cannot extract rules from a file it hasn't actually read.
   - **Alias map (`ivr-alias-json-map.json`)** — parse the full JSON, then for every node alias enumerate every attribute and capture (a) the `# use default value: X` comment if present, (b) the role/semantic comment text, (c) the static type. Build `defaultMap[alias][attr]` and `commentMap[alias][attr]` exhaustively before any node walk runs. Skipping any attribute in any alias is a skill bug.
   - **Agent code files** under `agentic_core/agents/` — read end-to-end if ≤80 KB. For files >80 KB (`add_transitions_agent.py`, `output_generation_agent.py`, `nodes_generation.py`, `orchestrator.py`, `validation_agent.py`), read in ordered chunks (Read tool with `offset`/`limit`) covering the full file; do NOT rely on grep alone. The skill must inspect every embedded prompt string and every assertion. Grep is allowed as an INDEX into the file (to find the chunks worth reading first), never as a substitute for reading.
   - **App layer + utils + root** — read end-to-end at default chunk size.
   - **Binary** (`.pdf`, `.docx`, `.xlsx`, `.pptx`, images) → dispatch to `/docx`, `/xlsx`, `/pptx`, or the PDF reader.
   - **Unreadable / unsupported** → record skip reason; no silent omissions.

   Build a single `projectContext` cache of `{path, classification, read_mode, extracted_rules}`. The extracted rules feed classes **G (manifest)**, **H (patterns)**, **I (scripting language)**, **J (constraints)**, and **K (other)** — and also supplement classes A–F when the alias map is silent.

   Print the coverage:
   ```
   File Index coverage:
     KB markdowns full-read:        {N}/{N}    (grep count MUST be 0)
     Alias map fully parsed:        yes/no
     Agent code full-read (≤80KB):  {N}/{N}
     Agent code chunk-read (>80KB): {N}/{N}
     App + utils + root full-read:  {N}/{N}
     Binary readers dispatched:     {N}
     Skipped with reason:           {N}
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
   - **KB markdown files were all read end-to-end** (grep-scan count for files under `agentic_core/llm_docs/` and `agentic_core/llm_docs/prompts/` MUST be 0).
   - **Rule manifest exists in memory**, per-file count printed, and no file produced fewer than 5 rules unless explicitly empty (intro stubs).
   - **Every manifest entry has been evaluated, advised, or accounted for** under `skipped_with_reason`. Skipped count must be 0.
   - **defaultMap walk is exhaustive**: every alias × every defaulted attribute × every generated node was visited. Class A coverage line printed.
   - **Conditions block was walked**: identifier-vs-registry cross-check ran for every condition expression (or recorded "0 conditions evaluated" if the flow has none).
   - No check class was silently skipped.
   - For every node that has a body-bearing attribute (script / preScript / postScript / columnNames / etc.), at least one class-L record exists in the in-memory findings pool — pass or flag. If a body-bearing attribute appears on a generated node and the walk produced zero class-L records for it, that's a walker bug; re-run the class-L walk for that node before writing the sheet.
   - **Bundling pass ran exactly once** and the row count written equals `bundled` from the summary.

   If any of the above fails, re-run the missing part before writing the sheet.

7. **Print the summary:**
   ```
   /find-bugs-exotel complete.
     File Index coverage:
       KB markdowns full-read:        {N}/{N}    (grep count: 0)
       Alias map fully parsed:        yes
       Agent code full-read (≤80KB):  {N}/{N}
       Agent code chunk-read (>80KB): {N}/{N}
       App + utils + root full-read:  {N}/{N}
       Binary readers dispatched:     {N}
       Skipped with reason:           {N}
     Rule manifest:
       Total rules extracted:         {grand total}
       By file (top 10):              step2.md → {N}, ivr-transition.md → {N}, ivr-variables.md → {N}, ivr-nodes.md → {N}, validation.md → {N}, ivr-default-nodeflow-patterns.md → {N}, alias-map → {N}, …
       Evaluated as predicates:       {evaluated}
       Advisory (manual review):      {advisory}
       Skipped:                       {skipped}        (must be 0)
     Class A coverage:                {default-bearing attrs} × {nodes} = {checks}
     Conditions evaluated:            {N}
     Nodes checked:                   {N}
     Attributes checked:              {M}
     Findings by category (post-bundling):
       MISSING_CONTENT  {a}
       WRONG_CONTENT    {b}
       EXTRA_CONTENT    {c}
       FORMATTING       {d}
     Findings by check class (post-bundling):
       A staticValue defaults:     {a1}
       B promptName issues:        {b1}
       C transitions & events:     {c1}
       D variables / conditions:   {d1}
       E structural completeness:  {e1}
       F flow sequence:            {f1}
       G manifest-driven strict:   {g1} evaluated, {g2} advisory of {gt} total
       H pattern compliance:       {h1}
       I embedded scripts:         {i1}
       J constraints:              {j1}
       K other project-context:    {k1}
       L body-bearing attrs:       {l1} verbatim comparisons ({lok} ok / {ldiff} differ / {lempty} empty-in-generated)
     Body-bearing attributes extracted verbatim: {total body attrs touched}
     Bundling: {raw} raw findings collapsed to {bundled} rows ({groups} groups bundled, {singletons} singletons)
     Rows written to comparison_sheet.md: {bundled}
   ```

---

## Important Rules

1. **Canonical single-table format.** Every finding goes in the one 13-column table. Never split tables. Downstream (`/process-comparison`, `/apply-fixes`) depends on the exact schema.

2. **All check classes run on every invocation.** A through L — minimum, with class K (open-ended) absorbing every manifest entry not naturally claimed by A–L. Classes may emit zero rows if a category has no applicable data, but must still run to completion. Silently skipping a class is a skill-side bug.

3. **Open-ended scope via class K and the manifest.** Class G builds the rule manifest exhaustively; every entry not naturally absorbed by A–L flows into class K. The listed classes are the floor, not the ceiling. Class K rows are emitted from the manifest, not ad-hoc.

4. **Alias map is the primary authority.** `ivr-alias-json-map.json` comments are authoritative for defaults and `*PromptName` slot roles. Hard-fail if the file is missing.

5. **Exhaustive File Index read.** Every KB markdown under `agentic_core/llm_docs/` and `agentic_core/llm_docs/prompts/` is opened end-to-end (no grep). Every agent `.py` file is full-read if ≤80 KB or chunk-read if larger (grep allowed only as an INDEX into chunks, never as a substitute for reading). Every app/util/root file is read end-to-end. Binary files dispatch to the appropriate reader. The coverage arithmetic must hold; no silent omissions.

6. **Free-form fields are never flagged.** Display names, timestamps, regenerated UUIDs, coordinates, and structural metadata (`alias`, `type`, `version`, `visible`, `uiProps.*`) are never discrepancies.

7. **Every row cites a source.** `KB Rule Violated` must name the authority: alias-map comment (verbatim quote), expected-file keypath, or `file:line` from project context. Never leave it empty.

8. **Generated vs expected parity.** The skill walks BOTH files in parallel, matching nodes by alias + position, not by ID. A discrepancy can be flagged from either direction.

9. **`.anfx` input is a zip.** Unpack in-memory and use the inner `nodeflow.json`.

10. **Propose-only.** No source edits, no git writes, `PENDING_REVIEW` only.

11. **No SOW.** Never reads, looks for, or requests a Statement of Work file. The expected JSON is the reference for what the flow should contain.

12. **Empty-result sanity.** "No discrepancies found" is valid only when every manifest entry has been evaluated against the generated JSON, every KB file was full-read, and the manifest's per-file extraction count is non-trivial. Never silently under-report.

13. **Every extracted strict / constraint / pattern must be processed.** Not sampled. Not skipped for verbosity. The total `evaluated_pass + evaluated_violation + advisory + skipped_with_reason` count must equal the total extracted count printed in the summary; `skipped_with_reason` must be 0 in normal runs.

14. **Body-bearing attributes are extracted verbatim, never summarised.** For every attribute whose name is in the body-bearing list (`script`, `preScript`, `postScript`, `preFunction`, `postFunction`, `expression`, `handler`, `onEnter`, `onExit`, `onError`, `columnNames`, `columnNamesList`, `headers`, `headerList`, `payload`, `body`, `requestBody`, `queryParams`, `conditionExpression`, `filterExpression`), the skill must copy the literal string value (or JSON literal, or resolved `from.variableName` value) into the finding record, compare it character-for-character against the expected file's corresponding slot, and emit class-L rows on any drift. Descriptions like "preScript contains logic to …" or "columnNames lists approximately N entries" are forbidden — they are always replaced by a row carrying the verbatim content in `Expected Content` / `Actual Content`. Truncation at 2 KB is permitted but the truncated prefix must still be verbatim.

15. **Body-bearing attribute coverage is audited.** The Step 6 plausibility check counts the body-bearing attributes present on generated nodes and verifies that each one produced at least one class-L record in the in-memory findings pool. A gap here means the walker silently summarised; re-run class L for the missing nodes before writing the sheet.

16. **Bundling is mandatory.** Identical-rule, identical-shape findings collapse to one row per the Bundling section. Reviewers must never see N near-identical rows when the rule and remediation are the same. The bundling pass runs exactly once, after all check classes complete and before the sheet is written.

17. **No tag-gated extraction.** Class G / J / K do not skip rules because they lack `CRITICAL` / `MUST` / `NEVER` / `STRICT` tags. Tag words are priority hints (`tag_priority` field on the manifest entry), not extraction prerequisites. A 798-line `ivr-variables.md` returning 3 manifest rules is a bug — re-read and re-extract.
