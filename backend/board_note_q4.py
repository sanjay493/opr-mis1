"""Q-4 + FY Board Note docx generator.

Fills `board_note_templates/board_note_q4_template.docx` (a verbatim copy of
`Report_format/BN_ Production Q-4 and FY'25-26.docx`) for any financial year,
using the same technique and shared helpers as `board_note_q2.py`.

Q-4 differs from the other quarters: its plant tables carry only the Q-1
item rows (three for the big five, two for ASP/SSP, one for VISL), each unit
has a full-year (FY) highlights block after its Q-4 block, and the techno
section has no improvement commentary (its FY25-26 "annual best" lines are
removed rather than shipped stale).

MoU: as in Q-3, the MoU table's MoU and %Ful cells and the "% of MoU" clause
are blank for every FY, because MoU targets are not in the DB. Actuals are
always filled from the DB.

Known limitations (documented, not bugs):
  - DSP, RSP and BSP have no Q-4 "Highlights:" block in this template
    (their best-ever bullets are only generated for the FY block, where the
    template has one). BSP, RSP, VISL have no FY-block-only limitation; ASP
    and SSP have FY highlights only.
  - The BSL paragraph "In FY 2025-26, the planned blowing down of BF-5..."
    is an FY25-26 note and is removed rather than shipped stale.
"""

import io

import docx

import board_note_common as bnc
import board_note_docx_utils as bdu
import board_note_manual_text as bnm
import board_note_q2 as bq2
import db
import page_techno as pt
import techno_period as tp

TEMPLATE_PATH = "board_note_templates/board_note_q4_template.docx"

# -- Title / opening (P3, P7, P9, P11, P16) ----------------------------------
P_TITLE = 3
P_MOU_HEADING = 7            # "SAIL: Production performance for Finished Steel w.r.t. MoU "
P_FS_Q4_NARRATIVE = 9
P_FS_FY_NARRATIVE = 11
P_CONVERSION_NOTE = 16       # "SAIL figures include finished steel produced through conversion agents/WLA/JVC" (static)
TABLE_MOU = 0                # Plant | Q-4 MoU | Q-4 Actual | %Ful | FY MoU | FY Actual | %Ful
MOU_ROW_PLANT = {2: "BSP", 3: "DSP", 4: "RSP", 5: "BSL", 6: "ISP"}
MOU_ROW_SPECIAL_STEEL = 7
MOU_ROW_SAIL = 8

# -- Intro -------------------------------------------------------------------
P_INTRO_Q4 = 20              # "SAIL and Plant-wise Production performance during Q-4’25-26 and "
P_INTRO_FY = 21              # "FY’25-26 (Apr-Mar’26) w.r.t. ABP"
P_PLANT_SECTION_TITLE = 47

# -- SAIL --------------------------------------------------------------------
TABLE_SAIL_Q4 = 1
TABLE_SAIL_FY = 2
P_SAIL_Q4_HEADING = 23
P_SAIL_Q4_LABEL = 25
P_SAIL_Q4_SUMMARY = 26
P_SAIL_FY_HEADING = 34
P_SAIL_FY_LABEL = 36
P_SAIL_FY_SUMMARY = 37

# -- Techno and annexure -----------------------------------------------------
P_TECHNO_SECTION_TITLE = 296
TABLE_TECHNO = 19            # Parameters | Plant | Target | Q-4cur | Q-4cply | FYcur | FYcply
TECHNO_STALE_REMOVE = [300, 301, 302, 303]   # "SAIL registered Annual Best..." FY25-26 values
TABLE_ANNEXURE_INDEX = 20

TECHNO_PLANTS = ["BSP", "DSP", "RSP", "BSL", "ISP", "SAIL"]
TECHNO_PARAMS = ["Coke Rate", "CDI Rate", "Fuel Rate", "BF Productivity"]

BIG5_Q1_ITEMS = [
    (2, "Hot Metal", "Hot Metal", False),
    (3, "Crude Steel", "Total Crude Steel", False),
    (4, "Saleable Steel", "Saleable Steel", False),
]
SAIL_ITEMS = bq2.SAIL_ITEMS
SPECIAL2_ITEMS = bq2.SPECIAL2_ITEMS[:2]          # Crude Steel, Saleable Steel only
VISL_ITEMS = bq2.VISL_ITEMS[:1]                  # Saleable Steel only
SPECIAL_STEEL_PLANTS = ["ASP", "SSP", "VISL"]

