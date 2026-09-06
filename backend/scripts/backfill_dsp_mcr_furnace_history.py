"""
One-off backfill: DSP furnace-wise Hot Metal (BF#2/BF#3/BF#4), "Hot Metal
to PCM", and "Hot Metal to ASP" from every "mcr_<date>.xls" month-end
report on disk, per direct instruction.

This report (see excel_extractor_dsp.py's own module note above
_extract_mcr_furnace_report) typically arrives BEFORE the monthly OMI PDF
— the authoritative, "final" source pdf_extractor_dsp.py already extracts
BF#2/BF#3/BF#4 and Hot Metal to ASP from (124 and 41 months of history
respectively, confirmed already complete for essentially every month this
MCR report also covers). Overwriting that already-correct final data with
this report's own preliminary read would only ever be a no-op at best
(verified: May 2026's MCR-derived BF#2/BF#3/BF#4/Hot Metal to ASP match
the PDF-derived DB values to the tonne) and a real risk at worst, for any
month where the two sources ever genuinely disagree. So:

  - BF#2 / BF#3 / BF#4 / Hot Metal to ASP: only written for a
    (report_month, item_name) that has NO existing production_table row at
    all — i.e. gap-filling months the final PDF hasn't been processed for
    yet, never touching a month the PDF route already covers.
  - Hot Metal to PCM: written for every month this report covers,
    unconditionally — no PDF-based (or any other) extraction path
    populates this item at all (confirmed: neither the monthly OMI PDF nor
    the "mcr1_<date>.xls" sibling report ever mentions "PCM"), so there is
    no competing "final" value to ever protect here.

Usage:
  python scripts/backfill_dsp_mcr_furnace_history.py            # dry-run
  python scripts/backfill_dsp_mcr_furnace_history.py --apply     # writes to the live DB

Dry-run is the default on purpose — this touches the live MySQL DB
(DB_ENGINE=mysql), so the values should be reviewed before anything is
written.
"""
import sys
import os
import argparse

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BACKEND_DIR)
sys.path.insert(0, os.path.join(BACKEND_DIR, "excel_extractors"))

import db  # noqa: E402
import excel_extractor_dsp as dsp  # noqa: E402

PLANT = "DSP"
ARCHIVE_DIR = r"G:\My Drive\Report_format\MONTHEND\DSP"
GAP_FILL_ONLY_ITEMS = ("BF#2", "BF#3", "BF#4", "Hot Metal to ASP")
ALWAYS_WRITE_ITEMS = ("Hot Metal to PCM",)


def extract_file(fname: str):
    path = os.path.join(ARCHIVE_DIR, fname)
    with open(path, encoding="utf-8", errors="replace") as f:
        lines = [line.rstrip("\r\n").split("\t") for line in f.readlines()]
    if not dsp._looks_like_mcr_furnace_report(lines):
        return None, {}
    result = dsp._extract_mcr_furnace_report(lines)
    return result["report_month"], result["values"]


def existing_months(cur, item_name):
    cur.execute(
        "SELECT report_month FROM production_table WHERE plant_name=? AND item_name=?",
        (PLANT, item_name),
    )
    return {row[0] for row in cur.fetchall()}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true",
                        help="Actually write to the live DB. Default is a dry-run.")
    args = parser.parse_args()

    conn = db.connect()
    cur = conn.cursor()
    existing = {item: existing_months(cur, item) for item in GAP_FILL_ONLY_ITEMS}
    conn.close()

    files = sorted(f for f in os.listdir(ARCHIVE_DIR)
                   if f.lower().startswith("mcr_") and f.lower().endswith((".xls", ".xlsx")))

    to_write = {}   # {(report_month, item_name): value}
    errors = []
    skipped_existing = []

    for fname in files:
        try:
            report_month, vals = extract_file(fname)
        except Exception as exc:
            errors.append((fname, str(exc)))
            continue
        if not report_month:
            continue

        kept = {}
        for item_name, value in vals.items():
            if item_name in ALWAYS_WRITE_ITEMS:
                kept[item_name] = value
            elif item_name in GAP_FILL_ONLY_ITEMS:
                if report_month in existing.get(item_name, set()):
                    skipped_existing.append((fname, report_month, item_name))
                else:
                    kept[item_name] = value

        parts = "   ".join(f"{k}={v:,.3f} '000T" for k, v in kept.items())
        print(f"{report_month} ({fname}): {parts or '(nothing new to write)'}")
        for item_name, value in kept.items():
            to_write[(report_month, item_name)] = value

    if errors:
        print("\n--- Files that raised errors (skipped) ---")
        for fname, msg in errors:
            print(f"  {fname}: {msg}")

    if skipped_existing:
        print(f"\n--- {len(skipped_existing)} (month, item) values skipped — already covered by the final PDF ---")
        for fname, report_month, item_name in skipped_existing:
            print(f"  {report_month} {item_name} ({fname})")

    if not args.apply:
        print(f"\nDry-run only — {len(to_write)} values NOT written. Re-run with --apply to save.")
        return

    conn = db.connect()
    cur = conn.cursor()
    saved = 0
    try:
        for (report_month, item_name), value in to_write.items():
            cur.execute("""
                INSERT INTO production_table (report_month, plant_name, item_name, month_actual)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(report_month, plant_name, item_name)
                DO UPDATE SET month_actual = excluded.month_actual
            """, (report_month, PLANT, item_name, value))
            saved += 1
        conn.commit()
    finally:
        conn.close()

    print(f"\nSaved {saved} values for {PLANT}.")


if __name__ == "__main__":
    main()
