"""Secretary Review deck, second layout: the redesigned "Operation Slides for
HSM Review" deck (12 slides). Same numbers and narrative as the standard
layout (page_secretary_review.build_context and the page's text blocks), in
secretary_review_templates/secretary_review_hsm.pptx (see
scripts/prep_secretary_review_hsm_template.py).

Slide 2's highlight cards are built from the hl_SAIL text: each line ending
in ':' / ':-' starts a card, "<Item> <n> MT (Previous best ...)" lines become
tiles, other lines the card's note. Delay slides get one row per
"<Plant> (<Mon>):" heading of the delay text."""

import calendar
import copy
import io
import math
import re

import page_secretary_review as psr
import secretary_review_pptx as sp
from pptx import Presentation
from pptx.oxml.ns import qn
from pptx.util import Emu, Inches
from secretary_review_layout import HL_PROTOS, HSM_KPIS, HSM_TEMPLATE_PATH, KPIS, SCOPES

_FMT = {k: fmt for k, _, fmt in KPIS}
_TILE_RE = re.compile(r"^(?P<item>[A-Za-z][A-Za-z.&/-]*(?: [A-Za-z.&/-]+){0,2})\s+"
                      r"(?P<val>\d[\d.,]*\s*(?:MT|Mt|T|kT|KT))\s*(?P<rest>\(.*\))?\s*$")
_DELAY_HEAD_RE = re.compile(r"^(?P<label>[^:]{1,30}?)\s*:\s*[-–]?\s*$")
_HEAD_ENDS = (":", ":-", ":–")
GAP = Inches(0.08)
MAX_TILE_ROWS = 2


# --------------------------------------------------------------------------
# Slide 2 highlights
# --------------------------------------------------------------------------

def parse_highlights(text):
    """[{"head", "tiles": [(item, value, rest)], "notes": [line]}]"""
    groups, cur = [], None
    for line in psr._lines(text):
        s = line.strip()
        if s.endswith(_HEAD_ENDS):
            cur = {"head": s, "tiles": [], "notes": []}
            groups.append(cur)
            continue
        if cur is None:
            cur = {"head": "", "tiles": [], "notes": []}
            groups.append(cur)
        m = _TILE_RE.match(s)
        if m:
            cur["tiles"].append((m["item"], m["val"], m["rest"] or ""))
        else:
            cur["notes"].append(s)
    for extra in groups[2:]:  # two cards fit; the rest joins the second as text
        groups[1]["notes"] += ([extra["head"]] if extra["head"] else []) + \
            [" ".join(t).strip() for t in extra["tiles"]] + extra["notes"]
    return groups[:2]


def _is_ytd(head, labels):
    marks = [labels["period_hdr"], labels["period_short"], f"Apr-{labels['abbr']}", "H1", "H-1", "Q1", "9M"]
    return labels["n"] > 1 and any(m in head for m in marks)


def _clone(shape):
    el = copy.deepcopy(shape._element)
    shape._element.addprevious(el)
    sp_tree = shape._element.getparent()
    ids = [int(x.get("id")) for x in sp_tree.iter(qn("p:cNvPr")) if x.get("id", "").isdigit()]
    nv = el.find(".//" + qn("p:cNvPr"))
    nv.set("id", str(max(ids) + 1))
    nv.set("name", "Highlights " + shape.name[3:-2])  # hl_tile_a -> Highlights tile
    return el


def _place(el, x, y, w, h):
    off, ext = el.find(".//" + qn("a:off")), el.find(".//" + qn("a:ext"))
    off.set("x", str(int(x)))
    off.set("y", str(int(y)))
    ext.set("cx", str(int(w)))
    ext.set("cy", str(int(h)))


def _set_runs(el, texts):
    """Paragraph i of the text box gets texts[i] in its first run; extra
    paragraphs are dropped, missing ones copied from the last."""
    tx = el.find(".//" + qn("p:txBody"))
    paras = tx.findall(qn("a:p"))
    while len(paras) < len(texts):
        paras[-1].addnext(copy.deepcopy(paras[-1]))
        paras = tx.findall(qn("a:p"))
    for p in paras[len(texts):]:
        tx.remove(p)
    for p, text in zip(tx.findall(qn("a:p")), texts):
        runs = p.findall(qn("a:r"))
        if not runs:
            continue
        runs[0].find(qn("a:t")).text = sp._XML_ILLEGAL.sub("", text)
        for r in runs[1:]:
            p.remove(r)


