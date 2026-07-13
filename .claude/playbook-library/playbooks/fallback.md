---
id: fallback
seen-in: []
fallback: true
---

# Playbook: fallback

Analysis advice for the case when **no archetype-specific playbook matches** the client's artifacts. Ensures kb-builder still produces a tailored, self-contained KB for first-of-kind clients.

Structurally different from other playbooks: a specific playbook holds domain advice for one archetype. The fallback holds **discovery advice** — how to figure out a use-case Claude hasn't seen before, from artifacts that don't fit any known archetype.

Every fallback run is a strong candidate for promotion into a real specific playbook. End-of-run candidate flag is mandatory — surface it when the build completes.

## When this playbook applies (recognition signals)

This playbook fires **only by exclusion** — when recognize.md finds no specific playbook fits. The matcher does not signal-test the fallback against artifacts. (See `pipeline/recognize.md`'s fallback handling.)

If you find yourself testing files against signals from this playbook, stop. Re-read recognize.md.

## What to look for when analyzing

The fallback's analysis advice is procedural — a discovery process rather than archetype-specific attention tips.

- **Triage the artifacts by superficial kind.** Group by:
  - *Structured data* — JSON, XML, YAML, CSV, schema files.
  - *Unstructured prose* — text docs, MOMs, transcripts, briefs, emails.
  - *Reference deliverables* — polished PDFs / DOCX / spreadsheets that look like end-state outputs.
  - *Code / source files*.
  - *Mixed / other*.

  For each group, characterize: file count, file shapes (top-level keys, doc genre), and the likely role each artifact plays (source content vs. reference example vs. format spec vs. brief). Report the grouping; do not propose a KB shape yet.

- **The use case must be elicited from the operator.** Claude cannot infer it from artifacts alone reliably. kb-builder must run an interactive use-case elicitation phase before drafting the KB. Specifically the operator needs to answer:
  - What does the downstream agent **produce**? (document / JSON artifact / config / code / form / other)
  - Are these artifacts **references to mimic**, **source material to extract from**, **format specs to learn**, or some combination?
  - Will the agent be invoked with **per-instance inputs that vary per run**, or is each invocation roughly identical?
  - What are the **per-instance must-haves** the agent needs before it can produce output?
  - Anything important about the deliverable that **isn't in these artifacts** — style guides, undocumented conventions, regulatory constraints, named entities not yet shared?

- **The KB shape must be proposed and confirmed before drafting.** Based on triage + use-case, kb-builder should propose a KB file list with one-line per-file purposes, surface it to the operator, and wait for confirmation. Drafting without confirming shape is how the fallback degrades into platform-kb.

- **Be ruthless about scope.** Default to skipping. If a category doesn't earn its keep against the use-case, drop it. The fallback's primary failure mode is producing a kitchen-sink KB that's longer than useful.

## Cross-cutting principles (carried over from the specific playbooks)

These hold for **every** archetype, so they hold for a first-of-kind client too. The specific playbooks each specialize them in their own vocabulary; the fallback inherits them in archetype-neutral form. Apply the ones the use-case actually exercises — they are how a discovery-mode KB reaches *valid*, not merely *plausible*.

- **A handful of artifacts is a few traversals of the deliverable, not a spec of it.** Whatever the archetype, samples exercise only the slice they happened to need. Sort every fact into two buckets and act on the bucket:
  1. **Sample-extractable** — the shapes and the observed instances. Mine these exhaustively, but treat them as a **floor**, never the full library.
  2. **Not sample-extractable** — defaults, full vocabularies, conventions, failure modes, runtime behavior, what varies per-instance vs. what's fixed, and the rules that make output *valid* rather than merely *well-formed*. These are invisible, partial, or unreliable in samples. **Every such category must resolve to an artifact request and/or a tagged question.** A category with no closing mechanism is a *silent cap* — the single most common failure of this whole skill, and the under-coverage twin of the kitchen-sink failure above.

- **Well-formed is not valid.** Output can match every documented field and shape and still fail downstream — because docs describe the artifact *above* the layer the consumer actually requires, or omit constraints, failure modes, or identity/discriminator fields. Capture not just the shape but what makes an instance valid and safe to use.

- **Request reference artifacts before — and instead of — interviewing.** One authoritative export or convention doc collapses dozens of questions and beats reverse-inference from samples. Two distinct kinds, both high-value: **(A) schema / spec / format exports** — the shapes the platform can emit; **(B) convention / rule documents** — the team's own build knowledge (routing rules, naming, defaults, validation rule-sets, house patterns) that no export contains and that is usually what separates "valid" from "well-formed." Ask for whichever exist; a *promise* to send one is a pending BLOCKING dependency — wait for it, don't draft around it and silently cap the surface.

- **Present the request in the operator's terms.** Operators don't recognize abstract artifact names but do recognize "your docs," "the export," "that spreadsheet." Render the ask as **one checklist** — one row per entity you actually found in their artifacts — each row saying what the doc contains in plain language, what you already extracted, and why the gap matters. Make the affordance explicit: **they can point you at files / a folder / a wiki / even a screenshot — they don't have to type the answers.**

- **Validate docs against a known-good instance; an attested instance beats a prose description.** Whenever even one real, finished example of the deliverable exists, make it ground truth and **diff every doc claim against it** — where they diverge, the instance wins. Prefer **copying an attested element verbatim** over reconstructing it from a prose example (a prose example is lossy by design). Where the consumer will assert or import the output, bake the structural diff in as a **generator verify step**.

- **Capture load-bearing strings verbatim.** Identity / dispatch / format-exact strings — field names, keys, enum values, defined terms, fixed constants — are exact, not paraphrasable. Quote them everywhere downstream; a synonym or a reformat silently breaks the consumer.

- **Distinguish fixed from per-instance — and don't guess it from a single sample.** With only one reference you cannot tell boilerplate from variable content; surface that as BLOCKING rather than freezing a field. Use multiple samples or ask. Classify each field **fixed / set-from-input / runtime-derived**, and never freeze a container that is empty-by-coverage to a fixed scalar.

- **When artifacts conflict, prefer the most recent confirmed position — and flag the conflict.** Different artifact types carry different authority; a later decision supersedes an earlier one. Don't silently overwrite; surface the conflict to the operator.

- **Keep the KB self-contained.** Bundle every reference the downstream agent must read at build or run time, and point at the **bundled copy**, never the path it arrived on. Do *not* bundle pure analysis inputs (e.g. a single sample once docs cover the surface) — they add bulk and pull the generator toward sample-mimicry over the documented rules. **Never bundle secrets.**

- **Halt over guessing.** When a required fact is missing from every artifact, ask — don't fabricate. Fabrication fails silently: a reviewer senses something is wrong but can't point to the source.

## Common pitfalls

When kb-builder composes the KB's Critical Rules:

- **Do not propose a KB shape without operator confirmation.** The use-case elicitation phase is non-negotiable. Skipping it turns the fallback into platform-kb.
- **Do not include sections "just in case."** Skip-entirely beats include-just-in-case. The KB should be the smallest thing that fully serves the deliverable.
- **Do not mistake the corpus for the platform.** Samples are traversals, not a spec. Cap the KB at the sampled slice and the generator emits output that's plausible but invalid because it never knew the default, the vocabulary, or the rule no sample exercised. Every not-sample-extractable category must resolve to an artifact request or a tagged question — no silent caps.
- **Do not reverse-infer a schema when an export exists.** Defaults, full vocabularies, and conventions are unreliable or impossible to recover from instances. Ask for the export or the convention doc first; one good artifact collapses dozens of questions.
- **Do not stop at "well-formed."** Matching the documented shape is not the same as being valid and safe. Validate against a known-good instance when one exists, and copy attested elements verbatim rather than rebuilding them from prose.
- **Do not silently invent the artifact's type or use-case.** If artifacts are ambiguous, ask. Halting beats guessing.
- **Do not skip the candidate-archetype flag at end of run.** Every fallback run is by definition a candidate for promotion. Surface it loudly so the library actually grows.
- **Do not let this client's vocabulary leak into a future playbook.** When the operator promotes this run into a real playbook, they must generalize the analysis advice to the archetype level — not copy this client's specific values, names, or constants.

## Useful questions to ask the operator

Examples of operator-facing questions for the discovery phase. These are phrasing examples, not a checklist: the discovery / scope step sets what matters, then ask only the questions whose answers would change the KB and that the artifacts do not already answer.

Ask in **two tiers**. *First*, request any reference artifact that would answer a whole cluster of these by construction (an export, a spec, a finished example, a convention doc) — render the ask in the operator's terms as one checklist, per the cross-cutting principle above. *Then* interview on the conventions no artifact contains. Every question keeps its severity tag (BLOCKING / IMPORTANT / VERIFY ASSUMPTION) so the operator sees which gaps actually halt the build.

- **BLOCKING — Deliverable shape unspecified.** "I couldn't pin down the downstream deliverable's exact format from the artifacts. Format / schema / example?"
- **BLOCKING — Reference example missing.** "I don't see a finished example of the deliverable. Without one I can't ground style / structure / vocabulary. Can you share one, or describe the target shape?"
- **IMPORTANT — Source-material scope.** "Are these artifacts everything the downstream agent will have, or will it be invoked with additional per-instance inputs?"
- **IMPORTANT — Mimic-vs-extract.** "Should the agent (a) mimic the style / structure of these references for new instances, (b) extract content from these as source material for one synthesis, or (c) both?"
- **IMPORTANT — Tier 1 per-instance fields.** "What are the must-have fields the agent needs before drafting? If I can't enumerate them, the agent will silently fabricate when they're missing."
- **VERIFY ASSUMPTION — KB shape.** "I drafted the KB using the shape we agreed on. Re-checking: still right, or have we learned something that should reshape it?"

## Typical KB shapes that have worked

By design, no canonical shape. kb-builder proposes a shape based on the use-case + triage and gets operator confirmation before drafting.

For reference, common shapes by use-case (use as inspiration only, not as defaults):

- *Artifact emission* (JSON / structured output): overview, building-blocks, composition-rules, schema, patterns, constraints, input-checklist, gap-log.
- *Document generation*: overview, document-structure, visual-style, language-and-tone, vocabulary, tables-and-figures, boilerplate, variable-vs-fixed, patterns, input-checklist, constraints, gap-log.
- *Configuration / template emission*: overview, schema, defaults, conditional-rules, examples, gap-log.

## Skip-entirely categories

kb-builder must be ruthless. Default to skipping. Specifically:

- Sections describing functionality the artifacts don't actually exercise.
- "Future-proofing" sections for things the operator didn't ask for.
- Cross-references to file types the agreed shape doesn't include.

If a category doesn't earn its keep against the use-case, drop it.
