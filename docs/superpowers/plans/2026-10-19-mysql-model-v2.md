# MySQL Data Model Redesign (v2) + SQLite Removal — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
> On approval, copy this file to `docs/superpowers/plans/2026-10-19-mysql-model-v2.md` and commit it.

**Goal:** Replace the organically-grown `mis_reports` MySQL schema with a normalised, typed, integrity-checked `mis_reports_v2`. Make report generation fast, and remove every trace of SQLite. Nothing the user sees may change: screens, API JSON, PDF, xlsx and pptx must stay identical.

**Architecture:** The work runs in three movements.
1. Freeze today's behaviour as a *parity snapshot*.
2. Move all SQL behind per-domain repository modules that speak native MySQL. Page modules stop owning SQL, and request-scoped bulk loading replaces the N+1 query loops. All of this happens on the **current** schema, so the parity check proves no behaviour changed.
3. Build `mis_reports_v2` side by side, migrate with a verifying script, and switch only the repository internals. The cutover is a `.env` change; rollback is the reverse `.env` change.

**Tech Stack:** Python 3 / FastAPI, PyMySQL (existing pool in `dbengine.py`), MySQL 9.7.2 on 127.0.0.1:**3307** (`C:\mysql`), pytest, pdfplumber, openpyxl, python-pptx.

**Spec:** This conversation's requirements (no separate spec doc):
- (a) Redesign the model from scratch to data-modelling guidelines.
- (b) Make the whole application fast.
- (c) No behaviour change. The DB-access code *may* change (user confirmed).
- (d) Reduce redundancy.
- (e) Remove SQLite completely (user confirmed).
- (f) Build the new DB side by side and cut over (user confirmed).
- (g) Plan only. Nothing is executed before final deployment.

## Context — what exists today (evidence)

- **Schema size.** 71 tables, about 30 MB in total. The largest is `production_table` at 27k rows. There are only 14 FKs, all on the mines tables.
  - DDL lives in `backend/scripts/mysql_schema.sql` plus 22 `migrate_*.sql` files.
  - `db.init_db()` (`db.py:42`) holds about 75 SQLite-only `CREATE TABLE`s. It returns early under MySQL.
- **SQL is spread through the code.** About 125 modules issue SQL in sqlite dialect. `dbengine.translate_sql` (`dbengine.py:59`) rewrites it at runtime.
  - `db.py` (4,767 lines) and `main.py` (8,391 lines) hold most of it.
  - `production_table` is referenced 130 times and `techno_data` 50 times.
- **Redundancy and integrity problems found:**
  - **Five dead `*_json` tables.** These are `production_data_json`, `production_plan_json`, `stock_data_json`, `ipt_data_json` and `special_steel_json`, all frozen since 2026-06-26. Their only writer, `json_extractor_adapter.py`, calls `db.insert_*_json` functions that no longer exist.
  - **Three identical-shape tables.** `production_table`, `production_plan_table` and `mou_plan_table` all have the key `(report_month, plant_name, item_name)` and a single value. Every report reads two or three of them for the same keys.
  - **Nine one-off narrative/note tables.** These are `page3_narrative`, `key_highlights_narrative`, `secretary_review_text`, `board_note_manual_text`, `steel_sales_highlights`, `sail_sales_note_table`, `do_letter_remark_table`, `rail_prod_despatch_note` and `special_steel_phys_note`.
  - **No plant or item master.** Plant appears as `plant`, `plant_name`, `plant_code` and `from_plant` in widths 8, 16 or 32. Item spellings drift ("Crude Steel" vs "Total Crude Steel"), and lists live in Python (`constants.py:1-3`, `plant_registry.py`).
  - **Techno data is stored as JSON blobs.** `techno_data.techno_json` holds `{month:{k:v}, till_month:{k:v}}`. Most values are numeric: about 77k, of which 309 are strings and 26 are objects. Every read parses whole blobs in Python.
  - **Dates and times stored as `VARCHAR`.** Formats are mixed: UTC ISO, local ISO and `%Y-%m-%d %H:%M:%S`. `bf_benchmark_external_data.report_month` actually holds an FY.
  - **Dead code against tables that no longer exist.** It touches `techno_actuals`, `techno_param`, `techno_param_group`, `techno_plant_data` and `techno_furnace_data`, in `db.py:1728-2660`, `main.py:2978-2992` and `main.py:5676-5866`.
    - `techno_aggregates.py:69` queries `sqlite_master`, so the BF shop aggregates fail silently on MySQL (`main.py:3057`).
    - `/api/preview-plan` (`main.py:2598-2661`) swaps a temp SQLite path into extractors that don't have one.
