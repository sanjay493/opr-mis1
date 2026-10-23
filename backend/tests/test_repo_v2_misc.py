"""v1 vs v2 equivalence of repo.misc (Task 7e2).

The same rows are seeded into v1's tables and v2's (as the migration loads
them: units and items by name, timestamps through repo.v2codec, the BF
*_at_plain flags). Every write runs through repo.misc on v1 and
repo.v2.misc on v2 with datetime.now() frozen; after each step both sides
must agree on the outcome (result, or exception type and args), the
activity-log entries, every read of the group (canonical form) and the
stored rows (v2 rendered back to v1's columns and strings).
"""
import datetime as dt

import pytest

import dbengine
from repo import conn as rc
from repo import misc as m1
from repo.v2 import misc as m2
from repo.v2._keys import OutOfModelError
from v2dual import FrozenNow, assert_same_reads, multiset, on_cursor, record_activity, run_step

NOW = dt.datetime(2026, 10, 23, 14, 30, 5, 250000)


@pytest.fixture
def base(dual, monkeypatch):
    FrozenNow(monkeypatch, m2, value=NOW)
    return dual


def _stepper(base, monkeypatch, reads, tables):
    acts = record_activity(monkeypatch)

    def go(fn):
        return run_step(base, m1, m2, fn, reads=reads, tables=tables, activity=acts)
    return go


def _conn(fn):
    def run(mod):
        conn = dbengine.connect()
        try:
            return fn(mod, conn)
        finally:
            conn.close()
    return run


def _cur(fn, commit=True):
    return on_cursor(lambda mod, cur: fn(mod, cur), commit=commit)


# ── market / macro ──────────────────────────────────────────────────────────

MARKET = [{"report_month": m, "series_code": s, "value": v} for m, s, v in [
    ("2026-04", "hrc_china", 520.5), ("2026-04", "ccs", None), ("2026-05", "hrc_china", 1e-3),
    ("2026-04", "a_first", 1.0)]]
MACRO = [{"report_month": m, "metric_code": s, "value": v} for m, s, v in [
    ("2026-04", "gdp", 7.1), ("2026-04", "cpi", 4.2), ("2026-05", "gdp", None)]]


def _market_reads(m):
    out = {}
    for months in ([], ["2026-04"], ["2026-05", "2026-04", "2099-01"], ["2026-04 ", "2026-06"]):
        out[("market", tuple(months))] = m.get_market_price_trend(months)
        out[("macro", tuple(months))] = m.get_macro_indicators(months)
    return out


def test_market_and_macro(base, monkeypatch):
    base.seed_simple("market_price_trend_monthly", MARKET)
    base.seed_simple("macro_indicators_monthly", MACRO)
    assert_same_reads(base, m1, m2, _market_reads)
    step = _stepper(base, monkeypatch, _market_reads, ("market_price_trend_monthly", "macro_indicators_monthly"))
    for fn in (
            lambda m: m.save_market_price_trend([{"report_month": "2026-04", "series_code": "hrc_china", "value": 9.5},
                                                 {"report_month": "2026-06", "series_code": "z", "value": 1},
                                                 {"report_month": "2026-06", "series_code": "y"}]),
            lambda m: m.save_market_price_trend([]),
            lambda m: m.save_market_price_trend([{"report_month": "2099-01", "series_code": "x", "value": 3}]),
            lambda m: m.save_market_price_trend([{"report_month": "2026-07 ", "series_code": "x", "value": 3}]),
            lambda m: m.save_market_price_trend([{"report_month": "2026-07", "series_code": "x"},
                                                 {"report_month": "2026-07"}]),            # KeyError: all rolled back
            lambda m: m.save_market_price_trend([{"report_month": "2026-077", "series_code": "x"}]),
            lambda m: m.save_market_price_trend([{"report_month": None, "series_code": "x"}]),
            lambda m: m.save_market_price_trend([{"report_month": "2026-07", "series_code": "s" * 49}]),
            lambda m: m.save_market_price_trend([{"report_month": "2026-07", "series_code": None}]),
            lambda m: m.save_macro_indicators([{"report_month": "2026-04", "metric_code": "gdp", "value": 7.5},
                                               {"report_month": "2026-08", "metric_code": "iip"}]),
            lambda m: m.save_macro_indicators([]),
            lambda m: m.save_macro_indicators([{"report_month": "2026-09 ", "metric_code": "iip", "value": 2}]),
            lambda m: m.save_macro_indicators([{"report_month": "2026-09", "metric_code": "m" * 33}]),
            lambda m: m.save_macro_indicators([{"metric_code": "x"}])):
        step(fn)


# ── pdf_item_alias ──────────────────────────────────────────────────────────

ALIAS = [{"plant_name": p, "pdf_label": lb, "item_name": it, "convert_t": c} for p, lb, it, c in [
    ("BSP", "Hot Metal Prodn", "Hot Metal", 1), ("BSP", "Ovens", "Oven Pushing(nos/d)", 0),
    ("DSP", "HM", "Hot Metal", None), ("bsp2", "Crude", "Crude Steel", 1)]]


def _alias_reads(m):
    return {("alias", p): m.get_pdf_item_aliases(p) for p in ("BSP", "bsp", "DSP", "bsp2", "XYZ")}


