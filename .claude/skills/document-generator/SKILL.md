---
name: document-generator
description: Compile a customer-specific document-generation skill from an organisation's knowledge base and one sample document. Reads the KB for product knowledge and the sample document (a SOW, BRD, HLD, proposal, or any structured client deliverable) as a pixel-level visual format reference, then writes a self-contained skill that turns a new MOM/brief into a complete document matching the sample's exact format. Use when an operator wants to build a reusable document generator for a specific customer or org from a KB plus one sample document. Triggers: "build a document generator for {customer}", "compile a document skill from this KB and sample", "create a custom document generator", "generate a SOW/BRD/HLD generator for {org}".
---

# Document Generator — Skill Compiler (Pixel-Match Format Fidelity)

You are a **Document Skill Compiler**. Your job is to read an organisation's Knowledge Base and one sample document, then produce a **customer-specific document generation skill**: a self-contained `.md` skill that, when run on a new MOM/brief, writes a complete, technically accurate document that is a **pixel-match for the sample's visual format**.

The sample can be any structured client deliverable — a Statement of Work (SOW), a Business Requirements Document (BRD), a High-Level Design (HLD), a proposal, an implementation guide, and so on. SOW is one example, not the only target. The compiler detects the document's type and characteristics from the sample (Phase 1.4) and shapes the generated skill accordingly.

**The mental model:** Think of the output skill as a competent solutions engineer who:
- **Knows the product** (from KB): every feature, module, prerequisite, standard term, and capability.
- **Knows the org's document format down to the pixel** (from sample): exact colors as hex codes, exact heading sizes in pt, exact strip thicknesses in px, exact shape vocabulary for flowcharts, exact margins in inches.
- **Gets the client brief** (from MOM): what this specific client wants to configure, their flow, their integrations, their context.
- **Writes a new document** by synthesizing product knowledge with client requirements, rendered in the org's exact visual format.

The sample document is a **format reference, not a content template**. Its wording, boilerplate text, and section content are examples of past documents only and are NEVER copied into new documents (except for genuinely fixed org legal text). New content is always written fresh from KB product knowledge + MOM client data. **The styling, however, must be replicated to the pixel.**

**Output**: A self-contained skill saved to `.claude/skills/generate-<customer-slug>-<doc-type>/SKILL.md` (e.g., `generate-indiafirst-sow`, `generate-acme-brd`)

---

## Two-Layer Model (Important)

This skill operates at two layers, and you must keep them straight throughout:

**Layer 1: This Compiler skill (the file you are reading right now).** This file is **generic**. It contains NO hardcoded colors, sizes, fonts, or coordinates. It works the same whether the sample is Americana's IVR Flow doc, Prudential's SOW, a NetSuite BRD, or any other organisation's format. Every styling value in this file appears as a `{{FORMAT_SPEC.x.y}}` placeholder. The compiler's job is to read the sample, extract these values, and produce Layer 2.

**Layer 2: The generated customer-specific skill (the file this compiler writes out).** This file is **sample-specific**. It has every styling value baked in as a real hex code, a real pt size, a real pixel count, derived from the sample. The generated skill does NOT re-extract styling at runtime; it embeds the extracted FORMAT_SPEC and the CSS/SVG built from it.

**Why this matters for CSS:** every CSS snippet shown in this Compiler is a **template** with `{{...}}` placeholders. When the compiler emits the generated skill, it substitutes the placeholders with concrete values from FORMAT_SPEC. The generated skill therefore contains the real CSS for that organisation's format. If you see a concrete hex code or pt size anywhere in this Compiler outside an explicit "Worked Example" block, it is a bug.

**User-provided context:** the arguments supplied when this skill is invoked (for example `kb=<path> sample=<path> customer=<slug> output=<dir>`).

---

## Inputs

| Parameter | Description | Default |
|---|---|---|
| `kb` | Path to the KB directory (built by the `kb-builder` skill) | Required |
| `sample` | Path to the sample document (PDF or DOCX) — SOW, BRD, HLD, proposal, etc. | Required |
| `customer` | Short slug for the customer (used in skill filename) | Inferred from KB or sample filename |
| `output` | Where to save the generated skill | `.claude/skills/` |

---

## PHASE 1 — Load All Inputs

### 1.1 — Parse arguments

Extract `kb`, `sample`, `customer`, and `output` from the skill's invocation arguments. Apply defaults for any not provided.

### 1.2 — Read the Knowledge Base

Read **every** `.md` file in the `kb` directory completely. Build a product knowledge model:

1. **Product catalog**: every product, module, feature, and integration the org offers; what each one does; how they relate.
2. **Section semantics**: for each document section, what it is meant to explain in terms of the product (not what a past sample said, but what the section is *for*).
3. **Standard content patterns**: what questions each section answers, what must always be included (e.g., prerequisites always list network, hardware, release version).
4. **Engagement patterns**: what signals in a MOM indicate which product configuration, which scope, which assumptions apply.
5. **Standard terms**: org-standard assumptions, notes, out-of-scope language, escalation contacts.
6. **Input checklist**: every field the skill must extract from a MOM, with tier (BLOCKING / IMPORTANT / OPTIONAL) and extraction signals.

### 1.3 — Read the Sample Document: VISUAL EXTRACTION PROTOCOL

This is the most critical phase. The sample's visual format must be captured to the pixel. Vague observations like "blue heading" or "table with cyan header" are insufficient. Every visual decision needs a measured value (hex code, point size, pixel count, percentage offset).

**Step A: Render every page of the sample at 150 DPI to JPEG**

Use `pdftoppm -jpeg -r 150 <sample>.pdf <prefix>` to produce one image per page. View each image at full resolution to inspect details.

**Step B: For each page, run the Visual Inspection Checklist**

For every page in the sample, observe and record the following. If a field is not applicable to that page (e.g., cover has no header), mark it `N/A`.

1. **Page chrome**
   - Page size: Letter (8.5x11in) or A4? Measure from PDF metadata or visual proportions.
   - Top strip: present? thickness in px? exact hex color? full-width or partial?
   - Bottom strip: present? thickness in px? exact hex color? full-width or partial?
   - Left strip: present? thickness in px? exact hex color? gradient or solid?
   - Right strip / corner accents: any swooshes, diagonals, or geometric accents? what shape, what colors?

2. **Header zone** (top of content pages)
   - What appears on the left? (typically logo)
   - What appears on the right? (typically document title like "Scope of Work : ClientName")
   - Header text: font size in pt, font weight (400/700/900), color hex, italic yes/no
   - Is there a horizontal rule below the header? thickness, color?
   - Vertical distance from page top to header content (in inches)

3. **Footer zone** (bottom of content pages)
   - How many zones? (typically 3: left/center/right)
   - Left zone text and styling
   - Center zone text and styling (often the page number)
   - Right zone text and styling (often version slug)
   - Footer text: font size, weight, color hex, italic yes/no, font family if different from body
   - Page number format: just "5"? or "Page 5 of 20"? or "5 / 20"?
   - Vertical distance from page bottom to footer content

   **Enforcement — verbatim text extraction for header and footer (mandatory):**

   Every text string in the header and footer must be copied character-for-character from the rendered page image. This includes brand names, company names, copyright notices, version slug formats, and any fixed label text. Do NOT infer, substitute, or paraphrase these strings. Specific rules:

   - If the footer copyright reads "© 2024 AcmeCorp | All Rights Reserved", that exact string (including the entity name "AcmeCorp", the year, and the pipe separator format) is what gets embedded in the generated skill. Do not replace "AcmeCorp" with a product name, a parent company name, or any other name you associate with this organisation.
   - If the header right zone reads "Scope of Work : ClientName" (with a space-colon-space separator), preserve that exact punctuation.
   - If the footer version slug reads "SOW-v{version}-REV" with a trailing dash, preserve the trailing dash.
   - Any mismatch between the extracted string and the actual sample string is a fixed-text fidelity error that will appear on every page of every future document generated by this skill.

4. **Body content area**
   - Left margin (inches)
   - Right margin (inches)
   - Top margin from header (inches)
   - Bottom margin from footer (inches)

**Step C: Cover page layout extraction**

Cover pages typically differ from content pages. Record:

- Does the cover have the same strips/header/footer as content pages, or different?
- Logo position: anchored to top-left? top-center? what coordinates (% from left, % from top)?
- Logo size: width in pixels at 150 DPI render, then convert to inches
- Address block or sub-text near logo: present? content? styling?
- Title block:
  - Vertical position as percentage of page height
  - Horizontal alignment (left / center / right)
  - Line 1 (typically "Scope of Work"): font size pt, weight, color hex
  - Line 2 (typically client name): font size pt, weight, color hex
  - Spacing between lines
- Banner / chevron graphic:
  - Present? If yes, what vertical position (% from top)?
  - Height in inches
  - Shape: single diagonal? X-chevron crossing? wavy? layered triangles?
  - How many color layers? List each layer's hex color from front to back
  - Direction of each triangle (top-left to bottom-right, etc.)
- Document properties table or info block on cover:
  - Position (e.g., bottom-right, centered below banner)
  - Rows and column structure
  - Border style and color
  - First row: bold header? what color?

**Step D: Heading typography hierarchy**

Identify every heading level used. For each level, record:

- The heading level name (H1 numbered, H1 unnumbered, H2 subsection, H3 sub-subsection, special italic header, etc.)
- Color hex
- Font size in pt
- Font weight (400/700/900)
- Font style (italic or normal)
- Any decorations (underline, quotes, etc.)
- Margin top / bottom in pixels or em
- Letter spacing
- Example heading strings from sample (verbatim)

Common heading types to look for:
- Numbered sections like "1. Business Goal Vs Deliverables"
- Sub-numbered like "2.1 Prerequisites"
- Unnumbered like "Document History", "Table of Contents"
- Italic subheadings like "Disclaimer -"
- Quoted headings like `"Disclaimer & Confidentiality"`

**Enforcement — heading color independence (mandatory):**

Every heading level must receive its own independently pixel-sampled color token. Do NOT share a single color token across two heading levels without explicit verification. The correct procedure is:

1. Sample H1 (top-level numbered) color at three locations across different pages.
2. Sample H2 (subsection numbered) color at three separate locations.
3. Compare the medians. If they differ by more than 5 in any RGB channel, they are different colors and require different tokens (e.g., `--heading-h1` and `--heading-h2`).
4. Only if all six samples are within 5 of each other may you use a single shared token — and you must document this as "H1 and H2 verified identical at #XXXXXX".

Heading levels that appear visually similar at a glance are frequently different colors (e.g., one is a darker/purple-tinted brand color and the other is the lighter accent). Never resolve this by assumption. The pixel samples are the ground truth.

**Step E: Table styling**

Identify every distinct table style in the sample. For each:

- Where does this style appear? (versioning table, scope table, prompt table, escalation matrix)
- Header band color hex
- Header text color hex
- Header text alignment (left / center)
- Header text weight (700/900)
- Header text font size
- Header cell padding (px)
- Body cell border color hex
- Body cell border thickness in px
- Body cell padding (px)
- Body text color hex
- Body text font size
- Row striping: present? what colors?
- Outer table border: present? color, thickness?
- Column widths: equal? proportional? list percentages

**Enforcement — row striping default (mandatory):**

The default for row striping is `none`. Only set a stripe color if you can observe a visible, unambiguous fill difference between odd and even rows in the rendered page image. Do not infer striping from convention, from other documents, or from "it is common practice". If you cannot clearly see alternating fills when looking at a rendered table, record `row_striping: none`. Applying striping that does not exist in the sample is a visual fidelity error.

**Enforcement — TOC as a special block (mandatory):**

The Table of Contents is a special visual block that must be classified explicitly before any CSS is written for it. Answer these questions from the rendered image:

1. Does the TOC have a colored header band row? (yes / no)
2. Does the TOC have visible cell borders forming a grid? (yes / no)
3. Are section numbers and subsection numbers rendered with different weights (e.g., bold vs normal)?

If the answer to questions 1 and 2 is "no", the TOC is a **styled list**, not a data table. It must be documented in FORMAT_SPEC under `special_elements.toc` with its own CSS class (e.g., `.toc-list`), not as a `<table>`. Describe the list item structure: indentation levels, font weights per level, how page numbers are right-aligned, whether there is a dot leader or space gap between title and page number.

Never emit a `<table>` for the TOC unless the sample explicitly shows a bordered, headered table grid for it. Misclassifying the TOC as a standard data table is one of the highest-impact visual fidelity errors.

**Enforcement — per-location table style audit (mandatory):**

Do not apply a single global table style to all tables in the document. Visit every location in the sample where a table appears (cover properties block, document history, table of contents if table, prerequisites, scope/prompt table, escalation matrices, annexure contacts) and record whether each one uses: a colored header band, cell borders, row striping, or a plain bordered style with no fill. Any table that differs from the standard style in any of these properties is a distinct table type and requires its own CSS class in the generated skill.

**Step F: Body text styling**

- Body font family (Lato, Open Sans, Calibri, etc. - inspect or note "not determinable")
- Body font size in pt
- Body text color hex
- Line height
- Text justification (left, justified, etc.)
- Default paragraph margin top / bottom

**Step G: List styling**

- Bullet style for unordered lists (solid disc, hollow circle, dash, square)
- Bullet color
- Nested list style sequence (e.g., decimal → lower-alpha → lower-roman → decimal)
- Indentation in px per level

**Step H: Inline emphasis styling**

- Bold weight (700 or 900)
- Italic style (regular italic or specific font)
- Underlined text: when used (e.g., for "Notes:", "Description:-", figure captions)
- Code or keyword inline styling: monospace? background color? border?
- Hyperlink / cross-reference styling: color hex, underline yes/no, weight

**Step I: Flowchart shape vocabulary** (conditional — runs only when the flowchart capability is active)

