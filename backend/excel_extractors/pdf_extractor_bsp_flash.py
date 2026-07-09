"""BSP Flash monthly PDF extractor (e.g. 'BSP flash-jun26.pdf').

The flash PDF is BSP's official monthly production-performance report and
contains, in one file, everything the project otherwise collects from several
BSP Excel uploads:

  Page (found by HEADING, never by page number)          → preview rows
  ------------------------------------------------------------------------
  PRODUCTION PERFORMANCE SUMMARY                         → production_rows
      (same item_names as the PPC MIS .xls extractor)
  BLAST FURNACES (furnace-wise Hot Metal + techno)       → production_rows
      BF#1/4/5/6/7 (furnace weights, like the MIS-2 file) and per-furnace
      CDI / BF Productivity / Slag Rate  → techno_param_rows
  KEY TECHNO-ECONOMIC INDICES                            → techno_param_rows
      Coke/Nut Coke/CDI/Fuel rate, Sinter in burden, SMS-2/3 consumption,
      converter availability, BF productivity, energy rate
  COKE OVENS & COAL CHEMICALS (Yield from Dry Charge)    → techno_param_rows
  SINTERING PLANTS (SP-2/SP-3 operational + basicity)    → techno_param_rows
  STEEL MELTING SHOP - 2 / - 3                           → techno_param_rows
      Utilisation, tap-to-tap, heat weight, ferro-alloy consumption
  RAIL & STRUCTURAL / UNIVERSAL RAIL / MERCHANT /
  WIRE ROD / BAR AND ROD / PLATE MILL                    → techno_param_rows
      Yield, rolling rate, availability, utilisation, heat & power cons.
  STOCK POSITION (closing stock = opening of next month) → stock_rows
      (same rows as the PPC MIS stock extraction)

All (group_code, section, parameter, unit) tuples are copied verbatim from
excel_extractor_bsp.PARAM_MAP_3PAGE / PARAM_MAP_OISCO so the PDF feeds the
SAME techno params as the Excel files.  sort_order is deliberately 0 so a
PDF upload never reshuffles the ordering established by the Excel maps.

Every techno row also carries (t_unit, t_key) — the unit name and param key
from techno_project/bsp_techno_map.json + bsp_oisco_map.json — so
extract_techno_records() can emit techno_data-shaped records
({unit, techno_json:{month, till_month}}) for the /api/bsp-techno pipeline,
exactly like the 3-page-Tech and OISCO Excel extractors.

Neither extract_preview() nor extract_techno_records() writes to the DB.
"""

import logging
import re
from typing import Any, Dict, List, Optional, Tuple

try:
    import pdfplumber
    _PDF_AVAILABLE = True
except ImportError:
    _PDF_AVAILABLE = False

logger = logging.getLogger("pdf_extractor_bsp_flash")

PLANT = "BSP"

_MONTH_ABBR = ["JAN", "FEB", "MAR", "APR", "MAY", "JUN",
               "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"]
_MONTH_FULL = {
    1: "January", 2: "February", 3: "March", 4: "April", 5: "May", 6: "June",
    7: "July", 8: "August", 9: "September", 10: "October", 11: "November",
    12: "December",
}


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------

def _clean(v) -> Optional[float]:
    if v is None:
        return None
    s = str(v).strip()
    if s in ("", "-", "--", "---", "—", "N/A", "NA", "NS", "nan",
             "#DIV/0!", "#VALUE!", "#REF!"):
        return None
    try:
        return float(s.replace(",", ""))
    except (ValueError, TypeError):
        return None


def _nums(text: str) -> List[float]:
    """All numbers in a text fragment (commas allowed, '#DIV/0!' ignored)."""
    out = []
    for tok in re.findall(r"-?\d[\d,]*(?:\.\d+)?", text.replace("#DIV/0!", " ")):
        v = _clean(tok)
        if v is not None:
            out.append(v)
    return out


def _cell(row: List, idx: int) -> str:
    if idx < 0 or idx >= len(row) or row[idx] is None:
        return ""
    return str(row[idx]).strip()


def _norm_label(s: str) -> str:
    """Normalize a table-cell label: newlines → space, squeeze, lowercase."""
    return re.sub(r"\s+", " ", str(s or "").replace("\n", " ")).strip().lower()


# ---------------------------------------------------------------------------
# Report month detection + header-token matching
# ---------------------------------------------------------------------------

def _detect_file_month(pages_text: List[str]) -> Optional[Tuple[int, int]]:
    """Return (year, month) from the cover / summary page, or None."""
    months = "|".join(_MONTH_ABBR)
    for text in pages_text[:5]:
        up = (text or "").upper()
        # 'JUN-2026' (cover) or 'SUMMARY: JUNE'2026'
        m = re.search(rf"\b({months})[A-Z]*\s*[-'’.,]?\s*(20\d{{2}})\b", up)
        if m:
            return int(m.group(2)), _MONTH_ABBR.index(m.group(1)) + 1
    return None


def _month_cell_re(mon: int, year: int):
    """Regex matching this report month in a column header cell:
    JUN'26 / Jun-2026 / JUN.- 2026 / JUN-26 — but NOT JUN'25 / APR'26-JUN'26."""
    abbr = _MONTH_ABBR[mon - 1]
    yy = f"{year % 100:02d}"
    return re.compile(
        rf"^\s*{abbr}[A-Z]*\s*[-'’., ]*\s*(?:20)?{yy}\s*$", re.IGNORECASE)


