"""Special steel repository on the v2 schema: special_steel_order (v1
special_steel_orders), special_steel_abp (v1 special_steel_abp_table),
special_steel_grade_club (v1 special_steel_grade_clubs) and the Special
Steel Plants Physical Performance tables special_steel_phys_perf /
special_steel_phys_meta / special_steel_ipt_requirement. The narrative
special_steel_phys_note lives in report_text (repo.text, scope
ss_phys_note).

Same public names, signatures, return shapes, row types and exceptions as
repo/special_steel.py. Renamed columns are aliased back to their v1 names
(plant_name / plant <- plant_code, financial_year <- fy, from_plant /
to_plant <- from_plant_code / to_plant_code); aggregate columns keep v1's
expressions, so a Row cursor sees v1's labels.

ORDER. Reads with an ORDER BY keep it, completed with the rest of the
primary key where v1's sort keys could tie. Reads without one were served
in v1 by the primary key, which v2 repeats under the same ai_ci collation:
that order is explicit here. v1's GROUP BYs without an ORDER BY returned
their groups in first-appearance order along the primary-key scan; the
ORDER BY reproduces it (ORDER BY MIN(report_month), then the group key).

GRADE CLUBS. created_at was a VARCHAR holding the caller's
datetime.now().isoformat(); v2 stores the DATETIME(6) (repo.v2codec
ISO_LOCAL renders it back). A `now` that is not such a string is refused
(OutOfModelError). No read returns created_at.

WRITES. Bump first (skipped in a dry run). v1's column limits are checked
before each statement where v1's would have failed (1048 / 1406 with v1's
column names), then a plant longer than the v2 plant master's 8 characters
is refused (OutOfModelError; v1's plant_name VARCHAR(32) stored it). Months
and FYs are cut to CHAR(7) as MySQL cut them (_keys.fit_month / fit_fy);
missing cal_month / plant rows are created (_keys.ensure_month /
ensure_plant). The activity 'old' rows and the DELETEs are v1's own
statements, run with the raw values.
"""
from typing import Optional

import activity_context
from dbengine import Row, connect
from repo import conn as rc
from repo import version as _ver
from repo.conn import row_dict as _row_dict
from repo import _keys
from repo.v2codec import ISO_LOCAL, CodecError, parse_ts

_ORDER_V1 = ("SELECT report_month, plant_code AS plant_name, product, quality_grade, section, sort_order, "
             "order_qty, actual_despatch FROM special_steel_order")
_PK_TAIL = "product, quality_grade, section"


# ── Moved from db.py ─────────────────────────────────────────────────────────

def clear_special_steel_orders(month: str, plant: str) -> int:
    """Delete all special_steel_orders rows for a given month + plant.
    Called once before a batch insert so stale grades/products don't linger."""
    conn = connect()
    try:
        conn.row_factory = Row
        olds = [dict(r) for r in conn.execute(
            f"{_ORDER_V1} WHERE report_month=%s AND plant_code=%s ORDER BY {_PK_TAIL}", (month, plant)).fetchall()]
        conn.row_factory = None
        cur = conn.cursor()
        _ver.bump(cur)
        cur.execute("DELETE FROM special_steel_order WHERE report_month=%s AND plant_code=%s", (month, plant))
        deleted = cur.rowcount
        conn.commit()
    finally:
        conn.close()
    for old in olds:
        activity_context.record(
            f"special_steel_orders/{plant}/{old.get('product')}/{old.get('quality_grade')}/{month}",
            old, None,
        )
    return deleted


