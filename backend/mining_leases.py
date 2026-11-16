"""
Details of SAIL Mining Leases — PDF Annexure-1 "SAIL Mining at a Glance" and
its data entry (Data Entry > Reference > Mining Leases, api_mining_leases.py).

One stored row per lease (repo.mines.mining_leases_rows). The mine, state, lease,
mineral, area, reserves and status cells can be merged down over several leases, as in
the source sheet: the head row's <col>_span is how many rows it covers, and
each covered row has span 0 and a blank cell. Area and reserves are free text
and print as typed ("Un-Explored", "208( Broken area- 11MT)").
"""
from repo import mines as rmines

SPAN_COLS = ("mine", "state", "lease", "mineral", "area", "reserves", "status")
TEXT_COLS = ("s_no", "mine", "state", "lease", "mineral", "area", "reserves", "status")


def _stored() -> list:
    return rmines.mining_leases_rows()


def _span(row: dict, col: str, n: int) -> int:
    try:
        v = int(row.get(f"{col}_span", 1))
    except (TypeError, ValueError):
        raise ValueError(f"row {n}: {col} span must be a whole number")
    if v < 0:
        raise ValueError(f"row {n}: {col} span cannot be negative")
    return v


def validate(rows: list) -> list:
    """The rows with every span an int, or ValueError naming the (1-based)
    row and column: a span running past the last row, a span-0 cell no
    cell above covers, a covered row that has its own span or a value."""
    out = [dict(r) for r in rows]
    for col in SPAN_COLS:
        covered_until = 0               # last row index (1-based) covered by the head above
        for n, r in enumerate(out, start=1):
            span = _span(r, col, n)
            r[f"{col}_span"] = span
            text = (r.get(col) or "")
            if n <= covered_until:
                if span != 0:
                    raise ValueError(f"row {n}: {col} is covered by the cell above, so its span must be 0")
                if str(text).strip():
                    raise ValueError(f"row {n}: {col} is covered by the cell above, so it must be blank")
                continue
            if span == 0:
                raise ValueError(f"row {n}: {col} span is 0 but no cell above covers this row")
            if n + span - 1 > len(out):
                raise ValueError(f"row {n}: {col} spans {span} rows but only {len(out) - n + 1} remain")
            covered_until = n + span - 1
    return out


def save(rows: list, user) -> int:
    """Validate, then replace the stored table. -> rows saved."""
    return rmines.save_mining_leases(validate(rows), user)


def build_page() -> dict:
    """{available, rows}: each row has s_no as text and mine, state, lease,
    mineral, area, reserves, status as {"text", "span"} (span 0 = print no cell)."""
    stored = _stored()
    rows = []
    for r in stored:
        row = {"s_no": r.get("s_no") or ""}
        for c in SPAN_COLS:
            row[c] = {"text": r.get(c) or "", "span": int(r.get(f"{c}_span", 1))}
        rows.append(row)
    return {"available": bool(rows), "rows": rows}
