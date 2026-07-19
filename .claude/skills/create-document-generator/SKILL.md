---
name: create-document-generator
description: One-call setup for a reusable document generator. Builds the knowledge base with kb-builder from a team's reference documents, then compiles a reusable generate-<client>-<product-line>-<doctype> skill with document-generator — both in one session. Inputs: inputs=<dir of reference documents> — finished deliverables the team has already issued (past SOWs/BRDs/HLDs as PDF/DOCX), plus any product or process docs; at least one is required. sample=<which one of them the output format must match> — required. client=<firm slug> — the firm that will operate the generator, i.e. the delivery team's own company, not the company its documents are addressed to; the addressee is a per-document value and never appears in a path or a skill name. product_line=<what that team delivers>. Optional mom=<brief> — a MOM, email or call transcript for a live deal; it is not used to build the knowledge base, but once setup finishes this skill offers to generate that document from it. Optional prompt=<any context>. When setup finishes, call the generated skill with a brief to produce each document. Triggers: "set up a document generator", "onboard a {doctype} generator", "build the KB and the {doctype} generator", "create-document-generator".
---

# create-document-generator — one-call setup for a delivery team's document generator

You take a delivery team's **reference documents** and, in **one session**, produce two things: the team's **knowledge base** and a **ready-to-run `generate-<client>-<product-line>-<doctype>` skill**. After this runs once, the operator generates documents by calling that generated skill with a brief — this skill is the one-time setup, not the per-document step.

## Artifact roles

Every artifact plays exactly one of three roles. Classify each one before you use it; the roles are not interchangeable.

| Role | What it is | Where it goes |
|---|---|---|
| **reference document** | A **finished deliverable this team has already issued** — a past SOW, BRD, HLD, proposal as PDF/DOCX. | → the KB (substance) and, for the `sample`, the format spec. **This is what you ask for.** |
| **supporting knowledge** | Product docs, spec sheets, process notes, style guides, pricing sheets — how the team's *offering* works. | → the KB (product knowledge). Welcome, but not a substitute for a reference document. |
| **brief** | A **MOM, call transcript, email thread, or scoping note** — one deal's requirements. | → **set aside.** Never the KB. Offered back at Phase 4. |

**Ask for reference documents. Don't ask for briefs.**

Why briefs stay out of the KB — internal reasoning, not something to recite to the operator: a brief is a *generate-time* input that arrives per document, exactly like the recipient it describes. It isn't knowledge about the team; it's knowledge about one deal. Fold a brief into the KB and that one recipient's requirements start reading as the team's **standard** scope, so every future document inherits them — a silent contamination nothing downstream checks for. A transcript of a team scoping an IVR for one buyer teaches nothing durable about the team; it teaches what that buyer asked for. In one line: **from a reference document the KB learns the substance; from a brief it learns nothing it should keep.**

Operators will hand you a brief anyway — they usually have a live deal in hand and it's the first file they reach for. Don't argue and don't discard it. **Set it aside** (Phase 0.4), mention in one line that you've saved it for later, and offer it back once the generator exists (Phase 4), where it's genuinely useful.

## Who is who — read this before resolving any name

Three different companies appear in this workflow and they are routinely confused for each other.

| Role | Who it is | Where it appears |
|---|---|---|
| **client** | The **firm whose delivery team operates this skill**, and whose format and product knowledge the KB encodes. | KB path `outputs/{client}/kb/`; first component of the generated skill name. |
| **product line** | **What that team delivers** — the offering the documents are about. | Second component of the generated skill name. |
| **recipient** | The company a finished document is **addressed to**. | **Nowhere in setup.** It arrives in the brief at generate time, per document. |

**The recipient is a generate-time value, not a setup-time value** — the same reason briefs are set aside rather than absorbed. One delivery team issues documents to many recipients from **one** generator, so a generator named after a recipient is always a bug: it implies recompiling per deal.

A reference document is addressed to *some* recipient. That's incidental — you're borrowing its layout and structure, not its addressee.

> A team selling IVR writes SOWs for many buyers from **one** skill: `generate-acme-ivr-sow`. Never `generate-contoso-sow`.

