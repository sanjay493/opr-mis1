"""
Central registry for techno-economic parameter units and canonical definitions.

Usage in extractors:
    from techno_registry import UNIT, canonical_unit

    # Use UNIT constants for new code:
    unit = UNIT.KG_THM

    # Normalize any raw string at save time:
    unit = canonical_unit(raw_string)

Run migrate_units(conn) once after adding this module to fix existing DB rows.
"""

# ── Canonical unit strings ────────────────────────────────────────────────────
# Import UNIT and use UNIT.KG_THM etc. — never write raw unit strings.

class _Units:
    # Per-tonne-of-hot-metal (BF rates)
    KG_THM    = "Kg/THM"
    NM3_THM   = "Nm³/THM"
    # Per-tonne-of-crude-steel (SMS/energy)
    KG_TCS    = "Kg/TCS"
    NM3_TCS   = "Nm³/TCS"
    KWH_TCS   = "KWh/TCS"
    GCAL_TCS  = "G.Cal/TCS"
    KCAL_TCS  = "Kcal/TCS"
    M3_TCS    = "m³/TCS"
    # Per-tonne-of-dry-coal (coke ovens)
    KG_TDC    = "Kg/TDC"
    NM3_TDC   = "Nm³/TDC"
    KG_TCO    = "Kg/TCO"
    NM3_TCO   = "Nm³/TCO"
    KCAL_TCO  = "Kcal/TCO"
    KCAL_NM3  = "Kcal/Nm³"
    # Productivity
    T_M3_DAY  = "T/m³/day"
    T_M2_HR   = "T/m²/hr"
    T_HR      = "T/Hr"
    T_UTL_HR  = "T/Utl.Hr."
    NOS_HR    = "Nos./Hr."
    # Energy / heat (rolling mills)
    MCAL_T    = "M.Cal/T"
    KWH_T     = "KWh/T"
    KWH_TCHS  = "KWh/TCHS"
    # Temperature
    DEG_C     = "°C"
    # Volume rates (water, gas)
    M3_T      = "m³/T"
    NM3_MIN   = "Nm³/min"
    NM3_T     = "Nm³/T"
    # Percentage
    PCT       = "%"
    PCT_AVL   = "%Avl."
    PCT_ICH   = "% ICH"
    PCT_AVAIL = "% Avail hr"
    # Count / discrete
    NOS       = "Nos."
    HEATS     = "Heats"
    HEATS_DAY = "Heats/Day"
    # Time
    MIN       = "Min"
    HRS       = "Hrs"
    # Weight
    T         = "T"
    # Dimensionless
    RATIO     = "Ratio"

UNIT = _Units()


# ── Normalisation map: lowercase(raw) → canonical ────────────────────────────
# Add new aliases here whenever a source uses a non-canonical spelling.

_NORMALIZE: dict[str, str] = {
    # Kg/THM variants
    "kg/thm":          "Kg/THM",
    "kg/thm":          "Kg/THM",
    "kg./thm":         "Kg/THM",
    "kg./thm":         "Kg/THM",
    # Kg/TCS variants (space, "T CS" etc.)
    "kg/t cs":         "Kg/TCS",
    "kg/tcs":          "Kg/TCS",
    # KWh variants
    "kwh/t":           "KWh/T",
    "kwh/t cs":        "KWh/TCS",
    "kwh/tchs":        "KWh/TCHS",
    # Nm³ variants (ascii 3 vs superscript, spaces)
    "nm3/tcs":         "Nm³/TCS",
    "nm³/tcs":         "Nm³/TCS",
    "nm3/t cs":        "Nm³/TCS",
    "nm³/t cs":        "Nm³/TCS",
    "nm3/tcs":         "Nm³/TCS",
    "m3/tdc":          "Nm³/TDC",
    "nm3/tdc":         "Nm³/TDC",
    "nm3/thm":         "Nm³/THM",
    "nm³/thm":         "Nm³/THM",
    "nm3/tco":         "Nm³/TCO",
    "nm³/tco":         "Nm³/TCO",
    "nm3/t":           "Nm³/T",
    "nm3/min":         "Nm³/min",
    # Productivity
    "t/m3/day":        "T/m³/day",
    "t/m³/day":        "T/m³/day",
    "t/m3/day":        "T/m³/day",
    "t/m2/hr":         "T/m²/hr",
    "t/m²/hr":         "T/m²/hr",
    "t/hr.":           "T/Hr",
    "t/hr":            "T/Hr",
    "t/utl.hr.":       "T/Utl.Hr.",
    "nos./hr.":        "Nos./Hr.",
    # Energy / heat
    "g.cal/tcs":       "G.Cal/TCS",
    "g.cal/t cs":      "G.Cal/TCS",
    "g.cal/t":         "G.Cal/T",
    "m.cal/t":         "M.Cal/T",
    "mcal/t":          "M.Cal/T",
    "kcal/t cs":       "Kcal/TCS",
    "kcal/nm3":        "Kcal/Nm³",
    "kcal/nm³":        "Kcal/Nm³",
    # Volume rates
    "cum/t":           "m³/T",
    "cum/tcs":         "m³/TCS",
    "m³/t":            "m³/T",
    "m3/t":            "m³/T",
    # Temperature
    "°c":              "°C",
    "deg c":           "°C",
    "deg. c":          "°C",
    # Percentage / availability
    "% avl.":          "%Avl.",
    "%avl.":           "%Avl.",
    "% avail hr":      "% Avail hr",
    # Count
    "nos.":            "Nos.",
    "nos":             "Nos.",
    # Time
    "minutes":         "Min",
    "min":             "Min",
    # Weight
    "tonnes":          "T",
    "tons":            "T",
    # Misc
    "ratio":           "Ratio",
    "--":              "Ratio",
    "kg/tco":          "Kg/TCO",
    "kcal/tco":        "Kcal/TCO",
    "kg/tdc":          "Kg/TDC",
}

