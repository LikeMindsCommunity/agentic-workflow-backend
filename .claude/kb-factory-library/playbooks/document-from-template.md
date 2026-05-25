---
id: document-from-template
seen-in: [exotel-ameyo-sow, bizom-jkcement-brd, bizom-jkcement-sow, metis-eduventures, qiic-ecc-omni, razorpay]
---

## Artifact description

Client setup is **formal business document generation from raw conversational sources, matching an existing reference template**. Inputs come in two distinct groups:

- **Raw source artifacts** — meeting minutes (MOMs), call transcripts, email threads, scoping notes, briefs. Unstructured, conversational, often incomplete. These hold the substantive content for one instance.
- **Reference deliverables** — one or more finished documents in PDF or DOCX (SOW, BRD, proposal, contract, scope of work, statement of work). These are polished, branded, formatted — cover page, defined sections, header/footer with logo and page numbers, styled tables, consistent typography. They show the exact end-state the downstream agent must reproduce.

The downstream agent's job is: take a new instance's raw sources, emit a new deliverable that is **structurally, visually, and linguistically indistinguishable from the reference**, with only per-instance content (client name, scope items, pricing, dates, contacts) substituted in.

Recognize this archetype by:

- Inputs include at least one PDF or DOCX that visibly resembles a polished, branded business document (cover page, ToC, header/footer with logo, formatted tables, multi-page).
- Inputs also include unstructured prose (transcripts, MOMs, emails, briefs) that do not themselves look like the target deliverable but contain the content that should populate one.
- Target deliverable is a **document**, not a component graph, JSON artifact, automation, API integration, or code.
- Filenames typically encode document type and version: `SOW_*`, `BRD_*`, `Scope of Work_*`, `*_v1.2.0`, internal doc reference IDs, etc.

## Recipe

The generated `.claude/skills/{client}-kb/` is a **style-and-structure spec for one reference template**, not a content summary and not a generic writing guide. Its purpose is to let a downstream generator agent rebuild the same-looking document from new source material.

Generate the following files. Use the `docx` and `pdf` skills to extract real style attributes from the reference files — never eyeball values from screenshots.

- `00-overview.md` — Document genre (SOW / BRD / proposal / etc.), intended audience (procurement, legal, client sponsors, internal delivery), one-paragraph description of what the document is for. Glossary of every defined term the reference uses (e.g. "Effective Date", "Deliverable", "Statement of Work", "Vendor", "Client", and any client-specific named concepts), with the exact definition wording from the reference.

- `01-document-structure.md` — Ordered list of every section in the reference, with full hierarchy and **exact heading text verbatim**. For each section: mandatory or optional or conditional, typical length (paragraphs / pages), what content it carries, how it cross-references other sections. Include cover page, revision history, table of contents, and any sign-off block.

- `02-visual-style.md` — **The look-and-feel spec.** Extract directly from the source DOCX (a zip of XML) or PDF; do not estimate:
  - Page setup: page size, orientation, margins, columns.
  - Typography: font face + size + weight + color for every level — H1, H2, H3 (deeper if used), body text, captions, table headers, table body, footnotes, hyperlinks.
  - Color palette: every distinct color used. Hex values. Tag each with role (brand-primary, brand-accent, table-border, link, etc.).
  - Header / footer: content per page (first page may differ), logo placement and size, page-number format ("Page X of Y" vs "X / Y" vs bare).
  - List styles: bullet marker, numbered-list format, indent depth per level, line spacing.
  - Table styling: border color and weight, header-row fill, alternating-row fill if used, cell padding, alignment defaults per column type.
  - Paragraph spacing: before / after, line height, section-break behavior.

- `03-language-and-tone.md` — Voice and prose patterns. Sentence length distribution. Tense and modality convention (e.g. "The Vendor shall..." vs "We will..."). Person (first / second / third). Capitalization rule for defined terms. Conventions for dates, currency, percentages, durations. Typical opening and closing phrases per section. Transition phrases between subsections. Tone descriptors with one example each.

