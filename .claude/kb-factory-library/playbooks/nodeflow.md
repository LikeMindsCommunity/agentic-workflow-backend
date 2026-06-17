---
id: nodeflow
seen-in: [exotel]
fallback: false
---

# Playbook: nodeflow

Analysis advice and lessons learned for clients whose artifacts are **JSON definitions of visual flows** — node-and-transition graphs exported from a visual flow / IVR / orchestration builder. The consuming skill uses this as guidance while analyzing the artifacts; the KB that gets generated is Claude's composition for *this* client, not a copy of this file.

## When this playbook applies (recognition signals)

Structural signals at the archetype level — vendor-agnostic by design. Specific vendor fingerprints (engine identifier strings, top-level container key names, exact node-type lists) are NOT here; they get captured from the actual artifacts during analysis.

- **File format**: JSON.
- **A node collection and a transition collection.** The JSON contains (under some top-level container) a list or map of *nodes* and a separate list or map of *transitions* / edges wiring nodes together. Names vary by vendor — what matters is the structural pair.
- **Each node carries a stable identifier** (commonly UUID) and a **type label** that categorizes its behavior (play / prompt, digit / input collection, script, stop, transfer / dial, etc.). Nodes often also carry an `alias` or `kind` namespaced string, plus attributes and events.
- **Each transition references nodes by ID** — typically a source node + event name → target node, optionally guarded by a condition.
- **Embedded scripts may live inside node attributes.** Short code blocks (script / preScript / postScript / condition expressions) usually run in a **sandboxed interpreter**, not general Node/browser JS.
- **Conditions, variables, and child / sub-flows** are often kept in dedicated top-level maps alongside nodes and transitions.
- **Layout coordinates** on nodes (x/y) and waypoints on transitions are common; they don't affect execution.
- Optional: a fixed engine/runtime fingerprint string identifying the script interpreter. If present, it's a strong vendor-specific recognition signal — capture into the KB, not here.

If a file doesn't match these structural signals (it's an n8n workflow with a `connections` map and no node-type concept, a prose document, a REST API schema, etc.), the playbook doesn't apply.

## The analyst's real job: close the sample-to-platform gap

**A handful of sample flows is not a spec of the platform — it is a few traversals of it.** Each flow exercises only the node types, attributes, events, variables, and patterns it happened to need. But the KB's job is to let a downstream agent **generate new, valid flows** — which means it must describe the *whole platform surface*, not the slice the samples walked.

So the primary analytical task is **not** "transcribe the samples." It is: for every knowledge category below, ask **"does the corpus fully reveal this, or only a slice — and if only a slice, what artifact or answer would capture the whole thing?"** Where the answer is "a slice," that is a gap to close by **requesting a platform artifact** (best, most reliable) or **interviewing the operator/SME** (for the conventions no export contains). Treat this gap-hunting as the spine of the analysis; everything else hangs off it.

Capping the KB at whatever the corpus happened to contain is the single most common failure: the generator then emits flows that are structurally plausible but invalid, because it never knew about the node type, the default attribute, the injected variable, or the routing convention that no sample exercised.

### What samples cannot (fully) tell you — ponder each before drafting

Walk this checklist for every nodeflow client. For each row, decide whether the corpus actually settles it; if not, it becomes an artifact request (next section) or a gap-question (severity-tagged later).

| Knowledge category | What a sample shows | What's missing — and must be elicited |
|---|---|---|
| **Node palette** | only the types those flows used | the full type vocabulary the builder offers |
| **Per-node attribute schema** | only the attributes a flow *populated* | every attribute, its type, **default value**, and whether each field is fixed / set-from-input / generated-at-runtime |
| **Event & port catalog** | only events that got wired | the complete event list per node type, and the fixed source/target **port identifiers** (often must be used verbatim, never guessed) |
| **Platform-injected variables** | **nothing** — they're never declared in a flow's variable map | the global/runtime variables the engine provides for free (caller id, call result, disposition, timings…) and the rule that flows must NOT re-declare them |
| **Script runtime surface** | only the built-ins a script happened to call | the full sandbox API — allowed calls, explicitly forbidden calls, guaranteed language built-ins |
| **Terminal & failure routing** | one instance of where an error / exhausted / failure port went | the *convention*: where each such port must route, per node type, and any success↔failure mirror rules |
| **Mandatory vs optional sub-flows** | the patterns those flows used (maybe) | which sub-flows the agent must emit by **default** vs only on request, and each canonical one's exact internal node sequence |
| **Artifact boundary & self-nesting** | a parent that *references* sub-flows by id, or a sub-flow shown standalone | whether the whole graph (parent + all descendants) is **one** artifact with sub-flows **nested** under a recursive container, or separate linked files — and which container holds the nested definitions |
| **Data/query libraries & provider constants** | a query string only if a flow embedded one | the standard query/template library the DB-backed nodes embed, and the data-provider constant each node type uses (and when it switches) |
| **Naming & init conventions** | the names a flow chose | the enforced naming scheme, what gets initialized where, parent-vs-child init differences, which result-variable each node type writes |
| **Singletons & placement rules** | individual nodes | which node types must be a single shared instance, which are forbidden inside sub-flows, what scaffolding every flow must include |
| **Identity / discriminator requirements** | the metadata a flow serialized | which discriminator / `_class`-style fields or metadata objects are mandatory, and what breaks (e.g. editor import) if omitted |
| **Envelope enums & constants** | the one or two enum values those flows used | the full flow-type enum, the fixed engine constants, the default sentinel values |
| **Layout convention** | the coordinates as rendered | the directional / swimlane rule the coordinates follow (no execution effect) |