def test_pdf_item_alias(base, monkeypatch):
    base.seed_simple("pdf_item_alias", ALIAS)
    assert_same_reads(base, m1, m2, _alias_reads)
    step = _stepper(base, monkeypatch, _alias_reads, ("pdf_item_alias",))
    for fn in (
            lambda m: m.save_pdf_item_alias("BSP", "Hot Metal Prodn", "hot metal", 0),         # ai_ci item, caller's spelling
            lambda m: m.save_pdf_item_alias("BSP", "hot metal prodn", "Hot Metal"),            # ai_ci label: same row
            lambda m: m.save_pdf_item_alias("bsp", "New label", "Pig Iron"),
            lambda m: m.save_pdf_item_alias("BSP", "Count", "Oven Pushing(nos/day)", 1),       # forced to 0
            lambda m: m.save_pdf_item_alias("BSP", "Count2", "Pushing (NOS)", 5),
            lambda m: m.save_pdf_item_alias("NEWP", "L", "Pig Iron", None),
            lambda m: m.save_pdf_item_alias("P" * 33, "L", "Pig Iron"),                         # 1406 plant_name
            lambda m: m.save_pdf_item_alias(None, "L", "Pig Iron"),
            lambda m: m.save_pdf_item_alias("BSP", "L" * 161, "Pig Iron"),
            lambda m: m.save_pdf_item_alias("BSP", None, "Pig Iron"),
            lambda m: m.save_pdf_item_alias("BSP", "L", "I" * 65),
            lambda m: m.save_pdf_item_alias("BSP", "L", None)):
        step(fn)


def test_pdf_item_alias_plant_between_9_and_32_characters_is_refused(base):
    base.seed_simple("pdf_item_alias", ALIAS)
    with base.v2():
        n = base.data_version(2)
        with pytest.raises(OutOfModelError):
            m2.save_pdf_item_alias("P" * 9, "L", "Pig Iron")
        assert base.data_version(2) == n


# ── rail_prod_despatch ──────────────────────────────────────────────────────

RAIL = [{"financial_year": fy, "metric": mt, "value": v, "note": nt} for fy, mt, v, nt in [
    ("2024-25", "rail_prod", 1000.5, "n1"), ("2024-25", "despatch", None, None), ("2025-26", "rail_prod", 5.0, "")]]


def _rail_reads(m):
    return {("rail", tuple(f)): m.get_rail_report_data(f)
            for f in ([], ["2024-25"], ["2025-26", "2024-25", "2023-24"], ["2024-25 "])}


def test_rail_report(base, monkeypatch):
    base.seed_simple("rail_prod_despatch", RAIL)
    assert_same_reads(base, m1, m2, _rail_reads)
    step = _stepper(base, monkeypatch, _rail_reads, ("rail_prod_despatch",))
    for fn in (
            lambda m: m.save_rail_report_data([{"financial_year": "2024-25", "metric": "rail_prod", "value": 7.0},
                                               {"financial_year": "2026-27", "metric": "x", "value": 1, "note": "q"}]),
            lambda m: m.save_rail_report_data([]),
            lambda m: m.save_rail_report_data([{"financial_year": "2027-28 ", "metric": "x"}]),        # cut
            lambda m: m.save_rail_report_data([{"financial_year": "2027-288", "metric": "x"}]),        # 1406
            lambda m: m.save_rail_report_data([{"financial_year": None, "metric": "x"}]),
            lambda m: m.save_rail_report_data([{"financial_year": "2027-28", "metric": "m" * 33}]),
            lambda m: m.save_rail_report_data([{"financial_year": "2027-28", "metric": "x", "note": "n" * 65}]),
            lambda m: m.save_rail_report_data([{"financial_year": "2027-28", "metric": "x"}, {"metric": "y"}])):
        step(fn)


# ── ready reckoner ──────────────────────────────────────────────────────────

RR = [{"plant_code": p, "plant_name": nm, "plant_group": g, "process_flow_image_path": img, "sort_order": so,
       "updated_by": "u", "updated_at": at, "capacity_rows": cr, "product_mix_headers": h, "product_mix_rows": r,
       "product_mix_caption": cap} for p, nm, g, img, so, at, cr, h, r, cap in [
    ("BSP", "Bhilai Steel Plant", "ISP", "/x/bsp.png", 1, "2026-09-01 10:00:00", '[{"item": "a", "is_total": false}]',
     '["h1", "h2"]', '[{"cells": ["c", "d"], "is_total": true}]', "caption"),
    ("DSP", "Durgapur", "ISP", None, 2, None, None, None, None, None),
    ("ASP", "Alloy", "SSP", None, 1, "2026-09-02 11:11:11", "[]", "[]", "[]", ""),
    ("ISP", "IISCO", "ISP", None, 1, None, '[{"x": 1}]', None, None, "c2")]]


def _rr_reads(m):
    out = {"all": m.get_ready_reckoner_pages()}
    for p in ("BSP", "bsp", "DSP", "ASP", "NEW", "ISP"):
        out[("one", p)] = m.get_ready_reckoner_page(p)
    return out


