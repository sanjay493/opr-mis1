"""Unique Activities: repo.misc's unique_activity functions and the API."""
import pytest
from fastapi import HTTPException

import api_unique_activity as api
from repo import conn as rc
from repo import misc as rmisc


def _n():
    with rc.cursor() as cur:
        cur.execute("SELECT n FROM data_version WHERE id = 1")
        return cur.fetchone()[0]


def test_save_read_search_delete(mysql_db):
    n0 = _n()
    a = rmisc.save_unique_activity(None, "2026-07-16", "BSL", "BF-3", "BF-3 blown in after capital repair",
                                   "Blown in on 16 Jul after a 14-month capital repair.",
                                   ["Revival after CR", "Blast Furnace"], "a@sail.in")
    b = rmisc.save_unique_activity(None, "2026-09-02", "RSP", None, "New Sinter Plant-3 commissioned",
                                   "First sinter produced.", ["New unit start-up"], "a@sail.in")
    assert _n() > n0

    rows = rmisc.unique_activity_rows()
    assert [r["id"] for r in rows] == [b, a]                         # newest first
    assert rows[1]["tags"] == ["Blast Furnace", "Revival after CR"]
    assert rows[1]["activity_date"] == "2026-07-16" and rows[1]["created_by"] == "a@sail.in"

    assert [r["id"] for r in rmisc.unique_activity_rows(q="capital")] == [a]       # description
    assert [r["id"] for r in rmisc.unique_activity_rows(q="start-up")] == [b]      # tag text
    assert [r["id"] for r in rmisc.unique_activity_rows(tag="revival after cr")] == [a]   # case-insensitive
    assert [r["id"] for r in rmisc.unique_activity_rows(plant_code="RSP")] == [b]
    assert [r["id"] for r in rmisc.unique_activity_rows(date_from="2026-08-01")] == [b]
    assert rmisc.unique_activity_tag_counts() == [("Blast Furnace", 1), ("New unit start-up", 1),
                                                  ("Revival after CR", 1)]

    assert rmisc.save_unique_activity(a, "2026-07-16", "BSL", "BF-3", "BF-3 revived", "Same text.",
                                      ["Milestone"], "b@sail.in") == a
    row = rmisc.unique_activity_row(a)
    assert row["title"] == "BF-3 revived" and row["tags"] == ["Milestone"] and row["updated_by"] == "b@sail.in"
    assert rmisc.save_unique_activity(999, "2026-07-16", None, None, "x", "y", [], "b") is None

    assert rmisc.delete_unique_activity(a) is True
    assert rmisc.delete_unique_activity(a) is False
    assert rmisc.unique_activity_row(a) is None
    assert [t for t, _ in rmisc.unique_activity_tag_counts()] == ["New unit start-up"]   # tags cascade


def test_validation():
    ok = dict(activity_date="2026-07-16", title=" BF-3  revived ", description="text",
              plant_code="bsl", tags=["Revival after CR", "revival after cr", " Record "])
    v = api._validated(api.ActivityRequest(**ok))
    assert v["title"] == "BF-3 revived" and v["plant_code"] == "BSL"
    assert v["tags"] == ["Revival after CR", "Record"]
    for bad in ({"activity_date": "16/07/2026"}, {"activity_date": "2026-02-30"}, {"title": "  "},
                {"description": ""}, {"plant_code": "XYZ"}, {"tags": ["x" * 49]}):
        with pytest.raises(HTTPException):
            api._validated(api.ActivityRequest(**{**ok, **bad}))