def save_special_steel_entry(month: str, plant: str, product: str, quality_grade: str,
                             sort_order: int = 0, order_qty: Optional[float] = None,
                             actual_despatch: Optional[float] = None,
                             section: str = ""):
    """Upsert one row into special_steel_orders. section stays '' for plants
    whose report has no section breakdown."""
    stored_month = _keys.fit_month(month)
    _keys.fits("report_month", stored_month, 7, nullable=False)
    _keys.fits("plant_name", plant, 32, nullable=False)
    _keys.fits("product", product, 160, nullable=False)
    _keys.fits("quality_grade", quality_grade, 160, nullable=False)
    _keys.fits("section", section or "", 160, nullable=False)
    _keys.check_month(stored_month)
    _keys.check_plant_model(plant, "plant_name", 32)
    conn = connect()
    try:
        old = _row_dict(conn, f"{_ORDER_V1} WHERE report_month=%s AND plant_code=%s AND product=%s "
                              "AND quality_grade=%s AND section=%s",
                        (month, plant, product, quality_grade, section or ""))
        cur = conn.cursor()
        _ver.bump(cur)
        _keys.ensure_month(cur, stored_month, bump=False)
        _keys.ensure_plant(cur, plant, bump=False)
        cur.execute("""
            INSERT INTO special_steel_order
                (report_month, plant_code, product, quality_grade, section,
                 sort_order, order_qty, actual_despatch)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            AS new ON DUPLICATE KEY UPDATE
                sort_order      = new.sort_order,
                order_qty       = new.order_qty,
                actual_despatch = new.actual_despatch
        """, (stored_month, plant, product, quality_grade, section or "",
              sort_order, order_qty, actual_despatch))
        conn.commit()
    finally:
        conn.close()
    new = {"report_month": month, "plant_name": plant, "product": product,
           "quality_grade": quality_grade, "section": section or "",
           "sort_order": sort_order, "order_qty": order_qty, "actual_despatch": actual_despatch}
    activity_context.record(f"special_steel_orders/{plant}/{product}/{quality_grade}/{month}", old, new)


def get_ss_phys_perf():
    """-> (meta, perf):
      meta[(plant, series)] = {capacity_kt, best_actual_kt, best_year, remark, sort_order}
      perf[(financial_year, plant, series, metric)] = value_kt
    """
    conn = connect()
    try:
        cur = conn.cursor()
        cur.execute("SELECT plant_code, series, capacity_kt, best_actual_kt, best_year, remark, sort_order "
                    "FROM special_steel_phys_meta ORDER BY plant_code, series")
        meta = {
            (p, s): {"capacity_kt": cap, "best_actual_kt": ba, "best_year": by,
                     "remark": rm, "sort_order": so or 0}
            for p, s, cap, ba, by, rm, so in cur.fetchall()
        }
        cur.execute("SELECT fy, plant_code, series, metric, value_kt FROM special_steel_phys_perf "
                    "ORDER BY fy, plant_code, series, metric")
        perf = {(fy, p, s, m): v for fy, p, s, m, v in cur.fetchall()}
    finally:
        conn.close()
    return meta, perf


def save_ss_phys_meta(rows):
    """Upsert special_steel_phys_meta rows: {plant, series, capacity_kt,
    best_actual_kt, best_year, remark, sort_order}."""
    conn = connect()
    try:
        cur = conn.cursor()
        _ver.bump(cur)
        for r in rows:
            values = (r["plant"], r["series"], r.get("capacity_kt"), r.get("best_actual_kt"),
                      r.get("best_year"), r.get("remark"), int(r.get("sort_order") or 0))
            _keys.fits("plant", values[0], 8, nullable=False)
            _keys.ensure_plant(cur, values[0], bump=False)
            cur.execute("""
                INSERT INTO special_steel_phys_meta
                    (plant_code, series, capacity_kt, best_actual_kt, best_year, remark, sort_order)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                AS new ON DUPLICATE KEY UPDATE
                    capacity_kt = new.capacity_kt, best_actual_kt = new.best_actual_kt,
                    best_year = new.best_year, remark = new.remark,
                    sort_order = new.sort_order
            """, values)
        conn.commit()
    finally:
        conn.close()
    return len(rows)


def save_ss_phys_perf(rows):
    """Upsert special_steel_phys_perf rows: {financial_year, plant, series,
    metric, value_kt}. value_kt None deletes the cell."""
    conn = connect()
    try:
        cur = conn.cursor()
        saved = 0
        _ver.bump(cur)
        for r in rows:
            key = (r["financial_year"], r["plant"], r["series"], r["metric"])
            if r.get("value_kt") is None:
                cur.execute("DELETE FROM special_steel_phys_perf WHERE fy=%s AND plant_code=%s "
                            "AND series=%s AND metric=%s", key)
            else:
                stored = (_keys.fit_fy(key[0]),) + key[1:]
                _keys.fits("financial_year", stored[0], 7, nullable=False)
                _keys.fits("plant", stored[1], 8, nullable=False)
                _keys.ensure_plant(cur, stored[1], bump=False)
                cur.execute("""
                    INSERT INTO special_steel_phys_perf
                        (fy, plant_code, series, metric, value_kt)
                    VALUES (%s, %s, %s, %s, %s)
                    AS new ON DUPLICATE KEY UPDATE value_kt = new.value_kt
                """, (*stored, r["value_kt"]))
            saved += 1
        conn.commit()
    finally:
        conn.close()
    return saved


