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
  - Finished Steel MoU (table 0's MoU cells and the opening narrative)
    comes from mou_plan_table when it has the whole FY (bnc.fs_mou). Without
    it the template's own MoU cells and `_FS_Q2_MOU`/`_FS_H1_MOU` below are
    used; those are FY2025-26 figures carried over from the one-off script.
  - The techno section's "This was achieved through..." bullets (P337-340)
    are left as template static text, same as the one-off script -- they
    are not period-parameterized here. (The title P3 and the "SAIL and
    Plant-wise Production performance during..." intro P18/P19 WERE left
    static in the first pass but are now regenerated -- see
    _title_text()/_intro_q2_text()/_intro_h1_text() below.)
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

import calendar
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

# -- Title / opening intro (P3, P18/P19) -- regenerated every call ----------
P_TITLE = 3   # "PRODUCTION PERFORMANCE DURING QUARTER-2'26-27 (JULY'26, AUGUST'26, SEPTEMBER'26 and APRIL-SEPTEMBER'26) "
P_INTRO_Q2 = 18   # "SAIL and Plant-wise Production performance during Q-2'26-27 and "
P_INTRO_H1 = 19   # "H-1'26-27 (Apr-Sep'26) w.r.t. ABP"

# -- Opening "SAIL: Production performance for Finished Steel w.r.t. MoU" --
P_FS_Q2_NARRATIVE = 9    # "The Production of Finished Steel during Q-2'26 was ..."
P_FS_H1_NARRATIVE = 11   # "The Production of Finished Steel during April-September'26 was ..."
TABLE_MOU = 0            # "Plant | MoU 2026-27 | Q-1'26-27 | Q-2'26-27 (ABP/Act/%Ful) | Apr-Sep'26 (ABP/Act/%Ful)"
MOU_ROW_PLANT = {2: "BSP", 3: "DSP", 4: "RSP", 5: "BSL", 6: "ISP"}
MOU_ROW_SPECIAL_STEEL = 7   # "Special Steel Plants" (ASP+SSP+VISL total)
MOU_ROW_SAIL = 8            # "SAIL" (5 plants + special steel + Conversion)
# Table 0's MoU columns (cells 1 annual, 3 Q-2, 6 H-1) come from
# mou_plan_table when it has the FY; otherwise the template's static cells
# are kept. %Ful (cells 5 and 8) is derived from whatever MoU cells end up
# there.

# -- Annexure index (table 20) -- titles only, no actual annexure content ---
TABLE_ANNEXURE_INDEX = 20
# row -> cell[3] text template; "ANNEX_MONTHS" is replaced with the 3 Q-2
# month names, everything else with quarter_label/long_period_label.
# "1. Annexure-Ia : SAIL: Production performance during July'25, August'25 and September'25."
# "1. Annexure-Ib : SAIL: Production performance during Q-2'25-26 and H-1'25-26"
# "2. Annexure-II : SAIL: Techno-economic parameters during Q-2'25-26 and H-1'25-26, best ever achieved, norms and benchmarks"
# "3. Annexure-III : SAIL: Production performance :New Facilities during \nQ-2'25-26 and H-1'25-26"
# "4. Annexure-IV : SAIL: Techno-economic parameters for New Blast Furnaces during Q-2'25-26 and H-1'25-26"
# "5. Annexure-V : SAIL: Product mix performance during Q-2'25-26 and H-1'25-26"

# Fallback only, when mou_plan_table lacks the FY -- see module docstring.
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

    # "Highlights:" (P177) / "BSL achieved best ever Quarter production for following:" (P178, kept,
    # rewritten to say "Q-2" -- see LEADIN_TEXT_FIX). P181 is a SECOND lead-in sentence (Normal style,
    # "BSL achieved best ever Q-2 production for following:"), not a bullet -- excluded from slots and
    # removed outright (see SECOND_LEADIN_REMOVE) rather than treated as List-Paragraph bullet content.
    ("BSL", "q2"): [179, 180, 182, 183, 184, 185],
    # "Highlights:" (P219) / "BSL achieved best ever half yearly production for following:" (P220, kept,
    # rewritten to say "H-1"). P224 is a second lead-in sentence, excluded/removed (see SECOND_LEADIN_REMOVE).
    ("BSL", "h1"): [221, 222, 223, 225, 226, 227, 228],

    # "Highlights:" (P237) / "ISP achieved best ever Quarter production for following:" (P239, kept,
    # rewritten to say "Q-2"). P244 is a second lead-in sentence, excluded/removed (see SECOND_LEADIN_REMOVE).
    ("ISP", "q2"): [240, 241, 242, 245, 246, 247, 248],
    # "Highlights:" (P268) / "ISP achieved best ever Half-yearly production for following:" (P269, kept,
    # rewritten to say "H-1"). P277 is a second lead-in sentence, excluded/removed (see SECOND_LEADIN_REMOVE).
    ("ISP", "h1"): [270, 271, 272, 273, 274, 275, 278, 279],

    # ASP/SSP/VISL: no entries -- no "Highlights:" section exists for them in this template.
}

