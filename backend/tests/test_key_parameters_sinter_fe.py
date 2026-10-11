"""Inter Plant Performance Comparison, Sinter Fe row: BSL and ISP extract
Sinter Fe as fe%_in_sinter under their sinter-plant unit ("Sinter" / "SP");
the row falls back to it when the BF unit has no tfe_in_sinter."""
import page_key_parameters as kp


def test_bsl_uses_sinter_unit_fe_pct_when_bf_has_none():
    techno = {("BSL", "BF_Shop"): {"slag_rate": 400}, ("BSL", "Sinter"): {"fe%_in_sinter": 51.1133}}
    assert kp._sinter_fe_val("BSL", techno, 2) == 51.11


def test_isp_uses_sp_unit():
    techno = {("ISP", "SP"): {"fe%_in_sinter": 55.8056}}
    assert kp._sinter_fe_val("ISP", techno, 2) == 55.81


def test_bf_value_still_wins_when_present():
    techno = {("BSL", "BF_Shop"): {"tfe_in_sinter": 51.15}, ("BSL", "Sinter"): {"fe%_in_sinter": 51.148}}
    assert kp._sinter_fe_val("BSL", techno, 2) == 51.15


def test_sinter_unit_tfe_key_also_read():
    techno = {("DSP", "Sinter"): {"tfe_in_sinter": 55.97}}
    assert kp._sinter_fe_val("DSP", techno, 2) == 55.97


def test_none_when_nothing_stored():
    assert kp._sinter_fe_val("BSP", {("BSP", "BF_Shop"): {}}, 2) is None
