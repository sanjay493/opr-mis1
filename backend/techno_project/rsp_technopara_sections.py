"""Declarative section/parameter registry for the RSP technopara techno sheet
(page-1-8), replacing the old hardcoded-row-number rsp_technopara_map.json.

The sheet is a sequence of unit sections, each starting with a title row
(column A = section name, e.g. "SINTER PLANT-I"; column B usually blank)
followed by that unit's parameter rows (column A = label, column B = a
unit-of-measure string). A handful of Blast-Furnace blocks pack all four
furnaces (BF-1/BF-4/BF-5/BF_Shop) into consecutive rows under one section
header instead — some with the furnace already encoded in the label text
(handled as ordinary PARAM_ALIASES entries with an explicit unit override),
others with a generic, repeating per-furnace label that's only disambiguated
by position (handled via FURNACE_BLOCKS below).

All keys below are RAW label text exactly as it appears in a real sample
file — never hand-normalized — because normalization (rsp_row_scan._norm,
lowercase + collapse every run of non-alnum chars to one space) is easy to
get subtly wrong by hand (e.g. "Coke Rate -BF#1" normalizes to
"coke rate bf 1", WITH a space before the digit, not "bf1"). Both the
registry keys and the sheet's cell text are normalized the same way at
lookup time in the extractor, so a raw copy-paste from the sheet always
matches correctly.

To extract a new parameter:
  - If it lives under a section already listed in SECTION_UNITS, add one
    entry to PARAM_ALIASES: raw label -> param_key (uses that section's
    unit), or -> (unit, param_key) to target a different unit (e.g. a
    "General" metric that happens to sit inside another section).
  - If its section doesn't exist yet, add the section title (raw text) to
    SECTION_UNITS first.
  - If it's a new per-furnace block like O2 Enrichment/Hot Blast Temp, add
    an entry to FURNACE_BLOCKS instead (anchor text + fixed row offsets).
"""

# Section-title text (raw, normalized at lookup time) -> canonical unit name.
# A section header updates "current unit" for every following row until the
# next header.
SECTION_UNITS = {
    "BATTERY - (1-5)":        "COB-old",
    "BATTERY - 6":            "COB-new",
    "COAL CHEMICALS":         "COB-new",   # byproduct-recovery rows for Battery 6
    "SINTER PLANT-I":         "SP-1",
    "SINTER PLANT - II":      "SP-2",
    "SINTER PLANT - III":     "SP-3",
    "BLAST FURNACES":         None,        # not itself a DB unit — every row
                                            # inside needs an explicit unit
                                            # (PARAM_ALIASES tuple form) or a
                                            # FURNACE_BLOCKS entry
    "STEEL MELTING SHOP-I":   "SMS-1",
    "STEEL MELTING SHOP-II":  "SMS-2",
    "PLATE MILL":             "PM",
    "NEW PLATE MILL":         "NPM",
    "HOT STRIP MILL-2":       "HSM-2",
    "SILICON STEEL MILL":     "SSM",
    "ERW PIPE PLANT":         "ERW",
    "SW PIPE PLANT":          "SWP",
    "HEAT CONS.PER T OF":     "General",   # per-ton-of-X heat table — default
                                            # unit General, individual mill
                                            # rows override below
    "ELECT.CONS.PER T OF":    "General",   # same, for the electricity table
    "GENERAL":                "General",
}

