# Mines Production Performance — design

Date: 2026-10-17
Status: approved in conversation (structure, calculations, outputs); spec awaiting review

## Purpose

A standalone report of mines' production performance, laid out like the
monthly report's pages 5-6 ("Plant Wise Item Wise Production & CS to HM
Ratio") but with mines in place of plants and mines items in place of plant
items. It is produced on its own (web view + PDF + Excel) and is **not** part
of the monthly PDF report yet: some of its information (coal and flux at mine
level) is not in the application today and will be added as it becomes
available. It will be added to the monthly report later.

### What the user asked for

1. I/Ore Fresh Production — heading row (blank cells), then Lump, Fines, Total.
2. I/Ore Despatch — Lump, Fines, Pellets, Dump Fines, Tailings, Total,
   sub-grouped by Captive / Conversion Agent / Sales with a total per
   sub-group and a grand total.
3. Reported Production — fresh production plus despatch of Pellets, Dump
   Fines, Tailings etc., as on the "SAIL Mines Production & Despatch
   Performance" page.
4. Coal mines production, washery production, coal despatch.
5. Flux mines: Limestone and Dolomite production and despatch.
6. A SAIL table clubbing like items from all mines.
7. Booking of sales quantity for each mine.

### Decisions taken

| Question | Decision |
|---|---|
| Iron ore granularity | Each mine, then its group (JGoM/OGoM/CGoM), then SAIL |
| Despatch layout | End-use sub-groups; material rows with no data hidden |
| Coal & flux | SAIL block only, from existing SAIL-level data; per-mine later |
| Where / outputs | New tab in `/reports/mines`; PDF and Excel downloads |
| Architecture | Approach A: standalone, same pattern as Plant Wise Performance (APP & MoU) |

## Architecture

Same pattern as the existing Plant Wise Performance (APP & MoU) report
(`api_plant_performance.py` + `plant_performance_pdf.py` + its `View.js`).

| Unit | Responsibility | Depends on |
|---|---|---|
| `backend/mines_performance.py` | Pure computation: `generate(month) -> {labels, blocks}` | `db.connect()` only |
| `backend/api_mines_performance.py` | FastAPI router: JSON, `/xlsx`, `/pdf`; input validation | `mines_performance`, `mines_performance_pdf`, `colors_loader`, openpyxl |
| `backend/mines_performance_pdf.py` | Standalone A4 HTML template + Playwright render | `colors_config.json` via `colors_loader`, `pdf._local_font_face_css` |
| `frontend/src/components/reports/mines-performance/View.js` | Web tab: controls, table, downloads | the JSON endpoint |

Wiring: `main.py` includes the router (one line, next to the plant
performance router); `reportGroups.js` gets a `mines-performance` tab in the
`mines` group; `ReportTabs.js`'s `VIEWS` map gets the view.

Not touched: the monthly report PDF (`pdf.py`, `page_templates/`,
`layout_config.json`, layout guard), `page_sail_mines.py`, and the database
schema (no new tables or columns).

## Report structure

Unit: '000 T (as the SAIL Mines page's iron-ore table).

### Block order

From `mine_groups_master.sort_order` and `mines_master.sort_order` (active
mines only), so a new mine appears without a code change:

```
JGoM: Kiriburu, Meghahatuburu, Gua, Manoharpur, then JGoM (group total)
OGoM: Bolani, Barsua, Taldih, Kalta,            then OGoM (group total)
CGoM: Rajhara, Dalli, Rowghat,                  then CGoM (group total)
SAIL
```

Each block's name is shown vertically in the left (entity) column, as plant
names are on pages 5-6.

### Iron-ore rows (every mine, group and the SAIL block)

```
I/ORE FRESH PRODUCTION            heading     (blank cells)
   Lump                           item
   Fines                          item
   Total Fresh Production         total
I/ORE DESPATCH                    heading
  Captive                         subheading
   <materials with data>          item        Lump, Fines, Pellets, Dump Fines, Tailings (master order)
   Total Captive                  total
  Conversion Agent                subheading
   <materials with data>          item
   Total Conversion Agent         total
  Sales                           subheading
   <materials with data>          item
   Total Sales                    total
   Grand Total Despatch           total
REPORTED PRODUCTION               heading
   Fresh Production (Lump+Fines)  item
   Pellets Despatch               item        any end use
   Dump Fines Despatch            item        Captive + Sales
   Tailings Despatch              item        Sales only
   Reported Production            total
BOOKED QUANTITY (SALES)           heading
   <materials with data>          item
   Total Booked                   total
```

