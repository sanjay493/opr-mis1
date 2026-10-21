"""Special steel repository: special_steel_orders (monthly order book /
despatch per plant, product, grade, section), special_steel_abp_table
(monthly special-steel ABP per plant), special_steel_grade_clubs (grade
clubbing for the Special Steel page), and the Special Steel Plants Physical
Performance tables special_steel_phys_perf / special_steel_phys_meta /
special_steel_ipt_requirement.

The db.py functions moved here verbatim (re-exported from db.py). The named
cursor-level queries further down are the statements that used to live
inline in main.py / api_special_steel_clubs.py / page_*.py / extractors /
scripts, moved verbatim: each runs on the caller's cursor (so the caller's
connection, transaction and row type are unchanged) and returns the plain
fetchone() / fetchall() result.
"""
from typing import Optional

import activity_context
from dbengine import Row, connect
from repo import version as _ver
from repo import conn as rc
from repo.conn import row_dict as _row_dict


# ── Moved from db.py ─────────────────────────────────────────────────────────

def clear_special_steel_orders(month: str, plant: str) -> int:
    """Delete all special_steel_orders rows for a given month + plant.
    Called once before a batch insert so stale grades/products don't linger."""
    conn = connect()
    conn.row_factory = Row
    old_rows = conn.execute(
        "SELECT * FROM special_steel_orders WHERE report_month=%s AND plant_name=%s",
        (month, plant),
    )
    olds = [dict(r) for r in old_rows.fetchall()]
    conn.row_factory = None
    _ver.bump(conn)
    cur = conn.execute(
        "DELETE FROM special_steel_orders WHERE report_month=%s AND plant_name=%s",
        (month, plant),
    )
    deleted = cur.rowcount
    conn.commit()
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
    conn = connect()
    old = _row_dict(conn,
        "SELECT * FROM special_steel_orders WHERE report_month=%s AND plant_name=%s AND product=%s AND quality_grade=%s AND section=%s",
        (month, plant, product, quality_grade, section or ""))
    _ver.bump(conn)
    conn.execute("""
        INSERT INTO special_steel_orders
            (report_month, plant_name, product, quality_grade, section,
             sort_order, order_qty, actual_despatch)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        AS new ON DUPLICATE KEY UPDATE
            sort_order      = new.sort_order,
            order_qty       = new.order_qty,
            actual_despatch = new.actual_despatch
    """, (month, plant, product, quality_grade, section or "",
          sort_order, order_qty, actual_despatch))
    conn.commit()
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
    cur = conn.cursor()
    cur.execute("SELECT plant, series, capacity_kt, best_actual_kt, best_year, remark, sort_order "
                "FROM special_steel_phys_meta")
    meta = {
        (p, s): {"capacity_kt": cap, "best_actual_kt": ba, "best_year": by,
                 "remark": rm, "sort_order": so or 0}
        for p, s, cap, ba, by, rm, so in cur.fetchall()
    }
    cur.execute("SELECT financial_year, plant, series, metric, value_kt FROM special_steel_phys_perf")
    perf = {(fy, p, s, m): v for fy, p, s, m, v in cur.fetchall()}
    conn.close()
    return meta, perf


def save_ss_phys_meta(rows):
    """Upsert special_steel_phys_meta rows: {plant, series, capacity_kt,
    best_actual_kt, best_year, remark, sort_order}."""
    conn = connect()
    cur = conn.cursor()
    _ver.bump(conn)
    for r in rows:
        cur.execute("""
            INSERT INTO special_steel_phys_meta
                (plant, series, capacity_kt, best_actual_kt, best_year, remark, sort_order)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            AS new ON DUPLICATE KEY UPDATE
                capacity_kt = new.capacity_kt, best_actual_kt = new.best_actual_kt,
                best_year = new.best_year, remark = new.remark,
                sort_order = new.sort_order
        """, (r["plant"], r["series"], r.get("capacity_kt"), r.get("best_actual_kt"),
              r.get("best_year"), r.get("remark"), int(r.get("sort_order") or 0)))
    conn.commit()
    conn.close()
    return len(rows)


