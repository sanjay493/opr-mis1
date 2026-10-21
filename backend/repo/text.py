"""Narrative / note text repository: the free-text tables behind the report's
editable prose.

    page3_narrative           page 3 Production Narrative + Highlights
    key_highlights_narrative  Key Highlights & Variances page
    steel_sales_highlights    Steel Sales Performance bullets
    secretary_review_text     Secretary Review deck blocks
    board_note_manual_text    quarterly Board Note per-plant narrative
    do_letter_remark_table    DO letter Annexure-A/B remarks
    sail_sales_note_table     SAIL 1-page report Table A footnote
    rail_prod_despatch_note   Rail Production & Dispatch footer remarks
    special_steel_phys_note   Special Steel Plants Physical footnotes

The db.py / board_note_manual_text.py / secretary_review_text.py functions
moved here verbatim and are re-exported from those modules. The named
cursor-level queries are the statements that used to live inline in main.py
/ page_*.py, moved verbatim: each runs on the caller's cursor (so the
caller's connection, transaction and row type are unchanged) and returns the
plain fetchone() / fetchall() result.

get() / put() at the bottom are the uniform text interface later tasks rely
on (Task 7 repoints them at one report_text table). Today they are a thin
dispatcher over the per-table functions; see SCOPES for the map.
"""
import datetime as _dt
import json
from typing import Any, Dict, List, Optional

from dbengine import connect
from repo import version as _ver
from repo import conn as rc
from secretary_review_layout import BLOCKS as _SECRETARY_BLOCKS


# ── Moved from db.py ─────────────────────────────────────────────────────────

def get_page3_narrative(month: str) -> Optional[dict]:
    """Returns the saved Page 3 Production Narrative + Highlights for a month,
    or None if nothing has ever been saved (caller should keep whatever
    default/computed value it already has)."""
    conn = connect()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT production_narrative, highlights FROM page3_narrative WHERE report_month = %s",
        (month,)
    )
    row = cursor.fetchone()
    conn.close()
    if not row:
        return None
    narrative, highlights_text = row[0] or "", row[1] or ""
    return {
        "production_narrative": narrative,
        "highlights": highlights_text.split("\n") if highlights_text else [],
    }


def save_page3_narrative(month: str, production_narrative: str, highlights: List[str]):
    """Saves/updates Page 3's Production Narrative + Highlights, keyed only by
    report_month — independent of page_configs so it never risks touching
    the other 34 pages' saved data for the month."""
    conn = connect()
    cursor = conn.cursor()
    highlights_text = "\n".join(highlights or [])
    cursor.execute("""
        INSERT INTO page3_narrative (report_month, production_narrative, highlights, updated_at)
        VALUES (%s, %s, %s, NOW())
        AS new ON DUPLICATE KEY UPDATE production_narrative = new.production_narrative,
                       highlights = new.highlights,
                       updated_at = new.updated_at
    """, (month, production_narrative or "", highlights_text))
    _ver.bump(conn)
    conn.commit()
    conn.close()


def get_key_highlights_narrative(month: str) -> Optional[dict]:
    """Returns the saved Key Highlights & Variances narrative (Major
    Achievements / Major Shortfalls / Focus Areas Going Forward) for a
    month, or None if nothing has ever been saved for it — the report page
    shows empty sections in that case rather than inventing text."""
    conn = connect()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT achievements, shortfalls, focus_areas, updated_by, updated_at "
        "FROM key_highlights_narrative WHERE report_month = %s",
        (month,)
    )
    row = cursor.fetchone()
    conn.close()
    if not row:
        return None
    achievements, shortfalls, focus_areas, updated_by, updated_at = row
    return {
        "achievements": json.loads(achievements) if achievements else [],
        "shortfalls":   json.loads(shortfalls) if shortfalls else [],
        "focus_areas":  json.loads(focus_areas) if focus_areas else [],
        "updated_by":   updated_by or "",
        "updated_at":   updated_at or "",
    }


