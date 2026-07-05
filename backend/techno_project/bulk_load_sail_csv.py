"""
Bulk-load hand-corrected SAIL techno values from a CSV straight into
techno_data, via the same merge_upsert_techno_data() path the manual-entry
UI (/api/techno/manual/save) uses — so existing params on the same
plant/unit/month row are preserved, not clobbered.

CSV columns (header required):
    plant,report_month,unit,period,key,value

    plant        - optional, defaults to SAIL if blank
    report_month - required, "YYYY-MM" (e.g. "2024-03")
    unit         - required, e.g. BF_Shop, General, SMS
    period       - optional, defaults to "till_month" if blank
                   ("month" or "till_month")
    key          - required, e.g. bf_productivity, specific_energy_consumption
    value        - required, numeric. Blank rows are skipped (not written as
                   null — matches merge_upsert semantics: null never clobbers).

Example CSV:
    plant,report_month,unit,period,key,value
    ,2023-03,BF_Shop,,bf_productivity,1.75
    ,2024-03,General,,specific_energy_consumption,6.42
    ,2024-03,SMS,,tmi,1042

Dry-run by default: prints what would be written without touching the DB.
Pass --apply to actually commit.

Run from backend/:
    python techno_project/bulk_load_sail_csv.py path/to/file.csv          # dry run
    python techno_project/bulk_load_sail_csv.py path/to/file.csv --apply  # commit
"""
import csv
import re
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
import db

_MONTH_RE = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")
_VALID_PERIODS = {"month", "till_month"}


def _load_rows(csv_path: str):
    """Read and validate CSV rows. Returns (valid_rows, errors)."""
    valid, errors = [], []
    with open(csv_path, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        missing = {"report_month", "unit", "key", "value"} - set(reader.fieldnames or [])
        if missing:
            raise SystemExit(f"CSV is missing required column(s): {', '.join(sorted(missing))}")

        for i, row in enumerate(reader, start=2):  # start=2: header is line 1
            plant  = (row.get("plant")  or "SAIL").strip().upper()
            rm     = (row.get("report_month") or "").strip()
            unit   = (row.get("unit")   or "").strip()
            period = (row.get("period") or "till_month").strip() or "till_month"
            key    = (row.get("key")    or "").strip()
            val_s  = (row.get("value")  or "").strip()

            if not rm or not unit or not key:
                errors.append(f"line {i}: missing report_month/unit/key — skipped")
                continue
            if not _MONTH_RE.match(rm):
                errors.append(f"line {i}: bad report_month '{rm}' (want YYYY-MM) — skipped")
                continue
            if period not in _VALID_PERIODS:
                errors.append(f"line {i}: bad period '{period}' (want 'month' or 'till_month') — skipped")
                continue
            if not val_s:
                errors.append(f"line {i}: blank value for {plant}/{rm}/{unit}/{key} — skipped (blank never overwrites)")
                continue
            try:
                val = float(val_s)
            except ValueError:
                errors.append(f"line {i}: value '{val_s}' is not numeric — skipped")
                continue

            valid.append((plant, rm, unit, period, key, val))
    return valid, errors


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    apply = "--apply" in sys.argv
    if not args:
        raise SystemExit("Usage: python bulk_load_sail_csv.py <path.csv> [--apply]")
    csv_path = args[0]

    rows, errors = _load_rows(csv_path)

    if errors:
        print(f"{len(errors)} row(s) skipped due to errors:")
        for e in errors:
            print(f"  {e}")
        print()

    if not rows:
        print("Nothing valid to load.")
        return

    # Group into one techno_json patch per (plant, report_month, unit)
    groups: dict = defaultdict(lambda: {"month": {}, "till_month": {}})
    for plant, rm, unit, period, key, val in rows:
        groups[(plant, rm, unit)][period][key] = val

    print(f"{len(rows)} value(s) across {len(groups)} plant/month/unit row(s):")
    for (plant, rm, unit), patch in sorted(groups.items()):
        parts = [f"{k}={v}" for period in ("month", "till_month") for k, v in patch[period].items()]
        print(f"  [{plant}] {rm} / {unit}: {', '.join(parts)}")

    if not apply:
        print("\nDry run only — no changes written. Re-run with --apply to commit.")
        return

    for (plant, rm, unit), patch in groups.items():
        db.merge_upsert_techno_data(
            plant=plant, report_month=rm, unit=unit,
            new_techno_json=patch, source_file="manual_bulk_csv",
        )
    print(f"\nCommitted {len(rows)} value(s) across {len(groups)} row(s).")


if __name__ == "__main__":
    main()
