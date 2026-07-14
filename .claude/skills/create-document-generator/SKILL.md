---
name: create-document-generator
description: One-call setup for a per-client document generator. From a client's raw artifacts it builds (or extends) the knowledge base with kb-builder, then compiles a reusable generate-<client>-<doctype> skill with document-generator — both in a single session, handing the KB from the first step to the second. Use when onboarding a new client or document type from scratch and you want the KB and the generator produced together in one go, instead of running kb-builder and document-generator as separate manual steps. When it finishes, you call the generated generate-<client>-<doctype> skill with a MOM/brief to produce each document. Inputs: inputs=<artifacts dir>, sample=<one format-reference document>, optional customer / prompt. Triggers: "set up a document generator for {client}", "onboard {client} from these artifacts", "build the KB and the {doctype} generator for {client}", "create-document-generator".
---

# create-document-generator — one-call setup for a per-client document generator

You take a client's raw artifacts and a single sample document and, in **one session**, produce two things: the client's **knowledge base** and a **ready-to-run `generate-<client>-<doctype>` skill**. After this runs once, the operator generates documents by calling that generated skill with a MOM/brief — this skill is the one-time setup, not the per-document step.

You are a **thin orchestrator**. You own no KB-building or format-extraction logic of your own. You run two existing skills in order and pass the output of the first into the second:

1. **`kb-builder`** → builds or extends the client KB from the raw artifacts.
2. **`document-generator`** → compiles a per-client `generate-<client>-<doctype>` skill from that KB plus one sample document.

Both sub-skills pause to ask the operator (kb-builder's gap-question Q&A; document-generator's Tier-1 blocking fields). Because everything runs in this single top-level session, those pauses surface to the operator normally. **Never answer a sub-skill's question on the operator's behalf — surface it and wait.**

```
                        ┌─────────────── this skill (one session) ───────────────┐
 raw artifacts ──┐      │  Phase 1: kb-builder      Phase 2: document-generator   │
                 ├────► │  artifacts ─► KB ──────►  KB + sample ─► generate-<...>  │ ─► call generate-<client>-<doctype>
 sample doc  ────┘      │              outputs/{client}/kb/       .claude/skills/  │      with mom=<brief>  → the document
                        └─────────────────────────────────────────────────────────┘
```

## Inputs

| Parameter | Description | Default |
|---|---|---|
| `inputs` | Path to the raw artifacts folder for the KB (docs, transcripts, samples, reference deliverables) | Required |
| `sample` | Path to the **one** document whose visual format the generated skill must match (a SOW, BRD, HLD, proposal, etc.). May be one of the files inside `inputs`. | Required |
| `customer` | Short client slug (used for the KB path and the generated skill name) | Inferred from `inputs` folder name or `prompt` |
| `prompt` | Optional free-text: the use case, the target document type, any context | — |
| `output` | Where the KB is written | `outputs/{client}/kb/` |

## Phase 0 — Resolve inputs and gate

1. Parse `inputs`, `sample`, `customer`, `prompt`, `output` from the invocation arguments.
2. Confirm the `inputs` folder exists and is non-empty. If it is missing or empty, **halt and ask** for the artifacts.
3. Resolve **one canonical client slug** (from `customer`, else the `inputs` folder name, else the `prompt`). Use this same slug for both sub-skills so the KB path and the generated skill name stay consistent.
4. Identify the `sample`. If none was given and exactly one obvious format-reference deliverable exists in `inputs`, use it and state which. If it is ambiguous or absent, **halt and ask which file is the format reference** — never guess.
5. Echo the resolved plan back to the operator (client slug, artifacts dir, sample file, KB output path) before starting Phase 1.

## Phase 1 — Build or extend the KB  ·  delegate to `kb-builder`

Carry out the **kb-builder** skill in full, here in this session — do not reimplement or shortcut it:

1. Read `.claude/skills/kb-builder/SKILL.md` and its `pipeline/*.md`, adopt those instructions, and execute them exactly as if `kb-builder` were invoked with `inputs=<inputs>` (plus `prompt` and `output` if provided).
2. Let kb-builder run its own recognize → scope → build pipeline, **including its interactive gap-question Q&A**. Present every survivor question to the operator and wait for answers; a BLOCKING question halts the run until answered. Never self-answer.
3. If a KB already exists for this client, kb-builder extends it — that is expected, not an error.
4. On completion, record the KB path it wrote (`output` if given, else `outputs/{client}/kb/`). This path is the handoff to Phase 2.

Do not start Phase 2 until Phase 1 has produced a usable KB directory.

## Phase 2 — Compile the per-client generator  ·  delegate to `document-generator`

Carry out the **document-generator** skill in full, here in this session — do not reimplement or shortcut it:

1. Read `.claude/skills/document-generator/SKILL.md`, adopt those instructions, and execute them exactly as if `document-generator` were invoked with `kb=<KB path from Phase 1> sample=<sample> customer=<slug>` (pass `output` only if the operator wants the generated skill written somewhere other than `.claude/skills/`).
2. Let document-generator run its full compile: detect the document type (Phase 1.4), extract the sample's pixel-level visual format, and emit `.claude/skills/generate-<client>-<doctype>/SKILL.md`. **Surface its Tier-1 blocking-field halts to the operator; never fabricate a value.**
3. On completion, record the generated skill's exact name (`generate-<client>-<doctype>`) and the detected document type.

## Phase 3 — Report and hand off

Print the summary, using the real values from Phases 1–2:

```
Setup complete for {client}
  Knowledge base:    outputs/{client}/kb/          ({N} files)
  Generated skill:   generate-<client>-<doctype>   (.claude/skills/…)
  Document type:     {document_type_name}

Next step — reusable, call once per document:
  run  generate-<client>-<doctype>  with  mom=<path-to-brief>
```

The generated skill auto-registers on the next `list_skills` / `run_skill` call — no extra install step.

## Critical rules

1. **Orchestrate, don't reimplement.** All KB logic lives in `kb-builder`; all format-extraction and compile logic lives in `document-generator`. This skill only sequences them and passes the KB path across. If a sub-skill's behavior needs changing, change that sub-skill — never fork its logic here.
2. **One session, fixed order.** KB first, compile second. Run both in this single session so the KB written in Phase 1 is on disk for Phase 2 to read, and so the operator's answers reach the right sub-skill.
3. **Never answer a sub-skill's operator question yourself.** Both sub-skills gate on real operator input (kb-builder gap Q&A; document-generator blocking fields). Surface each question and wait.
4. **One canonical client slug** flows to both phases, so `outputs/{client}/kb/` and `generate-<client>-<doctype>` agree.
5. **Halt on a missing/ambiguous sample.** The sample is the format reference; if you cannot identify exactly one, ask — do not guess.
6. **Stop after Phase 3.** This skill sets up the generator; it does **not** produce a document. Generating a document is the generated skill's job, called separately with a MOM. This is the deliberate two-call UX: setup once, then generate many.
7. **Re-running is safe.** Running this skill again for the same client with a different `sample` extends the KB (via kb-builder) and compiles an additional `generate-<client>-<doctype>` skill for that document type. Existing generated skills keep their names.

## Folder layout

```
inputs (operator-supplied)                     produced by this skill
──────────────────────────                     ──────────────────────
<artifacts dir>/            ──kb-builder──►     outputs/{client}/kb/         (the KB, self-contained)
<sample document>           ──document-        .claude/skills/
                              generator──►        generate-<client>-<doctype>/SKILL.md   (the reusable generator)
```
