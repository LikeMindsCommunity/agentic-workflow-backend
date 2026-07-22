---
name: document-generator
description: From a delivery team's Knowledge Base (KB) plus a MOM/brief for one deal, generate the finished business DOCUMENT the KB describes — a SOW, BRD, HLD, proposal, implementation guide or any structured deliverable — written fresh in that team's exact measured format and delivered as PDF or DOCX. The KB carries the team's format spec (palette, typography, page geometry, table styles, flowchart vocabulary), its verbatim boilerplate, its section order and render order, and its product knowledge; the MOM carries only this one recipient's requirements. Every format fact comes from the KB and is used as measured — nothing is re-derived, eyeballed, or borrowed from another team. Asks before writing whether the deliverable is PDF or DOCX and whether flow diagrams are drawn or left as placeholders, unless the KB or the request already answers. Reusable for every document this team issues — the company each one is addressed to arrives in the MOM, per document. Use when an operator points at a KB + a brief and wants the document written. Inputs: kb=<dir> (required), mom=<path> (required), format=pdf|docx, diagrams=draw|placeholder, output=<dir>. Triggers: "generate the {doctype} from this KB and brief", "write the SOW for {recipient}", "draft the BRD as a Word doc", "document-generator".
---

# document-generator

Turn a **team's KB** + a **MOM** (the brief for one deal, in any form) into that team's **finished document**, rendered in their measured format and verified against it.

```
   KB  (how this team's documents look, read, and are built) ─┐
                                                              ├─► compose ─► render ─► verify ─► the document
   MOM (what this one deal needs, in any form)               ─┘
```

The skill is a **generic engine**. It knows nothing about any team and hardcodes nothing — no colour, no font, no heading string, no boilerplate, no section order. It learns the team entirely from the KB at runtime. Point it at a different KB and it produces a different team's document, with no change to the skill.

## Inputs

| Input | Meaning | Required |
|---|---|---|
| `kb=<dir>` | The team's KB directory (e.g. `outputs/<client>/kb/`), built by `kb-builder`. The single source of truth for **how** this team's documents look and read, and for the product knowledge behind them. | **Yes** |
| `mom=<path>` | The MOM / brief / call transcript / email thread — **what** this one document must say. Any form: prose, `.md`, `.txt`, **PDF**, or **DOCX**. The skill extracts and reads it. | **Yes\*** |
| `prompt` / `$ARGUMENTS` | Free-text intent and per-document values that refine or override the MOM. | No\* |
| `format=pdf\|docx` | The deliverable format. Answers the Phase 0.1 gate so it is not asked. | No |
| `diagrams=draw\|placeholder` | Whether flow/process diagrams are drawn or left as marked placeholders. Answers the Phase 0.2 gate so it is not asked. | No |
| `output=<dir>` | Where the document is written. **Default fallback: `outputs/<client>/documents/`**, where `<client>` is the parent of `kb`. | No |

\*At least one of `mom` or `prompt` must be present — there must be something to write about. If both are given, the MOM carries the requirements and the prompt carries refinements; reconcile them and **ask if they conflict**.

**Beyond these, assume nothing exists.** No sample document, no format reference, no hidden defaults. Everything about the team's format comes from the KB.

## Who is who

Two different companies appear in every run and they are routinely confused.

| Role | Who it is | Where it comes from |
|---|---|---|
| **the team** | The firm whose KB this is and who issues the document. Their format, boilerplate, and product knowledge. | the KB |
| **the recipient** | The company this one document is **addressed to**. Their name, requirements, flow, decisions, dates. | the MOM, per document |

One KB serves every recipient this team writes to. A fact about the recipient never enters the KB, and a fact about the team never comes from the MOM.

## Core principles

