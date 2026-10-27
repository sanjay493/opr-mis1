# Cutover to the v2 database schema (`mis_reports` to `mis_reports_v2`)

Runbook for moving the live MIS database from the old (v1) schema `mis_reports` to the
normalised v2 schema `mis_reports_v2`. The application code on branch `db-model-v2` runs
only on v2; there is no switch back to v1 inside the same code.

**Merging the branch to `main` in the live checkout `C:\opr-mis1` IS the cutover.** The v2
code cannot run on `mis_reports`, and the dev server's `--reload` picks up changed files at
once, so a merge or checkout there while the app is running breaks the live app (the new
startup check then refuses to start it on a v1 database). Everything up to Step 5 is therefore
run from the worktree (or an extract of the branch), never from `C:\opr-mis1`. The merge or
checkout happens once, at Step 6, with the servers stopped.

**Status (2026-10-28): done on the main machine.** The cutover ran on 2026-10-24, the smoke
test passed, v1 is read-only, and the scratch databases (`mis_reports_baseline`,
`mis_reports_rehearsal`, `mis_reports_v2_rehearsal`) and the `db-model-v2` worktree are gone.
`mis_reports` and `C:\mysql\archive\mis_reports_pre_v2_2026-10-24.sql` stay until the end of
the next reporting cycle. Another machine that still runs v1 follows "Other machines" at the end.
Day-to-day schema changes from now on: `MYSQL_MODEL_CHANGES.md`.

This runbook replaces `MYSQL_MIGRATION_PLAN.md` (the SQLite to MySQL move, now history).
The v2 table design is in `scripts/v2/schema_v2.sql` (header map) and
`docs/DATA_MODEL_AND_REPORT_PAGES.md` section 4.

## Machine facts used below