def get_ss_ipt_requirement(financial_year):
    """-> [{item, from_plant, to_plant, plan_kt, sort_order}, ...] ordered."""
    conn = connect()
    try:
        cur = conn.cursor()
        cur.execute("""
            SELECT item, from_plant_code, to_plant_code, plan_kt, sort_order
            FROM special_steel_ipt_requirement WHERE fy=%s
            ORDER BY sort_order, item, from_plant_code, to_plant_code
        """, (financial_year,))
        rows = [{"item": i, "from_plant": f, "to_plant": t, "plan_kt": p, "sort_order": so or 0}
                for i, f, t, p, so in cur.fetchall()]
    finally:
        conn.close()
    return rows


def list_ss_ipt_requirement_fys():
    conn = connect()
    try:
        cur = conn.cursor()
        cur.execute("SELECT DISTINCT fy FROM special_steel_ipt_requirement ORDER BY fy DESC")
        fys = [r[0] for r in cur.fetchall()]
    finally:
        conn.close()
    return fys


def save_ss_ipt_requirement(financial_year, rows):
    """Upsert a batch of IPT-requirement rows for one FY. Each row:
    {item, from_plant, to_plant, plan_kt, sort_order} plus optional
    orig_item/orig_from_plant/orig_to_plant — if the natural key changed,
    the old row is deleted first (same rename handling as ipt_table)."""
    stored_fy = _keys.fit_fy(financial_year)
    conn = connect()
    try:
        cur = conn.cursor()
        saved = 0
        _ver.bump(cur)
        for r in rows:
            item = (r.get("item") or "").strip()
            frm, to = (r.get("from_plant") or "").strip(), (r.get("to_plant") or "").strip()
            if not item or not frm or not to or frm == to:
                continue
            oi, of, ot = r.get("orig_item"), r.get("orig_from_plant"), r.get("orig_to_plant")
            if oi and (oi != item or of != frm or ot != to):
                cur.execute("DELETE FROM special_steel_ipt_requirement WHERE fy=%s "
                            "AND item=%s AND from_plant_code=%s AND to_plant_code=%s",
                            (financial_year, oi, of, ot))
            plan_kt, sort_order = r.get("plan_kt"), int(r.get("sort_order") or 0)
            _keys.fits("financial_year", stored_fy, 7, nullable=False)
            _keys.fits("item", item, 64, nullable=False)
            _keys.fits("from_plant", frm, 8, nullable=False)
            _keys.fits("to_plant", to, 8, nullable=False)
            _keys.ensure_plant(cur, frm, bump=False)
            _keys.ensure_plant(cur, to, bump=False)
            cur.execute("""
                INSERT INTO special_steel_ipt_requirement
                    (fy, item, from_plant_code, to_plant_code, plan_kt, sort_order)
                VALUES (%s, %s, %s, %s, %s, %s)
                AS new ON DUPLICATE KEY UPDATE plan_kt = new.plan_kt, sort_order = new.sort_order
            """, (stored_fy, item, frm, to, plan_kt, sort_order))
            saved += 1
        conn.commit()
    finally:
        conn.close()
    return saved


def delete_ss_ipt_requirement(financial_year, item, from_plant, to_plant):
    conn = connect()
    try:
        cur = conn.cursor()
        _ver.bump(cur)
        cur.execute("DELETE FROM special_steel_ipt_requirement WHERE fy=%s AND item=%s "
                    "AND from_plant_code=%s AND to_plant_code=%s", (financial_year, item, from_plant, to_plant))
        conn.commit()
    finally:
        conn.close()


# ── Named queries ────────────────────────────────────────────────────────────
# special_steel_orders

