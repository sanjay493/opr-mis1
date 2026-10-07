import datetime as dt

import page_secretary_review_texts as t


def _ev(start, end, hours=None, ongoing=0, cause="x", plant="BSP", ut="BF", unit="BF-4"):
    return {"plant": plant, "unit_type": ut, "unit_name": unit, "start_ts": start, "end_ts": end,
            "is_ongoing": ongoing, "cause": cause, "hours_lost_override": hours}


def test_event_hours_clipped_to_month():
    assert t.event_hours(_ev("2026-08-31 12:00", "2026-09-01 12:00"), "2026-09") == 12
    assert t.event_hours(_ev("2026-09-30 00:00", "2026-10-02 00:00"), "2026-09") == 24
    assert t.event_hours(_ev("2026-09-29 00:00", None, ongoing=1), "2026-09") == 48
    assert t.event_hours(_ev("2026-09-01", "2026-09-01", hours=5.0), "2026-09") == 5
    assert t.event_hours(_ev("2026-08-01", "2026-08-01", hours=5.0), "2026-09") == 0


def test_clean_cause():
    raw = ("BF-2: Planned S/D (Shot creting & stove-2.2 comp. change) w.e.f. 1215 hrs (2.9.26) "
           "to 2355 hrs (14\ntuy. in oprns.)")
    assert t.clean_cause(raw, "BF-2") == "Planned S/D (Shot creting & stove-2.2 comp. change)"
    assert len(t.clean_cause("a" * 200, "BF-1")) == 91


def test_unit_summaries_threshold_and_top_cause():
    evs = [_ev("2026-09-01 00:00", "2026-09-02 00:00", cause="short"),
           _ev("2026-09-10 00:00", "2026-09-12 00:00", cause="long one"),
           _ev("2026-09-05 00:00", "2026-09-05 10:00", unit="BF-7")]
    s = t.unit_summaries(evs, "2026-09")
    assert len(s) == 1
    assert s[0]["unit_name"] == "BF-4" and s[0]["hours"] == 72 and s[0]["cause"] == "long one"


def test_delay_and_bd_text():
    s = [{"plant": "BSP", "unit_type": "BF", "unit_name": "BF-4", "hours": 360, "cause": "BLT chute changing"},
         {"plant": "BSP", "unit_type": "MILL", "unit_name": "RSM", "hours": 96, "cause": ""}]
    assert t.delay_text(s, ("BF", "COKE", "SINTER", "SMS"), "Sep’26") == "BSP (Sep’26):\nBF-4: BLT chute changing – 15 days"
    assert t.bd_group_text(s, "BSP", "MILL") == "RSM – 4 days"
    assert t.bd_group_text(s, "BSP", "SMS") == ""


def test_cr_line_completed_and_span():
    row = {"shop": "SMS2", "equipment": "Conv-A", "actual_start": "2026-06-07",
           "actual_end": "2026-08-07", "actual_ongoing": 0}
    assert t.cr_line(row, dt.date(2026, 9, 30)) == "SMS2 Conv-A (62 days in Jun-Aug’26)"


def test_cr_line_ongoing_clipped():
    row = {"shop": "BF", "equipment": "No-2", "actual_start": "2026-09-20",
           "actual_end": "2026-10-10", "actual_ongoing": 0}
    assert t.cr_line(row, dt.date(2026, 9, 30)) == "BF No-2 (11 days in Sep’26, contd.)"
    row2 = dict(row, actual_end=None, actual_ongoing=1)
    assert t.cr_line(row2, dt.date(2026, 9, 30)) == "BF No-2 (11 days in Sep’26, contd.)"