# BF-rate params where Kg/T is a unit error (should be Kg/THM)
_BF_RATE_SECTIONS = frozenset({
    "BF Coke Rate", "Coke Rate", "Nut Coke Rate", "CDI", "CDI Rate", "Blast Furnaces",
})
# Params stored as dimensionless ratio — Kg/THM label is wrong
_RATIO_SECTIONS = frozenset({
    "Coal to Hot Metal", "Coal to Hot Metal Ratio",
    "Gross Coal to Hot Metal", "Coal to Hot metal ratio",
})


def canonical_unit(raw: str, group_code: str = "", section: str = "") -> str:
    """Return the canonical unit for *raw*.

    Pass group_code + section for context-aware corrections (e.g. Kg/T → Kg/THM
    for BF-rate params but not for mill acid consumption).
    """
    if not raw:
        return raw or ""
    key = raw.strip().lower()
    result = _NORMALIZE.get(key, raw.strip())
    # Coal to Hot Metal is dimensionless ratio — any Kg/T* label is wrong
    if section in _RATIO_SECTIONS and result in ("Kg/THM", "Kg/T", "Kg/TCS"):
        result = "Ratio"
    # Context correction: Kg/T in BF-rate sections means Kg/THM
    elif result == "Kg/T" and section in _BF_RATE_SECTIONS:
        result = "Kg/THM"
    return result


# ── Canonical parameter name normalisation ───────────────────────────────────

_NAME_NORMALIZE: dict[str, str] = {
    "bf coke rate":                     "Coke Rate",
    "bf productivity (working volume)": "BF Productivity",
    "gross coal to hot metal":          "Coal to Hot Metal",
    "coal to hot metal ratio":          "Coal to Hot Metal",
    "nut coke consumption":             "Nut Coke Rate",
    "cdi":                              "CDI Rate",
    "hot metal consumption":            "Hot Metal Consumption",
    "hm consumption":                   "Hot Metal Consumption",
}


def canonical_name(raw: str) -> str:
    """Return the canonical parameter name for *raw* (case-insensitive lookup)."""
    if not raw:
        return raw or ""
    return _NAME_NORMALIZE.get(raw.strip().lower(), raw.strip())


# ── One-time DB migration ─────────────────────────────────────────────────────

def migrate_units(conn) -> int:
    """Normalise all unit strings in techno_param_master.

    Returns the number of rows updated.
    """
    import sqlite3
    cur = conn.cursor()
    cur.execute("SELECT param_id, group_code, section, unit FROM techno_param_master")
    rows = cur.fetchall()

    updated = 0
    for param_id, group_code, section, raw_unit in rows:
        canon = canonical_unit(raw_unit or "", group_code, section)
        if canon != (raw_unit or ""):
            cur.execute(
                "UPDATE techno_param_master SET unit=? WHERE param_id=?",
                (canon, param_id),
            )
            updated += 1

    conn.commit()
    return updated
