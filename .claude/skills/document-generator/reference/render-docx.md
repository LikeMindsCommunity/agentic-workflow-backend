# DOCX render pipeline

Read this only when `OUTPUT_FORMAT == "docx"`. The PDF path is `reference/render-pdf.md` and needs none of this.

python-docx writes the deliverable directly. There is **no converter in the runtime** — no LibreOffice, no pandoc — so a DOCX is never produced by rendering a PDF and converting it, and vice versa. Each format is authored natively. Any plan that says "generate the PDF then convert to Word" is wrong and will fail.

Which of the two cases below applies is decided by `FORMAT_SPEC.output.sample_format` in the KB.

---

## Case A — the KB bundles a `.docx` reference (the high-fidelity path)

**Load the bundled reference as the base document. Never start from a blank `Document()`.**

```python
from docx import Document

# The reference deliverable the KB bundled — the style/theme/header/footer template.
# This is the ONLY correct way to initialise the document for this case.
# Do NOT replace this with Document(): a blank document loses all styles,
# the Office theme (font and colour palette), header images, and footer layout.
REFERENCE_PATH = "<kb_dir>/<FORMAT_SPEC.reference_document>"
doc = Document(REFERENCE_PATH)

# Strip all body content while preserving styles, theme, header, and footer.
body = doc.element.body
for child in list(body):
    if child.tag.split("}")[-1] != "sectPr":
        body.remove(child)

# Every named style, the Office theme (font pair and colour tokens), header images,
# footer text, page margins, and contextualSpacing are now inherited exactly.
# Write content from this point — do not call _ensure_style() or recreate styles.
# They already exist.
```

**Why this is mandatory.** Creating a blank `Document()` and rebuilding styles by hand produces a document that deviates from the reference in at least nine measurable ways, every one of them visible in the output: wrong body style name, incomplete `NoSpacing` definition, incorrect top margin, missing Office theme, wrong header tab stop, missing `contextualSpacing` on list paragraphs, missing `Normal1` style, inconsistent line-spacing inheritance, and table cell font override. Word's style inheritance chain, the theme XML, and `docDefaults` cannot be faithfully reproduced from a style description no matter how precise the FORMAT_SPEC values are. Loading the reference eliminates all nine in one line.

**The path must point inside the KB.** kb-builder bundles the reference deliverable into the KB directory precisely so this step has a file that still exists at generate time. Never point at an operator's original input path: that breaks the moment the skill runs anywhere but the machine the KB was built on — a container, another checkout, or after the operator tidies their inputs. If `FORMAT_SPEC.reference_document` names a file that is not in the KB directory, the KB has a dangling dependency; say so rather than reaching outside it.

---

## Case B — the KB's reference is a `.pdf` (nothing to clone)

There is no source document to inherit styles from and no converter, so build from FORMAT_SPEC with python-docx. This is the one place a blank `Document()` is correct.

1. Start from `Document()`.
2. Page size and margins from `FORMAT_SPEC.page`.
3. One paragraph style per heading level in `FORMAT_SPEC.headings` — font family, pt size, weight, and the colour token resolved to its hex.
4. One table style per entry in `FORMAT_SPEC.tables`.
5. Body defaults from `FORMAT_SPEC.body`.
6. Insert `FORMAT_SPEC.assets` images via `add_picture()` at their recorded widths.

Two consequences to handle rather than ignore:

- **Vector chrome does not survive.** Strips, corner accents, and inline-SVG flowcharts have no DOCX equivalent. Render each to PNG at 2× print resolution during generation and place the raster — do not silently drop the element. Where the KB marks a diagram `CLIENT_SPECIFIC`, keep the placeholder behaviour.
- **Pagination will not match the PDF.** Word reflows text; absolute page coordinates measured from a PDF reference do not transfer. Use style-driven page breaks at section boundaries (`WD_BREAK.PAGE`) rather than reproducing measured y-offsets, and do not run the pixel-diff loop against the PDF reference on this path — verify structure and typography instead.

---

## Fidelity is asymmetric, and the completion summary must say so

`FORMAT_SPEC.output.primary` is whichever format the KB's reference document is. That format reproduces the reference **directly** — a `.docx` reference is cloned style-for-style, a `.pdf` reference is measured into HTML that renders near-identically.

The other format is a **rebuild from the measured spec**. It matches the palette, typography, page geometry, and section order the KB recorded, but minor spacing and pagination will differ, and a PDF-sourced DOCX has no Office theme to inherit.

State this when the operator asked for the non-primary format. Never refuse it.

---

## Verification for this path

The PDF pixel-diff does not apply — Word reflows, so a diff against a PDF reference reports differences that cannot be fixed and are not defects. Check instead:

- Cloned base: the document opens; styles, theme, header images, and footer survived the body strip.
- Cloned base: no `_ensure_style()` calls anywhere — every style came from the loaded base.
- Rebuilt from spec: page size and margins match `FORMAT_SPEC.page`.
- Rebuilt from spec: one paragraph style per heading level, each with its measured font, pt size, weight, and hex colour.
- Rebuilt from spec: table styles match `FORMAT_SPEC.tables` (header band colour, borders, padding).
- Vector chrome rasterised at 2× and placed, not dropped.
- Section page breaks are style-driven (`WD_BREAK.PAGE`), not measured y-offsets.
- `FORMAT_SPEC.assets` images embedded at their recorded widths.

## Post-render cleanup

Identical to the PDF path — see the closing section of `reference/render-pdf.md`. The two traps apply here in full: the extension in the cleanup filter is a run-time value (a hardcoded `.pdf` deletes this run's deliverable), and `"$DELIVERABLE"` must be quoted because recipient names contain spaces as a rule.