def test_ready_reckoner(base, monkeypatch):
    base.seed_simple("ready_reckoner_pages", RR)
    assert_same_reads(base, m1, m2, _rr_reads)
    step = _stepper(base, monkeypatch, _rr_reads, ("ready_reckoner_pages",))
    for fn in (
            lambda m: m.upsert_ready_reckoner_master({"plant_code": "BSP", "plant_name": "Bhilai", "plant_group": "SSP",
                                                      "sort_order": 9}),
            lambda m: m.upsert_ready_reckoner_master({"plant_code": "RSP", "plant_group": "ISP"}),         # new, sort 0
            lambda m: m.upsert_ready_reckoner_master({"plant_code": "bsp", "plant_group": "ISP", "sort_order": "3"}),
            lambda m: m.upsert_ready_reckoner_master({"plant_code": "P" * 9, "plant_group": "ISP"}),         # 1406
            lambda m: m.upsert_ready_reckoner_master({"plant_code": "NEWX", "plant_group": "G" * 5}),
            lambda m: m.upsert_ready_reckoner_master({"plant_code": "NEWY", "plant_group": "ISP", "plant_name": "n" * 65}),
            lambda m: m.upsert_ready_reckoner_master({"plant_code": "NEWZ"}),                                # KeyError
            lambda m: m.save_ready_reckoner_content("BSP", capacity_rows=[{"item": "z", "is_total": True}],
                                                    updated_by="bob"),
            lambda m: m.save_ready_reckoner_content("DSP", capacity_rows=[], product_mix_headers=["a"],
                                                    product_mix_rows=[{"cells": ["x"], "is_total": False}],
                                                    product_mix_caption="", updated_by="bob"),
            lambda m: m.save_ready_reckoner_content("DSP", product_mix_caption="c" * 256),
            lambda m: m.save_ready_reckoner_content("ASP"),                                                  # nothing: no bump
            lambda m: m.save_ready_reckoner_content("NOPE", capacity_rows=[1]),                              # no row
            lambda m: m.save_ready_reckoner_content("BSP", capacity_rows=[], updated_by="u" * 129),
            lambda m: m.save_ready_reckoner_image("BSP", "/new.png", "carol"),
            lambda m: m.save_ready_reckoner_image("NOPE", "/new.png", "carol"),
            lambda m: m.save_ready_reckoner_image("ISP", "i" * 256, "carol")):
        step(fn)


# ── major_unit_daily_record ─────────────────────────────────────────────────

MU = [{"plant_code": p, "unit_label": u, "unit_of_measure": um, "value": v, "record_date": d, "remarks": rm,
       "sort_order": so, "updated_by": "u", "updated_at": at} for p, u, um, v, d, rm, so, at in [
    ("BSP", "Blast Furnace 1", "tpd", 4500.5, "2026-03-01", "best", 2, "2026-09-01T10:00:00"),
    ("BSP", "Blast Furnace 2", "tpd", None, None, None, 1, None),
    ("BSP", "Coke Oven 1", "t", 3.0, "2025-12-31", "", 1, "2026-09-02T11:11:11"),
    ("DSP", "Blast Furnace 1", "tpd", 4000.0, "2026-01-01", None, 0, "2026-09-03T12:00:00")]]


def _mu_reads(m):
    out = {"all": m.get_major_unit_daily_records_all()}
    for p in ("BSP", "bsp", "DSP", "NEW"):
        out[("plant", p)] = m.get_major_unit_daily_records(p)
        out[("values", p)] = multiset(_conn(lambda mod, c: mod.major_unit_daily_values(c, p))(m))
        for u in ("Blast Furnace 1", "blast furnace 1", "Blast Furnace 2", "Nope", "BF 1"):
            out[("label", p, u)] = on_cursor(lambda mod, cur: mod.major_unit_daily_label_row(cur, p, u))(m)
    return out


def _rename(new, plant, old):
    return _cur(lambda mod, cur: (mod.rename_major_unit_label(cur, new, plant, old), cur.rowcount)[1])


def test_major_unit_daily(base, monkeypatch):
    base.seed_simple("major_unit_daily_record", MU)
    assert_same_reads(base, m1, m2, _mu_reads)
    step = _stepper(base, monkeypatch, _mu_reads, ("major_unit_daily_record",))

    def save(**k):
        a = dict(plant_code="BSP", unit_label="Blast Furnace 1", value=1.5, unit_of_measure="tpd",
                 record_date="2026-10-01", remarks="r", sort_order=3, updated_by="bob")
        a.update(k)
        return lambda m: m.save_major_unit_daily_record(**a)
    for fn in (save(), save(unit_label="blast furnace 1", value=None, record_date=None),     # ai_ci twin: keeps spelling
               save(plant_code="bsp", unit_label="BLAST FURNACE 2"),
               save(unit_label="New Unit"), save(plant_code="NEWP", unit_label="Blast Furnace 1"),
               save(unit_label="Ünit"), save(updated_by=None), save(remarks=None, unit_of_measure=None),
               save(record_date="2026-10-01 "),                                                # cut
               save(record_date="05/04/2026"), save(record_date=""), save(record_date="1 Oct"),   # free text, verbatim
               save(plant_code="P" * 9), save(plant_code=None), save(unit_label="U" * 65), save(unit_label=None),
               save(unit_of_measure="u" * 17), save(record_date="2026-10-011"), save(sort_order=None),
               save(updated_by="b" * 129),
               _rename("Blast Furnace One", "BSP", "Blast Furnace 1"),
               _rename("blast furnace one", "BSP", "BLAST FURNACE ONE"),                       # case-only rename
               _rename("Blast Furnace 2", "BSP", "Coke Oven 1"),                                # clash
               _rename("BLAST FURNACE 2", "BSP", "Coke Oven 1"),                                # ai_ci clash
               _rename("Nothing", "BSP", "Nope"),                                               # no row
               _rename("Coke Oven 1", "BSP", "Coke Oven 1"),                                    # same name
               _rename("X" * 65, "BSP", "Coke Oven 1"),
               _rename("Fresh Name", "bsp", "coke oven 1")):
        step(fn)


