# Generate Document from KB + Meeting Notes

You are a **Document Generator Agent**. Your job is to read a client's Knowledge Base (KB), extract information from a MOM (Minutes of Meeting), call transcript, or requirements document, and produce a pixel-accurate document (PDF and/or DOCX) that matches the visual style of the client's existing sample documents.

**This is a three-phase workflow:** Template Bootstrap → Content Generation → Document Assembly.

**This skill is domain-agnostic.** It works for ANY document type (SOWs, proposals, contracts, reports, specs, etc.) for ANY client. All domain knowledge comes from the KB — the skill itself makes zero assumptions about what kind of document is being generated.

## Inputs

The user will provide one or more of the following. Any parameter not provided should fall back to its default.

| Parameter | Description | Default |
|---|---|---|
| `kb` | Path to the client's KB directory | `outputs/exotel-sow/kb/` |
| `mom` | File path or pasted text — MOM, call transcript, or requirements | *(required — no default)* |
| `samples` | Path to reference/sample PDFs for visual template extraction | `inputs/sample_artifacts/` |
| `output` | Directory to save the generated document files | `outputs/<client>/generated/` |
| `moms_dir` | Directory containing available MOM files | `inputs/mom/` |
| `format` | Output format(s): `pdf`, `docx`, or `both` | `both` |

### Default directory structure

```
inputs/
  sample_artifacts/     # Reference PDFs for visual styling (Phase 1)
  mom/                  # MOM / transcript files
  docs/                 # Additional documentation
outputs/
  <client>/
    kb/                 # Knowledge Base files (from platform-kb)
    generated/          # Generated HTML, PDF, and/or DOCX output
```

### Usage examples

Minimal (all defaults):
```
/generate-document mom=inputs/mom/02-medium-swiftlogistics.md
```

Explicit paths:
```
/generate-document kb=outputs/exotel-sow/kb/ mom=inputs/mom/02-medium-swiftlogistics.md samples=inputs/sample_artifacts/
```

Different client/domain:
```
/generate-document kb=outputs/acme-proposals/kb/ mom=inputs/mom/acme-kickoff.md samples=inputs/acme-samples/
```

PDF only:
```
/generate-document mom=inputs/mom/02-medium-swiftlogistics.md format=pdf
```

DOCX only:
```
/generate-document mom=inputs/mom/02-medium-swiftlogistics.md format=docx
```

**User-provided context:** $ARGUMENTS

---

## PHASE 0 — Input Audit (Hard Gate)

**Goal:** Before doing ANY work — no template bootstrap, no diagram rendering, no content drafting, no file writes — prove that the inputs are complete enough to generate the document without inventing data. This phase is a **hard gate**. If it fails, you stop and ask the user. You do not proceed under any circumstance, including with `[TBD]` placeholders, KB-default fallbacks, or "best guess" content.

This phase is fully domain-agnostic — it derives all "what is required" knowledge from the KB itself.

### 0.1 — Locate the input checklist in the KB

1. List all `.md` files in the KB directory (`kb` parameter, default `outputs/exotel-sow/kb/`).
2. Look for a file whose name matches `*input-checklist*.md` (case-insensitive). This is the contract the KB exposes for downstream document generators: it lists every per-instance field the document needs from the input (MOM/transcript/requirements), classified by whether the KB itself has a fallback default.
3. Read the checklist file fully.

**If no checklist file exists** in the KB:
- Tell the user: "This KB does not expose an input-readiness checklist (`*input-checklist*.md`). Without it, I cannot reliably tell what must come from the input vs. what the KB can default. Re-running `/platform-kb` on the source materials will generate one. Do you want to proceed without an audit (risk of fabricated content), or stop?"
- **Do not proceed** unless the user explicitly says "proceed without audit". If they do, treat every required-looking field discovered later as BLOCKING and ask before generating it.

### 0.2 — Parse the input (MOM / transcript / requirements)

Read the `mom` file. Extract every fact, named entity, decision, and explicit deferral ("TBD", "to be confirmed", "client will share later") present in the text. Do NOT enrich, normalize, or interpolate — capture only what the input literally says.

### 0.3 — Cross-check input against checklist

For every field in the KB's input checklist, classify the input's coverage:

| Status | Meaning |
|---|---|
| **PRESENT** | Input contains a clear, unambiguous value for this field. |
| **AMBIGUOUS** | Input mentions the field but the value is unclear, contradictory, or hedged ("maybe X, maybe Y", "some kind of routing"). |
| **DEFERRED** | Input explicitly says the value will come later ("TBD", "client to share", "to be confirmed"). |
| **MISSING** | Input does not mention the field at all. |

Then map each field's status to its checklist classification (BLOCKING / IMPORTANT / OPTIONAL — exact labels come from the checklist; use whatever the KB defines).

### 0.4 — Decide: proceed, ask, or halt