def _cum_cell_re(mon: int, year: int):
    """Regex matching the Apr-to-month cumulative header cell:
    APR'26-JUN'26 / APRIL'26-JUN'26 / APR-JUN-2026 / CUM / CUM."""
    abbr = _MONTH_ABBR[mon - 1]
    yy = f"{year % 100:02d}"
    return re.compile(
        rf"(^\s*CUM\.?\s*$)|(^\s*APR[A-Z']*\s*[-'’. ]*(?:{yy}\s*)?-\s*{abbr}"
        rf"[A-Z]*\s*[-'’. ]*(?:20)?{yy}\s*$)",
        re.IGNORECASE | re.DOTALL)


# ---------------------------------------------------------------------------
# Page index — every page is found by its heading, never by page number
# ---------------------------------------------------------------------------

_PAGE_ANCHORS = {
    # key: (must-contain-all, must-contain-any-of-these-too)
    # 2nd anchor keeps the CONTENTS page (which lists the same headings)
    # from being mistaken for the data page.
    "production": (["PRODUCTION PERFORMANCE SUMMARY"],
                   ["TOTAL SALEABLE STEEL PRODN"]),
    "key_techno": (["KEY TECHNO-ECONOMIC INDICES"], ["IMPORT COAL IN BLEND"]),
    "coke":       (["COKE OVENS"], ["YIELD FROM DRY CHARGE"]),
    "sinter":     (["SINTERING PLANTS"], ["OPERATIONAL CHARACTERISTICS"]),
    "bf":         (["BLAST FURNACES"], ["HOT METAL PRODUCTION",
                                        "TECHNO-ECONOMIC"]),
    "sms2":       (["STEEL MELTING SHOP - 2"], ["SP.CONS.OF RAW MATERIALS"]),
    "sms3":       (["STEEL MELTING SHOP - 3"], ["SP.CONS.OF RAW MATERIALS"]),
    "rsm":        (["RAIL & STRUCTURAL MILL"], ["MILL AVAILABILITY"]),
    "urm":        (["UNIVERSAL RAIL MILL"], ["MILL AVAILABILITY"]),
    "mm":         (["MERCHANT MILL"], ["MILL AVAILABILITY"]),
    "wrm":        (["WIRE ROD MILL"], ["MILL AVAILABILITY"]),
    "brm":        (["BAR AND ROD MILL"], ["MILL AVAILABILITY"]),
    "pm":         (["PLATE MILL"], ["MILL AVAILABILITY"]),
    "stock":      (["STOCK POSITION"], ["IN-PROCESS SEMIS"]),
}


def _build_page_index(pages_text: List[str]) -> Dict[str, int]:
    idx: Dict[str, int] = {}
    for pno, text in enumerate(pages_text):
        up = (text or "").upper()
        for key, (need_all, need_any) in _PAGE_ANCHORS.items():
            if key in idx:
                continue
            if all(a in up for a in need_all) and any(a in up for a in need_any):
                idx[key] = pno
    return idx


# ---------------------------------------------------------------------------
# Block 1 — Production Performance Summary (production_rows)
# ---------------------------------------------------------------------------
# Each entry: (label_regex, item_name, divide_by_1000)
# Matched SEQUENTIALLY down the page — the cursor only moves forward, so
# short labels like '^URM' or '^Total' can never match an earlier row.
# Value taken = 2nd number after the label (columns are ABP | ACTUAL | ...).

_PROD_MAP: List[Tuple[str, str, bool]] = [
    (r"Bat\.?\s*1\s*-\s*8",                    "COB#1-8",                False),
    (r"Eq\.?\s*Ovens",                         "Oven Pushing (nos/day)", False),
    (r"SINTER\s+SP\s*-\s*2|SP\s*-\s*2\b",      "SP-2",                   True),
    (r"Total\s+SP\s*-?\s*3",                   "SP-3",                   True),
    (r"Total\s+Sinter",                        "Total Sinter",           True),
    (r"BF\s*:?\s*1\s*-\s*7",                   "BF#1-7",                 True),
    (r"BF\s*:?\s*8\b",                         "BF#8",                   True),
    (r"^Total\b",                              "Hot Metal",              True),
    (r"Pig\s+Iron",                            "Pig Iron",               True),
    (r"Total\s+Cast\s+Steel",                  "SMS-2",                  True),
    (r"Cast\s+Steel\s+Prodn",                  "SMS-3",                  True),
    (r"Total\s+Crude\s+Steel\s+Production",    "Total Crude Steel",      True),
    (r"Total\s*\(\s*Rails\s*&\s*Structurals\)", "RSM_RAIL",              True),
    (r"URM\s+FINISHED\s+Rails",                "URM_RAIL",               True),
    (r"PRIME\s+RAIL\s+PRODN\.?\s+RSM",         "RSMPRIME",               True),
    (r"^URM\b",                                "URMPRIME",               True),
    (r"MERCHANT\s+MILL\s+PRODN",               "MM",                     True),
    (r"WIRE\s+RODS?\s+MILL\s+PRODN",           "WIRERODS",               True),
    (r"^BRM\b",                                "BARS&RODMILL",           True),
    (r"Finished\s+Plates",                     "PLATEMILL",              True),
    (r"TOTAL\s+FINISHED\s+STEEL\s+PRODN",      "Finished Steel",         True),
    (r"Total\s+SEMIS",                         "Saleable Semis",         True),
    (r"TOTAL\s+SALEABLE\s+STEEL\s+PRODN",      "Saleable Steel",         True),
]


