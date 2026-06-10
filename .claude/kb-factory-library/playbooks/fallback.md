---
id: fallback
seen-in: []
fallback: true
---

# Playbook: fallback

Analysis advice for the case when **no archetype-specific playbook matches** the client's artifacts. Ensures kb-factory still produces a tailored, self-contained `{client}-kb` skill for first-of-kind clients.

Structurally different from other playbooks: a specific playbook holds domain advice for one archetype. The fallback holds **discovery advice** — how to figure out a use-case Claude hasn't seen before, from artifacts that don't fit any known archetype.

Every fallback run is a strong candidate for promotion into a real specific playbook. End-of-run candidate flag is mandatory (enforced by `assemble.md`).

## When this playbook applies (recognition signals)

This playbook fires **only by exclusion** — when match.md finds no specific playbook fits. The matcher does not signal-test the fallback against artifacts. (See `pipeline/match.md`'s fallback-flag handling.)

If you find yourself testing files against signals from this playbook, stop. Re-read match.md.

## What to look for when analyzing

The fallback's analysis advice is procedural — a discovery process rather than archetype-specific attention tips.

- **Triage the artifacts by superficial kind.** Group by:
  - *Structured data* — JSON, XML, YAML, CSV, schema files.
  - *Unstructured prose* — text docs, MOMs, transcripts, briefs, emails.
  - *Reference deliverables* — polished PDFs / DOCX / spreadsheets that look like end-state outputs.
  - *Code / source files*.
  - *Mixed / other*.

  For each group, characterize: file count, file shapes (top-level keys, doc genre), and the likely role each artifact plays (source content vs. reference example vs. format spec vs. brief). Report the grouping; do not propose a KB shape yet.

- **The use case must be elicited from the operator.** Claude cannot infer it from artifacts alone reliably. The generated skill must include an interactive use-case elicitation phase that fires before drafting. Specifically the operator needs to answer:
  - What does the downstream agent **produce**? (document / JSON artifact / config / code / form / other)
  - Are these artifacts **references to mimic**, **source material to extract from**, **format specs to learn**, or some combination?
  - Will the agent be invoked with **per-instance inputs that vary per run**, or is each invocation roughly identical?
  - What are the **per-instance must-haves** the agent needs before it can produce output?
  - Anything important about the deliverable that **isn't in these artifacts** — style guides, undocumented conventions, regulatory constraints, named entities not yet shared?

- **The KB shape must be proposed and confirmed before drafting.** Based on triage + use-case, the generated skill should propose a KB file list with one-line per-file purposes, surface it to the operator, and wait for confirmation. Drafting without confirming shape is how the fallback degrades into platform-kb.

- **Be ruthless about scope.** Default to skipping. If a category doesn't earn its keep against the use-case, drop it. The fallback's primary failure mode is producing a kitchen-sink KB that's longer than useful.

## Common pitfalls

When kb-factory composes the generated skill's Critical Rules:

- **Do not propose a KB shape without operator confirmation.** The use-case elicitation phase is non-negotiable. Skipping it turns the fallback into platform-kb.
- **Do not include sections "just in case."** Skip-entirely beats include-just-in-case. The KB should be the smallest thing that fully serves the deliverable.
- **Do not silently invent the artifact's type or use-case.** If artifacts are ambiguous, ask. Halting beats guessing.
- **Do not skip the candidate-archetype flag at end of run.** Every fallback run is by definition a candidate for promotion. Surface it loudly so the library actually grows.
- **Do not let this client's vocabulary leak into a future playbook.** When the operator promotes this run into a real playbook, they must generalize the analysis advice to the archetype level — not copy this client's specific values, names, or constants.

## Useful questions to ask the operator

Examples of operator-facing questions for the discovery phase. These are phrasing examples, not a checklist: the discovery / scope step sets what matters, then ask only the questions whose answers would change the KB and that the artifacts do not already answer.

- **BLOCKING — Deliverable shape unspecified.** "I couldn't pin down the downstream deliverable's exact format from the artifacts. Format / schema / example?"
- **BLOCKING — Reference example missing.** "I don't see a finished example of the deliverable. Without one I can't ground style / structure / vocabulary. Can you share one, or describe the target shape?"
- **IMPORTANT — Source-material scope.** "Are these artifacts everything the downstream agent will have, or will it be invoked with additional per-instance inputs?"
- **IMPORTANT — Mimic-vs-extract.** "Should the agent (a) mimic the style / structure of these references for new instances, (b) extract content from these as source material for one synthesis, or (c) both?"
- **IMPORTANT — Tier 1 per-instance fields.** "What are the must-have fields the agent needs before drafting? If I can't enumerate them, the agent will silently fabricate when they're missing."
- **VERIFY ASSUMPTION — KB shape.** "I drafted the KB using the shape we agreed on. Re-checking: still right, or have we learned something that should reshape it?"

## Typical KB shapes that have worked

By design, no canonical shape. The generated skill proposes a shape based on the use-case + triage and gets operator confirmation before drafting.

For reference, common shapes by use-case (use as inspiration only, not as defaults):

- *Artifact emission* (JSON / structured output): overview, building-blocks, composition-rules, schema, patterns, constraints, input-checklist, gap-log.
- *Document generation*: overview, document-structure, visual-style, language-and-tone, vocabulary, tables-and-figures, boilerplate, variable-vs-fixed, patterns, input-checklist, constraints, gap-log.
- *Configuration / template emission*: overview, schema, defaults, conditional-rules, examples, gap-log.

## Skip-entirely categories

The generated skill must be ruthless. Default to skipping. Specifically:

- Sections describing functionality the artifacts don't actually exercise.
- "Future-proofing" sections for things the operator didn't ask for.
- Cross-references to file types the agreed shape doesn't include.

If a category doesn't earn its keep against the use-case, drop it.