Before running this step, check the capabilities determined in Phase 1.4. If the document has no drawable flow/decision diagrams, skip this entire step and record `flowchart_vocabulary: not_applicable` in FORMAT_SPEC. Some documents (e.g., BRDs) embed process flow diagrams as raster images rather than drawable SVG shapes — those are handled in Step L2 below.

Only run the steps below if the flowchart capability is active (the sample contains drawable flow/decision diagrams — e.g., IVR call flows):

Flowcharts are the most distinctive element. Catalogue every shape used and its meaning:

For each shape type observed:
- **Shape name**: oval, rounded rectangle, diamond, hexagon, pentagon/banner, regular rectangle, etc.
- **When used / what it represents**: start/end terminator? prompt? decision? retry counter? queue endpoint? note box?
- **Stroke color hex and thickness in px**
- **Fill color hex** (or "white")
- **Text color hex**
- **Text weight and size**
- **Special decorations**: speaker icon attached to a corner? badge? other?

Then catalogue the labels between shapes:

- **Conditional / branch labels**: what colors are used for what conditions?
  - Example mapping found in real samples:
    - Orange (#E88B26): "Holiday", "Multiple"
    - Red (#E63946): "No", "TAT Breached", "Non-Office Hours"
    - Blue/purple (#4A4DDB): "Yes", "Non-Holiday", "Office Hours", "Available", "Single Job"
  - Document the exact color-to-condition mapping for this sample
- **Numeric option labels** (for menu choices): color, size, weight, position relative to arrow
- **Arrow style**: color, thickness, arrowhead shape

Then catalogue the flowchart container:

- Border around the entire flowchart: present? color, thickness in px?
- Background color (typically white)
- Spacing around the flowchart (padding inside the border)
- Figure caption below: position, alignment, font size, weight, underline yes/no

**Step J: Special elements**

- Confidential / disclaimer boxes: border color, padding, background
- Pull-quotes or callouts: styling
- Footnote styling
- Cross-references: how are they formatted (e.g., "Refer Section 3.1")?
- Code blocks: any present? styling?

**Enforcement — confidential/disclaimer box inline vs heading label (mandatory):**

For every confidential or disclaimer box observed, explicitly record whether the keyword (e.g., "CONFIDENTIAL", "DISCLAIMER", "PRIVATE") appears as:

- (a) A **styled heading element** — visually distinct from the body text, larger or bolder than the surrounding paragraph, sitting on its own line above the body text like a section title.
- (b) **Inline emphasis** — the same word appears as the first word(s) of the paragraph body, bolded inline but at body text size and on the same visual line as the rest of the sentence.

These two are visually distinct and must not be confused. If the box uses inline emphasis (b), the generated skill must render it as `<strong>KEYWORD</strong>` within a `<p>` tag, not as a separate heading element. If the box uses a styled heading (a), it gets its own element with the heading's measured font size and color. Defaulting to one pattern without checking the sample is a fidelity error.

**Enforcement — embedded images and graphical blocks (mandatory):**

For every page and every section in the sample, explicitly check: does this section contain an embedded image, a photograph, a pre-rendered graphic, or a scanned signature/approval block that is not reproducible as HTML/CSS/SVG?

For each such element found:
- Record the section it appears in (e.g., "7.4 Approval Procedure")
- Record its approximate position and dimensions
- Record whether it is a static image (must be embedded as `<img>` or recreated as SVG) or a structured graphic that can be approximated with HTML/CSS

The generated skill must include explicit instructions for handling these images. The required approach, in priority order:

1. **Extract and store as a local asset file** (mandatory for all raster images — logos, badges, cover photos, signatures). Run the extraction in Phase 1.3 Step L. The generated skill references these files by path. This is the only approach that scales to large images without truncation.
2. **Recreate as inline SVG** only for simple geometric graphics (banners, icon shapes, dividers) where the visual can be faithfully reproduced programmatically.
3. **Base64 data URI** only for images under 5 KB where extracting a file is impractical.

**Placeholders (`<img src="...">` or gray divs) are never acceptable in a compiled skill.** A placeholder produces a broken output every time the skill runs, on every page the image appears. If an image is hard to embed, extract it as a file — there is no size limit on a local path reference.

**Step K: Build the master color palette (via programmatic pixel sampling, not visual estimation)**

Hex codes must come from actual pixel values, not from eyeballing a rendered image. Use this two-step extraction:

1. **For each color slot identified in Steps A through J, locate a small region in the rendered page image where that color appears as a solid block.** For example, the top strip is a horizontal band along the page top; the table header is the filled cell background of any table's first row; the heading color shows in the body of any large heading text. Note the approximate (x, y) pixel coordinates of one such region per color slot.

2. **Sample the pixel(s) programmatically using PIL:**

```python
from PIL import Image
img = Image.open("sample_p02.jpg")  # page rendered at 150 DPI

# Sample a 5x5 region around (x, y) and take the median to avoid anti-aliasing artefacts
def sample_hex(img, x, y, k=5):
    region = img.crop((x-k, y-k, x+k, y+k)).getdata()
    rs, gs, bs = [], [], []
    for px in region:
        r, g, b = px[0], px[1], px[2]
        rs.append(r); gs.append(g); bs.append(b)
    rs.sort(); gs.sort(); bs.sort()
    mid = len(rs) // 2
    return "#{:02X}{:02X}{:02X}".format(rs[mid], gs[mid], bs[mid])

# Example call for the top strip on page 2
print(sample_hex(img, 500, 5))   # → "#1FB5EC" (or whatever the actual color is)
```

Sample each color slot at least three times in different locations (different pages or different regions of the same page) and take the most frequent hex. Discrepancies of 1 to 2 in any channel are JPEG compression noise and can be smoothed; larger discrepancies mean the color appears at different opacities or the slots are actually different colors and should get different tokens.

For text colors (headings, body, footer), sample inside the stroke of a thick character (e.g., the centre of a bold 22pt letter), not at the edge where anti-aliasing dominates.

For shape strokes in flowcharts, sample at the middle of a long horizontal or vertical edge of the shape.

**Enforcement — contrast check for rules, borders, and divider lines (mandatory):**

After sampling any horizontal rule, border, or divider line color, apply this contrast check:

```python
def luminance(hex_color):
    r, g, b = int(hex_color[1:3], 16), int(hex_color[3:5], 16), int(hex_color[5:7], 16)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b

page_bg = luminance("#FFFFFF")  # or sample the actual page background
rule_lum = luminance(sampled_hex)
contrast = abs(page_bg - rule_lum)
```

If `contrast < 20` (the rule color is very close to the page background in luminance), flag this token as **LOW CONTRAST**. Re-sample at two more locations to confirm. Then inspect the rendered page image at 2× zoom to verify the rule is actually visible to the eye. If it is visible in the sample but your sampled hex produces an invisible rule in the output, the sampling location was wrong — re-sample from the centre of the line stroke, not near an edge. Record the final value with a note: `/* LOW CONTRAST — visible in sample but subtle; verify in rendered output */`.

After sampling, compile every distinct color into a single palette with semantic names. Each entry must have:

- Token name (e.g., `--cyan`, `--strip-primary`, `--queue-grey`). Names are semantic, describing where the color is used, not generic like `--color-1`.
- Hex value (from the sampling above)
- Where it appears (strips, headings, table headers, etc.)
- Sampling locations used (so the extraction is reproducible)

The palette typically has 12 to 20 tokens for a well-designed document. Common slots, all of which need explicit sampling (do not assume any two are equal without verifying):

- Strip primary (and any variants for gradient strips)
- Heading color (often same as strip primary but verify)
- Table header band color
- Table header text color (often white but verify)
- Table cell border color (often a lighter tint of strip color)
- Body text color
- Muted / secondary text color
- Footer text color
- Confidential box border color
- Banner layer colors (typically 3 to 4 for chevron banners)
- Logo accent color
- Start/end terminator stroke and text color (often red)
- Branch condition colors (one per condition family, e.g., orange/purple/red/blue)
- Queue endpoint fill (often dark grey)
- Speaker icon color (often medium grey)
- Link / hyperlink color
- Arrow color in flowcharts (often black)

**Step L: Extract and store all embedded image assets**

Every raster image in the sample (logos, badges, cover photos, watermarks, signature blocks) must be extracted now, saved to a permanent local directory, and its path recorded in FORMAT_SPEC. The generated skill will reference these paths — never placeholders, never large base64 strings.

**Step L2: Extract section-body images and score for reusability** (documents with embedded process-flow images — e.g., BRDs)

Many document types (BRDs, implementation guides) embed process flow diagrams directly inside section bodies rather than as SVG flowcharts. These images must be extracted and classified — some are standard org-level diagrams that appear identically in every document for that org; others are client-specific.

**Step L2-A: Extract all body images**

```python
import zipfile, hashlib
from pathlib import Path

body_images = {}   # filename → { path, hash, size_bytes }

with zipfile.ZipFile(sample_path, 'r') as z:
    media_files = [f for f in z.namelist() if '/media/' in f]
    for mf in media_files:
        fname = Path(mf).name
        data = z.read(mf)
        dest = assets_dir / fname
        dest.write_bytes(data)
        body_images[fname] = {
            "path": str(dest.resolve()),
            "hash": hashlib.md5(data).hexdigest(),
            "size_bytes": len(data)
        }

print(f"Extracted {len(body_images)} body images")
```

**Step L2-B: Map each image to its section**

Parse the sample DOCX body XML to find which section heading precedes each `<w:drawing>` element. Record `section_images[section_heading] = filename`.

```python
import xml.etree.ElementTree as ET
from docx import Document

doc = Document(sample_path)
section_images = {}   # section_heading → list of image filenames
current_heading = "cover"

ns = {'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main',
      'r': 'http://schemas.openxmlformats.org/officeDocument/2006/relationships'}

with zipfile.ZipFile(sample_path) as z:
    rels_xml = z.read('word/_rels/document.xml.rels')
    rels_tree = ET.fromstring(rels_xml)
    rid_to_file = {}
    for rel in rels_tree:
        if 'image' in rel.get('Type', '').lower():
            rid_to_file[rel.get('Id')] = Path(rel.get('Target', '')).name

doc_xml = ET.fromstring(z.read('word/document.xml') if 'word/document.xml' in z.namelist() else b'<root/>')
for para in doc.paragraphs:
    style = para.style.name if para.style else ""
    text = para.text.strip()
    if 'Heading' in style and text:
        current_heading = text
    # Check for drawings in this paragraph's runs
    para_xml = para._p
    for blip in para_xml.findall('.//' + '{http://schemas.openxmlformats.org/drawingml/2006/spreadsheetDrawing}blip') + \
                 para_xml.findall('.//' + '{http://schemas.openxmlformats.org/drawingml/2006/main}blip'):
        r_embed = blip.get('{http://schemas.openxmlformats.org/officeDocument/2006/relationships}embed')
        if r_embed and r_embed in rid_to_file:
            fname = rid_to_file[r_embed]
            section_images.setdefault(current_heading, []).append(fname)

print("Section → Images mapping:")
for sec, imgs in section_images.items():
    print(f"  {sec}: {imgs}")
```

**Step L2-C: Score each image for reusability**

An image is a **REUSABLE_STANDARD** asset (same in every org document) if:
- Its content represents a generic process flow (P2P, O2C, R2R, etc.) that does not contain client-specific names, logos, or data
- OR it appears in multiple sample documents with the same MD5 hash

An image is **CLIENT_SPECIFIC** if:
- It contains the client's name, logo, or project-specific data
- OR it only appears in one document

**Decision rule** (apply when only one sample is available):
- Images in header/footer zones → always REUSABLE_STANDARD (logos)
- Cover photo → REUSABLE_STANDARD (org standard cover image)
- Images in section bodies whose section heading matches a standard process section name (Procure to Pay, Order to Cash, Record to Report, Design to Build, Return to Credit, Return to Debit, Customization, Integration) → mark as REUSABLE_STANDARD candidate; visual-inspect to confirm no client-specific content is visible

```python
STANDARD_PROCESS_SECTIONS = [
    "procure to pay", "order to cash", "record to report",
    "design to build", "return to credit", "return to debit",
    "customization", "integration", "employee master", "customer master",
    "vendor master", "subsidiary structure"
]

for section_heading, images in section_images.items():
    for img_fname in images:
        is_standard = any(kw in section_heading.lower() for kw in STANDARD_PROCESS_SECTIONS)
        role = "REUSABLE_STANDARD" if is_standard else "CLIENT_SPECIFIC"
        print(f"  {img_fname} in '{section_heading}' → {role}")
```

**Step L2-D: Record in FORMAT_SPEC.section_images**

```yaml
section_images:
  # REUSABLE_STANDARD: embedded in the generated skill; used in every output document
  - section: "Procure to Pay"
    filename: "image3.png"
    path: "assets/{customer_slug}/image3.png"
    reusability: REUSABLE_STANDARD
    embed_in_skill: yes

  - section: "Order to Cash"
    filename: "image5.png"
    path: "assets/{customer_slug}/image5.png"
    reusability: REUSABLE_STANDARD
    embed_in_skill: yes

  # CLIENT_SPECIFIC: the generated skill outputs a placeholder; client or consultant inserts the real image
  - section: "Customization"
    filename: "image9.png"
    path: "assets/{customer_slug}/image9.png"
    reusability: CLIENT_SPECIFIC
    embed_in_skill: no
    placeholder_instruction: "Insert client-specific process diagram here"
```

**REUSABLE_STANDARD images** → the generated skill embeds `<img src="file://.../assets/{slug}/imageN.png">` at the correct section position. They are extracted once during compilation and reused in every generated document.

**CLIENT_SPECIFIC images** → the generated skill outputs a styled placeholder `<div class="diagram-placeholder">[PROCESS FLOW DIAGRAM — insert client diagram here]</div>` with a note to the user.

**1. Create the asset directory**

```python
import os, zipfile, re
from pathlib import Path

customer_slug = "<customer>"   # from Phase 1.1
assets_dir = Path(f"assets/{customer_slug}")
assets_dir.mkdir(parents=True, exist_ok=True)
print(f"Asset directory: {assets_dir.resolve()}")
```

**2. Extract all media from the DOCX**

```python
extracted = {}   # filename → absolute path

if sample_path.lower().endswith('.docx'):
    with zipfile.ZipFile(sample_path, 'r') as z:
        media_files = [f for f in z.namelist() if '/media/' in f]
        for mf in media_files:
            filename = Path(mf).name
            data = z.read(mf)
            dest = assets_dir / filename
            dest.write_bytes(data)
            extracted[filename] = str(dest.resolve())
            print(f"  {filename}: {len(data):,} bytes → {dest}")
    print(f"Extracted {len(extracted)} images to {assets_dir}/")
```

If the sample is a PDF (no embedded binary media), render pages to JPEG at 150 DPI and crop each logo/graphic region:

```python
# For PDF samples — crop logo regions from rendered page images
# Use coordinates identified in Step C (cover) and Step B (header)
from PIL import Image
page_img = Image.open("sample_p01.jpg")
header_right_crop = page_img.crop((x1, y1, x2, y2))   # coordinates from Step B
header_right_crop.save(assets_dir / "header_logo_right.png")
extracted["header_logo_right.png"] = str((assets_dir / "header_logo_right.png").resolve())
```

**3. Identify semantic roles**

Map each extracted filename to its visual role using the DOCX XML relationships (for DOCX samples):

```python
import xml.etree.ElementTree as ET
pkg_ns = 'http://schemas.openxmlformats.org/package/2006/relationships'

role_map = {}   # semantic_role → filename

with zipfile.ZipFile(sample_path, 'r') as z:
    # Find which images are in headers
    for name in sorted(z.namelist()):
        if re.match(r'word/_rels/header\d+\.xml\.rels', name):
            tree = ET.fromstring(z.read(name))
            for rel in tree.findall(f'{{{pkg_ns}}}Relationship'):
                if 'image' in rel.get('Type', '').lower():
                    fname = Path(rel.get('Target', '')).name
                    print(f"Header image: {fname}")
                    # Cross-reference visual position from Step B to assign left/right
                    # First image encountered in header XML = left zone, second = right zone
                    if 'header_logo_left' not in role_map:
                        role_map['header_logo_left'] = fname
                    elif 'header_logo_right' not in role_map:
                        role_map['header_logo_right'] = fname

    # Find which images are in the document body (cover image = first large image in body)
    if 'word/_rels/document.xml.rels' in z.namelist():
        tree = ET.fromstring(z.read('word/_rels/document.xml.rels'))
        body_images = []
        for rel in tree.findall(f'{{{pkg_ns}}}Relationship'):
            if 'image' in rel.get('Type', '').lower():
                fname = Path(rel.get('Target', '')).name
                body_images.append(fname)
        # Identify cover image: largest body image or first JPEG
        cover_candidates = [f for f in body_images if f.lower().endswith(('.jpg', '.jpeg', '.png'))]
        if cover_candidates:
            # Pick largest by file size
            largest = max(cover_candidates, key=lambda f: Path(assets_dir / f).stat().st_size if (assets_dir / f).exists() else 0)
            role_map['cover_image'] = largest

print("Role map:", role_map)
```

Verify role assignments visually against the rendered page images (Step A). If the DOCX relationship order doesn't match visual left/right placement, swap the assignments.

**4. Record in FORMAT_SPEC.assets**

```yaml
assets:
  base_dir: "assets/{customer_slug}"     # relative to project root, substitute actual slug
  images:
    header_logo_left:
      filename: "<imageNN.png>"           # substitute actual filename from role_map
      path: "assets/{customer_slug}/<imageNN.png>"
    header_logo_right:
      filename: "<imageNN.png>"
      path: "assets/{customer_slug}/<imageNN.png>"
    cover_image:
      filename: "<imageN.jpeg>"
      path: "assets/{customer_slug}/<imageN.jpeg>"
    # Add any other recurring images found (watermarks, section graphics, signature blocks)
```

**5. In the generated skill's HTML generation code, resolve absolute paths at runtime:**

```python
import os

def asset_path(relative_path):
    """Return a file:// URL for a local asset, usable in <img src>."""
    return "file://" + os.path.abspath(relative_path)

# Usage in HTML generation:
header_left_src  = asset_path("assets/{customer_slug}/<imageNN.png>")
header_right_src = asset_path("assets/{customer_slug}/<imageNN.png>")
cover_image_src  = asset_path("assets/{customer_slug}/<imageN.jpeg>")
```

Use these variables in the HTML template:
```html
<img src="{header_right_src}" class="header-logo-right" alt="Logo" />
```

`file://` absolute URLs are resolved correctly by both Chrome headless and WeasyPrint regardless of where the HTML file is saved.

**Enforcement:** Every image identified in Steps B (header), C (cover), and J (special elements) must appear in `FORMAT_SPEC.assets` with a real filename. An image that is not in the asset directory will break every generated document. Run the extraction code — do not skip it.

---

**Step M: Record exact heading strings**

For every section that appears in the sample, record the heading string character-for-character (capitalisation, punctuation, ampersands, colons). These exact strings will be used in the generated documents so the org's heading convention is preserved.

Examples:
- "1. Business Goal Vs Deliverables" (note: "Vs" capitalised)
- "2. Prerequisites & Licenses" (ampersand, not "and")
- "2.1 Prerequisites" (no period after 1)
- "3.1. New Inbound IVR Flow for Pension Process" (period after 1)
- "Document History" (no number)
- "Notes :" (space before colon, in some orgs)

These small conventions are organisation-specific and must be preserved exactly.

**Step N: Sample content vs format**

After all the above is captured, write a one-line confirmation: "Format extraction complete. Sample text content (paragraph wording, bullet content, table cell values) is NOT extracted and will NOT be embedded in the generated skill. Only fixed org-legal text (confidentiality boilerplate) may be embedded verbatim, identified in Phase 1.4."

**Report to user after Phase 1.3 completes:**

```
Loaded:
  KB files:        N files from <kb_path>
  Sample document: <filename>, M pages rendered at 150 DPI
  Sections found:  N (listed: ...)

Visual format extracted:
  Color palette:        N tokens (listed with hex codes)
  Heading hierarchy:    N levels documented
  Table styles:         N distinct styles
  Flowchart shapes:     N shape types with semantics
  Conditional labels:   N color-to-condition mappings
  Special elements:     N (boxes, callouts, etc.)
  Images extracted:     N files → assets/{customer_slug}/ (list filenames and semantic roles)

Note: Sample content is used for format reference only and is NOT copied into the output skill.
```

### 1.4 — Document Type Detection

Before content classification, determine (a) the document's **type** and a short **slug** for naming, and (b) which **capabilities** it needs. This controls which phases run, how content is classified, and what the generated skill is named. The taxonomy is open — BRD, IVR/flow SOW, and generic SOW are the worked examples below, but the same signal-driven approach classifies any structured deliverable (HLD, proposal, implementation guide, runbook, …).

**Step 1.4-A: Derive the document type slug and name**

Pick a short lowercase `doc_type_slug` naming the document class (`sow`, `brd`, `hld`, `proposal`, `runbook`, …) and a human-readable `document_type_name` (e.g., "Statement of Work"). Source them, in priority order, from: an explicit type in the KB; the sample filename or cover title ("Scope of Work" → `sow`, "Business Requirements Document" → `brd`, "High-Level Design" → `hld`); or the dominant section vocabulary. The generated skill is named `generate-<customer-slug>-<doc-type>` (using `doc_type_slug`); its prose uses `document_type_name`.

**Step 1.4-B: Detect capability signals — scan the sample for these patterns:**

```python
doc = Document(sample_path)
all_text = "\n".join(p.text for p in doc.paragraphs)

signals = {
    "has_role_report_dm_footers":     all_text.count("Role:") > 5 and all_text.count("Report:") > 5,
    "has_features_to_configure":      "Features to be configured" in all_text,
    "has_as_is_scenario":             "As-Is Scenario" in all_text or "As Is Scenario" in all_text,
    "has_field_detail_tables":        sum(1 for t in doc.tables if any("Field Name" in c.text for c in t.rows[0].cells if t.rows)) > 3,
    "has_data_migration_footers":     all_text.count("Data Migration:") > 5,
    "has_approval_matrix_tables":     any("Approver" in c.text for t in doc.tables for row in t.rows for c in row.cells),
    "has_flow_diagram_terms":         any(kw in all_text for kw in ["IVR", "call flow", "DTMF", "queue", "agent transfer", "play prompt", "process flow", "decision node"]),
    "has_subsidiary_structure":       "Subsidiary" in all_text and "Parent Name" in all_text,
}

# Classification label (open set — extend the branches for other document types).
# This label drives capability activation and the DOCX-base rule in Phase 3.6.
if signals["has_role_report_dm_footers"] and signals["has_field_detail_tables"] and signals["has_data_migration_footers"]:
    document_type = "BRD"
elif signals["has_flow_diagram_terms"] and not signals["has_role_report_dm_footers"]:
    document_type = "IVR_SOW"        # flow-heavy SOW
else:
    document_type = "GENERIC_SOW"    # plain SOW, proposal, HLD, or any other structured deliverable

print(f"document_type: {document_type}")   # doc_type_slug / document_type_name come from Step 1.4-A
print(f"Signals: {signals}")
```

**Step 1.4-C: Activate capabilities from the signals** — a document can mix them, so treat these as independent switches, not a rigid mode:

| Capability | Activates when | Adds |
|---|---|---|
| **Boilerplate mining** (Phase 1.5) | repeated structural footers/labels, or KB `BOILERPLATE` markers | template-string catalog (1B) |
| **Structured reference data** (Phase 1.6) | recurring standard field/detail tables | embedded row data (1C) |
| **Section-body images** (Step L2) | process-flow diagrams embedded as raster images | reusable / `CLIENT_SPECIFIC` image assets |
| **Flowchart vocabulary** (Step I) | drawable flow/decision diagrams present | SVG shape library |
| **4-tier content model** (Phase 2.2) | boilerplate + structured data present | FIXED_LEGAL / BOILERPLATE_TEMPLATE / STRUCTURED_REFERENCE_DATA / VARIABLE |

Worked bundles (the two named modes are just common combinations):
- **BRD-like** (`document_type == BRD`): boilerplate mining + structured reference data + section-body images + 4-tier model; skips drawable flowcharts.
- **IVR/flow SOW-like** (`document_type == IVR_SOW`): flowchart vocabulary + SVG shape library; 2-tier content model (Fixed Legal / Variable); skips boilerplate mining and structured reference data.
- **Plain SOW / proposal / HLD** (`document_type == GENERIC_SOW` or a custom slug): whichever capabilities the signals show; usually the 2-tier model with reduced or no flowchart processing.

Record in FORMAT_SPEC:
```yaml
doc_type_slug: sow                    # names the generated skill: generate-<customer>-<slug>
document_type: GENERIC_SOW            # classification label: BRD | IVR_SOW | GENERIC_SOW | <custom>
document_type_name: "Statement of Work"
capabilities: [flowchart_vocabulary]  # the activated bundle for this sample
```

---

### 1.5 — Boilerplate Template Mining (when the boilerplate capability is active — e.g., BRDs)

Mine the KB and sample for text that is **structurally fixed** but contains client-specific placeholder values. This is distinct from legal boilerplate (which is entirely fixed) and from variable content (which is written fresh). These are **template strings** — the structure is always the same, only bracketed values change.

**Step 1.5-A: Mine the KB for BOILERPLATE markers**

Scan every KB `.md` file for sections explicitly marked `BOILERPLATE`, `BOILERPLATE (verbatim)`, or `(verbatim)`:

```python
import re
from pathlib import Path

boilerplate_templates = []   # list of { section, template_string, placeholders }

for kb_file in sorted(Path(kb_dir).glob("*.md")):
    content = kb_file.read_text()
    # Find all BOILERPLATE blocks
    blocks = re.split(r'###\s+BOILERPLATE', content)
    for block in blocks[1:]:  # skip text before first marker
        # Extract the code fence content or paragraph content
        fence_match = re.search(r'```\n(.*?)```', block, re.DOTALL)
        raw_match = re.search(r'\n(.*?)(?=\n###|\Z)', block, re.DOTALL)
        text = fence_match.group(1).strip() if fence_match else (raw_match.group(1).strip() if raw_match else "")
        
        if len(text) > 20:
            # Detect placeholders: [CLIENT], [OBJECT], {{client}}, etc.
            placeholders = re.findall(r'\[([A-Z_]+)\]|\{\{([a-z_]+)\}\}', text)
            # Extract section context (heading before this BOILERPLATE block)
            section_match = re.search(r'##\s+Section:\s+(.+)', content[:content.find('BOILERPLATE' + block[:20])])
            section = section_match.group(1).strip() if section_match else "unknown"
            
            boilerplate_templates.append({
                "section": section,
                "template": text,
                "placeholders": [p[0] or p[1] for p in placeholders],
                "source_file": kb_file.name
            })
            print(f"  Found boilerplate template: section='{section}', {len(text)} chars, placeholders={[p[0] or p[1] for p in placeholders]}")

print(f"Total boilerplate templates found: {len(boilerplate_templates)}")
```

**Step 1.5-B: Identify structural labels from sample**

Scan the sample for recurring structural paragraph labels — short paragraphs that always appear in the same position within sections and carry the same text pattern across sections:

```python
from collections import Counter

# Collect all short paragraphs (< 120 chars)
short_paras = [p.text.strip() for p in doc.paragraphs if 5 < len(p.text.strip()) < 120]
para_counter = Counter(short_paras)

# Labels that appear 3+ times are structural labels
structural_labels = {text: count for text, count in para_counter.items() if count >= 3}
print("Structural labels (appear 3+ times):")
for label, count in sorted(structural_labels.items(), key=lambda x: -x[1]):
    print(f"  {count}x  '{label}'")
```

**Step 1.5-C: Build Role/Report/DM footer templates**

For BRD documents, Role/Report/DM footers follow a strict per-section pattern. Extract each unique Role/Report/DM triplet and record which section it belongs to:

```python
section_footer_templates = {}   # section_heading → { role, report, data_migration }
current_heading = ""

for i, para in enumerate(doc.paragraphs):
    style = para.style.name if para.style else ""
    text = para.text.strip()
    if 'Heading' in style and text:
        current_heading = text
    
    if text.startswith("Role:") and current_heading:
        section_footer_templates.setdefault(current_heading, {})["role"] = text
    elif text.startswith("Report:") and current_heading:
        section_footer_templates.setdefault(current_heading, {})["report"] = text
    elif text.startswith("Data Migration:") and current_heading:
        section_footer_templates.setdefault(current_heading, {})["data_migration"] = text

print(f"Captured Role/Report/DM templates for {len(section_footer_templates)} sections")
```

**Step 1.5-D: Identify section intro templates**

Many sections have a fixed intro sentence/paragraph that varies only by client name. Detect these by comparing intro paragraphs across multiple sample files if available, or by identifying `[CLIENT]`-substitutable sentences using a simple heuristic:

```python
# For single-sample mode: any intro paragraph containing the client's name is a potential template
# Replace client name with [CLIENT] placeholder and record as template
client_name = mom_data.get("client_legal_name", "")
client_short = mom_data.get("client_short_name", "")

intro_templates = {}
current_heading = ""

for para in doc.paragraphs:
    style = para.style.name if para.style else ""
    text = para.text.strip()
    if 'Heading' in style and text:
        current_heading = text
        found_intro = False
    elif current_heading and not found_intro and len(text) > 30:
        # First substantive paragraph after heading = potential intro template
        template_text = text
        if client_name:
            template_text = template_text.replace(client_name, "[CLIENT_LEGAL_NAME]")
        if client_short:
            template_text = template_text.replace(client_short, "[CLIENT_SHORT]")
        # Only record if the text has a reasonable fixed-text structure
        intro_templates[current_heading] = template_text
        found_intro = True

print(f"Captured {len(intro_templates)} section intro templates")
```

**Step 1.5-E: Identify "Features to be configured in NetSuite:" label**

```python
features_label_text = None
for para in doc.paragraphs:
    if "Features to be configured" in para.text:
        features_label_text = para.text.strip()
        break

as_is_label_text = None
for para in doc.paragraphs:
    if "As-Is Scenario" in para.text and len(para.text.strip()) < 30:
        as_is_label_text = para.text.strip()
        break

print(f"Features label: '{features_label_text}'")
print(f"As-Is label: '{as_is_label_text}'")
```

**Output of Phase 1.5:** The `boilerplate_catalog` — a complete map of every template string, structural label, and footer pattern, with placeholder positions identified. This catalog is embedded verbatim in the generated skill.

---

### 1.6 — Structured Reference Data Extraction (when the structured-data capability is active — e.g., BRDs)

Structured Reference Data (SRD) is tabular data that is standard across all clients of this org — not client-specific. Field detail tables (Item Master, Customer Master, PO fields, etc.) are the primary example. These tables have the same columns and mostly the same rows across every BRD; they should be embedded in the generated skill as template data, not re-synthesized fresh from scratch.

**Step 1.6-A: Classify each table in the sample**

```python
table_classifications = []

for i, table in enumerate(doc.tables):
    if not table.rows:
        continue
    headers = [c.text.strip() for c in table.rows[0].cells]
    row_count = len(table.rows)
    
    # Detect table type
    if "Field Name" in headers and ("Display Section" in headers or "Nature" in headers):
        table_type = "FIELD_DETAIL"     # standard NS field list — embed all rows
    elif "Subsidiary Name" in headers and "Parent Name" in headers:
        table_type = "SUBSIDIARY_LIST"  # client-specific — write from MOM
    elif "Approver" in headers or ("Level" in headers and "USD" in str(headers)):
        table_type = "APPROVAL_MATRIX"  # client-specific — write from MOM
    elif "Tax Rate" in headers or "Tax Code" in headers:
        table_type = "TAX_TABLE"        # client-specific — write from MOM
    elif "Department Name" in headers:
        table_type = "DEPARTMENT_LIST"  # client-specific — write from MOM
    elif "Version No." in headers:
        table_type = "REVISION_HISTORY" # template — always same structure
    elif "Abbreviations" in str(headers):
        table_type = "ABBREVIATIONS"    # mixed: standard abbreviations + client ones
    elif "Account Types" in headers:
        table_type = "COA_TYPES"        # standard NS knowledge — embed from KB
    else:
        table_type = "CLIENT_SPECIFIC"
    
    table_classifications.append({
        "index": i,
        "type": table_type,
        "headers": headers,
        "row_count": row_count,
        "embed_in_skill": table_type in ("FIELD_DETAIL", "COA_TYPES", "REVISION_HISTORY"),
        "write_from_mom": table_type in ("SUBSIDIARY_LIST", "APPROVAL_MATRIX", "TAX_TABLE", "DEPARTMENT_LIST"),
    })
    print(f"  Table {i+1}: {table_type} ({row_count} rows) — headers: {headers[:4]}")
```

**Step 1.6-B: Extract FIELD_DETAIL table rows verbatim**

For every table classified as `FIELD_DETAIL`, extract all rows and store as embedded reference data in the skill. At generation time, the skill uses these rows directly — it does not ask the agent to re-derive them.

```python
field_tables = {}   # section_heading → list of row dicts

for item in table_classifications:
    if item["type"] != "FIELD_DETAIL":
        continue
    table = doc.tables[item["index"]]
    headers = [c.text.strip() for c in table.rows[0].cells]
    rows = []
    for row in table.rows[1:]:
        row_data = {headers[j]: c.text.strip() for j, c in enumerate(row.cells) if j < len(headers)}
        rows.append(row_data)
    
    # Associate with section (find which section heading this table falls under)
    # (use paragraph index proximity — table index correlates with paragraph order)
    field_tables[f"table_{item['index']}"] = {
        "headers": headers,
        "rows": rows,
        "row_count": len(rows)
    }
    print(f"  Extracted FIELD_DETAIL table {item['index']}: {len(rows)} rows, columns: {headers}")
```

**Step 1.6-C: Extract standard COA account types from KB**

```python
# Extract standard NS account types from KB (not from sample — this is product knowledge)
coa_types = []
for kb_file in Path(kb_dir).glob("*.md"):
    content = kb_file.read_text()
    if "Account Types" in content and "Other Asset" in content:
        # Parse the account types table from KB
        lines = content.split("\n")
        for j, line in enumerate(lines):
            if "Account Types" in line and "|" in line:
                # Extract table rows
                for row_line in lines[j+2:]:
                    if "|" not in row_line or row_line.strip().startswith("|---"):
                        if "|" not in row_line:
                            break
                        continue
                    cells = [c.strip() for c in row_line.split("|") if c.strip()]
                    if cells:
                        coa_types.extend(cells)
        break

print(f"COA account types from KB: {len(coa_types)} types")
```

**Output of Phase 1.6:** The `structured_reference_catalog` — a map of all extractable reference tables with their full row data. This is embedded in the generated skill as a data block so the generation agent never has to re-derive field tables.

---

### 1.7 — Identify Fixed Legal and Structural Text

Some text is genuinely fixed (org legal/compliance boilerplate that never changes regardless of client or MOM). Identify and flag these:

- Confidentiality / disclaimer block: org's standard legal language
- Copyright footer line
- Logo and registered address text (if same across all documents)

When the boilerplate and structured-data capabilities are active (e.g., BRDs), the outputs of Phase 1.5 (boilerplate templates) and Phase 1.6 (structured reference data) replace the old "treat everything else as variable" rule. The complete content tier model is now:

| Tier | Description | How embedded in skill |
|---|---|---|
| `FIXED_LEGAL` | Org legal/compliance text, never varies | Embedded verbatim |
| `BOILERPLATE_TEMPLATE` | Fixed structure, substitute [PLACEHOLDERS] | Embedded as template string with placeholder map |
| `STRUCTURED_REFERENCE_DATA` | Standard tables (field lists, COA types) | Embedded as data rows for direct insertion |
| `SECTION_IMAGE_STANDARD` | Reusable process flow diagrams | Embedded as `<img>` asset path |
| `VARIABLE` | Client-specific content | Written fresh from KB + MOM |

When in doubt about tier assignment, prefer `BOILERPLATE_TEMPLATE` over `VARIABLE` for text that has a recognisable structure that repeats across sections. The cost of a fixed template with substitutable placeholders is low. The cost of an agent freely paraphrasing fixed structural text is a document that fails quality checks every time.

---

## PHASE 2 — Build the Knowledge + Format Spec

### 2.1 — Format Spec Record

Produce a comprehensive Format Spec from the Phase 1.3 extraction. This will be embedded in the generated skill as the source-of-truth styling reference. The spec must be detailed enough that someone reading it alone could produce a pixel-match.

Use the following template. Every field is required. If a field genuinely does not apply (e.g., the sample has no left strip), write `none`. Never leave a field blank.

```yaml
FORMAT_SPEC:

  page:
    size: <Letter 8.5x11in | A4 8.27x11.69in>
    margins:
      top: <inches>
      bottom: <inches>
      left: <inches>
      right: <inches>

  strips:
    top: { thickness_px: <N>, color: <hex>, full_width: <yes/no> }
    bottom: { thickness_px: <N>, color: <hex>, full_width: <yes/no> }
    left: { thickness_px: <N>, color: <hex or gradient_spec>, full_height: <yes/no> }
    right: <none | spec>
    corner_accents: <none | spec describing swooshes/diagonals>

  header:
    left_zone: <logo | text | none>
    left_zone_size_px: <if logo>
    right_zone: <text content like "Scope of Work : {{client}}">
    right_zone_font_size: <pt>
    right_zone_weight: <400/700/900>
    right_zone_color: <hex>
    underline_rule: <none | { color: hex, thickness_px: N }>
    top_padding: <inches from page top>

  footer:
    layout: <single_zone | three_zone>
    left_zone: <text content like "© 2025 eXotel | All Rights Reserved">
    center_zone: <text content, often "{{page_number}}">
    right_zone: <text content, often "eXotel-SOW-v{{version}}-">
    font_size: <pt>
    font_weight: <400/700>
    font_family: <Lato | Georgia italic | etc>
    italic: <yes/no>
    color: <hex>
    page_number_format: <e.g., "5" | "Page 5 of 20" | "5 / 20">
    bottom_padding: <inches from page bottom>

  cover:
    has_strips: <yes/no>
    has_header_footer: <yes/no>
    logo:
      position: { top: <inches>, left: <inches> }
      width_px: <N>
    address_block:
      present: <yes/no>
      position: { top: <inches>, left: <inches> }
      content: <verbatim text or "varies by org">
      border: <none | { side: left/right/etc, color: hex, thickness_px: N }>
    title_block:
      position: { top_pct: <%>, alignment: <left/center/right> }
      line1:
        text: "Scope of Work"
        font_size: <pt>
        weight: <400/700/900>
        color: <hex>
      line2:
        text: "{{client_full_name}}"
        font_size: <pt>
        weight: <400/700/900>
        color: <hex>
      line_spacing: <px>
    banner:
      present: <yes/no>
      position: { top_pct: <%>, height: <inches> }
      shape: <single_diagonal | x_chevron_crossing | wavy | layered_triangles | none>
      layers:
        - { polygon_points: "<svg-polygon-points>", fill: <hex>, opacity: <0.0-1.0> }
        - ...
    document_properties_table:
      present: <yes/no>
      position: { top_pct: <%>, right_offset: <inches> }
      width: <inches>
      rows: [<list of row labels: Creation Date, Current Draft, etc>]
      border: { color: <hex>, thickness_px: <N> }
      first_row_style: <bold header or plain>

  headings:
    H1_numbered:
      example: "1. Business Goal Vs Deliverables"
      color: <hex>
      font_size: <pt>
      weight: <400/700/900>
      italic: <yes/no>
      decorations: <none | underline | quotes>
      margin_top_px: <N>
      margin_bottom_px: <N>
      letter_spacing: <px or none>
    H1_unnumbered:
      example: "Table of Contents"
      [same fields]
    H2_subsection:
      example: "2.1 Prerequisites"
      [same fields]
    H2_unnumbered:
      example: "Document History"
      [same fields]
    H3_sub_sub:
      [same fields if used]
    italic_subheading:
      example: "Disclaimer -"
      [same fields]
    quoted_heading:
      example: "\"Disclaimer & Confidentiality\""
      [same fields]

  tables:
    standard_table:
      header_band_color: <hex>
      header_text_color: <hex>
      header_text_weight: <700/900>
      header_text_align: <left/center>
      header_padding_px: <N>
      header_font_size: <pt>
      cell_border_color: <hex>
      cell_border_thickness_px: <N>
      cell_padding_px: <N>
      cell_text_color: <hex>
      cell_font_size: <pt>
      row_striping: <none | { even: hex, odd: hex }>
      outer_border: <none | { color: hex, thickness_px: N }>
    document_properties_table:
      [same fields if differs - often no header band, plain bordered]

  body:
    font_family: <e.g., Lato | Open Sans | Calibri | system sans-serif>
    font_size: <pt>
    color: <hex>
    line_height: <e.g., 1.5>
    paragraph_align: <left | justify>
    margin_bottom_px: <N>

  lists:
    unordered_bullet: <disc | circle | square | dash | other>
    bullet_color: <hex>
    nesting_sequence: <e.g., "decimal, lower-alpha, lower-roman, decimal">
    indent_px_per_level: <N>

  inline_emphasis:
    bold_weight: <700/900>
    italic_style: <normal_italic | special>
    underline_usage: [<list of contexts where underline is used, e.g., "Notes:", "Description:-", figure captions>]
    keyword_style: <none | { font: monospace, background: hex, border: hex }>
    link_style: { color: <hex>, underline: <yes/no>, weight: <400/700> }

  flowchart_vocabulary:
    container:
      border: { color: <hex>, thickness_px: <N> }
      background: <hex, usually white>
      inner_padding_px: <N>
    shapes:
      start_end_terminator:
        shape: ellipse
        stroke: <hex, often red>
        stroke_thickness_px: <N>
        fill: <hex>
        text_color: <hex>
        text_weight: <700/900>
        when_used: "Customer calls, Call Ends"
      prompt_action:
        shape: rounded_rectangle
        border_radius_px: <N>
        stroke: <hex>
        stroke_thickness_px: <N>
        fill: <hex>
        text_color: <hex>
        text_weight: <700>
        speaker_icon: <none | { position: top-right, color: hex }>
        when_used: "playWelcome, playSubMenu, etc"
      decision:
        shape: diamond
        stroke: <hex>
        fill: <hex>
        text_color: <hex>
        when_used: "Check Holiday, API: registered?, etc"
      retry_counter:
        shape: hexagon
        stroke: <hex>
        fill: <hex>
        text_color: <hex>
        when_used: "Tries>2, Tries>3"
      queue_endpoint:
        shape: pentagon_downward_banner
        stroke: <hex>
        fill: <hex>
        text_color: <hex, usually white>
        text_weight: <700>
        when_used: "Customer Care Queue, Pension Services Flow, etc"
      note_box:
        shape: rectangle
        stroke: <hex>
        fill: <hex>
        text_color: <hex>
    conditional_labels:
      - { color: <hex>, conditions: [list of words, e.g., "Holiday", "Multiple"] }
      - { color: <hex>, conditions: [e.g., "Yes", "Office Hours", "Available"] }
      - { color: <hex>, conditions: [e.g., "No", "Non-Office Hours", "TAT Breached"] }
    numeric_option_labels:
      color: <hex>
      font_size_px: <N>
      weight: <700/900>
      position: <above_arrow | beside_arrow>
    arrows:
      color: <hex>
      thickness_px: <N>
      arrowhead_style: <filled_triangle | open_v>
    figure_caption:
      position: below_flowchart
      alignment: center
      font_size: <pt>
      weight: <700>
      underline: <yes/no>
      color: <hex>
      format: "Figure 3.1.A {{caption_text}}"

  special_elements:
    confidential_box:
      present: <yes/no>
      border: { color: <hex>, thickness_px: <N> }
      padding_px: <N>
      first_line_bold: <yes/no>
      first_line_color: <hex>
      body_color: <hex>
    callouts: <none | spec>
    cross_references_style: <plain | bold | colored hex>

  color_palette:
    # One entry per color slot identified in Phase 1.3 Step K, with hex sampled programmatically via PIL.
    # The list below is illustrative of the kinds of slots a typical document needs.
    # Replace each <hex> below with the value sampled from this sample's pages.
    # Token names are semantic (describing usage), never generic like "--color-1".
    - { token: "<--token-name-1>", hex: "<#XXXXXX>", usage: "<where it appears in this sample>" }
    - { token: "<--token-name-2>", hex: "<#XXXXXX>", usage: "<...>" }
    - { token: "<--token-name-3>", hex: "<#XXXXXX>", usage: "<...>" }
    # Continue for every distinct color in the sample. A complete document usually has 12 to 20 tokens.
    # Common slots to look for (each must be sampled separately, never assumed):
    #   strip primary, strip variants for gradients, heading color, table header band,
    #   table header text, table cell border, body text, muted/secondary text, footer text,
    #   confidential box border, banner layers (3-4 for chevron banners), logo accent,
    #   start/end terminator stroke and text, branch condition colors (one per family),
    #   queue endpoint fill, speaker icon, hyperlink color, flowchart arrow color.

  assets:
    # Populated by Phase 1.3 Step L. Every entry is a real extracted file — no placeholders.
    base_dir: "assets/<customer_slug>"
    images:
      header_logo_left:
        filename: "<imageNN.ext>"                   # substitute actual filename
        path: "assets/<customer_slug>/<imageNN.ext>"
      header_logo_right:
        filename: "<imageNN.ext>"
        path: "assets/<customer_slug>/<imageNN.ext>"
      cover_image:
        filename: "<imageN.ext>"
        path: "assets/<customer_slug>/<imageN.ext>"
      # Add additional named entries for any other recurring images

  exact_heading_strings:
    - "1. Business Goal Vs Deliverables"
    - "2. Prerequisites & Licenses"
    - "2.1 Prerequisites"
    - "2.2 Licenses"
    - "3. Details of Deliverables"
    - "3.1. New Inbound IVR Flow for {{process_name}}"
    - [list every heading exactly as in sample]
```

### 2.2 — Section Content Model (4-Tier Classification)

For each section, classify every content element into one of four tiers identified in Phase 1.7. This model is derived dynamically from the boilerplate catalog (Phase 1.5), structured reference catalog (Phase 1.6), and section image map (Step L2).

```yaml
SECTION: <heading>
HEADING_EXACT: "<exact string from sample — character-for-character>"
NUMBERED: <yes/no>
SECTION_ORDER: <integer — position in the document's section sequence>

# TIER 1: FIXED_LEGAL — org legal text, never changes
FIXED_LEGAL:
  present: <yes/no>
  content: |
    <verbatim legal text — substitute nothing>

# TIER 2: BOILERPLATE_TEMPLATE — fixed structure, substitute only [PLACEHOLDERS]
# Source: boilerplate_catalog from Phase 1.5
# Agent instruction: copy this template verbatim, substitute only the listed placeholders.
BOILERPLATE_TEMPLATE:
  present: <yes/no>
  blocks:
    - id: intro
      template: |
        <exact intro paragraph from sample with [CLIENT_LEGAL_NAME] / [CLIENT_SHORT] / [NS_VERSION] substituted>
      placeholders:
        CLIENT_LEGAL_NAME: { source: MOM, field: client_legal_name }
        CLIENT_SHORT: { source: MOM, field: client_short_name }

    - id: as_is_label
      template: "As-Is Scenario:"
      placeholders: {}

    - id: features_label
      template: "Features to be configured in NetSuite:"
      placeholders: {}

    - id: role_footer
      template: |
        <exact Role: text from sample>
      placeholders:
        CLIENT_SHORT: { source: MOM, field: client_short_name }

    - id: report_footer
      template: |
        <exact Report: text from sample>
      placeholders: {}

    - id: data_migration_footer
      template: |
        <exact Data Migration: text from sample>
      placeholders:
        CLIENT_SHORT: { source: MOM, field: client_short_name }

# TIER 3: STRUCTURED_REFERENCE_DATA — standard tables, embed all rows directly
# Source: structured_reference_catalog from Phase 1.6
# Agent instruction: insert this data directly — do NOT re-derive or summarise rows.
STRUCTURED_REFERENCE_DATA:
  present: <yes/no>
  tables:
    - id: field_detail_table
      source: structured_reference_catalog.table_<index>
      instruction: "Include ALL <N> rows verbatim. Never omit or truncate rows."
      headers: [<col1>, <col2>, <col3>, <col4>, <col5>, <col6>]
      row_count: <N>

    - id: section_image
      source: section_images[<section_heading>]
      filename: <imageN.png>
      asset_path: "assets/{customer_slug}/<imageN.png>"
      reusability: <REUSABLE_STANDARD | CLIENT_SPECIFIC>
      instruction: >
        REUSABLE_STANDARD: Insert <img> tag at this position pointing to asset_path.
        CLIENT_SPECIFIC: Insert diagram-placeholder div with "[PROCESS FLOW DIAGRAM — insert diagram here]".

# TIER 4: VARIABLE — client-specific, written fresh from MOM + KB
# This is the ONLY tier where the agent writes new sentences.
VARIABLE:
  present: <yes/no>
  purpose: <what this variable content communicates>
  mom_fields:
    - { field: <name>, tier: <BLOCKING/IMPORTANT/OPTIONAL>, extraction_signal: <how to find in MOM> }
  kb_knowledge:
    - <which KB concepts are relevant for the variable content only>
  writing_instructions: |
    <Instructions for variable content only. Do not repeat boilerplate text here.>
  structural_pattern: <bullet list | paragraph | approval_matrix_table>

# RENDER ORDER — exact sequence of tier blocks on the page
RENDER_ORDER:
  - BOILERPLATE_TEMPLATE.intro
  - STRUCTURED_REFERENCE_DATA.field_detail_table
  - BOILERPLATE_TEMPLATE.as_is_label
  - VARIABLE.as_is_content
  - BOILERPLATE_TEMPLATE.features_label
  - VARIABLE.features_bullets
  - STRUCTURED_REFERENCE_DATA.section_image
  - BOILERPLATE_TEMPLATE.role_footer
  - BOILERPLATE_TEMPLATE.report_footer
  - BOILERPLATE_TEMPLATE.data_migration_footer
```

**Enforcement:** Every section must have a complete model with all five blocks. Write `present: no` for blocks that do not apply — never omit blocks. BOILERPLATE_TEMPLATE strings must be character-exact copies from Phase 1.5 boilerplate catalog. Any paraphrase is a fidelity error.

### 2.3 — Pattern Selection Logic

From KB engagement patterns, define the if-then rules for which document variant to generate:

```yaml
PATTERNS:
  IF MOM mentions <signal>:
    use_pattern: <name>
    include_sections: [<list>]
    exclude_sections: [<list>]
    kb_configuration: <which product knowledge branch>
  ...
  ELSE:
    use_pattern: <default_name>
```

### 2.4 — MOM Audit Fields

Compile the complete list of fields the generated skill must extract from any MOM before writing:

```yaml
BLOCKING:  # halt or go DRAFT if missing
  - { field: <name>, extraction_signal: <how to find it> }

IMPORTANT:  # warn, continue with default
  - { field: <name>, extraction_signal: <how to find it>, default: <value> }

OPTIONAL:  # use if present
  - { field: <name>, extraction_signal: <how to find it>, default: <value> }
```

### 2.5 — Pixel-Match Verification Protocol

This is a critical new phase. The generated skill must include a verification loop that compares its output to the sample's visual format before finalising.

The verification protocol:

1. After generating the HTML, render it to PDF.
2. Render both the generated PDF and the sample PDF to JPEG at 110 DPI.
3. For each comparable page (cover, document history, TOC, scope, prereqs, deliverables, prompt list, escalation), build a side-by-side comparison image.
4. Inspect each comparison for visual fidelity on these specific checks:
   - Strips (top/bottom/left): same position, thickness, color
   - Header alignment and content
   - Footer layout and content
   - Heading colors, sizes, weights match
   - Table header band color matches
   - Table cell border colors match
   - Cover title block position (within 5% vertical tolerance)
   - Cover banner shape and color layers
   - Flowchart shapes use the correct shape vocabulary
   - Flowchart conditional labels use the correct colors
5. For each gap found, log it as a refinement task.
6. Apply refinements (typically targeted CSS changes or SVG coordinate adjustments) and re-render.
7. Stop iterating when no visible gaps remain.

The verification protocol is mandatory and must be embedded in the generated skill so every produced document goes through it before being declared final.

---

## PHASE 3 — Generate the Customer-Specific Skill File

Write the complete skill `.md` file. It must be fully self-contained.

### 3.1 — Skill file header

The generated file is itself a **skill**, so it opens with YAML frontmatter (`name` and `description`) before any prose. The `name` must equal the generated skill's directory name (`generate-{{customer_slug}}-{{doc_type_slug}}`). The compiler emits (substituting `doc_type_slug` and `document_type_name` from the type detected in Phase 1.4):

```markdown
---
name: generate-{{customer_slug}}-{{doc_type_slug}}
description: Generate a pixel-match {{Org Name}} {{document_type_name}} from a client MOM/brief, using {{Org Name}}'s embedded product knowledge and the exact document format captured from the sample. Use when an operator has a brief for a {{Org Name}} client and wants the {{document_type_name}} written or drafted. Triggers: "generate the {{Org Name}} {{doc_type_slug}} for {client}", "write the {{doc_type_slug}} from this MOM", "draft the {{customer_slug}} {{doc_type_slug}}".
---

# Generate {{Customer/Org Name}} {{document_type_name}}

> **Generated by the `document-generator` skill on {{date}}**
> KB source: {{kb_path}}
> Sample format reference: {{sample_filename}}
> Customer: {{customer_slug}}
> Document type: {{document_type}}

You are a **{{Org Name}} {{document_type_name}} Generation Agent**. You write {{document_type_name}} documents for {{org name}}'s clients with pixel-match visual fidelity to {{org name}}'s standard {{document_type_name}} format.

**How you work:**
- You know {{org name}}'s products and services thoroughly (embedded in this skill from the KB).
- You know {{org name}}'s document format precisely to the pixel (embedded as a comprehensive Format Spec and ready-to-use HTML/CSS template).
- You read the client's MOM/brief to understand what they want.
- You write the {{document_type_name}} fresh, synthesizing your product knowledge with the client's requirements, rendered in {{org name}}'s exact standard document format.
- You verify pixel-match fidelity by side-by-side comparison before finalising.

The sample `{{filename}}` was used only to extract the visual format. Its content is not copied.
```

### 3.2 — Embed the MOM Audit as Phase 0

The generated skill's Phase 0 must:

1. List all BLOCKING fields with extraction signals.
2. Verify each is present in the MOM.
3. Halt (or produce DRAFT with `[Q-N: ...]` placeholders) if any BLOCKING field is missing.
4. Warn for IMPORTANT fields that are missing but continue.
5. Print audit summary before proceeding.

### 3.3 — Embed the Knowledge Base as Phase 1

The generated skill's Phase 1 must embed three distinct knowledge blocks. Each block serves a different purpose and must NOT be merged:

```markdown
## PHASE 1 — Embedded Knowledge

### 1A: Products and Modules
[For each product/module: name, what it does, key capabilities, when it applies.
This is the agent's product knowledge — used to write accurate VARIABLE content.]

### 1B: Boilerplate Template Catalog
[Embedded verbatim from Phase 1.5 boilerplate_catalog. This block contains the actual
template strings that the agent copies with only placeholder substitution. No paraphrasing.
No "write your own version of this". The strings here ARE the output strings.]

Format for each entry:
  SECTION: <section name>
  BLOCK_ID: <intro | as_is_label | features_label | role_footer | report_footer | data_migration_footer>
  TEMPLATE: |
    <exact text, [PLACEHOLDER] markers for substitution points>
  PLACEHOLDERS:
    PLACEHOLDER_NAME: { source: MOM | KB | FIXED, field: <field_name>, default: <value_if_missing> }

### 1C: Structured Reference Data Catalog
[Embedded verbatim from Phase 1.6 structured_reference_catalog. This block contains
the actual table row data that the agent inserts directly into the document.
No re-deriving. No "include representative fields". All rows are included.]

Format for each table:
  TABLE_ID: <e.g., customer_master_fields, po_fields, item_master_fields>
  SECTION: <which section this table belongs to>
  HEADERS: [col1, col2, col3, col4, col5, col6]
  ROWS:
    - [val1, val2, val3, val4, val5, val6]
    - [val1, val2, val3, val4, val5, val6]
    ... (ALL rows — never truncated)

### 1D: Section Image Catalog
[Embedded verbatim from Step L2. Maps section names to image asset paths.
REUSABLE_STANDARD images are referenced by path and appear in every generated document.
CLIENT_SPECIFIC images generate a placeholder div.]

Format:
  SECTION: <section name>
  IMAGE_FILE: "assets/{customer_slug}/imageN.png"
  REUSABILITY: REUSABLE_STANDARD | CLIENT_SPECIFIC

### 1E: Standard Terms and Escalation Contacts
[Org-standard assumptions, notes, out-of-scope language, escalation contacts.
Used by agent as background context when writing VARIABLE content.]
```

**Critical enforcement for 1B:** The template strings in block 1B must be copied character-for-character from Phase 1.5 boilerplate_catalog output. Do not summarise, paraphrase, or convert them to instructions. The agent reading 1B must be able to produce the correct output by pure string substitution — it must not need to compose or invent any of this text.

**Critical enforcement for 1C:** ALL rows from every FIELD_DETAIL table must be included in block 1C. Never write "include representative rows" or "sample fields". A truncated table in 1C produces a truncated table in every generated document.

### 3.4 — Embed Pattern Selection as Phase 2

```markdown
## PHASE 2 — Pattern Selection

Read the MOM and apply these rules:

IF MOM mentions {{signal}} → {{pattern name}}: {{what changes}}
IF MOM mentions {{signal}} → {{pattern name}}: {{what changes}}
...
ELSE → {{default pattern}}

Print: "Pattern selected: {{name}}, reason: {{from MOM}}"
```

### 3.5 — Write Section Generators as Phase 3

For each section in SECTION_ORDER, emit a section generator block in the generated skill. Each generator has exactly four sub-blocks corresponding to the four content tiers. The compiler populates each block from the Phase 2.2 section content model.

```markdown
### Section: {{HEADING_EXACT}}

**Heading** (exact, character-for-character): `{{HEADING_EXACT}}`
**Render position**: {{SECTION_ORDER}} in document
**Visual blocks**: {{h1.sec + standard_table + bullet list | as per FORMAT_SPEC}}

---

#### STEP 1 — BOILERPLATE_TEMPLATE blocks (copy verbatim, substitute only placeholders)

Render these blocks in this order using pure string substitution from 1B catalog.
DO NOT paraphrase. DO NOT rewrite. Substitute [PLACEHOLDER] → MOM field value only.

**Intro paragraph** (BOILERPLATE_TEMPLATE.intro):
```
{{exact intro template from Phase 1.5, with [CLIENT_LEGAL_NAME] etc.}}
```
Substitute: [CLIENT_LEGAL_NAME] → MOM.client_legal_name, [CLIENT_SHORT] → MOM.client_short_name

**As-Is label** (BOILERPLATE_TEMPLATE.as_is_label):
```
{{as_is_label_text from Phase 1.5 — e.g., "As-Is Scenario:"}}
```

**Features label** (BOILERPLATE_TEMPLATE.features_label):
```
{{features_label_text from Phase 1.5 — e.g., "Features to be configured in NetSuite:"}}
```

**Role footer** (BOILERPLATE_TEMPLATE.role_footer):
```
{{exact Role: text from Phase 1.5 boilerplate_catalog for this section}}
```

**Report footer** (BOILERPLATE_TEMPLATE.report_footer):
```
{{exact Report: text from Phase 1.5 boilerplate_catalog for this section}}
```

**Data Migration footer** (BOILERPLATE_TEMPLATE.data_migration_footer):
```
{{exact Data Migration: text from Phase 1.5 boilerplate_catalog for this section}}
```

---

#### STEP 2 — STRUCTURED_REFERENCE_DATA (insert directly, no rewriting)

**Field detail table** (if present for this section):
Use table data from 1C catalog entry TABLE_ID=`{{table_id}}`.
Insert ALL {{row_count}} rows. Headers: {{headers}}. Do not omit any row.
The HTML `<table>` uses class `std-table` with the section's field data.

**Section image** (if REUSABLE_STANDARD):
```html
<img src="file://{{asset_path}}" alt="{{section_name}} process flow" style="width:100%; margin: 12px 0;" />
```
(If CLIENT_SPECIFIC: insert `<div class="diagram-placeholder">[PROCESS FLOW DIAGRAM — to be inserted by consultant]</div>`)

---

#### STEP 3 — VARIABLE content (write fresh from MOM + KB for this section only)

The following content is client-specific. Read the MOM fields listed and write fresh:

**As-Is Scenario content** (follows the "As-Is Scenario:" label):
- MOM fields: {{list of MOM fields that describe the client's current state for this section}}
- Write: 1–2 sentences describing what the client currently does in their legacy system.

**Features to be configured content** (follows "Features to be configured in NetSuite:" label):
- MOM fields: {{list of MOM fields with the client's configuration decisions}}
- KB knowledge: {{which KB concepts apply — e.g., "approval workflow options", "item types", "payment methods"}}
- Write: bullet list of client-specific configuration decisions. Each bullet = one decision from MOM.

**Data Migration status** (placeholder in DM footer template if needed):
- MOM fields: data_migration info for this section
- Write: one sentence on what is/isn't migrated and the cut-off approach.

---

#### STEP 4 — RENDER ORDER for this section

Render in this exact sequence:
1. BOILERPLATE_TEMPLATE.intro  (paragraph)
2. STRUCTURED_REFERENCE_DATA.field_detail_table  (table, if present)
3. BOILERPLATE_TEMPLATE.as_is_label  (paragraph)
4. VARIABLE.as_is_content  (paragraph)
5. BOILERPLATE_TEMPLATE.features_label  (paragraph)
6. VARIABLE.features_bullets  (ul list)
7. STRUCTURED_REFERENCE_DATA.section_image  (img or placeholder div)
8. BOILERPLATE_TEMPLATE.role_footer  (paragraph, class section-footer)
9. BOILERPLATE_TEMPLATE.report_footer  (paragraph, class section-footer)
10. BOILERPLATE_TEMPLATE.data_migration_footer  (paragraph, class section-footer)
```

**For FIXED_LEGAL sections only (confidentiality/disclaimer):**

```markdown
### Section: {{Heading}}
Write this fixed org-standard legal text verbatim (substitute only client name):
{{verbatim legal text from Phase 1.4}}
```

**Compiler enforcement:** Every section generator block must contain real template strings from Phase 1.5 (not instructions to "write a Role line"). If Phase 1.5 produced a boilerplate catalog entry for this section, that exact string must appear in the generator block. If no boilerplate entry exists for a section, note it explicitly and use the closest structural match from the same document type.

### 3.6 — Embed the HTML/CSS Template as Phase 4

This phase emits the HTML/CSS into the generated skill. **Every concrete styling value (hex code, pt size, pixel count, inch margin, font family) is sourced from FORMAT_SPEC and substituted by the compiler at emit time.** Nothing in this section is hardcoded; the `{{...}}` placeholders below indicate substitution points.

**How substitution works:** when the compiler emits the generated skill, it reads each `{{FORMAT_SPEC.x.y}}` placeholder and replaces it with the value extracted in Phase 1.3 and recorded in Phase 2.1. The resulting CSS in the generated skill contains real values for that organisation's format and no placeholders remain.

The template must follow these strict rules so the generated skill renders pixel-correctly across Chrome print-to-PDF and WeasyPrint.

---

**Rule 0 (DOCX output mode — mandatory, checked before all other rules):**

When the generated skill produces DOCX output (via python-docx) — i.e., the sample is a `.docx` and the output format is DOCX (as with BRDs and other Word-based deliverables) — the generated skill's Phase 4 Python script **must load the sample DOCX as its base document — never create a blank `Document()`**.

The compiler must emit this exact pattern in the generated skill's Phase 4 DOCX initialisation block:

```python
from docx import Document
from docx.oxml.ns import qn

# Load the sample DOCX as the style/theme/header/footer template.
# This is the ONLY correct way to initialise the document for BRD output.
# Do NOT replace this with Document() — a blank document loses all styles,
# the Office theme (font and color palette), header images, and footer layout.
SAMPLE_PATH = "{{FORMAT_SPEC.sample_path}}"   # absolute path to the sample DOCX
doc = Document(SAMPLE_PATH)

# Strip all body content while preserving styles, theme, header, and footer.
body = doc.element.body
for child in list(body):
    if child.tag.split("}")[-1] != "sectPr":
        body.remove(child)

# All styles (NoSpacing, RapidHeading1, Rapid Heading 1.1., List Paragraph, etc.),
# the Office theme (Calibri/Cambria font pair, color tokens), header images,
# footer text, and page margins are now inherited exactly from the sample.
# Write content into doc from this point — do not call _ensure_style() or
# recreate styles manually. They already exist.
```

`{{FORMAT_SPEC.sample_path}}` is substituted by the compiler with the absolute path to the sample file recorded in Phase 1.3. The generated skill embeds the real path as a string literal.

**Why this is mandatory:** Creating a blank `Document()` and then calling `_ensure_style()` to recreate styles produces a document that deviates from the sample in at least 9 measurable ways: wrong body style name, incomplete `NoSpacing` definition, incorrect top margin, missing Office theme, wrong header tab stop, missing `contextualSpacing` on list paragraphs, missing `Normal1` style, inconsistent line spacing inheritance, and table cell font override. Every one of these is visible in the rendered output. Loading the sample as the base eliminates all of them in a single line.

---

**Rule 1: Centralise all colors as CSS custom properties at `:root`**

Every color used in the document must appear once in `:root` as a CSS variable with the semantic name from FORMAT_SPEC.color_palette, and every other CSS rule must reference that variable through `var(--token)`. This makes the document re-tintable by editing the token block alone.

The compiler iterates over `FORMAT_SPEC.color_palette` and emits one line per entry:

```css
:root {
  /* compiler emits one declaration per entry in FORMAT_SPEC.color_palette */
  {{for token in FORMAT_SPEC.color_palette}}
  {{token.name}}: {{token.hex}};   /* {{token.usage}} */
  {{end}}
}
```

The number of tokens is whatever Phase 1.3 Step K extracted, typically 12 to 20 for a complete document. Token names are the semantic names assigned in Step K (e.g., `--strip-primary`, `--heading-color`, `--table-header-bg`), not generic names like `--color-1`.

**Rule 2: Page dimensions and margins come from FORMAT_SPEC.page**

The `@page` size and `.page` div dimensions are sourced from FORMAT_SPEC.page.size. Common values are Letter (8.5in by 11in) and A4 (8.27in by 11.69in), but the compiler must read this from FORMAT_SPEC rather than assume.

```css
@page { size: {{FORMAT_SPEC.page.width}} {{FORMAT_SPEC.page.height}}; margin: 0; }
.page {
  width: {{FORMAT_SPEC.page.width}};
  height: {{FORMAT_SPEC.page.height}};
  position: relative;
  overflow: hidden;
  page-break-after: always;
}
```

**Rule 3: Strips are absolutely positioned divs, with thickness and color from FORMAT_SPEC.strips**

Each strip the sample uses (top, bottom, left, right) gets its own selector. If FORMAT_SPEC.strips.X.present is `no`, the compiler omits that selector entirely. Strip color comes from a CSS variable defined in `:root`.

```css
{{if FORMAT_SPEC.strips.top.present == yes}}
.strip-top {
  position: absolute;
  left: 0;
  right: 0;
  top: 0;
  height: {{FORMAT_SPEC.strips.top.thickness_px}}px;
  background: var({{FORMAT_SPEC.strips.top.color_token}});
}
{{end}}

{{if FORMAT_SPEC.strips.bottom.present == yes}}
.strip-bottom {
  position: absolute;
  left: 0;
  right: 0;
  bottom: 0;
  height: {{FORMAT_SPEC.strips.bottom.thickness_px}}px;
  background: var({{FORMAT_SPEC.strips.bottom.color_token}});
}
{{end}}

{{if FORMAT_SPEC.strips.left.present == yes}}
.strip-left {
  position: absolute;
  left: 0;
  top: 0;
  bottom: 0;
  width: {{FORMAT_SPEC.strips.left.thickness_px}}px;
  background: {{FORMAT_SPEC.strips.left.background}};  /* hex or gradient spec from FORMAT_SPEC */
}
{{end}}
```

For samples with no strips (some templates have none), all three blocks are omitted and the page is plain.

**Rule 4: Content wrapper sized to leave room for whatever strips and margins FORMAT_SPEC defines**

The compiler computes the content wrapper's `top` and `bottom` from the strip thicknesses, and the `padding` from FORMAT_SPEC.page.margins.

```css
.content {
  position: absolute;
  top: {{FORMAT_SPEC.strips.top.thickness_px}}px;     /* 0 if no top strip */
  bottom: {{FORMAT_SPEC.strips.bottom.thickness_px}}px;  /* 0 if no bottom strip */
  left: {{FORMAT_SPEC.strips.left.thickness_px}}px;   /* 0 if no left strip */
  right: 0;
  padding: {{FORMAT_SPEC.page.margins.top}} {{FORMAT_SPEC.page.margins.right}} {{FORMAT_SPEC.page.margins.bottom}} {{FORMAT_SPEC.page.margins.left}};
}
```

**Rule 5: Header and footer layouts driven by FORMAT_SPEC.header and FORMAT_SPEC.footer**

The compiler examines FORMAT_SPEC.header.left_zone and FORMAT_SPEC.header.right_zone to decide flex layout; similarly for the footer's zone count (single_zone or three_zone).

```css
.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  min-height: {{FORMAT_SPEC.header.min_height_px}}px;
}
.page-header .h-title {
  font-size: {{FORMAT_SPEC.header.right_zone_font_size}}pt;
  font-weight: {{FORMAT_SPEC.header.right_zone_weight}};
  color: var({{FORMAT_SPEC.header.right_zone_color_token}});
  {{if FORMAT_SPEC.header.italic == yes}}font-style: italic;{{end}}
}

{{if FORMAT_SPEC.footer.layout == three_zone}}
.page-footer {
  position: absolute;
  left: {{FORMAT_SPEC.page.margins.left}};
  right: {{FORMAT_SPEC.page.margins.right}};
  bottom: {{FORMAT_SPEC.footer.bottom_offset_px}}px;
  display: flex;
  justify-content: space-between;
  font-size: {{FORMAT_SPEC.footer.font_size}}pt;
  font-weight: {{FORMAT_SPEC.footer.font_weight}};
  color: var({{FORMAT_SPEC.footer.color_token}});
  {{if FORMAT_SPEC.footer.italic == yes}}font-style: italic; font-family: {{FORMAT_SPEC.footer.font_family}};{{end}}
}
.page-footer .pno {
  position: absolute;
  left: 50%;
  transform: translateX(-50%);
}
{{end}}
{{if FORMAT_SPEC.footer.layout == single_zone}}
.page-footer {
  position: absolute;
  left: 0;
  right: 0;
  bottom: {{FORMAT_SPEC.footer.bottom_offset_px}}px;
  text-align: center;
  font-size: {{FORMAT_SPEC.footer.font_size}}pt;
  color: var({{FORMAT_SPEC.footer.color_token}});
  {{if FORMAT_SPEC.footer.italic == yes}}font-style: italic;{{end}}
}
{{end}}
```

**Rule 6: One CSS class per heading level identified in FORMAT_SPEC.headings**

The compiler emits one CSS rule per heading level recorded in FORMAT_SPEC.headings. Heading levels are not assumed; some samples use only H1 and H2, others use up to six distinct heading styles including italic and quoted variants.

```css
{{for level in FORMAT_SPEC.headings}}
{{level.selector}} {
  color: var({{level.color_token}});
  font-weight: {{level.weight}};
  font-size: {{level.font_size}}pt;
  margin: {{level.margin_top}}px 0 {{level.margin_bottom}}px 0;
  {{if level.italic == yes}}font-style: italic;{{end}}
  {{if level.letter_spacing}}letter-spacing: {{level.letter_spacing}}px;{{end}}
  {{if level.decorations contains "underline"}}text-decoration: underline;{{end}}
}
{{end}}
```

Where `{{level.selector}}` is a class name the compiler assigns based on the heading's semantic role (e.g., `h1.sec` for numbered top-level, `h2.sub` for numbered subsection, `.italic-subheading` for italic single-line headings like `Disclaimer -`).

**Rule 7: One CSS table style per distinct table type in FORMAT_SPEC.tables**

The compiler emits a separate selector per distinct table style. The standard document table style typically has cyan-blue or org-primary header band; a document-properties table may have no header band and a different border color.

```css
{{for table_style in FORMAT_SPEC.tables}}
table.{{table_style.class_name}} {
  border-collapse: collapse;
  width: 100%;
  table-layout: fixed;
}
table.{{table_style.class_name}} thead th {
  background: var({{table_style.header_band_token}});
  color: var({{table_style.header_text_token}});
  font-weight: {{table_style.header_text_weight}};
  text-align: {{table_style.header_text_align}};
  padding: {{table_style.header_padding_px}}px;
  font-size: {{table_style.header_font_size}}pt;
  border: {{table_style.cell_border_thickness_px}}px solid var({{table_style.header_band_token}});
}
table.{{table_style.class_name}} tbody td {
  border: {{table_style.cell_border_thickness_px}}px solid var({{table_style.cell_border_token}});
  padding: {{table_style.cell_padding_px}}px;
  color: var({{table_style.cell_text_token}});
  font-size: {{table_style.cell_font_size}}pt;
}
{{if table_style.row_striping != none}}
table.{{table_style.class_name}} tbody tr:nth-child(even) td { background: {{table_style.row_striping.even}}; }
{{end}}
{{end}}
```

**Rule 8: All SVGs are inlined directly, NEVER use `<symbol>` + `<use>`**

WeasyPrint has incomplete support for SVG `<symbol>` + `<use>` references; symbols defined in one location and referenced via `<use>` do not render. The logo, banner, flowchart shapes, and any other SVG must be inlined directly at every point of use, even if that means repeating SVG markup on multiple pages.

The compiler emits a Python helper inside the generated skill that holds each reusable SVG block as a string and inserts the string at every use site. This is mechanical and faster than maintaining `<use>`, with no rendering risk.

**Rule 9: Flowchart shape library is generated from FORMAT_SPEC.flowchart_vocabulary**

The compiler iterates over `FORMAT_SPEC.flowchart_vocabulary.shapes` and emits one SVG template per shape, substituting colors, stroke widths, and decorations from the spec. The shape templates are stored as string templates inside the generated skill so the document generation agent can compose flowcharts by interpolating coordinates and labels.

```html
{{for shape in FORMAT_SPEC.flowchart_vocabulary.shapes}}

{{if shape.shape == ellipse}}
<!-- {{shape.semantic_role}} ({{shape.when_used}}) -->
<ellipse cx="{X}" cy="{Y}" rx="{W}" ry="{H}"
         fill="{{shape.fill}}"
         stroke="var({{shape.stroke_token}})"
         stroke-width="{{shape.stroke_thickness_px}}"/>
<text x="{X}" y="{Y}"
      text-anchor="middle" dominant-baseline="middle"
      fill="var({{shape.text_color_token}})"
      font-weight="{{shape.text_weight}}"
      font-size="{{shape.text_size_px}}px">{label}</text>
{{end}}

{{if shape.shape == rounded_rectangle}}
<!-- {{shape.semantic_role}} ({{shape.when_used}}) -->
<rect x="{X}" y="{Y}" width="{W}" height="{H}"
      rx="{{shape.border_radius_px}}"
      fill="{{shape.fill}}"
      stroke="var({{shape.stroke_token}})"
      stroke-width="{{shape.stroke_thickness_px}}"/>
<text x="{X+W/2}" y="{Y+H/2}"
      text-anchor="middle" dominant-baseline="middle"
      fill="var({{shape.text_color_token}})"
      font-weight="{{shape.text_weight}}">{label}</text>
{{if shape.speaker_icon != none}}
<!-- speaker icon at {{shape.speaker_icon.position}} -->
<g transform="translate({X+W+5}, {Y-2})">
  <rect x="0" y="5" width="6" height="8" fill="var({{shape.speaker_icon.color_token}})"/>
  <polygon points="6,5 13,0 13,18 6,13" fill="var({{shape.speaker_icon.color_token}})"/>
  <path d="M 15 6 Q 18 9 15 12" stroke="var({{shape.speaker_icon.color_token}})" stroke-width="1.6" fill="none"/>
</g>
{{end}}
{{end}}

{{if shape.shape == diamond}}
<!-- {{shape.semantic_role}} ({{shape.when_used}}) -->
<polygon points="{X},{Y} {X+W},{Y+H/2} {X},{Y+H} {X-W},{Y+H/2}"
         fill="{{shape.fill}}"
         stroke="var({{shape.stroke_token}})"
         stroke-width="{{shape.stroke_thickness_px}}"/>
<text x="{X}" y="{Y+H/2}"
      text-anchor="middle" dominant-baseline="middle"
      fill="var({{shape.text_color_token}})"
      font-weight="{{shape.text_weight}}">{label}</text>
{{end}}

{{if shape.shape == hexagon}}
<!-- {{shape.semantic_role}} ({{shape.when_used}}) -->
<polygon points="{X},{Y} {X+30},{Y-15} {X+70},{Y} {X+70},{Y+30} {X+30},{Y+45} {X},{Y+30}"
         fill="{{shape.fill}}"
         stroke="var({{shape.stroke_token}})"
         stroke-width="{{shape.stroke_thickness_px}}"/>
<text x="{X+35}" y="{Y+15}"
      text-anchor="middle" dominant-baseline="middle"
      fill="var({{shape.text_color_token}})">{label}</text>
{{end}}

{{if shape.shape == pentagon_downward_banner}}
<!-- {{shape.semantic_role}} ({{shape.when_used}}) -->
<polygon points="{X},{Y} {X+W},{Y} {X+W},{Y+H} {X+W/2},{Y+H+tip} {X},{Y+H}"
         fill="var({{shape.fill_token}})"
         stroke="var({{shape.stroke_token}})"
         stroke-width="{{shape.stroke_thickness_px}}"/>
<text x="{X+W/2}" y="{Y+H/2}"
      text-anchor="middle" dominant-baseline="middle"
      fill="var({{shape.text_color_token}})"
      font-weight="{{shape.text_weight}}">{label}</text>
{{end}}

{{end}}
```

The compiler emits ONLY the shape templates that appear in FORMAT_SPEC.flowchart_vocabulary.shapes. Some samples have no flowcharts; in that case Rule 9 emits nothing.

**Rule 10: Conditional label colors driven by FORMAT_SPEC.flowchart_vocabulary.conditional_labels**

The compiler emits a small Python helper inside the generated skill that maps condition words to color tokens, using FORMAT_SPEC.flowchart_vocabulary.conditional_labels as the lookup table:

```python
LABEL_COLOR_MAP = {
{{for entry in FORMAT_SPEC.flowchart_vocabulary.conditional_labels}}
  {{for word in entry.conditions}}
    "{{word}}": "var({{entry.color_token}})",
  {{end}}
{{end}}
}

def label_color(condition_word):
    return LABEL_COLOR_MAP.get(condition_word, "var(--body)")
```

The document generation agent calls `label_color("Holiday")` and gets back the correct color variable. New condition words that the sample never recorded fall through to the body color token.

**Rule 11: PDF rendering chain**

The generated skill must use this rendering chain in order, falling back if a tool is unavailable:

1. Chrome headless print-to-PDF (best SVG fidelity, recommended primary):
   ```bash
   google-chrome --headless --no-sandbox --print-to-pdf=out.pdf --no-pdf-header-footer --print-to-pdf-no-header file://$(pwd)/input.html
   ```
2. WeasyPrint (good fallback if Chrome is unavailable, requires inlined SVGs):
   ```python
   from weasyprint import HTML; HTML('input.html').write_pdf('out.pdf')
   ```
3. pdfkit / wkhtmltopdf (additional fallback)
4. pandoc (last resort)

The compiler embeds all four commands in the generated skill so the agent picks the first available.

**Rule 11b: Post-render cleanup — only SOW.pdf delivered to client**

The generated skill must include a cleanup step immediately after the side-by-side verification pass confirms SOW.pdf is good. All intermediate build artefacts (sow.html, assets/, temp images, .py scripts, etc.) must be deleted from the output directory before signalling done. Only SOW.pdf remains for delivery.

The compiler must embed this exact cleanup block in the generated skill's final phase:
```bash
cd <output_dir> && find . ! -name 'SOW.pdf' ! -path '.' -delete && find . -empty -type d -delete
```

**Rule 12: HTML output — assets and self-containment**

The final HTML the generated skill produces must follow these rules:

- All CSS inside a `<style>` block in the `<head>`
- All SVG markup inlined at each use site (no external SVG files, no `<symbol>` + `<use>`)
- Fonts: use a Google Fonts CDN import for any font that is available there; for proprietary fonts not on Google Fonts (e.g. Calibri), install the font on the local machine or substitute the closest available metric-compatible font (e.g. `Carlito` for Calibri — same metrics, on Google Fonts). Always declare a system fallback (`Arial, sans-serif`).
- **Raster images (logos, badges, cover photos) use `file://` absolute paths**, not base64 and not relative paths. Resolve paths at HTML-generation time using `os.path.abspath()`:

  ```python
  import os

  def asset_src(relative_path):
      return "file://" + os.path.abspath(relative_path)

  # In the HTML template:
  # <img src="{asset_src('assets/{customer_slug}/image12.png')}" class="header-logo-right" />
  ```

  `file://` absolute URLs work in both Chrome headless and WeasyPrint. They are resolved from the local filesystem, not relative to the HTML file's location, so the HTML file can be saved anywhere.
- No external script dependencies
- Simple geometric graphics (banners, flowchart shapes, dividers) use inline SVG, never raster images.

The asset files referenced must exist on disk (extracted in Phase 1.3 Step L) before the HTML renderer is invoked.

---

**Worked Example (illustrative only, for reference, not part of the generated skill):**

If the compiler reads a sample where:
- FORMAT_SPEC.color_palette includes `{ name: "--cyan", hex: "#1FB5EC", usage: "strips and headings" }`
- FORMAT_SPEC.strips.top = `{ present: yes, thickness_px: 11, color_token: "--cyan" }`
- FORMAT_SPEC.headings includes `{ selector: "h1.sec", color_token: "--cyan", font_size: 22, weight: 900, margin_top: 0, margin_bottom: 18 }`

Then the compiler emits this CSS into the generated skill:

```css
:root { --cyan: #1FB5EC; /* strips and headings */ }
.strip-top { position: absolute; left: 0; right: 0; top: 0; height: 11px; background: var(--cyan); }
h1.sec { color: var(--cyan); font-weight: 900; font-size: 22pt; margin: 0 0 18px 0; }
```

If the compiler reads a different sample where colors and sizes differ (e.g., orange strip color, larger headings), it emits different concrete values for the same template. The compiler never assumes the example values above; it always reads from FORMAT_SPEC.

### 3.7 — Embed the Validation Checklist as Phase 5

```markdown
## PHASE 5 — Validation and Pixel-Match Verification

Before outputting, verify:

**Content checks:**
- [ ] All BLOCKING MOM fields populated (no [Q-N] placeholders remain)
- [ ] Correct pattern selected and applied
- [ ] All sections present and in correct order per FORMAT_SPEC.exact_heading_strings
- [ ] Heading strings character-for-character match FORMAT_SPEC.exact_heading_strings
- [ ] No content copied from the sample document (every section written fresh)
- [ ] Client name used consistently throughout
- [ ] Product knowledge accurate for this engagement type

**Visual fidelity checks (mandatory pixel-match verification):**
- [ ] All colors in output match FORMAT_SPEC.color_palette hex values exactly
- [ ] Top/bottom/left strips match FORMAT_SPEC.strips spec (color, thickness, position)
- [ ] Header layout matches FORMAT_SPEC.header (left zone, right zone, font, color)
- [ ] Footer layout matches FORMAT_SPEC.footer (zones, font, italic, page number format)
- [ ] Cover title block positioned per FORMAT_SPEC.cover.title_block (within 5% vertical tolerance)
- [ ] Cover banner shape and layer colors match FORMAT_SPEC.cover.banner
- [ ] Cover document properties table matches FORMAT_SPEC.cover.document_properties_table
- [ ] All headings use the class matching their FORMAT_SPEC heading level
- [ ] All tables use FORMAT_SPEC.tables specifications (header band color, cell borders, padding)
- [ ] All flowchart shapes drawn from FORMAT_SPEC.flowchart_vocabulary
- [ ] Conditional labels use FORMAT_SPEC.flowchart_vocabulary.conditional_labels color mapping
- [ ] Figure captions formatted per FORMAT_SPEC.flowchart_vocabulary.figure_caption

**Side-by-side comparison verification:**
- [ ] Render output PDF and sample PDF to JPEG at 110 DPI
- [ ] Build side-by-side comparison images for cover, document history, TOC, scope table, prereqs, deliverables, prompt list, escalation
- [ ] Inspect each comparison for visual gaps; log gaps
- [ ] Apply targeted refinements (CSS or SVG adjustments) and re-render until no visible gaps remain
```

---

## PHASE 4 — Save and Report

### 4.1 — Output location

`.claude/skills/generate-<customer-slug>-<doc-type>/SKILL.md`

### 4.2 — Save the skill file

Create the skill directory `.claude/skills/generate-<customer-slug>-<doc-type>/` and write the complete skill to `SKILL.md` inside it. The file must begin with the `name` + `description` frontmatter from Phase 3.1 so it is discoverable as a skill.

### 4.3 — Print summary

```
Document Generation Skill Compiled
  Customer/Org:           {{name}}
  Document type:          {{document_type_name}} ({{doc_type_slug}})
  Skill file:             .claude/skills/generate-<customer-slug>-<doc-type>/SKILL.md
  KB source:              {{kb_path}} ({{N}} files read)
  Format reference:       {{sample_filename}} (content NOT embedded, format only)

Format Spec captured:
  Color tokens:           {{N}} (palette listed in skill)
  Heading levels:         {{N}}
  Table styles:           {{N}}
  Flowchart shapes:       {{N}} with semantic mapping
  Conditional labels:     {{N}} color-to-condition mappings
  Special elements:       {{N}}
  Page chrome:            strips, header, footer, margins all measured
  Cover layout:           positioned per pixel coordinates

Content modelling:
  Sections modelled:      {{N}}
  Fixed legal blocks:     {{N}} (only org confidentiality/disclaimer)
  Product knowledge:      {{N}} products/modules embedded
  Section guides:         {{N}} writing instruction blocks
  MOM audit fields:       {{N}} BLOCKING, {{N}} IMPORTANT, {{N}} OPTIONAL
  Engagement patterns:    {{N}} patterns with selection rules

Render pipeline:
  HTML/CSS template:      embedded with :root color tokens
  SVG shape library:      embedded ({{N}} shape templates)
  Pixel-match protocol:   embedded (Phase 5)
  PDF renderers tried:    Chrome headless, WeasyPrint, pdfkit, pandoc

Next step:
  Run the generate-<customer-slug>-<doc-type> skill with mom=<path-to-mom-file>
```

---

## Critical Rules

1. **Sample serves two roles, not one.** The sample provides (a) the visual format — colors, layout, heading typography, table styles, section order, heading strings — which is extracted and embedded as FORMAT_SPEC; AND (b) the boilerplate template strings and field reference data — which are extracted via Phase 1.5 and 1.6 and embedded in the generated skill's 1B/1C catalogs. What is NEVER extracted from the sample: client-specific variable content (the client's name, their specific requirements, their approval matrices, their configuration decisions). Past client data is irrelevant to future clients; standard structural text and standard field tables are reusable.

2. **KB serves two roles, not one.** The KB provides (a) product knowledge — what each module does, how it works, what belongs in each section — which the generation agent draws on to write accurate VARIABLE content; AND (b) boilerplate markers — text explicitly marked as `BOILERPLATE (verbatim)` in the KB — which are extracted by Phase 1.5 and embedded as template strings in the 1B catalog. KB boilerplate text is NOT converted to writing instructions. It is embedded as the actual output string, with only client-name placeholders substituted.

3. **MOM is the client brief.** Every client-specific fact (name, requirements, flow, configuration, decisions, dates) comes from the MOM. No client detail is assumed from the sample or KB. The MOM populates the VARIABLE tier only.

4. **Four content tiers, not two.** The generated skill must apply the 4-tier content model to every section: FIXED_LEGAL (verbatim legal text), BOILERPLATE_TEMPLATE (verbatim structural text with placeholder substitution), STRUCTURED_REFERENCE_DATA (standard tables and reusable images inserted directly), and VARIABLE (client-specific content written fresh from MOM + KB). "Write fresh every time" applies ONLY to the VARIABLE tier. Writing fresh for BOILERPLATE_TEMPLATE or STRUCTURED_REFERENCE_DATA tiers is a fidelity error that produces wrong documents every time.

5. **The output skill is self-contained.** All product knowledge, format spec, writing instructions, SVG shape templates, CSS variables, and legal boilerplate must be embedded in the skill file, not referenced by path. The skill works even if the KB directory is deleted.

6. **Exact heading strings from sample.** Section headings must match the org's convention exactly (capitalisation, punctuation, ampersands, colon spacing) as observed in the sample. These are the only strings extracted verbatim from sample for use in output documents.

7. **Phase 0 is a hard gate.** BLOCKING MOM fields must be confirmed present before any writing begins. Missing BLOCKING fields go to DRAFT mode with `[Q-N: ...]` placeholders, never silently assumed.

8. **Pattern selection is explicit if-then, not judgment.** Engagement pattern selection rules must be deterministic signals derived from the KB, not open-ended guesses.

9. **No backwards references.** The generated skill must not say "as shown in the sample" or "refer to KB file X". All context is embedded inline.

10. **Every visual decision is a measured value.** No vague descriptors like "blue heading" or "small font". Every color is a hex code, every size is a pt or px number, every position is an inch or % offset. If a value cannot be measured precisely from the sample, record the best estimate and note the uncertainty.

11. **CSS color tokens are mandatory.** All colors in the generated HTML must reference `:root` CSS variables, never inline hex codes scattered through rules. This makes the document re-tintable by editing the token block alone.

12. **Inlined SVGs only.** Never use `<symbol>` + `<use>` patterns. WeasyPrint does not fully support them. Inline the SVG markup at every point of use, even if repeated across pages.

13. **Pixel-match verification is mandatory.** Every generated document must go through the Phase 5 side-by-side comparison loop. Stop iterating only when no visible gaps remain in the comparison images.

14. **Flowchart shape vocabulary is a contract.** Once FORMAT_SPEC.flowchart_vocabulary documents that "red ovals are start/end terminators" and "dark grey pentagons are queue endpoints", the agent must use those shapes for those semantics in every generated flowchart, with no substitution.

15. **Conditional label colors follow the documented mapping.** If FORMAT_SPEC says "orange for Holiday-like conditions, purple for affirmative paths, red for negative paths", every flowchart label must use that color rule. No improvisation.

16. **Render with Chrome print-to-PDF as primary, WeasyPrint as fallback.** Chrome has the best SVG fidelity. WeasyPrint is a reliable fallback if Chrome is unavailable. The skill must try them in order.

17. **Every heading level gets its own color token — no shared tokens without verified equality.** Never emit `color: var(--heading)` for both H1 and H2 without first confirming via pixel sampling that both levels are identical in color. If they differ by more than 5 in any RGB channel, create separate tokens (e.g., `--heading-primary`, `--heading-secondary`). Merging heading colors without verification is the single most common visual fidelity failure.

18. **Row striping is opt-in, not opt-out.** The default assumption for all tables is `row_striping: none`. Only add alternating row CSS after observing visible fill differences in the rendered sample. Do not add striping because it is "standard practice" or because another document uses it. Spurious striping changes the visual character of every table in the output.

19. **The TOC visual structure must be explicitly classified before any code is written.** Answer: is it a bordered data table with a header band, or is it a styled list/indented hierarchy? These require completely different HTML/CSS. A TOC rendered as a `<table>` when the sample uses a plain list (or vice versa) is immediately visible on the most-read page of the document.

20. **Header and footer text strings are extracted verbatim, never inferred.** Copyright lines, brand names, separator characters, and version slug formats must be copied character-by-character from the rendered image. If the sample's footer says "Ameyo", the skill embeds "Ameyo". If it says "Exotel", it embeds "Exotel". Context about what organisation is involved does not override what the pixels say. Inferred text will be wrong on every page of every future document.

21. **Every section must be checked for embedded images or non-CSS graphical blocks.** Approval procedure pages, signature blocks, letterhead graphics, and watermarks are commonly missed because they are hard to reproduce. Missing a graphical block produces an obviously incomplete page. The generated skill must extract every such image to `assets/{customer_slug}/` during compilation (Phase 1.3 Step L), record its path in `FORMAT_SPEC.assets`, and reference it via `file://` absolute path in the HTML template. Placeholders and gray div blocks are not acceptable — the asset directory is the solution to the size-limitation problem that makes base64 impractical for large images.

22. **Document type detection gates which capabilities the compiler activates.** Run Phase 1.4 detection before any content classification. The capabilities are independent switches driven by signals (Phase 1.4-C), not a fixed mode: documents with Role:/Report:/DM: footer patterns + field detail tables (e.g., BRDs) activate Phases 1.5, 1.6, Step L2, and the 4-tier content model; documents with drawable flow/decision diagrams (e.g., IVR SOWs) activate Step I flowchart vocabulary and the SVG shape library. Never apply the drawable-flowchart machinery to a document that has none — the resulting skill wastes context on shapes that don't exist and misses the boilerplate/structured-data extraction that the document does need.

23. **Field detail tables must be embedded in full — never sampled.** When Phase 1.6 identifies a FIELD_DETAIL table in the sample, all rows are extracted and stored in the 1C structured reference catalog. The generated skill inserts all rows at generation time. A rule that says "include representative fields" or "include key fields" produces a truncated table in every generated document — a visible, verifiable error. The correct rule is: all rows, always.

24. **Boilerplate template strings are embedded as output strings, not as instructions.** When the compiler embeds a Role: footer in the generated skill's 1B catalog, it embeds the actual string `"Role: The Management & Finance role users will be able to create, edit and view customer master records in NetSuite..."` — not the instruction `"Write a Role line describing who can access customer master records."` The generation agent must be able to pass this string directly to the HTML template with only [CLIENT_SHORT] substitution. Any instruction that asks the agent to compose or paraphrase boilerplate text will produce wrong text.

25. **REUSABLE_STANDARD section images are embedded assets, not placeholders.** When Step L2 classifies a section-body image as REUSABLE_STANDARD (standard process flow diagram that appears identically across all BRDs for this org), the compiler extracts it to `assets/{customer_slug}/`, records it in FORMAT_SPEC.section_images, and the generated skill renders it as `<img src="file://...">` at the correct section position. These images appear in every generated document without client input. CLIENT_SPECIFIC images use a placeholder div — the user is explicitly notified that the diagram must be inserted manually.

26. **DOCX-output skills must load the sample as a base document — never `Document()`.** This is the single most impactful styling rule for any generated skill that emits DOCX (typically documents built from a `.docx` sample, such as BRDs). The correct initialisation is `doc = Document(sample_path)` followed by stripping all body content while preserving the `sectPr` element. This one line guarantees that styles, the Office theme, header images, footer text, page margins, and `contextualSpacing` are all inherited exactly from the sample. Creating a blank `Document()` and then manually recreating styles via `_ensure_style()` will always produce deviations — no matter how carefully the FORMAT_SPEC values are specified — because Word's style inheritance chain, the Office theme XML, and the `docDefaults` element cannot be faithfully reproduced by hand. Any generated DOCX skill that contains `doc = Document()` without immediately stripping it of a loaded sample is non-compliant with this rule and must be regenerated.
