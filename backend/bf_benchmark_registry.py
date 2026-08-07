"""
Large BF Benchmarking — parameter and BF registry.

Single source of truth for the columns the /reports/bf-benchmark comparison
page and /data-entry/bf-benchmark entry page show. Adding a new comparison
parameter later is one more entry in BF_BENCHMARK_PARAMS — bf_benchmark_
external_data.param_json is a free-form JSON blob, so no migration is
needed; SAIL-side params must additionally exist as a techno_data key (see
techno_registry.py) to have real data behind them.

Param keys are snake_case and match techno_registry/techno_cumulative's
existing keys exactly, so SAIL-side lookups need no translation.
"""

from techno_registry import UNIT

# Fixed SAIL BFs this feature compares — not admin-addable, unlike non-SAIL
# BFs (bf_benchmark_external_bf). Their monthly operating data already lives
# in techno_data; only Working Volume is tracked separately (bf_benchmark_
# sail_meta), since it's a static engineering spec, not a monthly figure.
SAIL_BFS = [
    {"plant": "BSP", "unit": "BF-8", "label": "BSP BF-8"},
    {"plant": "RSP", "unit": "BF-5", "label": "RSP BF-5"},
    {"plant": "ISP", "unit": "BF-5", "label": "ISP BF-5"},
]

# Comparison parameters shown as columns, in display order. `static=True`
# means the value is a per-BF constant (edited via the BF's registry row /
# sail-meta, not entered monthly). `key` for non-static params must be a
# key techno_data actually stores for SAIL BFs to have any figure show up —
# see techno_registry.py's per-plant extractor mapping for what's captured
# today (BSP BF-8 is missing coke_rate/fuel_rate/slag_rate/hot_blast_temp
# per-furnace — those cells show blank for BSP, by design, not a bug).
BF_BENCHMARK_PARAMS = [
    {"key": "working_volume_m3", "label": "Working Volume", "unit": "m³", "static": True},
    {"key": "bf_productivity", "label": "BF Productivity", "unit": UNIT.T_M3_DAY, "static": False},
    {"key": "coke_rate", "label": "Coke Rate", "unit": UNIT.KG_THM, "static": False},
    {"key": "nut_coke_rate", "label": "Nut Coke Rate", "unit": UNIT.KG_THM, "static": False},
    {"key": "cdi", "label": "CDI Rate", "unit": UNIT.KG_THM, "static": False},
    {"key": "fuel_rate", "label": "Fuel Rate", "unit": UNIT.KG_THM, "static": False},
    {"key": "slag_rate", "label": "Slag Rate", "unit": UNIT.KG_THM, "static": False},
    {"key": "hot_blast_temp", "label": "HBT", "unit": UNIT.DEG_C, "static": False},
    {"key": "o2_enrichment", "label": "O2 Enrichment", "unit": UNIT.PCT, "static": False},
]

# Weighting-only input, collected for non-SAIL BFs alongside the params
# above but never shown as its own comparison column — mirrors what
# production_table already supplies for SAIL BFs (see techno_cumulative.py).
HM_PRODUCTION_KEY = "hot_metal_production"

DYNAMIC_PARAM_KEYS = [p["key"] for p in BF_BENCHMARK_PARAMS if not p["static"]]
STATIC_PARAM_KEYS = [p["key"] for p in BF_BENCHMARK_PARAMS if p["static"]]
PARAM_BY_KEY = {p["key"]: p for p in BF_BENCHMARK_PARAMS}
