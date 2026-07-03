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
  DSP rows, unit == "Coke Ovens":
    "coal_tar_yield"              -> "crude_tar_yield"
    "crude_benzol"                -> "crude_benzol_yield"
    "ammonium_sulphate"           -> "ammonium_sulphate_yield"
  BSL rows, any unit:
    "coal_to_hot_metal"           -> "coal_to_hm"
    "crude_tar"                   -> "crude_tar_yield"
    "crude_benzol"                -> "crude_benzol_yield"
    "ammonium_sulphate"           -> "ammonium_sulphate_yield"

Also moves "coal_to_hm" into the "General" unit wherever it was stored
under a per-furnace/BF-shop unit instead (ISP: "BF-5", BSL: "BF_Shop"),
so the parameter lives under the same unit across all plants — RSP/BSP/
DSP already store it under "General", which is also where the current
ISP/BSL extractors write it going forward; this only fixes old rows.

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

_DSP_COKE_RENAMES = {
    "coal_tar_yield":    "crude_tar_yield",
    "crude_benzol":      "crude_benzol_yield",
    "ammonium_sulphate": "ammonium_sulphate_yield",
}

_BSL_RENAMES = {
    "coal_to_hot_metal": "coal_to_hm",
    "crude_tar":         "crude_tar_yield",
    "crude_benzol":      "crude_benzol_yield",
    "ammonium_sulphate": "ammonium_sulphate_yield",
}

# (plant, wrong unit) -> coal_to_hm should live under "General" instead
_COAL_TO_HM_WRONG_UNIT = {
    "ISP": "BF-5",
    "BSL": "BF_Shop",
}


def _rename_keys(period_dict: dict, renames: dict) -> bool:
    """Rename keys in-place per `renames`. Returns True if anything changed."""
    changed = False
    for old_key, new_key in renames.items():
        if old_key in period_dict:
            period_dict[new_key] = period_dict.pop(old_key)
            changed = True
    return changed


def _move_coal_to_hm(cur, apply: bool) -> int:
    """Move "coal_to_hm" out of the wrong per-plant unit and into "General",
    merging into an existing General row if one exists for that month.
    Returns the number of (plant, month) pairs fixed."""
    moves = []  # (plant, month, src_unit, src_id, src_tj, gen_id_or_None, gen_tj)
    for plant, wrong_unit in _COAL_TO_HM_WRONG_UNIT.items():
        cur.execute(
            "SELECT id, report_month, techno_json FROM techno_data WHERE plant=? AND unit=?",
            (plant, wrong_unit),
        )
        for src_id, rm, src_json in cur.fetchall():
            src_tj = json.loads(src_json)
            if not any("coal_to_hm" in src_tj.get(p, {}) for p in ("month", "till_month")):
                continue
            cur.execute(
                "SELECT id, techno_json FROM techno_data WHERE plant=? AND report_month=? AND unit='General'",
                (plant, rm),
            )
            gen_row = cur.fetchone()
            gen_id, gen_tj = (gen_row[0], json.loads(gen_row[1])) if gen_row else (None, {"month": {}, "till_month": {}})
            moves.append((plant, rm, wrong_unit, src_id, src_tj, gen_id, gen_tj))

    print(f"\n{len(moves)} coal_to_hm value(s) stored under the wrong unit:")
    for plant, rm, wrong_unit, _sid, src_tj, _gid, gen_tj in moves:
        for period in ("month", "till_month"):
            v = src_tj.get(period, {}).get("coal_to_hm")
            if v is None:
                continue
            existing = gen_tj.get(period, {}).get("coal_to_hm")
            note = "" if existing is None or existing == v else f"  [CONFLICT: General already has {existing}, keeping it]"
            print(f"  [{plant}] {rm} / {wrong_unit} -> General ({period}={v}){note}")

    if not moves:
        return 0
    if not apply:
        return len(moves)

    for plant, rm, wrong_unit, src_id, src_tj, gen_id, gen_tj in moves:
        for period in ("month", "till_month"):
            v = src_tj.get(period, {}).pop("coal_to_hm", None)
            if v is None:
                continue
            gen_tj.setdefault(period, {})
            if "coal_to_hm" not in gen_tj[period]:  # never clobber a differing existing value
                gen_tj[period]["coal_to_hm"] = v
        cur.execute("UPDATE techno_data SET techno_json = ? WHERE id = ?", (json.dumps(src_tj), src_id))
        if gen_id is not None:
            cur.execute("UPDATE techno_data SET techno_json = ? WHERE id = ?", (json.dumps(gen_tj), gen_id))
        else:
            cur.execute(
                "INSERT INTO techno_data (plant, report_month, unit, techno_json) VALUES (?, ?, 'General', ?)",
                (plant, rm, json.dumps(gen_tj)),
            )
    return len(moves)


def main():
    apply = "--apply" in sys.argv

    conn = sqlite3.connect(db.DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    cur.execute(
        "SELECT id, plant, report_month, unit, techno_json FROM techno_data "
        "WHERE plant IN ('RSP', 'ISP', 'DSP', 'BSL')"
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
        elif plant == "DSP" and unit == "Coke Ovens":
            renames = _DSP_COKE_RENAMES
        elif plant == "BSL":
            renames = _BSL_RENAMES
        else:
            continue

        changed = False
        for period in ("month", "till_month"):
            if period in tj and _rename_keys(tj[period], renames):
                changed = True

        if changed:
            to_update.append((row["id"], json.dumps(tj), plant, row["report_month"], unit))

    print(f"Scanned {len(rows)} RSP/ISP/DSP/BSL techno_data rows.")
    print(f"{len(to_update)} rows contain a legacy key and would be renamed:")
    for _id, _json_str, plant, rm, unit in to_update:
        print(f"  [{plant}] {rm} / {unit}")

    move_count = _move_coal_to_hm(cur, apply)

    if not to_update and not move_count:
        print("\nNothing to do.")
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
    print(f"\nCommitted {len(to_update)} rename(s) and {move_count} unit move(s).")


if __name__ == "__main__":
    main()