def _parse_production(text: str, page_no: int) -> List[Dict[str, Any]]:
    lines = [ln.strip() for ln in (text or "").splitlines() if ln.strip()]
    rows: List[Dict[str, Any]] = []
    cursor = 0
    for pattern, item_name, divide in _PROD_MAP:
        rx = re.compile(pattern, re.IGNORECASE)
        val = None
        label = ""
        for li in range(cursor, len(lines)):
            m = rx.search(lines[li])
            if not m:
                continue
            nums = _nums(lines[li][m.end():])
            if len(nums) >= 2:                    # ABP | ACTUAL | ...
                val = nums[1]
                label = lines[li][:m.end()].strip()
                cursor = li + 1
                break
        if val is not None and divide:
            val = round(val / 1000.0, 3)
        rows.append({
            "item_name": item_name,
            "value":     val,
            "unit":      "'000T" if divide else "nos/d",
            "cell":      f"PDF p{page_no + 1}",
            "pdf_label": label or item_name,
            "status":    "ok" if val is not None else "skip",
        })
    return rows


# ---------------------------------------------------------------------------
# Block 2 — Key Techno-Economic Indices page (text lines)
# ---------------------------------------------------------------------------
# Line layout: <label> <unit> <month> <Apr-to-month cum> <prev.month> ...
# Entries matched sequentially (the page has two 'Steel scrap cons.' lines —
# SMS-2 first, then SMS-3 — and '- SMS-2/3' availability lines come before
# the rate-of-production block).

# (label_regex, (group, section, parameter, unit), (techno_data unit, key))
_KEY_TECHNO_MAP: List[Tuple[str, Tuple[str, str, str, str], Tuple[str, str]]] = [
    (r"^Coke\s+rate",           ("IRON_MAKING", "BF Coke Rate",  "BSP", "Kg/THM"),
     ("BF_Shop", "coke_rate")),
    (r"^Nut\s+Coke\s+rate",     ("IRON_MAKING", "Nut Coke Rate", "BSP", "Kg/THM"),
     ("BF_Shop", "nut_coke_rate")),
    (r"^Total\s+Fuel\s+rate",   ("IRON_MAKING", "Fuel Rate",     "BSP", "Kg/THM"),
     ("BF_Shop", "fuel_rate")),
    (r"^Sinter\s+in\s+burden",  ("IRON_MAKING", "Sinter in Burden", "BSP", "%"),
     ("BF_Shop", "sinter% in burden")),
    (r"^SMS\s*-?\s*2\s*:?\s*Hot\s*metal\s+cons",
     ("SMS", "SMS-II Consumption",  "Hot Metal",              "Kg/TCS"),
     ("SMS-2", "specific_hm_consumption")),
    (r"^Steel\s+scrap\s+cons",
     ("SMS", "SMS-II Consumption",  "Scrap",                  "Kg/TCS"),
     ("SMS-2", "specific_scrap_consumption")),
    (r"^Total\s+Metallic\s+Input",
     ("SMS", "SMS-II Consumption",  "Total Metallic Charge",  "Kg/TCS"),
     ("SMS-2", "tmi")),
    (r"^SMS\s*-?\s*3\s*:?\s*Hot\s*metal\s+cons",
     ("SMS", "SMS-III Consumption", "Hot Metal",              "Kg/TCS"),
     ("SMS-3", "specific_hm_consumption")),
    (r"^Steel\s+scrap\s+cons",
     ("SMS", "SMS-III Consumption", "Scrap",                  "Kg/TCS"),
     ("SMS-3", "specific_scrap_consumption")),
    (r"^Total\s+metallic\s+input",
     ("SMS", "SMS-III Consumption", "Total Metallic Charge",  "Kg/TCS"),
     ("SMS-3", "tmi")),
    (r"^Overall\s+energy\s+rate",
     ("MILL_BSP", "Energy", "Sp. Energy Consumption", "G.Cal/T"),
     ("General", "specific_energy_consumption")),
    (r"^-\s*SMS\s*-?\s*2\s+%",
     ("SMS", "BSP SMS-2", "Converter Availability", "% ICH"),
     ("SMS-2", "converter_availability")),
    (r"^-\s*SMS\s*-?\s*3\s+%",
     ("SMS", "BSP SMS-3", "Converter Availability", "% ICH"),
     ("SMS-3", "converter_availability")),
]
# Note: CDI, BF Productivity and Slag Rate come from the BLAST FURNACES page
# (per-furnace + shop total); SP-2/SP-3 productivity comes from the
# SINTERING PLANTS page (3 decimals there vs 2 on this page).


def _parse_key_techno(text: str, page_no: int) -> List[Dict[str, Any]]:
    lines = [ln.strip() for ln in (text or "").splitlines() if ln.strip()]
    rows: List[Dict[str, Any]] = []
    cursor = 0
    for pattern, (group, section, param, unit), (t_unit, t_key) in _KEY_TECHNO_MAP:
        rx = re.compile(pattern, re.IGNORECASE)
        actual = cum = None
        label = ""
        for li in range(cursor, len(lines)):
            m = rx.search(lines[li])
            if not m:
                continue
            nums = _nums(lines[li][m.end():])
            if len(nums) >= 2:
                actual, cum = nums[0], nums[1]
                label = lines[li][:m.end()].strip()
                cursor = li + 1
                break
        rows.append(_techno_row(group, section, param, unit, actual, cum,
                                f"PDF p{page_no + 1}", label, t_unit, t_key))
    return rows


def _techno_row(group: str, section: str, param: str, unit: str,
                actual, cum, cell: str, file_label: str,
                t_unit: str = "", t_key: str = "") -> Dict[str, Any]:
    return {
        "group_code": group, "section": section, "parameter": param,
        "unit": unit, "actual": actual, "cum_actual": cum,
        "sort_order": 0, "cell": cell,
        "file_label": file_label or param, "plant": PLANT,
        "found_via": "flash-pdf",
        # techno_data (bsp_techno_map / bsp_oisco_map) addressing:
        "t_unit": t_unit, "t_key": t_key,
        "status": "ok" if (actual is not None or cum is not None) else "skip",
    }


