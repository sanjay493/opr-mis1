# Project Setup — fresh machine / fresh clone from GitHub

How to bring the SAIL MIS portal up from nothing: clone, MySQL, data
restore from backup, and all settings. Written for Windows (no admin
rights required anywhere in this guide).

**What is NOT in the git repo — you must bring these yourself:**

| Item | Where it lives on the current machine | Why not in git |
|---|---|---|
| `backend/.env` | `D:\opr-mis1\backend\.env` | secrets (JWT, SMTP password, MySQL password) |
| Database backups `mis_reports_YYYY-MM-DD.sql` | `D:\opr-mis1\Report_format\db_backup\` | data, and Report_format/ is untracked |
| Legacy SQLite snapshot `mis_reports.db` | `D:\opr-mis1\backend\` | data (frozen at MySQL-cutover time; rollback only) |
| Source report archive | `D:\opr-mis1\Report_format\` | large binaries |
| MySQL server itself | `D:\mysql\` | 260 MB installation |

> Moving to a new machine? Copy at minimum: the newest `db_backup/*.sql`
> file and `backend/.env`. Everything else is recreated below.

---

## 1. Clone and install dependencies

```powershell
git clone https://github.com/sanjay493/opr-mis1.git D:\opr-mis1

# Backend (Python 3.11+)
cd D:\opr-mis1\backend
python -m venv venv
venv\Scripts\pip install -r requirements.txt
venv\Scripts\pip install pymysql     # if not yet in requirements.txt

# Frontend (Node 20.9+, required by Next.js 16)
cd D:\opr-mis1\frontend
npm install
```

## 2. Install MySQL 8.4 (ZIP, no admin needed)

```powershell
# 1. Download mysql-8.4.x-winx64.zip from https://dev.mysql.com/downloads/mysql/
#    and extract to D:\mysql\mysql-8.4.8-winx64  (adjust version in paths below)

# 2. Create D:\mysql\my.ini with exactly this content:
```
```ini
[mysqld]
basedir=D:/mysql/mysql-8.4.8-winx64
datadir=D:/mysql/data
port=3306
bind-address=127.0.0.1
character-set-server=utf8mb4
collation-server=utf8mb4_0900_ai_ci
innodb_buffer_pool_size=256M
max_connections=100
log-error=D:/mysql/data/mysql-error.log

[client]
port=3306
default-character-set=utf8mb4
```

Two settings here are load-bearing — do not change them:
- `collation-server=utf8mb4_0900_ai_ci` — the app's queries rely on
  case-insensitive matching (same behaviour SQLite had).
- `bind-address=127.0.0.1` — the DB is reached only by the backend on the
  same machine; LAN users go through the Next.js proxy, never the DB.

```powershell
# 3. Initialize the data directory (creates root with NO password - fixed next step)
D:\mysql\mysql-8.4.8-winx64\bin\mysqld.exe --defaults-file=D:\mysql\my.ini --initialize-insecure --console

# 4. Start the server (hidden, detached)
powershell -Command "Start-Process -WindowStyle Hidden -FilePath 'D:\mysql\mysql-8.4.8-winx64\bin\mysqld.exe' -ArgumentList '--defaults-file=D:\mysql\my.ini'"

# 5. Secure root + create the app database and user
#    (pick a strong password; you will put the SAME one in backend/.env)
D:\mysql\mysql-8.4.8-winx64\bin\mysql.exe -u root --host=127.0.0.1
```
```sql
ALTER USER 'root'@'localhost' IDENTIFIED BY '<your-password>';
CREATE DATABASE mis_reports CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci;
CREATE USER 'mis_app'@'localhost' IDENTIFIED BY '<your-password>';
CREATE USER 'mis_app'@'127.0.0.1' IDENTIFIED BY '<your-password>';
GRANT ALL PRIVILEGES ON mis_reports.* TO 'mis_app'@'localhost';
GRANT ALL PRIVILEGES ON mis_reports.* TO 'mis_app'@'127.0.0.1';
FLUSH PRIVILEGES;
```

## 3. Import data from a backup file

The daily backup files are complete (schema + all data + triggers), so a
fresh database needs nothing except the newest backup imported:

```powershell
D:\mysql\mysql-8.4.8-winx64\bin\mysql.exe -u root --host=127.0.0.1 -p mis_reports < "D:\opr-mis1\Report_format\db_backup\mis_reports_YYYY-MM-DD.sql"
```

Verify the import:

```powershell
D:\mysql\mysql-8.4.8-winx64\bin\mysql.exe -u root --host=127.0.0.1 -p -e "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='mis_reports'; SELECT COUNT(*) FROM mis_reports.production_table;"
# expect: 21 tables; production_table in the tens of thousands of rows
```

**If you have no backup file** (worst case): apply the empty schema with
`mysql -u root -p mis_reports < backend\scripts\mysql_schema.sql`, and/or
re-migrate from a SQLite file with
`python backend\scripts\migrate_sqlite_to_mysql.py --copy`.

## 4. Configure backend/.env

Copy `backend\.env.example` to `backend\.env` and fill every key:

```ini
SMTP_EMAIL=<gmail address used to send OTP mails>
SMTP_APP_PASSWORD=<gmail app password>
JWT_SECRET=<64-char random hex; generate: python -c "import secrets; print(secrets.token_hex(32))">
FIRST_ADMIN_EMAIL=kumarsanjay@sail.in

DB_ENGINE=mysql
MYSQL_HOST=127.0.0.1
MYSQL_PORT=3306
MYSQL_DB=mis_reports
MYSQL_USER=mis_app
MYSQL_PASSWORD=<the password you set in step 2.5>
```

Notes:
- **If you reuse the OLD machine's `.env`, users keep their logins.** With a
  NEW `JWT_SECRET`, all existing sessions become invalid (users just log in
  again — passwords still work since hashes live in the DB).
- `DB_ENGINE=sqlite` switches the whole app back to
  `backend/mis_reports.db` — that's the rollback path; no other change needed.

## 5. Auto-start and daily backups

```powershell
# copy the two ops scripts out of the repo to D:\mysql\
copy D:\opr-mis1\backend\scripts\start_mysql.bat  D:\mysql\
copy D:\opr-mis1\backend\scripts\backup_mysql.bat D:\mysql\

# credentials file used by the backup (never on a command line):
#   D:\mysql\backup.cnf
```
```ini
[client]
user=mis_app
password=<the password from step 2.5>
host=127.0.0.1
```
```powershell
# start MySQL at every Windows logon (also refreshes that day's backup):
powershell -Command "Copy-Item 'D:\mysql\start_mysql.bat' ([Environment]::GetFolderPath('Startup') + '\start_mysql_mis.bat')"

# daily 13:00 backup task:
schtasks /Create /F /SC DAILY /ST 13:00 /TN "MIS_MySQL_Daily_Backup" /TR "D:\mysql\backup_mysql.bat"
```

Backups land in `D:\opr-mis1\Report_format\db_backup\mis_reports_YYYY-MM-DD.sql`,
14-day retention. Same-day runs overwrite, so overlapping triggers are fine.

`backup_mysql.bat` fails loudly: it dumps to a temp file and only replaces
today's backup once the dump passes sanity checks (mysqldump exit code,
minimum size, completion footer) — a bad run never overwrites a good backup.
On failure it exits non-zero, logs to `D:\mysql\backup_error.log`, and pops
a Windows notification balloon.

## 6. Run the app

```powershell
# Backend (port 8082, loopback only - correct; LAN goes via the Next proxy)
cd D:\opr-mis1\backend
venv\Scripts\uvicorn main:app --host 127.0.0.1 --port 8082

# Frontend - development
cd D:\opr-mis1\frontend
npm run dev            # http://localhost:3000 and http://<your-ip>:3000

# Frontend - production
npm run build
npx next start
```

All browser API calls are relative `/api/*` and are proxied by
`next.config.mjs` to `127.0.0.1:8082` — so the ONLY port other machines
need is 3000. One-time firewall rule (admin PowerShell):

```powershell
New-NetFirewallRule -DisplayName "SAIL MIS Frontend (3000)" -Direction Inbound -Action Allow -Protocol TCP -LocalPort 3000 -Profile Any
```

## 7. Smoke test

1. `http://127.0.0.1:8082/api/production-fys` → JSON list of FYs.
2. `http://localhost:3000` → login page; log in.
3. Reports → pick a month → all 35 pages render.
4. `dir D:\opr-mis1\Report_format\db_backup` → today's `.sql` exists after
   a logon or 13:00.

## 8. Troubleshooting

| Symptom | Cause / fix |
|---|---|
| API 500s with `Can't connect to MySQL server on '127.0.0.1'` | mysqld not running → run `D:\mysql\start_mysql.bat`; check `D:\mysql\data\mysql-error.log` |
| mysqld won't start, stale `.pid` mentioned | delete `D:\mysql\data\*.pid`, start again (script does this automatically) |
| Login broken / "Not logged in" on every action | `JWT_SECRET` missing or changed in `.env`; cookie sessions died — log in again |
| Everything broken after a bad migration/experiment | set `DB_ENGINE=sqlite` in `.env`, restart backend → instantly on the pre-MySQL snapshot |
| Need yesterday's data | `mysql -u root -p mis_reports < db_backup\mis_reports_<date>.sql` (replaces ALL current data with that day's) |
| Notification balloon "MIS Backup Failed" appears, or Task Scheduler shows a non-zero `Last Result` for `MIS_MySQL_Daily_Backup` | check `D:\mysql\backup_error.log` for the reason (mysqld down, bad credentials in `backup.cnf`, truncated dump); today's `db_backup\*.sql` still holds the last known-good backup — nothing was overwritten |
| Today's `db_backup\*.sql` is missing/stale after a failure | expected — the failed dump was discarded, not written over the last good one; fix the cause in `backup_error.log`, then rerun `D:\mysql\backup_mysql.bat` (or wait for the next trigger) |
