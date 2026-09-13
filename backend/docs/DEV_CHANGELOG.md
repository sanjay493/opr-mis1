# Developer Changelog

Log of report-affecting changes, grouped by the report **page** they change
(a PDF page number like `2.1`, or `Frontend Reports` / `Cross-Page &
Infrastructure` for anything not tied to one page), newest first within each
group. The point is speed: when you need to change something (or figure out
why it behaves the way it does), jump to that page's section, find the
entry, and go straight to the `file:line` named in it instead of
re-discovering the whole area from scratch.

**Maintaining this file (do this from now on, every session):**
1. Finish a logical piece of work and commit it (or a small group of related
   commits).
2. Find (or create) the `## Page X.Y — <name>` heading for the report page
   this change affects, and add one entry at the **top** of that section,
   using the template:

   ```
   ### YYYY-MM-DD — Short, specific title
   **Commit:** `<hash>` — `<one-line commit subject>`
   **What:** 1-3 sentences, plain description of the behavior/code change.
   **Why:** the reason/instruction behind it — this is the part git log
   alone won't tell you.
   **Files:**
   - `path/to/file.py:123` — function/class name and what changed there
   - `path/to/other_file.html:45-60` — ...
   **Known issues:** only if something was left broken/incomplete on purpose.
   ```
3. If a change spans multiple report pages, log it once under its primary
   page and add a one-line cross-reference under the other page(s) (`See
   YYYY-MM-DD entry under Page X.Y.`) rather than duplicating the detail.
   If it isn't tied to any single report page (DB backfill, perf work,
   shared infra, docs), use the `Cross-Page & Infrastructure` section; if it
   only affects a frontend `/reports/...` route (not a numbered PDF page),
   use `Frontend Reports`.
4. If a change is DB-content only (a backfill, a data correction) with no
   code commit, still log it — write `**Commit:** none — data-only change`
   and say which table/DB so the data lineage isn't lost.
5. Keep each entry short enough to skim in a few seconds, and keep line
   numbers honest — re-check them with a quick `grep -n` if the file has
   moved on since; a stale line number is worse than none. Link to the
   code's own docstrings/comments for full detail rather than duplicating it
   here — this file is a map, not the territory.
6. New page heading: add `## Page X.Y — <name>` the first time a change
   touches that page, keeping page headings in ascending page-number order,
   with `Frontend Reports` and `Cross-Page & Infrastructure` last.

---

## Page 2.1 — Steel Sector Performance (Production & Prices)

### 2026-09-13 — Fill leftover page space: 12pt subtitle/notes + padding
**Commit:** `f46ebc1` — Steel Sector page 2.1: fill leftover page space, 12pt subtitle/notes
**What:** `.ssp-subtitle` (10→12pt) and `.ssp-note` (10.5→12pt) bumped to
match the rest of the page's 12pt text; table cell padding and
section/table-heading margins loosened slightly, to use up the visible
blank space at the bottom of the page. Verified by generating real
single-page PDFs for Aug/Jul/Jun 2026 after each increment — still one
physical page, less wasted space at the bottom.
**Why:** direct instruction — the page was rendering with a lot of unused
space below the price-trend chart; legibility should be raised (up to
12pt) and the page's own room used instead of left blank.
**Files:**
- `backend/page_templates/main.html:514-519` — `.ssp-subtitle` font-size
  + margin.
- `backend/page_templates/main.html:520-527` — `.ssp-section-heading`
  margin/padding.
- `backend/page_templates/main.html:528-540` — `.ssp-table` margin-bottom,
  `.ssp-table th/td` padding.
- `backend/page_templates/main.html:611-624` — `.ssp-table-heading`
  margin/padding, `.ssp-note` font-size/margin/padding.
