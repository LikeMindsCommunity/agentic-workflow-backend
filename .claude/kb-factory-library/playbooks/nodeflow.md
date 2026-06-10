---
id: nodeflow
seen-in: [exotel]
fallback: false
---

# Playbook: nodeflow

Analysis advice and lessons learned for clients whose artifacts are **JSON definitions of visual flows** — node-and-transition graphs exported from a visual flow / IVR / orchestration builder. kb-factory uses this as guidance while analyzing the artifacts; the generated `{client}-kb` skill is Claude's composition, not a copy of this file.

## When this playbook applies (recognition signals)

Structural signals at the archetype level — vendor-agnostic by design. Specific vendor fingerprints (engine identifier strings, top-level container key names, exact node-type lists) are NOT here; kb-factory captures those from the actual artifacts during analysis.

- **File format**: JSON.
- **A node collection and a transition collection.** The JSON contains (under some top-level container) a list or map of *nodes* and a separate list or map of *transitions* / edges wiring nodes together. Names vary by vendor — what matters is the structural pair.
- **Each node carries a stable identifier** (commonly UUID) and a **type label** that categorizes its behavior (a play / prompt node, a digit / input collection node, a script node, a stop node, a transfer / dial node, etc.). Nodes often also carry an `alias` or `kind` namespaced string, plus attributes and events.
- **Each transition references nodes by ID** — typically a source node + event name → target node, optionally guarded by a condition.
- **Embedded scripts may live inside node attributes.** Short code blocks (script / preScript / postScript / condition expressions) usually run in a **sandboxed interpreter**, not general Node/browser JS.
- **Conditions, variables, and child / sub-flows** are often kept in dedicated top-level maps alongside nodes and transitions.
- **Layout coordinates** on nodes (x/y) and waypoints on transitions are common; they don't affect execution.
- Optional: a fixed engine/runtime fingerprint string identifying the script interpreter. If present, it's a strong vendor-specific recognition signal — capture into the generated skill, not here.

If a file doesn't match these structural signals (it's an n8n workflow with a `connections` map and no node-type concept, a prose document, a REST API schema, etc.), the playbook doesn't apply.

## What to look for when analyzing

These are the things experience says actually matter when reading flow JSON. kb-factory pays attention to these and then composes the generated skill accordingly.

- **The node type vocabulary is vendor-specific and matters exhaustively.** Enumerate every distinct `type` (or vendor equivalent) across all files, with occurrence counts and source files. Missing one type means the downstream agent can't generate flows using it.
- **The alias/kind namespace pairs with the type.** Record the `alias` → `type` mapping. Aliases are often the human-friendly handle the runtime dispatches on.
- **Event names are exact dispatch strings.** Extract every distinct event from both nodes (`events[*]`) and transitions (`from.eventName` or vendor equivalent). They're case-sensitive, often dotted, and must be quoted verbatim everywhere downstream.
- **Embedded scripts reveal the platform's built-ins.** Walk every script body in every script-accepting attribute. Extract bare identifiers used as function calls or variable references. These are *what the runtime actually provides*. Do NOT assume Node/browser globals (`console`, `fetch`, `require`, `process`, `window`, DOM) exist unless they actually appear in real scripts.
- **Condition expressions reveal the operator set and any function calls** the expression language supports.
- **Variable initialization conventions vary.** Often there's a designated "init script" node at the start of the flow where all variables get assigned defaults. Check whether this is enforced or merely conventional.
- **Top-level container shape and fixed constants are vendor-specific recognition signals** the generated skill should bake in (engine identifier strings, the fixed top-level keys, etc.).
- **Universal node fields** (the fields every node carries regardless of type) are worth documenting once and not repeating per type.
- **Sentinel target IDs** sometimes exist (e.g. a literal `"SuccessStop"` as a transition target instead of a real node ID). Spot these so the downstream generator doesn't try to dereference them.
- **Cross-corpus consistency.** If you have multiple sample flows, check whether assumptions hold across all of them. A convention that holds in one sample may not be universal — flag the discrepancy.

## Common pitfalls

When kb-factory composes the generated skill's Critical Rules, it draws from these (selecting the ones that apply to this client + any new ones the analysis surfaces):

