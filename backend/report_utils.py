import db
from typing import List, Dict, Any


def compute_item_row(month: str, item_name: str) -> list:
    """Computes a 10-value list for the SAIL summary page by summing metrics across plants."""
    db_item = item_name
    if item_name == "Crude Steel":
        db_item = "Total Crude Steel"
    elif item_name == "Finish Steel":
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

    def pct(num, den):
        if num is None or den is None or den == 0:
            return ""
        return str(round((num / den) * 100))

    def growth(num, den):
        if num is None or den is None or den == 0:
            return ""
        return str(round(((num - den) / den) * 100))

    # 0: APP, 1: Actual, 2: % Ful, 3: Act (CPLY), 4: % Gr,
    # 5: APP (YTD), 6: Actual (YTD), 7: % Ful (YTD), 8: Act (YTD CPLY), 9: % Gr (YTD)
    return [
        fmt(month_plan),
        fmt(month_actual),
        pct(month_actual, month_plan),
        fmt(month_cply_actual),
        growth(month_actual, month_cply_actual),
        fmt(ytd_plan),
        fmt(ytd_actual),
        pct(ytd_actual, ytd_plan),
        fmt(ytd_cply_actual),
        growth(ytd_actual, ytd_cply_actual),
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
