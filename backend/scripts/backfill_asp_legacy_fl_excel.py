"""
One-off backfill: ASP production_table for FY 2020-21 through FY 2023-24
(48 months, Apr 2020 - Mar 2024), sourced from the legacy FL*.xls FLASH
workbooks at "I:\\My Drive\\Report_format\\ASP Legacy\\".

Why this is needed: production_table already has ASP data across this whole
range, but only 2 items (Saleable Steel, Total Crude Steel) per month — a
bulk historical import, not the full FL item set. These legacy workbooks are
literally the Excel source the monthly FL*.pdf FLASH report used to be
printed from (see excel_extractors/pdf_extractor_asp.py's FL section for the
item map this mirrors), so they carry the same item set: Ingot Steel, Total
Caster, Ingot Semis, Billets, BARS, FS PRD, PLATES, Saleable Steel Despatch,
plus computed Finished Steel.

Workbook layout (all discovered empirically — see conversation this script
came out of, no prior art for this file format):
  Each FL<YY>-<YY+1>.xls has one sheet, 'FL1112', which is NOT scoped to that
  one FY — it's an accumulating archive: the FY named in the filename sits
  at the TOP (12 monthly blocks, one after another), followed by dozens more
  older monthly blocks reaching back to 2008 (leftover snapshots from past
  reuses of the same template file). This script only reads each file's own
  top-of-file FY section — i.e. FL22-23.xls contributes Apr'22-Mar'23 only,
  even though the same file also contains (older, already-covered-elsewhere-
  or out-of-scope) 2008-2021 data further down.

  Each monthly block is anchored by its 'DETAILS' header row (col A). Column
  layout per data row: [0]=label [1]=Plan(this month) [2]=Actual(this month)
  [3]=%Ach [4]=Actual(previous month) [5]=Actual(same month, last year/CPLY)
  ... (matches the FL PDF's own column order — see pdf_extractor_asp.py).
  Sections within a block, tracked sequentially top-to-bottom (a row's
  section, not just its label, disambiguates the two bare "TOTAL" rows):
  GENERAL (untitled, right after the header) -> PRODUCTION FOR FINISHING ->
  SALEABLE PRDUCTION -> DESPATCH -> STN:- (ignored, not part of the FL item
  set). Item labels within each section mirror pdf_extractor_asp.py's
  _FL_ITEMS exactly.

  Report month detection is the hard part: neither the "FLASH : <MON>-<YYYY>"
  banner, the DETAILS row's own freeform month/year text, nor the block's
  "date of report" cell (always the 1st of the month after the one being
  reported, e.g. '01.05.2020' for the April 2020 block) is reliably correct
  on its own — all three have been observed wrong in different blocks (typos,
  stale copy-pasted labels, a wrong generation date). What IS reliable is the
  file's own structural promise: each FY section is exactly its 12 months in
  strict calendar order starting at April, with only rare, genuine skips
  (e.g. FL25-26.xls has no December 2025 block at all — confirmed real gap,
  not a parsing failure). So this script trusts strict sequential position
  (April, May, ..., March) as the default report month for each successive
  DETAILS block, and only jumps ahead of that sequence when the DETAILS row's
  own text unambiguously names a later month within the same FY (a genuine
  skip) — see _parse_details_month_year() and _iter_fy_blocks(). Any block
  where the position-based month disagrees with the block's own free-text
  signals is still written (position wins), but flagged in the printed diff
  so a human can sanity-check it before --apply.

Usage:
  python scripts/backfill_asp_legacy_fl_excel.py            # dry-run: prints a diff, writes nothing
  python scripts/backfill_asp_legacy_fl_excel.py --apply     # actually writes to production_table (live DB)

Dry-run is the default on purpose — this touches the live MySQL DB
(DB_ENGINE=mysql).
"""
import sys
import os
import re
import argparse

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BACKEND_DIR)

import db  # noqa: E402

PLANT = "ASP"
SRC_DIR = r"I:\My Drive\Report_format\ASP Legacy"
SRC_FILES = [
    "FL20-21.xls", "FL21-22.xls", "FL22-23.xls", "FL23-24.xls",
]  # FY24-25 and FY25-26 already covered by live uploads / the FY24-25 FL-backfill script.
SHEET_NAME = "FL1112"

