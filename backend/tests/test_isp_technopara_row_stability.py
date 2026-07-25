"""Golden-rule self-check for the ISP Technopara extractor
(techno_project/isp_technopara_extractor.py).

`ISPSummarizedMonthlyReport-March26.xlsx` is unique among the sample files:
its COKE OVENS/B-FCE/etc. sheets carry EVERY month of FY2025-26 as its own
'ACT' column in one workbook (Apr'25 .. Mar'26), interspersed with
cumulative columns. That lets us run the extractor 12 times against a
SINGLE, known-good file and check two invariants that a code change or a
future report-template tweak could silently break:

  1. Every month extracts without raising, and returns a stable number of
     units with a healthy amount of non-null data (catches wholesale
     column/row-detection breakage).
  2. Twelve different report_months resolve to twelve DIFFERENT Excel
     columns for the same parameter (catches _get_cum_column_offset or
     month-header matching accidentally aliasing two months onto the same
     column).

This does NOT catch row-position drift between files (the row numbers are
fixed within one workbook) — that's what the whole-sheet label search in
_resolve_unit_rows() is for, and what the per-real-file sanity loop below
(using real monthly report files spanning 2021-26) guards against instead:
those are the real upload artifacts, so if SAIL ever changes the template,
extraction from one of them should still return data, not raise.
"""

import importlib
from pathlib import Path

import pytest

BACKEND_DIR = Path(__file__).resolve().parents[1]
ISP_DIR = BACKEND_DIR.parent / "Report_format" / "Monthly" / "ISP"
MARCH_FILE = ISP_DIR / "ISPSummarizedMonthlyReport-March26.xlsx"
# A second, independently-shifted cumulative workbook (FY2026-27, Apr-Jun so
# far) — its row layout is NOT the same as MARCH_FILE's (confirmed: B-FCE -1,
# SINTER +1, WRM +4, USM +5, COKE OVENS -3, Maj Techno Summ +2 vs. the
# isp_technopara_map.json row numbers), which is exactly the "cell shifting"
# scenario extract_available_months()/the offset-correction in
# _compute_unit_offset need to survive.
BULK_FILE = ISP_DIR / "Summarized Monthly Report 2026-27 upto Jun26.xlsx"

FY2025_26_MONTHS = [f"2025-{m:02d}" for m in range(4, 13)] + [f"2026-{m:02d}" for m in range(1, 4)]

# The 15 real monthly upload files, each with its own report_month.
REAL_MONTHLY_FILES = [
    ("Summarized Monthly Report Apr'25.xlsx", "2025-04"),
    ("Summarized Monthly Report May'25.xlsx", "2025-05"),
    ("Summarized Monthly Report Jun'25.xlsx", "2025-06"),
    ("Summarized Monthly Report Jul'25.xlsx", "2025-07"),
    ("Summarized Monthly Report Aug'25.xlsx", "2025-08"),
    ("Summarized Monthly Report Sep'25.xlsx", "2025-09"),
    ("Summarized Monthly Report Oct'25.xlsx", "2025-10"),
    ("Summarized Monthly Report Nov'25.xlsx", "2025-11"),
    ("Summarized Monthly Report Dec'25.xlsx", "2025-12"),
    ("Summarized Monthly Report Jan'26.xlsx", "2026-01"),
    ("Summarized Monthly Report Feb'26.xlsx", "2026-02"),
    ("Summarized Monthly Report Mar'25.xlsx", "2025-03"),
    ("Summarized Monthly Report Apr'26.xlsx", "2026-04"),
    ("Summarized Monthly Report May'26.xlsx", "2026-05"),
    ("Mar'24Summarized Monthly Report.xlsx", "2024-03"),
    # Older archival files (2021-24) — real crash found here: 'ammonium_
    # sulphate_yield's expected label 'Total (NH4)₂SO4' (isp_technopara_
    # row_labels.json) crashed the WHOLE extraction with UnicodeEncodeError
    # on Windows' cp1252 console the moment _resolve_unit_rows had to print
    # a "not found" warning quoting it — fixed via _safe_print.
    ("Summarized Report 2023-24 (final).xlsx", "2023-04"),
    ("Summarised Monthly 2021-22 (R=f 2.5.22).xlsx", "2021-04"),
]

