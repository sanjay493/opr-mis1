"""v1 vs v2 equivalence of repo.text (Task 7d).

The same narrative data is seeded into the v1 schema (the 9 v1 tables) and
the v2 schema (report_text, through repo.v2codec as the migration loads
it), covering all 9 scopes with non-empty data and NULL vs '' vs absent.
Every write function runs through _v1_frozen.text on v1 and repo.text (v2) on v2;
after each step both sides must agree on

  * every read function, called through each side's own module (the
    cursor helpers on tuple and Row cursors), compared in the oracle's
    canonical form, so order, key names and types count; this includes the
    reads the oracle never saw called (get, get_page3_narrative);
  * the stored data: each v1 table's rows against report_text decoded back
    to v1 rows (repo.v2codec.decode_text_rows), so the exact stored text
    (JSON list text, newline-joined highlights, '' vs NULL) and the
    timestamps count: updated_at strings are equal, except those written
    by NOW() during the test, which must be in v1's 'YYYY-MM-DD HH:MM:SS'
    form and within two minutes of each other;
  * the outcome: the return value, or the exception's type and args.
"""
import datetime as dtmod
import re
import types

import pytest

import dbengine
from repo import conn as rc
from _v1_frozen import text as t1
from repo import _keys
from repo import text as t2
from repo.v2codec import TEXT_SCOPES, decode_text_rows, v1_text_columns
from tools import repo_oracle as ro

ROW = dbengine.Row
MONTHS = ["2025-03", "2025-04", "2025-05", "2025-06", "2025-07", "2099-01"]
FYS = ["2024-25", "2025-26", "2026-27"]
BOARD = [("2025-26", 1), ("2025-26", 2), ("2025-26", 3), ("2024-25", 1)]
SR_KEYS = ["hl_SAIL", "hl_BSP", "delay_fs", "cr_BSP_cur", "bd_ISP_MILL"]
ITEMS = ["Crude Steel", "crude steel", "Finished Steel", "Saleable Steel"]
PLANTS = ["BSP", "bsp", "DSP", "ASP", "RSP", "XYZ"]