- **Not redundant; keep:**
  - `plant_name='SAIL'` production rows are reported figures: only 19 of 318 equal the plant sum, and 18 are SAIL-only items.
  - `techno_data` `till_month` values are entered or computed with weighting, not simple sums.
  - `sail_sales_table` and `steel_sector_performance_table` JSON are raw archives of source figures.
  - `user_name` in the audit logs is a deliberate point-in-time record.
- **Performance.** From the timing log `backend/scratch_review/gen_full_partial.log`, a full 88-page export took about 450 s.
  - `/api/data` took 19.5 s, and re-building the same pages for the PDF took 20.3 s. The rest was Chromium.
  - The main database hot spots:
    - Page 4: about 3,000 per-month queries, 9.8 s (`page4.py:109-327`).
    - `report_utils.compute_item_row`: 6 calls, each on its own connection.
    - Month-by-month YTD loops (`db.py:1408-1469`, `page5_6.py:349-362`).
    - `generate_group_records` runs twice, with full-history `GROUP BY SUBSTR(...)` (`page_records.py:52-247`).
    - Per plant × month × unit `techno_data` reads with JSON re-parsing (`page_techno.py:358, 543`; `db.py:3019`).
  - Pooling already exists (`dbengine.py:244-325`). Bulk-load patterns to copy are at `page_techno.py:1243-1335` and `page_power_data.py:79`.
- **SQLite file.** `backend/mis_reports.db` is already gone; only `mis_reports.db.backup-20260712-180532` remains. `DB_ENGINE` still defaults to `sqlite` (`dbengine.py:31`). Tests build SQLite temp DBs and monkeypatch `db.connect`.

## Global Constraints

- **No user-visible change.** For every month in the parity range, these must be byte-identical (or cell- or text-identical for binary formats):
  - `/api/data` JSON
  - every standalone report endpoint
  - every xlsx, pptx and PDF export
- **Parity range:** 2024-04 … 2026-09, plus 2016-03 and 2021-03, which exercise the 10-year trend and records pages.
- **Backend only.** No frontend file changes. API routes, request and response shapes, and status codes stay exactly as they are.
- **PDF layout.** Never touch templates, CSS, `layout_config.json` or `colors_config.json`. `layout_guard.py --render 2026-08` must pass against the existing baseline with no `--accept`.
- **MySQL only.** No `import sqlite3` anywhere under `backend/` (tests included) once the work is done. No `DB_ENGINE` variable and no `DB_PATH`.
- **Native SQL.** All SQL is native MySQL with `%s` parameters, and lives **only** in `backend/repo/*.py`. `page_*.py`, `api_*.py` and `main.py` call repository functions.
- **Old DB untouched.** `mis_reports` is never altered. It stays as the rollback target until it is retired by hand at least 30 days after cutover.
- **Python and tools.** Use `backend/venv/Scripts/python.exe -m <tool>` (Device Guard blocks the `.exe` launchers).
- **Table design rules for v2:**
  - InnoDB, `utf8mb4` / `utf8mb4_0900_ai_ci`, snake_case singular-noun table names.
  - Every table has a PK; every reference is a declared FK.
  - Use `DATETIME` (stored in UTC) for instants, `DATE` for dates and `TINYINT(1)` for booleans.
  - Keep `report_month CHAR(7) 'YYYY-MM'` and `fy CHAR(7) 'YYYY-YY'` as the period keys. The app passes these strings everywhere.
  - Column names are uniform: `plant_code`, `fy`, `created_at`/`updated_at`, `created_by`/`updated_by`.

## Review Focus

