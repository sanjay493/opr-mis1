"""
One-off backfill: link existing breakdown-log entries to the capital repair
they really are (breakdown_table.capital_repair_id), using bd_cr_link's
suggestion rule. Plants often log a capital repair in the breakdown log too
(exact date-times + a remark naming it) - linked, every report counts the
event once, as the CR.

Usage (from backend/):
  venv\\Scripts\\python.exe scripts\\link_breakdown_capital_repairs.py          # dry-run
  venv\\Scripts\\python.exe scripts\\link_breakdown_capital_repairs.py --apply  # write links

Dry-run is the default on purpose: review every proposed pair first. Only
entries with no link yet are considered, so re-running never overwrites a
link set (or cleared) by hand on the breakdown entry form.
"""
import argparse
import os
import sys

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BACKEND_DIR)

import bd_cr_link  # noqa: E402
import db  # noqa: E402
from api_breakdown import _actual_crs  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="write the links (default: dry-run)")
    args = ap.parse_args()

    breakdowns = [b for b in db.list_breakdown_entries() if not b.get("capital_repair_id")]
    crs_by_plant = {}
    pairs = []
    for b in sorted(breakdowns, key=lambda r: (r["plant"], str(r["start_ts"]))):
        crs = crs_by_plant.setdefault(b["plant"], _actual_crs(b["plant"]))
        cr = bd_cr_link.suggest_cr(b, crs)
        if cr:
            pairs.append((b, cr))

    print(f"{len(pairs)} breakdown entr{'y' if len(pairs) == 1 else 'ies'} look like a capital repair:\n")
    for b, cr in pairs:
        end = "ongoing" if b.get("is_ongoing") else b.get("end_ts")
        cr_end = "ongoing" if cr.get("actual_ongoing") else cr.get("actual_end")
        print(f"  {b['plant']}  BD #{b['id']:<4} {b['unit_type']}/{b['unit_name']:<10} {b['start_ts']} -> {end}")
        print(f"            {(b.get('cause') or '').splitlines()[0][:100]}")
        print(f"        ->  CR #{cr['id']:<4} {cr.get('shop')}/{cr.get('equipment')}  {cr['actual_start']} -> {cr_end}"
              f"  ({cr.get('activity')})\n")

    if not args.apply:
        print("Dry-run: nothing written. Re-run with --apply to link these.")
        return
    for b, cr in pairs:
        db.update_breakdown_entry(b["id"], updated_by="link_breakdown_capital_repairs.py",
                                  capital_repair_id=cr["id"])
    print(f"Linked {len(pairs)} entr{'y' if len(pairs) == 1 else 'ies'}.")


if __name__ == "__main__":
    main()
