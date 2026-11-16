"""Seed mining_leases from the "Details of SAIL Mining Leases" sheet.

    python scripts/seed_mining_leases.py "<path to .xlsx>"

Replaces the whole table (Data Entry > Reference > Mining Leases is the place
to edit afterwards). Text is kept as the sheet has it (typos and the S.No.
order included); the sheet's merged ranges become the *_span columns. The
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
    rows = read_rows(sys.argv[1])
    print(f"{mining_leases.save(rows, 'seed') } rows saved")