Labels: the end uses come from `mine_end_uses_master` (CAPTIVE, PELLET_CONV,
SALES), displayed as "Captive", "Conversion Agent", "Sales"; materials from
`mine_materials_master.material_name`.

### Extra SAIL-only sections (coal & flux)

Appended to the SAIL block, from `sail_mines_monthly`:

```
COAL MINES PRODUCTION     Raw Coking Coal, Thermal Coal, Total
WASHERY                   Input Raw Coal, Clean Coal, Yield (%)
COAL DESPATCH             Clean Coal, Thermal, Total
FLUX PRODUCTION           Limestone, Dolomite, Total
FLUX DESPATCH             Limestone, Dolomite, Total
```

(`sail_mines_monthly` sections `coal_prod`, `washery`, `coal_despatch`,
`flux_prod`, `flux_despatch`.) A one-line note under the SAIL block:
"Coal and flux are shown at SAIL level; mine-level figures will be added."

### Hiding empty rows

- A material `item` row is hidden when its FY Plan, month and Apr-to-month
  Plan/Actual, and both CPLY values are all blank.
- A sub-group with no visible item rows is hidden with its sub-heading and
  total.
- A section with no visible rows is hidden with its heading (e.g. Booked
  Quantity at a mine that books nothing; Despatch sub-groups a mine never
  uses).
- Exceptions: I/Ore Fresh Production (Lump, Fines, Total) always shows; the
  Reported Production section always shows its Fresh Production and total
  rows (its three despatch component rows follow the normal rule).
- Coal/flux rows always show (fixed SAIL-level items).

## Columns and calculations

Every row has 11 values, as on pages 5-6:

| # | Column | Value |
|---|---|---|
| 0 | FY Plan | sum of the 12 monthly plans of the FY |
| 1 | Month Plan | report month's plan |
| 2 | Month Actual | report month's actual |
| 3 | Month %Ful | Actual ÷ Plan × 100 |
| 4 | Month CPLY Act. | same month last FY, actual |
| 5 | Month %Gr | (Actual − CPLY) ÷ CPLY × 100 |
| 6 | Apr-to-month Plan | April..report month plans summed |
| 7 | Apr-to-month Actual | April..report month actuals summed |
| 8 | Apr-to-month %Ful | Actual ÷ Plan × 100 |
| 9 | Apr-to-month CPLY Act. | same span last FY, actuals summed |
| 10 | Apr-to-month %Gr | (Actual − CPLY) ÷ CPLY × 100 |

Rules:

- Sums skip blanks; a sum is blank only when every part is blank.
- %Ful / %Gr are blank (not 0, not infinite) when the denominator is blank or
  0, or the numerator is blank.
- Heading and sub-heading rows: all 11 values blank.
- Every total (sub-group, Grand Total, Reported Production, group and SAIL
  blocks) is a live sum of its parts; nothing is a stored total.
- Group = sum of its mines; SAIL iron-ore = sum of all mines.
- Washery Yield (%) = Clean Coal ÷ Input Raw Coal × 100, computed separately
  for each of FY Plan, Plan, Actual and CPLY (month and Apr-to-month); its
  %Ful / %Gr are then taken from those yields. Shown with 1 decimal.
- Coal/flux "Total" rows = sum of the two items (coal despatch Total =
  Clean Coal + Thermal).

### Sources

| Rows | Actual | Plan |
|---|---|---|
| Fresh Lump/Fines | `mines_production_monthly.qty_actual` | `mines_production_monthly.qty_plan` |
| Despatch, per material × end use | `mines_despatch_actual_monthly.qty_actual`, Rail + Road summed | `mines_despatch_plan_monthly.qty_plan` |
| Reported Production components | the despatch actuals above, filtered by the rule | the despatch plans, same filter |
| Booked Quantity, per material | `mines_booked_qty_actual_monthly.qty_actual`, Rail + Road summed | `mines_booked_qty_plan_monthly.qty_plan` |
| Coal / washery / flux (SAIL) | `sail_mines_monthly.month_actual` | `sail_mines_monthly.month_plan` |

The Reported Production rule is the one in
`db.get_iron_ore_group_rollup_monthly` (Pellets: any end use; Dump Fines:
CAPTIVE or SALES; Tailings: SALES), applied per mine. Its SAIL total must
equal the SAIL Mines page's Iron Ore Production for the same month.

All data is read in one pass for the 24 months needed (current FY to the
report month, and the same months of the previous FY), into an in-memory
`{(mine, kind, material, end_use): {month: (actual, plan)}}` map; rows are
built from that map.

