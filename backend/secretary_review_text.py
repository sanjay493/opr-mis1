"""Saved narrative for the Secretary Review deck, keyed by
(report_month, block_key) in `secretary_review_text`. Block keys are listed
in secretary_review_layout.BLOCKS. An empty text is stored as '' — it means
"leave this block empty", unlike a missing row, which falls back to the DB
default (page_secretary_review_texts.effective_texts)."""

import datetime as _dt

import db


def get_texts(month: str) -> dict:
    conn = db.connect()
    cur = conn.cursor()
    try:
        cur.execute("SELECT block_key, text FROM secretary_review_text WHERE report_month=?", (month,))
        return {k: (t or "") for k, t in cur.fetchall()}
    finally:
        conn.close()


def save_texts(month: str, texts: dict) -> int:
    now = _dt.datetime.now().isoformat(timespec="seconds")
    conn = db.connect()
    cur = conn.cursor()
    try:
        n = 0
        for key, text in texts.items():
            key = str(key).strip()
            if not key:
                continue
            text = str(text or "").strip()
            cur.execute("""
                INSERT INTO secretary_review_text (report_month, block_key, text, updated_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(report_month, block_key) DO UPDATE SET text = excluded.text, updated_at = excluded.updated_at
            """, (month, key, text, now))
            n += 1
        conn.commit()
        return n
    finally:
        conn.close()


def delete_texts(month: str, keys) -> int:
    """Drop the saved rows for `keys`, so those blocks follow the DB default
    again. Returns the number of rows removed."""
    keys = [str(k).strip() for k in keys if str(k).strip()]
    if not keys:
        return 0
    conn = db.connect()
    cur = conn.cursor()
    try:
        phs = ",".join("?" for _ in keys)
        cur.execute(f"DELETE FROM secretary_review_text WHERE report_month=? AND block_key IN ({phs})",
                    [month] + keys)
        n = cur.rowcount
        conn.commit()
        return n
    finally:
        conn.close()


def latest_saved_before(block_key: str, month: str, window: list):
    candidates = sorted(m for m in window if m < month)
    if not candidates:
        return None
    conn = db.connect()
    cur = conn.cursor()
    try:
        phs = ",".join("?" for _ in candidates)
        cur.execute(
            f"SELECT text FROM secretary_review_text WHERE block_key=? AND report_month IN ({phs}) "
            f"ORDER BY report_month DESC LIMIT 1",
            [block_key] + candidates,
        )
        row = cur.fetchone()
        return row[0] if row else None
    finally:
        conn.close()