def save_key_highlights_narrative(month: str, achievements: list, shortfalls: list,
                                   focus_areas: list, updated_by: str = ""):
    """Saves/updates the Key Highlights & Variances narrative for a month,
    keyed only by report_month — independent of page_configs, same as
    save_page3_narrative above."""
    conn = connect()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO key_highlights_narrative
            (report_month, achievements, shortfalls, focus_areas, updated_by, updated_at)
        VALUES (%s, %s, %s, %s, %s, NOW())
        AS new ON DUPLICATE KEY UPDATE achievements = new.achievements,
                       shortfalls  = new.shortfalls,
                       focus_areas = new.focus_areas,
                       updated_by  = new.updated_by,
                       updated_at  = new.updated_at
    """, (month, json.dumps(achievements or []), json.dumps(shortfalls or []),
          json.dumps(focus_areas or []), updated_by or ""))
    _ver.bump(conn)
    conn.commit()
    conn.close()


def get_steel_sales_highlights(month: str) -> Optional[dict]:
    """Saved Steel Sales Performance bullets (report-month + YTD lists) for
    a month, or None if nothing has ever been saved for it — the report
    page shows empty sections in that case rather than inventing text."""
    conn = connect()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT month_items, ytd_items, updated_by, updated_at "
        "FROM steel_sales_highlights WHERE report_month = %s",
        (month,)
    )
    row = cursor.fetchone()
    conn.close()
    if not row:
        return None
    month_items, ytd_items, updated_by, updated_at = row
    return {
        "month_items": json.loads(month_items) if month_items else [],
        "ytd_items":   json.loads(ytd_items) if ytd_items else [],
        "updated_by":  updated_by or "",
        "updated_at":  updated_at or "",
    }


def save_steel_sales_highlights(month: str, month_items: list, ytd_items: list, updated_by: str = ""):
    """Saves/updates the Steel Sales Performance bullets for a month, keyed
    only by report_month — independent of page_configs, same as
    save_key_highlights_narrative above."""
    conn = connect()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO steel_sales_highlights
            (report_month, month_items, ytd_items, updated_by, updated_at)
        VALUES (%s, %s, %s, %s, NOW())
        AS new ON DUPLICATE KEY UPDATE month_items = new.month_items,
                       ytd_items   = new.ytd_items,
                       updated_by  = new.updated_by,
                       updated_at  = new.updated_at
    """, (month, json.dumps(month_items or []), json.dumps(ytd_items or []), updated_by or ""))
    _ver.bump(conn)
    conn.commit()
    conn.close()


# ── "Special Steel Plants Physical Performance" report ────────────────────────
# Backing store for page_special_steel_physical.py + its two data-entry pages.
# All physical figures are '000 T. See migrate_add_special_steel_physical.sql.

def get_ss_phys_notes(financial_year):
    """-> [(sort_order, note_text), ...] ordered."""
    conn = connect()
    cur = conn.cursor()
    cur.execute("SELECT sort_order, note_text FROM special_steel_phys_note "
                "WHERE financial_year=%s ORDER BY sort_order", (financial_year,))
    rows = cur.fetchall()
    conn.close()
    return [(so, t) for so, t in rows]


def save_ss_phys_notes(financial_year, rows):
    """Replace every note for a FY with `rows`: {sort_order, note_text}."""
    conn = connect()
    cur = conn.cursor()
    cur.execute("DELETE FROM special_steel_phys_note WHERE financial_year=%s", (financial_year,))
    for r in rows:
        text = (r.get("note_text") or "").strip()
        if not text:
            continue
        cur.execute("INSERT INTO special_steel_phys_note (financial_year, sort_order, note_text) "
                    "VALUES (%s, %s, %s)", (financial_year, int(r.get("sort_order") or 0), text))
    _ver.bump(conn)
    conn.commit()
    conn.close()
    return len(rows)


def get_rail_report_notes() -> List[tuple]:
    """-> [(sort_order, note_text), ...] ordered."""
    conn = connect()
    cur = conn.cursor()
    cur.execute("SELECT sort_order, note_text FROM rail_prod_despatch_note ORDER BY sort_order")
    rows = cur.fetchall()
    conn.close()
    return [(so, t) for so, t in rows]


def save_rail_report_notes(rows: List[Dict[str, Any]]) -> int:
    """Replace every footer remark with `rows`: {sort_order, note_text}."""
    conn = connect()
    cur = conn.cursor()
    cur.execute("DELETE FROM rail_prod_despatch_note")
    for r in rows:
        text = (r.get("note_text") or "").strip()
        if not text:
            continue
        cur.execute("INSERT INTO rail_prod_despatch_note (sort_order, note_text) VALUES (%s, %s)",
                    (int(r.get("sort_order") or 0), text))
    _ver.bump(conn)
    conn.commit()
    conn.close()
    return len(rows)


# ── Moved from board_note_manual_text.py ──────────────────────────────────────

