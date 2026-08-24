"""
One-off backfill for Coal Mines Production, Washery, and Despatch data
(sail_mines_monthly, sections 'coal_prod'/'washery'/'coal_despatch' — see
page_sail_mines.py's SAIL_MINES_SECTIONS) from Report_format/Mines
data.xlsx.

The workbook has 3 pairs of tables (Production / Washery / Despatch), each
with an "APP" table (FY26-27 target, Apr'26-Mar'27, 12 months -> month_plan)
and an "Actual" table (Apr'25-Jul'26, 16 months -> month_actual, covering
both FY25-26 in full for future CPLY needs and FY26-27 YTD through the
current report month).

Item-name mapping to page_sail_mines.py's SAIL_MINES_SECTIONS (workbook ->
DB item), decided per direct instruction where the workbook doesn't split
cleanly:
  coal_prod:     "Total Coking Coal" -> "Raw Coking Coal"
                 "Total Non-Coking Coal" -> "Thermal Coal"
  washery:       "Input: Raw Coal" -> "Input Raw Coal"
                 "Output: Clean coal" -> "Clean Coal"
                 ("Out put: Middlings" has no DB item in this section — not
                 stored, matches SAIL_MINES_SECTIONS' washery items list)
  coal_despatch: "Clean Coal" -> "Clean Coal"
                 "Thermal coal (Middlings + Ramnagore coal)" -> "Thermal"
                 (whole combined figure goes to "Thermal" per direct
                 instruction; "Middlings" is left unset — the workbook
                 doesn't break despatch middlings out separately from
                 thermal/Ramnagore coal)

Run once: python scripts/backfill_mines_data.py [--apply]
Without --apply, only prints the diff against current DB values (dry run).
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import db

ACTUAL_MONTHS = ["2025-04", "2025-05", "2025-06", "2025-07", "2025-08", "2025-09",
                  "2025-10", "2025-11", "2025-12", "2026-01", "2026-02", "2026-03",
                  "2026-04", "2026-05", "2026-06", "2026-07"]
PLAN_MONTHS = ["2026-04", "2026-05", "2026-06", "2026-07", "2026-08", "2026-09",
                "2026-10", "2026-11", "2026-12", "2027-01", "2027-02", "2027-03"]

# {(section, item): {"actual": [16 values, ACTUAL_MONTHS], "plan": [12 values, PLAN_MONTHS]}}
DATA = {
    ("coal_prod", "Raw Coking Coal"): {
        "actual": [57888, 51508, 47155, 58994, 50321, 62760, 63865, 57405, 42025, 34480, 32226, 29922, 57833, 56563, 38087, 49803],
        "plan": [38250, 38250, 38250, 29180, 29180, 35230, 38260, 38250, 44300, 44300, 46300, 40250],
    },
    ("coal_prod", "Thermal Coal"): {
        "actual": [7680, 5025, 3030, 3810, 3315, 3345, 3480, 2790, 1890, 3855, 7545, 2310, 617, 0, 0, 0],
        "plan": [12000] * 12,
    },
    ("washery", "Input Raw Coal"): {
        "actual": [105500, 79600, 43900, 93500, 90600, 104500, 88400, 106600, 129500, 116400, 88300, 111400, 108500, 97400, 91600, 109700],
        "plan": [135460, 140270, 140270, 112130, 109590, 118190, 126560, 126560, 145320, 145320, 153200, 147130],
    },
    ("washery", "Clean Coal"): {
        "actual": [29319, 22890, 9305, 19608, 24132, 27615, 18922, 29340, 49357, 46086, 31617, 37077, 31528, 25547, 22999, 27606],
        "plan": [55710, 57690, 57690, 46120, 45070, 48600, 52050, 52050, 59760, 59760, 62990, 60510],
    },
    ("coal_despatch", "Clean Coal"): {
        "actual": [27505, 21833, 11704, 21332, 25231, 26009, 19523, 30194, 45753, 44825, 30398, 38214, 28040, 23025, 25255, 33117],
        "plan": [55710, 57690, 57690, 46120, 45070, 48600, 52050, 52050, 59760, 59760, 62990, 60510],
    },
    ("coal_despatch", "Thermal"): {
        "actual": [55724, 65676, 46670, 52288, 46003, 52356, 71392, 44959, 66759, 52912, 45630, 63222, 58186, 57662, 67794, 67703],
        "plan": [78620, 81170, 81170, 66290, 64950, 69500, 73920, 73920, 83840, 83840, 87990, 84790],
    },
}


# The workbook's figures are raw tonnes; every other sail_mines_monthly
# section (e.g. iron_ore_prod: ~700-1300 per mine per month) is stored in
# '000 T to match the report's own "Unit: '000 T" label (page_sail_mines.py
# declares the unit but never rescales at render time — the DB is expected
# to already hold '000 T), so every value here is divided by 1000 on the
# way in.
UNIT_SCALE = 1 / 1000


def build_entries_by_month():
    """{report_month: [ {section, item, actual, plan}, ... ]}"""
    out = {}
    for (section, item), vals in DATA.items():
        for rm, v in zip(ACTUAL_MONTHS, vals["actual"]):
            out.setdefault(rm, {}).setdefault((section, item), {})["actual"] = v * UNIT_SCALE
        for rm, v in zip(PLAN_MONTHS, vals["plan"]):
            out.setdefault(rm, {}).setdefault((section, item), {})["plan"] = v * UNIT_SCALE
    return {rm: [{"section": k[0], "item": k[1], **v} for k, v in by_key.items()]
            for rm, by_key in out.items()}


def diff_and_apply(apply: bool):
    entries_by_month = build_entries_by_month()
    changed = 0
    for rm in sorted(entries_by_month):
        entries = entries_by_month[rm]
        current = db.get_sail_mines_monthly([rm])[rm]
        for e in entries:
            cur = current.get(e["section"], {}).get(e["item"], {})
            cur_a, cur_p = cur.get("actual"), cur.get("plan")
            new_a, new_p = e.get("actual"), e.get("plan")
            a_changed = (new_a is not None) and (cur_a is None or abs(cur_a - new_a) > 0.01)
            p_changed = (new_p is not None) and (cur_p is None or abs(cur_p - new_p) > 0.01)
            if a_changed or p_changed:
                print(f"  {rm} {e['section']:>13} {e['item']:>16}: "
                      + (f"actual {cur_a!r}->{new_a} " if new_a is not None else "")
                      + (f"plan {cur_p!r}->{new_p}" if new_p is not None else ""))
                changed += 1
        if apply:
            # Preserve whichever field this batch doesn't carry for a given
            # (section, item) this month (e.g. actual-only for months
            # outside the APP's Apr'26-Mar'27 span) — a blind full-grid
            # save would otherwise NULL out an already-stored plan/actual.
            merged = []
            for e in entries:
                cur = current.get(e["section"], {}).get(e["item"], {})
                merged.append({
                    "section": e["section"], "item": e["item"],
                    "actual": e["actual"] if "actual" in e else cur.get("actual"),
                    "plan": e["plan"] if "plan" in e else cur.get("plan"),
                })
            db.save_sail_mines_monthly(rm, merged)
    print(f"{changed} cell(s) changed" + (" (applied)" if apply else " (dry run)"))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true", help="Write changes to the DB (default: dry run)")
    args = parser.parse_args()
    diff_and_apply(args.apply)
