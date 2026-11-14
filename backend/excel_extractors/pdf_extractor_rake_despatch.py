"""
PDF extractor for the Rail Movement Cell's monthly "Despatch Summary Report"
(sample: Report_format/Miscellaneous/Despatch Summary Report 2026-10.pdf,
"REPORT AS ON 1.11.2026"), feeding api_rake_despatch.py and the Reports >
Rail Logistics page. Never writes to the DB itself.

Pages used (found by title, not position):
  - DESPATCH SUMMARY REPORT (page 1): per-plant month-end position, slab
    despatch between plants, slag / coke / sinter rakes.
  - MONTHWISE STEEL DESPATCH (INCLUDING EXPORT) SUMMARY (page 2): rakes per
    plant x wagon type x month of the FY, and export rakes per destination.
  - MONTHWISE STEEL DESPATCH SUMMARY DURING ... (page 5): total rakes per
    plant per month for seven FYs.
The date-wise empty-received / loading pages (3-4) are not read.

Layout: every table is a printed grid whose cell text pdfplumber returns as
words with coordinates. A value is placed by its row label (nearest label
vertically; some rows print their numbers a point or two off the label's
line) and by its column header's x position. Only plant rows are returned;
the PDF's own SAIL rows and TOTAL rows are kept as `printed_*` so
`checks` can report where the PDF disagrees with itself (the 2026-10 file's
page 2 and page 5 differ for May 2026, for instance).
"""
import re
from datetime import date, timedelta

import pdfplumber

PLANTS = ["BSP", "DSP", "RSP", "BSL", "ISP"]
_ALL = PLANTS + ["SAIL"]
_MONTHS = ["APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC", "JAN", "FEB", "MAR"]
_NUM = re.compile(r"^-?\d+(?:\.\d+)?$")
_FY = re.compile(r"^(\d{4})-(\d{2})$")

# Page 1, main table: metric -> x0 range of its column.
_P1_COLS = [
    ("plan_avg_day", 80, 125), ("empties_received", 125, 175), ("made_over", 175, 250),
    ("cumm", 250, 330), ("avg_day", 330, 415), ("diff_plan", 415, 475),
    ("made_over_after_00", 475, 515), ("under_loading", 515, 560), ("empty_forecast", 560, 615),
]
# Columns whose BSP cell also carries a DMT sub-figure printed under the main one.
_P1_DMT = {"empties_received", "made_over", "cumm", "empty_forecast"}
# Page 1, slag / coke / sinter table.
_P1_BYPRODUCT_COLS = [
    ("slag_plan_avg_day", 80, 135), ("slag_on_date", 135, 170), ("slag_cumm", 170, 210), ("slag_avg_day", 210, 250),
    ("coke_plan_avg_day", 250, 290), ("coke_on_date", 290, 330), ("coke_cumm", 330, 380), ("coke_avg_day", 380, 425),
    ("sinter_plan_avg_day", 425, 470), ("sinter_on_date", 470, 510), ("sinter_cumm", 510, 560), ("sinter_avg_day", 560, 615),
]

# Every metric code stored in rake_despatch_position, in display order.
POSITION_METRICS = (
    [m for m, _a, _b in _P1_COLS]
    + [f"{m}_dmt" for m, _a, _b in _P1_COLS if m in _P1_DMT]
    + [m for m, _a, _b in _P1_BYPRODUCT_COLS]
)


def _num(text):
    return float(text) if _NUM.match(text) else None


def _int_or_float(v):
    return int(v) if v is not None and float(v).is_integer() else v


def _words(page):
    return page.extract_words(keep_blank_chars=False, use_text_flow=False)


def _lines(words, tol=2.5):
    """Words grouped into printed lines (tops within tol), top to bottom,
    each line's words left to right."""
    out = []
    for w in sorted(words, key=lambda w: (w["top"], w["x0"])):
        if out and abs(w["top"] - out[-1][0]) <= tol:
            out[-1][1].append(w)
        else:
            out.append([w["top"], [w]])
    return [(top, sorted(ws, key=lambda w: w["x0"])) for top, ws in out]


