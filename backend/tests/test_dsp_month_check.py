"""DSP MCR-I: a report whose header date is not the selected month is refused."""
import sys
from pathlib import Path

import pytest

# The DSP extractor imports sibling extractors by bare name, as main.py's sys.path allows.
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "excel_extractors"))
from excel_extractors import excel_extractor_dsp as dsp  # noqa: E402


def _mcr1(tmp_path):
    p = tmp_path / "mcr1.xls"
    p.write_text("DAILY MANAGEMENT CONTROL REPORT -I\t\t31.10.2026\n" + "x\t1\t2\t3\t4\n" * 45)
    return str(p)


def test_mcr1_wrong_month_refused(tmp_path):
    with pytest.raises(ValueError, match="select 2026-10"):
        dsp.extract_preview(_mcr1(tmp_path), "2026-09")


def test_mcr1_right_month_accepted(tmp_path):
    assert dsp.extract_preview(_mcr1(tmp_path), "2026-10")["month"] == "2026-10"
