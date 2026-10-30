# Changing the MySQL data model (v2)

How to add or change a table, column or index in the live database `mis_reports_v2`, from the
first edit to the release. Read this before any change that touches `backend/repo/` or
`backend/scripts/v2/`.

The cutover from v1 is history (`DB_V2_CUTOVER.md`). Which table feeds which report page is in
`docs/DATA_MODEL_AND_REPORT_PAGES.md`.

## The rules

1. **Two schema files, always together.** `backend/scripts/v2/schema_v2.sql` is the full DDL that
   builds an empty database (the tests and a fresh machine use it). A
   `backend/scripts/v2/migrate_<what>.sql` brings the live database to the same state. A change
   in only one of them means the tests and the live database disagree.
2. **All SQL lives in `backend/repo/<module>.py`.** Native MySQL, `%s` placeholders. No `?`,
   `ON CONFLICT` or `INSERT OR REPLACE`. Upserts are
   `INSERT ... AS new ON DUPLICATE KEY UPDATE col = new.col`. Routes, page modules and extractors
   call repo functions; they never hold SQL (`tests/test_repo_boundary.py`).
3. **Every repo write bumps `data_version` first**, on the same cursor and before the first
   write: `_ver.bump(cur)` (`from repo import version as _ver`). The page cache is keyed on it
   (`tests/test_repo_writes_bump.py`).
4. **Do not use the v1 files.** `backend/scripts/*.sql` outside `v2/`, `mysql_schema.sql` and
   `backfill_*.py` are v1 history. Never run them against `mis_reports_v2`.
5. **Back up before touching the live database**, and never paste a password into a command.
   Use the option files `C:\mysql\rmg_client.cnf` (root) and `C:\mysql\backup.cnf` (`mis_app`).

## Shell setup used below

```powershell
$M    = 'C:\mysql\mysql-9.7.2-winx64\bin'
$ROOT = '--defaults-extra-file=C:\mysql\rmg_client.cnf'   # must be the FIRST mysql argument
$PY   = 'C:\opr-mis1\backend\venv\Scripts\python.exe'
cd C:\opr-mis1\backend
```

The `mysql` client reads files with `<`, which PowerShell does not support, so those lines go
through `cmd /c`.

## Step 1. Plan the change

Write down, before editing anything:

- **What changes**: new table / new column / changed type / new index / dropped column.
- **Who reads and writes it**: which `repo/<module>.py` functions, which API routes, which
  report pages (`DATA_MODEL_AND_REPORT_PAGES.md`), which extractors and entry forms.
- **Existing rows**: does the change need a default or a backfill for data already there?
- **Destructive?** Dropping or narrowing a column loses data. Prefer adding a new column, moving
  the data, and dropping the old one in a later release once nothing reads it.

Follow the conventions in the header of `schema_v2.sql`:

- InnoDB, `utf8mb4` / `utf8mb4_0900_ai_ci`, snake_case singular table names.
- Every table has a primary key. Every plant / item / unit / month reference is a declared foreign
  key (`plant_code` to `plant`, `report_month` CHAR(7) `'YYYY-MM'` to `cal_month`, ...).
- `fy` is CHAR(7) `'YYYY-YY'` with no FK. Booleans are TINYINT(1), dates DATE, instants DATETIME
  (DATETIME(6) where microseconds are kept). No VARCHAR timestamps
  (`test_no_varchar_timestamps`).
- Columns are named `plant_code`, `fy`, `created_at` / `updated_at`, `created_by` / `updated_by`.
- An index states the repo function it serves in a comment (`-- repo.ipt.routes`).

## Step 2. Work on a branch

```powershell
git -C C:\opr-mis1 switch -c model-<what>
```

The dev server reloads on every saved file and runs against the live database, so the live
database must not be changed until Step 7. Code that needs the new column before it exists will
fail on the running app; keep the dev server stopped, or write the code so it works both before
and after the migration, until then.

## Step 3. Edit `schema_v2.sql`

Add or change the `CREATE TABLE` in `backend/scripts/v2/schema_v2.sql`, at the spot where related
tables live, with a short comment on what the table holds.

A **new table** must also be known to the table-map test: `tests/test_schema_v2.py`
`test_every_v1_table_is_mapped` fails on a v2 table that no v1 table maps to. Add the new name to
`NEW_DIMENSIONS` in that file (the set of v2-only tables). Do not touch the `V1-TABLE-MAP` block;
it records the v1 migration.