**Known issues (tried, reverted):** also asked to let table 1b's 4
non-producer columns (Annual Crude Steel Capacity / Crude Steel
Production / Hot Metal Production / Finished Steel Production) wrap their
headers instead of staying `nowrap`. Tried it — `table-layout:auto`
recomputes every column's width once any column's content can break, and
here that shrank table 1b's data columns enough to reflow table 1a's
header row too and push table 1c + the price chart onto a 2nd physical
page, confirmed across all 3 archived months. Reverted to `nowrap` across
all of table 1b (see the comment on `.ssp-table-1b`,
`backend/page_templates/main.html:554-568`) since that's what actually
renders on one page.

### 2026-09-13 — Table 1b (Producer wise Production) shrink-to-fit column
**Commit:** `c86bc5a` — Steel Sector page 2.1: table 1b columns shrink-to-fit, no wrap
**What:** Table 1b's producer-name column was wrapping at the shared
`.ssp-table` 100%-width column sizing. Scoped table 1b (only, via a new
`.ssp-table-1b` wrapper) to `table-layout:auto` with the label column at
`width:1%;white-space:nowrap` — the same shrink-to-fit trick as Page 3's
TE table — so the column widens to its content while the table itself
stays at 100% width overall (no horizontal or next-page spill). Tables
1a/1c/2/3a/4a/5 still share the untouched `.ssp-table` even-width layout.
**Why:** direct instruction to fix wrapped producer names on page 2.1
without letting the table spill off the page or onto page 2.2.
**Files:**
- `backend/page_templates/main.html:554-574` — new `.ssp-table-1b` rule
  block (`table-layout:auto`, `white-space:nowrap`, label column
  `width:1%`).
- `backend/page_templates/steel_sector_performance.html:111` — wraps
  `generic_table(page.tables.get('1b'))` in the `.ssp-table-1b` div.

### 2026-09-13 — Price-trend charts + typography pass
**Commit:** `8aeb565` — Add Steel Sector Performance price-trend charts; page 2.1 typography pass
**What:** Page 2.1 (`prod_prices`) gets a "Steel Prices Trend" line chart
under Table 1c (TMT/HR Coil/CR Coil/GP Sheet). (Page 2.2 gets the matching
NMDC Iron Ore Price Trend chart — see that page's section.) Both trend
from the current FY's April onward, using whatever archived PIB releases
actually exist; chart labels show value in `'000` to 1 decimal with a "K"
suffix (e.g. `58.0K`) plus a top-right swatch+name legend.
**Why:** the page had leftover blank space after an earlier CSS pass; each
monthly PIB release only ever archives its own rolling ~3-month price
window (not a full history), so a dedicated aggregator was needed to stitch
a real trend together across releases.
**Files:**
- `backend/page_steel_sector_performance.py:95` — `_parse_month_header()`,
  keeps only columns that parse as a real calendar month.
- `backend/page_steel_sector_performance.py:124` —
  `_series_from_archive()`, scans every archived row via
  `_parse_month_header()` so trailing MoM%/YoY% columns are dropped
  automatically.
- `backend/page_steel_sector_performance.py:188` — `_price_trend_svg()`,
  y-axis auto-scaled to the data's own min/max (NOT zero-based, unlike
  `page_at_a_glance._trend_line_svg`).
- `backend/page_steel_sector_performance.py:253` — `_price_chart_html()`,
  wraps the chart; wired in at lines 369 (`page["steel_price_chart_html"]`)
  and 374 (`page["nmdc_price_chart_html"]`).
- `backend/page_templates/steel_sector_performance.html:113` — insertion
  point for `page.steel_price_chart_html`.
- `backend/page_templates/main.html:1758-1772` — experimental page-2.1-only
  compaction block (`.pg-2-1`), meant to stop the new chart pushing Table
  1c onto a 2nd page. **Currently commented out** (disabled).
**Known issues:** the `.pg-2-1` compaction block (`main.html:1758-1772`) is
disabled pending a decision on whether its tighter margins/type are
wanted — as of this commit, page 2.1 may spill onto 2 physical pages
depending on the report month's data.

