# Monthly Rail Loading table (Rail Logistics, first page) — design

Agreed with the user 2026-11-14. Extends
`2026-11-14-rail-logistics-mis-pdf-design.md`.

## Goal

The Rail Logistics pages only cover rakes loaded at the plants. SAIL's total
rail loading also includes every inward raw-material rake. A new first page of
the Rail Logistics section shows SAIL's month-wise rail loading by commodity —
inward raw materials (with sub-groups) and outward plant despatch — with
totals.

## Source

The Rail Movement Cell's monthly highlights note, kept as plain text
(`I:\My Drive\Report_format\Miscellaneous\Monthly Rail logistic highlights.txt`,
one "*Rail Transportation Performance of SAIL during <MONTH> <YEAR>*" block per
month; Apr–Oct 2026 today). History is loaded now from that file by a script;
a data-entry screen comes later (out of scope).

## Rows (item codes, in print order)

INWARD – RAW MATERIALS & COAL
| code | label | from the note |
|---|---|---|
| ore_ogom_jgom | Iron ore – OGOM & JGOM mines | (i)(a) "From OGOM & JGOM Mines – N rakes" |
| ore_bhilai | Iron ore – Bhilai mines | (i)(b) |
| ore_total | Total iron ore | "Total Iron Ore – N rakes" |
| flux_limestone | Flux – Limestone | "(Limestone – N Rakes, …)" |
| flux_dolomite | Flux – Dolomite | "(…, Dolomite – N Rakes)" |
| flux_total | Total flux | "Total Flux loaded N rakes" |
| port_coal | Ports – Imported coal | (iii)(a) |
| port_limestone | Ports – Imported limestone | (iii)(b) |
| port_total | Total from ports | "Total from Ports – N rakes" |
| coal_coking | Indigenous coal – Coking | "(Coking Coal – N rakes" (may be fractional, e.g. 46.3) |
| coal_power | Indigenous coal – Powerhouse | "Powerhouse coal – N rakes)" |
| coal_total | Total indigenous coal | "(iv) Loading of Indigenous Coal – N rakes" |
| misc_pellets | Misc – Pellets | "Pellets-N" |
| misc_other | Misc – Ferro alloy, Mn ore & others | misc_total − misc_pellets, at load time |
| misc_total | Total misc raw materials | "(v) Misc raw materials … – N rakes" |
| inward_total | TOTAL INWARD | "Total Raw Materials and Coal … – N rakes" |

OUTWARD – FROM SAIL PLANTS
| code | label | from the note |
|---|---|---|
| out_steel | Iron & steel | "(i) … Total Despatch – N rakes" |
| out_slag | Slag | "(ii) Total Slag … - N rakes" |
| out_coke | Coke & coke fraction | "(iii) Coke & Coke fraction – N rakes" |
| out_sinter | Sinter | "(iv) Sinter - N rakes" (blank = 0) |
| outward_total | TOTAL OUTWARD | "Total Outward rakes … – N rakes" |

| grand_total | GRAND TOTAL (inward + outward) | "… during the month was N rakes" |
| (computed) | Rakes per day | grand_total ÷ days (not stored) |

EXPORT (memo, included in iron & steel)
| export_port | Export – through ports | "(a) Through Ports : N rakes" (blank = 0) |
| export_nepal | Export – to Nepal | "(b) To Nepal Destinations : N rakes" |
| export_total | Total export | "Total export rakes : N rakes" |

Totals are **stored as the note reports them, never summed**: imported
limestone is counted under both Flux and Ports, so the sections add up to more
than the reported inward total (Apr'26: 1646 vs 1623). The item registry
(codes, labels, groups, which rows are totals) lives in Python
(`rail_loading.py`), not in the database.

## Storage

New table `rail_loading_monthly` (schema_v2.sql + `scripts/v2/migrate_add_rail_loading.sql`):
`report_month CHAR(7)` (FK cal_month), `item_code VARCHAR(32)`, `rakes DOUBLE NULL`,
`updated_at DATETIME`, `updated_by VARCHAR(64)`; PK (report_month, item_code).
SQL only in `backend/repo/rail_loading.py`: `rail_loading_rows(first_month, last_month)`
and `save_rail_loading(month, {code: rakes}, user)` (bumps data_version first,
replaces the month's rows).

## Loading the history

`rail_loading_highlights.py` — pure parser: text → `{report_month: {code: rakes}}`
(month from the block heading). `scripts/load_rail_loading_highlights.py <file>
[--dry-run]` parses, prints each month's figures and a check that the sections
it found are present, then saves through the repo. Re-running replaces those
months. A month whose block can't be parsed is reported and skipped, never
half-saved.

## Page

New page id **40.05** ("Rail Logistics – Monthly Rail Loading"), portrait,
first of the section (before 40.1). Columns: item label, Apr…Mar of the report
month's FY (months after the report month blank), FYTD (sum of the months
present), FYTD rakes/day for the total rows. Group heading rows (INWARD /
OUTWARD / EXPORT), total rows bold on the total-row tint, grand total and
rakes/day emphasised. Missing values print "–". No data for any month of the
FY → the page prints its title and "Monthly rail loading for FY <fy> not yet
entered".

Wiring as the other Rail Logistics pages: `RAIL_LOGISTICS_PAGES` gains 40.05
(so main.py's dispatch, page lists and export insertion pick it up), Index row
count 3 → 4 (anchor = min id = 40.05), `report_utils` canonical order + badge
group 10, `/report` `PAGE_LABELS` + `SERVER_DATED_TYPES`, a React preview
template. Colours: existing `rail_log_*` / `perf_*` keys.

## Testing

- Parser: golden test on the real Apr and Oct 2026 blocks (fixture copy of the
  file) — every code's value, incl. fractional coal, blank sinter/port export,
  and misc_other.
- Page builder: FYTD sums, blank future months, rakes/day, placeholder.
- Repo: save/read round trip on the test DB conventions used by
  `tests/test_repo_v2_rake.py`; guard tests (boundary, writes-bump, schema).
- Real render 2026-10: 40.05 on one sheet, Index row = 4 pages.

## Out of scope

The data-entry/upload screen; older history (loaded later with the same
script once the user sends it); any change to pages 40.1-40.3.