1. **KB is *how*, the MOM is *what*.** Every format fact — palette, typography, page geometry, table styles, heading strings, boilerplate, section order, render order, flowchart vocabulary — comes from the **KB**, already measured. The MOM supplies only this recipient's requirements and values. If the MOM states a format fact that conflicts with the KB, the **KB wins**: take the MOM's intent, resolve the format from the KB, and **surface the conflict**.
2. **Measured values are used as measured.** The KB's numbers were sampled from the team's own reference document — pixel-sampled hex codes, pt sizes, inch margins. Use them exactly. Never re-derive a value you could read, never round one to something tidier, and never substitute one that "looks right". If a value you need is missing from the KB, **say the KB is missing it** — do not fill the gap from general knowledge.
3. **Never borrow a format.** Not from another team's KB, not from a document elsewhere in the repo, not from your own idea of what a SOW or BRD looks like. If you find yourself reaching outside this KB for a format fact, that is the halt condition — stop and say so. A document rendered in another firm's identity is a confident, plausible, wrong result that nothing downstream catches.
4. **Only the VARIABLE tier is written fresh.** The KB classifies every piece of content into tiers (below). Boilerplate is copied with placeholder substitution; reference tables are inserted whole; standard images are embedded. Writing fresh prose where the KB recorded a fixed string produces a wrong document every single run.
5. **Verify before you deliver.** Run the checks in Phase 5 and fix what they find. A document that is 95% right is a document that gets rejected without the reviewer being able to say why.
6. **Ask as you go — never force a batch.** See below.

## Asking questions

Ask **only** when the answer would **materially change the document** AND it is **not already answered by the KB or the MOM/prompt**.

- If a reasonable default exists (a KB convention, an obvious choice), **take it, state the assumption, and keep going.** Reserve real questions for genuine forks where guessing wrong is costly.
- **The three hard gates in Phase 0 are the exception** — format, diagram provenance, and missing BLOCKING MOM fields are never defaulted. They go out **together, in one block, before anything is written**, and the run stops for the answers.
- Never ask the operator for format knowledge that belongs in the KB. If the KB is missing it, say the KB is missing it.

You run **in the main conversation**, so asking mid-flow just works.

---

## PHASE 0 — Gates, audit, and the deliverable's name

Nothing is written until this phase closes. Everything below is resolved **in one question block**, so one document costs the operator one interruption, not three.

### 0.1 — Resolve the output format (hard gate)

Resolution order:

0. **A KB house policy wins first.** If the KB records `format_policy` as `pdf` or `docx`, the team already decided: use it, state it in the audit summary, do not ask.
1. **An explicit instruction wins next.** A `format=` argument; a phrasing in the operator's request ("as a Word doc", "give me the PDF", "send it as .docx"); or an explicit statement in the MOM ("deliverable: PDF"). Match case-insensitively; treat `word` / `.docx` / `doc` as DOCX.
2. **Otherwise ASK, and stop.** There is no default. Do not pick one, do not start writing, do not "proceed with PDF and convert later" — there is no converter in the runtime.

What does **not** count as being told: the format of the KB's own reference document, the format of a document produced earlier, the extension in an output path, "whatever's easiest", or an operator who is clearly in a hurry.

Record `OUTPUT_FORMAT`. Phase 4 then runs **only** the matching pipeline.

### 0.2 — Resolve diagram provenance (hard gate)

Applies whenever the document can carry a diagram at all — the KB records a `flowchart_vocabulary`, a section-image catalogue, or a non-zero diagram count. Skip it only for document types with no diagram surface anywhere.

- If the KB records `diagram_policy` as `draw` or `placeholder`, that is the team's standing decision — record it, do not ask.
- If the operator already said (`diagrams=` argument, "draw the call flow", "I'll add the diagrams"), record it, do not ask.
- Otherwise ASK and stop. Do not draw "a first pass they can replace", and do not leave a placeholder because drawing looks hard.

Both answers are routine and guessing wrong is expensive in both directions: a drawn diagram that contradicts the operator's real flow is worse than a blank box, and a blank box in a document that was meant to be complete is a broken deliverable that ships.

Record `DIAGRAM_MODE`:

- **draw** — build every diagram from the KB's `flowchart_vocabulary`, honouring its shape and label contracts. A flow the MOM does not describe well enough to draw is a `[Q-N: ...]` gap, not an invented flow.
- **placeholder** — render the styled placeholder block at each diagram's position, and list every one in the closing summary with its section and caption, so the operator knows exactly what to insert and where.

Images the KB classified `REUSABLE_STANDARD` are unaffected by this gate — they are the team's own fixed assets and are always embedded.

### 0.3 — Audit the MOM

Read the MOM in whatever form it arrives (prose/`.md`/`.txt` directly; **PDF** via the `pdf` skill; **DOCX** via the `docx` skill). Then check it against the KB's input checklist:

1. Every **BLOCKING** field present, using the KB's extraction signals. Missing ones go into the question block, or — if the operator wants a draft anyway — become `[Q-N: ...]` placeholders in DRAFT mode. **Never silently assume a BLOCKING value.**
2. **IMPORTANT** fields missing: warn, apply the KB's recorded default, continue.
3. **OPTIONAL** fields: use if present.

### 0.4 — Resolve the recipient and the filename

The recipient is a BLOCKING field (it is the company the document is addressed to), so it is in hand by now. Carry it forward as the filename stem rather than re-deriving it later:

```
<recipient>_<DOC_TYPE>.<ext>
```

- `<recipient>` — from the MOM. Not the team, not the KB's reference document's addressee. This is the whole point of the name: one KB produces many documents and the operator tells them apart by who each is for.
- `<DOC_TYPE>` — the KB's doc type slug, uppercased: `SOW`, `BRD`, `HLD`.
- `<ext>` — follows `OUTPUT_FORMAT`.

So `SwiftTrack Logistics_SOW.pdf`, `Contoso_BRD.docx`. Both halves are run-time values.

```python
import re

def deliverable_name(recipient: str, doc_type: str, output_format: str) -> str:
    # Keep the recipient as the MOM writes it — spaces included — but strip the
    # characters that are illegal in a filename or would break the cleanup glob.
    clean = re.sub(r'[/\\:*?"<>|]', "", recipient or "").strip()
    clean = re.sub(r"\s+", " ", clean)
    # No recipient means DRAFT mode; fall back rather than emit "_SOW.pdf".
    stem = f"{clean}_{doc_type}" if clean else f"DRAFT_{doc_type}"
    return f"{stem}.{output_format}"
```

### 0.5 — Print the audit summary

State the resolved format, the diagram mode, the fields found and missing, and **the filename this run will produce**, before proceeding.

---

## PHASE 1 — Learn the team from the KB

Read the **entire** KB. Determine, from its content alone:

- **The format spec** — the measured record of page geometry, strips, header, footer, cover, heading levels, table styles, body, lists, inline emphasis, special elements, the colour palette with its semantic tokens, the bundled assets, and (where present) the flowchart vocabulary. Read it whole; you will hand its values to Phase 4.
- **The document's structure** — every section in order, with its heading string recorded character-for-character, and which sections are mandatory, optional, or conditional.
- **The content model** — for each section, which tiers apply and the **render order** of their blocks on the page.
- **The boilerplate** — verbatim strings with their placeholder maps.
- **The reference data** — standard tables with their full row data.
- **The assets** — which images are the team's own standard and which are per-document.
- **The product knowledge** — what the team sells, what each module does, what each section is *for*, the standard terms, the voice and vocabulary.
- **The patterns** — the if-then rules mapping MOM signals to document variants.
- **The constraints** — what makes a generated document invalid. These become Phase 5's checks.

If the KB doesn't document something you need, **say the KB is missing it**. Do not fill the gap from general knowledge, and do not go looking for it in another KB.

## PHASE 2 — Select the pattern

Apply the KB's pattern rules to the MOM. These are explicit if-then signals, not judgment calls: if the KB says a signal selects a variant, that signal decides. State the choice and why:

```
Pattern selected: <name>   (signal in the MOM: "<the phrase that matched>")
Sections included: ...     Sections excluded: ...
```

If no rule matches, take the KB's default pattern and say so. If two rules match and disagree, that is a real fork — ask.

## PHASE 3 — Compose the document

Walk the sections in the KB's recorded order. For each, render its blocks in the KB's recorded **render order** — not in the order the tiers happen to be listed, and not in an order that seems natural.

The tiers, and what each one permits:

| Tier | What it is | What you do with it |
|---|---|---|
| `FIXED_LEGAL` | The team's legal/compliance text | Copy **verbatim**. Substitute nothing but the recipient's name where the KB marks it. |
| `BOILERPLATE_TEMPLATE` | Fixed structure with marked placeholders | Copy **verbatim**, substitute only the listed `[PLACEHOLDERS]` from their recorded sources. Pure string substitution — never compose, never paraphrase. |
| `STRUCTURED_REFERENCE_DATA` | The team's standard tables | Insert **all** rows exactly as recorded. Never re-derive, never summarise, never "include representative fields". A truncated table here is a truncated table in the deliverable. |
| `SECTION_IMAGE_STANDARD` | The team's reusable diagrams | Embed the bundled asset at the recorded position. |
| `VARIABLE` | This recipient's content | **The only tier you write.** Synthesise the KB's product knowledge with the MOM's requirements, in the KB's recorded voice. |

**Heading strings are copied from the KB character-for-character** — capitalisation, punctuation, ampersands, colon spacing, numbering format. `Prerequisites & Licenses` is not `Prerequisites and Licenses`; `Notes :` is not `Notes:`. These conventions are the team's identity and paraphrasing them is this archetype's most common failure.

**Nothing is carried over from the KB's reference document's own content.** Its wording, its client's requirements, its approval matrices, its configuration decisions belong to a past deal and are irrelevant to this one. The KB separates format and boilerplate (reusable) from that document's variable content (not reusable) — respect the line it drew.

Diagrams follow `DIAGRAM_MODE` from Phase 0.2.

## PHASE 4 — Render

Run **exactly one** pipeline, chosen by `OUTPUT_FORMAT`. Read only that pipeline's reference file:

| `OUTPUT_FORMAT` | Read | Produces |
|---|---|---|
| `pdf` | `reference/render-pdf.md` | HTML/CSS authored from the KB's format spec → Chrome headless (WeasyPrint fallback) |
| `docx` | `reference/render-docx.md` | python-docx, cloning the KB's bundled reference when it is a `.docx` |

**Fidelity is asymmetric and the summary must say so.** The format matching the KB's own reference document reproduces it directly; the other is a rebuild from the measured spec that matches palette, typography, geometry, and section order but may differ in minor spacing and pagination. Say which one the operator is getting when it is not the native one. Never refuse the non-native format.

## PHASE 5 — Verify

**Format**
- [ ] `OUTPUT_FORMAT` was resolved by KB policy or an explicit instruction, never defaulted
- [ ] The deliverable is named `<recipient>_<DOC_TYPE>.<ext>`, recipient from the MOM, `<ext>` matching `OUTPUT_FORMAT`
- [ ] The recipient in the filename is the same company the document is addressed to inside it
- [ ] If this is not the KB's native format, the completion summary says so

**Content**
- [ ] Every BLOCKING field populated — no `[Q-N: ...]` placeholders left outside declared DRAFT mode
- [ ] The selected pattern's sections are all present, in the KB's order, none extra
- [ ] Heading strings match the KB character-for-character
- [ ] Boilerplate is verbatim with only placeholders substituted — nothing paraphrased
- [ ] Reference tables carry **all** their rows
- [ ] No content carried over from the KB's reference document
- [ ] The recipient's name is used consistently, and no other company's name appears anywhere
- [ ] Product claims are accurate for this engagement type per the KB
- [ ] Every constraint the KB records is satisfied

