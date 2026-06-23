# PDF vs Preview Layout Differences

## Overview

The SAIL MIS Report Portal uses **two separate rendering pipelines**:

1. **Preview (Browser)** — React components render in HTML on screen
2. **PDF (Server-side)** — Jinja2 templates render via WeasyPrint to PDF file

Both pipelines use the **same data** but with **different styling, spacing, and formatting**.

---

## Architecture & Data Flow

```
┌─────────────────────────────────────────────────────────────┐
│                      Backend (FastAPI)                       │
│                                                              │
│  /api/data (Preview)          /api/generate-pdf (PDF)       │
│  ├─ generate_page_X()         ├─ generate_page_X()         │
│  ├─ generate_techno()         ├─ generate_techno()         │
│  └─ Returns JSON              └─ Passes to build_pdf_response()
└─────────────────────────────────────────────────────────────┘
        ↓                              ↓
┌─────────────────────────────────────────────────────────────┐
│                    Frontend (React/Jinja2)                   │
│                                                              │
│ PageRenderer.js (React)      main.html (Jinja2)            │
│ ├─ HTML Layout               ├─ HTML Layout                │
│ ├─ globals.css               ├─ CSS Variables              │
│ ├─ React Components          ├─ CSS Includes               │
│ └─ Interactive Editing       └─ Static PDF Render          │
└─────────────────────────────────────────────────────────────┘
        ↓                              ↓
┌─────────────────────────────────────────────────────────────┐
│            Preview (Browser)         PDF File               │
│                                                              │
│ • Interactive                    • Static/Immutable        │
│ • Editable cells                 • Final output             │
│ • A4-simulated layout            • Print-optimized         │
│ • Sidebar controls visible       • Sidebar hidden          │
└─────────────────────────────────────────────────────────────┘
```

---

## Key Differences

### 1. **Rendering Engine**

| Aspect | Preview | PDF |
|--------|---------|-----|
| **Engine** | Browser (Chromium) | WeasyPrint (Python) |
| **Format** | HTML + React | HTML + Jinja2 |
| **Language** | JavaScript (React) | Python (Jinja2) |
| **Templates** | React components in `src/components/` | Jinja2 templates in `backend/page_templates/` |
| **Styling** | CSS (`globals.css`, component CSS) | Inline CSS + `layout_config.json` |

---

### 2. **Layout & Spacing**

#### **Preview (React Browser)**

```
┌────────────────────────────────────────────┐
│  .app-container (flex row)                  │
├────────────┬────────────────────────────────┤
│  .sidebar  │  .preview-area                  │
│ 380px      │  flex-grow: 1                   │
│            │  padding: 40px (around edges)   │
│ • Month    │  background: #cbd5e1 (gray)    │
│ • Plant    │  overflow-y: auto               │
│ • etc.     │                                 │
│            │  ┌─────────────────────────┐   │
│            │  │    .a4-page             │   │
│            │  │  210mm × 297mm (A4)     │   │
│            │  │  box-shadow             │   │
│            │  │  padding: 7mm 15mm      │   │
│            │  │  background: white      │   │
│            │  │                         │   │
│            │  │  [ Page Content ]       │   │
│            │  │                         │   │
│            │  └─────────────────────────┘   │
│            │  margin-bottom: 40px            │
└────────────┴────────────────────────────────┘
```

**Key styles:**
- `.preview-area`: `padding: 40px`, background gray
- `.a4-page`: `width: 210mm`, `box-shadow`, white background
- Page margins: Controlled by CSS variables (7mm top, 5mm bottom, 15mm sides)
- Scrollable: User scrolls through pages vertically

---

#### **PDF (Jinja2 WeasyPrint)**

```
┌────────────────────────────────────────────┐
│  Page 1 (A4 210mm × 297mm)                 │
│  margin: 15mm 10mm 15mm 10mm               │
│                                            │
│  [ Page Content ]                          │
│                                            │
└────────────────────────────────────────────┘
┌────────────────────────────────────────────┐
│  Page 2 (A4 210mm × 297mm)                 │
│  margin: 15mm 10mm 15mm 10mm               │
│                                            │
│  [ Page Content ]                          │
│                                            │
└────────────────────────────────────────────┘
```

