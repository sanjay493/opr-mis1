"""Manual narrative storage for the quarterly Board Note generator.

Per-plant free-text entries keyed by (report_fy, quarter, plant, field) in
`board_note_manual_text`. Two fields exist today (see FIELDS): editors add
extra plant highlights the auto-generated data doesn't cover, and short
narratives explaining notable variances ("why" text). An empty text value
deletes the row rather than storing a blank, so a cleared textbox doesn't
leave a stale empty row behind (same convention as do_letter_remark_table).
get_manual_text / save_manual_text live in repo/text.py (re-exported here).
"""

from repo.text import get_manual_text, save_manual_text  # noqa: F401

FIELDS = ("additional_highlights", "why_narrative")


def additional_highlight_lines(manual: dict, plant: str) -> list:
    """Non-blank, stripped lines of this plant's additional-highlights text."""
    text = manual.get((plant, "additional_highlights"), "")
    return [ln.strip() for ln in text.split("\n") if ln.strip()]


def why_narrative_lines(manual: dict, plant: str, placeholder: str) -> list:
    """Non-blank, stripped lines of this plant's why-narrative text, or
    [placeholder] when there's nothing entered."""
    text = manual.get((plant, "why_narrative"), "")
    lines = [ln.strip() for ln in text.split("\n") if ln.strip()]
    return lines or [placeholder]
