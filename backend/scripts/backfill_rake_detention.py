"""
One-time backfill for "Details of Rakes Detention Plant Wise" — every
figure transcribed directly from the sample source PDF ("Average Plant
Detention Report for the period 01-08-2026 to 31-08-2026.pdf", SAIL Rail
Movement Cell). Idempotent: every db.save_* call here is an upsert, safe
to re-run.

Seeds, in order:
  1. rake_detention_master — the row registry (plant/section/commodity/
     wagon-type/freetime), built fresh from DETAIL_DATA below.
  2. rake_detention_monthly — pages 1-2's Apr-Aug'26 figures for every
     master row (including each section's own Total/Overall summary row).
  3. rake_detention_monthly (again, same table) — page 4's older closed-FY
     history (2021-22 through 2025-26) for each plant's "Overall Wagon"
     master row only, since that's the only row with years of history.
  4. rake_detention_annual — page 4's own "APR-MAR" full-FY average column,
     current FY included (its own directly-reported figure, not a mean of
     the 5 months filled so far).
  5. rake_detention_summary — page 3's "Improvement in Average Detention"
     9-period x 6-plant table.

Run: python backfill_rake_detention.py   (from backend/scripts/, same venv
as the rest of the backend)
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import db

REPORT_MONTH = "2026-08"
CUR_FY_MONTHS = ["2026-04", "2026-05", "2026-06", "2026-07", "2026-08"]

# ── Pages 1-2: commodity/wagon-type detail, Apr-Aug'26 ─────────────────────
# {plant: {section: {"direction": str|None, "rows": [(commodity, wagon_type, freetime, [5 values]), ...],
#                     "total": (row_label, [5 values])}}}
DETAIL_DATA = {
    "BSP": {
        "INWARD": {"direction": "L-E", "rows": [
            ("Ind.Coking Coal", "BOXN", 8.0, [7.0, 7.3, 8.1, 9.1, 13.4]),
            ("Ind.Coking Coal", "BOST", 8.0, [7.2, 12.0, 10.0, 8.0, 7.6]),
            ("Ind.Coking Coal", "BOSM", 8.0, [7.5, 0.0, 8.0, 8.0, 11.5]),
            ("Imp.Coking Coal", "BOXN", 8.0, [7.1, 7.4, 7.2, 8.2, 9.5]),
            ("Imp.Coking Coal", "BOST", 8.0, [6.3, 0.0, 0.0, 6.5, 9.0]),
            ("Imp.Coking Coal", "BOSM", 8.0, [0.0, 9.4, 0.0, 7.4, 17.0]),
            ("Boiler Coal", "BOXN", 8.0, [7.4, 10.3, 9.5, 9.1, 9.5]),
            ("Iron Ore", "BOBS/N", 3.0, [3.1, 3.2, 3.4, 4.3, 8.2]),
            ("Iron Ore", "BOSM", 3.0, [0.0, 10.4, 7.5, 11.3, 13.5]),
            ("Iron Ore", "BOXN", 8.0, [7.1, 9.0, 8.1, 11.2, 13.1]),
            ("Flux", "BOBS/N", 3.0, [7.0, 1.3, 2.1, 0.0, 2.0]),
            ("Flux", "BOSM", 3.0, [0.0, 7.6, 7.3, 7.2, 0.0]),
            ("Flux", "BOST", 8.0, [6.3, 8.3, 8.0, 6.5, 0.0]),
            ("Flux", "BOXN", 8.0, [7.2, 7.5, 8.1, 10.1, 12.0]),
            ("Coke Products", "BOXN", 8.0, [0.0, 0.0, 0.0, 0.0, 0.0]),
        ], "total": ("Total Inward", [5.3, 5.5, 6.1, 7.4, 10.0])},
        "OUTWARD": {"direction": "E-L", "rows": [
            ("Outward Despatch", "BOST", 16.0, [17.5, 16.2, 14.5, 15.4, 18.2]),
            ("Outward Despatch", "BOXN", 16.0, [4.6, 4.4, 10.4, 10.2, 11.1]),
            ("Outward Despatch", "BRN", 18.0, [19.1, 16.4, 15.3, 17.1, 20.1]),
            ("Outward Despatch", "BFNS", 18.0, [19.2, 17.2, 14.5, 16.4, 20.4]),
            ("Outward Despatch", "LOHA-BRN", 16.0, [16.4, 13.1, 15.4, 16.5, 22.0]),
            ("Outward Despatch", "DMT", 16.0, [15.3, 15.1, 14.5, 15.1, 17.4]),
        ], "total": ("Total Outward", [14.4, 13.3, 13.6, 14.4, 16.5])},
        "OVERALL": {"direction": None, "rows": [
            ("", "BOST", 34.0, [17.1, 15.2, 14.2, 14.6, 17.3]),
            ("", "BRN", 36.0, [19.1, 16.4, 15.3, 16.6, 20.1]),
            ("", "BFNS", 36.0, [19.2, 17.2, 14.5, 16.4, 20.4]),
            ("", "LOHA BRN", 36.0, [16.4, 13.1, 15.4, 16.5, 22.0]),
            ("", "DMT", 24.0, [15.3, 15.1, 14.5, 15.1, 17.4]),
            ("", "BOXN", 14.0, [6.6, 7.3, 8.1, 9.3, 11.0]),
            ("", "BOBS/N", 5.5, [3.1, 3.1, 3.3, 4.3, 8.1]),
        ], "total": ("Overall Wagon", [7.4, 7.4, 8.1, 9.2, 11.4])},
    },
    "DSP": {
        "INWARD": {"direction": "L-E", "rows": [
            ("Ind.Coking Coal", "BOXN", 12.0, [12.0, 10.0, 10.0, 12.0, 15.0]),
            ("Imp.Coking Coal", "BOXN", 12.0, [11.0, 11.0, 10.0, 11.0, 14.0]),
            ("Middling Coal", "BOXN", 12.0, [13.0, 10.0, 12.0, 12.0, 12.0]),
            ("Iron Ore", "BOSM", 12.0, [12.0, 0.0, 0.0, 0.0, 0.0]),
            ("Iron Ore", "BOST", 12.0, [0.0, 0.0, 0.0, 0.0, 0.0]),
            ("Iron Ore", "BOXN", 12.0, [14.0, 13.0, 13.0, 18.0, 17.0]),
            ("Flux", "BOXN", 12.0, [12.0, 13.0, 12.0, 13.0, 15.0]),
            ("Hard Coke", "BOXN", 12.0, [32.0, 20.0, 0.0, 0.0, 0.0]),
        ], "total": ("Total Inward", [13.0, 12.0, 12.0, 15.0, 15.0])},
        "OUTWARD": {"direction": "E-L", "rows": [
            ("Outward Despatch", "BOST", 20.0, [18.0, 17.0, 18.0, 18.0, 19.0]),
            ("Outward Despatch", "BOSM", 20.0, [20.0, 17.0, 19.0, 19.0, 20.0]),
            ("Outward Despatch", "BOXN", 20.0, [19.0, 24.0, 22.0, 32.0, 20.0]),
            ("Outward Despatch", "BRN", 20.0, [18.0, 17.0, 17.0, 17.0, 18.0]),
        ], "total": ("Total Outward", [19.0, 17.0, 18.0, 18.0, 20.0])},
        "OVERALL": {"direction": None, "rows": [
            ("", "BOST", 34.0, [18.0, 22.0, 18.0, 18.0, 19.0]),
            ("", "BRN", 36.0, [20.0, 21.0, 17.0, 17.0, 18.0]),
            ("", "BOXN", 14.0, [13.0, 12.0, 12.0, 15.0, 15.0]),
            ("", "BOSM", 14.0, [20.0, 17.0, 19.0, 19.0, 20.0]),
        ], "total": ("Overall Wagon", [14.0, 13.0, 13.0, 16.0, 16.0])},
    },
    "RSP": {
        "INWARD": {"direction": "L-E", "rows": [
            ("Ind.Coking Coal", "BOXN", 12.0, [20.7, 19.8, 18.8, 21.3, 49.8]),
            ("Imp.Coking Coal", "BOXN", 12.0, [19.9, 20.7, 22.5, 24.6, 43.3]),
            ("Boiler Coal", "BOXN", 12.0, [16.6, 16.8, 14.1, 21.7, 26.6]),
            ("Iron Ore", "BOBS/N", 5.0, [4.6, 5.5, 6.0, 11.3, 15.9]),
            ("Iron Ore", "NBOY", 12.0, [0.0, 0.0, 0.0, 0.0, 0.0]),
            ("Iron Ore", "BOXN", 12.0, [0.0, 0.0, 0.0, 0.0, 0.0]),
            ("Flux", "BOXN", 12.0, [19.4, 15.0, 16.4, 19.3, 30.6]),
            ("Boiler Coke", "BOXN", 12.0, [17.6, 21.0, 23.5, 33.8, 42.1]),
            ("Hard Coke", "BOXN", 12.0, [0.0, 0.0, 26.2, 22.2, 29.8]),
        ], "total": ("Total Inward", [12.6, 13.8, 14.3, 18.7, 29.5])},
        "OUTWARD": {"direction": "E-L", "rows": [
            ("Outward Despatch", "BOST", 24.0, [32.5, 26.8, 25.9, 29.0, 32.7]),
            ("Outward Despatch", "BOXN", 24.0, [29.0, 40.9, 34.2, 31.8, 36.2]),
            ("Outward Despatch", "BRN", 24.0, [30.3, 27.4, 23.8, 23.4, 27.0]),
            ("Outward Despatch", "BFNS", 24.0, [43.5, 40.3, 36.8, 43.9, 40.5]),
        ], "total": ("Total Outward", [33.5, 29.4, 27.8, 30.8, 32.3])},
        "OVERALL": {"direction": None, "rows": [
            ("", "BOST", 34.0, [27.2, 21.98, 21.8, 26.9, 29.8]),
            ("", "BRN", 36.0, [23.1, 22.3, 21.9, 24.3, 26.6]),
            ("", "BFNS", 36.0, [43.5, 40.3, 36.8, 43.9, 40.5]),
            ("", "BOXN", 14.0, [20.2, 21.1, 22.4, 24.2, 37.3]),
            ("", "NBOY", 14.0, [0.0, 0.0, 0.0, 0.0, 0.0]),
            ("", "BOBS/N", 5.5, [4.6, 5.5, 6.0, 11.3, 15.9]),
        ], "total": ("Overall Wagon", [17.9, 18.27, 18.5, 23.1, 31.8])},
    },
    "BSL": {
        "INWARD": {"direction": "L-E", "rows": [
            ("Ind.Coking Coal", "BOXN/BOST", 12.0, [13.8, 14.2, 17.2, 23.7, 22.5]),
            ("Imp.Coking Coal", "BOXN", 12.0, [14.6, 14.6, 21.2, 20.7, 27.6]),
            ("Boiler Coal", "BOXN", 12.0, [16.9, 18.9, 21.0, 21.6, 23.2]),
            ("Iron Ore", "BOXN/BOY", 12.0, [9.4, 10.9, 15.2, 27.9, 26.3]),
            ("Flux", "BOXN", 12.0, [10.5, 10.3, 12.8, 11.7, 17.0]),
            ("Hard Coke", "BOXN", 12.0, [0.0, 15.2, 0.0, 0.0, 0.0]),
        ], "total": ("Total Inward", [11.8, 12.5, 16.5, 21.2, 25.5])},
        "OUTWARD": {"direction": "E-L", "rows": [
            ("Outward Despatch", "BOXN", 24.0, [19.3, 17.9, 18.2, 26.6, 24.9]),
            ("Outward Despatch", "BOST", 24.0, [26.7, 26.9, 25.6, 29.2, 28.7]),
            ("Outward Despatch", "BRN", 24.0, [26.0, 26.3, 29.8, 32.3, 28.4]),
            ("Outward Despatch", "BOSM", 24.0, [27.1, 23.8, 26.4, 30.3, 27.4]),
            ("Outward Despatch", "BFNS", 24.0, [26.8, 26.5, 26.0, 27.3, 28.3]),
        ], "total": ("Total Outward", [25.2, 23.6, 25.1, 29.5, 27.6])},
        "OVERALL": {"direction": None, "rows": [
            ("", "BOST", 34.0, [22.6, 22.1, 22.3, 28.9, 28.5]),
            ("", "BRN", 36.0, [23.6, 23.5, 27.8, 29.5, 26.2]),
            ("", "BOSM", None, [21.9, 14.6, 20.3, 28.9, 27.7]),
            ("", "BFNS", 36.0, [26.8, 26.5, 26.0, 27.3, 28.3]),
            ("", "BOXN", 14.0, [13.3, 13.8, 17.4, 18.6, 20.5]),
        ], "total": ("Overall Wagon", [15.0, 14.8, 18.4, 23.3, 26.1])},
    },
    "ISP": {
        "INWARD": {"direction": "L-E", "rows": [
            ("Ind. Coking Coal", "BOXN (BCME)", 12.0, [12.0, 13.0, 12.0, 14.6, 11.0]),
            ("Imp. Coking Coal", "BOXN (BCME)", 12.0, [14.0, 15.4, 15.0, 12.5, 15.4]),
            ("Boiler coal", "BOXN (BCME)", 12.0, [0.0, 0.0, 0.0, 0.0, 0.0]),
            ("Ind. Coking Coal", "BOXN (IISD) *", 5.0, [5.0, 5.0, 5.0, 0.0, 5.0]),
            ("Imp. Coking Coal", "BOXN (IISD) *", 5.0, [5.2, 5.5, 5.0, 6.2, 6.5]),
            ("Iron Ore", "BOXN (IISD) *", 5.0, [5.3, 5.3, 5.4, 8.4, 9.6]),
            ("Iron Ore", "BOBS/N (IISD) *", 2.0, [2.0, 2.0, 2.4, 5.4, 6.2]),
            ("Flux", "BOXN (IISD) *", 5.0, [5.2, 5.1, 5.4, 5.36, 6.4]),
            ("Coke Products", "BOXN (BCME)", 12.0, [20.4, 21.2, 19.3, 14.0, 0.0]),
        ], "total": ("Total Inward", [5.3, 5.3, 5.3, 6.4, 7.3])},
        "OUTWARD": {"direction": "E-L", "rows": [
            ("Outward Despatch", "BOST", 22.0, [20.4, 20.1, 19.1, 19.2, 20.3]),
            ("Outward Despatch", "BOXN", 22.0, [14.1, 13.4, 10.5, 13.1, 12.2]),
            ("Outward Despatch", "BRN", 22.0, [18.5, 24.1, 22.5, 20.04, 23.2]),
            ("Outward Despatch", "BFNS", 22.0, [0.0, 0.0, 23.0, 18.1, 23.2]),
        ], "total": ("Total Outward", [18.2, 18.4, 16.1, 17.2, 17.3])},
        "OVERALL": {"direction": None, "rows": [
            ("", "BOST", 36.0, [20.4, 20.1, 19.1, 19.2, 20.3]),
            ("", "BRN", 36.0, [18.5, 24.1, 22.5, 20.04, 23.2]),
            ("", "BFNS", None, [0.0, 0.0, 23.0, 18.1, 23.2]),
            ("", "BOXN", None, [15.1, 16.1, 12.5, 13.1, 13.2]),
            ("", "BOXN (NEW PLANT) *", 2.0, [5.3, 5.3, 5.3, 6.4, 7.3]),
            ("", "BOBS/N (NEW PLANT) *", 2.0, [2.0, 2.0, 2.4, 5.4, 6.2]),
        ], "total": ("Overall Wagon", [9.2, 8.3, 8.1, 9.4, 10.4])},
    },
}

# ── Page 4: closed-FY history (2021-22 .. 2025-26), 12 months each ────────
# {plant: {fy: [12 monthly values, Apr..Mar]}}
_MON_KEYS = ["04", "05", "06", "07", "08", "09", "10", "11", "12", "01", "02", "03"]


def _fy_month_keys(fy_start_year: int) -> list:
    y1, y2 = fy_start_year, fy_start_year + 1
    return [f"{y1}-{m}" for m in _MON_KEYS[:9]] + [f"{y2}-{m}" for m in _MON_KEYS[9:]]


TREND_HISTORY = {
    "BSP": {
        2025: [7.5, 7.5, 8.4, 11.4, 11.5, 10.3, 9.1, 8.2, 7.3, 7.1, 7.4, 7.5],
        2024: [7.4, 7.5, 7.4, 8.4, 8.3, 8.1, 8.1, 8.1, 8.3, 8.1, 7.4, 8.0],
        2023: [8.3, 7.6, 8.0, 8.1, 8.0, 9.1, 7.4, 8.2, 7.5, 7.3, 7.3, 7.5],
        2022: [12.3, 12.6, 13.4, 13.5, 14.1, 11.0, 12.2, 10.1, 9.1, 9.1, 8.4, 8.2],
        2021: [13.5, 12.6, 13.2, 13.0, 12.5, 13.4, 12.5, 13.3, 12.1, 11.4, 11.3, 12.5],
    },
    "DSP": {
        2025: [16.0, 18.0, 21.0, 20.0, 21.0, 23.0, 24.0, 18.0, 17.0, 16.0, 14.0, 14.0],
        2024: [18.0, 16.0, 19.0, 18.0, 25.0, 28.0, 25.0, 22.0, 19.0, 16.0, 16.0, 16.0],
        2023: [19.0, 21.0, 19.0, 19.0, 22.0, 20.0, 22.0, 19.0, 19.0, 19.0, 19.0, 18.0],
        2022: [20.0, 19.0, 22.0, 21.0, 26.0, 22.0, 24.0, 22.0, 20.0, 18.0, 16.0, 17.0],
        2021: [21.0, 23.0, 27.0, 27.0, 30.0, 29.0, 29.0, 25.0, 23.0, 21.0, 19.0, 19.0],
    },
    "RSP": {
        2025: [22.0, 21.3, 21.2, 26.4, 28.7, 32.8, 27.3, 23.2, 22.7, 19.7, 17.0, 16.8],
        2024: [25.1, 21.8, 20.5, 20.9, 23.4, 24.1, 22.8, 23.3, 21.8, 15.7, 17.1, 18.1],
        2023: [16.5, 16.1, 17.9, 19.8, 23.2, 23.6, 21.7, 17.9, 17.7, 17.7, 18.0, 19.0],
        2022: [20.6, 19.3, 20.9, 24.6, 23.7, 17.7, 18.0, 15.4, 15.4, 16.8, 15.9, 14.3],
        2021: [21.8, 21.1, 25.5, 25.3, 33.1, 36.2, 26.0, 18.3, 17.3, 16.7, 16.0, 19.0],
    },
    "BSL": {
        2025: [19.5, 18.1, 21.4, 28.9, 24.9, 25.1, 22.4, 18.9, 17.0, 15.9, 15.7, 15.6],
        2024: [15.7, 15.7, 15.2, 16.9, 22.0, 18.9, 19.9, 18.3, 17.4, 17.6, 17.4, 18.3],
        2023: [16.0, 14.7, 16.7, 17.8, 19.2, 19.3, 24.6, 15.0, 14.7, 15.5, 16.0, 16.3],
        2022: [16.3, 15.9, 17.6, 18.9, 20.6, 19.4, 20.3, 16.7, 15.2, 15.2, 15.4, 15.2],
        2021: [20.7, 23.6, 23.6, 23.1, 26.3, 25.3, 23.9, 21.0, 20.0, 18.5, 17.3, 16.5],
    },
    "ISP": {
        2025: [8.5, 10.3, 11.1, 11.1, 12.1, 12.1, 11.2, 12.4, 12.2, 11.1, 11.0, 9.5],
        2024: [10.1, 10.2, 10.0, 10.4, 11.3, 11.6, 11.0, 11.6, 10.0, 10.1, 10.1, 9.6],
        2023: [10.3, 10.3, 9.0, 10.4, 11.1, 10.2, 9.5, 9.3, 8.4, 8.5, 9.4, 10.0],
        2022: [10.9, 10.8, 9.7, 12.0, 12.4, 10.2, 9.5, 9.4, 10.4, 9.4, 9.4, 9.4],
        2021: [12.4, 12.3, 12.2, 12.1, 11.6, 11.8, 11.8, 12.2, 11.3, 10.7, 10.7, 10.3],
    },
    "SAIL": {
        2025: [15.1, 14.6, 15.8, 19.0, 19.1, 19.9, 18.2, 15.5, 14.6, 13.6, 12.6, 12.4],
        2024: [14.7, 13.6, 13.8, 14.4, 16.9, 16.9, 16.1, 16.4, 14.7, 12.8, 13.0, 13.3],
        2023: [13.3, 13.0, 13.5, 14.2, 15.7, 15.8, 16.3, 13.5, 13.2, 13.5, 13.2, 13.5],
        2022: [15.9, 15.4, 16.9, 18.0, 19.0, 15.6, 16.3, 14.0, 13.3, 13.2, 12.6, 12.1],
        2021: [17.9, 18.5, 19.8, 19.4, 21.9, 22.8, 19.9, 17.3, 16.1, 15.2, 14.3, 15.3],
    },
}

# {plant: {fy_label: annual_avg}} — page 4's own "APR-MAR" column, every FY
# shown including the still-open 2026-27 (its own reported figure, not a
# mean of the 5 months filled so far).
ANNUAL_DATA = {
    "BSP": {"2026-27": 8.6, "2025-26": 8.6, "2024-25": 7.9, "2023-24": 7.8, "2022-23": 11.0, "2021-22": 12.6},
    "DSP": {"2026-27": 14.2, "2025-26": 18.5, "2024-25": 19.9, "2023-24": 20.0, "2022-23": 20.6, "2021-22": 24.3},
    "RSP": {"2026-27": 21.0, "2025-26": 22.9, "2024-25": 21.2, "2023-24": 19.3, "2022-23": 18.5, "2021-22": 22.9},
    "BSL": {"2026-27": 19.2, "2025-26": 20.1, "2024-25": 17.9, "2023-24": 17.1, "2022-23": 17.2, "2021-22": 21.6},
    "ISP": {"2026-27": 8.9, "2025-26": 11.1, "2024-25": 10.5, "2023-24": 9.7, "2022-23": 10.3, "2021-22": 11.6},
    "SAIL": {"2026-27": 14.1, "2025-26": 15.8, "2024-25": 14.7, "2023-24": 14.0, "2022-23": 15.1, "2021-22": 18.1},
}

# ── Page 3: "Improvement in Average Detention per Wagon in Hrs" ───────────
# {period_row: {plant: value}} — CPLY rows are already % figures.
SUMMARY_DATA = {
    "CUR_MON_TY":      {"BSP": 11.41, "DSP": 16.00, "RSP": 31.83, "BSL": 26.09, "ISP": 10.39, "SAIL": 18.65},
    "CUR_MON_LY":      {"BSP": 11.47, "DSP": 21.00, "RSP": 28.68, "BSL": 24.91, "ISP": 12.09, "SAIL": 19.08},
    "CUR_MON_CPLY_PCT": {"BSP": 0.5, "DSP": 23.8, "RSP": -11.0, "BSL": -4.7, "ISP": 14.1, "SAIL": 2.2},
    "YTD_TY":          {"BSP": 8.63, "DSP": 14.18, "RSP": 21.00, "BSL": 19.23, "ISP": 8.95, "SAIL": 14.12},
    "YTD_LY":          {"BSP": 9.29, "DSP": 19.13, "RSP": 23.58, "BSL": 22.44, "ISP": 10.26, "SAIL": 16.67},
    "YTD_CPLY_PCT":    {"BSP": 7.1, "DSP": 25.9, "RSP": 11.0, "BSL": 14.3, "ISP": 12.8, "SAIL": 15.4},
    "FY_TY":           {"BSP": 8.60, "DSP": 18.53, "RSP": 22.99, "BSL": 20.09, "ISP": 11.05, "SAIL": 15.80},
    "FY_LY":           {"BSP": 7.93, "DSP": 19.85, "RSP": 21.22, "BSL": 17.89, "ISP": 10.45, "SAIL": 14.70},
    "FY_CPLY_PCT":     {"BSP": -8.4, "DSP": 6.6, "RSP": -8.4, "BSL": -12.3, "ISP": -5.8, "SAIL": -7.5},
}


def backfill():
    # Idempotency key is (plant, section, commodity, wagon_type_or_total_
    # label) — NOT (plant, section, row_label) alone: the same wagon_type
    # (e.g. "BOXN") legitimately repeats under several different commodities
    # within one plant/section (see BSP INWARD), so commodity has to be part
    # of the identity or those rows collide/overwrite each other.
    existing = db.get_rake_detention_master(active_only=False)
    existing_by_key = {
        (r["plant"], r["section"], r["commodity"], r["row_label"]): r["id"]
        for r in existing
    }

    _master_upsert_count = 0

    def _upsert_master(plant, section, commodity, wagon_type, row_label, is_total,
                        direction, freetime, sort_order):
        nonlocal _master_upsert_count
        key = (plant, section, commodity, row_label)
        row = {
            "id": existing_by_key.get(key),
            "plant": plant, "section": section,
            "commodity": commodity, "wagon_type": wagon_type,
            "row_label": row_label, "is_total": is_total,
            "direction": direction, "freetime_hours": freetime,
            "freetime_effective_from": "2022-09-01" if freetime else None,
            "sort_order": sort_order,
        }
        mid = db.save_rake_detention_master_row(row)
        existing_by_key[key] = mid
        _master_upsert_count += 1
        return mid

    # Note: keyed on (plant, section, wagon_type) alone — collapses the
    # handful of rows that legitimately share a wagon_type across different
    # commodities within one section (e.g. BSP INWARD's several "BOXN"
    # rows). Harmless here: nothing below reads it back for those keys,
    # only for each section's unique "Overall Wagon" total row.
    master_ids = {}
    monthly_rows = []

    for plant, sections in DETAIL_DATA.items():
        for section, spec in sections.items():
            sort_order = 0
            for commodity, wagon_type, freetime, values in spec["rows"]:
                sort_order += 1
                mid = _upsert_master(plant, section, commodity or None, wagon_type,
                                      wagon_type, False, spec["direction"], freetime, sort_order)
                master_ids[(plant, section, wagon_type)] = mid
                for month, val in zip(CUR_FY_MONTHS, values):
                    monthly_rows.append((month, mid, val))
            total_label, total_values = spec["total"]
            sort_order += 1
            mid = _upsert_master(plant, section, None, None, total_label, True,
                                  None, None, sort_order)
            master_ids[(plant, section, total_label)] = mid
            for month, val in zip(CUR_FY_MONTHS, total_values):
                monthly_rows.append((month, mid, val))

    # Add a SAIL-only "Overall Wagon" master row (SAIL has no detail rows on
    # pages 1-2 — it only ever appears as the aggregate column on pages 3-4).
    sail_overall_id = _upsert_master("SAIL", "OVERALL", None, None, "Overall Wagon", True,
                                      None, None, 1)
    master_ids[("SAIL", "OVERALL", "Overall Wagon")] = sail_overall_id
    # SAIL's own current-FY (2026-27) Apr-Aug monthly figures — page 4's SAIL
    # block, not derivable from any per-plant detail page (SAIL has none).
    for month, val in zip(CUR_FY_MONTHS, [12.7, 12.3, 12.5, 15.8, 18.7]):
        monthly_rows.append((month, sail_overall_id, val))

    for month, mid, val in monthly_rows:
        db.save_rake_detention_monthly(month, [{"master_id": mid, "value_hours": val}])
    print(f"Seeded {_master_upsert_count} master rows, {len(monthly_rows)} monthly (Apr-Aug'26) values.")

    # Page 4: older closed-FY history, for each plant's own "Overall Wagon"
    # master row (BSP/DSP/RSP/BSL/ISP from DETAIL_DATA's OVERALL total row,
    # SAIL from the standalone row just added above).
    overall_ids = {
        plant: master_ids[(plant, "OVERALL", "Overall Wagon")]
        for plant in ("BSP", "DSP", "RSP", "BSL", "ISP")
    }
    overall_ids["SAIL"] = sail_overall_id

    trend_rows = 0
    for plant, fys in TREND_HISTORY.items():
        mid = overall_ids[plant]
        for fy_start, values in fys.items():
            months = _fy_month_keys(fy_start)
            for month, val in zip(months, values):
                db.save_rake_detention_monthly(month, [{"master_id": mid, "value_hours": val}])
                trend_rows += 1
    print(f"Seeded {trend_rows} historical (FY2021-22..2025-26) trend values.")

    annual_rows = [
        {"plant": plant, "financial_year": fy, "avg_hours": val}
        for plant, fys in ANNUAL_DATA.items()
        for fy, val in fys.items()
    ]
    db.save_rake_detention_annual(annual_rows)
    print(f"Seeded {len(annual_rows)} annual (APR-MAR) figures.")

    summary_rows = [
        {"period_row": period, "plant": plant, "value": val}
        for period, plants in SUMMARY_DATA.items()
        for plant, val in plants.items()
    ]
    db.save_rake_detention_summary(REPORT_MONTH, summary_rows)
    print(f"Seeded {len(summary_rows)} summary (Improvement table) values for {REPORT_MONTH}.")


if __name__ == "__main__":
    backfill()
