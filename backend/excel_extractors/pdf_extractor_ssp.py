"""
SSP PDF extractor — SSP-DPR Monthly Report (e.g. SSP-DPR-01.06.206-REVISED.pdf)

Single-page DPR with 5 numbered sections, each row laid out as:
    On Date Actual | Cum Actual | Monthly Target | Rate | Stock As on Date | Stock As on 1st
(trailing columns are absent on some rows — e.g. SMS (SLAB) has no On Date
Actual, so its first number IS the Cum Actual).

Extraction mapping (all "Cum Actual" / "Stock As on Date" columns):
  1.0 UNITWISE PRODUCTION
    Total Crude Steel   — "SMS (SLAB)" row, Cum Actual (On Date blank → 1st number)
    HRM                 — "HRM" row, Cum Actual
    Input SS Slab Stock       — "- STAINLESS" row, Stock As on Date
    Input Carbon Slab Stock   — "- CARBON" row, Stock As on Date
  2.0 SALEABLE PRODUCTION
    Saleable Steel            — "TOTAL" row, Cum Actual
    Carbon Steel Production   — "HRCS" row, Cum Actual
    NO1 Production            — "NO1" row, Cum Actual
    CRSS Production           — "CRSS" row, Cum Actual
    HRSS Production           — "HRSS" row, Cum Actual (no Target/Stock cols on this row)
    (Finished Steel — same "TOTAL" Cum Actual, existing alias of Saleable Steel)
  3.0 DESPATCHES
    Finished Carbon Steel Despatch — "HRCS" row, Cum Actual
    Total Saleable Steel Despatch  — "TOTAL" row, Cum Actual
    Finished Carbon Steel Stock    — "HRCS" row, Stock As on Date
    Finished Total Steel Stock     — "TOTAL" row, Stock As on Date
    Finished Stainless Steel Stock — computed: Finished Total Steel Stock - Finished Carbon Steel Stock

Values are in Tonnes in the PDF → stored as '000T (÷ 1000).

Mid-month reports
-----------------
The header date ("DAILY PRODUCTION REPORT FOR DD/MM/YYYY") is meant to be the
month's last day, but the plant routinely mails the report a day or two early
(e.g. a report headed 30/08 for a 31-day August). "Cum Actual" is then a
month-to-date running total and understates the month.

The DPR carries the plant's own full-month projection one column right of
"Cum Actual" — the "Rate" column (Cum x days_in_month / report_day). So on a
mid-month report each cumulative production/despatch item is taken from Rate
when it agrees with what Cum implies (basis "m-rate"), otherwise from the
computed projection Cum x days_in_month / report_day (basis "projected"). The
two "TOTAL" rows are always projected from Cum — their Rate cell silently
drops the HRSS sub-line. Point-in-time stock columns are never projected. A
strict no-op on a last-day or undated report (basis "cum").
"""
import calendar
import os
import re
import sys
from datetime import date

PLANT = "SSP"

_MONTHS = ["JAN", "FEB", "MAR", "APR", "MAY", "JUN",
           "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"]

_DATE_RE = re.compile(r'REPORT\s+FOR\s+(\d{1,2})[/.](\d{1,2})[/.](\d{4})', re.I)


def _detect_date_from_pdf_text(full_text: str):
    """(report_day, days_in_month, 'YYYY-MM') from the report's own 'DAILY
    PRODUCTION REPORT FOR DD/MM/YYYY' header line, or (None, None, None).

    That date is the day the cumulative ('Cum Actual') figures run through —
    normally the month's last day, but a day or two earlier when the report
    is mailed before month-end. It has nothing to do with the filename,
    which carries the issue date (typically the 1st of the next month)."""
    m = _DATE_RE.search(full_text[:400])
    if not m:
        return None, None, None
    d, mo, y = (int(g) for g in m.groups())
    try:
        date(y, mo, d)
    except ValueError:
        return None, None, None
    return d, calendar.monthrange(y, mo)[1], f"{y}-{mo:02d}"


def _detect_month_from_pdf_text(full_text: str):
    """'YYYY-MM' from the header date (see _detect_date_from_pdf_text), or None."""
    return _detect_date_from_pdf_text(full_text)[2]


def _is_mid_month(report_day, days_in_month) -> bool:
    return bool(report_day and days_in_month and 0 < report_day < days_in_month)