def _card(protos, v, group, box, labels):
    x, y, w, h = box
    card, head, tile, fig, note = (protos[f"hl_{k}_{v}"] for k in ("card", "head", "tile", "fig", "note"))
    pad = head.left - card.left
    card_el = _clone(card)
    period = labels["period_hdr"] if _is_ytd(group["head"], labels) else labels["mon"]
    el = _clone(head)
    _place(el, x + pad, y + (head.top - card.top), w - 2 * pad, head.height)
    _set_runs(el, [f"{period} Highlights", group["head"] or "SAIL achieved:-"])

    inner_w = w - 2 * pad
    top = y + (tile.top - card.top)
    bottom = y + h - pad
    tiles, notes = list(group["tiles"]), list(group["notes"])
    if tiles:
        wide = w > 2 * card.width
        cols = min(len(tiles), 4) if wide else (len(tiles) if len(tiles) <= 3 else 2 if len(tiles) == 4 else 3)
        rows = min(math.ceil(len(tiles) / cols), MAX_TILE_ROWS)
        notes = [" ".join(t).strip() for t in tiles[cols * rows:]] + notes
        tiles = tiles[: cols * rows]
    note_h = note.height + Inches(0.18) * max(len(notes) - 2, 0) if notes else 0
    if tiles:
        area = bottom - top - (note_h + GAP if notes else 0)
        tw = (inner_w - (cols - 1) * GAP) / cols
        th = min(tile.height, (area - (rows - 1) * GAP) / rows)
        for i, (item, val, rest) in enumerate(tiles):
            tx = x + pad + (i % cols) * (tw + GAP)
            ty = top + (i // cols) * (th + GAP)
            _place(_clone(tile), tx, ty, tw, th)
            el = _clone(fig)
            _place(el, tx + (fig.left - tile.left), ty + (fig.top - tile.top),
                   tw - (tile.width - fig.width), th - (fig.top - tile.top) * 2)
            _set_runs(el, [item, val, rest])
        note_top = top + rows * th + (rows - 1) * GAP + GAP
    else:
        note_top = top
    if notes:
        el = _clone(note)
        nh = note_h if tiles else max(bottom - note_top, note.height)
        _place(el, x + pad, note_top, inner_w, nh)
        _set_runs(el, notes)
        end = note_top + nh
    else:
        end = note_top - GAP
    # The card ends below its content rather than leaving the space empty.
    _place(card_el, x, y, w, min(h, end + pad - y))


def fill_highlights(prs, text, labels):
    protos = sp.named_shapes(prs)
    protos = {k: protos[k] for k in HL_PROTOS}
    groups = parse_highlights(text)
    a, b = protos["hl_card_a"], protos["hl_card_b"]
    if len(groups) == 1:
        _card(protos, "a", groups[0], (a.left, a.top, b.left + b.width - a.left, a.height), labels)
    elif len(groups) == 2:
        _card(protos, "a", groups[0], (a.left, a.top, a.width, a.height), labels)
        _card(protos, "b", groups[1], (b.left, b.top, b.width, b.height), labels)
    for sh in protos.values():
        sp.remove_shape(sh)


# --------------------------------------------------------------------------
# Delay slides
# --------------------------------------------------------------------------

def parse_delays(text):
    """[(label, [lines])], one per '<Plant> (<Mon>):' heading."""
    groups = []
    for line in psr._lines(text):
        s = line.strip()
        m = _DELAY_HEAD_RE.match(s)
        if m:
            groups.append((m["label"], []))
        else:
            if not groups:
                groups.append(("", []))
            groups[-1][1].append(s)
    return groups


_KEY_RE = re.compile(r"^(?P<key>[^:\s][^:]{0,18}:)(?P<rest>.*)$")


def set_keyed_lines(text_frame, lines):
    """One paragraph per line, like the template's: a leading unit ('BF-2:')
    in the first run's style, the rest in the second's."""
    tx = text_frame._txBody
    paras = tx.findall(qn("a:p"))
    proto = paras[0]
    for p in paras:
        tx.remove(p)
    for line in lines or [""]:
        p = copy.deepcopy(proto)
        key_r, rest_r = p.findall(qn("a:r"))[:2]
        line = sp._XML_ILLEGAL.sub("", line)
        m = _KEY_RE.match(line)
        if m:
            key_r.find(qn("a:t")).text, rest_r.find(qn("a:t")).text = m["key"], m["rest"]
        else:
            p.remove(key_r)
            rest_r.find(qn("a:t")).text = line
        tx.append(p)


def fill_delays(shape, text, slide_h, warn, label):
    table = shape.table
    tbl = table._tbl
    first, nxt = (copy.deepcopy(tr) for tr in tbl.tr_lst[:2])
    for tr in list(tbl.tr_lst):
        tbl.remove(tr)
    groups = parse_delays(text) or [("", ["No major delays"])]
    # Every row styled like the continuation row; the first keeps the merged group cell.
    for i in range(len(groups)):
        tr = copy.deepcopy(nxt)
        if i == 0:
            tr.replace(tr.tc_lst[0], copy.deepcopy(first.tc_lst[0]))
        tbl.append(tr)
    tc0 = table.cell(0, 0)._tc
    if len(groups) > 1:
        tc0.set("rowSpan", str(len(groups)))
    elif "rowSpan" in tc0.attrib:
        del tc0.attrib["rowSpan"]
    for i, (head, lines) in enumerate(groups):
        sp.set_text_lines(table.cell(i, 1).text_frame, [head])
        set_keyed_lines(table.cell(i, 2).text_frame, lines)
    # Each row its text's height, the table's spare height shared equally.
    sz = psr._base_sz([table.cell(0, 2)])
    need = [max(psr._wrapped_lines(table.cell(i, 2), sz, table.columns[2].width), 1)
            * sz / 100 * psr.LINE_FACTOR * 12700 + psr.CELL_MARGIN_EMU for i in range(len(groups))]
    spare = max(shape.height - sum(need), 0) / len(need)
    for i, h in enumerate(need):
        table.rows[i].height = Emu(int(h + spare))
    psr._fit_table_text(shape, [table.cell(i, 2) for i in range(len(groups))], slide_h, warn, label)


# --------------------------------------------------------------------------
# Charts and render
# --------------------------------------------------------------------------

def fill_charts(shapes, techno, labels, warn):
    head = [labels["fy_m2"], labels["fy_m1"], labels["fy_tgt"]]
    for scope in SCOPES:
        for key in HSM_KPIS:
            t = techno[scope][key]
            frame = shapes.get(f"ch_{scope}_{key}")
            if frame is None:
                warn(f"template shape ch_{scope}_{key} not found")
                continue
            ab = calendar.month_abbr[int(t["month_used"][5:])]
            values = [t["fy_m2"], t["fy_m1"], t["target"], t["month"], t["ytd"]]
            fmt = _FMT[key]
            sp.replace_chart_data(frame.chart, head + [ab, labels["ytd_cat"]], values, fmt)
            sp.fit_value_axis(frame.chart, values, 0.1 if "." in fmt else 10)


def render_pptx(month, texts=None):
    ctx = psr.build_context(month)
    labels, production = ctx["labels"], ctx["production"]
    # Sp. CO2 is not on this layout.
    warnings = [w for w in ctx["warnings"] if "CO2" not in w and "CO₂" not in w]
    merged = psr.merged_texts(month, texts)

    prs = Presentation(str(HSM_TEMPLATE_PATH))
    shapes = sp.named_shapes(prs)

    def get(name):
        sh = shapes.get(name)
        if sh is None:
            warnings.append(f"template shape {name} not found")
        return sh

    plan_label = psr.BASIS_LABEL[ctx["basis"]]
    if (sh := get("tbl_sail")) is not None:
        psr._fill_item_table(sh.table, production, "SAIL")
        psr._relabel_plan_headers(sh.table, plan_label)
    for name in ("tbl_plants_hm_cs", "tbl_plants_ss_fs"):
        if (sh := get(name)) is not None:
            psr._fill_section_table(sh.table, production)
            psr._relabel_plan_headers(sh.table, plan_label)
    if all(k in shapes for k in HL_PROTOS):
        fill_highlights(prs, merged["hl_SAIL"], labels)
    else:
        warnings.append("template highlight shapes not found")
    for name, key, n in (("tbl_delay_hmcs", "delay_hmcs", 4), ("tbl_delay_fs", "delay_fs", 6)):
        if (sh := get(name)) is not None:
            fill_delays(sh, merged[key], prs.slide_height, warnings.append, f"Delay report (slide {n})")
    fill_charts(shapes, ctx["techno"], labels, warnings.append)
    sp.replace_placeholders(prs, {"MON": labels["mon"], "YTD": labels["ytd"], "CPLY": labels["cply"],
                                  "YTD_PREV": labels["ytd_prev"], "PERIOD": labels["period_hdr"]})
    buf = io.BytesIO()
    prs.save(buf)
    return psr.RenderResult(content=buf.getvalue(), filename=labels["filename_hsm"], warnings=warnings)