def manual_rows(cur, month, plant):
    """fetchall() of (product, quality_grade, section, sort_order, order_qty,
    actual_despatch) for one plant/month, in manual-entry order.
    main /api/special-steel-manual."""
    cur.execute("""
            SELECT product, quality_grade, section, sort_order, order_qty, actual_despatch
            FROM special_steel_order
            WHERE report_month=%s AND plant_code=%s
            ORDER BY sort_order ASC, product ASC, quality_grade ASC, section ASC
        """, (month, plant))
    return cur.fetchall()


def fy_plant_month_sums(cur, months, plants):
    """fetchall() of (plant_name, report_month, SUM(order_qty),
    SUM(actual_despatch)) over months x plants. main _special_steel_fy_data."""
    phs = ",".join("%s" for _ in months)
    plant_phs = ",".join("%s" for _ in plants)
    cur.execute(f"""
            SELECT plant_code AS plant_name, report_month, SUM(order_qty), SUM(actual_despatch)
            FROM special_steel_order
            WHERE report_month IN ({phs}) AND plant_code IN ({plant_phs})
            GROUP BY plant_code, report_month
            ORDER BY report_month, plant_code
        """, (*months, *plants))
    return cur.fetchall()


def order_months(cur):
    """fetchall() of (report_month,), every well-formed YYYY-MM month with a
    special_steel_orders row. main /api/special-steel-fys."""
    cur.execute("""
        SELECT DISTINCT report_month FROM special_steel_order
        WHERE report_month REGEXP '^[0-9][0-9][0-9][0-9]-[0-9][0-9]$'
        ORDER BY report_month
    """)
    return cur.fetchall()


def products_for_plant(cur, plant):
    """fetchall() of (product,) ever recorded for a plant.
    api_special_steel_clubs /products."""
    cur.execute(
        "SELECT DISTINCT product FROM special_steel_order WHERE plant_code=%s ORDER BY product",
        (plant,),
    )
    return cur.fetchall()


def grades_for_product(cur, plant, product):
    """fetchall() of (quality_grade,), non-blank, for a plant/product.
    api_special_steel_clubs /grades."""
    cur.execute(
        "SELECT DISTINCT quality_grade FROM special_steel_order "
        "WHERE plant_code=%s AND product=%s AND quality_grade != '' ORDER BY quality_grade",
        (plant, product),
    )
    return cur.fetchall()


def group_rows(cur, month, plant, product):
    """page_special_steel._fetch_group."""
    cur.execute("""
        SELECT quality_grade, section, order_qty, actual_despatch
        FROM special_steel_order
        WHERE report_month=%s AND plant_code=%s AND product=%s
        ORDER BY sort_order, quality_grade, section
    """, (month, plant, product))
    return cur.fetchall()


def all_grade_rows(cur, all_months, plant, product):
    """fetchall() of (quality_grade, section, MIN(sort_order)).
    page_special_steel._fetch_all_grades."""
    ph = ",".join(["%s"] * len(all_months))
    cur.execute(f"""
        SELECT quality_grade, section, MIN(sort_order)
        FROM special_steel_order
        WHERE report_month IN ({ph}) AND plant_code=%s AND product=%s
        GROUP BY quality_grade, section
        ORDER BY MIN(sort_order), quality_grade, section
    """, (*all_months, plant, product))
    return cur.fetchall()


def cply_rows(cur, cply_month, plant, product):
    """fetchall() of (quality_grade, section, actual_despatch).
    page_special_steel._fetch_cply."""
    cur.execute("""
        SELECT quality_grade, section, actual_despatch
        FROM special_steel_order
        WHERE report_month=%s AND plant_code=%s AND product=%s
        ORDER BY quality_grade, section
    """, (cply_month, plant, product))
    return cur.fetchall()


def group_ytd_rows(cur, ytd_months, plant, product):
    """page_special_steel._fetch_group_ytd."""
    ph = ",".join(["%s"] * len(ytd_months))
    cur.execute(f"""
        SELECT quality_grade, section,
               COALESCE(SUM(order_qty),0),
               COALESCE(SUM(actual_despatch),0)
        FROM special_steel_order
        WHERE report_month IN ({ph}) AND plant_code=%s AND product=%s
        GROUP BY quality_grade, section
        ORDER BY MIN(report_month), quality_grade, section
    """, (*ytd_months, plant, product))
    return cur.fetchall()