# -- Per-plant index map -----------------------------------------------------
PLANT_CONFIG = {
    "BSP": dict(table_q4=3, table_fy=4, label_q4=51, summary_q4=52, label_fy=71, summary_fy=72,
                item_rows=BIG5_Q1_ITEMS, kind="big"),
    "DSP": dict(table_q4=5, table_fy=6, label_q4=89, summary_q4=90, label_fy=110, summary_fy=111,
                item_rows=BIG5_Q1_ITEMS, kind="big"),
    "RSP": dict(table_q4=7, table_fy=8, label_q4=122, summary_q4=123, label_fy=137, summary_fy=138,
                item_rows=BIG5_Q1_ITEMS, kind="big"),
    "BSL": dict(table_q4=9, table_fy=10, label_q4=153, summary_q4=154, label_fy=179, summary_fy=180,
                item_rows=BIG5_Q1_ITEMS, kind="big"),
    "ISP": dict(table_q4=11, table_fy=12, label_q4=198, summary_q4=199, label_fy=219, summary_fy=220,
                item_rows=BIG5_Q1_ITEMS, kind="big"),
    "ASP": dict(table_q4=13, table_fy=14, label_q4=235, summary_q4=236, label_fy=247, summary_fy=248,
                item_rows=SPECIAL2_ITEMS, kind="small"),
    "SSP": dict(table_q4=15, table_fy=16, label_q4=258, summary_q4=259, label_fy=269, summary_fy=270,
                item_rows=SPECIAL2_ITEMS, kind="small"),
    "VISL": dict(table_q4=17, table_fy=18, label_q4=280, summary_q4=282, label_fy=289, summary_fy=291,
                 item_rows=VISL_ITEMS, kind="visl"),
}
PLANT_ORDER = ["BSP", "DSP", "RSP", "BSL", "ISP", "ASP", "SSP", "VISL"]

# -- Highlights bullet slots -------------------------------------------------
HIGHLIGHTS_SLOTS = {
    ("SAIL", "q4"): [31, 32],
    ("SAIL", "fy"): [42, 43, 44],
    ("DSP", "q4"): [94, 95],
    ("DSP", "fy"): [116, 117, 118],
    ("BSP", "fy"): [77, 78, 79, 80, 81, 82, 83, 84, 85],
    ("RSP", "fy"): [144, 145, 146, 147, 148, 149],
    ("BSL", "q4"): [159, 160, 161, 162, 163, 164, 165, 168],
    ("BSL", "fy"): [188, 189, 190, 191, 192, 193, 194, 195],
    ("ISP", "q4"): [204, 205, 206],
    ("ISP", "fy"): [225, 226, 227, 228, 229, 230, 231],
    ("ASP", "fy"): [253, 254],
    ("SSP", "fy"): [275, 276],
}
HIGHLIGHTS_HEADING = {
    ("SAIL", "q4"): 29, ("SAIL", "fy"): 40,
    ("DSP", "q4"): 93, ("DSP", "fy"): 114,
    ("BSP", "fy"): 75,
    ("RSP", "fy"): 142,
    ("BSL", "q4"): 157, ("BSL", "fy"): 186,
    ("ISP", "q4"): 202, ("ISP", "fy"): 223,
    ("ASP", "fy"): 251,
    ("SSP", "fy"): 273,
}
HIGHLIGHTS_LEADIN = {
    ("SAIL", "q4"): 30, ("SAIL", "fy"): 41,
    ("DSP", "q4"): None, ("DSP", "fy"): 115,
    ("BSP", "fy"): 76,
    ("RSP", "fy"): 143,
    ("BSL", "q4"): 158, ("BSL", "fy"): 187,
    ("ISP", "q4"): 203, ("ISP", "fy"): 224,
    ("ASP", "fy"): 252,
    ("SSP", "fy"): 274,
}
# Lead-ins rewritten to the narrower claim best_ever_bullets checks.
LEADIN_TEXT_FIX = {
    ("SAIL", "q4"): (30, "SAIL achieved best ever Q-4 production for following:"),
    ("BSL", "q4"): (158, "BSL achieved best ever Q-4 production for following:"),
    ("ISP", "q4"): (203, "ISP achieved best ever Q-4 production for following:"),
    ("ASP", "fy"): (252, "ASP achieved best ever annual production for following:"),
}
# A second "...for following:" lead-in in the middle of a bullet block; removed.
SECOND_LEADIN_REMOVE = {
    ("BSL", "q4"): 167,
}
# Empty spacer paragraphs inside a highlights block; removed before filling.
HIGHLIGHTS_BLANKS_REMOVE = {
    ("BSL", "q4"): [166],
}
# An FY25-26 narrative paragraph under the BSL FY summary; removed.
STALE_PARAGRAPHS_REMOVE = [184]