SEED = {
    "page3_narrative": [
        {"report_month": "2025-04", "production_narrative": "Narr A", "highlights": "h1\n\nh2",
         "updated_at": "2025-05-01 10:00:00"},
        {"report_month": "2025-05", "production_narrative": "", "highlights": "",
         "updated_at": "2025-06-01 00:00:00"},
        {"report_month": "2025-06", "production_narrative": None, "highlights": "only highlights",
         "updated_at": None},
    ],
    "key_highlights": [
        {"report_month": "2025-04", "achievements": '["a1", "a2"]', "shortfalls": None, "focus_areas": "",
         "updated_by": "u@x", "updated_at": "2025-05-02 11:12:13"},
        # not json.dumps' spelling: a put to another block re-dumps it, as v1 did
        {"report_month": "2025-05", "achievements": '["x","y"]', "shortfalls": '["s"]',
         "focus_areas": '["f\\u00e9"]', "updated_by": None, "updated_at": None},
    ],
    "steel_sales": [
        {"report_month": "2025-04", "month_items": '["m1", "m2"]', "ytd_items": "[]",
         "updated_by": "", "updated_at": "2025-05-03 01:02:03"},
        {"report_month": "2025-06", "month_items": None, "ytd_items": '["y"]',
         "updated_by": "seed:x.pdf", "updated_at": "2025-07-01 00:00:00"},
    ],
    "secretary_review": [
        {"report_month": "2025-04", "block_key": "hl_SAIL", "text": "SAIL text", "updated_at": "2025-05-01T09:00:00"},
        {"report_month": "2025-04", "block_key": "hl_BSP", "text": "", "updated_at": "2025-05-01T09:00:01"},
        {"report_month": "2025-04", "block_key": "delay_fs", "text": None, "updated_at": None},
        {"report_month": "2025-03", "block_key": "hl_SAIL", "text": "older", "updated_at": "2025-04-01T09:00:00"},
        {"report_month": "2025-03", "block_key": "cr_BSP_cur", "text": None, "updated_at": None},
        {"report_month": "2025-05", "block_key": "bd_ISP_MILL", "text": "bd", "updated_at": "2025-06-01T09:00:00"},
    ],
    "board_note": [
        {"report_fy": "2025-26", "quarter": 1, "plant": "BSP", "field": "additional_highlights", "text": "bh"},
        {"report_fy": "2025-26", "quarter": 1, "plant": "DSP", "field": "why_narrative", "text": "dw"},
        {"report_fy": "2025-26", "quarter": 1, "plant": "ASP", "field": "why_narrative", "text": ""},
        {"report_fy": "2025-26", "quarter": 1, "plant": "BSP", "field": "why_narrative", "text": "bw"},
        {"report_fy": "2025-26", "quarter": 2, "plant": "BSP", "field": "why_narrative", "text": None},
        {"report_fy": "2024-25", "quarter": 1, "plant": "RSP", "field": "additional_highlights", "text": "old"},
    ],
    "do_letter": [
        {"report_month": "2025-04", "item_name": "Finished Steel", "plant_name": "DSP", "remark": "r2"},
        {"report_month": "2025-04", "item_name": "Crude Steel", "plant_name": "BSP", "remark": "r1"},
        {"report_month": "2025-04", "item_name": "Crude Steel", "plant_name": "ASP", "remark": ""},
        {"report_month": "2025-04", "item_name": "Crude Steel", "plant_name": "RSP", "remark": None},
        {"report_month": "2025-05", "item_name": "crude steel", "plant_name": "BSP", "remark": "lower"},
    ],
    "sail_sales_note": [
        {"report_month": "2025-04", "note": "Table A note"},
        {"report_month": "2025-05", "note": ""},
        {"report_month": "2025-06", "note": None},
    ],
    "rail_note": [
        {"sort_order": 3, "note_text": "r three"},
        {"sort_order": 1, "note_text": "r one"},
        {"sort_order": 2, "note_text": "r two"},
    ],
    "ss_phys_note": [
        {"financial_year": "2025-26", "sort_order": 2, "note_text": "p2"},
        {"financial_year": "2025-26", "sort_order": 1, "note_text": "p1"},
        {"financial_year": "2024-25", "sort_order": 1, "note_text": "old note"},
    ],
}

_SQL_FORM = re.compile(r"\d{4}-\d\d-\d\d \d\d:\d\d:\d\d")
FIXED_NOW = dtmod.datetime(2025, 8, 9, 10, 11, 12, 345678)


class _FixedDT(dtmod.datetime):
    @classmethod
    def now(cls, tz=None):
        return FIXED_NOW


@pytest.fixture
def seeded(dual, monkeypatch):
    for scope, rows in SEED.items():
        dual.seed_text(scope, rows)
    # secretary_review's updated_at: both sides see the same clock
    fake = types.SimpleNamespace(datetime=_FixedDT)
    monkeypatch.setattr(t1, "_dt", fake)
    monkeypatch.setattr(t2, "_dt", fake)
    return dual


def canon(v):
    return ro.dumps(ro.canonical(v))


def _cur_read(fn, row_factory):
    conn = dbengine.connect()
    conn.row_factory = row_factory
    try:
        return fn(conn.cursor())
    finally:
        conn.close()