# Second ("...for following:") lead-in sentences that sit in the middle of a
# unit's bullet block (Normal style, not List Paragraph) -- these are not
# genuine bullet slots (fixing Important-4-class review finding) and, now
# that the FIRST lead-in is rewritten to the correct narrower claim (see
# LEADIN_TEXT_FIX), restating the same claim a second time is redundant, so
# they are removed outright rather than overwritten as a bullet.
SECOND_LEADIN_REMOVE = {
    ("BSL", "q2"): 181,   # "BSL achieved best ever Q-2 production for following:"
    ("BSL", "h1"): 224,   # "BSL achieved best ever H-1 production for following:"
    ("ISP", "q2"): 244,   # "ISP achieved best ever Q-2 production for following:"
    ("ISP", "h1"): 277,   # "ISP achieved best ever H-1 production for following:" (same class of bug as
                           # the 3 the review named explicitly; found during the general sweep and fixed too)
}

# First lead-in sentences whose wording overclaims relative to what
# best_ever_bullets actually checks (BSL/ISP said "best ever Quarter"/
# "half yearly" -- an all-time-across-any-quarter claim -- but the bullets
# underneath are Q-2-vs-Q-2-only / H-1-vs-H-1-only). Rewritten to match the
# narrower claim, same wording pattern every other unit's lead-in uses.
LEADIN_TEXT_FIX = {
    ("BSL", "q2"): (178, "BSL achieved best ever Q-2 production for following:"),
    ("BSL", "h1"): (220, "BSL achieved best ever H-1 production for following:"),
    ("ISP", "q2"): (239, "ISP achieved best ever Q-2 production for following:"),
    ("ISP", "h1"): (269, "ISP achieved best ever H-1 production for following:"),
}

