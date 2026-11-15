"""
SAIL's monthly rail loading by commodity — the first Rail Logistics page of
the MIS PDF (40.05, page_rail_logistics.py): inward raw materials with their
sub-groups, outward plant despatch, the grand total with rakes per day, and
the export memo, month by month for the report month's FY.

The figures are the Rail Movement Cell's monthly highlights note, stored one
row per item code in rail_loading_monthly (repo.rake) and entered month by
month on Data Entry > Reference & Records > Monthly Rail Loading
(api_rail_loading.py). This module holds the
item registry (codes, labels, print order, which rows are totals) and builds
the page table. Totals print as the note reports them and are never summed
here: imported limestone is counted under both Flux and Ports, so the
sections add up to more than the reported inward total.
"""
from repo import rake as rrake
from rake_despatch_report import days_in, fy_label, fy_months, fy_start_year, mlabel

# (kind, code, label) in print order. kind: "group" heading, "sub" (a
# sub-heading inside a group: no figures), "subitem" (a row under a "sub",
# indented one step more than an "item"), "item", "total" (a reported
# sub-total), "grand", "per_day" (computed, not stored).
ITEMS = (
    ("group", "inward", "INWARD – RAW MATERIALS & COAL"),
    ("sub", "ore", "Iron ore"),
    ("subitem", "ore_ogom", "OGOM"),
    ("subitem", "ore_jgom", "JGOM"),
    ("subitem", "ore_ogom_jgom", "EGOM (OGOM + JGOM)"),
    ("subitem", "ore_bhilai", "CGOM"),
    ("total", "ore_total", "Total iron ore"),
    ("sub", "limestone", "Flux – Limestone"),
    ("subitem", "flux_ls_kuteswar", "Kuteswar"),
    ("subitem", "flux_ls_nandini", "Nandini"),
    ("subitem", "flux_ls_rsmml", "RSMML (Sonu)"),
    ("subitem", "flux_ls_wonder", "Wonder"),
    ("subitem", "flux_ls_other", "Others"),
    ("total", "flux_limestone", "Total limestone"),
    ("sub", "dolomite", "Flux – Dolomite"),
    ("subitem", "flux_dol_hirri", "Hirri"),
    ("subitem", "flux_dol_other", "Others"),
    ("total", "flux_dolomite", "Total dolomite"),
    ("total", "flux_total", "Total flux"),
    ("item", "port_coal", "Ports – Imported coal"),
    ("item", "port_limestone", "Ports – Imported limestone"),
    ("total", "port_total", "Total from ports"),
    ("item", "coal_coking", "Indigenous coal – Coking"),
    ("item", "coal_power", "Indigenous coal – Powerhouse"),
    ("total", "coal_total", "Total indigenous coal"),
    ("item", "misc_pellets", "Misc – Pellets"),
    ("item", "misc_other", "Misc – Ferro alloy, Mn ore & others"),
    ("total", "misc_total", "Total misc raw materials"),
    ("total", "inward_total", "TOTAL INWARD"),
    ("group", "outward", "OUTWARD – FROM SAIL PLANTS"),
    ("item", "out_steel", "Iron & steel"),
    ("item", "out_slag", "Slag"),
    ("item", "out_coke", "Coke & coke fraction"),
    ("item", "out_sinter", "Sinter"),
    ("total", "outward_total", "TOTAL OUTWARD"),
    ("grand", "grand_total", "GRAND TOTAL (inward + outward)"),
    ("per_day", "per_day", "Rakes per day"),
    ("group", "export", "EXPORT (memo, included in iron & steel)"),
    ("item", "export_port", "Export – through ports"),
    ("item", "export_nepal", "Export – to Nepal"),
    ("total", "export_total", "Total export"),
)
_HEADINGS = ("group", "sub")
# The stored item codes, in print order.
CODES = tuple(code for kind, code, _label in ITEMS if kind not in _HEADINGS + ("per_day",))