# ── power ───────────────────────────────────────────────────────────────────

POWER = [{"report_month": mo, "plant_name": p, "item_name": it, "value": v} for mo, p, it, v in [
    ("2026-04", "BSP", "actual_total", 10.5), ("2026-04", "DSP", "actual_total", None),
    ("2026-04", "BSP", "plan_total", 8.0), ("2026-05", "RSP", "actual_total", 1e-3)]]


def _power_reads(m):
    out = {}
    for mo in ("2026-04", "2026-05", "2026-06", "2026-04 "):
        out[("plants", mo)] = m.power_plants_for_month(mo)
        for p in ("BSP", "bsp", "DSP"):
            for it in ("actual_total", "plan_total"):
                out[("val", mo, p, it)] = on_cursor(lambda mod, cur: mod.power_value_row(cur, mo, p, it))(m)
    out["rows"] = on_cursor(lambda mod, cur: mod.power_rows_for_months(cur, ["2026-05", "2026-04", "2099-01"]))(m)
    return out


def test_power(base, monkeypatch):
    base.seed_simple("power_data_table", POWER)
    assert_same_reads(base, m1, m2, _power_reads)
    step = _stepper(base, monkeypatch, _power_reads, ("power_data_table",))
    for fn in (
            _cur(lambda m, c: m.upsert_power_value(c, "2026-04", "BSP", "actual_total", 99.0)),
            _cur(lambda m, c: m.upsert_power_value(c, "2026-04", "bsp", "ACTUAL_TOTAL", 1.0)),        # ai_ci key
            _cur(lambda m, c: m.upsert_power_value(c, "2026-06", "NEWP", "x", None)),
            _cur(lambda m, c: m.upsert_power_value(c, "2099-01", "BSP", "x", 1)),
            _cur(lambda m, c: m.upsert_power_value(c, "2026-07 ", "BSP", "x", 1)),
            _cur(lambda m, c: m.upsert_power_value(c, "2026-077", "BSP", "x", 1)),
            _cur(lambda m, c: m.upsert_power_value(c, None, "BSP", "x", 1)),
            _cur(lambda m, c: m.upsert_power_value(c, "2026-07", "P" * 33, "x", 1)),
            _cur(lambda m, c: m.upsert_power_value(c, "2026-07", None, "x", 1)),
            _cur(lambda m, c: m.upsert_power_value(c, "2026-07", "BSP", "i" * 65, 1)),
            _cur(lambda m, c: m.upsert_power_value(c, "2026-07", "BSP", None, 1))):
        step(fn)


def test_power_out_of_model(base):
    base.seed_simple("power_data_table", POWER)
    with base.v2():
        n = base.data_version(2)
        for args in (("2026-4", "BSP", "x"), ("2026-13", "BSP", "x"), ("2026-07", "P" * 9, "x")):
            with pytest.raises(OutOfModelError):
                on_cursor(lambda mod, cur: mod.upsert_power_value(cur, *args, 1), commit=True)(m2)
        assert base.data_version(2) == n


# ── steel_sector_performance ───────────────────────────────────────────────

STEEL = [{"report_month": mo, "data_json": dj, "source_file": sf, "created_at": at} for mo, dj, sf, at in [
    ("2026-02", '{"b": 1, "a": [1, 2]}', "jpc_feb.pdf", "2026-03-05T10:00:00.123456"),
    ("2026-05", '{"x": null}', None, "2026-06-05T10:00:00"),
    ("2026-06", '[1, 2, 3]', "jpc_jun.pdf", None)]]


def _steel_reads(m):
    out = {"json": on_cursor(lambda mod, cur: mod.steel_sector_data_json_rows(cur))(m)}
    for mo in ("2026-01", "2026-02", "2026-04", "2026-06", "2026-12", "2026-05 "):
        out[("latest", mo)] = on_cursor(lambda mod, cur: mod.steel_sector_latest_row(cur, mo))(m)
        out[("any", mo)] = m.steel_sector_any_row(mo)
    return out


