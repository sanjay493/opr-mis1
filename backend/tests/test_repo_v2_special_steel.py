"""v1 vs v2 equivalence of repo.special_steel (Task 7e1).

The same rows are seeded into v1's special_steel_orders / _abp_table /
_grade_clubs / _phys_meta / _phys_perf / _ipt_requirement and their v2
tables (as the migration loads them; grade-club created_at through
repo.v2codec). Every write runs through _v1_frozen.special_steel on v1 and
repo.special_steel (v2) on v2; after each step both sides must agree on the
outcome (result, or exception type and args), the activity-log entries,
every read (the cursor helpers on tuple and Row cursors, canonical form:
order, key names, float bits and types count), including the reads the
oracle never saw called (club_member_rows, club_rows, despatch_rows,
grade_club_row, grades_for_product, rsp_prior_grade_rows), and the stored
rows (created_at rendered back to v1's string).
"""
import pytest

import dbengine
from repo import conn as rc
from _v1_frozen import special_steel as s1
from repo import _keys
from repo import special_steel as s2
from v2dual import assert_same_reads, on_cursor, record_activity, run_step

ROW = dbengine.Row
MONTHS = ["2025-03", "2025-04", "2025-05", "2099-01"]
PLANTS = ["BSP", "bsp", "ISP", "RSP", "SSPs", "ASP"]
PRODUCTS = ["Plates", "plates", "Rails", "WRM", "Bar"]
TABLES = ("special_steel_orders", "special_steel_abp_table", "special_steel_grade_clubs",
          "special_steel_phys_meta", "special_steel_phys_perf", "special_steel_ipt_requirement")


def _o(month, plant, product, grade, section="", so=0, oq=None, ad=None):
    return {"report_month": month, "plant_name": plant, "product": product, "quality_grade": grade,
            "section": section, "sort_order": so, "order_qty": oq, "actual_despatch": ad}


ORDERS = [
    _o("2025-04", "BSP", "Plates", "E250", "", 2, 10.5, 9.25), _o("2025-04", "BSP", "Plates", "E350", "", 1, 3, 2.1),
    _o("2025-04", "BSP", "Plates", "API", "10mm", 1, 0.1, 0.2), _o("2025-04", "BSP", "Plates", "API", "12mm", 1, None, 1e-3),
    _o("2025-05", "BSP", "Plates", "E250", "", 2, 11.0, None), _o("2025-05", "BSP", "Plates", "ZZ", "", 0, 1.0, 1.0),
    _o("2025-03", "BSP", "Plates", "OLD", "", 5, 0.3, 0.3),
    _o("2025-04", "ISP", "WRM", "SAE1008", "", 0, 7.7, 6.6), _o("2025-04", "ISP", "WRM", "EQ", "", 0, 1.1, 2.2),
    _o("2025-05", "ISP", "Bar", "", "", 0, 5.0, 4.0),
    _o("2025-04", "SSPs", "All", "", "", 0, 100.0, None), _o("2025-05", "SSPs", "All", "", "", 0, 50.5, None),
    _o("2025-03", "RSP", "Rails", "R260", "", 0, 1.0, 1.0), _o("2025-04", "RSP", "Rails", "r260", "x", 0, 2.0, 2.0),
    _o("2025-04", "RSP", "Plates", "IS2062", "", 1, 3.0, 3.0),
]
ABP = [{"report_month": m, "plant_name": p, "abp_qty": q} for m, p, q in
       [("2025-04", "BSP", 10.0), ("2025-04", "SSPs", 20.5), ("2025-05", "BSP", None), ("2025-03", "ISP", 0.1)]]
CLUBS = [{"plant_name": p, "product": pr, "quality_grade": g, "club_label": l, "created_at": at} for p, pr, g, l, at in
         [("BSP", "Plates", "E250", "Mild", "2026-08-19T11:02:50.043984"),
          ("BSP", "Plates", "E350", "Mild", "2026-08-19T11:02:50"), ("BSP", "Plates", "API", "Line pipe", None),
          ("RSP", "Rails", "R260", "Rails", "2026-09-01T10:00:00.000001")]]