| Item | Value |
|---|---|
| MySQL binaries | `C:\mysql\mysql-9.7.2-winx64\bin\` (`mysql.exe`, `mysqldump.exe`) |
| Port | 3307, host 127.0.0.1 |
| Root option file | `C:\mysql\rmg_client.cnf` (user root; holds the password) |
| App option file | `C:\mysql\backup.cnf` (user `mis_app`; holds the password) |
| Python | `C:\opr-mis1\backend\venv\Scripts\python.exe`, always run as `python.exe -m <tool>` |
| Live checkout | `C:\opr-mis1` (stays on the old code until Step 6; no merge or checkout there before) |
| Branch code for Steps 2 to 5 | `C:\opr-mis1\.claude\worktrees\db-model-v2\backend` (the worktree), or a `git archive` extract of the branch; run the tools from there |
| Backups | `C:\opr-mis1\Report_format\db_backup\` |

Passwords live only in those two option files and in `backend\.env`. Never paste them into a
command line or a document. `--defaults-extra-file` must be the first mysql / mysqldump argument.

PowerShell setup used by the commands below (the `mysql` client reads files with `<`, which
PowerShell does not support, so those lines go through `cmd /c`):

```powershell
$M    = 'C:\mysql\mysql-9.7.2-winx64\bin'
$ROOT = '--defaults-extra-file=C:\mysql\rmg_client.cnf'
$APP  = '--defaults-extra-file=C:\mysql\backup.cnf'
$PY   = 'C:\opr-mis1\backend\venv\Scripts\python.exe'
# the branch code, NOT C:\opr-mis1\backend (the live checkout keeps the old code until Step 6)
$BR   = 'C:\opr-mis1\.claude\worktrees\db-model-v2'
cd $BR\backend
```

If the worktree is gone, extract the branch instead and point `$BR` at the extract (`.env` is
copied in; `backend\venv` is reused through `$PY`):

```powershell
$BR = 'C:\mysql\archive\v2code'
New-Item -ItemType Directory $BR | Out-Null
cmd /c "git -C C:\opr-mis1 archive db-model-v2 | tar -x -C $BR"
copy C:\opr-mis1\backend\.env "$BR\backend\.env"
```

## Before the day

1. Rehearse on a copy at least once: the same steps against `mis_reports_v2_rehearsal`
   (migrate from `mis_reports_baseline`, verify, parity) have passed with 0 problems.
2. The branch code must be ready: the worktree `db-model-v2` (or an extract of the branch) is
   what Steps 2 to 5 run. It is **not** merged or checked out in `C:\opr-mis1` yet; that is
   Step 6. `backend\venv` is unchanged (`requirements.txt` did not change in this work).
3. Pick the cutover date. Every parity run below pins the app's "today" to it (`--today`).
4. Check disk space: a v1 dump, the v2 database, a v2 copy and two snapshots.

## Step 1. Freeze data entry

Tell the users that data entry, uploads and the admin restore are frozen from now until the
smoke test passes (about 2 to 4 hours, most of it the parity snapshots). Reads and report
downloads can continue. Nothing may write to `mis_reports` after step 2.

## Step 2. Back up v1

`backend\.env` still says `MYSQL_DB=mis_reports`, so the backup script dumps v1:

```powershell
C:\opr-mis1\backend\scripts\backup_mysql.bat
echo $LASTEXITCODE        # 0
dir C:\opr-mis1\Report_format\db_backup\mis_reports_*.sql | sort LastWriteTime | select -Last 1
```

The file is `mis_reports_YYYY-MM-DD.sql` (the script names the file after the database, so a
v2 backup of the same day will not overwrite it). Then make a second copy of it outside
`Report_format`. This is mandatory, not optional:
`copy C:\opr-mis1\Report_format\db_backup\mis_reports_YYYY-MM-DD.sql C:\mysql\archive\mis_reports_pre_v2_YYYY-MM-DD.sql`.
The daily backup prunes `Report_format` after 14 days, and this dump is the rollback copy of v1.

If the machine runs a scheduled copy of the script from `C:\mysql\backup_mysql.bat`, refresh
that copy from the repo (`copy backend\scripts\backup_mysql.bat C:\mysql\`): the new version
reads `MYSQL_DB` from `.env`.

**`C:\mysql\backup.cnf` needs no edit.** It holds only user, host and port, not a database
name. What the daily backup needs after the cutover is the grant in step 3 (the
`mis_app` privileges on `mis_reports_v2`), because `backup.cnf` logs in as `mis_app`.

## Step 3. Create v2, apply the schema, grant

```powershell
& "$M\mysql.exe" $ROOT -e "CREATE DATABASE mis_reports_v2 CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci"

cmd /c "`"$M\mysql.exe`" $ROOT --default-character-set=utf8mb4 mis_reports_v2 < $BR\backend\scripts\v2\schema_v2.sql"
cmd /c "`"$M\mysql.exe`" $ROOT --default-character-set=utf8mb4 mis_reports_v2 < $BR\backend\scripts\v2\seed_cal_month.sql"

