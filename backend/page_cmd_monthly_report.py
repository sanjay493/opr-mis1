"""
"SAIL: Monthly Activity Report" for the CMD Office — one page, Word.

Format-matched against the CMD Office reference (Oct'26.docx, reporting
September 2026), copied to cmd_report_templates/cmd_monthly_report_template.docx
and mutated in place (text only), the same way page_do_letter.py fills its
letter template, so fonts, numbering and bullets stay exactly as the reference.

  * Performance of SAIL — Hot Metal / Crude Steel / Saleable Steel / Finished
    Steel for report_month vs the previous month (CPLM) and the same month
    last year (CPLY). SAIL = null-skipped sum of the eight producing units;
    Finished Steel also adds the SAIL-level Conversion figure (the reference
    letter's 1.376 MT for Sep'26 is that "8 Plants + Conv." figure).
  * Significant Events — "SAIL recorded its best-ever <Month> performance for
    following" bullets. best_ever_suggestions() proposes the ones the DB can
    prove: the production items exactly as the PDF report's Page 3 highlights
    (page3_highlights.best_month_records — same figures, same wording), plus
    Iron Ore Production. The page lets the user edit the list and add the
    rest (sales, fuel rate …) before downloading.
  * Areas of Concern — free text from the page ("None" when blank).
"""

import io
import os

import dbengine
import month_utils
from page3_highlights import best_month_records
from page_do_letter import (
    _clone_paragraph_after, _fetch_conversion, _fetch_item_month,
    _remove_paragraph, _set_paragraph_text, _sum_or_none,
)
from constants import FIVE_PLANTS as _5P
from repo import mines as rmines

_TEMPLATE = os.path.join(os.path.dirname(__file__), "cmd_report_templates",
                         "cmd_monthly_report_template.docx")

_MONTH_FULL = ["January", "February", "March", "April", "May", "June", "July",
               "August", "September", "October", "November", "December"]
_MONTH_ABBR = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
               "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

_SAIL_PLANTS = _5P + ["ASP", "SSP", "VISL"]

# (heading label, sentence lead, item_name, add Conversion, unit suffix) —
# unit wording per item exactly as the reference letter has it.
_PERF_ITEMS = [
    ("Hot Metal Production",      "Hot Metal",      "Hot Metal",         False, "Million Tonnes (MT)"),
    ("Crude Steel Production",    "Crude steel",    "Total Crude Steel", False, "Million Tonnes (MT)"),
    ("Saleable Steel Production", "Saleable steel", "Saleable Steel",    False, "Million Tonnes"),
    ("Finished Steel Production", "Finished steel", "Finished Steel",    True,  "Million Tonnes"),
]

# Iron Ore Production's "best-ever <Month>" needs at least this many earlier
# years of the same calendar month — its mine-level history has gaps (none
# for 2008-09, partial mine coverage before 2013).
_MIN_PRIOR_YEARS = 5

# Template paragraph indexes (see the reference document).
_TITLE_IDX = 0
_PERF_HEADER_IDX = 2
_PERF_BODY_IDX = [5, 8, 11, 14]
_EVENTS_HEADER_IDX = 17
_BEST_LEAD_IDX = 18
_BEST_BULLET_IDX = 19
_N_TEMPLATE_BULLETS = 4
_CONCERN_IDX = 24


def _full(ym: str) -> str:
    return f"{_MONTH_FULL[int(ym[5:7]) - 1]} {ym[:4]}"


def _prev_month(ym: str) -> str:
    y, m = int(ym[:4]), int(ym[5:7])
    return f"{y - 1}-12" if m == 1 else f"{y}-{m - 1:02d}"


def _pct(cur_v, base):
    if cur_v is None or base is None or base == 0:
        return None
    return (cur_v - base) / base * 100


def _sail_total(cur, item, month, add_conv):
    v = _sum_or_none(_fetch_item_month(cur, item, month, _SAIL_PLANTS), _SAIL_PLANTS)
    if add_conv:
        c = _fetch_conversion(cur, month)
        if c is not None:
            v = (v or 0.0) + c
    return v


def _comparison(pct, label, tag):
    if pct is None:
        return None
    r = round(abs(pct), 1)
    if r == 0:
        return f"at par with {label} ({tag})"
    return f"{r:.1f}% {'higher' if pct > 0 else 'lower'} than {label} ({tag})"


def _perf_sentence(lead, unit, month, value, cplm, cply):
    if value is None:
        return f"{lead} production data for {_full(month)} is not available."
    text = f"{lead} production during {_full(month)} is {value / 1000.0:.3f} {unit}."
    parts = [p for p in (
        _comparison(_pct(value, cplm), _full(_prev_month(month)), "CPLM"),
        _comparison(_pct(value, cply), _full(month_utils.get_cply_month(month)), "CPLY"),
    ) if p]
    if parts:
        text += " This is " + " and ".join(parts) + "."
    return text


