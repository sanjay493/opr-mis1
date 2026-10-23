"""Category-wise Saleable and Segment-wise pages: BSL "Chequered Coils" row
right after "HR Coils", read from item "Checkered Coil"; Category-wise
Total Flat still adds every displayed flat row (so splitting the coil out
of HR Coils leaves the total unchanged)."""
import pytest

from v2dual import put_production

import page_catwise_saleable as pcs
import page_segment_wise as psw

ACT = {"HSM HR Coil (Sale)": 160.0, "Checkered Coil": 24.0, "HSM HR Plate": 32.0,
       "Checkered plate": 3.0, "HR Sheet": 10.0, "Saleable Steel": 355.0}


@pytest.fixture
def fake_db(mysql_db):
    put_production("production_table", [("2026-09", "BSL", k, v) for k, v in ACT.items()])


def _labels_after(rows, label, n=2):
    labels = [r.get("label") for r in rows]
    i = labels.index(label)
    return labels[i:i + n]


def _row(rows, label):
    return next(r for r in rows if r.get("label") == label)


def _bsl_rows(result):
    """The BSL block's rows, whatever the generator's container shape."""
    if isinstance(result, dict):
        result = result.get("rows") or result.get("sections") or []
    flat = []
    for r in result:
        if isinstance(r, dict) and isinstance(r.get("rows"), list):
            flat.extend(r["rows"])
        else:
            flat.append(r)
    return flat


def test_catwise_chequered_coils_after_hr_coils(fake_db):
    rows = _bsl_rows(pcs.generate_catwise_saleable("2026-09", ["BSL"]))
    assert _labels_after(rows, "HR Coils") == ["HR Coils", "Chequered Coils"]
    assert "24" in str(_row(rows, "Chequered Coils"))


def test_catwise_total_flat_includes_chequered_coil(fake_db):
    rows = _bsl_rows(pcs.generate_catwise_saleable("2026-09", ["BSL"]))
    total = next(r for r in rows if "Total Flat" in str(r.get("label")))
    assert "229" in str(total)  # 160 + 24 + 32 + 3 + 10


def test_segment_chequered_coils_after_hr_coils(fake_db):
    rows = [r for r in _bsl_rows(psw.generate_segment_wise("2026-09")) if r.get("plant") == "BSL"]
    assert _labels_after(rows, "HR Coils") == ["HR Coils", "Chequered Coils"]
    assert "24" in str(_row(rows, "Chequered Coils"))
