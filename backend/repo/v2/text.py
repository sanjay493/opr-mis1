"""Narrative / note text repository on the v2 schema: the 9 v1 narrative
tables live in one table, report_text (scripts/v2/schema_v2.sql), one scope
per v1 table (repo.v2codec.TEXT_SCOPES is the shared map):

    scope             v1 table                  period          block_key        plant / item / seq
    page3_narrative   page3_narrative           report_month    column name      -
    key_highlights    key_highlights_narrative  report_month    column name      -
    steel_sales       steel_sales_highlights    report_month    column name      -
    secretary_review  secretary_review_text     report_month    block key        -
    board_note        board_note_manual_text    '<fy>:Q<n>'     field            plant_code
    do_letter         do_letter_remark_table    report_month    'remark'         plant_code, item_id
    sail_sales_note   sail_sales_note_table     report_month    'note'           -
    rail_note         rail_prod_despatch_note   ''              'note'           seq = sort_order
    ss_phys_note      special_steel_phys_note   financial_year  'note'           seq = sort_order

Same public names, signatures, return shapes, row types and exceptions as
repo/text.py. The rules that keep them equal:

WIDE SCOPES (page3 / key_highlights / steel_sales). A v1 row is one
report_text row per column, all written by one statement, so they carry one
updated_by / updated_at. "Saved" (v1: the row exists) is "any row of the
scope and period exists"; a NULL column is a row with text NULL, so NULL
vs '' vs absent reads back as v1's. Writers store exactly v1's text:
page3 highlights newline-joined, the list blocks json.dumps(list) (the same
text v1 stored), updated_by `updated_by or ""` (page3 has no updated_by:
NULL), updated_at NOW(). Reads render updated_at in v1's 'YYYY-MM-DD
HH:MM:SS' form (the str() dbengine gave v1's DATETIME).

READ-MODIFY-WRITE. v1 put() read with one connection and saved with
another. Here every wide-scope and note write runs in ONE transaction:
bump, a locking read (FOR UPDATE) of the stored rows, the new rows computed
from them, then the write (_write_wide / _replace_notes take that
computation as `make`). The save_* functions are the same with a `make`
that ignores what is stored.

NOTES (rail_note / ss_phys_note). block_key 'note', seq = sort_order; v1
put() passes sort_order as block_key, which is translated here. A save
replaces every note of the period (v1: DELETE, then one INSERT per non-blank
row), checking each row in v1's order before its insert.

SECRETARY REVIEW. updated_at is datetime.now() truncated to the second (v1
stored isoformat(timespec="seconds"); v2codec ISO_SECONDS renders it back).

PLANTS / ITEMS. plant_code is ai_ci and an FK to the plant master: a write
creates a missing plant (repo/v2/_keys.ensure_plant) and stores the
caller's spelling; the unique key (plant_key ai_ci) makes a case variant
update the stored row, keeping its spelling, as v1's ai_ci primary key did.
do_letter items: a locking ai_ci lookup of the stored remark for
(month, plant, item) reuses its item_id (v1's ai_ci key updated that row);
otherwise the item is resolved by its EXACT string (created when missing).
Reads match items with `item_name COLLATE utf8mb4_0900_ai_ci`.

ORDER. v1 reads with no ORDER BY were served in primary-key order (every
one filters on a primary-key prefix); the same order is explicit here, on
the same ai_ci collation: get_manual_text (plant, field), get_texts
(block_key), do_letter_remark_rows (item ai_ci, plant),
do_letter_item_remark_rows (plant). Notes: ORDER BY seq, as v1's sort_order.

v1 COLUMN LIMITS. report_text's columns are wider than some v1 columns
(period VARCHAR(10), block_key VARCHAR(48), text MEDIUMTEXT). Every write
checks the v1 limit first and raises v1's own error (strict sql_mode):
DataError 1406 "Data too long for column '<v1 column>' at row 1", 1264 out
of range, IntegrityError 1048 NULL / 1062 duplicate note sort_order with
v1's key text. Only what v2 cannot hold at all raises
_keys.OutOfModelError before anything is written: a board_note plant of
9..16 characters (v1 plant VARCHAR(16), v2 plant_code VARCHAR(8)) and a
board_note period longer than 10 ('<fy>:Q<n>' with a 2+ digit quarter).
"""
import datetime as _dt
import json
from typing import Any, Dict, List, Optional

