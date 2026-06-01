---
name: kb-factory
description: Generate a tailored, self-contained per-client KB skill from a new client's raw artifacts, drawing on a hand-curated playbook library that holds analysis advice for recurring client archetypes. Use when the user provides client inputs (docs, transcripts, sample artifacts) and wants a new `{client}-kb` skill produced. Triggers: "create a kb skill for {client}", "generate a {client}-kb", "build me a skill for {client}'s {deliverable}".
---

# kb-factory

Turns a new client's raw artifacts into a tailored, self-contained `{client}-kb` skill. That's its only job.

## What this skill does and doesn't do

- **Does**: read the artifacts, pick the right playbook(s) from the library, actually analyze the artifacts (informed by playbook advice + general inference), compose a self-contained `{client}-kb/SKILL.md` that captures everything the runtime needs.
- **Doesn't**: produce the KB. The KB at `outputs/{client}/kb/` is generated *by the generated skill* when the operator later invokes it against artifacts (first invocation: draft from scratch; subsequent invocations: extend the existing KB).

```
playbooks  ──►  kb-factory   ──►  {client}-kb skill  (self-contained, tailored)
              (analyzes artifacts,             │
               composes the skill)             ▼  (on every invocation by the operator)
                                       outputs/{client}/kb/
                                       (first run: drafted; later runs: extended)
```

## What playbooks are (and aren't)

Playbooks are **analysis advice and lessons learned** for a recurring client archetype. They are not recipes the generated skill copies from. The generated skill is Claude's inferred recipe composed by analyzing this client's actual artifacts, *informed* by the playbook's domain advice.

A playbook holds:

- **Recognition signals** — how to spot artifacts of this archetype (used by match step).
- **What to look for when analyzing** — domain-specific tips on what details matter, what gets missed, what to enumerate carefully.
- **Common pitfalls** — anti-patterns past engagements hit. Candidates for critical rules in the generated skill.
- **Useful questions** — gap-question phrasings that worked before. Examples, not prescriptions.
- **Typical KB shapes that have worked** — past file lists for reference. The generated skill decides what shape *this* client actually needs.
- **Skip-entirely categories** — what's typically out of scope for the archetype.

Playbooks are **used by kb-factory at generation time only**. Generated skills do not dereference playbooks at runtime — they are self-contained.

## When to use

- "create a kb skill for {client}"
- "generate a {client}-kb"
- "build me a skill for {client}'s {deliverable}"
- The user hands over a folder of artifacts and asks for a new client KB skill

Not for editing an existing client skill or for one-off deliverables.

## Inputs

- `client_name` — short slug, used to name the generated skill folder
- `artifacts/` — docs, transcripts, samples, code, briefs, reference deliverables (the seed corpus kb-factory analyzes)
- `target_deliverable` — what the downstream agent should eventually produce (NodeFlow JSON, SOW, BRD, etc.)

## Pipeline

Two phases. Execute in order.

1. **`pipeline/match.md`** — Read each playbook's recognition signals; decide which apply. Multiple specific playbooks can fire. If none fire, surface to operator and (with confirmation) carry the fallback playbook forward.
2. **`pipeline/assemble.md`** — Analyze the artifacts (informed by the fired playbook's advice + general inference), compose a self-contained `{client}-kb/SKILL.md` that bakes in this client's structural specifics, then flag candidate-playbook updates.

## What lives where (load-bearing)

The architecture only earns its keep if these layers stay disciplined.

| Layer | Content | Reused across clients? |
|---|---|---|
| **Playbook** (`.claude/kb-factory-library/playbooks/*.md`) | Archetype-wide analysis advice: recognition signals, what to look for, common pitfalls, useful questions, typical KB shapes, skip-entirely categories | **Yes** — every kb-factory run against a similar client benefits |
| **Generated `{client}-kb`** (`.claude/skills/{client}-kb/SKILL.md`) | Self-contained, Claude-composed recipe tailored to *this* client. Vendor-specific recognition signals + container key names + field paths + KB file list + critical rules + gap-question templates. Everything the runtime needs to produce / extend the KB. | No |
| **KB** (`outputs/{client}/kb/`) | The client-specific facts the runtime extracted — observed node types, event names, headings, vocabulary, etc. Also the deliverable downstream agents consume. | No — produced at runtime, extended over invocations |

**The discipline question, asked at every observation during assembly:** *would this apply to a different client of the same archetype?*

- **Yes** → archetype-wide. It belongs in the playbook, not in the per-client skill. If the playbook doesn't carry it yet, **flag as a candidate playbook update at end of run**. Do not silently bake it into the per-client skill — that strands the learning.
- **No** → client-specific. Either lands in the generated `{client}-kb/SKILL.md` (if it's a recipe/instruction for the runtime) or will land in the KB (if it's an observed value the runtime will record).
- **Unsure** → write it where it goes AND flag as a candidate. The operator decides whether to promote.

The risk this defends against: cross-client learnings drift into per-client skills, the library never grows, and every new similar client starts from the same impoverished playbook. The candidate-playbook flag is the mechanism that keeps the library learning.

## Output

- `.claude/skills/{client_name}-kb/SKILL.md` — the self-contained generated skill.
- A short list of candidate-playbook flags for the operator (zero or more lines).

No KB. No drafts. No intermediate files.

## The library

Playbooks live in `.claude/kb-factory-library/playbooks/*.md`. One markdown file per archetype. Format reference: `kb-factory-library/_template.md`.

The library grows manually. Add a playbook after seeing the archetype on 2+ engagements. Current playbooks:

- `nodeflow.md` — visual flow JSON: nodes + transitions + embedded scripts (any vendor of this archetype).
- `document-from-template.md` — formal business documents (SOW, BRD, proposal) generated from MOMs / transcripts / emails, matching a reference template.
- `fallback.md` — special **fallback playbook** (`fallback: true` in front matter). Fires only when no specific playbook matches. Carries discovery-oriented advice for first-of-kind clients.

Specific playbooks are **vendor-agnostic** in their advice. Vendor-specific fingerprints (exact constants, exact field names, exact node-type lists) are not in the playbook — they're things the generated skill bakes in after kb-factory analyzes a particular client's artifacts.

Every fallback run is a strong candidate for promotion into a new specific playbook — assemble surfaces the candidate-archetype flag at end of run.

## Folder layout

```
.claude/
├── skills/
│   ├── kb-factory/                ← this skill
│   │   ├── SKILL.md
│   │   └── pipeline/
│   │       ├── match.md
│   │       └── assemble.md
│   └── {client}-kb/               ← self-contained generated skill
│       └── SKILL.md
│
└── kb-factory-library/
    ├── _template.md
    └── playbooks/                 ← hand-curated, grows manually
```

## Re-running kb-factory for an existing client

Self-contained generated skills don't auto-pick-up library improvements. When a playbook gains a new tip or pitfall, only future kb-factory runs benefit. To refresh an existing client's skill, re-run kb-factory for that client — it re-analyzes artifacts using the current playbook and rewrites the generated skill. This is the price of self-containment; library updates are deliberate, refreshes are deliberate.
