"""
PDF extractor for "Details of Rakes Detention Plant Wise" — SAIL Rail
Movement Cell's "Average Plant Detention Report" (Report_format's sample:
"Average Plant Detention Report for the period_(01-08-2026 to
31-08-2026).pdf"). Gives the /data-entry/rake-detention page a second,
faster way to fill in a month's figures alongside the always-available
manual grid — upload the same monthly PDF the Rail Movement Cell already
emails out, review the extracted preview, then Save through the existing
grid/summary endpoints (this module never writes to the DB itself).

Why this can't be a generic value-scrape (unlike techno_project's Excel
extractors, whose sheets have one fixed cell per figure): the source
table's Commodity column is a vertically-merged cell spanning several
wagon-type rows, and pdfplumber's text/word extraction places that merged
cell's text at its own vertically-CENTERED position — which does not
align with any individual wagon-type row's own line. Worse, on this
particular PDF a wagon-type label and its own row of monthly figures are
occasionally rendered one visual line apart (a rendering quirk of the
source export, confirmed on real files — e.g. IISCO's "BOXN (IISD) *"
label sits one line above its own numbers). Exact line-position matching
between label and values is therefore unreliable.

The approach instead never tries to recover the Commodity grouping from
the PDF at all — rake_detention_master already IS that row registry,
in the same top-to-bottom order this report has always been transcribed
in. Per (plant, section), this module extracts two ordered sequences
independently — wagon-type labels (by x-position column, walking the
page top-to-bottom) and numeric row-tuples (freetime + however many
consecutive FY months are populated, oldest first) — then zips them
positionally: the Nth label pairs with the Nth tuple. A count mismatch
against that section's existing master rows (a wagon type in the PDF the
registry doesn't have yet, or vice versa) is reported as a clear
mismatch in the preview rather than silently guessed at — matching this
codebase's "stay silent rather than guess" rule (see e.g.
coal_omi_extractor.py's ValueError-on-mismatch checks) — the actual fix
for a real new wagon type is to add it via the Wagon Types registry
first (see /data-entry/rake-detention), then re-extract.

Column x-positions are computed fresh per page from that page's own
header row ("COMMODITY", "WAGON"/"TYPE", "FREETIME"), not hardcoded —
confirmed necessary: this report's own page-2 table starts ~110pt
further left than page 1's (a page-per-plant-group layout quirk of the
source export), so a single hardcoded x-range would silently misfile
page 2's columns.

Also extracts page 3's "Improvement in Average Detention per Wagon in
Hrs" table (3 period-triples x 6 plants) the same way the rest of this
report's summary block already works — matched by its own period-row
label text (Aug'26 / Apr'26-Aug'26 / Apr'25-Mar'26 pattern, generic to
any month) rather than position, since that table's layout is simple and
regular.

Run as a script to dry-extract one file without touching the DB:
    python page_rake_detention_pdf_extractor.py "path\\to\\report.pdf" 2026-08
"""
import re
import sys

PLANT_TOKENS = {
    "BHILAI": "BSP", "DURGAPUR": "DSP", "ROURKELA": "RSP",
    "BOKARO": "BSL", "IISCO": "ISP",
}
_BANNER_FILLER = {"STEEL", "PLANT", "PTO"}  # decorative vertical banner words sharing the plant-name
                                            # column, plus a stray "PTO" (Please Turn Over) page-break
                                            # artifact seen trailing page 1's last section on this PDF