# Mar'24Summarized Monthly Report.xlsx — a real file with a MUCH bigger and
# non-uniform row shift than any other sample (USM -51 rows, WRM -34, BM -7,
# and COKE OVENS' oven-count block -4 rows while its coke-quality block
# shifted -7 in the SAME sheet). It exposed two real bugs:
#   1. The row-shift self-heal's fixed +/-20 search window was too narrow
#      to find labels shifted further than that (USM/WRM) — widened via
#      _max_safe_window (unbounded for sheets holding only one unit).
#   2. total_gas_consumption/dry_coal_charge_oven (expression row specs) were
#      never verified per-row at all, so a shift there silently summed the
#      wrong cells (confirmed: BM read 2532.8 instead of ~9.9) — fixed via
#      _verified_expr_row + isp_technopara_expr_row_labels.json.
MAR24_FILE = ISP_DIR / "Mar'24Summarized Monthly Report.xlsx"
_MAR24_GAS_CEILING = 1000  # same reasoning as _TOTAL_GAS_CONSUMPTION_CEILING below

# Expected record count (extract() emits one record per (sheet, unit)
# pair, so a unit name reused by multiple sheets — e.g. "General" from
# B-FCE and Maj Techno Summ — legitimately produces multiple records that
# get merged into the same techno_data row on save):
#   B-FCE: BF-5, General [coke_screen_loss only] (2)
#   + SMS: SMS (1) + SINTER: SP (1) + WRM (1) + BM (1) + USM (1)
#   + COKE OVENS: COB-old/COB-new (2) + Maj Techno Summ: General [incl.
#     coal_to_hm] (1) = 10
#
# B-FCE's stray "SP" sub-group (just "return_fines", no other consumer
# expects a specific unit for it) was folded into "BF-5" to remove that
# particular collision. coal_to_hm lives under Maj Techno Summ's "General"
# (row 15, isp_technopara_map.json) — an earlier revision moved it to a
# dedicated "Coal to Hot Metal" sheet/row and back again (see git history);
# "Maj Techno Summ" row 15 is present and stable across every sample file
# checked (2016-17 through 2026-27), coke_screen_loss stays under "General"
# because page_techno.py's report reads it from units ["General", "BF_Shop"]
# specifically. merge_upsert_techno_data (not the old clobbering upsert)
# makes sharing the "General" unit name across two sheets safe.
EXPECTED_UNIT_COUNT = 10
MIN_NONNULL_VALUES = 30  # out of 81 mapped params total, a generous floor


def _extractor_class():
    mod = importlib.import_module("techno_project.isp_technopara_extractor")
    return mod.IspTechnoExtractor


@pytest.mark.parametrize("report_month", FY2025_26_MONTHS)
def test_all_fy2025_26_months_extract_cleanly(report_month):
    if not MARCH_FILE.exists():
        pytest.skip(f"sample file not present: {MARCH_FILE}")
    IspTechnoExtractor = _extractor_class()
    records = IspTechnoExtractor(str(MARCH_FILE), report_month).extract()

    assert len(records) == EXPECTED_UNIT_COUNT, (
        f"{report_month}: expected {EXPECTED_UNIT_COUNT} units, got {len(records)} "
        f"({[r['unit'] for r in records]})"
    )
    for rec in records:
        assert rec["report_month"] == report_month
        assert rec["plant"] == "ISP"

    total_nonnull = sum(
        1 for rec in records for v in rec["techno_json"]["month"].values() if v is not None
    )
    assert total_nonnull >= MIN_NONNULL_VALUES, (
        f"{report_month}: only {total_nonnull} non-null month values extracted "
        f"(expected >= {MIN_NONNULL_VALUES}) — likely a column-detection regression"
    )


