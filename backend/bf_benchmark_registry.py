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
# per-furnace — those cells show blank for BSP, by design, not a bug). Some
# of the params below (carbon_rate, blast_pressure, cold_blast_volume,
# top_pressure, steam_addition, raw_flux_addition, raft, total_heat_loss)
# have NO extractor writing them for any SAIL plant today — they're mapped
# here per explicit request so the column exists and non-SAIL BFs can still
# enter them by hand; SAIL's own cells just stay blank until an extractor
# is written for them.
#
# `better`: which direction counts as the best value in a row, for the
# comparison table's per-row highlight — "low" for coke_rate/nut_coke_rate/
# fuel_rate/slag_rate (per direct instruction), "high" for every other
# performance param, None for params that aren't a performance ranking
# (working_volume_m3 is a fixed engineering spec, not something to rank).
#
# `computed`: True means the value is never read/entered directly — it's
# derived from other params in this same row set (see
# bf_benchmark_registry.compute_fuel_rate).
BF_BENCHMARK_PARAMS = [
    {"key": "working_volume_m3", "label": "Working Volume", "unit": "m³", "static": True, "better": None},
    {"key": "production", "label": "Production", "unit": UNIT.T, "static": False, "better": "high"},
    {"key": "bf_productivity", "label": "BF Productivity", "unit": UNIT.T_M3_DAY, "static": False, "better": "high"},
    {"key": "coke_rate", "label": "Coke Rate", "unit": UNIT.KG_THM, "static": False, "better": "low"},
    {"key": "nut_coke_rate", "label": "Nut Coke Rate", "unit": UNIT.KG_THM, "static": False, "better": "low"},
    {"key": "cdi", "label": "CDI Rate", "unit": UNIT.KG_THM, "static": False, "better": "high"},
    {"key": "fuel_rate", "label": "Fuel Rate", "unit": UNIT.KG_THM, "static": False, "better": "low", "computed": True},
    {"key": "carbon_rate", "label": "Carbon Rate", "unit": UNIT.KG_THM, "static": False, "better": "high"},
    {"key": "slag_rate", "label": "Slag Rate", "unit": UNIT.KG_THM, "static": False, "better": "low"},
    {"key": "hot_blast_temp", "label": "HBT", "unit": UNIT.DEG_C, "static": False, "better": "high"},
    {"key": "o2_enrichment", "label": "O2 Enrichment", "unit": UNIT.PCT, "static": False, "better": "high"},
    {"key": "avg_hot_metal_temperature", "label": "Hot Metal Temperature", "unit": UNIT.DEG_C, "static": False, "better": "high"},
    {"key": "blast_pressure", "label": "Blast Pressure", "unit": "kg/cm²", "static": False, "better": "high"},
    {"key": "cold_blast_volume", "label": "Cold Blast Volume", "unit": UNIT.NM3_MIN, "static": False, "better": "high"},
    {"key": "top_pressure", "label": "Top Pressure", "unit": "kg/cm²", "static": False, "better": "high"},
    {"key": "steam_addition", "label": "Steam Addition", "unit": UNIT.KG_THM, "static": False, "better": "high"},
    {"key": "sinter_in_burden", "label": "Sinter in Burden", "unit": UNIT.PCT, "static": False, "better": "high"},
    {"key": "pellet_in_burden", "label": "Pellet in Burden", "unit": UNIT.PCT, "static": False, "better": "high"},
    {"key": "lump_in_burden", "label": "Lump in Burden", "unit": UNIT.PCT, "static": False, "better": "high"},
    # Both added backfilling Report_format/Large BFs for OMI.xlsx's Non-SAIL
    # data — that source has a Coke Ash and a Sinter Fe row (same concepts
    # the SAIL annexure page already shows, page_bf_large_annexure.py's
    # _coke_ash_and_sinter_fe), but neither existed here yet, so a non-SAIL
    # BF had nowhere to enter them. Same key names as the SAIL side uses
    # (ash_in_coke, tfe_in_sinter) — no translation needed either direction.
    {"key": "ash_in_coke", "label": "Coke Ash", "unit": UNIT.PCT, "static": False, "better": "low"},
    {"key": "tfe_in_sinter", "label": "Sinter Fe", "unit": UNIT.PCT, "static": False, "better": "high"},
    {"key": "raw_flux_addition", "label": "Raw Flux Addition", "unit": UNIT.KG_THM, "static": False, "better": "high"},
    {"key": "silicon_in_hm", "label": "HM Silicon", "unit": UNIT.PCT, "static": False, "better": "high"},
    {"key": "sulphur_in_hm", "label": "HM Sulphur", "unit": UNIT.PCT, "static": False, "better": "high"},
    {"key": "raft", "label": "RAFT", "unit": UNIT.DEG_C, "static": False, "better": "high"},
    {"key": "total_heat_loss", "label": "Total Heat Loss", "unit": "Kcal/THM", "static": False, "better": "high"},

    # Added for the Large BFs (SAIL vs Non-SAIL) annexure report page — see
    # page_bf_large_annexure.py. No SAIL extractor writes any of these today
    # (same "blank until entered" situation as top_pressure/steam_addition/
    # etc. above); for the 3 SAIL BFs, entered via the Techno Manual Entry
    # form's BF-8/BF-5 tabs (technoParamRegistry.js's Blast Furnace
    # template), which write into the same per-BF techno_data unit
    # (BF-8/BF-5) these keys are read from here. avg_burden_fe is the one
    # exception for SAIL: page_bf_large_annexure.py computes it live from
    # the burden-mix and Fe-assay rows instead of reading a stored value —
    # this key still matters here for non-SAIL BFs' own entry grid below,
    # which has no such formula and enters it directly.
    {"key": "lump_ore_fe", "label": "Lump Ore Fe", "unit": UNIT.PCT, "static": False, "better": "high"},
    {"key": "pellet_fe", "label": "Pellet Fe", "unit": UNIT.PCT, "static": False, "better": "high"},
    {"key": "avg_burden_fe", "label": "Avg. Burden Fe", "unit": UNIT.PCT, "static": False, "better": "high"},
    # Distinct from steam_addition (Kg/THM, a per-tonne rate) above — this is
    # an hourly flow figure, the unit the Excel source uses for this row.
    {"key": "steam_rate_hr", "label": "Steam Rate", "unit": UNIT.T_HR, "static": False, "better": None},
    {"key": "slag_mgo", "label": "Slag MgO", "unit": UNIT.PCT, "static": False, "better": None},
    {"key": "slag_al2o3", "label": "Slag Al2O3", "unit": UNIT.PCT, "static": False, "better": None},
    {"key": "slag_b2", "label": "Slag B2", "unit": UNIT.RATIO, "static": False, "better": None},
    {"key": "eta_co", "label": "Eta CO", "unit": UNIT.PCT, "static": False, "better": "high"},
    # Distinct from total_heat_loss (Kcal/THM, a per-tonne rate) above —
    # this is an hourly figure, the unit the Excel source uses for this row.
    {"key": "heat_load_flux", "label": "Heat Load/Flux", "unit": "MJ/hr", "static": False, "better": "low"},
    {"key": "tapping_duration", "label": "Tapping Duration", "unit": UNIT.HRS, "static": False, "better": None},
    # "furnace_availability" is an alias — ISP's own techno upload already
    # writes it under that name (see KEY_ALIASES below); every other plant
    # has nothing under either name yet.
    {"key": "availability", "label": "Fce Availability", "unit": UNIT.PCT, "static": False, "better": "high"},
    {"key": "utilisation", "label": "Fce Utilisation", "unit": UNIT.PCT, "static": False, "better": "high"},
]

