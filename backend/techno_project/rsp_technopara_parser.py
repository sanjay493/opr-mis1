"""Pandas-based cleaning step for the RSP technopara techno sheet (page-1-8).

Reads the already-open worksheet into a tidy DataFrame — one row per sheet
row, holding only the label columns, the current month's column, and the
Cum. column — with every legacy fiscal-year column dropped. This is the
"unwanted column... legacy yearly data" the sheet otherwise carries (18+ and
growing every year), and makes the cleaned data directly inspectable
(e.g. `df.to_csv()` during development) instead of an opaque cell-reference
trace.
"""
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
from rsp_row_scan import find_month_cum_columns, detect_label_column  # noqa: E402


def clean_technopara_sheet(ws, month_num: str, probe_labels) -> pd.DataFrame:
    """Build the cleaned DataFrame for one worksheet.

    Args:
        ws: an openpyxl worksheet (the already-located page-1-8-style sheet).
        month_num: report month as '01'..'12'.
        probe_labels: a handful of known label strings used to detect whether
            this file's labels live in column A or column B (see
            rsp_row_scan.detect_label_column) — some sheet variants insert an
            extra leading serial-number column before the label.

    Returns a DataFrame with columns:
        row       — 1-based source row number (kept for warnings/debugging only)
        label     — column-A/B text (whichever column holds the real label)
        unit_str  — the unit-of-measure column immediately after the label
        month_val — this month's value
        cum_val   — the Cum. column's value

    Raises ValueError if the month/Cum header columns can't be located.
    """
    month_col, cum_col = find_month_cum_columns(ws, month_num)
    if month_col is None or cum_col is None:
        raise ValueError(
            f"Cannot locate month '{month_num}' / 'Cum.' header columns on "
            f"sheet {ws.title!r}."
        )

    label_col = detect_label_column(ws, 5, probe_labels)
    unit_col = label_col + 1

    records = []
    for r in range(1, ws.max_row + 1):
        records.append({
            "row": r,
            "label": ws.cell(r, label_col).value,
            "unit_str": ws.cell(r, unit_col).value,
            "month_val": ws.cell(r, month_col).value,
            "cum_val": ws.cell(r, cum_col).value,
        })

    return pd.DataFrame.from_records(records)
