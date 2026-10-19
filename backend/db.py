import json
import os
import re
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
from constants import ALL_PLANTS as PLANTS
from techno_registry import canonical_unit as _canon_unit
import dbengine
from dbengine import Row, IntegrityError, OperationalError
import activity_context
from repo.conn import row_dict as _row_dict  # noqa: F401  (also used by main.py)
# Production / capacity SQL lives in repo/; re-exported so db.<name> callers
# keep working.
from repo.production import (  # noqa: F401
    _FS_ALIAS_PLANTS,
    _fs_alias_sum,
    _sail_conversion_actual,
    get_sail_production_actual,
    get_sail_production_plan,
    get_sail_production_ytd_actual,
    get_sail_production_ytd_plan,
    save_production_actual,
    save_production_plan,
    get_production_actual_value,
    get_production_actual_for_months,
    enrich_rows_with_db_production,
)
from repo.capacity import (  # noqa: F401
    list_capacity_entries,
    get_effective_capacity,
    save_capacity_entry,
    update_capacity_entry,
    delete_capacity_entry,
)
# Techno SQL (techno_data / techno_plan_fy) lives in repo/techno.py.
from repo.techno import (  # noqa: F401
    save_techno_data_from_extraction,
    save_techno_json,
    _raw_upsert_techno_data,
    upsert_techno_data,
    _log_techno_save,
    _TMI_INPUT_KEYS,
    _FUEL_RATE_INPUT_KEYS,
    _maybe_recompute_derived_params,
    _SAIL_BF_UNITS,
    merge_upsert_techno_data,
    enrich_techno_records_with_db,
    get_techno_data,
    get_sail_techno_actuals,
    save_sail_techno_actuals,
    get_techno_months,
    get_techno_plan,
    _get_techno_plan_cached,
    save_techno_plan,
    get_techno_plant_plan,
    _get_techno_plant_plan_cached,
    save_techno_plant_plan,
    get_sail_techno_plan,
    _get_sail_techno_plan_cached,
    save_sail_techno_plan,
    list_techno_plan_fys,
)
# Special steel / stock / IPT SQL lives in repo/special_steel.py,
# repo/stock.py and repo/ipt.py.
from repo.special_steel import (  # noqa: F401
    clear_special_steel_orders,
    save_special_steel_entry,
    get_ss_phys_perf,
    save_ss_phys_meta,
    save_ss_phys_perf,
    get_ss_ipt_requirement,
    list_ss_ipt_requirement_fys,
    save_ss_ipt_requirement,
    delete_ss_ipt_requirement,
)
from repo.stock import save_stock_entry  # noqa: F401
from repo.ipt import save_ipt_entry, delete_ipt_entry  # noqa: F401
# Mines / rake detention / cost trend / market-intel SQL lives in
# repo/mines.py, repo/rake.py, repo/cost_trend.py and repo/misc.py.
from repo.cost_trend import (  # noqa: F401
    COST_TREND_PLANTS,
    COST_TREND_COST_TYPES,
    COST_TREND_ENTRY_PLANTS,
    COST_TREND_ENTRY_COST_TYPES,
    get_cost_trend_annual,
    save_cost_trend_annual,
    get_cost_trend_monthly,
    save_cost_trend_monthly,
    save_cost_trend_monthly_field,
)
from repo.mines import (  # noqa: F401
    get_sail_mines_monthly,
    save_sail_mines_monthly,
    get_mines_masters,
    get_mines_production_despatch_monthly,
    save_mines_production_despatch_monthly,
    get_iron_ore_group_rollup_monthly,
    get_iron_ore_despatch_mix,
    get_iron_ore_sales_group_rollup_monthly,
    get_iron_ore_mines_series,
)
from repo.misc import (  # noqa: F401
    get_market_price_trend,
    save_market_price_trend,
    get_macro_indicators,
    save_macro_indicators,
)
from repo.rake import (  # noqa: F401
    _RAKE_MASTER_COLS,
    get_rake_detention_master,
    _group_rake_master_rows,
    save_rake_detention_master_row,
    deactivate_rake_detention_master_row,
    get_rake_detention_monthly,
    save_rake_detention_monthly,
    get_rake_detention_trend,
    get_rake_detention_summary,
    save_rake_detention_summary,
    get_rake_detention_annual,
    save_rake_detention_annual,
)


def connect():
    """Single connection factory for the whole backend: a pooled MySQL
    connection (see dbengine.py). Deprecated alias kept for existing call
    sites; new code uses repo.conn.cursor() / repo.conn.tx()."""
    return dbengine.connect()


def init_db():
    """No-op kept for existing callers. The MySQL schema is owned by
    scripts/mysql_schema.sql (plus scripts/migrate_*.sql), not created
    lazily at runtime."""
    return None

def get_ytd_months(report_month: str) -> List[str]:
    """Returns YYYY-MM strings from April of the current FY up to report_month."""
    try:
        y, m = int(report_month[:4]), int(report_month[5:7])
    except (ValueError, IndexError):
        return [report_month]
    fy_start_year = y if m >= 4 else y - 1
    result = []
    cur_y, cur_m = fy_start_year, 4
    while True:
        result.append(f"{cur_y}-{cur_m:02d}")
        if cur_y == y and cur_m == m:
            break
        cur_m += 1
        if cur_m > 12:
            cur_m = 1
            cur_y += 1
    return result

