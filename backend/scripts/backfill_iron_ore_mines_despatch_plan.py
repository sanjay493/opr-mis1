"""
One-off backfill for Iron Ore Mines Despatch PLAN (mine-level,
mines_despatch_plan_monthly — see db.get_mines_production_despatch_monthly /
get_iron_ore_group_rollup_monthly) from Report_format/iron ore.xlsx.

This is the "despatch data ... comes from the user separately later" promised
in backfill_iron_ore_mines_production.py's docstring. Only despatch PLAN is in
this workbook (qty_plan per report_month x mine x material x end_use — Plan
has no Rail/Road split, matching mines_despatch_plan_monthly's grain).
Despatch Actual and Booked Quantity are still not provided.

Sheet1 has 6 stacked blocks, all covering 12 months Apr'26-Mar'27:

  row  2  "Tailing sales despatch plan"      rows 3-5    TAILINGS  / SALES
  row  8  "Dump Fines sale Despatch plan"    rows 9-12   DUMP_FINES/ SALES
  row 15  "Pellets despatch to captive"      row 16      PELLETS   / CAPTIVE
  row 20  "Dump Despatch Captive"            row 21      DUMP_FINES/ CAPTIVE
  row 25  "Lump Fines Despatch Captive"      rows 28-38  LUMP+FINES/ CAPTIVE
  row 42  "conversion agent"                 rows 44-47  LUMP+FINES/ PELLET_CONV

Blocks 1-4 are a single 12-wide row of months (cols B..M) per mine.
Blocks 5-6 are 24 wide: a (Lump, Fines) column pair per month, month dates on
the block's first row at cols B,D,F,... and a Lump/Fines sub-header row below.
In block 6 only the Fines column is populated (conversion agents take fines).

Values in this workbook are already in '000 T (unlike
Report_format/iron ore production.xlsx which was raw tonnes) — magnitudes
match mines_production_monthly's '000 T figures for the same mines/materials,
so NO scaling is applied here. The one negative source cell (ROWGHAT Sep'26
Fines Captive = -29) is a data-entry error in the sheet and is skipped
(left empty in the DB) per direct instruction (2026-08-27).

Run once: python scripts/backfill_iron_ore_mines_despatch_plan.py [--apply]
Without --apply, only prints the diff against current DB values (dry run).
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import db

import openpyxl

WORKBOOK_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "Report_format", "iron ore.xlsx",
)

# This workbook is already in '000 T (see module docstring).
UNIT_SCALE = 1

# Source cells to skip entirely (leave NULL/absent in the DB), keyed
# (report_month, mine_code, material_code, end_use_code). ROWGHAT Sep'26
# Fines Captive is -29 in the sheet — a data-entry error, not a real plan.
EXCLUDE = {("2026-09", "ROWGHAT", "FINES", "CAPTIVE")}

MINE_NAME_TO_CODE = {
    "kiriburu": "KIRIBURU", "meghahatuburu": "MEGHAHATUBURU", "gua": "GUA",
    "manoharpur": "MANOHARPUR", "bolani": "BOLANI", "barsua": "BARSUA",
    "taldih": "TALDIH", "kalta": "KALTA", "rajhara": "RAJHARA",
    "dalli": "DALLI", "rowghat": "ROWGHAT",
}

# (title_row, first_data_row, last_data_row, layout, [(material_code, end_use_code), ...])
#   layout "narrow": one 12-wide row of months, cols B..M
#   layout "wide":   (Lump, Fines) column pair per month, months on title_row
SINGLE_BLOCKS = [
    (2, 3, 5, "narrow", ("TAILINGS", "SALES")),
    (8, 9, 12, "narrow", ("DUMP_FINES", "SALES")),
    (15, 16, 16, "narrow", ("PELLETS", "CAPTIVE")),
    (20, 21, 21, "narrow", ("DUMP_FINES", "CAPTIVE")),
]
# (date_row, first_data_row, last_data_row, end_use_code) — month dates sit on
# date_row at cols B,D,F,...; a Lump/Fines sub-header row sits just below it.
WIDE_BLOCKS = [
    (26, 28, 38, "CAPTIVE"),
    (42, 44, 47, "PELLET_CONV"),
]


def _month_str(dt) -> str:
    return f"{dt.year}-{dt.month:02d}"


def _mine_code(name):
    return MINE_NAME_TO_CODE[str(name).strip().lower()]


def _num(v):
    if v is None or v == "":
        return None
    return float(v) * UNIT_SCALE


def build_entries():
    """-> {(report_month, mine_code): [{material_code, end_use_code, plan}, ...]}"""
    wb = openpyxl.load_workbook(WORKBOOK_PATH, data_only=True)
    ws = wb["Sheet1"]
    out = {}  # (rm, mine_code) -> list

    def add(rm, mine_code, material_code, end_use_code, plan):
        if plan is None:
            return
        if (rm, mine_code, material_code, end_use_code) in EXCLUDE:
            return
        out.setdefault((rm, mine_code), []).append({
            "material_code": material_code, "end_use_code": end_use_code, "plan": plan,
        })

    for title_row, first_row, last_row, _layout, (material_code, end_use_code) in SINGLE_BLOCKS:
        months = []
        col = 2
        while ws.cell(row=title_row, column=col).value is not None:
            months.append((col, _month_str(ws.cell(row=title_row, column=col).value)))
            col += 1
        for r in range(first_row, last_row + 1):
            name = ws.cell(row=r, column=1).value
            if name is None:
                continue
            mc = _mine_code(name)
            for col, rm in months:
                add(rm, mc, material_code, end_use_code, _num(ws.cell(row=r, column=col).value))

    for date_row, first_row, last_row, end_use_code in WIDE_BLOCKS:
        months = []
        col = 2
        while ws.cell(row=date_row, column=col).value is not None:
            months.append((col, _month_str(ws.cell(row=date_row, column=col).value)))
            col += 2
        for r in range(first_row, last_row + 1):
            name = ws.cell(row=r, column=1).value
            if name is None:
                continue
            mc = _mine_code(name)
            for col, rm in months:
                add(rm, mc, "LUMP", end_use_code, _num(ws.cell(row=r, column=col).value))
                add(rm, mc, "FINES", end_use_code, _num(ws.cell(row=r, column=col + 1).value))

    return out


def diff_and_apply(apply: bool):
    entries_by_rm_mine = build_entries()
    changed = 0
    for (rm, mine_code) in sorted(entries_by_rm_mine):
        entries = entries_by_rm_mine[(rm, mine_code)]
        current = db.get_mines_production_despatch_monthly(rm, mine_code)["despatch_plan"]
        to_apply = []
        for e in entries:
            cur_p = current.get(e["material_code"], {}).get(e["end_use_code"])
            new_p = e["plan"]
            if cur_p is None or abs(cur_p - new_p) > 0.001:
                print(f"  {rm} {mine_code:>14} {e['material_code']:>10} {e['end_use_code']:>11}: "
                      f"plan {cur_p!r} -> {new_p}")
                changed += 1
            to_apply.append(e)
        if apply:
            db.save_mines_production_despatch_monthly(rm, mine_code, [], [], to_apply)
    print(f"{changed} cell(s) changed" + (" (applied)" if apply else " (dry run)"))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true", help="Write changes to the DB (default: dry run)")
    args = parser.parse_args()
    diff_and_apply(args.apply)