1. **Int vs float in techno values.** JSON `5` and `5.0` both currently reach Python. A row-based store must hand back the same type, or formatted cells change (for example "5" becomes "5.0"). Pinned by `test_techno_roundtrip_preserves_types` (Task 6).
2. **Missing key vs explicit `null`.** In techno JSON (858 nulls) and in production, "no row" and "a row with NULL" render differently: blank vs 0 / "-". Pinned by `test_absent_vs_null_distinct` (Task 6) and by the production NULL rows in parity (Task 1).
3. **A write during a request.** A save to `/api/data` or a data-entry form while a report is being built must not serve stale cached pages afterwards. Pinned by `test_cache_invalidated_by_write` (Task 4).
4. **Spelling variants of items and plants** (`Crude Steel`/`Total Crude Steel`, `SSPs`, `CFP`, `5 Plants`, `BF#1`/`BF-1`). The migration must keep each exact stored string. The masters record the strings; they do not "clean" them. Pinned by `test_migration_preserves_every_distinct_string` (Task 6).
5. **Varchar timestamps in mixed formats moving to DATETIME.** Sorting, the "last N days" filters and displayed strings must not shift by the UTC/IST offset. Pinned by `test_timestamp_render_unchanged` (Task 6) and by the admin endpoints in parity (Task 1).

---

## The v2 model (target)

**Dimensions (new):**
- `plant(plant_code VARCHAR(8) PK, plant_name, plant_kind ENUM('integrated','special','aggregate','external'), sort_order)`. Seeded from every distinct plant string in v1: BSP DSP RSP BSL ISP ASP SSP VISL CFP SAIL SSPs …
- `item(item_id SMALLINT AUTO_INCREMENT PK, item_name VARCHAR(64) UNIQUE, uom VARCHAR(16) NULL)`. Seeded with the 152+ distinct production, plan and MoU item names, stored verbatim.
- `plant_unit(unit_id SMALLINT PK, plant_code FK, unit_code VARCHAR(32), unit_type VARCHAR(16), UNIQUE(plant_code, unit_code))`. Seeded verbatim from the units in techno, breakdown, capital repair, BF meta and major-unit records.
- `cal_month(report_month CHAR(7) PK, month_start DATE, fy CHAR(7), fy_month TINYINT, quarter TINYINT, half TINYINT)` for 1960-04 … 2040-03. This replaces the `SUBSTR` FY math.

**Facts (merged and retyped):**
- `production_monthly(report_month FK cal_month, plant_code FK, item_id FK, actual DOUBLE NULL, abp_plan DOUBLE NULL, mou_plan DOUBLE NULL)`.
  - PK `(report_month, plant_code, item_id)`, plus an index `(item_id, report_month)`.
  - Replaces `production_table`, `production_plan_table` and `mou_plan_table`.
  - Each source table needs a `has_*` flag so an absent row stays distinguishable from a NULL value: `has_actual`, `has_abp`, `has_mou` (TINYINT(1)).
- `techno_value(report_month, plant_code, unit_id FK, param_key VARCHAR(190), period ENUM('month','till_month'), num DOUBLE NULL, is_int TINYINT(1), raw JSON NULL)`.
  - PK `(report_month, plant_code, unit_id, period, param_key)`.
  - `raw` is set only for string, object or null values. Replaces `techno_data`.
  - `techno_upload(report_month, plant_code, unit_id, source_file, created_at)` keeps the per-blob metadata.
- `power_monthly`. Same as `power_data_table`, with plant and item FKs (`power_item` stays a free key, because its keys are power-OIS codes).
- `report_text(scope ENUM(...), period VARCHAR(7), block_key VARCHAR(48), plant_code NULL, item_id NULL, seq SMALLINT, text MEDIUMTEXT, updated_by, updated_at DATETIME)`.
  - Replaces the 9 narrative and note tables. Each old table maps to one `scope` value; that mapping is the repository's job.
- **Retyped, renamed and FK-ed, otherwise unchanged:**
  - `stock_monthly`, `ipt_monthly`, `special_steel_order`, `special_steel_abp`, `special_steel_grade_club`
  - `special_steel_phys_*`, `special_steel_ipt_requirement`, `item_capacity`
  - `cost_trend_*`, `rake_detention_*`, `sail_mines_monthly`
  - all `mine*` tables (already normalised)
  - `macro_indicator_monthly`, `market_price_monthly`
  - `bf_benchmark_*`. Its `report_month` column becomes `fy`.
  - `breakdown`, `capital_repair`, `major_unit_daily_record`, `ready_reckoner_page`
  - `cover_photo`, `report_cover_setting`, `rail_prod_despatch`, `pdf_item_alias`
  - `page_config`, with `page_data` changed to type `JSON`