def _text(page):
    return " ".join(w["text"] for w in _words(page)).upper()


def _find_pages(pdf):
    found = {}
    for i, page in enumerate(pdf.pages):
        t = _text(page)
        if "DESPATCH SUMMARY REPORT" in t and "IRON & STEEL" in t and "p1" not in found:
            found["p1"] = page
        elif "(INCLUDING EXPORT)" in t and "p2" not in found:
            found["p2"] = page
        elif "MONTHWISE STEEL DESPATCH SUMMARY DURING" in t and "p5" not in found:
            found["p5"] = page
    missing = [k for k in ("p1", "p2", "p5") if k not in found]
    if missing:
        names = {"p1": "Despatch Summary Report (page 1)",
                 "p2": "Monthwise Steel Despatch (Including Export) Summary (page 2)",
                 "p5": "Monthwise Steel Despatch Summary During ... (page 5)"}
        raise ValueError("Not a Despatch Summary Report, or a page is missing: "
                         + ", ".join(names[k] for k in missing))
    return found


def _as_on(page):
    """'REPORT AS ON 1 . 11. 2026' -> date(2026, 11, 1)."""
    for _top, ws in _lines(_words(page)):
        texts = [w["text"] for w in ws]
        if len(texts) >= 3 and texts[:3] == ["REPORT", "AS", "ON"]:
            digits = re.findall(r"\d+", " ".join(texts[3:]))
            if len(digits) >= 3:
                d, m, y = int(digits[0]), int(digits[1]), int(digits[2])
                return date(y, m, d)
    raise ValueError("Could not read the 'REPORT AS ON' date on page 1.")


def _fy_months(fy_start):
    return [f"{fy_start + (i >= 9):04d}-{(i + 3) % 12 + 1:02d}" for i in range(12)]


def _col(x0, cols):
    for name, lo, hi in cols:
        if lo <= x0 < hi:
            return name
    return None


def _nearest(top, anchors, limit):
    """The anchor whose top is closest to `top`, if within limit."""
    best = min(anchors, key=lambda a: abs(a["top"] - top), default=None)
    return best if best is not None and abs(best["top"] - top) <= limit else None


# ── page 1 ───────────────────────────────────────────────────────────────────

def _page1(page):
    words = _words(page)
    labels = [w for w in words if w["text"] in _ALL and w["x0"] < 40]
    slag = next((w for w in words if w["text"] == "SLAG"), None)
    slab_hdr = next((w for w in words if w["text"] == "FROM"), None)
    split = slag["top"] if slag else 1e9
    main_end = slab_hdr["top"] if slab_hdr else split

    position, printed_sail = {}, {}

    # Main table: a plant's cell values sit within its row band; BSP's cells
    # carry a second, DMT figure below the main one.
    main_labels = [w for w in labels if w["top"] < main_end]
    cells = {}
    for w in words:
        if w["top"] >= main_end or w["x0"] < 80 or _num(w["text"]) is None:
            continue
        lab = _nearest(w["top"], main_labels, 14)
        col = _col(w["x0"], _P1_COLS)
        if lab and col:
            cells.setdefault((lab["text"], col), []).append(w)
    for (plant, col), ws in cells.items():
        ws.sort(key=lambda w: w["top"])
        target = printed_sail if plant == "SAIL" else position.setdefault(plant, {})
        target[col] = _int_or_float(_num(ws[0]["text"]))
        if len(ws) > 1 and col in _P1_DMT:
            target[f"{col}_dmt"] = _int_or_float(_num(ws[1]["text"]))

    # Slag / coke / sinter: one printed line per plant.
    for w in words:
        if w["top"] <= split or w["x0"] < 80 or _num(w["text"]) is None:
            continue
        lab = _nearest(w["top"], [l for l in labels if l["top"] > split], 6)
        col = _col(w["x0"], _P1_BYPRODUCT_COLS)
        if lab and col:
            target = printed_sail if lab["text"] == "SAIL" else position.setdefault(lab["text"], {})
            target[col] = _int_or_float(_num(w["text"]))

    # Slab despatch: "BSL RSP 3 7548.6" lines under the FROM/TO header.
    slab, note_lines = [], []
    lines = _lines(words)
    for top, ws in lines:
        if slab_hdr and slab_hdr["top"] < top < split:
            t = [w["text"] for w in ws]
            if len(t) >= 4 and t[0] in PLANTS and t[1] in PLANTS and _num(t[2]) is not None:
                slab.append({"from": t[0], "to": t[1], "rakes": int(float(t[2])),
                             "qty_mt": _num(t[3])})
    note_hdr = next((top for top, ws in lines if ws[0]["text"].upper() == "TODAY'S"), None)
    if note_hdr is not None:
        for top, ws in lines:
            if note_hdr < top < split:
                note_lines.append(" ".join(w["text"] for w in ws))
    return position, printed_sail, slab, " ".join(note_lines).strip() or None