META = [{"plant": p, "series": s, "capacity_kt": c, "best_actual_kt": b, "best_year": y, "remark": r,
         "sort_order": so} for p, s, c, b, y, r, so in
        [("ASP", "crude", 234.0, 200.5, "2019-20", "note", 1), ("SSP", "crude", None, None, None, None, 0),
         ("VISL", "finished", 100, 90.0, "2018-19", "", 2)]]
PERF = [{"financial_year": fy, "plant": p, "series": s, "metric": m, "value_kt": v} for fy, p, s, m, v in
        [("2024-25", "ASP", "crude", "plan", 200.0), ("2024-25", "ASP", "crude", "actual", 180.5),
         ("2025-26", "SSP", "crude", "plan", None), ("2023-24", "VISL", "finished", "actual", 1e-3)]]
IPTREQ = [{"financial_year": fy, "item": i, "from_plant": f, "to_plant": t, "plan_kt": p, "sort_order": so}
          for fy, i, f, t, p, so in
          [("2025-26", "Blooms", "BSP", "ASP", 100.0, 2), ("2025-26", "Slabs", "RSP", "ASP", None, 1),
           ("2025-26", "Billets", "BSP", "SSP", 5.5, 1), ("2024-25", "Blooms", "BSP", "ASP", 90.0, 0)]]


@pytest.fixture
def seeded(dual):
    for t, rows in (("special_steel_orders", ORDERS), ("special_steel_abp_table", ABP),
                    ("special_steel_grade_clubs", CLUBS), ("special_steel_phys_meta", META),
                    ("special_steel_phys_perf", PERF), ("special_steel_ipt_requirement", IPTREQ)):
        dual.seed_simple(t, rows)
    return dual


MSETS = [["2025-04"], ["2025-04", "2025-05"], ["2025-05", "2025-04", "2025-03"], MONTHS, ["2024-01"]]


