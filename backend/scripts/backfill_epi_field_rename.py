"""
One-off backfill: unify the retired "specific_co2_emissions"/
"specific_water_consumption" techno_data keys onto the canonical
"sp_co2_emission"/"sp_water_consumption" keys every plant's own techno
extractor (ISP, RSP, BSP-OISCO) was switched to write instead (per direct
instruction, 2026-09-15) — see techno_project/isp_technopara_map.json,
bsp_oisco_map.json, rsp_technopara_sections.py, and
frontend/src/lib/technoParamRegistry.js. The EMD "Major EPIs" report
extractor (techno_project/coal_co2_epi_extractor.py) already wrote the
canonical keys and is untouched by this rename.

For every techno_data row (any plant, unit='General'), in both the "month"
and "till_month" period dicts independently:
  - old key present, new key missing/null  -> copy the value across
  - old key present, new key already set to a DIFFERENT value -> the
    canonical key's existing value is kept as the sole source going
    forward (not overwritten); flagged as a CONFLICT in the output for
    someone to double check against the source report if it matters
  - either way, the old key is then deleted — this is a rename, not an
    alias: after this runs, sp_co2_emission/sp_water_consumption is the
    only field left in the row.
Rows with neither key, or with the old key already deleted, are left alone
(and not counted).

Run once:  python scripts/backfill_epi_field_rename.py             (dry run)
           python scripts/backfill_epi_field_rename.py --apply     (writes DB)
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import db

_RENAMES = {
    "specific_co2_emissions": "sp_co2_emission",
    "specific_water_consumption": "sp_water_consumption",
}
_PERIODS = ("month", "till_month")


def main(apply: bool):
    db.init_db()
    conn = db.connect()
    cur = conn.cursor()
    cur.execute(
        "SELECT plant, report_month, unit, techno_json, source_file "
        "FROM techno_data WHERE unit = 'General'"
    )
    rows = cur.fetchall()

    changed = 0
    conflicts = 0
    for plant, report_month, unit, techno_json_raw, source_file in rows:
        try:
            data = json.loads(techno_json_raw) if techno_json_raw else {}
        except (json.JSONDecodeError, TypeError):
            print(f"  SKIP {plant} {report_month}: unparseable techno_json")
            continue

        row_changed = False
        for period in _PERIODS:
            period_data = data.get(period)
            if not isinstance(period_data, dict):
                continue
            for old_key, new_key in _RENAMES.items():
                if old_key not in period_data:
                    continue
                old_val = period_data.pop(old_key)
                new_val = period_data.get(new_key)
                row_changed = True
                if new_val is None:
                    period_data[new_key] = old_val
                    print(f"  {plant} {report_month} {period}.{new_key}: (blank) -> {old_val!r} (from {old_key})")
                elif new_val != old_val:
                    conflicts += 1
                    print(f"  CONFLICT {plant} {report_month} {period}: "
                          f"{new_key}={new_val!r} kept, {old_key}={old_val!r} discarded")
                else:
                    print(f"  {plant} {report_month} {period}.{old_key}: duplicate of {new_key}={new_val!r}, dropped")

        if row_changed:
            changed += 1
            if apply:
                db._raw_upsert_techno_data(plant, report_month, unit, data, source_file=source_file or '', conn=conn)

    if apply:
        conn.commit()
    conn.close()

    print(f"\n{changed} row(s) {'updated' if apply else 'to update (dry run)'}"
          + (f", {conflicts} conflict(s) flagged above" if conflicts else ""))
    if not apply and changed:
        print("Re-run with --apply to write these changes.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true", help="Write changes to the DB (default: dry run)")
    args = parser.parse_args()
    main(args.apply)