import pymysql

from repo import conn as rc
from repo import version as _ver
from repo.v2 import _keys
from repo.v2codec import ISO_SECONDS, SQL_SECONDS, board_note_period, render_ts
from secretary_review_layout import BLOCKS as _SECRETARY_BLOCKS

_TEXT_MAX = 65535                   # v1 TEXT, in bytes
_ITEM_CI = "i.item_name COLLATE utf8mb4_0900_ai_ci"


# ── v1 column checks ──────────────────────────────────────────────────────────

def _fits(column, value, limit, *, nbytes=False, nullable=True):
    """Raise v1's error for `value` in a v1 column of `limit` characters
    (bytes for TEXT)."""
    if value is None:
        if not nullable:
            raise rc.IntegrityError(1048, f"Column '{column}' cannot be null")
        return
    s = value if isinstance(value, str) else str(value)
    n = len(s.encode("utf-8")) if nbytes else len(s)
    if n > limit:
        raise pymysql.err.DataError(1406, f"Data too long for column '{column}' at row 1")


def _in_range(column, value, lo, hi):
    if not lo <= int(value) <= hi:
        raise pymysql.err.DataError(1264, f"Out of range value for column '{column}' at row 1")


def _item_id_for_write(cur, item, *, bump):
    """item_id of the item spelled exactly `item`, created when missing."""
    if bump:
        _ver.bump(cur)
    item_id = _keys.exact_item_id(cur, item, lock=True)
    if item_id is None:
        cur.execute("INSERT INTO item (item_name) VALUES (%s) AS new "
                    "ON DUPLICATE KEY UPDATE item_name = item.item_name", (item,))
        item_id = _keys.exact_item_id(cur, item, lock=True)
    return item_id


# ── wide scopes: page3 / key_highlights / steel_sales ─────────────────────────

_WIDE = {
    "page3_narrative": ("production_narrative", "highlights"),
    "key_highlights": ("achievements", "shortfalls", "focus_areas"),
    "steel_sales": ("month_items", "ytd_items"),
}
_WIDE_SELECT = ("SELECT block_key, text, updated_by, updated_at FROM report_text "
                "WHERE scope = %s AND period = %s")


def _decode_wide(scope, rows) -> Optional[dict]:
    """The stored rows of one (scope, period) -> what v1's get_* returned."""
    if not rows:
        return None
    text = {r[0]: r[1] for r in rows}
    updated_by, updated_at = rows[0][2], render_ts(SQL_SECONDS, rows[0][3])
    if scope == "page3_narrative":
        narrative, highlights_text = text.get("production_narrative") or "", text.get("highlights") or ""
        return {
            "production_narrative": narrative,
            "highlights": highlights_text.split("\n") if highlights_text else [],
        }
    out = {col: (json.loads(text[col]) if text.get(col) else []) for col in _WIDE[scope]}
    out["updated_by"] = updated_by or ""
    out["updated_at"] = updated_at or ""
    return out


def _get_wide(scope, month):
    with rc.cursor() as cur:
        rows = cur.execute(_WIDE_SELECT, (scope, month)).fetchall()
    return _decode_wide(scope, rows)