# -- "Production Performance during Q-4’25-26:" why blocks (Q-4 only) --------
WHY_HEADING = {
    "BSP": 55, "DSP": 96, "RSP": 126, "BSL": 170, "ISP": 208,
    "ASP": 241, "SSP": 262, "VISL": 285,
}
WHY_SLOTS = {
    "BSP": [57, 58, 59, 61, 62, 63, 65, 66, 67, 68, 69],
    "DSP": [98, 99, 100, 101, 102, 104, 105, 107, 108],
    "RSP": [128, 129, 130, 131, 133, 135],
    "BSL": [172, 173, 174, 175, 176, 177],
    "ISP": [210, 211, 213, 214, 216, 217],
    "ASP": [243, 245],
    "SSP": [264, 265, 267],
    "VISL": [287],
}


def _title_text(fy_start):
    yy = str(fy_start)[2:]
    zz = str(fy_start + 1)[2:]
    m1, m2, m3 = (bq2._month_name(m) for m in bnc.quarter_months(fy_start, 4))
    return (f"PRODUCTION PERFORMANCE DURING QUARTER-4’{yy}-{zz} "
            f"({m1}’{zz}, {m2}’{zz}, {m3}’{zz} and APRIL-MARCH’{zz}) ")


def _set_fy_header(table, fy_label, cply_label):
    """FY tables have six columns (no separate annual-ABP column): the annual
    ABP sits under the FY label as "ABP", followed by Actual, % Ful., CPLY,
    and % Gr."""
    row0, row1 = table.rows[0].cells, table.rows[1].cells
    for c in (1, 2, 3):
        bdu.set_cell(row0[c], fy_label)
    bdu.set_cell(row1[1], "ABP")
    bdu.set_cell(row1[2], "Actual")
    bdu.set_cell(row1[3], "% Ful.")
    bdu.set_cell(row0[4], f"{cply_label}\nAct.")
    bdu.set_cell(row1[4], f"{cply_label}\nAct.")
    bdu.set_cell(row0[5], f"% Gr. w.r.t.\n{cply_label}")
    bdu.set_cell(row1[5], f"% Gr. w.r.t.\n{cply_label}")


def _fill_fy_table(cur, table, plant, item_rows, cur_months, cply_months, fy_start):
    for row_idx, _display, db_item, add_conv in item_rows:
        ann, _abp, act, pct, cply, gr = bnc.row_values(
            cur, plant, db_item, cur_months, cply_months, fy_start, add_conv=add_conv
        )
        cells = table.rows[row_idx].cells
        bdu.set_cell(cells[1], bnc.fmt_ann(ann))
        bdu.set_cell(cells[2], bnc.fmt_tbl(act, plant))
        bdu.set_cell(cells[3], bnc.fmt_pct(pct))
        bdu.set_cell(cells[4], bnc.fmt_tbl(cply, plant))
        bdu.set_cell(cells[5], bnc.fmt_pct(gr))


def _fmt_techno_target(param, v):
    if v is None:
        return None
    return f"{v:.2f}" if param == "BF Productivity" else str(round(v))


def _special_steel_total(cur, months):
    total, found = 0.0, False
    for p in SPECIAL_STEEL_PLANTS:
        v = bnc.period_sum(cur, "act", months, p, "Finished Steel")
        if v is not None:
            total += v
            found = True
    return total if found else None


def _sail_finished_with_conv(cur, months):
    act = bnc.period_sum(cur, "act", months, "SAIL", "Finished Steel")
    if act is None:
        return None
    cv = bnc.conv_sum(cur, months)
    return act + cv if cv is not None else None


