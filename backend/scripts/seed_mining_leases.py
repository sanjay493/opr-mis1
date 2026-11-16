"""Seed mining_leases from the "Details of SAIL Mining Leases" sheet.

    python scripts/seed_mining_leases.py "<path to .xlsx>"

Replaces the whole table (Data Entry > Reference > Mining Leases is the place
to edit afterwards). Text is kept as the sheet has it (typos and the S.No.
order included, except as group_rows says); the sheet's merged ranges become the *_span columns. The
header is rows 5-6, data starts at row 7 and ends at the last row with a
S.No. or lease name.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import openpyxl

import mining_leases

FIRST_DATA_ROW = 7
COLS = {"A": "s_no", "B": "mine", "C": "state", "D": "lease", "E": "mineral", "F": "area", "G": "reserves", "H": "status"}


def _text(v) -> str:
    if v is None:
        return ""
    if isinstance(v, float) and v == int(v):
        v = int(v)
    return str(v).strip()


# Category column (merged down, printed vertically): the sheet's first 26 leases
# are iron and manganese ore, then flux (limestone, dolomite, dunite) and coal; the
# last three (magnesite and dunite) are flux too, so they move up to join it.
GROUPS = (("Iron Ore & Manganese Ore", 26), ("Flux", 14), ("Coal", 13))
MOVE_UP = 3             # the last 3 rows go right after the flux rows of the sheet (its S.No. 37)
FLUX_END_SNO = 37


def group_rows(rows: list) -> list:
    """rows (the sheet's 53 leases, spans set) -> the same rows with the last
    MOVE_UP rows moved up after S.No. FLUX_END_SNO, those and every later row
    renumbered in sequence, and the Category column filled and merged per GROUPS."""
    at = next(i for i, r in enumerate(rows) if r["s_no"] == str(FLUX_END_SNO)) + 1
    moved = rows[-MOVE_UP:]
    rows = rows[:at] + moved + rows[at:-MOVE_UP]
    assert len(rows) == sum(n for _g, n in GROUPS), len(rows)
    for i in range(at, len(rows)):
        rows[i]["s_no"] = str(i + 1)
    pos = 0
    for name, n in GROUPS:
        for k in range(n):
            rows[pos + k]["grp"] = name if k == 0 else ""
            rows[pos + k]["grp_span"] = n if k == 0 else 0
        pos += n
    return rows


def read_rows(path: str) -> list:
    ws = openpyxl.load_workbook(path, data_only=True).active
    last = max(r for r in range(FIRST_DATA_ROW, ws.max_row + 1) if ws[f"A{r}"].value is not None or ws[f"D{r}"].value is not None)
    rows = [{c: _text(ws[f"{L}{r}"].value) for L, c in COLS.items()} for r in range(FIRST_DATA_ROW, last + 1)]
    for r in rows:
        r.update({f"{c}_span": 1 for c in COLS.values() if c != "s_no"})
    for m in ws.merged_cells.ranges:
        col = COLS.get(openpyxl.utils.get_column_letter(m.min_col))
        if m.min_col != m.max_col or col in (None, "s_no") or m.min_row < FIRST_DATA_ROW or m.min_row > last:
            continue
        end = min(m.max_row, last)
        rows[m.min_row - FIRST_DATA_ROW][f"{col}_span"] = end - m.min_row + 1
        for i in range(m.min_row + 1 - FIRST_DATA_ROW, end + 1 - FIRST_DATA_ROW):
            rows[i][f"{col}_span"] = 0
            rows[i][col] = ""
    return rows


if __name__ == "__main__":
    rows = group_rows(read_rows(sys.argv[1]))
    print(f"{mining_leases.save(rows, 'seed') } rows saved")