## What to look for when analyzing

Extraction technique for mining the corpus. In every case: **capture exhaustively what the corpus shows, AND log where it only shows a slice** so the gap carries forward to the artifact-request / question round.

- **Enumerate every distinct node `type` (or vendor equivalent)** across all files with occurrence counts and source files — then treat that set as a *floor, not the library*.
- **Record the `alias` / `kind` → `type` mapping.** Aliases are often the handle the runtime dispatches on.
- **Extract every event name verbatim** from both nodes (`events[*]`) and transitions (`from.eventName` or equivalent). They're case-sensitive dispatch strings — quote them exactly everywhere downstream.
- **Walk every script body** in every script-accepting attribute and pull the bare identifiers used as calls/variables. These are what the runtime actually provides — never assume Node/browser globals.
- **Extract the condition operator set and any function calls** the expression language uses.
- **Note the variable-initialization convention** (often a designated init/start node) — and check whether it's enforced or merely conventional.
- **Capture the top-level container shape, fixed constants, and universal node fields** (the fields every node carries) once.
- **Spot sentinel target IDs** (a literal like `"SuccessStop"` used as a transition target instead of a real node id) so the generator doesn't dereference them.
- **Check cross-corpus consistency.** A convention that holds in one sample may not be universal — flag discrepancies.
- **Reason over whole flows, not isolated nodes**, to surface scaffolding, singletons, forbidden-in-subflow rules, and required terminal sub-sequences — none of which any single node declares.
- **Spot recursive / self-referential containers and pin the artifact boundary.** Flow artifacts often embed whole copies of their own type (child / sub-flows) under a dedicated container. Decide explicitly: is the entire graph **one** self-contained file with descendants nested recursively, or are sub-flows separate files linked by id, and *which container holds the nested definition* vs *which just lists the id*? If that container is `null`/empty in the sampled instances, that is a **coverage** fact, not a **fixed-value** fact — find a sample that has children (or consult the template export / ask) before classifying it. **Never freeze a recursive container as a fixed empty/`null` scalar:** that leaves the generator nowhere to nest descendants, so it splits one deliverable into multiple files.

## Close the gap first: artifacts to request

Before — or alongside — the gap-question round, ask whether the operator can share any of these. One good export collapses dozens of questions and is far more reliable than reverse-inference from samples:

- **The node palette / library export** — the full type vocabulary.
- **The per-node definition / JSON-template export** — the builder's own schema for each node (attributes, types, defaults, field classification, full event list, port ids). *This is the single highest-value artifact; it is most of a deep KB by itself.*
- **The global / runtime variable reference** — the variables the engine injects that never appear in a flow's variable map.
- **The scripting runtime / API reference** — sandbox built-ins, allowed vs forbidden calls, guaranteed language built-ins.
- **The standard query / template library** the DB- or HTTP-backed nodes embed (plus just enough data schema to parameterize them).
- **A broader set of SME-blessed "golden" flows** covering more node types and patterns than the initial corpus.
- **The platform's own validator / linter rules**, if one exists — they encode the constraints directly.

Record every unsampled-but-real type / attribute / event as **known-but-unsampled** (named, no fabricated schema/events) until an artifact or the SME confirms it. Per the gap loop, a *promise* to send an export is a pending **BLOCKING** dependency — wait for it; don't draft around it and silently cap the vocabulary.

When you do receive a big reference export (the per-node template map is the usual one), the generator will need to read it directly at generation time — so **bundle it into the KB directory and reference the bundled copy**, never the path it arrived on. A KB that points at an external file the consumer can't see is a broken deliverable (see the skill's self-contained-KB rule).

## Useful questions to ask the operator

Ask in **two tiers**. *First*, request the artifacts above — they answer most of this by construction. *Then* interview the operator/SME on the conventions no export contains. This is a phrasing bank, not a checklist: align scope first, then ask only the in-scope unknowns whose answers would change the KB, generated from *this* client's artifacts. Fill the `{...}` placeholders from your analysis; don't enumerate the list verbatim.