### Known data gaps (shown as blanks)

- Despatch plan exists only from Apr'26: earlier FYs show no despatch
  Plan / %Ful.
- Booked Quantity actuals start Apr'25 (CPLY blank before that); its plan
  exists only for Sep'26 so far.
- Coal and flux exist only at SAIL level.

## Number display

- Decimals selector 0–3 on the web tab (default 0, as pages 5-6), remembered
  per browser (try/catch'd localStorage, same as Plant Wise Performance).
- Quantities to the chosen decimals; percentages whole numbers, except
  Washery Yield (%) at 1 decimal.
- Downloads use the chosen decimals.

## API

```
GET /api/mines-performance?month=YYYY-MM                    -> JSON
GET /api/mines-performance/xlsx?month=YYYY-MM&decimals=N    -> .xlsx
GET /api/mines-performance/pdf?month=YYYY-MM&decimals=N     -> .pdf
```

JSON shape:

```
{
  "labels": {"title", "fy", "fy_plan", "month", "cply", "ytd", "ytd_cply"},
  "blocks": [
    {"name": "Kiriburu", "kind": "mine" | "group" | "sail", "group": "JGoM",
     "note": null | "Coal and flux ...",
     "rows": [{"label", "kind": "heading"|"subheading"|"item"|"total",
               "values": [11 numbers or null], "pct_idx": [3,5,8,10],
               "decimals": null | 1}]}
  ]
}
```

Unrounded values in JSON; rounding happens in the view / downloads.

Errors: malformed month or decimals outside 0–3 → HTTP 400. A month with no
mines data at all returns `blocks: []`; the view shows
"No mines data for <month>".

## Outputs

### Web tab

`/reports/mines?tab=mines-performance`, label "Mines Production
Performance". Controls: Report month, Decimals, Download Excel, Download PDF.
Table styling follows the current Plant Wise Performance view: IBM Plex Sans
figures, Arial Narrow headers, black outer frame, no light lines between rows,
black rule above each section heading and total row; headings bold capitals,
sub-headings bold, totals bold with a light fill; Plan and Actual columns
tinted as pages 5-6. Block name vertical in the left column.

### PDF

`mines_performance_pdf.py`, A4 portrait, own template (not the monthly
report's), same fonts and border rules as `plant_performance_pdf.py`, colours
from `colors_config.json` (existing `perf_*` keys; no new keys unless a new
colour is needed, in which case added to both `colors_config.json` and
`colors_loader._DEFAULTS`). Page heading: "Mines Production Performance
:<Mon>'<yy> and Apr-<Mon>'<yy>", "Unit: '000 T". A block is never split
across pages (`break-inside: avoid` per block `tbody`); the header row repeats
on each page; the SAIL block starts a new page. Natural row height — no
fit-to-page stretching.

### Excel

One sheet "Mines Performance": title row, two header rows (as pages 5-6),
block name in a merged vertical cell per block, headings/sub-headings/totals
bold, number format by the chosen decimals (percent columns whole numbers,
Yield 1 decimal).

## Testing

1. `backend/tests/test_mines_performance.py` — generator against a temp
   SQLite DB (`db.connect` monkeypatched, as `test_page4_basis.py`):
   Fresh Total = Lump + Fines; despatch sub-group totals and Grand Total;
   Reported Production rule (Pellets any end use, Dump Fines Captive+Sales
   only, Tailings Sales only); group = sum of mines, SAIL = sum of all mines;
   Apr-to-month and CPLY spans; %Ful/%Gr blank on zero/missing denominators;
   hiding of empty rows/sub-groups/sections and the always-shown exceptions;
   Washery Yield from its parts.
2. `backend/tests/test_api_mines_performance.py` — month/decimals validation
   (400s), JSON shape, xlsx structure (merged block cells, number formats),
   PDF endpoint returns PDF bytes (renderer monkeypatched).
3. Live check on MySQL for 2026-09: SAIL Reported Production and Grand Total
   Despatch (month and Apr-to-month) equal the SAIL Mines page's iron-ore
   Production and Despatch for 2026-09.
4. `npm run lint` for the frontend; open the tab in the browser; open the
   downloaded PDF and xlsx.

## Later (out of scope now)

- Mine-level coal (mines, washeries) and flux entry + masters, then coal/flux
  rows per mine and group.
- Adding the report to the monthly PDF: a thin `page_mines_performance.py`
  calling `mines_performance.generate(month)` plus a template under
  `page_templates/`, following `PDF_LAYOUT_GUARDRAILS.md`.
