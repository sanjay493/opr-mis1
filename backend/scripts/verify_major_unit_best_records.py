"""
Read-only verification for Annexure-III (5 ISPs Major Units Records) — see
page_major_unit_records.py's module docstring and the approved plan.

For every registry unit at BSP/BSL/RSP/ISP, computes the live Annual/Monthly
best from production_table (page_major_unit_records.best_for_unit) and
compares it against the same unit's claimed Annual/Monthly best in its
source workbook (I:\\My Drive\\Report_format\\Plants Best\\{plant}.xlsx —
parsing shared with backfill_major_unit_daily_records.py via
major_unit_xlsx_parse.py).

This makes NO database writes. It only reports:
  MATCH          - DB-derived value equals the workbook's claim
  DB_LOWER       - DB-derived value is below the workbook's claim. Per
                   direct instruction (2026-09-23), accepted as expected
                   for units whose production_table history starts well
                   after the workbook's claimed record year — individual-
                   unit tracking (BF#1, SMS-2, etc.) only began around
                   2015, while plant-level totals go back to 2000. A
                   DB_LOWER case whose xlsx period is itself recent (not
                   an old pre-2015 record) is the one worth a manual look.
  DB_HIGHER      - DB-derived value exceeds the workbook's claim (fine — a
                   newer record than the workbook's snapshot, or the
                   workbook's own figure is stale/wrong)
  UNMAPPED       - registry has no item_names for this unit (nothing to
                   compare; Daily-only via major_unit_daily_record)
  NO_DB_HISTORY  - item_names are mapped but production_table has no rows
                   for them at all (mapping likely wrong)
  NOT_IN_WORKBOOK - registry unit has no Annual/Monthly figure in the
                   workbook at all (e.g. a pure ABP-target subtotal row)

Run: python scripts/verify_major_unit_best_records.py [--tolerance 1.0]
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import db
import page_major_unit_records as mur
import major_unit_xlsx_parse as xp


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tolerance", type=float, default=1.0,
                     help="absolute value difference below which a mismatch is still counted MATCH (rounding)")
    args = ap.parse_args()

    conn = db.connect()
    cur = conn.cursor()

    totals = {"MATCH": 0, "DB_LOWER": 0, "DB_HIGHER": 0, "UNMAPPED": 0, "NO_DB_HISTORY": 0, "NOT_IN_WORKBOOK": 0}

    for plant in ["BSL", "RSP", "ISP", "BSP"]:
        path = os.path.join(xp.SOURCE_DIR, f"{plant}.xlsx")
        wb_data = xp.PARSERS[plant](path)
        print(f"\n{'=' * 10} {plant} {'=' * 10}")
        for unit in mur.registry_for(plant):
            label = unit["label"]
            live = mur.best_for_unit(cur, plant, unit["item_names"], unit["unit"] == mur._RATE)

            if not unit["item_names"]:
                totals["UNMAPPED"] += 1
                print(f"  [UNMAPPED]      {label}")
                continue

            wb_row = xp.take_row(wb_data, plant, label)
            if wb_row is None:
                totals["NOT_IN_WORKBOOK"] += 1
                print(f"  [NOT_IN_WORKBOOK] {label}  (registry label not found in {plant}.xlsx)")
                continue

            if live["month_best"] is None and live["fy_best"] is None:
                totals["NO_DB_HISTORY"] += 1
                print(f"  [NO_DB_HISTORY] {label}  item_names={unit['item_names']}")
                continue

            for period_key, wb_key in (("fy_best", "annual"), ("month_best", "monthly")):
                wb_pair = wb_row.get(wb_key)
                live_pair = live[period_key]
                if wb_pair is None or live_pair is None:
                    continue
                wb_val, wb_period = wb_pair
                diff = live_pair["value"] - wb_val
                status = ("MATCH" if abs(diff) <= args.tolerance
                          else "DB_LOWER" if diff < 0 else "DB_HIGHER")
                totals[status] += 1
                if status != "MATCH":
                    print(f"  [{status:9s}] {label:28s} {wb_key:7s} "
                          f"db={live_pair['value']} ({live_pair['period']})  "
                          f"xlsx={wb_val} ({wb_period})  diff={round(diff, 2)}")

    print("\n" + "=" * 30)
    for k, v in totals.items():
        print(f"{k:16s} {v}")


if __name__ == "__main__":
    main()