def test_steel_sector_performance(base, monkeypatch):
    base.seed_simple("steel_sector_performance_table", STEEL)
    assert_same_reads(base, m1, m2, _steel_reads)
    step = _stepper(base, monkeypatch, _steel_reads, ("steel_sector_performance_table",))
    now = NOW.isoformat()
    for fn in (
            _cur(lambda m, c: m.upsert_steel_sector_performance(c, "2026-02", '{"z": 1, "a": 2}', "new.pdf", now)),
            _cur(lambda m, c: m.upsert_steel_sector_performance(c, "2026-07", '{"k": "v"}', None, now)),
            _cur(lambda m, c: m.upsert_steel_sector_performance(c, "2026-08", '{}', "f", None)),
            _cur(lambda m, c: m.upsert_steel_sector_performance(c, "2099-01", '[]', "f", "2026-10-23T14:30:05")),
            _cur(lambda m, c: m.upsert_steel_sector_performance(c, "2026-09 ", 'null', "f", now)),
            _cur(lambda m, c: m.upsert_steel_sector_performance(c, "2026-09", 'not json', "f", now)),    # 3140
            _cur(lambda m, c: m.upsert_steel_sector_performance(c, "2026-099", '{}', "f", now)),
            _cur(lambda m, c: m.upsert_steel_sector_performance(c, None, '{}', "f", now)),
            _cur(lambda m, c: m.upsert_steel_sector_performance(c, "2026-09", '{}', "f" * 256, now)),
            _cur(lambda m, c: m.upsert_steel_sector_performance(c, "2026-09", '{}', "f", "c" * 33))):
        step(fn)


def test_steel_sector_created_at_not_isoformat_is_refused(base):
    base.seed_simple("steel_sector_performance_table", STEEL)
    with base.v2():
        n = base.data_version(2)
        for at in ("2026-10-23 14:30:05", "yesterday", "2026-10-23T14:30:05.000000"):
            with pytest.raises(OutOfModelError):
                on_cursor(lambda mod, cur: mod.upsert_steel_sector_performance(cur, "2026-08", "{}", "f", at),
                          commit=True)(m2)
        assert base.data_version(2) == n


# ── bf_benchmark ────────────────────────────────────────────────────────────

BF_META = [{"plant": p, "unit": u, "working_volume_m3": w, "updated_at": at} for p, u, w, at in [
    ("BSP", "Blast Furnace 1", 1000.0, "2026-09-09T05:58:59.243471+00:00"),
    ("BSP", "Blast Furnace 2", None, None), ("DSP", "Blast Furnace 1", 2000.5, "2026-09-09T05:58:59+00:00")]]
BF_EXT = [{"id": i, "name": n, "company": c, "location": lo, "working_volume_m3": w, "active": a,
           "created_at": at, "created_by": by} for i, n, c, lo, w, a, at, by in [
    (1, "Zeta BF", "Zeta Co", "Zeta City", 500.0, 1, "2026-09-09T05:58:59.243471+00:00", "u"),
    (2, "alpha BF", "", "", None, 0, "2026-01-05 10:00:00", ""),
    (3, "Mid BF", "M", "L", 10.0, 1, "2026-09-10T00:00:00+00:00", None)]]
BF_DATA = [{"id": i, "external_bf_id": b, "report_month": fy, "param_json": pj, "created_at": c, "updated_at": u}
           for i, b, fy, pj, c, u in [
    (1, 1, "2024-25", '{"b": 1, "a": 2}', "2026-09-09T05:58:59.243471+00:00", "2026-09-10T00:00:00+00:00"),
    (2, 1, "2025-26", '{"x": 1}', "2026-01-05 10:00:00", "2026-01-06 11:00:00"),
    (3, 2, "2025-26", '{}', "2026-09-09T05:58:59+00:00", None)]]


def _bf_reads(m):
    out = {"wv": on_cursor(lambda mod, cur: mod.bf_sail_working_volume_rows(cur))(m),
           "meta": on_cursor(lambda mod, cur: mod.bf_sail_meta_rows(cur))(m)}
    for p in ("BSP", "bsp", "DSP"):
        for u in ("Blast Furnace 1", "blast furnace 1", "Blast Furnace 2"):
            out[("wvrow", p, u)] = on_cursor(lambda mod, cur: mod.bf_sail_working_volume_row(cur, p, u))(m)
    for act in (False, True):
        out[("list", act)] = on_cursor(lambda mod, cur: mod.external_bf_list_rows(cur, act))(m)
    for i in (1, 2, 3, 4):
        out[("id", i)] = on_cursor(lambda mod, cur: mod.external_bf_id_row(cur, i))(m)
        for fy in ("2024-25", "2025-26", "2026-27"):
            out[("data", i, fy)] = on_cursor(lambda mod, cur: mod.external_bf_data_row(cur, i, fy))(m)
    out["meta_rows"] = multiset(on_cursor(lambda mod, cur: mod.external_bf_meta_rows(cur, [3, 1, 99]))(m))
    out["meta_rows_all"] = multiset(on_cursor(lambda mod, cur: mod.external_bf_meta_rows(cur, [1, 2, 3]))(m))
    return out


@pytest.fixture
def bf(base, monkeypatch):
    base.seed_simple("bf_benchmark_sail_meta", BF_META)
    base.seed_simple("bf_benchmark_external_bf", BF_EXT)
    base.seed_simple("bf_benchmark_external_data", BF_DATA)
    assert_same_reads(base, m1, m2, _bf_reads)
    return _stepper(base, monkeypatch, _bf_reads,
                    ("bf_benchmark_sail_meta", "bf_benchmark_external_bf", "bf_benchmark_external_data"))


UTC_NOW = "2026-10-23T09:00:05.250000+00:00"