**BLOCKING — coverage the KB cannot be complete without**

- **Node palette completeness (reconcile, don't just count).** "I observed `{observed_types}`. Samples show only the types a flow used — can you share the full palette / node-definition export so I capture the rest, with their attribute schemas, defaults, events, and port ids? Anything in the palette but absent from a sample I'll record as available-but-unsampled rather than guess."
- **Per-node attribute schema & defaults.** "For each node type, what is the complete attribute list with default values, and which fields are fixed vs set-from-input vs generated at runtime? Samples only reveal the attributes a flow happened to populate."
- **Platform-injected variables.** "What global / runtime variables does the engine provide that never appear in a flow's variable map (caller id, call result, disposition, call timings, etc.)? The generator must reference these and must NOT re-declare them — and I can't see them in any sample."

**IMPORTANT — conventions samples under-reveal**

- **Terminal & failure routing.** "Where must each node's error / exhausted-retries / failure ports route by convention — one designated terminal, a prompt-then-stop, something per node type? And do any failure ports mirror their matching success port's destinations?"
- **Mandatory vs optional sub-flows.** "Which sub-flows should the agent emit by default (entry gating, queue/agent routing with retry, callback/voicemail, recording, post-call processing) vs only when the request asks? Give the exact node sequence for each canonical one — I'd rather capture it than infer it from one example."
- **Artifact boundary & sub-flow packaging.** "Is the deliverable a single self-contained file with all sub-flows **nested** under a recursive container, or are parent and sub-flows separate linked artifacts? Which field nests a sub-flow's full *definition* vs which merely lists its *id*? I saw `{container}` empty/`null` in the samples — confirm whether it nests child definitions when children exist."
- **Singletons, placement & scaffolding.** "Any node types that must exist as a single shared instance reused across paths? Any forbidden inside sub-flows? Any required start/init node or closing sub-sequence every flow must include?"
- **Script runtime surface.** "Scripts in the artifacts call `{observed_built_ins}`. What is the full allowed set the runtime provides, and which calls are explicitly forbidden?"
- **Data/query library & provider constants.** "For DB- or HTTP-backed nodes, is there a standard query/template library (and the schema it targets), and what data-provider constant does each node type use — and when does it switch?"
- **Naming & initialization conventions.** "Is there an enforced variable naming scheme? Which node type writes which result variable? What must be initialized where, and how do parent vs child sub-flows differ (values a parent sets that a child must not re-init)?"
- **Identity / discriminator requirements.** "Which fields or metadata objects are mandatory for a flow to import and run (e.g. class discriminators on bound variables or transition labels), and what fails if they're missing?"
- **Condition / expression language.** "Conditions used `{observed_operators}`. Is that the complete operator/function set, and are there value-formatting rules (e.g. compare collected digits as strings, copy exact values from the script)?"
- **Envelope enums & constants.** "What are the allowed flow-type values, the fixed engine constants, and the default sentinel values for the top-level envelope? Samples only show the one or two we used."
- **Rare node usage.** For a type seen in only one or two files: "I saw `{TypeName}` only in `{filenames}` — standard type or a one-off variant?"

**VERIFY ASSUMPTION — state the default, let them correct**

- **Variable initialization.** "I observed variables initialized in `{init_node_type}` before any node references them — confirm that's the required convention?"
- **Parent vs sub-flow init.** "Do sub-flows re-initialize the same way, or does the parent set values a child must not touch?"
- **Engine fingerprint.** "I saw `{engine_fingerprint}` as the interpreter id — always fixed for this platform, or does it vary by environment/version?"
- **Layout convention.** "Coordinates look like `{observed_layout_rule}` (e.g. left-to-right by flow order, start leftmost / stop rightmost, branches offset vertically). Confirm? (No execution effect.)"

## Common pitfalls

When composing the KB's Critical Rules, draw from these (the ones that apply + new ones the analysis surfaces):

- **Do not mistake the corpus for the platform.** Samples are traversals, not a spec. The KB must cover the whole surface a generator could need, not just the slice the samples walked.
- **Do not skip the artifact request and reverse-infer a schema from samples.** Defaults, field classification, full event/port catalogs, and the injected-variable list are unreliable or impossible to recover from instances — ask for the export.
- **Do not omit platform-injected variables** just because they never appear in a flow's variable map. They are invisible in samples by definition, and the generator both needs them and must not re-declare them.
- **Do not treat the sample-observed node set as the full palette.** Reconcile against an authoritative palette; record unsampled-but-real types as gaps; never silently cap the vocabulary.
- **Do not describe the scripting layer as generic JavaScript.** It is typically a sandboxed interpreter; built-ins come from real script bodies and the runtime reference, not web/Node assumptions.
- **Do not paraphrase event names, aliases, or port ids.** They are exact dispatch/identity strings — quote them verbatim everywhere.
- **Do not record error / terminal routing as a free choice when it's a fixed convention.** If the platform mandates where error / exhausted / failure ports go (or that a failure port mirrors its success port), capture it as a rule; "route somewhere sensible" lets the generator emit non-conforming flows.
- **Capture fixed per-type constants from what working flows attest, not from documentation "options."** A node's data-provider id (and similar fixed-per-type strings) is constant per type. Record the value **real working flows actually carry** for each type — including `null` where that's what they use. Be wary of a template/doc that lists several "options" for such a field: an option named only in a comment, attested in **no** working flow, may be unregistered and will crash import (a null-registry read like `…reading 'async'`). In the KB, pin the canonical attested value per type, note that documented-but-unattested alternatives are unverified, and state that the value is copy-verbatim and an unregistered one breaks import — so the generator copies it and can validate against the allowed set (this is the data-provider analogue of the verbatim port-id rule).
- **Do not flatten a recursive container into a fixed scalar, and do not externalise nested sub-flows.** A self-nesting field (a child / sub-flow map) seen as `null` in a sample is empty-by-coverage, not constant. Classifying it "fixed null" makes the generator emit child flows as **separate files** and break the single-artifact contract. Capture the recursive shape *and* the packaging boundary (one file, children nested under the container, `null` only for a leaf) as a constraint.
- **Do not merge variables-and-scripting into the building-blocks file.** The variable system and the expression/script language are a separate subsystem the generator dereferences constantly; give them their own reference.
- **Do not invent node types or attributes.** Document only what the corpus or an authoritative artifact confirms; record absent-but-likely items under Known Gaps without fabricating schema/events.
- **Do not include external REST API / auth / webhook reference.** Producing flow JSON is artifact-emission; the standard *query/template a node embeds* is in scope, but a general API/integration surface is not.
- **Do not hardcode vendor fingerprints into this playbook.** Engine identifier strings, container key names, exact node vocabularies, the injected-variable list — all vary by vendor; they belong in the KB as observed values, not here.

## Typical KB shapes that have worked

Past clients of this archetype have settled around these KB files. Reference only — the file list is sized to what *this* client's artifacts and the elicited platform surface demand.

- `00-overview.md` — Domain context, glossary (node, transition, event, condition, port, variable, child flow), top-level container shape, fixed engine constants, the allowed flow-type enum.
- `01-building-blocks.md` — One subsection per node type (observed and elicited): alias, type, purpose, when-to-use, **full attribute schema with defaults and field classification**, event + port catalog. Universal node fields documented once.
- `02-composition-rules.md` — Transition schema, conditional vs unconditional transitions, condition resolution, source/target port semantics, parent ↔ child wiring (the reference locations) **plus where a child's full definition is nested**, sentinel target ids, terminal/failure routing conventions and success↔failure mirror rules.
- `03-artifact-schema.md` — Full top-level schema, fields classified fixed / identity / configurable / computed — but a **recursive sub-flow container is structural, not a fixed scalar; never freeze it to `null`** — and the **single-artifact packaging rule** (does the whole graph serialize to one file with sub-flows nested, or separate linked files?), with minimum-valid + fully-featured annotated examples.
- `04-variables-and-scripting.md` — Variable system, **platform-injected/global variables**, naming + initialization conventions, parent-vs-child rules, embedded scripting, the sandbox API (allowed + forbidden), condition language with CORRECT/WRONG examples.
- `05-patterns.md` — Canonical composition patterns, each with when-to-use, step-by-step node sequence, required wirings, anti-pattern. Mandatory/default patterns and scaffolding sub-flows called out and distinguished from optional ones.
- `06-constraints.md` — Numbered constraints (rule / consequence / CORRECT / WRONG), capturing routing conventions, singleton/placement rules, single-artifact packaging (sub-flows nested, not separate files), identity/discriminator requirements, and value-formatting rules.
- `07-layout-rules.md` — Coordinate / waypoint conventions (no execution effect).
- `08-input-checklist.md` — Per-instance fields the generator must extract before building a flow, tiered by criticality.
- `09-gap-log.md` — Remaining uncertainties, known-but-unsampled node types/attributes/events, and any artifact still pending from the operator.

## Skip-entirely categories

What's typically out of scope. The KB should never emit:

- External REST API reference.
- Authentication setup.
- Webhook contracts.
- Entity data model catalogs (the *standard query/template a node embeds* is in scope; a general data-model reference is not).
- Generic configuration reference.

Generating flow JSON is artifact-emission, not API integration. Including these wastes context and invites the generator to hallucinate a surface the runtime doesn't expose to flow scripts.
