---
name: kb-factory
description: Generate a tailored per-client KB skill from a new client's raw artifacts, using a hand-curated playbook library that encodes recipes for recurring client archetypes. Use when the user provides client inputs (docs, transcripts, sample artifacts) and wants a new `{client}-kb` skill produced. Triggers: "create a kb skill for {client}", "generate a {client}-kb", "build me a skill for {client}'s {deliverable}".
---

# kb-factory

Turns a new client's raw artifacts into a tailored `{client}-kb` skill by applying lessons from past client work.

Each playbook in the library encodes one **client archetype** — a kind of artifact + use case we've seen recur — and a **recipe** for what the generated KB skill should contain when that archetype applies. The matcher reads each playbook's artifact description, decides which fit, and assemble composes the new skill from the fired recipes. When no archetype fits, the run stops and surfaces the no-fit to the operator with a candidate-playbook flag — the operator decides whether to author a playbook before proceeding.

The run is a conversation, not a batch. Ask when something matters and a default could plausibly get it wrong; commit silently when it's clear.

## When to use

- "create a kb skill for {client}"
- "generate a {client}-kb"
- "build me a skill for {client}'s {deliverable}"
- The user hands over a folder of artifacts and asks for a new client KB skill

Not for editing an existing client skill or for one-off deliverables.

## Inputs

- `client_name` — short slug, used to name the generated skill folder
- `artifacts/` — docs, transcripts, samples, code, briefs, reference deliverables
- `target_deliverable` — what the skill should produce (NodeFlow JSON, SOW, BRD, etc.)

## Pipeline

Two phases. Execute in order.

1. **`pipeline/match.md`** — Read each playbook in the library; decide which apply to this client.
2. **`pipeline/assemble.md`** — Compose the new `.claude/skills/{client}-kb/` from the fired playbooks' recipes. If no playbook fired, stop and report the no-fit to the operator.

## Output

`.claude/skills/{client_name}-kb/` — the deliverable skill folder, ready to use.

No drafts, no provenance files, no learning loop. The user runs the new skill on their own artifacts whenever they want.

## The library

Playbooks live in `.claude/kb-factory-library/playbooks/*.md`. One markdown file per client archetype. Format reference: `kb-factory-library/_template.md`.

The library grows manually. Drop a new file in when the same archetype has been seen on 2+ engagements. Current playbooks:

- `nodeflow.md` — Exotel NodeFlow / visual IVR flow artifacts.
- `document-from-template.md` — formal business documents (SOW, BRD, proposal) generated from MOMs / transcripts / emails, matching a reference template.

If no playbook fires on a run, the client is a candidate for a new archetype — assemble flags it at the end.

## Folder layout

```
.claude/
├── skills/
│   ├── kb-factory/                ← this skill
│   │   ├── SKILL.md
│   │   └── pipeline/
│   │       ├── match.md
│   │       └── assemble.md
│   └── {client}-kb/               ← per-client skills (emitted by assemble)
│
└── kb-factory-library/
    ├── _template.md
    └── playbooks/                 ← hand-curated, grows manually
```
