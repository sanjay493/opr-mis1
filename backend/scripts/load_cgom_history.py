"""One-off: CGOM's monthly iron ore rakes before the mines' rake record starts,
from "Rakes 2020-2023.xlsx" (sheet `cgom`, IOC-Rajhara + Rowghat = Total, Apr 2020
to Mar 2023), into iron_ore_rake as mine BGM / wagon BS / dest BSP (the same shape
the CSV gives CGOM up to 2024-04-30, see iron_ore_rakes.py).

The sheet has no lump / fines split. A new month stores the total as lump; a month
the rake record already holds (Nov 2022 on) keeps its lump and fines becomes the
rest, so the total is the sheet's. Only BGM rows are written; the other mines' rows
stay. Dry run unless --apply. A later CSV upload that covers these months replaces
them again.

    python scripts/load_cgom_history.py <xlsx> [--apply]
"""
import datetime
import os
import sys

import openpyxl

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from repo import rake as rrake  # noqa: E402

MINE, WAGON, DEST = "BGM", "BS", "BSP"
USER = "cgom-history-load"


def sheet_totals(path: str) -> dict:
    """{YYYY-MM: Total} from the three Apr-Mar blocks of the `cgom` sheet."""
    ws = openpyxl.load_workbook(path, data_only=True)["cgom"]
    out = {}
    for row in ws.iter_rows(values_only=True):
        for at in (1, 5, 9):    # label column of each block; its Total is 3 to the right
            label = row[at] if at < len(row) else None
            if isinstance(label, str) and "'" in label and label[:3].isalpha():
                month = datetime.datetime.strptime(label.replace("'", " 20"), "%b %Y")
                out[month.strftime("%Y-%m")] = float(row[at + 3])
    return out


def main(path: str, apply: bool):
    totals = sheet_totals(path)
    assert len(totals) == 36, f"expected 36 months, found {len(totals)}"
    have = {r["report_month"]: r for r in rrake._read(
        "SELECT report_month, lump_rakes, fines_rakes FROM iron_ore_rake WHERE mine_code = %s AND wagon_code = %s"
        " AND dest = %s", (MINE, WAGON, DEST))}
    rows = []
    for month, total in sorted(totals.items()):
        old = have.get(month)
        lump = old["lump_rakes"] if old else total
        rows.append({"report_month": month, "mine_code": MINE, "wagon_code": WAGON, "dest": DEST,
                     "lump_rakes": lump, "fines_rakes": total - lump})
        was = f"{old['lump_rakes'] + old['fines_rakes']:g}" if old else "-"
        print(f"{month}  {was:>5} -> {total:g}")
    if apply:
        print(rrake.upsert_iron_ore_rakes(rows, USER))
    else:
        print("dry run; --apply to write")


if __name__ == "__main__":
    main(sys.argv[1], "--apply" in sys.argv)