_MONTHS = ["JAN", "FEB", "MAR", "APR", "MAY", "JUN",
           "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"]
_MONTH_ALIASES = {
    "JAN": 1, "JANUARY": 1, "FEB": 2, "FEBRUARY": 2, "MAR": 3, "MARCH": 3,
    "APR": 4, "APRIL": 4, "MAY": 5, "JUN": 6, "JUNE": 6, "JUL": 7, "JULY": 7,
    "AUG": 8, "AUGUST": 8, "SEP": 9, "SEPT": 9, "SEPTEMBER": 9,
    "OCT": 10, "OCTOBER": 10, "NOV": 11, "NOVEMBER": 11,
    "DEC": 12, "DECEMBER": 12,
}
_MONTH_WORD_RE = re.compile(
    r"\b(" + "|".join(sorted(_MONTH_ALIASES, key=len, reverse=True)) + r")\b", re.I)
_YEAR_RE = re.compile(r"(\d{2,4})")
_GEN_DATE_RE = re.compile(r'^\s*(\d{1,2})\.(\d{1,2})\.(\d{2,4})\s*$')

# ── item map, mirrors pdf_extractor_asp.py's _FL_ITEMS exactly (section,
# exact-label) -> item_name. 'exact' rows must have col0 stripped-upper
# equal to the label (not just startswith) — matters for the two bare
# "TOTAL" rows and 'ING' vs longer look-alikes.
_ITEMS = [
    ("GENERAL",   "INGT.",    "Ingot Steel"),
    ("GENERAL",   "TOT.CC.",  "Total Caster"),
    ("GENERAL",   "CRUDE",    "Total Crude Steel"),
    ("FINISHING", "ING",      "Ingot Semis"),
    ("SALEABLE",  "BILLETS",  "Billets"),
    ("SALEABLE",  "BARS",     "BARS"),
    ("SALEABLE",  "FS PRD.",  "FS PRD"),
    ("SALEABLE",  "PL MILL",  "PLATES"),
    ("SALEABLE",  "TOTAL",    "Saleable Steel"),
    ("DESPATCH",  "TOTAL",    "Saleable Steel Despatch"),
]
_FINISHED_STEEL_PARTS = ["BARS", "FS PRD", "PLATES"]


def _fy_bounds(fname):
    """'FL22-23.xls' -> (2022, 4), (2023, 3) i.e. Apr'22 .. Mar'23."""
    yy1 = int(fname[2:4])
    return (2000 + yy1, 4), (2000 + yy1 + 1, 3)


def _key(y, m):
    return y * 12 + m


def _fmt(y, m):
    return f"{y:04d}-{m:02d}"


def _cell_text(sh, r, c):
    v = sh.cell_value(r, c)
    return v if isinstance(v, str) else ""


def _find_details_rows(sh):
    return [r for r in range(sh.nrows)
            if _cell_text(sh, r, 0).strip().upper() == "DETAILS"]


def _parse_details_month_year(sh, dr):
    """Best-effort (year, month) parse from the DETAILS row's own free text
    (columns 1-3), for cross-checking / gap detection only — NOT trusted as
    the primary source (see module docstring). Returns None if no month name
    is found."""
    text = " ".join(_cell_text(sh, dr, c) or str(sh.cell_value(dr, c) or "")
                     for c in range(1, 4))
    mm = _MONTH_WORD_RE.search(text)
    if not mm:
        return None
    month = _MONTH_ALIASES[mm.group(1).upper()]
    rest = text[mm.end():] + " " + text[:mm.start()]
    ym = _YEAR_RE.search(rest)
    if not ym:
        return None
    yr = int(ym.group(1))
    if yr < 100:
        yr += 2000
    elif yr > 2100 or 100 <= yr < 1900:  # e.g. the 'OCT'122' typo -> take last 2 digits
        yr = 2000 + int(str(yr)[-2:])
    return (yr, month)


