"""
One-off backfill: BSL Saleable Steel Despatch / Direct Despatch / Semis
Export / Finished Export for FY 2025-26 (Apr'25-Mar'26), read from the BSL
Annual Statistics 2025-26 PDF's own Table No. 24.6 pages, per direct
instruction:
  Saleable Steel Despatch  -> "SALEABLE STEEL" table (doc page 405 /
                              PDF viewer page 450), Grand Total column.
  Direct Despatch          -> same table, Direct column.
  Semis Export             -> "MONTHWISE DESPATCH" EXPORT/IPT table (doc
                              page 408 / PDF viewer page 453), the EXPORT
                              block's Slab column.
  Finished Export          -> derived: the SALEABLE STEEL table's own
                              Export column (the EXPORT block's own Total,
                              cross-checked equal) minus Semis Export
                              above — this PDF carries no separate
                              "Finished Export" figure of its own, unlike
                              the ongoing monthly-PDF route (see
                              excel_extractor_bsl.py's
                              _parse_despatch_glance_page, which reads an
                              explicit "-Finished" row instead of deriving
                              it, once a report exists for the month).

Road Despatch is NOT backfilled here — it doesn't appear anywhere in this
PDF (neither table carries a Road/Rail split) and no FY25-26 monthly "Rev
<Month>.pdf"/"Review <Month>.pdf" exists in
G:\\My Drive\\Report_format\\Monthly\\BSL\\ to fall back on either (that
folder jumps from "Rev March 2025.pdf" straight to "Rev June26 (2).pdf" —
no Apr'25-May'26 file at all). It'll start being captured from the first
month excel_extractor_bsl.py's monthly-PDF extractor actually runs on
(and it may not appear even there on report vintages older than ~2026 —
confirmed absent on Rev March 2025.pdf's own despatch page, present on
Rev June26 (2).pdf's).

Every figure here was cross-checked against real files before being
trusted — see this script's own comments below and
excel_extractor_bsl.py's _parse_despatch_glance_page docstring (May 2025's
BSL DPR Mail figure for Saleable Steel Despatch, 393,707 T, tracks this
PDF's own May'25 Grand Total of 392,342 T; June'26's monthly-PDF figures
for Direct Despatch/Semis Export both match this PDF's own FY25-26 1st
QTR totals for the equivalent columns exactly).

Source file:
  C:\\Users\\sanja\\Downloads\\BSL Annual Statistics 2025-26.pdf

Usage:
  python scripts/backfill_bsl_despatch_fy2526.py            # dry-run: prints the 12 months, writes nothing
  python scripts/backfill_bsl_despatch_fy2526.py --apply     # actually writes to production_table (live DB)

Dry-run is the default on purpose — this touches the live MySQL DB
(DB_ENGINE=mysql), so the values should be reviewed before anything is
written.
"""
import sys
import os
import re
import argparse

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BACKEND_DIR)

import pdfplumber  # noqa: E402
import db  # noqa: E402

PDF_PATH = r"C:\Users\sanja\Downloads\BSL Annual Statistics 2025-26.pdf"
PLANT = "BSL"

# 0-based PDF viewer page indices — the document's own footer calls these
# "Page No. 405" and "Page No. 408" respectively; this PDF's internal page
# numbering trails the PDF viewer's own by a constant 45 (confirmed on
# both pages used here: viewer page 450 -> "Page No. 405", 453 -> 408).
SALEABLE_STEEL_PAGE = 449
EXPORT_IPT_PAGE = 452

# "SALEABLE STEEL" table columns, left to right: Direct, Stock Yard, IPT,
# Export, Secondary Total, [[unlabeled — always Secondary Total short of
# Grand Total by this amount; not needed here]], Grand Total. 7 numbers
# per row — confirmed against every one of FY25-26's 12 months plus every
# quarter/annual/prior-year recap row this table also carries.
_SS_DIRECT_IDX, _SS_EXPORT_IDX, _SS_GRAND_TOTAL_IDX = 0, 3, 6
_SS_NUM_COLS = 7

# EXPORT/IPT table columns, left to right: Pig Iron, Slab, HR Coil, HR
# Plate, HRSheet, CR Coil, GP Coil, [EXPORT block Total], Hard Coke, Mixed
# Coke, Breeze Coke, Slab, HR Coil, [IPT block Total]. 14 numbers per row —
# the EXPORT block's own Total (index 7) was cross-checked equal to the
# SALEABLE STEEL table's Export column for all 12 months before trusting
# either.
_EXP_SLAB_IDX, _EXP_TOTAL_IDX = 1, 7
_EXP_NUM_COLS = 14

_MONTH_TO_REPORT_MONTH = {
    "APR'25": "2025-04", "MAY": "2025-05", "JUN": "2025-06", "JULY": "2025-07",
    "AUG": "2025-08", "SEP": "2025-09", "OCT": "2025-10", "NOV": "2025-11",
    "DEC": "2025-12", "JAN'26": "2026-01", "FEB": "2026-02", "MAR": "2026-03",
}
_MONTH_ROW_RE = re.compile(
    r"^(APR'25|MAY|JUN|JULY|AUG|SEP|OCT|NOV|DEC|JAN'26|FEB|MAR)\s+(.+)$"
)