def _reads(m):
    """Every read function of `m`, on the data of every seeded key."""
    out = {}
    for mo in MONTHS:
        out[("page3", mo)] = m.get_page3_narrative(mo)
        out[("kh", mo)] = _now_marked(m.get_key_highlights_narrative(mo))
        out[("ss", mo)] = _now_marked(m.get_steel_sales_highlights(mo))
        out[("texts", mo)] = m.get_texts(mo)
        out[("any", mo)] = m.page3_narrative_any_row(mo)
        for rf in (None, ROW):
            name = "row" if rf else "tuple"
            out[("do", mo, name)] = _cur_read(lambda c: m.do_letter_remark_rows(c, mo), rf)
            out[("sail", mo, name)] = _cur_read(lambda c: m.sail_sales_note_row(c, mo), rf)
            for it in ITEMS:
                out[("do_item", mo, it, name)] = _cur_read(lambda c: m.do_letter_item_remark_rows(c, mo, it), rf)
        for k in SR_KEYS[:3]:
            out[("latest", k, mo)] = m.latest_saved_before(k, mo, MONTHS)
    out["latest_empty"] = m.latest_saved_before("hl_SAIL", "2025-03", ["2025-04"])
    for fy, q in BOARD:
        out[("board", fy, q)] = m.get_manual_text(fy, q)
    for fy in FYS:
        out[("phys", fy)] = m.get_ss_phys_notes(fy)
    out["rail"] = m.get_rail_report_notes()
    # get(): every scope and block key
    for scope, (_, keys) in m.SCOPES.items():
        if scope in ("page3_narrative", "key_highlights", "steel_sales", "sail_sales_note"):
            for mo in MONTHS:
                for k in keys:
                    out[("get", scope, mo, k)] = m.get(scope, mo, k)
        elif scope == "secretary_review":
            for mo in ("2025-03", "2025-04", "2025-05"):
                for k in SR_KEYS:
                    out[("get", scope, mo, k)] = m.get(scope, mo, k)
        elif scope == "board_note":
            for period in ("2025-26:Q1", "2025-26:q2", "2025-26:Q3"):
                for k in keys:
                    for p in ("BSP", "bsp", "DSP", "ASP", "XYZ"):
                        out[("get", scope, period, k, p)] = m.get(scope, period, k, plant=p)
        elif scope == "do_letter":
            for mo in ("2025-04", "2025-06"):
                for p in ("BSP", "bsp", "DSP", "XYZ"):
                    for it in ("Crude Steel", "crude steel", "Saleable Steel"):
                        out[("get", scope, mo, p, it)] = m.get(scope, mo, "remark", plant=p, item=it)
        elif scope == "rail_note":
            for k in ("1", "2", "3", "4", "7"):
                out[("get", scope, k)] = m.get(scope, "ignored", k)
        else:
            for fy in FYS:
                for k in ("1", "2", "3", "7"):
                    out[("get", scope, fy, k)] = m.get(scope, fy, k)
    return {k: canon(v) for k, v in out.items()}


def _now_marked(saved):
    """updated_at written by NOW() during the test reads as '<now>' (the
    stored-data check holds it to v1's form and to the other side's value)."""
    if saved and _SQL_FORM.fullmatch(saved["updated_at"]):
        if abs((dtmod.datetime.now() - dtmod.datetime.fromisoformat(saved["updated_at"])).total_seconds()) < 600:
            saved = {**saved, "updated_at": "<now>"}
    return saved


_V2_KEYS = ("period", "block_key", "plant_code", "item_name", "seq", "text", "updated_by", "updated_at")


def _stored(dual):
    """{scope: sorted v1 rows} per side; v2 rows decoded by repo.v2codec."""
    s1, s2 = {}, {}
    for scope, spec in TEXT_SCOPES.items():
        cols = v1_text_columns(scope)
        s1[scope] = sorted((tuple(r) for r in dual.sql(1, f"SELECT {', '.join(cols)} FROM {spec['table']}")),
                           key=repr)
        rows = dual.sql(2, "SELECT rt.period, rt.block_key, rt.plant_code, i.item_name, rt.seq, rt.text, "
                           "rt.updated_by, rt.updated_at FROM report_text rt LEFT JOIN item i "
                           "ON i.item_id = rt.item_id WHERE rt.scope = %s", (scope,))
        decoded = decode_text_rows(scope, [dict(zip(_V2_KEYS, r)) for r in rows])
        s2[scope] = sorted((tuple(d[c] for c in cols) for d in decoded), key=repr)
    return s1, s2