def test_bf_sail_meta(bf):
    for fn in (
            _cur(lambda m, c: m.upsert_bf_sail_meta(c, "BSP", "Blast Furnace 1", 1111.0, UTC_NOW)),
            _cur(lambda m, c: m.upsert_bf_sail_meta(c, "bsp", "blast furnace 1", 1.5, UTC_NOW)),     # ai_ci twin
            _cur(lambda m, c: m.upsert_bf_sail_meta(c, "RSP", "Blast Furnace 3", None, "2026-10-23T09:00:05+00:00")),
            _cur(lambda m, c: m.upsert_bf_sail_meta(c, "BSP", "Blast Furnace 2", 2.0, None)),
            _cur(lambda m, c: m.upsert_bf_sail_meta(c, "P" * 33, "u", 1.0, UTC_NOW)),
            _cur(lambda m, c: m.upsert_bf_sail_meta(c, None, "u", 1.0, UTC_NOW)),
            _cur(lambda m, c: m.upsert_bf_sail_meta(c, "BSP", "u" * 33, 1.0, UTC_NOW)),
            _cur(lambda m, c: m.upsert_bf_sail_meta(c, "BSP", None, 1.0, UTC_NOW)),
            _cur(lambda m, c: m.upsert_bf_sail_meta(c, "BSP", "x", 1.0, "u" * 41))):
        bf(fn)


def test_bf_external(bf):
    for fn in (
            _cur(lambda m, c: (m.insert_external_bf(c, "New BF", " co ", "here", UTC_NOW), c.lastrowid)[1]),
            _cur(lambda m, c: (m.insert_external_bf(c, "Plain BF", "", "", "2026-10-23 09:00:05"), c.lastrowid)[1]),
            _cur(lambda m, c: m.insert_external_bf(c, "N" * 191, "", "", UTC_NOW)),
            _cur(lambda m, c: m.insert_external_bf(c, None, "", "", UTC_NOW)),
            _cur(lambda m, c: m.insert_external_bf(c, "No time", "", "", None)),
            _cur(lambda m, c: m.insert_external_bf(c, "Long time", "", "", "t" * 41)),
            _cur(lambda m, c: m.update_external_bf(c, ["name=%s", "active=%s"], ["Renamed", 0, 1])),
            _cur(lambda m, c: m.update_external_bf(c, ["company=%s", "location=%s", "working_volume_m3=%s"],
                                                   ["", "x", 12.5, 2])),
            _cur(lambda m, c: m.update_external_bf(c, ["name=%s"], ["N" * 191, 3])),
            _cur(lambda m, c: m.update_external_bf(c, ["name=%s"], ["Ghost", 99])),
            _cur(lambda m, c: m.insert_external_bf_data(c, 3, "2025-26", '{"k": [3, 1]}', UTC_NOW)),
            _cur(lambda m, c: m.insert_external_bf_data(c, 3, "2026-27 ", '{}', "2026-10-23 09:00:05")),
            _cur(lambda m, c: m.insert_external_bf_data(c, 3, "2025-26", '{}', UTC_NOW)),             # 1062
            _cur(lambda m, c: m.insert_external_bf_data(c, 3, "2027-288", '{}', UTC_NOW)),
            _cur(lambda m, c: m.insert_external_bf_data(c, 3, "2027-28", 'not json', UTC_NOW)),
            _cur(lambda m, c: m.insert_external_bf_data(c, 3, "2027-28", '{}', None)),
            _cur(lambda m, c: m.update_external_bf_data(c, '{"z": 1, "a": 2}', UTC_NOW, 1, "2024-25")),
            _cur(lambda m, c: m.update_external_bf_data(c, '{"p": 1}', "2026-10-23 09:00:05", 1, "2025-26")),
            _cur(lambda m, c: m.update_external_bf_data(c, '{"p": 1}', UTC_NOW, 99, "2025-26")),         # no row
            _cur(lambda m, c: m.update_external_bf_data(c, '{"p": 1}', None, 2, "2025-26")),
            _cur(lambda m, c: m.update_external_bf_data(c, 'not json', UTC_NOW, 2, "2025-26"))):
        bf(fn)


def test_bf_timestamps_not_in_a_v1_form_are_refused(bf, base):
    with base.v2():
        n = base.data_version(2)
        for call in (lambda c: m2.upsert_bf_sail_meta(c, "BSP", "x", 1.0, "2026-10-23 09:00:05"),
                     lambda c: m2.upsert_bf_sail_meta(c, "BSP", "x", 1.0, "2026-10-23T09:00:05+05:30"),
                     lambda c: m2.insert_external_bf(c, "n", "", "", "2026-10-23T09:00:05"),
                     lambda c: m2.insert_external_bf_data(c, 1, "2030-31", "{}", "2026-10-23T09:00:05.000000+00:00"),
                     lambda c: m2.update_external_bf_data(c, "{}", "soon", 1, "2024-25")):
            with pytest.raises(OutOfModelError):
                on_cursor(lambda mod, cur: call(cur), commit=True)(m2)
        assert base.data_version(2) == n


# ── cover photos / settings ─────────────────────────────────────────────────