& "$M\mysql.exe" $ROOT -e "SELECT COUNT(*) AS tables_in_v2 FROM information_schema.tables WHERE table_schema='mis_reports_v2'; SELECT COUNT(*) AS months, MIN(report_month), MAX(report_month) FROM mis_reports_v2.cal_month"
```

Expected: 62 tables (every `CREATE TABLE` in `schema_v2.sql`), 960 months from 1960-04 to 2040-03.
If the table count differs from `grep -c "^CREATE TABLE" scripts/v2/schema_v2.sql`, stop.

Grants for `mis_app` on v2 (both host forms exist on this machine, see `docs/SETUP.md`):

```powershell
& "$M\mysql.exe" $ROOT -e "GRANT ALL PRIVILEGES ON mis_reports_v2.* TO 'mis_app'@'localhost'; GRANT ALL PRIVILEGES ON mis_reports_v2.* TO 'mis_app'@'127.0.0.1'; FLUSH PRIVILEGES"
& "$M\mysql.exe" $ROOT -e "SHOW GRANTS FOR 'mis_app'@'127.0.0.1'; SHOW GRANTS FOR 'mis_app'@'localhost'"
```

- `ALL PRIVILEGES` on the database already includes **CREATE TEMPORARY TABLES**, which
  `/api/preview-plan` needs (it builds temp tables for its dry run). If you grant a narrower set
  instead, it must include at least SELECT, INSERT, UPDATE, DELETE, CREATE TEMPORARY TABLES,
  LOCK TABLES (mysqldump) and REFERENCES.
- The global `RELOAD, PROCESS ON *.*` grant that `mysqldump` needs is already in place
  (`SETUP.md` section 3) and applies to every database; check that it shows in `SHOW GRANTS`.
- Do not touch the grants on `mis_reports` yet (step 8).

## Step 4. Migrate and verify

Run from `$BR\backend` (the setup above). Both tools read v1 read-only and take their
connection from the option file. A first run needs no flag: `migrate_v1_to_v2` refuses a
destination whose data tables already hold rows. A deliberate re-run on a non-live database
(a rehearsal copy) adds `--replace`; never use `--replace` on `mis_reports_v2` once the app has
written to it.

```powershell
& $PY -m tools.migrate_v1_to_v2 --src mis_reports --dst mis_reports_v2 --src-defaults-file C:/mysql/backup.cnf --dst-defaults-file C:/mysql/backup.cnf
& $PY -m tools.verify_v2        --src mis_reports --dst mis_reports_v2 --src-defaults-file C:/mysql/backup.cnf --dst-defaults-file C:/mysql/backup.cnf
```

- `migrate_v1_to_v2` reads and converts all of v1 first and writes nothing if any value cannot
  be carried exactly; it then empties the v2 tables (except `cal_month`) and loads everything in
  one transaction. After a failure that wrote nothing, fix the cause and run it again without a
  flag; a failure during the load ("has been emptied") leaves the tables empty, so that needs no
  flag either. `--replace` is only for a destination that holds data.
- `verify_v2` must end with `verify mis_reports -> mis_reports_v2: 0 problem(s)` and exit 0.
  Any problem line: stop and do not continue; v1 is untouched.
- `--help` lists the flags (`--src`, `--dst`, `--src-defaults-file`, `--dst-defaults-file`, and `--replace` on migrate).

## Step 5. Parity

Goal: the app on v2 shows what it showed on v1 for the same data. Run from `$BR\backend`. The snapshot tool refuses the
live names (`mis_reports`, `mis_reports_v2`), and the branch code cannot read v1, so the two sides
come from copies and from the frozen v1 code.

### 5a. v2 side

```powershell
& "$M\mysql.exe" $ROOT -e "CREATE DATABASE mis_reports_v2_cutover CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci; GRANT ALL PRIVILEGES ON mis_reports_v2_cutover.* TO 'mis_app'@'localhost'; GRANT ALL PRIVILEGES ON mis_reports_v2_cutover.* TO 'mis_app'@'127.0.0.1'; FLUSH PRIVILEGES"
cmd /c "`"$M\mysqldump.exe`" $ROOT --single-transaction --routines --triggers mis_reports_v2 | `"$M\mysql.exe`" $ROOT mis_reports_v2_cutover"
```

Snapshot it (the cutover date as `--today`; widen `--months` if v1 holds months after 2026-09).
Run in 2-month chunks into the same `--out`, because Chromium can run out of memory in a long
run; if a month crashes ("Target crashed"), re-run that month alone:

```powershell
$D = '2026-MM-DD'     # the cutover date
$env:MYSQL_DB = 'mis_reports_v2_cutover'
& $PY -m tools.parity_snapshot --db mis_reports_v2_cutover --out C:\mysql\archive\parity\cut_v2 --today $D --months "2024-04..2024-05,2016-03,2021-03"
# ... then 2024-06..2024-07, and so on up to the latest month
```

`--pdf-months` defaults to `2026-08,2026-09`; add the newest month if it is later.

### 5b. v1 side

The frozen v1 code is commit `5574414` (the last commit before the v2 switch-over), extracted
without git history. `5574414` is the branch's frozen v1-SQL code, not the pre-branch release,
and task 7g2 tied it to the baseline, so it is the v1 reference for this parity run:

```powershell
$V1 = 'C:\mysql\archive\parity\v1code'
if (-not (Test-Path $V1)) { New-Item -ItemType Directory $V1 | Out-Null; cmd /c "git -C C:\opr-mis1 archive 5574414 | tar -x -C $V1" }
copy C:\opr-mis1\backend\.env "$V1\backend\.env"
```

(`C:\mysql\archive\parity\v1code` already exists from the rehearsal; reuse it.) Restore the
step-2 dump into a scratch database and snapshot that with the v1 code:

```powershell
& "$M\mysql.exe" $ROOT -e "CREATE DATABASE mis_reports_cutover_v1 CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci; GRANT ALL PRIVILEGES ON mis_reports_cutover_v1.* TO 'mis_app'@'localhost'; GRANT ALL PRIVILEGES ON mis_reports_cutover_v1.* TO 'mis_app'@'127.0.0.1'; FLUSH PRIVILEGES"
cmd /c "`"$M\mysql.exe`" $ROOT --default-character-set=utf8mb4 mis_reports_cutover_v1 < C:\opr-mis1\Report_format\db_backup\mis_reports_YYYY-MM-DD.sql"
cd $V1\backend
$env:MYSQL_DB = 'mis_reports_cutover_v1'
& $PY -m tools.parity_snapshot --db mis_reports_cutover_v1 --out C:\mysql\archive\parity\cut_v1 --today $D --months "2024-04..2024-05,2016-03,2021-03"
# ... same chunks as 5a
cd $BR\backend
```