def _iron_ore_line(month: str):
    """'Iron Ore Production :: X MT (Previous best Y MT in Mon'YY)' when
    month beats every earlier year's same calendar month (at least
    _MIN_PRIOR_YEARS of them), else None. JGoM + OGoM + CGoM, same rollup
    as the Mines pages; '000 T."""
    same_months = [f"{y}{month[4:]}" for y in range(2000, int(month[:4]) + 1)]
    rollup = rmines.get_iron_ore_group_rollup_monthly(same_months)
    totals = {rm: sum((g.get("actual") or 0) for g in rollup[rm]["iron_ore_prod"].values())
              for rm in same_months}
    v = totals.get(month)
    prior = [(t, rm) for rm, t in totals.items() if rm < month and t]
    if not v or len(prior) < _MIN_PRIOR_YEARS:
        return None
    best, best_m = max(prior)
    if v <= best:
        return None
    return (f"Iron Ore Production :: {v / 1000.0:.3f} MT "
            f"(Previous best {best / 1000.0:.3f} MT in {_MONTH_ABBR[int(best_m[5:7]) - 1]}'{best_m[2:4]})")


def best_ever_suggestions(month: str) -> list:
    out = [r["line"] for r in best_month_records(month)]
    iron = _iron_ore_line(month)
    if iron:
        out.append(iron)
    return out


def generate_cmd_report_data(month: str) -> dict:
    prev_m, cply_m = _prev_month(month), month_utils.get_cply_month(month)
    conn = dbengine.connect()
    cur = conn.cursor()
    try:
        items = []
        for label, lead, item, add_conv, unit in _PERF_ITEMS:
            v = _sail_total(cur, item, month, add_conv)
            p = _sail_total(cur, item, prev_m, add_conv)
            c = _sail_total(cur, item, cply_m, add_conv)
            items.append({
                "label": label, "value": v, "cplm": p, "cply": c,
                "pct_cplm": _pct(v, p), "pct_cply": _pct(v, c),
                "sentence": _perf_sentence(lead, unit, month, v, p, c),
            })
    finally:
        conn.close()
    best = best_ever_suggestions(month)
    return {
        "month": month, "month_label": _full(month),
        "cplm_label": _full(prev_m), "cply_label": _full(cply_m),
        "items": items, "best_ever": best,
    }


def build_cmd_report_docx_bytes(month: str, best_ever=None, events=None, concerns=None) -> bytes:
    """best_ever: bullet labels under "SAIL recorded its best-ever <Month>
    performance for following"; None = the DB suggestions. events: extra
    free-text points under section 3. concerns: "Areas of Concern" text."""
    from docx import Document

    data = generate_cmd_report_data(month)
    if best_ever is None:
        best_ever = data["best_ever"]
    best_ever = [s.strip() for s in best_ever if s and s.strip()]
    events = [s.strip() for s in (events or []) if s and s.strip()]
    concerns = (concerns or "").strip() or "None"

    mon_full = _MONTH_FULL[int(month[5:7]) - 1]
    yy = month[2:4]

    doc = Document(_TEMPLATE)
    paras = doc.paragraphs

    _set_paragraph_text(paras[_TITLE_IDX], f"SAIL: Monthly Activity Report for {mon_full}’{month[:4]}")
    _set_paragraph_text(paras[_PERF_HEADER_IDX],
                        f"Performance of SAIL – {_MONTH_ABBR[int(month[5:7]) - 1]} {month[:4]} (Provisional):")
    for idx, it in zip(_PERF_BODY_IDX, data["items"]):
        _set_paragraph_text(paras[idx], it["sentence"])
    _set_paragraph_text(paras[_EVENTS_HEADER_IDX],
                        f"3. Significant Events / Achievements during {mon_full}’{yy}:")

    lead, bullet_ref = paras[_BEST_LEAD_IDX], paras[_BEST_BULLET_IDX]
    extra_bullets = paras[_BEST_BULLET_IDX + 1:_BEST_BULLET_IDX + _N_TEMPLATE_BULLETS]
    concern_p = paras[_CONCERN_IDX]

    _set_paragraph_text(lead, f"SAIL recorded its best-ever {mon_full} performance for following :")
    for p in extra_bullets:
        _remove_paragraph(p)

    anchor = lead
    if best_ever:
        _set_paragraph_text(bullet_ref, best_ever[0])
        anchor = bullet_ref
        for b in best_ever[1:]:
            anchor = _clone_paragraph_after(anchor, b)

    # Other events: same numbered style as the "best-ever" lead line.
    import copy
    from docx.text.paragraph import Paragraph
    for ev in events:
        el = copy.deepcopy(lead._p)
        anchor._p.addnext(el)
        anchor = Paragraph(el, lead._parent)
        _set_paragraph_text(anchor, ev)

    if not best_ever:
        _remove_paragraph(bullet_ref)
        if events:
            _remove_paragraph(lead)
        else:
            _set_paragraph_text(lead, "None")

    runs = concern_p.runs
    runs[1].text = concerns
    for r in runs[2:]:
        r.text = ""

    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()