# ---------------------------------------------------------------------------
# Table helpers (pdfplumber extract_tables)
# ---------------------------------------------------------------------------

def _find_month_cum_cols(row: List, mon_re, cum_re) -> Tuple[Optional[int], Optional[int]]:
    """Column indexes of the report-month header cell and the cum cell."""
    m_col = c_col = None
    for i in range(len(row)):
        c = _cell(row, i).replace("\n", "")
        if m_col is None and mon_re.match(c):
            m_col = i
        elif m_col is not None and c_col is None and cum_re.match(c):
            c_col = i
    if m_col is not None and c_col is None:
        c_col = m_col + 1
    return m_col, c_col


# ---------------------------------------------------------------------------
# Block 3 — Coke Ovens page: Yield from Dry Charge (table)
# ---------------------------------------------------------------------------
# Columns: label | unit | Norm | <month> | <Apr-cum> | prior years...

_COKE_YIELD_MAP = [
    ("bf coke",           ("COKE_SINTER", "Coke Yield", "BF Coke",           "%"),
     "bf_coke_yield"),
    ("crude tar",         ("COKE_SINTER", "Coke Yield", "Crude Tar",         "%"),
     "crude_tar_yield"),
    ("crude benzol",      ("COKE_SINTER", "Coke Yield", "Crude Benzol",      "%"),
     "crude_benzol_yield"),
    ("ammonium sulphate", ("COKE_SINTER", "Coke Yield", "Ammonium Sulphate", "%"),
     "ammonium_sulphate_yield"),
]


def _parse_coke_tables(tables, page_no: int, mon_re, cum_re) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for tbl in tables:
        flat = " ".join(_norm_label(c) for r in tbl for c in r if c)
        if "yield from dry charge" not in flat:
            continue
        m_col = c_col = None
        done = set()
        for r in tbl:
            mc, cc = _find_month_cum_cols(r, mon_re, cum_re)
            if mc is not None and mc >= 2:      # skip production-block headers
                m_col, c_col = mc, cc
            if m_col is None:
                continue
            label = _norm_label(_cell(r, 0))
            for key, tup, t_key in _COKE_YIELD_MAP:
                if key in done or not label.startswith(key):
                    continue
                done.add(key)
                rows.append(_techno_row(
                    *tup, _clean(_cell(r, m_col)), _clean(_cell(r, c_col)),
                    f"PDF p{page_no + 1}", _cell(r, 0).replace("\n", " "),
                    "COB", t_key))
        break
    return rows


# ---------------------------------------------------------------------------
# Block 4 — Sintering Plants page: SP-2 / SP-3 (table)
# ---------------------------------------------------------------------------
# Header rows carry the report month TWICE (SP-2 block, then SP-3 block);
# each value row holds month + cum in adjacent columns under each block.

_SINTER_PARAM_MAP = [
    ("machine avail",       "Machine Availability", "%",       "machine_availability"),
    ("machine utilisation", "Machine Utilisation",  "%",       "machine_utilisation"),
    ("productivity",        "Productivity",         "T/m²/hr", "specific_productivity"),
    ("basicity",            "Basicity",             "",        "basicity"),
]


def _parse_sinter_tables(tables, page_no: int, mon_re, cum_re) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    done = set()
    for tbl in tables:
        month_cols: List[int] = []
        for r in tbl:
            mcs = [i for i in range(len(r))
                   if mon_re.match(_cell(r, i).replace("\n", ""))]
            if mcs:
                month_cols = mcs
            if len(month_cols) < 2:
                continue
            label = _norm_label(_cell(r, 0))
            for key, param, unit, t_key in _SINTER_PARAM_MAP:
                if key in done or not label.startswith(key):
                    continue
                done.add(key)
                for sp_idx, section, t_unit in ((0, "Sinter Plant SP-2", "SP-2"),
                                                (1, "Sinter Plant SP-3", "SP-3")):
                    mc = month_cols[sp_idx]
                    rows.append(_techno_row(
                        "COKE_SINTER", section, param, unit,
                        _clean(_cell(r, mc)), _clean(_cell(r, mc + 1)),
                        f"PDF p{page_no + 1}", _cell(r, 0).replace("\n", " "),
                        t_unit, t_key))
    return rows


# ---------------------------------------------------------------------------
# Block 5 — Blast Furnaces page (table): furnace-wise production + techno
# ---------------------------------------------------------------------------

_BF_HEADER_COLS = ["BF-1", "BF-4", "BF-5", "BF-6", "BF-7", "BF-1-7",
                   "BF-8", "BF-1-8"]

# anchor keyword (in first 3 cells) → techno spec:
#   {furnace-header: (group, section, parameter, unit)}
_BF_TECHNO_SPECS = {
    "productivity": {
        "BF-7":   (("IRON_MAKING", "BF Productivity", "BSP BF-7", "T/m³/day"),
                   ("BF-7",    "bf_productivity")),
        "BF-8":   (("IRON_MAKING", "BF Productivity", "BSP BF-8", "T/m³/day"),
                   ("BF-8",    "bf_productivity")),
        "BF-1-8": (("IRON_MAKING", "BF Productivity", "BSP",      "T/m³/day"),
                   ("BF_Shop", "bf_productivity")),
    },
    "cdi": {
        "BF-4":   (("IRON_MAKING", "CDI", "BSP BF-4", "Kg/THM"), ("BF-4",    "cdi")),
        "BF-5":   (("IRON_MAKING", "CDI", "BSP BF-5", "Kg/THM"), ("BF-5",    "cdi")),
        "BF-6":   (("IRON_MAKING", "CDI", "BSP BF-6", "Kg/THM"), ("BF-6",    "cdi")),
        "BF-7":   (("IRON_MAKING", "CDI", "BSP BF-7", "Kg/THM"), ("BF-7",    "cdi")),
        "BF-8":   (("IRON_MAKING", "CDI", "BSP BF-8", "Kg/THM"), ("BF-8",    "cdi")),
        "BF-1-8": (("IRON_MAKING", "CDI", "BSP",      "Kg/THM"), ("BF_Shop", "cdi")),
    },
    "slag rate": {
        "BF-1-8": (("IRON_MAKING", "Slag Rate", "BSP", "Kg/THM"),
                   ("BF_Shop", "slag_rate")),
    },
}

