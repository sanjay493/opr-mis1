# SAIL Mining Leases Annexure Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Print the SAIL Mining Leases table as Annexure-1 "SAIL Mining at a Glance" (merged-cell look), merge the Ready Reckoner annexures into Annexure-2 "5 ISPs & 3 SSPs Ready Reckoner", and let editors maintain the lease rows.

**Architecture:** New MySQL table `mining_leases` (one row per lease, span counts per merged column) behind `repo/mining_leases.py`; pure span/page logic in `mining_leases.py`; `api_mining_leases.py` router (editor login); a new PDF page type `mining_leases` wired like Rail Logistics; a Data Entry > Reference tab; separator/Index changes.

**Tech Stack:** FastAPI, MySQL (`%s`), Jinja page templates rendered by Chromium, Next.js 16 (read `frontend/AGENTS.md` first), pytest.

**Spec:** `docs/superpowers/specs/2026-11-16-mining-leases-annexure-design.md`

## Global Constraints

- Python: `backend/venv/Scripts/python.exe -m pytest ...`; never the system Python.
- SQL only in `backend/repo/mining_leases.py`, native MySQL `%s`; every repo write calls `_ver.bump(cur)` first (`tests/test_repo_writes_bump.py`); `tests/test_repo_boundary.py` stays green.
- New table goes in `scripts/v2/schema_v2.sql` **and** `scripts/v2/migrate_mining_leases.sql`; apply the migration to the live DB `mis_reports_v2`.
- Every PDF colour is a key in `colors_config.json` and `colors_loader._DEFAULTS`; no hex in templates.
- Read `backend/docs/PDF_LAYOUT_GUARDRAILS.md` before touching templates / `pdf.py`; finish with `layout_guard.py --render 2026-08` then `--accept --render 2026-08`.
- Index counts are hand-maintained in `main.py` `_INDEX_SECTIONS`.
- Titles: "Annexure-1 : SAIL Mining at a Glance", "Annexure-2 : 5 ISPs & 3 SSPs Ready Reckoner".

## Review Focus

- A span that overruns the table end, or covers a row that carries its own value, is rejected with 422.
- A lease with no mine/state/mineral (blank, un-merged) prints blank, not "None".
- Area and reserves free text ("208( Broken area- 11MT)", "Un-Explored", "Exhausted") is stored and printed verbatim.
- Reordering or deleting a row that is the head of a span re-validates the spans (no orphaned covered rows).
- An empty table prints the page with a "no data" line, not a crash; non-editors get 401/403 on save.

---

### Task 1: Table, migration and repo

**Files:**
- Modify: `backend/scripts/v2/schema_v2.sql`
- Create: `backend/scripts/v2/migrate_mining_leases.sql`, `backend/repo/mining_leases.py`
- Test: `backend/tests/test_repo_mining_leases.py`

**Interfaces:**
- Produces: `repo.mining_leases.list_rows() -> list[dict]` (ordered by `sort_order`, each dict has keys `id, sort_order, s_no, mine, state, lease, mineral, area, reserves, status, mine_span, state_span, mineral_span, reserves_span, status_span`) and `replace_rows(rows: list[dict], user: str | None) -> int` (replaces the whole table in one transaction, bumping `data_version` first; returns rows saved).

- [ ] **Step 1:** Write `test_repo_mining_leases.py` (copy the fixture/DB approach of `tests/test_repo_v2_misc.py`): `test_replace_then_list_round_trips` (spans and verbatim text such as `"208( Broken area- 11MT)"` survive), `test_replace_bumps_data_version`, `test_replace_with_empty_list_clears`.
- [ ] **Step 2:** Run it; expected FAIL (module missing).
- [ ] **Step 3:** Add `mining_leases` to `schema_v2.sql` and `migrate_mining_leases.sql`: `id INT AUTO_INCREMENT PK, sort_order INT NOT NULL, s_no VARCHAR(8), mine/state/lease/mineral VARCHAR(160), area/reserves VARCHAR(160), status VARCHAR(255), five *_span TINYINT NOT NULL DEFAULT 1, updated_at, updated_by VARCHAR(64)`. Apply the migration to the live DB.
- [ ] **Step 4:** Implement `repo/mining_leases.py` in the style of `repo/rake.py` (`connect`, `_ver.bump`, `activity_context.record("mining_leases", ...)`).
- [ ] **Step 5:** Run `tests/test_repo_mining_leases.py tests/test_repo_boundary.py tests/test_repo_writes_bump.py`; expected PASS.
- [ ] **Step 6:** Commit.

