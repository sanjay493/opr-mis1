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