# Furnaces whose for-the-month Hot Metal goes into production_rows.
# BF-8 / BF-1-7 / totals already come from the summary page.
_BF_PROD_FURNACES = ["BF-1", "BF-4", "BF-5", "BF-6", "BF-7"]

# EVERY parameter heading on the Blast Furnaces page, in a first-match-wins
# order.  Headings not extracted still MUST switch the active block, or their
# month/cum rows would be credited to the previous parameter.
_BF_ANCHORS = ["hot metal production", "productivity", "bf coke", "nut coke",
               "cdi", "total fuel", "carbon", "slag rate", "sinter in burden",
               "overall availability", "overall utilisation", "tuyere",
               "distribution of hot metal", "slag processing"]


def _parse_bf_tables(tables, page_no: int, mon_re, cum_re):
    prod_rows: List[Dict[str, Any]] = []
    techno_rows: List[Dict[str, Any]] = []
    for tbl in tables:
        # header row → furnace column map
        fur_cols: Dict[str, int] = {}
        for r in tbl:
            cells = [_cell(r, i).replace("\n", "").upper() for i in range(len(r))]
            if "BF-4" in cells and "BF-8" in cells:
                for name in _BF_HEADER_COLS:
                    if name in cells:
                        fur_cols[name] = cells.index(name)
                break
        if not fur_cols:
            continue

        current: Optional[str] = None      # active anchor key
        prod_done = False
        for r in tbl:
            joined = _norm_label(" ".join(_cell(r, i) for i in range(min(3, len(r)))))
            for key in _BF_ANCHORS:
                if key == "hot metal production":
                    if key in joined:
                        current = key
                        break
                elif re.search(rf"(?:^|\W){re.escape(key)}", joined):
                    current = key
                    break
            if current is None or (current != "hot metal production"
                                   and current not in _BF_TECHNO_SPECS):
                continue
            # month / cum row inside the active block?
            row_kind = None
            for i in range(min(3, len(r))):
                c = _cell(r, i).replace("\n", "")
                if mon_re.match(c):
                    row_kind = "month"
                    break
                if cum_re.match(c):
                    row_kind = "cum"
                    break
            if row_kind is None:
                continue

            if current == "hot metal production":
                if row_kind == "month" and not prod_done:
                    prod_done = True
                    for name in _BF_PROD_FURNACES:
                        col = fur_cols.get(name)
                        val = _clean(_cell(r, col)) if col is not None else None
                        v = round(val / 1000.0, 3) if val is not None else None
                        prod_rows.append({
                            "item_name": name.replace("BF-", "BF#"),
                            "value":     v,
                            "unit":      "'000T",
                            "cell":      f"PDF p{page_no + 1}",
                            "pdf_label": name,
                            "status":    "ok" if v is not None else "skip",
                        })
                continue

            spec = _BF_TECHNO_SPECS[current]
            for name, (tup, (t_unit, t_key)) in spec.items():
                col = fur_cols.get(name)
                if col is None:
                    continue
                val = _clean(_cell(r, col))
                existing = next(
                    (t for t in techno_rows
                     if t["section"] == tup[1] and t["parameter"] == tup[2]),
                    None)
                if existing is None:
                    existing = _techno_row(*tup, None, None,
                                           f"PDF p{page_no + 1}",
                                           f"{current.title()} {name}",
                                           t_unit, t_key)
                    techno_rows.append(existing)
                if row_kind == "month":
                    existing["actual"] = val
                else:
                    existing["cum_actual"] = val
                existing["status"] = ("ok" if (existing["actual"] is not None or
                                               existing["cum_actual"] is not None)
                                      else "skip")
        if prod_rows or techno_rows:
            break
    return prod_rows, techno_rows


# ---------------------------------------------------------------------------
# Block 6 — Steel Melting Shops 2 & 3
# ---------------------------------------------------------------------------
# Converter Utilisation comes from the shop table; Availability comes from
# the Key-Techno page (the shop tables occasionally lose a digit there).
# Ferro-alloy consumption arrives as newline-packed cells: the label cell and
# the month/cum cells hold one line per item, matched by line index.

_SMS_CONS_MAP = {
    "si mn": ("Si-Mn Consumption", "Kg/TCS", "si-mn"),
    "fe si": ("Fe-Si Consumption", "Kg/TCS", "fe-si"),
    "fe mn": ("Fe-Mn Consumption", "Kg/TCS", "fe-mn"),
}