def _fresh_now(a, b):
    """Both NOW() values written during the test, in v1's form."""
    if not (isinstance(a, str) and isinstance(b, str) and _SQL_FORM.fullmatch(a) and _SQL_FORM.fullmatch(b)):
        return False
    ta, tb = dtmod.datetime.fromisoformat(a), dtmod.datetime.fromisoformat(b)
    now = dtmod.datetime.now()
    return abs((ta - tb).total_seconds()) < 120 and abs((now - ta).total_seconds()) < 600


def _assert_same(dual):
    r1, r2 = dual.both(_reads, v1=t1, v2=t2)
    s1, s2 = _stored(dual)
    for scope in TEXT_SCOPES:
        a, b = s1[scope], s2[scope]
        assert len(a) == len(b), (scope, a, b)
        wide = TEXT_SCOPES[scope]["kind"] == "wide"
        if wide:            # updated_at is the last column; NOW() may differ by a second
            a = sorted(a, key=lambda r: repr(r[:-1]))
            b = sorted(b, key=lambda r: repr(r[:-1]))
        for x, y in zip(a, b):
            if wide and x[:-1] == y[:-1] and x[-1] != y[-1]:
                assert _fresh_now(x[-1], y[-1]), (scope, x, y)
            else:
                assert x == y, (scope, x, y)
    diff = [k for k in r1 if r1[k] != r2[k]]
    assert not diff, [(k, r1[k], r2[k]) for k in diff[:5]]
    # the NOW()-written rows share one timestamp per v1 row
    return r1


def _outcome(fn):
    try:
        return ("ok", canon(fn()))
    except Exception as e:      # noqa: BLE001
        return (type(e).__name__, canon(list(e.args)))


def _step(dual, fn):
    """fn(module) on both sides; same outcome, same reads, same stored data."""
    o1, o2 = dual.both(lambda m: _outcome(lambda: fn(m)), v1=t1, v2=t2)
    assert o1 == o2, (o1, o2)
    _assert_same(dual)
    return o1


def _on_tx(fn):
    """fn(module, cursor) on a repo.conn.tx() cursor (committed)."""
    def go(m):
        with rc.tx() as cur:
            return fn(m, cur)
    return go


def _on_dbengine(fn):
    """fn(module, cursor) on a db.connect() cursor, then commit."""
    def go(m):
        conn = dbengine.connect()
        try:
            r = fn(m, conn.cursor())
            conn.commit()
            return r
        finally:
            conn.close()
    return go


# ── the seed itself ─────────────────────────────────────────────────────────

def test_seeded_reads_and_storage_agree(seeded):
    r = _assert_same(seeded)
    # the seed exercises what it claims to
    assert r[("page3", "2025-05")] != canon(None) and r[("get", "sail_sales_note", "2025-05", "note")] == canon(None)


# ── wide scopes ─────────────────────────────────────────────────────────────

def test_page3_writes(seeded):
    for fn in (lambda m: m.save_page3_narrative("2025-04", "New narr", ["a", "", "b"]),     # update
               lambda m: m.save_page3_narrative("2025-07", None, None),                  # new, empty
               lambda m: m.save_page3_narrative("2025-06", "", []),                      # NULL -> ''
               lambda m: m.put("page3_narrative", "2025-05", "highlights", "x\ny", "u"),
               lambda m: m.put("page3_narrative", "2025-06", "production_narrative", None, "u"),
               lambda m: m.put("page3_narrative", "2025-03", "highlights", "", None),     # new month via put
               lambda m: m.save_page3_narrative("2025-031", "x", []),                    # v1 CHAR(7)
               lambda m: m.save_page3_narrative("2025-08", "é" * 32768, [])):            # TEXT bytes
        _step(seeded, fn)