def generate(fy: str) -> bytes:
    fy_start = int(fy[:4])
    yy = str(fy_start)[2:]
    zz = str(fy_start + 1)[2:]

    Q4_CUR = bnc.quarter_months(fy_start, 4)
    Q4_CPLY = bnc.quarter_months(fy_start - 1, 4)
    FY_CUR = bnc.long_period_months(fy_start, 4)
    FY_CPLY = bnc.long_period_months(fy_start - 1, 4)

    q4_label = bnc.quarter_label(fy_start, 4)
    q4_cply_label = bq2._cply_label_nl(bnc.quarter_label, fy_start, 4)
    fy_label = bnc.long_period_label(fy_start, 4)
    fy_cply_label = bq2._cply_label_nl(bnc.long_period_label, fy_start, 4)

    manual = bnm.get_manual_text(fy, 4)

    conn = db.connect()
    cur = conn.cursor()
    try:
        doc = docx.Document(TEMPLATE_PATH)
        tables = doc.tables
        paras = doc.paragraphs

        def para(i):
            return paras[i]

        def apply_highlights(plant, period, bullets):
            key = (plant, period)
            slots_idx = HIGHLIGHTS_SLOTS.get(key)
            if not slots_idx:
                return
            fix = LEADIN_TEXT_FIX.get(key)
            if fix:
                idx, text = fix
                bdu.set_para(para(idx), text)
            second = SECOND_LEADIN_REMOVE.get(key)
            if second is not None:
                bdu.remove_paragraph(para(second))
            for blank_idx in HIGHLIGHTS_BLANKS_REMOVE.get(key, []):
                bdu.remove_paragraph(para(blank_idx))
            bdu.fill_variable_bullets([para(i) for i in slots_idx], bullets)
            if not bullets:
                heading_idx = HIGHLIGHTS_HEADING.get(key)
                leadin_idx = HIGHLIGHTS_LEADIN.get(key)
                if heading_idx is not None:
                    bdu.remove_paragraph(para(heading_idx))
                if leadin_idx is not None:
                    bdu.remove_paragraph(para(leadin_idx))

        # ---- unit tables -----------------------------------------------
        bq2.set_abp_header(tables[TABLE_SAIL_Q4], fy_start)
        bq2.set_period_header(tables[TABLE_SAIL_Q4], q4_label, q4_cply_label)
        bq2.fill_period_table(cur, tables[TABLE_SAIL_Q4], "SAIL", SAIL_ITEMS, Q4_CUR, Q4_CPLY, fy_start)

        _set_fy_header(tables[TABLE_SAIL_FY], fy_label, fy_cply_label)
        _fill_fy_table(cur, tables[TABLE_SAIL_FY], "SAIL", SAIL_ITEMS, FY_CUR, FY_CPLY, fy_start)

        for plant in PLANT_ORDER:
            cfg = PLANT_CONFIG[plant]
            bq2.set_abp_header(tables[cfg["table_q4"]], fy_start)
            bq2.set_period_header(tables[cfg["table_q4"]], q4_label, q4_cply_label)
            bq2.fill_period_table(cur, tables[cfg["table_q4"]], plant, cfg["item_rows"], Q4_CUR, Q4_CPLY, fy_start)

            _set_fy_header(tables[cfg["table_fy"]], fy_label, fy_cply_label)
            _fill_fy_table(cur, tables[cfg["table_fy"]], plant, cfg["item_rows"], FY_CUR, FY_CPLY, fy_start)

        # ---- table 0: Finished Steel actuals (MoU cells blanked) ------------
        t0 = tables[TABLE_MOU]
        for c in (1, 2, 3):
            bdu.set_cell(t0.rows[0].cells[c], q4_label)
        for c in (4, 5, 6):
            bdu.set_cell(t0.rows[0].cells[c], fy_label)

        def _fill_mou_row(ridx, q4_act, fy_act):
            cells = t0.rows[ridx].cells
            for c in (1, 3, 4, 6):
                bdu.set_cell(cells[c], "")
            bdu.set_cell(cells[2], bnc.fmt_ann(q4_act))
            bdu.set_cell(cells[5], bnc.fmt_ann(fy_act))

        for ridx, plant in MOU_ROW_PLANT.items():
            _fill_mou_row(ridx,
                          bnc.period_sum(cur, "act", Q4_CUR, plant, "Finished Steel"),
                          bnc.period_sum(cur, "act", FY_CUR, plant, "Finished Steel"))
        _fill_mou_row(MOU_ROW_SPECIAL_STEEL,
                      _special_steel_total(cur, Q4_CUR), _special_steel_total(cur, FY_CUR))
        _fill_mou_row(MOU_ROW_SAIL,
                      _sail_finished_with_conv(cur, Q4_CUR), _sail_finished_with_conv(cur, FY_CUR))

        # ---- Finished Steel opening (no MoU clause) -------------------------
        _, _, fs_q4_act, _, _, fs_q4_gr = bnc.row_values(
            cur, "SAIL", "Finished Steel", Q4_CUR, Q4_CPLY, fy_start, add_conv=True)
        _, _, fs_fy_act, _, _, fs_fy_gr = bnc.row_values(
            cur, "SAIL", "Finished Steel", FY_CUR, FY_CPLY, fy_start, add_conv=True)
        bdu.set_para(para(P_MOU_HEADING), "SAIL: Production performance for Finished Steel ")
        bdu.set_para(
            para(P_FS_Q4_NARRATIVE),
            f"The Production of Finished Steel during {q4_label} was {bnc.fmt_mt(fs_q4_act)} MT "
            f"with a growth of {bnc.fmt_pct(fs_q4_gr)}% over CPLY."
        )
        bdu.set_para(
            para(P_FS_FY_NARRATIVE),
            f"The Production of Finished Steel during April-March’{zz} was {bnc.fmt_mt(fs_fy_act)} MT, "
            f"with a growth of {bnc.fmt_pct(fs_fy_gr)}% over CPLY. "
        )

        # ---- title, intro, plant-wise title ---------------------------------
        bdu.set_para(para(P_TITLE), _title_text(fy_start))
        bdu.set_para(para(P_INTRO_Q4), f"SAIL and Plant-wise Production performance during {q4_label} and ")
        bdu.set_para(para(P_INTRO_FY), f"{fy_label} (Apr-Mar’{zz}) w.r.t. ABP")
        bdu.set_para(para(P_PLANT_SECTION_TITLE),
                     f"Plant wise: Production performance during {q4_label} and {fy_label} w.r.t. ABP")

        # ---- SAIL Q-4 and FY -------------------------------------------------
        bdu.set_para(para(P_SAIL_Q4_HEADING), f"SAIL: Production performance during {q4_label} ")
        bdu.set_para(para(P_SAIL_Q4_LABEL), f"{q4_label}:")
        bdu.set_para(para(P_SAIL_Q4_SUMMARY),
                     bq2.plant_summary_big(cur, "SAIL", Q4_CUR, Q4_CPLY, fy_start).replace("{P}", q4_label))
        sail_q4_bullets = bnc.best_ever_bullets(cur, "SAIL", lambda f: bnc.quarter_months(f, 4), fy_start, "q4")
        sail_q4_bullets += bnm.additional_highlight_lines(manual, "SAIL")
        apply_highlights("SAIL", "q4", sail_q4_bullets)

        bdu.set_para(para(P_SAIL_FY_HEADING), f"SAIL: Production performance during {fy_label} ")
        bdu.set_para(para(P_SAIL_FY_LABEL), f"{fy_label}:")
        bdu.set_para(para(P_SAIL_FY_SUMMARY),
                     bq2.plant_summary_big(cur, "SAIL", FY_CUR, FY_CPLY, fy_start).replace("{P}", fy_label))
        sail_fy_bullets = bnc.best_ever_bullets(cur, "SAIL", lambda f: bnc.long_period_months(f, 4), fy_start, "fy")
        apply_highlights("SAIL", "fy", sail_fy_bullets)

        # ---- per-plant ---------------------------------------------------------
        for plant in PLANT_ORDER:
            cfg = PLANT_CONFIG[plant]
            summary_fn = bq2._SUMMARY_FN[cfg["kind"]]

            bdu.set_para(para(cfg["label_q4"]), f"{q4_label}:")
            bdu.set_para(para(cfg["summary_q4"]),
                         summary_fn(cur, plant, Q4_CUR, Q4_CPLY, fy_start).replace("{P}", q4_label))
            q4_bullets = bnc.best_ever_bullets(cur, plant, lambda f: bnc.quarter_months(f, 4), fy_start, "q4")
            q4_bullets += bnm.additional_highlight_lines(manual, plant)
            apply_highlights(plant, "q4", q4_bullets)

            why_heading_idx = WHY_HEADING.get(plant)
            if why_heading_idx is not None:
                bdu.set_para(para(why_heading_idx), f"Production Performance during {q4_label}:")
            placeholder = f"[Add production narrative for {plant} here]"
            lines = bnm.why_narrative_lines(manual, plant, placeholder)
            bdu.fill_variable_bullets([para(i) for i in WHY_SLOTS[plant]], lines)

            bdu.set_para(para(cfg["label_fy"]), f"{fy_label}:")
            bdu.set_para(para(cfg["summary_fy"]),
                         summary_fn(cur, plant, FY_CUR, FY_CPLY, fy_start).replace("{P}", fy_label))
            fy_bullets = bnc.best_ever_bullets(cur, plant, lambda f: bnc.long_period_months(f, 4), fy_start, "fy")
            apply_highlights(plant, "fy", fy_bullets)

        for idx in STALE_PARAGRAPHS_REMOVE:
            bdu.remove_paragraph(para(idx))

        # ---- techno section ---------------------------------------------------
        periods = [
            {"label": "Q4cur", "months": Q4_CUR}, {"label": "Q4cply", "months": Q4_CPLY},
            {"label": "FYcur", "months": FY_CUR}, {"label": "FYcply", "months": FY_CPLY},
        ]
        techno_res = tp.build_period_report(TECHNO_PLANTS, TECHNO_PARAMS, periods)
        techno_by_param = {s["parameter"]: s for s in techno_res["sections"]}

        report_month = FY_CUR[-1]
        targets = {}
        for plant in ["BSP", "DSP", "RSP", "BSL", "ISP"]:
            raw = pt._get_plant_techno_plan_targets(plant, report_month)
            targets[plant] = {k[1]: v for k, v in raw.items()}
        sail_targets_raw = pt.compute_sail_targets(fy)
        targets["SAIL"] = {k[1]: v for k, v in sail_targets_raw.items()}
        for plant in list(targets):
            targets[plant] = bnc.fuel_rate_fallback(targets[plant])

        t19 = tables[TABLE_TECHNO]
        for r in (0, 1):
            bdu.set_cell(t19.rows[r].cells[3], q4_label)
            bdu.set_cell(t19.rows[r].cells[4], q4_cply_label)
            bdu.set_cell(t19.rows[r].cells[5], fy_label)
            bdu.set_cell(t19.rows[r].cells[6], fy_cply_label)
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

                tgt = _fmt_techno_target(param, (targets.get(plant) or {}).get(param))
                bdu.set_cell(cells[2], tgt if tgt is not None else "")
                bdu.set_cell(cells[3], disp("Q4cur"))
                bdu.set_cell(cells[4], disp("Q4cply"))
                bdu.set_cell(cells[5], disp("FYcur"))
                bdu.set_cell(cells[6], disp("FYcply"))
                ri += 1

        bdu.set_para(
            para(P_TECHNO_SECTION_TITLE),
            f"SAIL and Plant-wise Major Techno-economic parameters performance during {q4_label} and {fy_label}:"
        )
        for idx in TECHNO_STALE_REMOVE:
            bdu.remove_paragraph(para(idx))

        # ---- annexure index (table 20) -----------------------------------------
        t20 = tables[TABLE_ANNEXURE_INDEX]
        m1, m2, m3 = (bq2._month_name_title(m) for m in Q4_CUR)
        bdu.set_cell(t20.rows[0].cells[3],
                     f"SAIL: Production performance during {m1}’{zz}, {m2}’{zz} and {m3}’{zz}.")
        bdu.set_cell(t20.rows[1].cells[3],
                     f"SAIL: Production performance during {q4_label} and {fy_label}")
        bdu.set_cell(t20.rows[2].cells[3],
                     f"SAIL: Techno-economic parameters during {q4_label} and {fy_label}, best ever achieved, "
                     f"norms and benchmarks")
        bdu.set_cell(t20.rows[3].cells[3],
                     f"SAIL: Techno-economic parameters for New Blast Furnaces during {q4_label} and {fy_label}")
        bdu.set_cell(t20.rows[4].cells[3],
                     f"SAIL: Product mix performance during {q4_label} and {fy_label}")

        buf = io.BytesIO()
        doc.save(buf)
        return buf.getvalue()
    finally:
        conn.close()