def get_manual_text(fy: str, quarter: int) -> dict:
    """Return {(plant, field): text} for every non-empty row in this period."""
    conn = connect()
    cur = conn.cursor()
    try:
        cur.execute(
            "SELECT plant, field, text FROM board_note_manual_text WHERE report_fy=%s AND quarter=%s",
            (fy, quarter),
        )
        return {(plant, field): text for plant, field, text in cur.fetchall() if text}
    finally:
        conn.close()


def save_manual_text(fy: str, quarter: int, entries: list) -> int:
    """Upsert or delete each entry ({"plant", "field", "text"}). An empty
    (after strip) text deletes the row. Returns the count processed."""
    conn = connect()
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
                    VALUES (%s, %s, %s, %s, %s)
                    AS new ON DUPLICATE KEY UPDATE text = new.text
                """, (fy, quarter, plant, field, text))
            else:
                cur.execute(
                    "DELETE FROM board_note_manual_text WHERE report_fy=%s AND quarter=%s AND plant=%s AND field=%s",
                    (fy, quarter, plant, field),
                )
            saved += 1
        _ver.bump(conn)
        conn.commit()
    finally:
        conn.close()
    return saved


# ── Moved from secretary_review_text.py ───────────────────────────────────────

def get_texts(month: str) -> dict:
    conn = connect()
    cur = conn.cursor()
    try:
        cur.execute("SELECT block_key, text FROM secretary_review_text WHERE report_month=%s", (month,))
        return {k: (t or "") for k, t in cur.fetchall()}
    finally:
        conn.close()


def save_texts(month: str, texts: dict) -> int:
    now = _dt.datetime.now().isoformat(timespec="seconds")
    conn = connect()
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
                VALUES (%s, %s, %s, %s)
                AS new ON DUPLICATE KEY UPDATE text = new.text, updated_at = new.updated_at
            """, (month, key, text, now))
            n += 1
        _ver.bump(conn)
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
    conn = connect()
    cur = conn.cursor()
    try:
        phs = ",".join("%s" for _ in keys)
        cur.execute(f"DELETE FROM secretary_review_text WHERE report_month=%s AND block_key IN ({phs})",
                    [month] + keys)
        n = cur.rowcount
        _ver.bump(conn)
        conn.commit()
        return n
    finally:
        conn.close()


def latest_saved_before(block_key: str, month: str, window: list):
    candidates = sorted(m for m in window if m < month)
    if not candidates:
        return None
    conn = connect()
    cur = conn.cursor()
    try:
        phs = ",".join("%s" for _ in candidates)
        cur.execute(
            f"SELECT text FROM secretary_review_text WHERE block_key=%s AND report_month IN ({phs}) "
            f"ORDER BY report_month DESC LIMIT 1",
            [block_key] + candidates,
        )
        row = cur.fetchone()
        return row[0] if row else None
    finally:
        conn.close()


# ── Named queries (moved verbatim from main.py / page_*.py) ──────────────────

def page3_narrative_any_row(report_month):
    """True when page3_narrative has a non-blank narrative or highlights for
    the month. page_missing_data."""
    with rc.cursor() as cur:
        cur.execute("SELECT 1 FROM page3_narrative WHERE report_month = %s "
                    "AND (COALESCE(production_narrative,'') != '' OR COALESCE(highlights,'') != '')",
                    [report_month])
        return bool(cur.fetchall())


def upsert_sail_sales_note(cur, month, note):
    """Upsert the Table A footnote on the caller's cursor; the caller commits.
    main POST /api/sail-1page/confirm."""
    _ver.bump(cur)
    cur.execute("""
                INSERT INTO sail_sales_note_table (report_month, note)
                VALUES (%s, %s)
                AS new ON DUPLICATE KEY UPDATE note = new.note
            """, (month, note))


def sail_sales_note_row(cur, month):
    """fetchone() of (note,) for the month, or None.
    page_one_page_report._sales_note."""
    cur.execute("SELECT note FROM sail_sales_note_table WHERE report_month=%s", (month,))
    return cur.fetchone()


def do_letter_remark_rows(cur, month):
    """fetchall() of (item_name, plant_name, remark) for the month.
    main GET /api/do-letter/remarks."""
    cur.execute(
            "SELECT item_name, plant_name, remark FROM do_letter_remark_table WHERE report_month=%s",
            (month,),
        )
    return cur.fetchall()