# raw label -> param_key (uses current section's unit)
#           -> (unit, param_key)  (explicit override — label lives in a
#                                  different section than its true unit)
PARAM_ALIASES = {
    # ---- COB-old (Battery 1-5) / COB-new (Battery 6) ------------------------
    # "H/Coke Yield(+25mm)" appears twice per section (a "T / Oven" row and a
    # "% dry coal" row) — see PARAM_UNIT_FILTERS below, which restricts this
    # alias to the "% dry coal" occurrence only (the one the old row-number
    # map targeted).
    "H/Coke Yield(+25mm)":             "bf_coke_yield",
    "COG Yield on dry Coal":           "coke_oven_gas_yield",
    "Dry Coal Charge":                 "dry_coal_charge_oven",
    "Crude Tar Yield ":                ("COB-new", "crude_tar_yield"),
    "Amm.Sulph.Yield ":                ("COB-new", "ammonium_sulphate_yield"),

    # ---- Sinter Plant I/II/III (same aliases, current section supplies unit) -
    "Specific productivity":           "specific_productivity",
    "LD Slag Cons.":                   "ld_slag_cons",
    "Basicity  (CaO/ SiO2)":           "basicity",
    "Plant Return Fines":              "return_fines",

    # ---- Blast Furnaces — label already encodes the furnace ------------------
    "Productivity - BF #1":            ("BF-1", "bf_productivity"),
    "Productivity - BF #4":            ("BF-4", "bf_productivity"),
    "Productivity - BF #5":            ("BF-5", "bf_productivity"),
    "Productivity - (Shop)":           ("BF_Shop", "bf_productivity"),
    "Coke Rate -BF#1":                 ("BF-1", "coke_rate"),
    "Coke Rate    BF#4":               ("BF-4", "coke_rate"),
    "Coke Rate  BF#5":                 ("BF-5", "coke_rate"),
    "Coke Rate SHOP":                  ("BF_Shop", "coke_rate"),
    "BF#1 PCI(Dry)":                   ("BF-1", "cdi"),
    "BF#4 PCI(Dry)":                   ("BF-4", "cdi"),
    "BF#5 PCI(Dry)":                   ("BF-5", "cdi"),
    "PCI - Shop":                      ("BF_Shop", "cdi"),
    "N/C --BF- 1":                     ("BF-1", "nut_coke_rate"),
    "N/C --BF- 4":                     ("BF-4", "nut_coke_rate"),
    "N/C --BF- 5":                     ("BF-5", "nut_coke_rate"),
    "N/C -SHOP":                       ("BF_Shop", "nut_coke_rate"),
    "Coal to H M Ratio ":              ("General", "coal_to_hm"),
    "Sinter in Burden":                ("BF_Shop", "sinter_in_burden"),
    "Pellet Burden":                   ("BF_Shop", "pellet_in_burden"),

    # ---- SMS-1 / SMS-2 (same aliases, current section supplies unit) ---------
    "Converter Avail. % on":           "converter_availability",
    "Conv.Utilisation% on":            "converter_utilisation",
    "Hot Metal Cons.":                 "specific_hm_consumption",
    "Scrap Consumption":               "specific_scrap_consumption",
    "Ferro- Mn Consmn LC":             "fe-mn",       # SMS-1 spelling
    "Ferro- Mn Cons.(LC)":             "fe-mn",       # SMS-2 spelling
    "Ferro Silicon Consmn":            "fe-si",
    "Silico -Mn Cons.":                "si-mn",       # SMS-1 spelling
    "Silico- Mn Cons.":                "si-mn",       # SMS-2 spelling
    "Tap to Tap time":                 "tap_to_tap_time",
    "Avg. Lining Life":                "average_lining_life",
    "Oxygen Consmn.(LD)":              "oxygen_blowing",   # SMS-1
    "Oxygen Cons.(BOF II)":            "oxygen_blowing",   # SMS-2
    "Caster Yield":                    "caster_yield",
    "Blow Weight ":                    "average_heat_weight",   # SMS-1 (trailing space)
    "Blow Weight":                     "average_heat_weight",   # SMS-2
    "Blow SMS1":                       "average_blows_per_day",
    "Blow SMS2":                       "average_blows_per_day",

    # ---- Plate Mill / New Plate Mill (same aliases per-section) ---------------
    "Yield - Primes":                  "yield_prime",
    "Yield - Total":                   "yield_total",
    "Average Slab Weight":             "average_slab_weight",
    "Mill Availability":               "availability",
    "Util. on Avail. Time":            "utilisation",
    "Rolling Rate-PLATE":              "rolling_rate",
    "Old Plates Production":           ("PM", "specific_power_consumption"),
    "New Plates Production":           ("NPM", "specific_power_consumption"),
    "Slabs Rolled- PM":                ("PM", "specific_heat_consumption"),
    "Slabs Rolled- NPM":               ("NPM", "specific_heat_consumption"),

    # ---- Hot Strip Mill-2 -------------------------------------------------------
    "H R Coil Yield":                  "yield_total",
    "Mill Availability on Cal Hrs":    "availability",
    "Utilisation on Avail. Hrs":       "utilisation",
    "Rolling Rate -HR Coils":          "rolling_rate",
    "R.H.Fce Avail-Average":          "average_furnace_availability",
    "H.R.Coil-2 Production":          ("HSM-2", "specific_power_consumption"),
    "Slabs Rolled -  HSM2":           ("HSM-2", "specific_heat_consumption"),

    # ---- Silicon Steel Mill -------------------------------------------------------
    "Yield from HRC-CRNO":            "yield",
    "Acid cons. in AP line":          "acid_consumption",
    "REV. MILL Availability On Cal Hrs":  "availability",
    "REV.MILL Utilisation.on Avail Hrs":  "utilisation",
    "Rolling Rate(Rev Mill)":         "rolling_rate",

    # ---- ERW / SW Pipe Plant (same aliases per-section) --------------------------
    "Yield from HR Coils":            "yield",
    "Utili.on Available Time":        "utilisation",   # ERW spelling
    "Utili. on Avail. Time":          "utilisation",   # SWP spelling
    "Rolling Rate ":                  "rolling_rate",

    # ---- General -------------------------------------------------------------------
    "Coke Screen Loss":               ("General", "coke_screen_loss"),
    "**Energy consumption. ":         "specific_energy_consumption",
    "Make-Up Water Cons.":            "specific_water_consumption",
    "Sp. CO2 Emmission ":             "specific_co2_emissions",
    "Dry Coal input":                 ("General", "specific_heat_coke_ovens"),
}