def _write_wide(scope, month, make, updated_by):
    """One transaction: bump, lock the stored rows, values = make(the v1
    get_* result or None) as {column: text}, upsert one row per column."""
    _fits("report_month", month, 7, nullable=False)
    cols = _WIDE[scope]
    with rc.tx() as cur:
        _ver.bump(cur)
        stored = _decode_wide(scope, cur.execute(_WIDE_SELECT + " FOR UPDATE", (scope, month)).fetchall())
        values = make(stored)
        for col in cols:
            _fits(col, values[col], _TEXT_MAX, nbytes=True)
        _fits("updated_by", updated_by, 190)
        tuples = ", ".join(["(%s, %s, %s, %s, %s, NOW())"] * len(cols))
        cur.execute(
            f"INSERT INTO report_text (scope, period, block_key, text, updated_by, updated_at) VALUES {tuples} "
            "AS new ON DUPLICATE KEY UPDATE text = new.text, updated_by = new.updated_by, "
            "updated_at = new.updated_at",
            [v for col in cols for v in (scope, month, col, values[col], updated_by)])


def _page3_values(production_narrative, highlights):
    return {"production_narrative": production_narrative or "", "highlights": "\n".join(highlights or [])}


def _list_values(scope, lists):
    return {col: json.dumps(lists[col] or []) for col in _WIDE[scope]}


def get_page3_narrative(month: str) -> Optional[dict]:
    """Returns the saved Page 3 Production Narrative + Highlights for a month,
    or None if nothing has ever been saved (caller should keep whatever
    default/computed value it already has)."""
    return _get_wide("page3_narrative", month)


def save_page3_narrative(month: str, production_narrative: str, highlights: List[str]):
    """Saves/updates Page 3's Production Narrative + Highlights, keyed only by
    report_month — independent of page_configs so it never risks touching
    the other 34 pages' saved data for the month."""
    _write_wide("page3_narrative", month, lambda _stored: _page3_values(production_narrative, highlights), None)


def get_key_highlights_narrative(month: str) -> Optional[dict]:
    """Returns the saved Key Highlights & Variances narrative (Major
    Achievements / Major Shortfalls / Focus Areas Going Forward) for a
    month, or None if nothing has ever been saved for it — the report page
    shows empty sections in that case rather than inventing text."""
    return _get_wide("key_highlights", month)


def save_key_highlights_narrative(month: str, achievements: list, shortfalls: list,
                                   focus_areas: list, updated_by: str = ""):
    """Saves/updates the Key Highlights & Variances narrative for a month,
    keyed only by report_month — independent of page_configs, same as
    save_page3_narrative above."""
    lists = {"achievements": achievements, "shortfalls": shortfalls, "focus_areas": focus_areas}
    _write_wide("key_highlights", month, lambda _stored: _list_values("key_highlights", lists), updated_by or "")


def get_steel_sales_highlights(month: str) -> Optional[dict]:
    """Saved Steel Sales Performance bullets (report-month + YTD lists) for
    a month, or None if nothing has ever been saved for it — the report
    page shows empty sections in that case rather than inventing text."""
    return _get_wide("steel_sales", month)


def save_steel_sales_highlights(month: str, month_items: list, ytd_items: list, updated_by: str = ""):
    """Saves/updates the Steel Sales Performance bullets for a month, keyed
    only by report_month — independent of page_configs, same as
    save_key_highlights_narrative above."""
    lists = {"month_items": month_items, "ytd_items": ytd_items}
    _write_wide("steel_sales", month, lambda _stored: _list_values("steel_sales", lists), updated_by or "")


# ── notes: rail_note / ss_phys_note ───────────────────────────────────────────

_NOTE_SELECT = ("SELECT seq, text FROM report_text WHERE scope = %s AND period = %s AND block_key = 'note' "
                "ORDER BY seq")
_INT_MIN, _INT_MAX = -2 ** 31, 2 ** 31 - 1


def _get_note_rows(scope, period):
    with rc.cursor() as cur:
        rows = cur.execute(_NOTE_SELECT, (scope, period)).fetchall()
    return [(so, t) for so, t in rows]