# ── page 2 ───────────────────────────────────────────────────────────────────

def _page2(page, report_month):
    words = _words(page)
    title = next(w for w in words if _FY.match(w["text"]) and w["top"] < 60)
    fy_start = int(_FY.match(title["text"]).group(1))
    months = _fy_months(fy_start)
    hdr = {w["text"].upper(): w["x0"] for w in words if w["text"].upper() in _MONTHS and w["top"] < 80}
    exp_top = next(w["top"] for w in words if w["text"] == "EXPORT" and w["top"] > 100)

    def month_of(x0):
        best = min(hdr.items(), key=lambda kv: abs(kv[1] - x0))
        return months[_MONTHS.index(best[0])] if abs(best[1] - x0) <= 12 else None

    # Despatch grid.
    grid = [w for w in words if 70 < w["top"] < exp_top - 15]
    row_labels = [w for w in grid if 105 <= w["x0"] < 140 and re.match(r"^[A-Z./]+$", w["text"])
                  and w["text"] not in ("AVG./DAY",)]
    plant_labels = sorted([w for w in grid if w["x0"] < 100 and w["text"] in _ALL], key=lambda w: w["top"])
    values = {}
    for w in grid:
        if w["x0"] < 140 or _num(w["text"]) is None:
            continue
        lab = _nearest(w["top"], row_labels, 4)
        m = month_of(w["x0"])
        if lab and m:
            values.setdefault(id(lab), {})[m] = _int_or_float(_num(w["text"]))

    groups, cur = [], []
    for lab in sorted(row_labels, key=lambda w: w["top"]):
        cur.append(lab)
        if lab["text"] == "TOTAL":
            groups.append(cur)
            cur = []
    if len(groups) != len(plant_labels):
        raise ValueError(f"Page 2: found {len(groups)} plant blocks but {len(plant_labels)} plant names.")

    types, printed_totals = {}, {}
    for plant_w, group in zip(plant_labels, groups):
        plant = plant_w["text"]
        for lab in group:
            row = values.get(id(lab), {})
            if lab["text"] == "TOTAL":
                printed_totals[plant] = {m: v for m, v in row.items() if m <= report_month}
                continue
            if plant == "SAIL":
                for m, v in row.items():
                    if m <= report_month:
                        printed_totals.setdefault("SAIL_TYPES", {}).setdefault(m, {})[_wagon(lab["text"])] = v
                continue
            for m, v in row.items():
                if m <= report_month:
                    types.setdefault(m, {}).setdefault(plant, {})[_wagon(lab["text"])] = int(v)

    export, printed_export = _export(words, exp_top)
    return fy_start, types, printed_totals, export, printed_export


def _wagon(label):
    # The PDF spells CONCOR (container rakes) as CONCORD.
    return "CONCOR" if label == "CONCORD" else label


