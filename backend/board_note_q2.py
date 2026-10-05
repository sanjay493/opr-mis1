"""Q-2 + H-1 Board Note docx generator.

Generalizes `_update_bn_board_report.py` (a one-off script that hand-patched
one real document, `Report_format/BN_ Production Q-2 and H-1'25-26 R-2.docx`,
from Q-2/H-1'25-26 to Q-2/H-1'26-27) into a reusable `generate(fy)` that
fills `board_note_templates/board_note_q2_template.docx` (a verbatim copy of
that same source file) for any financial year.

IMPORTANT: the template is a partially-completed real draft, not a blank
form -- the SAIL-level Q-2 section (narrative, table, best-ever bullets) had
already been hand-updated to Q-2'26-27 figures when this template was
copied, while everything else was still stale 25-26 content. This module
must never rely on any paragraph "already looking right" for one fy --
every period-specific paragraph listed in the index map below is
unconditionally regenerated from the DB on every call.

Index map (Step 2): derived directly from the template via
`document.element.body.iterchildren()` (see dump technique in the design
doc). Paragraph/table indices are into `docx.Document(...).paragraphs` /
`.tables` as produced by python-docx for this exact template file -- if the
template file is ever hand-edited, these must be re-derived.

Known limitations (documented, not bugs):
  - The MoU figures used in the opening "Finished Steel w.r.t. MoU" section
    (`_FS_Q2_MOU`, `_FS_H1_MOU` below) are not sourced from the DB (no MoU
    table exists); they are the FY2026-27 quarterly/half-yearly MoU values
    carried over from the one-off script and must be updated by hand if
    this generator is ever run for a different fy.
  - The title (P3), the "SAIL and Plant-wise Production performance
    during..." intro (P18/P19), and the techno section's "This was achieved
    through..." bullets (P337-340) are left as template static text, same
    as the one-off script -- they are not period-parameterized here.
  - ASP, SSP and VISL have no "Highlights:" section in the template for
    either Q-2 or H-1 (the source document simply didn't include one for
    these three plants), so no highlights are written for them even if
    `board_note_common.best_ever_bullets` would otherwise report a record;
    there is no template slot to host that text without restructuring the
    document, which is out of scope for a slot-filling adapter.
  - No plant has a "why production fell short" block for H-1 in this
    template (only Q-2) -- confirmed from the template structure, not an
    oversight.
"""

import io

import docx

import board_note_common as bnc
import board_note_docx_utils as bdu
import board_note_manual_text as bnm
import db
import page_techno as pt
import techno_period as tp

TEMPLATE_PATH = "board_note_templates/board_note_q2_template.docx"

# --------------------------------------------------------------------------
# Index map (Step 2) -- re-derived directly against the template via
# docx.Document(...).element.body.iterchildren(); every constant below is
# commented with the literal heading/lead-in text it sits under so it can
# be re-verified by eye against a fresh dump.
# --------------------------------------------------------------------------

# -- Opening "SAIL: Production performance for Finished Steel w.r.t. MoU" --
P_FS_Q2_NARRATIVE = 9    # "The Production of Finished Steel during Q-2'26 was ..."
P_FS_H1_NARRATIVE = 11   # "The Production of Finished Steel during April-September'26 was ..."
TABLE_MOU = 0            # "Plant | MoU 2026-27 | Q-1'26-27 | Q-2'26-27 (ABP/Act/%Ful) | Apr-Sep'26 (ABP/Act/%Ful)"
MOU_ROW_PLANT = {2: "BSP", 3: "DSP", 4: "RSP", 5: "BSL", 6: "ISP"}
MOU_ROW_SPECIAL_STEEL = 7   # "Special Steel Plants" (ASP+SSP+VISL total)
MOU_ROW_SAIL = 8            # "SAIL" (5 plants + special steel + Conversion)

# These two are NOT sourced from the DB -- see module docstring.
_FS_Q2_MOU = 4.448
_FS_H1_MOU = 8.812

# -- "SAIL and Plant-wise Production performance during Q-2... and H-1..." -
P_PLANT_SECTION_TITLE = 48   # "Plant wise: Production performance during Q-2'25-26 and H-1'25-26 w.r.t. ABP"

