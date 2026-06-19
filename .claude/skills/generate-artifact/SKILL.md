---
name: generate-artifact
description: Generate a platform deliverable — either a config (JSON, XML, YAML, a NodeFlow JSON, any structured config a platform consumes) or a piece of code (an SDK integration, a function, a glue/script snippet — NOT a whole project or codebase) — from a platform-specific Knowledge Base plus a user prompt, and nothing else. The skill is completely platform-agnostic: every platform-specific fact (schema, node types, events, API surface, rules, vocabulary, what "valid" means) comes from the KB; the prompt says what to build. Use when an operator points at a KB and asks to produce the actual deliverable it describes. Triggers: "generate the config / nodeflow / artifact from this KB", "use the {client} KB to build ...", "produce the {platform} deliverable for ...".
---

# generate-artifact

Turn a **platform-specific KB** + a **user prompt** into the actual deliverable that KB describes producing — a config or a piece of code.

```
   KB (how this platform works)  ─┐
                                   ├─► generate-artifact ─► the deliverable (config or code)
   prompt (what to build)        ─┘        (verified)
```

The skill is a **generic engine**. It knows nothing about any platform. It learns the platform entirely from the KB at runtime and never hardcodes a node type, a schema, an API, or a language. Point it at a different KB and it produces a different platform's deliverable with no change to the skill.

## Inputs — only these two

| Input | Meaning | Required |
|---|---|---|
| `kb=<dir>` | The platform-specific Knowledge Base directory (e.g. `outputs/exotel/kb/`). The single source of truth for **how** this platform expresses things. | **Yes** |
| `prompt` / `$ARGUMENTS` | Free text: **what** to build and the specific requirements/content for it. | **Yes** |
| `output=<dir>` | Where to write the deliverable. Default: `outputs/<client>/generated/`, where `<client>` is the parent folder of the `kb` directory. | No |

**There is no other input.** No sample artifacts, no source-material folder, no reference deliverables. If you find yourself wanting one, you instead either (a) read it from the KB, (b) take it from the prompt, or (c) ask the user. Do not assume any file exists beyond the KB.

## Core principles

1. **Platform-agnostic, always.** Make zero assumptions about the platform or the deliverable. Every platform-specific fact — schemas, field names, node/event types, API methods, language, idioms, naming rules, defaults, what counts as valid — comes from the KB. If it is not in the KB and not in the prompt, you do not know it: ask, or flag it. **Never invent platform facts from general knowledge.**
2. **KB is *how*, prompt is *what*.** The KB carries the platform's grammar and rules. The prompt carries the specific thing to build. Your job is to express the prompt's intent using only the KB's constructs.
3. **Verify before you deliver.** Derive the validity checks from the KB (see Phase 4) and run them. A config that is 95% right is broken; a code snippet that does not parse or calls a nonexistent symbol is broken. Repair what fails; report what you could not.
4. **Ask as you go — never force a batch.** See below. This is the behavior the operator cares most about.

## Asking questions

Ask the user a question **whenever you actually need to, at the moment you need to** — not as one big upfront questionnaire, and not a long checklist at the end. Most forced batch questions turn out irrelevant or out of scope; do not generate them.