def _export(words, exp_top):
    """Export programme vs actual per destination x plant."""
    hdr_line = [w for w in words if w["text"] in ("PROG", "ACTUAL") and w["top"] > exp_top]
    plant_hdr = sorted([w for w in words if w["text"] in _ALL and exp_top < w["top"] < exp_top + 20],
                       key=lambda w: w["x0"])
    cols = []  # (plant, field, x0)
    progs = sorted([w for w in hdr_line if w["text"] == "PROG"], key=lambda w: w["x0"])
    acts = sorted([w for w in hdr_line if w["text"] == "ACTUAL"], key=lambda w: w["x0"])
    for plant_w, p, a in zip(plant_hdr, progs, acts):
        cols += [(plant_w["text"], "prog", p["x0"]), (plant_w["text"], "actual", a["x0"])]
    hdr_top = max(w["top"] for w in hdr_line)

    body = [w for w in words if w["top"] > hdr_top + 4]
    # A destination label: the words left of the figures on one line.
    label_lines = []
    for top, ws in _lines([w for w in body if w["x0"] < 180]):
        label_lines.append({"top": top, "text": " ".join(w["text"] for w in ws)})
    figures = {}
    for w in body:
        if w["x0"] < 190 or _num(w["text"]) is None:
            continue
        lab = _nearest(w["top"], label_lines, 4)
        col = min(cols, key=lambda c: abs(c[2] - w["x0"]))
        if lab and abs(col[2] - w["x0"]) <= 15:
            figures.setdefault(lab["text"], {}).setdefault(col[0], {})[col[1]] = _num(w["text"])

    export, printed, group, order = [], {}, "NEPAL", 0
    for lab in label_lines:
        name = lab["text"]
        row = figures.get(name, {})
        if name.upper().startswith(("TOTAL", "GRAND")):
            printed[name.upper()] = row
            if name.upper() == "TOTAL NEPAL":
                group = "PORT"
            continue
        order += 1
        for plant in PLANTS:
            cell = row.get(plant, {})
            export.append({"destination": name, "group": group, "sort_order": order, "plant": plant,
                           "prog": cell.get("prog"), "actual": cell.get("actual")})
        printed[name.upper()] = row
    return export, printed


# ── page 5 ───────────────────────────────────────────────────────────────────

def _page5(page, report_month):
    words = _words(page)
    hdr = {w["text"].upper(): w["x0"] for w in words if w["text"].upper() in _MONTHS and w["top"] < 80}
    cumm_hdr = next(w for w in words if w["text"].upper().startswith("CUMM"))
    years = [w for w in words if _FY.match(w["text"]) and 140 < w["x0"] < 200 and w["top"] > 75]
    plant_labels = sorted([w for w in words if w["text"] in _ALL and w["x0"] < 150 and w["top"] > 75],
                          key=lambda w: w["top"])

    rows = {}
    for w in words:
        if w["x0"] < 195 or w["top"] < 75 or _num(w["text"]) is None:
            continue
        lab = _nearest(w["top"], years, 5)
        if lab is None:
            continue
        if abs(w["x0"] - cumm_hdr["x0"]) <= 12:
            rows.setdefault(id(lab), {})["CUMM"] = _int_or_float(_num(w["text"]))
            continue
        name, hx = min(hdr.items(), key=lambda kv: abs(kv[1] - w["x0"]))
        if abs(hx - w["x0"]) <= 14:
            rows.setdefault(id(lab), {})[name] = _int_or_float(_num(w["text"]))

    years.sort(key=lambda w: w["top"])
    newest = years[0]["text"]
    blocks, cur = [], []
    for y in years:
        if y["text"] == newest and cur:
            blocks.append(cur)
            cur = []
        cur.append(y)
    blocks.append(cur)
    if len(blocks) != len(plant_labels):
        raise ValueError(f"Page 5: found {len(blocks)} plant blocks but {len(plant_labels)} plant names.")

    history, printed_sail, printed_cumm = {}, {}, {}
    for plant_w, block in zip(plant_labels, blocks):
        plant = plant_w["text"]
        for y in block:
            months = _fy_months(int(_FY.match(y["text"]).group(1)))
            row = rows.get(id(y), {})
            printed_cumm[(plant, y["text"])] = row.get("CUMM")
            for i, name in enumerate(_MONTHS):
                v = row.get(name)
                if v is None or months[i] > report_month:
                    continue
                if plant == "SAIL":
                    printed_sail[months[i]] = int(v)
                else:
                    history.setdefault(months[i], {})[plant] = int(v)
    return history, printed_sail, printed_cumm