def save_ss_phys_perf(rows):
    """Upsert special_steel_phys_perf rows: {financial_year, plant, series,
    metric, value_kt}. value_kt None deletes the cell."""
    conn = connect()
    cur = conn.cursor()
    saved = 0
    _ver.bump(conn)
    for r in rows:
        key = (r["financial_year"], r["plant"], r["series"], r["metric"])
        if r.get("value_kt") is None:
            cur.execute("DELETE FROM special_steel_phys_perf WHERE financial_year=%s AND plant=%s "
                        "AND series=%s AND metric=%s", key)
        else:
            cur.execute("""
                INSERT INTO special_steel_phys_perf
                    (financial_year, plant, series, metric, value_kt)
                VALUES (%s, %s, %s, %s, %s)
                AS new ON DUPLICATE KEY UPDATE value_kt = new.value_kt
            """, (*key, r["value_kt"]))
        saved += 1
    conn.commit()
    conn.close()
    return saved


def get_ss_ipt_requirement(financial_year):
    """-> [{item, from_plant, to_plant, plan_kt, sort_order}, ...] ordered."""
    conn = connect()
    cur = conn.cursor()
    cur.execute("""
        SELECT item, from_plant, to_plant, plan_kt, sort_order
        FROM special_steel_ipt_requirement WHERE financial_year=%s
        ORDER BY sort_order, item, from_plant, to_plant
    """, (financial_year,))
    rows = [{"item": i, "from_plant": f, "to_plant": t, "plan_kt": p, "sort_order": so or 0}
            for i, f, t, p, so in cur.fetchall()]
    conn.close()
    return rows


def list_ss_ipt_requirement_fys():
    conn = connect()
    cur = conn.cursor()
    cur.execute("SELECT DISTINCT financial_year FROM special_steel_ipt_requirement "
                "ORDER BY financial_year DESC")
    fys = [r[0] for r in cur.fetchall()]
    conn.close()
    return fys


def save_ss_ipt_requirement(financial_year, rows):
    """Upsert a batch of IPT-requirement rows for one FY. Each row:
    {item, from_plant, to_plant, plan_kt, sort_order} plus optional
    orig_item/orig_from_plant/orig_to_plant — if the natural key changed,
    the old row is deleted first (same rename handling as ipt_table)."""
    conn = connect()
    cur = conn.cursor()
    saved = 0
    _ver.bump(conn)
    for r in rows:
        item = (r.get("item") or "").strip()
        frm, to = (r.get("from_plant") or "").strip(), (r.get("to_plant") or "").strip()
        if not item or not frm or not to or frm == to:
            continue
        oi, of, ot = r.get("orig_item"), r.get("orig_from_plant"), r.get("orig_to_plant")
        if oi and (oi != item or of != frm or ot != to):
            cur.execute("DELETE FROM special_steel_ipt_requirement WHERE financial_year=%s "
                        "AND item=%s AND from_plant=%s AND to_plant=%s", (financial_year, oi, of, ot))
        cur.execute("""
            INSERT INTO special_steel_ipt_requirement
                (financial_year, item, from_plant, to_plant, plan_kt, sort_order)
            VALUES (%s, %s, %s, %s, %s, %s)
            AS new ON DUPLICATE KEY UPDATE plan_kt = new.plan_kt, sort_order = new.sort_order
        """, (financial_year, item, frm, to, r.get("plan_kt"), int(r.get("sort_order") or 0)))
        saved += 1
    conn.commit()
    conn.close()
    return saved


def delete_ss_ipt_requirement(financial_year, item, from_plant, to_plant):
    conn = connect()
    cur = conn.cursor()
    _ver.bump(conn)
    cur.execute("DELETE FROM special_steel_ipt_requirement WHERE financial_year=%s AND item=%s "
                "AND from_plant=%s AND to_plant=%s", (financial_year, item, from_plant, to_plant))
    conn.commit()
    conn.close()