## Page 2.2 — Steel Sector Performance (Demand & Trade)

### 2026-09-13 — NMDC price-trend chart
**Commit:** `8aeb565` — Add Steel Sector Performance price-trend charts; page 2.1 typography pass
**What:** Page 2.2 (`demand_trade`) gets an "NMDC Iron Ore Price Trend"
chart under Table 4a (Lump/Fines), built by the same aggregator as Page
2.1's Steel Prices Trend chart.
**Why:** see the 2026-09-13 entry under Page 2.1 (same commit/aggregator).
**Files:**
- `backend/page_steel_sector_performance.py:253` — `_price_chart_html()`
  call at line 374 (`page["nmdc_price_chart_html"]`).
- `backend/page_templates/steel_sector_performance.html:64` — insertion
  point for `page.nmdc_price_chart_html`.

## Page 2.5 — At-a-Glance

### 2026-09-13 — Trim legend/x-axis font-size on the 6-month trend chart
**Commit:** `5614fab` — Trim legend/x-axis font-size by 1pt on the 6-month trend chart
**What:** On the "Saleable Steel & Finished Steel Production Trend — Last 6
Months" chart, legend text 9.5→8.5 and month-axis labels 10→9 (SVG
user-units).
**Why:** direct instruction, a small readability adjustment.
**Files:**
- `backend/page_at_a_glance.py:274` — `_trend_line_svg()` legend text
  font-size.
- `backend/page_at_a_glance.py:281` — `_trend_line_svg()` month-axis label
  font-size.
**Known issues:** this is a partial mitigation, not a fix — the chart's
month-axis labels still visually overlap the "Semis by plant" heading/note
that follows it (same root cause as the 2026-09-13 At-a-Glance typography
entry below: the chart's canvas height was never grown to match any of its
enlarged text). Per-point value labels (still 9.5, line ~267) and the chart
canvas height (`_trend_section()`, line 924) were left untouched — only the
two sizes named above were in scope for this change.

### 2026-09-13 — At-a-Glance page typography pass (KNOWN ISSUE)
**Commit:** `1f3c9e0` — At-a-Glance page typography pass (KNOWN ISSUE: chart overlap, see DEV_CHANGELOG.md)
**What:** Increased font sizes across `at_a_glance.html` (title, section
headings, KPI-tile text, Techno-Economic tiles, Value Added Steel box) and
in `page_at_a_glance.py`'s `_trend_line_svg`/`_semis_table_html` chart
generators.
**Why:** manual readability tweak (page felt too dense/small).
**Files:**
- `backend/page_templates/at_a_glance.html` — every size is inline
  per-element, no shared classes except `.techno-tile`.
- `backend/page_at_a_glance.py:218` — `_trend_line_svg()`.
- `backend/page_at_a_glance.py:292` — `_semis_table_html()`.
- `backend/page_at_a_glance.py:924` — `_trend_section()`'s `vh=` call into
  `_trend_line_svg` (canvas height, NOT grown to match — see Known issues).
