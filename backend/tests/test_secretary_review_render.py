import calendar
import io
import re
from pathlib import Path

import pytest
from pptx import Presentation

import board_note_common as bnc
import page_secretary_review as psr
import page_secretary_review_texts as pst
import secretary_review_layout as L
import secretary_review_pptx as sp
from test_secretary_review_context import db_up, live

REF = Path(__file__).parent / "fixtures" / "secretary_review_sep26_reference.pptx"

# (slide, row, col) -> reason, for reference-deck cells the DB no longer reproduces.
# Every entry needs a reason checked by hand.
KNOWN_TABLE_DIFFS = {}


def _num(s):
    s = s.replace(",", "").strip()
    return float(s) if re.fullmatch(r"-?\d+(\.\d+)?", s) else None


def _perf_tables(slide):
    return [sh.table for sh in slide.shapes if getattr(sh, "has_table", False) and sh.has_table
            and len(sh.table.rows) > 1 and len(sh.table.columns) == 10]


def fake_context(month):
    """build_context stand-in (no DB): every figure 1, every KPI on time."""
    labels = L.period_labels(month)
    months = bnc.fy_months(labels["fy_start"])[:labels["n"]]
    row = {k: 1.0 for k in psr.VALUE_COLS}
    production = {item: {s: dict(row) for s in L.SCOPES + ["SSPs", "TOTAL_CONV"]} for item, _ in psr.ITEMS}
    kpi = {"fy_m2": 1.0, "fy_m1": 1.0, "target": 1.0, "month": 1.0, "ytd": 1.0, "month_used": month,
           "trend": [(calendar.month_abbr[int(m[5:])], 1.0) for m in months]}
    techno = {s: {k: dict(kpi) for k, _, _ in L.KPIS} for s in L.SCOPES}
    return {"labels": labels, "production": production, "techno": techno, "warnings": []}


@pytest.fixture
def offline(monkeypatch):
    """render_pptx without the DB: fake context; effective_texts must not be
    needed when every block is passed in."""
    def no_effective(month, keys=None):
        raise AssertionError(f"effective_texts called for {keys}")
    monkeypatch.setattr(psr, "build_context", fake_context)
    monkeypatch.setattr(pst, "effective_texts", no_effective)


@pytest.fixture(scope="module")
def rendered():
    texts = {k: "" for k, _, _ in L.BLOCKS}
    texts["hl_SAIL"] = "Line one:\nLine two"
    res = psr.render_pptx("2026-09", texts)
    return res, Presentation(io.BytesIO(res.content))


@live
def test_tables_match_reference(rendered):
    _, out = rendered
    ref = Presentation(str(REF))
    diffs = []
    for idx in (2, 3, 5, 8, 10, 12, 14, 16):
        for t_out, t_ref in zip(_perf_tables(out.slides[idx - 1]), _perf_tables(ref.slides[idx - 1])):
            for r, (row_o, row_r) in enumerate(zip(t_out.rows, t_ref.rows)):
                for c, (co, cr) in enumerate(zip(row_o.cells, row_r.cells)):
                    a, b = _num(co.text), _num(cr.text)
                    if b is not None and (a is None or abs(a - b) > 1) and (idx, r, c) not in KNOWN_TABLE_DIFFS:
                        diffs.append((idx, r, c, co.text, cr.text))
    assert not diffs, diffs


@live
def test_charts_filled(rendered):
    _, out = rendered
    shapes = sp.named_shapes(out)
    ch = shapes["ch_SAIL_coke"].chart
    assert list(ch.plots[0].categories) == ["FY25", "FY26", "FY'27 Target", "Sep", "Apr-Sep"]
    assert ch.plots[0].series[0].values == (421.0, 419.0, 400.0, 432.0, 424.0)
    tr = shapes["trend_BSP_fuel"].chart
    assert list(tr.plots[0].categories)[:3] == ["FY25", "FY26", "FY'27 Target"]
    assert list(tr.plots[0].categories)[-1] == "Sep"


@live
def test_labels_and_narrative(rendered):
    res, out = rendered
    assert res.filename == "SECRETARY REVIEW Operations Inputs Sep26.pptx"
    all_text = " ".join(sh.text_frame.text for s in out.slides for sh in s.shapes if sh.has_text_frame)
    assert "{" not in all_text and "Sep’26" in all_text
    shapes = sp.named_shapes(out)
    hl = shapes["tbl_sail_hl"].table.cell(0, 1).text_frame
    assert [p.text for p in hl.paragraphs] == ["Line one:", "Line two"]
    assert "tbl_BSP_hl" not in shapes                     # empty highlights -> table removed
    bd = shapes["tbl_bd_BSP"].table
    assert len(bd.rows) == 1 and bd.cell(0, 1).text == "No major breakdowns"


