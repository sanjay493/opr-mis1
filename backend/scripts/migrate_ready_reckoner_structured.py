"""One-time migration: parses ready_reckoner_pages' existing capacity_html/
product_mix_html (raw, editor-authored HTML strings) into the new plain-
data JSON columns (capacity_rows/product_mix_headers/product_mix_rows) —
per direct instruction, 2026-09-21: no HTML/markup/style stored in the DB
any more, all presentation applied at render time instead. See backend/
db.py's own comment above _READY_RECKONER_COLS for the exact JSON shape,
and scripts/migrate_ready_reckoner_structured.sql for the column-add step
this script's `columns` mode also performs itself (idempotent either way).

Reads the LIVE database, not backfill_ready_reckoner.py's static seed data
— some plants (e.g. RSP, BSP) have real hand-edits made after the original
seed via the /report live preview's old inline editor, and this migration
must preserve those, not silently revert to the original seed content.

Cell text extraction: <br> tags become "\\n" (a literal line break, not
HTML); every other tag is stripped (get_text()) since only the plain text
content is kept. A row counts as is_total if any of its cells contained a
<b> tag in the source HTML — the one piece of "formatting" the old HTML
carried that actually encoded meaning (a summary row), preserved as a
boolean flag instead of markup.

Usage (from backend/scripts/, same venv as the rest of the backend):
    python migrate_ready_reckoner_structured.py preview   -- writes
        _preview_<plant>_capacity.json / _preview_<plant>_product_mix.json
        next to this script for review, touches nothing in the DB.
    python migrate_ready_reckoner_structured.py apply     -- adds the new
        columns if missing, writes the parsed structured data into them.
        Leaves capacity_html/product_mix_html in place (untouched) — drop
        them separately (see the .sql file) only once you've confirmed the
        new columns render correctly.
"""
import io
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from bs4 import BeautifulSoup
import db


PLANTS = ["BSP", "DSP", "RSP", "BSL", "ISP", "ASP", "SSP", "VISL"]


def _cell_text(td) -> str:
    """Inner text of one <td>/<th>, with <br> turned into a literal "\\n"
    line break (never HTML) and every other tag stripped."""
    for br in td.find_all("br"):
        br.replace_with("\n")
    return td.get_text().strip()


def _row_is_total(cells) -> bool:
    return any(td.find("b") is not None for td in cells)


def parse_capacity(html: str) -> list:
    """-> [{"item", "details", "capacity", "is_total"}, ...]. Assumes the
    3-column Item/Details/Capacity shape every plant's capacity table was
    already normalized to (see the column-restructuring done 2026-09-20) —
    if a table doesn't have exactly 3 <td>s in some row, that row is kept
    as best-effort (missing cells become "") rather than raising, so one
    malformed row can't abort the whole plant's migration."""
    if not html:
        return []
    soup = BeautifulSoup(html, "html.parser")
    table = soup.find("table")
    if not table or not table.tbody:
        return []
    rows = []
    for tr in table.tbody.find_all("tr", recursive=False):
        cells = tr.find_all("td", recursive=False)
        texts = [_cell_text(td) for td in cells] + ["", "", ""]
        rows.append({
            "item": texts[0], "details": texts[1], "capacity": texts[2],
            "is_total": _row_is_total(cells),
        })
    return rows


def parse_product_mix(html: str) -> tuple:
    """-> (headers: [str, ...], rows: [{"cells": [...], "is_total"}, ...],
    caption: str). Column count follows this plant's own <thead>, unlike
    capacity — Product Mix genuinely has a different shape per plant (see
    the schema-design discussion, 2026-09-21). caption is BSL's only today
    (a one-line note above its grade-family table) — "" for every other
    plant."""
    if not html:
        return [], [], ""
    soup = BeautifulSoup(html, "html.parser")
    table = soup.find("table")
    if not table:
        return [], [], ""
    caption = _cell_text(table.caption) if table.caption else ""
    headers = []
    if table.thead:
        headers = [_cell_text(th) for th in table.thead.find_all(["th", "td"])]
    rows = []
    if table.tbody:
        for tr in table.tbody.find_all("tr", recursive=False):
            cells = tr.find_all("td", recursive=False)
            rows.append({
                "cells": [_cell_text(td) for td in cells],
                "is_total": _row_is_total(cells),
            })
    return headers, rows, caption


def build_structured():
    out = {}
    for plant in PLANTS:
        # db.get_ready_reckoner_page now reads the NEW columns (already
        # migrated to db.py) — read the old HTML columns directly here
        # instead, since those still exist on disk until the separate DROP
        # step and db.py's own getters no longer know about them.
        conn = db.connect()
        cur = conn.cursor()
        cur.execute(
            "SELECT capacity_html, product_mix_html FROM ready_reckoner_pages WHERE plant_code = ?",
            (plant,),
        )
        r = cur.fetchone()
        conn.close()
        capacity_html, product_mix_html = (r[0], r[1]) if r else ("", "")

        capacity_rows = parse_capacity(capacity_html)
        pm_headers, pm_rows, pm_caption = parse_product_mix(product_mix_html)
        out[plant] = {
            "capacity_rows": capacity_rows,
            "product_mix_headers": pm_headers,
            "product_mix_rows": pm_rows,
            "product_mix_caption": pm_caption,
        }
    return out


def preview():
    for plant, data in build_structured().items():
        path = f"_preview_{plant.lower()}.json"
        with io.open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"wrote {path}")


def _ensure_columns():
    conn = db.connect()
    cur = conn.cursor()
    cols = [
        ("capacity_rows", "LONGTEXT"), ("product_mix_headers", "LONGTEXT"),
        ("product_mix_rows", "LONGTEXT"), ("product_mix_caption", "VARCHAR(255)"),
    ]
    for col, coltype in cols:
        try:
            cur.execute(f"ALTER TABLE ready_reckoner_pages ADD COLUMN {col} {coltype}")
            conn.commit()
            print(f"added column {col}")
        except Exception as e:
            # Column already exists (MySQL: 1060 Duplicate column name /
            # sqlite: "duplicate column name") — fine, already migrated.
            if "duplicate" not in str(e).lower() and "1060" not in str(e):
                raise
    conn.close()


def apply():
    _ensure_columns()
    for plant, data in build_structured().items():
        db.save_ready_reckoner_content(
            plant,
            capacity_rows=data["capacity_rows"],
            product_mix_headers=data["product_mix_headers"],
            product_mix_rows=data["product_mix_rows"],
            product_mix_caption=data["product_mix_caption"],
            updated_by="migrate_ready_reckoner_structured",
        )
        print(f"{plant} migrated "
              f"({len(data['capacity_rows'])} capacity rows, "
              f"{len(data['product_mix_headers'])} product-mix columns, "
              f"{len(data['product_mix_rows'])} product-mix rows)")


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "preview"
    if mode == "apply":
        apply()
    else:
        preview()