# -- SAIL: Q-2 section -------------------------------------------------------
P_SAIL_Q2_HEADING = 21       # "SAIL: Production performance during Q-2'26-27 "
P_SAIL_Q2_LABEL = 23         # "Q-2'26-27:"
P_SAIL_Q2_SUMMARY = 24       # "Hot Metal production during Q-2'26-27 was ... Saleable Steel production was ..."
TABLE_SAIL_Q2 = 1            # SAIL Q-2 ABP/Actual/%Ful/CPLY/%Gr table
P_SAIL_Q2_HIGHLIGHTS_HEADING = 28   # "Highlights:"
P_SAIL_Q2_HIGHLIGHTS_LEADIN = 29    # "SAIL achieved best ever Q-2 production for following:" (kept static)
SAIL_Q2_HIGHLIGHTS_SLOTS = [30, 31, 32, 33]   # one bullet per core item, unconditionally regenerated

# -- SAIL: H-1 section --------------------------------------------------------
P_SAIL_H1_HEADING = 35       # "SAIL: Production performance during H-1'25-26 "
P_SAIL_H1_LABEL = 37         # "H-1'25-26:"
P_SAIL_H1_SUMMARY = 38       # "Hot Metal production during H-1'25-26 was ... Saleable Steel production was ..."
TABLE_SAIL_H1 = 2            # SAIL H-1 ABP/Actual/%Ful/CPLY/%Gr table
P_SAIL_H1_HIGHLIGHTS_HEADING = 41   # "Highlights:"
P_SAIL_H1_HIGHLIGHTS_LEADIN = 42    # "SAIL achieved best ever Apr-Sep (H-1) production for following:" (kept static)
SAIL_H1_HIGHLIGHTS_SLOTS = [43, 44, 45]       # template has 3 slots (Hot Metal often isn't a new H-1 record)

# SAIL has no "why production fell short" block at all (neither Q-2 nor H-1).

# -- Item-row configs for fill_period_table (row_idx, display, db_item, add_conv) --
BIG5_ITEMS = [
    (2, "Hot Metal", "Hot Metal", False),
    (3, "Crude Steel", "Total Crude Steel", False),
    (4, "Saleable Steel", "Saleable Steel", False),
    (5, "Finished Steel", "Finished Steel", False),
]
SAIL_ITEMS = [
    (2, "Hot Metal", "Hot Metal", False),
    (3, "Crude Steel", "Total Crude Steel", False),
    (4, "Saleable Steel", "Saleable Steel", False),
    (5, "Finished Steel", "Finished Steel", True),   # SAIL Finished Steel includes Conversion
]
SPECIAL2_ITEMS = [
    (2, "Crude Steel", "Total Crude Steel", False),
    (3, "Saleable Steel", "Saleable Steel", False),
    (4, "Finished Steel", "Finished Steel", False),
]
VISL_ITEMS = [
    (2, "Saleable Steel", "Saleable Steel", False),
    (3, "Finished Steel", "Finished Steel", False),
]

SPECIAL_STEEL_PLANTS = ["ASP", "SSP", "VISL"]

# -- Per-plant (Big-5) index map ----------------------------------------------
# (table_q2, table_h1, period_label_p_q2, period_label_p_h1,
#  summary_p_q2, summary_p_h1, item_rows, summary_kind)
BIG5_PLANT_CONFIG = {
    # "BHILAI STEEL PLANT:" (P50)
    "BSP": dict(table_q2=3, table_h1=4, label_q2=52, label_h1=73,
                summary_q2=53, summary_h1=74, item_rows=BIG5_ITEMS, kind="big"),
    # "DURGAPUR STEEL PLANT:" (P94)
    "DSP": dict(table_q2=5, table_h1=6, label_q2=96, label_h1=116,
                summary_q2=97, summary_h1=117, item_rows=BIG5_ITEMS, kind="big"),
    # "ROURKELA STEEL PLANT:" (P127)
    "RSP": dict(table_q2=7, table_h1=8, label_q2=129, label_h1=159,
                summary_q2=130, summary_h1=160, item_rows=BIG5_ITEMS, kind="big"),
    # "BOKARO STEEL PLANT" (P171)
    "BSL": dict(table_q2=9, table_h1=10, label_q2=173, label_h1=214,
                summary_q2=174, summary_h1=215, item_rows=BIG5_ITEMS, kind="big"),
    # "IISCO STEEL PLANT:" (P230)
    "ISP": dict(table_q2=11, table_h1=12, label_q2=232, label_h1=264,
                summary_q2=233, summary_h1=265, item_rows=BIG5_ITEMS, kind="big"),
}

# "ALLOY STEELS PLANT:" (P280) / "SALEM STEEL PLANT:" (P293) /
# "VISVESVARAYA IRON & STEEL PLANT:" (P312)
SMALL_PLANT_CONFIG = {
    "ASP": dict(table_q2=13, table_h1=14, label_q2=282, label_h1=289,
                summary_q2=283, summary_h1=290, item_rows=SPECIAL2_ITEMS, kind="small"),
    "SSP": dict(table_q2=15, table_h1=16, label_q2=295, label_h1=309,
                summary_q2=296, summary_h1=310, item_rows=SPECIAL2_ITEMS, kind="small"),
    "VISL": dict(table_q2=17, table_h1=18, label_q2=314, label_h1=323,
                 summary_q2=316, summary_h1=325, item_rows=VISL_ITEMS, kind="visl"),
}