def _replace_notes(scope, period, make):
    """One transaction: bump, lock the stored notes, rows = make([(sort_order,
    text), ...]) as [{sort_order, note_text}], then v1's replace: delete
    every note of the period and insert each non-blank row (each checked
    in v1's order: sort_order range, note_text length, duplicate key)."""
    with rc.tx() as cur:
        _ver.bump(cur)
        stored = [(so, t) for so, t in cur.execute(_NOTE_SELECT + " FOR UPDATE", (scope, period)).fetchall()]
        rows = make(stored)
        cur.execute("DELETE FROM report_text WHERE scope = %s AND period = %s", (scope, period))
        seen = set()
        for r in rows:
            text = (r.get("note_text") or "").strip()
            if not text:
                continue
            so = int(r.get("sort_order") or 0)
            if scope == "ss_phys_note":
                _fits("financial_year", period, 7, nullable=False)
            _in_range("sort_order", so, _INT_MIN, _INT_MAX)
            _fits("note_text", text, 500)
            if so in seen:
                key = f"{period}-{so}" if scope == "ss_phys_note" else f"{so}"
                table = "special_steel_phys_note" if scope == "ss_phys_note" else "rail_prod_despatch_note"
                raise rc.IntegrityError(1062, f"Duplicate entry '{key}' for key '{table}.PRIMARY'")
            seen.add(so)
            cur.execute("INSERT INTO report_text (scope, period, block_key, seq, text) "
                        "VALUES (%s, %s, 'note', %s, %s)", (scope, period, so, text))
        return len(rows)


def get_ss_phys_notes(financial_year):
    """-> [(sort_order, note_text), ...] ordered."""
    return _get_note_rows("ss_phys_note", financial_year)


def save_ss_phys_notes(financial_year, rows):
    """Replace every note for a FY with `rows`: {sort_order, note_text}."""
    return _replace_notes("ss_phys_note", financial_year, lambda _stored: rows)


def get_rail_report_notes() -> List[tuple]:
    """-> [(sort_order, note_text), ...] ordered."""
    return _get_note_rows("rail_note", "")


def save_rail_report_notes(rows: List[Dict[str, Any]]) -> int:
    """Replace every footer remark with `rows`: {sort_order, note_text}."""
    return _replace_notes("rail_note", "", lambda _stored: rows)


# ── board note ────────────────────────────────────────────────────────────────

def get_manual_text(fy: str, quarter: int) -> dict:
    """Return {(plant, field): text} for every non-empty row in this period."""
    with rc.cursor() as cur:
        rows = cur.execute(
            "SELECT plant_code, block_key, text FROM report_text WHERE scope = 'board_note' AND period = %s "
            "ORDER BY plant_code, block_key", (board_note_period(fy, quarter),)).fetchall()
    return {(plant, field): text for plant, field, text in rows if text}


def save_manual_text(fy: str, quarter: int, entries: list) -> int:
    """Upsert or delete each entry ({"plant", "field", "text"}). An empty
    (after strip) text deletes the row. Returns the count processed."""
    period = board_note_period(fy, quarter)
    with rc.tx() as cur:
        saved = 0
        _ver.bump(cur)
        for e in entries:
            plant = str(e.get("plant", "")).strip()
            field = str(e.get("field", "")).strip()
            text = str(e.get("text", "")).strip()
            if not plant or not field:
                continue
            if text:
                _fits("report_fy", fy, 7, nullable=False)
                _in_range("quarter", quarter, -128, 127)
                _fits("plant", plant, 16)
                _fits("field", field, 24)
                _fits("text", text, _TEXT_MAX, nbytes=True)
                if len(plant) > 8:
                    raise _keys.OutOfModelError(f"board note plant {plant!r}: v1 stored up to 16 characters, "
                                                f"the v2 plant master holds 8")
                if len(period) > 10:
                    raise _keys.OutOfModelError(f"board note period {period!r} is longer than 10 characters")
                _keys.ensure_plant(cur, plant, bump=False)
                cur.execute("""
                    INSERT INTO report_text (scope, period, block_key, plant_code, text)
                    VALUES ('board_note', %s, %s, %s, %s)
                    AS new ON DUPLICATE KEY UPDATE text = new.text
                """, (period, field, plant, text))
            else:
                cur.execute("DELETE FROM report_text WHERE scope = 'board_note' AND period = %s "
                            "AND plant_code = %s AND block_key = %s", (period, plant, field))
            saved += 1
    return saved


