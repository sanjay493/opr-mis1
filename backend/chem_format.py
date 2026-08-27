"""Render chemical formulae in parameter labels/units with subscripted digits.

Used as the Jinja `chemsub` filter (see pdf.py) on techno-economic /
environmental / BF parameter labels and unit strings only — never on free
prose or generic table headers, so it can't touch "H2" as a half-year
column, "12 Parameters", dates, etc.

Whitelist-driven: only the exact formula tokens below are rewritten, and
only the digit runs inside them are wrapped in <sub>…</sub>. Letters are
left exactly as written.
"""
import re

# Every chemical formula that actually appears (or plausibly could) in a
# report parameter label or unit. Only tokens that contain a digit are
# listed — a digit-free formula (CO, FeO, CaO, MgO, NOx, SOx, …) has
# nothing to subscript.
_CHEM_TOKENS = [
    # acids / misc
    "H2SO4", "H2O2", "H3PO4",
    # oxides (steel/BF slag & sinter chemistry)
    "Al2O3", "Fe2O3", "Fe3O4", "Cr2O3", "V2O5", "P2O5", "SiO2", "TiO2",
    "MnO2", "Mn3O4", "Na2O", "K2O",
    # carbonates
    "CaCO3", "MgCO3", "Na2CO3",
    # gases / molecules
    "CO2", "SO2", "SO3", "NO2", "N2O", "NH3", "CH4", "C2H2", "C2H4",
    "C2H6", "H2O", "H2S", "H2",
    "N2", "O2",
]

# Longest first so "H2SO4" wins over "H2", "Fe3O4" over "Fe", etc.
_CHEM_RE = re.compile(
    r"(?<![A-Za-z0-9])(?:"
    + "|".join(re.escape(t) for t in sorted(_CHEM_TOKENS, key=len, reverse=True))
    + r")(?![A-Za-z0-9])",
    re.IGNORECASE,
)


def _subscript_digits(match: "re.Match") -> str:
    return re.sub(r"\d+", lambda d: f"<sub>{d.group(0)}</sub>", match.group(0))


def chem_subscript(text) -> str:
    """Wrap the digit runs of any whitelisted chemical formula in <sub>.

    Returns a str containing HTML markup (the Jinja env this is registered
    on runs with autoescape=False, same as the other label filters). A
    None / empty input returns "".
    """
    if text is None:
        return ""
    return _CHEM_RE.sub(_subscript_digits, str(text))