# Rows worked out from other rows when a month is entered by hand
# (with_derived). EGOM is OGOM + JGOM once both are entered; before the mines
# were reported apart only the combined EGOM figure exists, and it stays as
# entered. Each "Others" row is its total less the named rows entered.
EGOM, EGOM_PARTS = "ore_ogom_jgom", ("ore_ogom", "ore_jgom")
OTHERS = {  # others code: (total code, named codes)
    "flux_ls_other": ("flux_limestone", ("flux_ls_kuteswar", "flux_ls_nandini", "flux_ls_rsmml", "flux_ls_wonder")),
    "flux_dol_other": ("flux_dolomite", ("flux_dol_hirri",)),
    "misc_other": ("misc_total", ("misc_pellets",)),
}
LABELS = {code: label for _kind, code, label in ITEMS}


def with_derived(values: dict) -> dict:
    """{item_code: rakes} with the derived rows filled in (see OTHERS): EGOM
    = OGOM + JGOM when both are given; an "Others" row = its total less the
    named rows given (None when the total or every named row is missing).
    Named rows adding up to more than their total -> ValueError."""
    out = dict(values)
    parts = [out.get(c) for c in EGOM_PARTS]
    if all(v is not None for v in parts):
        out[EGOM] = round(sum(parts), 1)
    for other, (total, named) in OTHERS.items():
        given = [out[c] for c in named if out.get(c) is not None]
        if out.get(total) is None or not given:
            out[other] = None
            continue
        rest = round(out[total] - sum(given), 1)
        if rest < 0:
            raise ValueError(f"{LABELS[total]} ({fmt_rakes(out[total])}) is less than the rows under it"
                             f" ({fmt_rakes(round(sum(given), 1))})")
        out[other] = rest
    return out


def fmt_rakes(v) -> str:
    """Table cell text for a rake count: "–" for a missing value, one decimal
    only where the figure has one (coking coal is reported as 46.3)."""
    if v is None:
        return "–"
    text = f"{v:.1f}"
    text = text[:-2] if text.endswith(".0") else text
    return "0" if text == "-0" else text


def save_month(month: str, values: dict, user) -> int:
    """Save one month's {item_code: rakes} (replacing the month); only the
    registry's codes are accepted. -> rows saved."""
    unknown = sorted(set(values) - set(CODES))
    if unknown:
        raise ValueError(f"unknown rail loading item code(s): {', '.join(unknown)}")
    return rrake.save_rail_loading(month, values, user)


def loading_table(rows: list, month: str) -> dict:
    """The page table from rail_loading_monthly rows ([{report_month,
    item_code, rakes}]): Apr..Mar of the report month's FY, months after the
    report month blank, FYTD = the months present. FYTD rakes/day (total rows
    only) divides by the days of the months that row has."""
    start = fy_start_year(month)
    months = fy_months(start)
    known = {(r["report_month"], r["item_code"]): r["rakes"] for r in rows
             if r["report_month"] in months and r["report_month"] <= month and r["rakes"] is not None}

    def series(code):
        return [known.get((m, code)) for m in months]

    grand = series("grand_total")
    out = []
    for kind, code, label in ITEMS:
        row = {"kind": kind, "code": code, "label": label, "months": [None] * 12, "fytd": None, "fytd_per_day": None}
        if kind == "per_day":
            row["months"] = [None if v is None else round(v / days_in(m), 2) for m, v in zip(months, grand)]
        elif kind not in _HEADINGS:
            row["months"] = series(code)
        vals = grand if kind == "per_day" else row["months"]
        present = [(m, v) for m, v in zip(months, vals) if v is not None]
        if present and kind not in _HEADINGS:
            total = round(sum(v for _m, v in present), 1)
            if kind != "per_day":
                row["fytd"] = total
            if kind in ("total", "grand", "per_day"):
                row["fytd_per_day"] = round(total / sum(days_in(m) for m, _v in present), 2)
        out.append(row)
    return {"fy": fy_label(start), "month_labels": [mlabel(m)[:3] for m in months],
            "has_data": any(c in CODES for _m, c in known), "rows": out}


def build_page(month: str) -> dict:
    """Page 40.05's data (page_rail_logistics adds type and title)."""
    t = loading_table(rrake.rail_loading_rows(fy_months(fy_start_year(month))[0], month), month)
    return {"available": t["has_data"], "subtitle": f"{mlabel(month)} · FY {t['fy']}",
            "placeholder": None if t["has_data"] else f"Monthly rail loading for FY {t['fy']} not yet entered",
            "fy": t["fy"], "month_labels": t["month_labels"], "rows": t["rows"]}