def test_all_fy2025_26_months_resolve_distinct_columns():
    """Same B-FCE 'coke_rate' parameter, 12 different report_months against
    the SAME file, must resolve to 12 different Excel columns."""
    if not MARCH_FILE.exists():
        pytest.skip(f"sample file not present: {MARCH_FILE}")
    IspTechnoExtractor = _extractor_class()

    columns = set()
    for report_month in FY2025_26_MONTHS:
        ex = IspTechnoExtractor(str(MARCH_FILE), report_month)
        ex.open_workbook()
        ws = ex.workbook["B-FCE"]
        header_row, header = ex._find_month_column(ws)
        assert header_row is not None, f"{report_month}: no month header row found"
        month_num = int(report_month.split("-")[1])
        from techno_project.isp_technopara_extractor import _MONTH_NUM_TO_ABBR
        target_abbr = _MONTH_NUM_TO_ABBR[month_num]
        month_col = next(i for i, h in enumerate(header) if target_abbr in h)
        act_col = ex._get_actual_column(ws, month_col)
        columns.add(act_col)

    assert len(columns) == 12, (
        f"Expected 12 distinct ACT columns across FY2025-26, got {len(columns)}: {sorted(columns)}"
    )


@pytest.mark.parametrize("filename,report_month", REAL_MONTHLY_FILES)
def test_real_monthly_files_extract_without_crashing(filename, report_month):
    """Sanity check against the real per-month upload files (not the
    multi-month March file) — catches genuine file-to-file template drift
    that a single multi-month workbook can't, since row positions don't vary
    across columns within one file."""
    sample = ISP_DIR / filename
    if not sample.exists():
        pytest.skip(f"sample file not present: {sample}")
    IspTechnoExtractor = _extractor_class()
    records = IspTechnoExtractor(str(sample), report_month).extract()
    assert records, f"{filename} ({report_month}): no units extracted at all"
    total_nonnull = sum(
        1 for rec in records for v in rec["techno_json"]["month"].values() if v is not None
    )
    assert total_nonnull >= MIN_NONNULL_VALUES, (
        f"{filename} ({report_month}): only {total_nonnull} non-null month values"
    )


# ── Regression guard: expression/list row specs must survive a row-shifted
# workbook, not just the simple int specs _verified_row already checks. ─────
#
# BULK_FILE's row layout is shifted vs. isp_technopara_map.json (WRM +4,
# USM +5 — confirmed via the extractor's own "row shifted" warnings). Before
# _compute_unit_offset (see isp_technopara_extractor.py), WRM/USM's
# total_gas_consumption ("174+175+176+177" / "140+141+142+143" — expression
# specs, which _verified_row never touches) silently summed the WRONG rows in
# this file and returned values in the millions (~7.4M / ~3.9M) instead of
# the correct single-digit m3/t figures. This test pins a plausible ceiling
# so that regression can't silently reappear.
_TOTAL_GAS_CONSUMPTION_CEILING = 1000  # real values are single/low-double digits


@pytest.mark.parametrize("report_month", ["2026-04", "2026-05", "2026-06"])
def test_bulk_file_expression_rows_survive_shift(report_month):
    """WRM/USM total_gas_consumption (expression row specs) must stay in a
    plausible range against BULK_FILE, whose rows are shifted vs. the map."""
    if not BULK_FILE.exists():
        pytest.skip(f"sample file not present: {BULK_FILE}")
    IspTechnoExtractor = _extractor_class()
    records = IspTechnoExtractor(str(BULK_FILE), report_month).extract()
    by_unit = {r["unit"]: r["techno_json"] for r in records}

    for unit in ("WRM", "USM"):
        assert unit in by_unit, f"{report_month}: expected unit {unit!r} in {sorted(by_unit)}"
        val = by_unit[unit]["month"].get("total_gas_consumption")
        assert val is None or abs(val) < _TOTAL_GAS_CONSUMPTION_CEILING, (
            f"{report_month}: {unit}.total_gas_consumption = {val!r} — looks like an "
            f"unshifted expression row spec summing the wrong cells (row-shift regression)"
        )


