"""repo.techno.rows_for_months served from the report_context bulk load must
return exactly what the SQL path returns: same list type, same rows in the
same order (month, then upload seq), same row type and keys, same values.
Seeded so that seq order differs from plant/unit alphabetical order, with
months both inside and outside the report month's window."""
import random

import pytest

import dbengine
import report_context
from repo import techno as rt

REPORT_MONTH = "2026-08"


def _blob(i):
    return {"month": {"Coke Rate": 430 + i, "Sinter": 1.5 * i, "Note": "x"},
            "till_month": {"Coke Rate": 431.25 + i}}


def _seed_rows():
    rows = []
    units = [("SAIL", "Shop"), ("RSP", "BF-1"), ("BSP", "Shop"), ("DSP", "General"), ("BSP", "BF-2"),
             ("ISP", "Shop")]
    i = 0
    # inserted month-by-month in a deliberately non-alphabetical order
    for month in ("2026-08", "2026-04", "2024-03", "2026-06", "2025-12", "2026-07"):
        for plant, unit in random.Random(month).sample(units, len(units)):
            i += 1
            rows.append((month, plant, unit, _blob(i), f"f{i}.xlsx", f"2026-08-0{1 + i % 8} 10:00:0{i % 10}"))
    return rows


MONTH_SETS = [
    ["2026-08"], ["2026-08", "2026-07"], ["2026-04", "2024-03"], ["2024-03"], ["2026-06", "2026-06", "2025-12"],
    ["2026-07", "2026-04", "2026-08", "2024-03", "2025-12", "2026-06"], ["2030-01"], ["2026-08", "2030-01"],
]


def _same(ref, got):
    assert type(ref) is type(got) and len(ref) == len(got)
    for a, b in zip(ref, got):
        assert type(a) is type(b)
        assert hasattr(a, 'keys') == hasattr(b, 'keys')
        if hasattr(a, 'keys'):
            assert a.keys() == b.keys()
        assert list(a) == list(b)
        assert [type(v) for v in a] == [type(v) for v in b]


@pytest.mark.parametrize("row_factory", [None, True])
def test_served_rows_equal_sql_rows(v2seed, row_factory, monkeypatch):
    served = []
    real = rt._rows_for_months_served
    monkeypatch.setattr(rt, '_rows_for_months_served', lambda *a: served.append(real(*a)) or served[-1])
    v2seed.seed_techno(_seed_rows())
    for months in MONTH_SETS:
        conn = dbengine.connect()
        if row_factory:
            conn.row_factory = True
        try:
            cur = conn.cursor()
            ref = rt._rows_for_months_sql(cur, months)
            with report_context.activate(REPORT_MONTH):
                got = rt.rows_for_months(cur, months)
                again = rt.rows_for_months(cur, months)
            _same(ref, got)
            _same(ref, again)
        finally:
            conn.close()
    # the bulk-load path really answered (not the SQL fallback) for the in-window sets
    assert sum(r is not None for r in served) >= 10
    # something real was compared
    conn = dbengine.connect()
    try:
        assert len(rt._rows_for_months_sql(conn.cursor(), ["2026-08", "2026-04"])) == 12
    finally:
        conn.close()