**Key styles:**
- `@page { margin: 15mm 10mm 15mm 10mm; }`
- No padding, no box-shadow
- `page-break-after: always` (each page breaks)
- Direct A4 dimensions, no scrolling

---

### 3. **Font Sizes & Typography**

#### **CSS Variable System**

Both use CSS variables defined in `frontend/src/app/globals.css`:

```css
:root {
  --report-font-size: 12.2pt;        /* Base font size */
  --page-margin-top: 7mm;            /* Preview top margin */
  --page-margin-bottom: 5mm;         /* Preview bottom margin */
  --page-margin-lr: 15mm;            /* Left/Right margin */
}

@media print {
  /* PDF uses different margins and fonts */
  @page {
    margin: 15mm 10mm 15mm 10mm;  /* PDF margins override CSS vars */
  }
  
  @page pg27_layout {
    margin: 6mm 8mm 3mm 8mm;      /* Page 27 tighter for more rows */
    --report-font-size: 10pt;     /* Page 27 specific smaller font */
  }
}
```

#### **Current Font Sizes** (from `layout_config.json`)

```json
{
  "global": {
    "td_size": 11.5,       // Table data cells
    "th_size": 11.0,       // Table header cells
    "title_size": 15.0,    // Page titles (h2)
    "heading_size": 12.0   // Section headings (h3)
  },
  "pages": {
    "27": { "fontSize": 8.5 }  // Page 27 specific override (MAJOR TECHNO)
  }
}
```

#### **Key Font Differences**

| Element | Variable | Preview | PDF |
|---------|----------|---------|-----|
| Table cells | `--report-font-size` | 12.2pt | 12.2pt (default) |
| Page 27 | `--report-font-size` | 12.2pt | 10pt (smaller on PDF) |
| Titles | `title_size` | 15pt | 15pt |
| Headers | `th_size` | 11pt | 11pt |

---

### 4. **Visual Styling**

#### **Preview Specific**

- ✓ **Box shadow**: `.a4-page { box-shadow: 0 10px 25px -5px... }`
- ✓ **Background**: `.preview-area { background: #cbd5e1 (slate gray) }`
- ✓ **Margins around pages**: `40px padding` + `40px margin-bottom`
- ✓ **Sidebar visible**: All controls visible
- ✓ **Scrollable**: Can scroll through all pages
- ✓ **Editable**: Input fields for cell editing

#### **PDF Specific**

- ✗ **No box shadow**: Removed via `@media print { box-shadow: none }`
- ✗ **No background color**: Converted to white
- ✗ **Tighter margins**: 6-15mm (configured per page in `@page` rules)
- ✗ **No sidebar**: Hidden with `.no-print { display: none }`
- ✗ **Not scrollable**: Each page is a separate piece of paper
- ✗ **Not editable**: Static output only

---

### 5. **Page-Specific Overrides**

The system has **special handling for specific pages**:

#### **Landscape Pages** (Pages 11-23)

**Preview:**
```css
.a4-page.landscape {
  width: 297mm;              /* Wider than portrait */
  min-height: 210mm;         /* Shorter height */
  padding: 7mm 20mm 5mm 20mm;
}
```

**PDF:**
```css
@page landscape_layout {
  size: A4 landscape;        /* Landscape orientation */
  margin: 10mm 15mm 10mm 15mm;
}
.a4-page.landscape {
  page: landscape_layout;    /* Apply landscape layout */
}
```

#### **Page 21 (RSP Special Steel)** — Tight margins

**PDF only:**
```css
@page pg21_layout {
  size: A4 portrait;
  margin: 5mm 10mm 3mm 10mm;  /* Tighter than default 15mm */
}
```