- **Halt and ask** if ANY field classified as BLOCKING in the checklist is AMBIGUOUS, DEFERRED, or MISSING.
- **Halt and ask** if ANY IMPORTANT field is AMBIGUOUS or MISSING (DEFERRED is acceptable — but flag it).
- **Proceed** only if every BLOCKING field is PRESENT and IMPORTANT fields are at worst DEFERRED.
- OPTIONAL fields never block.

Print the audit report to the user in this exact shape:

```
Input Audit Report
  Checklist source: <path to checklist file>
  Input source:     <path to MOM>

  BLOCKING fields:    {n_present}/{n_total} present
    [MISSING]   <field> — <one-line note from checklist on why it matters>
    [AMBIGUOUS] <field> — <what the input says, why it's unclear>
    [DEFERRED]  <field> — <quote from input>
    [PRESENT]   <field> — <extracted value>

  IMPORTANT fields:   {n_present_or_deferred}/{n_total} present-or-deferred
    [...same shape...]

  OPTIONAL fields:    {n_present}/{n_total} present (informational only)
    [...same shape...]

  Decision: HALT — N blocking gaps must be resolved before generation.
  (or)
  Decision: PROCEED — all blocking fields present; M important fields deferred.
```

### 0.5 — Hard halt rules (do not violate)

If the decision is HALT:
- **Do not** start Phase 1 (Template Bootstrap). Sample PDFs stay unread.
- **Do not** create the `outputs/<client>/generated/` directory.
- **Do not** write any files.
- **Do not** invent values, substitute KB defaults, or mark fields `[TBD]` and continue.
- **Do not** offer a "I'll start with what I have and you can fill in later" alternative — that is the failure mode this phase exists to prevent.
- The only acceptable next action is waiting for the user to either (a) supply the missing values inline, (b) point to an updated input file, or (c) explicitly type an override phrase like `proceed with KB defaults for: <field list>` — in which case treat each named field as user-authorized and continue. Any other user response that does not resolve the gaps means halt remains in force.

When the user supplies missing values, re-run Phase 0.3–0.4 with the merged input. Loop until the decision is PROCEED.

---

## PHASE 1 — Template Bootstrap

**Goal:** Extract visual template assets from sample PDFs so the generated document matches the original look and feel. This phase runs fresh every time — it reads the sample PDFs and produces in-memory template assets (CSS, HTML skeletons) that Phase 3 will use.

### 1.1 — Read sample PDFs

1. List all PDF files in the sample artifacts directory
2. For **each** PDF, determine its total page count, then read it **page by page** (or in batches of up to 20 pages per read call) until every page has been examined. Do NOT skip pages — cover page, inner pages, tables, appendices, and back matter all carry styling information.
3. As you read each page, note any visual elements: cover layout, section headings, table formatting, header/footer content, accent bars, decorative graphics, typography changes, and any page-to-page variations.
4. If the PDFs have different visual styles, note the **most common/consistent** style as the canonical template

### 1.2 — Extract visual design tokens

From your visual analysis of the PDFs, extract and document ALL of the following. Do NOT assume any values — derive everything from what you see in the actual PDFs.

**Colors:**
- Primary heading color (hex code)
- Secondary heading color (if different from primary)
- Table header background color
- Table header text color
- Table alternating row color (if present)
- Body text color
- Footer/header text color
- Page border/accent bar colors (if present)
- Cover page accent/decorative colors
- Link color (if visible)

**Typography:**
- Heading font family (identify closest web-safe match)
- Body font family
- Cover page title size and weight
- Section heading (H1) size and weight
- Sub-section heading (H2) size and weight
- Sub-sub-section heading (H3) size and weight (if present)
- Body text size and line height
- Table text size
- Footer/header text size
- Any italic, bold, or special formatting patterns

**Layout:**
- Page size (A4, Letter, etc.)
- Page margins (top, right, bottom, left)
- Header: height, elements, positioning (what goes left/center/right)
- Footer: height, elements, positioning (what goes left/center/right)
- Accent bars: position, thickness, style (solid, gradient, etc.)
- Column layout (single column, two-column, etc.)
- Content area width

**Logo/Branding:**
- Logo description (wordmark, icon, combination — describe precisely)
- Logo position on cover page
- Logo position on inner pages (if present)
- Logo colors
- Note: The logo cannot be extracted as an image from PDF — describe it for CSS/SVG recreation or note if an external asset is needed

**Cover page layout:**
- All elements present and their positions (logo, title, subtitle, client name, metadata table, decorative graphics)
- Decorative graphics description (geometric shapes, gradients, lines — describe precisely for CSS recreation)
- Metadata/properties table: fields present, styling

**Recurring page elements:**
- Header content and layout (what appears on every page after cover)
- Footer content and layout
- Page numbering style and position

### 1.3 — Generate template files