def _pick_month_value(rate, cum, report_day, days_in_month, use_rate=True, label=""):
    """Choose an item's full-month figure and label its basis.

    Last-day / undated report  → (cum, "cum")            — unchanged behaviour.
    Mid-month, use_rate:
        Rate present & Rate / (Cum x dim/day) in 0.6–1.6  → (rate, "m-rate")
        else                                             → (projected, "projected")
    Mid-month, not use_rate (the TOTAL rows)              → (projected, "projected")

    Returns (value, basis). `value` is still in Tonnes."""
    mid = _is_mid_month(report_day, days_in_month)
    if not mid or cum is None:
        return cum, "cum"

    projected = cum * days_in_month / report_day
    if use_rate and rate not in (None, 0):
        ratio = rate / projected if projected else None
        if ratio is not None and 0.6 <= ratio <= 1.6:
            return rate, "m-rate"
        print(f"[SSP PDF] {label}: Rate {rate} is "
              f"{(ratio * 100) if ratio else float('nan'):.0f}% of the expected "
              f"{projected:.0f} (Cum {cum}, day {report_day}/{days_in_month}) — "
              f"using the projected figure instead.", flush=True, file=sys.stderr)
    return projected, "projected"


def _fmt_month(ym: str) -> str:
    try:
        y, mo = ym[:4], int(ym[5:7])
        return f"{_MONTHS[mo - 1].title()} {y}"
    except Exception:
        return ym


def _assert_month_match(detected, user_month: str) -> None:
    if detected and detected != user_month:
        raise ValueError(
            f"Month mismatch: this SSP DPR's own header shows "
            f"{_fmt_month(detected)} (the report date is that month's last "
            f"day), but you selected {_fmt_month(user_month)}. Please "
            f"select '{_fmt_month(detected)}' in the month picker, or "
            f"upload the report for {_fmt_month(user_month)}."
        )


_SECTION_ANCHORS = [
    ("unitwise",   re.compile(r'^1\.0\s+UNITWISE', re.I)),
    ("saleable",   re.compile(r'^2\.0\s+SALEABLE', re.I)),
    ("despatches", re.compile(r'^3\.0\s+DESPATCHES', re.I)),
    ("sales",      re.compile(r'^4\.0\s+SALES', re.I)),
    ("raw_material", re.compile(r'^5\.0\s+RAW', re.I)),
]


def _load_pdf_text(file_path: str):
    import pdfplumber
    try:
        with pdfplumber.open(file_path) as pdf:
            n = len(pdf.pages)
            parts = [pg.extract_text() or "" for pg in pdf.pages]
            return "\n".join(parts), n
    except Exception as exc:
        raise ValueError(f"Cannot open PDF '{os.path.basename(file_path)}': {exc}") from exc


def _nums_from_line(line: str):
    """All positive floats on the line.

    Unlike the other plants' PDF extractors, this does NOT exclude
    year-like values (2000-2099) — SSP's DPR rows are matched and read
    per-section (never against the report's own date header line), and
    tonnage/stock figures for this plant routinely fall in that range
    (e.g. a 'Stock As on 1st' of 2017 t), so filtering them out would
    silently drop a real column value instead of a stray year token.
    """
    result = []
    for tok in re.findall(r'\d[\d,]*(?:\.\d+)?', line):
        try:
            v = float(tok.replace(',', ''))
        except ValueError:
            continue
        result.append(v)
    return result


def _split_sections(lines):
    """Split report lines into named sections by their '#.0 LABEL' anchors."""
    sections = {}
    cur_key, cur_lines = None, []
    for ln in lines:
        matched = None
        for key, pat in _SECTION_ANCHORS:
            if pat.match(ln.strip()):
                matched = key
                break
        if matched:
            if cur_key:
                sections[cur_key] = cur_lines
            cur_key, cur_lines = matched, []
            continue
        if cur_key:
            cur_lines.append(ln)
    if cur_key:
        sections[cur_key] = cur_lines
    return sections


def _find_row(lines, predicate):
    """First line in `lines` matching predicate(upper-stripped text) →
    (nums, label) or (None, None) if not found."""
    for ln in lines:
        if predicate(ln.strip().upper()):
            return _nums_from_line(ln), ln.strip()[:80]
    return None, None


def _row(item_name, val_t, cell_desc, pdf_label, basis="cum"):
    """Build a standard production_row dict. val_t is in Tonnes."""
    if val_t is None:
        return {
            "item_name": f"(not found) {item_name}",
            "value":     None,
            "unit":      "T",
            "cell":      cell_desc,
            "pdf_label": pdf_label,
            "basis":     basis,
            "status":    "unmapped",
        }
    return {
        "item_name": item_name,
        "value":     round(val_t / 1000.0, 3),
        "unit":      "'000T",
        "cell":      cell_desc,
        "pdf_label": pdf_label,
        "basis":     basis,
        "status":    "ok",
    }


