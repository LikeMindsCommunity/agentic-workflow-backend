# PDF render pipeline

Read this only when `OUTPUT_FORMAT == "pdf"`. The DOCX path is `reference/render-docx.md` and needs none of this.

You are authoring HTML/CSS to the measured spec, then printing it. Every concrete styling value — hex code, pt size, pixel count, inch margin, font family — comes from the KB's `FORMAT_SPEC` (in `02-visual-style.md`). Nothing here is a default: where a rule below names `FORMAT_SPEC.x.y`, read that value from the KB and write the real value into the CSS. If a value you need is absent from FORMAT_SPEC, the KB is incomplete — say so rather than inventing a plausible one.

---

## Rule 1 — Every colour is a `:root` custom property

Emit one CSS variable per entry in `FORMAT_SPEC.color_palette`, then reference it everywhere through `var(--token)`. Never scatter raw hex codes through the rules. This keeps the document re-tintable by editing the token block alone.

```css
:root {
  /* one declaration per entry in FORMAT_SPEC.color_palette */
  --strip-primary: #1FB5EC;   /* usage recorded in the KB */
  ...
}
```

Token names are the semantic names the KB recorded (`--strip-primary`, `--heading-h1`, `--table-header-bg`), never generic (`--color-1`). A complete document usually carries 12 to 20.

## Rule 2 — Page geometry from `FORMAT_SPEC.page`

```css
@page { size: <FORMAT_SPEC.page.width> <FORMAT_SPEC.page.height>; margin: 0; }
.page {
  width: <FORMAT_SPEC.page.width>;
  height: <FORMAT_SPEC.page.height>;
  position: relative;
  overflow: hidden;
  page-break-after: always;
}
```

Letter (8.5in × 11in) and A4 (8.27in × 11.69in) are both common. Read it; do not assume.

## Rule 3 — Strips are absolutely positioned divs

One selector per strip the sample actually uses. If `FORMAT_SPEC.strips.<side>` is `none`, omit that selector entirely — do not emit a zero-height div.

```css
.strip-top    { position:absolute; left:0; right:0; top:0;
                height:<strips.top.thickness>; background:var(<strips.top.color_token>); }
.strip-bottom { position:absolute; left:0; right:0; bottom:0;
                height:<strips.bottom.thickness>; background:var(<strips.bottom.color_token>); }
.strip-left   { position:absolute; left:0; top:0; bottom:0;
                width:<strips.left.thickness>; background:<strips.left.background>; }
```

**Emit the physical unit the KB records — never a bare pixel count.** The KB stores these in inches or points precisely because a pixel measured off a 150 DPI render is not a CSS pixel: `16px` written into CSS renders as 25 device pixels at 150 DPI, a 56% error that looks deliberate on every page. If a KB value you need is a bare `_px`, convert it (`px / measured_at_dpi` inches) rather than passing it through.

`strips.left.background` may be a hex or a gradient spec — carry whichever the KB recorded. Samples with no strips get a plain page.

## Rule 4 — Content wrapper leaves room for the strips

Compute `top`/`bottom`/`left` from the strip thicknesses (0 where a strip is absent) and the padding from `FORMAT_SPEC.page.margins`.

```css
.content {
  position: absolute;
  top: <strips.top.thickness_px>px;
  bottom: <strips.bottom.thickness_px>px;
  left: <strips.left.thickness_px>px;
  right: 0;
  padding: <margins.top> <margins.right> <margins.bottom> <margins.left>;
}
```

## Rule 5 — Header and footer from `FORMAT_SPEC.header` / `.footer`

The header's zone content decides the flex layout; the footer's `layout` field selects single-zone or three-zone.

```css
.page-header { display:flex; justify-content:space-between; align-items:center;
               min-height:<header.min_height_px>px; }
.page-header .h-title { font-size:<header.right_zone_font_size>pt;
                        font-weight:<header.right_zone_weight>;
                        color:var(<header.right_zone_color_token>); }

/* three_zone */
.page-footer { position:absolute; left:<margins.left>; right:<margins.right>;
               bottom:<footer.bottom_offset_px>px; display:flex;
               justify-content:space-between; font-size:<footer.font_size>pt;
               font-weight:<footer.font_weight>; color:var(<footer.color_token>); }
.page-footer .pno { position:absolute; left:50%; transform:translateX(-50%); }

/* single_zone */
.page-footer { position:absolute; left:0; right:0; bottom:<footer.bottom_offset_px>px;
               text-align:center; font-size:<footer.font_size>pt;
               color:var(<footer.color_token>); }
```