**Why?** Special Steel table is dense and tall. Tight margins squeeze content to fit on one page.

#### **Page 27 (MAJOR TECHNO-ECONOMIC PARAMETERS)** — Very tight

**PDF only:**
```css
@page pg27_layout {
  size: A4 portrait;
  margin: 6mm 8mm 3mm 8mm;    /* Extremely tight */
}
.a4-page.pg-27 {
  --report-font-size: 10pt;   /* Reduce font size */
}
```

**Why?** MAJOR page has 80+ parameters. Tight margins + smaller font = fits more rows.

---

### 6. **Margin Comparison**

| Page | Preview Top | Preview Sides | PDF Top | PDF Bottom | PDF Sides |
|------|-------------|---------------|---------|-----------|-----------|
| Default | 7mm | 15mm | 15mm | 10mm | 10mm |
| Landscape | 7mm | 15mm | 10mm | 10mm | 15mm |
| Page 21 | 7mm | 15mm | 5mm | 3mm | 10mm |
| Page 27 | 7mm | 15mm | 6mm | 3mm | 8mm |

**Key insight:** PDF margins are **tighter** than preview, especially for dense tables.

---

### 7. **Component Rendering**

#### **Preview (React Components)**

- Uses React templates: `TechnoParamsTemplate`, `SpecialSteelTemplate`, etc.
- Components import CSS modules or use inline styles
- State management: Can edit cells, update parent state
- Real-time validation and error handling
- Conditional rendering based on screen size

**Example:**
```jsx
export default function TechnoParamsTemplate({ data, onCellChange }) {
  return (
    <div className="techno-section">
      {data.sections.map(section => (
        <section key={section.section}>
          <h3>{section.section}</h3>
          <table>
            {/* Editable cells with onChange handlers */}
          </table>
        </section>
      ))}
    </div>
  );
}
```

#### **PDF (Jinja2 Templates)**

- Uses Jinja2 templates: `techno_params.html`, `special_steel.html`, etc.
- Templates reference CSS via WeasyPrint inline rendering
- No state management, pure template rendering
- Font sizes from `layout_config.json` injected as CSS variables
- Page breaks and margins controlled via `@page` rules

**Example:**
```html
{% for section in sections %}
  <div class="techno-section">
    <h3>{{ section.section }}</h3>
    <table class="techno-table">
      {% for row in section.rows %}
        <tr>
          <td>{{ row.label }}</td>
          <td class="value">{{ row.actual }}</td>
        </tr>
      {% endfor %}
    </table>
  </div>
{% endfor %}
```

---

### 8. **CSS Injection Points**

#### **Preview**

CSS comes from:
1. `frontend/src/app/globals.css` — Global styles
2. Component CSS modules — Per-component styling
3. Inline styles — React JSX style props

No injection needed — CSS is static.

#### **PDF**

CSS comes from:
1. `backend/page_templates/main.html` — Base template with `<style>` block
2. `layout_config.json` — Font sizes injected as CSS variables
3. `backend/models.py` — FontConfig defaults
4. `backend/pdf.py` — Converts FontConfig to CSS

**CSS variables injected into HTML:**

```html
<style>
  :root {
    --td-size: {{ td_size }}pt;
    --th-size: {{ th_size }}pt;
    --title-size: {{ title_size }}pt;
    --heading-size: {{ heading_size }}pt;
  }
  
  td { font-size: var(--td-size); }
  th { font-size: var(--th-size); }
  h2 { font-size: var(--title-size); }
  h3 { font-size: var(--heading-size); }
</style>
```

---

### 9. **Interaction & Editability**

#### **Preview**

- ✓ Click to edit cell values
- ✓ Change month/plant/report settings
- ✓ See live updates
- ✓ Validations and error messages shown
- ✓ Scroll through pages
- ✓ Sidebar controls always visible

#### **PDF**

