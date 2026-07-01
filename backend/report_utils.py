import db
from typing import List, Dict, Any


def compute_item_row(month: str, item_name: str) -> list:
    """Computes a 12-value list for the SAIL summary production table.

    Index  Column
    -----  ------
    0      Monthly APP
    1      Monthly ACT
    2      Monthly VAR  (ACT - APP)
    3      Monthly %FUL
    4      CPLY Monthly ACT
    5      %GR vs CPLY month
    6      YTD APP
    7      YTD ACT
    8      YTD VAR  (ACT - APP)
    9      YTD %FUL
    10     YTD CPLY ACT
    11     %GR vs CPLY YTD
    """
    db_item = item_name
    if item_name == "Crude Steel":
        db_item = "Total Crude Steel"
    elif item_name in ("Finish Steel", "Finished Steel"):
        db_item = "Finished Steel"

    month_plan        = db.get_sail_production_plan(month, db_item)
    month_actual      = db.get_sail_production_actual(month, db_item)

    cply_month        = db.get_cply_month(month)
    month_cply_actual = db.get_sail_production_actual(cply_month, db_item)

    ytd_months        = db.get_ytd_months(month)
    ytd_plan          = db.get_sail_production_ytd_plan(ytd_months, db_item)
    ytd_actual        = db.get_sail_production_ytd_actual(ytd_months, db_item)

    ytd_cply_months   = db.get_ytd_months(cply_month)
    ytd_cply_actual   = db.get_sail_production_ytd_actual(ytd_cply_months, db_item)

    def fmt(val):
        return "" if val is None else str(round(val))

    def var(a, p):
        if a is None or p is None:
            return ""
        return str(round(a - p))

    def pct(num, den):
        if num is None or den is None or den == 0:
            return ""
        return str(round((num / den) * 100))

    def growth(num, den):
        if num is None or den is None or den == 0:
            return ""
        return str(round(((num - den) / den) * 100))

    return [
        fmt(month_plan),                          # 0  Monthly APP
        fmt(month_actual),                        # 1  Monthly ACT
        var(month_actual, month_plan),            # 2  Monthly VAR
        pct(month_actual, month_plan),            # 3  Monthly %FUL
        fmt(month_cply_actual),                   # 4  CPLY Monthly ACT
        growth(month_actual, month_cply_actual),  # 5  %GR vs CPLY
        fmt(ytd_plan),                            # 6  YTD APP
        fmt(ytd_actual),                          # 7  YTD ACT
        var(ytd_actual, ytd_plan),                # 8  YTD VAR
        pct(ytd_actual, ytd_plan),                # 9  YTD %FUL
        fmt(ytd_cply_actual),                     # 10 YTD CPLY ACT
        growth(ytd_actual, ytd_cply_actual),      # 11 %GR vs YTD CPLY
    ]


def blank_out_page_data(pages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Blanks out mock/dummy numeric data and highlights from the template pages config."""
    blanked = []
    for page in pages:
        p = dict(page)

        if "highlights" in p:
            p["highlights"] = []

        if "production_table" in p and p["production_table"]:
            p["production_table"] = [
                {**row, "values": [""] * len(row.get("values", []))}
                for row in p["production_table"]
            ]

        if "te_table" in p and p["te_table"]:
            p["te_table"] = [
                {**row, "values": [""] * len(row.get("values", []))}
                for row in p["te_table"]
            ]

        if "rows" in p and p["rows"] and p.get("type") not in ("index", "cover"):
            p["rows"] = [
                {**row, "values": [""] * len(row.get("values", []))}
                for row in p["rows"]
            ]

        blanked.append(p)
    return blanked
