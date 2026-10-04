"""Page 4's "Tentative" label: a month is final once RSP, ISP, BSL and DSP
each have their final monthly report in extraction_log (db.
_production_month_status — the pure rule behind db.production_month_status).
Months before Apr'26 predate the upload log's tracking and always count as
final.
"""

import db

FINAL_AUG = [
    ("RSP", "Final Monthly Report", "rsp_aug.xlsx"),
    ("ISP", "Summarized Monthly Report", "isp_aug.xlsx"),
    ("BSL", "BSL Production of Main Products (PDF)", "bsl.pdf"),
    ("DSP", "DSP OMI PDF Report", "mis0826.pdf"),
    ("BSP", "BSP PPC MIS Monthly Report", "BSP PPC MIS.xls"),
]


def test_all_four_final_reports_present():
    assert db._production_month_status("2026-08", FINAL_AUG) == {"tentative": False, "missing": []}


def test_one_plant_missing_is_tentative():
    rows = [r for r in FINAL_AUG if r[0] != "BSL"]
    assert db._production_month_status("2026-08", rows) == {"tentative": True, "missing": ["BSL"]}


def test_interim_reports_do_not_count():
    rows = [
        ("RSP", "Daily Morning Report", "rsp.xlsx"),
        ("ISP", "Daily Morning Report", "isp.xlsx"),
        ("BSL", "BSL DPR Mail (Month-End)", "dpr.msg"),
        ("DSP", "DSP OMI PDF Report", "pcontrep.pdf"),      # interim, not mis<MMYY>
        ("DSP", "DSP OMI PDF Report", "mis0925 (1).pdf"),   # Sep'25's report, not Sep'26
    ]
    assert db._production_month_status("2026-09", rows) == {
        "tentative": True, "missing": ["RSP", "ISP", "BSL", "DSP"]}


def test_isp_final_monthly_report_also_counts():
    rows = [r for r in FINAL_AUG if r[0] != "ISP"] + [("ISP", "Final Monthly Report", "isp.xlsx")]
    assert db._production_month_status("2026-08", rows)["tentative"] is False


def test_months_before_tracking_are_final():
    assert db._production_month_status("2026-03", []) == {"tentative": False, "missing": []}