If the operator hands you a transcript and says "this one's for Contoso", Contoso is the **recipient**: it isn't the client, it names nothing, and its transcript is a set-aside brief. What you still need is the client, the product line, and a reference document.

## Architecture

You are a **thin orchestrator**. You own no KB-building or format-extraction logic of your own. You run two existing skills in order and pass the output of the first into the second:

1. **`kb-builder`** → builds or extends the client KB from the reference documents.
2. **`document-generator`** → compiles the `generate-<client>-<product-line>-<doctype>` skill from that KB plus the sample.

Both sub-skills pause to ask the operator (kb-builder's gap-question Q&A; document-generator's Tier-1 blocking fields). Because everything runs in this single top-level session, those pauses surface to the operator normally. **Never answer a sub-skill's question on the operator's behalf — surface it and wait.**

```
                         ┌────────────── this skill (one session) ──────────────┐
 reference docs ──┐      │ Phase 1: kb-builder     Phase 2: document-generator   │
                  ├────► │ ref docs ─► KB ───────► KB + sample ─► generate-<…>   │
 sample doc   ────┘      │            outputs/{client}/kb/       .claude/skills/ │
                         │                                                       │
 brief (MOM etc.) ─────► │ ░░ set aside — never reaches the KB ░░ ──────────────►│ Phase 4: "generate it now?"
                         └───────────────────────────────────────────────────────┘
```

## Inputs

| Parameter | Description | Default |
|---|---|---|
| `inputs` | Path to the **reference documents** folder: finished deliverables this team has issued, plus any product/process/spec docs. This is what the KB is built from. | **Required** |
| `sample` | The **one** reference document whose visual format the generated skill must pixel-match. Normally one of the files in `inputs`. Several reference documents are better than one. | **Required — blocking** |
| `client` | Short slug for the **firm operating this skill** (used for the KB path and the skill-name prefix). Accepts `customer` as a legacy alias. | Ask if not inferable |
| `product_line` | Short slug for **what the team delivers** (used as the skill-name middle component) | Ask if not inferable |
| `mom` | Optional. A brief for a live deal. **Not KB material** — set aside and offered at Phase 4. | — |
| `prompt` | Optional free-text: the use case, the target document type, any context | — |
| `output` | Where the KB is written | `outputs/{client}/kb/` |

## Phase 0 — Classify, resolve, gate

Do all of this before any other work. Every halt below is **blocking**: stop, ask the operator, and wait for a real answer.

1. Parse `inputs`, `sample`, `client` (or `customer`), `product_line`, `mom`, `prompt`, `output`.

2. **Classify every file in `inputs`** into one of the three roles above. Judge by what the file *is*, not where it sits: a finished, formatted, branded deliverable is a reference document; a spec or product doc is supporting knowledge; anything conversational or deal-shaped (meeting notes, attendees + decisions + action items, a speaker-labelled transcript, an email thread, a scoping note) is a **brief**.

3. **Gate — reference documents.** You need at least one **finished deliverable of the target document type**: a real past SOW/BRD/HLD/proposal as PDF or DOCX, issued by this team, showing what the generator must produce.
   - If `inputs` holds **zero** reference documents, halt and ask — however many files it holds. Ten transcripts are still zero reference documents, and "there was only one file, so it must be the sample" is the trap.
   - Supporting knowledge doesn't satisfy this gate either: a product spec explains the offering, not the deliverable.
   - Keep the halt short:

     ```
     To build the knowledge base and match your format, I need at least one finished
     {doctype} your team has already issued (PDF or DOCX). Everything here looks like
     {briefs / product docs}.

     Any past one works — I read its layout and structure, not its content. Two or
     more is better: it lets me tell fixed boilerplate from per-document fields.
     ```
   - If the operator's real intent is a single document for a live deal rather than a reusable generator, say so plainly: that's the generated skill's job, not this one. If `generate-<client>-<product-line>-<doctype>` already exists, point them at it and stop.

4. **Set aside every brief.** Record its path and, if you can read it, the recipient it concerns. It takes no further part in Phases 1–2. Do **not** pass it to kb-builder, don't cite it, don't let it inform a single KB fact — not even "harmlessly", and not as an example of what a brief looks like. Any `mom` argument is set aside the same way. Tell the operator in **one line** that you've saved it for the end; don't explain the reasoning unless they ask.

