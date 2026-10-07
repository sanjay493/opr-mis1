# Secretary Review PPTX Generator Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A tab at `/reports/external?tab=secretary-review` where the user picks a month, edits DB-prefilled narrative, and downloads the "SECRETARY REVIEW Operations Inputs" deck filled with that month's data.

**Architecture:** The user-updated Sep'26 deck is turned (once, by a script) into a template with stable shape names and `{MON}`-style placeholders. `page_secretary_review.py` builds a data context (production via `page4._p4_row_values`, techno via `techno_period.build_period_report`) and fills the template with python-pptx: table-cell text, native chart data via `chart.replace_data()`, narrative blocks from a new `secretary_review_text` table (DB defaults from `page_secretary_review_texts.py`). A FastAPI router serves context, texts and the file; a Next.js View edits and downloads.

**Tech Stack:** Python 3 / FastAPI / python-pptx 1.0.2 / MySQL via `db.connect()` (sqlite dialect) / Next.js 16 (React client component).

**Spec:** `docs/superpowers/specs/2026-10-07-secretary-review-pptx-design.md`

## Global Constraints

- Python: always `backend/venv/Scripts/python.exe`, tools as `python.exe -m <tool>` (Device Guard blocks pip `.exe` launchers).
- `backend/requirements.txt` is pinned exactly: `python-pptx==1.0.2`; regenerate `requirements-lock.txt` with `pip freeze`; then `python -m playwright install --force chromium` (CLAUDE.md rule after any requirements change).
- Backend SQL is written in sqlite dialect (`?`, `ON CONFLICT`) through `db.connect()`; a new table needs the SQLite `CREATE TABLE` in `db.init_db`, `scripts/mysql_schema.sql`, and a `scripts/migrate_*.sql`. This machine runs MySQL (`DB_ENGINE=mysql`).
- Shapes are found by name, never by slide index (slide indices are used only inside the one-off prep script).
- Production numbers must come from `page4._p4_row_values` so they agree with the MIS report.
- Template file: `backend/secretary_review_templates/secretary_review.pptx`. Reference deck: `G:\My Drive\Report_format\work\SECRETARY REVIEW Operations Inputs Sep26 update.pptx`.
- Download filename: `SECRETARY REVIEW Operations Inputs <Mon><YY>.pptx` (e.g. `Sep26`).
- CO₂ uses the latest month with SAIL CO₂ data, no later than the selected month; its chart labels follow that month.
- Period names: n=3 → Q1/Q-1, n=6 → H1/H-1, n=9 → 9M, n=12 → FY, else `Apr-<Mon>` (n = months elapsed in FY).
- Narrative blocks: plain text, one paragraph per line, blank lines dropped; a line ending in `:` is bold.
- An empty saved block stays empty (stored as `''`), it does not fall back to the DB default.
- Frontend: read `frontend/AGENTS.md` first (Next 16). Register the tab in `reportGroups.js` (external group) and the `VIEWS` map in `ReportTabs.js`.
- Commit messages end with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`. Do not push.

## Review Focus

1. A month with no production/techno data yet (e.g. `2030-01`) — expect a deck with blank cells/points and warnings, never a 500. Test: Task 6 `test_render_month_without_data`.
2. April (n=1): YTD equals the month; labels must not read "Apr-Apr" twice in charts. Test: Task 2 `test_period_labels_april`.
3. Jan–Mar months cross the calendar year (FY start, CPLY, YTD labels). Test: Task 2 `test_period_labels_january`.
4. Narrative with `&`, `<`, blank lines or a trailing `:` — must be XML-safe, blank lines dropped, header bold. Test: Task 1 `test_set_text_lines_escapes_and_drops_blanks`.
5. Breakdowns/CRs that start before or run past the month, or are ongoing — hours/days clipped to the month. Tests: Task 5 `test_event_hours_clipped_to_month`, `test_cr_line_ongoing_clipped`.

---

### Task 1: python-pptx dependency and fill helpers

**Files:**
- Modify: `backend/requirements.txt`, `backend/requirements-lock.txt`
- Create: `backend/secretary_review_pptx.py`
- Test: `backend/tests/test_secretary_review_pptx.py`

**Interfaces:**
- Produces (`secretary_review_pptx`):
  - `norm(s: str) -> str` — collapse whitespace, lowercase.
  - `named_shapes(prs) -> dict[str, Shape]` — first shape per name, all slides, recursing into groups.
  - `set_text_lines(text_frame, lines: list[str], header_bold: bool = False) -> None`
  - `sub_paragraphs(text_frame, fn: Callable[[str], str]) -> None`
  - `replace_placeholders(prs, mapping: dict[str, str]) -> None` — replaces `{KEY}` in every text frame and table cell.
  - `replace_chart_data(chart, categories: list[str], values: list[float|None], number_format: str) -> None`
  - `remove_shape(shape) -> None`, `remove_row(table, idx: int) -> None`

- [ ] **Step 1: Add the dependency**

Append to `backend/requirements.txt`:

```
python-pptx==1.0.2  # Secretary Review deck (page_secretary_review.py) — fills secretary_review_templates/*.pptx
```

Run (from `backend/`):

```
venv/Scripts/python.exe -m pip install -r requirements.txt
venv/Scripts/python.exe -m pip freeze > requirements-lock.txt
venv/Scripts/python.exe -m playwright install --force chromium
```

Expected: `Successfully installed python-pptx-1.0.2 XlsxWriter-…`. `git diff requirements-lock.txt` shows only `python-pptx` and `XlsxWriter` added.

- [ ] **Step 2: Write the failing tests**

`backend/tests/test_secretary_review_pptx.py`:

```python
import io

from pptx import Presentation
from pptx.chart.data import CategoryChartData
from pptx.enum.chart import XL_CHART_TYPE
from pptx.util import Inches

import secretary_review_pptx as sp


def _deck_with_table(rows=3, cols=2):
    prs = Presentation()
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    gf = slide.shapes.add_table(rows, cols, Inches(1), Inches(1), Inches(6), Inches(2))
    gf.name = "tbl_x"
    return prs, slide, gf


def test_norm_collapses_whitespace():
    assert sp.norm("  Crude\n  Steel ") == "crude steel"


def test_named_shapes_finds_by_name():
    prs, _, _ = _deck_with_table()
    assert "tbl_x" in sp.named_shapes(prs)


def test_set_text_lines_escapes_and_drops_blanks():
    prs, _, gf = _deck_with_table()
    tf = gf.table.cell(0, 1).text_frame
    sp.set_text_lines(tf, ["BSP (Sep’26):", "", "BF-4: R&D <test> – 15 days", "   "], header_bold=True)
    paras = tf.paragraphs
    assert [p.text for p in paras] == ["BSP (Sep’26):", "BF-4: R&D <test> – 15 days"]
    assert paras[0].runs[0].font.bold is True
    assert paras[1].runs[0].font.bold is False
    buf = io.BytesIO()
    prs.save(buf)                      # must serialise (XML-escaped)
    Presentation(io.BytesIO(buf.getvalue()))


def test_set_text_lines_empty_list_leaves_one_empty_paragraph():
    prs, _, gf = _deck_with_table()
    tf = gf.table.cell(0, 0).text_frame
    sp.set_text_lines(tf, [])
    assert [p.text for p in tf.paragraphs] == [""]


def test_replace_placeholders_in_tables_and_text():
    prs, slide, gf = _deck_with_table()
    gf.table.cell(0, 0).text = "% Growth Over {CPLY}"
    tb = slide.shapes.add_textbox(Inches(1), Inches(4), Inches(4), Inches(1))
    tb.text_frame.text = "SAIL Performance : {MON} & {YTD}"
    sp.replace_placeholders(prs, {"CPLY": "Sep’25", "MON": "Sep’26", "YTD": "Apr-Sep’26"})
    assert gf.table.cell(0, 0).text == "% Growth Over Sep’25"
    assert tb.text_frame.text == "SAIL Performance : Sep’26 & Apr-Sep’26"


def test_remove_row_and_shape():
    prs, slide, gf = _deck_with_table(rows=3)
    sp.remove_row(gf.table, 1)
    assert len(gf.table.rows) == 2
    sp.remove_shape(gf)
    assert "tbl_x" not in sp.named_shapes(prs)


def test_replace_chart_data_keeps_point_formatting():
    prs = Presentation()
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    cd = CategoryChartData()
    cd.categories = ["FY25", "FY26", "FY'27 Target", "Sep", "Apr-Sep"]
    cd.add_series("Series 1", (1, 2, 3, 4, 5))
    chart = slide.shapes.add_chart(XL_CHART_TYPE.COLUMN_CLUSTERED, 0, 0, Inches(4), Inches(3), cd).chart
    pt = chart.plots[0].series[0].points[2]
    pt.format.fill.solid()
    before = len(chart._chartSpace.xpath(".//c:dPt"))
    sp.replace_chart_data(chart, ["FY26", "FY27", "FY'28 Target", "Oct", "Apr-Oct"], [421, None, 400, 432, 424], "0")
    assert len(chart._chartSpace.xpath(".//c:dPt")) == before == 1
    assert list(chart.plots[0].categories) == ["FY26", "FY27", "FY'28 Target", "Oct", "Apr-Oct"]
    assert chart.plots[0].series[0].values == (421.0, None, 400.0, 432.0, 424.0)
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `venv/Scripts/python.exe -m pytest tests/test_secretary_review_pptx.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'secretary_review_pptx'`.

- [ ] **Step 4: Implement `backend/secretary_review_pptx.py`**

```python
"""python-pptx helpers for filling the Secretary Review template
(page_secretary_review.py). Everything edits the existing XML in place so
the template's fonts, colours and chart styling survive."""

import copy
import re

from pptx.chart.data import CategoryChartData
from pptx.enum.shapes import MSO_SHAPE_TYPE
from pptx.oxml.ns import qn
from pptx.oxml.xmlchemy import OxmlElement


def norm(s: str) -> str:
    return re.sub(r"\s+", " ", s or "").strip().lower()


def named_shapes(prs) -> dict:
    out = {}

    def walk(shapes):
        for sh in shapes:
            if sh.shape_type == MSO_SHAPE_TYPE.GROUP:
                walk(sh.shapes)
            elif sh.name:
                out.setdefault(sh.name, sh)

    for slide in prs.slides:
        walk(slide.shapes)
    return out


def _rpr_from_end(end):
    """A run's rPr copied from a paragraph's endParaRPr, so a run added to an
    empty template cell gets the cell's font."""
    rpr = OxmlElement("a:rPr")
    for k, v in end.attrib.items():
        rpr.set(k, v)
    for child in end:
        rpr.append(copy.deepcopy(child))
    return rpr


def set_text_lines(text_frame, lines, header_bold=False):
    """Replace the frame's paragraphs with one paragraph per non-blank line,
    each formatted like the frame's first paragraph/run. header_bold: a line
    ending in ':' is bold, every other line not bold."""
    lines = [ln.rstrip() for ln in (lines or []) if ln and ln.strip()] or [""]
    tx = text_frame._txBody
    paras = tx.findall(qn("a:p"))
    proto = copy.deepcopy(paras[0]) if paras else OxmlElement("a:p")
    first_run = proto.find(qn("a:r"))
    run_proto = copy.deepcopy(first_run) if first_run is not None else None
    end_proto = proto.find(qn("a:endParaRPr"))
    for p in paras:
        tx.remove(p)
    for line in lines:
        p = copy.deepcopy(proto)
        for child in list(p):
            if child.tag in (qn("a:r"), qn("a:br"), qn("a:fld")):
                p.remove(child)
        if run_proto is not None:
            r = copy.deepcopy(run_proto)
        else:
            r = OxmlElement("a:r")
            if end_proto is not None:
                r.append(_rpr_from_end(end_proto))
            r.append(OxmlElement("a:t"))
        r.find(qn("a:t")).text = line
        if header_bold:
            rpr = r.find(qn("a:rPr"))
            if rpr is None:
                rpr = OxmlElement("a:rPr")
                r.insert(0, rpr)
            rpr.set("b", "1" if line.endswith(":") else "0")
        end = p.find(qn("a:endParaRPr"))
        if end is not None:
            end.addprevious(r)
        else:
            p.append(r)
        tx.append(p)


def sub_paragraphs(text_frame, fn):
    """Apply fn to each paragraph's full text; when it changes, the new text
    goes into the first run and the other runs are emptied (placeholders may
    be split across runs)."""
    for p in text_frame.paragraphs:
        runs = p.runs
        if not runs:
            continue
        full = "".join(r.text for r in runs)
        new = fn(full)
        if new != full:
            runs[0].text = new
            for r in runs[1:]:
                r.text = ""


def _text_frames(prs):
    for slide in prs.slides:
        for sh in slide.shapes:
            if sh.has_text_frame:
                yield sh.text_frame
            if getattr(sh, "has_table", False) and sh.has_table:
                for row in sh.table.rows:
                    for cell in row.cells:
                        yield cell.text_frame


def replace_placeholders(prs, mapping):
    def fn(text):
        for k, v in mapping.items():
            text = text.replace("{" + k + "}", v)
        return text

    for tf in _text_frames(prs):
        sub_paragraphs(tf, fn)


def replace_chart_data(chart, categories, values, number_format):
    cd = CategoryChartData(number_format=number_format)
    cd.categories = categories
    cd.add_series(chart.plots[0].series[0].name, values)
    chart.replace_data(cd)


def remove_shape(shape):
    el = shape._element
    el.getparent().remove(el)


def remove_row(table, idx):
    tbl = table._tbl
    tbl.remove(tbl.tr_lst[idx])
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `venv/Scripts/python.exe -m pytest tests/test_secretary_review_pptx.py -v`
Expected: 7 passed. If `test_replace_chart_data_keeps_point_formatting` fails on the dPt count, stop and report — the spec's fallback (write chart caches + embedded workbook directly) becomes this task's implementation.

- [ ] **Step 6: Commit**

```bash
git add backend/requirements.txt backend/requirements-lock.txt backend/secretary_review_pptx.py backend/tests/test_secretary_review_pptx.py
git commit -m "Add python-pptx and Secretary Review template fill helpers

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 2: Layout constants, period labels and the template

