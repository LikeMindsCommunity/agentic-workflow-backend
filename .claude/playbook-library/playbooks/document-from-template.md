---
id: document-from-template
seen-in: [exotel-ameyo-sow, bizom-jkcement-brd, bizom-jkcement-sow, metis-eduventures, qiic-ecc-omni, razorpay]
fallback: false
---

# Playbook: document-from-template

Analysis advice and lessons learned for clients whose setup is **formal business document generation from raw conversational sources, matching an existing reference template with visual fidelity** (SOW, BRD, PRD, proposal, contract, scope of work). The downstream agent's job is to read MOMs / call transcripts / email threads / scoping notes, then emit a finished document that is **visually indistinguishable** from the reference samples — same fonts, sizes, weights, colors, margins, headers, footers, logo placement, table styling, numbering, list bullets, paragraph spacing. kb-builder uses this as guidance while analyzing the artifacts; the {client} KB is Claude's composition, not a copy of this file.

## When this playbook applies (recognition signals)

The artifact set has **two distinct groups — and only one of them is KB material**:

- **Reference deliverables** — one or more finished documents in PDF or DOCX (SOW, BRD, PRD, proposal, contract). Polished, branded, formatted: cover page with client logo, defined sections with consistent numbering, header / footer with logo and page numbers, styled tables, named paragraph styles, embedded diagrams or screenshots. They show the exact end-state the downstream agent must reproduce. **This is what the KB is built from** — its substance and its format both.
- **Raw source artifacts** — meeting minutes (MOMs), call transcripts, email threads, scoping notes, briefs, slide decks from discovery calls. Unstructured, conversational, often incomplete and contradictory across files. They hold the substantive content **for one instance** — one deal, one recipient. **They are the downstream agent's generate-time input, not KB material.** Their presence is a strong recognition signal for this archetype; their *content* belongs in a generated document and never in the KB.

**Why the split matters.** A MOM describes one deal. Fold it into the KB and that recipient's requirements start reading as the client's *standard* scope, so every later document quietly inherits them — a contamination nothing downstream checks for. The KB learns substance from the reference deliverables, and learns how to *read* a MOM from the "type your sources" section below. It needs no particular MOM's content, and must not keep any.

**A reference deliverable is required; raw sources are not.** With no finished document there is nothing to match and the archetype does not apply — ask the operator for one before going further. References with no raw sources is the **normal, intended** shape for building a KB, not a gap (a *single* reference is a separate concern — see the single-reference gap question below).

Other structural signals:

- Inputs include at least one PDF or DOCX that visibly resembles a polished, branded business document (cover page, ToC, header / footer with logo, formatted tables, multi-page, version string in filename).
- Reference file sizes are often **1 MB or larger** — the bulk is embedded images (logos, screenshots, architecture diagrams, process flowcharts), not text. This is a tell.
- Inputs also include unstructured prose (transcripts, MOMs, emails, briefs) that does not itself look like the target deliverable but contains the content that should populate one. This is a recognition *signal*, not a KB source — see the split above.
- Target deliverable is a **document**, not a component graph, JSON artifact, automation, API integration, or code.
- Filenames typically encode document type and version: `SOW_*`, `BRD_*`, `Scope of Work_*`, `*_v1.2.0`, `*_FinalV1.4`, internal doc reference IDs, dates.

Only raw sources and no reference deliverable: the archetype does not apply yet — ask the operator for a finished document rather than building from the sources. Only reference deliverables and no raw sources: proceed normally, that is the intended shape.

## What to look for when analyzing

These are the things experience says actually matter when working with this archetype.

### Parse references; never eyeball them

