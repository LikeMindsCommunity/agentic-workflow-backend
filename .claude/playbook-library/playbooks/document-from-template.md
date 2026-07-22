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

**Never substitute a format reference you were not given.** Not another client's KB or output; not an existing generated skill; not this playbook library (archetype advice carries no team's format); not any "gold standard" elsewhere in the repo; not your own idea of what a SOW or BRD looks like. **Reaching outside the operator's own artifacts for a format is itself the halt condition — stop and ask.** A KB built on another firm's format silently hands this team a competitor's document identity: every measurement that follows is taken faithfully from the wrong document, every generated document inherits it, and nothing downstream ever flags it. "There was only one file, so it must be the reference" is the trap — a lone transcript is zero references, not one.

**A document this pipeline produced earlier is not a reference either — it is the most dangerous impostor of the set.** It is the right document type, it carries the team's branding, it is named like a deliverable, and it sits in the same folders. Measuring it makes the KB circular: whatever the previous run rendered becomes the team's ground truth, including every fidelity error it made, and the next run reproduces those errors with new confidence. Nothing downstream can detect this, because the output will match its reference perfectly.

Check provenance before measuring anything. A PDF whose metadata reads `Title: sow.html`, `Creator: HeadlessChrome`, `Producer: Skia/PDF` came out of an HTML-to-print pipeline — which is how a generated document is produced, and also how some teams legitimately export their own. That ambiguity is the reason to **ask** rather than infer. Corroborate: does its recipient match a brief sitting alongside it (circular), is it dated after the KB or generator existed, does its content read as a past engagement or as this brief rendered? When the answer isn't clearly "a real deliverable this team issued to a real client", treat it as not-a-reference and ask for a genuine one.

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
- For a **PDF reference** there is no style XML, so measure the tokens programmatically: `pdffonts` for the real font faces (they will not be web-safe — e.g. Proxima Nova; record a close substitute for render time), and `pdfplumber` for per-character size/color, rect fills (table-header shading, accent bars), and the text bounding box (→ real margins). Watch for a **non-black body color** (e.g. gray `#666666` from Google-Docs exports) — eyeballing would default it to black. Render **every** page to JPEG at 150 DPI (`pdftoppm -jpeg -r 150`) — not a sample of pages — and view each at full resolution. Pages differ: the cover has chrome the content pages don't, and a table style that appears once on page 14 is still a distinct table style.
- Eyeballed values produce regenerated docs that *look* wrong without being obviously wrong — slightly off margins, near-but-not-exact heading sizes, a different shade of brand blue. The reviewer can't pin it down but rejects the doc.

### Sample colours programmatically — never from looking

This is the protocol that decides whether the KB is worth anything. A hex code read off a screen is wrong by a few points in every channel, and every downstream document inherits that error.

For each colour slot, find a region in a rendered page where it appears as a solid block, then sample it:

```python
from PIL import Image

def sample_hex(img, x, y, k=5):
    """Median of a 5x5 region — the median rejects anti-aliasing artefacts."""
    region = img.crop((x-k, y-k, x+k, y+k)).getdata()
    rs, gs, bs = [], [], []
    for px in region:
        rs.append(px[0]); gs.append(px[1]); bs.append(px[2])
    rs.sort(); gs.sort(); bs.sort()
    mid = len(rs) // 2
    return "#{:02X}{:02X}{:02X}".format(rs[mid], gs[mid], bs[mid])

img = Image.open("ref_p02.jpg")     # rendered at 150 DPI
print(sample_hex(img, 500, 5))      # the top strip
```

Rules that make the sample trustworthy:

- **Sample each slot at least three times**, in different regions or on different pages, and take the most frequent result. A 1–2 point spread in a channel is JPEG noise and can be smoothed; a larger spread means either the colour appears at different opacities or you are looking at two different slots that need two tokens.
- **For text colours**, sample inside the stroke of a thick character — the centre of a bold 22pt letter — never near an edge where anti-aliasing dominates.
- **For flowchart strokes**, sample at the middle of a long horizontal or vertical edge.
- Record each token with a semantic name describing where it is used (`--strip-primary`, `--table-header-bg`), never a generic one (`--color-1`), plus the sampling locations, so the extraction is reproducible.