def _find_gen_date(sh, dr, wb):
    """(year, month) of the block's 'date of report' cell (rows dr-8..dr-1,
    col 0) — always the 1st of the month AFTER the one being reported.
    Cross-check only, see module docstring. Returns None if not found."""
    import xlrd
    for r in range(max(0, dr - 8), dr):
        v = sh.cell_value(r, 0)
        if sh.cell_type(r, 0) == 1 and isinstance(v, str):
            m = _GEN_DATE_RE.match(v)
            if m:
                d, mo, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
                y = y if y > 100 else 2000 + y
                return (y, mo)
        elif sh.cell_type(r, 0) == 3:
            try:
                dt = xlrd.xldate_as_datetime(v, wb.datemode)
                return (dt.year, dt.month)
            except Exception:
                pass
    return None


def _iter_fy_blocks(sh, wb, fname):
    """Yield (details_row, report_year, report_month, note) for each monthly
    block in *fname*'s own top-of-file FY section, in order. `note` is None
    for a clean sequential match, else a short string describing why this
    block's month required a cross-check judgment call (for the printed
    diff)."""
    (fy_y0, fy_m0), (fy_y1, fy_m1) = _fy_bounds(fname)
    fy_end_key = _key(fy_y1, fy_m1)

    expected_y, expected_m = fy_y0, fy_m0
    for dr in _find_details_rows(sh):
        expected_key = _key(expected_y, expected_m)
        if expected_key > fy_end_key:
            break  # this FY's 12 months are all accounted for

        details = _parse_details_month_year(sh, dr)
        gen = _find_gen_date(sh, dr, wb)
        gen_report = None
        if gen is not None:
            gy, gm = gen
            gm -= 1
            if gm == 0:
                gm, gy = 12, gy - 1
            gen_report = (gy, gm)

        # Only ever accept a JUMP ahead of `expected` (a genuine skipped
        # month) when the free-text DETAILS parse unambiguously agrees with
        # itself and lands within this FY, within a small (<=3 month) hop —
        # everything else defaults to strict sequential position (see
        # module docstring: both free-text fields have been seen wrong).
        note = None
        if details is not None:
            dkey = _key(*details)
            if dkey > expected_key and dkey - expected_key <= 3 and dkey <= fy_end_key:
                note = (f"gap detected: sequence expected {_fmt(expected_y, expected_m)}, "
                        f"DETAILS row names {_fmt(*details)} — trusting the skip")
                expected_y, expected_m = details
            elif dkey != expected_key:
                note = (f"DETAILS row text suggests {_fmt(*details)}, "
                        f"using sequential {_fmt(expected_y, expected_m)} instead")
        if gen_report is not None and gen_report != (expected_y, expected_m):
            extra = f"gen-date cell suggests {_fmt(*gen_report)}"
            note = f"{note}; {extra}" if note else f"{extra}, using sequential {_fmt(expected_y, expected_m)} instead"

        yield dr, expected_y, expected_m, note
        expected_m += 1
        if expected_m == 13:
            expected_m, expected_y = 1, expected_y + 1


def _block_end_row(sh, dr, next_dr):
    """Row index one past this block's last data row. Bounded by the NEXT
    block's own DETAILS row rather than by scanning for a '=' separator —
    blocks inconsistently use '=' for both their true end AND for internal
    section dividers (e.g. the GENERAL/FINISHING divider is sometimes '='
    instead of the usual '-'), which made a first-'=' scan stop mid-block
    and silently drop the FINISHING/SALEABLE/DESPATCH sections. The next
    block's own pre-DETAILS header lines (FLASH banner etc.) are harmless
    noise here — none of them match any of _ITEMS' labels."""
    return next_dr if next_dr is not None else min(dr + 200, sh.nrows)


def _num(sh, r, c):
    if sh.cell_type(r, c) == 2:  # XL_CELL_NUMBER
        return sh.cell_value(r, c)
    return None


def _parse_block(sh, dr, next_dr):
    """Extract this block's items -> {item_name: value_T (raw tonnes)}."""
    end = _block_end_row(sh, dr, next_dr)
    section = "GENERAL"
    found = {}
    for r in range(dr + 1, end):
        label = _cell_text(sh, r, 0).strip().upper()
        if not label:
            continue
        if label.startswith("PRODUCTION FOR FINISHING"):
            section = "FINISHING"
            continue
        if label.startswith("SALEABLE"):
            section = "SALEABLE"
            continue
        if label == "DESPATCH":
            section = "DESPATCH"
            continue
        if label.startswith("STN:"):
            # exact section header ("STN:-") — NOT "STN SLAB" / "STN.SAL.:-",
            # which are ordinary item rows inside DESPATCH/SALEABLE.
            section = "STN"
            continue
        for item_section, item_label, item_name in _ITEMS:
            if item_section != section or label != item_label:
                continue
            if item_name in found:
                continue  # first match in the right section wins
            val = _num(sh, r, 2)
            if val is not None:
                found[item_name] = val
    return found