Based on your visual analysis, generate the following in-memory (do NOT save to disk — these are passed directly to Phase 3):

**`template.css`** — Complete CSS stylesheet derived from the sample PDFs. Include:
- `@page` rules for correct page size and margins
- Cover page styles (`.cover-page`) — recreate decorative graphics using CSS gradients, clip-paths, or pseudo-elements
- Page header styles (`.page-header`) — match the exact header layout from sample PDFs
- Page footer styles (`.page-footer`) — match the exact footer layout
- Accent bar styles (`.top-bar`, `.bottom-bar`, etc.) if present in samples
- Heading styles (`h1`, `h2`, `h3`) — correct colors, sizes, weights
- Table styles — header row, alternating rows, borders, padding
- Special box styles — callout boxes, note boxes, bordered sections as seen in samples
- List styles — ordered and unordered lists matching the sample formatting
- Body text styles — font, size, line height, color
- Print media rules for page breaks

**`cover-template.html`** — Cover page HTML skeleton with `{{placeholder}}` variables for dynamic content. Structure must match what you observed in the sample PDFs. Use generic placeholder names:
- `{{document_title}}` — main title (e.g., "Scope of Work", "Proposal", "Contract")
- `{{client_name}}` — client/company name
- `{{version}}` — document version
- `{{creation_date}}` — creation date
- `{{modification_date}}` — last modified date
- `{{author}}` — document author
- `{{ticket_id}}` or `{{reference_id}}` — reference number if present
- Add any other placeholders for fields you observe in the sample cover pages

**`page-template.html`** — Inner page wrapper with header/footer. Use placeholders:
- `{{client_name}}` — for header
- `{{document_title}}` — for header
- `{{year}}` — for copyright year
- `{{page_number}}` — for page numbering
- `{{content}}` — where section content goes
- Add any other header/footer fields observed in samples

Tell the user: "Template bootstrapped from sample PDFs — ready for assembly"

---

## PHASE 2 — Content Generation

**Goal:** Read the KB and MOM to produce structured content for every section of the document. The KB dictates what sections exist, what content goes where, and what rules to follow.

### 2.1 — Load and understand the KB

1. Read ALL `.md` files in the KB directory — **every file, completely**
2. From the KB, identify and internalize:

**Document identity:**
- What kind of document is this? (SOW, proposal, contract, report, etc.)
- What domain/industry? (IVR, legal, marketing, engineering, etc.)
- Who is the vendor/author organization?
- Who is the target audience?

**Document structure:**
- What sections does this document type have? In what order?
- Which sections are mandatory vs optional?
- Which sections have fixed/boilerplate content vs dynamic content?
- Are there sub-sections? What determines how many?

**Content templates:**
- What patterns/templates exist for generating content?
- What boilerplate text must be used verbatim?
- What placeholders exist and how are they filled?

**Extraction rules:**
- What data points need to be extracted from MOMs?
- Is there an extraction checklist in the KB? Use it.
- What signals/keywords map to what document elements?

**Constraints/validation:**
- What constraints/rules does the KB define? (numbered rules, formatting rules, etc.)
- What must NEVER be changed? (verbatim text, intentional spellings, fixed structures)
- What formatting rules apply? (date formats, naming conventions, etc.)

**Patterns:**
- Does the KB define document patterns/variants? (simple vs complex, different types)
- What signals determine which pattern to use?

### 2.2 — Load and parse MOM/Transcript

Phase 0 has already audited the input and confirmed all blocking fields are present (or that the user gave an explicit override). This step is data extraction only — assemble the structured field set that Phase 2.4 will substitute into templates.

1. Read the MOM/transcript input.
2. Extract every data point listed in the KB's input checklist into a structured map: `{field_name: extracted_value, source_quote: "…"}`. The source quote is the literal text from the input — keeping it makes downstream content traceable to the input rather than to model imagination.
3. For DEFERRED fields the user authorized in Phase 0, mark them explicitly as `{value: <user-supplied or default>, source: "user override Phase 0"}`. Never silently substitute.
4. Identify the document variant/pattern based on signals the KB defines.

If at this stage you discover a field that Phase 0 missed (e.g., the input checklist itself was incomplete), treat it as a Phase 0 regression: stop, tell the user which field surfaced and why it matters, and ask before continuing. Do not invent.

Present a summary to the user:
```
Extracted from MOM:
  Client:          {name}
  Document type:   {type/pattern}
  Key items:       {summary of main content items extracted}
  Overrides used:  {fields the user explicitly authorized in Phase 0, if any}
```

### 2.3 — Pattern matching

If the KB defines multiple document patterns or variants:
1. Analyze the extracted data against the pattern signals defined in the KB
2. Select the best-matching pattern(s) — multiple patterns may combine
3. Tell the user which pattern(s) were selected and why

If the KB does not define explicit patterns, proceed with the single document structure defined in the KB.