Use exactly the same `--months`, `--pdf-months` and chunking on both sides, otherwise
`parity_diff` reports harness-only "file only in B" lines. (The v1 copy's `.env` is the live one; the `$env:MYSQL_DB` lines above override its database.
Do not edit it for `DB_ENGINE`: the v1 code at 5574414 no longer reads that setting, it was
removed in task 2b.)

### 5c. Compare

```powershell
& $PY -m tools.parity_diff C:\mysql\archive\parity\cut_v1 C:\mysql\archive\parity\cut_v2
```

`0 differences` is the target. The **only accepted differences** are the ones in
`backend/tools/parity_exceptions.md`:

- section 1: `_global/api_production-records.json`. Second-place month labels among equal totals on
  the /records single-plant tabs (33 labels, BSP, DSP, RSP, BSL), including the derived BSL
  "New CR Sheet" `best_month`. Totals are identical; only a tied month label changes.
- section 1b: `_global/api_iron-ore-mines__series--fy_start=2026.json`, `despatch_plan` rows in another
  order (same rows).
- section 1c: row order the optimizer picked per call (`breakdown.open_breakdown_rows`; groups and
  sorts afterwards, so no visible change).

`parity_diff` stops listing at 50 lines per file, so for those two files confirm that nothing
else changed (compare the JSON with the tied label fields removed, or as a multiset for 1b).
If the data has changed since the rehearsal, regenerate the section 1 table first, as the
"Upkeep" note there says. Any other difference is a real regression: stop, do not switch.

Drop the scratch databases when done:

```powershell
& "$M\mysql.exe" $ROOT -e "DROP DATABASE mis_reports_v2_cutover; DROP DATABASE mis_reports_cutover_v1"
```

## Step 6. Switch the application to v2

1. Stop the backend and frontend (close the `start-development.bat` windows, or the
   `start-production.bat` windows in production). Check that nothing listens on 8082.
2. Only now put the branch code into `C:\opr-mis1`: merge `db-model-v2` into `main` there (or
   check the branch out). This is the cutover itself. Check:
   `git -C C:\opr-mis1 log -1 --oneline`.