# key -> [alternate techno_data key names already in use for that concept
# under some plant's BF unit] — checked in listed order, first match wins.
# Only needed where a plant's existing extractor already writes the same
# concept under a different name than this registry's own key.
KEY_ALIASES = {
    "availability": ["furnace_availability"],
    "utilisation": ["furnace_utilisation"],
}

# Fuel Rate is not entered/stored directly — always the sum of Coke Rate,
# CDI and Nut Coke Rate (per direct instruction). Coke Rate and CDI are
# required; Nut Coke Rate is optional and defaults to 0 if absent — same
# rule db._maybe_recompute_derived_params already applies when SAIL's own
# techno_data is saved (its _FUEL_RATE_INPUT_KEYS), kept identical here so
# this feature's number always matches what the rest of the app computes.
# Shared by the SAIL lookup (api_bf_benchmark._sail_period_values) and the
# non-SAIL lookup (_external_bf_values) so both sides compute it the same
# way, and by the data-entry page (read-only display) via the /params
# response's `computed: True` flag.
def compute_fuel_rate(values: dict) -> "float | None":
    coke, cdi = values.get("coke_rate"), values.get("cdi")
    if coke is None or cdi is None:
        return None
    nut = values.get("nut_coke_rate") or 0
    return round(coke + nut + cdi, 4)


DYNAMIC_PARAM_KEYS = [p["key"] for p in BF_BENCHMARK_PARAMS if not p["static"]]
STATIC_PARAM_KEYS = [p["key"] for p in BF_BENCHMARK_PARAMS if p["static"]]
PARAM_BY_KEY = {p["key"]: p for p in BF_BENCHMARK_PARAMS}