- Open DOCX with the `docx` skill (it's a zip of XML — `document.xml`, `styles.xml`, `numbering.xml`, `theme.xml`, `header*.xml`, `footer*.xml`, `settings.xml`, `media/` folder). Open PDF with the `pdf` skill.
- Extract **real** style attributes: page setup (paper size, margins top / bottom / left / right / gutter), section breaks and section-specific page setup, fonts per heading level and per named paragraph style (exact face, size in half-points, weight, italic, hex color, underline), theme color palette with role tags, header and footer content per section, list styles with exact bullet glyphs and indentation, table styling (borders per side per cell, shading, cell margins), paragraph spacing before / after, line spacing, indentation.
- For a **PDF reference** there is no style XML, so measure the tokens programmatically: `pdffonts` for the real font faces (they will not be web-safe — e.g. Proxima Nova; record a close substitute for render time), and `pdfplumber` for per-character size/color, rect fills (table-header shading, accent bars), and the text bounding box (→ real margins). Watch for a **non-black body color** (e.g. gray `#666666` from Google-Docs exports) — eyeballing would default it to black. Render a few pages to PNG (`pdftoppm`) to confirm cover layout, header/footer chrome, and table styling against the measured numbers.
- Eyeballed values produce regenerated docs that *look* wrong without being obviously wrong — slightly off margins, near-but-not-exact heading sizes, a different shade of brand blue. The reviewer can't pin it down but rejects the doc.

### Plan to clone the reference, not rebuild it

The fastest path to visual identity is: open the reference DOCX as a working template, replace section bodies with new content, save. Don't try to author a fresh DOCX from a style spec — embedded numbering definitions, list-level inheritance, theme overrides, language tags, compatibility settings, and dozens of other XML attributes are nearly impossible to recreate from scratch and will silently drift.

The KB's drafting guidance should explicitly call this out: *start from a copy of the canonical reference DOCX; preserve cover page chrome, header / footer, styles, theme, numbering, embedded logo / images by default; replace only the variable content within established paragraph styles*. The KB's job is to tell the agent **what to replace and what to leave alone**, not how to author DOCX XML from first principles.

For PDF-only references where no DOCX source exists, there are two runtime paths, chosen by the required deliverable:

- **Deliverable is DOCX** (editable review cycle wanted): produce a DOCX that closely mirrors the PDF's visual style, deliver DOCX as primary output, optionally export to PDF.
- **Deliverable is PDF** (and no editable source to clone): author styled **HTML/CSS to the measured spec** (`02-visual-style.md`) and render with a **headless browser** (e.g. Chrome `--headless --print-to-pdf`, or the `pdf`/browser skill). This *does* reach near-indistinguishable fidelity — the "can't rebuild a faithful PDF without the source" caution applies to hand-rebuilding, not to a measured HTML→print pipeline. The KB's drafting guidance should say so, and carry print-ready CSS values (px/pt sizes, hex colors, `@page` size + margins) plus the bundled chrome assets so the generator isn't guessing.
  - Repeating header/footer + edge bars: **do not** rely on `position:fixed` — Chrome's print engine offsets fixed elements by the `@page` margin and they land in the content area. Use a wrapping `<table>` with `<thead>`/`<tfoot>` (the browser repeats them on every printed page); keep the cover *outside* that table so it gets no running header.

### Section headings are captured letter-for-letter

Casing, punctuation, spacing, trailing colon or not, numbering format (`1.`, `1.0`, `1.0.0`, `I.`, `(a)`). The downstream agent must reproduce these exactly. Paraphrasing is the failure mode this archetype most often falls into.

### Boilerplate is stored verbatim

Every paragraph that recurs near-identically across reference samples is exact-quote material. Mark which clauses have per-instance fill-ins (e.g. `{{Effective Date}}`, `{{Client Name}}`, `{{Project Title}}`) and which are fully fixed. Confidentiality clauses, sign-off blocks, warranty language, termination clauses, and assumptions sections are typical boilerplate. Capture them with paragraph breaks intact.

### Defined terms vs. casual usage

Identify every capitalized term the reference uses as a term-of-art (Effective Date, Deliverable, Statement of Work, Vendor, Client, Project, Services, etc.) and capture the exact definition wording. A defined term used before it's defined breaks the doc. Some clients have a project-wide glossary; ask if so.

### Per-instance variables vs. fixed boilerplate

This is the central distinction. Compare reference samples to spot what varies across instances (client name, project title, dates, prices, scope items, contacts, signing authority, logo on cover, header / footer client mention) vs. what's identical (vendor name, vendor address, confidentiality clauses, generic warranty language). With only one reference sample, this distinction is a guess — flag it as BLOCKING.

### Embedded images and diagrams

References at this scale carry embedded assets, often multi-MB worth:

- **Client logos** on cover page and header / footer — usually per-instance variable. If the agent is producing for client `Acme`, the client logo needs to be the `Acme` logo, not the previous reference's logo. Ask the operator for client logo files explicitly.
- **Vendor logo** — usually fixed boilerplate. The reference samples should agree on which one.
- **Cover page hero imagery / decorative artwork** — sometimes fixed, sometimes themed per industry. Compare across samples.
- **Process flow diagrams, architecture diagrams, screenshots** — usually per-instance, sometimes drawn from a stock library. If MOMs / transcripts describe a workflow the diagram should reflect, the agent must either ask for diagrams or generate them; do not silently omit.
- **Section icons, table-of-contents bullets, badges** — usually fixed chrome to be preserved by cloning.

Enumerate every distinct embedded image type observed and record extraction strategy and replacement policy per type.

When the reference is a **PDF** and the deliverable must render its chrome (logo, cover banner, accent bars), extract those raster assets from the PDF (`pdfimages` — composite each colour image with its `smask` to preserve transparency) and **bundle them into the KB** so it stays self-contained. Critical: **open every extracted asset and look at it before wiring it in** — image order in a PDF does not match semantic role, so the "logo" and "banner" files are easily swapped or mislabeled. A mislabeled asset renders as (e.g.) a banner where the logo should be and slips through if you trust filenames instead of eyes. Record real pixel dimensions after verifying, not before.

### Table types matter

For every distinct table observed (deliverables, pricing, timeline, milestone, RACI, sign-off, scope-items, use-cases, user-stories): exact column count, column headers verbatim, column widths or proportions, header-row styling, alternating row shading rules if any, cell-content conventions (currency format, date format, duration format, alignment per column), and how empty cells are rendered (em dash, "N/A", blank).

### Numbering and lists

Heading numbering (`1`, `1.1`, `1.1.1`) is often managed by DOCX's numbering.xml linked to a multilevel list definition, not typed manually. The agent must use the same numbering definition. Bulleted lists likewise carry style identity (square vs round vs custom glyph, indentation per level). Capture these as references to the style ID, not as raw "use a square bullet" prose.

### Source material is messy — teach the agent to type its sources

These are the shapes the **generated** agent gets handed at generate time, one deal at a time — it never sees them while the KB is being built, so the KB must carry the reading rules for them. Capture what each shape is good for. The rules below are durable and firm-agnostic, which is exactly why they belong in a KB; no particular MOM's *content* ever does:

- **MOMs** — typically structured: attendees, agenda, decisions, action items, next steps. The *decisions* and *agreed scope* sections are gold. The *action items* are typically follow-ups for internal tracking, NOT scope items the SOW should commit to; don't confuse them.
- **Call transcripts** — verbatim speech with timestamps and speaker labels. High signal-to-noise but lots of filler ("uh, so I think we should, um"), tangents, and someone walking it back ten minutes later. The agent must read the whole transcript to find the *final* decision, not lift the first plausible-sounding sentence.
- **Email threads** — the canonical decision is often in a reply mid-thread, not the original. Read the thread in chronological order and prefer the **most recent** affirmation; ignore proposals that were later withdrawn or modified.
- **Slide decks from discovery calls** — vendor-authored sales artifacts. Useful for client name, project framing, big-picture scope, vendor positioning language. Treat scope items as proposed, not committed, unless confirmed in a later MOM / email.
- **Briefs / scoping notes** — often the client's own ask. High authority for what the client *wants*; weak authority for what the vendor will *deliver* (that's the SOW's job).

### Conflicting sources

When MOM #2 from a later meeting contradicts MOM #1, the later one usually wins — but flag the conflict to the operator before silently overwriting. The same applies to email threads where the scope grew or shrank across replies. Never silently merge contradictions; the agent's job is to surface the conflict, not to invent a synthesis.

### Conditional sections

Some sections appear only when applicable (e.g. "Hardware" only if engagement includes hardware, "Integration" only if there's a third-party system, "Migration" only if there's existing data). Identify the signal that triggers inclusion. Conditional sections that are inappropriately included are a common reviewer reject.

### Voice and prose patterns

Sentence length, tense, modality ("The Vendor shall..." vs "We will..."), person, typical opening / closing phrases per section. Whether the document speaks of "we" / "you" / "the Parties" / "Vendor and Client". A pricing section that says "We'll charge..." in a doc that everywhere else says "The Vendor shall invoice..." reads as a hand-off seam.

### Source-to-output mapping

What typical MOM / transcript phrasings signal each Tier 1 field the downstream agent must extract? This is what the input checklist is for. "We agreed on a six-week timeline" → `project.duration_weeks: 6`. "INR 25 lakhs all-in" → `pricing.total_amount`. Capture the typical wording patterns alongside the field name so the agent's extraction is grounded.

## Common pitfalls

When kb-builder composes the KB's Critical Rules, it draws from these (selecting the ones that apply + any new ones the analysis surfaces):

- **Do not summarize the reference document.** The KB's purpose is exact reproduction. Boilerplate is stored verbatim. Section headings are captured letter-for-letter. Paraphrasing is the failure mode this archetype most often falls into.
- **Do not estimate fonts, colors, margins, or spacing visually.** Parse the source DOCX or PDF with the appropriate skill and extract real style attributes. Eyeballed values produce regenerated docs that look wrong without being obviously wrong.
- **Do not rebuild the DOCX from scratch when a reference DOCX is available.** Clone the reference as a working template, preserve all chrome (cover, header, footer, styles, numbering, theme, embedded assets), replace only variable content. Authoring DOCX XML from style descriptions silently drifts on numbering, list inheritance, theme overrides, and compatibility flags.
- **Do not strip or replace embedded assets without an explicit policy.** Logos, diagrams, decorative artwork on the cover page are part of visual identity. Replace per the per-asset policy (vendor logo: keep; client logo: swap; cover hero: per policy; diagrams: regenerate or carry over). Silently dropping is a reviewer reject.
- **Do not produce a generic "how to write a SOW / BRD" guide.** The KB is specific to one client's reference template. A different client with a different template needs a separate KB. The KB encodes one template's identity.
- **Do not collapse boilerplate into language-and-tone.** Boilerplate is exact-quote material; tone is descriptive guidance. The downstream agent must copy boilerplate verbatim and write fresh prose in the documented tone. Merging them invites paraphrasing the boilerplate.
- **Do not skip the input checklist.** Document generation fails silently when MOMs / transcripts omit a field and the downstream agent invents one. The Tier 1 list is what enforces "halt and ask" instead of fabrication.
- **Do not treat a single reference as authoritative.** With one sample, the fixed-vs-variable split is a guess. Surface this as a BLOCKING gap before treating any field as confidently "fixed".
- **Do not lift the first plausible sentence from a transcript or email thread.** Read end-to-end and prefer the most recent confirmed position. Walking it back is common; the agent must follow the walk-back.
- **Do not confuse MOM action items with SOW scope items.** Action items are internal follow-ups; scope items are vendor commitments. They look similar in MOMs but produce different downstream artifacts.
- **Do not silently resolve source conflicts.** When two MOMs disagree, flag and ask. Inventing a synthesis is fabrication.
- **Match the deliverable format to what exists and what's asked.** DOCX is the canonical editable form when an editable reference exists or a review cycle needs it — emit DOCX, PDF as export. But when the references are PDF-only *and* the operator wants a PDF, don't force a DOCX detour: author HTML/CSS to the measured spec and render to PDF (see the clone section). Confirm the target format during scoping rather than assuming.
- **Do not trust the filenames of assets extracted from a PDF.** Extraction order ≠ semantic role; the logo and banner are commonly swapped. View each extracted asset before wiring it into the KB, and again in the first rendered page.
- **Do not preserve the previous client's identifying details when cloning.** Cover page client name, header / footer client mention, in-body references to "Acme Corp", embedded screenshots showing the previous client's UI must all be cleansed before the new client's content is dropped in.

## Useful questions to ask the operator

Examples of gap-questions that have surfaced real issues. The KB's gap-question list is Claude's composition for this client's unknowns; inspire here but don't copy.

Use this as a phrasing bank, not a checklist. This archetype's list is long on purpose; do not work through it. Align the KB's scope with the operator first, then ask only the few questions that are in scope, still unknown after reading the artifacts, and whose answers would change the KB.

- **BLOCKING — Single reference sample.** "Only one reference sample given — the fixed-vs-variable split is a guess for fields I haven't seen vary. Please share at least one more reference before I treat boilerplate as canonical."
- **BLOCKING — No reference at all.** "I see source materials (MOMs / transcripts) but no reference deliverable. I can extract content but I cannot match a visual identity I haven't seen. Please share at least one finished SOW / BRD / PRD that represents the target look-and-feel."
- **BLOCKING — Reference is PDF-only.** "The reference is PDF; no DOCX source. I can produce a DOCX that closely matches the PDF's visual style, but it will not be byte-identical. Confirm DOCX-as-deliverable is acceptable, or share the source DOCX if available."
- **BLOCKING — Client logo missing.** "Cover page and header carry a client logo position. I don't see a logo file for `{client_name}`. Please share a high-resolution logo (PNG with transparency preferred) before drafting."
- **IMPORTANT — Boilerplate variation.** "Across reference samples, the `{clause_name}` clause differs between `{file_a}` and `{file_b}`. Which version is canonical?"
- **IMPORTANT — Vendor identity in reference.** "The reference samples were authored under vendor identity `{prior_vendor}`. Confirm this is the same vendor as the current engagement, or share an updated template carrying the correct vendor name."
- **IMPORTANT — Source recency conflict.** "MOM dated `{date_1}` says scope includes `{item}`; email thread on `{date_2}` says it's deferred. I'm treating the later position as canonical — confirm?"
- **IMPORTANT — Action item vs scope item.** "MOM lists `{item}` under Action Items. Is this an internal follow-up, or a deliverable that should appear in the SOW's scope section?"
- **IMPORTANT — Conditional sections.** "I see the `{section_name}` section in some references but not others. Is this a conditional section? What signals when to include it?"
- **IMPORTANT — Embedded diagrams.** "The reference includes `{n}` process-flow / architecture diagrams. For this engagement, should I (a) carry the reference's diagrams verbatim, (b) generate new ones from the MOMs, or (c) request diagrams from you?"
- **VERIFY ASSUMPTION — Defined term used but not defined.** "The reference uses `{term}` as if defined, but I couldn't find its definition in the samples. Is this defined in a parent template or company glossary I should reference?"
- **VERIFY ASSUMPTION — Per-instance variable detection.** "I classified `{field_name}` as per-instance variable because it differed across samples. Confirm, or is this actually a boilerplate value I should fix?"
- **VERIFY ASSUMPTION — Output format.** "Reference is DOCX; I'll emit DOCX as the primary deliverable and optionally a PDF export. Confirm?"
- **NICE TO HAVE — Page-numbering / footer variants.** "Page-number format varies across samples (`{observed_formats}`). Which is canonical?"
- **NICE TO HAVE — Revision history seed.** "Reference carries a revision history table. For this draft, should the agent seed it with `v1.0 — Draft for review` or leave it for the operator?"

## Typical KB shapes that have worked

Past clients have settled around these files. Reference only — sized to what *this* client's artifacts demand. Trim aggressively if the corpus is small; extend when a section earns its keep.

- `00-overview.md` — Document genre (SOW / BRD / PRD / proposal / etc.), intended audience, one-paragraph purpose, the canonical reference file path (the one the agent will clone), and a glossary of every defined term the reference uses with the exact definition wording.
- `01-document-structure.md` — Ordered list of every section in the reference, with full hierarchy and exact heading text verbatim, including numbering format. For each: mandatory / optional / conditional, typical length, what content it carries, how it cross-references other sections. Includes cover page, revision history, ToC, sign-off block.
- `02-visual-style.md` — Page setup (paper size, margins per side, gutter), typography per heading level and per named paragraph style (exact face / size / weight / hex color / underline), color palette with role tags, header / footer content per section, list styles with bullet glyphs and indentation, table styling (borders, shading, cell margins), paragraph spacing before / after, line spacing. Records both *named style IDs* in the DOCX (e.g. `Heading1`, `BodyText`) and their resolved attributes — the agent must reference styles by ID when authoring, not duplicate the attributes inline.
- `03-language-and-tone.md` — Voice and prose patterns. Sentence length distribution. Tense and modality. Person. Capitalization rule for defined terms. Conventions for dates, currency, percentages, durations. Typical opening / closing phrases per section.
- `04-vocabulary.md` — Domain keywords and named entities with fixed surface forms. Capitalized defined terms with reference definitions. Acronyms with expansions. Product / platform names and their exact written form (spacing, casing, registered marks).
- `05-tables-and-figures.md` — For every table type observed: exact column count, column headers verbatim, column widths or proportions, header-row styling, alternating-row policy, cell-content conventions per column, empty-cell rendering convention.
- `06-boilerplate.md` — Verbatim text for every clause or section reused near-identically across reference samples. Do not paraphrase. Mark which clauses have per-instance fill-ins (`{{Effective Date}}`, `{{Client Name}}`, etc.) and which are fully fixed. Preserve paragraph breaks and any internal numbering.
- `07-variable-vs-fixed.md` — Per-section breakdown: fixed (boilerplate, identical across instances), per-instance variable (client name, scope items, pricing, dates, contacts, signing authority, client logo), conditional (sections that appear only when applicable). Bridge between visual spec, asset policy, and input checklist.
- `08-assets.md` — Embedded image inventory: every distinct image in the reference (logos, cover-page artwork, section icons, process diagrams, architecture diagrams, screenshots). Per asset: where it appears in the doc, its source file path inside the DOCX media folder, its role tag (vendor logo / client logo / cover hero / process diagram / etc.), and its **replacement policy** (keep verbatim / per-instance swap / regenerate from MOMs / request from operator).
- `09-patterns.md` — Composition patterns from references — how a pricing tier is laid out, how a milestone table connects to a payment schedule, how out-of-scope is phrased, how assumptions are listed, how a use-case is written up. Each pattern: when-to-use, exact template with placeholders, variations observed.
- `10-input-checklist.md` — Per-instance fields the downstream agent must extract from MOMs / transcripts / emails before drafting. Tiered by criticality (BLOCKING / IMPORTANT / NICE TO HAVE). For each field, include "what to extract" guidance — typical MOM / transcript / email phrasings that signal the field — so extraction is grounded, not guessed.
- `11-constraints.md` — Numbered. What makes a generated doc invalid: defined term used before defined; pricing-table totals don't sum; sign-off block missing; section ordering deviates from template; boilerplate paraphrased; placeholder `{{...}}` left in output; font / color / margin deviation from visual-style; cross-reference to nonexistent section; client logo missing or wrong; previous-client identifying details retained.
- `12-gap-log.md` — Remaining uncertainties, assumptions, areas where reference samples disagreed, asset-policy decisions to revisit on next reference share.

## Skip-entirely categories

What's typically out of scope. The KB should never lead the downstream agent to emit:

- External API reference.
- Authentication setup.
- Data model entity catalogs.
- Event / webhook contracts.
- Configuration reference.
- Component-graph composition rules.
- Generic "how to write a good SOW / BRD / PRD" advice — the KB is for one template's identity, not for industry-wide best practices.

The artifact is a styled, structured document — not a programmable platform.