3. Edit `backend\.env`: set `MYSQL_DB=mis_reports_v2`. Leave the other lines as they are,
   including `MYSQL_PORT=3307`. A leftover `DB_ENGINE=mysql` line is ignored by the v2 code and is
   needed again if you roll back, so leave it. (The v2 code defaults to `mis_reports_v2` when
   `MYSQL_DB` is unset, and refuses to start on a database that still has the v1 tables.)
4. Start: `start-development.bat` (uvicorn reloads on its own) or `start-production.bat`
   (rebuild the frontend first only if the frontend changed: `cd frontend && npm run build`).

## Step 7. Smoke test

```powershell
curl.exe -s "http://127.0.0.1:8082/api/production-fys"
curl.exe -s -o NUL -w "%{http_code} %{time_total}s\n" "http://127.0.0.1:8082/api/data?month=2026-09"
```

Then in the browser, as an admin:

1. `/report` for 2026-09: all pages render; the page count matches the last v1 report.
2. One upload preview (Uploads, pick any plant file, Preview only, do not insert): it must show rows.
   (A preview that ends in a deadlock error is rare and harmless; retry. See Notes.)
3. One data-entry save: a value you can undo, for example re-save an unchanged cell on a data-entry
   page, or enter and then delete one `todo` item. Check it appears and that `/report` reflects it.
4. A full PDF export of 2026-09 ("Download PDF"): it completes and looks like the previous month's.
5. `dir C:\opr-mis1\Report_format\db_backup` after the next daily backup (or run
   `backend\scripts\backup_mysql.bat` now): a new `mis_reports_v2_YYYY-MM-DD.sql` exists.

Announce that data entry is open again.

## Step 8. Make v1 read-only

Only after the smoke test passes:

```powershell
& "$M\mysql.exe" $ROOT -e "REVOKE INSERT, UPDATE, DELETE ON mis_reports.* FROM 'mis_app'@'localhost'; REVOKE INSERT, UPDATE, DELETE ON mis_reports.* FROM 'mis_app'@'127.0.0.1'; FLUSH PRIVILEGES"
& "$M\mysql.exe" $ROOT -e "SHOW GRANTS FOR 'mis_app'@'127.0.0.1'"
```

Keep `mis_reports` and the step-2 dump for at least one reporting cycle before dropping anything.
(`REVOKE` errors with "no such grant" if only the `ALL PRIVILEGES` form was granted on
`mis_reports`; then `REVOKE ALL PRIVILEGES ON mis_reports.* FROM ...` and
`GRANT SELECT ON mis_reports.* TO ...` for each host form.)

## Rollback

The v2 code cannot run on v1, so a rollback is "old code + old database":

1. Stop backend and frontend.
2. Put the pre-cutover code back in `C:\opr-mis1` (the release that ran before the branch was merged,
   for example by checking out that commit or tag).
3. Edit `backend\.env`: `MYSQL_DB=mis_reports` and keep `DB_ENGINE=mysql`. That is right for the
   pre-branch release: its `dbengine.py` still reads `DB_ENGINE` and defaults to `sqlite`, so
   without that line the old code would open the SQLite fallback instead of MySQL.
4. Restore v1 write access if step 8 was done:
   ```powershell
   & "$M\mysql.exe" $ROOT -e "GRANT INSERT, UPDATE, DELETE ON mis_reports.* TO 'mis_app'@'localhost'; GRANT INSERT, UPDATE, DELETE ON mis_reports.* TO 'mis_app'@'127.0.0.1'; FLUSH PRIVILEGES"
   ```
5. Start the app and run the smoke test of step 7 against v1.
6. Data entered on v2 after the cutover is not in v1. Replay it from the v2 `activity_log`
   (`SELECT * FROM mis_reports_v2.activity_log WHERE created_at >= '<cutover time>' ORDER BY id`) or
   re-enter it by hand. If nothing was entered, there is nothing to replay.
7. Leave `mis_reports_v2` in place for diagnosis; do not drop it.

