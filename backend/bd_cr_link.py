"""Suggest which capital repair a breakdown-log entry really is.

Plants often log a capital repair (CR) in the breakdown log too - with exact
date-times and a remark naming it ("CK-2 under CR wef 06:15 Hrs(19.08.2026)
/2200 hrs 25.08.26"). breakdown_table.capital_repair_id links such an entry
to its capital_repair_table row, and every report then counts the event
once, as the CR. This module only SUGGESTS the link (breakdown entry form,
scripts/link_breakdown_capital_repairs.py); the stored id is what counts.

A breakdown matches a CR when all of these hold:
  - same plant, and the CR has actual dates;
  - start days within 1 day, and end days within 1 day (or either is still
    ongoing - the start and the naming below are then decisive);
  - the breakdown points at THAT repair: its remark names the CR's
    equipment (CK-2 ~ CK2, CV-1 ~ CV1, M/c-2 ~ MC2, RSM), or it is logged
    against the same unit AND its remark says capital repair / CR /
    relining / planned repair. Repair wording alone isn't enough - WRM's
    "Planned Repair & c/over" overlaps BRM's capital repair by a day.
"""
import re
from datetime import date
from typing import Optional

from production_loss_analysis import _CR_IN_BD, _norm

_REPAIR_WORDS = re.compile(rf"{_CR_IN_BD.pattern}|planned\s+repair", re.IGNORECASE)
_DAY_WINDOW = 1


def _day(ts) -> Optional[date]:
    s = str(ts or "")[:10]
    try:
        return date.fromisoformat(s)
    except ValueError:
        return None


def _token(text) -> str:
    """Normalised equipment token ('CK-2' -> 'CK2', 'M/c-1' -> 'MC1',
    'BOF-1*' -> 'BOF1'); too-short tokens are useless for matching."""
    t = _norm(text)
    return t if len(t) >= 3 else ""


def _dates_match(bd: dict, cr: dict) -> bool:
    bs, cs = _day(bd.get("start_ts")), _day(cr.get("actual_start"))
    if not bs or not cs or abs((bs - cs).days) > _DAY_WINDOW:
        return False
    if bd.get("is_ongoing") or cr.get("actual_ongoing"):
        return True
    be, ce = _day(bd.get("end_ts")), _day(cr.get("actual_end"))
    return bool(be and ce and abs((be - ce).days) <= _DAY_WINDOW)


def _score(bd: dict, cr: dict) -> int:
    """0 = not this CR; higher = stronger evidence."""
    cause = _norm(bd.get("cause"))
    equip = _token(cr.get("equipment"))
    if equip and equip in cause:
        return 2
    same_unit = _norm(bd.get("unit_name")) in {_norm(cr.get("equipment")), _norm(cr.get("shop"))} - {""}
    if same_unit and _REPAIR_WORDS.search(bd.get("cause") or ""):
        return 1
    return 0


def suggest_cr(bd: dict, crs: list) -> Optional[dict]:
    """The capital repair `bd` (a breakdown_table row) most likely is, from
    `crs` (capital_repair_table rows), or None."""
    best, best_key = None, None
    for cr in crs:
        if cr.get("plant") != bd.get("plant") or not cr.get("actual_start") or not _dates_match(bd, cr):
            continue
        score = _score(bd, cr)
        if not score:
            continue
        gap = abs((_day(bd.get("start_ts")) - _day(cr.get("actual_start"))).days)
        key = (score, -gap)
        if best_key is None or key > best_key:
            best, best_key = cr, key
    return best