def do_letter_item_remark_rows(cur, report_month, item_name):
    """fetchall() of (plant_name, remark) for one item.
    page_do_letter._fetch_remarks."""
    cur.execute(
        "SELECT plant_name, remark FROM do_letter_remark_table "
        "WHERE report_month=%s AND item_name=%s",
        (report_month, item_name),
    )
    return cur.fetchall()


def upsert_do_letter_remark(cur, report_month, item_name, plant_name, remark):
    """Upsert one remark on the caller's cursor; the caller commits.
    main POST /api/do-letter/remarks."""
    _ver.bump(cur)
    cur.execute("""
                    INSERT INTO do_letter_remark_table (report_month, item_name, plant_name, remark)
                    VALUES (%s, %s, %s, %s)
                    AS new ON DUPLICATE KEY UPDATE remark = new.remark
                """, (report_month, item_name, plant_name, remark))


def delete_do_letter_remark(cur, report_month, item_name, plant_name):
    """Delete one remark on the caller's cursor; the caller commits.
    main POST /api/do-letter/remarks (empty remark)."""
    _ver.bump(cur)
    cur.execute(
                    "DELETE FROM do_letter_remark_table WHERE report_month=%s AND item_name=%s AND plant_name=%s",
                    (report_month, item_name, plant_name),
                )


# ── get / put: the uniform text interface ────────────────────────────────────
#
# scope              table                     period          block_key                    plant / item
# page3_narrative    page3_narrative           report_month    production_narrative |       -
#                                                              highlights
# key_highlights     key_highlights_narrative  report_month    achievements | shortfalls |  -
#                                                              focus_areas
# steel_sales        steel_sales_highlights    report_month    month_items | ytd_items      -
# secretary_review   secretary_review_text     report_month    block key (layout BLOCKS)    -
# board_note         board_note_manual_text    "<fy>:Q<n>"     BOARD_NOTE_FIELDS            plant (required)
# do_letter          do_letter_remark_table    report_month    "remark"                     plant, item (required)
# sail_sales_note    sail_sales_note_table     report_month    "note"                       -
# rail_note          rail_prod_despatch_note   (ignored)       sort_order, as a string      -
# ss_phys_note       special_steel_phys_note   financial_year  sort_order, as a string      -
#
# Text formats. page3 `highlights` is the stored newline-joined string. The
# key_highlights / steel_sales blocks are stored as JSON lists: get() returns
# that JSON string; put() takes either a JSON list or plain text, which is
# split into one item per non-blank line. `user` is stored where the table
# has an updated_by column (key_highlights, steel_sales) and ignored
# elsewhere. put() keeps each table's own semantics: an empty text deletes
# the board_note / do_letter / rail_note / ss_phys_note row (those tables
# never store blanks) and is stored as '' elsewhere.

# board_note's fields (re-exported as board_note_manual_text.FIELDS).
BOARD_NOTE_FIELDS = ("additional_highlights", "why_narrative")

# block_key is validated for every scope that has a fixed key set:
# secretary_review against secretary_review_layout.BLOCKS (the same set
# api_secretary_review accepts) and board_note against BOARD_NOTE_FIELDS (the
# only fields board_note_q1-q4 read). rail_note / ss_phys_note keys are
# sort_order numbers, so any integer string is accepted there.
SCOPES = {
    "page3_narrative": ("page3_narrative", ("production_narrative", "highlights")),
    "key_highlights": ("key_highlights_narrative", ("achievements", "shortfalls", "focus_areas")),
    "steel_sales": ("steel_sales_highlights", ("month_items", "ytd_items")),
    "secretary_review": ("secretary_review_text", tuple(k for k, _, _ in _SECRETARY_BLOCKS)),
    "board_note": ("board_note_manual_text", BOARD_NOTE_FIELDS),
    "do_letter": ("do_letter_remark_table", ("remark",)),
    "sail_sales_note": ("sail_sales_note_table", ("note",)),
    "rail_note": ("rail_prod_despatch_note", None),
    "ss_phys_note": ("special_steel_phys_note", None),
}


def _check(scope, block_key):
    if scope not in SCOPES:
        raise ValueError(f"unknown text scope {scope!r}")
    keys = SCOPES[scope][1]
    if keys is not None and block_key not in keys:
        raise ValueError(f"unknown block_key {block_key!r} for scope {scope!r}")


# Scopes whose rows are keyed by plant (and item): put() refuses to write
# without them rather than storing a row no reader would ever find.
_REQUIRED = {"board_note": ("plant",), "do_letter": ("plant", "item")}