def _reads(m):
    out = {"phys": m.get_ss_phys_perf(), "ipt_fys": m.list_ss_ipt_requirement_fys()}
    for fy in ("2025-26", "2024-25", "2026-27", "2025-26 "):
        out[("iptreq", fy)] = m.get_ss_ipt_requirement(fy)
    for mo in MONTHS:
        out[("plants", mo)] = sorted(m.plants_for_month(mo))
        out[("abp_any", mo)] = m.abp_any_row(mo)
    for rf, name in ((None, "tuple"), (ROW, "row")):
        def c(fn):
            return on_cursor(fn, rf)(m)
        out[("order_months", name)] = c(lambda md, cur: md.order_months(cur))
        for p in PLANTS:
            out[("products", name, p)] = c(lambda md, cur: md.products_for_plant(cur, p))
            for mo in MONTHS + ["2025-04 "]:
                out[("manual", name, mo, p)] = c(lambda md, cur: md.manual_rows(cur, mo, p))
                out[("pm_sums", name, mo, p)] = c(lambda md, cur: md.plant_month_sums_row(cur, mo, p))
                out[("pm_act", name, mo, p)] = c(lambda md, cur: md.plant_month_actual_row(cur, mo, p))
            for ms in MSETS:
                k = tuple(ms)
                out[("pms_sums", name, k, p)] = c(lambda md, cur: md.plant_months_sums_row(cur, ms, p))
                out[("pms_act", name, k, p)] = c(lambda md, cur: md.plant_months_actual_row(cur, ms, p))
                out[("prod_sums", name, k, p)] = c(lambda md, cur: md.product_actual_sums(cur, ms, p))
                out[("sum_count", name, k, p)] = c(lambda md, cur: md.actual_sum_count_row(cur, ms, p))
                out[("abp_sum", name, k, p)] = c(lambda md, cur: md.abp_sum_row(cur, ms, p))
            for pr in PRODUCTS:
                out[("grades", name, p, pr)] = c(lambda md, cur: md.grades_for_product(cur, p, pr))
                out[("clubs", name, p, pr)] = c(lambda md, cur: md.club_rows(cur, p, pr))
                out[("oclubs", name, p, pr)] = c(lambda md, cur: md.ordered_club_rows(cur, p, pr))
                for label in ("Mild", "mild", "Rails", "None"):
                    out[("members", name, p, pr, label)] = c(lambda md, cur: md.club_member_rows(cur, p, pr, label))
                for g in ("E250", "e250", "API", "R260", "None"):
                    out[("club_of", name, p, pr, g)] = c(lambda md, cur: md.grade_club_row(cur, p, pr, g))
                for mo in MONTHS:
                    out[("group", name, mo, p, pr)] = c(lambda md, cur: md.group_rows(cur, mo, p, pr))
                    out[("cply", name, mo, p, pr)] = c(lambda md, cur: md.cply_rows(cur, mo, p, pr))
                for ms in MSETS:
                    k = tuple(ms)
                    out[("all_grades", name, k, p, pr)] = c(lambda md, cur: md.all_grade_rows(cur, ms, p, pr))
                    out[("gytd", name, k, p, pr)] = c(lambda md, cur: md.group_ytd_rows(cur, ms, p, pr))
                    out[("cytd", name, k, p, pr)] = c(lambda md, cur: md.cply_ytd_rows(cur, ms, p, pr))
        for ms in MSETS:
            k = tuple(ms)
            out[("fy_sums", name, k)] = c(lambda md, cur: md.fy_plant_month_sums(cur, ms, PLANTS))
            out[("ssps_ms", name, k)] = c(lambda md, cur: md.ssps_order_months_row(cur, ms))
            out[("abp_rows", name, k)] = c(lambda md, cur: md.abp_rows(cur, ms))
            out[("despatch", name, k)] = c(lambda md, cur: md.despatch_rows(cur, PLANTS, ms))
            for mill in ("WRM", "wrm", "Bar", "None"):
                out[("isp_ytd", name, k, mill)] = c(lambda md, cur: md.isp_ytd_sums_row(cur, ms, mill))
                out[("isp_asum", name, k, mill)] = c(lambda md, cur: md.isp_actual_sum_row(cur, ms, mill))
        for mo in MONTHS:
            out[("ssps", name, mo)] = c(lambda md, cur: md.ssps_order_row(cur, mo))
            out[("rsp_prior", name, mo)] = c(lambda md, cur: md.rsp_prior_grade_rows(cur, mo))
            for mill in ("WRM", "Bar", "None"):
                out[("isp_m", name, mo, mill)] = c(lambda md, cur: md.isp_month_row(cur, mo, mill))
                out[("isp_a", name, mo, mill)] = c(lambda md, cur: md.isp_actual_row(cur, mo, mill))
    return out


@pytest.fixture
def step(seeded, monkeypatch):
    activity = record_activity(monkeypatch)

    def go(fn):
        return run_step(seeded, s1, s2, fn, reads=_reads, tables=TABLES, activity=activity)
    return go


def test_seeded_reads_agree(seeded):
    r = assert_same_reads(seeded, s1, s2, _reads)
    assert r[("members", "tuple", "BSP", "Plates", "Mild")] != r[("members", "tuple", "BSP", "Plates", "None")]