A complete document usually needs 12 to 20 tokens. Slots that each need their own sample, none of which may be assumed equal to another: strip primary and any gradient variants, heading colour **per level**, table header band, table header text, table cell border, body text, muted/secondary text, footer text, box borders, banner layers (3–4 for chevron covers), logo accent, terminator stroke and text, one per branch-condition family, queue endpoint fill, link colour, arrow colour.

### Record sizes in physical units, never in bare pixels

A pixel is not a unit until you say at what resolution it was measured, and a downstream renderer will not guess the same one you did. A strip measured as "16px" on a page rendered at 150 DPI becomes 25 device pixels when a renderer treats it as 16 CSS pixels — 56% too thick, on every page, in a way that looks deliberate.

So for anything with a physical size — strip and rule thicknesses, margins, padding, offsets, logo and figure widths, corner radii — **record inches or points**, and put the pixel value beside it only as provenance:

```yaml
strips:
  top: { thickness: 0.107in, thickness_px_at_150dpi: 16, color_token: "--strip" }
```

Font sizes stay in points, which are already physical. Line heights and letter spacing stay unitless or in ems. The only values that may be stored as bare pixels are ones that are genuinely resolution-independent because they are relative to something else already recorded.

State the render resolution once at the top of the record as well, so every provenance number in it can be converted back.

### Heading colours are sampled per level, never shared on sight

Heading levels that look alike at a glance are frequently different colours — one a darker brand tint, the other the lighter accent. Resolve this by measurement, never by assumption:

1. Sample the top-level heading colour at three locations across different pages.
2. Sample the subsection heading colour at three separate locations.
3. Compare medians. **If they differ by more than 5 in any RGB channel they are different colours** and need different tokens.
4. Only if all six samples agree within 5 may one shared token be recorded — and the KB must say so explicitly: "H1 and H2 verified identical at #XXXXXX".

Merging heading colours without this check is the single most common visual fidelity failure in this archetype, and it is invisible until a reviewer sees the two documents side by side.

### Low-contrast rules and borders need a second look

A hairline rule sampled at its edge yields a colour indistinguishable from the page, and the regenerated document then draws an invisible line where the reference has a visible one. After sampling any rule, border, or divider:

```python
def luminance(hex_color):
    r, g, b = int(hex_color[1:3],16), int(hex_color[3:5],16), int(hex_color[5:7],16)
    return 0.2126*r + 0.7152*g + 0.0722*b

contrast = abs(luminance("#FFFFFF") - luminance(sampled_hex))   # or the real page bg
```

If `contrast < 20`, re-sample at two more locations and inspect the page at 2× zoom. If the rule is plainly visible in the reference but your hex would render it invisible, you sampled the wrong pixels — re-sample from the centre of the stroke. Record the final value with a note that it is low-contrast and needs checking in the first rendered output.

### Header and footer strings are transcribed, not recognised

Every string in the header and footer is copied character-for-character from the rendered page: brand names, copyright notices, separator punctuation, version slug formats, fixed labels.

**The pixels outrank everything else** — the product docs, the operator's description, your own sense of what the organisation is called. If the footer reads `© 2024 AcmeCorp | All Rights Reserved`, that entire string goes into the KB including the entity name, the year, and the pipe spacing. Do not substitute a parent company, a product name, or the name the rest of the artifacts use. If the header reads `Scope of Work : ClientName` with spaces around the colon, keep them. If the version slug has a trailing dash, keep it.

An inferred string is wrong on every page of every document the KB ever produces, and it is the kind of error nobody catches because it looks deliberate.

### Plan to clone the reference, not rebuild it

The fastest path to visual identity is: open the reference DOCX as a working template, replace section bodies with new content, save. Don't try to author a fresh DOCX from a style spec — embedded numbering definitions, list-level inheritance, theme overrides, language tags, compatibility settings, and dozens of other XML attributes are nearly impossible to recreate from scratch and will silently drift.