# Per-furnace blocks where all four furnaces (BF-1/BF-4/BF-5/BF_Shop) sit in
# consecutive rows under one section-title row with a repeating or blank
# label — resolved by fixed position relative to the anchor, never by label
# text, so the ambiguous "BF-I"/"BF-V"/"Shop" labels can never be
# cross-attributed to the wrong block.
# {raw anchor text: (param_key, [(row_offset, unit), ...])}
FURNACE_BLOCKS = {
    "Oxygen enrchiment %":  ("o2_enrichment",  [(1, "BF-1"), (2, "BF-4"), (3, "BF-5"), (4, "BF_Shop")]),
    "Hot Blast Tempeture":  ("hot_blast_temp", [(1, "BF-1"), (2, "BF-4"), (3, "BF-5"), (4, "BF_Shop")]),
    "SI % IN HOTMETAL":     ("silicon_in_hm",  [(1, "BF-1"), (2, "BF-4"), (3, "BF-5"), (4, "BF_Shop")]),
    "BF Fuel Rate":         ("fuel_rate",      [(1, "BF-1"), (3, "BF-4"), (4, "BF-5"), (5, "BF_Shop")]),
}

# Params reported as a TOTAL for the period, not a daily average — divided by
# days-in-month/YTD-days before being stored, to match "Average Blows/Day" as
# actually labelled.
DAILY_AVG_PARAMS = {"average_blows_per_day"}

# raw label -> required substring (normalized) of the column-B unit-of-measure
# string, for the rare label that appears twice in the same section with two
# different units — restricts PARAM_ALIASES's match to the one occurrence
# that's actually wanted, instead of matching whichever copy comes first.
PARAM_UNIT_FILTERS = {
    "H/Coke Yield(+25mm)": "dry coal",
}

# Every DB unit name this registry can ever produce — derived here (not
# hand-maintained separately) so api_unified_techno.py's allowed_units()
# insert-time validation guard can't drift out of sync with the extractor.
ALL_UNITS = (
    {u for u in SECTION_UNITS.values() if u}
    | {v[0] for v in PARAM_ALIASES.values() if isinstance(v, tuple)}
    | {unit for _param, offsets in FURNACE_BLOCKS.values() for _off, unit in offsets}
)