# ── Named queries (moved verbatim from callers) ──────────────────────────────
# special_steel_orders

def manual_rows(cur, month, plant):
    """fetchall() of (product, quality_grade, section, sort_order, order_qty,
    actual_despatch) for one plant/month, in manual-entry order.
    main /api/special-steel-manual."""
    cur.execute("""
            SELECT product, quality_grade, section, sort_order, order_qty, actual_despatch
            FROM special_steel_orders
            WHERE report_month=%s AND plant_name=%s
            ORDER BY sort_order ASC, product ASC, quality_grade ASC
        """, (month, plant))
    return cur.fetchall()


def fy_plant_month_sums(cur, months, plants):
    """fetchall() of (plant_name, report_month, SUM(order_qty),
    SUM(actual_despatch)) over months x plants. main _special_steel_fy_data."""
    phs = ",".join("%s" for _ in months)
    plant_phs = ",".join("%s" for _ in plants)
    cur.execute(f"""
            SELECT plant_name, report_month, SUM(order_qty), SUM(actual_despatch)
            FROM special_steel_orders
            WHERE report_month IN ({phs}) AND plant_name IN ({plant_phs})
            GROUP BY plant_name, report_month
        """, (*months, *plants))
    return cur.fetchall()


def order_months(cur):
    """fetchall() of (report_month,), every well-formed YYYY-MM month with a
    special_steel_orders row. main /api/special-steel-fys."""
    cur.execute("""
        SELECT DISTINCT report_month FROM special_steel_orders
        WHERE report_month REGEXP '^[0-9][0-9][0-9][0-9]-[0-9][0-9]$'
    """)
    return cur.fetchall()


def products_for_plant(cur, plant):
    """fetchall() of (product,) ever recorded for a plant.
    api_special_steel_clubs /products."""
    cur.execute(
        "SELECT DISTINCT product FROM special_steel_orders WHERE plant_name=%s ORDER BY product",
        (plant,),
    )
    return cur.fetchall()


def grades_for_product(cur, plant, product):
    """fetchall() of (quality_grade,), non-blank, for a plant/product.
    api_special_steel_clubs /grades."""
    cur.execute(
        "SELECT DISTINCT quality_grade FROM special_steel_orders "
        "WHERE plant_name=%s AND product=%s AND quality_grade != '' ORDER BY quality_grade",
        (plant, product),
    )
    return cur.fetchall()


def group_rows(cur, month, plant, product):
    """page_special_steel._fetch_group."""
    cur.execute("""
        SELECT quality_grade, section, order_qty, actual_despatch
        FROM special_steel_orders
        WHERE report_month=%s AND plant_name=%s AND product=%s
        ORDER BY sort_order, quality_grade, section
    """, (month, plant, product))
    return cur.fetchall()


def all_grade_rows(cur, all_months, plant, product):
    """fetchall() of (quality_grade, section, MIN(sort_order)).
    page_special_steel._fetch_all_grades."""
    ph = ",".join(["%s"] * len(all_months))
    cur.execute(f"""
        SELECT quality_grade, section, MIN(sort_order)
        FROM special_steel_orders
        WHERE report_month IN ({ph}) AND plant_name=%s AND product=%s
        GROUP BY quality_grade, section
        ORDER BY MIN(sort_order), quality_grade, section
    """, (*all_months, plant, product))
    return cur.fetchall()


def cply_rows(cur, cply_month, plant, product):
    """fetchall() of (quality_grade, section, actual_despatch).
    page_special_steel._fetch_cply."""
    cur.execute("""
        SELECT quality_grade, section, actual_despatch
        FROM special_steel_orders
        WHERE report_month=%s AND plant_name=%s AND product=%s
    """, (cply_month, plant, product))
    return cur.fetchall()