def test_key_highlights_and_steel_sales_writes(seeded):
    for fn in (lambda m: m.save_key_highlights_narrative("2025-04", ["n1"], [], None, "me"),
               lambda m: m.save_key_highlights_narrative("2025-07", ["é"], ["s"], ["f"]),
               lambda m: m.put("key_highlights", "2025-05", "shortfalls", '["j1", "j2"]', "putter"),
               lambda m: m.put("key_highlights", "2025-05", "focus_areas", "line 1\n\n  line 2 ", None),
               lambda m: m.put("key_highlights", "2025-06", "achievements", "", "p"),
               lambda m: m.put("key_highlights", "2025-06", "achievements", '{"not": "a list"}', "p"),
               lambda m: m.save_steel_sales_highlights("2025-04", [], ["y1"], "s@x"),
               lambda m: m.save_steel_sales_highlights("2025-05", None, None),
               lambda m: m.put("steel_sales", "2025-06", "month_items", "m\nn", "q"),
               lambda m: m.put("steel_sales", "2025-03", "ytd_items", "[1, 2.5]", ""),
               lambda m: m.save_steel_sales_highlights("2025-07", [], [], "x" * 191)):    # updated_by 190
        _step(seeded, fn)


# ── notes ───────────────────────────────────────────────────────────────────

def test_note_writes(seeded):
    for fn in (lambda m: m.save_ss_phys_notes("2025-26", [{"sort_order": "3", "note_text": " three "},
                                                          {"sort_order": 1, "note_text": "one"},
                                                          {"sort_order": 2, "note_text": "   "},
                                                          {"note_text": "zero"}]),
               lambda m: m.save_ss_phys_notes("2026-27", []),
               lambda m: m.save_ss_phys_notes("2026-27", [{"sort_order": 1, "note_text": "a"},
                                                          {"sort_order": 1, "note_text": "dup"}]),
               lambda m: m.save_ss_phys_notes("2026-27", [{"sort_order": 1, "note_text": "x" * 501}]),
               lambda m: m.save_ss_phys_notes("2026-270", [{"sort_order": 1, "note_text": "a"}]),
               lambda m: m.save_ss_phys_notes("2026-270", [{"sort_order": 1, "note_text": " "}]),
               lambda m: m.save_ss_phys_notes("2026-27", [{"sort_order": 2 ** 31, "note_text": "big"}]),
               lambda m: m.put("ss_phys_note", "2024-25", "2", "second", "u"),
               lambda m: m.put("ss_phys_note", "2024-25", "1", "", "u"),                # delete
               lambda m: m.put("ss_phys_note", "2026-27", "5", " five ", "u"),          # new fy
               lambda m: m.save_rail_report_notes([{"sort_order": 2, "note_text": "two"},
                                                   {"sort_order": 0, "note_text": ""},
                                                   {"sort_order": 5, "note_text": "five"}]),
               lambda m: m.save_rail_report_notes([{"sort_order": 1, "note_text": "a"},
                                                   {"sort_order": "1", "note_text": "b"}]),
               lambda m: m.put("rail_note", "whatever", "1", "one again", None),
               lambda m: m.put("rail_note", "", "2", "  ", None),
               lambda m: m.save_rail_report_notes([])):
        _step(seeded, fn)


# ── board note ──────────────────────────────────────────────────────────────

def test_board_note_writes(seeded):
    for fn in (lambda m: m.save_manual_text("2025-26", 1, [
                   {"plant": "bsp", "field": "additional_highlights", "text": " upd "},     # ai_ci variant
                   {"plant": "DSP", "field": "why_narrative", "text": "  "},                # delete
                   {"plant": "", "field": "why_narrative", "text": "skipped"},
                   {"plant": "RSP", "field": "", "text": "skipped"},
                   {"plant": "XYZ", "field": "why_narrative", "text": "new plant"},
                   {"plant": "ISP", "field": "free_field", "text": "any field"}]),
               lambda m: m.save_manual_text("2025-26", "3", [{"plant": "BSP", "field": "why_narrative", "text": "q3"}]),
               lambda m: m.save_manual_text("2025-26", 1, [{"plant": "BSP", "field": "f" * 25, "text": "x"}]),
               lambda m: m.save_manual_text("2025-260", 1, [{"plant": "BSP", "field": "f", "text": "x"}]),
               lambda m: m.save_manual_text("2025-26", 1, [{"plant": "P" * 17, "field": "f", "text": "x"}]),
               lambda m: m.save_manual_text("2025-26", 1, [{"plant": "P" * 17, "field": "f", "text": ""}]),
               lambda m: m.put("board_note", "2025-26:q1", "why_narrative", "via put", "u", plant="ASP"),
               lambda m: m.put("board_note", "2025-26:Q1", "why_narrative", "", "u", plant="BSP"),
               lambda m: m.put("board_note", "2026-27:Q4", "additional_highlights", "n", "u", plant="VISL")):
        _step(seeded, fn)


