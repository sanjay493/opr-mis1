"""The Breakdown & CR log downloads name the month when narrowed to one."""
import io

import openpyxl

import page_bd_cr_log_export as export

_EVENT = {"month": "Oct'26", "kind": "BD", "linked": False, "dates": "03 Oct", "sub": "",
          "details": "Tilting issue", "duration": "2h", "ongoing": False}
_DATA = {"plant": "BSP", "plant_title": "Bhilai Steel Plant", "fy": "2026-27",
         "units": [{"title": "SMS-2", "type_label": "SMS", "bd": 1, "cr": 0, "events": [_EVENT]}]}
_OCT = {**_DATA, "month": "2026-10", "month_label": "Oct'26"}


def _subtitle(data):
    wb = openpyxl.load_workbook(io.BytesIO(export.build_excel_bytes(data)))
    return wb.active.cell(row=2, column=1).value


def test_whole_fy_export_is_unchanged():
    assert export._filename(_DATA, "pdf") == "BD_CR_Log_BSP_2026-27.pdf"
    assert _subtitle(_DATA).startswith("FY 2026-27  ·  BD = Breakdown")
    assert "FY 2026-27 · BD = Breakdown" in " ".join(export.build_pdf_html(_DATA).replace("  ·  ", " · ").split())


def test_month_export_names_the_month():
    assert export._filename(_OCT, "xlsx") == "BD_CR_Log_BSP_2026-27_2026-10.xlsx"
    assert _subtitle(_OCT).startswith("FY 2026-27  ·  Oct'26  ·  BD = Breakdown")
    assert "Oct&#x27;26" in export.build_pdf_html(_OCT)