**Files:**
- Create: `backend/secretary_review_layout.py`
- Create: `backend/scripts/prep_secretary_review_template.py`
- Create: `backend/secretary_review_templates/secretary_review.pptx` (generated)
- Create: `backend/tests/fixtures/secretary_review_sep26_reference.pptx` (copy of the reference deck)
- Test: `backend/tests/test_secretary_review_layout.py`

**Interfaces:**
- Consumes: `secretary_review_pptx` (Task 1).
- Produces (`secretary_review_layout`):
  - `TEMPLATE_PATH: Path`
  - `SCOPES = ["SAIL","BSP","DSP","RSP","BSL","ISP"]`, `PLANTS = ["BSP","DSP","RSP","BSL","ISP"]`, `BD_PLANTS = ["BSP","DSP","RSP","ISP"]`
  - `BD_GROUPS = [("BF","BFs"),("SMS","SMS"),("MILL","Mills")]`
  - `KPIS = [(key, techno_param_name, number_format), …]` — keys `coke, pci, fuel, bfprod, energy, co2`
  - `BLOCKS: list[tuple[key, section, label]]` (30 blocks)
  - `required_shape_names() -> set[str]`
  - `period_labels(month: str) -> dict` with keys `month, fy_start, n, abbr, mon, cply, ytd, ytd_prev, period_short, period_hdr, fy_label, fy_prev_label, fy_m2, fy_m1, fy_tgt, ytd_cat, filename`
  - `validate_month(month: str) -> bool`

- [ ] **Step 1: Write the failing tests**

`backend/tests/test_secretary_review_layout.py`:

```python
from pptx import Presentation

import secretary_review_layout as L
import secretary_review_pptx as sp


def test_period_labels_september():
    d = L.period_labels("2026-09")
    assert d["fy_start"] == 2026 and d["n"] == 6
    assert (d["mon"], d["cply"], d["ytd"], d["ytd_prev"]) == ("Sep’26", "Sep’25", "Apr-Sep’26", "Apr-Sep’25")
    assert (d["period_short"], d["period_hdr"]) == ("H1", "H-1")
    assert (d["fy_m2"], d["fy_m1"], d["fy_tgt"]) == ("FY25", "FY26", "FY'27 Target")
    assert (d["fy_label"], d["fy_prev_label"]) == ("2026-27", "2025-26")
    assert d["ytd_cat"] == "Apr-Sep"
    assert d["filename"] == "SECRETARY REVIEW Operations Inputs Sep26.pptx"


def test_period_labels_april():
    d = L.period_labels("2026-04")
    assert d["n"] == 1
    assert d["period_short"] == "Apr" and d["period_hdr"] == "Apr"
    assert d["ytd_cat"] == "Apr (YTD)"


def test_period_labels_january():
    d = L.period_labels("2027-01")
    assert d["fy_start"] == 2026 and d["n"] == 10
    assert (d["mon"], d["cply"], d["ytd"]) == ("Jan’27", "Jan’26", "Apr-Jan’27")
    assert d["period_short"] == "Apr-Jan"
    assert d["fy_tgt"] == "FY'27 Target"


def test_period_labels_quarters():
    assert L.period_labels("2026-06")["period_hdr"] == "Q-1"
    assert L.period_labels("2026-12")["period_hdr"] == "9M"
    assert L.period_labels("2027-03")["period_hdr"] == "FY"


def test_validate_month():
    assert L.validate_month("2026-09")
    assert not L.validate_month("2026-13")
    assert not L.validate_month("26-09")


def test_blocks_are_unique_and_complete():
    keys = [k for k, _, _ in L.BLOCKS]
    assert len(keys) == len(set(keys)) == 30
    assert "hl_SAIL" in keys and "cr_ISP_prev" in keys and "bd_RSP_MILL" in keys


def test_template_has_all_named_shapes_and_placeholders():
    prs = Presentation(str(L.TEMPLATE_PATH))
    names = set(sp.named_shapes(prs))
    missing = L.required_shape_names() - names
    assert not missing, sorted(missing)
    text = " ".join(
        cell.text for sh in sp.named_shapes(prs).values() if getattr(sh, "has_table", False) and sh.has_table
        for row in sh.table.rows for cell in row.cells
    )
    for ph in ("{MON}", "{YTD}", "{CPLY}", "{YTD_PREV}", "{PERIOD}"):
        assert ph in text, ph
    assert len(prs.slides) == 30
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `venv/Scripts/python.exe -m pytest tests/test_secretary_review_layout.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'secretary_review_layout'`.

- [ ] **Step 3: Implement `backend/secretary_review_layout.py`**

```python
"""Constants shared by the Secretary Review deck generator: scopes, KPIs,
narrative blocks, template shape names and period labels."""

import calendar
import re
from pathlib import Path

TEMPLATE_PATH = Path(__file__).resolve().parent / "secretary_review_templates" / "secretary_review.pptx"

SCOPES = ["SAIL", "BSP", "DSP", "RSP", "BSL", "ISP"]
PLANTS = ["BSP", "DSP", "RSP", "BSL", "ISP"]
BD_PLANTS = ["BSP", "DSP", "RSP", "ISP"]           # plants with a breakdown slide (21-24)
BD_GROUPS = [("BF", "BFs"), ("SMS", "SMS"), ("MILL", "Mills")]

# (key, techno_period parameter name, chart number format)
KPIS = [
    ("coke", "Coke Rate", "0"),
    ("pci", "CDI Rate", "0"),
    ("fuel", "Fuel Rate", "0"),
    ("bfprod", "BF Productivity", "0.00"),
    ("energy", "Specific Energy Consumption", "0.00"),
    ("co2", "Sp. CO2 Emission", "0.00"),
]

BLOCKS = (
    [("hl_SAIL", "Highlights", "SAIL highlights (slide 2)")]
    + [(f"hl_{p}", "Highlights", f"{p} highlights") for p in PLANTS]
    + [("delay_hmcs", "Delays", "Hot Metal & Crude Steel delays (slide 4)"),
       ("delay_fs", "Delays", "Finished Steel delays (slide 6)")]
    + [(f"cr_{p}_{w}", "Capital Repairs", f"{p} – {'current FY' if w == 'cur' else 'previous FY'}")
       for p in PLANTS for w in ("cur", "prev")]
    + [(f"bd_{p}_{g}", "Breakdowns", f"{p} – {lbl}") for p in BD_PLANTS for g, lbl in BD_GROUPS]
)


def required_shape_names() -> set:
    names = {"tbl_sail", "tbl_sail_hl", "tbl_plants_hm_cs", "tbl_plants_ss_fs",
             "tbl_delay_hmcs", "tbl_delay_fs", "tbl_cr_1", "tbl_cr_2"}
    names |= {f"tbl_{p}" for p in PLANTS} | {f"tbl_{p}_hl" for p in PLANTS}
    names |= {f"tbl_bd_{p}" for p in BD_PLANTS}
    names |= {f"ch_{s}_{k}" for s in SCOPES for k, _, _ in KPIS}
    names |= {f"trend_{s}_{k}" for s in SCOPES for k, _, _ in KPIS}
    return names


_MONTH_RE = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")


def validate_month(month: str) -> bool:
    return bool(_MONTH_RE.match(month or ""))


def _yy(v: int) -> str:
    return f"{v % 100:02d}"


def period_labels(month: str) -> dict:
    y, m = int(month[:4]), int(month[5:7])
    fy_start = y if m >= 4 else y - 1
    n = (m - 4) % 12 + 1
    ab = calendar.month_abbr[m]
    to_date = f"Apr-{ab}" if n > 1 else "Apr"
    short = {3: "Q1", 6: "H1", 9: "9M", 12: "FY"}.get(n, to_date)
    hdr = {3: "Q-1", 6: "H-1", 9: "9M", 12: "FY"}.get(n, to_date)
    return {
        "month": month, "fy_start": fy_start, "n": n, "abbr": ab,
        "mon": f"{ab}’{_yy(y)}", "cply": f"{ab}’{_yy(y - 1)}",
        "ytd": f"{to_date}’{_yy(y)}", "ytd_prev": f"{to_date}’{_yy(y - 1)}",
        "period_short": short, "period_hdr": hdr,
        "fy_label": f"{fy_start}-{_yy(fy_start + 1)}",
        "fy_prev_label": f"{fy_start - 1}-{_yy(fy_start)}",
        "fy_m2": f"FY{_yy(fy_start - 1)}", "fy_m1": f"FY{_yy(fy_start)}",
        "fy_tgt": f"FY'{_yy(fy_start + 1)} Target",
        "ytd_cat": to_date if n > 1 else "Apr (YTD)",
        "filename": f"SECRETARY REVIEW Operations Inputs {ab}{_yy(y)}.pptx",
    }
```

- [ ] **Step 4: Write `backend/scripts/prep_secretary_review_template.py`**

```python
"""One-off: turn the user-updated Sep'26 Secretary Review deck into the
generator's template (secretary_review_templates/secretary_review.pptx).

- names every filled table/chart (see secretary_review_layout.required_shape_names)
- puts {MON}/{YTD}/{CPLY}/{YTD_PREV}/{PERIOD} placeholders in titles and headers
- adds a highlights table to the DSP/RSP/ISP plant slides (cloned from BSP's)
- normalises each breakdown table to three rows: BFs / SMS / Mills

Slide indices are used only here. Re-run only to rebuild the template:
    venv/Scripts/python.exe scripts/prep_secretary_review_template.py "<reference.pptx>"
"""

import copy
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pptx import Presentation  # noqa: E402
from pptx.util import Emu  # noqa: E402

import secretary_review_layout as L  # noqa: E402
import secretary_review_pptx as sp  # noqa: E402

PLANT_SLIDES = {8: "BSP", 10: "DSP", 12: "RSP", 14: "BSL", 16: "ISP"}
BAR_SLIDES = {7: "SAIL", 9: "BSP", 11: "DSP", 13: "RSP", 15: "BSL", 17: "ISP"}
TREND_SLIDES = {25: "SAIL", 26: "BSP", 27: "DSP", 28: "RSP", 29: "BSL", 30: "ISP"}
BD_SLIDES = {21: "BSP", 22: "DSP", 23: "RSP", 24: "ISP"}
SINGLE_TABLE = {3: "tbl_plants_hm_cs", 4: "tbl_delay_hmcs", 5: "tbl_plants_ss_fs",
                6: "tbl_delay_fs", 19: "tbl_cr_1", 20: "tbl_cr_2"}

TITLES = {
    2: "SAIL  Performance : {MON} & {YTD}",
    3: "SAIL Plant-wise Performance  :  {MON}  &  {YTD}",
    4: "Major Breakdowns/Delays  during  {MON} & {YTD}",
    5: "SAIL Plant-wise Performance  :  {MON}  &  {YTD}",
    6: "Major Breakdowns/Delays  during  {MON} & {YTD}",
    7: "SAIL  Techno  Performance ({YTD})",
    **{i: f"{p}  Performance : {{MON}} & {{YTD}}" for i, p in PLANT_SLIDES.items()},
    **{i: f"{p}: Major Breakdowns/Delays during  {{MON}}" for i, p in BD_SLIDES.items()},
}

