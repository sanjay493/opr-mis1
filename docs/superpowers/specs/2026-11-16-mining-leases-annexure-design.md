# SAIL Mining Leases annexure — design (approved 2026-11-16)

## Intent
Add the "Details of SAIL Mining Leases" table (source: `14.10.2026_Details of SAIL Mining Leases.xlsx`) to the PDF report as **Annexure-1: SAIL Mining at a Glance**, kept editable by authenticated users. The Ready Reckoner annexures move to Annexure-2 under one separator.

## Goals
- One merged-cell table page (mine / state / mineral / reserves / status spanning several lease rows, as in the Excel).
- Data entry tab (Data Entry > Reference) behind the existing editor login: add, edit, delete, reorder rows, and set "spans N rows" on spanning cells.
- Annexure-1 separator + mining page; Annexure-2 "5 ISPs & 3 SSPs Ready Reckoner" with a single separator; Annexure-3/4 unchanged; Index page and `report/page.js` titles/ids updated.

## Non-goals
Cleaning the source data (typos, S.No. order are seeded as-is and fixed through the form). No per-month versioning: the table is a single current snapshot.

## Constraints
- MySQL only; SQL only in `backend/repo/mining_leases.py`; native `%s`; every write bumps `data_version`; schema in `schema_v2.sql` plus `scripts/v2/migrate_mining_leases.sql`.
- PDF layout guardrails; colours as named keys in `colors_config.json` and `colors_loader._DEFAULTS`.
- Index page counts are hand-maintained in `main.py` `_INDEX_SECTIONS`.

## Approaches
Storage: (a) relational table with span columns (chosen: matches the repo pattern, editable row by row); (b) one JSON blob per page (rejected: no row-level edit, harder to validate).
Merging: (a) explicit span counts per cell (chosen by the user); (b) repeat values on each row (rejected by the user).

## Design
- Table `mining_leases`: id, sort_order, s_no, mine, state, lease, mineral, area (text), reserves (text), status, plus `mine_span`, `state_span`, `mineral_span`, `reserves_span`, `status_span` (1 = own row; N = covers N rows; 0 = covered by the cell above, stored blank). Server rejects spans that overrun the table or cover a row that has its own value.
- Seed from the Excel using its merged ranges.
- `api_mining_leases.py`: list (public to the report), save/replace rows (editor login).
- Frontend: `components/entry/mining-leases/Form.js`, added to `entryGroups.js` and `EntryTabs.js`.
- PDF: `page_mining_leases.py` + `page_templates/mining_leases.html`, separator reuse of `ready_reckoner_separator` with new labels; preview `MiningLeasesTemplate.js`.
- Ready Reckoner: drop the SSP separator, relabel the ISP separator.

## Left to the builder
Exact page ids, fit-to-page behaviour if 55 rows run tall (landscape or scale), colours, tests, `layout_guard --accept`.
