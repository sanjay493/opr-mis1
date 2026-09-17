"""
One-off backfill: "Movement of Key Prices - International" and "India Macro
Economic Indicators" (pages 2.41/2.42), scraped from the single sample file
at I:\\My Drive\\Report_format\\work\\"DC-2 pages.pdf" (a BigMint market-
intelligence snapshot, read/transcribed by hand rather than PDF-table-
parsed — a one-time source with no plan to ever be re-uploaded in this
exact form, so a bespoke PDF-layout parser would be pure one-shot effort
for no future benefit; the values below are transcribed directly from that
file's own chart labels/table cells).

Market prices: 3 Raw Materials series read Jan'26-31st Aug (8 months,
CAPTIVE - CAPTIVE, USD/T), 4 Finished Steel series read Sep'25-25th Aug (12
months, USD/T) — see page_market_prices.py's own docstring for why each
starts where it does (Raw Materials tracking apparently only began Jan'26;
Finished Steel already had a full trailing 12).

Macro indicators: 14 rows, Jul'25-Jul'26 (13 months) — see
page_macro_indicators.py's METRIC_CODES for the row registry.

Usage:
  python scripts/backfill_market_intel.py            # dry-run
  python scripts/backfill_market_intel.py --apply     # writes to the live DB

Dry-run is the default on purpose — this touches the live MySQL DB
(DB_ENGINE=mysql), so the values should be reviewed before anything is
written.
"""
import argparse
import os
import sys

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BACKEND_DIR)

import db  # noqa: E402

# ---------------------------------------------------------------------------
# Market prices — {series_code: {report_month: value}}
# ---------------------------------------------------------------------------

_RAW_MATERIALS_MONTHS = ["2026-01", "2026-02", "2026-03", "2026-04", "2026-05", "2026-06", "2026-07", "2026-08"]
_FINISHED_STEEL_MONTHS = ["2025-09", "2025-10", "2025-11", "2025-12", "2026-01", "2026-02",
                          "2026-03", "2026-04", "2026-05", "2026-06", "2026-07", "2026-08"]

_MARKET_PRICE_ROWS = {
    "premium_hcc_aus_cnf_paradip":           dict(zip(_RAW_MATERIALS_MONTHS, [247, 263, 250, 255, 264, 265, 251, 291])),
    "iron_ore_fines_aus_cfr_china_fe61":     dict(zip(_RAW_MATERIALS_MONTHS, [107, 99, 106, 107, 109, 101, 98, 98])),
    "iron_ore_fines_india_fob_paradip_fe57": dict(zip(_RAW_MATERIALS_MONTHS, [67, 62, 61, 63, 62, 55, 55, 58])),
    "hrc_fob_rizhao_china":       dict(zip(_FINISHED_STEEL_MONTHS, [478, 464, 464, 468, 470, 465, 481, 505, 518, 516, 498, 495])),
    "hrc_cfr_antwerp_europe":     dict(zip(_FINISHED_STEEL_MONTHS, [598, 594, 576, 570, 561, 616, 620, 699, 698, 679, 645, 670])),
    "hrc_cfr_west_coast_india":   dict(zip(_FINISHED_STEEL_MONTHS, [503, 489, 489, 493, 495, 494, 511, 535, 548, 546, 528, 525])),
    "rebars_exw_donghua_china":   dict(zip(_FINISHED_STEEL_MONTHS, [452, 437, 440, 439, 442, 436, 444, 456, 477, 457, 448, 454])),
}

# ---------------------------------------------------------------------------
# Macro indicators — {metric_code: {report_month: value}}
# ---------------------------------------------------------------------------

_MACRO_MONTHS = ["2025-07", "2025-08", "2025-09", "2025-10", "2025-11", "2025-12",
                 "2026-01", "2026-02", "2026-03", "2026-04", "2026-05", "2026-06", "2026-07"]

_MACRO_ROWS = {
    "crude_steel_prod":    [14, 14.09, 13.56, 13.56, 13.71, 14.79, 15.15, 14.07, 15.32, 13.83, 14.08, 14.1, 14.3],
    "pig_iron_prod":       [0.68, 0.72, 0.68, 0.65, 0.67, 0.71, 0.71, 0.65, 0.68, 0.73, 0.79, 0.77, 0.8],
    "steel_exports":       [0.56, 0.67, 0.72, 0.72, 0.88, 0.82, 0.81, 0.73, 0.77, 0.64, 0.66, 0.90, 0.80],
    "steel_imports":       [0.85, 0.70, 0.79, 0.69, 0.60, 0.64, 0.52, 0.57, 0.52, 0.67, 0.63, 0.67, 0.50],
    "iron_ore_imports":    [1.82, 1.12, 1.00, 1.09, 0.97, 1.49, 0.63, 0.89, 1.11, 0.98, 1.24, 1.15, 0.59],
    "coal_prod":           [64.86, 69.86, 68.18, 77.45, 92.69, 101.44, 107.98, 100.51, 113.67, 74.31, 78.128, 80, 69.8],
    "coal_imports":        [21.33, 20.03, 23.37, 20.27, 21.45, 19.8, 20.3, 18.83, 22.57, 21.7, 22.8, 20.4, 20.0],
    "auto_prod":           [2.69, 2.69, 3.27, 3.2, 3.04, 3.03, 3.21, 3.14, 2.97, 2.92, 2.92, 3.00, 3.4],
    "auto_sales":          [2.05, 2.31, 2.69, 2.85, 2.52, 2.09, 2.54, 2.47, 2.6, 2.47, 2.41, 2.32, 2.5],
    "power_consumption":   [4.96, 4.85, 4.86, 4.26, 4.12, 4.47, 4.6, 4.75, 4.82, 5.13, 5.32, 5.50, 5.5],
    "merchandise_exports": [37.2, 35.1, 36.38, 34.38, 38.13, 38.5, 36.56, 36.61, 38.92, 43.56, 45.2, 40.4, 44.2],
    "ev_registrations":    [1.9, 1.89, 1.84, 2.37, 2.19, 2.03, 2.19, 1.98, 2.8, 2.39, 2.64, 3.05, 3.2],
    "gst_collections":     [1.96, 1.86, 1.89, 1.96, 1.75, 1.75, 1.93, 1.83, 2, 2.43, 1.94, 1.95, 2.1],
    "manufacturing_pmi":   [59.1, 59.3, 57.7, 59.2, 57.4, 55, 55.4, 57.5, 53.9, 54.7, 55, 54.2, 53.5],
}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true",
                        help="Actually write to the live DB. Default is a dry-run.")
    args = parser.parse_args()

    price_rows = [
        {"report_month": rm, "series_code": series, "value": val}
        for series, by_month in _MARKET_PRICE_ROWS.items()
        for rm, val in by_month.items()
    ]
    macro_rows = [
        {"report_month": rm, "metric_code": code, "value": val}
        for code, values in _MACRO_ROWS.items()
        for rm, val in zip(_MACRO_MONTHS, values)
    ]

    print(f"Market price rows: {len(price_rows)} ({len(_MARKET_PRICE_ROWS)} series)")
    print(f"Macro indicator rows: {len(macro_rows)} ({len(_MACRO_ROWS)} metrics x {len(_MACRO_MONTHS)} months)")

    if not args.apply:
        print("\nDry-run only — nothing written. Re-run with --apply to save.")
        return

    n1 = db.save_market_price_trend(price_rows)
    n2 = db.save_macro_indicators(macro_rows)
    print(f"\nSaved {n1} market price rows and {n2} macro indicator rows.")


if __name__ == "__main__":
    main()