def test_months_and_fys_with_trailing_spaces(seeded):
    """Task 7e1 (_keys.fit_month / fit_fy): v1 stored the value cut to
    CHAR(7) (its ON DUPLICATE KEY updated the stored row) while its own
    reads and DELETEs with the raw value matched nothing: a put() merges
    onto nothing, a note replace deletes nothing and clashes (1062) with
    the stored notes, a board-note blank deletes nothing."""
    for fn in (lambda m: m.save_page3_narrative("2025-04 ", "spaced", ["s"]),
               lambda m: m.put("page3_narrative", "2025-06  ", "highlights", "h only", "u"),
               lambda m: m.put("key_highlights", "2025-04 ", "shortfalls", '["k"]', "u"),
               lambda m: m.save_steel_sales_highlights("2025-06 ", ["m"], None, "s@x"),
               lambda m: m.save_texts("2025-04 ", {"hl_SAIL": "sp", "delay_fs": "d"}),
               lambda m: m.delete_texts("2025-04 ", ["hl_SAIL"]),                     # matches nothing
               lambda m: m.put("secretary_review", "2025-05 ", "bd_ISP_MILL", "p", "u"),
               lambda m: m.save_ss_phys_notes("2025-26 ", [{"sort_order": 1, "note_text": "clash"}]),
               lambda m: m.save_ss_phys_notes("2025-26 ", [{"sort_order": 5, "note_text": "added"}]),
               lambda m: m.put("ss_phys_note", "2025-26 ", "6", "via put", "u"),
               lambda m: m.save_manual_text("2025-26 ", 1, [
                   {"plant": "BSP", "field": "why_narrative", "text": "upd"},
                   {"plant": "DSP", "field": "why_narrative", "text": ""}]),       # delete matches nothing
               lambda m: m.save_manual_text("2025-26", "x", []),                  # nothing to do: 0
               lambda m: m.save_manual_text("2025-26", "x", [{"plant": "BSP", "field": "f", "text": ""}]),
               _on_tx(lambda m, cur: m.upsert_do_letter_remark(cur, "2025-04 ", "crude steel", "BSP", "sp")),
               _on_tx(lambda m, cur: m.delete_do_letter_remark(cur, "2025-04 ", "Crude Steel", "DSP")),
               _on_tx(lambda m, cur: m.upsert_sail_sales_note(cur, "2025-05 ", "note sp")),
               lambda m: m.save_page3_narrative("2025-04 x", "too long", [])):         # 1406
        _step(seeded, fn)


def test_board_note_plant_longer_than_the_v2_master(seeded):
    """v1 board_note plant is VARCHAR(16), the v2 plant master holds 8: v1
    stores a 9..16-character plant, v2 refuses it before writing anything."""
    def fn(m):
        return m.save_manual_text("2025-26", 1, [{"plant": "LONGPLANT", "field": "why_narrative", "text": "x"}])
    with seeded.v1():
        assert fn(t1) == 1
    n = seeded.data_version(2)
    with seeded.v2():
        with pytest.raises(_keys.OutOfModelError):
            fn(t2)
    assert seeded.data_version(2) == n
    assert seeded.sql(2, "SELECT COUNT(*) FROM report_text WHERE plant_code = 'LONGPLAN'")[0][0] == 0


# ── secretary review ────────────────────────────────────────────────────────