**Known issues:** `_trend_line_svg`'s per-point/legend/axis font sizes grew
(6.5/7/6.6 → 9.5/9.5/10 SVG user-units) but its canvas height
(`_trend_section()`'s `vh=` call, `page_at_a_glance.py:924`) did NOT grow to
match — the bottom "Saleable Steel & Finished Steel" trend chart's
month-axis labels now visibly overlap the "Semis by plant" heading/note
right after it (confirmed by rendering a real PDF). The enlarged
`_semis_table_html` sizes also push that table onto its own near-blank 2nd
page, breaking this page's original one-page design (see
`.at-a-glance-page`'s own comment in `main.html`).
**Fix options, not yet applied:** either shrink those 3 font-sizes back
down, or raise the `vh=` value at `page_at_a_glance.py:924` to give the
larger text room (and re-check the semis table still fits after).

## Page 3 — SAIL Performance Summary

### 2026-09-13 — 12pt typography pass + dynamic layout
**Commit:** `7281674` — Page 3 (SAIL Performance Summary): 12pt typography pass + dynamic layout
**What:**
- `.report-table` padding/font-size loosened to 12pt (was 5px 4px / 4px 4px
  padding, `var(--sz-td)`/`var(--sz-th)` size) — scoped to this page only
  via `.pg-3`, every other page using `.report-table` (page4, page5-6,
  techno, ...) is untouched. Table headers stay bold at the same 12pt.
- `.page3-section-heading`/`.page3-narrative`/`.page3-footnote`/
  `.page3-highlights` all set to 12pt (were 10pt / `var(--sz-td)` / 7.5pt /
  `var(--sz-td)`).
- The TE Parameters table's Parameter column now sizes to its own content
  and never wraps (`table-layout:auto` + `width:1%` + `white-space:nowrap`
  — the standard "shrink-to-fit" trick) instead of a fixed `width:24%`.
- The gap between Highlights and "TE parameters performance:" is now
  computed from the highlights line count instead of a fixed 5px, so a
  light-highlights month doesn't leave the page looking half-empty and a
  heavy one doesn't risk overflow.
- The 4 TE bar charts' shared x-axis/data-point label size trimmed a
  further 0.8pt (true, rendered) smaller.
**Why:** direct instruction — table felt cramped at the old sizes, the
Parameter column wrapped long parameter names awkwardly, and the fixed
highlights gap didn't adapt to how much Highlights content a given month
actually has.
**Files:**
- `backend/main.py:98` — `_page3_highlights_gap_px()` (28px base, -1.5px
  per highlight line, clamped to `[5, 28]`).
- `backend/main.py:751` — wired into `get_data()` (live preview path).
- `backend/main.py:1180` — wired into `_enrich_pdf_pages()` (PDF-generation
  path).
- `backend/page_templates/main.html:1120-1125` — `.pg-3 .report-table
  th/td` block (12pt padding/font).
- `backend/page_templates/main.html:1085-1102` — `.page3-section-heading`/
  `.page3-narrative`/`.page3-footnote`/`.page3-highlights` size edits.
- `backend/page_templates/summary.html:62` — `page.highlights_gap_px`
  margin-top on the TE section heading.
- `backend/page_templates/summary.html:68-71` — TE table's `te-table`
  class + Parameter column shrink-to-fit markup
  (`table-layout:auto;width:100%` on the table, `width:1%;white-space:
  nowrap` on the Parameter `<th>`/`<td>`).
- `backend/page_techno.py:966` — `_param_svg()`'s `label_fs` (11.30 →
  10.22; see that line's own comment for the ~1.346 viewBox-to-page scale
  factor this chart uses to convert a "true pt" instruction into a literal
  SVG value).
