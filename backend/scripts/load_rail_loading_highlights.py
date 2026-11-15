"""
Load SAIL's monthly rail loading (MIS PDF page 40.05, table
rail_loading_monthly) from the Rail Movement Cell's monthly highlights note,
kept as plain text with one "*Rail Transportation Performance of SAIL during
<MONTH> <YEAR>*" block per month (rail_loading_highlights.py parses it).

Prints every month's figures and anything the parser could not read, then
saves each parsed month through the repo. A month already loaded is
replaced, so the file can be re-run after it gains a month or a correction.
A month whose block lacks a figure is reported and skipped, never half-saved.
--dry-run prints only.

Run (from backend/):
    venv\\Scripts\\python.exe scripts\\load_rail_loading_highlights.py "<file>.txt" [--dry-run]
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

import rail_loading  # noqa: E402
import rail_loading_highlights  # noqa: E402
from rake_despatch_report import mlabel  # noqa: E402

USER = "load_rail_loading_highlights"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.strip().splitlines()[0])
    ap.add_argument("file", help="the highlights note (.txt, UTF-8)")
    ap.add_argument("--dry-run", action="store_true", help="print the figures, save nothing")
    args = ap.parse_args()
    with open(args.file, encoding="utf-8-sig") as f:
        months, problems = rail_loading_highlights.parse(f.read())

    labels = {code: label for _kind, code, label in rail_loading.ITEMS}
    for month in sorted(months):
        print(f"\n{mlabel(month)} ({month})")
        for code in rail_loading.CODES:
            print(f"  {labels[code]:<38}{rail_loading.fmt_rakes(months[month].get(code)):>8}")
    print(f"\n{len(months)} month(s) read, {len(problems)} problem(s)")
    for p in problems:
        print(f"  ! {p}")

    if args.dry_run:
        print("Dry run: nothing saved.")
    else:
        from repo import rake as rrake
        for month in sorted(months):
            n = rrake.save_rail_loading(month, months[month], USER)
            print(f"saved {month}: {n} rows")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
