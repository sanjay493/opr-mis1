"""
One-time script: populate techno_param / techno_param_group / techno_actuals
from the renamed legacy tables (_old_techno_param_master, _old_techno_monthly).

Run once after server restart has created the new schema:
    cd backend && python migrate_techno_data.py
"""
import sqlite3
import db
from db import get_or_create_techno_param

db.init_db()
conn = sqlite3.connect(db.DB_PATH)
conn.row_factory = sqlite3.Row

# ── 1. Verify old tables exist ────────────────────────────────────────────────
tables = {r[0] for r in conn.execute(
    "SELECT name FROM sqlite_master WHERE type='table'"
).fetchall()}

for t in ("_old_techno_param_master", "_old_techno_monthly"):
    if t not in tables:
        print(f"ERROR: {t} not found — migration may have already run or old data is gone.")
        raise SystemExit(1)

# ── 2. Build old param_id -> new param_id map ─────────────────────────────────
print("Mapping old param_master rows to new techno_param …")
old_params = conn.execute(
    "SELECT param_id, group_code, section, row_label, unit, sort_order "
    "FROM _old_techno_param_master"
).fetchall()

old_to_new = {}  # old param_id -> new param_id
for row in old_params:
    new_id = get_or_create_techno_param(
        row["group_code"],
        row["section"],
        row["row_label"],
        row["unit"] or "",
        row["sort_order"] or 0,
    )
    old_to_new[row["param_id"]] = new_id

print(f"  {len(old_to_new)} params mapped")

# ── 3. Migrate actuals from _old_techno_monthly -> techno_actuals ─────────────
print("Migrating _old_techno_monthly -> techno_actuals …")
monthly_rows = conn.execute(
    "SELECT param_id, report_month, actual, cum_actual, source_priority FROM _old_techno_monthly"
).fetchall()

inserted = skipped = 0
for row in monthly_rows:
    new_id = old_to_new.get(row["param_id"])
    if new_id is None:
        skipped += 1
        continue
    source = "manual" if (row["source_priority"] or 5) < 5 else "excel"
    conn.execute("""
        INSERT INTO techno_actuals (report_month, param_id, actual, till_month_actual, source)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(report_month, param_id) DO NOTHING
    """, (row["report_month"], new_id, row["actual"], row["cum_actual"], source))
    inserted += 1

conn.commit()
print(f"  inserted={inserted}  skipped={skipped}")

# ── 4. Report ─────────────────────────────────────────────────────────────────
total = conn.execute("SELECT COUNT(*) FROM techno_actuals").fetchone()[0]
print(f"techno_actuals now has {total} rows.")
conn.close()
print("Done.")