def group_ytd_rows(cur, ytd_months, plant, product):
    """page_special_steel._fetch_group_ytd."""
    ph = ",".join(["%s"] * len(ytd_months))
    cur.execute(f"""
        SELECT quality_grade, section,
               COALESCE(SUM(order_qty),0),
               COALESCE(SUM(actual_despatch),0)
        FROM special_steel_orders
        WHERE report_month IN ({ph}) AND plant_name=%s AND product=%s
        GROUP BY quality_grade, section
    """, (*ytd_months, plant, product))
    return cur.fetchall()


def cply_ytd_rows(cur, cply_ytd_months, plant, product):
    """page_special_steel._fetch_cply_ytd."""
    ph = ",".join(["%s"] * len(cply_ytd_months))
    cur.execute(f"""
        SELECT quality_grade, section, COALESCE(SUM(actual_despatch),0)
        FROM special_steel_orders
        WHERE report_month IN ({ph}) AND plant_name=%s AND product=%s
        GROUP BY quality_grade, section
    """, (*cply_ytd_months, plant, product))
    return cur.fetchall()


# ISP summary (page_special_steel, one row per ISP mill product)

def isp_month_row(cur, month, mill):
    """fetchone() of (order_qty, actual_despatch) for one ISP product/month."""
    cur.execute("""
                SELECT order_qty, actual_despatch FROM special_steel_orders
                WHERE report_month=%s AND plant_name='ISP' AND product=%s
            """, (month, mill))
    return cur.fetchone()


def isp_actual_row(cur, month, mill):
    """fetchone() of (actual_despatch,) for one ISP product/month."""
    cur.execute("""
                SELECT actual_despatch FROM special_steel_orders
                WHERE report_month=%s AND plant_name='ISP' AND product=%s
            """, (month, mill))
    return cur.fetchone()


def isp_ytd_sums_row(cur, months, mill):
    """fetchone() of (SUM(order_qty), SUM(actual_despatch)), COALESCEd to 0,
    for one ISP product over months."""
    ph_ytd = ",".join(["%s"] * len(months))
    cur.execute(f"""
                SELECT COALESCE(SUM(order_qty),0), COALESCE(SUM(actual_despatch),0)
                FROM special_steel_orders
                WHERE report_month IN ({ph_ytd}) AND plant_name='ISP' AND product=%s
            """, (*months, mill))
    return cur.fetchone()


def isp_actual_sum_row(cur, months, mill):
    """fetchone() of (SUM(actual_despatch),), COALESCEd to 0, for one ISP
    product over months."""
    ph_cytd = ",".join(["%s"] * len(months))
    cur.execute(f"""
                SELECT COALESCE(SUM(actual_despatch),0)
                FROM special_steel_orders
                WHERE report_month IN ({ph_cytd}) AND plant_name='ISP' AND product=%s
            """, (*months, mill))
    return cur.fetchone()


# SAIL summary (page_special_steel generate_special_steel_sail)

def plant_month_sums_row(cur, month, plant):
    """fetchone() of (SUM(order_qty), SUM(actual_despatch)), COALESCEd to 0."""
    cur.execute("""
                SELECT COALESCE(SUM(order_qty),0), COALESCE(SUM(actual_despatch),0)
                FROM special_steel_orders WHERE report_month=%s AND plant_name=%s
            """, (month, plant))
    return cur.fetchone()


def plant_month_actual_row(cur, month, plant):
    """fetchone() of (SUM(actual_despatch),), COALESCEd to 0."""
    cur.execute("""
                SELECT COALESCE(SUM(actual_despatch),0)
                FROM special_steel_orders WHERE report_month=%s AND plant_name=%s
            """, (month, plant))
    return cur.fetchone()


def plant_months_sums_row(cur, months, plant):
    """fetchone() of (SUM(order_qty), SUM(actual_despatch)) over months,
    COALESCEd to 0."""
    ph_ytd = ",".join(["%s"] * len(months))
    cur.execute(f"""
                SELECT COALESCE(SUM(order_qty),0), COALESCE(SUM(actual_despatch),0)
                FROM special_steel_orders WHERE report_month IN ({ph_ytd}) AND plant_name=%s
            """, (*months, plant))
    return cur.fetchone()