**Verified:** rendered a real PDF (Aug'26, 5 highlights lines → 20px gap)
— table padding/font legible, Parameter column stayed on one line for
"Specific Energy Consumption" (the longest name), all 4 charts rendered
with no overlap, whole page still fit on one physical page.

## Page 4.5 — SAIL Mines

### 2026-09-13 — Iron Ore Production now includes Dump Fines/Tailings sales + Pellets despatch
**Commit:** `46a6456` — Iron Ore Production now includes Dump Fines/Tailings sales + Pellets despatch
**What:** `db.get_iron_ore_group_rollup_monthly()`'s "Production" figure
was fresh Lump+Fines only; it now also adds Dump Fines/Tailings despatched
to `end_use_code='SALES'` and Pellets despatch of any end_use, since
neither material has its own production entry (`mine_materials_master`
only flags `has_production=1` for Lump/Fines) — previously invisible to
this headline figure entirely. Also restored `page_sail_mines.py`'s "Iron
Ore Mines Performance" table (`iron_ore_prod`/`iron_ore_despatch` sections)
to this live rollup instead of the frozen Apr-Jul'26 snapshot in
`hardcoded_config.json` — that stopgap only existed because mine-level
despatch actuals hadn't been backfilled yet (see the 2026-09-12 backfill
entry under Cross-Page & Infrastructure); they have been since. This also
changes the Cover page's Iron Ore KPI, which reads the same rollup.
**Why:** direct instruction — SAIL's own convention counts these
despatch-only materials as production at the point they leave the mine.
GUA's Dump Fines despatched CAPTIVE is deliberately excluded (that tonnage
already reaches the consuming plant as ordinary ore movement, not a
standalone recovered-and-sold quantity).
**Files:**
- `backend/db.py:3193` — `get_iron_ore_group_rollup_monthly()`.
- `backend/page_sail_mines.py:472` — `generate_sail_mines()`.
- `backend/page_sail_mines.py:487-494` — the `iron_ore_monthly`/
  `iron_ore_cply_monthly` merge, replacing the old
  `hardcoded.get(section["key"])` short-circuit for these two sections.
- `backend/hardcoded_config.json:20-21` — `sail_mines.iron_ore_group_kt`
  (the `iron_ore_prod`/`iron_ore_despatch` keys were removed;
  `iron_ore_sales`/`iron_ore_sales_despatch`, a different table — Booked
  Quantity — stay hardcoded, unbackfilled).
**Verified against:** Cover page's own reported number for Aug'26: 2.692 MT
(Lump+Fines only) → 2.846 MT (correct, +153.8 kt of Dump Fines/Tailings
sales that month).

## Frontend Reports (non-PDF pages)

### 2026-09-13 — Redesign Iron Ore Mines despatch table: full mode/end-use/material breakdown
**Commit:** `ad688be` — Redesign Iron Ore Mines despatch table: full mode/end-use/material breakdown
**Route:** `/reports/iron-ore-mines`
**What:** The Despatch table now shows a nested Rail/Road →
Captive/Sales/Pellet Conv. → Lump/Fines/Dump Fines/Tailings/Pellets
breakdown instead of flat material-only columns, hiding any combination
with no non-zero data for the current scope/FY so the table stays readable
despite the extra depth. Excel export updated to match; the old flat
Rail/Road total columns were removed (redundant — each mode block now
carries its own Total column).
**Why:** direct instruction, to expose the full despatch classification now
that the underlying data supports it (see the 2026-09-12 RMG backfill entry
under Cross-Page & Infrastructure).
**Files:**
- `frontend/src/app/reports/iron-ore-mines/page.js:109` — `despDetail`
  (per-month/mode/end-use/material actuals).
- `frontend/src/app/reports/iron-ore-mines/page.js:130` — `despStructure`
  (the visibility-filtering logic that hides all-zero mode/end-use/material
  combos).
- `frontend/src/app/reports/iron-ore-mines/page.js:234-268` — the 3-row
  `<thead>` builder (`despHeaderRow1`/`despHeaderRow2`/`despHeaderRow3`).
- `frontend/src/app/reports/iron-ore-mines/page.js:269` —
  `despBodyCells()`.
- `frontend/src/app/reports/iron-ore-mines/page.js:282` —
  `despFYTotalCells()`.

### 2026-09-12 — Iron ore mines page: 3-decimal display
**Commit:** `f15cbf3` — Show iron ore mines despatch/production figures to 3 decimal places
**Route:** `/reports/iron-ore-mines`
**What:** The `'000 T` figures now show 3 decimals instead of 2 (values at
this scale were losing meaningful precision).
**Files:**
- `frontend/src/app/reports/iron-ore-mines/page.js:204` — `fmt()`.

## Cross-Page & Infrastructure

