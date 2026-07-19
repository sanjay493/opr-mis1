"""One-shot data copy SQLite -> MySQL with a verification gate.

Usage (from backend/): python scripts/migrate_sqlite_to_mysql.py [--copy]
Without --copy it only runs the verification (safe to re-run any time).

Reads MySQL credentials from backend/.env (MYSQL_* keys).
"""
import argparse
import os
import sqlite3
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

import pymysql

SQLITE_PATH = os.path.join(os.path.dirname(__file__), "..", "mis_reports.db")

TABLES = [
    "production_table", "production_plan_table", "page_configs",
    "special_steel_orders", "stock_table", "ipt_table", "pdf_item_alias",
    "techno_data", "techno_plan_fy", "extraction_log", "users",
    "allowed_emails", "otp_codes", "activity_log", "todo_jobs",
    "daily_work_log", "ipt_data_json", "production_data_json",
    "production_plan_json", "special_steel_json", "stock_data_json",
]

JSON_COLS = {  # table -> columns that must be valid JSON in MySQL
    "techno_data": ["techno_json"],
    "techno_plan_fy": ["techno_json", "calculated_json", "calculation_method"],
    "ipt_data_json": ["data"], "production_data_json": ["data"],
    "production_plan_json": ["data"], "special_steel_json": ["data"],
    "stock_data_json": ["data"],
}


def mysql_conn():
    return pymysql.connect(
        host=os.environ.get("MYSQL_HOST", "127.0.0.1"),
        port=int(os.environ.get("MYSQL_PORT", "3306")),
        user=os.environ.get("MYSQL_USER", "mis_app"),
        password=os.environ.get("MYSQL_PASSWORD", ""),
        database=os.environ.get("MYSQL_DB", "mis_reports"),
        charset="utf8mb4", autocommit=False,
    )


def copy_all():
    sq = sqlite3.connect(SQLITE_PATH)
    my = mysql_conn()
    mc = my.cursor()
    for table in TABLES:
        cur = sq.cursor()
        cur.execute(f"SELECT * FROM {table}")
        cols = [d[0] for d in cur.description]
        col_list = ", ".join(f"`{c}`" for c in cols)
        ph = ", ".join(["%s"] * len(cols))
        rows = cur.fetchall()
        mc.execute(f"DELETE FROM {table}")
        if rows:
            sql = f"INSERT INTO {table} ({col_list}) VALUES ({ph})"
            for i in range(0, len(rows), 1000):
                mc.executemany(sql, rows[i:i + 1000])
        my.commit()
        # reseed AUTO_INCREMENT where an id column exists
        if "id" in cols and rows:
            mc.execute(f"SELECT MAX(id) FROM {table}")
            mx = mc.fetchone()[0] or 0
            mc.execute(f"ALTER TABLE {table} AUTO_INCREMENT = {mx + 1}")
            my.commit()
        print(f"copied {table}: {len(rows)} rows")
    sq.close()
    my.close()


def verify():
    sq = sqlite3.connect(SQLITE_PATH)
    my = mysql_conn()
    mc = my.cursor()
    failures = 0
    for table in TABLES:
        sc = sq.cursor()
        sc.execute(f"SELECT COUNT(*) FROM {table}")
        n_s = sc.fetchone()[0]
        mc.execute(f"SELECT COUNT(*) FROM {table}")
        n_m = mc.fetchone()[0]
        ok = n_s == n_m
        detail = f"count {n_s} vs {n_m}"

        # numeric column checksums
        sc.execute(f"SELECT * FROM {table} LIMIT 1")
        if sc.description and n_s:
            cols = [d[0] for d in sc.description]
            for c in cols:
                sc.execute(f"SELECT ROUND(COALESCE(SUM(\"{c}\"),0), 3) FROM {table} "
                           f"WHERE typeof(\"{c}\") IN ('integer','real')")
                s_sum = sc.fetchone()[0]
                if s_sum in (0, None):
                    continue
                try:
                    mc.execute(f"SELECT ROUND(COALESCE(SUM(`{c}`),0), 3) FROM {table}")
                    m_sum = float(mc.fetchone()[0] or 0)
                except pymysql.Error:
                    my.rollback()
                    continue
                if abs(float(s_sum) - m_sum) > 0.01:
                    ok = False
                    detail += f" | SUM({c}) {s_sum} vs {m_sum}"

        # JSON validity
        for jc in JSON_COLS.get(table, []):
            mc.execute(f"SELECT COUNT(*) FROM {table} "
                       f"WHERE `{jc}` IS NOT NULL AND NOT JSON_VALID(`{jc}`)")
            bad = mc.fetchone()[0]
            if bad:
                ok = False
                detail += f" | {bad} invalid JSON in {jc}"

        print(f"{'OK  ' if ok else 'FAIL'} {table}: {detail}")
        failures += 0 if ok else 1
    sq.close()
    my.close()
    print(f"\nverification {'PASSED' if failures == 0 else f'FAILED ({failures} tables)'}")
    return failures == 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--copy", action="store_true", help="copy data before verifying")
    args = ap.parse_args()
    if args.copy:
        copy_all()
    sys.exit(0 if verify() else 1)
