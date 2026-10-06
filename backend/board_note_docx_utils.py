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