# ── secretary review ──────────────────────────────────────────────────────────

def get_texts(month: str) -> dict:
    with rc.cursor() as cur:
        rows = cur.execute("SELECT block_key, text FROM report_text WHERE scope = 'secretary_review' "
                           "AND period = %s ORDER BY block_key", (month,)).fetchall()
    return {k: (t or "") for k, t in rows}


def save_texts(month: str, texts: dict) -> int:
    now = _dt.datetime.now().replace(microsecond=0)     # v1: isoformat(timespec="seconds")
    with rc.tx() as cur:
        n = 0
        _ver.bump(cur)
        for key, text in texts.items():
            key = str(key).strip()
            if not key:
                continue
            text = str(text or "").strip()
            _fits("report_month", month, 7, nullable=False)
            _fits("block_key", key, 32)
            _fits("text", text, _TEXT_MAX, nbytes=True)
            cur.execute("""
                INSERT INTO report_text (scope, period, block_key, text, updated_at)
                VALUES ('secretary_review', %s, %s, %s, %s)
                AS new ON DUPLICATE KEY UPDATE text = new.text, updated_at = new.updated_at
            """, (month, key, text, now))
            n += 1
        return n


def delete_texts(month: str, keys) -> int:
    """Drop the saved rows for `keys`, so those blocks follow the DB default
    again. Returns the number of rows removed."""
    keys = [str(k).strip() for k in keys if str(k).strip()]
    if not keys:
        return 0
    with rc.tx() as cur:
        phs = ",".join("%s" for _ in keys)
        _ver.bump(cur)
        cur.execute(f"DELETE FROM report_text WHERE scope = 'secretary_review' AND period = %s "
                    f"AND block_key IN ({phs})", [month] + keys)
        return cur.rowcount


def latest_saved_before(block_key: str, month: str, window: list):
    candidates = sorted(m for m in window if m < month)
    if not candidates:
        return None
    with rc.cursor() as cur:
        phs = ",".join("%s" for _ in candidates)
        row = cur.execute(
            f"SELECT text FROM report_text WHERE scope = 'secretary_review' AND block_key = %s "
            f"AND period IN ({phs}) ORDER BY period DESC LIMIT 1",
            [block_key] + candidates).fetchone()
    return row[0] if row else None


# ── Named queries (v1: moved verbatim from main.py / page_*.py) ──────────────

def page3_narrative_any_row(report_month):
    """True when page3_narrative has a non-blank narrative or highlights for
    the month. page_missing_data."""
    with rc.cursor() as cur:
        cur.execute("SELECT 1 FROM report_text WHERE scope = 'page3_narrative' AND period = %s "
                    "AND COALESCE(text, '') != ''", [report_month])
        return bool(cur.fetchall())


def upsert_sail_sales_note(cur, month, note):
    """Upsert the Table A footnote on the caller's cursor; the caller commits.
    main POST /api/sail-1page/confirm."""
    _fits("report_month", month, 7, nullable=False)
    _fits("note", note, _TEXT_MAX, nbytes=True)
    _ver.bump(cur)
    cur.execute("""
                INSERT INTO report_text (scope, period, block_key, text)
                VALUES ('sail_sales_note', %s, 'note', %s)
                AS new ON DUPLICATE KEY UPDATE text = new.text
            """, (month, note))


def sail_sales_note_row(cur, month):
    """fetchone() of (note,) for the month, or None.
    page_one_page_report._sales_note."""
    cur.execute("SELECT text AS note FROM report_text WHERE scope = 'sail_sales_note' AND period = %s "
                "AND block_key = 'note'", (month,))
    return cur.fetchone()


_DO_FROM = ("FROM report_text rt JOIN item i ON i.item_id = rt.item_id "
            "WHERE rt.scope = 'do_letter' AND rt.period = %s AND rt.block_key = 'remark'")


