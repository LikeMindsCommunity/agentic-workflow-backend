---
name: brd-kb
description: Build and extend a knowledge base that captures the Rapid e-Suite Pte. Ltd. NetSuite / Oracle NetSuite ERP-implementation Business Requirement Document template, so a downstream agent can later turn a client's MOMs / call transcripts into a finished BRD that is visually indistinguishable from the reference samples. Use when pointed at a folder of reference BRD .docx files, or to refresh the KB after new samples arrive. Triggers: "build the brd KB", "generate brd-kb", "run brd-kb on BRD/", "extract the NetSuite BRD template".
---

# brd-kb

Builds a reusable knowledge base for one document template: the **Rapid e-Suite Pte. Ltd. NetSuite ERP-implementation BRD**. The KB encodes that template's identity — section skeleton, verbatim boilerplate, visual style, table shapes, vocabulary, composition patterns, and the MOM / transcript fields a generator must extract — so a downstream agent (e.g. `/generate-document`) can later turn raw meeting sources into a finished BRD that matches the samples.

**This skill does NOT write a client BRD.** It produces / extends the KB at `outputs/brd/kb/`. The actual document is generated downstream from KB + that client's MOMs / transcripts.

**The KB must be authoring-complete and self-sufficient.** brd-kb reads the reference samples once, here, to build the KB — but it must fully absorb everything the downstream generator needs (complete style/numbering specs *and* the fixed reusable assets, physically extracted into the KB). After this run, the original `.docx` / `.pdf` samples are not required for anything: the downstream agent authors each new BRD **from scratch** from KB + MOMs. Do not design any step that assumes a reference file is present at generation time — cloning a reference is explicitly out of scope, because a reference is not guaranteed to exist later.

```
reference BRD .docx  ──►  brd-kb (parse + fully absorb)  ──►  outputs/brd/kb/  (self-sufficient: specs + assets)
                                                                      │
                                          MOMs / transcripts  ──►  downstream generator  ──►  new client BRD
                                                              (authored from scratch, no reference file needed)
```

## What it consumes / produces

- **Consumes**: reference BRD `.docx` files. Seed corpus lives in `BRD/`. Six samples seen: FRP, Knorex, UEMS, Kreuz, SRS, Womar — all Rapid e-Suite NetSuite ERP BRDs, i.e. one template captured at several evolution stages.
- **Produces**: `outputs/brd/kb/` — markdown spec files capturing the template **plus** an `assets/` folder holding the fixed reusable images extracted from the samples (vendor logo, cover artwork, section icons / chrome). Together these are everything the downstream generator needs; the original samples are not consulted again.
- **First invocation**: draft the KB from scratch by parsing every reference and extracting its fixed assets. **Subsequent invocations**: load the existing KB as baseline, parse new / changed references only, extend it (new sections, new boilerplate variants, new table types, newly observed assets). Never silently overwrite — reconcile, and surface any conflict to the operator before changing a captured value.

## Inputs

- `inputs=<dir>` — folder of reference BRD `.docx` files. Default: `BRD/`
- `output=<dir>` — KB destination. Default: `outputs/brd/kb/`

### Recognition — is a file a Rapid e-Suite NetSuite BRD reference?

A `.docx` (often 1 MB+, the bulk being embedded NetSuite screenshots / diagrams) qualifies when its front matter shows these template fingerprints:

- Cover reads `Business Requirement Document` + `For {Client}` (or `Of … NetSuite Implementation At {Client}`).
- A **Project Details** / **Project Information** table naming Document Owner `Rapid e-Suite Pte. Ltd.`
- A **Document Revision History** / **Document Version History** table (Version / Date / Change Description / Changed By / Reviewed By / Approved By).
- An **Abbreviations / Acronyms** table defining `NS = NetSuite system`.
- An **Introduction** / **Document Purpose** paragraph about "summarize functional and procedural requirements captured by Rapid … during the business requirement mapping phase … blueprint … to configure the application, in the NetSuite version […]".
- A Table of Contents of NetSuite process-area sections (Subsidiary Structure, Role and Permissions, Customer / Vendor / Employee Master, Order to Cash, Procure to Pay, Record to Report, Data Migration, Acceptance, …).