def _parse_sms_page(tables, text: str, page_no: int, shop: str,
                    mon_re, cum_re) -> List[Dict[str, Any]]:
    """shop: 'BSP SMS-2' or 'BSP SMS-3' (OISCO section names)."""
    rows: List[Dict[str, Any]] = []
    cellref = f"PDF p{page_no + 1}"
    t_unit = shop.replace("BSP ", "")          # 'SMS-2' / 'SMS-3'

    # --- Converter Utilisation (% of available hours) from the shop table ---
    for tbl in tables:
        flat = " ".join(_norm_label(c) for r in tbl for c in r if c)
        if "availability (%of cal hrs)" not in flat:
            continue
        avail_col = util_col = None
        for r in tbl:
            # header sub-row: month cells under Availability and Utilisation
            mcs = [i for i in range(len(r))
                   if mon_re.match(_cell(r, i).replace("\n", ""))]
            if len(mcs) >= 2:
                avail_col, util_col = mcs[0], mcs[1]
                continue
            if util_col is None:
                continue
            first = _norm_label(_cell(r, 0))
            if not first.startswith("converter"):
                continue
            lines = [_norm_label(x) for x in _cell(r, 0).split("\n")]
            li = next((i for i, x in enumerate(lines) if x.startswith("converter")), 0)

            def _line_val(col_idx, line_idx=li):
                parts = _cell(r, col_idx).split("\n")
                return _clean(parts[line_idx]) if line_idx < len(parts) else None

            rows.append(_techno_row(
                "SMS", shop, "Converter Utilisation", "% Avail hr",
                _line_val(util_col), _line_val(util_col + 1),
                cellref, "Converter Utilisation (%of Avl Hrs)",
                t_unit, "converter_utilisation"))
            break
        break

    # --- Ferro-alloy specific consumption (newline-packed cells) ------------
    for tbl in tables:
        for r in tbl:
            first = _norm_label(_cell(r, 0))
            if not (first.startswith("hotmetal") or first.startswith("hot metal")):
                continue
            labels = [_norm_label(x) for x in _cell(r, 0).split("\n")]
            # value columns: the two right-most cells with the same line count
            packed = [i for i in range(1, len(r))
                      if len(_cell(r, i).split("\n")) == len(labels)]
            if len(packed) < 2:
                continue
            m_col, c_col = packed[-2], packed[-1]
            m_parts = _cell(r, m_col).split("\n")
            c_parts = _cell(r, c_col).split("\n")
            for li, lab in enumerate(labels):
                for key, (param, unit, t_key) in _SMS_CONS_MAP.items():
                    if lab.startswith(key):
                        rows.append(_techno_row(
                            "SMS", shop, param, unit,
                            _clean(m_parts[li]), _clean(c_parts[li]),
                            cellref, _cell(r, 0).split("\n")[li],
                            t_unit, t_key))
            break

    # --- Tap-to-tap time / average heat weight / DS heats (text lines) ------
    lines = [ln.strip() for ln in (text or "").splitlines() if ln.strip()]

    def _text_param(pattern, param, unit, t_key, n_month=0, n_cum=1):
        rx = re.compile(pattern, re.IGNORECASE)
        for li, ln in enumerate(lines):
            m = rx.search(ln)
            if not m:
                continue
            nums = _nums(ln[m.end():])
            if not nums and li + 1 < len(lines):     # values on the next line
                nums = _nums(lines[li + 1])
            if len(nums) > max(n_month, n_cum):
                rows.append(_techno_row("SMS", shop, param, unit,
                                        nums[n_month], nums[n_cum],
                                        f"PDF p{page_no + 1}", ln[:60],
                                        t_unit, t_key))
            return

    _text_param(r"TAP\s+TO\s+TAP\s+TIME(?:\s*\(MIN\.?\))?",
                "Tap to Tap Time", "Min", "tap_to_tap_time")
    _text_param(r"AV(?:G)?\.?\s*(?:WT\.?/BLOW|heat\s+wt\./Blows)\s*\(T\)[^\d]*",
                "Average Heat Weight", "T", "average_heat_weight")
    if shop.endswith("3"):
        _text_param(r"Heats\s+thro'?\s+Desulphurisation\s+unit\s*\(Nos\)",
                    "DS Heats", "Nos.", "ds_heats")
    return rows


# ---------------------------------------------------------------------------
# Block 7 — Rolling mills (tables)
# ---------------------------------------------------------------------------
# Techno table layout: label | unit | ABP/Norm | <month> | <Apr-cum> | ...
# The month column is located from the sub-header row of the techno table
# (its month cell sits at col >= 3, unlike the production header at col 1).

_MILL_SECTIONS = {
    "rsm": "Rail & Structural Mill",
    "urm": "Universal Rail Mill",
    "mm":  "Merchant Mill",
    "wrm": "Wire Rod Mill",
    "brm": "Bar & Rod Mill",
    "pm":  "Plate Mill",
}

# (label regex on normalized text, parameter, unit, techno_data key)
_MILL_PARAM_SPECS = [
    (r"^yield(?!.*as rolled)",    "Yield",             "%",         "yield"),
    (r"^mill availability",       "Mill Availability", "%",         "availability"),
    (r"^mill utilisation.*avail", "Mill Utilisation",  "%",         "utilisation"),
    (r"^rolling rate",            "Rolling Rate",      "T/Hr",      "rolling_rate"),
    (r"^heat consump",            "Heat Consumption",  "103Kcal/T", "heat_consumption"),
    (r"^power consump",           "Power Consumption", "Kwh/T",     "power_consumption"),
]

# PARAM_MAP_3PAGE carries no heat/power rows for BRM — keep parity.
_MILL_SKIP = {"brm": {"Heat Consumption", "Power Consumption"}}


