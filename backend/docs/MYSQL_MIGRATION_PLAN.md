# MySQL Migration Plan — SAIL MIS Portal

Status: **EXECUTED July 2026.** The app now runs on MySQL 8.4.8 (LTS), ZIP
install at `D:\mysql` (no admin required), `DB_ENGINE=mysql` in backend/.env.
SQLite remains the rollback path (`DB_ENGINE=sqlite` + restart; the .db file
is a frozen snapshot from cutover time).

Operational pieces (all also copied into `backend/scripts/`):
- `D:\mysql\start_mysql.bat` — starts mysqld if not running, then refreshes
  today's backup; a copy in the user's Startup folder runs it at every logon.
- `D:\mysql\backup_mysql.bat` — mysqldump (single-transaction,
  no-tablespaces) to `Report_format/db_backup/mis_reports_YYYY-MM-DD.sql`,
  14-day retention; also runs daily at 13:00 via the
  `MIS_MySQL_Daily_Backup` scheduled task. Credentials come from
  `D:\mysql\backup.cnf` (never on the command line).
- `backend/scripts/mysql_schema.sql` — canonical schema (21 tables).
- `backend/scripts/migrate_sqlite_to_mysql.py` — copy + verification gate.
- Restore: `mysql -u root -p mis_reports < mis_reports_YYYY-MM-DD.sql`.

What the execution found beyond this plan: case-insensitive unique keys
exposed same-month duplicate rows and cross-month case/whitespace-variant
item names that had been silently splitting YTD sums under SQLite — cleaned
in the data and guarded at the insert points (see commit 0bcc962).

The original plan follows, kept for reference. All counts below were
measured from the live SQLite DB and source tree, not estimated.

---

## 1. Current state (measured inventory)

| Fact | Value |
|---|---|
| Engine | SQLite 3, single file `backend/mis_reports.db` (~7 MB) |
| Tables | 22 (incl. one obsolete: `_old_plant_units`) |
| Total rows | ~41,000 — largest: `production_table` 16.5k, `special_steel_orders` 9.7k, `extraction_log` 8k, `techno_data` 4.5k |
| Explicit indexes | **0** (only implicit PK/UNIQUE indexes) |
| `sqlite3.connect(...)` call sites | **169 across 44 files** — every module opens its own connections |
| `ON CONFLICT ... DO UPDATE` upserts | **42 across 14 files** |
| `INSERT OR REPLACE / OR IGNORE` | 4 (in `plant_registry.py`, `sync_techno_tables.py`) |
| `AUTOINCREMENT`, `PRAGMA`, `sqlite3.Row` usages | 46 across 16 files |
| Query placeholders | qmark style (`?`) throughout — several hundred queries |
| Dates | stored as TEXT: `'YYYY-MM'` (report_month), ISO strings (timestamps). String `BETWEEN`/`<=` comparisons rely on lexicographic order |
| JSON payloads | TEXT columns holding JSON (`techno_data.techno_json`, `*_json` tables, `page_configs.page_data`) |
| Booleans | INTEGER 0/1 (`barred`, `used`, `is_user_supplied`, `convert_t`, …) |

Access pattern: FastAPI (uvicorn, threaded), short-lived connection per
operation, autocommit-style commits. Low write volume (single office user +
extraction jobs), read volume dominated by report page generation.

**Honest framing:** SQLite is not the bottleneck for this workload today.
The migration's real value is concurrent multi-user writes, network-hosted
DB, standard backup/replication tooling, and future growth.

---

## 2. Target

- **MySQL 8.0+** (or MariaDB 10.6+ — everything below applies to both;
  pick MySQL 8 unless the office already standardises on MariaDB)
- Engine **InnoDB**, charset **utf8mb4**, collation **utf8mb4_0900_ai_ci**
  (case-insensitive — matches SQLite's default `LIKE` behaviour the code
  currently relies on)
- Driver: **PyMySQL** (pure Python, no build deps on Windows)
- `sql_mode` must include `STRICT_TRANS_TABLES` (default in 8.0)

---

## 3. Phase 0 — prep work in the current codebase (do this first, still on SQLite)

These changes pay off regardless of when the migration happens, and shrink
the migration diff massively:

1. **Centralise connections.** Add `db.get_conn()` (and a context-manager
   variant) in `db.py`; replace all 169 `sqlite3.connect(db.DB_PATH)` /
   `sqlite3.connect(DB_PATH)` call sites with it. Mechanical change, easy to
   verify with grep — after it, the engine swap touches ONE function.
2. **Centralise row-dict access.** The 15+ places setting
   `conn.row_factory = sqlite3.Row` should get dict rows from the factory
   (`get_conn(dict_rows=True)`), so the PyMySQL `DictCursor` swap is invisible.