PLANT_CONFIG = {**BIG5_PLANT_CONFIG, **SMALL_PLANT_CONFIG}
PLANT_ORDER = ["BSP", "DSP", "RSP", "BSL", "ISP", "ASP", "SSP", "VISL"]

# -- Per-plant Highlights bullet slots -----------------------------------
# Each entry's lead-in paragraph (e.g. "BSP achieved best ever Q-2
# production for following:") is left untouched as static prose; the
# slots listed are every paragraph after it (flattened, including any
# second lead-in sentence some plants have, e.g. BSL/ISP's separate
# "...Quarter..."/"...Q-2..." split) up to the next heading. ASP/SSP/VISL
# have no "Highlights:" section at all in the template for either period.
HIGHLIGHTS_SLOTS = {
    # "Highlights:" (P28) / "SAIL achieved best ever Q-2 production for following:" (P29, kept)
    ("SAIL", "q2"): SAIL_Q2_HIGHLIGHTS_SLOTS,
    # "Highlights:" (P41) / "SAIL achieved best ever Apr-Sep (H-1) production for following:" (P42, kept)
    ("SAIL", "h1"): SAIL_H1_HIGHLIGHTS_SLOTS,

    # "Highlights:" (P56) / "BSP achieved best ever Q-2 production for following:" (P57, kept)
    ("BSP", "q2"): [58, 59],
    # "Highlights:" (P77) / "BSP achieved best ever H-1 production for following:" (P78, kept)
    ("BSP", "h1"): [79, 80, 81, 82, 83, 84, 85, 86, 87, 88, 89, 90, 91, 92],

    # "Highlights:" (P102) -- no lead-in sentence in the template
    ("DSP", "q2"): [103, 104],
    # "Highlights:" (P121) -- no lead-in sentence in the template
    ("DSP", "h1"): [122, 123, 124],

    # "Highlights:" (P134) -- no lead-in sentence in the template
    ("RSP", "q2"): [135, 136],
    # "Highlights:" (P164) / "RSP achieved best ever H-1 production for following:" (P165, kept)
    ("RSP", "h1"): [166, 167, 168, 169],

    # "Highlights:" (P177) / "BSL achieved best ever Quarter production for following:" (P178, kept);
    # P181's second lead-in ("BSL achieved best ever Q-2 production for following:") is flattened in
    ("BSL", "q2"): [179, 180, 181, 182, 183, 184, 185],
    # "Highlights:" (P219) / "BSL achieved best ever half yearly production for following:" (P220, kept);
    # P224's second lead-in ("BSL achieved best ever H-1 production for following:") is flattened in
    ("BSL", "h1"): [221, 222, 223, 224, 225, 226, 227, 228],

    # "Highlights:" (P237) / "ISP achieved best ever Quarter production for following:" (P239, kept);
    # P244's second lead-in ("ISP achieved best ever Q-2 production for following:") is flattened in
    ("ISP", "q2"): [240, 241, 242, 244, 245, 246, 247, 248],
    # "Highlights:" (P268) / "ISP achieved best ever Half-yearly production for following:" (P269, kept);
    # P277's second lead-in ("ISP achieved best ever H-1 production for following:") is flattened in
    ("ISP", "h1"): [270, 271, 272, 273, 274, 275, 277, 278, 279],

    # ASP/SSP/VISL: no entries -- no "Highlights:" section exists for them in this template.
}

