"""
One-off backfill: BF Coke and Sinter cost of production (Rs/T) for
Apr-Jul'26, transcribed from Report_format/Plant wise Comparative for
Apr-Jul'26.pdf.

"BF Coke" and "Sinter" cost used to be hard-coded stopgaps in
hardcoded_config.json ("key_parameters" -> "pdf_values" -> cop_bf_coke /
cop_sinter). They are now real cost_trend_monthly products, COKE and SINTER,
read by page_key_parameters.py's "cop" rows exactly like HM/CS/SS.

The comparative sheet gives only a lump Rs/T per plant (no Variable/Fixed
split), so the figure is written under cost_type "VARIABLE",
till_month_value only (the Apr-Jul'26 cumulative; there is no single-month
figure). page_key_parameters._fetch_cop sums VARIABLE + FIXED, so a real
split entered later via /data-entry/cost-trend just adds to / replaces this.
Only the till_month column is touched (save_cost_trend_monthly_field), so a
month figure entered separately is never blanked.

COKE/SINTER have no page_cost_trend.py report page — they exist only for the
Inter Plant Performance Comparison page.

Run once:  python scripts/backfill_cop_coke_sinter_202607.py            (dry run)
           python scripts/backfill_cop_coke_sinter_202607.py --apply    (writes DB)
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import db

REPORT_MONTH = "2026-07"
COST_TYPE = "VARIABLE"

# product -> {plant: Apr-Jul'26 cumulative Rs/T}
DATA = {
    "COKE": {
        "BSP": 33232, "DSP": 33158, "RSP": 36081, "BSL": 31739, "ISP": 36110,
    },
    "SINTER": {
        "BSP": 5386, "DSP": 6149, "RSP": 5285, "BSL": 5709, "ISP": 6248,
    },
}


def main(apply: bool):
    db.init_db()
    changed = 0
    for product, by_plant in DATA.items():
        current = db.get_cost_trend_monthly(product, [REPORT_MONTH]).get(REPORT_MONTH, {})
        entries = []
        for plant, new_val in by_plant.items():
            cur_cell = current.get(COST_TYPE, {}).get(plant, {})
            cur_val = cur_cell.get("till_month")
            entries.append({"cost_type": COST_TYPE, "plant": plant, "value": new_val})
            if cur_val is not None and abs(cur_val - new_val) < 1e-9:
                print(f"  {product:<7} {plant:<4} {COST_TYPE} till_month: {cur_val!r} (unchanged)")
                continue
            print(f"  {product:<7} {plant:<4} {COST_TYPE} till_month: {cur_val!r} -> {new_val}")
            changed += 1
        if apply:
            db.save_cost_trend_monthly_field(REPORT_MONTH, product, entries, "till_month_value")
    print(f"\nCoP BF Coke / Sinter: {changed} cell(s) {'applied' if apply else 'to change (dry run)'}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true", help="Write changes to the DB (default: dry run)")
    args = parser.parse_args()
    main(args.apply)