HEADER_SUBS = [
    (re.compile(r"Apr-(Sep|Aug)\s*[’']\s*26"), "{YTD}"),
    (re.compile(r"Apr-(Sep|Aug)\s*[’']\s*25"), "{YTD_PREV}"),
    (re.compile(r"Sep\s*[’']\s*26"), "{MON}"),
    (re.compile(r"Sep\s*[’']\s*25"), "{CPLY}"),
    (re.compile(r"H-1\s+Highlights"), "{PERIOD} Highlights"),
]


def kpi_of(title: str):
    t = sp.norm(title)
    if "coke" in t:
        return "coke"
    if "pci" in t:
        return "pci"
    if "fuel" in t:
        return "fuel"
    if "productivity" in t:
        return "bfprod"
    if "energy" in t:
        return "energy"
    if re.search(r"co\s*2", t):
        return "co2"
    return None


def tables(slide):
    return [sh for sh in slide.shapes if getattr(sh, "has_table", False) and sh.has_table]


def header_subs(text):
    for rx, rep in HEADER_SUBS:
        text = rx.sub(rep, text)
    return text


def set_title(slide, idx):
    for sh in slide.shapes:
        if sh.has_text_frame and re.search(r"performance|breakdowns", sp.norm(sh.text_frame.text)):
            sp.set_text_lines(sh.text_frame, [TITLES[idx]])
            sh.name = f"title_{idx}"
            return
    raise SystemExit(f"slide {idx}: title not found")


def split_main_and_hl(slide):
    tbls = tables(slide)
    main = [t for t in tbls if len(t.table.rows) > 1]
    hl = [t for t in tbls if len(t.table.rows) == 1]
    return main[0], (hl[0] if hl else None)


def clone_hl(src_hl, slide, plant_tbl, name):
    el = copy.deepcopy(src_hl._element)
    slide.shapes._spTree.insert_element_before(el, "p:extLst")
    new = tables(slide)[-1]
    new.name = name
    new.top = max(src_hl.top, plant_tbl.top + plant_tbl.height + Emu(60000))
    sp.set_text_lines(new.table.cell(0, 0).text_frame, ["Highlights"])
    sp.set_text_lines(new.table.cell(0, 1).text_frame, [""])
    return new