### 2026-09-12 — RMG data backfills into `mis_reports` (no code commit — DB content only)
**Commit:** none — data-only changes, `mis_reports` database.
**What:** Backfilled `mines_production_monthly` and
`mines_despatch_actual_monthly` from the external `rmg` database's
`ubgm_pr_mth`/`u_pr_mth` (production) and `ubgm_ds_mth`/`u_ds_mth`
(despatch — Fines/Lump RAIL Captive+Sales, then Dump Fines) tables, using a
strict no-op-on-conflict upsert (`ON DUPLICATE KEY UPDATE x = x`) so nothing
already entered was ever overwritten. Also ran a correction pass: customer
codes prefixed "P" (`PBSP`/`PBSL`/`PISP`/`PRSP`/`PDSP`) turned out to mean
despatch to that plant's **Pellet Plant**, not open-market Sales — the
original Captive/Sales classification had lumped them into SALES for
BARSUA/BOLANI/KALTA/TALDIH, so those rows were split out into a proper
`PELLET_CONV` end-use (150 rows deleted, 30 updated, 171 inserted).
**Why:** the mine-level despatch/production tables were the last major gap
before `page_sail_mines.py`'s Iron Ore Production/Despatch table and the
Cover page's Iron Ore KPIs could be un-hardcoded (see the 2026-09-13 "Iron
Ore Production" entry under Page 4.5, which depends directly on this data
existing).
**Worth knowing:** if you ever backfill more despatch data from `rmg` for
BARSUA/BOLANI/KALTA/TALDIH, remember the "P"-prefix = Pellet Plant rule —
it's easy to silently re-introduce this same misclassification.

### 2026-09-12 — Dependency lockfile updates
**Commit:** `8c3961b` — Update dependency lockfiles from PDF generation perf work
**What:** `backend/requirements.txt` and `frontend/package-lock.json`,
picked up as a side effect of the PDF perf work below.
**Files:**
- `backend/requirements.txt`
- `frontend/package-lock.json`

### 2026-09-12 — layout_config.json decimal page-key support
**Commit:** `c3298b5` — Support decimal page keys in layout_config page-key expansion
**What:** `layout_config.json` page keys can now be sentinel decimals (e.g.
`"4.5"`, `"2.1"`), individually or via comma list, not just whole numbers/
ranges — lets per-page font/margin overrides target inserted sub-pages
(like the Steel Sector 2.1/2.2/2.3 pages) that don't have integer numbers.
**Files:**
- `backend/layout_loader.py:10` — `_expand_page_key()`.
- `backend/layout_loader.py:75` — call site.

### 2026-09-12 — PDF generation performance
**Commit:** `d828b31` — Speed up PDF generation: reuse browser, cache trend-split, batch stamps
**What:** Four independent fixes, ~2-3.7x faster full-report generation:
(1) a persistent Playwright/Chromium browser instance instead of relaunching
per render, (2) a trend-split result cache keyed by content hash, (3)
batching the main-page-number stamping into one `page.pdf()` call per
physical page dimension instead of one per page, (4) `_apply_dept_badges`
accepting a precomputed `start_of` index map instead of a full re-scan.
**Files:**
- `backend/pdf.py:1330` — `_get_persistent_browser()`.
- `backend/pdf.py:13` — `_PDF_EXECUTOR`.
- `backend/pdf.py:978-1022` — `_TREND_SPLIT_CACHE` /
  `_cache_trend_split_result()`.
- `backend/pdf.py:463` — `_wrap_stamp_batch_html()`.
- `backend/pdf.py:498` — `_stamp_main_page_numbers()`.
- `backend/pdf.py:264` — `_apply_dept_badges(..., start_of=...)`.

### 2026-09-11 — SETUP.md rewrite
**Commit:** `6498eea` — docs: update SETUP.md for fresh C: drive install (MySQL 9.7.2, Python 3.11 pin)
**What:** Rewritten for a fresh C: drive install (MySQL 9.7.2, Python 3.11
pin) after a full machine reformat.
**Files:**
- `backend/docs/SETUP.md`
