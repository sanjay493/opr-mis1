"""
Special Steel grade-clubbing API — lets an editor pick 2+ near-duplicate
quality grades for a plant+product and display them as one combined row on
the Special Steel report (see page_special_steel.py's _resolve_clubs()).

Endpoints:
  GET    /api/special-steel/products     – distinct products for a plant
  GET    /api/special-steel/grades       – grades for a plant+product, grouped by current club
  POST   /api/special-steel/grade-clubs  – club 2+ grades together
  DELETE /api/special-steel/grade-clubs  – remove one grade from its club
"""

import datetime
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

import db as _db
from page_special_steel import _auto_club_label

router = APIRouter(prefix="/api/special-steel", tags=["special-steel-clubs"])

# Only these plants carry a real quality-grade breakdown in special_steel_orders
# — ISP and SSPs store a fixed quality_grade='TOTAL' sentinel (see
# page_special_steel.py's module docstring), so clubbing doesn't apply to them.
GRADE_CLUB_PLANTS = ["BSP", "DSP", "RSP", "BSL"]


class ClubRequest(BaseModel):
    plant: str
    product: str
    grades: List[str]
    label: Optional[str] = None


class UnclubRequest(BaseModel):
    plant: str
    product: str
    grade: Optional[str] = None    # remove just this one grade from its club
    label: Optional[str] = None    # dissolve the whole club (all members ungrouped)


@router.get("/products")
async def list_products(plant: str = Query(...)):
    """Distinct product groups ever recorded for this plant."""
    plant = plant.upper()
    if plant not in GRADE_CLUB_PLANTS:
        raise HTTPException(400, f"Grade clubbing isn't applicable for {plant}")
    conn = _db.connect()
    cur = conn.cursor()
    cur.execute(
        "SELECT DISTINCT product FROM special_steel_orders WHERE plant_name=? ORDER BY product",
        (plant,),
    )
    products = [r[0] for r in cur.fetchall()]
    conn.close()
    return {"plant": plant, "products": products}


@router.get("/grades")
async def list_grades(plant: str = Query(...), product: str = Query(...)):
    """Distinct quality grades for this plant+product, grouped by current club
    membership. Response: {ungrouped: [grade, ...], clubs: [{label, members}, ...]}."""
    plant = plant.upper()
    conn = _db.connect()
    cur = conn.cursor()
    cur.execute(
        "SELECT DISTINCT quality_grade FROM special_steel_orders "
        "WHERE plant_name=? AND product=? AND quality_grade != '' ORDER BY quality_grade",
        (plant, product),
    )
    all_grades = [r[0] for r in cur.fetchall()]

    cur.execute(
        "SELECT quality_grade, club_label FROM special_steel_grade_clubs "
        "WHERE plant_name=? AND product=?",
        (plant, product),
    )
    club_rows = cur.fetchall()
    conn.close()

    clubbed = {g for g, _ in club_rows}
    clubs_by_label = {}
    for grade, label in club_rows:
        clubs_by_label.setdefault(label, []).append(grade)

    return {
        "plant": plant, "product": product,
        "ungrouped": [g for g in all_grades if g not in clubbed],
        "clubs": [{"label": label, "members": sorted(members)}
                  for label, members in sorted(clubs_by_label.items())],
    }


@router.post("/grade-clubs")
async def create_club(body: ClubRequest):
    """Club 2+ grades together. Upserts — a grade already in a different
    club for this plant+product simply moves to the new one."""
    plant = body.plant.upper()
    grades = [g.strip() for g in body.grades if g.strip()]
    if len(grades) < 2:
        raise HTTPException(400, "Select at least 2 grades to club together")

    label = (body.label or "").strip() or _auto_club_label(sorted(grades))
    now = datetime.datetime.now().isoformat()

    conn = _db.connect()
    cur = conn.cursor()
    for grade in grades:
        cur.execute("""
            INSERT INTO special_steel_grade_clubs (plant_name, product, quality_grade, club_label, created_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(plant_name, product, quality_grade) DO UPDATE SET club_label=excluded.club_label
        """, (plant, body.product, grade, label, now))
    conn.commit()
    conn.close()

    return {"status": "ok", "plant": plant, "product": body.product,
            "label": label, "members": grades}


@router.delete("/grade-clubs")
async def remove_from_club(body: UnclubRequest):
    """Two modes, mutually exclusive:
      - `label` given: dissolve the whole club — every member reverts to an
        ungrouped grade.
      - `grade` given: remove just that one grade from its club. If exactly
        one member remains afterward, that member's row is deleted too
        (auto-dissolve back to a plain grade — a 1-member club renders
        identically anyway, but leaving a stray row is untidy)."""
    plant = body.plant.upper()
    conn = _db.connect()
    cur = conn.cursor()

    if body.label:
        cur.execute(
            "SELECT quality_grade FROM special_steel_grade_clubs WHERE plant_name=? AND product=? AND club_label=?",
            (plant, body.product, body.label),
        )
        members = [r[0] for r in cur.fetchall()]
        if not members:
            conn.close()
            raise HTTPException(404, "That club doesn't exist")
        cur.execute(
            "DELETE FROM special_steel_grade_clubs WHERE plant_name=? AND product=? AND club_label=?",
            (plant, body.product, body.label),
        )
        conn.commit()
        conn.close()
        return {"status": "ok", "plant": plant, "product": body.product, "ungrouped": members}

    if not body.grade:
        conn.close()
        raise HTTPException(400, "Provide either 'grade' or 'label'")

    cur.execute(
        "SELECT club_label FROM special_steel_grade_clubs WHERE plant_name=? AND product=? AND quality_grade=?",
        (plant, body.product, body.grade),
    )
    row = cur.fetchone()
    if row is None:
        conn.close()
        raise HTTPException(404, "That grade isn't currently clubbed")
    label = row[0]

    cur.execute(
        "DELETE FROM special_steel_grade_clubs WHERE plant_name=? AND product=? AND quality_grade=?",
        (plant, body.product, body.grade),
    )

    cur.execute(
        "SELECT quality_grade FROM special_steel_grade_clubs WHERE plant_name=? AND product=? AND club_label=?",
        (plant, body.product, label),
    )
    remaining = [r[0] for r in cur.fetchall()]
    if len(remaining) == 1:
        cur.execute(
            "DELETE FROM special_steel_grade_clubs WHERE plant_name=? AND product=? AND quality_grade=?",
            (plant, body.product, remaining[0]),
        )
    conn.commit()
    conn.close()

    return {"status": "ok", "plant": plant, "product": body.product, "removed": body.grade}
