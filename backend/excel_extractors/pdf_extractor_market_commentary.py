"""Commentary & Market PDF extractor — the monthly CMO / BigMint deck
(e.g. Report_format/Market/dc_2026-09.pdf, a PowerPoint printed to PDF).

  Page (found by TITLE, never by page number)          -> result key
  ------------------------------------------------------------------------
  "<Month>'YY Key Performance Parameters"               -> commentary.month_items
  "April-<Month>'YY Key Performance Parameters"         -> commentary.ytd_items
      Steel Sales Performance page (3.05) bullets — see
      api_steel_sales_highlights.py / db.save_steel_sales_highlights.
  "Movement of Key Prices-International"                -> market_prices
      7 USD/T series, see page_market_prices._SERIES — saved via
      db.save_market_price_trend.
  A page with no text layer (the India Macro Economic Indicators table is a
  pasted image)                                         -> skipped_pages
      entered by hand in /data-entry/market-intel instead (OCR of the
      low-resolution image was unreliable).

Bullets: one per slide line. A line set closer to the one above than the
page's usual line gap continues that bullet (joined with "\\n", the same
convention as the hand-entered bullets) — e.g. the Apr-<Month> "Products
with YoY Growth" list. Slide numbers in the bottom-right corner are dropped.

Prices: every value label is a coloured number. Labels are split between
the two charts by x (Raw Materials left, Finished Steel right), grouped by
colour, and each colour group is paired with a legend entry by the
smallest total colour distance (label and legend shades differ, so the
pairing is solved as a whole, not per colour). Legend text is matched to
page_market_prices.SERIES_LABEL by closest text. Months: the Raw Materials
x-axis labels are text ("Jan 26" ... "29th Sept"; a spot date counts as its
month); the Finished Steel axis labels are drawn as shapes, so that chart's
months are the consecutive months ending at the same last month. Points go
into month columns by x position, so a missing point leaves a gap rather
than shifting the rest.
"""
import calendar
import difflib
import itertools
import re
from collections import defaultdict
from statistics import median

import pdfplumber

import page_market_prices

_MONTHS = {m.lower(): i for i, m in enumerate(calendar.month_name) if m}
_MONTH_ABBR = {m.lower(): i for i, m in enumerate(calendar.month_abbr) if m}
_MONTH_RE = "|".join(calendar.month_name[1:])

_KPP_TITLE = re.compile(
    rf"^(?P<ytd>April\s*-\s*)?(?P<mon>{_MONTH_RE})\W{{0,2}}(?P<yy>\d{{2}})\s+Key Performance Parameters",
    re.I)
_PRICES_TITLE = "movement of key prices"
_NUM = re.compile(r"\d+(?:\.\d+)?")

# A line closer to the previous one than this fraction of the page's median
# line gap continues the previous bullet.
_CONTINUATION_GAP = 0.85


def _clean(text: str) -> str:
    # The deck's typographic apostrophe comes through as U+FFFD.
    return text.replace("�", "'").strip()


def _ym(year: int, month: int) -> str:
    return f"{year:04d}-{month:02d}"


