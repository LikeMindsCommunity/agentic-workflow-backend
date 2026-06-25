---
name: config-agent
description: From a platform-specific Knowledge Base (KB) plus a Statement of Work / solution doc (SOW), generate the structured CONFIG the platform ingests — a JSON / XML / YAML / NodeFlow or any structured config file — strictly from the KB's grammar, verify it against the KB's own rules, and write it to the output directory (default fallback `outputs/<client>/generated/`). Nothing is executed. The skill is platform-agnostic: every schema, field name, node/event type, enum, naming rule, and definition of "valid" comes from the KB; the SOW (and any inline prompt) says only WHAT to build. Use when an operator points at a KB + SOW and wants the structured config the KB describes. Triggers: "generate the config / nodeflow from this KB + SOW", "build the {platform} config", "config-agent", "produce the {client} config from the KB and solution doc".
---

# config-agent

Turn a **platform-specific KB** + a **SOW** (the client's statement of work / solution doc, in any form) into the **structured config** that platform ingests, verified against the KB's own rules. **Nothing is executed.**

```
   KB  (how this platform expresses config) ─┐
                                             ├─► generate ─► verify ─► a structured config file, written
   SOW (what to build, in any form)         ─┘
```

The skill is a **generic engine**. It knows nothing about any platform and hardcodes nothing — no node type, no schema, no enum, no naming rule. It learns the platform entirely from the KB at runtime. Point it at a different KB and it produces a different platform's config, with no change to the skill.

## Inputs

| Input | Meaning | Required |
|---|---|---|
| `kb=<dir>` | The platform-specific KB directory (e.g. `outputs/<client>/kb/`). The single source of truth for **how** this platform expresses config. | **Yes** |
| `sow=<path>` | The Statement of Work / solution doc — **what** to build. Any form: prose, `.md`, `.txt`, JSON, YAML, **PDF**, or **DOCX**. The skill extracts and reads it. | **Yes\*** |
| `prompt` / `$ARGUMENTS` | Free-text intent and/or per-build values that refine or override the SOW. | No\* |
| `output=<dir>` | Where to write the config. **Default fallback: `outputs/<client>/generated/`**, where `<client>` is the parent of `kb`. | No |

\*At least one of `sow` or `prompt` must be present — there must be something to build. If both are given, the SOW carries the requirements and the prompt carries refinements/values; reconcile them and **ask if they conflict**.

**Beyond these, assume nothing exists.** No sample artifacts, no reference config, no hidden defaults. If you want one, either (a) read it from the KB, (b) take it from the SOW/prompt, or (c) ask.

## Core principles

1. **Platform-agnostic, always.** Every platform fact — schema, field names, node/event/condition types, enums, naming rules, required vs optional parts, defaults, what counts as valid — comes from the **KB**. The SOW/prompt supplies only *intent and per-build values*. If a fact you need isn't in the KB, you do not know it: ask or flag it, **even if the SOW appears to state it**. **Never invent a platform fact (a field, node type, enum value, constant) from general knowledge or from a mechanic the SOW inlines.**
2. **KB is *how*, the SOW is *what*.** The KB carries the grammar; the SOW carries the specific config to build, expressed using only the KB's constructs. If the SOW spells out a mechanic that conflicts with the KB, the **KB wins** — take the SOW's intent and values, resolve the mechanic from the KB, and **surface the conflict** rather than silently following the SOW.
3. **Verify before you trust.** Derive validity checks from the KB and run them (step 5). A config that is 95% right is broken.
4. **Ask as you go — never force a batch.** See below.

## Asking questions

Ask **only** when the answer would **materially change the config** AND it is **not already answered by the KB or the SOW/prompt**.

- If a reasonable default exists (a KB convention, or an obvious choice), **take it, state the assumption, and keep going.** Reserve real questions for genuine forks where guessing wrong is costly.
- Ask **one or a few tightly-scoped questions at a time**, in the flow of the work — never a wall of speculative questions, never a long checklist at the end.
- **Missing *required* inputs are the one case where a consolidated ask is right** — surface them together, once, before you build, naming each.
- Never ask the operator for platform knowledge that belongs in the KB. If the KB is missing it, say the KB is missing it.

You run **in the main conversation**, so asking mid-flow just works.

## Pipeline

### 1. Learn the platform from the KB
Read the **entire** KB. Determine, from its content alone:
- **What config it enables and in what form** (which format — JSON / XML / YAML / a NodeFlow `.anfx` / etc.). An explicit KB declaration of its target governs.
- **The grammar to obey** — schema, field/symbol catalog, node/event/condition types, vocabulary, naming conventions, required vs optional parts, and any **reference structures** the KB ships (alias→JSON maps, templates, canonical examples) to be used **faithfully, not approximated**.
- **What "valid" means** for this platform — the exact checks step 5 will run.

If the KB doesn't document something you need, **say the KB is missing it** — don't fill the gap from general knowledge.

### 2. Read the SOW and fix the deliverable
Ingest the SOW in whatever form it arrives — prose/`.md`/`.txt` read directly; JSON/YAML parsed; **PDF** extracted with the `pdf` skill; **DOCX** with the `docx` skill — and reduce it to plain requirements. Reconcile with what the KB can produce:
- One clear config → proceed.
- KB supports several and the SOW is ambiguous → ask one quick question.
- SOW asks for something the KB doesn't cover → say so plainly; don't fabricate platform facts.

### 3. Plan the config
Form an internal, platform-neutral spec of what's being built, mapped onto the KB's constructs. Missing a specific → take a KB-supported default and state it, or ask if it's a real fork. **The deliverable is the config itself, not the plan.**

### 4. Generate
Produce the config **strictly** from the KB's grammar / schema / templates / idioms. Use the KB's reference structures **verbatim** where it provides them (an alias→JSON map, a template snippet, a canonical example). Use no platform knowledge that is not in the KB.

**Fixed-per-type constants — copy, never choose or coin.** For any value the KB marks fixed-per-type (data-provider ids, port ids, engine/interpreter identifiers, class discriminators, etc.), copy the **exact value the KB's reference/template gives for that exact type** — including when it is `null`. Do **not** pick an alternative from a documentation "options"/prose list, and do **not** synthesize one by pattern-matching the type's name (e.g. coining `<type>.data.provider`). A documentation "option" attested in **no** known-good example is unverified: a plausible-but-unregistered constant passes structural checks and then crashes the platform at import. When in doubt, prefer the value **attested in a known-good reference flow** over anything that appears only in a comment.

### 5. Verify and repair
Run the validity checks the KB implies:
- Structural / schema validity; required fields present; references resolve; enums and values legal; naming conventions honored.
- **Validate every fixed-per-type constant and enumerated value against the KB's allowed set for that type** — and when the KB ships known-good reference flows, the value must match one **attested** there, not merely something a comment lists as possible. A documented-but-unattested value is a **failed** check: replace it with the attested value or flag it. (This is the silent-invalid class — structurally fine, rejected by the platform.)

Loop **Generate ↔ Verify** until clean or genuinely stuck. Surface anything unresolved with the reason — **never silently ship a failing check.**

### 6. Deliver
Write the config to `output` (default `outputs/<client>/generated/`). Then a short report: **what** was produced and **where**, the **key assumptions** you made, and any **open questions or checks you couldn't satisfy**. On a re-run into an existing `output`, treat it as an **update** — apply only what the new SOW/prompt changes and keep a tiny `manifest.json` (what was built, from which KB + SOW, key assumptions, open items) beside it.

## Deliverable
A structured config file: JSON / XML / YAML / a visual-flow JSON (e.g. NodeFlow `.anfx`) / any file a platform ingests. Validity is structural + schema + reference integrity, graded against the KB (and a known-good reference if the KB names one).

## Never do this
- Never hardcode a platform fact in the skill, or carry one over from a previous run / general knowledge. The KB is the only authority.
- Never invent a field, node type, event, enum value, or constant to make something fit. If the KB lacks it, say so.
- Never emit a generator program or scaffold a project — the deliverable is the **config itself**.
- Never emit a fixed-per-type constant just because documentation lists it as an "option"; use the value attested in a known-good example or flag it.
- Never dump a forced wall of clarifying questions. Ask narrowly, when it matters, as you go.

## Folder layout
```
.claude/skills/config-agent/
└── SKILL.md                 ← this file (router + full config pipeline)

outputs/<client>/
├── kb/         ← the KB (input — produced by kb-builder)
└── generated/  ← the config is written here (+ manifest.json), unless output= overrides
```