## Notes

- **After a manual SQL edit** (any `UPDATE`/`INSERT`/`DELETE` or script run that bypasses the
  app), run `UPDATE data_version SET n = n + 1` on `mis_reports_v2`, or restart the backend.
  Otherwise stale cached pages are served: the page cache is keyed on `data_version.n`. An admin
  restore from the app does this itself.
- **Manual SQL edits must keep `production_monthly` unique** per (report_month, plant_code,
  item name compared case-insensitively) among `has_actual = 1` rows; `tools.verify_v2` checks it.
  Two item spellings that differ only in case, both holding an actual, would double count.
- **Preview dry run deadlock.** `/api/preview-plan` and the other dry runs hold share locks without
  bumping the version. Under concurrent saves MySQL can roll one side back with a deadlock error.
  It is rare, the preview writes nothing anyway, and a retry works.
- **`backend/scripts/` backfill scripts hold v1 SQL.** `backfill_*.py`, `migrate_*.sql` (outside
  `scripts/v2/`), `mysql_schema.sql` and the one-off scripts there are historical. Do not run them
  against v2. New writers must go through `backend/repo/`.
- **Unknown plants and spellings.** A write for a plant that is not in the master creates a
  `plant` row with `plant_kind = 'external'`, and a case-variant item or unit name creates one
  more spelling (`CC Billet` next to `CC BILLET`). This is the v1 behaviour. Filter by
  `plant_kind` (and fold case) when building display lists.
- **Real-data tests.** Four tests read live data: the rake detention PDF and report-month tests and
  the secretary-review context and render tests. `tests/conftest.py:live_v2_db_name()` picks
  `MYSQL_LIVE_V2_DB` if set, else `MYSQL_DB` when it starts with `mis_reports_v2`, else
  `mis_reports_v2`. They read it read-only. (Before the cutover they read the rehearsal copy,
  dropped on 2026-10-28.)
- **Test database.** The pytest fixtures use a separate MySQL user, `MYSQL_TEST_USER` /
  `MYSQL_TEST_PASSWORD` in `backend\.env`, with rights only on ``mis_reports_test_%`` schemas
  (``GRANT ALL ON `mis\_reports\_test\_%`.* TO 'mis_test'@'127.0.0.1'``, created as root). The
  tests never touch `mis_reports`, `mis_reports_v2` or `mis_reports_baseline`.
- **Guard tests** that protect the model: `tests/test_repo_boundary.py` (no SQL outside
  `backend/repo/`), `tests/test_repo_writes_bump.py` (every repo write bumps `data_version` first),
  `tests/test_repo_oracle.py` (public functions of each repo module keep their frozen signatures),
  `tests/test_no_unbound_local_imports.py` (the pyflakes F823 pattern). Keep them green.
- **Running the tests.** The full suite takes about 75 minutes. Run it in parts, for example:
  ```powershell
  cd $BR/backend
  # schema and migration
  & $PY -m pytest tests/test_schema_v2.py tests/test_migrate_v1_to_v2.py tests/test_verify_v2.py -q
  # repo layer and the guard tests
  & $PY -m pytest tests/test_repo_*.py tests/test_data_version.py tests/test_report_context.py tests/test_no_unbound_local_imports.py -q
  # everything else (app, extractors, board notes, pages)
  & $PY -m pytest tests -q --ignore-glob="tests/test_repo_*" --ignore=tests/test_schema_v2.py --ignore=tests/test_migrate_v1_to_v2.py --ignore=tests/test_verify_v2.py --ignore=tests/test_data_version.py --ignore=tests/test_report_context.py --ignore=tests/test_no_unbound_local_imports.py
  ```
  Five tests fail on the untouched main as well (the known baseline set); a new failure outside
  them is a regression.
- **Colour, layout and PDF rules** are unaffected by this change; see `PDF_LAYOUT_GUARDRAILS.md`.

## Other machines