def test_order_writes(step):
    for fn in (lambda m: m.save_special_steel_entry("2025-04", "BSP", "Plates", "E250", 3, 1.5, 2.5),       # update
               lambda m: m.save_special_steel_entry("2025-04", "bsp", "plates", "e350", 1, 4.0, None),     # ai_ci
               lambda m: m.save_special_steel_entry("2025-04", "BSP", "Plates", "NEW", 0, None, None, None),
               lambda m: m.save_special_steel_entry("2099-01", "XYZ", "Plates", "N", section="s"),        # new month/plant
               lambda m: m.save_special_steel_entry("2025-05  ", "BSP", "Plates", "ZZ", 9, 9.0, 9.0),     # cut; old None
               lambda m: m.save_special_steel_entry("2025-055", "BSP", "Plates", "ZZ"),                   # 1406
               lambda m: m.save_special_steel_entry(None, "BSP", "Plates", "ZZ"),                         # 1048
               lambda m: m.save_special_steel_entry("2025-05", "P" * 33, "Plates", "ZZ"),                  # 1406 plant
               lambda m: m.save_special_steel_entry("2025-05", "BSP", "P" * 161, "ZZ"),                    # 1406 product
               lambda m: m.save_special_steel_entry("2025-05", "BSP", "Plates", None),                     # 1048 grade
               lambda m: m.save_special_steel_entry("2025-05", "BSP", "Plates", "ZZ", "x"),                # 1366 sort
               lambda m: m.clear_special_steel_orders("2025-04", "BSP"),
               lambda m: m.clear_special_steel_orders("2025-04", "bsp"),                                   # gone: 0
               lambda m: m.clear_special_steel_orders("2025-05 ", "ISP"),                                  # raw: none
               lambda m: m.clear_special_steel_orders("2025-05", "isp")):
        step(fn)


def test_abp_and_club_writes(step):
    def cw(fn):
        return on_cursor(fn, commit=True)
    for fn in (cw(lambda m, c: m.upsert_abp(c, "2025-04", "BSP", 1.5)),
               cw(lambda m, c: m.upsert_abp(c, "2025-04", "ssps", 2.5)),                  # ai_ci stored row
               cw(lambda m, c: m.upsert_abp(c, "2099-05", "XYZ", None)),
               cw(lambda m, c: m.upsert_abp(c, "2025-05 ", "BSP", 3.0)),
               cw(lambda m, c: m.upsert_abp(c, "2025-055", "BSP", 3.0)),                  # 1406
               cw(lambda m, c: m.upsert_abp(c, "2025-05", None, 3.0)),                    # 1048
               cw(lambda m, c: m.upsert_grade_club(c, "BSP", "Plates", "E250", "Hard", "2026-10-01T09:00:00.500000")),
               cw(lambda m, c: m.upsert_grade_club(c, "bsp", "plates", "e350", "Hard", "2026-10-01T09:00:00")),
               cw(lambda m, c: m.upsert_grade_club(c, "RSP", "Rails", "R350", "Rails", "2026-10-02T01:02:03.000001")),
               cw(lambda m, c: m.upsert_grade_club(c, "XYZ", "Bars", "G", "L", None)),
               cw(lambda m, c: m.upsert_grade_club(c, "BSP", "Plates", "Q", "L" * 201, "2026-10-01T09:00:00")),
               cw(lambda m, c: m.upsert_grade_club(c, "BSP", "Plates", None, "L", "2026-10-01T09:00:00")),
               cw(lambda m, c: m.delete_grade_club(c, "BSP", "Plates", "api")),
               cw(lambda m, c: m.delete_grade_club(c, "BSP", "Plates", "none")),
               cw(lambda m, c: m.delete_club(c, "bsp", "Plates", "hard")),
               cw(lambda m, c: m.delete_club(c, "RSP", "Rails", "Nope"))):
        step(fn)