# -- Per-plant/SAIL "why production fell short" slots (Q-2 only; no unit has an H-1 block) --
WHY_HEADING = {
    # "Production Performance during Q-2'25-26:"
    "BSP": 61, "DSP": 106, "RSP": 138, "BSL": 187, "ISP": 250,
    "ASP": 286, "SSP": 299, "VISL": 319,
}
WHY_SLOTS = {
    # "Hot Metal: The shortfall in production was mainly due to:" ... "Saleable Steel: ..."
    "BSP": [63, 64, 65, 66, 67, 69, 71],
    # "Hot Metal: BF-2: ..." / "Crude Steel:" / "Saleable Steel:"
    "DSP": [108, 110, 111, 113, 114],
    # "Hot Metal: Production was mainly affected due to following:" ... "Saleable Steel: ..."
    "RSP": [140, 141, 142, 143, 144, 145, 146, 147, 148, 149, 150, 151, 152, 153, 154, 155, 157],
    # "BF-5: Blowing down has been deferred..." ... "Saleable Steel: As per Crude availability..."
    "BSL": [189, 191, 192, 193, 194, 195, 196, 197, 199, 200, 201, 202, 203, 204, 205, 206, 207,
            208, 209, 210, 211, 212],
    # "Hot Metal: " / "BF-5: Capital Repair deferred..." ... "USM: Capital Repair deferred..."
    "ISP": [251, 252, 254, 255, 256, 258, 259, 260, 261, 262],
    # "Saleable Steel production was as per Crude Steel availability and availability of orders."
    "ASP": [288],
    # "Crude Steel production was affected due to the following issues: " ... bullets
    "SSP": [301, 302, 303, 304, 305, 306, 307],
    # "Saleable Steel production was as per availability of orders."
    "VISL": [321],
}

# -- Techno-economic section -------------------------------------------------
P_TECHNO_SECTION_TITLE = 329   # "SAIL and Plant-wise Major Techno-economic parameters performance during Q-2'25-26 and H-1'25-26:"
TABLE_TECHNO = 19               # Parameters | Plant | Target | Q-2cur | Q-2cply | H-1cur | H-1cply
P_TECHNO_PERF_HEADING = 331     # "Techno-economic Performance during H-1'25-26"
P_TECHNO_COKE = 332             # "Coke Rate: SAIL registered an improvement of 2% w.r.t. CPLY."
P_TECHNO_CDI = 333              # "CDI Rate: SAIL registered an improvement of 3% w.r.t. CPLY."
P_TECHNO_FUEL = 334             # "Fuel Rate: SAIL registered an improvement of 2% w.r.t. CPLY."
P_TECHNO_BFP = 335              # "BF Productivity: SAIL registered an improvement of 6% w.r.t. CPLY."
# P337-340 ("This was achieved through...") are left as static template text -- see module docstring.

TECHNO_PLANTS = ["BSP", "DSP", "RSP", "BSL", "ISP", "SAIL"]
TECHNO_PARAMS = ["Coke Rate", "CDI Rate", "Fuel Rate", "BF Productivity"]


# --------------------------------------------------------------------------
# Table-fill / paragraph-text helpers (adapter-local; same shape as the
# one-off script, now driven by board_note_common for all period math)
# --------------------------------------------------------------------------

def _cply_label_nl(label_fn, fy_start, quarter):
    """A prior-year period label with a newline inserted after the quote
    mark, matching the "Q-2'\\n25-26" style used in the CPLY half of every
    table header."""
    return label_fn(fy_start - 1, quarter).replace("’", "’\n")


def fill_period_table(cur, table, plant, item_rows, cur_months, cply_months, fy_start):
    for row_idx, _display, db_item, add_conv in item_rows:
        ann, abp, act, pct, cply, gr = bnc.row_values(
            cur, plant, db_item, cur_months, cply_months, fy_start, add_conv=add_conv
        )
        cells = table.rows[row_idx].cells
        bdu.set_cell(cells[1], bnc.fmt_ann(ann))
        bdu.set_cell(cells[2], bnc.fmt_tbl(abp, plant))
        bdu.set_cell(cells[3], bnc.fmt_tbl(act, plant))
        bdu.set_cell(cells[4], bnc.fmt_pct(pct))
        bdu.set_cell(cells[5], bnc.fmt_tbl(cply, plant))
        bdu.set_cell(cells[6], bnc.fmt_pct(gr))


def set_period_header(table, cur_label, cply_label):
    """Row 0 is the merged period label (repeated over the ABP/Actual/%Ful
    trio of columns); row 1 keeps its own ABP/Actual/% Ful. sub-labels and
    only gets the period-less cply/%Gr labels refreshed."""
    row0, row1 = table.rows[0].cells, table.rows[1].cells
    for c in (2, 3, 4):
        bdu.set_cell(row0[c], cur_label)
    bdu.set_cell(row1[2], "ABP")
    bdu.set_cell(row1[3], "Actual")
    bdu.set_cell(row1[4], "% Ful.")
    bdu.set_cell(row0[5], f"{cply_label}\nAct.")
    bdu.set_cell(row1[5], f"{cply_label}\nAct.")
    bdu.set_cell(row0[6], f"% Gr. w.r.t.\n{cply_label}")
    bdu.set_cell(row1[6], f"% Gr. w.r.t.\n{cply_label}")


def set_abp_header(table, fy_start):
    row0, row1 = table.rows[0].cells, table.rows[1].cells
    label = f"ABP\n{fy_start}-{str(fy_start + 1)[2:]}"
    bdu.set_cell(row0[1], label)
    bdu.set_cell(row1[1], label)