5. **Gate — sample.** Identify the one reference document whose format to match.
   - If `sample` was given, confirm it's a finished deliverable of the target type.
   - If not given and exactly one reference document exists, adopt it and say which.
   - If the choice is ambiguous, halt and ask.
   - **Never substitute a format reference you weren't given.** Not another client's KB, sample, or output; not an existing `generate-*` skill in `.claude/skills/`; not the playbook library; not any "gold standard" elsewhere in the repo; not your own knowledge of what a SOW looks like. **If you find yourself hunting for a format outside the operator's own `inputs`/`sample`, that is the halt condition firing — stop and ask.** Compiling against another team's format silently gives this team a competitor's document identity, and nothing downstream will catch it.

6. **Resolve the `client` slug — the firm, not the recipient.** Take it from `client`/`customer`, else the `inputs` folder name, else the `prompt`. Before accepting it, test it against the "Who is who" table: if the name you resolved is the company a reference document is **addressed to**, or the buyer named throughout a set-aside brief, you've picked up the **recipient** — halt and ask which firm's delivery team this generator belongs to. This slug becomes both the KB path and the skill-name prefix, so a swap here poisons both.

7. **Resolve the `product_line` slug.** Take it from `product_line`, else the `prompt`, else infer it from what the reference documents are consistently *about* — the offering being scoped, not the buyer. If you can't infer it confidently, halt and ask. Don't fall back to the doctype alone, and never to a recipient name.

8. **Echo the resolved plan** before Phase 1, so the operator can catch a swap at a glance:

   ```
   Client (firm):        acme
   Product line:         ivr
   Document type:        sow                    (confirmed in Phase 2)
   Reference documents:  3  → knowledge base
     northwind-sow.pdf     ↳ format sample
     globex-sow.pdf
     ivr-product-spec.pdf
   Set aside:            contoso-call.md        (a brief — offered at the end)
   KB output:            outputs/acme/kb/
   Will compile:         generate-acme-ivr-sow
   ```

## Phase 1 — Build or extend the KB · delegate to `kb-builder`

Carry out the **kb-builder** skill in full, here in this session — do not reimplement or shortcut it:

1. Read `.claude/skills/kb-builder/SKILL.md` and its `pipeline/*.md`, adopt those instructions, and execute them exactly as if `kb-builder` were invoked with `client=<slug>` and an artifacts set containing **only the reference documents and supporting knowledge from Phase 0.2** (plus `prompt` and `output` if provided). The set-aside briefs are not part of that set. If kb-builder's own instructions invite transcripts or MOMs as source material, that invitation does not apply here: Phase 0 already decided what this KB is built from.
2. Let kb-builder run its own recognize → scope → build pipeline, **including its interactive gap-question Q&A**. Present every survivor question to the operator and wait for answers; a BLOCKING question halts the run until answered. Never self-answer.
3. If a KB already exists for this client, kb-builder extends it — that is expected, not an error.
4. On completion, record the KB path it wrote (`output` if given, else `outputs/{client}/kb/`). This path is the handoff to Phase 2.

Do not start Phase 2 until Phase 1 has produced a usable KB directory.

## Phase 2 — Compile the generator · delegate to `document-generator`

Carry out the **document-generator** skill in full, here in this session — do not reimplement or shortcut it:

1. Read `.claude/skills/document-generator/SKILL.md`, adopt those instructions, and execute them exactly as if `document-generator` were invoked with `kb=<KB path from Phase 1> sample=<sample> client=<slug> product_line=<slug>` (pass `output` only if the operator wants the generated skill written somewhere other than `.claude/skills/`).
2. Let document-generator run its full compile: detect the document type (Phase 1.4), extract the sample's pixel-level visual format, and emit `.claude/skills/generate-<client>-<product-line>-<doctype>/SKILL.md`. **Surface its Tier-1 blocking-field halts to the operator; never fabricate a value.**
3. On completion, record the generated skill's exact name and the detected document type.

## Phase 3 — Report

Print the summary, using the real values from Phases 1–2:

```
Setup complete — acme · ivr

  Knowledge base:   outputs/acme/kb/          ({N} files)
  Generated skill:  generate-acme-ivr-sow     (.claude/skills/…)
  Document type:    Statement of Work
  Built from:       3 reference documents
  Format source:    northwind-sow.pdf         (layout only)

Reusable for every SOW this team issues — the company each document is addressed to
comes from the brief, per document.

Next step — call once per document:
  run  generate-acme-ivr-sow  with  mom=<path-to-brief>
  Delivers PDF or DOCX — add format=pdf / format=docx, or it will ask.
```

The generated skill auto-registers on the next `list_skills` / `run_skill` call — no extra install step.

## Phase 4 — Offer to generate from a set-aside brief

**Only if Phase 0.4 set one aside.** Setup is finished and the generator now exists, so the brief is finally usable for what it actually is — a generate-time input. This is the one and only point where this skill may produce a document.

Keep the offer short, and wait for a real answer:

```
You also gave me `contoso-call.md` — a brief for a live deal, so I kept it out of the
knowledge base and saved it for now. It's exactly what the new generator takes.

Generate that SOW from it?

  run  generate-acme-ivr-sow  with  mom=contoso-call.md
```

- **On a yes:** carry out the generated skill in this session with `mom=<set-aside brief>`, surface its own blocking-field questions to the operator — **including its PDF-or-DOCX format question**, which it asks whenever the operator hasn't already named a format — and hand back the document. Don't answer the format question on the operator's behalf.
- **On a no:** stop. The brief stays where it is; the operator runs the generator whenever they want.
- **Either way, the brief never enters the KB.** A "yes" is permission to *generate from* it, not to absorb it.

Never generate without asking. If several briefs are set aside, list them and let the operator pick.

## Critical rules

1. **Orchestrate, don't reimplement.** All KB logic lives in `kb-builder`; all format-extraction and compile logic lives in `document-generator`. This skill only sequences them, decides what reaches them, and passes the KB path across. If a sub-skill's behavior needs changing, change that sub-skill — never fork its logic here.
2. **Reference documents in; briefs set aside.** Ask for finished deliverables, never for MOMs/transcripts/emails. A brief describes one deal, so it teaches the KB nothing it should keep and quietly makes one recipient's requirements read as house standard. Setting aside is not discarding — Phase 4 gives it back, used correctly.
3. **No reference document, no setup. No sample, no compile.** Both are Phase 0 gates and both stop the run. Never let a transcript stand in for either, and never borrow a format from anywhere else (Phase 0.5). Halting to ask costs one message; a generator built on the wrong format, or a KB built on one deal, is a confident, plausible, unrecoverable wrong answer.
4. **Never answer a sub-skill's operator question yourself.** Both sub-skills gate on real operator input (kb-builder gap Q&A; document-generator blocking fields). Surface each question and wait.
5. **Name by client + product line; never by recipient.** One canonical `client` slug and one `product_line` slug flow to both phases, so `outputs/{client}/kb/` and `generate-<client>-<product-line>-<doctype>` agree. The recipient names nothing — it enters at generate time, from the brief.
6. **Setup is the job; generating is an offer.** This skill exists to build the generator. It produces a document only via Phase 4, only from a brief the operator already supplied, and only after they say yes. This is the deliberate two-call UX: set up once, then generate many.
7. **Talk to the operator like a colleague, not a spec.** Ask plainly for what you need; don't recite this skill's internal reasoning, role taxonomy, or rules at them, and don't lecture them about what not to send. The vocabulary here (`client`, `recipient`, `brief`, roles, tiers) is for you. Never name another firm — real client names from elsewhere in this repo, other KBs, or other generated skills must never appear in anything you say or write.
8. **Re-running is safe.** Running this skill again for the same client with a different `sample` or `product_line` extends the KB (via kb-builder) and compiles an additional generator for that document type or line. Existing generated skills keep their names.

## Folder layout

```
inputs (operator-supplied)                     produced by this skill
──────────────────────────                     ──────────────────────
<reference docs>/           ──kb-builder──►     outputs/{client}/kb/         (the KB, self-contained)
<sample document>           ──document-        .claude/skills/
                              generator──►        generate-<client>-<product-line>-<doctype>/SKILL.md

<brief / MOM>               ──set aside───►     never in the KB; offered back at Phase 4
```