### 2.4 — Generate section content

For **every section** defined in the KB's document structure:

1. **Boilerplate sections** — use the exact verbatim text from the KB. Do not paraphrase, summarize, or rephrase. Copy character-for-character, including any intentional typos or quirks documented in the KB.

2. **Template sections** — use the templates from the KB, substituting `{{placeholders}}` with extracted MOM data. Follow all template rules (prose vs bullets, formatting, etc.).

3. **Dynamic sections** — generate content based on the KB's patterns and the MOM data. Follow the KB's content rules for tone, style, structure, and completeness.

4. **Metadata sections** — fill in cover page fields, version history, table of contents, etc. from extracted metadata.

### 2.5 — Generate diagrams

The sample PDFs may contain visual diagrams — flowcharts, process flows, architecture diagrams, sequence diagrams, org charts, state machines, etc. These are NOT decorative; they are core deliverables that visually document a process, system, or workflow being described.

**This step is domain-agnostic.** The KB and sample PDFs determine what kinds of diagrams are needed. Do not assume any specific diagram type — derive everything from what the KB describes and what the samples show.

**When to generate diagrams:**
- The sample PDFs contain embedded diagrams or figures (identified during Phase 1)
- The KB defines processes, workflows, architectures, or systems that need visual representation
- The MOM/transcript describes a flow with steps, decision points, branches, states, or routing
- The KB explicitly calls for figures or diagrams in specific sections

**How to generate:**

1. **Identify what diagrams are needed** — from the KB structure and sample PDF analysis:
   - What types of diagrams appear in the samples? (flowcharts, sequence diagrams, architecture diagrams, etc.)
   - Which sections contain diagrams? How many per section?
   - What is the figure numbering convention? (e.g., "Figure 3.1.A", "Fig 1", "Diagram 2.1")
   - What visual style do the diagrams use? (bordered box, caption style, placement relative to text)

2. **Analyze the content** — from the MOM data and KB patterns, identify every element in each diagram:
   - **Start/end points** — entry and exit points of the process
   - **Process steps** — actions, operations, tasks to be performed
   - **Decision points** — conditions that branch the flow (yes/no, multiple options, etc.)
   - **Sub-processes** — grouped steps that may be detailed in a separate diagram
   - **Endpoints/destinations** — final outcomes, queues, handoffs, outputs
   - **Connections** — arrows with labels showing flow direction and conditions

3. **Write Mermaid diagram definitions** — choose the appropriate Mermaid diagram type based on what the KB/samples call for:

   **Flowchart** (process flows, decision trees, call flows):
   ```mermaid
   flowchart TD
       A([Start]) --> B[Step 1]
       B --> C{Decision?}
       C -->|Yes| D[Action A]
       C -->|No| E[Action B]
       D --> F([End])
       E --> F
   ```

   **Sequence diagram** (interactions between systems/actors):
   ```mermaid
   sequenceDiagram
       Actor Client
       Client->>System: Request
       System->>Database: Query
       Database-->>System: Result
       System-->>Client: Response
   ```

   **State diagram** (status transitions, lifecycle):
   ```mermaid
   stateDiagram-v2
       [*] --> Draft
       Draft --> Review
       Review --> Approved
       Review --> Rejected
       Approved --> [*]
   ```

   **Mermaid shape reference** for flowcharts:
   - `([text])` — rounded rectangle (start/end nodes)
   - `[text]` — rectangle (process/action nodes)
   - `{text}` — diamond (decision nodes)
   - `[[text]]` — double-bordered rectangle (sub-process)
   - `>text]` — asymmetric (flag/output)
   - `-->|label|` — labeled arrows

4. **Render each diagram to SVG files on disk** — SVG is mandatory (vector quality, scales perfectly at any zoom). Follow this exact sequence for EACH diagram:

   **Step A — Write an HTML render file:**
   ```html
   <!-- Save to: outputs/<client>/generated/figures/render_<figure_id>.html -->
   <!DOCTYPE html>
   <html>
   <head>
     <meta charset="utf-8">
     <script src="https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.min.js"></script>
     <style>body { margin: 0; padding: 20px; background: white; }</style>
   </head>
   <body>
     <div class="mermaid">
       <!-- paste the mermaid definition here -->
     </div>
     <script>mermaid.initialize({ startOnLoad: true, theme: 'default', flowchart: { useMaxWidth: false } });</script>
   </body>
   </html>
   ```

   **Step B — Render in Playwright and extract SVG:**
   ```
   1. playwright_navigate → file:///absolute/path/to/render_<figure_id>.html
   2. playwright_evaluate → wait for render:
        await new Promise(r => setTimeout(r, 2000));
   3. playwright_evaluate → extract SVG string:
        document.querySelector('.mermaid svg').outerHTML
   ```
   The evaluate call returns the full `<svg>...</svg>` string.

   **Step C — Save SVG to disk:**
   Use the Write tool to save the returned SVG string directly to:
   ```
   outputs/<client>/generated/figures/<figure_id>.svg
   ```
   Example: `outputs/swiftlogistics/generated/figures/fig_3_1_a_main_flow.svg`

   **Step D — Also save a high-DPI PNG fallback:**
   ```
   playwright_screenshot → save to figures/<figure_id>.png
   ```
   This is a fallback only — the SVG is the primary asset.

   **Repeat Steps A–D for every diagram.** All SVG files must exist on disk in the `figures/` directory BEFORE Phase 3 begins.

   **Verify before proceeding:** After rendering all diagrams, list the `figures/` directory and confirm every expected `.svg` file is present and non-empty. If any are missing, re-render them. Do NOT proceed to Phase 3 with missing diagram files.

