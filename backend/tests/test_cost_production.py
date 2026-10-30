"""cost_production.generate: monthly/yearly columns, Total = Variable +
Fixed, till-month fallback note, product filter. Repo reads stubbed."""
import datetime as dt

import pytest

import cost_production as cp
import cost_production_pdf as cpp

TODAY = dt.date(2026, 10, 29)


def _m(v, f=None, tv=None, tf=None, plant="BSP"):
    out = {"VARIABLE": {plant: {"month": v, "till_month": tv}}, "TOTAL": {}}
    if f is not None or tf is not None:
        out["FIXED"] = {plant: {"month": f, "till_month": tf}}
    return out


MONTHLY = {
    "HM": {"2026-04": _m(100, 10, 100, 10), "2026-05": _m(200, 20, 150, 15)},
    "SINTER": {"2026-04": _m(50, None, 50)},
}
ANNUAL = {"HM": {"2025-26": {"VARIABLE": {"BSP": 900}, "FIXED": {"BSP": 90}}}}


@pytest.fixture(autouse=True)
def stub_repo(monkeypatch):
    def monthly(product, months):
        return {m: MONTHLY.get(product, {}).get(m, {}) for m in months}

    def annual(product, fys):
        return {fy: ANNUAL.get(product, {}).get(fy, {}) for fy in fys}

    monkeypatch.setattr(cp.rct, "get_cost_trend_monthly", monthly)
    monkeypatch.setattr(cp.rct, "get_cost_trend_annual", annual)


def _row(prod, cost_type, plant="BSP"):
    block = next(b for b in prod["blocks"] if b["cost_type"] == cost_type)
    return next(r for r in block["rows"] if r["plant"] == plant)["values"]


def test_fy_options():
    assert cp.fy_options(TODAY) == ["2026-27", "2025-26", "2024-25", "2023-24", "2022-23", "2021-22", "2020-21"]
    assert cp.fy_options(dt.date(2027, 3, 31))[0] == "2026-27"


def test_monthly_columns_and_total():
    d = cp.generate("monthly", "2026-27", today=TODAY)
    assert [p["label"] for p in d["periods"]] == ["Apr'26", "May'26", "Apr-May'26"]
    hm = next(p for p in d["products"] if p["code"] == "HM")
    assert _row(hm, "TOTAL") == [110.0, 220.0, 165.0]
    assert _row(hm, "FIXED") == [10.0, 20.0, 15.0]
    assert _row(hm, "TOTAL", "DSP") == [None, None, None]
    assert hm["note"] is None


def test_monthly_till_falls_back_with_note():
    d = cp.generate("monthly", "2026-27", today=TODAY)
    sinter = next(p for p in d["products"] if p["code"] == "SINTER")
    assert _row(sinter, "TOTAL") == [50.0, None, 50.0]
    assert sinter["note"] == "Apr-May'26 column shows Apr'26 (no May'26 entry yet)"


def test_yearly_annual_then_running_fy():
    d = cp.generate("yearly", today=TODAY)
    assert [p["label"] for p in d["periods"]] == ["2025-26", "2026-27 (Apr-May'26)"]
    hm = next(p for p in d["products"] if p["code"] == "HM")
    assert _row(hm, "TOTAL") == [990.0, 165.0]


def test_product_filter_and_empty_fy():
    d = cp.generate("monthly", "2024-25", products=["CS"], today=TODAY)
    assert [p["code"] for p in d["products"]] == ["CS"]
    assert d["periods"] == []
    assert "No cost of production data" in cpp.build_html(d, {})


def test_cost_type_filter():
    d = cp.generate("monthly", "2026-27", today=TODAY, cost_types=["FIXED"])
    assert all([b["cost_type"] for b in p["blocks"]] == ["FIXED"] for p in d["products"])
    hm = next(p for p in d["products"] if p["code"] == "HM")
    assert _row(hm, "FIXED") == [10.0, 20.0, 15.0]


def test_pdf_html_has_one_sheet_per_product():
    html = cpp.build_html(cp.generate("monthly", "2026-27", today=TODAY), {})
    assert html.count('class="sheet"') == len(cp.PRODUCTS)
    assert "165" in html and "Apr-May&#x27;26" not in html
