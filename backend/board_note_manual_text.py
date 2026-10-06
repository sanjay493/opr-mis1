"""Manual narrative storage for the quarterly Board Note generator.

Per-plant free-text entries keyed by (report_fy, quarter, plant, field) in
`board_note_manual_text`. Two fields exist today (see FIELDS): editors add
extra plant highlights the auto-generated data doesn't cover, and short
narratives explaining notable variances ("why" text). An empty text value
deletes the row rather than storing a blank, so a cleared textbox doesn't
leave a stale empty row behind (same convention as do_letter_remark_table).
"""

import db

FIELDS = ("additional_highlights", "why_narrative")


def get_manual_text(fy: str, quarter: int) -> dict:
    """Return {(plant, field): text} for every non-empty row in this period."""
    conn = db.connect()
    cur = conn.cursor()
    try:
        cur.execute(
            "SELECT plant, field, text FROM board_note_manual_text WHERE report_fy=? AND quarter=?",
            (fy, quarter),
        )
        return {(plant, field): text for plant, field, text in cur.fetchall() if text}
    finally:
        conn.close()


def save_manual_text(fy: str, quarter: int, entries: list) -> int:
    """Upsert or delete each entry ({"plant", "field", "text"}). An empty
    (after strip) text deletes the row. Returns the count processed."""
    conn = db.connect()
    cur = conn.cursor()
    try:
        saved = 0
        for e in entries:
            plant = str(e.get("plant", "")).strip()
            field = str(e.get("field", "")).strip()
            text = str(e.get("text", "")).strip()
            if not plant or not field:
                continue
            if text:
                cur.execute("""
                    INSERT INTO board_note_manual_text (report_fy, quarter, plant, field, text)
                    VALUES (?, ?, ?, ?, ?)
                    ON CONFLICT(report_fy, quarter, plant, field) DO UPDATE SET text = excluded.text
                """, (fy, quarter, plant, field, text))
            else:
                cur.execute(
                    "DELETE FROM board_note_manual_text WHERE report_fy=? AND quarter=? AND plant=? AND field=?",
                    (fy, quarter, plant, field),
                )
            saved += 1
        conn.commit()
    finally:
        conn.close()
    return saved


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