The table count quoted in `SETUP.md` section 4 and `DB_V2_CUTOVER.md` Step 3 ("64 tables")
changes too; update both numbers.

## Step 4. Write the migration for the live database

Create `backend/scripts/v2/migrate_<what>.sql` with a header comment saying what it does, the
date, and that it was applied to `mis_reports_v2`. An example (a made-up column on a real
table):

```sql
-- migrate_add_rake_remarks.sql -- 2026-11-02
-- Adds rake_detention_monthly.remarks (free text from the rake PDF). Applied to mis_reports_v2.
-- schema_v2.sql has the same column. Run once.
ALTER TABLE rake_detention_monthly
  ADD COLUMN remarks VARCHAR(255) NULL AFTER value_hours;
```

- MySQL has `CREATE TABLE IF NOT EXISTS` but not `ADD COLUMN IF NOT EXISTS` or
  `CREATE INDEX IF NOT EXISTS`. A migration is run once; check `information_schema.columns`
  before running it a second time.
- A new NOT NULL column on a table with rows needs a `DEFAULT`, or add it NULL, backfill with an
  `UPDATE`, then `MODIFY` it to NOT NULL.
- A backfill `UPDATE` / `INSERT` in a migration bypasses the app, so end the file with
  `UPDATE data_version SET n = n + 1;` (otherwise cached pages go stale).
- New foreign keys must match the referenced column type exactly (`plant_code VARCHAR(8)`,
  `report_month CHAR(7)`).

## Step 5. Change the repo layer and the callers

1. **Repo functions** go in the matching `backend/repo/<module>.py` (`ipt`, `rake`, `mines`,
   `production`, `techno`, ...). Follow the module's own pattern, for example
   `repo/ipt.py:save_ipt_entry`: check the key widths and plant/month with `_keys`, open the
   connection, `_ver.bump(cur)` before the first write, `%s` placeholders, commit, close.
   Reads take a `cur` (or use `rc.cursor()`) and return plain rows or dicts.
2. **Frozen API test.** `tests/test_repo_oracle.py`
   `test_modules_keep_the_v1_public_functions_and_signatures` checks that each repo module has
   exactly the public functions and signatures of the frozen v1 copy in `tests/_v1_frozen/`.
   - Changing the signature of an existing public function fails it by design. Add a new
     function instead, and move callers over.
   - A new public function fails it too, because the set must match exactly. The first time a
     module gains a new public function, relax that assertion to
     `assert set(ro.public_functions(v1)) <= set(ro.public_functions(v2)), module`
     (existing functions stay frozen, new ones are allowed) and say so in the commit. Never edit
     `tests/_v1_frozen/`.
   - A new public function that **writes** must be listed in `WRITE_FUNCTIONS` in
     `backend/tools/repo_oracle.py` (`test_write_functions_match_the_bump_tests_write_detection`
     checks the list). Reads are classified automatically.
   - Helpers used only inside the module should start with `_`; none of the above applies to
     them.
3. **Callers**: API routes (`main.py`, `api_*.py`), page modules (`page_*.py`), extractors
   (`excel_extractors/`), techno code. They call the repo function; they never build SQL.
4. **Frontend**: entry forms (`frontend/src/components/entry/<slug>/Form.js`) and report views
   (`frontend/src/components/reports/<slug>/View.js`) when a field is shown or entered.
5. **PDF pages**: if a report page changes, follow `PDF_LAYOUT_GUARDRAILS.md` (render check with
   `python layout_guard.py --render YYYY-MM`).

## Step 6. Test

Tests build a throwaway database from `schema_v2.sql` (user `mis_test`, databases named
`mis_reports_test_*`); they never touch `mis_reports_v2`.

```powershell
# the schema and the guard tests (fast, run every time)
& $PY -m pytest tests/test_schema_v2.py tests/test_repo_boundary.py tests/test_repo_writes_bump.py tests/test_repo_oracle.py tests/test_no_unbound_local_imports.py -q
# the repo layer and the module you changed
& $PY -m pytest tests/test_repo_*.py tests/test_data_version.py tests/test_report_context.py -q
# the rest (long; see DB_V2_CUTOVER.md "Running the tests" for the split)
& $PY -m pytest tests -q
```

Add a test for the new repo function: write a row, read it back, and check `data_version` moved.
Five tests also fail on an untouched `main` (the known baseline set); any other failure is a
regression.

An interrupted test run can leave `mis_reports_test_*` databases behind. Drop them as root when
no tests are running (each DROP takes about 25 seconds).

## Step 7. Apply to the live database