def do_letter_remark_rows(cur, month):
    """fetchall() of (item_name, plant_name, remark) for the month.
    main GET /api/do-letter/remarks."""
    cur.execute(
            f"SELECT i.item_name, rt.plant_code AS plant_name, rt.text AS remark {_DO_FROM} "
            f"ORDER BY {_ITEM_CI}, rt.plant_code",
            (month,),
        )
    return cur.fetchall()


def do_letter_item_remark_rows(cur, report_month, item_name):
    """fetchall() of (plant_name, remark) for one item.
    page_do_letter._fetch_remarks."""
    cur.execute(
        f"SELECT rt.plant_code AS plant_name, rt.text AS remark {_DO_FROM} AND {_ITEM_CI} = %s "
        "ORDER BY rt.plant_code",
        (report_month, item_name),
    )
    return cur.fetchall()


def upsert_do_letter_remark(cur, report_month, item_name, plant_name, remark):
    """Upsert one remark on the caller's cursor; the caller commits.
    main POST /api/do-letter/remarks."""
    _fits("report_month", report_month, 7, nullable=False)
    _fits("item_name", item_name, 32, nullable=False)
    _fits("plant_name", plant_name, 8, nullable=False)
    _fits("remark", remark, _TEXT_MAX, nbytes=True)
    _ver.bump(cur)
    _keys.ensure_plant(cur, plant_name, bump=False)
    stored = cur.execute(f"SELECT rt.item_id {_DO_FROM} AND rt.plant_code = %s AND {_ITEM_CI} = %s "
                         "FOR UPDATE", (report_month, plant_name, item_name)).fetchone()
    item_id = stored[0] if stored is not None else _item_id_for_write(cur, item_name, bump=False)
    cur.execute("""
                    INSERT INTO report_text (scope, period, block_key, plant_code, item_id, text)
                    VALUES ('do_letter', %s, 'remark', %s, %s, %s)
                    AS new ON DUPLICATE KEY UPDATE text = new.text
                """, (report_month, plant_name, item_id, remark))


def delete_do_letter_remark(cur, report_month, item_name, plant_name):
    """Delete one remark on the caller's cursor; the caller commits.
    main POST /api/do-letter/remarks (empty remark)."""
    _ver.bump(cur)
    cur.execute(
                    f"DELETE rt {_DO_FROM} AND rt.plant_code = %s AND {_ITEM_CI} = %s",
                    (report_month, plant_name, item_name),
                )


# ── get / put: the uniform text interface ────────────────────────────────────
# (see repo/text.py for the scope map; the same rules hold here)

# board_note's fields (re-exported as board_note_manual_text.FIELDS).
BOARD_NOTE_FIELDS = ("additional_highlights", "why_narrative")

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
    def make(stored):
        notes = {so: t for so, t in stored}
        if text:
            notes[sort_order] = text
        else:
            notes.pop(sort_order, None)
        return [{"sort_order": so, "note_text": t} for so, t in sorted(notes.items())]
    _replace_notes(scope, "" if scope == "rail_note" else period, make)


def _put_page3(period, block_key, text):
    def make(stored):
        saved = stored or {"production_narrative": "", "highlights": []}
        if block_key == "highlights":
            saved["highlights"] = text.split("\n") if text else []
        else:
            saved["production_narrative"] = text
        return _page3_values(saved["production_narrative"], saved["highlights"])
    _write_wide("page3_narrative", period, make, None)


def _put_list(scope, period, block_key, text, user):
    def make(stored):
        saved = stored or {col: [] for col in _WIDE[scope]}
        saved[block_key] = _as_list(text)
        return _list_values(scope, saved)
    _write_wide(scope, period, make, user or "")


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
    """Save one block's text (see the map in repo/text.py for each scope's
    rules). Raises ValueError for an unknown scope / block_key, or when
    board_note has no `plant` or do_letter lacks `plant` or `item`."""
    _check(scope, block_key)
    _check_keys(scope, plant, item)
    text = "" if text is None else str(text)
    if scope == "page3_narrative":
        _put_page3(period, block_key, text)
    elif scope in ("key_highlights", "steel_sales"):
        _put_list(scope, period, block_key, text, user)
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
