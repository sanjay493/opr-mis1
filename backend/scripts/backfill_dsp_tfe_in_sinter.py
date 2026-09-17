"""
One-off backfill: DSP TFe in Sinter ("FE (%)" Todate, Sinter Plant Quality
block) from every month-end MCR report on disk, per direct instruction
(2026-09-17) — see dsp_mcr_techno_extractor.py's module docstring for the
"FE (%)" column-A / column-D layout this newly reads.

Iterates every file in ARCHIVE_DIR whose name starts with "mcr" (covers both
the genuine techno-page files, named "mcr_<date>.xls", and the occasional
"mcr1_<date>.xlsx" one-off that happens to carry the same sheet — see the
extractor's own docstring) and skips whichever don't parse as a DSP MCR
techno report (e.g. the "mcr1_<date>.xls" sibling, which is actually the
unrelated Production/Despatch "MCR-1" daily report saved under a similarly-
named file — DspMcrTechnoExtractor.extract() already raises a clear
ValueError for those, caught and skipped here).

Writes ONLY tfe_in_sinter under unit "BF_Shop" via merge_upsert_techno_data
(merge semantics — every other already-stored BF_Shop parameter, including
any later manual correction, is left untouched) — deliberately not
re-running the extractor's other BF/SMS parameters through this backfill,
since those already have their own normal monthly extraction path and
re-pushing them here could clobber a manual correction with a stale
re-extracted value.

Usage:
  python scripts/backfill_dsp_tfe_in_sinter.py            # dry-run
  python scripts/backfill_dsp_tfe_in_sinter.py --apply     # writes to the live DB

Dry-run is the default on purpose — this touches the live MySQL DB
(DB_ENGINE=mysql), so the values should be reviewed before anything is
written.
"""
import argparse
import os
import sys

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BACKEND_DIR)
sys.path.insert(0, os.path.join(BACKEND_DIR, "techno_project"))

import db  # noqa: E402
from dsp_mcr_techno_extractor import DspMcrTechnoExtractor  # noqa: E402

PLANT = "DSP"
ARCHIVE_DIR = r"I:\My Drive\Report_format\MONTHEND\DSP"
UNIT = "BF_Shop"
KEY = "tfe_in_sinter"


def extract_file(path: str):
    """-> (report_month, value) or (None, None) if this file isn't a DSP
    MCR techno report / has no Sinter Fe reading."""
    ext = DspMcrTechnoExtractor(path)
    try:
        records = ext.extract()
    except Exception:
        return None, None
    for rec in records:
        if rec["unit"] == UNIT:
            val = rec["techno_json"]["month"].get(KEY)
            if val is not None:
                return rec["report_month"], val
    return None, None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true",
                        help="Actually write to the live DB. Default is a dry-run.")
    args = parser.parse_args()

    files = sorted(f for f in os.listdir(ARCHIVE_DIR)
                   if f.lower().startswith("mcr") and f.lower().endswith((".xls", ".xlsx")))

    to_write = {}   # {report_month: (value, source_file)}
    skipped = []

    for fname in files:
        path = os.path.join(ARCHIVE_DIR, fname)
        report_month, val = extract_file(path)
        if report_month is None:
            skipped.append(fname)
            continue
        if report_month in to_write and to_write[report_month][0] != val:
            print(f"  NOTE: {report_month} already has {to_write[report_month][0]} "
                  f"from {to_write[report_month][1]} — {fname} gives {val}, keeping the first.")
            continue
        to_write.setdefault(report_month, (val, fname))

    for month in sorted(to_write):
        val, fname = to_write[month]
        print(f"{month} ({fname}): tfe_in_sinter = {val}")

    print(f"\nSkipped {len(skipped)} file(s) that aren't a DSP MCR techno report "
          f"(e.g. the Production/Despatch 'mcr1_<date>.xls' sibling):")
    for fname in skipped:
        print(f"  {fname}")

    if not args.apply:
        print(f"\nDry-run only — {len(to_write)} month(s) NOT written. Re-run with --apply to save.")
        return

    saved = 0
    for month, (val, fname) in to_write.items():
        db.merge_upsert_techno_data(
            plant=PLANT, report_month=month, unit=UNIT,
            new_techno_json={"month": {KEY: val}, "till_month": {}},
            source_file=fname,
        )
        saved += 1

    print(f"\nSaved {saved} month(s) of tfe_in_sinter for {PLANT}/{UNIT}.")


if __name__ == "__main__":
    main()