- Ask only when the answer would **materially change the deliverable** AND it is **not already answered by the KB or the prompt**.
- If a reasonable default exists (in the KB's conventions, or an obvious choice), **take it, state the assumption, and keep going** — do not stop to ask. Reserve real questions for genuine blockers or true forks where guessing wrong is costly.
- Ask **one or a few tightly-scoped questions at a time**, in the natural flow of the work, then continue. It is fine to ask again later when a new decision actually comes up.
- Never ask the user to supply platform knowledge that belongs in the KB — if the KB is missing it, say the KB is missing it.

You run **in the main conversation**, so asking mid-flow just works. Use that.

## Pipeline

Run in order, but the question behavior above applies throughout — not just at one gate.

### 1. Learn the platform from the KB
Read the **entire** KB directory. Determine, from its content alone:
- What deliverable(s) this KB enables, and in what form (which config format, or which code/SDK + language). If the KB explicitly declares its target/deliverable, that declaration governs.
- The grammar to obey: schema, field catalog, node/event/condition types, API surface, vocabulary, naming conventions, required vs. optional parts, and any reference structures the KB provides (e.g. an alias→JSON map, template snippets, canonical examples) — these are to be used faithfully, not approximated.
- **What "valid" means for this platform** — the checks you will run in Phase 4. The KB implies them: required fields, reference integrity, allowed enums, naming patterns, "must compile / lint clean", "symbols must exist", etc.

### 2. Understand the request and fix the deliverable
Parse the prompt: what they want built, and the specific requirements/content. Reconcile with what the KB can produce.
- One clear deliverable → proceed.
- KB supports several and the prompt is ambiguous → ask one quick question to pick.
- Prompt asks for something the KB does not cover → say so plainly; do not fabricate platform facts to fill the gap.

### 3. Plan the deliverable
Form an internal, platform-neutral spec of what is being built (its structure and intent), mapped onto the KB's constructs. Where a needed specific is missing: take a stated default if the KB supports one, otherwise ask now if it is a real fork. Keep the plan in your head or as a short note — the deliverable is the artifact, not the plan.

### 4. Generate
Produce the artifact **strictly** from the KB's grammar/schema/templates/idioms. Use the KB's reference structures verbatim where it provides them. Use no platform knowledge that is not in the KB.

**Fixed per-type constants — copy, never choose or coin.** For any value the KB marks fixed-per-type (data-provider ids, port ids, engine/interpreter identifiers, class discriminators, etc.), copy the **exact value the KB's reference/template gives for that exact type** — including when it is `null`. Do **not** pick an alternative from a documentation "options"/prose list, and do **not** synthesize one by pattern-matching the type's name (e.g. coining `<type>.data.provider`). A documentation "option" attested in **no** known-good example is unverified: a plausible-but-unregistered constant passes structural checks and then crashes the platform at import (a null-registry lookup). When in doubt, prefer the value **attested in a known-good reference flow** over anything that appears only in a comment.

### 5. Verify and repair
Run the validity checks identified in Phase 1.
- **Config:** structural/schema validity, required fields present, references resolve, enums/values legal, naming conventions honored. **Validate every fixed-per-type constant and enumerated value against the KB's allowed set for that type** — and when the KB ships known-good reference flows, the value must match one **attested** there, not merely something a comment lists as possible. A value that is documented-but-unattested is a failed check: replace it with the attested value or flag it. (This is the silent-invalid class — structurally fine, rejected by the platform.)
- **Code:** it parses; if a toolchain is available, it lints/compiles/type-checks (use Bash to run it); the SDK symbols/methods it calls actually exist in the KB's API surface.
Loop generate↔verify until clean or genuinely stuck. Surface anything unresolved with the reason — do not silently ship a failing check.

### 6. Deliver
Write the artifact to `output`. Then give a short report:
- what was produced and where,
- the key assumptions you made (so the user can correct them),
- any open questions or checks you could not satisfy,
- if useful, how to verify it on the platform.

## Deliverable types

- **Config** — JSON / XML / YAML / a visual-flow JSON (e.g. NodeFlow `.anfx`) / any structured file a platform ingests. Validity is structural + schema + reference integrity, graded against the KB (and a known-good reference if the KB names one).
- **Code** — an SDK integration, a function, a handler, a glue script. **Snippets and integrations, not whole projects or codebases.** Validity is "parses, lints/compiles if a toolchain exists, and only calls real symbols from the KB's API surface."

## Never do this

- Never hardcode a platform fact in the skill, or carry one over from a previous run / general knowledge. The KB is the only authority.
- Never emit a generator program or scaffold a project. The deliverable is the artifact itself.
- Never invent a field, node type, event, or API method to make something fit. If the KB lacks it, say so.
- Never emit a fixed-per-type constant just because documentation lists it as an "option" or because the type's name suggests it. If no known-good example attests the value, it's unverified — use the attested value for that type or flag it. Plausible-but-unregistered constants are the most common silent-invalid that ships broken.
- Never dump a forced wall of clarifying questions. Ask narrowly, when it matters, as you go.

## Re-runs

If the same `output` already holds a prior deliverable, treat the run as an **update**: read what is there, apply only what the new prompt changes, and note what changed. Keep a tiny manifest (what was built, from which KB, key assumptions, open items) next to the output so a later run can update in place rather than start over.

## Folder layout

```
.claude/skills/generate-artifact/SKILL.md   ← this skill (platform-agnostic engine)

outputs/<client>/
├── kb/            ← platform-specific KB (produced by kb-builder) — INPUT
└── generated/     ← the deliverable this skill writes — OUTPUT
    ├── <artifact>
    └── manifest.json
```