**Visual — PDF path**
- [ ] Colours match the KB's palette hex values exactly
- [ ] Strips, header, footer, and margins match the measured spec
- [ ] Each heading level uses its own recorded colour and size — no level borrowing another's token
- [ ] Table styles match per table type, including the striping decision
- [ ] Cover title block within 5% vertical tolerance of the recorded position; banner shape and layers match
- [ ] Flowchart shapes follow the KB's vocabulary and conditional-label colours follow its mapping

**Visual — DOCX path** — see the checklist in `reference/render-docx.md`.

**Side-by-side comparison (PDF path).** The KB bundles the team's reference document precisely so this can run. Render the output and the reference to JPEG at 110 DPI, build side-by-side images for each comparable page (cover, document history, TOC, and the main content pages), inspect for gaps, apply targeted CSS or SVG fixes, and re-render. Stop when no visible gap remains.

Skip this block for DOCX: Word reflows text, so a pixel diff against a PDF reference reports differences that cannot be fixed and are not defects.

**Never silently ship a failing check.** Surface anything unresolved with the reason.

## PHASE 6 — Deliver

Write the document to `output` (default `outputs/<client>/documents/`), run the post-render cleanup from the render reference so only the deliverable remains, then report:

```
<document_type_name> generated — <recipient>

  Deliverable:      <recipient>_<DOC_TYPE>.<ext>   (<output_dir>)
  Format:           <pdf|docx>   <"native to this team's reference" | "rebuilt from the measured spec">
  Diagrams:         <drawn from the brief | N placeholders — listed below>
  Pattern:          <name>       (signal: "<phrase>")
  Sections:         <N> written
  KB:               <kb_path>

  Assumptions:      <each one, or "none">
  Open items:       <missing IMPORTANT fields, unresolved checks, [Q-N] gaps, or "none">
  Placeholders:     <section + caption for every one, when DIAGRAM_MODE = placeholder>
```

On a re-run into an existing `output`, treat it as an **update**: apply only what the new MOM/prompt changes, and keep a small `manifest.json` beside the deliverable recording what was built, from which KB and MOM, the key assumptions, and the open items.

---

## Deliverable

One finished document — PDF or DOCX — written fresh for this recipient in the team's measured format. Validity is the KB's own definition of it: the constraints it records, plus visual fidelity to the reference it bundles.

## Never do this

- Never hardcode a format fact in this skill, or carry one over from a previous run or from general knowledge. The KB is the only authority.
- Never borrow a format, a palette, a boilerplate string, or a heading convention from another team's KB or another document in the repo. Reaching outside this KB is the halt condition.
- Never re-measure what the KB already measured, and never round or "tidy" a measured value.
- Never write fresh prose where the KB recorded a fixed string, and never truncate a reference table.
- Never copy the KB's reference document's own variable content into a new document.
- Never invent a product fact, a module, or a capability to make a requirement fit. If the KB lacks it, say so.
- Never default the output format or the diagram mode, and never carry over the previous document's answer — both are per-document decisions.
- Never draw a diagram the brief does not describe well enough to draw. That is a `[Q-N: ...]` gap, not a guess.
- Never run the cleanup before confirming the deliverable exists, and never leave `"$DELIVERABLE"` unquoted.
- Never dump a forced wall of clarifying questions. The Phase 0 gates go out in one block; after that, ask narrowly and only when it matters.

## Folder layout

```
.claude/skills/document-generator/
├── SKILL.md                  ← this file (gates + pipeline)
└── reference/
    ├── render-pdf.md         ← the PDF pipeline (read only when OUTPUT_FORMAT = pdf)
    └── render-docx.md        ← the DOCX pipeline (read only when OUTPUT_FORMAT = docx)

outputs/<client>/
├── kb/          ← the KB (input — produced and maintained by kb-builder),
│                  including the bundled reference document and assets/
└── documents/   ← the deliverable is written here (+ manifest.json), unless output= overrides
```