1. Stop data entry for a few minutes (tell the users), or pick a quiet time.
2. **Back up**: `C:\opr-mis1\backend\scripts\backup_mysql.bat`, or Admin > Backup & Restore.
   Check that a new `mis_reports_v2_*.sql` is in `C:\opr-mis1\Report_format\db_backup\`.
3. Run the migration:
   ```powershell
   cmd /c "`"$M\mysql.exe`" $ROOT --default-character-set=utf8mb4 mis_reports_v2 < scripts\v2\migrate_<what>.sql"
   ```
4. Check that it took:
   ```powershell
   & "$M\mysql.exe" $ROOT -e "SHOW CREATE TABLE mis_reports_v2.<table>\G"
   ```
5. **Check that the live database matches `schema_v2.sql`**: build a fresh copy from the file and
   compare the table definitions.
   ```powershell
   & "$M\mysql.exe" $ROOT -e "CREATE DATABASE mis_reports_schemacheck CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci"
   cmd /c "`"$M\mysql.exe`" $ROOT --default-character-set=utf8mb4 mis_reports_schemacheck < scripts\v2\schema_v2.sql"
   cmd /c "`"$M\mysqldump.exe`" $ROOT --no-data --skip-comments --compact mis_reports_v2 > %TEMP%\live.sql"
   cmd /c "`"$M\mysqldump.exe`" $ROOT --no-data --skip-comments --compact mis_reports_schemacheck > %TEMP%\file.sql"
   git diff --no-index --ignore-all-space $env:TEMP\file.sql $env:TEMP\live.sql
   & "$M\mysql.exe" $ROOT -e "DROP DATABASE mis_reports_schemacheck"
   ```
   The only differences should be `AUTO_INCREMENT=` values. Column order counts: use `AFTER`
   in the migration so it matches the file.
6. If the migration changed data, check that it ended with `UPDATE data_version SET n = n + 1`
   (or restart the backend).

If something goes wrong: stop the app, restore the Step 7.2 backup (Admin > Backup & Restore,
or `SETUP.md` section 4), fix the migration, and run it again.

## Step 8. Release

1. Start the app (or let `--reload` pick up the branch once merged) and check the pages that use
   the table: `/report` for the latest month, the entry form, and one upload preview if an
   extractor changed.
2. Update the docs: `docs/DATA_MODEL_AND_REPORT_PAGES.md` (the table and the pages it feeds),
   and this file if the procedure itself changed.
3. Commit everything in one commit: `schema_v2.sql`, `migrate_<what>.sql`, repo and caller code,
   tests, docs. Merge the branch into `main`.
4. Push only when you choose to. Every other machine must then run the same
   `migrate_<what>.sql` against its own `mis_reports_v2` right after pulling (Step 7, items 2
   to 4), before starting the app there. A machine that restores a backup made after the
   migration needs nothing more.

## Checklist

- [ ] `schema_v2.sql` changed (and `NEW_DIMENSIONS` for a new table, table count in the docs)
- [ ] `scripts/v2/migrate_<what>.sql` written, with a `data_version` bump if it changes data
- [ ] SQL only in `repo/`, `%s` placeholders, `_ver.bump(cur)` before each write
- [ ] new public write functions in `tools/repo_oracle.py` `WRITE_FUNCTIONS`; no changed signatures
- [ ] tests pass (schema, guard tests, repo, full suite apart from the known five)
- [ ] backup taken, migration applied to `mis_reports_v2`, schema compare shows no difference
- [ ] pages and forms checked in the browser; PDF layout checked if a page changed
- [ ] docs updated, one commit, migration run on every other machine after its pull

## Quick reference

| What | Where |
|---|---|
| Full DDL (empty database, tests) | `backend/scripts/v2/schema_v2.sql` + `seed_cal_month.sql` |
| Live-database changes | `backend/scripts/v2/migrate_<what>.sql` |
| SQL | `backend/repo/<module>.py` only |
| Write counter | `repo/version.py` (`bump`); `UPDATE data_version SET n = n + 1` after manual SQL |
| Startup guard | `repo/schema.py` (refuses a database without `techno_value` or with `techno_data`) |
| Guard tests | `test_repo_boundary`, `test_repo_writes_bump`, `test_repo_oracle`, `test_no_unbound_local_imports`, `test_schema_v2` |
| Backups | `backend/scripts/backup_mysql.bat` to `Report_format/db_backup/`; Admin > Backup & Restore |
| Table to page map | `docs/DATA_MODEL_AND_REPORT_PAGES.md` |