def test_secretary_review_writes(seeded):
    for fn in (lambda m: m.save_texts("2025-04", {" hl_SAIL ": " new ", "": "skip", "  ": "skip",
                                                  "delay_fs": None, "HL_BSP": "ci variant", "new_key": 5}),
               lambda m: m.save_texts("2025-07", {}),
               lambda m: m.save_texts("2025-07", {"k" * 33: "x"}),
               lambda m: m.save_texts("2025-070", {"k": "x"}),
               lambda m: m.delete_texts("2025-04", [" hl_sail ", "", "nope", "delay_fs"]),
               lambda m: m.delete_texts("2025-04", ["", "  "]),
               lambda m: m.put("secretary_review", "2025-05", "hl_BSP", "via put", "u"),
               lambda m: m.put("secretary_review", "2025-03", "hl_SAIL", None, "u")):
        _step(seeded, fn)


# ── do letter / sail sales note (caller-cursor writers) ─────────────────────

def test_do_letter_writes(seeded):
    for fn in (_on_tx(lambda m, c: m.upsert_do_letter_remark(c, "2025-04", "CRUDE STEEL", "bsp", "upd")),
               _on_dbengine(lambda m, c: m.upsert_do_letter_remark(c, "2025-04", "Saleable Steel", "XYZ", "new")),
               _on_tx(lambda m, c: m.upsert_do_letter_remark(c, "2025-06", "crude steel", "DSP", "variant")),
               _on_tx(lambda m, c: m.upsert_do_letter_remark(c, "2025-06", "Crude Steel", "DSP", "keeps")),
               _on_tx(lambda m, c: m.upsert_do_letter_remark(c, "2025-06", "Finished Steel", "ASP", None)),
               _on_tx(lambda m, c: m.delete_do_letter_remark(c, "2025-04", "finished steel", "dsp")),
               _on_dbengine(lambda m, c: m.delete_do_letter_remark(c, "2025-04", "Nope", "BSP")),
               _on_tx(lambda m, c: m.upsert_do_letter_remark(c, "2025-04", "I" * 33, "BSP", "x")),
               _on_tx(lambda m, c: m.upsert_do_letter_remark(c, "2025-04", "Crude Steel", "P" * 9, "x")),
               _on_tx(lambda m, c: m.upsert_do_letter_remark(c, None, "Crude Steel", "BSP", "x")),
               lambda m: m.put("do_letter", "2025-05", "remark", "  via put ", "u", plant="DSP", item="Crude Steel"),
               lambda m: m.put("do_letter", "2025-05", "remark", " ", "u", plant="BSP", item="CRUDE steel")):
        _step(seeded, fn)


def test_sail_sales_note_writes(seeded):
    for fn in (_on_tx(lambda m, c: m.upsert_sail_sales_note(c, "2025-04", "changed")),
               _on_dbengine(lambda m, c: m.upsert_sail_sales_note(c, "2025-07", None)),
               _on_tx(lambda m, c: m.upsert_sail_sales_note(c, "2025-0700", "x")),
               lambda m: m.put("sail_sales_note", "2025-05", "note", "now set", "u"),
               lambda m: m.put("sail_sales_note", "2025-04", "note", "", "u"),        # '' stored, reads None
               lambda m: m.put("sail_sales_note", "2025-03", "note", None, "u")):
        _step(seeded, fn)


# ── put validation, bump, dry run ───────────────────────────────────────────

def test_put_validation_raises_before_writing(seeded):
    for fn in (lambda m: m.put("nope", "2025-04", "x", "t", "u"),
               lambda m: m.put("secretary_review", "2025-04", "not_a_block", "t", "u"),
               lambda m: m.put("board_note", "2025-26:Q1", "free_field", "t", "u", plant="BSP"),
               lambda m: m.put("board_note", "2025-26:Q1", "why_narrative", "t", "u"),
               lambda m: m.put("do_letter", "2025-04", "remark", "t", "u", plant="BSP"),
               lambda m: m.put("do_letter", "2025-04", "remark", "t", "u", item="Crude Steel"),
               lambda m: m.get("page3_narrative", "2025-04", "nope")):
        n1, n2 = seeded.data_version(1), seeded.data_version(2)
        o = _step(seeded, fn)
        assert o[0] == "ValueError"
        assert (seeded.data_version(1), seeded.data_version(2)) == (n1, n2)