The KB's drafting guidance should explicitly call this out: *start from a copy of the canonical reference DOCX; preserve cover page chrome, header / footer, styles, theme, numbering, embedded logo / images by default; replace only the variable content within established paragraph styles*. The KB's job is to tell the agent **what to replace and what to leave alone**, not how to author DOCX XML from first principles.

**Bundle the canonical reference into the KB itself, and point at the bundled copy.** The downstream agent needs that file at generate time for two jobs — it is the base document the DOCX path clones, and it is the target the PDF path diffs its output against page by page. A KB that names the operator's original input path has a dangling dependency: it works on the machine the KB was built on and breaks everywhere else, the moment the operator tidies their inputs, or as soon as the KB is handed to a consumer as a directory. Copy the reference in alongside the extracted assets and record its bundled relative path.

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

Fixed-vs-variable is really a **spectrum, and the KB should record where each block sits on it**. Five positions, and only the last one is prose the downstream agent writes:

| Tier | What it is | What the agent does with it |
|---|---|---|
| fixed legal | Legal / compliance text that never varies | copies verbatim |
| boilerplate template | Fixed structure with marked fill-ins | copies verbatim, substitutes only the marked placeholders |
| reference data | Standard tables identical across instances | inserts every row as recorded |
| standard image | The team's own reusable diagrams | embeds the bundled asset |
| variable | This deal's content | writes fresh from product knowledge + the brief |

**When a block has a recognisable structure that repeats across sections, prefer the boilerplate tier over the variable one.** A fixed template with substitutable placeholders costs almost nothing if the call was too conservative. An agent freely paraphrasing text that was supposed to be fixed produces a document that fails review every time, and the failure is hard to attribute because the prose reads fine on its own.

### Record the render order, not just the ingredients

Knowing a section contains an intro, a table, a label, some bullets, and three footer lines does not say what order they appear in on the page — and the downstream agent has to reproduce the order exactly. For every section, record the **exact sequence of blocks as they appear**, naming each block and its tier:

```
1. boilerplate.intro          (paragraph)
2. reference_data.field_table (table)
3. boilerplate.as_is_label    (paragraph)
4. variable.as_is_content     (paragraph)
5. variable.features_bullets  (list)
6. standard_image             (image or placeholder)
7. boilerplate.role_footer    (paragraph)
```

Without this the agent reconstructs the layout from what seems natural, and "seems natural" varies run to run. With it, the layout is a lookup. This is the single highest-value thing the section model carries.

Record every block explicitly, including the ones that don't apply to a given section — an absent block stated as absent is information; an omitted block is ambiguity.

### Embedded images and diagrams

References at this scale carry embedded assets, often multi-MB worth:

- **Client logos** on cover page and header / footer — usually per-instance variable. If the agent is producing for client `Acme`, the client logo needs to be the `Acme` logo, not the previous reference's logo. Ask the operator for client logo files explicitly.
- **Vendor logo** — usually fixed boilerplate. The reference samples should agree on which one.
- **Cover page hero imagery / decorative artwork** — sometimes fixed, sometimes themed per industry. Compare across samples.
- **Process flow diagrams, architecture diagrams, screenshots** — usually per-instance, sometimes drawn from a stock library. If MOMs / transcripts describe a workflow the diagram should reflect, the agent must either ask for diagrams or generate them; do not silently omit.
- **Section icons, table-of-contents bullets, badges** — usually fixed chrome to be preserved by cloning.

Enumerate every distinct embedded image type observed and record extraction strategy and replacement policy per type.

When the reference is a **PDF** and the deliverable must render its chrome (logo, cover banner, accent bars), extract those raster assets from the PDF (`pdfimages` — composite each colour image with its `smask` to preserve transparency) and **bundle them into the KB** so it stays self-contained. Critical: **open every extracted asset and look at it before wiring it in** — image order in a PDF does not match semantic role, so the "logo" and "banner" files are easily swapped or mislabeled. A mislabeled asset renders as (e.g.) a banner where the logo should be and slips through if you trust filenames instead of eyes. Record real pixel dimensions after verifying, not before.

