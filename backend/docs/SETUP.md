# Project Setup — fresh machine / fresh clone from GitHub

How to bring the SAIL MIS portal up from nothing: clone, Python, Node,
MySQL, data restore from backup, and all settings. Written for Windows
(no admin rights required, except the one optional firewall step in §7).

> **This machine's actual layout (verified 2026-09-11):** everything on
> `C:\` — repo at `C:\opr-mis1`, MySQL at `C:\mysql`. Earlier machines used
> `D:\` for one or both; adjust drive letters if you deviate.

**What is NOT in the git repo — you must bring these yourself:**

| Item | Where it lives on this machine | Why not in git |
|---|---|---|
| `backend/.env` | `C:\opr-mis1\backend\.env` | secrets (JWT, SMTP password, MySQL password) |
| Database backups `mis_reports_*.sql` | `C:\opr-mis1\Report_format\db_backup\` | data, and `Report_format/` is untracked |
| Source report archive | `C:\opr-mis1\Report_format\` | large binaries |
| MySQL server itself | `C:\mysql\` | ~1.4 GB installation (9.7.x) |

> Moving to a new machine? Copy at minimum: the newest `db_backup/*.sql`
> file and `backend/.env`. Everything else is recreated below.

---

## 1. Prerequisites

| Tool | Version used here | Install command |
|---|---|---|
| Git | any recent | usually already present; else `winget install --id Git.Git -e` |
| Python | **3.11.9** (pin this — the app is tested against 3.11, not whatever `python` resolves to on a fresh Windows box, e.g. the Store stub) | `winget install --id Python.Python.3.11 -e` |
| Node.js | v20.9+ (v24 verified working) | `winget install --id OpenJS.NodeJS.LTS -e` |
| Tesseract OCR | 5.4.x — only needed for ISP Special Steel **image** extraction (`pytesseract`); everything else works without it | `winget install --id UB-Mannheim.TesseractOCR -e` |
| MS Visual C++ Redistributable (x64) | required by MySQL 9.x's `mysqld.exe` on Windows — without it mysqld exits immediately with code `-1073741515` (`STATUS_DLL_NOT_FOUND`) | `winget install --id Microsoft.VCRedist.2015+.x64 -e` |

After installing Python 3.11 alongside any other Python, use the `py -3.11`
launcher (not bare `python`) to make sure the venv is built with the right
version:

```powershell
py -3.11 --version   # should print Python 3.11.9
```

---

## 2. Clone and install dependencies

```powershell
git clone https://github.com/sanjay493/opr-mis1.git C:\opr-mis1

# Backend
cd C:\opr-mis1\backend
py -3.11 -m venv venv
venv\Scripts\pip install -r requirements.txt
venv\Scripts\pip install pymysql          # not yet in requirements.txt

# PDF export (page_*_export.py, pdf.py) uses Playwright + headless Chromium,
# NOT WeasyPrint — no GTK3 runtime is needed.
venv\Scripts\playwright install chromium

# Frontend (Node 20.9+, required by Next.js 16)
cd C:\opr-mis1\frontend
npm install
```

`npm install` prints an `npm warn install-scripts` note about `sharp` and
`unrs-resolver` postinstall scripts being skipped (npm's default script
allowlist). This is fine for `npm run dev`; if `next build`'s image
optimization misbehaves later, run `npm install-scripts approve sharp` and
reinstall.

## 3. Install MySQL (ZIP, no admin needed)

This machine previously ran MySQL 9.7.1 on `C:\mysql`, port **3307**
(not the 3306 default — kept as-is here for continuity with the restored
`.env`/backup tooling). The instructions below use the current patch,
9.7.2 LTS; any 9.7.x is a drop-in.

```powershell
# 1. Download and extract (no installer/admin needed)
Invoke-WebRequest "https://cdn.mysql.com/Downloads/MySQL-9.7/mysql-9.7.2-winx64.zip" -OutFile C:\mysql\mysql-9.7.2-winx64.zip
Expand-Archive C:\mysql\mysql-9.7.2-winx64.zip -DestinationPath C:\mysql
```

Create `C:\mysql\my.ini` with exactly this content:
```ini
[mysqld]
basedir=C:/mysql/mysql-9.7.2-winx64
datadir=C:/mysql/data
port=3307
bind-address=127.0.0.1
character-set-server=utf8mb4
collation-server=utf8mb4_0900_ai_ci
innodb_buffer_pool_size=256M
max_connections=100
log-error=C:/mysql/data/mysql-error.log

[client]
port=3307
default-character-set=utf8mb4
```

Two settings here are load-bearing — do not change them:
- `collation-server=utf8mb4_0900_ai_ci` — the app's queries rely on
  case-insensitive matching (the v2 schema declares its own
  per-column collations; see the header of `backend/scripts/v2/schema_v2.sql`).
- `bind-address=127.0.0.1` — the DB is reached only by the backend on the
  same machine; LAN users go through the Next.js proxy, never the DB.

```powershell
# 2. Initialize the data directory (creates root with NO password - fixed next step)
C:\mysql\mysql-9.7.2-winx64\bin\mysqld.exe --defaults-file=C:\mysql\my.ini --initialize-insecure --console

# 3. Start the server (hidden, detached)
powershell -Command "Start-Process -WindowStyle Hidden -FilePath 'C:\mysql\mysql-9.7.2-winx64\bin\mysqld.exe' -ArgumentList '--defaults-file=C:\mysql\my.ini'"

# 4. Secure root + create the app database and user
#    (pick a strong password; you will put the SAME app password in backend/.env)
C:\mysql\mysql-9.7.2-winx64\bin\mysql.exe -u root --host=127.0.0.1 --port=3307
```
```sql
ALTER USER 'root'@'localhost' IDENTIFIED BY '<your-root-password>';
CREATE DATABASE mis_reports_v2 CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci;
CREATE USER 'mis_app'@'localhost' IDENTIFIED BY '<your-app-password>';
CREATE USER 'mis_app'@'127.0.0.1' IDENTIFIED BY '<your-app-password>';
-- ALL on the database includes CREATE TEMPORARY TABLES, which /api/preview-plan needs.
GRANT ALL PRIVILEGES ON mis_reports_v2.* TO 'mis_app'@'localhost';
GRANT ALL PRIVILEGES ON mis_reports_v2.* TO 'mis_app'@'127.0.0.1';
-- RELOAD + PROCESS are global privileges mysqldump needs for its FLUSH TABLES
-- step (backup_mysql.bat fails with "Access denied ... RELOAD or FLUSH_TABLES"
-- without these - the database-scoped GRANT ALL above does not cover them).
GRANT RELOAD, PROCESS ON *.* TO 'mis_app'@'localhost';
GRANT RELOAD, PROCESS ON *.* TO 'mis_app'@'127.0.0.1';
FLUSH PRIVILEGES;
```

## 4. Create the schema, then load data

The database is empty after step 3. Apply the v2 schema and the month calendar (root,
from `C:\opr-mis1ackend`; the `mysql` client reads the files with `<`, so use `cmd`):

```powershell
$M = 'C:\mysql\mysql-9.7.2-winx64in'
cmd /c "`"$M\mysql.exe`" -u root --host=127.0.0.1 --port=3307 -p --default-character-set=utf8mb4 mis_reports_v2 < scripts2\schema_v2.sql"
cmd /c "`"$M\mysql.exe`" -u root --host=127.0.0.1 --port=3307 -p --default-character-set=utf8mb4 mis_reports_v2 < scripts2\seed_cal_month.sql"
```

Check it: 62 tables and 960 months (1960-04 to 2040-03):

```powershell
& "$M\mysql.exe" -u root --host=127.0.0.1 --port=3307 -p -e "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='mis_reports_v2'; SELECT COUNT(*), MIN(report_month), MAX(report_month) FROM mis_reports_v2.cal_month"
```

**Restoring data from a backup.** The daily backup (`mis_reports_v2_YYYY-MM-DD.sql`, written by
`backup_mysql.bat`) and the admin-triggered backup (Admin > Backup & Restore) are complete
dumps (schema, data, triggers). To restore one into an empty database, skip the schema step above
and import it directly:

```powershell
cmd /c "`"$M\mysql.exe`" -u root --host=127.0.0.1 --port=3307 -p mis_reports_v2 < path	o\mis_reports_v2_YYYY-MM-DD.sql"
```

A dump made before the v2 cutover (`mis_reports_YYYY-MM-DD.sql`) is a v1 dump: it cannot be
imported as v2. Load it into a scratch database and migrate it with
`python -m tools.migrate_v1_to_v2`, as described in `DB_V2_CUTOVER.md`.

Restoring over a live database bypasses the app's write counter: afterwards run
`UPDATE data_version SET n = n + 1` (or restart the backend), otherwise cached pages go stale.

**Without any backup**, the app starts on the empty schema and fills as users upload and enter data.

## 5. Configure backend/.env

Copy `backend\.env.example` to `backend\.env` and fill every key:

```ini
SMTP_EMAIL=<gmail address used to send OTP mails>
SMTP_APP_PASSWORD=<gmail app password>
JWT_SECRET=<64-char random hex; generate: python -c "import secrets; print(secrets.token_hex(32))">
FIRST_ADMIN_EMAIL=<admin's login email>

MYSQL_HOST=127.0.0.1
MYSQL_PORT=3307
MYSQL_DB=mis_reports_v2
MYSQL_USER=mis_app
MYSQL_PASSWORD=<the password you set in step 3.4>
# Folder holding mysqldump.exe/mysql.exe, for the admin Backup & Restore
# page (Admin > Backup & Restore). Update this whenever MySQL is
# reinstalled/moved on this machine - no code change needed.
MYSQL_BIN_DIR=C:/mysql/mysql-9.7.2-winx64/bin
```

Notes:
- **If you reuse an OLD machine's `.env`, users keep their logins.** With a
  NEW `JWT_SECRET`, all existing sessions become invalid (users just log in
  again — passwords still work since hashes live in the DB). This machine's
  setup reused the prior `.env` verbatim except `MYSQL_BIN_DIR`'s version
  number, so logins and the MySQL app password carried over unchanged.
- MySQL is the only engine; there is no `DB_ENGINE` or SQLite fallback. The backend reads
  `MYSQL_*` from this file; `backup_mysql.bat` reads `MYSQL_DB` and `MYSQL_BIN_DIR` from it too.
- The pytest suite needs a second MySQL user, `MYSQL_TEST_USER` / `MYSQL_TEST_PASSWORD`, with rights
  only on the `mis_reports_test_%` schemas (see `DB_V2_CUTOVER.md`, Notes).

## 6. Ops scripts — MySQL auto-start and daily backup

```powershell
# copy the two ops scripts out of the repo to C:\mysql\
copy C:\opr-mis1\backend\scripts\start_mysql.bat  C:\mysql\
copy C:\opr-mis1\backend\scripts\backup_mysql.bat C:\mysql\

# credentials file used by the backup (never on a command line):
#   C:\mysql\backup.cnf
```
```ini
[client]
user=mis_app
password=<the password from step 3.4>
host=127.0.0.1
port=3307
```
```powershell
# start MySQL at every Windows logon (also refreshes that day's backup):
Copy-Item 'C:\mysql\start_mysql.bat' ([Environment]::GetFolderPath('Startup') + '\start_mysql_mis.bat')

# daily 13:00 backup task:
schtasks /Create /F /SC DAILY /ST 13:00 /TN "MIS_MySQL_Daily_Backup" /TR "C:\mysql\backup_mysql.bat"
```

> These two steps register machine-persistent auto-run behaviour (Startup
> folder + Task Scheduler) — run them yourself from an interactive
> PowerShell window; they are intentionally NOT something an automated
> setup script/agent should do unattended.

Backups land in `C:\opr-mis1\Report_format\db_backup\<database>_YYYY-MM-DD.sql`
(`mis_reports_v2_YYYY-MM-DD.sql` for the v2 database; the name follows `MYSQL_DB`),
14-day retention. Same-day runs overwrite, so overlapping triggers are fine.

`backup_mysql.bat` fails loudly: it dumps to a temp file and only replaces
today's backup once the dump passes sanity checks (mysqldump exit code,
minimum size, completion footer) — a bad run never overwrites a good backup.
On failure it exits non-zero, logs to `C:\mysql\backup_error.log`, and pops
a Windows notification balloon.

## 7. Run the app

```powershell
# Backend (port 8082, loopback only - correct; LAN goes via the Next proxy)
cd C:\opr-mis1\backend
venv\Scripts\python -m uvicorn main:app --host 127.0.0.1 --port 8082

# Frontend - development
cd C:\opr-mis1\frontend
npm run dev            # http://localhost:3000 and http://<your-ip>:3000

# Frontend - production
npm run build
npm start
```

Or use the repo's one-shot scripts from `C:\opr-mis1\`:
`start-development.bat` (dev, auto-reload, opens two windows) or
`start-production.bat` (production, port 80).

All browser API calls are relative `/api/*` and are proxied by
`next.config.mjs` to `127.0.0.1:8082` — so the ONLY port other machines
need is 3000 (or 80 in production). One-time firewall rule (admin
PowerShell — not run as part of this setup; run it yourself if you need
LAN access):

```powershell
New-NetFirewallRule -DisplayName "SAIL MIS Frontend (3000)" -Direction Inbound -Action Allow -Protocol TCP -LocalPort 3000 -Profile Any
```

## 8. Smoke test (verified on this machine 2026-09-11)

1. `http://127.0.0.1:8082/api/production-fys` → JSON list of FYs (2000-01
   through 2026-27 on this restore). ✅
2. `http://127.0.0.1:8082/docs` → FastAPI Swagger UI, HTTP 200. ✅
3. `http://localhost:3000` → Next.js dev server responds HTTP 200. ✅
4. Log in, Reports → pick a month → all pages render. *(verify manually —
   needs a browser session)*
5. `dir C:\opr-mis1\Report_format\db_backup` → today's `.sql` exists after
   a logon or 13:00, once step 6's automation is set up.

## 9. Troubleshooting

| Symptom | Cause / fix |
|---|---|
| `mysqld.exe` exits immediately, code `-1073741515` | Missing VC++ runtime — install `Microsoft.VCRedist.2015+.x64` (see §1) |
| API 500s with `Can't connect to MySQL server on '127.0.0.1'` | mysqld not running → run `C:\mysql\start_mysql.bat`; check `C:\mysql\data\mysql-error.log` |
| mysqld won't start, stale `.pid` mentioned | delete `C:\mysql\data\*.pid`, start again (script does this automatically) |
| Login broken / "Not logged in" on every action | `JWT_SECRET` missing or changed in `.env`; cookie sessions died — log in again |
| Everything broken after a bad migration/experiment | restore the newest good dump into a fresh database (section 4), point `MYSQL_DB` at it and restart the backend |
| Need yesterday's data | `mysql -u root -p mis_reports_v2 < db_backup\mis_reports_v2_<date>.sql` (replaces ALL current data with that day's) |
| `venv\Scripts\pip install --upgrade pip` errors "please run ... -m pip install" | Harmless — Windows won't let pip replace its own running `pip.exe`; use `venv\Scripts\python.exe -m pip install --upgrade pip` instead, or just skip it |
| `npm install` warns about `sharp`/`unrs-resolver` install scripts skipped | Harmless for `npm run dev`; run `npm install-scripts approve sharp` then reinstall if `next build` image optimization fails |
| Notification balloon "MIS Backup Failed" appears, or Task Scheduler shows a non-zero `Last Result` for `MIS_MySQL_Daily_Backup` | check `C:\mysql\backup_error.log` for the reason (mysqld down, bad credentials in `backup.cnf`, truncated dump); today's `db_backup\*.sql` still holds the last known-good backup — nothing was overwritten |
| Today's `db_backup\*.sql` is missing/stale after a failure | expected — the failed dump was discarded, not written over the last good one; fix the cause in `backup_error.log`, then rerun `C:\mysql\backup_mysql.bat` (or wait for the next trigger) |