def _shift(ym: str, n: int) -> str:
    y, m = int(ym[:4]), int(ym[5:7])
    t = y * 12 + (m - 1) + n
    return _ym(t // 12, t % 12 + 1)


def _not_slide_number(page):
    """Drop the slide number printed in the bottom-right corner."""
    w, h = page.width, page.height

    def keep(obj):
        return not (obj.get("object_type") == "char" and obj["x0"] > w * 0.9
                    and obj["top"] > h * 0.8 and obj["text"].strip().isdigit())
    return page.filter(keep)


# ── Commentary ──────────────────────────────────────────────────────────────

def _bullets(lines: list) -> list:
    """Text lines (below the title) -> bullets, joining closely spaced
    continuation lines."""
    if not lines:
        return []
    gaps = [b["top"] - a["top"] for a, b in zip(lines, lines[1:])]
    typical = median(gaps) if gaps else 0
    bullets = [_clean(lines[0]["text"])]
    for gap, line in zip(gaps, lines[1:]):
        text = _clean(line["text"])
        if not text:
            continue
        if typical and gap < typical * _CONTINUATION_GAP:
            bullets[-1] += "\n" + text
        else:
            bullets.append(text)
    return bullets


# ── Market prices ───────────────────────────────────────────────────────────

def _axis_months(text: str) -> list:
    """'Jan 26 Feb 26 Mar'26 ... Aug'26 29th Sept' -> ['2026-01', ..., '2026-09']."""
    tokens = re.findall(r"(\d{1,2}(?:st|nd|rd|th)\s+)?([A-Za-z]{3,9})\W?\s*(\d{2})?", text)
    out, year = [], None
    for _day, mon, yy in tokens:
        m = _MONTHS.get(mon.lower()) or _MONTH_ABBR.get(mon.lower()[:3])
        if not m:
            continue
        if yy:
            year = 2000 + int(yy)
        elif out:  # a spot date with no year ("29th Sept") follows the previous label
            py, pm = int(out[-1][:4]), int(out[-1][5:7])
            year = py + (1 if m < pm else 0)
        if year is None:
            continue
        out.append(_ym(year, m))
    return out


def _dist(a, b):
    return sum((x - y) ** 2 for x, y in zip(a, b)) ** 0.5


def _rgb(color):
    c = tuple(color or ())
    return c if len(c) == 3 else None


def _match_series(label: str) -> str:
    norm = lambda s: re.sub(r"[^a-z0-9]", "", s.lower())
    best, score = None, 0.0
    for code, ref in page_market_prices.SERIES_LABEL.items():
        r = difflib.SequenceMatcher(None, norm(label), norm(ref)).ratio()
        if r > score:
            best, score = code, r
    return best if score >= 0.8 else None


def _columns(xs: list, n: int) -> list:
    """Cluster x positions into n month columns (left to right) — returns
    each column's centre."""
    xs = sorted(xs)
    if len(xs) < n:
        return []
    # split at the n-1 widest gaps
    gaps = sorted(range(1, len(xs)), key=lambda i: xs[i] - xs[i - 1], reverse=True)[:n - 1]
    cuts = sorted(gaps)
    groups, start = [], 0
    for c in cuts + [len(xs)]:
        groups.append(xs[start:c])
        start = c
    return [sum(g) / len(g) for g in groups]


def _extract_prices(page, warnings: list) -> dict:
    words = page.extract_words(extra_attrs=["non_stroking_color"])
    lines = page.extract_text_lines()

    # Raw Materials x-axis: the text line holding the month labels.
    axis = next((l for l in lines if len(_axis_months(l["text"])) >= 3), None)
    if axis is None:
        warnings.append("Key Prices: month axis not found")
        return {"months": [], "series": {}}
    raw_months = _axis_months(axis["text"])
    axis_top = axis["top"]

    # Legend: short coloured stroke segments below the axis, label text to the right.
    segs = [o for o in page.lines if o["top"] > axis_top and 15 < o["x1"] - o["x0"] < 40
            and _rgb(o.get("stroking_color"))]
    if not segs:
        warnings.append("Key Prices: legend not found")
        return {"months": [], "series": {}}
    split = (min(s["x0"] for s in segs) + max(s["x0"] for s in segs)) / 2   # left vs right legend column
    right_col_x = min(s["x0"] for s in segs if s["x0"] >= split)
    legend = []   # (side, rgb, series_code)
    for s in segs:
        side = "L" if s["x0"] < split else "R"
        right_limit = right_col_x if side == "L" else page.width
        y = (s["top"] + s["bottom"]) / 2
        text = " ".join(w["text"] for w in sorted(
            (w for w in words if w["x0"] >= s["x1"] and w["x1"] <= right_limit
             and abs((w["top"] + w["bottom"]) / 2 - y) < 7), key=lambda w: w["x0"]))
        text = re.split(r"\s+Source:", text)[0]
        code = _match_series(text)
        if code is None:
            warnings.append(f"Key Prices: legend entry not recognised: {text!r}")
            continue
        legend.append((side, _rgb(s["stroking_color"]), code))

    # Value labels: coloured numbers above the axis. The chart split for
    # labels is the gap between the two plot areas (the legend columns sit
    # further right than the right plot's left edge), so use the axis end.
    plot_split = axis["x1"] + 5
    groups = defaultdict(list)   # (side, rgb) -> [(xcentre, value)]
    for w in words:
        rgb = _rgb(w.get("non_stroking_color"))
        if (w["top"] >= axis_top or not _NUM.fullmatch(w["text"]) or rgb is None
                or max(rgb) - min(rgb) < 0.1):           # skip black/grey/white text
            continue
        side = "L" if w["x0"] < plot_split else "R"
        groups[(side, tuple(round(c, 3) for c in rgb))].append(((w["x0"] + w["x1"]) / 2, float(w["text"])))

    series, all_months = {}, set()
    for side in ("L", "R"):
        leg = [(rgb, code) for sd, rgb, code in legend if sd == side]
        grp = [(rgb, pts) for (sd, rgb), pts in groups.items() if sd == side]
        if len(grp) != len(leg):
            warnings.append(f"Key Prices: {len(grp)} label colours vs {len(leg)} legend entries "
                            f"({'Raw Materials' if side == 'L' else 'Finished Steel'})")
            continue
        # Pair label colours with legend entries by the smallest total colour distance.
        best = min(itertools.permutations(range(len(leg))),
                   key=lambda p: sum(_dist(grp[i][0], leg[j][0]) for i, j in enumerate(p)))
        n = max(len(pts) for _, pts in grp)
        if side == "L":
            months = raw_months
        else:
            months = [_shift(raw_months[-1], k - n + 1) for k in range(n)]
        if len(months) != n:
            warnings.append(f"Key Prices: {n} points vs {len(months)} axis months (Raw Materials)")
            continue
        centres = _columns([x for _, pts in grp for x, _ in pts], n)
        for i, j in enumerate(best):
            code = leg[j][1]
            vals = {}
            for x, v in grp[i][1]:
                col = min(range(n), key=lambda k: abs(centres[k] - x))
                if months[col] in vals:
                    warnings.append(f"Key Prices: {code} has two values for {months[col]}")
                vals[months[col]] = int(v) if v.is_integer() else v
            series[code] = dict(sorted(vals.items()))
            all_months.update(vals)
    return {"months": sorted(all_months), "series": series}


# ── Entry point ─────────────────────────────────────────────────────────────

def extract_market_commentary_pdf(path: str) -> dict:
    result = {
        "report_month": None,
        "commentary": {"month_items": [], "ytd_items": []},
        "market_prices": {"months": [], "series": {}},
        "skipped_pages": [],
        "warnings": [],
    }
    warnings = result["warnings"]
    found = set()
    with pdfplumber.open(path) as pdf:
        for no, page in enumerate(pdf.pages, start=1):
            page = _not_slide_number(page)
            lines = [l for l in page.extract_text_lines() if l["text"].strip()]
            if not lines:
                result["skipped_pages"].append(no)
                continue
            title = _clean(lines[0]["text"])
            m = _KPP_TITLE.match(title)
            if m:
                ym = _ym(2000 + int(m["yy"]), _MONTHS[m["mon"].lower()])
                key = "ytd_items" if m["ytd"] else "month_items"
                if result["report_month"] and result["report_month"] != ym:
                    warnings.append(f"Page {no}: '{title}' is for {ym}, not {result['report_month']}")
                result["report_month"] = result["report_month"] or ym
                result["commentary"][key] = _bullets(lines[1:])
                found.add(key)
            elif _PRICES_TITLE in title.lower():
                result["market_prices"] = _extract_prices(page, warnings)
                found.add("prices")
    for key, what in (("month_items", "month Key Performance Parameters page"),
                      ("ytd_items", "April-to-month Key Performance Parameters page"),
                      ("prices", "Movement of Key Prices page")):
        if key not in found:
            warnings.append(f"No {what} found")
    return result