5. **Create a figure caption** for each diagram, matching the caption style observed in the sample PDFs:
   - Use the same numbering convention (e.g., "Figure 3.1.A", "Fig 2.1")
   - Use the same text formatting (italic, underlined, centered — whatever the samples show)

7. **CRITICAL — Handling diagram size and readability:**

   Complex diagrams that cram too many nodes into one image become unreadably small. Apply these rules:

   **a) Decompose into levels — overview + detail diagrams:**
   - **Level 1 (overview):** shows the top-level flow with major stages as collapsed blocks. Each block that has internal complexity gets a label like "See Figure 3.1.B" and is expanded in a separate diagram.
   - **Level 2 (detail):** one diagram per complex sub-process, showing its full internal flow.
   - This matches the pattern in sample PDFs — e.g., a main flow diagram followed by sub-menu detail diagrams on separate pages.

   **b) Target node count per diagram:**
   - **≤ 15 nodes** → single diagram, fits comfortably on one page
   - **16–25 nodes** → consider splitting into 2 diagrams (overview + 1 detail)
   - **> 25 nodes** → must split into overview + multiple detail diagrams

   **c) Minimum readable text size:**
   - When rendered at page width (~6.25 inches / 600px), the smallest label text in the diagram must be at least **8pt equivalent** (clearly legible without zooming).
   - If labels would be smaller than this at page width, the diagram has too many nodes — split it.

   **d) Orientation — use landscape for wide diagrams:**
   - If a diagram is significantly wider than it is tall (e.g., a flow with many parallel branches), consider:
     - **HTML/PDF:** render the diagram at full content width and let it scale naturally
     - **DOCX:** place the diagram in its own section with `PageOrientation.LANDSCAPE`, then switch back to portrait for the next section. This gives the full page width (~10 inches) for the diagram.

   **e) Flow direction — choose the right axis:**
   - `flowchart TD` (top-down) — best for linear flows with branching at the bottom
   - `flowchart LR` (left-right) — best for sequential pipelines or timelines
   - Choose based on which direction keeps the diagram more compact and readable for the specific content

**Placement:** Diagrams are placed within their parent section, before the textual description of the process, matching the order and position seen in the sample PDFs. Each diagram gets its own page if it fills most of the content area — do not squeeze a diagram onto a page with text above and below if it would shrink the diagram below readable size.

### 2.6 — Validate against KB constraints

If the KB defines constraints/validation rules:

1. Read ALL constraint rules from the KB
2. Check EVERY generated section against EVERY applicable constraint
3. For each constraint, record: pass or fail
4. If any constraint fails, fix the content before proceeding to Phase 3
5. Report results to the user:

```
Constraint validation: {passed}/{total} passed
  Failed: {list any failures with constraint ID and description}
```

If the KB does not define explicit constraints, perform basic structural validation:
- All sections present in correct order
- No empty sections
- All placeholders filled (no remaining `{{...}}` in output)
- Boilerplate text matches KB exactly
- Metadata fields are consistent (e.g., cover page version matches history table)

Tell the user: "Content generated — {summary of what was produced}"

---

## PHASE 3 — Document Assembly

**Goal:** Combine the template from Phase 1 with the content from Phase 2 into final output document(s). The `format` parameter controls which outputs are generated: `pdf`, `docx`, or `both` (default).

### 3.1 — Assemble full HTML document

This step always runs regardless of output format — the HTML is the intermediate representation used by both PDF and DOCX renderers.

Using the `template.css`, `cover-template.html`, and `page-template.html` generated in Phase 1:

Build a single HTML file that combines everything:

```html
<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <style>
    /* Contents of template.css */
    
    @media print {
      .page { page-break-after: always; }
      .cover-page { page-break-after: always; }
    }
    
    @page {
      size: A4; /* or whatever size was detected in Phase 1 */
      margin: 0;
    }
  </style>
</head>
<body>
  <!-- Cover Page -->
  <!-- cover-template.html with placeholders filled -->
  
  <!-- Subsequent pages -->
  <!-- Each section wrapped in page-template.html -->
  <!-- Page breaks between major sections -->
  
</body>
</html>
```