V2_WRITES = [
    lambda: t2.save_page3_narrative("2025-04", "n", ["h"]),
    lambda: t2.save_key_highlights_narrative("2025-04", ["a"], [], []),
    lambda: t2.save_steel_sales_highlights("2025-04", ["m"], []),
    lambda: t2.save_ss_phys_notes("2025-26", [{"sort_order": 1, "note_text": "x"}]),
    lambda: t2.save_rail_report_notes([{"sort_order": 1, "note_text": "x"}]),
    lambda: t2.save_manual_text("2025-26", 1, [{"plant": "BSP", "field": "why_narrative", "text": "x"}]),
    lambda: t2.save_texts("2025-04", {"hl_SAIL": "x"}),
    lambda: t2.delete_texts("2025-04", ["hl_BSP"]),
    lambda: _on_tx(lambda m, c: m.upsert_sail_sales_note(c, "2025-04", "x"))(t2),
    lambda: _on_tx(lambda m, c: m.upsert_do_letter_remark(c, "2025-04", "Crude Steel", "BSP", "x"))(t2),
    lambda: _on_tx(lambda m, c: m.delete_do_letter_remark(c, "2025-04", "Crude Steel", "ASP"))(t2),
    lambda: t2.put("page3_narrative", "2025-04", "highlights", "p", "u"),
    lambda: t2.put("key_highlights", "2025-04", "shortfalls", "p", "u"),
    lambda: t2.put("steel_sales", "2025-04", "ytd_items", "p", "u"),
    lambda: t2.put("secretary_review", "2025-04", "hl_BSP", "p", "u"),
    lambda: t2.put("board_note", "2025-26:Q1", "why_narrative", "p", "u", plant="DSP"),
    lambda: t2.put("do_letter", "2025-04", "remark", "p", "u", plant="DSP", item="Finished Steel"),
    lambda: t2.put("sail_sales_note", "2025-04", "note", "p", "u"),
    lambda: t2.put("rail_note", "", "4", "p", "u"),
    lambda: t2.put("ss_phys_note", "2025-26", "4", "p", "u"),
]


def test_every_v2_write_bumps_and_a_dry_run_does_not(seeded):
    with seeded.v2():
        for step in V2_WRITES:
            n = seeded.data_version(2)
            step()
            assert seeded.data_version(2) > n
        before = _reads(t2)
        n = seeded.data_version(2)
        with rc.rollback_tx():
            t2.save_page3_narrative("2025-07", "dry", [])
            t2.save_manual_text("2025-26", 3, [{"plant": "NEWP", "field": "why_narrative", "text": "dry"}])
            _on_tx(lambda m, c: m.upsert_do_letter_remark(c, "2025-07", "Dry Item", "DRY", "x"))(t2)
            for step in V2_WRITES:
                step()
            assert _reads(t2) != before                  # the dry run sees its own writes
        assert seeded.data_version(2) == n
        assert _reads(t2) == before
    assert seeded.sql(2, "SELECT COUNT(*) FROM plant WHERE plant_code IN ('NEWP', 'DRY')")[0][0] == 0
    assert seeded.sql(2, "SELECT COUNT(*) FROM item WHERE item_name = 'Dry Item'")[0][0] == 0


def test_writes_on_a_caller_cursor_roll_back_with_it(seeded):
    """The caller-cursor writers join the caller's transaction (v1 and v2)."""
    def go(m):
        conn = dbengine.connect()
        try:
            cur = conn.cursor()
            m.upsert_sail_sales_note(cur, "2025-04", "rolled back")
            m.upsert_do_letter_remark(cur, "2025-04", "New Item", "NEWP", "rolled back")
            m.delete_do_letter_remark(cur, "2025-04", "Crude Steel", "BSP")
            conn.rollback()
        finally:
            conn.close()
    seeded.both(go, v1=t1, v2=t2)
    _assert_same(seeded)
    assert seeded.sql(2, "SELECT COUNT(*) FROM plant WHERE plant_code = 'NEWP'")[0][0] == 0
