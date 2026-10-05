import docx

import board_note_docx_utils as u


def _doc_with_paragraphs(*texts):
    d = docx.Document()
    paras = [d.add_paragraph(t) for t in texts]
    return d, paras


def test_set_para_keeps_first_run_formatting_and_clears_rest():
    d, [p] = _doc_with_paragraphs("old")
    p.add_run(" extra")
    u.set_para(p, "new")
    assert p.text == "new"


def test_replace_in_para_substring_swap():
    d, [p] = _doc_with_paragraphs("Q-2'25-26:")
    u.replace_in_para(p, [("Q-2'25-26", "Q-2'26-27")])
    assert p.text == "Q-2'26-27:"


def test_set_cell_clears_extra_paragraphs():
    d = docx.Document()
    t = d.add_table(rows=1, cols=1)
    cell = t.rows[0].cells[0]
    cell.add_paragraph("second line")
    u.set_cell(cell, "only line")
    assert [p.text for p in cell.paragraphs] == ["only line"]


def test_fill_variable_bullets_exact_fit():
    d, slots = _doc_with_paragraphs("a", "b", "c")
    u.fill_variable_bullets(slots, ["x", "y", "z"])
    assert [p.text for p in d.paragraphs] == ["x", "y", "z"]


def test_fill_variable_bullets_fewer_lines_removes_unused_slots():
    d, slots = _doc_with_paragraphs("a", "b", "c")
    u.fill_variable_bullets(slots, ["x"])
    assert [p.text for p in d.paragraphs] == ["x"]


def test_fill_variable_bullets_more_lines_clones_extra_paragraphs():
    d, slots = _doc_with_paragraphs("a")
    u.fill_variable_bullets(slots, ["x", "y", "z"])
    assert [p.text for p in d.paragraphs] == ["x", "y", "z"]


def test_fill_variable_bullets_empty_lines_removes_all_slots():
    d, slots = _doc_with_paragraphs("a", "b")
    u.fill_variable_bullets(slots, [])
    assert [p.text for p in d.paragraphs] == []