- ✗ No editing (output only)
- ✗ No interactivity (static file)
- ✗ No validation feedback
- ✗ No scrolling (fixed pages)
- ✗ No sidebar (hidden in print)
- ✓ Print-ready, save to file, email, archive

---

### 10. **Performance Implications**

| Aspect | Preview | PDF |
|--------|---------|-----|
| **Render Time** | ~500ms (React component mount) | ~2-5s (WeasyPrint) |
| **File Size** | N/A (displayed) | 500KB - 2MB (PDF) |
| **Memory** | ~50-100MB (browser) | ~200-500MB (Python process) |
| **Fonts** | Google Fonts (loaded in browser) | System fonts + embedded |
| **Images** | Rasterized | Vectorized (better compression) |

---

## Summary Table

| Feature | Preview | PDF | Note |
|---------|---------|-----|------|
| **Rendering** | Browser React | WeasyPrint Jinja2 | Different engines |
| **Interactivity** | Yes | No | Preview is live, PDF is static |
| **Font Size** | From `globals.css` vars | From `layout_config.json` | JSON config overrides CSS |
| **Margins** | 7mm (top), 15mm (sides) | 6-15mm (varies by page) | PDF tighter for density |
| **Box Shadow** | Yes (visual) | No (print) | Removed for clean PDF |
| **Background Color** | Gray (#cbd5e1) | White | Optimized for paper |
| **Sidebar** | Visible | Hidden | Print removes UI |
| **Scrolling** | Vertical | Page breaks | Different navigation |
| **Editability** | Full (cells editable) | None (static) | Preview for entry, PDF for output |
| **Page 27 Font** | 12.2pt | 10pt | PDF shrinks for density |

---

## Recent Changes (Font Size Increase)

**What changed:**

1. **`backend/models.py`** — Updated FontConfig defaults:
   - `td_size`: 9.5 → 11.5pt
   - `th_size`: 9.0 → 11.0pt
   - `title_size`: 13.0 → 15.0pt
   - `heading_size`: 10.5 → 12.0pt

2. **`backend/layout_config.json`** — Updated global and page-specific:
   - Global settings updated to match models.py
   - Page 27 fontSize: 6.8 → 8.5pt (was too small)

3. **No CSS changes needed** — The Jinja2 templates already use CSS variables that reference `layout_config.json`.

**Impact:**

- ✅ Preview: No visible change (uses `globals.css` CSS vars, not `layout_config.json`)
- ✅ PDF: **All pages appear with larger, more legible fonts**
- ⚠️ **Trade-off**: Larger fonts mean tables may need more vertical space (possible page overflow)

---

## Troubleshooting Layout Issues

### "Font sizes changed in PDF but not preview"

**Reason:** Preview uses `globals.css` CSS variables, PDF uses `layout_config.json`.

**Solution:** Edit `frontend/src/app/globals.css`:
```css
:root {
  --report-font-size: 12.2pt;  /* Change this */
}
```

### "Content overflows on page 27"

**Reason:** Larger fonts + tight margins = less space for rows.

**Solution:** Adjust page 27 in `layout_config.json`:
```json
"27": { "fontSize": 9.5 }  /* Reduce from 8.5 if needed */
```

### "PDF margins different from preview"

**Reason:** PDF uses `@page` rules; preview uses CSS vars.

**Solutions:**
1. Adjust `@page` margin rules in `globals.css` (affects preview)
2. Adjust `layout_config.json` margins (affects PDF only)
3. Both must be adjusted for consistent layout

---

## File Reference

| File | Purpose | Affects |
|------|---------|---------|
| `frontend/src/app/globals.css` | Preview styling & margins | **Preview only** |
| `backend/layout_config.json` | Font sizes & page-specific overrides | **PDF only** |
| `backend/models.py` (FontConfig) | Default font configuration | PDF (fallback) |
| `backend/pdf.py` | PDF rendering engine | PDF generation |
| `backend/page_templates/*.html` | Jinja2 templates for PDF | PDF content |
| `frontend/src/components/*.js` | React templates for preview | Preview content |