@db_up
def test_render_month_without_data():
    res = psr.render_pptx("2030-01", {k: "" for k, _, _ in L.BLOCKS})
    out = Presentation(io.BytesIO(res.content))
    assert len(out.slides) == 30
    assert res.filename.endswith("Jan30.pptx")


def test_missing_texts_fall_back_to_effective(monkeypatch):
    asked = []

    def eff(month, keys=None):
        asked.append(list(keys))
        return {k: {"text": "DB " + k if k == "delay_hmcs" else "", "saved": False} for k in keys}
    monkeypatch.setattr(psr, "build_context", fake_context)
    monkeypatch.setattr(pst, "effective_texts", eff)
    res = psr.render_pptx("2030-01", {"delay_fs": "MILL: x – 3 days"})
    out = Presentation(io.BytesIO(res.content))
    shapes = sp.named_shapes(out)
    assert shapes["tbl_delay_fs"].table.cell(0, 1).text == "MILL: x – 3 days"
    assert shapes["tbl_delay_hmcs"].table.cell(0, 1).text == "DB delay_hmcs"
    assert asked == [[k for k, _, _ in L.BLOCKS if k != "delay_fs"]]


def _all_texts(out):
    for slide in out.slides:
        for sh in slide.shapes:
            if sh.has_text_frame:
                yield sh.name, sh.text_frame.text
            if getattr(sh, "has_table", False) and sh.has_table:
                for row in sh.table.rows:
                    for cell in row.cells:
                        yield sh.name, cell.text


def test_august_labels_and_no_placeholders_left(offline):
    texts = {k: "" for k, _, _ in L.BLOCKS}
    for k in ("hl_SAIL",) + tuple(f"hl_{p}" for p in L.PLANTS):
        texts[k] = "Best ever:-\nHot Metal 1.000 MT"
    res = psr.render_pptx("2026-08", texts)
    out = Presentation(io.BytesIO(res.content))
    assert res.filename == "SECRETARY REVIEW Operations Inputs Aug26.pptx"
    leftover = [(n, t) for n, t in _all_texts(out) if "{" in t]
    assert not leftover, leftover
    shapes = sp.named_shapes(out)
    assert "Aug’26 & Apr-Aug’26" in shapes["title_2"].text_frame.text
    sail_cells = [c.text for r in shapes["tbl_sail"].table.rows for c in r.cells]
    assert "Aug’26" in sail_cells and "Apr-Aug’26" in sail_cells and "% Growth Over Aug’25" in sail_cells
    cr_cells = [c.text.strip() for r in shapes["tbl_cr_1"].table.rows for c in r.cells]
    assert "Apr-Aug’26" in cr_cells and "Apr-Aug’25" in cr_cells
    ch = shapes["ch_SAIL_coke"].chart
    assert list(ch.plots[0].categories)[-2:] == ["Aug", "Apr-Aug"]


def test_highlight_headers_uniform(offline):
    texts = {k: "" for k, _, _ in L.BLOCKS}
    for k in ("hl_SAIL",) + tuple(f"hl_{p}" for p in L.PLANTS):
        texts[k] = "Line"
    out = Presentation(io.BytesIO(psr.render_pptx("2026-09", texts).content))
    shapes = sp.named_shapes(out)
    heads = {n: shapes[n].table.cell(0, 0).text for n in ["tbl_sail_hl"] + [f"tbl_{p}_hl" for p in L.PLANTS]}
    assert set(heads.values()) == {"H-1 Highlights"}, heads


def _cr_run_sizes(out):
    t = sp.named_shapes(out)["tbl_cr_1"].table
    return {int(r.font._element.get("sz")) for row in t.rows if row.cells[0].text.strip().upper() in L.PLANTS
            for c in list(row.cells)[1:3]
            for p in c.text_frame.paragraphs for r in p.runs if r.font._element.get("sz")}


def _render_cr(n):
    texts = {k: "" for k, _, _ in L.BLOCKS}
    texts["cr_BSP_cur"] = "\n".join(f"Item {i}: repair work" for i in range(n))
    res = psr.render_pptx("2030-01", texts)
    return res, Presentation(io.BytesIO(res.content))


def test_long_capital_repairs_text_is_scaled(offline):
    res, out = _render_cr(25)
    sizes = _cr_run_sizes(out)
    assert sizes and max(sizes) < 1200 and min(sizes) >= 800
    if min(sizes) == 800:
        assert any("Capital repairs (slide 19)" in w for w in res.warnings)


def test_overlong_capital_repairs_text_warns(offline):
    res, out = _render_cr(45)
    assert _cr_run_sizes(out) == {800}
    assert any("Capital repairs (slide 19)" in w and "may overflow" in w for w in res.warnings)


def test_short_capital_repairs_text_keeps_template_size(offline):
    res, out = _render_cr(3)
    assert _cr_run_sizes(out) == {1200}
    assert not any("Capital repairs" in w for w in res.warnings)