def test_extract_available_months_against_bulk_file():
    """extract_available_months() must return exactly April..June 2026 for
    BULK_FILE (a file that only carries those 3 FY2026-27 months so far),
    with real data in each — the backing extraction for the "backfill all
    months" upload feature."""
    if not BULK_FILE.exists():
        pytest.skip(f"sample file not present: {BULK_FILE}")
    IspTechnoExtractor = _extractor_class()
    result = IspTechnoExtractor(str(BULK_FILE)).extract_available_months("2026-06")

    assert result["months"] == ["2026-04", "2026-05", "2026-06"], result["months"]
    assert result["skipped_months"] == [], result["skipped_months"]
    for month in result["months"]:
        recs = result["records_by_month"][month]
        assert len(recs) == EXPECTED_UNIT_COUNT, (
            f"{month}: expected {EXPECTED_UNIT_COUNT} units, got {len(recs)}"
        )
        total_nonnull = sum(
            1 for rec in recs for v in rec["techno_json"]["month"].values() if v is not None
        )
        assert total_nonnull >= MIN_NONNULL_VALUES, (
            f"{month}: only {total_nonnull} non-null month values"
        )


def test_mar24_file_wide_shift_recovers_full_coverage():
    """Regression test for a real bug: before _max_safe_window (unbounded
    search for sheets holding only one unit), USM's labels — shifted -51
    rows in this file — were never found within the old +/-20 window, so
    USM extracted ZERO units and WRM extracted only 1/8 params. Both must
    now fully recover."""
    if not MAR24_FILE.exists():
        pytest.skip(f"sample file not present: {MAR24_FILE}")
    IspTechnoExtractor = _extractor_class()
    records = IspTechnoExtractor(str(MAR24_FILE), "2024-03").extract()
    by_unit = {r["unit"]: r["techno_json"] for r in records}

    for unit, expected_param_count in (("WRM", 8), ("USM", 8), ("BM", 8)):
        assert unit in by_unit, f"expected unit {unit!r} in {sorted(by_unit)}"
        nonnull = sum(1 for v in by_unit[unit]["month"].values() if v is not None)
        assert nonnull == expected_param_count, (
            f"{unit}: expected all {expected_param_count} params non-null, got {nonnull}"
        )


def test_mar24_file_expression_rows_verified_individually():
    """Regression test for a real bug: this file's COKE OVENS sheet has TWO
    different shift zones in the same sheet (oven-count block -4, coke-
    quality block -7), so the single per-unit blanket offset that
    total_gas_consumption/dry_coal_charge_oven fell back to before
    _verified_expr_row was wrong for at least one of them. Confirmed:
    BM.total_gas_consumption read 2532.8 (summing 'Crop'/'Total Mill
    Arisings'/etc., the wrong block entirely) instead of ~9.9."""
    if not MAR24_FILE.exists():
        pytest.skip(f"sample file not present: {MAR24_FILE}")
    IspTechnoExtractor = _extractor_class()
    records = IspTechnoExtractor(str(MAR24_FILE), "2024-03").extract()
    by_unit = {r["unit"]: r["techno_json"] for r in records}

    for unit in ("WRM", "USM", "BM"):
        val = by_unit[unit]["month"].get("total_gas_consumption")
        assert val is not None, f"{unit}: total_gas_consumption unexpectedly null"
        assert abs(val) < _MAR24_GAS_CEILING, (
            f"{unit}.total_gas_consumption = {val!r} — looks like the wrong "
            f"shift zone was applied (row-shift regression)"
        )


def test_mar24_dry_coal_charge_oven_uses_average_pushing_fallback():
    """dry_coal_charge_oven = Dry Coal Charge / Num of Ovens Pushed (the
    MONTHLY TOTAL push count). This file has no such row at all — only a
    per-day average under the wording 'No.of Ovens Pushed (COB#10)' /
    'Nos.of Ovens Pushed (COB#11)'. Per SAIL convention (confirmed by the
    user and cross-checked against the canonical template's own Average
    Pushing/Num of Ovens Pushed pair): monthly total = daily average * days
    in month. Verified: COB-old 99.0645...*31 = 3071 -> 52821.2/3071 = 17.2
    (the same value a clean, unshifted file gives), COB-new -> 31.55."""
    if not MAR24_FILE.exists():
        pytest.skip(f"sample file not present: {MAR24_FILE}")
    IspTechnoExtractor = _extractor_class()
    records = IspTechnoExtractor(str(MAR24_FILE), "2024-03").extract()
    by_unit = {r["unit"]: r["techno_json"] for r in records}

    assert by_unit["COB-old"]["month"]["dry_coal_charge_oven"] == pytest.approx(17.2, abs=0.01)
    assert by_unit["COB-new"]["month"]["dry_coal_charge_oven"] == pytest.approx(31.55, abs=0.01)


