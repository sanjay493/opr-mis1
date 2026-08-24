"""
One-off validation (read-only, no DB writes): checks whether each plant's
and SAIL 5 ISPs' "Annual 25-26" Cost Trend figure (VARIABLE/FIXED, for HM/
CS/SS) is consistent with a production-weighted average, per direct
instruction:

  - Per-plant Annual 25-26 vs a production-weighted average of that plant's
    own FY25-26 monthly costs (weighted by that plant's own monthly
    production of the same product) — reconstructs the annual figure
    "bottom-up" from the monthly trend, as a plausibility check.
  - SAIL 5 ISPs Annual 25-26 vs a production-weighted average of the 5
    plants' own Annual 25-26 costs, weighted by each plant's FY25-26 annual
    production of the same product.

FY25-26 monthly costs come from Report_format/COST TREND 2026-27 OF HM CS
SS 10.08.2026.pdf (via backfill_cost_trend_202608.DATA) — Oct/Nov/Dec'25
aren't broken out individually there (only their Q3 aggregate is), so that
quarter is treated as one weighted bucket (Q3 cost weighted by summed Q3
production) rather than 3 separate months.

Production weights come from production_table (item_name 'Hot Metal' /
'Total Crude Steel' / 'Saleable Steel'), which does have full monthly
granularity for FY25-26.

This does NOT write anything to cost_trend_annual — SAIL stays a directly-
entered figure (see db.py's COST_TREND_ENTRY_PLANTS docstring); this is a
plausibility check on the figures actually entered.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import db
from backfill_cost_trend_202608 import DATA, PLANTS

ITEM_NAME = {"HM": "Hot Metal", "CS": "Total Crude Steel", "SS": "Saleable Steel"}
PRODUCT_LABEL = {"HM": "Hot Metal", "CS": "Crude Steel", "SS": "Saleable Steel"}

# (label, cost-row index, production report_months to sum for the weight)
MONTH_BUCKETS = [
    ("Apr'25", 5, ["2025-04"]),
    ("May'25", 6, ["2025-05"]),
    ("Jun'25", 7, ["2025-06"]),
    ("Jul'25", 9, ["2025-07"]),
    ("Aug'25", 10, ["2025-08"]),
    ("Sep'25", 11, ["2025-09"]),
    ("Q3(O-D'25)", 14, ["2025-10", "2025-11", "2025-12"]),
    ("Jan'26", 16, ["2026-01"]),
    ("Feb'26", 17, ["2026-02"]),
    ("Mar'26", 18, ["2026-03"]),
]
ANNUAL_2526_IDX = 20


def get_production(plant: str, item: str, months: list) -> float:
    conn = db.connect()
    cur = conn.cursor()
    ph = ",".join("?" * len(months))
    cur.execute(
        f"SELECT SUM(month_actual) FROM production_table WHERE plant_name=? AND item_name=? AND report_month IN ({ph})",
        (plant, item, *months),
    )
    row = cur.fetchone()
    conn.close()
    return float(row[0]) if row and row[0] is not None else 0.0


def weighted_avg(costs_weights: list) -> "float | None":
    num = sum(c * w for c, w in costs_weights)
    den = sum(w for _, w in costs_weights)
    return (num / den) if den else None


def validate_plant_annual(tolerance_pct=2.0):
    print("=" * 100)
    print("PER-PLANT: Annual 25-26 vs production-weighted average of own FY25-26 monthly costs")
    print("=" * 100)
    flags = []
    for product in ("HM", "CS", "SS"):
        item = ITEM_NAME[product]
        for cost_type in ("VARIABLE", "FIXED"):
            for plant in PLANTS[:-1]:  # exclude SAIL here
                row = DATA[product][cost_type][plant]
                reported_annual = row[ANNUAL_2526_IDX]
                cw = []
                for label, idx, months in MONTH_BUCKETS:
                    prod = get_production(plant, item, months)
                    cw.append((row[idx], prod))
                wavg = weighted_avg(cw)
                if wavg is None:
                    continue
                delta_pct = abs(wavg - reported_annual) / reported_annual * 100
                flag = " <-- MISMATCH" if delta_pct > tolerance_pct else ""
                if flag:
                    flags.append((product, cost_type, plant, reported_annual, wavg, delta_pct))
                print(f"{PRODUCT_LABEL[product]:>13} {cost_type:>8} {plant:>4}: "
                      f"reported={reported_annual:>8.0f}  weighted-avg={wavg:>9.1f}  "
                      f"delta={delta_pct:5.2f}%{flag}")
    return flags


def validate_sail_annual(tolerance_pct=2.0):
    print()
    print("=" * 100)
    print("SAIL 5 ISPs: Annual 25-26 vs production-weighted average of the 5 plants' Annual 25-26 costs")
    print("=" * 100)
    flags = []
    for product in ("HM", "CS", "SS"):
        item = ITEM_NAME[product]
        for cost_type in ("VARIABLE", "FIXED"):
            cw = []
            for plant in PLANTS[:-1]:
                cost = DATA[product][cost_type][plant][ANNUAL_2526_IDX]
                prod = get_production(plant, item, [f"2025-{m:02d}" for m in range(4, 13)]
                                       + [f"2026-{m:02d}" for m in range(1, 4)])
                cw.append((cost, prod))
            wavg = weighted_avg(cw)
            reported_sail = DATA[product][cost_type]["SAIL"][ANNUAL_2526_IDX]
            delta_pct = abs(wavg - reported_sail) / reported_sail * 100
            flag = " <-- MISMATCH" if delta_pct > tolerance_pct else ""
            if flag:
                flags.append((product, cost_type, "SAIL", reported_sail, wavg, delta_pct))
            print(f"{PRODUCT_LABEL[product]:>13} {cost_type:>8} SAIL: "
                  f"reported={reported_sail:>8.0f}  weighted-avg={wavg:>9.1f}  "
                  f"delta={delta_pct:5.2f}%{flag}")
    return flags


if __name__ == "__main__":
    plant_flags = validate_plant_annual()
    sail_flags = validate_sail_annual()

    print()
    print("=" * 100)
    print(f"SUMMARY: {len(plant_flags)} per-plant mismatch(es) > 2%, {len(sail_flags)} SAIL mismatch(es) > 2%")
    print("=" * 100)
    for f in plant_flags + sail_flags:
        print(" ", f)