### Task 2: Span logic and Excel seed

**Files:**
- Create: `backend/mining_leases.py`, `backend/scripts/seed_mining_leases.py`
- Test: `backend/tests/test_mining_leases.py`

**Interfaces:**
- Consumes: `repo.mining_leases.list_rows/replace_rows`.
- Produces: `SPAN_COLS = ("mine", "state", "mineral", "reserves", "status")`; `validate(rows: list[dict]) -> list[dict]` (raises `ValueError` with a row-numbered message; returns rows with covered cells forced to `""` and spans normalised to ints); `build_page() -> {"available": bool, "rows": [...]}` where each row has, per span column, `{"text": str, "span": int}` and `span == 0` means skip the cell when rendering; `save(rows, user) -> int` (validate then `replace_rows`).

- [ ] **Step 1:** Write tests: `test_span_overrun_rejected`, `test_covered_cell_with_value_rejected`, `test_head_span_covers_following_rows_in_page`, `test_verbatim_free_text_kept`, `test_empty_table_page_unavailable`.
- [ ] **Step 2:** Run; FAIL.
- [ ] **Step 3:** Implement `mining_leases.py` (pure functions, no SQL).
- [ ] **Step 4:** Write `seed_mining_leases.py`: reads the xlsx path from argv, uses `openpyxl` merged ranges to set spans (column map B/C/E/G/H -> mine/state/mineral/reserves/status), keeps source text and S.No. order verbatim, calls `mining_leases.save`. Run it on `C:\Users\H000493\Downloads\14.10.2026_Details of SAIL Mining Leases.xlsx`; check the printed row count equals the source's data rows.
- [ ] **Step 5:** Run `tests/test_mining_leases.py`; PASS. Commit.

### Task 3: API router

**Files:**
- Create: `backend/api_mining_leases.py`
- Modify: `backend/main.py` (import + `app.include_router`, next to `rail_loading_router`)
- Test: `backend/tests/test_api_mining_leases.py`

**Interfaces:**
- Produces: `GET /api/mining-leases` -> `{"rows": [...]}` (public, like other report reads); `POST /api/mining-leases` with `{"rows": [...]}` guarded by `Depends(_auth.require_editor_or_admin)`, 422 with the `validate` message on bad spans, returns `{"status": "ok", "saved": n, "rows": [...]}`.

- [ ] **Step 1:** Tests modelled on `test_rail_loading.py` (`test_api_save_needs_an_editor_login`): `test_save_needs_editor_login`, `test_get_returns_rows`, `test_bad_span_422`, `test_save_round_trip`.
- [ ] **Step 2:** Run; FAIL. **Step 3:** Implement and register. **Step 4:** Run; PASS. **Step 5:** Commit.

### Task 4: PDF page, separators, Index

**Files:**
- Create: `backend/page_mining_leases.py`, `backend/page_templates/mining_leases.html`
- Modify: `backend/page_ready_reckoner.py` (`_SEPARATOR_LABELS`, `generate_ready_reckoner_separator`), `backend/main.py` (every site that lists `READY_RECKONER_ISP_SEPARATOR_PAGE_ID` / `READY_RECKONER_SSP_SEPARATOR_PAGE_ID`: lines near 760-830, 1147-1151, 1292-1299, 1387-1391, 1487-1494, 1790-1800, 1922-1935; and `_INDEX_SECTIONS` near 426), `backend/colors_config.json` + `colors_loader.py`, `backend/pdf.py` if page types are registered there, `backend/layout_config.json` if the page needs an entry
- Test: `backend/tests/test_page_mining_leases.py`