def get_fy_months(report_month: str) -> List[str]:
    """Returns all 12 YYYY-MM strings of the financial year that contains report_month."""
    try:
        y, m = int(report_month[:4]), int(report_month[5:7])
    except (ValueError, IndexError):
        return []
    fy_start_year = y if m >= 4 else y - 1
    result = []
    cur_y, cur_m = fy_start_year, 4
    for _ in range(12):
        result.append(f"{cur_y}-{cur_m:02d}")
        cur_m += 1
        if cur_m > 12:
            cur_m = 1
            cur_y += 1
    return result


def shift_month(month: str, delta: int) -> str:
    """'YYYY-MM' shifted by `delta` calendar months (negative = earlier)."""
    y, m = int(month[:4]), int(month[5:7])
    idx = y * 12 + (m - 1) + delta
    return f"{idx // 12}-{idx % 12 + 1:02d}"


def get_trailing_months(end_month: str, n: int) -> List[str]:
    """n calendar months ending at end_month (inclusive), oldest first —
    a plain rolling window, unlike get_ytd_months/get_fy_months which reset
    at the April FY boundary. Used by pages whose source data is a rolling
    snapshot rather than an FY-aligned series (e.g. page_market_prices.py /
    page_macro_indicators.py's BigMint market-intelligence pages)."""
    return [shift_month(end_month, -i) for i in range(n - 1, -1, -1)]


def get_fy_for_month(report_month: str) -> str:
    """Returns FY string (e.g., '2026-27') for a given report_month (e.g., '2026-05')."""
    try:
        y, m = int(report_month[:4]), int(report_month[5:7])
    except (ValueError, IndexError):
        return report_month
    # FY starts Apr (month 4), so Apr-Dec of year Y → FY Y-(Y+1), Jan-Mar of year Y → FY (Y-1)-Y
    if m >= 4:
        return f"{y}-{(y+1) % 100:02d}"
    else:
        return f"{y-1}-{y % 100:02d}"


def get_cply_month(report_month: str) -> str:
    """Returns same month in the previous year (e.g. 2025-11 -> 2024-11)."""
    try:
        y, m = int(report_month[:4]), int(report_month[5:7])
        return f"{y - 1}-{m:02d}"
    except (ValueError, IndexError):
        return report_month


def get_page_config(month: str, page_number: int) -> Optional[dict]:
    """Retrieves standard page configuration if saved in DB."""
    init_db()
    conn = connect()
    cursor = conn.cursor()
    cursor.execute("SELECT page_data FROM page_configs WHERE report_month = %s AND page_number = %s", (month, page_number))
    row = cursor.fetchone()
    conn.close()
    return json.loads(row[0]) if row else None

def get_all_page_configs(month: str) -> List[dict]:
    """Retrieves all standard page configurations for a month, ordered by page number."""
    init_db()
    conn = connect()
    cursor = conn.cursor()
    cursor.execute("SELECT page_data FROM page_configs WHERE report_month = %s ORDER BY page_number ASC", (month,))
    rows = cursor.fetchall()
    conn.close()
    return [json.loads(row[0]) for row in rows]

def save_page_config(month: str, page_number: int, page_data: dict):
    """Saves or updates a page configuration."""
    init_db()
    conn = connect()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO page_configs (report_month, page_number, page_data)
        VALUES (%s, %s, %s)
        AS new ON DUPLICATE KEY UPDATE page_data = new.page_data
    """, (month, page_number, json.dumps(page_data)))
    conn.commit()
    conn.close()

def get_page3_narrative(month: str) -> Optional[dict]:
    """Returns the saved Page 3 Production Narrative + Highlights for a month,
    or None if nothing has ever been saved (caller should keep whatever
    default/computed value it already has)."""
    init_db()
    conn = connect()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT production_narrative, highlights FROM page3_narrative WHERE report_month = %s",
        (month,)
    )
    row = cursor.fetchone()
    conn.close()
    if not row:
        return None
    narrative, highlights_text = row[0] or "", row[1] or ""
    return {
        "production_narrative": narrative,
        "highlights": highlights_text.split("\n") if highlights_text else [],
    }

def save_page3_narrative(month: str, production_narrative: str, highlights: List[str]):
    """Saves/updates Page 3's Production Narrative + Highlights, keyed only by
    report_month — independent of page_configs so it never risks touching
    the other 34 pages' saved data for the month."""
    init_db()
    conn = connect()
    cursor = conn.cursor()
    highlights_text = "\n".join(highlights or [])
    cursor.execute("""
        INSERT INTO page3_narrative (report_month, production_narrative, highlights, updated_at)
        VALUES (%s, %s, %s, NOW())
        AS new ON DUPLICATE KEY UPDATE production_narrative = new.production_narrative,
                       highlights = new.highlights,
                       updated_at = new.updated_at
    """, (month, production_narrative or "", highlights_text))
    conn.commit()
    conn.close()