def plant_summary_big(cur, plant, months, cply_months, fy_start):
    _, _, hm, hm_pct, _, _ = bnc.row_values(cur, plant, "Hot Metal", months, cply_months, fy_start)
    _, _, cs, cs_pct, _, _ = bnc.row_values(cur, plant, "Total Crude Steel", months, cply_months, fy_start)
    _, _, ss, ss_pct, _, _ = bnc.row_values(cur, plant, "Saleable Steel", months, cply_months, fy_start)
    return (f"Hot Metal production during {{P}} was {bnc.fmt_mt(hm)} MT ({bnc.fmt_pct(hm_pct)}% of ABP), Crude Steel "
            f"production was {bnc.fmt_mt(cs)} MT ({bnc.fmt_pct(cs_pct)}% of ABP) and Saleable Steel production was "
            f"{bnc.fmt_mt(ss)} MT ({bnc.fmt_pct(ss_pct)}% of ABP). ")


def plant_summary_small(cur, plant, months, cply_months, fy_start):
    _, _, cs, cs_pct, _, _ = bnc.row_values(cur, plant, "Total Crude Steel", months, cply_months, fy_start)
    _, _, ss, ss_pct, _, _ = bnc.row_values(cur, plant, "Saleable Steel", months, cply_months, fy_start)
    return (f"Crude Steel production during {{P}} was {bnc.fmt_t(cs)} T ({bnc.fmt_pct(cs_pct)}% of ABP) and Saleable "
            f"Steel production was {bnc.fmt_t(ss)} T ({bnc.fmt_pct(ss_pct)}% of ABP).")


def plant_summary_visl(cur, plant, months, cply_months, fy_start):
    _, _, ss, ss_pct, _, _ = bnc.row_values(cur, plant, "Saleable Steel", months, cply_months, fy_start)
    return f"Saleable Steel production during {{P}} was {bnc.fmt_t(ss)} T ({bnc.fmt_pct(ss_pct)}% of ABP). "


_SUMMARY_FN = {"big": plant_summary_big, "small": plant_summary_small, "visl": plant_summary_visl}


def fmt_techno_target(param, v):
    if v is None:
        return None
    return f"{v:.2f}" if param == "BF Productivity" else str(round(v))


def techno_improvement(techno_by_param, param, higher_is_better=False):
    sec = techno_by_param[param]
    row = next(r for r in sec["rows"] if r["plant"] == "SAIL")
    cur_v = row["values"]["H1cur"]["value"]
    cply_v = row["values"]["H1cply"]["value"]
    return bnc.improvement_pct(cur_v, cply_v, higher_is_better)


# --------------------------------------------------------------------------
# generate()
# --------------------------------------------------------------------------