def _parse_month_rows(text: str, expected_cols: int) -> dict:
    """{report_month: [float, ...]} for exactly the 12 real month rows —
    quarter subtotals ("1ST QTR."), the annual recap ("2025-26 ..."), and
    every prior-year recap row never match _MONTH_ROW_RE's fixed
    month-label set, so they're skipped automatically rather than needing
    to be explicitly excluded."""
    out = {}
    for line in text.splitlines():
        m = _MONTH_ROW_RE.match(line.strip())
        if not m:
            continue
        label, rest = m.groups()
        nums = re.findall(r'-?\d[\d,]*(?:\.\d+)?', rest)
        if len(nums) != expected_cols:
            continue
        out[_MONTH_TO_REPORT_MONTH[label]] = [float(n.replace(',', '')) for n in nums]
    return out


def extract_fy2526_despatch() -> dict:
    """{report_month: {item_name: value_in_tonnes}} for all 12 FY25-26
    months. Raises if either page doesn't yield exactly 12 month rows, or
    if the EXPORT block's own Total ever disagrees with the SALEABLE
    STEEL table's Export column — better to abort the whole backfill than
    silently write a wrong Finished Export figure for one month."""
    with pdfplumber.open(PDF_PATH) as pdf:
        ss_text = pdf.pages[SALEABLE_STEEL_PAGE].extract_text(layout=False)
        exp_text = pdf.pages[EXPORT_IPT_PAGE].extract_text(layout=False)

    ss_rows = _parse_month_rows(ss_text, _SS_NUM_COLS)
    exp_rows = _parse_month_rows(exp_text, _EXP_NUM_COLS)

    missing_ss = set(_MONTH_TO_REPORT_MONTH.values()) - set(ss_rows)
    missing_exp = set(_MONTH_TO_REPORT_MONTH.values()) - set(exp_rows)
    if missing_ss or missing_exp:
        raise ValueError(
            f"Expected all 12 FY25-26 months on both pages. Missing from "
            f"SALEABLE STEEL page: {sorted(missing_ss)}; missing from "
            f"EXPORT/IPT page: {sorted(missing_exp)}. Verify {PDF_PATH} "
            f"still has 'SALEABLE STEEL' at viewer page {SALEABLE_STEEL_PAGE + 1} "
            f"and the EXPORT/IPT table at viewer page {EXPORT_IPT_PAGE + 1}."
        )

    out = {}
    for report_month in _MONTH_TO_REPORT_MONTH.values():
        ss = ss_rows[report_month]
        exp = exp_rows[report_month]

        direct = ss[_SS_DIRECT_IDX]
        export_total_ss = ss[_SS_EXPORT_IDX]
        grand_total = ss[_SS_GRAND_TOTAL_IDX]
        semis_export = exp[_EXP_SLAB_IDX]
        export_total_exp = exp[_EXP_TOTAL_IDX]

        if abs(export_total_ss - export_total_exp) > 1.0:  # 1 tonne tolerance
            raise ValueError(
                f"{report_month}: Export Total disagrees between the two "
                f"source tables — SALEABLE STEEL page says {export_total_ss:,.0f} T, "
                f"EXPORT/IPT page's own EXPORT block Total says "
                f"{export_total_exp:,.0f} T. Aborting without writing anything."
            )

        out[report_month] = {
            "Saleable Steel Despatch": grand_total,
            "Direct Despatch": direct,
            "Semis Export": semis_export,
            "Finished Export": export_total_ss - semis_export,
        }
    return out


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true",
                        help="Actually write to the live DB. Default is a dry-run.")
    args = parser.parse_args()

    by_month = extract_fy2526_despatch()

    for report_month in sorted(by_month):
        vals = by_month[report_month]
        print(f"{report_month}: "
              f"Saleable Steel Despatch={vals['Saleable Steel Despatch']:>10,.0f} T   "
              f"Direct Despatch={vals['Direct Despatch']:>10,.0f} T   "
              f"Semis Export={vals['Semis Export']:>8,.0f} T   "
              f"Finished Export={vals['Finished Export']:>8,.0f} T")

    if not args.apply:
        print(f"\nDry-run only — {len(by_month) * 4} values NOT written. Re-run with --apply to save.")
        return

    conn = db.connect()
    cur = conn.cursor()
    saved = 0
    try:
        for report_month, vals in by_month.items():
            for item_name, value_tonnes in vals.items():
                stored = round(value_tonnes / 1000.0, 3)
                cur.execute("""
                    INSERT INTO production_table (report_month, plant_name, item_name, month_actual)
                    VALUES (?, ?, ?, ?)
                    ON CONFLICT(report_month, plant_name, item_name)
                    DO UPDATE SET month_actual = excluded.month_actual
                """, (report_month, PLANT, item_name, stored))
                saved += 1
        conn.commit()
    finally:
        conn.close()

    print(f"\nSaved {saved} values across {len(by_month)} months for {PLANT}.")
    print("Road Despatch NOT backfilled for FY25-26 — no source in this PDF "
          "(see module docstring); will be captured going forward once the "
          "monthly-PDF extractor runs on a report that carries it.")


if __name__ == "__main__":
    main()