def get_key_highlights_narrative(month: str) -> Optional[dict]:
    """Returns the saved Key Highlights & Variances narrative (Major
    Achievements / Major Shortfalls / Focus Areas Going Forward) for a
    month, or None if nothing has ever been saved for it — the report page
    shows empty sections in that case rather than inventing text."""
    init_db()
    conn = connect()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT achievements, shortfalls, focus_areas, updated_by, updated_at "
        "FROM key_highlights_narrative WHERE report_month = %s",
        (month,)
    )
    row = cursor.fetchone()
    conn.close()
    if not row:
        return None
    achievements, shortfalls, focus_areas, updated_by, updated_at = row
    return {
        "achievements": json.loads(achievements) if achievements else [],
        "shortfalls":   json.loads(shortfalls) if shortfalls else [],
        "focus_areas":  json.loads(focus_areas) if focus_areas else [],
        "updated_by":   updated_by or "",
        "updated_at":   updated_at or "",
    }

def save_key_highlights_narrative(month: str, achievements: list, shortfalls: list,
                                   focus_areas: list, updated_by: str = ""):
    """Saves/updates the Key Highlights & Variances narrative for a month,
    keyed only by report_month — independent of page_configs, same as
    save_page3_narrative above."""
    init_db()
    conn = connect()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO key_highlights_narrative
            (report_month, achievements, shortfalls, focus_areas, updated_by, updated_at)
        VALUES (%s, %s, %s, %s, %s, NOW())
        AS new ON DUPLICATE KEY UPDATE achievements = new.achievements,
                       shortfalls  = new.shortfalls,
                       focus_areas = new.focus_areas,
                       updated_by  = new.updated_by,
                       updated_at  = new.updated_at
    """, (month, json.dumps(achievements or []), json.dumps(shortfalls or []),
          json.dumps(focus_areas or []), updated_by or ""))
    conn.commit()
    conn.close()

def get_steel_sales_highlights(month: str) -> Optional[dict]:
    """Saved Steel Sales Performance bullets (report-month + YTD lists) for
    a month, or None if nothing has ever been saved for it — the report
    page shows empty sections in that case rather than inventing text."""
    init_db()
    conn = connect()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT month_items, ytd_items, updated_by, updated_at "
        "FROM steel_sales_highlights WHERE report_month = %s",
        (month,)
    )
    row = cursor.fetchone()
    conn.close()
    if not row:
        return None
    month_items, ytd_items, updated_by, updated_at = row
    return {
        "month_items": json.loads(month_items) if month_items else [],
        "ytd_items":   json.loads(ytd_items) if ytd_items else [],
        "updated_by":  updated_by or "",
        "updated_at":  updated_at or "",
    }

def save_steel_sales_highlights(month: str, month_items: list, ytd_items: list, updated_by: str = ""):
    """Saves/updates the Steel Sales Performance bullets for a month, keyed
    only by report_month — independent of page_configs, same as
    save_key_highlights_narrative above."""
    init_db()
    conn = connect()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO steel_sales_highlights
            (report_month, month_items, ytd_items, updated_by, updated_at)
        VALUES (%s, %s, %s, %s, NOW())
        AS new ON DUPLICATE KEY UPDATE month_items = new.month_items,
                       ytd_items   = new.ytd_items,
                       updated_by  = new.updated_by,
                       updated_at  = new.updated_at
    """, (month, json.dumps(month_items or []), json.dumps(ytd_items or []), updated_by or ""))
    conn.commit()
    conn.close()

# ============================================================================
# Breakdown log — plant/unit-wise unplanned-downtime events (see
# api_breakdown.py). Unlike capital_repair_table (a pre-seeded annual plan
# where only "actual" is ever edited), breakdown_table rows are ad hoc
# events plant users create/edit/delete freely, so this is full CRUD.
# ============================================================================

def list_breakdown_entries(plant: Optional[str] = None, fy: Optional[str] = None,
                            unit_type: Optional[str] = None, unit_name: Optional[str] = None) -> List[Dict[str, Any]]:
    """List breakdown events, optionally filtered. `fy` filters by the FY
    fy_from_month(start_ts) falls in (computed in Python — start_ts has no
    stored FY column, see breakdown_table's docstring in init_db())."""
    from page_capital_repair import fy_from_month
    init_db()
    conn = connect()
    sql = "SELECT * FROM breakdown_table WHERE 1=1"
    args = []
    if plant:
        sql += " AND plant=%s"; args.append(plant)
    if unit_type:
        sql += " AND unit_type=%s"; args.append(unit_type)
    if unit_name:
        sql += " AND unit_name=%s"; args.append(unit_name)
    sql += " ORDER BY start_ts DESC, id DESC"
    prev_factory = conn.row_factory
    conn.row_factory = Row
    try:
        cur = conn.execute(sql, args)
        rows = [dict(r) for r in cur.fetchall()]
    finally:
        conn.row_factory = prev_factory
        conn.close()
    if fy:
        rows = [r for r in rows if r.get("start_ts") and fy_from_month(r["start_ts"][:7]) == fy]
    return rows


