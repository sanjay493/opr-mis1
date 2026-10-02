"""
Backfill "Details of Rakes Detention Plant Wise" from a folder of the SAIL
Rail Movement Cell's monthly "Average Plant Detention Report" PDFs, using
the same extractor as /data-entry/rake-detention's "Extract from PDF".

Each report carries every month of its financial year up to the report
month (Apr..month), plus that month's page-3 "Improvement" summary. So:
  - rake_detention_monthly: every matched row's value for every month the
    report covers. Reports are processed oldest first, so a later report's
    (possibly revised) figure for an earlier month wins.
  - rake_detention_summary: the report's own month only.
Only rows the extractor matched to the Wagon Types registry ("ok") are
written; anything else is listed and skipped.

The report month is read from the file name ("..._(01-09-2026 to
30-09-2026).pdf"). Dry run by default — prints what would be added or
changed; pass --apply to write. A value already in the DB that differs
from the PDF is NOT overwritten (it may be a later report's revised
figure, e.g. page 4's multi-year history) — such conflicts are listed;
add --overwrite to replace them with the PDF's figure.

Run (from backend/):
    venv\\Scripts\\python.exe scripts\\backfill_rake_detention_pdfs.py "G:\\My Drive\\Report_format\\Miscellaneous"
    venv\\Scripts\\python.exe scripts\\backfill_rake_detention_pdfs.py "<folder>" --apply [--overwrite]
"""
import glob
import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import db  # noqa: E402
import page_rake_detention_pdf_extractor as ex  # noqa: E402

_PERIOD_RE = re.compile(r"01-(\d\d)-(\d{4})")


def _report_month(path):
    m = _PERIOD_RE.search(os.path.basename(path))
    return f"{m.group(2)}-{m.group(1)}" if m else None


def main(folder, apply, overwrite=False):
    files = [(m, p) for p in glob.glob(os.path.join(folder, "*Detention*.pdf"))
             for m in [_report_month(p)] if m]
    files.sort()
    if not files:
        print(f"No 'Average Plant Detention Report' PDFs with a dated name in {folder}")
        return 1

    monthly = {}   # report_month -> {master_id: value}, later reports overwrite
    summary = {}   # report_month -> [{period_row, plant, value}]
    for month, path in files:
        r = ex.extract_rake_detention_pdf(path, month)
        skipped = 0
        for sections in r["plants"].values():
            for sec in sections.values():
                for row in sec["rows"] + ([sec["total"]] if sec["total"] else []):
                    if row.get("status") != "ok" or row.get("matched_master_id") is None:
                        skipped += row.get("status") != "missing_in_pdf"
                        continue
                    for m, v in row["monthly"].items():
                        monthly.setdefault(m, {})[row["matched_master_id"]] = v
        summary[month] = [{"period_row": code, "plant": p, "value": v}
                          for code, by_plant in r["summary"].items() for p, v in by_plant.items()]
        print(f"{month}: {os.path.basename(path)}  "
              f"summary={'yes' if r['summary'] else 'NO'}  unmatched_rows={skipped}")
        for w in r["warnings"]:
            print(f"    WARN {w}")

    print()
    total_new = total_changed = 0
    for m in sorted(monthly):
        existing = db.get_rake_detention_monthly(m)
        new = sum(1 for k in monthly[m] if existing.get(k) is None)
        changed = [(k, existing[k], v) for k, v in monthly[m].items()
                   if existing.get(k) is not None and v is not None and abs(existing[k] - v) > 1e-9]
        total_new += new
        total_changed += len(changed)
        print(f"  {m}: {len(monthly[m]):3d} values  new={new:3d}  conflicts={len(changed):3d}")
        for k, old, v in changed:
            print(f"      conflict master {k}: DB {old} vs PDF {v}"
                  + ("  -> overwrite" if overwrite else "  -> kept (use --overwrite)"))
            if not overwrite:
                del monthly[m][k]
    for m in sorted(summary):
        existing = db.get_rake_detention_summary(m)
        filled = sum(1 for d in existing.values() for v in d.values() if v is not None)
        print(f"  summary {m}: {len(summary[m])} values (DB has {filled})")
    print(f"\nmonthly values: {total_new} new, {total_changed} conflicting")

    if not apply:
        print("Dry run — nothing written. Re-run with --apply to save.")
        return 0
    for m in sorted(monthly):
        db.save_rake_detention_monthly(m, [{"master_id": k, "value_hours": v} for k, v in monthly[m].items()])
    for m, rows in summary.items():
        if rows:
            db.save_rake_detention_summary(m, rows)
    print("Saved.")
    return 0


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if not args:
        print(__doc__)
        sys.exit(2)
    sys.exit(main(args[0], "--apply" in sys.argv, "--overwrite" in sys.argv))