PHOTOS = [{"id": i, "filename": f, "thumb_filename": f"t_{f}", "original_name": o, "width": w, "height": h,
           "uploaded_by": by, "uploaded_at": at, "is_active": a} for i, f, o, w, h, by, at, a in [
    (1, "a.jpg", "A.jpg", 1920, 1080, "u@x", "2026-08-01 10:00:00", 1),
    (2, "b.jpg", "B.jpg", None, None, None, None, 0),
    (3, "c.jpg", "C.jpg", 800, 600, "v@x", "2026-09-01 09:30:15", 1)]]
SETTINGS = [{"report_month": mo, "design": d, "photo_mode": pm, "photo_id": pid, "updated_by": by, "updated_at": at}
            for mo, d, pm, pid, by, at in [
    ("2026-08", "classic", "random", 1, "u@x", "2026-08-02 10:00:00"),
    ("2026-09", "modern", "fixed", 3, None, None), ("2026-10", "classic", "random", 1, "u", "2026-10-01 00:00:00")]]


def _cover_reads(m):
    out = {"newest": m.active_cover_photo_rows_newest_first(), "active": m.active_cover_photo_rows(),
           "usage": m.cover_photo_usage_rows()}
    for i in (1, 2, 3, 4):
        out[("photo", i)] = m.cover_photo_rows(i)
    for mo in ("2026-08", "2026-09", "2026-11", "2026-08 "):
        out[("setting", mo)] = m.cover_setting_rows(mo)
    return out


@pytest.fixture
def cover(base, monkeypatch):
    base.seed_simple("cover_photos", PHOTOS)
    base.seed_simple("report_cover_settings", SETTINGS)
    assert_same_reads(base, m1, m2, _cover_reads)
    return _stepper(base, monkeypatch, _cover_reads, ("cover_photos", "report_cover_settings"))


def test_cover_photos(cover):
    ts = "2026-10-23 14:30:05"
    for fn in (lambda m: m.insert_cover_photo("d.jpg", "t_d.jpg", "D.jpg", 100, 50, "w@x", ts),
               lambda m: m.insert_cover_photo("e.jpg", "t_e.jpg", "E.jpg", None, None, None, None),
               lambda m: m.insert_cover_photo("f.jpg", "t_f.jpg", "F.jpg", 1, 1, "w@x", ts + "   "),     # cut
               lambda m: m.insert_cover_photo("f" * 65, "t", "F", 1, 1, "w", ts),
               lambda m: m.insert_cover_photo(None, "t", "F", 1, 1, "w", ts),
               lambda m: m.insert_cover_photo("f", "t" * 65, "F", 1, 1, "w", ts),
               lambda m: m.insert_cover_photo("f", "t", "F" * 256, 1, 1, "w", ts),
               lambda m: m.insert_cover_photo("f", "t", "F", 1, 1, "w" * 256, ts),
               lambda m: m.insert_cover_photo("f", "t", "F", 1, 1, "w", "2026-10-23 14:30:05 x"),     # 1406
               lambda m: m.deactivate_cover_photo(1), lambda m: m.deactivate_cover_photo(1),
               lambda m: m.deactivate_cover_photo(99)):
        cover(fn)


def test_cover_settings(cover):
    ts = "2026-10-23 14:30:05"
    for fn in (lambda m: m.replace_cover_setting("2026-08", "modern", "fixed", 3, "w@x", ts),
               lambda m: m.replace_cover_setting("2026-11", "classic", "random", None, None, None),
               lambda m: m.replace_cover_setting("2099-01", "classic", "random", 1, "w", ts),
               lambda m: m.replace_cover_setting("2026-12 ", "classic", "random", 1, "w", ts),
               lambda m: m.replace_cover_setting("2026-127", "classic", "random", 1, "w", ts),
               lambda m: m.replace_cover_setting(None, "classic", "random", 1, "w", ts),
               lambda m: m.replace_cover_setting("2026-11", "d" * 25, "random", 1, "w", ts),
               lambda m: m.replace_cover_setting("2026-11", None, "random", 1, "w", ts),
               lambda m: m.replace_cover_setting("2026-11", "classic", "r" * 9, 1, "w", ts),
               lambda m: m.replace_cover_setting("2026-11", "classic", "random", 1, "w" * 256, ts)):
        cover(fn)


def test_cover_timestamps_not_in_the_v1_form_are_refused(cover, base):
    with base.v2():
        n = base.data_version(2)
        for call in (lambda: m2.replace_cover_setting("2026-11", "classic", "random", 1, "w", "2026-10-23T14:30:05"),
                     lambda: m2.replace_cover_setting("2026-11", "classic", "random", 1, "w", "soon"),
                     lambda: m2.insert_cover_photo("g.jpg", "t", "G", 1, 1, "w", "2026-10-23T14:30:05")):
            with pytest.raises(OutOfModelError):
                call()
        assert base.data_version(2) == n


def test_cover_setting_for_a_photo_that_does_not_exist_is_refused_by_the_fk(cover, base):
    """v1 had no FK photo_id -> cover_photos: cover_store.save_setting only
    stores ids of photos it just found (parity_exceptions.md §2)."""
    with base.v2():
        with pytest.raises(rc.IntegrityError):
            m2.replace_cover_setting("2026-11", "classic", "fixed", 999, "w", "2026-10-23 14:30:05")