def save_breakdown_entry(plant: str, unit_type: str, unit_name: str, sms_subtag: Optional[str],
                          start_ts: str, end_ts: Optional[str], is_ongoing: bool,
                          cause: str, hours_lost_override: Optional[float],
                          created_by: str, capital_repair_id: Optional[int] = None) -> int:
    """Create one breakdown event. Returns the new row id. capital_repair_id
    links it to the capital repair it really is (see bd_cr_link)."""
    from datetime import datetime
    init_db()
    conn = connect()
    now = datetime.now().isoformat()
    cur = conn.execute("""
        INSERT INTO breakdown_table
            (plant, unit_type, unit_name, sms_subtag, start_ts, end_ts, is_ongoing,
             cause, hours_lost_override, capital_repair_id, created_by, created_at, updated_by, updated_at)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    """, (plant, unit_type, unit_name, sms_subtag, start_ts, end_ts, int(is_ongoing),
          cause, hours_lost_override, capital_repair_id, created_by, now, created_by, now))
    conn.commit()
    new_id = cur.lastrowid
    conn.close()
    activity_context.record(f"breakdown_table/{plant}/{unit_name}/{new_id}", None, {
        "plant": plant, "unit_type": unit_type, "unit_name": unit_name, "sms_subtag": sms_subtag,
        "start_ts": start_ts, "end_ts": end_ts, "is_ongoing": is_ongoing, "cause": cause,
        "hours_lost_override": hours_lost_override, "capital_repair_id": capital_repair_id,
    })
    return new_id


def update_breakdown_entry(breakdown_id: int, updated_by: str, **fields) -> bool:
    """Update the given fields (any subset of plant/unit_type/unit_name/sms_subtag/
    start_ts/end_ts/is_ongoing/cause/hours_lost_override/capital_repair_id) on one breakdown event.
    Returns False if the row doesn't exist."""
    from datetime import datetime
    init_db()
    conn = connect()
    old = _row_dict(conn, "SELECT * FROM breakdown_table WHERE id=%s", (breakdown_id,))
    if old is None:
        conn.close()
        return False
    allowed = {"plant", "unit_type", "unit_name", "sms_subtag", "start_ts", "end_ts",
               "is_ongoing", "cause", "hours_lost_override", "capital_repair_id"}
    sets, args = [], []
    for k, v in fields.items():
        if k not in allowed:
            continue
        sets.append(f"{k}=%s")
        args.append(int(v) if k == "is_ongoing" else v)
    if not sets:
        conn.close()
        return True
    sets.append("updated_by=%s"); args.append(updated_by)
    sets.append("updated_at=%s"); args.append(datetime.now().isoformat())
    args.append(breakdown_id)
    conn.execute(f"UPDATE breakdown_table SET {', '.join(sets)} WHERE id=%s", args)
    conn.commit()
    conn.close()
    new = {**old, **{k: v for k, v in fields.items() if k in allowed}}
    activity_context.record(f"breakdown_table/{old['plant']}/{old['unit_name']}/{breakdown_id}", old, new)
    return True


def delete_breakdown_entry(breakdown_id: int) -> bool:
    """Delete one breakdown event, recording its prior state. Returns False if not found."""
    init_db()
    conn = connect()
    old = _row_dict(conn, "SELECT * FROM breakdown_table WHERE id=%s", (breakdown_id,))
    if old is None:
        conn.close()
        return False
    conn.execute("DELETE FROM breakdown_table WHERE id=%s", (breakdown_id,))
    conn.commit()
    conn.close()
    activity_context.record(f"breakdown_table/{old['plant']}/{old['unit_name']}/{breakdown_id}", old, None)
    return True





def log_page_visit(ip_address: str, user: Optional[dict], path: str) -> None:
    """Appends one row to page_visits — a frontend navigation to `path`,
    from `ip_address`, by `user` (the get_current_user_optional dict) or
    anonymously if `user` is None. See api_visits.py's POST /api/log-visit."""
    init_db()
    conn = connect()
    conn.execute("""
        INSERT INTO page_visits (timestamp, ip_address, user_email, user_name, path)
        VALUES (%s, %s, %s, %s, %s)
    """, (
        datetime.now(timezone.utc).isoformat(),
        ip_address or None,
        user.get("email") if user else None,
        user.get("name") if user else None,
        path,
    ))
    conn.commit()
    conn.close()


ANON_VISIT_NOTIFY_WINDOW_MINUTES = 30


def add_admin_notification(kind: str, ip_address: str = "", user: Optional[dict] = None,
                           path: Optional[str] = None) -> None:
    """Records one event for the admin notification bell. kind is 'sign_in'
    or 'anon_visit'. An 'anon_visit' is skipped when the same IP already
    raised one in the last ANON_VISIT_NOTIFY_WINDOW_MINUTES, so a visitor
    clicking around doesn't produce one alert per page.

    Best-effort: a failure here is logged and swallowed — it must never
    break the sign-in or visit request that triggered it."""
    try:
        _add_admin_notification(kind, ip_address, user, path)
    except Exception as e:
        print(f"[admin_notifications] could not record {kind}: {e}")