- **Do not describe the scripting layer as generic JavaScript.** It is typically a sandboxed interpreter. Built-ins come from real script bodies in the corpus, not from web/Node assumptions.
- **Do not paraphrase event names.** They are exact dispatch strings. Quote them verbatim everywhere — building-blocks, composition rules, patterns, examples, gap log.
- **Do not merge variables-and-scripting into the building-blocks file.** The variable system and the expression / script language are a separate subsystem the downstream agent dereferences constantly. They need their own focused reference.
- **Do not include API / auth / webhook content even partially.** Producing flow JSON is artifact-emission, not REST integration. Including these sections wastes context and invites hallucination of an API surface the runtime doesn't expose.
- **Do not invent node types.** Only document types actually present in the corpus. If documentation or operator response mentions an absent-but-likely type, record under Known Gaps — do not fabricate its schema, events, or examples.
- **Do not hardcode vendor fingerprints into the playbook.** Engine identifier strings, top-level container key names, exact node-type vocabularies vary by vendor — they belong in the generated skill (as captured recognition signals) and in the KB at runtime (as observed values), not here.

## Useful questions to ask the operator

Examples of gap-questions that have surfaced real issues in past engagements. The generated skill's gap-question list is Claude's composition for this client's actual unknowns; inspire here but don't copy.

Use this as a phrasing bank, not a checklist. Align the KB's scope with the operator first, then ask only the few questions that are in scope, still unknown after reading the artifacts, and whose answers would change the KB. Do not enumerate this list.

- **BLOCKING — Node type completeness.** "I observed these node types in the artifacts: `{observed_types}`. Is this list complete, or are there other types in your full library? If so, please share more sample flows."
- **IMPORTANT — Script built-ins completeness.** "Scripts in your artifacts reference these globals / built-ins: `{observed_built_ins}`. Is this the full set the runtime provides, or are there others?"
- **IMPORTANT — Operator set completeness.** "Conditions used these operators: `{observed_operators}`. Is this the complete operator set the expression language supports?"
- **VERIFY ASSUMPTION — Variable initialization.** "I observed variables being initialized in `{init_node_type}` before any other node references them. Confirm that's the platform's required convention?"
- **IMPORTANT — Rare node type usage.** For each type appearing in only one or two files: "I saw `{TypeName}` only in `{filenames}`. Is this a standard type or a one-off variant?"
- **VERIFY ASSUMPTION — Engine fingerprint.** If a fixed engine identifier was observed: "I saw `{engine_fingerprint}` as the script interpreter identifier. Is this always the same for this platform, or does it vary by environment / version?"

## Typical KB shapes that have worked

Past clients of this archetype have settled around these KB files. Reference only — the generated skill's file list is sized to what *this* client's artifacts demand.

- `00-overview.md` — Domain context (what the flows do), glossary of basic concepts (node, transition, event, condition, port, variable, child flow), vendor's top-level container shape, fixed engine constants if present.
- `01-building-blocks.md` — One subsection per distinct node type observed: alias, type, purpose, when-to-use, full attribute schema, event catalog. Universal node fields documented once in a dedicated subsection.
- `02-composition-rules.md` — Transition schema, conditional vs unconditional transitions, condition resolution, source/target port semantics, parent ↔ child flow wiring, sentinel target IDs, universal conventions (e.g. "every node typically declares an error-event handler").
- `03-artifact-schema.md` — Full top-level schema. Fields classified fixed / identity / configurable / computed. Minimum-valid example + a fully-featured annotated example from real input.
- `04-variables-and-scripting.md` — Variable system, embedded scripting, observed built-ins, variable read/write idioms, condition expression language with CORRECT and WRONG examples per form.
- `05-patterns.md` — Common composition patterns extracted from input flows. Each pattern: when-to-use, step-by-step component sequence, required wirings, anti-pattern.
- `06-constraints.md` — Numbered constraints. Each: rule, consequence, CORRECT, WRONG.
- `07-layout-rules.md` — Coordinate / waypoint conventions. No execution effect; document the directional / swimlane convention observed.
- `08-input-checklist.md` — Per-instance fields the downstream agent needs to extract before generating a flow, tiered by criticality (must-halt vs may-proceed-with-default vs safe-default).
- `09-gap-log.md` — Remaining uncertainties, assumptions, node types mentioned in docs but absent from artifacts.

## Skip-entirely categories

What's typically out of scope for this archetype. The generated skill should never emit:

- External REST API reference.
- Authentication setup.
- Webhook contracts.
- Entity data model catalogs.
- Configuration reference.

Generating flow JSON is artifact-emission, not API integration. Including these sections wastes context and invites the agent to hallucinate an API surface the runtime doesn't expose to flow scripts.
