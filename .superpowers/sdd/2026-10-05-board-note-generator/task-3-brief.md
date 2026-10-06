### Task 3: `board_note_manual_text.py` — manual narrative storage

**Files:**
- Create: `backend/board_note_manual_text.py`
- Test: `backend/tests/test_board_note_manual_text.py`

**Interfaces:**
- Consumes: `board_note_docx_utils.fill_variable_bullets` (Task 2), `db.connect()`.
- Produces: `FIELDS = ("additional_highlights", "why_narrative")`; `get_manual_text(fy: str, quarter: int) -> dict[tuple[str, str], str]` keyed `(plant, field)`; `save_manual_text(fy: str, quarter: int, entries: list[dict]) -> int` (returns count processed; entries shaped `{"plant": str, "field": str, "text": str}`); `additional_highlight_lines(manual: dict, plant: str) -> list[str]`; `why_narrative_lines(manual: dict, plant: str, placeholder: str) -> list[str]`.

- [ ] **Step 1: Write the failing tests** in `backend/tests/test_board_note_manual_text.py`, following `tests/test_cover_store.py`'s own fixture pattern (throwaway SQLite file, `monkeypatch` on the module's DB entry point):

```python
import sqlite3

import pytest

import board_note_manual_text as bnm


@pytest.fixture
def store(tmp_path, monkeypatch):
    dbfile = tmp_path / "board_note.db"
    conn = sqlite3.connect(dbfile)
    conn.execute("""
        CREATE TABLE board_note_manual_text (
            report_fy TEXT, quarter INTEGER, plant TEXT, field TEXT, text TEXT,
            PRIMARY KEY (report_fy, quarter, plant, field)
        )
    """)
    conn.commit()
    conn.close()

    class _Conn:
        def __init__(self):
            self._c = sqlite3.connect(dbfile)
        def cursor(self):
            return self._c.cursor()
        def commit(self):
            self._c.commit()
        def close(self):
            self._c.close()

    monkeypatch.setattr(bnm.db, "connect", _Conn)
    return bnm


def test_get_manual_text_empty_for_untouched_period(store):
    assert store.get_manual_text("2026-27", 2) == {}


def test_save_then_get_round_trip(store):
    store.save_manual_text("2026-27", 2, [
        {"plant": "BSP", "field": "additional_highlights", "text": "BF-8 record"},
    ])
    assert store.get_manual_text("2026-27", 2) == {("BSP", "additional_highlights"): "BF-8 record"}


def test_empty_text_deletes_existing_row(store):
    store.save_manual_text("2026-27", 2, [{"plant": "BSP", "field": "why_narrative", "text": "shutdown"}])
    store.save_manual_text("2026-27", 2, [{"plant": "BSP", "field": "why_narrative", "text": ""}])
    assert store.get_manual_text("2026-27", 2) == {}


def test_new_period_never_sees_another_periods_text(store):
    store.save_manual_text("2025-26", 2, [{"plant": "BSP", "field": "why_narrative", "text": "old year text"}])
    assert store.get_manual_text("2026-27", 2) == {}


def test_additional_highlight_lines_splits_and_strips_blanks():
    manual = {("BSP", "additional_highlights"): "line one\n\nline two  "}
    assert bnm.additional_highlight_lines(manual, "BSP") == ["line one", "line two"]


def test_why_narrative_lines_uses_placeholder_when_blank():
    assert bnm.why_narrative_lines({}, "BSP", "[Add narrative]") == ["[Add narrative]"]
```

- [ ] **Step 2: Run to verify failure**

Run: `cd backend && venv/Scripts/python.exe -m pytest tests/test_board_note_manual_text.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'board_note_manual_text'`

- [ ] **Step 3: Implement `backend/board_note_manual_text.py`.** `get_manual_text` runs `SELECT plant, field, text FROM board_note_manual_text WHERE report_fy=? AND quarter=?` and returns `{(plant, field): text for ... if text}` (drop empty/NULL rows, same convention `do_letter_remark_table`'s reader uses). `save_manual_text` loops entries: non-empty `text.strip()` does an `INSERT ... ON CONFLICT(report_fy, quarter, plant, field) DO UPDATE SET text = excluded.text`; empty does `DELETE FROM board_note_manual_text WHERE report_fy=? AND quarter=? AND plant=? AND field=?` — same two-branch shape as `save_do_letter_remarks` in `main.py:5311-5346`. `additional_highlight_lines` returns `[ln.strip() for ln in manual.get((plant, "additional_highlights"), "").split("\n") if ln.strip()]`. `why_narrative_lines` returns the same split/stripped list, or `[placeholder]` if that list is empty.
- [ ] **Step 4: Run to verify pass**

Run: `cd backend && venv/Scripts/python.exe -m pytest tests/test_board_note_manual_text.py -v`
Expected: 6 passed

- [ ] **Step 5: Commit**

```bash
git add backend/board_note_manual_text.py backend/tests/test_board_note_manual_text.py
git commit -m "Add Board Note manual-narrative storage (get/save + line helpers)"
```

---

