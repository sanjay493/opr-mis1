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

So each numeric row-tuple (freetime + however many consecutive FY months
are populated, oldest first) gets its wagon-type label from the wagon
column — a text-only label line is attached to the vertically nearest
numeric row, which also reassembles wrapped labels — and is then matched
to rake_detention_master (the row registry) by WAGON TYPE + COMMODITY
(see _match_to_master): wagon type must agree, and among same-type
registry rows the one whose commodity text sits closest to the PDF row
wins. Matching is NOT positional: a report's row set and order can differ
from today's registry (FY 2025-26 reports carry 9 BSP inward rows vs 15
now; ISP lists BCME rows ahead of IISD ones) and a positional zip filed
later rows under the wrong wagon type. A PDF row with no registry match,
or a registry row the PDF lacks, is reported in the preview rather than
silently guessed at — matching this codebase's "stay silent rather than
guess" rule — the actual fix for a real new wagon type is to add it via
the Wagon Types registry first (see /data-entry/rake-detention), then
re-extract.

The column header is found by its row of PLANT + COMMODITY + month
columns (APR'26 ...), not by the first "COMMODITY" on the page — the
report title ("COMMODITY WISE AVERAGE PLANT DETENTION ...") sits above it
— and header words are matched letter-spacing-insensitively: some
reports (Jun/Sep'26) render page 1's header as "W A G O N".

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


def _find_in_row(row, phrase):
    """x0 of the word where `phrase` starts in this row's text, matched
    against the row's words concatenated WITHOUT spaces — so a header the
    source export renders letter-spaced ("W A G O N", "FREE T I M E", seen
    on the Jun/Sep'26 reports' page 1) is found the same as a whole word.
    None if absent."""
    phrase = phrase.upper().replace(" ", "")
    joined, owner = "", []
    for w in row:
        t = w["text"].upper()
        joined += t
        owner.extend([w] * len(t))
    i = joined.find(phrase)
    return owner[i]["x0"] if i >= 0 else None


_MONTH_COL_RE = re.compile(r"^(APR|MAY|JUNE?|JULY?|AUG|SEPT?|OCT|NOV|DEC|JAN|FEB|MAR)'\d\d")


def _header_row_index(rows):
    """Index of the column-header row ("PLANT  COMMODITY  APR'26  MAY'26 ..."),
    within the page's first ~25 rows. Requires a month column token so the
    report TITLE row ("COMMODITY WISE AVERAGE PLANT DETENTION AT STEEL
    PLANTS ..."), which also contains PLANT and COMMODITY and sits above
    the header, isn't mistaken for it — anchoring on the title put the
    Wagon Type cutoff to the right of the wagon labels, dropping every
    label."""
    # The month tokens can sit ~1pt off the PLANT/COMMODITY words' own top,
    # landing in a neighbouring rounded row, so look within a few points.
    for i, (top, row) in enumerate(rows[:25]):
        if _find_in_row(row, "PLANT") is None or _find_in_row(row, "COMMODITY") is None:
            continue
        near = [w for t, r in rows[max(0, i - 3):i + 4] if abs(t - top) <= 3 for w in r]
        if any(_MONTH_COL_RE.match(w["text"].upper()) for w in near):
            return i
    return None


def _wagon_col_threshold(rows):
    """x0 cutoff separating the Commodity column's text from the Wagon
    Type column's — derived per-page from the column header's own
    COMMODITY and WAGON anchors (this report's page 2 starts ~110pt further
    left than page 1's, so a fixed cutoff across pages would misfile
    columns). WAGON sits on its own line a few points above/below the
    PLANT/COMMODITY header line. Returns None if this page has no such
    header (i.e. not a plant-detail page — the Improvement Summary / Trend
    pages have a different table)."""
    hi = _header_row_index(rows)
    if hi is None:
        return None
    commodity_x = _find_in_row(rows[hi][1], "COMMODITY")
    wagon_x = next((x for _, row in rows[max(0, hi - 3):hi + 4]
                    for x in [_find_in_row(row, "WAGON")] if x is not None), None)
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
    string. A wagon-zone text line with no numbers of its own (a label
    rendered a line off, or one half of a wrapped label) is attached to the
    vertically NEAREST numeric row of the same section, ties going to the
    row below — a wrapped label is printed around its own numbers ("BOXN
    (NEW" / numbers / "PLANT) *"), so nearest-row, not previous-row, is
    what reassembles it. Each row's label is its fragments in top order."""
    out = {}
    cur_plant = None
    cur_section = None
    fragments = []  # (plant, section, top, text) text-only wagon-zone lines
    awaiting_total_numbers = None  # section whose "Total X"/"Overall Wagon" label
                                   # appeared with no numbers on its own line yet

    for top, row in rows:
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

        if cur_plant is None:
            continue  # header/cover rows before the first plant block

        total_hit = next((sec for phrase, sec in _SECTION_TOTAL_PHRASES.items()
                           if phrase in joined_upper), None)
        if total_hit:
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
            parts = [(top, " ".join(wagon_zone_text))] if wagon_zone_text else []
            out[cur_plant][cur_section]["rows"].append([parts, nums, top])
        elif wagon_zone_text:
            fragments.append((cur_plant, cur_section, top, " ".join(wagon_zone_text)))

    for plant, section, ftop, text in fragments:
        cands = out[plant][section]["rows"]
        if not cands:
            continue
        best = min(cands, key=lambda r: (abs(r[2] - ftop), r[2] < ftop))
        best[0].append((ftop, text))

    for sections in out.values():
        for blob in sections.values():
            blob["rows"] = [(" ".join(txt for _, txt in sorted(parts)), nums, top)
                            for parts, nums, top in blob["rows"]]
    return out


def _commodity_lines(rows, hi, wagon_threshold):
    """[(top, text), ...] — each line of Commodity-column text on this page
    ("Ind.Coking Coal", "Outward" / "Despatch", "Over all" ...).

    The Commodity column is a merged cell per commodity on some pages and
    one cell per row on others, and its text sits near — not on — the
    rows it labels: vertically centred in a merged cell, and sometimes a
    full line off (BSP's "Boiler Coal" is drawn on the line above its own
    row). So the text is used as positional evidence for matching (see
    _match_to_master), never as a hard per-row key."""
    header = rows[hi][1]
    commodity_x = _find_in_row(header, "COMMODITY")
    plant_x = _find_in_row(header, "PLANT")
    if commodity_x is None or plant_x is None:
        return []
    lo_x = plant_x + (commodity_x - plant_x) * 0.5
    out = []
    for top, row in rows[hi + 1:]:
        words = [w["text"] for w in row
                 if lo_x <= w["x0"] < wagon_threshold and not _NUM_RE.match(w["text"])
                 and w["text"].upper() not in PLANT_TOKENS and w["text"].upper() not in _BANNER_FILLER
                 and w["text"].upper() not in _DIRECTION_TOKENS]
        if words:
            out.append((top, " ".join(words)))
    return out


_NO_TEXT_COST = 60.0   # commodity text not found near the row at all


def _commodity_distance(row_top, commodity, lines):
    """Vertical distance (pt) from a PDF row to the nearest line of text
    belonging to `commodity` (normalized match, allowing a commodity split
    across lines: "Outward" + "Despatch")."""
    key = _norm(commodity)
    if not key:
        return 0.0
    best = None
    for top, text in lines:
        k = _norm(text)
        if k and (k == key or (len(k) >= 4 and (k in key or key in k))):
            d = abs(top - row_top)
            best = d if best is None else min(best, d)
    return _NO_TEXT_COST if best is None else best


def _match_to_master(extracted, sec_master):
    """Match a section's PDF rows to its master registry rows ->
    [(extracted_row, master_row | None)] in PDF order.

    A pair needs the same wagon type (normalized). Among candidates, the
    master row whose COMMODITY text sits closest to the PDF row wins —
    globally, cheapest pair first — with registry order as a tie-break
    (Overall-section rows have no commodity and rely on it). This doesn't
    assume the PDF lists rows in registry order (ISP's report groups its
    BCME rows ahead of the IISD ones; the registry groups by commodity) or
    the same row set (older reports lack wagon types added since, e.g.
    BSP's FY 2025-26 inward table has 9 rows vs 15 now) — a positional zip
    silently filed later rows under the wrong wagon type."""
    cands = []
    for i, (label, _nums, top, lines) in enumerate(extracted):
        w_key = _norm(label)
        for j, mr in enumerate(sec_master):
            if _norm(mr["row_label"]) != w_key:
                continue
            cost = _commodity_distance(top, mr.get("commodity"), lines) + 0.01 * abs(i - j)
            cands.append((cost, i, j))
    cands.sort()
    row_to_master, taken = {}, set()
    for cost, i, j in cands:
        if i in row_to_master or j in taken:
            continue
        row_to_master[i] = j
        taken.add(j)
    return [(row, sec_master[row_to_master[i]] if i in row_to_master else None)
            for i, row in enumerate(extracted)]


def _norm(s):
    """Uppercase letters/digits only — 'Ind. Coking Coal' == 'Ind.Coking Coal',
    'LOHA-BRN' == 'LOHA BRN', 'BOXN (IISD) *' == 'BOXN (IISD)*'."""
    return re.sub(r"[^A-Z0-9]", "", (s or "").upper())


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
                # Each extracted row: (wagon label hint, numbers, its line's
                # top, this page's Commodity-column text lines) — the lines
                # are what _match_to_master measures commodity distance on.
                lines = _commodity_lines(rows, _header_row_index(rows), wagon_threshold)
                for sections in page_blob.values():
                    for blob in sections.values():
                        blob["rows"] = [(h, n, t, lines) for h, n, t in blob["rows"]]
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

            # Match each PDF row to a master row by (commodity, wagon type),
            # not by position: a report's row set differs from today's
            # registry whenever a wagon type is added or dropped (e.g. the
            # FY 2025-26 reports carry 9 BSP inward rows vs 15 now), and a
            # positional zip then silently files every later row under the
            # wrong wagon type. Wagon type alone isn't unique (BOXN appears
            # under most commodities), hence the commodity from the merged
            # Commodity cell. A master row with no commodity (the Overall
            # section) matches on wagon type alone; duplicates of the same
            # key are consumed in registry order.
            pairs = _match_to_master(blob["rows"], sec_master)
            used = {m["id"] for _, m in pairs if m is not None}

            out_rows = []
            for extracted, master in pairs:
                wagon_label, raw_nums, _top, _lines = extracted
                commodity = master.get("commodity") if master else None
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
                        "wagon_type": wagon_label, "commodity": commodity, "freetime_hours": freetime,
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
                    "wagon_type": wagon_label, "commodity": commodity, "freetime_hours": freetime,
                    "monthly": dict(zip(months, monthly_vals)),
                    "matched_master_id": master["id"], "matched_row_label": master["row_label"],
                    "status": "ok",
                })

            # Registry rows this report doesn't carry (e.g. a wagon type
            # added after the report's month): nothing extracted for them.
            for m in sec_master:
                if m["id"] not in used:
                    out_rows.append({
                        "wagon_type": None, "commodity": m.get("commodity"), "freetime_hours": None,
                        "monthly": {}, "matched_master_id": m["id"],
                        "matched_row_label": m["row_label"], "status": "missing_in_pdf",
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
