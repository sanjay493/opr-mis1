"""Quarterly Board Note dispatcher.

Picks one of the four per-quarter adapters (`board_note_q1..q4`) and returns
the generated .docx bytes. Input validation lives here so the route layer and
the adapters can both rely on it.
"""

import re

import board_note_q1
import board_note_q2
import board_note_q3
import board_note_q4

QUARTER_ADAPTERS = {
    1: board_note_q1,
    2: board_note_q2,
    3: board_note_q3,
    4: board_note_q4,
}


def generate_board_note_docx_bytes(fy: str, quarter: int) -> bytes:
    if not re.fullmatch(r"\d{4}-\d{2}", fy):
        raise ValueError(f"fy must be YYYY-YY, got {fy!r}")
    if quarter not in QUARTER_ADAPTERS:
        raise ValueError(f"quarter must be 1-4, got {quarter!r}")
    return QUARTER_ADAPTERS[quarter].generate(fy)
