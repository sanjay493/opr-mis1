"""Golden-file tests for the plant Excel extractors.

Each case runs one extractor's `extract_preview(file_path, report_month)`
against a sample file committed under `Report_format/` and compares the full
result dict with a golden JSON file in `tests/goldens/`.

To regenerate the goldens after an intentional extraction change:

    cd backend
    venv/Scripts/python -m pytest tests -q --update-goldens

then review the golden diff in git before committing — the diff IS the
behaviour change.
"""

import importlib
import json
import math
from dataclasses import dataclass
from pathlib import Path

import pytest

BACKEND_DIR = Path(__file__).resolve().parents[1]
SAMPLES_DIR = BACKEND_DIR.parent / "Report_format"
GOLDENS_DIR = Path(__file__).parent / "goldens"


@dataclass(frozen=True)
class Case:
    id: str            # golden file name (without .json)
    module: str        # extractor module with an extract_preview() function
    sample: str        # sample file path, relative to Report_format/
    month: str         # report_month argument, YYYY-MM


CASES = [
    Case("rsp_morning_2026-05",
         "excel_extractors.excel_extractor_rsp",
         "MONTHEND/RSP31052026.xlsx", "2026-05"),
    Case("bsp_mis_2026-05",
         "excel_extractors.excel_extractor_bsp",
         "MONTHEND/BSPMIS30052026.xls", "2026-05"),
    Case("bsl_dpr_2026-05",
         "excel_extractors.excel_extractor_bsl",
         "MONTHEND/BSL/BSL-DPR31052026.xlsx", "2026-05"),
    Case("isp_morning_2026-05",
         "excel_extractors.excel_extractor_isp",
         "MONTHEND/MORNING REPORT.xlsx", "2026-05"),
    Case("dsp_mcr1_2026-05",
         "excel_extractors.excel_extractor_dsp",
         "MONTHEND/mcr1_31052026.xls", "2026-05"),
    Case("dsp_pdf_2025-08",
         "excel_extractors.pdf_extractor_dsp",
         "Monthly/DSP mis0825 (1).pdf", "2025-08"),
    Case("dsp_pdf_2026-03",
         "excel_extractors.pdf_extractor_dsp",
         "Monthly/DSPmis0326.pdf", "2026-03"),
    Case("dsp_pdf_2025-05",
         "excel_extractors.pdf_extractor_dsp",
         "Monthly/mis0525.pdf", "2025-05"),
    Case("isp_summarized_2026-03",
         "excel_extractors.excel_extractor_isp",
         "Monthly/ISP/ISPSummarizedMonthlyReport-March26.xlsx", "2026-03"),
    Case("bsp_techno_2026-05",
         "excel_extractors.excel_extractor_bsp_techno",
         "Monthly/BSP/3 page Tech for COMay'26.xlsx", "2026-05"),
    Case("bsp_oisco_2026-05",
         "excel_extractors.excel_extractor_bsp_oisco",
         "Monthly/BSP/OISCO_MAY26.xlsx", "2026-05"),
    Case("bsp_flash_pdf_2026-03",
         "excel_extractors.pdf_extractor_bsp_flash",
         "Monthly/BSP/flash-mar26.pdf", "2026-03"),
    Case("bsp_flash_pdf_2026-04",
         "excel_extractors.pdf_extractor_bsp_flash",
         "Monthly/BSP/flash-apr26.pdf", "2026-04"),
    Case("bsp_flash_pdf_2026-05",
         "excel_extractors.pdf_extractor_bsp_flash",
         "Monthly/BSP/flash-may26.pdf", "2026-05"),
    Case("bsp_flash_pdf_2026-06",
         "excel_extractors.pdf_extractor_bsp_flash",
         "Monthly/BSP/flash-jun26.pdf", "2026-06"),
    # RSP "Final Monthly Report" (page-9 production + page-1-8 techno-table)
    # cases below lock in the production-side fix: page-1-8's sheet name
    # varies constantly ("PAGE-1-8", "page-1-8 &11-12", "PAGE-1-8 & 11' 12", …)
    # and its month/Cum columns shift every year as a legacy fiscal-year
    # column gets prepended — these three cover a plain name, and two
    # differently-punctuated compound names.
    Case("rsp_technopara_oct2025_2025-10",
         "excel_extractors.excel_extractor_rsp",
         "Monthly/RSP/TECHNOPARA OCT-2025.xlsx", "2025-10"),
    Case("rsp_technopara_nov2023_2023-11",
         "excel_extractors.excel_extractor_rsp",
         "Monthly/RSP/TECHNOPARA NOV-2023 Revised.xlsx", "2023-11"),
    Case("rsp_technopara_apr2024_2024-04",
         "excel_extractors.excel_extractor_rsp",
         "Monthly/RSP/TECHNOPARA APRIL-2024.xlsx", "2024-04"),
]


def _normalize(obj):
    """Make extractor output JSON-stable: round floats, stringify exotics."""
    if isinstance(obj, dict):
        return {str(k): _normalize(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_normalize(v) for v in obj]
    if isinstance(obj, float):
        if math.isnan(obj) or math.isinf(obj):
            return repr(obj)
        return round(obj, 6)
    if isinstance(obj, (str, int, bool)) or obj is None:
        return obj
    return str(obj)


@pytest.mark.parametrize("case", CASES, ids=lambda c: c.id)
def test_extract_preview_matches_golden(case, update_goldens):
    sample = SAMPLES_DIR / case.sample
    if not sample.exists():
        pytest.skip(f"sample file not present: {sample}")

    mod = importlib.import_module(case.module)
    result = _normalize(mod.extract_preview(str(sample), case.month))

    golden_path = GOLDENS_DIR / f"{case.id}.json"
    if update_goldens:
        GOLDENS_DIR.mkdir(exist_ok=True)
        golden_path.write_text(
            json.dumps(result, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        return

    if not golden_path.exists():
        pytest.fail(
            f"Golden file missing: {golden_path}\n"
            "Generate it with: pytest tests -q --update-goldens"
        )

    golden = json.loads(golden_path.read_text(encoding="utf-8"))
    assert result == golden, (
        f"Extractor output for {case.id} differs from golden file. "
        "If the change is intentional, rerun with --update-goldens and "
        "review the golden diff in git."
    )
