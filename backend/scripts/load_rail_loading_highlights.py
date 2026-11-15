"""
Load SAIL's monthly rail loading (MIS PDF page 40.05, table
rail_loading_monthly) from the Rail Movement Cell's monthly highlights note,
kept as plain text with one "*Rail Transportation Performance of SAIL during
<MONTH> <YEAR>*" block per month (rail_loading_highlights.py parses it).

Prints every month's figures and anything the parser could not read, then
saves each parsed month through the repo. A month already loaded is
replaced, so the file can be re-run after it gains a month or a correction;
--month limits the run to the months named, leaving the others in the
database as they are (figures corrected there are not overwritten).
A month whose block lacks a figure is reported and skipped, never
half-saved: correct the note and run again. Each month is saved on its own,
so a failure part-way leaves the earlier months saved and whole.
--dry-run prints only. Exit code 1 if anything was reported.

Run (from backend/):
    venv\\Scripts\\python.exe scripts\\load_rail_loading_highlights.py "<file>.txt" [--dry-run] [--month YYYY-MM ...]
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

import rail_loading  # noqa: E402
import rail_loading_highlights  # noqa: E402
from rake_despatch_report import mlabel  # noqa: E402

USER = "load_rail_loading_highlights"


def read_note(path: str) -> str:
    """The note's text: UTF-8 (with or without BOM), else Windows ANSI —
    Notepad's two ways of saving it."""
    with open(path, "rb") as f:
        raw = f.read()
    try:
        return raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        return raw.decode("cp1252", errors="replace")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.strip().splitlines()[0])
    ap.add_argument("file", help="the highlights note (.txt)")
    ap.add_argument("--dry-run", action="store_true", help="print the figures, save nothing")
    ap.add_argument("--month", action="append", metavar="YYYY-MM",
                    help="load only this month (repeatable); default: every month in the file")
    args = ap.parse_args(argv)
    months, problems = rail_loading_highlights.parse(read_note(args.file))
    if args.month:
        problems += [f"{m}: asked for with --month but not read from the file"
                     for m in sorted(set(args.month) - set(months))]
        months = {m: v for m, v in months.items() if m in args.month}

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
        for month in sorted(months):
            n = rail_loading.save_month(month, months[month], USER)
            print(f"saved {month}: {n} rows")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