def cply_ytd_rows(cur, cply_ytd_months, plant, product):
    """page_special_steel._fetch_cply_ytd."""
    ph = ",".join(["%s"] * len(cply_ytd_months))
    cur.execute(f"""
        SELECT quality_grade, section, COALESCE(SUM(actual_despatch),0)
        FROM special_steel_order
        WHERE report_month IN ({ph}) AND plant_code=%s AND product=%s
        GROUP BY quality_grade, section
        ORDER BY MIN(report_month), quality_grade, section
    """, (*cply_ytd_months, plant, product))
    return cur.fetchall()


# ISP summary (page_special_steel, one row per ISP mill product)

def isp_month_row(cur, month, mill):
    """fetchone() of (order_qty, actual_despatch) for one ISP product/month."""
    cur.execute("""
                SELECT order_qty, actual_despatch FROM special_steel_order
                WHERE report_month=%s AND plant_code='ISP' AND product=%s
                ORDER BY quality_grade, section
            """, (month, mill))
    return cur.fetchone()


def isp_actual_row(cur, month, mill):
    """fetchone() of (actual_despatch,) for one ISP product/month."""
    cur.execute("""
                SELECT actual_despatch FROM special_steel_order
                WHERE report_month=%s AND plant_code='ISP' AND product=%s
                ORDER BY quality_grade, section
            """, (month, mill))
    return cur.fetchone()


def isp_ytd_sums_row(cur, months, mill):
    """fetchone() of (SUM(order_qty), SUM(actual_despatch)), COALESCEd to 0,
    for one ISP product over months."""
    ph_ytd = ",".join(["%s"] * len(months))
    cur.execute(f"""
                SELECT COALESCE(SUM(order_qty),0), COALESCE(SUM(actual_despatch),0)
                FROM special_steel_order
                WHERE report_month IN ({ph_ytd}) AND plant_code='ISP' AND product=%s
            """, (*months, mill))
    return cur.fetchone()


def isp_actual_sum_row(cur, months, mill):
    """fetchone() of (SUM(actual_despatch),), COALESCEd to 0, for one ISP
    product over months."""
    ph_cytd = ",".join(["%s"] * len(months))
    cur.execute(f"""
                SELECT COALESCE(SUM(actual_despatch),0)
                FROM special_steel_order
                WHERE report_month IN ({ph_cytd}) AND plant_code='ISP' AND product=%s
            """, (*months, mill))
    return cur.fetchone()


# SAIL summary (page_special_steel generate_special_steel_sail)

def plant_month_sums_row(cur, month, plant):
    """fetchone() of (SUM(order_qty), SUM(actual_despatch)), COALESCEd to 0."""
    cur.execute("""
                SELECT COALESCE(SUM(order_qty),0), COALESCE(SUM(actual_despatch),0)
                FROM special_steel_order WHERE report_month=%s AND plant_code=%s
            """, (month, plant))
    return cur.fetchone()


def plant_month_actual_row(cur, month, plant):
    """fetchone() of (SUM(actual_despatch),), COALESCEd to 0."""
    cur.execute("""
                SELECT COALESCE(SUM(actual_despatch),0)
                FROM special_steel_order WHERE report_month=%s AND plant_code=%s
            """, (month, plant))
    return cur.fetchone()


def plant_months_sums_row(cur, months, plant):
    """fetchone() of (SUM(order_qty), SUM(actual_despatch)) over months,
    COALESCEd to 0."""
    ph_ytd = ",".join(["%s"] * len(months))
    cur.execute(f"""
                SELECT COALESCE(SUM(order_qty),0), COALESCE(SUM(actual_despatch),0)
                FROM special_steel_order WHERE report_month IN ({ph_ytd}) AND plant_code=%s
            """, (*months, plant))
    return cur.fetchone()


def plant_months_actual_row(cur, months, plant):
    """fetchone() of (SUM(actual_despatch),) over months, COALESCEd to 0."""
    ph_cytd = ",".join(["%s"] * len(months))
    cur.execute(f"""
                SELECT COALESCE(SUM(actual_despatch),0)
                FROM special_steel_order WHERE report_month IN ({ph_cytd}) AND plant_code=%s
            """, (*months, plant))
    return cur.fetchone()


def ssps_order_row(cur, month):
    """fetchone() of (SUM(order_qty),) for plant_name='SSPs', COALESCEd to 0."""
    cur.execute("""
            SELECT COALESCE(SUM(order_qty),0) FROM special_steel_order
            WHERE report_month=%s AND plant_code='SSPs'
        """, (month,))
    return cur.fetchone()


