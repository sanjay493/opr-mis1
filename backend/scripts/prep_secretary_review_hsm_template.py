"""One-off: turn the redesigned "Operation Slides for HSM Review Oct26" deck
(12 slides: cover, SAIL table + highlights, plant-wise tables, delays, SAIL
and plant techno charts) into the Secretary Review page's second layout
(secretary_review_templates/secretary_review_hsm.pptx).

- names every filled table/chart (see secretary_review_layout.hsm_required_shape_names)
- puts {MON}/{YTD}/{CPLY} placeholders in titles and headers, APP in the plan headers
- slide 2: keeps one card/headline/tile/figure/note of each highlight card as
  prototypes (hl_*_a navy, hl_*_b light) and drops the rest
- delay tables: keeps the first row and one continuation row as prototypes

Slide indices are used only here. Re-run only to rebuild the template:
    venv/Scripts/python.exe scripts/prep_secretary_review_hsm_template.py "<reference.pptx>"
"""

import copy
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pptx import Presentation  # noqa: E402
from pptx.dml.color import RGBColor  # noqa: E402
from pptx.oxml.ns import qn  # noqa: E402

import secretary_review_layout as L  # noqa: E402
import secretary_review_pptx as sp  # noqa: E402

TITLES = {
    2: "SAIL Performance : {MON} & {YTD}",
    3: "SAIL Plant-wise Performance : {MON} & {YTD}",
    4: "Major Breakdowns/Delays  during  {MON} & {YTD}",
    5: "SAIL Plant-wise Performance : {MON} & {YTD}",
    6: "Major Breakdowns/Delays  during  {MON} & {YTD}",
    **{7 + i: f"{s} Techno  Performance ({{YTD}})" for i, s in enumerate(L.SCOPES)},
}
TABLES = {2: "tbl_sail", 3: "tbl_plants_hm_cs", 4: "tbl_delay_hmcs", 5: "tbl_plants_ss_fs", 6: "tbl_delay_fs"}
CHART_KEY = {"fuel rate": "fuel", "coke rate": "coke", "pci rate": "pci", "bf productivity": "bfprod",
             "sp. energy": "energy"}
HEADER_TEXT = {"oct'26": "{MON}", "apr-oct'26": "{YTD}", "mou": "APP"}


def _set(cell_or_tf, text):
    tf = getattr(cell_or_tf, "text_frame", cell_or_tf)
    sp.set_text_lines(tf, text.split("\n"))


def _perf_table(table):
    """Header rows have 'Plant' or nothing in the first column."""
    for row in table.rows:
        header = sp.norm(row.cells[0].text) in ("", "plant")
        for c, cell in enumerate(row.cells):
            t = cell.text.strip()
            if header:
                if sp.norm(t) in HEADER_TEXT:
                    _set(cell, HEADER_TEXT[sp.norm(t)])
                elif "Oct’25" in t:
                    _set(cell, t.replace("Oct’25", "{CPLY}"))
            elif c > 0 and t:
                _set(cell, "")


def _highlights(slide):
    by = {}
    for sh in list(slide.shapes):
        by.setdefault(sh.name, []).append(sh)
    rename = {"Oct'26 card": "hl_card_a", "Oct'26 headline": "hl_head_a",
              "H-1 card": "hl_card_b", "H-1 headline": "hl_head_b", "H-1 reductions": "hl_note_b"}
    for old, new in rename.items():
        by[old][0].name = new
    card_a = by["Oct'26 card"][0]
    for kind in ("tile", "figures"):
        shapes = [sh for name, lst in by.items() if name.endswith(" " + kind) for sh in lst]
        a = sorted((s for s in shapes if s.left < card_a.left + card_a.width), key=lambda s: (s.top, s.left))
        b = sorted((s for s in shapes if s.left >= card_a.left + card_a.width), key=lambda s: (s.top, s.left))
        suffix = "tile" if kind == "tile" else "fig"
        a[0].name, b[0].name = f"hl_{suffix}_a", f"hl_{suffix}_b"
        for s in a[1:] + b[1:]:
            sp.remove_shape(s)
    # Card a had no note: a copy of b's in the headline's white.
    note_b = by["H-1 reductions"][0]
    el = copy.deepcopy(note_b._element)
    note_b._element.addnext(el)
    note_a = [s for s in slide.shapes if s._element is el][0]
    note_a.name = "hl_note_a"
    note_a.left = by["Oct'26 headline"][0].left
    white = by["Oct'26 headline"][0].text_frame.paragraphs[1].runs[0].font.color.rgb
    for p in note_a.text_frame.paragraphs:
        for r in p.runs:
            r.font.color.rgb = RGBColor.from_string(str(white))
    for name in ("hl_head_a", "hl_head_b"):
        sh = [s for s in slide.shapes if s.name == name][0]
        paras = sh.text_frame.paragraphs
        paras[0].runs[0].text, paras[1].runs[0].text = "{PERIOD} Highlights", "SAIL achieved:-"
        for p in paras:
            for r in p.runs[1:]:
                r.text = ""


def _delays(table):
    """Two prototype rows; the text cell's paragraph keeps the deck's two
    run styles: the unit ('BF-2:', bold amber) and the rest."""
    proto = copy.deepcopy(table.cell(0, 2).text_frame.paragraphs[0]._p)
    runs = proto.findall(qn("a:r"))
    for r in runs[2:]:
        proto.remove(r)
    runs[0].find(qn("a:t")).text, runs[1].find(qn("a:t")).text = "Unit:", " delay text"
    tbl = table._tbl
    for tr in tbl.tr_lst[2:]:
        tbl.remove(tr)
    table.cell(0, 0)._tc.set("rowSpan", "2")
    for r in range(2):
        _set(table.cell(r, 1), "XXX :")
        tx = table.cell(r, 2).text_frame._txBody
        for p in tx.findall(qn("a:p")):
            tx.remove(p)
        tx.append(copy.deepcopy(proto))


def main(src):
    prs = Presentation(src)
    assert len(prs.slides) == 12, len(prs.slides)
    for n, slide in enumerate(prs.slides, 1):
        if n in TITLES:
            _set(slide.shapes.title, TITLES[n])
        if n in TABLES:
            frame = [sh for sh in slide.shapes if getattr(sh, "has_table", False) and sh.has_table][0]
            frame.name = TABLES[n]
            if n in (4, 6):
                _delays(frame.table)
            else:
                _perf_table(frame.table)
        if n >= 7:
            scope = L.SCOPES[n - 7]
            for sh in slide.shapes:
                if getattr(sh, "has_chart", False) and sh.has_chart:
                    title = sp.norm(sh.chart.chart_title.text_frame.text)
                    key = next(v for k, v in CHART_KEY.items() if title.startswith(k))
                    sh.name = f"ch_{scope}_{key}"
    _highlights(prs.slides[1])
    missing = L.hsm_required_shape_names() - set(sp.named_shapes(prs))
    assert not missing, missing
    prs.save(str(L.HSM_TEMPLATE_PATH))
    print("wrote", L.HSM_TEMPLATE_PATH)


if __name__ == "__main__":
    main(sys.argv[1])
