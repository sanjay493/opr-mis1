"""
One-off backfill: RLTIFR (Reportable Lost Time Injury Frequency Rate) for
Apr-Jul'26, transcribed from Report_format/Plant wise Comparative for
Apr-Jul'26.pdf.

RLTIFR used to be a hard-coded stopgap in hardcoded_config.json
("key_parameters" -> "pdf_values" -> "rltifr"). It is now a real
techno_data key: plant / report_month "2026-07" / unit "General", written
into the "till_month" dict (the Apr-Jul'26 figure is a cumulative — there
is no single-month split in the source). The Key Parameters report page
(page_key_parameters.py, "RLTIFR" row, kind="general") reads it from there,
same as CAPEX / Labour Productivity / Demurrage etc. Future months are
entered via /data-entry/key-parameters-manual (month + till-month) or wired
to an extractor.

Run once:  python scripts/backfill_rltifr_202607.py            (dry run)
           python scripts/backfill_rltifr_202607.py --apply    (writes DB)
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import db

REPORT_MONTH = "2026-07"
UNIT = "General"
KEY = "rltifr"

# plant -> Apr-Jul'26 cumulative RLTIFR
VALUES = {
    "BSP": 0.19,
    "DSP": 0.11,
    "RSP": 0.12,
    "BSL": 0.05,
    "ISP": 0.00,
}


def main(apply: bool):
    db.init_db()
    changed = 0
    for plant, new_val in VALUES.items():
        existing = db.get_techno_data(plant, REPORT_MONTH, UNIT)
        cur_val = existing.get(UNIT, {}).get("till_month", {}).get(KEY)
        if cur_val is not None and abs(cur_val - new_val) < 1e-9:
            print(f"  {plant} {REPORT_MONTH} {UNIT}/{KEY}: {cur_val!r} (unchanged)")
            continue
        print(f"  {plant} {REPORT_MONTH} {UNIT}/{KEY}: {cur_val!r} -> {new_val}")
        changed += 1
        if apply:
            db.merge_upsert_techno_data(
                plant=plant,
                report_month=REPORT_MONTH,
                unit=UNIT,
                new_techno_json={"month": {}, "till_month": {KEY: new_val}},
                source_file="manual",
            )
    print(f"\nRLTIFR: {changed} cell(s) {'applied' if apply else 'to change (dry run)'}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true", help="Write changes to the DB (default: dry run)")
    args = parser.parse_args()
    main(args.apply)
