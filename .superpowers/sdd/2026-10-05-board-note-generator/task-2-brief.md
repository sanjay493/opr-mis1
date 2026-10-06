### Task 2: `board_note_docx_utils.py` — generic docx mutation helpers

**Files:**
- Create: `backend/board_note_docx_utils.py`
- Test: `backend/tests/test_board_note_docx_utils.py`

**Interfaces:**
- Produces: `set_cell(cell, text: str) -> None`, `set_para(paragraph, text: str) -> None`, `replace_in_para(paragraph, replacements: list[tuple[str, str]]) -> None`, `remove_paragraph(paragraph) -> None`, `clone_paragraph_after(ref_paragraph, text: str)` (returns the new `Paragraph`), `fill_variable_bullets(slots: list, lines: list[str]) -> None`.
- Consumes: only `python-docx` (`docx.Document`, `docx.text.paragraph.Paragraph`) — no DB, no other board_note module.

These are the same operations already proven in `page_do_letter.py`
(`_set_paragraph_text`, `_set_cell_text`, `_remove_paragraph`,
`_clone_paragraph_after`), pulled out standalone so all four adapters share
one implementation. `fill_variable_bullets` generalizes the "fill N
template slots, clone extras, delete unused slots" pattern already used
there for the best-ever bullets list.

- [ ] **Step 1: Write the failing tests** in `backend/tests/test_board_note_docx_utils.py`:

```python
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
```

- [ ] **Step 2: Run to verify failure**

Run: `cd backend && venv/Scripts/python.exe -m pytest tests/test_board_note_docx_utils.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'board_note_docx_utils'`

- [ ] **Step 3: Implement `backend/board_note_docx_utils.py`** — port `_set_paragraph_text`/`_set_cell_text`/`_remove_paragraph`/`_clone_paragraph_after` from `page_do_letter.py:348-377` verbatim under the new public names, then write `fill_variable_bullets(slots, lines)`: zip `slots` with `lines` calling `set_para` on each matched pair; if `lines` is longer, call `clone_paragraph_after` on the last slot (or last cloned paragraph) for each remaining line, in order; if `slots` is longer, call `remove_paragraph` on every unmatched trailing slot.
- [ ] **Step 4: Run to verify pass**

Run: `cd backend && venv/Scripts/python.exe -m pytest tests/test_board_note_docx_utils.py -v`
Expected: 7 passed

- [ ] **Step 5: Commit**

```bash
git add backend/board_note_docx_utils.py backend/tests/test_board_note_docx_utils.py
git commit -m "Add shared docx mutation helpers for Board Note adapters"
```

---