def extract_file(path, fname):
    """Return list of (report_month:'YYYY-MM', item_name, value_'000T, note)."""
    import xlrd
    wb = xlrd.open_workbook(path)
    sh = wb.sheet_by_name(SHEET_NAME)

    blocks = list(_iter_fy_blocks(sh, wb, fname))
    rows = []
    for i, (dr, y, m, note) in enumerate(blocks):
        next_dr = blocks[i + 1][0] if i + 1 < len(blocks) else None
        raw = _parse_block(sh, dr, next_dr)
        parts = {}
        for item_name, raw_val in raw.items():
            val = round(raw_val / 1000.0, 3)
            rows.append((_fmt(y, m), item_name, val, note))
            if item_name in _FINISHED_STEEL_PARTS:
                parts[item_name] = val
        if all(p in parts for p in _FINISHED_STEEL_PARTS):
            fs = round(sum(parts[p] for p in _FINISHED_STEEL_PARTS), 3)
            rows.append((_fmt(y, m), "Finished Steel", fs, note))
    return rows


def current_db_values(months):
    conn = db.connect()
    cur = conn.cursor()
    ph = ",".join("?" * len(months))
    cur.execute(
        f"SELECT report_month, item_name, month_actual FROM production_table "
        f"WHERE plant_name=? AND report_month IN ({ph})",
        (PLANT, *months),
    )
    out = {(m, item): val for m, item, val in cur.fetchall()}
    conn.close()
    return out


def upsert(report_month, item_name, value):
    conn = db.connect()
    conn.execute("""
        INSERT INTO production_table (report_month, plant_name, item_name, month_actual)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(report_month, plant_name, item_name)
        DO UPDATE SET month_actual = excluded.month_actual
    """, (report_month, PLANT, item_name, value))
    conn.commit()
    conn.close()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="actually write to the DB (default: dry-run)")
    args = ap.parse_args()

    all_rows = []  # (report_month, item_name, value, note)
    for fname in SRC_FILES:
        path = os.path.join(SRC_DIR, fname)
        if not os.path.exists(path):
            print(f"  SKIP {fname}: not found at {path}")
            continue
        rows = extract_file(path, fname)
        months = sorted({m for m, _, _, _ in rows})
        print(f"{fname}: {len(rows)} values across {len(months)} months "
              f"({months[0] if months else '-'}..{months[-1] if months else '-'})")
        notes = [(m, n) for m, _, _, n in rows if n]
        seen_notes = set()
        for m, n in notes:
            if (m, n) not in seen_notes:
                seen_notes.add((m, n))
                print(f"    NOTE {m}: {n}")
        all_rows.extend(rows)

    months = sorted({m for m, _, _, _ in all_rows})
    print(f"\nTotal: {len(all_rows)} (month, item) values across {len(months)} months.\n")

    cur_vals = current_db_values(months)

    new_count = changed_count = same_count = 0
    for report_month, item_name, new_val, _note in sorted(all_rows, key=lambda r: (r[0], r[1])):
        old_val = cur_vals.get((report_month, item_name))
        if old_val is None:
            new_count += 1
            print(f"  {report_month}  {item_name:24s}  {'-':>10s} -> {new_val:<10}  [new]")
        elif round(float(old_val), 3) != round(float(new_val), 3):
            changed_count += 1
            print(f"  {report_month}  {item_name:24s}  {old_val!s:>10s} -> {new_val:<10}  [DIFFERS FROM DB]")
        else:
            same_count += 1

    print(f"\n{new_count} new, {changed_count} differ from current DB, "
          f"{same_count} already match ({len(all_rows)} total).")

    if not args.apply:
        print("\nDRY RUN - nothing written. Re-run with --apply to write.")
        return

    for report_month, item_name, val, _note in all_rows:
        upsert(report_month, item_name, val)
    print(f"\nAPPLIED - {len(all_rows)} value(s) written to production_table.")


if __name__ == "__main__":
    main()
