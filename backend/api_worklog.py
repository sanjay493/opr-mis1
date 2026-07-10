"""
Daily Work Log API

Records work completed by the user each day — a free-text description per
entry, dated by the day the work was done. Complements the To-Do list
(api_todo.py): to-dos are upcoming jobs, this is the record of what actually
got done.

Endpoints:
  GET    /api/worklog/list             – list entries (optional month=YYYY-MM,
                                          or from/to YYYY-MM-DD range)
  POST   /api/worklog/add              – create an entry
  POST   /api/worklog/{id}/update      – edit an entry's fields
  POST   /api/worklog/{id}/delete      – hard delete (POST, not DELETE verb —
                                          this app's CORS middleware only allows
                                          GET/POST, matching every other router)
"""

import re
import sqlite3
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

import db as _db

router = APIRouter(prefix="/api/worklog", tags=["worklog"])

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_MONTH_RE = re.compile(r"^\d{4}-\d{2}$")


class EntryRequest(BaseModel):
    work_date: str         # YYYY-MM-DD
    description: str
    remarks: str = ""


class EntryUpdateRequest(BaseModel):
    work_date: Optional[str] = None
    description: Optional[str] = None
    remarks: Optional[str] = None


def _validate_work_date(work_date: str):
    if not work_date or not _DATE_RE.match(work_date):
        raise HTTPException(400, "work_date must be YYYY-MM-DD, e.g. '2026-07-10'")


def _row_to_dict(row: sqlite3.Row) -> dict:
    return {
        "id":          row["id"],
        "work_date":   row["work_date"],
        "description": row["description"],
        "remarks":     row["remarks"],
        "created_at":  row["created_at"],
    }


@router.get("/list")
async def list_entries(
    month: Optional[str] = Query(None, description="YYYY-MM — list one month"),
    from_date: Optional[str] = Query(None, alias="from", description="YYYY-MM-DD range start"),
    to_date: Optional[str] = Query(None, alias="to", description="YYYY-MM-DD range end"),
):
    if month is not None and not _MONTH_RE.match(month):
        raise HTTPException(400, "month must be YYYY-MM, e.g. '2026-07'")
    for name, val in (("from", from_date), ("to", to_date)):
        if val is not None and not _DATE_RE.match(val):
            raise HTTPException(400, f"{name} must be YYYY-MM-DD")

    where, params = [], []
    if month:
        where.append("work_date LIKE ?")
        params.append(f"{month}-%")
    if from_date:
        where.append("work_date >= ?")
        params.append(from_date)
    if to_date:
        where.append("work_date <= ?")
        params.append(to_date)
    where_sql = f"WHERE {' AND '.join(where)}" if where else ""

    _db.init_db()
    conn = sqlite3.connect(_db.DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        cur = conn.execute(
            f"SELECT * FROM daily_work_log {where_sql} ORDER BY work_date DESC, id DESC",
            params,
        )
        entries = [_row_to_dict(r) for r in cur.fetchall()]
    finally:
        conn.close()
    return {"entries": entries, "count": len(entries)}


@router.post("/add")
async def add_entry(body: EntryRequest):
    _validate_work_date(body.work_date)
    if not body.description.strip():
        raise HTTPException(400, "description is required")

    _db.init_db()
    conn = sqlite3.connect(_db.DB_PATH)
    try:
        cur = conn.execute(
            """INSERT INTO daily_work_log (work_date, description, remarks, created_at)
               VALUES (?, ?, ?, ?)""",
            (body.work_date, body.description.strip(), body.remarks,
             datetime.now().isoformat()),
        )
        conn.commit()
        new_id = cur.lastrowid
    finally:
        conn.close()
    return {"status": "ok", "id": new_id}


@router.post("/{entry_id}/update")
async def update_entry(entry_id: int, body: EntryUpdateRequest):
    if body.work_date is not None:
        _validate_work_date(body.work_date)
    if body.description is not None and not body.description.strip():
        raise HTTPException(400, "description cannot be empty")

    fields, values = [], []
    for col in ("work_date", "description", "remarks"):
        val = getattr(body, col)
        if val is not None:
            fields.append(f"{col} = ?")
            values.append(val)
    if not fields:
        raise HTTPException(400, "No fields provided to update.")

    conn = sqlite3.connect(_db.DB_PATH)
    try:
        cur = conn.execute(
            f"UPDATE daily_work_log SET {', '.join(fields)} WHERE id = ?",
            (*values, entry_id),
        )
        conn.commit()
        if cur.rowcount == 0:
            raise HTTPException(404, f"No entry with id {entry_id}")
    finally:
        conn.close()
    return {"status": "ok", "id": entry_id}


@router.post("/{entry_id}/delete")
async def delete_entry(entry_id: int):
    conn = sqlite3.connect(_db.DB_PATH)
    try:
        cur = conn.execute("DELETE FROM daily_work_log WHERE id=?", (entry_id,))
        conn.commit()
        if cur.rowcount == 0:
            raise HTTPException(404, f"No entry with id {entry_id}")
    finally:
        conn.close()
    return {"status": "ok", "id": entry_id}