`main` now holds the v2 code, so on any other machine a `git pull` is the cutover: the backend
then refuses to start on a v1 database. Stop the backend and frontend there **before** pulling,
and pick one of the two paths. `$M` / `$ROOT` are that machine's MySQL bin folder and root
option file (see "Machine facts"); the paths below assume the same layout as here.

**A. It should hold the same data as the main machine (the usual case).** No migration: restore
the newest v2 backup from the main machine.

```powershell
# 1. on the main machine: take a fresh backup and copy it across
C:\opr-mis1\backend\scripts\backup_mysql.bat        # -> Report_format\db_backup\mis_reports_v2_YYYY-MM-DD.sql
# 2. on the other machine: stop the app, then pull
git -C C:\opr-mis1 pull
# 3. create the empty v2 database, load the dump, grant
& "$M\mysql.exe" $ROOT -e "CREATE DATABASE mis_reports_v2 CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci"
cmd /c "`"$M\mysql.exe`" $ROOT mis_reports_v2 < C:\path\to\mis_reports_v2_YYYY-MM-DD.sql"
& "$M\mysql.exe" $ROOT -e "GRANT ALL PRIVILEGES ON mis_reports_v2.* TO 'mis_app'@'localhost'; GRANT ALL PRIVILEGES ON mis_reports_v2.* TO 'mis_app'@'127.0.0.1'; FLUSH PRIVILEGES"
```

If the load stops at `SET @@GLOBAL.GTID_PURGED` (a server with its own GTID history), make a
copy of the dump without that statement and load the copy:
`cmd /c "findstr /V GTID_PURGED dump.sql > dump.nogtid.sql"` (`findstr` keeps the bytes as they
are; PowerShell's `Set-Content` would add a BOM).

Then set `MYSQL_DB=mis_reports_v2` in that machine's `backend\.env`, install the pinned
requirements if they changed (CLAUDE.md, "Python"), start the app and run the Step 7 smoke test.

**B. It holds its own v1 data that must be kept.** Run this runbook there from Step 2 (dump v1,
keep a copy in `C:\mysql\archive\`), Step 3 (create v2), Step 4 (migrate with
`python -m tools.migrate_v1_to_v2 --src mis_reports --dst mis_reports_v2`, then
`python -m tools.verify_v2` with the same pair: 0 problems), then Steps 6 to 8. Because `main` is
already v2, the tools run from `C:\opr-mis1\backend` itself after the pull; no worktree is needed.
Keep the app stopped from the pull until Step 6.

**Then, on either path, clean up** (only what exists on that machine):

```powershell
& "$M\mysql.exe" $ROOT -N -e "SHOW DATABASES LIKE 'mis\_reports\_%'"
# drop scratch copies, one per statement (each DROP can take ~25 s):
& "$M\mysql.exe" $ROOT -e "DROP DATABASE IF EXISTS mis_reports_baseline"
& "$M\mysql.exe" $ROOT -e "DROP DATABASE IF EXISTS mis_reports_rehearsal"
& "$M\mysql.exe" $ROOT -e "DROP DATABASE IF EXISTS mis_reports_v2_rehearsal"
# and any mis_reports_test_* left by an interrupted pytest run (only while no tests run)
# grants survive DROP DATABASE; remove them too (for both 'localhost' and '127.0.0.1'):
& "$M\mysql.exe" $ROOT -e "REVOKE IF EXISTS ALL PRIVILEGES ON mis_reports_baseline.* FROM 'mis_app'@'127.0.0.1'"
git -C C:\opr-mis1 worktree list        # remove a leftover db-model-v2 worktree:
git -C C:\opr-mis1 worktree remove .claude\worktrees\db-model-v2
git -C C:\opr-mis1 branch -d db-model-v2
```

Keep `mis_reports` (read-only, Step 8) and the Step 2 dump for one reporting cycle. Point the
daily backup task at the repo script (`SETUP.md` section 6), not at a copy in `C:\mysql\`.