If several of these are absent, it is **not** this template — do not fold it into this KB; flag it to the operator.

## Parsing the references (never eyeball)

Open each `.docx` with the `docx` skill (it is a zip of XML: `document.xml`, `styles.xml`, `numbering.xml`, `theme.xml`, `header*.xml` / `footer*.xml`, `settings.xml`, `media/`). Extract **real** attributes, not visual guesses: page setup and per-section margins, fonts per heading level and per named paragraph style (face, size in half-points, weight, italic, hex color), theme palette with role tags, header / footer content per section, list + multilevel-numbering definitions with glyphs and indentation, table borders / shading / cell margins, paragraph and line spacing.

**Capture completely enough to author from scratch.** Because the downstream generator builds the document fresh (no clone), the KB must hold every value needed to *recreate* the styles, not just to reference them. For each named style record the full attribute set; for numbering record the complete multilevel-list definition (level format, start-at, suffix, indent / hanging per level) so the agent can rebuild `numbering.xml` rather than inherit it from a source. If any visual detail cannot be captured with confidence, write it to `12-gap-log.md` as an open item — never leave it implicit on the assumption a reference will be on hand.

**Extract the fixed assets into the KB.** Pull the reusable embedded images from each sample's `media/` folder and save the ones that are part of the template's fixed identity (vendor logo, cover artwork, section icons, decorative chrome) into `outputs/brd/kb/assets/`, recording each in `08-assets.md` with its role and where it sits in the layout. Per-instance images (client logo, NetSuite screenshots, client-specific diagrams) are NOT extracted as fixed assets — they are supplied at generation time by the operator / MOMs.

The six samples are **one evolving template**, not six templates. Record each variant; do not flatten them:

- **FRP / Knorex / UEMS** — flat `1 … N` numbering; `Project Details` + `Document Revision History` + `Introduction`.
- **Kreuz** — sub-numbered (`15.1`, `16.1`), Procure-to-Pay / Return-to-Debit focused; ToC labelled "Table of Figures".
- **SRS** — deep multilevel numbering (`3.6.1`, `4.1.7.1`); `Project Information` + `Document Version History` + `Document Purpose`; adds `Scope of Work`, `Existing applications`, `Business Segmentation`.
- **Womar** — AS-IS / TO-BE structure; integration with IMOS; `Distributed to` table; `Overall Solution Architecture Diagram`.

## Phases

1. **Recognition & inventory.** List qualifying references in `inputs`. For each: filename, client, NetSuite version, template variant, top-level section list, version-history rows. If a KB already exists, diff each reference against it and process only deltas.
2. **Structure extraction → `01`.** For every reference, capture each section heading **verbatim** (casing, punctuation, trailing colon, numbering format `1.` / `1.1` / `1.1.1`). Union across samples; tag each section mandatory / common / conditional and list which samples carry it.
3. **Visual style → `02`.** Parse styles; record DOCX style IDs (`Heading1`, `BodyText`, …) **and** their full resolved attributes, plus the complete numbering / multilevel-list and theme definitions; note per-variant differences. Record enough that the generator can **recreate** each style and numbering definition from scratch and then apply it by name — not rely on inheriting them from a source file.
4. **Boilerplate → `06`.** Capture verbatim every recurring block: the Introduction / Document Purpose paragraph, the `Data Migration:` note, the `Features to be configured in NetSuite:` lead-in, the `Role:` clause, the Acceptance / sign-off block. Mark per-instance fill-ins as `{{Client}}`, `{{NetSuite version}}`, `{{Released On}}`, `{{Account Number}}`, etc. Preserve paragraph breaks.
5. **Tables & figures → `05`, assets → `08` + `assets/`.** Every distinct table type (Project Details, Revision History, Abbreviations, Subsidiary, field-detail tables such as "Customer Master Field Details", Role matrix): exact column count, headers verbatim, widths / proportions, header-row styling, empty-cell convention — captured as a build spec, not a sample to copy. Asset handling: **extract** the fixed-identity images (vendor logo, cover artwork, section icons / chrome) into `outputs/brd/kb/assets/` and log them in `08`; record client logo on cover/header as per-instance **operator-supplied**, NetSuite screenshots + process-flow / architecture diagrams as per-instance **regenerate or request**.
6. **Vocabulary `04`, tone `03`, patterns `09`.** `04`: defined terms, acronyms, NetSuite module names in their exact written form. `03`: voice ("Rapid will…", "{Client} will…", future tense, third person), date / currency conventions. `09`: the within-section micro-template observed across samples — intro paragraph → field-detail table → `Features to be configured in NetSuite:` bullets → `Role:` → `Data Migration:` note → AS-IS / TO-BE → gap markers (`* … still to be received from {Client}`).
7. **Input checklist `10`, constraints `11`.** `10`: the per-instance fields the downstream agent must pull from MOMs / transcripts, tiered by criticality, each with the typical MOM / transcript phrasing that signals it. `11`: what makes a generated BRD invalid.
8. **Gap loop → `12`, then save.** Run the gap questions with the operator; record resolutions and open items in `12`. Write the KB to `output`.