_SECTION_TOTAL_PHRASES = {
    "TOTAL INWARD": "INWARD", "TOTAL OUTWARD": "OUTWARD", "OVERALL WAGON": "OVERALL",
}
_DIRECTION_TOKENS = {"L", "E", "-"}
_NUM_RE = re.compile(r'^-?\d+(\.\d+)?$')
_MON_ABBR = ["", "Jan", "Feb", "Mar", "Apr", "May", "Jun",
             "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def _fy_months_from(report_month: str, count: int) -> list:
    """First `count` FY months starting from April of report_month's own
    FY — e.g. report_month="2026-08", count=5 -> Apr..Aug'26. Matches
    page_rake_detention.py's own _fy_months/CUR_FY_MONTHS convention (this
    report's populated columns always run contiguously from April)."""
    y, m = int(report_month[:4]), int(report_month[5:7])
    fy_start_year = y if m >= 4 else y - 1
    out = []
    yy, mm = fy_start_year, 4
    for _ in range(count):
        out.append(f"{yy}-{mm:02d}")
        mm += 1
        if mm == 13:
            mm, yy = 1, yy + 1
    return out


def _num(tok):
    try:
        return float(tok)
    except (TypeError, ValueError):
        return None


def _page_words_by_top(page):
    by_top = {}
    for w in page.extract_words():
        by_top.setdefault(round(w["top"]), []).append(w)
    return [(top, sorted(by_top[top], key=lambda w: w["x0"])) for top in sorted(by_top.keys())]


def _header_anchor_x(rows, *phrases):
    """First word matching any of `phrases` (case-insensitive, exact) —> its
    x0, scanning only the first ~15 rows (the header block always sits at
    the top of a plant-detail page)."""
    wanted = {p.upper() for p in phrases}
    for _, row in rows[:15]:
        for w in row:
            if w["text"].upper() in wanted:
                return w["x0"]
    return None


def _wagon_col_threshold(rows):
    """x0 cutoff separating the Commodity column's text from the Wagon
    Type column's — derived per-page from the header row's own COMMODITY
    and WAGON anchors (this report's page 2 starts ~110pt further left
    than page 1's, so a fixed cutoff across pages would misfile columns).
    Returns None if this page has no such header (i.e. not a plant-detail
    page — the Improvement Summary / Trend pages have a different table)."""
    commodity_x = _header_anchor_x(rows, "COMMODITY")
    wagon_x = _header_anchor_x(rows, "WAGON")
    if commodity_x is None or wagon_x is None:
        return None
    return commodity_x + (wagon_x - commodity_x) * 0.6


def _extract_plant_page(rows, wagon_threshold: float):
    """-> {plant_code: {section: {"rows": [(pdf_label_hint, [raw_nums]), ...],
                                    "total": [monthly_vals] | None}}}
    for every plant block found on this page. `raw_nums` is intentionally
    NOT split into (freetime, monthly) here — some rows have a genuinely
    blank Freetime cell in the source (seen on IISCO's Overall section:
    "BFNS 0.0 0.0 23.0 18.1 23.2" — 5 numbers, no freetime, not 6), so
    whether the first number is freetime or already April's own value
    can't be decided from count alone. extract_rake_detention_pdf makes
    that call once it has the matching master row's own freetime_hours
    (None there means: treat every number here as a monthly value).

    pdf_label_hint is best-effort only (see module docstring — this
    report occasionally renders a wagon-type label one visual line away
    from its own numbers, or wraps a long label across lines with the
    trailing fragment appearing AFTER the numbers row, e.g. IISCO's
    "BOXN (NEW" / <numbers> / "PLANT) *"). It's never used for matching —
    only rake_detention_master's own row_label is authoritative, matched
    purely by position (see extract_rake_detention_pdf) — so a slightly
    garbled hint here (picking up a neighboring row's fragment) doesn't
    affect which master row a value lands on, only a cosmetic display
    string. Any non-numeric wagon-zone text seen since the previous
    numeric tuple is attached to the NEXT tuple; unclaimed trailing text
    at the very end of a section (e.g. a wrapped continuation appearing
    after the last row's own numbers) is instead appended to the PREVIOUS
    tuple's hint, since that's the far more common real shape."""
    out = {}
    cur_plant = None
    cur_section = None
    pending_prefix = []  # wagon-zone fragments seen since the last tuple
    awaiting_total_numbers = None  # section whose "Total X"/"Overall Wagon" label
                                   # appeared with no numbers on its own line yet

    for _, row in rows:
        texts_upper = [w["text"].upper() for w in row]
        joined_upper = " ".join(texts_upper)

        # Page footer ("NOTE : UNDER ENGINE ON LOAD..." / "RAIL MOVEMENT
        # CELL, L&I DEPARTMENT," / "KOLKATA") — an unambiguous hard stop.
        # Its own numbers (freetime footnote values) would otherwise be
        # swept into whichever plant/section was still open, corrupting
        # that section's positional zip against the master registry.
        if joined_upper.startswith("NOTE") or "RAIL MOVEMENT CELL" in joined_upper:
            cur_plant = None
            continue

        plant_hit = next((PLANT_TOKENS[t] for t in texts_upper if t in PLANT_TOKENS), None)
        if plant_hit:
            cur_plant, cur_section = plant_hit, "INWARD"
            out[cur_plant] = {s: {"rows": [], "total": None} for s in ("INWARD", "OUTWARD", "OVERALL")}
            pending_prefix.clear()

        if cur_plant is None:
            continue  # header/cover rows before the first plant block

        total_hit = next((sec for phrase, sec in _SECTION_TOTAL_PHRASES.items()
                           if phrase in joined_upper), None)
        if total_hit:
            pending_prefix.clear()
            nums = [_num(w["text"]) for w in row if _NUM_RE.match(w["text"])]
            nums = [n for n in nums if n is not None]
            # This report's own total rows have no freetime figure (blank
            # cell in that column) — every number present is a monthly
            # value already, oldest-first. Usually shares its own line
            # with the label ("OVERALL WAGON 7.4 7.4 ..."), but sometimes
            # (confirmed on this exact PDF, inconsistently across plants)
            # the label and its numbers render one line apart, same
            # quirk as ordinary wagon-type rows — awaiting_total_numbers
            # catches that case on whichever later row actually has the
            # numbers, rather than letting them fall through and get
            # misread as a brand new ordinary row.
            if nums:
                out[cur_plant][total_hit]["total"] = nums
                awaiting_total_numbers = None
            else:
                awaiting_total_numbers = total_hit
            cur_section = {"INWARD": "OUTWARD", "OUTWARD": "OVERALL", "OVERALL": "OVERALL"}[total_hit]
            continue

        # Direction marker row ("L - E" / "E - L", split across 2-3
        # single-char tokens) — carries no other data, skip entirely.
        if texts_upper and all(t in _DIRECTION_TOKENS for t in texts_upper):
            continue

        wagon_zone_text = [w["text"] for w in row
                            if w["x0"] >= wagon_threshold and w["text"].upper() not in _BANNER_FILLER
                            and not _NUM_RE.match(w["text"]) and w["text"].upper() not in _DIRECTION_TOKENS]
        nums = [_num(w["text"]) for w in row if _NUM_RE.match(w["text"])]
        nums = [n for n in nums if n is not None]

        if awaiting_total_numbers and not wagon_zone_text and nums:
            out[cur_plant][awaiting_total_numbers]["total"] = nums
            awaiting_total_numbers = None
            continue

        if len(nums) >= 2:
            hint = " ".join(pending_prefix + wagon_zone_text)
            pending_prefix.clear()
            out[cur_plant][cur_section]["rows"].append((hint, nums))
        elif wagon_zone_text:
            if out[cur_plant][cur_section]["rows"]:
                # No numbers on this row — most often a wrapped label
                # fragment trailing its own already-emitted row (see
                # docstring), so attach it there rather than to whatever
                # row comes next.
                prev_hint, prev_nums = out[cur_plant][cur_section]["rows"][-1]
                out[cur_plant][cur_section]["rows"][-1] = (
                    (prev_hint + " " + " ".join(wagon_zone_text)).strip(), prev_nums,
                )
            else:
                pending_prefix.extend(wagon_zone_text)

    return out


def _merge_plant_dicts(a: dict, b: dict) -> dict:
    for plant, sections in b.items():
        if plant not in a:
            a[plant] = sections
            continue
        for sec, blob in sections.items():
            a[plant][sec]["rows"].extend(blob["rows"])
            if blob["total"] is not None:
                a[plant][sec]["total"] = blob["total"]
    return a


_PCT_RE = re.compile(r'^-?\d+(\.\d+)?%$')
_SUMMARY_PLANT_COUNT = 6  # BSP/DSP/RSP/BSL/ISP/SAIL, in PERIOD_ROWS's own fixed order


def _extract_summary_page(rows) -> list:
    """Page 3 — "Improvement in Average Detention per Wagon in Hrs": 9
    period rows (3 This-Year/Last-Year/Changes-CPLY triples) x plant
    columns. Matched purely by POSITION against PERIOD_ROWS's own fixed
    order (see extract_rake_detention_pdf), not by reconstructing each
    row's own label — this table's period labels are inconsistently
    tokenized in the source (e.g. "APR'26-AUG'26" as one token,
    "APR'25-" + "AUG'25" as two, "APR'25" + "-" + "MAR'26" as three) and,
    for the very last This-Year/Last-Year pair, the label even renders
    AFTER its own numbers rather than before — the same "don't trust
    label/number line alignment" situation as the plant-detail tables.
    Only a row's OWN 6 numbers are extracted; single-digit footnote
    markers ("1"/"2"/"3" printed beside the CPLY rows) are naturally
    excluded by requiring exactly 6."""
    out = []
    for _, row in rows:
        nums = [w["text"] for w in row if _NUM_RE.match(w["text"]) or _PCT_RE.match(w["text"])]
        if len(nums) != _SUMMARY_PLANT_COUNT:
            continue
        out.append([_num(t.rstrip("%")) for t in nums])
    return out


def extract_rake_detention_pdf(file_path: str, report_month: str) -> dict:
    """Main entry point — see module docstring. Returns a preview dict:
    {"detected_period": "...", "plants": {plant_code: {section: {
        "rows": [{"wagon_type", "freetime_hours", "monthly", "matched_master_id",
                   "matched_row_label", "status"}, ...],
        "total": {"monthly": {...}, "matched_master_id", "matched_row_label", "status"} | None,
     }}}, "summary": {period_row_code: {plant: value}}, "warnings": [...]}
    Never writes to the DB — purely extraction + best-effort matching
    against the current rake_detention_master registry (import deferred
    to keep this module import-safe / independently testable without a
    live DB)."""
    import pdfplumber
    import db

    warnings = []
    plant_blob = {}
    summary_rows = []

    with pdfplumber.open(file_path) as pdf:
        for page in pdf.pages:
            rows = _page_words_by_top(page)
            wagon_threshold = _wagon_col_threshold(rows)
            if wagon_threshold is not None:
                page_blob = _extract_plant_page(rows, wagon_threshold)
                plant_blob = _merge_plant_dicts(plant_blob, page_blob)
                continue
            # No plant-detail header on this page. Only the page titled
            # "IMPROVEMENT IN AVERAGE DETENTION..." holds the Improvement
            # Summary table — the OTHER non-detail page (the "AVERAGE
            # DETENTION PER WAGONS IN HOURS" multi-year trend table) can
            # incidentally also produce some 6-number rows (a plant's
            # still-in-progress current-FY row: 5 populated months + its
            # own Apr-Mar average column = 6 cells), which would otherwise
            # get misread as summary rows.
            if any(w["text"].upper() == "IMPROVEMENT" for _, row in rows for w in row):
                summary_rows.extend(_extract_summary_page(rows))

    if not plant_blob:
        raise ValueError(
            "No recognizable plant-detail table found in this PDF — expected the "
            "\"Average Plant Detention Report\" layout (PLANT / COMMODITY / WAGON TYPE / "
            "FREETIME columns)."
        )

    months = _fy_months_from(report_month, 12)  # capped to however many each row actually has

    plants_out = {}
    for plant_code, sections in plant_blob.items():
        master_rows = db.get_rake_detention_master(plants=[plant_code])
        sections_out = {}
        for section, blob in sections.items():
            sec_master = [r for r in master_rows if r["section"] == section and not r["is_total"]]
            total_master = next((r for r in master_rows
                                  if r["section"] == section and r["is_total"]), None)

            out_rows = []
            n = max(len(blob["rows"]), len(sec_master))
            for i in range(n):
                extracted = blob["rows"][i] if i < len(blob["rows"]) else None
                master = sec_master[i] if i < len(sec_master) else None
                if extracted is None:
                    out_rows.append({
                        "wagon_type": None, "freetime_hours": None, "monthly": {},
                        "matched_master_id": master["id"] if master else None,
                        "matched_row_label": master["row_label"] if master else None,
                        "status": "missing_in_pdf",
                    })
                    continue
                wagon_label, raw_nums = extracted
                # Whether the row's first number is Freetime or already
                # April's own value depends on the MASTER row's own
                # freetime_hours (None there means this row's Freetime
                # cell is genuinely blank in the source — see
                # _extract_plant_page's docstring); with no master match
                # at all there's no ground truth, so default to the
                # far-more-common freetime-present shape and flag it for
                # manual review either way.
                has_freetime = master is None or master.get("freetime_hours") is not None
                freetime = raw_nums[0] if has_freetime and raw_nums else None
                monthly_vals = raw_nums[1:] if has_freetime else raw_nums
                if master is None:
                    out_rows.append({
                        "wagon_type": wagon_label, "freetime_hours": freetime,
                        "monthly": dict(zip(months, monthly_vals)),
                        "matched_master_id": None, "matched_row_label": None,
                        "status": "new_wagon_type_not_in_registry",
                    })
                    warnings.append(
                        f"{plant_code}/{section}: PDF row \"{wagon_label}\" (freetime {freetime}) has "
                        f"no matching entry in the Wagon Types registry — add it there first "
                        f"(/data-entry/rake-detention) if this is a genuinely new wagon type, "
                        f"then re-extract."
                    )
                    continue
                out_rows.append({
                    "wagon_type": wagon_label, "freetime_hours": freetime,
                    "monthly": dict(zip(months, monthly_vals)),
                    "matched_master_id": master["id"], "matched_row_label": master["row_label"],
                    "status": "ok",
                })

            total_out = None
            if blob["total"] is not None:
                total_out = {
                    "monthly": dict(zip(months, blob["total"])),
                    "matched_master_id": total_master["id"] if total_master else None,
                    "matched_row_label": total_master["row_label"] if total_master else None,
                    "status": "ok" if total_master else "no_total_row_in_registry",
                }

            sections_out[section] = {"rows": out_rows, "total": total_out}
        plants_out[plant_code] = sections_out

    from page_rake_detention import PERIOD_ROWS, SUMMARY_PLANTS

    summary_out = {}
    if len(summary_rows) != len(PERIOD_ROWS):
        warnings.append(
            f"Improvement Summary page: expected {len(PERIOD_ROWS)} period rows, "
            f"found {len(summary_rows)} — summary values not extracted (check the PDF's "
            f"page 3 layout hasn't changed)."
        )
    else:
        for (code, _), values in zip(PERIOD_ROWS, summary_rows):
            summary_out[code] = dict(zip(SUMMARY_PLANTS, values))

    return {
        "detected_period": report_month,
        "plants": plants_out,
        "summary": summary_out,
        "warnings": warnings,
    }


if __name__ == "__main__":
    import json as _json
    path_arg = sys.argv[1]
    month_arg = sys.argv[2] if len(sys.argv) > 2 else "2026-08"
    result = extract_rake_detention_pdf(path_arg, month_arg)
    print(_json.dumps(result, indent=2, default=str))