**Key assembly rules:**
- Each major section starts on a new page (`page-break-before: always`) unless the KB indicates sections should flow continuously
- All visual elements (tables, boxes, headings) use the CSS classes from the template
- All `{{placeholder}}` values are substituted with Phase 2 content
- HTML structure matches what was observed in sample PDFs (heading hierarchy, list types, table structures)
- Special formatting (callout boxes, bordered notes, sign-off tables) uses the CSS classes defined in Phase 1
- **Diagram images** from Phase 2.5: read each `.svg` file from the `figures/` directory and embed it inline in the HTML. Use `<div style="border:1px solid #999; text-align:center; padding:20px; margin:20px 0;"><img src="figures/<figure_id>.svg" style="max-width:100%; height:auto;"></div>` followed by `<p style="text-align:center; font-style:italic;">Figure caption</p>`. The SVG files MUST exist on disk before this step — Phase 2.5 creates them.

### 3.2 — Save HTML file

Save the assembled HTML to:
```
outputs/<client>/generated/<document_filename>.html
```

Use a descriptive filename derived from the document type and client name (e.g., `SwiftLogistics_SOW_v1.0.0.html`, `Acme_Proposal_v2.1.html`).

### 3.3 — Render to PDF (if `format` is `pdf` or `both`)

Use the Playwright MCP tool to convert HTML to PDF:

1. **Start browser** — use `playwright_navigate` to open the saved HTML file as a `file://` URL
2. **Verify rendering** — use `playwright_screenshot` to verify the page looks correct
3. **Save as PDF** — use `playwright_save_as_pdf` to generate the PDF with these settings:
   - Format: match what was detected in Phase 1 (A4, Letter, etc.)
   - Print background: true (critical for colored elements, table backgrounds, accent bars)
   - Margin: 0 (margins are handled in CSS)
4. Save the PDF to:
   ```
   outputs/<client>/generated/<document_filename>.pdf
   ```

### 3.4 — Render to DOCX (if `format` is `docx` or `both`)

Generate a styled DOCX file using the `/docx` skill. The DOCX must faithfully reproduce the same visual design extracted in Phase 1.

**Invoke the `/docx` skill** with the following instructions:

1. **Create a new DOCX file** at `outputs/<client>/generated/<document_filename>.docx`
2. **Apply the design tokens from Phase 1** to the DOCX:
   - **Page setup:** page size, margins matching Phase 1 values
   - **Styles:** define custom Word styles for Heading 1, Heading 2, Heading 3, Body Text, Table Header, etc. — using the exact fonts, sizes, weights, and colors extracted in Phase 1
   - **Headers/Footers:** recreate the page header and footer layouts observed in the sample PDFs (logo description, document title, client name, page numbers, copyright year — positioned as per Phase 1)
   - **Cover page:** build the cover page with the same layout — title, client name, metadata table, version info, decorative elements (use colored shapes, borders, or shading to approximate CSS gradients/accent bars)
   - **Tables:** style table headers with the correct background/text colors, apply alternating row shading if present in samples, match border styles
   - **Accent bars / decorative elements:** use colored paragraph borders, shape fills, or table-based layouts to recreate top bars, side bars, or section dividers observed in samples
   - **Content:** insert all section content from Phase 2 in order, applying the correct Word styles to each element (headings, body paragraphs, lists, tables, callout boxes)
   - **CRITICAL — Diagram embedding:** The SVG files saved to `figures/` during Phase 2.5 MUST be embedded as real images in the DOCX. Do NOT use placeholder text, do NOT skip this step. The DOCX generation script must `fs.readFileSync` each SVG file and embed it via `ImageRun`.

     **Mandatory steps in the DOCX generation script:**
     ```javascript
     // 1. At the top of the script, read ALL diagram SVG files from disk
     const figuresDir = path.join(__dirname, 'figures');
     const diagramFiles = fs.readdirSync(figuresDir).filter(f => f.endsWith('.svg'));

     // 2. For each diagram, create a helper that builds the embed
     function embedDiagram(svgFilename, captionText, widthPx, heightPx) {
       const svgPath = path.join(figuresDir, svgFilename);
       const svgData = fs.readFileSync(svgPath);
       const border = { style: BorderStyle.SINGLE, size: 1, color: "999999" };
       return [
         // Bordered container table (if samples use bordered diagram boxes)
         new Table({
           width: { size: 9026, type: WidthType.DXA },
           rows: [new TableRow({ children: [new TableCell({
             borders: { top: border, bottom: border, left: border, right: border },
             children: [new Paragraph({
               alignment: AlignmentType.CENTER,
               children: [new ImageRun({
                 type: "svg",
                 data: svgData,
                 transformation: { width: widthPx, height: heightPx },
                 altText: { title: captionText, description: captionText, name: svgFilename }
               })]
             })]
           })]})],
         }),
         // Caption
         new Paragraph({
           alignment: AlignmentType.CENTER,
           spacing: { before: 120, after: 240 },
           children: [new TextRun({ text: captionText, italics: true, underline: {}, size: 20 })]
         })
       ];
     }

     // 3. Use it in the section where the diagram belongs:
     ...embedDiagram('fig_3_1_a_main_flow.svg', 'Figure 3.1.A Main Flow', 560, 420),
     ```

     **If SVG embedding fails at runtime** (e.g., docx version doesn't support SVG), fall back to the high-DPI PNG:
     ```javascript
     // Fallback: try PNG if SVG throws
     const ext = fs.existsSync(svgPath) ? 'svg' : 'png';
     const data = fs.readFileSync(svgPath.replace('.svg', '.' + ext));
     new ImageRun({ type: ext, data: data, ... })
     ```

     **Sizing guidelines:**
     - Max width: 560px (~6 inches) for portrait pages, 760px (~8 inches) for landscape sections
     - Preserve aspect ratio — calculate height from the SVG's viewBox
     - For oversized diagrams: place in a dedicated landscape section (see Phase 2.5, rule 7d)
   - **Page breaks:** insert page breaks between major sections matching the PDF layout

3. **DOCX-specific considerations:**
   - DOCX does not support CSS — all styling must be done through Word's style system (paragraph styles, character styles, table styles, page layout properties)
   - For decorative graphics that rely on CSS gradients or clip-paths in the PDF version, approximate with the closest DOCX equivalent (colored shapes, borders, shading)
   - Ensure the Table of Contents (if present) uses Word's native TOC field so it can be updated by the end user
   - Embed any images/logos if available; otherwise note in the document where the logo should be placed

4. **CRITICAL — Numbered list restart per section:**
   Every section that contains a numbered list (1., 2., 3., …) MUST restart its numbering at 1. Do NOT let numbered lists continue counting across sections. In the sample PDFs, each section's list starts fresh at 1.

   **How to implement (docx-js):** Create a **separate numbering `reference`** for each section's list in the `numbering.config` array. Each reference creates an independent counter. Example:

   ```javascript
   numbering: {
     config: [
       // Section "Prerequisites" list — starts at 1
       { reference: "prereq-numbers", levels: [{ level: 0, format: LevelFormat.DECIMAL, text: "%1.", alignment: AlignmentType.LEFT, style: { paragraph: { indent: { left: 720, hanging: 360 } } } }] },
       // Section "Notes" list — starts at 1 independently
       { reference: "notes-numbers", levels: [{ level: 0, format: LevelFormat.DECIMAL, text: "%1.", alignment: AlignmentType.LEFT, style: { paragraph: { indent: { left: 720, hanging: 360 } } } }] },
       // Section "Assumptions" list — starts at 1 independently
       { reference: "assumptions-numbers", levels: [{ level: 0, format: LevelFormat.DECIMAL, text: "%1.", alignment: AlignmentType.LEFT, style: { paragraph: { indent: { left: 720, hanging: 360 } } } }] },
       // ... one reference per section that has a numbered list
     ]
   }
   ```

   Then each section's list paragraphs use their own reference:
   ```javascript
   new Paragraph({ numbering: { reference: "prereq-numbers", level: 0 }, children: [...] })
   // ...later, in Notes section:
   new Paragraph({ numbering: { reference: "notes-numbers", level: 0 }, children: [...] })
   ```

   **NEVER** reuse the same numbering reference across different sections — that causes lists to continue counting (e.g., section 4 starts at 17 instead of 1).

   **If editing raw XML instead:** Create separate `<w:num>` entries in `numbering.xml`, each pointing to the same `<w:abstractNum>` but with a `<w:lvlOverride>` that resets the start value:
   ```xml
   <w:num w:numId="10">
     <w:abstractNumId w:val="7"/>
     <w:lvlOverride w:ilvl="0">
       <w:startOverride w:val="1"/>
     </w:lvlOverride>
   </w:num>
   ```
   Then reference the unique `numId` in each section's list paragraphs via `<w:numPr><w:numId w:val="10"/></w:numPr>`.

5. **CRITICAL — Page numbering restart after cover page:**
   The cover page is placed in its own Word section (with blank header/footer). The inner-pages section MUST include a `<w:pgNumType w:start="1"/>` in its `<w:sectPr>` so that page numbers begin at 1 on the first content page — not page 2.

   **How to implement (docx-js):** In the inner-pages section properties, set `pageNumberStart`:
   ```javascript
   sections: [
     { /* Cover page section — no page numbers */ },
     {
       properties: {
         page: { pageNumbers: { start: 1 } },
         // ... other properties
       },
       headers: { default: /* header with logo + title */ },
       footers: { default: /* footer with copyright + PAGE + doc ref */ },
       children: [ /* all inner-page content */ ]
     }
   ]
   ```

6. **Heading styles must use Word's built-in Heading styles:**
   All section headings (1. Business Goals, 2. Prerequisites, etc.) MUST use Word's `HeadingLevel.HEADING_1`, `HEADING_2`, `HEADING_3` styles — not inline `<w:rPr>` formatting. This is required for:
   - Native Table of Contents generation and update
   - Navigation pane support in Word
   - Consistent styling via style definitions

   Override the built-in Heading style definitions in the document's `styles` config to match the Phase 1 design tokens (colors, fonts, sizes). Then apply them via `heading: HeadingLevel.HEADING_1` on paragraphs.

7. **Table widths must be explicit:**
   Always set table `width` using `WidthType.DXA` matching the content area width (page width minus left and right margins). Never use `tblW type="auto"` — it causes inconsistent table widths across viewers. For A4 with 1-inch margins: content width = 11906 - 2880 = 9026 DXA.

### 3.5 — Visual QA

After document generation:

**For PDF** (if generated):
1. Read the generated PDF (first 3 pages) using the Read tool
2. Read a sample artifact PDF (same pages) for comparison
3. Compare visually:
   - Cover page: layout, colors, decorative elements, metadata table placement
   - Inner pages: header/footer consistency, accent bars, section heading styling
   - Tables: header styling, row colors, border consistency
   - Typography: heading sizes and colors, body text appearance
   - Diagrams: verify images rendered correctly, are centered, have bordered containers and captions matching sample PDF style
4. If significant visual discrepancies exist, identify the CSS issue, fix it, and re-render

**For DOCX** (if generated):
1. Open and read the generated DOCX to verify structure and content completeness
2. Verify all sections are present in correct order
3. Verify styling was applied (headings, tables, headers/footers)
4. **Check numbered lists:** confirm each section's numbered list starts at 1 — not continuing from the previous section. If any list shows numbers like 17, 23, 30, etc., the numbering references are shared and must be fixed.
5. **Check page numbering:** confirm the first inner page (after cover) is page 1, not page 2.
6. **Check heading styles:** confirm headings use Word's built-in Heading styles (not inline formatting), so the TOC can auto-update.
7. **Check table widths:** confirm tables span the full content width and don't appear narrow or inconsistent.
8. **Check diagrams:** confirm all diagram images are embedded, visible, centered, with containers and captions matching the sample PDF style. Verify the diagrams accurately represent the processes or flows described in the content.
9. If issues are found, fix and regenerate

5. Report findings to the user for all generated formats

---

## Output

After all phases complete, print:

```
Document Generated Successfully
  Client:        {client_name}
  Document type:  {document_type}
  Version:       {version}
  Format:        {format — pdf, docx, or both}
  Sections:      {count} sections generated
  Diagrams:      {count} figures generated (if any)
  Constraints:   {passed}/{total} passed (if applicable)
  HTML:          {html_path}
  PDF:           {pdf_path}   (if generated)
  DOCX:          {docx_path}  (if generated)
  Figures:       {figures_dir} (if diagrams generated)
```

---

## Critical Rules

1. **KB is the ONLY source of domain knowledge.** This skill knows nothing about any specific industry, document type, or client. ALL document structure, section definitions, boilerplate text, templates, patterns, constraints, and formatting rules come from the KB files. Read them fully before generating any content.

2. **Verbatim means verbatim.** When the KB marks text as boilerplate or verbatim, copy it exactly — character for character. Do not paraphrase, improve grammar, fix perceived typos, or rephrase. If the KB documents intentional misspellings or quirks, preserve them.

3. **Visual fidelity matters.** The generated documents (PDF and/or DOCX) should be visually indistinguishable from the sample artifacts at a glance. Colors, table styling, page layout, headers, footers, and decorative elements must match. For DOCX, use the closest Word-native equivalents to achieve the same visual result.

4. **Constraint validation is mandatory.** If the KB defines validation rules, check every one before generating the output documents. Fix violations before proceeding.

5. **Sample artifacts are visual reference only.** Use them to extract the visual template (Phase 1), but all content structure and rules come from the KB + MOM.

6. **Ask, don't guess.** Phase 0 is the enforcement point: it reads the KB's input checklist, classifies every required field as PRESENT/AMBIGUOUS/DEFERRED/MISSING, and HALTS before any other phase runs if blocking gaps exist. KB defaults, `[TBD]` placeholders, and "best guess" content are NOT acceptable substitutes — they re-introduce the hallucination this gate exists to prevent. The only way past Phase 0 is supplying the values or an explicit user override.

7. **Adapt to any KB.** Whether the KB describes SOWs, legal contracts, marketing proposals, engineering specs, or anything else — follow its structure. The generation logic adapts to whatever the KB defines.