def test_phys_writes(step):
    for fn in (lambda m: m.save_ss_phys_meta([{"plant": "ASP", "series": "crude", "capacity_kt": 1.0,
                                               "best_year": "2020-21", "sort_order": "3"},
                                              {"plant": "ssp", "series": "CRUDE", "remark": "r"},
                                              {"plant": "XYZ", "series": "new", "sort_order": None}]),
               lambda m: m.save_ss_phys_meta([]),
               lambda m: m.save_ss_phys_meta([{"plant": "P" * 9, "series": "s"}]),               # 1406 plant
               lambda m: m.save_ss_phys_meta([{"plant": "ASP", "series": "S" * 17}]),            # 1406 series
               lambda m: m.save_ss_phys_meta([{"plant": "ASP", "series": "s", "best_year": "2020-211"}]),
               lambda m: m.save_ss_phys_meta([{"plant": "ASP"}]),                                # KeyError
               lambda m: m.save_ss_phys_perf([{"financial_year": "2024-25", "plant": "ASP", "series": "crude",
                                               "metric": "plan", "value_kt": 1.5},
                                              {"financial_year": "2024-25", "plant": "asp", "series": "crude",
                                               "metric": "ACTUAL", "value_kt": None},              # delete ai_ci
                                              {"financial_year": "2026-27", "plant": "XYZ", "series": "s",
                                               "metric": "m", "value_kt": 2}]),
               lambda m: m.save_ss_phys_perf([{"financial_year": "2023-24 ", "plant": "VISL", "series": "finished",
                                               "metric": "actual", "value_kt": 3.0},                 # cut fy
                                              {"financial_year": "2025-26 ", "plant": "SSP", "series": "crude",
                                               "metric": "plan", "value_kt": None}]),                # raw: none
               lambda m: m.save_ss_phys_perf([{"financial_year": "2023-244", "plant": "ASP", "series": "s",
                                               "metric": "m", "value_kt": 1.0}]),                    # 1406
               lambda m: m.save_ss_phys_perf([{"financial_year": "2023-24", "plant": "P" * 9, "series": "s",
                                               "metric": "m", "value_kt": 1.0}]),
               lambda m: m.save_ss_phys_perf([{"financial_year": "2023-24", "plant": "ASP", "series": "s",
                                               "metric": "M" * 9, "value_kt": 1.0}])):
        step(fn)


def test_ipt_requirement_writes(step):
    for fn in (lambda m: m.save_ss_ipt_requirement("2025-26", [
                   {"item": " Blooms ", "from_plant": "BSP", "to_plant": "ASP", "plan_kt": 1.0, "sort_order": "4"},
                   {"item": "slabs", "from_plant": "rsp", "to_plant": "asp", "plan_kt": 2.0},     # ai_ci
                   {"item": "Rounds", "from_plant": "BSP", "to_plant": "BSP"},                   # skipped
                   {"item": "", "from_plant": "BSP", "to_plant": "ASP"},                         # skipped
                   {"item": "Billets", "from_plant": "DSP", "to_plant": "SSP", "plan_kt": 3,
                    "orig_item": "Billets", "orig_from_plant": "BSP", "orig_to_plant": "SSP"},   # rename
                   {"item": "New", "from_plant": "XYZ", "to_plant": "QQ"}]),
               lambda m: m.save_ss_ipt_requirement("2024-25 ", [{"item": "Blooms", "from_plant": "BSP",
                                                                "to_plant": "ASP", "plan_kt": 9.0,
                                                                "orig_item": "Old", "orig_from_plant": "BSP",
                                                                "orig_to_plant": "ASP"}]),
               lambda m: m.save_ss_ipt_requirement("2024-255", [{"item": "Blooms", "from_plant": "BSP",
                                                                "to_plant": "ASP"}]),         # 1406
               lambda m: m.save_ss_ipt_requirement("2024-25", [{"item": "I" * 65, "from_plant": "BSP",
                                                               "to_plant": "ASP"}]),
               lambda m: m.save_ss_ipt_requirement("2024-25", [{"item": "X", "from_plant": "P" * 9,
                                                               "to_plant": "ASP"}]),
               lambda m: m.save_ss_ipt_requirement("2024-25", [{"item": "X", "from_plant": "BSP",
                                                               "to_plant": "ASP", "sort_order": "z"}]),  # ValueError
               lambda m: m.save_ss_ipt_requirement("2027-28", []),
               lambda m: m.delete_ss_ipt_requirement("2025-26", "slabs", "RSP", "ASP"),
               lambda m: m.delete_ss_ipt_requirement("2025-26 ", "Blooms", "BSP", "ASP"),          # raw: none
               lambda m: m.delete_ss_ipt_requirement("2030-31", "x", "y", "z")):
        step(fn)