**Interfaces:**
- Consumes: `mining_leases.build_page()`.
- Produces: `MINING_SEPARATOR_PAGE_ID` and `MINING_PAGE_ID` (next two unused ids above 1074; grep to confirm free), `generate_mining_leases() -> {"type": "mining_leases", "title": "SAIL Mining at a Glance", **mining_leases.build_page()}`, `generate_ready_reckoner_separator("MINING" | "ISP")` returning ("Annexure-1", "SAIL Mining at a Glance") / ("Annexure-2", "5 ISPs & 3 SSPs Ready Reckoner").

- [ ] **Step 1:** Tests: `test_separator_labels` (MINING and ISP labels as above), `test_page_rows_carry_spans`, `test_sequence_has_one_ready_reckoner_separator` (page order: mining separator, mining page, ISP separator, 5 ISP plants x2 pages, SSP plants x2 pages with no SSP separator).
- [ ] **Step 2:** Run; FAIL.
- [ ] **Step 3:** Implement `page_mining_leases.py`; template renders a `rowspan` table in the guardrail style (colours as named keys, 1px borders, fit-to-page); mining separator reuses `ready_reckoner_separator.html`.
- [ ] **Step 4:** Update the main.py sites so the order is: mining separator, mining page, ISP separator (now Annexure-2), ISP pages, SSP pages; remove the SSP separator from every sequence.
- [ ] **Step 5:** `_INDEX_SECTIONS`: replace the two Annexure rows with `("Annexure-1 : SAIL Mining at a Glance", 2)` and `("Annexure-2 : 5 ISPs & 3 SSPs Ready Reckoner", 20)` (14 + 7 - the dropped SSP separator); Annexure-3/4 rows unchanged.
- [ ] **Step 6:** Run the new tests plus `tests/test_rail_loading.py tests/test_page_rail_logistics.py` and the full `pytest tests`; PASS. Commit.

### Task 5: Frontend preview and data entry

**Files:**
- Create: `frontend/src/components/MiningLeasesTemplate.js`, `frontend/src/components/entry/mining-leases/Form.js`
- Modify: `frontend/src/components/PageRenderer.js` (type list ~line 57-61 and the `case`), `frontend/src/app/report/page.js` (titles ~91 and 102, and the type list ~262), `frontend/src/components/entry/entryGroups.js` (Reference tab), `frontend/src/components/entry/EntryTabs.js` (`FORMS`), `frontend/src/components/ReadyReckonerSeparatorTemplate.js` if it holds the old labels

- [ ] **Step 1:** Template mirrors `mining_leases.html` (read `frontend/AGENTS.md`; copy hex values from `colors_config.json`).
- [ ] **Step 2:** Form: loads `GET /api/mining-leases`; table of editable rows with add / delete / move up-down; a "spans N rows" number input on each span column that disables and blanks the covered cells; Save posts to the API; shows the server's 422 message; read-only note when not logged in as editor (follow `entry/rail-loading/Form.js`).
- [ ] **Step 3:** Update titles: 1041 -> "Annexure-2 : 5 ISPs & 3 SSPs Ready Reckoner", drop 1052's entry, add the mining ids.
- [ ] **Step 4:** `cd frontend && npm run lint`; expected no errors. Check in the browser (`http://localhost:3000/data-entry/reference?tab=mining-leases` and `/report`). Commit.

### Task 6: Verify and baseline

- [ ] **Step 1:** `venv/Scripts/python.exe -m pytest tests` all green.
- [ ] **Step 2:** `venv/Scripts/python.exe layout_guard.py --render 2026-08`: no warnings; inspect the mining page and Index in the PDF (pypdfium2) for spans, borders and page numbers.
- [ ] **Step 3:** `layout_guard.py --accept --render 2026-08`; commit with `layout_baseline.json`; tag the next `pdf-layout-baseline-2026-11-16d`-style tag; update the 3 tag references in `PDF_LAYOUT_GUARDRAILS.md`. Push only when asked.