- **Ops tables:** `user`, `allowed_email`, `otp_code`, `activity_log`, `page_visit`, `admin_notification`, `extraction_log`, `todo_job`, `daily_work_log`.
  - All timestamps become `DATETIME` UTC. Add indexes for `extraction_log(report_month)`, `activity_log(user_email, id)` and `activity_log(action, id)`.
- **Dropped:** the 5 `*_json` tables (no replacement), plus all code that references them or the nonexistent `techno_*` tables.
- **Result:** 71 tables become about 60. Redundant storage is gone, and every plant, item and unit reference is enforced by an FK.

**Table names:** the repository layer hides them, so renaming to singular nouns costs nothing extra. Do it once, here.

---

## File Structure

- **Create `backend/repo/`:**
  - `__init__.py`
  - `conn.py`: native connection helper over the existing pool. It has `cursor()` and `tx()` context managers, DictCursor rows, and a `Row` that is compatible with today's `sqlite3.Row` usage: index, key and `keys()`.
  - Domain repositories, one file each: `production.py`, `techno.py`, `stock.py`, `ipt.py`, `special_steel.py`, `cost_trend.py`, `mines.py`, `rake.py`, `capacity.py`, `breakdown.py`, `text.py`, `pages.py`, `ops.py` (users, logs, otp, todo, worklog), `misc.py` (cover, ready reckoner, bf benchmark, alias, power, macro/market, rail).
- **Create:**
  - `backend/report_context.py`: request-scoped bulk cache via `contextvars`.
  - `backend/data_version.py`: the write counter used for page-cache invalidation.
- **Create `backend/tools/`:** `parity_snapshot.py`, `parity_diff.py`, `migrate_v1_to_v2.py`, `verify_v2.py`.
- **Create `backend/scripts/v2/`:** `schema_v2.sql` (single DDL source of truth) and `seed_cal_month.sql`.
- **Modify:**
  - `db.py`: becomes a thin re-export shim of `repo.*`, keeping existing `db.get_*`/`save_*` names so callers barely change. It is deleted at the end of Task 7.
  - `dbengine.py`: MySQL-only; `translate_sql` and the sqlite branches are removed.
  - `main.py`, `page_*.py`, `api_*.py`, `report_utils.py`, `production_utils.py`, `techno_*.py`, `excel_extractors/*`: inline SQL is replaced by repository calls.
  - `tests/conftest.py`: MySQL test fixture.
  - `backup_mysql.bat`, `C:\mysql\backup.cnf`, `.env.example`.
  - Docs: `CLAUDE.md`, `docs/DATA_MODEL_AND_REPORT_PAGES.md`, `backend/docs/SETUP.md`, `MYSQL_MIGRATION_PLAN.md`.
