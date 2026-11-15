"""
Iron ore rakes loaded at the mines — the Rail Logistics page "Iron Ore Rake
Loading from Mines" (40.07, page_rail_logistics.py) and the OGOM / JGOM rows
of Monthly Rail Loading (40.05, rail_loading.py).

The source is the mines' rake-by-rake record (u_rakes_rmg.csv: one line per
rake — id, unit, rpt_date, rake_no, dest, type, l_wg, f_wg), uploaded on
Data Entry > Uploads (api_iron_ore_rakes.py) and kept one row per rake in
iron_ore_rake (repo.rake). One line is one rake whatever its destination
(plants, OTH, and the P-prefixed pellet-fines rakes to conversion agents):
counted that way the file agrees with the reported iron ore totals.

This module holds the mine groups and wagon-type names (not in the
database, as rail_loading.py's items), reads the file, and builds the page.
"""
import csv
import datetime
import io

import rake_despatch_report as rdr
from rake_despatch_report import fy_label, fy_months, fy_start_year, mlabel, shift_year
from repo import rake as rrake

# Mine (the file's `unit`) -> mines group. EGOM = OGOM + JGOM.
MINE_GROUP = {
    "BOL": "OGOM", "BAR": "OGOM", "KAL": "OGOM", "TAL": "OGOM",
    "KRB": "JGOM", "MBR": "JGOM", "GUA": "JGOM", "MPR": "JGOM",
    "BGM": "CGOM", "DAL": "CGOM", "RAJ": "CGOM", "ROW": "CGOM",
}
# Wagon code (the file's `type`) -> printed name; BX and EL print together.
WAGON_NAME = {
    "BS": "BOBSNM1", "BY": "BOYEL", "BX": "BOXN", "EL": "BOXN", "PR": "Private GPWIS",
    "GP": "SAIL BOXN GPWIS", "GS": "SAIL BOBSNM1 GPWIS",
}
GROUPS = ["EGOM", "CGOM"]       # the page's blocks
TOTAL = "Total"
ALL = GROUPS + [TOTAL]

_COLUMNS = ("id", "unit", "rpt_date", "rake_no", "dest", "type", "l_wg", "f_wg")
_MAX_EXAMPLES = 5


def read_file(data: bytes) -> str:
    """The uploaded file as text: UTF-8 (with or without BOM), else ANSI."""
    try:
        return data.decode("utf-8-sig")
    except UnicodeDecodeError:
        return data.decode("cp1252")


def _num(text):
    text = (text or "").strip()
    return float(text) if text else None


def parse_csv(text: str, today: str = None) -> list:
    """The file's rakes: [{id, rpt_date, report_month, mine_code, rake_no,
    dest, wagon_code, l_wg, f_wg}], codes upper-cased. The file is taken
    whole or not at all: any line that cannot be read, an id that repeats,
    a date after today or a mine / wagon code this module does not know
    raises ValueError naming the lines (a rake must never drop out of its
    group unnoticed)."""
    today = today or datetime.date.today().isoformat()
    reader = csv.reader(io.StringIO(text.lstrip("﻿")))
    header = next(reader, None)
    names = [h.strip().lower() for h in header or []]
    if not any(names):
        raise ValueError("There are no rakes in the file.")
    missing = [c for c in _COLUMNS if c not in names]
    if missing:
        raise ValueError(f"The file has no column named {', '.join(missing)}; expected {', '.join(_COLUMNS)}.")
    at = {c: names.index(c) for c in _COLUMNS}

    rows, seen, problems = [], set(), {}

    def problem(kind, what):
        problems.setdefault(kind, []).append(what)

    for line_no, cells in enumerate(reader, start=2):
        if not any(c.strip() for c in cells):
            continue
        cells = cells + [""] * (len(names) - len(cells))
        v = {c: cells[at[c]].strip() for c in _COLUMNS}
        try:
            rake_id = int(v["id"])
        except ValueError:
            problem("id is not a number", f"line {line_no} ({v['id']!r})")
            continue
        if rake_id in seen:
            problem("id appears more than once", f"{rake_id} (line {line_no})")
            continue
        seen.add(rake_id)
        try:
            if len(v["rpt_date"]) != 10:
                raise ValueError
            date = datetime.date.fromisoformat(v["rpt_date"]).isoformat()
        except ValueError:
            problem("date is not YYYY-MM-DD", f"line {line_no} ({v['rpt_date']!r})")
            continue
        if date > today:
            problem("date is in the future", f"line {line_no} ({date})")
        mine, wagon = v["unit"].upper(), v["type"].upper()
        if mine not in MINE_GROUP:
            problem("unknown mine code", f"{mine or '(blank)'} (line {line_no})")
        if wagon not in WAGON_NAME:
            problem("unknown wagon type", f"{wagon or '(blank)'} (line {line_no})")
        try:
            l_wg, f_wg = _num(v["l_wg"]), _num(v["f_wg"])
        except ValueError:
            problem("wagon count is not a number", f"line {line_no}")
            continue
        rows.append({"id": rake_id, "rpt_date": date, "report_month": date[:7], "mine_code": mine,
                     "rake_no": v["rake_no"] or None, "dest": v["dest"].upper() or None, "wagon_code": wagon,
                     "l_wg": l_wg, "f_wg": f_wg})
    if problems:
        raise ValueError("The file was not loaded. " + " ".join(
            f"{kind[0].upper()}{kind[1:]}: {', '.join(found[:_MAX_EXAMPLES])}"
            + (f" and {len(found) - _MAX_EXAMPLES} more" if len(found) > _MAX_EXAMPLES else "") + "."
            for kind, found in problems.items()))
    if not rows:
        raise ValueError("There are no rakes in the file.")
    return rows