## KB file list (`outputs/brd/kb/`)

- `00-overview.md` — genre (NetSuite ERP BRD), vendor (Rapid e-Suite), audience, the variants on record and how to choose one per client scope, output-format policy (operator chooses per run), glossary pointer.
- `01-document-structure.md` — every section, verbatim heading + numbering, hierarchy, mandatory / common / conditional, which samples carry it.
- `02-visual-style.md` — complete from-scratch authoring spec: page setup, typography per style ID with full resolved values, palette, header / footer, complete list / multilevel-numbering definitions, theme, table styling, spacing — per variant. Enough to rebuild the styles without a source file.
- `03-language-and-tone.md` — voice, tense, modality, person, date / currency / percentage conventions, per-section opening phrases.
- `04-vocabulary.md` — defined terms, acronyms (NS, JE, CRP, R2R, P2P, COA, FAM, RMA…), NetSuite module names exact form.
- `05-tables-and-figures.md` — every table type with columns, headers, widths, styling, empty-cell rule.
- `06-boilerplate.md` — verbatim recurring text with `{{fill-in}}` markers; fully-fixed clauses flagged.
- `07-variable-vs-fixed.md` — per-section split: fixed boilerplate / per-instance variable / conditional. Bridge between style, assets, and input checklist.
- `08-assets.md` — embedded-image inventory: for each fixed asset its file path **inside `kb/assets/`**, where it sits in the layout, role tag; for per-instance images (client logo, screenshots, diagrams) the source policy (operator-supplied / regenerate / request). Fixed assets are physically present in `assets/`, not referenced back to the samples.
- `assets/` — the extracted fixed-identity image files (vendor logo, cover artwork, icons / chrome). This is what makes the KB self-sufficient for authoring.
- `09-patterns.md` — composition patterns (within-section micro-template, AS-IS/TO-BE write-up, field-detail table layout, gap-marker convention) with placeholders.
- `10-input-checklist.md` — per-instance fields for the downstream agent, tiered (BLOCKING / IMPORTANT / NICE TO HAVE), each with the MOM / transcript phrasing that signals it.
- `11-constraints.md` — numbered invalid-output conditions.
- `12-gap-log.md` — assumptions, sample disagreements, asset-policy decisions to revisit.

Trim or extend per what the corpus actually demands; a file that earns nothing should not be written.

## Critical Rules

