"""Shim over repo/: every query lives in a repo/<domain>.py module and is
re-exported here so existing db.<name> callers keep working. What is left
is connect() and the month / FY helpers."""
from typing import List
import dbengine
from dbengine import Row, IntegrityError, OperationalError  # noqa: F401
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
    get_pdf_item_aliases,
    save_pdf_item_alias,
    get_rail_report_data,
    save_rail_report_data,
    _READY_RECKONER_COLS,
    _READY_RECKONER_JSON_COLS,
    _decode_ready_reckoner_row,
    get_ready_reckoner_pages,
    get_ready_reckoner_page,
    upsert_ready_reckoner_master,
    save_ready_reckoner_content,
    save_ready_reckoner_image,
    _MAJOR_UNIT_DAILY_COLS,
    get_major_unit_daily_records,
    get_major_unit_daily_records_all,
    save_major_unit_daily_record,
)
# Breakdown / capital repair SQL lives in repo/breakdown.py.
from repo.breakdown import (  # noqa: F401
    list_breakdown_entries,
    save_breakdown_entry,
    update_breakdown_entry,
    delete_breakdown_entry,
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
from repo.pages import (  # noqa: F401
    get_page_config,
    get_all_page_configs,
    save_page_config,
)
from repo.text import (  # noqa: F401
    get_page3_narrative,
    save_page3_narrative,
    get_key_highlights_narrative,
    save_key_highlights_narrative,
    get_steel_sales_highlights,
    save_steel_sales_highlights,
    get_ss_phys_notes,
    save_ss_phys_notes,
    get_rail_report_notes,
    save_rail_report_notes,
)
from repo.ops import (  # noqa: F401
    log_page_visit,
    ANON_VISIT_NOTIFY_WINDOW_MINUTES,
    add_admin_notification,
    _add_admin_notification,
    list_admin_notifications,
    _FINAL_STATUS_FROM,
    _FINAL_REPORT_RULES,
    _production_month_status,
    production_month_status,
    log_extraction,
    get_extraction_logs,
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