def _check_keys(scope, plant, item):
    given = {"plant": plant, "item": item}
    for name in _REQUIRED.get(scope, ()):
        if not given[name]:
            raise ValueError(f"scope {scope!r} needs {name!r}")


def _board_period(period):
    fy, _, q = str(period).partition(":")
    return fy, int(q.upper().lstrip("Q"))


def _as_list(text):
    try:
        val = json.loads(text)
    except (TypeError, ValueError):
        val = None
    if isinstance(val, list):
        return val
    return [ln.strip() for ln in str(text or "").split("\n") if ln.strip()]


def _get_notes(scope, period):
    return get_rail_report_notes() if scope == "rail_note" else get_ss_phys_notes(period)


def _put_note(scope, period, sort_order, text):
    notes = {so: t for so, t in _get_notes(scope, period)}
    if text:
        notes[sort_order] = text
    else:
        notes.pop(sort_order, None)
    rows = [{"sort_order": so, "note_text": t} for so, t in sorted(notes.items())]
    if scope == "rail_note":
        save_rail_report_notes(rows)
    else:
        save_ss_phys_notes(period, rows)


def get(scope: str, period: str, block_key: str, plant=None, item=None) -> Optional[str]:
    """The saved text of one block, or None when nothing is saved."""
    _check(scope, block_key)
    if scope == "page3_narrative":
        saved = get_page3_narrative(period)
        if saved is None:
            return None
        if block_key == "highlights":
            return "\n".join(saved["highlights"])
        return saved["production_narrative"]
    if scope in ("key_highlights", "steel_sales"):
        saved = (get_key_highlights_narrative if scope == "key_highlights" else get_steel_sales_highlights)(period)
        return None if saved is None else json.dumps(saved[block_key])
    if scope == "secretary_review":
        return get_texts(period).get(block_key)
    if scope == "board_note":
        fy, q = _board_period(period)
        return get_manual_text(fy, q).get((plant, block_key))
    if scope == "do_letter":
        with rc.cursor() as cur:
            return {p: r for p, r in do_letter_item_remark_rows(cur, period, item) if r}.get(plant)
    if scope == "sail_sales_note":
        with rc.cursor() as cur:
            row = sail_sales_note_row(cur, period)
        # A blank note reads as None, as page_one_page_report._sales_note.
        return row[0] if row and row[0] else None
    return dict(_get_notes(scope, period)).get(int(block_key))


def put(scope: str, period: str, block_key: str, text: str, user, plant=None, item=None) -> None:
    """Save one block's text (see the map above for each scope's rules).
    Raises ValueError for an unknown scope / block_key, or when board_note
    has no `plant` or do_letter lacks `plant` or `item`."""
    _check(scope, block_key)
    _check_keys(scope, plant, item)
    text = "" if text is None else str(text)
    if scope == "page3_narrative":
        saved = get_page3_narrative(period) or {"production_narrative": "", "highlights": []}
        if block_key == "highlights":
            saved["highlights"] = text.split("\n") if text else []
        else:
            saved["production_narrative"] = text
        save_page3_narrative(period, saved["production_narrative"], saved["highlights"])
    elif scope == "key_highlights":
        saved = get_key_highlights_narrative(period) or {"achievements": [], "shortfalls": [], "focus_areas": []}
        saved[block_key] = _as_list(text)
        save_key_highlights_narrative(period, saved["achievements"], saved["shortfalls"],
                                      saved["focus_areas"], updated_by=user or "")
    elif scope == "steel_sales":
        saved = get_steel_sales_highlights(period) or {"month_items": [], "ytd_items": []}
        saved[block_key] = _as_list(text)
        save_steel_sales_highlights(period, saved["month_items"], saved["ytd_items"], updated_by=user or "")
    elif scope == "secretary_review":
        save_texts(period, {block_key: text})
    elif scope == "board_note":
        fy, q = _board_period(period)
        save_manual_text(fy, q, [{"plant": plant, "field": block_key, "text": text}])
    elif scope == "do_letter":
        with rc.tx() as cur:
            if text.strip():
                upsert_do_letter_remark(cur, period, item, plant, text.strip())
            else:
                delete_do_letter_remark(cur, period, item, plant)
    elif scope == "sail_sales_note":
        with rc.tx() as cur:
            upsert_sail_sales_note(cur, period, text)
    else:
        _put_note(scope, period, int(block_key), text.strip())
