# Developer Changelog

Chronological log of report-affecting changes, one entry per logical piece of
work, each pointing at the commit(s) that made it. The point is speed: when
you need to change something (or figure out why it behaves the way it does),
skim this list, find the entry, and jump straight to the files/functions
named in it instead of re-discovering the whole area from scratch.

**Maintaining this file (do this from now on, every session):**
1. Finish a logical piece of work and commit it (or a small group of related
   commits).
2. Add one entry below, newest at the **top**, using the template:

   ```
   ### YYYY-MM-DD — Short, specific title
   **Commit:** `<hash>` — `<one-line commit subject>`
   **What:** 1-3 sentences, plain description of the behavior/code change.
   **Why:** the reason/instruction behind it — this is the part git log
   alone won't tell you.
   **Key files:** `path/to/file.py` (function/class names worth knowing),
   ...
   **Known issues:** only if something was left broken/incomplete on purpose.
   ```
3. If a change is DB-content only (a backfill, a data correction) with no
   code commit, still log it — write `**Commit:** none — data-only change`
   and say which table/DB so the data lineage isn't lost.
4. Keep each entry short enough to skim in a few seconds; link to the code's
   own docstrings/comments for the full detail rather than duplicating it
   here — this file is a map, not the territory.

---

### 2026-09-13 — At-a-Glance page typography pass (KNOWN ISSUE)
**Commit:** `1f3c9e0` — At-a-Glance page typography pass (KNOWN ISSUE: chart overlap, see DEV_CHANGELOG.md)
**What:** Increased font sizes across `at_a_glance.html` (title, section
headings, KPI-tile text, Techno-Economic tiles, Value Added Steel box) and
in `page_at_a_glance.py`'s `_trend_line_svg`/`_semis_table_html` chart
generators.
**Why:** manual readability tweak (page felt too dense/small).
**Key files:** `backend/page_templates/at_a_glance.html` (every size is
inline per-element, no shared classes except `.techno-tile`),
`backend/page_at_a_glance.py` (`_trend_line_svg` lines ~218-286,
`_semis_table_html` lines ~292+).
**Known issues:** `_trend_line_svg`'s per-point/legend/axis font sizes grew
(6.5/7/6.6 → 9.5/9.5/10 SVG user-units) but its canvas height
(`_trend_section()`'s `vh=95` call) did NOT grow to match — the bottom
"Saleable Steel & Finished Steel" trend chart's month-axis labels now
visibly overlap the "Semis by plant" heading/note right after it (confirmed
by rendering a real PDF). The enlarged `_semis_table_html` sizes also push
that table onto its own near-blank 2nd page, breaking this page's original
one-page design (see `.at-a-glance-page`'s own comment in `main.html`).
**Fix options, not yet applied:** either shrink those 3 font-sizes back
down, or raise `vh` in the `_trend_section()` call at line ~924 to give the
larger text room (and re-check the semis table still fits after).

### 2026-09-13 — Steel Sector Performance price-trend charts + page 2.1 typography
**Commit:** `8aeb565` — Add Steel Sector Performance price-trend charts; page 2.1 typography pass
**What:** Page 2.1 (`prod_prices`) gets a "Steel Prices Trend" line chart
under Table 1c (TMT/HR Coil/CR Coil/GP Sheet); page 2.2 (`demand_trade`)
gets an "NMDC Iron Ore Price Trend" chart under Table 4a (Lump/Fines).
Both trend from the current FY's April onward, using whatever archived PIB
releases actually exist. Chart labels show value in `'000` to 1 decimal
with a "K" suffix (e.g. `58.0K`) plus a top-right swatch+name legend.
**Why:** both pages had leftover blank space after an earlier CSS pass;
each monthly PIB release only ever archives its own rolling ~3-month price
window (not a full history), so a dedicated aggregator was needed to stitch
a real trend together across releases.
**Key files:** `backend/page_steel_sector_performance.py` —
`_series_from_archive()` (scans every archived row, keeps only columns that
parse as a real calendar month via `_parse_month_header()`, so each
release's trailing MoM%/YoY% columns are dropped automatically),
`_price_trend_svg()` (the chart itself — y-axis auto-scaled to the data's
own min/max, NOT zero-based, unlike `page_at_a_glance._trend_line_svg`),
`_price_chart_html()` (wraps it + wires into `generate_steel_sector_performance()`).
`backend/page_templates/steel_sector_performance.html` — the 2 one-line
insertion points (`page.steel_price_chart_html`, `page.nmdc_price_chart_html`).
`backend/page_templates/main.html` — also carries this session's manual
`.ssp-*` typography tweaks (title/table/section-heading sizes, section
padding, affects all 3 Steel Sector pages) plus an experimental
page-2.1-only compaction block (`.pg-2-1`, ~line 1719) meant to stop the new
chart pushing Table 1c onto a 2nd page.
**Known issues:** the `.pg-2-1` compaction block is currently **commented
out** (disabled) pending a decision on whether its tighter margins/type are
wanted — as of this commit, page 2.1 may spill onto 2 physical pages
depending on the report month's data. See `.pg-2-1`'s own comment in
`main.html` for exactly what it does when re-enabled.

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
entries below); they have been since.
**Why:** direct instruction — SAIL's own convention counts these
despatch-only materials as production at the point they leave the mine.
GUA's Dump Fines despatched CAPTIVE is deliberately excluded (that tonnage
already reaches the consuming plant as ordinary ore movement, not a
standalone recovered-and-sold quantity).
**Key files:** `backend/db.py` — `get_iron_ore_group_rollup_monthly()`.
`backend/page_sail_mines.py` — `generate_sail_mines()` (the
`iron_ore_monthly`/`iron_ore_cply_monthly` merge, replacing the old
`hardcoded.get(section["key"])` short-circuit for these two sections).
`backend/hardcoded_config.json` — `sail_mines.iron_ore_group_kt` (the
`iron_ore_prod`/`iron_ore_despatch` keys were removed; `iron_ore_sales`/
`iron_ore_sales_despatch`, a different table — Booked Quantity — stay
hardcoded, unbackfilled).
**Verified against:** Cover page's own reported number for Aug'26: 2.692 MT
(Lump+Fines only) → 2.846 MT (correct, +153.8 kt of Dump Fines/Tailings
sales that month).

### 2026-09-13 — Redesign Iron Ore Mines despatch table: full mode/end-use/material breakdown
**Commit:** `ad688be` — Redesign Iron Ore Mines despatch table: full mode/end-use/material breakdown
**What:** `/reports/iron-ore-mines`'s Despatch table now shows a nested
Rail/Road → Captive/Sales/Pellet Conv. → Lump/Fines/Dump Fines/Tailings/
Pellets breakdown instead of flat material-only columns, hiding any
combination with no non-zero data for the current scope/FY so the table
stays readable despite the extra depth. Excel export updated to match; the
old flat Rail/Road total columns were removed (redundant — each mode block
now carries its own Total column).
**Why:** direct instruction, to expose the full despatch classification
now that the underlying data supports it (see the backfill entries below).
**Key files:** `frontend/src/app/reports/iron-ore-mines/page.js` —
`despDetail`/`despStructure` (the visibility-filtering logic that hides
all-zero mode/end-use/material combos), the 3-row `<thead>` builder
(`despHeaderRow1/2/3`), `despBodyCells()`/`despFYTotalCells()`.

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
Cover page's Iron Ore KPIs could be un-hardcoded (see the 2026-09-13
"Iron Ore Production" entry above, which depends directly on this data
existing).
**Worth knowing:** if you ever backfill more despatch data from `rmg` for
BARSUA/BOLANI/KALTA/TALDIH, remember the "P"-prefix = Pellet Plant rule —
it's easy to silently re-introduce this same misclassification.

