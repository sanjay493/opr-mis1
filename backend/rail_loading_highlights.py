"""
Parser for the Rail Movement Cell's monthly highlights note (plain text, one
"*Rail Transportation Performance of SAIL during <MONTH> <YEAR>*" block per
month) -> the rail_loading_monthly figures of each month. Pure: no database.
scripts/load_rail_loading_highlights.py saves the result.

The note is typed by hand, so each block is normalised first (bold stars
dropped, every dash a "-", whitespace collapsed) and the figures are found
by the phrase in front of them, not by position. Totals are taken as the
note reports them, never summed; only misc_other is derived
(misc_total - misc_pellets).
"""
import calendar
import re
from datetime import date
from typing import Dict, List, Optional, Tuple

# A block starts at every heading, whatever follows it; the month and year
# must then read as "during <MONTH> <YEAR>". A heading typed any other way
# still ends the block before it and is reported, so its figures can never
# be read into the previous month.
_BLOCK_START = re.compile(r"Rail Transportation Performance of SAIL", re.I)
_HEADING = re.compile(r"\s+during\s+([A-Za-z]+)\s+(\d{4})(?!\d)", re.I)
_MONTHS = {name.upper(): i for i, name in enumerate(calendar.month_name) if name}
_NUM = r"(\d+(?:\.\d+)?)"


def _rx(phrase: str) -> "re.Pattern":
    """phrase -> regex: a space is any whitespace (or none), "~" a dash,
    "#" the figure, "#?" a figure that may be left blank."""
    out = re.escape(phrase).replace(r"\ ", r"\s*").replace("\\~", r"\s*-\s*").replace("~", r"\s*-\s*")
    out = out.replace(r"\#\?", _NUM + "?").replace(r"\#", _NUM)
    return re.compile(out, re.I)


# code -> the phrase its figure follows. out_sinter and export_port may be
# blank in the note (= 0); every other figure is required.
PATTERNS = {
    "ore_ogom_jgom": _rx("From OGOM & JGOM Mines ~ # rakes"),
    "ore_bhilai": _rx("From Bhilai Mines ~ # rakes"),
    "ore_total": _rx("Total Iron Ore ~ # rakes"),
    "flux_limestone": _rx("( Limestone ~ # Rakes"),
    "flux_dolomite": _rx("Dolomite ~ # Rakes )"),
    "flux_total": _rx("Total Flux loaded # rakes"),
    "port_coal": _rx("Imported Coal ~ # rakes"),
    "port_limestone": _rx("(b) Lime Stone ~ # Rakes"),
    "port_total": _rx("Total from Ports ~ # rakes"),
    "coal_coking": _rx("( Coking Coal ~ # rakes"),
    "coal_power": _rx("Powerhouse coal ~ # rakes"),
    "coal_total": _rx("Loading of Indigenous Coal ~ # rakes"),
    "misc_pellets": _rx("Pellets ~ #"),
    "misc_total": _rx("Misc raw materials rakes loaded for Plants ~ # rakes"),
    "inward_total": re.compile(r"Total Raw Materials and Coal rakes[^-]{0,80}-\s*" + _NUM + r"\s*rakes", re.I),
    "out_steel": _rx("Total Despatch ~ # rakes"),
    "out_slag": _rx("Total Slag despatched from SAIL Plants ~ # rakes"),
    "out_coke": _rx("Coke & Coke fraction ~ # rakes"),
    "out_sinter": _rx("(iv) Sinter ~ #? rakes"),
    "outward_total": _rx("Total Outward rakes despatched from SAIL Plants ~ # rakes"),
    "grand_total": _rx("during the month was # rakes"),
    "export_port": _rx("Through Ports : #? rake"),
    "export_nepal": _rx("To Nepal Destinations : # rakes"),
    "export_total": _rx("Total export rakes : # rakes"),
}
_MAY_BE_BLANK = ("out_sinter", "export_port")
_OPENING = _rx("total inward was # rakes and total outward was # rakes")


def _normalise(block: str) -> str:
    return re.sub(r"\s+", " ", re.sub("[–—−]", "-", block.replace("*", "")))


def _parse_block(text: str) -> Tuple[Dict[str, float], List[str], List[str]]:
    """-> (values, codes not found, cross-check notes)."""
    values, missing = {}, []
    # "Pellets - N" is read from the misc section onwards only, so pellets
    # mentioned under ore, flux or ports are never taken for it.
    misc = PATTERNS["misc_total"].search(text)
    for code, rx in PATTERNS.items():
        m = rx.search(text, misc.start() if misc else len(text)) if code == "misc_pellets" else rx.search(text)
        if m and m.group(1) is not None:
            values[code] = float(m.group(1))
        elif m and code in _MAY_BE_BLANK:
            values[code] = 0.0
        else:
            missing.append(code)
    notes = []
    if not missing:
        values["misc_other"] = round(values["misc_total"] - values["misc_pellets"], 1)
        m = _OPENING.search(text)
        if m:
            for said, code, word in ((m.group(1), "inward_total", "inward"), (m.group(2), "outward_total", "outward")):
                if float(said) != values[code]:
                    notes.append(f"opening line says total {word} {said}, the section total is {values[code]:g}")
    return values, missing, notes


def parse(text: str, latest: Optional[str] = None) -> Tuple[Dict[str, Dict[str, float]], List[str]]:
    """text -> ({report_month: {item_code: rakes}}, problems). A month whose
    block lacks any figure is listed in problems and left out whole; so is a
    month typed twice, and one after `latest` (YYYY-MM, default the current
    month — a mistyped year). A cross-check mismatch is listed too, but that
    month is still returned."""
    latest = latest or date.today().strftime("%Y-%m")
    months, problems, blocks = {}, [], []
    starts = list(_BLOCK_START.finditer(text))
    for i, s in enumerate(starts):
        end = starts[i + 1].start() if i + 1 < len(starts) else len(text)
        h = _HEADING.match(text, s.end())
        number = h and _MONTHS.get(h.group(1).upper())
        if not number:
            line = text[s.start():end].splitlines()[0].strip()
            problems.append(f"month heading not understood: {line[:90]}")
            continue
        blocks.append((f"{h.group(2)}-{number:02d}", text[h.end():end]))
    seen = [month for month, _body in blocks]
    twice = set()
    for month, body in blocks:
        if seen.count(month) > 1:
            if month not in twice:
                twice.add(month)
                problems.append(f"{month}: heading appears more than once; month skipped")
            continue
        if month > latest:
            problems.append(f"{month}: month is after {latest}; skipped")
            continue
        values, missing, notes = _parse_block(_normalise(body))
        if missing:
            problems.append(f"{month}: not found: {', '.join(missing)}")
            continue
        problems += [f"{month}: {n}" for n in notes]
        months[month] = values
    return months, problems