def test_effective_texts_prefers_saved_including_blank(monkeypatch):
    monkeypatch.setattr(t, "default_texts", lambda m, keys=None: {k: "DB " + k for k, _, _ in t.BLOCKS})
    monkeypatch.setattr(t.srt, "get_texts", lambda m: {"hl_DSP": "", "hl_SAIL": "mine"})
    eff = t.effective_texts("2026-09")
    assert eff["hl_DSP"] == {"text": "", "saved": True}
    assert eff["hl_SAIL"] == {"text": "mine", "saved": True}
    assert eff["hl_BSP"] == {"text": "DB hl_BSP", "saved": False}
    assert len(eff) == 30


def test_unit_summaries_merges_overlapping_events():
    evs = [_ev("2026-09-10 00:00", "2026-09-12 00:00", cause="first"),
           _ev("2026-09-11 00:00", "2026-09-13 00:00", cause="second")]
    s = t.unit_summaries(evs, "2026-09")
    assert len(s) == 1 and s[0]["hours"] == 72


def test_unit_summaries_caps_at_month_hours():
    evs = [_ev("2026-08-20 00:00", None, ongoing=1, cause="a"),
           _ev("2026-09-01 00:00", None, ongoing=1, cause="b"),
           _ev("2026-09-05 00:00", "2026-09-20 00:00", cause="c"),
           _ev("2026-09-02", "2026-09-02", hours=40.0, cause="d")]
    s = t.unit_summaries(evs, "2026-09")
    assert len(s) == 1 and s[0]["hours"] == 30 * 24


def test_unit_line_strips_shop_prefix():
    a = {"unit_name": "Shop: BF", "cause": "relining", "hours": 72}
    assert t._unit_line(a) == "BF: relining – 3 days"
    assert t._unit_line(dict(a, unit_name="  shop :SMS-2", cause="")) == "SMS-2 – 3 days"
    assert t._unit_line(dict(a, unit_name="Workshop: X")) == "Workshop: X: relining – 3 days"


class _FakeConn:
    def cursor(self):
        return None

    def close(self):
        pass


def _kind_spies(monkeypatch):
    calls = []

    def spy(kind, prefix):
        def fn(cur, month, labels):
            calls.append(kind)
            return {k: kind for k, _, _ in t.BLOCKS if k.startswith(prefix)}
        return fn

    monkeypatch.setattr(t.db, "connect", lambda: _FakeConn())
    monkeypatch.setattr(t, "_hl_texts", spy("hl", ("hl_",)))
    monkeypatch.setattr(t, "_bd_texts", spy("bd", ("delay_", "bd_")))
    monkeypatch.setattr(t, "_cr_texts", spy("cr", ("cr_",)))
    return calls


def test_default_text_computes_only_its_kind(monkeypatch):
    calls = _kind_spies(monkeypatch)
    assert t.default_text("2026-09", "cr_BSP_prev") == "cr"
    assert calls == ["cr"]
    calls.clear()
    assert t.default_text("2026-09", "delay_fs") == "bd"
    assert calls == ["bd"]


def test_default_texts_all_keys(monkeypatch):
    calls = _kind_spies(monkeypatch)
    out = t.default_texts("2026-09")
    assert len(out) == 30 and sorted(calls) == ["bd", "cr", "hl"]
    assert out["hl_SAIL"] == "hl" and out["bd_ISP_MILL"] == "bd" and out["cr_ISP_cur"] == "cr"


def test_effective_texts_skips_defaults_when_all_saved(monkeypatch):
    calls = _kind_spies(monkeypatch)
    monkeypatch.setattr(t.srt, "get_texts", lambda m: {"hl_SAIL": "mine", "cr_BSP_cur": ""})
    assert t.effective_texts("2026-09", ["hl_SAIL", "cr_BSP_cur"]) == {
        "hl_SAIL": {"text": "mine", "saved": True}, "cr_BSP_cur": {"text": "", "saved": True}}
    assert calls == []
    eff = t.effective_texts("2026-09", ["hl_SAIL", "hl_BSP"])
    assert eff == {"hl_SAIL": {"text": "mine", "saved": True}, "hl_BSP": {"text": "hl", "saved": False}}
    assert calls == ["hl"]
