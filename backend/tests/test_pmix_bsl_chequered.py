"""BSL HR Coils / HR Plates on the JPC report's Pmix sheet and the Pmix FY
report: the extractor stores "Checkered Coil" / "Checkered plate" apart from
"HSM HR Coil (Sale)" / "HSM HR Plate", so both reports add them back
(HR Coils = HR Coil + Chequered Coil, HR Plates = HR Plate + Chequered
Plate), in the BSL block and in the SAIL rollup. The Pmix FY report keeps
its own row mapping rather than reusing the JPC report's."""
import pytest

import dbengine
import page_jpc_report as jpc
import page_pmix_fy_report as pfy
from repo.conn import tx

BSL = {"HSM HR Coil (Sale)": 160.138, "Checkered Coil": 24.179,
       "HSM HR Plate": 32.075, "Checkered plate": 2.801}
RSP = {"HSM-2 HR Coil (Sale)": 100.0, "HSM-2 HR Plate": 20.0}


@pytest.fixture
def cur(mysql_db):
    with tx() as seed:
        for plant, items in (("BSL", BSL), ("RSP", RSP)):
            seed.executemany("INSERT INTO production_table VALUES ('2026-09', %s, %s, %s)",
                             [(plant, k, v) for k, v in items.items()])
    c = dbengine.connect()
    yield c.cursor()
    c.close()


def _block(rows, header):
    out, on = {}, False
    for r in rows:
        if r["kind"] == "header":
            on = r["label"] == header
        elif on:
            out[r["label"]] = r["value"]
    return out


@pytest.mark.parametrize("compute", [jpc.compute_pmix_rows, pfy.compute_pmix_fy_rows],
                         ids=["jpc", "pmix_fy"])
def test_bsl_hr_coils_and_plates_include_chequered(cur, compute):
    bsl = _block(compute(cur, "2026-09"), "BSL")
    assert bsl["HR Coils"] == pytest.approx(184.317)
    assert bsl["HR Plates"] == pytest.approx(34.876)


@pytest.mark.parametrize("compute", [jpc.compute_pmix_rows, pfy.compute_pmix_fy_rows],
                         ids=["jpc", "pmix_fy"])
def test_sail_rollup_includes_bsl_chequered(cur, compute):
    sail = _block(compute(cur, "2026-09"), "SAIL")
    assert sail["HR Coils/Skelp"] == pytest.approx(284.317)
    assert sail["HR Plates"] == pytest.approx(54.876)


def test_pmix_fy_has_its_own_mapping():
    assert not hasattr(pfy, "compute_pmix_rows")
    assert pfy._BSL_ITEMS is not jpc._BSL_ITEMS
