"""
One-time script: rename legacy techno_data parameter keys to the canonical
short-form convention used across BSL/RSP/ISP and page_techno.py's schemas.

Renames (within the "month" and "till_month" dicts of techno_json):
  RSP/ISP rows, any unit:
    "sinter% in burden"  -> "sinter_in_burden"
    "pellet% in burden"  -> "pellet_in_burden"
  DSP rows, unit == "SMS":
    "ferro_silicon_consumption"   -> "fe-si"
    "ferro_manganese_consumption" -> "fe-mn"
    "silicon_manganese_consumption" -> "si-mn"
    "heat_size"                   -> "average_heat_weight"
    "oxygen_converter"            -> "oxygen_blowing"

Dry-run by default: prints a summary of rows that would change without
writing anything. Pass --apply to actually commit the renames.

Run from backend/:
    python techno_project/migrate_key_rename.py         # dry run
    python techno_project/migrate_key_rename.py --apply # commit
"""
import json
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
import db

_RSP_ISP_RENAMES = {
    "sinter% in burden": "sinter_in_burden",
    "pellet% in burden": "pellet_in_burden",
}

_DSP_SMS_RENAMES = {
    "ferro_silicon_consumption":     "fe-si",
    "ferro_manganese_consumption":   "fe-mn",
    "silicon_manganese_consumption": "si-mn",
    "heat_size":                     "average_heat_weight",
    "oxygen_converter":              "oxygen_blowing",
}


def _rename_keys(period_dict: dict, renames: dict) -> bool:
    """Rename keys in-place per `renames`. Returns True if anything changed."""
    changed = False
    for old_key, new_key in renames.items():
        if old_key in period_dict:
            period_dict[new_key] = period_dict.pop(old_key)
            changed = True
    return changed


def main():
    apply = "--apply" in sys.argv

    conn = sqlite3.connect(db.DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    cur.execute(
        "SELECT id, plant, report_month, unit, techno_json FROM techno_data "
        "WHERE plant IN ('RSP', 'ISP', 'DSP')"
    )
    rows = cur.fetchall()

    to_update = []  # (id, new_json_str, plant, report_month, unit)
    for row in rows:
        plant = row["plant"]
        unit = row["unit"]
        tj = json.loads(row["techno_json"])

        if plant in ("RSP", "ISP"):
            renames = _RSP_ISP_RENAMES
        elif plant == "DSP" and unit == "SMS":
            renames = _DSP_SMS_RENAMES
        else:
            continue

        changed = False
        for period in ("month", "till_month"):
            if period in tj and _rename_keys(tj[period], renames):
                changed = True

        if changed:
            to_update.append((row["id"], json.dumps(tj), plant, row["report_month"], unit))

    print(f"Scanned {len(rows)} RSP/ISP/DSP techno_data rows.")
    print(f"{len(to_update)} rows contain a legacy key and would be renamed:")
    for _id, _json_str, plant, rm, unit in to_update:
        print(f"  [{plant}] {rm} / {unit}")

    if not to_update:
        print("Nothing to do.")
        conn.close()
        return

    if not apply:
        print("\nDry run only — no changes written. Re-run with --apply to commit.")
        conn.close()
        return

    for _id, json_str, *_ in to_update:
        cur.execute("UPDATE techno_data SET techno_json = ? WHERE id = ?", (json_str, _id))
    conn.commit()
    conn.close()
    print(f"\nCommitted renames for {len(to_update)} rows.")


if __name__ == "__main__":
    main()