def generate(fy: str) -> bytes:
    fy_start = int(fy[:4])

    Q1_CUR = bnc.quarter_months(fy_start, 1)
    Q2_CUR = bnc.quarter_months(fy_start, 2)
    Q2_CPLY = bnc.quarter_months(fy_start - 1, 2)
    H1_CUR = bnc.long_period_months(fy_start, 2)
    H1_CPLY = bnc.long_period_months(fy_start - 1, 2)

    q2_label = bnc.quarter_label(fy_start, 2)
    q2_cply_label = _cply_label_nl(bnc.quarter_label, fy_start, 2)
    h1_label = bnc.long_period_label(fy_start, 2)
    h1_cply_label = _cply_label_nl(bnc.long_period_label, fy_start, 2)
    yy = str(fy_start)[2:]

    manual = bnm.get_manual_text(fy, 2)

    conn = db.connect()
    cur = conn.cursor()
    try:
        doc = docx.Document(TEMPLATE_PATH)
        tables = doc.tables
        paras = doc.paragraphs

        def para(i):
            return paras[i]

        # ---- SAIL Q-2 / H-1 tables -----------------------------------
        set_abp_header(tables[TABLE_SAIL_Q2], fy_start)
        set_period_header(tables[TABLE_SAIL_Q2], q2_label, q2_cply_label)
        fill_period_table(cur, tables[TABLE_SAIL_Q2], "SAIL", SAIL_ITEMS, Q2_CUR, Q2_CPLY, fy_start)

        set_abp_header(tables[TABLE_SAIL_H1], fy_start)
        set_period_header(tables[TABLE_SAIL_H1], h1_label, h1_cply_label)
        fill_period_table(cur, tables[TABLE_SAIL_H1], "SAIL", SAIL_ITEMS, H1_CUR, H1_CPLY, fy_start)

        # ---- plant tables ---------------------------------------------
        for plant in PLANT_ORDER:
            cfg = PLANT_CONFIG[plant]
            set_abp_header(tables[cfg["table_q2"]], fy_start)
            set_period_header(tables[cfg["table_q2"]], q2_label, q2_cply_label)
            fill_period_table(cur, tables[cfg["table_q2"]], plant, cfg["item_rows"], Q2_CUR, Q2_CPLY, fy_start)

            set_abp_header(tables[cfg["table_h1"]], fy_start)
            set_period_header(tables[cfg["table_h1"]], h1_label, h1_cply_label)
            fill_period_table(cur, tables[cfg["table_h1"]], plant, cfg["item_rows"], H1_CUR, H1_CPLY, fy_start)

        # ---- table 0: Finished Steel vs MoU (Actual columns only) -----
        t0 = tables[TABLE_MOU]
        for ridx, plant in MOU_ROW_PLANT.items():
            q1 = bnc.period_sum(cur, "act", Q1_CUR, plant, "Finished Steel")
            q2 = bnc.period_sum(cur, "act", Q2_CUR, plant, "Finished Steel")
            h1 = bnc.period_sum(cur, "act", H1_CUR, plant, "Finished Steel")
            cells = t0.rows[ridx].cells
            bdu.set_cell(cells[2], bnc.fmt_ann(q1))
            bdu.set_cell(cells[4], bnc.fmt_ann(q2))
            bdu.set_cell(cells[7], bnc.fmt_ann(h1))

        def special_steel_total(months):
            total, found = 0.0, False
            for p in SPECIAL_STEEL_PLANTS:
                v = bnc.period_sum(cur, "act", months, p, "Finished Steel")
                if v is not None:
                    total += v
                    found = True
            return total if found else None

        ssp_q1, ssp_q2, ssp_h1 = special_steel_total(Q1_CUR), special_steel_total(Q2_CUR), special_steel_total(H1_CUR)
        cells = t0.rows[MOU_ROW_SPECIAL_STEEL].cells
        bdu.set_cell(cells[2], bnc.fmt_ann(ssp_q1))
        bdu.set_cell(cells[4], bnc.fmt_ann(ssp_q2))
        bdu.set_cell(cells[7], bnc.fmt_ann(ssp_h1))

        sail_q1 = (bnc.period_sum(cur, "act", Q1_CUR, "SAIL", "Finished Steel") or 0) + (bnc.conv_sum(cur, Q1_CUR) or 0)
        sail_q2 = (bnc.period_sum(cur, "act", Q2_CUR, "SAIL", "Finished Steel") or 0) + (bnc.conv_sum(cur, Q2_CUR) or 0)
        sail_h1 = (bnc.period_sum(cur, "act", H1_CUR, "SAIL", "Finished Steel") or 0) + (bnc.conv_sum(cur, H1_CUR) or 0)
        cells = t0.rows[MOU_ROW_SAIL].cells
        bdu.set_cell(cells[2], bnc.fmt_ann(sail_q1))
        bdu.set_cell(cells[4], bnc.fmt_ann(sail_q2))
        bdu.set_cell(cells[7], bnc.fmt_ann(sail_h1))

        # ================================================================
        # Paragraph text
        # ================================================================

        # -- opening Finished-Steel-vs-MoU narrative ---------------------
        _, _, fs_q2_act, _, fs_q2_cply, _ = bnc.row_values(cur, "SAIL", "Finished Steel", Q2_CUR, Q2_CPLY,
                                                             fy_start, add_conv=True)
        _, _, fs_h1_act, _, fs_h1_cply, _ = bnc.row_values(cur, "SAIL", "Finished Steel", H1_CUR, H1_CPLY,
                                                             fy_start, add_conv=True)
        fs_q2_mt = None if fs_q2_act is None else fs_q2_act / 1000.0
        fs_h1_mt = None if fs_h1_act is None else fs_h1_act / 1000.0
        fs_q2_pct = round(fs_q2_mt / _FS_Q2_MOU * 100) if fs_q2_mt is not None else None
        fs_h1_pct = round(fs_h1_mt / _FS_H1_MOU * 100) if fs_h1_mt is not None else None
        fs_q2_gr = (round((fs_q2_act - fs_q2_cply) / fs_q2_cply * 100, 1)
                    if fs_q2_act is not None and fs_q2_cply else None)
        fs_h1_gr = (round((fs_h1_act - fs_h1_cply) / fs_h1_cply * 100, 1)
                    if fs_h1_act is not None and fs_h1_cply else None)
        bdu.set_para(
            para(P_FS_Q2_NARRATIVE),
            f"The Production of Finished Steel during Q-2’{yy} was {bnc.fmt_mt(fs_q2_act)} MT "
            f"({bnc.fmt_pct(fs_q2_pct)}% of the quarterly MoU of {_FS_Q2_MOU} MT) with a growth of "
            f"{bnc.fmt_pct(fs_q2_gr)}% over CPLY."
        )
        bdu.set_para(
            para(P_FS_H1_NARRATIVE),
            f"The Production of Finished Steel during April-September’{yy} was {bnc.fmt_mt(fs_h1_act)} MT "
            f"({bnc.fmt_pct(fs_h1_pct)}% of the Apr-Sep’{yy} MoU of {_FS_H1_MOU} MT), with a growth of "
            f"{bnc.fmt_pct(fs_h1_gr)}% over CPLY. "
        )

        # -- SAIL Q-2 heading + period label + summary -------------------
        bdu.set_para(para(P_SAIL_Q2_HEADING), f"SAIL: Production performance during {q2_label} ")
        bdu.set_para(para(P_SAIL_Q2_LABEL), f"{q2_label}:")
        bdu.set_para(para(P_SAIL_Q2_SUMMARY),
                     plant_summary_big(cur, "SAIL", Q2_CUR, Q2_CPLY, fy_start).replace("{P}", q2_label))

        # -- SAIL Q-2 best-ever highlights (unconditionally regenerated) -
        sail_q2_bullets = bnc.best_ever_bullets(cur, "SAIL", lambda f: bnc.quarter_months(f, 2), fy_start, "q2")
        sail_q2_bullets += bnm.additional_highlight_lines(manual, "SAIL")
        bdu.fill_variable_bullets([para(i) for i in HIGHLIGHTS_SLOTS[("SAIL", "q2")]], sail_q2_bullets)

        # -- SAIL H-1 heading + period label + summary --------------------
        bdu.set_para(para(P_SAIL_H1_HEADING), f"SAIL: Production performance during {h1_label} ")
        bdu.set_para(para(P_SAIL_H1_LABEL), f"{h1_label}:")
        bdu.set_para(para(P_SAIL_H1_SUMMARY),
                     plant_summary_big(cur, "SAIL", H1_CUR, H1_CPLY, fy_start).replace("{P}", h1_label))

        # -- SAIL H-1 best-ever highlights --------------------------------
        sail_h1_bullets = bnc.best_ever_bullets(cur, "SAIL", lambda f: bnc.long_period_months(f, 2), fy_start, "h1")
        sail_h1_bullets += bnm.additional_highlight_lines(manual, "SAIL")
        bdu.fill_variable_bullets([para(i) for i in HIGHLIGHTS_SLOTS[("SAIL", "h1")]], sail_h1_bullets)

        # -- plant-wise section title --------------------------------------
        bdu.set_para(para(P_PLANT_SECTION_TITLE),
                     f"Plant wise: Production performance during {q2_label} and {h1_label} w.r.t. ABP")

        # -- per-plant heading/summary/highlights/why ----------------------
        for plant in PLANT_ORDER:
            cfg = PLANT_CONFIG[plant]
            summary_fn = _SUMMARY_FN[cfg["kind"]]

            bdu.set_para(para(cfg["label_q2"]), f"{q2_label}:")
            bdu.set_para(para(cfg["summary_q2"]),
                         summary_fn(cur, plant, Q2_CUR, Q2_CPLY, fy_start).replace("{P}", q2_label))

            bdu.set_para(para(cfg["label_h1"]), f"{h1_label}:")
            bdu.set_para(para(cfg["summary_h1"]),
                         summary_fn(cur, plant, H1_CUR, H1_CPLY, fy_start).replace("{P}", h1_label))

            # Highlights (Q-2 and H-1), only where the template has a slot range for this plant/period.
            for period, months_fn, style in (("q2", lambda f: bnc.quarter_months(f, 2), "q2"),
                                              ("h1", lambda f: bnc.long_period_months(f, 2), "h1")):
                slots_idx = HIGHLIGHTS_SLOTS.get((plant, period))
                if not slots_idx:
                    continue
                bullets = bnc.best_ever_bullets(cur, plant, months_fn, fy_start, style)
                bullets += bnm.additional_highlight_lines(manual, plant)
                bdu.fill_variable_bullets([para(i) for i in slots_idx], bullets)

            # Why production fell short (Q-2 only; no unit has an H-1 block).
            why_heading_idx = WHY_HEADING.get(plant)
            if why_heading_idx is not None:
                bdu.set_para(para(why_heading_idx), f"Production Performance during {q2_label}:")
            why_slots_idx = WHY_SLOTS.get(plant)
            if why_slots_idx:
                placeholder = f"[Add production narrative for {plant} here]"
                lines = bnm.why_narrative_lines(manual, plant, placeholder)
                bdu.fill_variable_bullets([para(i) for i in why_slots_idx], lines)

        # ================================================================
        # Techno-economic section
        # ================================================================
        periods = [
            {"label": "Q2cur", "months": Q2_CUR}, {"label": "Q2cply", "months": Q2_CPLY},
            {"label": "H1cur", "months": H1_CUR}, {"label": "H1cply", "months": H1_CPLY},
        ]
        techno_res = tp.build_period_report(TECHNO_PLANTS, TECHNO_PARAMS, periods)
        techno_by_param = {s["parameter"]: s for s in techno_res["sections"]}

        report_month = H1_CUR[-1]   # last month of H-1 (September of fy_start)
        targets = {}
        for plant in ["BSP", "DSP", "RSP", "BSL", "ISP"]:
            raw = pt._get_plant_techno_plan_targets(plant, report_month)
            targets[plant] = {k[1]: v for k, v in raw.items()}
        sail_targets_raw = pt.compute_sail_targets(fy)
        targets["SAIL"] = {k[1]: v for k, v in sail_targets_raw.items()}
        for plant in list(targets):
            targets[plant] = bnc.fuel_rate_fallback(targets[plant])

        t19 = tables[TABLE_TECHNO]
        bdu.set_cell(t19.rows[0].cells[3], q2_label)
        bdu.set_cell(t19.rows[1].cells[3], q2_label)
        bdu.set_cell(t19.rows[0].cells[4], q2_cply_label)
        bdu.set_cell(t19.rows[1].cells[4], q2_cply_label)
        bdu.set_cell(t19.rows[0].cells[5], h1_label)
        bdu.set_cell(t19.rows[1].cells[5], h1_label)
        bdu.set_cell(t19.rows[0].cells[6], h1_cply_label)
        bdu.set_cell(t19.rows[1].cells[6], h1_cply_label)
        zz = str(fy_start + 1)[2:]
        bdu.set_cell(t19.rows[0].cells[2], f"Target\n{yy}-{zz}")
        bdu.set_cell(t19.rows[1].cells[2], f"{yy}-{zz}")

        ri = 2
        for param in TECHNO_PARAMS:
            sec = techno_by_param[param]
            row_by_plant = {r["plant"]: r["values"] for r in sec["rows"]}
            for plant in TECHNO_PLANTS:
                cells = t19.rows[ri].cells
                vals = row_by_plant.get(plant, {})

                def disp(label):
                    d = vals.get(label)
                    return d["display"] if d else ""

                tgt = fmt_techno_target(param, (targets.get(plant) or {}).get(param))
                if tgt is not None:
                    bdu.set_cell(cells[2], tgt)
                bdu.set_cell(cells[3], disp("Q2cur"))
                bdu.set_cell(cells[4], disp("Q2cply"))
                bdu.set_cell(cells[5], disp("H1cur"))
                bdu.set_cell(cells[6], disp("H1cply"))
                ri += 1

        # -- techno section title + improvement commentary -----------------
        bdu.set_para(
            para(P_TECHNO_SECTION_TITLE),
            f"SAIL and Plant-wise Major Techno-economic parameters performance during {q2_label} and {h1_label}:"
        )
        bdu.set_para(para(P_TECHNO_PERF_HEADING), f"Techno-economic Performance during {h1_label}")

        coke_imp = techno_improvement(techno_by_param, "Coke Rate")
        cdi_imp = techno_improvement(techno_by_param, "CDI Rate")
        fuel_imp = techno_improvement(techno_by_param, "Fuel Rate")
        bfp_imp = techno_improvement(techno_by_param, "BF Productivity", higher_is_better=True)

        bdu.set_para(para(P_TECHNO_COKE), f"Coke Rate: SAIL registered {bnc.imp_phrase(coke_imp)} w.r.t. CPLY.")
        bdu.set_para(para(P_TECHNO_CDI), f"CDI Rate: SAIL registered {bnc.imp_phrase(cdi_imp)} w.r.t. CPLY.")
        bdu.set_para(para(P_TECHNO_FUEL), f"Fuel Rate: SAIL registered {bnc.imp_phrase(fuel_imp)} w.r.t. CPLY.")
        bdu.set_para(para(P_TECHNO_BFP), f"BF Productivity: SAIL registered {bnc.imp_phrase(bfp_imp)} w.r.t. CPLY.")

        buf = io.BytesIO()
        doc.save(buf)
        return buf.getvalue()
    finally:
        conn.close()