def extract_preview(file_path: str, report_month: str, **_kwargs) -> dict:
    """
    Extract SSP production data from a monthly DPR PDF.

    Returns a dict in the standard extract_preview() format — no DB writes.
    """
    y, m     = int(report_month[:4]), int(report_month[5:7])
    want_mon = _MONTHS[m - 1]
    yy       = str(y)[2:]
    fname    = os.path.basename(file_path)

    print(f"[SSP PDF] extract_preview: file={fname}  month={want_mon}'{yy}",
          flush=True, file=sys.stderr)

    full_text, n_pages = _load_pdf_text(file_path)
    print(f"[SSP PDF] Loaded {n_pages} pages, {len(full_text)} chars", flush=True, file=sys.stderr)

    report_day, days_in_month, detected_month = _detect_date_from_pdf_text(full_text)
    _assert_month_match(detected_month, report_month)

    mid_month = _is_mid_month(report_day, days_in_month)
    is_month_end = (not report_day) or report_day >= (days_in_month or 0)
    if mid_month:
        print(f"[SSP PDF] mid-month report (day {report_day} of {days_in_month}) — "
              f"cumulative items projected x{days_in_month}/{report_day}",
              flush=True, file=sys.stderr)

    def _proj_tag(basis: str) -> str:
        if basis == "m-rate":
            return "Rate col"
        if basis == "projected":
            return f"Cum x{days_in_month}/{report_day}"
        return "Cum Actual"

    lines = full_text.splitlines()
    sections = _split_sections(lines)

    prod_rows = []
    cell_tag  = f"PDF ({n_pages}p) · {want_mon}'{yy}"

    def add_cum(item_name, section_key, predicate, cum_from_end, rate_from_end,
                tag_suffix, use_rate=True):
        """A cumulative production/despatch item: read Cum (cum_from_end) and
        Rate (rate_from_end) counted from the row's last column, then pick the
        full-month value via _pick_month_value. 'On Date Actual' is the only
        column that goes missing on a zero-production day, so counting from the
        end stays correct whether or not it is present."""
        nums, label = _find_row(sections.get(section_key, []), predicate)
        cum = rate = None
        if nums is not None:
            if len(nums) >= abs(cum_from_end):
                cum = nums[cum_from_end]
            if rate_from_end is not None and len(nums) >= abs(rate_from_end):
                rate = nums[rate_from_end]
        if nums is None:
            label = f"({item_name} line not found)"
        val, basis = _pick_month_value(rate, cum, report_day, days_in_month,
                                       use_rate=use_rate, label=item_name)
        prod_rows.append(_row(item_name, val,
                              f"{cell_tag} · {tag_suffix} ({_proj_tag(basis)})",
                              label, basis))
        return val

    def add_stock(item_name, section_key, predicate, col_from_end, tag_suffix):
        """A point-in-time stock column — read as-is, never projected."""
        nums, label = _find_row(sections.get(section_key, []), predicate)
        val = None
        if nums is not None and len(nums) >= abs(col_from_end):
            val = nums[col_from_end]
        if nums is None:
            label = f"({item_name} line not found)"
        prod_rows.append(_row(item_name, val, f"{cell_tag} · {tag_suffix}", label, "stock"))
        return val

    # ── 1.0 UNITWISE PRODUCTION ─────────────────────────────────────────────
    # 6-col layout: [OnDate?, Cum, Target, Rate, StockDate, Stock1st]
    # SMS (SLAB) / HRM carry no stock: [OnDate?, Cum, Target, Rate].
    add_cum("Total Crude Steel", "unitwise", lambda t: t.startswith("SMS") and "SLAB" in t,
            -3, -1, "SMS(SLAB) Cum Actual")
    add_cum("HRM", "unitwise", lambda t: t.startswith("HRM"),
            -5, -3, "HRM Cum Actual")
    add_stock("Input SS Slab Stock", "unitwise",
              lambda t: t.startswith("- STAINLESS") or t.startswith("STAINLESS"),
              -2, "- STAINLESS Stock As on Date")
    add_stock("Input Carbon Slab Stock", "unitwise",
              lambda t: t.startswith("- CARBON") or t.startswith("CARBON"),
              -2, "- CARBON Stock As on Date")

    # ── 2.0 SALEABLE PRODUCTION ─────────────────────────────────────────────
    # 4-col layout: [OnDate?, Cum, Target, Rate]. The TOTAL row's Rate cell
    # omits HRSS, so Saleable/Finished Steel are always projected from Cum.
    sal_val = add_cum("Saleable Steel", "saleable", lambda t: t.startswith("TOTAL"),
                      -3, -1, "SALEABLE PRODUCTION TOTAL Cum Actual", use_rate=False)
    # Finished Steel — same "TOTAL" figure, existing alias of Saleable Steel.
    sal_cell, sal_label, sal_basis = (prod_rows[-1]["cell"], prod_rows[-1]["pdf_label"],
                                      prod_rows[-1]["basis"])
    prod_rows.append(_row("Finished Steel", sal_val, sal_cell, sal_label, sal_basis))

    add_cum("Carbon Steel Production", "saleable", lambda t: t.startswith("HRCS"),
            -3, -1, "SALEABLE PRODUCTION HRCS Cum Actual")
    add_cum("NO1 Production", "saleable", lambda t: t.startswith("NO1"),
            -3, -1, "SALEABLE PRODUCTION NO1 Cum Actual")
    add_cum("CRSS Production", "saleable", lambda t: t.startswith("CRSS"),
            -3, -1, "SALEABLE PRODUCTION CRSS Cum Actual")
    # HRSS carries no Monthly Target / Stock — [OnDate, Cum] at month-end, or
    # [OnDate, Cum, Rate] mid-month (Rate is usually 0 here → projected from Cum).
    hrss_nums, hrss_label = _find_row(sections.get("saleable", []), lambda t: t.startswith("HRSS"))
    hrss_cum = hrss_rate = None
    if hrss_nums:
        hrss_cum = hrss_nums[1] if len(hrss_nums) >= 2 else hrss_nums[0]
        hrss_rate = hrss_nums[2] if len(hrss_nums) >= 3 else None
    hrss_val, hrss_basis = _pick_month_value(hrss_rate, hrss_cum, report_day, days_in_month,
                                             label="HRSS Production")
    prod_rows.append(_row("HRSS Production", hrss_val,
                          f"{cell_tag} · SALEABLE PRODUCTION HRSS Cum Actual ({_proj_tag(hrss_basis)})",
                          hrss_label or "(HRSS line not found)", hrss_basis))

    # ── 3.0 DESPATCHES ───────────────────────────────────────────────────────
    # 6-col layout: [OnDate?, Cum, Target, Rate, StockDate, Stock1st]
    add_cum("Finished Carbon Steel Despatch", "despatches", lambda t: t.startswith("HRCS"),
            -5, -3, "DESPATCHES HRCS Cum Actual")
    add_cum("Total Saleable Steel Despatch", "despatches", lambda t: t.startswith("TOTAL"),
            -5, -3, "DESPATCHES TOTAL Cum Actual", use_rate=False)
    finished_carbon_val = add_stock("Finished Carbon Steel Stock", "despatches",
                                    lambda t: t.startswith("HRCS"), -2,
                                    "DESPATCHES HRCS Stock As on Date")
    finished_total_val = add_stock("Finished Total Steel Stock", "despatches",
                                   lambda t: t.startswith("TOTAL"), -2,
                                   "DESPATCHES TOTAL Stock As on Date")

    # Finished Stainless Steel Stock = Finished Total Steel Stock - Finished Carbon Steel Stock
    if finished_total_val is not None and finished_carbon_val is not None:
        finished_ss_val = finished_total_val - finished_carbon_val
        prod_rows.append(_row("Finished Stainless Steel Stock", finished_ss_val,
                              f"{cell_tag} · Finished Total Steel Stock - Finished Carbon Steel Stock",
                              "(computed)", "stock"))
    else:
        prod_rows.append(_row("Finished Stainless Steel Stock", None,
                              f"{cell_tag} · Finished Total Steel Stock - Finished Carbon Steel Stock",
                              "(Finished Total Steel Stock or Finished Carbon Steel Stock missing)", "stock"))

    ok = sum(1 for r in prod_rows if r["status"] == "ok")
    print(f"[SSP PDF] {ok}/{len(prod_rows)} rows ok", flush=True, file=sys.stderr)

    if ok == 0:
        raise ValueError(
            "No values extracted. Verify this is an SSP DPR PDF with "
            "'SMS (SLAB)', 'HRM' and 'SALEABLE PRODUCTION ... TOTAL' rows."
        )

    return {
        "plant":              PLANT,
        "month":              report_month,
        "detected_month":     detected_month,
        "source_type":        "SSP Daily Production Report (DPR)",
        "sheets":             f"PDF ({n_pages} page) — SSP DPR",
        "workbook_sheets":    [f"PDF ({n_pages} pages)"],
        "report_type":        "DPR",
        "production_rows":    prod_rows,
        "special_steel_rows": [],
        "special_steel_note": "",
        "techno_rows":        [],
        "techno_param_rows":  [],
        "morning_report_day":    report_day,
        "morning_days_in_month": days_in_month,
        "morning_is_month_end":  is_month_end,
    }