def _parse_mill_tables(tables, page_no: int, mill_key: str,
                       mon_re, cum_re) -> List[Dict[str, Any]]:
    section = _MILL_SECTIONS[mill_key]
    skip = _MILL_SKIP.get(mill_key, set())
    rows: List[Dict[str, Any]] = []
    done = set()
    m_col = c_col = None
    for tbl in tables:
        for r in tbl:
            mc, cc = _find_month_cum_cols(r, mon_re, cum_re)
            if mc is not None and mc >= 3:       # techno sub-header, not prodn
                m_col, c_col = mc, cc
            if m_col is None:
                continue
            label = _norm_label(_cell(r, 0))
            if not label:
                continue
            for rx, param, unit, t_key in _MILL_PARAM_SPECS:
                if param in done or param in skip or not re.search(rx, label):
                    continue
                actual = _clean(_cell(r, m_col))
                cum = _clean(_cell(r, c_col))
                if actual is None and cum is None:
                    continue
                done.add(param)
                rows.append(_techno_row(
                    "MILL_BSP", section, param, unit, actual, cum,
                    f"PDF p{page_no + 1}", _cell(r, 0).replace("\n", " "),
                    mill_key.upper(), t_key))
    return rows


# ---------------------------------------------------------------------------
# Block 8 — Stock Position page (closing stock = opening of next month)
# ---------------------------------------------------------------------------
# Column headers are as-on dates (1-04-2023 ... 1-07-2026): the LAST column
# is the 1st of the month after the report month.  Values in Tonnes → '000T.

def _parse_stock(text: str, page_no: int, report_month: str) -> List[Dict[str, Any]]:
    lines = [ln.strip() for ln in (text or "").splitlines() if ln.strip()]

    # stock month from the last as-on date column, fallback: next month
    def _next_month(m):
        y, mo = int(m[:4]), int(m[5:7])
        return f"{y + 1 if mo == 12 else y}-{1 if mo == 12 else mo + 1:02d}"

    stock_month = _next_month(report_month)
    for ln in lines:
        dates = re.findall(r"\b0?1-(\d{2})-(20\d{2})\b", ln)
        if len(dates) >= 3:
            mm, yyyy = dates[-1]
            stock_month = f"{yyyy}-{mm}"
            break

    def _last_num(pattern, start=0, occurrence=1):
        """Last number on the matching line (= latest as-on column)."""
        rx = re.compile(pattern, re.IGNORECASE)
        seen = 0
        for li in range(start, len(lines)):
            m = rx.search(lines[li])
            if not m:
                continue
            seen += 1
            if seen < occurrence:
                continue
            nums = _nums(lines[li][m.end():])
            return (nums[-1] if nums else None), li
        return None, None

    fin_steel, _ = _last_num(r"Total\s+Finished\s+Steel")
    slabs_sale, li_sale = _last_num(r":?\s*CCS\s+Slabs")
    semis_sale, _ = _last_num(r"Total\s+Saleable\s+Semis")
    # second ':CCS Slabs' occurrence = the In-Process section
    slabs_wip, _ = _last_num(r":?\s*CCS\s+Slabs", occurrence=2)
    semis_wip, _ = _last_num(r"Total\s+In-Process\s+Semis")
    pig_iron, _ = _last_num(r"^\d*\s*Pig\s+Iron")

    def _t(v):
        return round(v / 1000.0, 3) if v is not None else None

    bb_sale = (semis_sale - slabs_sale
               if semis_sale is not None and slabs_sale is not None else None)
    bb_wip = (semis_wip - slabs_wip
              if semis_wip is not None and slabs_wip is not None else None)

    def _row(item, stype, val, formula):
        return {"plant": PLANT, "item_type": item, "stock_type": stype,
                "stock_month": stock_month, "value": _t(val),
                "formula": formula, "cell": f"PDF p{page_no + 1}",
                "status": "ok" if val is not None else "skip"}

    return [
        _row("SLABS",          "FOR SALE",  slabs_sale, "Saleable CCS Slabs"),
        _row("SLABS",          "INPROCESS", slabs_wip,  "In-Process CCS Slabs"),
        _row("BLOOM/BILLETS",  "FOR SALE",  bb_sale,    "Saleable Semis - CCS Slabs"),
        _row("BLOOM/BILLETS",  "INPROCESS", bb_wip,     "In-Process Semis - CCS Slabs"),
        _row("FINISHED STEEL", "",          fin_steel,  "Total Finished Steel"),
        _row("PIG IRON",       "",          pig_iron,   "Pig Iron"),
    ]


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def extract_preview(file_path: str, report_month: str) -> dict:
    """Extract BSP flash monthly PDF → standard preview dict (no DB writes)."""
    if not _PDF_AVAILABLE:
        raise ImportError(
            "pdfplumber is required for the BSP flash PDF: pip install pdfplumber")

    with pdfplumber.open(file_path) as pdf:
        pages_text = [(p.extract_text() or "") for p in pdf.pages]
        page_idx = _build_page_index(pages_text)
        logger.info("BSP flash PDF: %d pages, anchors found: %s",
                    len(pages_text),
                    {k: v + 1 for k, v in sorted(page_idx.items(), key=lambda kv: kv[1])})

        if "production" not in page_idx:
            raise ValueError(
                "This PDF does not look like a BSP flash monthly report "
                "('PRODUCTION PERFORMANCE SUMMARY' page not found).")

        # ------- resolve report month (file wins over UI selection) ---------
        detected = _detect_file_month(pages_text)
        if detected:
            y, m = detected
            db_month = f"{y}-{m:02d}"
        elif report_month and len(report_month) >= 7:
            y, m = int(report_month[:4]), int(report_month[5:7])
            db_month = report_month
        else:
            raise ValueError("Cannot determine the report month from the PDF; "
                             "please select a month (YYYY-MM).")
        month_mismatch = bool(report_month and db_month != report_month)
        if month_mismatch:
            logger.warning("BSP flash PDF: file month %s != selected %s — "
                           "file month will be used", db_month, report_month)

        mon_re = _month_cell_re(m, y)
        cum_re = _cum_cell_re(m, y)

        # ------------------- production ------------------------------------
        p = page_idx["production"]
        production_rows = _parse_production(pages_text[p], p)

        # ------------------- techno ----------------------------------------
        techno_rows: List[Dict[str, Any]] = []

        if "key_techno" in page_idx:
            p = page_idx["key_techno"]
            techno_rows += _parse_key_techno(pages_text[p], p)

        if "coke" in page_idx:
            p = page_idx["coke"]
            techno_rows += _parse_coke_tables(pdf.pages[p].extract_tables(),
                                              p, mon_re, cum_re)

        if "sinter" in page_idx:
            p = page_idx["sinter"]
            techno_rows += _parse_sinter_tables(pdf.pages[p].extract_tables(),
                                                p, mon_re, cum_re)

        if "bf" in page_idx:
            p = page_idx["bf"]
            bf_prod, bf_techno = _parse_bf_tables(pdf.pages[p].extract_tables(),
                                                  p, mon_re, cum_re)
            production_rows += bf_prod
            techno_rows += bf_techno

        for key, shop in (("sms2", "BSP SMS-2"), ("sms3", "BSP SMS-3")):
            if key in page_idx:
                p = page_idx[key]
                techno_rows += _parse_sms_page(pdf.pages[p].extract_tables(),
                                               pages_text[p], p, shop,
                                               mon_re, cum_re)

        for mill_key in ("rsm", "urm", "mm", "wrm", "brm", "pm"):
            if mill_key in page_idx:
                p = page_idx[mill_key]
                techno_rows += _parse_mill_tables(pdf.pages[p].extract_tables(),
                                                  p, mill_key, mon_re, cum_re)

        # ------------------- stock ------------------------------------------
        stock_rows: List[Dict[str, Any]] = []
        if "stock" in page_idx:
            p = page_idx["stock"]
            stock_rows = _parse_stock(pages_text[p], p, db_month)

    ok_p = sum(1 for r in production_rows if r["status"] == "ok")
    ok_t = sum(1 for r in techno_rows if r["status"] == "ok")
    ok_s = sum(1 for r in stock_rows if r["status"] == "ok")
    logger.info("BSP flash PDF preview: %d/%d production, %d/%d techno, "
                "%d/%d stock rows ok for %s",
                ok_p, len(production_rows), ok_t, len(techno_rows),
                ok_s, len(stock_rows), db_month)

    return {
        "source_type":        "BSP Flash Monthly PDF",
        "month":              db_month,
        "plant":              PLANT,
        "workbook_sheets":    [],
        "month_mismatch":     month_mismatch,
        "selected_month":     report_month or "",
        "file_month":         _MONTH_FULL.get(m, str(m)),
        "production_rows":    production_rows,
        "techno_rows":        [],
        "techno_param_rows":  techno_rows,
        "special_steel_rows": [],
        "stock_rows":         stock_rows,
    }


