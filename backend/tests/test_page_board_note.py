import asyncio

import pytest
from fastapi import HTTPException

import main
import page_board_note as pbn


def test_rejects_quarter_out_of_range():
    with pytest.raises(ValueError):
        pbn.generate_board_note_docx_bytes("2026-27", 5)


def test_rejects_malformed_fy():
    with pytest.raises(ValueError):
        pbn.generate_board_note_docx_bytes("2026", 2)


def test_dispatches_to_the_right_adapter(monkeypatch):
    calls = []
    monkeypatch.setattr(pbn.board_note_q3, "generate", lambda fy: calls.append(fy) or b"docx-bytes")
    assert pbn.generate_board_note_docx_bytes("2026-27", 3) == b"docx-bytes"
    assert calls == ["2026-27"]


def _status(coro):
    try:
        asyncio.run(coro)
    except HTTPException as e:
        return e.status_code
    return 200


def test_docx_route_rejects_bad_fy_and_quarter_with_400():
    assert _status(main.board_note_docx(fy="2026", quarter="2")) == 400
    assert _status(main.board_note_docx(fy="2026-27", quarter="9")) == 400
    assert _status(main.board_note_docx(fy="2026-27", quarter="x")) == 400


def test_manual_text_routes_reject_bad_period_with_400():
    assert _status(main.get_board_note_manual_text(fy="2026", quarter="2")) == 400
    assert _status(main.get_board_note_manual_text(fy="2026-27", quarter="0")) == 400
    assert _status(main.save_board_note_manual_text({"report_fy": "2026", "quarter": 2, "entries": []})) == 400
    assert _status(main.save_board_note_manual_text({"report_fy": "2026-27", "quarter": 7, "entries": []})) == 400