# ── counts -> groups, wagon names, report ────────────────────────────────────

def _page_group(mine_code: str) -> str:
    group = MINE_GROUP[mine_code]
    return "CGOM" if group == "CGOM" else "EGOM"


def type_rows(counts: list) -> list:
    """repo counts ([{report_month, mine_code, wagon_code, rakes}]) summed to
    the page's groups and printed wagon names, in the row shape
    rake_despatch_report.wagon_mix takes: [{report_month, plant_code: group,
    wagon_type: name, rakes}]."""
    out = {}
    for c in counts:
        key = (c["report_month"], _page_group(c["mine_code"]), WAGON_NAME[c["wagon_code"]])
        out[key] = out.get(key, 0) + c["rakes"]
    return [{"report_month": m, "plant_code": g, "wagon_type": t, "rakes": n} for (m, g, t), n in sorted(out.items())]


def group_totals(counts: list) -> dict:
    """{month: {OGOM, JGOM, EGOM, CGOM, Total}} for the months that have rakes."""
    out = {}
    for c in counts:
        row = out.setdefault(c["report_month"], {"OGOM": 0, "JGOM": 0, "EGOM": 0, "CGOM": 0, TOTAL: 0})
        group = MINE_GROUP[c["mine_code"]]
        row[group] += c["rakes"]
        row[TOTAL] += c["rakes"]
        if group != "CGOM":
            row["EGOM"] += c["rakes"]
    return out


def _vs(now, before) -> str:
    return "" if not before else f" ({(now - before) / before * 100:+.1f}%"


def key_points(month: str, upto: str, totals: dict, mix: dict) -> list:
    """Up to three plain sentences: the report month against the same month
    last year (only when the month itself has rakes), the FY to date (the
    months up to `upto`, the last one that has rakes) against the same
    months of last FY, and the biggest wagon-mix move of 2 points or more."""
    pts = []
    now = totals.get(month)
    if now:
        ly_month = shift_year(month, -1)
        ly = totals.get(ly_month, {})
        egom, cgom = _vs(now["EGOM"], ly.get("EGOM")), _vs(now["CGOM"], ly.get("CGOM"))
        pts.append(f"Iron ore loading from mines in {mlabel(month)}: EGOM {now['EGOM']} rakes"
                   + (f"{egom} vs {mlabel(ly_month)})" if egom else "")
                   + f", CGOM {now['CGOM']} rakes" + (f"{cgom})" if cgom else "") + ".")
    fytd = [m for m in fy_months(fy_start_year(month)) if m <= upto]
    loaded = sum(totals.get(m, {}).get(TOTAL, 0) for m in fytd)
    before = sum(totals.get(shift_year(m, -1), {}).get(TOTAL, 0) for m in fytd)
    if loaded and before:
        change = (loaded - before) / before * 100
        pts.append(f"FY to date{'' if upto == month else f' (to {mlabel(upto)})'} the mines loaded {loaded} iron ore"
                   f" rakes, {abs(change):.1f}% {'ahead of' if change >= 0 else 'behind'} the same period last year"
                   f" ({before}).")
    whole = next((p for p in mix["plants"] if p["plant"] == TOTAL), None)
    shift = whole and whole["biggest_shift"]
    if shift and abs(shift["shift_pp"]) >= 2:
        pts.append(f"Wagon mix ({mix['label']}): {shift['type']} share {'up' if shift['shift_pp'] > 0 else 'down'} "
                   f"{abs(shift['shift_pp']):.1f} points to {shift['share_now']:.1f}%.")
    return pts


def build_report(month: str) -> dict:
    """Everything page 40.07 prints for `month`, from the stored rakes:
    {available, fy, fy_months, month_label, key_points, trend, wagon_mix,
    types}. trend and wagon_mix are rake_despatch_report's own shapes with
    the mines groups (and Total) where it has plants (and SAIL); types is
    {group: {wagon name: {month: rakes}}} for the report month's FY.
    Months after the report month are never shown; a report month with no
    rakes yet (file not uploaded) prints blank and the mix and FY-to-date
    stop at the last month that has rakes."""
    start = fy_start_year(month)
    months = fy_months(start)
    out = {"available": False, "fy": fy_label(start), "fy_months": months, "month_label": mlabel(month)}
    counts = rrake.iron_ore_rake_counts(fy_months(start - rdr.HISTORY_FYS + 1)[0], month)
    totals = group_totals(counts)
    with_rakes = [m for m in months if m <= month and m in totals]
    if not with_rakes:
        return out
    upto = with_rakes[-1]
    rows = type_rows(counts)
    mix = rdr.wagon_mix(upto, rows, groups=GROUPS, total_row=TOTAL)
    types = {}
    for r in rows:
        if r["report_month"] in months:
            types.setdefault(r["plant_code"], {}).setdefault(r["wagon_type"], {})[r["report_month"]] = r["rakes"]
    out.update(available=True, key_points=key_points(month, upto, totals, mix),
               trend=rdr.trend(month, totals, rows=ALL), wagon_mix=mix, types=types)
    return out
