---
name: kb-builder
description: Generate and maintain a per-client knowledge base (KB) directly from a client's raw artifacts, drawing on a hand-curated playbook library of archetype advice. One skill owns the KB's whole lifecycle — first run drafts it from scratch; later runs extend it as new artifacts arrive — and runs the operator gap-question Q&A interactively in the main conversation. Use when an operator provides client inputs (docs, transcripts, sample artifacts) and wants the KB built or updated. Triggers: "build the KB for {client}", "update {client}'s KB", "generate a KB from these artifacts", "extend the {client} KB with this new material".
---

# kb-builder

Turns a client's raw artifacts into a per-client KB at `outputs/{client}/kb/`, and maintains that KB over time. One skill, the whole lifecycle.

It branches on exactly one thing: **does a KB already exist at `outputs/{client}/kb/`?**

- **No KB yet (first run):** decide the archetype from the artifacts, inventory them, align scope with the operator, draft the KB, run the scope-gated gap loop, save.
- **KB exists (update run):** read the existing KB as the authoritative structural baseline (the archetype is inferred from its content), confirm scope is unchanged, analyze only the new artifacts as a delta, fold new facts in, run the gap loop on just the new gaps, save.

```
                          ┌─ no KB     → draft from scratch ─┐
artifacts ─► kb-builder ──┤                                  ├─► outputs/{client}/kb/
            (+ playbooks) └─ KB exists → extend as a delta  ─┘
```

The gap-question Q&A runs **in the main conversation**, so the interactive back-and-forth with the operator just works (a sub-agent couldn't pause to ask).

## Relationship to kb-factory

kb-factory manufactures a per-client `{client}-kb` skill, then that skill produces the KB (a two-step). kb-builder collapses that: it is the single producer and maintainer of the KB — there is no generated per-client skill. Use kb-builder when the KB is the deliverable and you don't need a standalone, portable per-client skill. The two share the same playbook library.

## Why one skill works without a frozen recipe

A generated per-client skill froze this client's recipe so updates replayed a known structure. kb-builder drops that, so **something else must be the structural source of truth on updates** — and that is the **KB itself**. Its files, vocabulary, and structure already encode the archetype and the established shape. An update run reads the existing KB, infers the archetype and structure directly from that content, and conforms new facts to it, without re-matching. That, plus the anti-drift rule, keeps the KB consistent run-over-run.

One trade-off to accept consciously: kb-builder consults the playbooks on every run, so playbook improvements reach update runs too (a generated skill was frozen against that). Usually a feature; the KB-as-source-of-truth rule keeps it from reshaping settled structure.

## Inputs

- `inputs=<dir>` — the artifacts folder (docs, transcripts, samples, code, reference deliverables). **Required.**
- `prompt` — optional free-text describing the use case or any important context.
- `output=<dir>` — where the KB is written. Defaults to `outputs/{client}/kb/`, where `{client}` is inferred from the inputs folder name (or the prompt).

## Pipeline

Three phases. Execute in order.

1. **`pipeline/recognize.md`** — detect whether a KB already exists. On a first run, the LLM decides which archetype(s) apply by matching the playbook library against the artifacts (it never asks the operator). On an update, it infers the archetype and structure from the existing KB's own content (no re-match).
2. **`pipeline/scope.md`** — understand the artifacts' anatomy, derive the requirement from the operator's prompt, and **lock the scope** (requirement + in scope + out of scope). Ask only when the prompt and artifacts leave real ambiguity. Everything downstream obeys this scope.
3. **`pipeline/build.md`** — deep-extract the in-scope components, draft or extend the KB conforming to the established structure, run the scope-gated gap loop, then save.

## The playbook library

Archetype advice lives in `.claude/kb-factory-library/playbooks/*.md` (shared with kb-factory; **read-only**). Each playbook holds recognition signals, what-to-look-for tips, common pitfalls, useful gap-questions, typical KB shapes, and skip-entirely categories. Playbooks are **advice, not recipes** — kb-builder composes the actual KB by analyzing this client's real artifacts, *informed* by the playbook.

Current playbooks: `nodeflow`, `document-from-template`, `api-integration`, `fallback` (the exclusion-only fallback for first-of-kind clients).

## Critical rules

1. **On update, the existing KB's structure is authoritative — extend it, don't reshape it.** New facts conform to the established containers / field paths / file shape. No renaming or re-bucketing of settled content.
2. **Scope first, then ask only what matters, but do ask.** The scope phase (`scope.md`) locks the requirement and what's in/out of scope before drafting, asking only when the prompt and artifacts leave ambiguity. In the gap loop, drop only questions that are out of scope, already answered by the artifacts, or that can't change the KB; **present every survivor to the operator and wait for answers before finalizing.** A safe default is not a reason to skip a question: surface it as a VERIFY ASSUMPTION with your proposed default. Never self-resolve all gaps into assumptions and save, and never guess a BLOCKING answer. **Whenever you have questions for the operator, display all of them as one severity-grouped list (BLOCKING first) and wait for the operator's input before proceeding** — don't drip them out across turns or proceed on the non-blocking ones without a reply; the relevance gate, not round-by-round rationing, is what keeps the list short, so don't pad it with the playbook's example questions. **A BLOCKING question halts the run** until the operator actually answers or explicitly waives it; a promise to supply a missing input later (e.g. "I'll share the palette export") does **not** count as resolved — pause and wait for that input to arrive. The gap log only **records** items the operator explicitly deferred or that no source can answer; it is never where an open BLOCKING question goes so the run can proceed. (This is about missing artifact *content*, not archetype selection.)
3. **Record observed values verbatim** — node types, event names, headings, vocabulary as they appear in the artifacts. Don't paraphrase.
4. **If artifacts disagree among themselves, surface to the operator and resolve before saving.**
5. **If new artifacts reveal a shape the existing KB can't account for, surface it** to the operator (it may be a genuinely new structure) rather than forcing it into the old shape.
6. **Leak no internal meta into the KB.** No archetype/playbook names, KB filenames, section codes, or constraint IDs in recorded content. The KB's content alone conveys the archetype and structure, both to downstream deliverables and to a future update run.
7. **Decide the archetype yourself — never ask the operator which to use.** Pick the applicable playbook(s) from the artifacts; if nothing specific fits, use the fallback automatically.
8. **The KB must be self-contained — bundle every file it references.** If any KB file points to a supporting artifact (a node-template / palette export, a schema file, a query/template library, a reference example the generator must read), **copy that artifact into `outputs/{client}/kb/` and reference it by its bundled relative path.** Never reference an external, working-directory, or absolute path that can move or be missing when the KB is consumed — a downstream consumer (e.g. `config-agent`, `code-agent`, or `api-agent`) is handed only the KB directory, so a referenced-but-absent file is a dangling dependency that breaks generation. At save time, scan the KB for references to anything outside the directory; bundle each one. If a referenced artifact can't be located or copied, treat it as a BLOCKING gap and surface it — never save a KB with a dangling reference.

## Folder layout

```
.claude/
├── skills/
│   └── kb-builder/
│       ├── SKILL.md
│       └── pipeline/
│           ├── recognize.md
│           ├── scope.md
│           └── build.md
└── kb-factory-library/
    └── playbooks/        ← shared archetype advice (read-only)

outputs/
└── {client}/
    └── kb/               ← the KB this skill produces and maintains
```

## Output

- `outputs/{client}/kb/` — the KB (first run: drafted; later runs: extended).