- **Delete:**
  - `json_extractor_adapter.py`, `populate_json_schema.py`, `sync_techno_tables.py`, `cleanup_sms.py`, `view_techno.py`, `techno_json_utils.py`
  - `techno_project/migrate_key_rename.py`, `scripts/migrate_sqlite_to_mysql.py`
  - the repo-root `scheduler.py` SQLite backup
  - `mis_reports.db.backup-*`, moved off-repo to `C:\mysql\archive\`

---

### Task 1: Parity harness and frozen baseline

**Files:** Create `backend/tools/parity_snapshot.py` and `backend/tools/parity_diff.py`. Test: `backend/tests/test_parity_diff.py`.

**Interfaces:**
- Produces: `snapshot(base_url: str, months: list[str], out_dir: Path) -> None`.
  - Writes `out_dir/<month>/api_data.json`.
  - Writes `out_dir/<month>/<endpoint-slug>.json` for every GET report endpoint. The list is enumerated from `main.app.routes` where `path` starts with `/api/` and the method is GET, minus a deny-list of auth and write routes.
  - Writes `*.xlsx.json` (openpyxl: value and number_format per cell), `*.pptx.json` (text per shape) and `report.pdf.txt` (pdfplumber text per page).
- Produces: `diff(a: Path, b: Path) -> list[str]`, which returns human-readable differences, empty when the snapshots are equal. CLI exit code 1 if there are any differences.

- [ ] Write `test_diff_detects_number_change`: two dirs whose `api_data.json` differs only in `12.3` vs `12.30001` → one diff mentioning the JSON path.
- [ ] Write `test_diff_ignores_volatile_fields`: `generated_at` and timestamp headers are ignored (an explicit allow-list in `parity_diff.VOLATILE_KEYS`).
- [ ] Run `python -m pytest tests/test_parity_diff.py -v` → FAIL. Implement both modules. Run again → PASS.
- [ ] **Freeze the baseline.**
  - `mysqldump --defaults-extra-file=C:\mysql\rmg_client.cnf --single-transaction --routines mis_reports > C:\mysql\archive\mis_reports_baseline.sql`
  - Restore that dump into a new schema, `mis_reports_baseline`.
  - Run the app with `MYSQL_DB=mis_reports_baseline` and take the snapshot into `C:\mysql\archive\parity\baseline\`.
  - All later parity runs use DBs derived from this same dump, so live data entry can't cause false diffs.
- [ ] Commit `tools/parity_*.py` and the test.

### Task 2: Remove SQLite and go native MySQL (current schema)

**Files:**
- Modify: `dbengine.py`, `db.py:1-60` (`DB_PATH`, `init_db`), every `sqlite3.*` reference (≈58 in db.py, 16 in main.py, plus the api_*, auth and techno_aggregates files listed in Context), `tests/conftest.py`, the 13 SQLite-using tests, `.env.example`, `.claude/settings.json:14`, `.gitignore:14-15`.
- Delete: the dead modules listed under File Structure; `init_db`'s SQLite DDL; `cover_store.SQLITE_DDL`.
- Create: `repo/conn.py`.

**Interfaces:**
- Produces in `repo/conn.py`:
  - `cursor() -> ContextManager[Cursor]`, read-only and autocommit.
  - `tx() -> ContextManager[Cursor]`: commit on success, rollback on exception.
  - `IntegrityError`, `OperationalError` (re-exported pymysql classes).
  - `Row`: the same access semantics as `dbengine.Row` today.
- `db.connect()` stays as a deprecated alias returning a pooled connection, until Task 7 removes it.

Steps:
- [ ] Write `tests/conftest.py` fixture `mysql_db`.
  - Session scope: create schema `mis_reports_test_<pid>` from `scripts/mysql_schema.sql`, using a dedicated test user with rights only on `mis_reports_test_%`.
  - Function scope: truncate all tables. Monkeypatch env `MYSQL_DB`.
  - Port the 13 SQLite-based tests onto it, keeping their assertions unchanged.
- [ ] Run `python -m pytest tests -q`. Expect only the ported tests to fail, on missing native SQL.
- [ ] Rewrite every SQL statement in the codebase to native MySQL.
  - Replace `?`→`%s`, `ON CONFLICT … DO UPDATE` → `INSERT … AS new ON DUPLICATE KEY UPDATE`, `INSERT OR REPLACE` → `REPLACE`, `INSERT OR IGNORE` → `INSERT IGNORE`, `GLOB` → `REGEXP`, `datetime('now')` → `UTC_TIMESTAMP()`.
  - Delete `translate_sql`, the sqlite branch, `DB_ENGINE` and `DB_PATH`.
  - Replace `except sqlite3.X` with `repo.conn.X`.
- [ ] Delete the dead techno_actuals / techno_param / techno_plant_data code paths (`db.py:1728-2660` region, `main.py:2978-2992`, `main.py:5676-5866`).
  - Before deleting, check each route: if a route exists only for that path, it currently returns 500. Keep the route and return the same 500. That preserves behaviour; note it in the PR as a known-broken endpoint for a later decision.
- [ ] Fix `techno_aggregates.py:69` to use `information_schema` **only if** the parity check shows no output change. It is silently disabled today, so enabling it would change output. Otherwise delete the call (`main.py:3057-3063`) and record the decision.
- [ ] Rewrite `/api/preview-plan` to run the extractor inside `repo.conn.tx()` and roll back instead of the temp SQLite swap. Test: `test_preview_plan_writes_nothing`. Row counts in `production_plan_table` are unchanged after the call, and the response equals the baseline snapshot for one plan file in `tests/fixtures/`.
- [ ] Verify all of the following:
  - `grep -rn "sqlite" backend --include=*.py | grep -v venv` → no hits.
  - `python -m pytest tests -q` → all pass.
  - `parity_diff baseline current` → 0 differences.
  - `layout_guard.py --render 2026-08` → passes.
- [ ] Commit: `MySQL-only: remove SQLite engine, translator and dead techno paths`.

### Task 3: Repository layer (current schema, no behaviour change)

**Files:** Create `backend/repo/<domain>.py` (list above). Modify all callers. `db.py` becomes a re-export shim.

**Interfaces (the contract later tasks rely on; one representative per domain):**
- `repo.production`:
  - `values(months: Iterable[str], plants: Iterable[str] | None, items: Iterable[str] | None, measure: Literal['actual','abp','mou']) -> dict[tuple[str,str,str], float | None]`, keyed `(report_month, plant_code, item_name)`. An absent key means "no row".
  - `upsert(measure, rows: Iterable[tuple[month, plant, item, value]])`.
  - `delete(measure, month, plant, items=None)`.
- `repo.techno`:
  - `blobs(months, plants=None, units=None) -> dict[tuple[month, plant, unit], {"month":{}, "till_month":{}}]`, which returns the exact dict shape `get_techno_data` returns today.
  - `merge_upsert(month, plant, unit, blob, source_file)`.
- `repo.text`:
  - `get(scope: str, period: str, block_key: str, plant=None, item=None) -> str | None`
  - `put(scope, period, block_key, text, user, plant=None, item=None)`
- **Other domains:** each existing `db.get_*/save_*/upsert_*` keeps its name and signature, moved into its domain module. There are no new semantics.

Steps:
- [ ] For each domain: move its SQL out of `page_*.py`, `api_*.py` and `main.py` into the repository module, keeping signatures. After each domain:
  - `grep` shows no table name of that domain outside `repo/`.
  - Run the tests and `parity_diff` → 0.
- [ ] Add `tests/test_repo_boundary.py::test_no_sql_outside_repo`. It scans `backend/*.py` (excluding `repo/`, `tests/`, `scripts/`, `tools/`) for `\b(SELECT|INSERT|UPDATE|DELETE)\b.+\b(FROM|INTO|SET)\b`, and passes when nothing is found.
- [ ] Commit per domain: `repo: move <domain> SQL behind repository`.

### Task 4: Speed — bulk loading, build-once pages, indexes (current schema)

**Files:**
- Create: `report_context.py`, `data_version.py`.
- Modify: `repo/production.py`, `repo/techno.py`, `report_utils.py:190-225`, `page4.py:109-350`, `page5_6.py:349-362`, `page_at_a_glance.py:506-526, 988`, `page_records.py:52-247`, `page_best_ever.py:120`, `page_best_calendar_month.py:56`, `page_techno.py:358-410, 543-570`, `main.py` (`/api/data` handler and `_enrich_pdf_pages` around `:1482-1989`).

**Interfaces:**
- `report_context.activate(report_month: str) -> ContextManager`.
  - Inside it, `repo.production.values` and `repo.techno.blobs` are served from a single bulk load: all of `production_*` for `report_month BETWEEN <CPLY FY start> AND <month>` (all measures), and the `techno_data` for the same months.
  - Rows outside that range fall through to SQL. Range queries for history (records, trends) are memoised per call signature.
- `data_version.current() -> int` and `data_version.bump() -> None`.
  - Backed by a one-row table `data_version(id=1, n BIGINT)`, added to the v1 schema through `scripts/migrate_add_data_version.sql` and to v2 natively.
  - Every `repo.*` write function calls `bump()` inside its transaction.
- **Page cache:** `main._page_cache: dict[(month, page_number, data_version), dict]`, an in-process LRU of 512 entries.
  - `/api/data` fills it; `_enrich_pdf_pages` reads from it instead of recomputing.
  - `generate_group_records` is memoised on `(items, upto_month, data_version)`.

Steps:
- [ ] Write `tests/test_report_context.py::test_page4_query_count`. With a counting cursor wrapper, `generate_page4_rows('2026-08')` against the fixture DB issues ≤ 10 queries.
- [ ] Write `test_cache_invalidated_by_write`:
  1. Build `/api/data` for a month.
  2. Upsert one production value through `repo.production.upsert`.
  3. Rebuild and assert the new value appears.
- [ ] Write `test_bulk_equals_single`. For a fixture month, every `(plant, item)` value from the context equals the value from the old per-month function.
- [ ] Run → FAIL. Implement the context, the cache and the version counter, then rewrite the listed loops to read from the context. Keep row-building logic unchanged; only the data source changes. Run → PASS.
- [ ] Add the v1 indexes `production_table(item_name, report_month)` and `extraction_log(report_month)` via `scripts/migrate_add_perf_indexes.sql`. These are also in v2.
- [ ] Measure with `pdf.py` `_time_phase`, before and after. Targets on 2026-08:
  - `/api/data` ≤ 4 s (from 19.5 s)
  - `_enrich_pdf_pages` ≤ 1 s (from 20.3 s)
  - Page 4 ≤ 0.5 s
  
  Record the numbers in the commit message. Then run `parity_diff` → 0 and `layout_guard --render 2026-08` → pass.
- [ ] Commit: `perf: request-scoped bulk loads, build-once pages, indexes`.

### Task 5: v2 schema DDL

**Files:** Create `backend/scripts/v2/schema_v2.sql` and `seed_cal_month.sql`. Test: `tests/test_schema_v2.py`.

- [ ] Write the following tests:
  - `test_schema_v2_applies_cleanly`: apply to an empty schema, with no errors.
  - `test_every_table_has_pk`.
  - `test_plant_columns_have_fk`: every column named `plant_code`/`from_plant_code`/`to_plant_code` has an FK to `plant`. Use `information_schema.key_column_usage`.
  - `test_no_varchar_timestamps`: no column matching `%_at` or `timestamp` is VARCHAR.
- [ ] Write the DDL exactly as in "The v2 model" above, with each table's other columns carried over from v1, retyped. Add indexes for every repository `WHERE`/`ORDER BY` found in Task 3: grep the `repo/` SQL and list each in a comment above its index. Run → PASS.
- [ ] Commit: `schema v2: normalised DDL`.

### Task 6: Migration v1 → v2 with verification

**Files:** Create `backend/tools/migrate_v1_to_v2.py` and `backend/tools/verify_v2.py`. Test: `tests/test_migrate_v1_to_v2.py`, which uses a small v1 fixture loaded into the test DB.

**Interfaces:** `migrate(src_db: str, dst_db: str) -> None` (idempotent: truncate dst, then load), and `verify(src_db, dst_db) -> list[str]` (empty means OK).

- [ ] Write the following tests:
  - `test_migration_preserves_every_distinct_string`. Every distinct plant, item and unit string in v1 resolves back to itself through the v2 masters.
  - `test_production_roundtrip`. For every `(month, plant, item)` in each of the three v1 tables, the v2 value and its `has_*` flag reproduce the v1 row; absent v1 rows have `has_*=0`.
  - `test_techno_roundtrip_preserves_types`. For every `techno_data` row, `repo.techno.blobs` on v2 returns a dict `==` `json.loads(v1.techno_json)`, with `type()` equal per leaf (int stays int, float stays float).
  - `test_absent_vs_null_distinct`. A key with an explicit null survives as a null key; a missing key stays missing.
  - `test_text_roundtrip`. Each of the 9 narrative tables reads back identically through `repo.text`.
  - `test_timestamp_render_unchanged`. Each v1 VARCHAR timestamp format parses to a DATETIME. The repository formats it back into the **original string format of that column**: a per-column format map in `repo/ops.py`, plus a stored `tz_was_utc` rule per column as found in Context.
- [ ] Run → FAIL. Implement. Run → PASS.
- [ ] Have `verify_v2` also check:
  - per-table row counts (allowing for the documented merges)
  - `SUM` of every numeric column per `(month, plant)`
  - `JSON_VALID` on JSON columns
  - FK orphan count = 0
  
  Run it on `mis_reports_baseline` → `mis_reports_v2_rehearsal`: no differences.
- [ ] Commit: `migration v1→v2 with round-trip verification`.

### Task 7: Point repositories at v2

**Files:** Modify `backend/repo/*.py` (SQL only) and `backend/.env.example` (`MYSQL_DB=mis_reports_v2`). Delete the `db.py` shim and update its callers to import `repo.*` directly.

- [ ] Switch each repository module's SQL to the v2 tables, one domain at a time.
  - The production repository joins `item` and `plant` once per bulk load. `cal_month` replaces the `SUBSTR` grouping in records and trends.
  - After each domain, with the app on `MYSQL_DB=mis_reports_v2_rehearsal`: `parity_diff baseline v2` → 0.
- [ ] Run `python -m pytest tests -q`, with the fixture now built from `schema_v2.sql` → all pass.
- [ ] Run these and confirm:
  - `layout_guard.py --render 2026-08` → passes with no `--accept`.
  - The Task 4 timing targets still hold.
- [ ] Commit: `repo: switch to schema v2`.

### Task 8: Cutover runbook, ops and docs

**Files:**
- Create: `backend/docs/DB_V2_CUTOVER.md`.
- Modify: `backup_mysql.bat`, `C:\mysql\backup.cnf` (DB name), `backend/.env`, `CLAUDE.md`, `docs/DATA_MODEL_AND_REPORT_PAGES.md` (§4 rewritten for v2), `backend/docs/SETUP.md`, `MYSQL_MIGRATION_PLAN.md` (mark it superseded), `README.md`.

**Runbook (executed only at final deployment, with the user's go-ahead):**
1. Announce a freeze on data entry.
2. Back up v1 with `backup_mysql.bat`.
3. Run `CREATE DATABASE mis_reports_v2`, apply `schema_v2.sql` and `seed_cal_month.sql`, and grant `mis_app` on v2.
4. Run `migrate_v1_to_v2 mis_reports mis_reports_v2`, then `verify_v2` → 0 differences.
5. Take a fresh `parity_snapshot` on v1 and on v2 for the parity range → `parity_diff` 0.
6. Set `MYSQL_DB=mis_reports_v2` in `.env`. Uvicorn reloads; in prod, restart `start-production.bat`.
7. Smoke test:
   - `/report` for 2026-09
   - one upload preview
   - one data-entry save
   - a full PDF export
8. Make v1 read-only: `REVOKE INSERT, UPDATE, DELETE ON mis_reports.* FROM mis_app`.

**Rollback:** set `MYSQL_DB=mis_reports` and restore the grants. Any data entered on v2 after cutover is replayed from `activity_log`, or re-entered.

- [ ] Update `CLAUDE.md`:
  - "MySQL only, port 3307, `mis_reports_v2`".
  - "SQL lives only in `backend/repo/`, native MySQL `%s`". This replaces the "write sqlite-dialect SQL" rule.
  - New tables go in `scripts/v2/schema_v2.sql` plus a `scripts/v2/migrate_*.sql`.
- [ ] Commit: `docs + ops for schema v2`. Do not push; the user decides.

---

## Verification (end to end)

- `cd backend && venv/Scripts/python.exe -m pytest tests -q` → all green (includes the MySQL fixture, repo-boundary, migration round-trip and query-count tests).
- `venv/Scripts/python.exe -m tools.parity_diff C:\mysql\archive\parity\baseline C:\mysql\archive\parity\v2` → `0 differences`, exit 0.
- `venv/Scripts/python.exe layout_guard.py --render 2026-08` → passes without `--accept`.
- `grep -rni sqlite backend --include=*.py` (excluding venv) → no hits.
- Timing log for 2026-08: `/api/data` ≤ 4 s, enrichment ≤ 1 s.
- `cd frontend && npm run lint`: unchanged. No frontend files touched (`git diff --stat frontend/` is empty).

## Out of scope (noted, not done)

- **Chromium/Playwright render time** (about 91% of the export). It is not a DB problem and would need layout work under `PDF_LAYOUT_GUARDRAILS.md`.
- **Changing `page_configs` to store only user overrides.** That would change "stale override" behaviour that users rely on.
- **The `/api/*` endpoints that already fail** (dead techno_actuals paths). Task 2 lists them; they are kept failing identically, and fixing them is a separate decision.