# ── checks ───────────────────────────────────────────────────────────────────

def _checks(position, printed_p1_sail, types, printed_totals, history, printed_hist_sail,
            printed_cumm, export, printed_export, report_month):
    out = []

    def close(a, b, tol=0.011):
        return a is None or b is None or abs(float(a) - float(b)) <= tol

    for metric, v in printed_p1_sail.items():
        s = sum(position.get(p, {}).get(metric) or 0 for p in PLANTS)
        if not close(s, v, 0.02):
            out.append(f"Page 1: SAIL {metric} is printed as {v} but the plants add up to {round(s, 2)}.")

    for m in sorted(types):
        sail_sum = 0
        for p in PLANTS:
            s = sum((types[m].get(p) or {}).values())
            sail_sum += s
            printed = printed_totals.get(p, {}).get(m)
            if printed is not None and printed != s:
                out.append(f"Page 2: {p} {m} wagon types add up to {s} but TOTAL is printed as {printed}.")
            h = history.get(m, {}).get(p)
            if h is not None and h != s:
                out.append(f"{p} {m}: page 2 shows {s} rakes but page 5 shows {h}.")
        printed = printed_totals.get("SAIL", {}).get(m)
        if printed is not None and printed != sail_sum:
            out.append(f"Page 2: SAIL {m} TOTAL is printed as {printed} but the plants add up to {sail_sum}.")
        h = printed_hist_sail.get(m)
        if h is not None and h != sail_sum:
            out.append(f"SAIL {m}: page 2 shows {sail_sum} rakes but page 5 shows {h}.")

    if report_month in types:
        for p in PLANTS:
            c = position.get(p, {}).get("cumm")
            s = sum((types[report_month].get(p) or {}).values())
            if c is not None and c != s:
                out.append(f"{p}: page 1 cumulative is {c} but page 2 {report_month} shows {s}.")

    for (plant, fy), printed in printed_cumm.items():
        months = _fy_months(int(fy[:4]))
        if plant == "SAIL":
            s = sum(printed_hist_sail.get(m, 0) for m in months)
        else:
            s = sum(history.get(m, {}).get(plant, 0) for m in months)
        if printed is not None and printed != s:
            out.append(f"Page 5: {plant} {fy} CUMM is printed as {printed} but its months add up to {s}.")

    for name, row in printed_export.items():
        if not name.startswith(("TOTAL", "GRAND")):
            continue
        group = {"TOTAL NEPAL": "NEPAL", "TOTAL PORT": "PORT"}.get(name)
        for p in PLANTS:
            for field in ("prog", "actual"):
                s = sum(e[field] or 0 for e in export if e["plant"] == p and (group is None or e["group"] == group))
                v = row.get(p, {}).get(field)
                if not close(s, v):
                    out.append(f"Page 2 export: {name} {p} {field} is printed as {v} but the destinations add up to {s}.")
    return out


# ── entry point ──────────────────────────────────────────────────────────────

def extract(path: str) -> dict:
    """-> {as_on, report_month, fy, position, slab, slab_note, types, history,
    export, checks}. report_month is the month the file closes: the day
    before its "as on" date (a 1.11.2026 file closes October 2026)."""
    with pdfplumber.open(path) as pdf:
        pages = _find_pages(pdf)
        as_on = _as_on(pages["p1"])
        report_month = (as_on - timedelta(days=1)).strftime("%Y-%m")
        position, printed_p1_sail, slab, slab_note = _page1(pages["p1"])
        fy_start, types, printed_totals, export, printed_export = _page2(pages["p2"], report_month)
        history, printed_hist_sail, printed_cumm = _page5(pages["p5"], report_month)

    checks = _checks(position, printed_p1_sail, types, printed_totals, history, printed_hist_sail,
                     printed_cumm, export, printed_export, report_month)
    return {
        "as_on": as_on.isoformat(),
        "report_month": report_month,
        "fy": f"{fy_start}-{(fy_start + 1) % 100:02d}",
        "position": position,
        "slab": slab,
        "slab_note": slab_note,
        "types": types,
        "history": history,
        "export": export,
        "checks": checks,
    }
