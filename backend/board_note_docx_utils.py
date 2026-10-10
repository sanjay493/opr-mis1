"""Generic python-docx paragraph/cell mutation helpers shared by the Board
Note document-generator adapters.

Standalone module: depends only on `python-docx`. No DB access, no imports
from any other board_note module. The four base helpers port the logic
already proven in `page_do_letter.py` (`_set_paragraph_text`,
`_set_cell_text`, `_remove_paragraph`, `_clone_paragraph_after`) under new
public names so all adapters can share one implementation.
"""

import copy

from docx.text.paragraph import Paragraph


def set_para(paragraph, text: str) -> None:
    """Overwrite a paragraph's visible text while keeping its first run's
    formatting (font/bold/size) — python-docx's own `paragraph.text = ...`
    doesn't exist, and Cell.text-style helpers drop formatting, hence this."""
    runs = paragraph.runs
    if not runs:
        paragraph.add_run(text)
        return
    runs[0].text = text
    for r in runs[1:]:
        r.text = ""


def replace_in_para(paragraph, replacements: list) -> None:
    """Apply a sequence of (old, new) substring swaps to a paragraph's text,
    then rewrite it with `set_para` (keeps the first run's formatting)."""
    text = paragraph.text
    for old, new in replacements:
        text = text.replace(old, new)
    set_para(paragraph, text)


def remove_paragraph(paragraph) -> None:
    el = paragraph._p
    el.getparent().remove(el)


def clone_paragraph_after(ref_paragraph, text: str):
    """Deep-copies ref_paragraph's XML (preserving its run/paragraph
    formatting and bullet numbering), inserts the copy immediately after it,
    and sets the copy's text. Used when more lines are needed than the
    template has slots for."""
    new_p_el = copy.deepcopy(ref_paragraph._p)
    ref_paragraph._p.addnext(new_p_el)
    new_paragraph = Paragraph(new_p_el, ref_paragraph._parent)
    set_para(new_paragraph, text)
    return new_paragraph


def set_cell(cell, text: str) -> None:
    """Multi-line remark cells have one <w:p> per original line — clearing
    only paragraphs[0] (often itself blank, the source of a stray leading
    line break) left every later paragraph's old template text in place.
    Extra paragraphs are removed outright (not just blanked) so a short or
    empty remark doesn't leave trailing blank lines from the old text's
    longer line count."""
    paras = cell.paragraphs
    set_para(paras[0], text)
    for p in paras[1:]:
        remove_paragraph(p)


def fill_variable_bullets(slots: list, lines: list) -> None:
    """Match `slots` (existing template paragraphs) to `lines` pairwise.

    - Equal counts: just overwrite each slot's text.
    - More lines than slots: clone extra paragraphs off the last placed
      paragraph, in order, for each remaining line.
    - More slots than lines: remove every unmatched trailing slot.
    """
    n = min(len(slots), len(lines))
    for i in range(n):
        set_para(slots[i], lines[i])

    if len(lines) > len(slots):
        last = slots[-1] if slots else None
        for line in lines[len(slots):]:
            last = clone_paragraph_after(last, line)
    elif len(slots) > len(lines):
        for slot in slots[n:]:
            remove_paragraph(slot)


# --------------------------------------------------------------------------
# Character formatting and the Finished-Steel-vs-MoU charts
# --------------------------------------------------------------------------

_W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"


def clear_strike_and_colour(cell) -> None:
    """Drop strike-through and font colour (the templates mark stale MoU
    figures in red strike-through), keeping bold/size/font."""
    for rpr in cell._tc.iter(f"{{{_W}}}rPr"):
        for tag in ("strike", "dstrike", "color"):
            for el in rpr.findall(f"{{{_W}}}{tag}"):
                rpr.remove(el)


_C = "http://schemas.openxmlformats.org/drawingml/2006/chart"
_A = "http://schemas.openxmlformats.org/drawingml/2006/main"
_FS_SERIES = ("MoU", "Actual", "%ful. MoU", "CPLY", "%Growth")


def fs_charts(document) -> dict:
    """The two Finished Steel MoU bar charts, keyed 'quarter' (title starts
    'Q-') and 'long' (H-1 / 9M / FY), as the docx chart parts."""
    import re
    out = {}
    for part in document.part.package.iter_parts():
        if not re.fullmatch(r"/word/charts/chart\d+\.xml", str(part.partname)):
            continue
        titles = re.findall(r"<a:t>([^<]*)</a:t>", part.blob.decode("utf-8"))
        if titles:
            out["quarter" if titles[0].startswith("Q-") else "long"] = part
    return out


def fill_fs_chart(part, title: str, mou, act, cply) -> None:
    """Rewrite one chart's title, its five one-point series (MoU, Actual,
    %ful. MoU, CPLY, %Growth) and its embedded workbook. None leaves a
    series' point empty. The value axis' fixed maximum is raised to the
    next major unit when a bar would not fit."""
    import io
    import math

    import openpyxl
    from lxml import etree

    pct = round(act / mou * 100) if (act is not None and mou) else None
    gr = round((act - cply) / cply * 100, 1) if (act is not None and cply) else None
    values = dict(zip(_FS_SERIES, (mou, act, pct, cply, gr)))

    root = etree.fromstring(part.blob)
    ns = {"c": _C, "a": _A}
    t = root.find("c:chart/c:title//a:t", ns)
    if t is not None:
        t.text = title
    for ser in root.iterfind(".//c:ser", ns):
        name = ser.find("c:tx//c:v", ns).text
        cache = ser.find("c:val//c:numCache", ns)
        if name not in values or cache is None:
            continue
        for pt in cache.findall("c:pt", ns):
            cache.remove(pt)
        v = values[name]
        if v is not None:
            pt = etree.SubElement(cache, f"{{{_C}}}pt", idx="0")
            etree.SubElement(pt, f"{{{_C}}}v").text = repr(float(v)) if isinstance(v, float) else str(v)
    top = max([v for v in (mou, act, cply) if v is not None], default=None)
    mx, unit = root.find(".//c:valAx/c:scaling/c:max", ns), root.find(".//c:valAx/c:majorUnit", ns)
    if top is not None and mx is not None and top > float(mx.get("val")):
        step = float(unit.get("val")) if unit is not None else float(mx.get("val"))
        mx.set("val", str(int(math.ceil(top / step) * step)))
    part._blob = etree.tostring(root, xml_declaration=True, encoding="UTF-8", standalone=True)

    for rel in part.rels.values():
        if rel.reltype.endswith("/package"):
            wb = openpyxl.load_workbook(io.BytesIO(rel.target_part.blob))
            ws = wb.active
            for col in range(2, 7):
                name = ws.cell(1, col).value
                if name in values:
                    ws.cell(2, col).value = values[name]
            buf = io.BytesIO()
            wb.save(buf)
            rel.target_part._blob = buf.getvalue()
