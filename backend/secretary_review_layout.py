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