def plant_months_actual_row(cur, months, plant):
    """fetchone() of (SUM(actual_despatch),) over months, COALESCEd to 0."""
    ph_cytd = ",".join(["%s"] * len(months))
    cur.execute(f"""
                SELECT COALESCE(SUM(actual_despatch),0)
                FROM special_steel_orders WHERE report_month IN ({ph_cytd}) AND plant_name=%s
            """, (*months, plant))
    return cur.fetchone()


def ssps_order_row(cur, month):
    """fetchone() of (SUM(order_qty),) for plant_name='SSPs', COALESCEd to 0."""
    cur.execute("""
            SELECT COALESCE(SUM(order_qty),0) FROM special_steel_orders
            WHERE report_month=%s AND plant_name='SSPs'
        """, (month,))
    return cur.fetchone()


def ssps_order_months_row(cur, months):
    """fetchone() of (SUM(order_qty),) for plant_name='SSPs' over months,
    COALESCEd to 0."""
    ph_ytd = ",".join(["%s"] * len(months))
    cur.execute(f"""
            SELECT COALESCE(SUM(order_qty),0) FROM special_steel_orders
            WHERE report_month IN ({ph_ytd}) AND plant_name='SSPs'
        """, (*months,))
    return cur.fetchone()


def product_actual_sums(cur, months, plant):
    """fetchall() of (product, SUM(actual_despatch)) over months, COALESCEd
    to 0. page_special_steel_donut."""
    ph = ",".join(["%s"] * len(months))
    cur.execute(f"""
        SELECT product, COALESCE(SUM(actual_despatch),0)
        FROM special_steel_orders
        WHERE report_month IN ({ph}) AND plant_name=%s
        GROUP BY product
    """, (*months, plant))
    return cur.fetchall()


def actual_sum_count_row(cur, months, plant):
    """fetchone() of (SUM(actual_despatch) COALESCEd to 0, COUNT(*)) over
    months. page_special_steel_trend._sum_actual."""
    ph = ",".join(["%s"] * len(months))
    cur.execute(f"""
            SELECT COALESCE(SUM(actual_despatch),0), COUNT(*)
            FROM special_steel_orders WHERE report_month IN ({ph}) AND plant_name=%s
        """, (*months, plant))
    return cur.fetchone()


def rsp_prior_grade_rows(cur, db_month):
    """fetchall() of (product, quality_grade, report_month) for RSP months
    before db_month, oldest first. excel_extractor_rsp._rsp_ss_grade_case_map."""
    cur.execute("""
            SELECT product, quality_grade, report_month
            FROM special_steel_orders
            WHERE plant_name='RSP' AND report_month < %s
            ORDER BY report_month
        """, (db_month,))
    return cur.fetchall()


def despatch_rows(cur, plants, months):
    """fetchall() of (plant_name, report_month, product, quality_grade,
    section, actual_despatch) over plants x months.
    scripts/backfill_special_steel_2022_23.current_db_values."""
    ph_p = ",".join(["%s"] * len(plants))
    ph_m = ",".join(["%s"] * len(months))
    cur.execute(
        f"SELECT plant_name, report_month, product, quality_grade, section, actual_despatch "
        f"FROM special_steel_orders WHERE plant_name IN ({ph_p}) AND report_month IN ({ph_m})",
        (*plants, *months),
    )
    return cur.fetchall()


def plants_for_month(report_month):
    """{plant_name} with any special_steel_orders row for the month.
    page_missing_data."""
    with rc.cursor() as cur:
        cur.execute("SELECT DISTINCT plant_name FROM special_steel_orders WHERE report_month = %s",
                    [report_month])
        return {r[0] for r in cur.fetchall()}


# special_steel_abp_table

def abp_rows(cur, months):
    """fetchall() of (plant_name, report_month, abp_qty) over months.
    main GET /api/special-steel-abp."""
    ph = ",".join(["%s"] * len(months))
    cur.execute(f"""
            SELECT plant_name, report_month, abp_qty
            FROM special_steel_abp_table
            WHERE report_month IN ({ph})
        """, tuple(months))
    return cur.fetchall()