For a **DOCX reference**, the media lives in the zip (`word/media/`) and the semantic roles come from the relationship XML: images referenced from `word/_rels/headerN.xml.rels` are header chrome, images from `word/_rels/document.xml.rels` are body content, and the largest body image is usually the cover. Extract all of them, then **verify each role against the rendered pages** — if the relationship order disagrees with the visual left/right placement, trust the pixels and swap.

**Extract to files; never plan on base64 or a placeholder.** A placeholder produces a broken page every time the document is generated, on every page the image appears. There is no size limit on a bundled file path, which is exactly why the asset directory is the answer to the size problem that makes base64 impractical. Reserve inline SVG for simple geometric graphics (banners, dividers, icon shapes) that can be faithfully reproduced programmatically.

### Section-body images: which are the team's, which are the deal's

Some document types (BRDs, implementation guides) embed process-flow diagrams inside section bodies rather than drawing them as vector shapes. These need a per-image judgment the downstream agent cannot make for itself, so make it here and record it:

- **Standard to this team** — a generic process flow with no recipient name, logo, or deal-specific data in it, or one that recurs byte-identically across several references. It is the team's own asset: bundle it and let every document embed it.
- **Specific to one deal** — carries the recipient's name, logo, or project data, or appears in only one reference. The generated document gets a marked placeholder here, not the old deal's picture.

Record which section each image sits under, so the downstream agent knows where it goes. Where a section heading names a standard process the team runs for everyone, the image is a standard-asset candidate — but confirm by looking at it, since a generic-sounding heading can still sit above a screenshot with a previous client's name in the title bar.

### Flowchart shape vocabulary is a language, and it has to be written down

When the reference draws flow or decision diagrams as vector shapes (call flows, process flows, decision trees), the shapes are not decoration — they are a vocabulary where each shape *means* something. The downstream agent has to speak it, so record it as a vocabulary, not as a description.

Per shape observed: the shape itself (ellipse, rounded rectangle, diamond, hexagon, pentagon/banner, plain rectangle), **what it represents** (start/end terminator, prompt or action, decision, retry counter, queue endpoint, note box), stroke hex and thickness, fill hex, text colour, text weight and size, and any decoration attached to it (a speaker icon in a corner, a badge).

Then the connective tissue, which is where fidelity is usually lost:

- **Conditional / branch labels** — the exact colour-to-condition mapping. Reference documents routinely use one colour for affirmative paths, another for negative, another for exception cases. Record which words take which colour, verbatim, as a lookup.
- **Numeric option labels** for menu choices: colour, size, weight, position relative to the arrow.
- **Arrows**: colour, thickness, arrowhead style.
- **The container**: border colour and thickness around the whole diagram, background, inner padding.
- **The figure caption**: position, alignment, size, weight, underline, and the exact numbering format (`Figure 3.1.A <text>`).

Skip this entirely for document types with no vector diagrams — recording a shape library for a document that has none wastes the downstream agent's attention on shapes it will never draw. Documents that embed diagrams as raster images are the previous section's business, not this one's.

### Table types matter

For every distinct table observed (deliverables, pricing, timeline, milestone, RACI, sign-off, scope-items, use-cases, user-stories): exact column count, column headers verbatim, column widths or proportions, header-row styling, alternating row shading rules if any, cell-content conventions (currency format, date format, duration format, alignment per column), and how empty cells are rendered (em dash, "N/A", blank).

**Audit every location, not one representative table.** Visit each place a table appears — cover properties block, document history, table of contents, prerequisites, scope, escalation matrix, annexure contacts — and record whether that one uses a coloured header band, cell borders, row striping, or a plain bordered style with no fill. Any table differing in any of those properties is a **distinct type** needing its own style entry. A single global table style applied to a document that has three is visible on every page that carries the odd ones.