def normalise_bd(tbl_shape):
    t = tbl_shape.table._tbl
    trs = list(t.tr_lst)
    total_h = sum(int(tr.get("h", "0")) for tr in trs)
    proto = trs[0]
    for tr in trs:
        t.remove(tr)
    for _ in L.BD_GROUPS:
        tr = copy.deepcopy(proto)
        tr.set("h", str(total_h // len(L.BD_GROUPS)))
        t.append(tr)
    for i, (_, label) in enumerate(L.BD_GROUPS):
        sp.set_text_lines(tbl_shape.table.cell(i, 0).text_frame, [label])
        sp.set_text_lines(tbl_shape.table.cell(i, 1).text_frame, [""])


def main(src):
    prs = Presentation(src)
    slides = {i + 1: s for i, s in enumerate(prs.slides)}

    for idx in TITLES:
        set_title(slides[idx], idx)

    main_tbl, hl = split_main_and_hl(slides[2])
    main_tbl.name, hl.name = "tbl_sail", "tbl_sail_hl"

    bsp_hl = None
    for idx, plant in PLANT_SLIDES.items():
        main_tbl, hl = split_main_and_hl(slides[idx])
        main_tbl.name = f"tbl_{plant}"
        if hl is not None:
            hl.name = f"tbl_{plant}_hl"
            if plant == "BSP":
                bsp_hl = hl
    for idx, plant in PLANT_SLIDES.items():
        if f"tbl_{plant}_hl" not in sp.named_shapes(prs):
            clone_hl(bsp_hl, slides[idx], sp.named_shapes(prs)[f"tbl_{plant}"], f"tbl_{plant}_hl")

    for idx, name in SINGLE_TABLE.items():
        tables(slides[idx])[0].name = name

    for idx, plant in BD_SLIDES.items():
        t = tables(slides[idx])[0]
        t.name = f"tbl_bd_{plant}"
        normalise_bd(t)

    for mapping, prefix in ((BAR_SLIDES, "ch"), (TREND_SLIDES, "trend")):
        for idx, scope in mapping.items():
            for sh in slides[idx].shapes:
                if getattr(sh, "has_chart", False) and sh.has_chart:
                    title = "".join(e.text or "" for e in sh.chart._chartSpace.xpath(".//c:title//a:t"))
                    key = kpi_of(title)
                    if key is None:
                        raise SystemExit(f"slide {idx}: unknown chart title {title!r}")
                    sh.name = f"{prefix}_{scope}_{key}"

    for slide in prs.slides:
        for t in tables(slide):
            for row in t.table.rows:
                for cell in row.cells:
                    sp.sub_paragraphs(cell.text_frame, header_subs)

    missing = L.required_shape_names() - set(sp.named_shapes(prs))
    if missing:
        raise SystemExit(f"missing shapes: {sorted(missing)}")
    L.TEMPLATE_PATH.parent.mkdir(exist_ok=True)
    prs.save(str(L.TEMPLATE_PATH))
    print(f"wrote {L.TEMPLATE_PATH}")


if __name__ == "__main__":
    main(sys.argv[1])
```

- [ ] **Step 5: Generate the template and the reference fixture**

Run (from `backend/`):

```
venv/Scripts/python.exe scripts/prep_secretary_review_template.py "G:/My Drive/Report_format/work/SECRETARY REVIEW Operations Inputs Sep26 update.pptx"
cp "G:/My Drive/Report_format/work/SECRETARY REVIEW Operations Inputs Sep26 update.pptx" tests/fixtures/secretary_review_sep26_reference.pptx
```

Expected: `wrote …secretary_review.pptx`. If it exits with `title not found` or `unknown chart title`, adjust the regex in the script to the actual text it printed — do not hand-edit the template.

- [ ] **Step 6: Run tests to verify they pass**

Run: `venv/Scripts/python.exe -m pytest tests/test_secretary_review_layout.py -v`
Expected: 7 passed.

- [ ] **Step 7: Visual check of the cloned highlights tables**

Export slides 8, 10, 12, 16 of the template to PNG and look at them (Read the PNGs). From PowerShell:

```powershell
$pp = New-Object -ComObject PowerPoint.Application
$p = $pp.Presentations.Open("C:\opr-mis1\backend\secretary_review_templates\secretary_review.pptx", $true, $false, $false)
foreach ($i in 8,10,12,16) { $p.Slides.Item($i).Export("C:\Users\sanja\AppData\Local\Temp\claude\C--opr-mis1\3a70cd03-2de8-48a2-841c-ff2521803604\scratchpad\tpl_$i.png", "PNG") }
$p.Close(); $pp.Quit()
```

Expected: on 10/12/16 the empty Highlights table sits below the plant table without overlap or running off the slide. If PowerPoint is not installed, try `soffice --headless --convert-to pdf` and render with pypdfium2; if neither exists, say so in the task report. If it overlaps, fix `clone_hl`'s `top` rule and re-run Step 5.

- [ ] **Step 8: Commit**

```bash
git add backend/secretary_review_layout.py backend/scripts/prep_secretary_review_template.py backend/secretary_review_templates/secretary_review.pptx backend/tests/fixtures/secretary_review_sep26_reference.pptx backend/tests/test_secretary_review_layout.py
git commit -m "Add Secretary Review template, layout constants and period labels

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 3: `secretary_review_text` storage

**Files:**
- Create: `backend/secretary_review_text.py`
- Modify: `backend/db.py` (in `init_db`, next to `board_note_manual_text` ~line 295)
- Modify: `backend/scripts/mysql_schema.sql` (after `board_note_manual_text`, ~line 190)
- Create: `backend/scripts/migrate_secretary_review_text.sql`
- Test: `backend/tests/test_secretary_review_text.py`

**Interfaces:**
- Produces (`secretary_review_text`):
  - `get_texts(month: str) -> dict[str, str]` — every saved row, including `''`.
  - `save_texts(month: str, texts: dict[str, str]) -> int` — upsert each key (empty string is stored, not deleted); returns count.
  - `latest_saved_before(block_key: str, month: str, window: list[str]) -> str | None` — text of the latest saved row for `block_key` whose `report_month` is in `window` and `< month`.

- [ ] **Step 1: Write the failing tests**

`backend/tests/test_secretary_review_text.py`:

```python
import sqlite3

import pytest

import secretary_review_text as srt


@pytest.fixture
def store(tmp_path, monkeypatch):
    dbfile = tmp_path / "sr.db"
    conn = sqlite3.connect(dbfile)
    conn.execute("""
        CREATE TABLE secretary_review_text (
            report_month TEXT, block_key TEXT, text TEXT, updated_at TEXT,
            PRIMARY KEY (report_month, block_key)
        )
    """)
    conn.commit()
    conn.close()

    class _Conn:
        def __init__(self):
            self._c = sqlite3.connect(dbfile)

        def cursor(self):
            return self._c.cursor()

        def commit(self):
            self._c.commit()

        def close(self):
            self._c.close()

    monkeypatch.setattr(srt.db, "connect", _Conn)
    return srt


def test_empty_month(store):
    assert store.get_texts("2026-09") == {}


def test_round_trip_and_update(store):
    store.save_texts("2026-09", {"hl_SAIL": "a\nb", "delay_fs": "x"})
    store.save_texts("2026-09", {"hl_SAIL": "c"})
    assert store.get_texts("2026-09") == {"hl_SAIL": "c", "delay_fs": "x"}


def test_empty_text_is_kept_as_intentional_blank(store):
    store.save_texts("2026-09", {"hl_DSP": "   "})
    assert store.get_texts("2026-09") == {"hl_DSP": ""}


def test_latest_saved_before(store):
    store.save_texts("2026-08", {"cr_BSP_prev": "aug"})
    store.save_texts("2026-09", {"cr_BSP_prev": "sep"})
    store.save_texts("2026-03", {"cr_BSP_prev": "last fy"})
    window = ["2026-04", "2026-05", "2026-06", "2026-07", "2026-08", "2026-09", "2026-10"]
    assert store.latest_saved_before("cr_BSP_prev", "2026-10", window) == "sep"
    assert store.latest_saved_before("cr_BSP_prev", "2026-09", window) == "aug"
    assert store.latest_saved_before("cr_BSP_prev", "2026-04", window) is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `venv/Scripts/python.exe -m pytest tests/test_secretary_review_text.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'secretary_review_text'`.

- [ ] **Step 3: Implement `backend/secretary_review_text.py`**

```python
"""Saved narrative for the Secretary Review deck, keyed by
(report_month, block_key) in `secretary_review_text`. Block keys are listed
in secretary_review_layout.BLOCKS. An empty text is stored as '' — it means
"leave this block empty", unlike a missing row, which falls back to the DB
default (page_secretary_review_texts.effective_texts)."""

import datetime as _dt

import db


def get_texts(month: str) -> dict:
    conn = db.connect()
    cur = conn.cursor()
    try:
        cur.execute("SELECT block_key, text FROM secretary_review_text WHERE report_month=?", (month,))
        return {k: (t or "") for k, t in cur.fetchall()}
    finally:
        conn.close()


def save_texts(month: str, texts: dict) -> int:
    now = _dt.datetime.now().isoformat(timespec="seconds")
    conn = db.connect()
    cur = conn.cursor()
    try:
        n = 0
        for key, text in texts.items():
            key = str(key).strip()
            if not key:
                continue
            text = str(text or "").strip()
            cur.execute("""
                INSERT INTO secretary_review_text (report_month, block_key, text, updated_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(report_month, block_key) DO UPDATE SET text = excluded.text, updated_at = excluded.updated_at
            """, (month, key, text, now))
            n += 1
        conn.commit()
        return n
    finally:
        conn.close()


def latest_saved_before(block_key: str, month: str, window: list):
    candidates = sorted(m for m in window if m < month)
    if not candidates:
        return None
    conn = db.connect()
    cur = conn.cursor()
    try:
        phs = ",".join("?" for _ in candidates)
        cur.execute(
            f"SELECT text FROM secretary_review_text WHERE block_key=? AND report_month IN ({phs}) "
            f"ORDER BY report_month DESC LIMIT 1",
            [block_key] + candidates,
        )
        row = cur.fetchone()
        return row[0] if row else None
    finally:
        conn.close()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `venv/Scripts/python.exe -m pytest tests/test_secretary_review_text.py -v`
Expected: 4 passed.

- [ ] **Step 5: Add the schema in all three places**

In `backend/db.py` `init_db`, directly after the `board_note_manual_text` CREATE TABLE block:

```python
    # Secretary Review deck: editable narrative per (month, block). See
    # secretary_review_text.py; block keys in secretary_review_layout.BLOCKS.
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS secretary_review_text (
            report_month TEXT,
            block_key    TEXT,
            text         TEXT,
            updated_at   TEXT,
            PRIMARY KEY (report_month, block_key)
        )
    """)
```

In `backend/scripts/mysql_schema.sql`, after the `board_note_manual_text` table:

```sql
CREATE TABLE IF NOT EXISTS secretary_review_text (
    report_month CHAR(7)     NOT NULL,
    block_key    VARCHAR(32) NOT NULL,
    text         TEXT,
    updated_at   VARCHAR(19),
    PRIMARY KEY (report_month, block_key)
) ENGINE=InnoDB;
```

Create `backend/scripts/migrate_secretary_review_text.sql` with a one-line comment `-- Secretary Review deck narrative (secretary_review_text.py). 2026-10-07.` followed by the same statement.

Apply it to the live MySQL DB (credentials from `backend/.env`):

```
venv/Scripts/python.exe -c "import db; c=db.connect(); cur=c.cursor(); cur.execute(open('scripts/migrate_secretary_review_text.sql').read().split(';')[0].split('\n',1)[1]); c.commit(); cur.execute('SELECT COUNT(*) FROM secretary_review_text'); print(cur.fetchone())"
```

Expected: `(0,)`.

- [ ] **Step 6: Commit**

```bash
git add backend/secretary_review_text.py backend/db.py backend/scripts/mysql_schema.sql backend/scripts/migrate_secretary_review_text.sql backend/tests/test_secretary_review_text.py
git commit -m "Add secretary_review_text table and storage module

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 4: Data context (production + techno)

**Files:**
- Create: `backend/page_secretary_review.py` (context part; render added in Task 6)
- Test: `backend/tests/test_secretary_review_context.py`

**Interfaces:**
- Consumes: `secretary_review_layout.period_labels`, `SCOPES`, `PLANTS`, `KPIS`; `page4._p4_row_values`, `page4._p4_conv_actuals`, `page4.PAGE4_ITEMS`, `page4._raw_gr`; `board_note_common.fy_months`, `fuel_rate_fallback`; `techno_period.build_period_report`, `techno_period._build_major_params`; `page_techno.compute_sail_targets(fy_label)`, `page_techno._get_plant_techno_plan_targets(plant, month)`.
- Produces (`page_secretary_review`):
  - `ITEMS = [("HM","Hot Metal"),("CS","Total Crude Steel"),("FS","Finished Steel"),("SS","Saleable Steel")]`
  - `latest_month() -> str | None`
  - `build_production(cur, month) -> dict[item_key][scope]` where scope ∈ `SCOPES + ["SSPs", "TOTAL_CONV"]` (`TOTAL_CONV` only under `"FS"`); each value is `{cap, app_m, act_m, cply_m, gr_m, cu_m, app_ytd, act_ytd, cply_ytd, gr_ytd, cu_ytd}` (floats or None).
  - `build_techno(labels: dict, warnings: list) -> dict[scope][kpi_key]` → `{fy_m2, fy_m1, target, month, ytd, trend: [(abbr, value)], month_used}`
  - `build_context(month) -> {"labels", "production", "techno", "warnings"}`

- [ ] **Step 1: Write the failing tests (live DB, values from the Sep'26 deck)**

`backend/tests/test_secretary_review_context.py`:

```python
import pytest

import db
import page_secretary_review as psr


def _has_month(month):
    try:
        c = db.connect()
        cur = c.cursor()
        cur.execute("SELECT COUNT(*) FROM production_table WHERE report_month=? AND item_name='Hot Metal'", (month,))
        n = cur.fetchone()[0]
        c.close()
        return n > 0
    except Exception:
        return False


live = pytest.mark.skipif(not _has_month("2026-09"), reason="needs live DB with 2026-09 data")


def _r(row):
    return [None if v is None else round(v) for v in
            (row["cap"], row["app_m"], row["act_m"], row["gr_m"], row["cu_m"],
             row["app_ytd"], row["act_ytd"], row["gr_ytd"], row["cu_ytd"])]


@live
def test_production_matches_reference_deck():
    c = db.connect()
    prod = psr.build_production(c.cursor(), "2026-09")
    c.close()
    assert _r(prod["HM"]["SAIL"]) == [21113, 1945, 1594, -1, 92, 11286, 10203, 2, 96]
    assert _r(prod["CS"]["BSP"]) == [5961, 530, 355, -21, 72, 3212, 2866, 1, 96]
    assert _r(prod["CS"]["SSPs"]) == [414, 31, 17, -9, 49, 179, 128, -10, 62]
    assert _r(prod["SS"]["SSPs"]) == [574, 45, 32, 16, 67, 262, 183, 1, 63]
    assert _r(prod["FS"]["SAIL"]) == [17500, 1546, 1328, -2, 92, 9230, 8156, 1, 93]
    conv = _r(prod["FS"]["TOTAL_CONV"])
    assert conv[2] in (1375, 1376) and conv[3] == -1 and conv[4] == 96 and conv[6] in (8388, 8389)


@live
def test_techno_matches_reference_deck():
    warnings = []
    t = psr.build_techno(psr.period_labels("2026-09"), warnings)
    coke = t["SAIL"]["coke"]
    assert (coke["fy_m2"], coke["fy_m1"], round(coke["target"]), coke["month"], coke["ytd"]) == (421, 419, 400, 432, 424)
    assert [a for a, _ in coke["trend"]] == ["Apr", "May", "Jun", "Jul", "Aug", "Sep"]
    assert t["SAIL"]["bfprod"]["month"] == 1.91
    assert t["SAIL"]["energy"]["target"] == 6.03
    assert t["BSP"]["coke"]["target"] == 407
    co2 = t["SAIL"]["co2"]
    assert co2["month_used"] in ("2026-08", "2026-09")


def test_context_for_month_without_data_has_warnings_not_errors():
    ctx = psr.build_context("2030-01")
    assert ctx["labels"]["mon"] == "Jan’30"
    assert ctx["production"]["HM"]["SAIL"]["act_m"] is None
    assert any("No production" in w for w in ctx["warnings"])
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `venv/Scripts/python.exe -m pytest tests/test_secretary_review_context.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'page_secretary_review'`.

- [ ] **Step 3: Implement the context part of `backend/page_secretary_review.py`**

```python
"""Secretary Review deck ("SECRETARY REVIEW Operations Inputs <Mon><YY>.pptx").

build_context(month) gathers the month's numbers; render_pptx(month, texts)
fills secretary_review_templates/secretary_review.pptx (see
scripts/prep_secretary_review_template.py for how the template was made).
Production figures come from page4._p4_row_values so they match the MIS
report; techno figures from techno_period.build_period_report."""

import calendar

import board_note_common as bnc
import db
import page4
import page_techno as pt
import techno_period as tp
from constants import FIVE_PLANTS
from secretary_review_layout import KPIS, PLANTS, SCOPES, period_labels

ITEMS = [("HM", "Hot Metal"), ("CS", "Total Crude Steel"), ("FS", "Finished Steel"), ("SS", "Saleable Steel")]
_P4 = {i["db_item"]: i for i in page4.PAGE4_ITEMS}


def latest_month():
    conn = db.connect()
    cur = conn.cursor()
    try:
        cur.execute("SELECT MAX(report_month) FROM production_table "
                    "WHERE item_name='Hot Metal' AND month_actual IS NOT NULL")
        row = cur.fetchone()
        return row[0] if row and row[0] else None
    finally:
        conn.close()


# --------------------------------------------------------------------------
# Production
# --------------------------------------------------------------------------

def _prod_row(cur, month, plant, db_item, members=None):
    """members: an explicit plant list summed as one row (the SSPs row)."""
    cfg = _P4[db_item]
    sail_set = members if members is not None else cfg["sail_set"]
    p = "SAIL" if members is not None else plant
    raw, cap = page4._p4_row_values(cur, month, p, db_item, False, cfg.get("five_plants", []),
                                    sail_set, has_capacity=True, raw=True)
    return {"cap": cap, "app_m": raw[1], "act_m": raw[2], "cply_m": raw[5], "gr_m": raw[6],
            "cu_m": raw[7], "app_ytd": raw[8], "act_ytd": raw[9], "cply_ytd": raw[12],
            "gr_ytd": raw[13], "cu_ytd": raw[14]}


def _plus(a, b):
    return None if a is None or b is None else a + b


def _with_conversion(cur, month, row):
    """SAIL Finished Steel plus Conversion (slide 5's Total row). CU% scales
    with the actual, since capacity is unchanged."""
    cm, cc, cy, cyc = page4._p4_conv_actuals(cur, month)
    r = dict(row)
    r["act_m"], r["cply_m"] = _plus(row["act_m"], cm), _plus(row["cply_m"], cc)
    r["act_ytd"], r["cply_ytd"] = _plus(row["act_ytd"], cy), _plus(row["cply_ytd"], cyc)
    r["gr_m"] = page4._raw_gr(r["act_m"], r["cply_m"])
    r["gr_ytd"] = page4._raw_gr(r["act_ytd"], r["cply_ytd"])
    for cu, act in (("cu_m", "act_m"), ("cu_ytd", "act_ytd")):
        r[cu] = (row[cu] * r[act] / row[act]) if (row[cu] is not None and r[act] is not None and row[act]) else None
    return r


def build_production(cur, month):
    out = {}
    for key, db_item in ITEMS:
        rows = {s: _prod_row(cur, month, s, db_item) for s in SCOPES}
        ssps = [p for p in _P4[db_item]["sail_set"] if p not in FIVE_PLANTS]
        rows["SSPs"] = _prod_row(cur, month, "SSPs", db_item, members=ssps) if ssps else None
        if key == "FS":
            rows["TOTAL_CONV"] = _with_conversion(cur, month, rows["SAIL"])
        out[key] = rows
    return out


# --------------------------------------------------------------------------
# Techno
# --------------------------------------------------------------------------

def _num(d):
    s = (d or {}).get("display") or ""
    s = s.replace(",", "").strip()
    try:
        return float(s) if s else None
    except ValueError:
        return None


def _targets(labels):
    """{scope: {param: target}}; a scope whose targets can't be read (e.g. an
    FY with no techno_plan_fy rows yet) gets {} and shows as 'no FY target'."""
    out = {}
    fetch = {"SAIL": lambda: pt.compute_sail_targets(labels["fy_label"])}
    fetch.update({p: (lambda p=p: pt._get_plant_techno_plan_targets(p, labels["month"])) for p in PLANTS})
    for scope, fn in fetch.items():
        try:
            raw = fn() or {}
        except Exception:
            raw = {}
        out[scope] = bnc.fuel_rate_fallback({k[1]: v for k, v in raw.items()})
    return out


def _round_fmt(v, fmt):
    if v is None:
        return None
    return round(v) if fmt == "0" else round(v, 2)


def build_techno(labels, warnings):
    fy_start, n, month = labels["fy_start"], labels["n"], labels["month"]
    months = bnc.fy_months(fy_start)[:n]
    periods = [{"label": "FYm2", "months": bnc.fy_months(fy_start - 2)},
               {"label": "FYm1", "months": bnc.fy_months(fy_start - 1)}]
    periods += [{"label": m, "months": [m]} for m in months]
    periods += [{"label": "ytd:" + m, "months": months[: i + 1]} for i, m in enumerate(months)]
    res = tp.build_period_report(SCOPES, [name for _, name, _ in KPIS], periods)
    display = {p["name"]: p["display_name"] for p in tp._build_major_params()}
    sections = {s["parameter"]: {r["plant"]: r["values"] for r in s["rows"]} for s in res["sections"]}
    targets = _targets(labels)

    def vals(name, scope):
        return sections.get(display.get(name, name), {}).get(scope, {})

    co2_name = dict((k, nm) for k, nm, _ in KPIS)["co2"]
    sail_co2 = vals(co2_name, "SAIL")
    co2_month = next((m for m in reversed(months) if _num(sail_co2.get(m)) is not None), month)
    if co2_month != month:
        warnings.append(f"Sp. CO₂ for {labels['mon']} not loaded yet – using "
                        f"{calendar.month_abbr[int(co2_month[5:])]}")

    out = {}
    for scope in SCOPES:
        out[scope] = {}
        for key, name, fmt in KPIS:
            v = vals(name, scope)
            used = co2_month if key == "co2" else month
            upto = months[: months.index(used) + 1]
            entry = {
                "fy_m2": _num(v.get("FYm2")), "fy_m1": _num(v.get("FYm1")),
                "target": _round_fmt((targets.get(scope) or {}).get(name), fmt),
                "month": _num(v.get(used)), "ytd": _num(v.get("ytd:" + used)),
                "trend": [(calendar.month_abbr[int(m[5:])], _num(v.get(m))) for m in upto],
                "month_used": used,
            }
            if entry["month"] is None:
                warnings.append(f"{scope} {name}: no value for {calendar.month_abbr[int(used[5:])]}")
            if entry["target"] is None:
                warnings.append(f"{scope} {name}: no FY target")
            out[scope][key] = entry
    return out


def build_context(month):
    labels = period_labels(month)
    warnings = []
    conn = db.connect()
    try:
        production = build_production(conn.cursor(), month)
    finally:
        conn.close()
    if production["HM"]["SAIL"]["act_m"] is None:
        warnings.append(f"No production actuals for {labels['mon']}")
    techno = build_techno(labels, warnings)
    return {"labels": labels, "production": production, "techno": techno, "warnings": warnings}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `venv/Scripts/python.exe -m pytest tests/test_secretary_review_context.py -v`
Expected: 3 passed. If a techno number differs from the deck, print the period report for that scope/param and find out why before touching the expected value (a DB correction since the Sep'26 update is the only acceptable reason; note it in the test with a comment).

- [ ] **Step 5: Commit**

```bash
git add backend/page_secretary_review.py backend/tests/test_secretary_review_context.py
git commit -m "Add Secretary Review data context (production, techno, CO2 lag)

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 5: Default narrative from the DB

**Files:**
- Create: `backend/page_secretary_review_texts.py`
- Test: `backend/tests/test_secretary_review_texts.py`

**Interfaces:**
- Consumes: `secretary_review_layout` (`BLOCKS`, `PLANTS`, `BD_PLANTS`, `BD_GROUPS`, `period_labels`), `secretary_review_text` (Task 3), `board_note_common.best_ever`, `ITEMS_FOR_PLANT`, `fy_months`.
- Produces (`page_secretary_review_texts`):
  - `BD_MIN_HOURS = 48`
  - `event_hours(ev: dict, month: str) -> float`
  - `clean_cause(cause: str, unit_name: str) -> str`
  - `unit_summaries(events: list[dict], month: str) -> list[dict]` (`plant, unit_type, unit_name, hours, cause`)
  - `delay_text(summaries, unit_types: tuple, mon: str) -> str`
  - `bd_group_text(summaries, plant: str, group: str) -> str`
  - `cr_line(row: dict, upto: datetime.date) -> str`
  - `highlight_text(cur, scope: str, labels: dict) -> str`
  - `default_texts(month: str) -> dict[str, str]` (every BLOCKS key)
  - `effective_texts(month: str) -> dict[str, {"text": str, "saved": bool}]`

- [ ] **Step 1: Write the failing tests**

`backend/tests/test_secretary_review_texts.py`:

```python
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
    monkeypatch.setattr(t, "default_texts", lambda m: {k: "DB " + k for k, _, _ in t.BLOCKS})
    monkeypatch.setattr(t.srt, "get_texts", lambda m: {"hl_DSP": "", "hl_SAIL": "mine"})
    eff = t.effective_texts("2026-09")
    assert eff["hl_DSP"] == {"text": "", "saved": True}
    assert eff["hl_SAIL"] == {"text": "mine", "saved": True}
    assert eff["hl_BSP"] == {"text": "DB hl_BSP", "saved": False}
    assert len(eff) == 30
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `venv/Scripts/python.exe -m pytest tests/test_secretary_review_texts.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'page_secretary_review_texts'`.

- [ ] **Step 3: Implement `backend/page_secretary_review_texts.py`**

```python
"""Default (DB-derived) narrative for the Secretary Review deck's text
blocks, and the saved-or-default merge the page and renderer use.

- highlights: all-time best production for the FY-to-date period
  (board_note_common.best_ever)
- delays / breakdowns: breakdown_table events in the month, summed per unit,
  units with >= BD_MIN_HOURS lost; the longest event's cause is shown.
  Events linked to a capital repair are left out (they are CRs).
- capital repairs: capital_repair_table rows with actual dates up to the
  month end (current FY) or the CPLY month end (previous FY). With no
  structured rows for the previous FY, the latest text saved earlier in
  this FY is carried forward."""

import calendar
import datetime as dt
import re

import board_note_common as bnc
import db
import secretary_review_text as srt
from secretary_review_layout import BD_GROUPS, BD_PLANTS, BLOCKS, PLANTS, period_labels

BD_MIN_HOURS = 48
UNIT_GROUP = {"BF": "BF", "COKE": "BF", "SINTER": "BF", "SMS": "SMS", "MILL": "MILL"}
HMCS_TYPES = ("BF", "COKE", "SINTER", "SMS")
FS_TYPES = ("MILL",)


def _bounds(month):
    y, m = int(month[:4]), int(month[5:7])
    start = dt.datetime(y, m, 1)
    end = dt.datetime(y + 1, 1, 1) if m == 12 else dt.datetime(y, m + 1, 1)
    return start, end


def _parse_ts(s):
    for f in ("%Y-%m-%d %H:%M", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            return dt.datetime.strptime(str(s).strip(), f)
        except (ValueError, TypeError):
            pass
    return None


def event_hours(ev, month):
    s, e = _bounds(month)
    start = _parse_ts(ev["start_ts"])
    if start is None:
        return 0.0
    if ev.get("hours_lost_override") is not None:
        return float(ev["hours_lost_override"]) if s <= start < e else 0.0
    if ev.get("is_ongoing") or not ev.get("end_ts"):
        end = e
    else:
        end = _parse_ts(ev["end_ts"]) or start
    lo, hi = max(start, s), min(end, e)
    return max((hi - lo).total_seconds() / 3600.0, 0.0)


def clean_cause(cause, unit_name):
    s = re.sub(r"\s+", " ", cause or "").strip()
    s = re.sub(r"\s*w\.?\s*e\.?\s*f\.?\b.*$", "", s, flags=re.I)
    if unit_name and s.lower().startswith(unit_name.lower()):
        s = s[len(unit_name):].lstrip(" :-")
    s = s.rstrip(" ,;-")
    return s[:90].rstrip() + "…" if len(s) > 90 else s


def unit_summaries(events, month):
    agg = {}
    for ev in events:
        h = event_hours(ev, month)
        if h <= 0:
            continue
        k = (ev["plant"], ev["unit_type"], ev["unit_name"])
        a = agg.setdefault(k, {"plant": k[0], "unit_type": k[1], "unit_name": k[2], "hours": 0.0, "_top": (0.0, "")})
        a["hours"] += h
        if h > a["_top"][0]:
            a["_top"] = (h, ev.get("cause") or "")
    out = []
    for a in agg.values():
        if a["hours"] >= BD_MIN_HOURS:
            top = a.pop("_top")
            a["cause"] = clean_cause(top[1], a["unit_name"])
            out.append(a)
    out.sort(key=lambda a: (a["plant"], a["unit_type"], a["unit_name"]))
    return out


def _days(hours):
    d = round(hours / 24)
    return f"{d} day" if d == 1 else f"{d} days"


def _unit_line(a):
    head = f"{a['unit_name']}: {a['cause']}" if a["cause"] else a["unit_name"]
    return f"{head} – {_days(a['hours'])}"


def delay_text(summaries, unit_types, mon):
    lines = []
    for p in PLANTS:
        rows = [a for a in summaries if a["plant"] == p and a["unit_type"] in unit_types]
        if rows:
            lines.append(f"{p} ({mon}):")
            lines += [_unit_line(a) for a in rows]
    return "\n".join(lines)


def bd_group_text(summaries, plant, group):
    return "\n".join(_unit_line(a) for a in summaries
                     if a["plant"] == plant and UNIT_GROUP.get(a["unit_type"]) == group)


def _mon(d):
    return calendar.month_abbr[d.month]


def _mon_span(a, b):
    if (a.year, a.month) == (b.year, b.month):
        return f"{_mon(a)}’{a.year % 100:02d}"
    if a.year == b.year:
        return f"{_mon(a)}-{_mon(b)}’{b.year % 100:02d}"
    return f"{_mon(a)}’{a.year % 100:02d}-{_mon(b)}’{b.year % 100:02d}"


def cr_line(row, upto):
    start = dt.date.fromisoformat(str(row["actual_start"])[:10])
    end = dt.date.fromisoformat(str(row["actual_end"])[:10]) if row.get("actual_end") else None
    ongoing = bool(row.get("actual_ongoing")) or end is None or end > upto
    stop = upto if (end is None or end > upto) else end
    days = (stop - start).days + 1
    label = " ".join(x for x in (row.get("shop"), row.get("equipment")) if x).strip()
    return f"{label} ({days} days in {_mon_span(start, stop)}{', contd.' if ongoing else ''})"


def _fetch_breakdowns(cur, month):
    s, e = _bounds(month)
    cur.execute(
        "SELECT plant, unit_type, unit_name, start_ts, end_ts, is_ongoing, cause, hours_lost_override "
        "FROM breakdown_table WHERE capital_repair_id IS NULL AND start_ts < ? "
        "AND (end_ts IS NULL OR end_ts >= ? OR is_ongoing = 1)",
        (e.strftime("%Y-%m-%d"), s.strftime("%Y-%m-%d")),
    )
    cols = ("plant", "unit_type", "unit_name", "start_ts", "end_ts", "is_ongoing", "cause", "hours_lost_override")
    return [dict(zip(cols, r)) for r in cur.fetchall()]


def _fetch_cr(cur, plant, fy_label, upto):
    cur.execute(
        "SELECT shop, equipment, actual_start, actual_end, actual_ongoing FROM capital_repair_table "
        "WHERE plant=? AND fy=? AND actual_start IS NOT NULL AND actual_start <> '' AND actual_start <= ? "
        "ORDER BY actual_start",
        (plant, fy_label, upto.isoformat()),
    )
    cols = ("shop", "equipment", "actual_start", "actual_end", "actual_ongoing")
    return [dict(zip(cols, r)) for r in cur.fetchall()]


def highlight_text(cur, scope, labels):
    fy_start, n = labels["fy_start"], labels["n"]

    def months_fn(fy):
        return bnc.fy_months(fy)[:n]

    lines = []
    for label, db_item in bnc.ITEMS_FOR_PLANT.get(scope, []):
        add_conv = scope == "SAIL" and label == "Finished Steel"
        r = bnc.best_ever(cur, scope, db_item, months_fn, fy_start, add_conv)
        if r:
            cur_v, prev_v, prev_fy = r
            lines.append(f"{label} {cur_v / 1000:.3f} MT (Previous best {prev_v / 1000:.3f} MT in "
                         f"{labels['period_short']} {prev_fy}-{(prev_fy + 1) % 100:02d})")
    if not lines:
        return ""
    who = "SAIL achieved best ever" if scope == "SAIL" else f"{scope} achieved best"
    rng = f"Apr-{labels['abbr']}" if labels["n"] > 1 else "Apr"
    period = labels["period_short"] if labels["period_short"] == rng else f"{labels['period_short']} ({rng})"
    return "\n".join([f"{who} {period} {labels['fy_label']} production for following:-"] + lines)


def default_texts(month):
    labels = period_labels(month)
    y, m = int(month[:4]), int(month[5:7])
    upto = dt.date(y, m, calendar.monthrange(y, m)[1])
    upto_prev = dt.date(y - 1, m, calendar.monthrange(y - 1, m)[1])
    fy_window = bnc.fy_months(labels["fy_start"])
    out = {}
    conn = db.connect()
    cur = conn.cursor()
    try:
        out["hl_SAIL"] = highlight_text(cur, "SAIL", labels)
        for p in PLANTS:
            out[f"hl_{p}"] = highlight_text(cur, p, labels)
        summaries = unit_summaries(_fetch_breakdowns(cur, month), month)
        out["delay_hmcs"] = delay_text(summaries, HMCS_TYPES, labels["mon"])
        out["delay_fs"] = delay_text(summaries, FS_TYPES, labels["mon"])
        for p in BD_PLANTS:
            for g, _ in BD_GROUPS:
                out[f"bd_{p}_{g}"] = bd_group_text(summaries, p, g)
        for p in PLANTS:
            out[f"cr_{p}_cur"] = "\n".join(cr_line(r, upto) for r in _fetch_cr(cur, p, labels["fy_label"], upto))
            prev = "\n".join(cr_line(r, upto_prev) for r in _fetch_cr(cur, p, labels["fy_prev_label"], upto_prev))
            out[f"cr_{p}_prev"] = prev or (srt.latest_saved_before(f"cr_{p}_prev", month, fy_window) or "")
    finally:
        conn.close()
    return {k: out.get(k, "") for k, _, _ in BLOCKS}


def effective_texts(month):
    saved = srt.get_texts(month)
    defaults = default_texts(month)
    return {k: {"text": saved[k] if k in saved else defaults.get(k, ""), "saved": k in saved}
            for k, _, _ in BLOCKS}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `venv/Scripts/python.exe -m pytest tests/test_secretary_review_texts.py -v`
Expected: 7 passed.

- [ ] **Step 5: Smoke-run against the live DB**

Run: `venv/Scripts/python.exe -c "import page_secretary_review_texts as t, json; print(json.dumps(t.default_texts('2026-09'), ensure_ascii=False, indent=1))"`
Expected: all 30 keys; `hl_SAIL` begins `SAIL achieved best ever H1 (Apr-Sep) 2026-27 production for following:-` and contains `Hot Metal 10.203 MT (Previous best 10.135 MT in H1 2023-24)`; `cr_BSP_cur` contains `SMS2 Conv-A (62 days in Jun-Aug’26)`. Paste the output in the task report.

- [ ] **Step 6: Commit**

```bash
git add backend/page_secretary_review_texts.py backend/tests/test_secretary_review_texts.py
git commit -m "Add DB-derived default narrative for the Secretary Review deck

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 6: Render the deck

**Files:**
- Modify: `backend/page_secretary_review.py` (append render part)
- Test: `backend/tests/test_secretary_review_render.py`

**Interfaces:**
- Consumes: Tasks 1, 2, 4, 5.
- Produces (`page_secretary_review`):
  - `RenderResult` dataclass: `content: bytes`, `warnings: list[str]`, `filename: str`
  - `render_pptx(month: str, texts: dict[str, str] | None = None) -> RenderResult` — `texts` missing keys are filled from `effective_texts(month)`.

- [ ] **Step 1: Write the failing tests**

`backend/tests/test_secretary_review_render.py`:

```python
import io
import re
from pathlib import Path

import pytest
from pptx import Presentation

import page_secretary_review as psr
import page_secretary_review_texts as pst
import secretary_review_layout as L
import secretary_review_pptx as sp
from test_secretary_review_context import live

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


def test_render_month_without_data():
    res = psr.render_pptx("2030-01", {k: "" for k, _, _ in L.BLOCKS})
    out = Presentation(io.BytesIO(res.content))
    assert len(out.slides) == 30
    assert res.filename.endswith("Jan30.pptx")


def test_missing_texts_fall_back_to_effective(monkeypatch):
    monkeypatch.setattr(pst, "effective_texts", lambda m: {k: {"text": "", "saved": False} for k, _, _ in L.BLOCKS})
    res = psr.render_pptx("2030-01", {"delay_fs": "MILL: x – 3 days"})
    out = Presentation(io.BytesIO(res.content))
    assert sp.named_shapes(out)["tbl_delay_fs"].table.cell(0, 1).text == "MILL: x – 3 days"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `venv/Scripts/python.exe -m pytest tests/test_secretary_review_render.py -v`
Expected: FAIL — `AttributeError: module 'page_secretary_review' has no attribute 'render_pptx'`.

- [ ] **Step 3: Append the render part to `backend/page_secretary_review.py`**

Add to the imports at the top:

```python
import io
from dataclasses import dataclass, field

from pptx import Presentation

import page_secretary_review_texts as pst
import secretary_review_pptx as sp
from secretary_review_layout import BD_GROUPS, BD_PLANTS, BLOCKS, TEMPLATE_PATH
```

Append:

```python
# --------------------------------------------------------------------------
# Render
# --------------------------------------------------------------------------

ITEM_BY_LABEL = {"hot metal": "HM", "crude steel": "CS", "finished steel": "FS", "saleable steel": "SS"}
PLANT_ROW = {"bsp": "BSP", "dsp": "DSP", "rsp": "RSP", "bsl": "BSL", "isp": "ISP", "ssps": "SSPs", "total": "SAIL"}
VALUE_COLS = ("cap", "app_m", "act_m", "gr_m", "cu_m", "app_ytd", "act_ytd", "gr_ytd", "cu_ytd")


@dataclass
class RenderResult:
    content: bytes
    filename: str
    warnings: list = field(default_factory=list)


def _fmt(v):
    return "" if v is None else str(round(v))


def _fill_values(row, values):
    for i, key in enumerate(VALUE_COLS, start=1):
        if i < len(row.cells):
            sp.set_text_lines(row.cells[i].text_frame, [_fmt((values or {}).get(key))])


def _fill_item_table(table, production, scope):
    """Rows labelled by item (slide 2 and the plant slides)."""
    for row in table.rows:
        item = ITEM_BY_LABEL.get(sp.norm(row.cells[0].text))
        if item:
            _fill_values(row, production[item].get(scope))


def _fill_section_table(table, production):
    """Item header rows followed by plant rows (slides 3 and 5)."""
    item = None
    for row in table.rows:
        label = sp.norm(row.cells[0].text)
        if label in ITEM_BY_LABEL:
            item = ITEM_BY_LABEL[label]
        elif item and label in PLANT_ROW:
            scope = PLANT_ROW[label]
            if item == "FS" and scope == "SAIL":
                scope = "TOTAL_CONV"
            _fill_values(row, production[item].get(scope))


def _lines(text):
    return [ln for ln in (text or "").splitlines() if ln.strip()]


def _fill_hl(shape, text):
    lines = _lines(text)
    if not lines:
        sp.remove_shape(shape)
    else:
        sp.set_text_lines(shape.table.cell(0, 1).text_frame, lines, header_bold=True)


def _fill_bd(shape, plant, texts):
    table = shape.table
    for i, (g, _) in enumerate(BD_GROUPS):
        if i < len(table.rows):
            sp.set_text_lines(table.cell(i, 1).text_frame, _lines(texts.get(f"bd_{plant}_{g}")), header_bold=True)
    empty = [i for i in range(len(table.rows)) if not table.cell(i, 1).text.strip()]
    if len(empty) == len(table.rows):
        for i in reversed(range(1, len(table.rows))):
            sp.remove_row(table, i)
        sp.set_text_lines(table.cell(0, 0).text_frame, [""])
        sp.set_text_lines(table.cell(0, 1).text_frame, ["No major breakdowns"])
    else:
        for i in reversed(empty):
            sp.remove_row(table, i)


def _fill_cr(shape, texts):
    for row in shape.table.rows:
        plant = row.cells[0].text.strip().upper()
        if plant in PLANTS and len(row.cells) >= 3:
            sp.set_text_lines(row.cells[1].text_frame, _lines(texts.get(f"cr_{plant}_cur")), header_bold=True)
            sp.set_text_lines(row.cells[2].text_frame, _lines(texts.get(f"cr_{plant}_prev")), header_bold=True)


def _fill_charts(shapes, techno, labels, warn):
    for scope in SCOPES:
        for key, _, fmt in KPIS:
            t = techno[scope][key]
            ab = calendar.month_abbr[int(t["month_used"][5:])]
            ytd_cat = labels["ytd_cat"] if t["month_used"] == labels["month"] else f"Apr-{ab}"
            head = [labels["fy_m2"], labels["fy_m1"], labels["fy_tgt"]]
            head_vals = [t["fy_m2"], t["fy_m1"], t["target"]]
            bar = shapes.get(f"ch_{scope}_{key}")
            if bar is None:
                warn(f"template shape ch_{scope}_{key} not found")
            else:
                sp.replace_chart_data(bar.chart, head + [ab, ytd_cat], head_vals + [t["month"], t["ytd"]], fmt)
            trend = shapes.get(f"trend_{scope}_{key}")
            if trend is None:
                warn(f"template shape trend_{scope}_{key} not found")
            else:
                sp.replace_chart_data(trend.chart, head + [a for a, _ in t["trend"]],
                                      head_vals + [v for _, v in t["trend"]], fmt)


def render_pptx(month, texts=None):
    ctx = build_context(month)
    labels, production = ctx["labels"], ctx["production"]
    warnings = list(ctx["warnings"])
    eff = {k: v["text"] for k, v in pst.effective_texts(month).items()}
    merged = {k: (texts[k] if texts and k in texts else eff.get(k, "")) for k, _, _ in BLOCKS}

    prs = Presentation(str(TEMPLATE_PATH))
    shapes = sp.named_shapes(prs)

    def get(name):
        sh = shapes.get(name)
        if sh is None:
            warnings.append(f"template shape {name} not found")
        return sh

    if (sh := get("tbl_sail")) is not None:
        _fill_item_table(sh.table, production, "SAIL")
    for p in PLANTS:
        if (sh := get(f"tbl_{p}")) is not None:
            _fill_item_table(sh.table, production, p)
    for name in ("tbl_plants_hm_cs", "tbl_plants_ss_fs"):
        if (sh := get(name)) is not None:
            _fill_section_table(sh.table, production)

    if (sh := get("tbl_sail_hl")) is not None:
        _fill_hl(sh, merged["hl_SAIL"])
    for p in PLANTS:
        if (sh := get(f"tbl_{p}_hl")) is not None:
            _fill_hl(sh, merged[f"hl_{p}"])
    for name, key in (("tbl_delay_hmcs", "delay_hmcs"), ("tbl_delay_fs", "delay_fs")):
        if (sh := get(name)) is not None:
            sp.set_text_lines(sh.table.cell(0, 1).text_frame, _lines(merged[key]), header_bold=True)
    for name in ("tbl_cr_1", "tbl_cr_2"):
        if (sh := get(name)) is not None:
            _fill_cr(sh, merged)
    for p in BD_PLANTS:
        if (sh := get(f"tbl_bd_{p}")) is not None:
            _fill_bd(sh, p, merged)

    _fill_charts(shapes, ctx["techno"], labels, warnings.append)
    sp.replace_placeholders(prs, {"MON": labels["mon"], "YTD": labels["ytd"], "CPLY": labels["cply"],
                                  "YTD_PREV": labels["ytd_prev"], "PERIOD": labels["period_hdr"]})
    buf = io.BytesIO()
    prs.save(buf)
    return RenderResult(content=buf.getvalue(), filename=labels["filename"], warnings=warnings)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `venv/Scripts/python.exe -m pytest tests/test_secretary_review_render.py -v`
Expected: 5 passed. For any `test_tables_match_reference` diff: query the DB for that cell's inputs; if the DB value was corrected after the Sep'26 update, add it to `KNOWN_TABLE_DIFFS` with the reason; otherwise fix the code.

- [ ] **Step 5: Visual check**

Write the 2026-09 render with saved/default texts to the scratchpad and export slides 2, 3, 7, 8, 10, 19, 21, 25 to PNG with the PowerShell/PowerPoint snippet from Task 2 Step 7 (path `…\scratchpad\sr_2026-09.pptx`):

```
venv/Scripts/python.exe -c "import page_secretary_review as p; r=p.render_pptx('2026-09'); open(r'C:/Users/sanja/AppData/Local/Temp/claude/C--opr-mis1/3a70cd03-2de8-48a2-841c-ff2521803604/scratchpad/sr_2026-09.pptx','wb').write(r.content); print(r.warnings)"
```

Read each PNG and compare with the same slide of the reference deck. Expected: same fonts/colours; chart bar colours unchanged; titles read `Sep’26` / `Apr-Sep’26`; narrative cells readable (no overflow off the slide). Report any slide whose text overflows.

- [ ] **Step 6: Commit**

```bash
git add backend/page_secretary_review.py backend/tests/test_secretary_review_render.py
git commit -m "Render the Secretary Review deck from the template

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 7: API router and docs

**Files:**
- Create: `backend/api_secretary_review.py`
- Modify: `backend/main.py` (import near line 436 with the other routers; `app.include_router` near line 916)
- Modify: `docs/DATA_MODEL_AND_REPORT_PAGES.md` (§3 standalone routes table, §4.12 narrative table)
- Test: `backend/tests/test_api_secretary_review.py`

**Interfaces:**
- Consumes: `page_secretary_review.build_context`, `latest_month`, `render_pptx`; `page_secretary_review_texts.effective_texts`, `default_texts`; `secretary_review_text.save_texts`; `secretary_review_layout.BLOCKS`, `validate_month`, `period_labels`.
- Produces HTTP:
  - `GET /api/secretary-review/context[?month=]` → `{labels, filename, warnings, summary: [{item, app_m, act_m, app_ytd, act_ytd}]}` (no month → latest month with production)
  - `GET /api/secretary-review/texts?month=` → `{month, blocks: [{key, section, label, text, saved}]}`
  - `POST /api/secretary-review/texts` body `{month, texts}` → `{saved: n}`
  - `GET /api/secretary-review/default-text?month=&block=` → `{key, text}`
  - `POST /api/secretary-review/pptx` body `{month, texts}` → pptx bytes, `Content-Disposition: attachment; filename="<filename>"`, header `X-Warnings-Count`

- [ ] **Step 1: Write the failing tests**

`backend/tests/test_api_secretary_review.py`:

```python
from fastapi import FastAPI
from fastapi.testclient import TestClient

import api_secretary_review as api
import secretary_review_layout as L

app = FastAPI()
app.include_router(api.router)
client = TestClient(app)


def test_bad_month_is_400():
    assert client.get("/api/secretary-review/texts?month=2026-13").status_code == 400
    assert client.post("/api/secretary-review/pptx", json={"month": "x"}).status_code == 400


def test_unknown_block_is_400():
    assert client.get("/api/secretary-review/default-text?month=2026-09&block=nope").status_code == 400


def test_texts_lists_all_blocks(monkeypatch):
    monkeypatch.setattr(api.pst, "effective_texts",
                        lambda m: {k: {"text": "t", "saved": k == "hl_SAIL"} for k, _, _ in L.BLOCKS})
    body = client.get("/api/secretary-review/texts?month=2026-09").json()
    assert len(body["blocks"]) == 30
    first = body["blocks"][0]
    assert first == {"key": "hl_SAIL", "section": "Highlights", "label": "SAIL highlights (slide 2)",
                     "text": "t", "saved": True}


def test_save_texts_rejects_unknown_keys(monkeypatch):
    seen = {}
    monkeypatch.setattr(api.srt, "save_texts", lambda m, t: seen.update(t) or len(t))
    r = client.post("/api/secretary-review/texts", json={"month": "2026-09", "texts": {"hl_SAIL": "a", "bad": "b"}})
    assert r.status_code == 200 and r.json() == {"saved": 1}
    assert seen == {"hl_SAIL": "a"}


def test_pptx_download(monkeypatch):
    monkeypatch.setattr(api.psr, "render_pptx",
                        lambda m, t: api.psr.RenderResult(content=b"PK", filename="SECRETARY REVIEW Operations Inputs Sep26.pptx", warnings=["w"]))
    r = client.post("/api/secretary-review/pptx", json={"month": "2026-09", "texts": {}})
    assert r.status_code == 200 and r.content == b"PK"
    assert 'filename="SECRETARY REVIEW Operations Inputs Sep26.pptx"' in r.headers["content-disposition"]
    assert r.headers["x-warnings-count"] == "1"


def test_pptx_missing_template_is_500(monkeypatch):
    def boom(m, t):
        raise FileNotFoundError("secretary_review.pptx")
    monkeypatch.setattr(api.psr, "render_pptx", boom)
    r = client.post("/api/secretary-review/pptx", json={"month": "2026-09", "texts": {}})
    assert r.status_code == 500 and "template" in r.json()["detail"].lower()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `venv/Scripts/python.exe -m pytest tests/test_api_secretary_review.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'api_secretary_review'`.

- [ ] **Step 3: Implement `backend/api_secretary_review.py`**

```python
"""Secretary Review deck: month context, editable narrative and the .pptx
download. See page_secretary_review.py."""

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import Response

import page_secretary_review as psr
import page_secretary_review_texts as pst
import secretary_review_text as srt
from secretary_review_layout import BLOCKS, validate_month

router = APIRouter(prefix="/api/secretary-review", tags=["secretary-review"])

_KEYS = {k for k, _, _ in BLOCKS}
_PPTX = "application/vnd.openxmlformats-officedocument.presentationml.presentation"


def _month(month):
    if not validate_month(month or ""):
        raise HTTPException(status_code=400, detail="month must be YYYY-MM")
    return month


@router.get("/context")
async def context(month: str = Query(None)):
    if month is None:
        month = psr.latest_month()
        if month is None:
            raise HTTPException(status_code=404, detail="No production data in the DB")
    _month(month)
    ctx = psr.build_context(month)
    summary = [{"item": name, **{k: ctx["production"][key]["SAIL"][k] for k in ("app_m", "act_m", "app_ytd", "act_ytd")}}
               for key, name in psr.ITEMS]
    return {"labels": ctx["labels"], "filename": ctx["labels"]["filename"],
            "warnings": ctx["warnings"], "summary": summary}


@router.get("/texts")
async def get_texts(month: str = Query(...)):
    _month(month)
    eff = pst.effective_texts(month)
    return {"month": month,
            "blocks": [{"key": k, "section": s, "label": lbl, **eff[k]} for k, s, lbl in BLOCKS]}


@router.post("/texts")
async def save_texts(payload: dict):
    month = _month(payload.get("month"))
    texts = {k: v for k, v in (payload.get("texts") or {}).items() if k in _KEYS}
    return {"saved": srt.save_texts(month, texts)}


@router.get("/default-text")
async def default_text(month: str = Query(...), block: str = Query(...)):
    _month(month)
    if block not in _KEYS:
        raise HTTPException(status_code=400, detail=f"unknown block {block!r}")
    return {"key": block, "text": pst.default_texts(month).get(block, "")}


@router.post("/pptx")
async def pptx(payload: dict):
    month = _month(payload.get("month"))
    texts = {k: v for k, v in (payload.get("texts") or {}).items() if k in _KEYS}
    try:
        res = psr.render_pptx(month, texts)
    except FileNotFoundError as e:
        raise HTTPException(status_code=500, detail=f"Secretary Review template missing: {e}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Secretary Review generation failed: {e}")
    return Response(content=res.content, media_type=_PPTX,
                    headers={"Content-Disposition": f'attachment; filename="{res.filename}"',
                             "X-Warnings-Count": str(len(res.warnings)),
                             "Access-Control-Expose-Headers": "Content-Disposition, X-Warnings-Count"})
```

- [ ] **Step 4: Register in `backend/main.py`**

Next to `from api_capacity import router as capacity_router` (~line 436):

```python
from api_secretary_review import router as secretary_review_router
```

Next to `app.include_router(capacity_router)` (~line 916):

```python
app.include_router(secretary_review_router)
```

- [ ] **Step 5: Run tests, compile, and hit the live API**

```
venv/Scripts/python.exe -m pytest tests/test_api_secretary_review.py -v
venv/Scripts/python.exe -m py_compile main.py api_secretary_review.py
curl -s "http://127.0.0.1:8082/api/secretary-review/context?month=2026-09"
curl -s -o /c/Users/sanja/AppData/Local/Temp/claude/C--opr-mis1/3a70cd03-2de8-48a2-841c-ff2521803604/scratchpad/api.pptx -w "%{http_code} %{size_download}\n" -X POST -H "Content-Type: application/json" -d "{\"month\":\"2026-09\",\"texts\":{}}" http://127.0.0.1:8082/api/secretary-review/pptx
```

Expected: 6 passed; context JSON with `labels.mon = "Sep’26"`; download `200` and a size over 1 MB. (Dev backend auto-reloads; no restart.)

- [ ] **Step 6: Update the data-model doc**

In `docs/DATA_MODEL_AND_REPORT_PAGES.md` §3 "Standalone report routes" table add:

```
| `secretary-review` | `/reports/external` | `page_secretary_review.py` (+ `_texts`, `secretary_review_pptx.py`, `secretary_review_layout.py`), `api_secretary_review.py` (`/api/secretary-review/*`); template `secretary_review_templates/secretary_review.pptx` (built by `scripts/prep_secretary_review_template.py`) | `production_table`, `production_plan_table`, `item_capacity_table`, `techno_data`, `techno_plan_fy`, `breakdown_table`, `capital_repair_table`, `secretary_review_text` |
```

In §4.12 Narrative table add:

```
| `secretary_review_text` | `(report_month, block_key)` → `text`, `updated_at`; `''` = block intentionally empty | `components/reports/secretary-review/View.js` → `/api/secretary-review/texts` | `page_secretary_review.py` (Secretary Review .pptx) |
```

- [ ] **Step 7: Commit**

```bash
git add backend/api_secretary_review.py backend/main.py backend/tests/test_api_secretary_review.py docs/DATA_MODEL_AND_REPORT_PAGES.md
git commit -m "Add /api/secretary-review endpoints and document them

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 8: Seed Sep'26 narrative from the reference deck

**Files:**
- Create: `backend/scripts/import_secretary_review_texts.py`
- Test: `backend/tests/test_import_secretary_review_texts.py`

**Interfaces:**
- Consumes: `secretary_review_text.save_texts`, `secretary_review_pptx.norm`.
- Produces: `extract_texts(pptx_path) -> dict[str, str]` (block key → text, from the *original* reference deck, by slide index); CLI `--month YYYY-MM --pptx PATH [--dry-run]`.

Purpose: 2026-09 regenerates with the hand-written narrative, and the previous-FY capital-repair text carries forward to later months (the DB has no 2025-26 CR rows).

- [ ] **Step 1: Write the failing test**

`backend/tests/test_import_secretary_review_texts.py`:

```python
from pathlib import Path

from scripts.import_secretary_review_texts import extract_texts

REF = Path(__file__).parent / "fixtures" / "secretary_review_sep26_reference.pptx"


def test_extract_texts_from_reference():
    t = extract_texts(REF)
    assert t["hl_SAIL"].startswith("SAIL achieved best")
    assert "Hot Metal" in t["hl_SAIL"]
    assert t["hl_BSP"].startswith("BSP achieved best")
    assert "hl_DSP" not in t                          # no highlights table on the DSP slide
    assert "BF#4" in t["delay_hmcs"]
    assert "RSM" in t["delay_fs"]
    assert "SMS2" in t["cr_BSP_cur"] and t["cr_BSP_prev"]
    assert t["cr_ISP_cur"].startswith("BF-5")
    assert "BLT chute" in t["bd_BSP_BF"]
    assert "HSM-2" in t["bd_RSP_MILL"]
    assert "\n\n" not in t["hl_SAIL"]
```

Also create an empty `backend/scripts/__init__.py` if it does not exist (so `scripts.` is importable in tests).

- [ ] **Step 2: Run test to verify it fails**

Run: `venv/Scripts/python.exe -m pytest tests/test_import_secretary_review_texts.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'scripts.import_secretary_review_texts'`.

- [ ] **Step 3: Implement `backend/scripts/import_secretary_review_texts.py`**

```python
"""One-off: copy the hand-written narrative of a Secretary Review deck that
predates the template (the Sep'26 reference) into secretary_review_text.

    venv/Scripts/python.exe scripts/import_secretary_review_texts.py --month 2026-09 --pptx "<deck.pptx>" [--dry-run]
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pptx import Presentation  # noqa: E402

import secretary_review_pptx as sp  # noqa: E402

HL_SLIDES = {2: "SAIL", 8: "BSP", 10: "DSP", 12: "RSP", 14: "BSL", 16: "ISP"}
BD_SLIDES = {21: "BSP", 22: "DSP", 23: "RSP", 24: "ISP"}
PLANTS = {"BSP", "DSP", "RSP", "BSL", "ISP"}


def _cell_text(cell):
    return "\n".join(p.text.strip() for p in cell.text_frame.paragraphs if p.text.strip())


def _tables(slide):
    return [sh.table for sh in slide.shapes if getattr(sh, "has_table", False) and sh.has_table]


def _group(label):
    n = sp.norm(label)
    if n.startswith("bf"):
        return "BF"
    if n.startswith("sms"):
        return "SMS"
    if n.startswith("mill"):
        return "MILL"
    return None


def extract_texts(pptx_path):
    slides = {i + 1: s for i, s in enumerate(Presentation(str(pptx_path)).slides)}
    out = {}
    for idx, scope in HL_SLIDES.items():
        for t in _tables(slides[idx]):
            if len(t.rows) == 1 and len(t.columns) >= 2:
                out[f"hl_{scope}"] = _cell_text(t.cell(0, 1))
    for idx, key in ((4, "delay_hmcs"), (6, "delay_fs")):
        out[key] = _cell_text(_tables(slides[idx])[0].cell(0, 1))
    for idx in (19, 20):
        for row in _tables(slides[idx])[0].rows:
            plant = row.cells[0].text.strip().upper()
            if plant in PLANTS:
                out[f"cr_{plant}_cur"] = _cell_text(row.cells[1])
                out[f"cr_{plant}_prev"] = _cell_text(row.cells[2])
    for idx, plant in BD_SLIDES.items():
        for row in _tables(slides[idx])[0].rows:
            g = _group(row.cells[0].text)
            if g:
                out[f"bd_{plant}_{g}"] = _cell_text(row.cells[1])
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--month", required=True)
    ap.add_argument("--pptx", required=True)
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    texts = extract_texts(a.pptx)
    for k, v in texts.items():
        print(f"--- {k}\n{v}")
    if not a.dry_run:
        import secretary_review_text as srt
        print(f"saved {srt.save_texts(a.month, texts)} blocks for {a.month}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `venv/Scripts/python.exe -m pytest tests/test_import_secretary_review_texts.py -v`
Expected: 1 passed. If an assertion on a specific slide fails, print `extract_texts(REF)` and correct the slide/row mapping (the reference deck is the ground truth; e.g. slide 22's first row is labelled "BFs" but holds MSM text — keep it as `bd_DSP_BF`, the user can move it on the page).

- [ ] **Step 5: Seed the live DB for 2026-09**

This writes to the live MySQL DB (`secretary_review_text` only, month 2026-09). Run the dry run first, then for real:

```
venv/Scripts/python.exe scripts/import_secretary_review_texts.py --month 2026-09 --pptx tests/fixtures/secretary_review_sep26_reference.pptx --dry-run
venv/Scripts/python.exe scripts/import_secretary_review_texts.py --month 2026-09 --pptx tests/fixtures/secretary_review_sep26_reference.pptx
```

Expected: `saved 21 blocks for 2026-09` (count may differ slightly; it must be > 15).

- [ ] **Step 6: Commit**

```bash
git add backend/scripts/import_secretary_review_texts.py backend/scripts/__init__.py backend/tests/test_import_secretary_review_texts.py
git commit -m "Add importer that seeds Secretary Review narrative from an existing deck

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 9: Frontend tab

**Files:**
- Create: `frontend/src/components/reports/secretary-review/View.js`
- Modify: `frontend/src/components/reports/reportGroups.js` (external group `tabs`, after `board-note`)
- Modify: `frontend/src/components/reports/ReportTabs.js` (`VIEWS` map, after `'board-note'`)

**Interfaces:**
- Consumes: the Task 7 HTTP API; `ReportPage` from `../ReportUI`.
- Produces: tab `secretary-review` at `/reports/external?tab=secretary-review`.

- [ ] **Step 1: Read `frontend/AGENTS.md`** and any Next 16 doc it points to under `frontend/node_modules/next/dist/docs/` for client components. Note anything that changes the code below.

- [ ] **Step 2: Register the tab**

`reportGroups.js`, in the `external` group's `tabs`, after the `board-note` entry:

```js
      { id: 'secretary-review', label: 'Secretary Review (PPTX)', description: 'Monthly Secretary Review operations deck (.pptx) with editable narrative.' },
```

`ReportTabs.js`, in `VIEWS` after `'board-note'`:

```js
  'secretary-review': dynamic(() => import('./secretary-review/View'), { loading }),
```

- [ ] **Step 3: Write `frontend/src/components/reports/secretary-review/View.js`**

```jsx
'use client';

import React, { useState, useEffect } from 'react';
import { ReportPage } from '../ReportUI';

const API = process.env.NEXT_PUBLIC_API_URL || '';
const SECTIONS = ['Highlights', 'Delays', 'Capital Repairs', 'Breakdowns'];
const MONTH_RE = /^\d{4}-(0[1-9]|1[0-2])$/;

async function getJson(url, opts) {
  const res = await fetch(url, opts);
  const body = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(body.detail || `HTTP ${res.status}`);
  return body;
}

function badge(b) {
  if (b.edited) return { text: 'Edited – not saved', color: '#b06000', bg: '#fef7e0' };
  if (b.saved) return { text: 'Saved', color: '#137333', bg: '#e6f4ea' };
  return { text: 'From DB – not saved', color: '#5f6368', bg: '#f1f3f4' };
}

const fmt = (v) => (v === null || v === undefined ? '–' : Math.round(v).toLocaleString('en-IN'));

export default function SecretaryReviewPage() {
  const [month, setMonth] = useState('');
  const [ctx, setCtx] = useState(null);
  const [blocks, setBlocks] = useState([]);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState('');
  const [error, setError] = useState(null);
  const [msg, setMsg] = useState(null);

  // First load: the backend picks the latest month with production data.
  useEffect(() => {
    let cancelled = false;
    getJson(`${API}/api/secretary-review/context`)
      .then((c) => { if (!cancelled) setMonth(c.labels.month); })
      .catch((e) => {
        if (!cancelled) {
          setError(`Failed to load: ${e.message}`);
          setLoading(false);
        }
      });
    return () => { cancelled = true; };
  }, []);

  useEffect(() => {
    if (!MONTH_RE.test(month)) return undefined;
    let cancelled = false;
    Promise.all([
      getJson(`${API}/api/secretary-review/context?month=${month}`),
      getJson(`${API}/api/secretary-review/texts?month=${month}`),
    ])
      .then(([c, t]) => {
        if (cancelled) return;
        setCtx(c);
        setBlocks(t.blocks.map((b) => ({ ...b, edited: false })));
      })
      .catch((e) => { if (!cancelled) setError(`Failed to load ${month}: ${e.message}`); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [month]);

  const changeMonth = (m) => {
    setMonth(m);
    setLoading(true);
    setError(null);
    setMsg(null);
  };

  const setText = (key, text) => {
    setBlocks((prev) => prev.map((b) => (b.key === key ? { ...b, text, edited: true } : b)));
  };

  const textsPayload = () => Object.fromEntries(blocks.map((b) => [b.key, b.text]));

  const resetBlock = async (key) => {
    setError(null);
    try {
      const body = await getJson(`${API}/api/secretary-review/default-text?month=${month}&block=${key}`);
      setText(key, body.text);
    } catch (e) {
      setError(`Reset failed: ${e.message}`);
    }
  };

  const saveAll = async () => {
    setBusy('saving');
    setError(null);
    setMsg(null);
    try {
      await getJson(`${API}/api/secretary-review/texts`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ month, texts: textsPayload() }),
      });
      setBlocks((prev) => prev.map((b) => ({ ...b, saved: true, edited: false })));
      setMsg(`Saved narrative for ${ctx?.labels?.mon || month}.`);
    } catch (e) {
      setError(`Save failed: ${e.message}`);
    } finally {
      setBusy('');
    }
  };

  const download = async () => {
    setBusy('downloading');
    setError(null);
    try {
      const res = await fetch(`${API}/api/secretary-review/pptx`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ month, texts: textsPayload() }),
      });
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        throw new Error(body.detail || `HTTP ${res.status}`);
      }
      const blob = await res.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = ctx?.filename || `Secretary_Review_${month}.pptx`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      window.URL.revokeObjectURL(url);
    } catch (e) {
      setError(`Download failed: ${e.message}`);
    } finally {
      setBusy('');
    }
  };

  const box = { padding: '20px 24px', border: '1px solid #dadce0', borderRadius: '8px', backgroundColor: '#ffffff', marginBottom: '24px' };
  const btn = (disabled, color = '#1a73e8') => ({
    padding: '10px 24px', fontSize: '11pt', fontWeight: 700, border: 'none', borderRadius: '6px',
    cursor: disabled ? 'not-allowed' : 'pointer', backgroundColor: disabled ? '#dadce0' : color, color: '#ffffff',
  });
  const ready = MONTH_RE.test(month) && !loading;

  return (
    <ReportPage
      maxWidth={960}
      title={<>Secretary Review (PPTX)</>}
      description={<>Monthly &ldquo;SECRETARY REVIEW Operations Inputs&rdquo; deck. Tables and charts come from the database for the chosen month. The narrative below starts from the database (breakdowns, capital repairs, best-ever records); edit it, save it for the month, then download. Download uses the text on screen, saved or not.</>}
    >
      <div style={{ ...box, display: 'flex', alignItems: 'center', gap: '16px', flexWrap: 'wrap' }}>
        <label style={{ fontSize: '11pt', fontWeight: 600 }} htmlFor="sr-month">Month</label>
        <input
          id="sr-month"
          type="month"
          value={month}
          onChange={(e) => changeMonth(e.target.value)}
          style={{ padding: '9px 14px', fontSize: '11pt', border: '1px solid #dadce0', borderRadius: '6px' }}
        />
        <button onClick={download} disabled={!ready || !!busy} style={btn(!ready || !!busy)}>
          {busy === 'downloading' ? 'Generating…' : '⬇ Download PPTX'}
        </button>
        <button onClick={saveAll} disabled={!ready || !!busy} style={btn(!ready || !!busy, '#0f9d58')}>
          {busy === 'saving' ? 'Saving…' : 'Save all text'}
        </button>
      </div>

      {error && (
        <div style={{ padding: '14px 18px', border: '1px solid #f28b82', borderRadius: '8px', backgroundColor: '#fce8e6', color: '#c5221f', marginBottom: '24px' }}>
          {error}
        </div>
      )}
      {msg && (
        <div style={{ padding: '10px 14px', backgroundColor: '#e6f4ea', color: '#137333', borderRadius: '6px', marginBottom: '24px' }}>
          {msg}
        </div>
      )}

      {loading ? (
        <div style={{ color: '#5f6368' }}>Loading…</div>
      ) : ctx && (
        <>
          <div style={box}>
            <div style={{ fontSize: '12pt', fontWeight: 700, marginBottom: '10px' }}>
              SAIL — {ctx.labels.mon} &amp; {ctx.labels.ytd} (&apos;000 T)
            </div>
            <table style={{ borderCollapse: 'collapse', fontSize: '10pt', width: '100%' }}>
              <thead>
                <tr style={{ textAlign: 'right', color: '#5f6368' }}>
                  <th style={{ textAlign: 'left' }}>Item</th><th>APP {ctx.labels.mon}</th><th>Actual</th><th>APP {ctx.labels.ytd}</th><th>Actual</th>
                </tr>
              </thead>
              <tbody>
                {ctx.summary.map((r) => (
                  <tr key={r.item} style={{ textAlign: 'right', borderTop: '1px solid #eee' }}>
                    <td style={{ textAlign: 'left' }}>{r.item}</td>
                    <td>{fmt(r.app_m)}</td><td>{fmt(r.act_m)}</td><td>{fmt(r.app_ytd)}</td><td>{fmt(r.act_ytd)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            {ctx.warnings.length > 0 && (
              <div style={{ marginTop: '14px', padding: '10px 14px', backgroundColor: '#fef7e0', borderRadius: '6px', fontSize: '10pt' }}>
                <strong>Data check ({ctx.warnings.length})</strong>
                <ul style={{ margin: '6px 0 0 18px', padding: 0 }}>
                  {ctx.warnings.map((w) => <li key={w}>{w}</li>)}
                </ul>
              </div>
            )}
          </div>

          {SECTIONS.map((section) => (
            <div key={section} style={box}>
              <div style={{ fontSize: '12pt', fontWeight: 700, marginBottom: '12px' }}>{section}</div>
              {blocks.filter((b) => b.section === section).map((b) => {
                const bd = badge(b);
                return (
                  <div key={`${month}-${b.key}`} style={{ marginBottom: '16px' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '4px', flexWrap: 'wrap' }}>
                      <label htmlFor={`sr-${b.key}`} style={{ fontSize: '10pt', fontWeight: 600 }}>{b.label}</label>
                      <span style={{ fontSize: '8.5pt', padding: '2px 8px', borderRadius: '10px', color: bd.color, backgroundColor: bd.bg }}>{bd.text}</span>
                      <button
                        onClick={() => resetBlock(b.key)}
                        style={{ marginLeft: 'auto', fontSize: '9pt', border: '1px solid #dadce0', borderRadius: '4px', background: '#fff', padding: '3px 10px', cursor: 'pointer' }}
                      >
                        Reset from DB
                      </button>
                    </div>
                    <textarea
                      id={`sr-${b.key}`}
                      value={b.text}
                      onChange={(e) => setText(b.key, e.target.value)}
                      rows={Math.min(Math.max(b.text.split('\n').length + 1, 3), 12)}
                      placeholder="Empty — this block is left out of the deck"
                      style={{ width: '100%', padding: '8px 10px', fontSize: '10pt', border: '1px solid #dadce0', borderRadius: '6px', fontFamily: 'inherit', resize: 'vertical' }}
                    />
                  </div>
                );
              })}
            </div>
          ))}
        </>
      )}
    </ReportPage>
  );
}
```

- [ ] **Step 4: Lint**

Run: `cd frontend && npm run lint`
Expected: no errors in the three changed files (pre-existing warnings elsewhere are fine; list any new ones).

- [ ] **Step 5: Check it in the browser**

Use the `run` skill (or claude-in-chrome) on `http://localhost:3000/reports/external?tab=secretary-review`:
1. The month defaults to the latest month; the SAIL summary shows HM Sep actual 1594 when 2026-09 is chosen.
2. 2026-09 text blocks show "Saved" (seeded in Task 8); `hl_DSP` shows "From DB – not saved".
3. Edit one block → badge "Edited – not saved"; Reset from DB restores the DB text.
4. Download PPTX → a file named `SECRETARY REVIEW Operations Inputs Sep26.pptx` downloads; open it with python-pptx and check the edited text is in it.
5. Choose 2026-08 → labels and warnings change; nothing errors in the console.
Report each result.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/components/reports/secretary-review/View.js frontend/src/components/reports/reportGroups.js frontend/src/components/reports/ReportTabs.js
git commit -m "Add Secretary Review (PPTX) tab under External Reports

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

- [ ] **Step 7: Full backend test run**

Run: `cd backend && venv/Scripts/python.exe -m pytest tests -q`
Expected: all pass (the existing golden tests unchanged). Report the summary line.