- `04-vocabulary.md` — Domain keywords and named entities with fixed surface forms. Capitalized defined terms with their reference definitions. Acronyms with expansions. Product / platform names and their exact written form (spacing, casing, registered marks). Terms that must never be paraphrased (especially contractual / legal).

- `05-tables-and-figures.md` — For every table type observed (deliverables, pricing, timeline, milestone, RACI, sign-off): exact column count, **column headers verbatim**, column widths or proportions, cell-content conventions (currency format, date format, duration format, alignment per column). For figures or diagrams: where they appear, captions style, numbering.

- `06-boilerplate.md` — **Verbatim text** for every clause or section that is reused near-identically across reference samples — confidentiality, IP, payment terms, change control, signatures block, T&Cs, governing law. Do not paraphrase. Mark which clauses have per-instance fill-ins (e.g. `{{Effective Date}}`) and which are fully fixed.

- `07-variable-vs-fixed.md` — Per-section breakdown of what is **fixed** (boilerplate, identical across instances), **per-instance variable** (client name, scope items, pricing, dates, contacts, signing authority), and **conditional** (sections that appear only when applicable, e.g. "Hardware" only if the engagement includes hardware). This is the bridge between the visual spec and the input checklist.

- `08-patterns.md` — Patterns extracted from the references — how a pricing tier is laid out, how a milestone table connects to a payment schedule, how an out-of-scope section is phrased, how assumptions are listed. Each pattern: when-to-use, exact template (with `{{placeholders}}`), variations observed across samples.

- `09-input-checklist.md` — Per-instance fields the downstream agent must extract from MOMs / transcripts / emails before drafting. **Tier 1 (must halt if missing)**: client legal name, engagement scope items, pricing, timeline / milestones, signing authority, effective date, any client-specific named entities used in the document. **Tier 2 (may proceed with default + warn)**: contact details, addresses, optional add-ons. **Tier 3 (KB defaults are safe)**: boilerplate clauses, header / footer, version conventions, file naming. Include "what to extract" guidance — typical MOM / transcript phrasings that signal each Tier 1 field.

- `10-constraints.md` — Numbered. What makes a generated doc invalid: defined term used before it is defined; pricing-table totals do not sum; sign-off block missing; section ordering deviates from the template; any boilerplate paraphrased rather than verbatim; placeholder `{{...}}` left in the output; font / color deviation from `02-visual-style.md`; cross-reference to a section that does not exist in the generated doc.

- `11-gap-log.md` — Remaining uncertainties, assumptions, areas where the reference samples disagreed, fields the source artifacts could not populate.

**Do not generate** files for: external API reference, authentication setup, data model entity catalogs, event/webhook contracts, configuration reference, or component-graph composition rules. The artifact is a styled, structured document, not a programmable platform. The recipe above is the right shape; don't blend in concepts that come from other archetypes.

## Anti-pattern

- **Do not summarize the reference document.** The KB's purpose is exact reproduction. Boilerplate is stored verbatim. Section headings are captured letter-for-letter. Paraphrasing is the failure mode this archetype most often falls into.
- **Do not estimate fonts and colors visually.** Parse the source DOCX (zip of XML — use the `docx` skill) or PDF (`pdf` skill) and extract the real style attributes. Eyeballed values produce regenerated docs that *look* wrong without being obviously wrong.
- **Do not produce a generic "how to write a SOW" guide.** This KB is specific to one client's reference template. A different client with a different template needs a separate `{client}-kb`. The recipe encodes one template's identity.
- **Do not collapse boilerplate into language-and-tone.** Boilerplate is exact-quote material; tone is descriptive guidance. The downstream agent must copy boilerplate verbatim and write fresh prose in the documented tone. Merging them invites paraphrasing the boilerplate.
- **Do not skip the input checklist.** Document generation fails silently when MOMs / transcripts omit a field and the downstream agent invents one. The Tier 1 list is what enforces "halt and ask" instead of fabrication.
- **Do not assume one reference sample is enough.** If only one finished document was provided, the variable-vs-fixed split is a guess. Flag this in the gap log and ask the user for at least one more sample before treating fields as confidently "fixed".