@pytest.mark.parametrize("report_month", ["2026-04", "2026-05"])
def test_short_generic_labels_resolve_to_own_row_not_a_distant_match(report_month):
    """Regression test for a real bug in _resolve_unit_rows: short/generic
    expected labels ('Coke', 'CDI', 'Total Fuel') substring-match many
    unrelated rows across a whole sheet (B-FCE has 16+ rows containing
    'coke' alone). An earlier version of _resolve_unit_rows disambiguated
    those against a cross-parameter centroid of other already-resolved
    rows, which let one contaminated resolution drag the anchor for every
    other ambiguous param toward it — confirmed: BF-5's coke_rate resolved
    to row 72 (a distant, unrelated 'coke' mention) instead of row ~38-39,
    reading a completely wrong parameter's value (10.35 instead of 10.52 for
    2026-05). Each param must resolve nearest to its OWN configured row,
    verified here by requiring the bulk multi-month file (BULK_FILE, whose
    B-FCE sheet is shifted by -1 vs the single-month file) and the
    single-month file to agree exactly on coke_rate for the same month."""
    if not BULK_FILE.exists():
        pytest.skip(f"sample file not present: {BULK_FILE}")
    single_name = "Summarized Monthly Report Apr'26.xlsx" if report_month == "2026-04" \
        else "Summarized Monthly Report May'26.xlsx"
    single_file = ISP_DIR / single_name
    if not single_file.exists():
        pytest.skip(f"sample file not present: {single_file}")

    IspTechnoExtractor = _extractor_class()
    single_val = next(
        r["techno_json"]["month"]["coke_rate"]
        for r in IspTechnoExtractor(str(single_file), report_month).extract()
        if r["unit"] == "BF-5"
    )
    bulk_val = next(
        r["techno_json"]["month"]["coke_rate"]
        for r in IspTechnoExtractor(str(BULK_FILE), report_month).extract()
        if r["unit"] == "BF-5"
    )
    assert single_val == pytest.approx(bulk_val, rel=1e-6), (
        f"{report_month}: BF-5.coke_rate differs between the single-month file "
        f"({single_val}) and the bulk file ({bulk_val}) — looks like a "
        f"short-label mis-resolution (row-shift regression)"
    )


FINAL_2023_24_FILE = ISP_DIR / "Summarized Report 2023-24 (final).xlsx"


def test_substring_match_never_beats_an_exact_match_elsewhere():
    """Regression test for a real bug: 'Coke' is a substring of 'Nut Coke'
    too, and in this file 'Nut Coke' (value 37.49, the nut-coke RATE)
    happens to sit exactly at coke_rate's configured row 39 — so the
    nearest-to-configured-row tiebreak alone picked it as a false match,
    reading 37.49 (a completely different parameter) as coke_rate instead
    of the real ~394.49 (row 38, labelled exactly 'Coke'). Exact label
    matches must always be preferred over mere substring hits."""
    if not FINAL_2023_24_FILE.exists():
        pytest.skip(f"sample file not present: {FINAL_2023_24_FILE}")
    IspTechnoExtractor = _extractor_class()
    records = IspTechnoExtractor(str(FINAL_2023_24_FILE), "2023-04").extract()
    by_unit = {r["unit"]: r["techno_json"] for r in records}

    coke_rate = by_unit["BF-5"]["month"]["coke_rate"]
    nut_coke_rate = by_unit["BF-5"]["month"]["nut_coke_rate"]
    assert coke_rate == pytest.approx(394.49, abs=0.01), (
        f"coke_rate = {coke_rate!r} — expected ~394.49 (row 38, exact label "
        f"'Coke'); got the nut-coke-rate row instead if this is ~37.49"
    )
    assert nut_coke_rate == pytest.approx(37.49, abs=0.01), (
        f"nut_coke_rate = {nut_coke_rate!r} — expected ~37.49 (row 39, exact "
        f"label 'Nut Coke')"
    )
    assert coke_rate != nut_coke_rate