def _add_admin_notification(kind, ip_address, user, path) -> None:
    from datetime import timedelta
    init_db()
    now = datetime.now(timezone.utc)
    conn = connect()
    try:
        if kind == "anon_visit":
            since = (now - timedelta(minutes=ANON_VISIT_NOTIFY_WINDOW_MINUTES)).isoformat()
            row = conn.execute(
                "SELECT 1 FROM admin_notifications WHERE kind = 'anon_visit' AND ip_address = %s AND created_at >= %s LIMIT 1",
                (ip_address or None, since),
            ).fetchone()
            if row:
                return
        conn.execute("""
            INSERT INTO admin_notifications (created_at, kind, user_email, user_name, ip_address, path)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (
            now.isoformat(),
            kind,
            user.get("email") if user else None,
            user.get("name") if user else None,
            ip_address or None,
            path,
        ))
        conn.commit()
    finally:
        conn.close()


def list_admin_notifications(limit: int = 30) -> List[Dict[str, Any]]:
    """Newest-first admin notification events (see add_admin_notification)."""
    init_db()
    conn = connect()
    conn.row_factory = Row
    try:
        rows = conn.execute(
            "SELECT id, created_at, kind, user_email, user_name, ip_address, path "
            "FROM admin_notifications ORDER BY id DESC LIMIT %s",
            (int(limit),),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


# ── Is a month's production data final? (page 4's "Tentative" label) ──────
# A month is final once each of these plants has its FINAL monthly report in
# extraction_log for that month; interim uploads (daily/morning reports, DSP's
# pcontrep/mcr1, BSL's DPR mail) don't count. BSP/ASP/SSP/VISL aren't
# checked (per direct instruction, 2026-10-04: BSP re-uploads the same PPC MIS
# workbook through and after the month, so no upload marks it final).
# Months before _FINAL_STATUS_FROM predate the log tracking these uploads
# (their final figures came from backfills), so they always count as final.
_FINAL_STATUS_FROM = "2026-04"
_FINAL_REPORT_RULES = {
    "RSP": lambda src, fname, ym: src.startswith("Final Monthly Report"),
    "ISP": lambda src, fname, ym: src.startswith(("Final Monthly Report", "Summarized Monthly Report")),
    "BSL": lambda src, fname, ym: src.startswith("BSL Production of Main Products (PDF)"),
    # DSP's monthly MIS PDF is named for its month: mis0826.pdf = Aug'26.
    "DSP": lambda src, fname, ym: src == "DSP OMI PDF Report" and re.match(
        rf"(?i)mis{ym[5:7]}{ym[2:4]}\b", fname or "") is not None,
}


def _production_month_status(report_month: str, log_rows) -> dict:
    """Pure rule: log_rows = [(plant_name, source_type, file_name), ...] for
    report_month -> {"tentative": bool, "missing": [plants without a final
    monthly report]}."""
    if report_month < _FINAL_STATUS_FROM:
        return {"tentative": False, "missing": []}
    missing = [plant for plant, rule in _FINAL_REPORT_RULES.items()
               if not any(p == plant and rule(src or "", fname, report_month) for p, src, fname in log_rows)]
    return {"tentative": bool(missing), "missing": missing}


def production_month_status(report_month: str) -> dict:
    """{"tentative", "missing"} for report_month from extraction_log — see
    _production_month_status."""
    init_db()
    conn = connect()
    try:
        cur = conn.cursor()
        cur.execute("SELECT plant_name, source_type, file_name FROM extraction_log WHERE report_month = %s",
                    (report_month,))
        return _production_month_status(report_month, cur.fetchall())
    finally:
        conn.close()


def log_extraction(plant: str, report_month: str, file_name: str, sheet_name: str,
                   source_type: str, items_extracted: int, conn=None):
    """Appends a record to the extraction audit log.

    `conn`: see merge_upsert_techno_data's docstring — when reused, this
    does NOT commit; the caller owns the transaction boundary (see
    _raw_upsert_techno_data's docstring for why that matters here)."""
    init_db()
    from datetime import datetime
    owns_conn = conn is None
    if owns_conn:
        conn = connect()
    conn.execute("""
        INSERT INTO extraction_log (logged_at, plant_name, report_month, file_name, sheet_name, source_type, items_extracted)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
    """, (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), plant, report_month, file_name, sheet_name, source_type, items_extracted))
    if owns_conn:
        conn.commit()
        conn.close()


def get_pdf_item_aliases(plant: str) -> Dict[str, Any]:
    """User-saved PDF label corrections for a plant: {pdf_label: (item_name, convert_t)}."""
    init_db()
    conn = connect()
    rows = conn.execute("""
        SELECT pdf_label, item_name, convert_t FROM pdf_item_alias WHERE plant_name = %s
    """, (plant,)).fetchall()
    conn.close()
    return {r[0]: (r[1], r[2]) for r in rows}


def save_pdf_item_alias(plant: str, pdf_label: str, item_name: str, convert_t: int = 1):
    """Upsert a PDF label → item_name correction so future extractions map it automatically."""
    # Count-type items (e.g. "Oven Pushing(nos/d)") are plain numbers, never
    # tonnes — force convert_t=0 so no caller (stale UI tab, mapping
    # suggestions, re-confirm) can re-poison the alias with a ÷1000 flag.
    if "(nos" in (item_name or "").lower():
        convert_t = 0
    init_db()
    conn = connect()
    old = _row_dict(conn,
        "SELECT * FROM pdf_item_alias WHERE plant_name=%s AND pdf_label=%s",
        (plant, pdf_label))
    conn.execute("""
        INSERT INTO pdf_item_alias (plant_name, pdf_label, item_name, convert_t)
        VALUES (%s, %s, %s, %s)
        AS new ON DUPLICATE KEY UPDATE item_name = new.item_name, convert_t = new.convert_t
    """, (plant, pdf_label, item_name, convert_t))
    conn.commit()
    conn.close()
    new = {"plant_name": plant, "pdf_label": pdf_label, "item_name": item_name, "convert_t": convert_t}
    activity_context.record(f"pdf_item_alias/{plant}/{pdf_label}", old, new)


def get_extraction_logs(limit: int = 60, plant: Optional[str] = None,
                         source_type: Optional[str] = None) -> List[Dict[str, Any]]:
    """Returns the most recent extraction log entries, newest first.
    Optional plant/source_type filters let a page (e.g. /data-entry/techno)
    show only its own entries from this shared log table."""
    init_db()
    conn = connect()
    conn.row_factory = Row
    clauses, params = [], []
    if plant:
        clauses.append("plant_name = %s")
        params.append(plant)
    if source_type:
        clauses.append("source_type = %s")
        params.append(source_type)
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    params.append(limit)
    rows = conn.execute(f"""
        SELECT id, logged_at, plant_name, report_month, file_name, sheet_name, source_type, items_extracted
        FROM extraction_log
        {where}
        ORDER BY id DESC
        LIMIT %s
    """, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]



# ── "Special Steel Plants Physical Performance" report ────────────────────────
# Backing store for page_special_steel_physical.py + its two data-entry pages.
# All physical figures are '000 T. See migrate_add_special_steel_physical.sql.

def get_ss_phys_notes(financial_year):
    """-> [(sort_order, note_text), ...] ordered."""
    init_db()
    conn = connect()
    cur = conn.cursor()
    cur.execute("SELECT sort_order, note_text FROM special_steel_phys_note "
                "WHERE financial_year=%s ORDER BY sort_order", (financial_year,))
    rows = cur.fetchall()
    conn.close()
    return [(so, t) for so, t in rows]


def save_ss_phys_notes(financial_year, rows):
    """Replace every note for a FY with `rows`: {sort_order, note_text}."""
    init_db()
    conn = connect()
    cur = conn.cursor()
    cur.execute("DELETE FROM special_steel_phys_note WHERE financial_year=%s", (financial_year,))
    for r in rows:
        text = (r.get("note_text") or "").strip()
        if not text:
            continue
        cur.execute("INSERT INTO special_steel_phys_note (financial_year, sort_order, note_text) "
                    "VALUES (%s, %s, %s)", (financial_year, int(r.get("sort_order") or 0), text))
    conn.commit()
    conn.close()
    return len(rows)


# ── "Rail Production & Dispatch from BSP" (page 18.5) ──────────────────────
# Backing store for page_rail_report.py + /data-entry/rail-report. See
# scripts/migrate_add_rail_report.sql.

def get_rail_report_data(fys: List[str]) -> Dict[str, Dict[str, Dict[str, Any]]]:
    """-> {financial_year: {metric: {"value": v, "note": n}}}."""
    init_db()
    conn = connect()
    cur = conn.cursor()
    out = {fy: {} for fy in fys}
    if fys:
        ph = ",".join(["%s"] * len(fys))
        cur.execute(f"SELECT financial_year, metric, value, note FROM rail_prod_despatch "
                    f"WHERE financial_year IN ({ph})", fys)
        for fy, metric, value, note in cur.fetchall():
            out.setdefault(fy, {})[metric] = {"value": value, "note": note}
    conn.close()
    return out


def save_rail_report_data(rows: List[Dict[str, Any]]) -> int:
    """Upsert rail_prod_despatch rows: {financial_year, metric, value, note}."""
    init_db()
    conn = connect()
    cur = conn.cursor()
    for r in rows:
        cur.execute("""
            INSERT INTO rail_prod_despatch (financial_year, metric, value, note)
            VALUES (%s, %s, %s, %s)
            AS new ON DUPLICATE KEY UPDATE
                value = new.value, note = new.note
        """, (r["financial_year"], r["metric"], r.get("value"), r.get("note")))
    conn.commit()
    conn.close()
    return len(rows)


def get_rail_report_notes() -> List[tuple]:
    """-> [(sort_order, note_text), ...] ordered."""
    init_db()
    conn = connect()
    cur = conn.cursor()
    cur.execute("SELECT sort_order, note_text FROM rail_prod_despatch_note ORDER BY sort_order")
    rows = cur.fetchall()
    conn.close()
    return [(so, t) for so, t in rows]


def save_rail_report_notes(rows: List[Dict[str, Any]]) -> int:
    """Replace every footer remark with `rows`: {sort_order, note_text}."""
    init_db()
    conn = connect()
    cur = conn.cursor()
    cur.execute("DELETE FROM rail_prod_despatch_note")
    for r in rows:
        text = (r.get("note_text") or "").strip()
        if not text:
            continue
        cur.execute("INSERT INTO rail_prod_despatch_note (sort_order, note_text) VALUES (%s, %s)",
                    (int(r.get("sort_order") or 0), text))
    conn.commit()
    conn.close()
    return len(rows)


# ── "Ready Reckoner" (Annexure-1: 5 ISPs / Annexure-2: 3 SSPs) ─────────────
# Backing store for page_ready_reckoner.py + its editor (/data-entry/ready-
# reckoner). See scripts/migrate_ready_reckoner_structured.sql. Not month-
# scoped — see this table's own comment in init_db().
#
# capacity_rows/product_mix_headers/product_mix_rows store PLAIN DATA only
# (JSON, no HTML/markup/style of any kind) — per direct instruction,
# 2026-09-21: the previous design (capacity_html/product_mix_html, raw
# editor-authored HTML strings rendered with Jinja's |safe) let formatting
# leak into the stored content itself. All presentation (colors, bold
# totals, line breaks) is now applied at render time instead — React in the
# live preview/editor, Jinja+CSS in the PDF template (ready_reckoner_
# plant.html) — never stored. See scripts/migrate_ready_reckoner_
# structured.py for the one-time migration that parsed the old HTML into
# this shape.
#
# Shapes (all json.dumps'd into TEXT columns, json.loads'd back out below):
#   capacity_rows:       [{"item": str, "details": str, "capacity": str, "is_total": bool}, ...]
#   product_mix_headers: [str, ...]                 -- this plant's own column titles
#   product_mix_rows:    [{"cells": [str, ...], "is_total": bool}, ...]  -- len(cells) == len(headers)
# product_mix_caption is plain TEXT (not JSON) — a one-line note some plants
# carry above their Product Mix table (e.g. BSL's "representative grade
# families per product — see full spec sheet for exhaustive list"); most
# plants leave it blank.
# A cell's "\n" means a line break (rendered as <br> at display time), never
# literal HTML.

_READY_RECKONER_COLS = (
    "plant_code", "plant_name", "plant_group", "process_flow_image_path",
    "capacity_rows", "product_mix_headers", "product_mix_rows", "product_mix_caption",
    "sort_order", "updated_by", "updated_at",
)

_READY_RECKONER_JSON_COLS = ("capacity_rows", "product_mix_headers", "product_mix_rows")


def _decode_ready_reckoner_row(row: tuple) -> dict:
    d = dict(zip(_READY_RECKONER_COLS, row))
    for col in _READY_RECKONER_JSON_COLS:
        d[col] = json.loads(d[col]) if d.get(col) else []
    d["product_mix_caption"] = d.get("product_mix_caption") or ""
    return d


def get_ready_reckoner_pages() -> List[dict]:
    """-> every plant's row (dict, _READY_RECKONER_COLS keys, JSON columns
    already decoded to lists), ordered for display (ISPs then SSPs, each
    group in its own sort_order)."""
    init_db()
    conn = connect()
    cur = conn.cursor()
    cur.execute(
        f"SELECT {','.join(_READY_RECKONER_COLS)} FROM ready_reckoner_pages "
        f"ORDER BY plant_group, sort_order, plant_code"
    )
    rows = [_decode_ready_reckoner_row(r) for r in cur.fetchall()]
    conn.close()
    return rows


def get_ready_reckoner_page(plant_code: str) -> Optional[dict]:
    init_db()
    conn = connect()
    cur = conn.cursor()
    cur.execute(
        f"SELECT {','.join(_READY_RECKONER_COLS)} FROM ready_reckoner_pages WHERE plant_code = %s",
        (plant_code,),
    )
    row = cur.fetchone()
    conn.close()
    return _decode_ready_reckoner_row(row) if row else None


def upsert_ready_reckoner_master(row: Dict[str, Any]) -> None:
    """Insert or update the non-editable identity fields of one plant's row
    (plant_name/plant_group/sort_order) — used by the one-time backfill, not
    the inline editor (which only ever touches content via the functions
    below)."""
    init_db()
    conn = connect()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO ready_reckoner_pages (plant_code, plant_name, plant_group, sort_order)
        VALUES (%s, %s, %s, %s)
        AS new ON DUPLICATE KEY UPDATE
            plant_name = new.plant_name, plant_group = new.plant_group,
            sort_order = new.sort_order
    """, (row["plant_code"], row.get("plant_name"), row["plant_group"], int(row.get("sort_order") or 0)))
    conn.commit()
    conn.close()


def save_ready_reckoner_content(
    plant_code: str, capacity_rows: Optional[list] = None,
    product_mix_headers: Optional[list] = None, product_mix_rows: Optional[list] = None,
    product_mix_caption: Optional[str] = None, updated_by: str = "",
) -> None:
    """Updates one or more of the plain-data fields for one plant, from the
    /data-entry/ready-reckoner form's Save action. None (not just an empty
    list) means "leave this field alone" — the capacity editor's Save action
    only ever sends capacity_rows, and must NOT blank out product_mix_*
    just because those fields weren't part of this particular payload.
    product_mix_headers and product_mix_rows are always sent together by
    the editor (changing column count means both change), but are still
    independently optional here for the same reason. A plain UPDATE, not an
    upsert: the row always already exists by this point (created by the
    one-time backfill via upsert_ready_reckoner_master, which owns
    plant_name/plant_group/sort_order) — MySQL's ON DUPLICATE KEY UPDATE
    still validates every column in the INSERT list against NOT NULL
    constraints even when it ends up taking the UPDATE branch, so a
    partial insert (omitting plant_group here) fails outright rather than
    falling through."""
    import datetime as _dt
    sets, args = [], []
    if capacity_rows is not None:
        sets.append("capacity_rows = %s")
        args.append(json.dumps(capacity_rows))
    if product_mix_headers is not None:
        sets.append("product_mix_headers = %s")
        args.append(json.dumps(product_mix_headers))
    if product_mix_rows is not None:
        sets.append("product_mix_rows = %s")
        args.append(json.dumps(product_mix_rows))
    if product_mix_caption is not None:
        sets.append("product_mix_caption = %s")
        args.append(product_mix_caption)
    if not sets:
        return
    sets += ["updated_by = %s", "updated_at = %s"]
    args += [updated_by, _dt.datetime.now().isoformat(timespec="seconds"), plant_code]
    init_db()
    conn = connect()
    cur = conn.cursor()
    cur.execute(f"UPDATE ready_reckoner_pages SET {', '.join(sets)} WHERE plant_code = %s", args)
    conn.commit()
    conn.close()


def save_ready_reckoner_image(plant_code: str, image_path: str, updated_by: str) -> None:
    """Updates just the process-flow diagram's file path for one plant, from
    the inline editor's image-upload control. Same plain-UPDATE reasoning
    as save_ready_reckoner_content."""
    import datetime as _dt
    init_db()
    conn = connect()
    cur = conn.cursor()
    cur.execute("""
        UPDATE ready_reckoner_pages
        SET process_flow_image_path = %s, updated_by = %s, updated_at = %s
        WHERE plant_code = %s
    """, (image_path, updated_by, _dt.datetime.now().isoformat(timespec="seconds"), plant_code))
    conn.commit()
    conn.close()


# ── Annexure-3 : 5 ISPs Major Units Records — Daily best (see
# major_unit_daily_record's own comment above and page_major_unit_records.py) ──

_MAJOR_UNIT_DAILY_COLS = (
    "plant_code", "unit_label", "unit_of_measure", "value",
    "record_date", "remarks", "sort_order", "updated_by", "updated_at",
)


def get_major_unit_daily_records(plant_code: str) -> List[dict]:
    """-> every unit row for one plant, in display order."""
    init_db()
    conn = connect()
    cur = conn.cursor()
    cur.execute(
        f"SELECT {','.join(_MAJOR_UNIT_DAILY_COLS)} FROM major_unit_daily_record "
        f"WHERE plant_code = %s ORDER BY sort_order",
        (plant_code,),
    )
    rows = [dict(zip(_MAJOR_UNIT_DAILY_COLS, r)) for r in cur.fetchall()]
    conn.close()
    return rows


def get_major_unit_daily_records_all() -> Dict[str, Dict[str, dict]]:
    """-> {plant_code: {unit_label: row_dict}} for every plant — used by
    page_major_unit_records.generate_major_unit_page to look up one plant's
    Daily figures alongside its live-computed Annual/Monthly bests."""
    init_db()
    conn = connect()
    cur = conn.cursor()
    cur.execute(f"SELECT {','.join(_MAJOR_UNIT_DAILY_COLS)} FROM major_unit_daily_record")
    out: Dict[str, Dict[str, dict]] = {}
    for r in cur.fetchall():
        d = dict(zip(_MAJOR_UNIT_DAILY_COLS, r))
        out.setdefault(d["plant_code"], {})[d["unit_label"]] = d
    conn.close()
    return out


def save_major_unit_daily_record(plant_code: str, unit_label: str, value: Optional[float],
                                  unit_of_measure: Optional[str], record_date: Optional[str],
                                  remarks: Optional[str], sort_order: int, updated_by: str = "") -> None:
    """Upsert one unit's Daily best — used by both the one-time backfill
    (scripts/backfill_major_unit_daily_records.py) and the
    /data-entry/major-unit-daily editor (see main.py's
    /api/major-unit-daily/{plant_code} POST)."""
    import datetime as _dt
    init_db()
    conn = connect()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO major_unit_daily_record
            (plant_code, unit_label, unit_of_measure, value, record_date,
             remarks, sort_order, updated_by, updated_at)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        AS new ON DUPLICATE KEY UPDATE
            unit_of_measure = new.unit_of_measure, value = new.value,
            record_date = new.record_date, remarks = new.remarks,
            sort_order = new.sort_order, updated_by = new.updated_by,
            updated_at = new.updated_at
    """, (plant_code, unit_label, unit_of_measure, value, record_date, remarks,
          sort_order, updated_by, _dt.datetime.now().isoformat(timespec="seconds")))
    conn.commit()
    conn.close()