1. **Reproduce, don't summarize.** Section headings letter-for-letter; boilerplate verbatim. Paraphrasing is the failure mode this archetype hits most.
2. **Parse style, never estimate.** No eyeballed fonts / colors / margins / spacing. Record style IDs + resolved values from the XML.
3. **Author from scratch from the KB — never depend on a reference file.** The downstream generator builds each BRD fresh from the KB spec plus the extracted `assets/`; it must not assume any sample `.docx` / `.pdf` is present (a reference is not guaranteed to exist at generation time). The KB must therefore be **authoring-complete**: every style, numbering definition, table spec, boilerplate block, and fixed asset needed to reproduce the look lives inside the KB. If a visual detail can't be captured with confidence, record it in `12-gap-log.md` — do not lean on cloning a reference to fill the gap.
4. **Six samples = one evolving template.** Capture each variant faithfully; never blend FRP's flat numbering with SRS's deep numbering into a hybrid that exists in no real sample.
5. **Boilerplate ≠ tone.** Boilerplate is exact-quote material; tone is descriptive guidance. Keep them in separate files so the agent copies one and writes the other.
6. **Asset policy is explicit per asset.** Fixed-identity assets (vendor logo, cover artwork, icons / chrome) live in `kb/assets/` and are placed from there as-is. Client logo and client screenshots / diagrams are per-instance: operator-supplied or regenerated at generation time, never carried over from a prior client. Never silently drop an asset.
7. **Cleanse prior-client identifiers.** No `FRP/Altrad`, `Knorex`, prior account numbers, or prior-client screenshots may survive into a new BRD.
8. **Output format is the operator's per-run choice** — DOCX (authored from the KB), PDF (export of that DOCX), or both. DOCX is the canonical editable form for BRD review cycles. Record this policy in `00` / `11`; the downstream agent asks each run.
9. **Never fabricate from incomplete MOMs.** The input checklist tiers fields; a missing BLOCKING field means halt and ask, not invent. Do not confuse MOM action items (internal follow-ups) with scope commitments.
10. **The KB is internal.** No KB filename, section number from these files, or constraint ID may appear in a generated client BRD. Translate internal labels to client-facing language before output.
11. **This KB encodes one template.** A non-Rapid-e-Suite, non-NetSuite, or non-BRD deliverable (a PRD, a different vendor's BRD) needs its own reference samples and a fresh kb-factory run — do not stretch this KB to cover it.

## Gap questions (asked at runtime, with the operator)

- **BLOCKING — Canonical variant.** "Samples span template variants (FRP / Knorex / UEMS flat-numbered; SRS deep-numbered with 'Document Purpose'; Kreuz P2P sub-numbered; Womar AS-IS / TO-BE). Which is canonical for new BRDs, or should I match the variant to each client's scope shape?"
- **BLOCKING — Client logo.** "Cover and header carry a client logo. Please share a high-resolution `{{Client}}` logo (PNG, transparent) before drafting."
- **IMPORTANT — Module scope.** "Which NetSuite process areas are in scope for `{{Client}}` (Order-to-Cash, Procure-to-Pay, Record-to-Report, Fixed Assets, CRM, Design-to-Build, integrations…)? Out-of-scope sections are dropped, not left empty."
- **IMPORTANT — Boilerplate variation.** "The `{{clause}}` clause differs between `{{file_a}}` and `{{file_b}}`. Which wording is canonical?"
- **IMPORTANT — Integrations.** "Samples include third-party integrations (UEMS↔UETrack, Womar↔IMOS, PEPPOL e-Invoicing, SAML SSO). Does `{{Client}}` need an integration section, and to which systems?"
- **IMPORTANT — Source conflict.** "MOM `{{date1}}` says `{{item}}`; a later source `{{date2}}` differs. I'll treat the later as canonical — confirm?"
- **VERIFY ASSUMPTION — Diagrams.** "The template carries per-instance process-flow / architecture diagrams and NetSuite screenshots (fixed chrome lives in `kb/assets/`; these do not). For `{{Client}}`: regenerate them from the MOMs, or will you supply them?"
- **VERIFY ASSUMPTION — Output format.** "Emit DOCX, PDF, or both for `{{Client}}`?"
- **NICE TO HAVE — Revision-history seed.** "Seed the version table with `v1.0 — Original Document`, or leave it for the operator?"

## Skip-entirely

External API reference, authentication setup, data-model entity catalogs, event / webhook contracts, configuration reference, component-graph composition rules, generic "how to write a good BRD" advice. The artifact is a styled NetSuite BRD, not a programmable platform spec.

## Runtime behavior

On invocation: detect references in `inputs` via the recognition fingerprints. If `outputs/brd/kb/` exists, load it as the baseline and run extraction as a **delta** (new references, new sections, new variants, new assets), reconciling any conflict with the operator before overwriting a captured value; otherwise draft from scratch. Extract the fixed assets into `kb/assets/`. Run the gap loop, then save the KB. Before finishing, sanity-check self-sufficiency: could a generator reproduce the template from the KB alone, with the samples deleted? If not, the missing piece is a gap to capture or log. Never write a client BRD here — that is the downstream generation step's job, which authors the document **from scratch** using this KB (specs + `assets/`) plus the client's MOMs / transcripts, requiring no reference file.