def ssps_order_months_row(cur, months):
    """fetchone() of (SUM(order_qty),) for plant_name='SSPs' over months,
    COALESCEd to 0."""
    ph_ytd = ",".join(["%s"] * len(months))
    cur.execute(f"""
            SELECT COALESCE(SUM(order_qty),0) FROM special_steel_order
            WHERE report_month IN ({ph_ytd}) AND plant_code='SSPs'
        """, (*months,))
    return cur.fetchone()


def product_actual_sums(cur, months, plant):
    """fetchall() of (product, SUM(actual_despatch)) over months, COALESCEd
    to 0. page_special_steel_donut."""
    ph = ",".join(["%s"] * len(months))
    cur.execute(f"""
        SELECT product, COALESCE(SUM(actual_despatch),0)
        FROM special_steel_order
        WHERE report_month IN ({ph}) AND plant_code=%s
        GROUP BY product
        ORDER BY MIN(report_month), product
    """, (*months, plant))
    return cur.fetchall()


def actual_sum_count_row(cur, months, plant):
    """fetchone() of (SUM(actual_despatch) COALESCEd to 0, COUNT(*)) over
    months. page_special_steel_trend._sum_actual."""
    ph = ",".join(["%s"] * len(months))
    cur.execute(f"""
            SELECT COALESCE(SUM(actual_despatch),0), COUNT(*)
            FROM special_steel_order WHERE report_month IN ({ph}) AND plant_code=%s
        """, (*months, plant))
    return cur.fetchone()


def rsp_prior_grade_rows(cur, db_month):
    """fetchall() of (product, quality_grade, report_month) for RSP months
    before db_month, oldest first. excel_extractor_rsp._rsp_ss_grade_case_map."""
    cur.execute("""
            SELECT product, quality_grade, report_month
            FROM special_steel_order
            WHERE plant_code='RSP' AND report_month < %s
            ORDER BY report_month, product, quality_grade, section
        """, (db_month,))
    return cur.fetchall()


def despatch_rows(cur, plants, months):
    """fetchall() of (plant_name, report_month, product, quality_grade,
    section, actual_despatch) over plants x months.
    scripts/backfill_special_steel_2022_23.current_db_values."""
    ph_p = ",".join(["%s"] * len(plants))
    ph_m = ",".join(["%s"] * len(months))
    cur.execute(
        f"SELECT plant_code AS plant_name, report_month, product, quality_grade, section, actual_despatch "
        f"FROM special_steel_order WHERE plant_code IN ({ph_p}) AND report_month IN ({ph_m}) "
        f"ORDER BY report_month, plant_code, product, quality_grade, section",
        (*plants, *months),
    )
    return cur.fetchall()


def plants_for_month(report_month):
    """{plant_name} with any special_steel_orders row for the month.
    page_missing_data."""
    with rc.cursor() as cur:
        cur.execute("SELECT DISTINCT plant_code FROM special_steel_order WHERE report_month = %s",
                    [report_month])
        return {r[0] for r in cur.fetchall()}


# special_steel_abp_table

def abp_rows(cur, months):
    """fetchall() of (plant_name, report_month, abp_qty) over months.
    main GET /api/special-steel-abp."""
    ph = ",".join(["%s"] * len(months))
    cur.execute(f"""
            SELECT plant_code AS plant_name, report_month, abp_qty
            FROM special_steel_abp
            WHERE report_month IN ({ph})
            ORDER BY report_month, plant_code
        """, tuple(months))
    return cur.fetchall()


def upsert_abp(cur, report_month, plant_name, abp_qty):
    """Upsert one ABP cell on the caller's cursor; the caller commits.
    main POST /api/special-steel-abp."""
    stored_month = _keys.fit_month(report_month)
    _keys.fits("report_month", stored_month, 7, nullable=False)
    _keys.fits("plant_name", plant_name, 32, nullable=False)
    _keys.check_month(stored_month)
    _keys.check_plant_model(plant_name, "plant_name", 32)
    _ver.bump(cur)
    _keys.ensure_month(cur, stored_month, bump=False)
    _keys.ensure_plant(cur, plant_name, bump=False)
    cur.execute("""
                INSERT INTO special_steel_abp (report_month, plant_code, abp_qty)
                VALUES (%s, %s, %s)
                AS new ON DUPLICATE KEY UPDATE abp_qty = new.abp_qty
            """, (stored_month, plant_name, abp_qty))