Add `font-style: italic` (and the footer's own `font_family`) when the KB records italic.

**Header and footer strings are copied from the KB character-for-character.** Copyright lines, brand names, separator punctuation, and version slug formats were measured off the reference and recorded verbatim. Whatever string the KB carries is the string you emit — even if the product name, the operator, or your own expectation says the organisation is called something else. An inferred string is wrong on every page of every document.

**Repeating header/footer under Chrome print.** Do not rely on `position: fixed` — Chrome's print engine offsets fixed elements by the `@page` margin and they land inside the content area. Wrap the running pages in a `<table>` with `<thead>` and `<tfoot>`; browsers repeat those on every printed page. Keep the cover page *outside* that table so it gets no running header.

## Rule 6 — One CSS class per heading level in `FORMAT_SPEC.headings`

```css
<level.selector> {
  color: var(<level.color_token>);
  font-weight: <level.weight>;
  font-size: <level.font_size>pt;
  margin: <level.margin_top>px 0 <level.margin_bottom>px 0;
  /* + font-style, letter-spacing, text-decoration where recorded */
}
```

Selectors follow the heading's semantic role: `h1.sec` for numbered top-level, `h2.sub` for numbered subsection, `.italic-subheading` for italic single-line headings. Heading levels are not assumed — some documents use two, others six including italic and quoted variants.

**Never share one colour token across two heading levels.** The KB records each level's colour independently because they were sampled independently; if it gives `--heading-h1` and `--heading-h2`, emit both even when the hexes look close. Merging heading colours is the most common visual fidelity failure in this archetype.

## Rule 7 — One table style per distinct table type in `FORMAT_SPEC.tables`

```css
table.<class_name> { border-collapse:collapse; width:100%; table-layout:fixed; }
table.<class_name> thead th {
  background: var(<header_band_token>);
  color: var(<header_text_token>);
  font-weight: <header_text_weight>;
  text-align: <header_text_align>;
  padding: <header_padding_px>px;
  font-size: <header_font_size>pt;
  border: <cell_border_thickness_px>px solid var(<header_band_token>);
}
table.<class_name> tbody td {
  border: <cell_border_thickness_px>px solid var(<cell_border_token>);
  padding: <cell_padding_px>px;
  color: var(<cell_text_token>);
  font-size: <cell_font_size>pt;
}
```

Emit a striping rule **only** where the KB records one. `row_striping: none` is the normal case; adding stripes because they are conventional changes the visual character of every table in the document.

**The TOC is whatever the KB says it is.** If the KB classified it as a styled list, render it with its own list CSS — never a `<table>`. A TOC rendered as a bordered table when the reference uses an indented list (or the reverse) is immediately visible on the document's most-read page.

## Rule 8 — Inline every SVG; never `<symbol>` + `<use>`

WeasyPrint's support for `<symbol>`/`<use>` is incomplete — symbols defined in one place and referenced elsewhere do not render. Inline the markup at every use site, even when that repeats it across pages. Hold each reusable block as a string in the generation script and insert the string at each site; that is mechanical, faster than maintaining `<use>`, and carries no rendering risk.

## Rule 9 — Flowchart shapes from `FORMAT_SPEC.flowchart_vocabulary.shapes`

Emit one SVG template per shape the KB records, substituting its colours, stroke widths, and decorations. Store them as string templates so the document composition step can interpolate coordinates and labels.

```html
<!-- ellipse: start/end terminator -->
<ellipse cx="{X}" cy="{Y}" rx="{W}" ry="{H}"
         fill="<shape.fill>" stroke="var(<shape.stroke_token>)"
         stroke-width="<shape.stroke_thickness_px>"/>
<text x="{X}" y="{Y}" text-anchor="middle" dominant-baseline="middle"
      fill="var(<shape.text_color_token>)" font-weight="<shape.text_weight>"
      font-size="<shape.text_size_px>px">{label}</text>

<!-- rounded_rectangle: prompt / action -->
<rect x="{X}" y="{Y}" width="{W}" height="{H}" rx="<shape.border_radius_px>"
      fill="<shape.fill>" stroke="var(<shape.stroke_token>)"
      stroke-width="<shape.stroke_thickness_px>"/>
<text x="{X+W/2}" y="{Y+H/2}" text-anchor="middle" dominant-baseline="middle"
      fill="var(<shape.text_color_token>)" font-weight="<shape.text_weight>">{label}</text>
<!-- plus the speaker icon group where shape.speaker_icon is recorded -->

<!-- diamond: decision -->
<polygon points="{X},{Y} {X+W},{Y+H/2} {X},{Y+H} {X-W},{Y+H/2}"
         fill="<shape.fill>" stroke="var(<shape.stroke_token>)"
         stroke-width="<shape.stroke_thickness_px>"/>

<!-- hexagon: retry counter -->
<polygon points="{X},{Y} {X+30},{Y-15} {X+70},{Y} {X+70},{Y+30} {X+30},{Y+45} {X},{Y+30}"
         fill="<shape.fill>" stroke="var(<shape.stroke_token>)"
         stroke-width="<shape.stroke_thickness_px>"/>

<!-- pentagon_downward_banner: queue endpoint -->
<polygon points="{X},{Y} {X+W},{Y} {X+W},{Y+H} {X+W/2},{Y+H+tip} {X},{Y+H}"
         fill="var(<shape.fill_token>)" stroke="var(<shape.stroke_token>)"
         stroke-width="<shape.stroke_thickness_px>"/>
```

Emit only the shapes the KB actually recorded. Documents with no flowcharts get nothing from this rule.

**The shape vocabulary is a contract.** Once the KB says red ovals are start/end terminators and dark grey pentagons are queue endpoints, use those shapes for those semantics in every diagram, with no substitution.

## Rule 10 — Conditional label colours from the KB's mapping

```python
LABEL_COLOR_MAP = {
    # one entry per condition word in FORMAT_SPEC.flowchart_vocabulary.conditional_labels
    "Holiday": "var(--branch-orange)",
    "Yes":     "var(--branch-affirmative)",
    ...
}

def label_color(condition_word):
    return LABEL_COLOR_MAP.get(condition_word, "var(--body)")
```

Words the KB never recorded fall through to the body token. Do not improvise a colour for an unmapped condition.

## Rule 11 — Rendering chain

Try in order, falling back when a tool is unavailable:

1. **Chrome headless** (best SVG fidelity, the primary):
   ```bash
   google-chrome --headless --no-sandbox --print-to-pdf=out.pdf \
     --no-pdf-header-footer --print-to-pdf-no-header file://$(pwd)/input.html
   ```
2. **WeasyPrint** (reliable fallback; requires the inlined SVGs of Rule 8):
   ```python
   from weasyprint import HTML; HTML('input.html').write_pdf('out.pdf')
   ```
3. **pdfkit / wkhtmltopdf**, if present.

Chrome and WeasyPrint are the two guaranteed to exist in the runtime image; the rest are opportunistic. **No pandoc fallback** — it is not installed and its HTML→PDF output does not preserve the measured format.

## Rule 12 — Self-contained HTML

- All CSS in a single `<style>` block in `<head>`.
- All SVG inlined at each use site (Rule 8). No external SVG files.
- Fonts: import from Google Fonts where the face is available. For proprietary faces not on Google Fonts (e.g. Calibri), substitute the closest metric-compatible one (`Carlito` for Calibri) and always declare a system fallback (`Arial, sans-serif`).
- **Raster images use `file://` absolute paths** — not base64, not relative paths:
  ```python
  import os
  def asset_src(relative_path):
      return "file://" + os.path.abspath(relative_path)
  ```
  `file://` absolute URLs resolve in both Chrome headless and WeasyPrint regardless of where the HTML file was saved. The referenced files are the ones the KB bundled; they must exist on disk before the renderer runs.
- No external script dependencies.
- Simple geometric graphics (banners, flowchart shapes, dividers) are inline SVG, never rasters.

---

## Post-render cleanup

Run **after** the verification pass confirms the deliverable, and never before. Delete every intermediate build artefact — the working `.html`, the copied assets, temp images, generation scripts — leaving only the deliverable, named `<recipient>_<DOC_TYPE>.<ext>`.

```bash
# DELIVERABLE comes from the Phase 0 filename resolution, e.g. "SwiftTrack Logistics_SOW.pdf"
cd <output_dir> && test -f "$DELIVERABLE" || { echo "render failed: $DELIVERABLE missing"; exit 1; }
find . ! -name "$DELIVERABLE" ! -path '.' -delete && find . -empty -type d -delete
```

Two ways this destroys the thing it is meant to keep, both of which have happened:

- **A hardcoded `.pdf`** deletes a DOCX run's output. Both halves of the name are run-time values.
- **An unquoted `"$DELIVERABLE"`** turns the filter into a delete-everything the moment a recipient name contains a space — which is the normal case, not the edge case.

The `test -f` guard runs **before** the delete. If the render failed there is nothing to preserve, and running the filter anyway empties the directory while the run still reports success.
