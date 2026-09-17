"""
One-off follow-up to backfill_dsp_tfe_in_sinter.py: compute and save the
April->report_month cumulative (till_month) for DSP/BF_Shop's tfe_in_sinter,
for every month that script backfilled a "month" value for, per direct
instruction (2026-09-17).

tfe_in_sinter has no entry in techno_cumulative.CUMULATIVE_RULES, so it uses
the default simple average across whatever April->report_month monthly
values are on file (a quality-% metric, same treatment as e.g. silicon_in_hm/
sulphur_in_hm) — not weighted by production. A month early in a FY that this
backfill doesn't reach further back for (2025-01/02/03, FY2024-25) just
averages over the months actually on file rather than the full April start,
same as compute_cumulative_preview's own "no monthly value in DB" warning
handling for any other parameter.

Writes ONLY tfe_in_sinter's till_month via merge_upsert_techno_data — every
other stored till_month value (for any other parameter) is left untouched.

Usage:
  python scripts/backfill_dsp_tfe_in_sinter_cumulative.py            # dry-run
  python scripts/backfill_dsp_tfe_in_sinter_cumulative.py --apply     # writes to the live DB
"""
import argparse
import os
import sys

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BACKEND_DIR)

import db  # noqa: E402
from techno_cumulative import compute_cumulative_preview  # noqa: E402

PLANT = "DSP"
UNIT = "BF_Shop"
KEY = "tfe_in_sinter"

# Same 19 months backfill_dsp_tfe_in_sinter.py wrote a "month" value for
# (2026-07 has no source file on disk, so it's excluded here too).
MONTHS = [
    "2025-01", "2025-02", "2025-03", "2025-04", "2025-05", "2025-06",
    "2025-07", "2025-08", "2025-09", "2025-10", "2025-11", "2025-12",
    "2026-01", "2026-02", "2026-03", "2026-04", "2026-05", "2026-06",
    "2026-08",
]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true",
                        help="Actually write to the live DB. Default is a dry-run.")
    args = parser.parse_args()

    to_write = {}
    for month in MONTHS:
        try:
            result = compute_cumulative_preview(PLANT, UNIT, KEY, month)
        except ValueError as e:
            print(f"{month}: SKIPPED — {e}")
            continue
        val = result["result"]
        if val is None:
            print(f"{month}: SKIPPED — no cumulative could be computed.")
            continue
        to_write[month] = val
        warn = f"  ({'; '.join(result['warnings'])})" if result["warnings"] else ""
        print(f"{month}: till_month tfe_in_sinter = {val}{warn}")

    if not args.apply:
        print(f"\nDry-run only — {len(to_write)} month(s) NOT written. Re-run with --apply to save.")
        return

    saved = 0
    for month, val in to_write.items():
        db.merge_upsert_techno_data(
            plant=PLANT, report_month=month, unit=UNIT,
            new_techno_json={"month": {}, "till_month": {KEY: val}},
            source_file="cumulative_calc",
        )
        saved += 1

    print(f"\nSaved {saved} month(s) of tfe_in_sinter till_month for {PLANT}/{UNIT}.")


if __name__ == "__main__":
    main()