def test_keys_v2_cannot_hold(seeded):
    """v1 stored a 9..32-character plant_name, a short non-month and a
    grade-club created_at that is not an isoformat() string; v2 refuses them
    before writing anything (parity_exceptions.md §2)."""
    def cw(fn):
        return on_cursor(fn, commit=True)
    for fn in (lambda m: m.save_special_steel_entry("2025-04", "LONGPLANT", "Plates", "G"),
               lambda m: m.save_special_steel_entry("2025-4", "BSP", "Plates", "G"),
               cw(lambda m, c: m.upsert_abp(c, "2025-04", "LONGPLANT", 1.0)),
               cw(lambda m, c: m.upsert_abp(c, "2025-4", "BSP", 1.0)),
               cw(lambda m, c: m.upsert_grade_club(c, "LONGPLANT", "Plates", "G", "L", "2026-10-01T09:00:00")),
               cw(lambda m, c: m.upsert_grade_club(c, "BSP", "Plates", "G", "L", "yesterday")),
               cw(lambda m, c: m.upsert_grade_club(c, "BSP", "Plates", "G", "L", "2026-10-01T09:00:00.5"))):
        with seeded.v1():
            fn(s1)
        n = seeded.data_version(2)
        with seeded.v2():
            with pytest.raises(_keys.OutOfModelError):
                fn(s2)
        assert seeded.data_version(2) == n


def test_every_v2_write_bumps_and_a_dry_run_does_not(seeded):
    def cw(fn):
        return lambda: on_cursor(fn, commit=True)(s2)
    writes = [lambda: s2.save_special_steel_entry("2025-04", "BSP", "Plates", "E250", 1, 1.0, 1.0),
              lambda: s2.clear_special_steel_orders("2025-03", "RSP"),
              lambda: s2.clear_special_steel_orders("2030-01", "RSP"),
              lambda: s2.save_ss_phys_meta([{"plant": "ASP", "series": "crude"}]),
              lambda: s2.save_ss_phys_perf([{"financial_year": "2024-25", "plant": "ASP", "series": "crude",
                                             "metric": "plan", "value_kt": None}]),
              lambda: s2.save_ss_ipt_requirement("2025-26", []),
              lambda: s2.delete_ss_ipt_requirement("2025-26", "Blooms", "BSP", "ASP"),
              cw(lambda m, c: m.upsert_abp(c, "2025-04", "BSP", 5.0)),
              cw(lambda m, c: m.upsert_grade_club(c, "BSP", "Plates", "E250", "X", "2026-10-01T09:00:00")),
              cw(lambda m, c: m.delete_club(c, "BSP", "Plates", "X")),
              cw(lambda m, c: m.delete_grade_club(c, "BSP", "Plates", "E350"))]
    with seeded.v2():
        for w in writes:
            n = seeded.data_version(2)
            w()
            assert seeded.data_version(2) > n
        before = {k: repr(v) for k, v in _reads(s2).items()}
        n = seeded.data_version(2)
        with rc.rollback_tx():
            s2.save_special_steel_entry("2098-01", "DRY", "Plates", "G", 0, 1.0)
            s2.clear_special_steel_orders("2025-04", "ISP")
            s2.save_ss_ipt_requirement("2025-26", [{"item": "Dry", "from_plant": "BSP", "to_plant": "ASP"}])
            on_cursor(lambda m, c: m.upsert_abp(c, "2025-04", "BSP", -1.0))(s2)
            on_cursor(lambda m, c: m.upsert_grade_club(c, "BSP", "Plates", "E250", "Dry", "2026-10-01T09:00:00"))(s2)
            assert {k: repr(v) for k, v in _reads(s2).items()} != before
        assert seeded.data_version(2) == n
        assert {k: repr(v) for k, v in _reads(s2).items()} == before
    assert seeded.sql(2, "SELECT COUNT(*) FROM plant WHERE plant_code = 'DRY'")[0][0] == 0