# "Highlights:" heading + first lead-in paragraph for every (unit, period)
# that has a highlights slot range -- removed together when the final
# bullet list for that unit/period turns out empty, so no dangling heading
# with nothing under it is left in the document.
HIGHLIGHTS_HEADING = {
    ("SAIL", "q2"): P_SAIL_Q2_HIGHLIGHTS_HEADING, ("SAIL", "h1"): P_SAIL_H1_HIGHLIGHTS_HEADING,
    ("BSP", "q2"): 56, ("BSP", "h1"): 77,
    ("DSP", "q2"): 102, ("DSP", "h1"): 121,
    ("RSP", "q2"): 134, ("RSP", "h1"): 164,
    ("BSL", "q2"): 177, ("BSL", "h1"): 219,
    ("ISP", "q2"): 237, ("ISP", "h1"): 268,
}
HIGHLIGHTS_LEADIN = {
    ("SAIL", "q2"): P_SAIL_Q2_HIGHLIGHTS_LEADIN, ("SAIL", "h1"): P_SAIL_H1_HIGHLIGHTS_LEADIN,
    ("BSP", "q2"): 57, ("BSP", "h1"): 78,
    ("DSP", "q2"): None, ("DSP", "h1"): None,   # no lead-in sentence in the template for DSP
    ("RSP", "q2"): None, ("RSP", "h1"): 165,     # no lead-in sentence in the template for RSP Q-2
    ("BSL", "q2"): 178, ("BSL", "h1"): 220,
    ("ISP", "q2"): 239, ("ISP", "h1"): 269,
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

def _nl(label: str) -> str:
    """Insert a newline right after the quote mark, matching the
    "Q-2'\\n25-26" style used for the CPLY half of every table header."""
    return label.replace("’", "’\n")


def _cply_label_nl(label_fn, fy_start, quarter):
    """A prior-year period label with the _nl() newline treatment."""
    return _nl(label_fn(fy_start - 1, quarter))


def _month_name(month_str: str) -> str:
    """'2026-07' -> 'JULY' (all-caps, for the all-caps title)."""
    _, m = month_str.split("-")
    return calendar.month_name[int(m)].upper()


def _month_name_title(month_str: str) -> str:
    """'2026-07' -> 'July' (title case, for sentence-style prose)."""
    _, m = month_str.split("-")
    return calendar.month_name[int(m)]


def _title_text(fy_start):
    yy = str(fy_start)[2:]
    zz = str(fy_start + 1)[2:]
    m1, m2, m3 = (_month_name(m) for m in bnc.quarter_months(fy_start, 2))
    return (f"PRODUCTION PERFORMANCE DURING QUARTER-2’{yy}-{zz} "
            f"({m1}’{yy}, {m2}’{yy}, {m3}’{yy} and APRIL-SEPTEMBER’{yy}) ")


def _intro_q2_text(q2_label):
    return f"SAIL and Plant-wise Production performance during {q2_label} and "


def _intro_h1_text(h1_label, fy_start):
    yy = str(fy_start)[2:]
    return f"{h1_label} (Apr-Sep’{yy}) w.r.t. ABP"


def _parse_num(text):
    text = (text or "").strip().replace(",", "")
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def set_mou_table_header(table, fy_start):
    """Table 0's header: col1 is the annual-MoU column label, col2 the
    single Q-1 actual column, cols 3-5 the Q-2 MoU/Actual/%Ful trio's
    merged label, cols 6-8 the Apr-Sep (H-1) trio's merged label -- note
    table 0 uses "Apr-Sep'YY", not the "H-1'YY-ZZ" label used elsewhere."""
    yy = str(fy_start)[2:]
    zz = str(fy_start + 1)[2:]
    mou_col = f"MoU \n{fy_start}-{zz}"
    q1_col = _nl(bnc.quarter_label(fy_start, 1))
    q2_col = bnc.quarter_label(fy_start, 2)
    h1_col = f"Apr-Sep’{yy}"
    row0, row1 = table.rows[0].cells, table.rows[1].cells
    for row in (row0, row1):
        bdu.set_cell(row[1], mou_col)
        bdu.set_cell(row[2], q1_col)
    for c in (3, 4, 5):
        bdu.set_cell(row0[c], q2_col)
    for c in (6, 7, 8):
        bdu.set_cell(row0[c], h1_col)


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

        def apply_highlights(plant, period, bullets):
            """Fill a unit's highlights bullet slots (fixing the lead-in
            wording / dropping a bogus second lead-in paragraph where the
            review flagged them), then remove the "Highlights:" heading
            and lead-in sentence outright if the final bullet list is
            empty, so no dangling heading is left with nothing under it.
            No-ops for units with no highlights section (ASP/SSP/VISL)."""
            slots_idx = HIGHLIGHTS_SLOTS.get((plant, period))
            if not slots_idx:
                return
            fix = LEADIN_TEXT_FIX.get((plant, period))
            if fix:
                idx, text = fix
                bdu.set_para(para(idx), text)
            second_leadin_idx = SECOND_LEADIN_REMOVE.get((plant, period))
            if second_leadin_idx is not None:
                bdu.remove_paragraph(para(second_leadin_idx))
            bdu.fill_variable_bullets([para(i) for i in slots_idx], bullets)
            if not bullets:
                heading_idx = HIGHLIGHTS_HEADING.get((plant, period))
                leadin_idx = HIGHLIGHTS_LEADIN.get((plant, period))
                if heading_idx is not None:
                    bdu.remove_paragraph(para(heading_idx))
                if leadin_idx is not None:
                    bdu.remove_paragraph(para(leadin_idx))

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

        # ---- table 0: Finished Steel vs MoU -----------------------------
        t0 = tables[TABLE_MOU]
        set_mou_table_header(t0, fy_start)

        FY_CUR = bnc.fy_months(fy_start)
        mou_in_db = bnc.fs_mou(cur, FY_CUR, bnc.SAIL_MOU_PLANTS) is not None

        def _fill_mou_row(ridx, q1, q2, h1, plants):
            """Fill Q-1/Q-2/H-1 Actual cells (2/4/7) and derive %Ful (5/8)
            from the Q-2/H-1 MoU cells (3/6): from the DB when it has the
            FY's MoU, else the template's static cells -- never guess a %Ful
            when the MoU cell is blank/unparseable."""
            cells = t0.rows[ridx].cells
            if mou_in_db:
                for c, months in ((1, FY_CUR), (3, Q2_CUR), (6, H1_CUR)):
                    bdu.set_cell(cells[c], bnc.fmt_ann(bnc.fs_mou(cur, months, plants)))
            bdu.set_cell(cells[2], bnc.fmt_ann(q1))
            bdu.set_cell(cells[4], bnc.fmt_ann(q2))
            bdu.set_cell(cells[7], bnc.fmt_ann(h1))
            q2_mou = _parse_num(cells[3].text)
            h1_mou = _parse_num(cells[6].text)
            bdu.set_cell(cells[5], str(round(q2 / q2_mou * 100)) if (q2 is not None and q2_mou) else "")
            bdu.set_cell(cells[8], str(round(h1 / h1_mou * 100)) if (h1 is not None and h1_mou) else "")

        for ridx, plant in MOU_ROW_PLANT.items():
            q1 = bnc.period_sum(cur, "act", Q1_CUR, plant, "Finished Steel")
            q2 = bnc.period_sum(cur, "act", Q2_CUR, plant, "Finished Steel")
            h1 = bnc.period_sum(cur, "act", H1_CUR, plant, "Finished Steel")
            _fill_mou_row(ridx, q1, q2, h1, [plant])

        def special_steel_total(months):
            total, found = 0.0, False
            for p in SPECIAL_STEEL_PLANTS:
                v = bnc.period_sum(cur, "act", months, p, "Finished Steel")
                if v is not None:
                    total += v
                    found = True
            return total if found else None

        ssp_q1, ssp_q2, ssp_h1 = special_steel_total(Q1_CUR), special_steel_total(Q2_CUR), special_steel_total(H1_CUR)
        _fill_mou_row(MOU_ROW_SPECIAL_STEEL, ssp_q1, ssp_q2, ssp_h1, SPECIAL_STEEL_PLANTS)

        def _sail_finished_with_conv(months):
            """None-propagating SAIL Finished-Steel-plus-Conversion total --
            matches row_values' own add_conv logic for this exact quantity;
            never silently treats a missing figure as 0."""
            act = bnc.period_sum(cur, "act", months, "SAIL", "Finished Steel")
            if act is None:
                return None
            cv = bnc.conv_sum(cur, months)
            return act + cv if cv is not None else None

        sail_q1 = _sail_finished_with_conv(Q1_CUR)
        sail_q2 = _sail_finished_with_conv(Q2_CUR)
        sail_h1 = _sail_finished_with_conv(H1_CUR)
        _fill_mou_row(MOU_ROW_SAIL, sail_q1, sail_q2, sail_h1, bnc.SAIL_MOU_PLANTS)
        if mou_in_db:
            # The template marks its stale MoU figures in red strike-through.
            for row in t0.rows:
                for cell in row.cells:
                    bdu.clear_strike_and_colour(cell)

        # ---- Annexure index (table 20) -- titles only -------------------
        t20 = tables[TABLE_ANNEXURE_INDEX]
        m1, m2, m3 = (_month_name_title(m) for m in Q2_CUR)
        bdu.set_cell(t20.rows[0].cells[3],
                     f"SAIL: Production performance during {m1}’{yy}, {m2}’{yy} and {m3}’{yy}.")
        bdu.set_cell(t20.rows[1].cells[3],
                     f"SAIL: Production performance during {q2_label} and {h1_label}")
        bdu.set_cell(t20.rows[2].cells[3],
                     f"SAIL: Techno-economic parameters during {q2_label} and {h1_label}, best ever achieved, "
                     f"norms and benchmarks")
        bdu.set_cell(t20.rows[3].cells[3],
                     f"SAIL: Production performance :New Facilities during \n{q2_label} and {h1_label}")
        bdu.set_cell(t20.rows[4].cells[3],
                     f"SAIL: Techno-economic parameters for New Blast Furnaces during {q2_label} and {h1_label}")
        bdu.set_cell(t20.rows[5].cells[3],
                     f"SAIL: Product mix performance during {q2_label} and {h1_label}")

        # ================================================================
        # Paragraph text
        # ================================================================

        # -- title + opening intro (P3, P18/P19) --------------------------
        bdu.set_para(para(P_TITLE), _title_text(fy_start))
        bdu.set_para(para(P_INTRO_Q2), _intro_q2_text(q2_label))
        bdu.set_para(para(P_INTRO_H1), _intro_h1_text(h1_label, fy_start))

        # -- opening Finished-Steel-vs-MoU narrative ---------------------
        _, _, fs_q2_act, _, fs_q2_cply, _ = bnc.row_values(cur, "SAIL", "Finished Steel", Q2_CUR, Q2_CPLY,
                                                             fy_start, add_conv=True)
        _, _, fs_h1_act, _, fs_h1_cply, _ = bnc.row_values(cur, "SAIL", "Finished Steel", H1_CUR, H1_CPLY,
                                                             fy_start, add_conv=True)
        if mou_in_db:
            fs_q2_mou = bnc.fs_mou(cur, Q2_CUR, bnc.SAIL_MOU_PLANTS)
            fs_h1_mou = bnc.fs_mou(cur, H1_CUR, bnc.SAIL_MOU_PLANTS)
        else:
            fs_q2_mou, fs_h1_mou = _FS_Q2_MOU * 1000, _FS_H1_MOU * 1000
        fs_q2_gr = (round((fs_q2_act - fs_q2_cply) / fs_q2_cply * 100, 1)
                    if fs_q2_act is not None and fs_q2_cply else None)
        fs_h1_gr = (round((fs_h1_act - fs_h1_cply) / fs_h1_cply * 100, 1)
                    if fs_h1_act is not None and fs_h1_cply else None)
        bdu.set_para(
            para(P_FS_Q2_NARRATIVE),
            f"The Production of Finished Steel during Q-2’{yy} was {bnc.fmt_mt(fs_q2_act)} MT"
            f"{bnc.mou_clause(fs_q2_act, fs_q2_mou, 'quarterly')} with a growth of "
            f"{bnc.fmt_pct(fs_q2_gr)}% over CPLY."
        )
        bdu.set_para(
            para(P_FS_H1_NARRATIVE),
            f"The Production of Finished Steel during April-September’{yy} was {bnc.fmt_mt(fs_h1_act)} MT"
            f"{bnc.mou_clause(fs_h1_act, fs_h1_mou, f'Apr-Sep’{yy}')}, with a growth of "
            f"{bnc.fmt_pct(fs_h1_gr)}% over CPLY. "
        )
        charts = bdu.fs_charts(doc)
        if "quarter" in charts:
            bdu.fill_fs_chart(charts["quarter"], f"Q-2'{yy}-{str(fy_start + 1)[2:]}",
                              fs_q2_mou, fs_q2_act, fs_q2_cply)
        if "long" in charts:
            bdu.fill_fs_chart(charts["long"], f"Apr-Sep'{yy}", fs_h1_mou, fs_h1_act, fs_h1_cply)

        # -- SAIL Q-2 heading + period label + summary -------------------
        bdu.set_para(para(P_SAIL_Q2_HEADING), f"SAIL: Production performance during {q2_label} ")
        bdu.set_para(para(P_SAIL_Q2_LABEL), f"{q2_label}:")
        bdu.set_para(para(P_SAIL_Q2_SUMMARY),
                     plant_summary_big(cur, "SAIL", Q2_CUR, Q2_CPLY, fy_start).replace("{P}", q2_label))

        # -- SAIL Q-2 best-ever highlights (unconditionally regenerated) -
        # Manual additional-highlights text is keyed once per plant for the
        # whole note (not split by sub-period), so it is appended to the
        # Q-2 block only -- appending it to H-1 too would duplicate it.
        sail_q2_bullets = bnc.best_ever_bullets(cur, "SAIL", lambda f: bnc.quarter_months(f, 2), fy_start, "q2")
        sail_q2_bullets += bnm.additional_highlight_lines(manual, "SAIL")
        apply_highlights("SAIL", "q2", sail_q2_bullets)

        # -- SAIL H-1 heading + period label + summary --------------------
        bdu.set_para(para(P_SAIL_H1_HEADING), f"SAIL: Production performance during {h1_label} ")
        bdu.set_para(para(P_SAIL_H1_LABEL), f"{h1_label}:")
        bdu.set_para(para(P_SAIL_H1_SUMMARY),
                     plant_summary_big(cur, "SAIL", H1_CUR, H1_CPLY, fy_start).replace("{P}", h1_label))

        # -- SAIL H-1 best-ever highlights (no manual-text append -- Q-2 only) --
        sail_h1_bullets = bnc.best_ever_bullets(cur, "SAIL", lambda f: bnc.long_period_months(f, 2), fy_start, "h1")
        apply_highlights("SAIL", "h1", sail_h1_bullets)

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

            # Highlights (Q-2 and H-1); apply_highlights no-ops for units with no
            # slot range (ASP/SSP/VISL). Manual additional-highlights text is
            # appended to the Q-2 block only -- see note above SAIL's Q-2 call.
            for period, months_fn, style in (("q2", lambda f: bnc.quarter_months(f, 2), "q2"),
                                              ("h1", lambda f: bnc.long_period_months(f, 2), "h1")):
                bullets = bnc.best_ever_bullets(cur, plant, months_fn, fy_start, style)
                if period == "q2":
                    bullets += bnm.additional_highlight_lines(manual, plant)
                apply_highlights(plant, period, bullets)

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
                bdu.set_cell(cells[2], tgt if tgt is not None else "")
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
