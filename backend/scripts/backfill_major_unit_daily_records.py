"""
One-off backfill for Annexure-III's Daily best-ever records
(major_unit_daily_record — see db.py's own comment and page_major_unit_
records.py's module docstring) from Report_format/Plants Best/
{BSL,RSP,ISP,BSP}.xlsx (DSP has no such workbook — its registry was given
directly per instruction, so DSP is skipped here; its Daily figures are
filled in going forward via /data-entry/major-unit-daily, see
page_major_unit_records.py). The "Saleable Steel Despatch" row added to
every plant (2026-09-23) is likewise absent from all four workbooks, so it
is simply never matched by xp.take_row and stays empty here too.

Reads each registry unit's Daily Prod/Date cell (shared parsing with
verify_major_unit_best_records.py — see major_unit_xlsx_parse.py) and
upserts plant_code/unit_label/value/unit_of_measure/record_date/remarks/
sort_order into major_unit_daily_record via db.save_major_unit_daily_record.

Dates are normalized to ISO 'YYYY-MM-DD' where they parse cleanly as a
plain DD.M(M).YY(YY) string or an Excel-native datetime; a 2-digit year is
read as 20YY unless that would be more than 1 year in the future (today's
date), in which case it's 19YY (this workbook's dates span 1976-2026).
A value/date that can't be parsed as a single clean number+date (ISP's
occasional compound cells combining two records in one, e.g. Oven
Pushing's "COB#10 - 103\\nCOB#11- 101" / "24.1.23\\n30.1.23") is kept as
raw text in `remarks` instead — nothing is silently dropped or guessed.

Run: python scripts/backfill_major_unit_daily_records.py [--apply]
Without --apply, only prints what would be written (dry run). Idempotent —
safe to re-run.
"""
import argparse
import datetime as _dt
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import db
import page_major_unit_records as mur
import major_unit_xlsx_parse as xp

_DATE_RE = re.compile(r"^\s*(\d{1,2})[.\-/](\d{1,2})[.\-/](\d{2,4})\s*$")


def _parse_date(raw) -> str | None:
    """DD.M(M).YY(YY) / DD-MM-YY / a datetime -> ISO 'YYYY-MM-DD', or None
    if it doesn't parse as one clean date (e.g. compound multi-date text)."""
    if isinstance(raw, _dt.datetime):
        return raw.date().isoformat()
    if isinstance(raw, _dt.date):
        return raw.isoformat()
    if not isinstance(raw, str):
        return None
    m = _DATE_RE.match(raw)
    if not m:
        return None
    d, mo, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
    if y < 100:
        this_yy = _dt.date.today().year % 100
        y += 2000 if y <= this_yy + 1 else 1900
    try:
        return _dt.date(y, mo, d).isoformat()
    except ValueError:
        return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="write to the DB (default: dry run)")
    args = ap.parse_args()

    rows_to_write = []  # (plant, unit_label, value, unit_of_measure, record_date, remarks, sort_order)
    unparsed_dates = []

    for plant in ["BSL", "RSP", "ISP", "BSP"]:
        path = os.path.join(xp.SOURCE_DIR, f"{plant}.xlsx")
        wb_data = xp.PARSERS[plant](path)
        for sort_order, unit in enumerate(mur.registry_for(plant)):
            label = unit["label"]
            wb_row = xp.take_row(wb_data, plant, label)
            if wb_row is None or wb_row.get("daily") is None:
                continue
            value_raw, date_raw = wb_row["daily"]
            remarks = wb_row.get("remarks")

            value = value_raw if isinstance(value_raw, (int, float)) else None
            record_date = _parse_date(date_raw) if value is not None else None

            if value is None or record_date is None:
                # Compound/unparseable cell (raw text value, or a date that
                # didn't parse) — keep everything as remarks rather than
                # guessing or dropping it.
                bits = [str(value_raw) if value_raw is not None else "", str(date_raw) if date_raw is not None else ""]
                combined = " / ".join(b for b in bits if b)
                remarks = (f"{remarks} | {combined}" if remarks else combined) or remarks
                unparsed_dates.append((plant, label, value_raw, date_raw))
                value = None
                record_date = None

            rows_to_write.append((plant, label, value, unit["unit"], record_date, remarks, sort_order))

    print(f"{len(rows_to_write)} unit rows found across BSL/RSP/ISP/BSP.")
    for plant, label, value, uom, record_date, remarks, sort_order in rows_to_write:
        print(f"  {plant:4s} {label:32s} value={value!r:>10} uom={uom:8s} date={record_date!r:12} "
              f"remarks={remarks!r}")

    if unparsed_dates:
        print(f"\n{len(unparsed_dates)} cells kept as remarks-only (compound/unparseable value or date):")
        for plant, label, v, d in unparsed_dates:
            print(f"  {plant:4s} {label:32s} raw_value={v!r} raw_date={d!r}")

    if not args.apply:
        print("\nDry run — no changes written. Re-run with --apply to write.")
        return

    for plant, label, value, uom, record_date, remarks, sort_order in rows_to_write:
        db.save_major_unit_daily_record(
            plant_code=plant, unit_label=label, value=value, unit_of_measure=uom,
            record_date=record_date, remarks=remarks, sort_order=sort_order,
            updated_by="backfill_major_unit_daily_records.py",
        )
    print(f"\nWrote {len(rows_to_write)} rows to major_unit_daily_record.")


if __name__ == "__main__":
    main()