def upsert_abp(cur, report_month, plant_name, abp_qty):
    """Upsert one ABP cell on the caller's cursor; the caller commits.
    main POST /api/special-steel-abp."""
    _ver.bump(cur)
    cur.execute("""
                INSERT INTO special_steel_abp_table (report_month, plant_name, abp_qty)
                VALUES (%s, %s, %s)
                AS new ON DUPLICATE KEY UPDATE abp_qty = new.abp_qty
            """, (report_month, plant_name, abp_qty))


def abp_sum_row(cur, months, plant):
    """fetchone() of (SUM(abp_qty),) over months, COALESCEd to 0.
    page_special_steel._get_abp_sum."""
    ph = ",".join(["%s"] * len(months))
    cur.execute(f"""
        SELECT COALESCE(SUM(abp_qty),0)
        FROM special_steel_abp_table
        WHERE report_month IN ({ph}) AND plant_name=%s
    """, (*months, plant))
    return cur.fetchone()


def abp_any_row(report_month):
    """True when special_steel_abp_table has any row for the month.
    page_missing_data."""
    with rc.cursor() as cur:
        cur.execute("SELECT 1 FROM special_steel_abp_table WHERE report_month = %s LIMIT 1",
                    [report_month])
        return bool(cur.fetchall())


# special_steel_grade_clubs

def club_rows(cur, plant, product):
    """fetchall() of (quality_grade, club_label) for a plant/product.
    api_special_steel_clubs /grades."""
    cur.execute(
        "SELECT quality_grade, club_label FROM special_steel_grade_clubs "
        "WHERE plant_name=%s AND product=%s",
        (plant, product),
    )
    return cur.fetchall()


def ordered_club_rows(cur, plant, product):
    """fetchall() of (quality_grade, club_label) ordered by label, grade.
    page_special_steel._resolve_clubs."""
    cur.execute(
        "SELECT quality_grade, club_label FROM special_steel_grade_clubs "
        "WHERE plant_name=%s AND product=%s ORDER BY club_label, quality_grade",
        (plant, product),
    )
    return cur.fetchall()


def upsert_grade_club(cur, plant, product, grade, label, now):
    """Put one grade in a club on the caller's cursor; the caller commits."""
    _ver.bump(cur)
    cur.execute("""
            INSERT INTO special_steel_grade_clubs (plant_name, product, quality_grade, club_label, created_at)
            VALUES (%s, %s, %s, %s, %s)
            AS new ON DUPLICATE KEY UPDATE club_label=new.club_label
        """, (plant, product, grade, label, now))


def club_member_rows(cur, plant, product, label):
    """fetchall() of (quality_grade,) in one club."""
    cur.execute(
        "SELECT quality_grade FROM special_steel_grade_clubs WHERE plant_name=%s AND product=%s AND club_label=%s",
        (plant, product, label),
    )
    return cur.fetchall()


def delete_club(cur, plant, product, label):
    """Delete every member of one club on the caller's cursor; the caller commits."""
    _ver.bump(cur)
    cur.execute(
        "DELETE FROM special_steel_grade_clubs WHERE plant_name=%s AND product=%s AND club_label=%s",
        (plant, product, label),
    )


def grade_club_row(cur, plant, product, grade):
    """fetchone() of (club_label,) for one grade, or None."""
    cur.execute(
        "SELECT club_label FROM special_steel_grade_clubs WHERE plant_name=%s AND product=%s AND quality_grade=%s",
        (plant, product, grade),
    )
    return cur.fetchone()


def delete_grade_club(cur, plant, product, grade):
    """Remove one grade from its club on the caller's cursor; the caller commits."""
    _ver.bump(cur)
    cur.execute(
        "DELETE FROM special_steel_grade_clubs WHERE plant_name=%s AND product=%s AND quality_grade=%s",
        (plant, product, grade),
    )
