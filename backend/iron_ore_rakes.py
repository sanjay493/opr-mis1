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