### 2026-09-12 — Dependency lockfile updates
**Commit:** `8c3961b` — Update dependency lockfiles from PDF generation perf work
**What:** `backend/requirements.txt` and `frontend/package-lock.json`,
picked up as a side effect of the PDF perf work below.

### 2026-09-12 — Iron ore mines page: 3-decimal display
**Commit:** `f15cbf3` — Show iron ore mines despatch/production figures to 3 decimal places
**What:** `/reports/iron-ore-mines`'s `'000 T` figures now show 3 decimals
instead of 2 (values at this scale were losing meaningful precision).
**Key files:** `frontend/src/app/reports/iron-ore-mines/page.js` — the
`fmt()` function.

### 2026-09-12 — layout_config.json decimal page-key support
**Commit:** `c3298b5` — Support decimal page keys in layout_config page-key expansion
**What:** `layout_config.json` page keys can now be sentinel decimals (e.g.
`"4.5"`, `"2.1"`), individually or via comma list, not just whole numbers/
ranges — lets per-page font/margin overrides target inserted sub-pages
(like the Steel Sector 2.1/2.2/2.3 pages) that don't have integer numbers.
**Key files:** `backend/layout_loader.py` — `_expand_page_key()`.

### 2026-09-12 — PDF generation performance
**Commit:** `d828b31` — Speed up PDF generation: reuse browser, cache trend-split, batch stamps
**What:** Four independent fixes, ~2-3.7x faster full-report generation:
(1) a persistent Playwright/Chromium browser instance instead of relaunching
per render, (2) a trend-split result cache keyed by content hash, (3)
batching the main-page-number stamping into one `page.pdf()` call per
physical page dimension instead of one per page, (4) `_apply_dept_badges`
accepting a precomputed `start_of` index map instead of a full re-scan.
**Key files:** `backend/pdf.py` — `_get_persistent_browser()`,
`_PDF_EXECUTOR`, `_TREND_SPLIT_CACHE`/`_cache_trend_split_result()`,
`_stamp_main_page_numbers()`/`_wrap_stamp_batch_html()`,
`_apply_dept_badges(..., start_of=...)`.

### 2026-09-11 — SETUP.md rewrite
**Commit:** `6498eea` — docs: update SETUP.md for fresh C: drive install (MySQL 9.7.2, Python 3.11 pin)
**What:** Rewritten for a fresh C: drive install (MySQL 9.7.2, Python 3.11
pin) after a full machine reformat.
**Key files:** `backend/docs/SETUP.md`.