# ---------------------------------------------------------------------------
# techno_data records — same shape as BspTechnoExtractor / BspOiscoExtractor
# ---------------------------------------------------------------------------

def extract_techno_records(file_path: str, report_month: str = "") -> List[Dict]:
    """Extract techno params as techno_data records for /api/bsp-techno:

        [{report_month, plant, unit, techno_json: {month: {...},
                                                   till_month: {...}}}, ...]

    Unit names and param keys match bsp_techno_map.json / bsp_oisco_map.json,
    so records merge with (and are validated like) the Excel extractions.
    """
    preview = extract_preview(file_path, report_month)
    month = preview["month"]

    by_unit: Dict[str, Dict] = {}
    for r in preview["techno_param_rows"]:
        if not r.get("t_unit") or not r.get("t_key"):
            continue
        techno = by_unit.setdefault(r["t_unit"], {"month": {}, "till_month": {}})
        techno["month"][r["t_key"]] = r.get("actual")
        techno["till_month"][r["t_key"]] = r.get("cum_actual")

    records = []
    for unit, techno in by_unit.items():
        if any(v is not None for v in techno["month"].values()) or \
           any(v is not None for v in techno["till_month"].values()):
            records.append({
                "report_month": month,
                "plant":        PLANT,
                "unit":         unit,
                "techno_json":  techno,
            })
    logger.info("BSP flash PDF: %d techno_data units for %s", len(records), month)
    return records


# ---------------------------------------------------------------------------
# CLI for standalone testing:
#   python pdf_extractor_bsp_flash.py "BSP flash-jun26.pdf" 2026-06
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import json
    import sys

    logging.basicConfig(level=logging.INFO)
    if len(sys.argv) < 2:
        print("Usage: python pdf_extractor_bsp_flash.py <pdf_file> [YYYY-MM]")
        sys.exit(1)
    result = extract_preview(sys.argv[1],
                             sys.argv[2] if len(sys.argv) > 2 else "")
    print(json.dumps(
        {k: v for k, v in result.items()
         if k not in ("production_rows", "techno_param_rows", "stock_rows")},
        indent=2))
    for section in ("production_rows", "techno_param_rows", "stock_rows"):
        print(f"\n===== {section} ({len(result[section])}) =====")
        for r in result[section]:
            if section == "production_rows":
                print(f"  [{r['status']:4}] {r['item_name']:28} = "
                      f"{r['value']!s:>10} {r['unit']:6} ({r['cell']})")
            elif section == "techno_param_rows":
                print(f"  [{r['status']:4}] {r['section']:24} | "
                      f"{r['parameter']:24} = {r['actual']!s:>9} / "
                      f"cum {r['cum_actual']!s:>9} {r['unit']}")
            else:
                print(f"  [{r['status']:4}] {r['item_type']:15} "
                      f"{r['stock_type']:10} {r['stock_month']} = "
                      f"{r['value']!s:>9} ('000T)  [{r['formula']}]")