**Row striping is opt-in.** The default is `none`. Only record a stripe colour after seeing an unambiguous fill difference between odd and even rows in a rendered page. Not from convention, not from another document, not from "it's common practice". Striping that isn't in the reference changes the visual character of every table in every generated document.

**Classify the Table of Contents before anything is written for it.** Answer from the rendered image:

1. Does it have a coloured header band row?
2. Does it have visible cell borders forming a grid?
3. Are section and subsection numbers rendered at different weights?

If 1 and 2 are both "no" it is a **styled list, not a data table**, and the KB must record it as such with its own structure: indentation per level, font weight per level, how page numbers are right-aligned, whether there is a dot leader or a plain gap. Recording a TOC as a table when the reference uses an indented list — or the reverse — is one of the highest-impact fidelity errors, because the TOC is the most-read page in the document.

### Reference tables carry their rows, not just their shape

Some tables are the same in every document this team issues — standard field lists, account-type tables, revision-history scaffolds. For those, capturing columns and styling is not enough: **capture every row verbatim** so the downstream agent inserts them rather than re-deriving them.

Distinguish them from the per-instance tables that share the same styling but not the same content (subsidiary lists, approval matrices, tax tables, department lists) — those get their shape recorded and their rows written from the MOM.

Never record "include representative rows" or "the key fields". A truncated table in the KB is a truncated table in every document, and it is a visible, verifiable defect.

### Confidential and disclaimer boxes: heading or inline?

For every such box, record explicitly whether the keyword (`CONFIDENTIAL`, `DISCLAIMER`, `PRIVATE`) is:

- **a styled heading** — visually distinct, larger or bolder than the body, on its own line above the text like a section title; or
- **inline emphasis** — the first word(s) of the paragraph itself, bolded at body size on the same visual line as the rest of the sentence.

These render as completely different markup and defaulting to one without checking is a fidelity error.

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
- **Do not share one colour token across two heading levels without proving they are equal.** Sample each level three times and compare; more than 5 in any channel means two tokens. Levels that look alike at a glance frequently aren't, and the error is invisible until two documents sit side by side.
- **Do not record a colour you read off a screen.** Sample it programmatically, three times, and take the median of a small region. Every downstream document inherits whatever error a glance introduced.
- **Do not infer a brand string in the header or footer.** Transcribe it character-for-character from the rendered page, even when the product docs or the operator call the organisation something else. The pixels are the authority, and an inferred string is wrong on every page forever.
- **Do not record a standard table's shape without its rows.** "Include the key fields" produces a truncated table in every generated document — a visible, verifiable defect. All rows, always, for tables that are the same across instances.
- **Do not leave the render order implicit.** Listing a section's ingredients without their sequence forces the downstream agent to reconstruct the layout from intuition, which varies run to run.
- **Do not add row striping, borders, or chrome the reference doesn't have.** Convention is not evidence. Absent unambiguous visual confirmation, the answer is `none`.
- **Do not record a physical size as a bare pixel count.** Pixels measured off a 150 DPI render are not the pixels a renderer will draw. Store inches or points and keep the pixel value only as provenance, or the whole document comes out subtly mis-scaled in a way that reads as intentional.

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

