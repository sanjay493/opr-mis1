"""Secretary Review second layout (page_secretary_review_hsm), without the DB."""

import io

import pytest
from pptx import Presentation
from pptx.oxml.ns import qn

import page_secretary_review as psr
import page_secretary_review_hsm as hsm
import page_secretary_review_texts as pst
import secretary_review_layout as L
import secretary_review_pptx as sp
from test_secretary_review_render import _all_texts, fake_context

HL = """SAIL achieved best Oct month production for following:-
Hot Metal 1.827 MT (Previous best 1.698 MT in 2024)
Crude Steel 1.718 MT (Previous best 1.604 MT in 2024)
SAIL achieved best ever Apr-Oct FY 26-27 production for following:-
Hot Metal 12.030 MT (Previous best 11.830 MT in 23-24)
Reduction of about 1,88,000 T in the inventory of Saleable Steel."""

DELAYS = """DSP (Oct’26):
BF-2: O/B taken for skip pulley repair – 4 days
BF-3: Operated at reduced blast – 11 days
RSP (Oct’26):
SMS-2: slag yard roof collapsed – 31 days
BSL (Oct’26):
SP MC-1 Down due to Drum Feeder shaft replacement – 3 days"""


@pytest.fixture
def offline(monkeypatch):
    def no_effective(month, keys=None):
        raise AssertionError(f"effective_texts called for {keys}")
    monkeypatch.setattr(psr, "build_context", fake_context)
    monkeypatch.setattr(pst, "effective_texts", no_effective)


def _render(month="2026-10", **texts):
    t = {k: "" for k, _, _ in L.BLOCKS}
    t.update(texts)
    res = psr.render_pptx(month, t, "hsm")
    return res, Presentation(io.BytesIO(res.content))


def test_template_has_every_shape():
    prs = Presentation(str(L.HSM_TEMPLATE_PATH))
    assert len(prs.slides) == 12
    assert not L.hsm_required_shape_names() - set(sp.named_shapes(prs))


def test_render_fills_everything(offline):
    res, out = _render(hl_SAIL=HL, delay_hmcs=DELAYS, delay_fs=DELAYS)
    assert res.filename == "Operation Slides for HSM Review Oct26.pptx"
    assert res.warnings == []
    assert len(out.slides) == 12
    leftover = [(n, t) for n, t in _all_texts(out) if "{" in t]
    assert not leftover, leftover
    shapes = sp.named_shapes(out)
    assert not set(L.HL_PROTOS) & set(shapes)
    assert "Oct’26 & Apr-Oct’26" in out.slides[1].shapes.title.text_frame.text
    assert out.slides[7].shapes.title.text_frame.text.startswith("BSP Techno")
    for s in L.SCOPES:
        for k in L.HSM_KPIS:
            ch = shapes[f"ch_{s}_{k}"].chart
            assert list(ch.plots[0].categories) == ["FY25", "FY26", "FY'27 Target", "Oct", "Apr-Oct"]
            assert ch.plots[0].series[0].values == (1.0,) * 5


def test_sail_table_filled(offline):
    _, out = _render()
    rows = sp.named_shapes(out)["tbl_sail"].table.rows
    hm = [c.text for c in rows[2].cells]
    assert sp.norm(hm[0]) == "hot metal" and hm[1:] == ["1"] * 9


def test_highlight_cards(offline):
    _, out = _render(hl_SAIL=HL)
    texts = [sh.text_frame.text for sh in out.slides[1].shapes if sh.has_text_frame]
    assert any(t.startswith("Oct’26 Highlights") for t in texts)
    assert any(t.startswith("Apr-Oct Highlights") for t in texts)
    assert sum(t.startswith(("Hot Metal\n", "Crude Steel\n")) for t in texts) == 3
    assert any(t.startswith("Reduction of about") for t in texts)


def test_parse_highlights():
    g = hsm.parse_highlights(HL)
    assert [len(x["tiles"]) for x in g] == [2, 1]
    assert g[0]["tiles"][0] == ("Hot Metal", "1.827 MT", "(Previous best 1.698 MT in 2024)")
    assert g[1]["notes"] == ["Reduction of about 1,88,000 T in the inventory of Saleable Steel."]
    assert hsm.parse_highlights("") == []


def test_no_highlights_leaves_no_cards(offline):
    _, out = _render()
    assert not [sh for sh in out.slides[1].shapes if sh.name.startswith("hl_")]
    assert len([sh for sh in out.slides[1].shapes if "Highlights" in (sh.text_frame.text if sh.has_text_frame else "")]) == 0


def test_delay_rows(offline):
    _, out = _render(delay_hmcs=DELAYS)
    table = sp.named_shapes(out)["tbl_delay_hmcs"].table
    assert len(table.rows) == 3
    assert table.cell(0, 0)._tc.get("rowSpan") == "3"
    assert [table.cell(i, 1).text for i in range(3)] == ["DSP (Oct’26)", "RSP (Oct’26)", "BSL (Oct’26)"]
    para = table.cell(0, 2).text_frame.paragraphs[0]
    assert [r.text for r in para.runs] == ["BF-2:", " O/B taken for skip pulley repair – 4 days"]
    assert para.runs[0].font.bold and not para.runs[1].font.bold
    # no unit prefix: only the plain run
    assert [r.text for r in table.cell(2, 2).text_frame.paragraphs[0].runs] == \
        ["SP MC-1 Down due to Drum Feeder shaft replacement – 3 days"]


def test_no_delays(offline):
    _, out = _render()
    table = sp.named_shapes(out)["tbl_delay_fs"].table
    assert len(table.rows) == 1 and "rowSpan" not in table.cell(0, 0)._tc.attrib
    assert table.cell(0, 2).text == "No major delays"


def test_fit_value_axis():
    prs = Presentation(str(L.HSM_TEMPLATE_PATH))
    ch = sp.named_shapes(prs)["ch_DSP_pci"].chart
    sp.fit_value_axis(ch, [65, 60, 77, 70, None], 10)
    sc = ch._chartSpace.find(".//" + qn("c:valAx") + "/" + qn("c:scaling"))
    assert [el.tag.split("}")[1] for el in sc] == ["orientation", "max", "min"]
    vmin, vmax = float(sc.find(qn("c:min")).get("val")), float(sc.find(qn("c:max")).get("val"))
    assert vmin < 60 and vmax > 77
    sp.fit_value_axis(ch, [None], 10)
    assert sc.find(qn("c:min")) is None and sc.find(qn("c:max")) is None