def test_external_bf_data_for_a_bf_that_does_not_exist_is_refused_by_the_fk(base):
    base.seed_simple("bf_benchmark_external_bf", BF_EXT)
    with base.v2():
        with pytest.raises(rc.IntegrityError):
            on_cursor(lambda mod, cur: mod.insert_external_bf_data(cur, 99, "2025-26", "{}", UTC_NOW), commit=True)(m2)


# ── bump and dry run ────────────────────────────────────────────────────────

def test_every_v2_write_bumps_and_a_dry_run_does_not(base):
    base.seed_simple("market_price_trend_monthly", MARKET)
    base.seed_simple("pdf_item_alias", ALIAS)
    base.seed_simple("ready_reckoner_pages", RR)
    base.seed_simple("major_unit_daily_record", MU)
    base.seed_simple("power_data_table", POWER)
    base.seed_simple("steel_sector_performance_table", STEEL)
    base.seed_simple("bf_benchmark_sail_meta", BF_META)
    base.seed_simple("bf_benchmark_external_bf", BF_EXT)
    base.seed_simple("bf_benchmark_external_data", BF_DATA)
    base.seed_simple("cover_photos", PHOTOS)
    base.seed_simple("report_cover_settings", SETTINGS)
    ts = "2026-10-23 14:30:05"
    writes = [
        lambda: m2.save_market_price_trend([{"report_month": "2026-04", "series_code": "q", "value": 1}]),
        lambda: m2.save_macro_indicators([]),
        lambda: m2.save_pdf_item_alias("BSP", "L2", "Pig Iron"),
        lambda: m2.save_rail_report_data([{"financial_year": "2024-25", "metric": "q"}]),
        lambda: m2.upsert_ready_reckoner_master({"plant_code": "BSP", "plant_group": "ISP"}),
        lambda: m2.save_ready_reckoner_content("BSP", capacity_rows=[1]),
        lambda: m2.save_ready_reckoner_image("BSP", "/q.png", "u"),
        lambda: m2.save_major_unit_daily_record("BSP", "Blast Furnace 1", 1.0, "t", None, None, 1, "u"),
        lambda: _cur(lambda m, c: m.upsert_power_value(c, "2026-04", "BSP", "q", 1))(m2),
        lambda: _cur(lambda m, c: m.upsert_steel_sector_performance(c, "2026-05", "{}", "f", None))(m2),
        lambda: _cur(lambda m, c: m.rename_major_unit_label(c, "Renamed", "BSP", "Blast Furnace 1"))(m2),
        lambda: _cur(lambda m, c: m.rename_major_unit_label(c, "Renamed", "BSP", "Missing"))(m2),
        lambda: _cur(lambda m, c: m.upsert_bf_sail_meta(c, "BSP", "Blast Furnace 1", 1.0, UTC_NOW))(m2),
        lambda: _cur(lambda m, c: m.insert_external_bf(c, "q", "", "", UTC_NOW))(m2),
        lambda: _cur(lambda m, c: m.update_external_bf(c, ["name=%s"], ["q", 1]))(m2),
        lambda: _cur(lambda m, c: m.insert_external_bf_data(c, 3, "2030-31", "{}", UTC_NOW))(m2),
        lambda: _cur(lambda m, c: m.update_external_bf_data(c, "{}", UTC_NOW, 1, "2024-25"))(m2),
        lambda: m2.insert_cover_photo("q.jpg", "t", "Q", 1, 1, "u", ts),
        lambda: m2.deactivate_cover_photo(1),
        lambda: m2.replace_cover_setting("2026-08", "classic", "random", None, "u", ts)]

    def all_reads(m):
        out = {}
        for f in (_market_reads, _alias_reads, _rr_reads, _mu_reads, _power_reads, _steel_reads, _bf_reads,
                  _cover_reads):
            out.update({(f.__name__, k): v for k, v in f(m).items()})
        return out
    with base.v2():
        for i, w in enumerate(writes):
            n = base.data_version(2)
            w()
            assert base.data_version(2) > n, i
        before = {k: repr(v) for k, v in all_reads(m2).items()}
        n = base.data_version(2)
        with rc.rollback_tx():
            m2.save_market_price_trend([{"report_month": "2098-01", "series_code": "dry", "value": 1}])
            m2.save_pdf_item_alias("DRY", "L", "Dry item")
            m2.save_major_unit_daily_record("BSP", "Dry unit", 1.0, "t", None, None, 1, "u")
            on_cursor(lambda mod, cur: mod.insert_external_bf(cur, "dry", "", "", UTC_NOW))(m2)
            m2.replace_cover_setting("2098-02", "classic", "random", None, "u", ts)
            assert {k: repr(v) for k, v in all_reads(m2).items()} != before
        assert base.data_version(2) == n
        assert {k: repr(v) for k, v in all_reads(m2).items()} == before
    for q in ("SELECT COUNT(*) FROM plant WHERE plant_code = 'DRY'",
              "SELECT COUNT(*) FROM cal_month WHERE report_month IN ('2098-01', '2098-02')",
              "SELECT COUNT(*) FROM plant_unit WHERE unit_code = 'Dry unit'",
              "SELECT COUNT(*) FROM item WHERE item_name = 'Dry item'"):
        assert base.sql(2, q)[0][0] == 0