3. **Kill the dead weight before migrating it:**
   - drop `_old_plant_units` (obsolete by name);
   - decide whether the four sparsely-used `*_json` snapshot tables
     (`production_data_json` 316, `production_plan_json` 12,
     `special_steel_json` 8, `stock_data_json` 17 rows) are still written by
     anything that matters, or fold/drop them;
   - the legacy `techno_rows` insert path in `/api/confirm-extraction`
     references tables that no longer exist (`techno_actuals`,
     `techno_param`) — delete that code so it doesn't get "migrated".
4. **Add the missing indexes now** (they help SQLite too):
   - `techno_data(report_month)` — page 27 fetches by month across plants
   - `production_table(plant_name, item_name)` — weight lookups
   - `extraction_log(logged_at)` — log panel reads newest-first
   - `activity_log(timestamp)`

---

## 4. Schema conversion rules

Generate MySQL DDL from `sqlite_master` with the rules below (a conversion
script is sketched in §8; hand-check every table against these):

| SQLite | MySQL | Notes |
|---|---|---|
| `INTEGER PRIMARY KEY AUTOINCREMENT` | `BIGINT PRIMARY KEY AUTO_INCREMENT` | |
| `TEXT` (key/lookup columns) | `VARCHAR(n)` | **MySQL cannot index bare TEXT.** Every PK/UNIQUE TEXT column needs an explicit length — see sizing table below |
| `TEXT` (free text / JSON payloads) | `TEXT` / `MEDIUMTEXT` / `JSON` | `techno_json`, `page_data`, `data` columns → `JSON` type (validates on write, enables `JSON_EXTRACT` later); free text (`details`, `remarks`) → `TEXT` |
| `REAL` | `DOUBLE` | Report figures; do **not** use FLOAT. `DECIMAL` unnecessary (values are measurements, not money) |
| `INTEGER` used as bool | `TINYINT(1)` | 0/1 semantics unchanged |
| `TEXT` dates (`'YYYY-MM'`, `'YYYY-MM-DD'`, ISO ts) | keep `VARCHAR`/`CHAR(7)` **in phase 1** | Lexicographic comparisons keep working. Converting to native DATE/DATETIME is a phase-2 cleanup, NOT part of the engine swap — don't couple the two |
| `DATETIME DEFAULT CURRENT_TIMESTAMP` | same | supported |
| implicit `rowid` | none | nothing in the code uses bare rowid — verified |

### VARCHAR sizing for composite keys (checked against real data)

utf8mb4 index limit is 3072 bytes = 768 chars total per index. Current
longest values in each key column leave ample slack with:

| Column family | Size |
|---|---|
| `report_month`, `stock_month`, `fy` | `CHAR(7)` |
| `plant_name`, `plant`, `unit` | `VARCHAR(32)` |
| `item_name`, `item_type`, `stock_type`, `purpose`, `role`, `priority`, `status` | `VARCHAR(64)` |
| `product`, `quality_grade`, `section`, `pdf_label` | `VARCHAR(160)` (longest grade today is ~45 chars — BSP's `TLT/MMn Grade(Billets)+(SBS-Slab)`) |
| `email` | `VARCHAR(190)` |
| widest composite PK: `special_steel_orders` (7+32+160+160+160 = 519 chars) | fits within 768 ✓ |

One semantic trap: `special_steel_orders.section` uses `''` (not NULL) as
"no section" **because it's part of the PK** — keep `NOT NULL DEFAULT ''`
in MySQL, do not "clean it up" to NULL (NULLs in unique keys don't collide
in MySQL, which would silently allow duplicate rows).

---

## 5. SQL dialect changes (the actual code diff)

1. **Placeholders:** every `?` → `%s`. This is the largest mechanical diff
   (hundreds of queries). Do it file-by-file with tests running; do NOT
   attempt a blind regex over string literals containing `?`.
2. **Upserts (42 sites):**
   ```sql
   -- SQLite
   INSERT INTO t (a,b,c) VALUES (?,?,?)
   ON CONFLICT(a,b) DO UPDATE SET c = excluded.c
   -- MySQL 8.0.19+
   INSERT INTO t (a,b,c) VALUES (%s,%s,%s) AS new
   ON DUPLICATE KEY UPDATE c = new.c
   ```
   Semantics match because every `ON CONFLICT(...)` in this codebase targets
   the table's PK/UNIQUE key — verified; none target a non-unique column set.
3. **`INSERT OR REPLACE`** (4 sites) → `REPLACE INTO` (same delete+insert
   semantics) or rewrite as ON DUPLICATE KEY UPDATE (preferred — REPLACE
   fires delete triggers and burns AUTO_INCREMENT ids).
4. **`PRAGMA table_info(...)`** (migration helpers in `db.py` use this to
   add columns idempotently) → query `information_schema.columns`.
5. **`executescript`** (if present in init paths) → split statements.
6. **`sqlite3.Row`** → `pymysql.cursors.DictCursor` (hidden behind
   `get_conn()` from Phase 0).
7. **`db.init_db()`** — currently creates tables on every call and is called
   in hot paths (e.g. once per `save_special_steel_entry`, which made the
   2,100-row backfill crawl). In MySQL, replace with a one-time schema setup
   + versioned migrations; make `init_db()` a no-op after first check.
8. **Keep an eye on:** string concatenation `||` (use `CONCAT`),
   `datetime('now')`/`strftime` in SQL (none found in queries — Python
   generates all timestamps ✓), division semantics (unchanged).

---

## 6. Configuration & connection management

- Extend `backend/.env`:
  ```
  DB_ENGINE=mysql            # or 'sqlite' — keep the fallback!
  MYSQL_HOST=127.0.0.1
  MYSQL_PORT=3306
  MYSQL_DB=mis_reports
  MYSQL_USER=mis_app
  MYSQL_PASSWORD=<generated>
  ```
- `db.get_conn()` reads `DB_ENGINE` and returns the right connection —
  **keep SQLite working behind the same interface** during the whole
  migration; it is the rollback path and keeps dev machines zero-setup.
- Connection handling: PyMySQL is not thread-safe per connection; the
  current one-connection-per-operation pattern is actually correct for it.
  Add pooling later only if profiling demands it (DBUtils `PooledDB` is a
  drop-in around `get_conn`).
- MySQL server binds to `127.0.0.1` only (same posture as the backend —
  clients reach data via the Next proxy, never the DB).
- Grants: `mis_app` gets `SELECT, INSERT, UPDATE, DELETE` on `mis_reports.*`
  only. DDL runs as a separate admin user during deploys.

---

## 7. Data migration procedure

One-shot copy script (`backend/scripts/migrate_sqlite_to_mysql.py`):

1. Stop the backend (no writers).
2. `CREATE DATABASE mis_reports CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci;`
   then apply the converted DDL.
3. For each table, in FK-free order (no FKs exist today, so any order):
   read all rows from SQLite, `executemany` into MySQL in batches of 1,000,
   one transaction per table.
4. `AUTO_INCREMENT` reseed: `ALTER TABLE t AUTO_INCREMENT = <max(id)+1>`.
5. **Verification gate (hard requirement before cutover):**
   - per-table `COUNT(*)` equality;
   - per-table checksum: sum/avg of every numeric column, min/max of every
     key column, compared between engines;
   - JSON columns: `JSON_VALID()` = 1 for every migrated row;
   - app-level: run the golden extraction tests and render pages 1–35 for
     3 sample months (one legacy, e.g. 2016-05; one mid, 2024-01; the
     current month) against MySQL and diff the JSON output against the same
     render on SQLite. This catches dialect bugs no row-count will.

At ~41k rows the copy itself takes seconds; the verification is the point.

---

## 8. Suggested execution order (each step is shippable on its own)

| Step | Content | Risk |
|---|---|---|
| 0a | `get_conn()` refactor of all 169 call sites (still SQLite) | mechanical, test after each file |
| 0b | Drop dead tables/code, add indexes | trivial |
| 1 | DDL conversion script + generated MySQL schema, reviewed by hand | none (no prod impact) |
| 2 | Dialect changes behind `DB_ENGINE` switch (`?`→`%s` via a tiny helper that rewrites at call time when engine=mysql, upserts via per-engine SQL constants) | contained |
| 3 | Migration + verification script; run against a **copy**; fix diffs | none |
| 4 | Shadow period: run MySQL locally, re-run step-3 verification weekly while normal work continues on SQLite | none |
| 5 | Cutover: stop backend → final copy+verify → flip `DB_ENGINE=mysql` → smoke test (login, one extraction preview+insert, one PDF) | rollback = flip env var back; SQLite file untouched |
| 6 | Post-cutover cleanups: native DATE columns, JSON queries, pooling | optional, unhurried |

---

## 9. Things that will bite if forgotten

- **`LIKE` case-sensitivity:** extractor lookups and `_find_label_rows`-style
  SQL rely on SQLite's case-insensitive LIKE. The chosen `_ai_ci` collation
  preserves this — do not let anyone "fix" the collation to `_bin`.
- **`GROUP BY` strictness:** MySQL 8 `ONLY_FULL_GROUP_BY` (default ON)
  rejects some queries SQLite tolerates (selecting non-aggregated columns).
  Audit every `GROUP BY` (grep shows they're concentrated in `page_*.py`).
- **Empty-string PKs** (see §4) — keep `NOT NULL DEFAULT ''`.
- **`REPLACE`/upsert + AUTO_INCREMENT:** ODKU still increments the counter
  on duplicate hits; irrelevant at this scale but don't be surprised by id
  gaps.
- **Backups change shape:** the "copy the .db file" habit becomes
  `mysqldump --single-transaction mis_reports > backup.sql` — wire it into
  whatever currently copies the SQLite file, BEFORE cutover.
- **Two DBs, one truth:** after cutover, physically rename the SQLite file
  (e.g. `mis_reports.db.pre-mysql`) so a misconfigured env var can't
  silently write to the old file.