def abp_sum_row(cur, months, plant):
    """fetchone() of (SUM(abp_qty),) over months, COALESCEd to 0.
    page_special_steel._get_abp_sum."""
    ph = ",".join(["%s"] * len(months))
    cur.execute(f"""
        SELECT COALESCE(SUM(abp_qty),0)
        FROM special_steel_abp
        WHERE report_month IN ({ph}) AND plant_code=%s
    """, (*months, plant))
    return cur.fetchone()


def abp_any_row(report_month):
    """True when special_steel_abp_table has any row for the month.
    page_missing_data."""
    with rc.cursor() as cur:
        cur.execute("SELECT 1 FROM special_steel_abp WHERE report_month = %s LIMIT 1",
                    [report_month])
        return bool(cur.fetchall())


# special_steel_grade_clubs

def club_rows(cur, plant, product):
    """fetchall() of (quality_grade, club_label) for a plant/product.
    api_special_steel_clubs /grades."""
    cur.execute(
        "SELECT quality_grade, club_label FROM special_steel_grade_club "
        "WHERE plant_code=%s AND product=%s ORDER BY quality_grade",
        (plant, product),
    )
    return cur.fetchall()


def ordered_club_rows(cur, plant, product):
    """fetchall() of (quality_grade, club_label) ordered by label, grade.
    page_special_steel._resolve_clubs."""
    cur.execute(
        "SELECT quality_grade, club_label FROM special_steel_grade_club "
        "WHERE plant_code=%s AND product=%s ORDER BY club_label, quality_grade",
        (plant, product),
    )
    return cur.fetchall()


def upsert_grade_club(cur, plant, product, grade, label, now):
    """Put one grade in a club on the caller's cursor; the caller commits."""
    _keys.fits("plant_name", plant, 32, nullable=False)
    _keys.fits("product", product, 160, nullable=False)
    _keys.fits("quality_grade", grade, 160, nullable=False)
    _keys.fits("club_label", label, 200, nullable=False)
    _keys.fits("created_at", now, 40)
    _keys.check_plant_model(plant, "plant_name", 32)
    try:
        created_at = parse_ts(ISO_LOCAL, now)
    except CodecError:
        raise _keys.OutOfModelError(f"grade club created_at {now!r}: v1 stored it as text, the v2 DATETIME "
                                    "holds only a datetime.now().isoformat() value") from None
    _ver.bump(cur)
    _keys.ensure_plant(cur, plant, bump=False)
    cur.execute("""
            INSERT INTO special_steel_grade_club (plant_code, product, quality_grade, club_label, created_at)
            VALUES (%s, %s, %s, %s, %s)
            AS new ON DUPLICATE KEY UPDATE club_label=new.club_label
        """, (plant, product, grade, label, created_at))


def club_member_rows(cur, plant, product, label):
    """fetchall() of (quality_grade,) in one club."""
    cur.execute(
        "SELECT quality_grade FROM special_steel_grade_club WHERE plant_code=%s AND product=%s AND club_label=%s "
        "ORDER BY quality_grade",
        (plant, product, label),
    )
    return cur.fetchall()


def delete_club(cur, plant, product, label):
    """Delete every member of one club on the caller's cursor; the caller commits."""
    _ver.bump(cur)
    cur.execute(
        "DELETE FROM special_steel_grade_club WHERE plant_code=%s AND product=%s AND club_label=%s",
        (plant, product, label),
    )


def grade_club_row(cur, plant, product, grade):
    """fetchone() of (club_label,) for one grade, or None."""
    cur.execute(
        "SELECT club_label FROM special_steel_grade_club WHERE plant_code=%s AND product=%s AND quality_grade=%s",
        (plant, product, grade),
    )
    return cur.fetchone()


def delete_grade_club(cur, plant, product, grade):
    """Remove one grade from its club on the caller's cursor; the caller commits."""
    _ver.bump(cur)
    cur.execute(
        "DELETE FROM special_steel_grade_club WHERE plant_code=%s AND product=%s AND quality_grade=%s",
        (plant, product, grade),
    )