- `00-overview.md` — Document genre (SOW / BRD / PRD / proposal / etc.), intended audience, one-paragraph purpose, the **bundled** reference file path (the one the agent clones and diffs against), and a glossary of every defined term the reference uses with the exact definition wording. Also the document's own type slug (`sow`, `brd`, `hld`) and the handful of standing decisions the downstream agent would otherwise have to ask about every time: whether this team's documents come out PDF or DOCX or the agent should ask per document; whether flow diagrams are drawn or left as placeholders or the agent should ask; and how many diagrams a document of this type typically carries (zero is a real answer, and it tells the agent to skip the question entirely). Record which capabilities this document type actually has — vector flowcharts, embedded process images, standard reference tables, repeating structural footers — so the agent doesn't hunt for machinery this genre doesn't use.
- `01-document-structure.md` — Ordered list of every section in the reference, with full hierarchy and exact heading text verbatim, including numbering format. For each: mandatory / optional / conditional, typical length, what content it carries, how it cross-references other sections. Includes cover page, revision history, ToC, sign-off block.
- `02-visual-style.md` — The measured format record, and the file the downstream agent leans on hardest. Page setup (paper size, margins per side, gutter), edge strips and corner accents with thickness and hex, header and footer zone-by-zone with their **verbatim** strings, cover layout (logo position and size, title block position and per-line typography, banner shape and layer colours, any properties table), typography per heading level and per named paragraph style (exact face / size / weight / **independently sampled** hex / underline / margins / letter spacing), the colour palette with semantic role tags, list styles with bullet glyphs and indentation, inline emphasis conventions, table styling per distinct table type, special elements, and the flowchart shape vocabulary where the genre has one.

  Write it as **one structured block the agent can read whole**, not as prose scattered through the file — it is consulted as a lookup during rendering, not read as an essay. Every value is a measured number or a sampled hex; a descriptor like "blue heading" or "small font" is a defect here. Where a value genuinely doesn't apply, say `none` rather than leaving it out.

  For a DOCX reference, record both the *named style IDs* (e.g. `Heading1`, `BodyText`) and their resolved attributes — the agent references styles by ID when authoring and needs the attributes only for the rebuild path.
- `03-language-and-tone.md` — Voice and prose patterns. Sentence length distribution. Tense and modality. Person. Capitalization rule for defined terms. Conventions for dates, currency, percentages, durations. Typical opening / closing phrases per section.
- `04-vocabulary.md` — Domain keywords and named entities with fixed surface forms. Capitalized defined terms with reference definitions. Acronyms with expansions. Product / platform names and their exact written form (spacing, casing, registered marks).
- `05-tables-and-figures.md` — For every table type observed: exact column count, column headers verbatim, column widths or proportions, header-row styling, alternating-row policy, cell-content conventions per column, empty-cell rendering convention. Distinguish tables whose **rows are standard across every document this team issues** from those that merely share a style — for the standard ones, record every row verbatim so the agent inserts them rather than re-deriving them; for the per-instance ones, record the shape and say the rows come from the brief. Note explicitly whether the table of contents is a data table or a styled list, and if a list, its per-level indentation, weights, and page-number alignment.
- `06-boilerplate.md` — Verbatim text for every clause or section reused near-identically across reference samples. Do not paraphrase. Mark which clauses have per-instance fill-ins (`{{Effective Date}}`, `{{Client Name}}`, etc.) and which are fully fixed. Preserve paragraph breaks and any internal numbering. For each fill-in, say **where its value comes from** — a named field in the brief, a fact in the product knowledge, or a fixed default — so substitution is mechanical and the agent never has to guess what fills a slot. Include the short recurring structural labels too (the one-line headings that introduce a block in every section); they read as trivial and are exactly the strings an agent paraphrases when they aren't written down.
- `07-variable-vs-fixed.md` — Per-section breakdown across the five tiers above: fixed legal, boilerplate template, reference data, standard image, and per-instance variable — plus which sections are conditional and what signals their inclusion. **Carries the render order for each section**: the exact sequence of blocks on the page, each named with its tier, including blocks marked absent. Bridge between visual spec, asset policy, and input checklist.
- `08-assets.md` — Embedded image inventory: every distinct image in the reference (logos, cover-page artwork, section icons, process diagrams, architecture diagrams, screenshots). Per asset: where it appears in the doc — **including which section body, for images that sit inside sections** — its bundled relative path inside the KB, its verified role tag (vendor logo / client logo / cover hero / process diagram / etc.), its real pixel dimensions, and its **replacement policy** (keep verbatim / per-instance swap / regenerate from the brief / request from operator). For section-body diagrams, state plainly whether the image is the team's own standard asset (embed it in every document) or belongs to one deal (placeholder instead), since that decision cannot be made at generate time.
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
