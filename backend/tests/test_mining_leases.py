"""SAIL mining leases (Annexure-1): span validation and the page rows, no database."""
import pytest

import mining_leases as ml


def _row(**kw):
    base = {"s_no": "", "mine": "", "state": "", "lease": "L", "mineral": "", "area": "", "reserves": "",
            "status": "", "mine_span": 1, "state_span": 1, "lease_span": 1, "mineral_span": 1, "area_span": 1,
            "reserves_span": 1, "status_span": 1, "grp": "", "grp_span": 1}
    base.update(kw)
    return base


def test_span_overrun_rejected():
    with pytest.raises(ValueError, match="row 2.*mine"):
        ml.validate([_row(), _row(mine="K", mine_span=3)])


def test_covered_cell_with_value_rejected():
    rows = [_row(mine="K", mine_span=2), _row(mine="other", mine_span=0)]
    with pytest.raises(ValueError, match="row 2.*mine"):
        ml.validate(rows)


def test_span_zero_without_a_head_rejected():
    with pytest.raises(ValueError, match="row 1.*state"):
        ml.validate([_row(state_span=0)])


def test_head_over_a_row_with_its_own_span_rejected():
    rows = [_row(mine="K", mine_span=2), _row(mine_span=1)]
    with pytest.raises(ValueError, match="row 2.*mine"):
        ml.validate(rows)


def test_spans_are_normalised_to_ints():
    out = ml.validate([_row(mine="K", mine_span="2"), _row(mine_span="0")])
    assert [r["mine_span"] for r in out] == [2, 0]


def test_head_span_covers_following_rows_in_page(monkeypatch):
    rows = [_row(s_no="1", mine="Kiriburu", mine_span=2), _row(s_no="2", mine="", mine_span=0, lease="Topailore")]
    monkeypatch.setattr(ml, "_stored", lambda: rows)
    page = ml.build_page()
    assert page["available"] is True
    assert (page["rows"][0]["mine"]["text"], page["rows"][0]["mine"]["span"]) == ("Kiriburu", 2)
    assert (page["rows"][1]["mine"]["text"], page["rows"][1]["mine"]["span"]) == ("", 0)
    assert page["rows"][1]["lease"]["text"] == "Topailore"


def test_verbatim_free_text_kept(monkeypatch):
    monkeypatch.setattr(ml, "_stored", lambda: [_row(reserves="208( Broken area- 11MT)", area="25.98 (Block A)")])
    r = ml.build_page()["rows"][0]
    assert r["reserves"]["text"] == "208( Broken area- 11MT)" and r["area"]["text"] == "25.98 (Block A)"


def test_blank_cells_print_empty_not_none(monkeypatch):
    monkeypatch.setattr(ml, "_stored", lambda: [_row(mine=None, state=None)])
    r = ml.build_page()["rows"][0]
    assert r["mine"]["text"] == "" and r["state"]["text"] == ""


def test_empty_table_page_unavailable(monkeypatch):
    monkeypatch.setattr(ml, "_stored", lambda: [])
    page = ml.build_page()
    assert page["available"] is False and page["rows"] == []


def test_group_column_spans_and_validates(monkeypatch):
    rows = [_row(grp="Flux", grp_span=2), _row(grp_span=0)]
    assert [r["grp_span"] for r in ml.validate(rows)] == [2, 0]
    monkeypatch.setattr(ml, "_stored", lambda: rows)
    g = ml.build_page()["rows"][0]["grp"]
    assert (g["text"], g["span"]) == ("Flux", 2)
    with pytest.raises(ValueError, match="row 1.*grp"):
        ml.validate([_row(grp="Flux", grp_span=3), _row(grp_span=0)])


def test_group_box_flags_mark_the_cells_on_a_category_boundary(monkeypatch):
    # Flux = rows 1-2 (status merged over both), Coal = rows 3-4
    rows = [_row(grp="Flux", grp_span=2, status="Op", status_span=2), _row(grp_span=0, status_span=0),
            _row(grp="Coal", grp_span=2), _row(grp_span=0)]
    monkeypatch.setattr(ml, "_stored", lambda: rows)
    r = ml.build_page()["rows"]
    assert (r[0]["grp"]["gt"], r[0]["grp"]["gb"]) == (True, True)        # the Flux label spans the whole block
    assert (r[0]["status"]["gt"], r[0]["status"]["gb"]) == (True, True)  # merged over rows 1-2: top of 1, end of 2
    assert (r[0]["mine"]["gt"], r[0]["mine"]["gb"]) == (True, False)     # row 1 mine: block top only
    assert (r[1]["mine"]["gt"], r[1]["mine"]["gb"]) == (False, True)     # row 2 mine: block bottom only
    assert (r[2]["mine"]["gt"], r[3]["mine"]["gb"]) == (True, True)
    assert (r[0]["first"], r[1]["last"], r[2]["first"], r[3]["last"]) == (True, True, True, True)
