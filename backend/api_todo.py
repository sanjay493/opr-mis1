"""
To-Do / Upcoming Jobs API

Tracks ad-hoc jobs/tasks with a due date, a free-text recipient ("where to
send it"), a priority, and a subject/details — separate from the plant
production/techno data this app otherwise manages.

Endpoints:
  GET    /api/todo/list             – list jobs (status=pending|done|all)
  POST   /api/todo/add              – create a job
  POST   /api/todo/{id}/update      – edit a job's fields
  POST   /api/todo/{id}/complete    – mark done
  POST   /api/todo/{id}/reopen      – mark pending again
  POST   /api/todo/{id}/delete      – hard delete (POST, not DELETE verb —
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

router = APIRouter(prefix="/api/todo", tags=["todo"])

_PRIORITIES = ("high", "medium", "low")
_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


class JobRequest(BaseModel):
    subject: str
    details: str = ""
    recipient: str = ""
    due_date: str          # YYYY-MM-DD
    priority: str = "medium"


class JobUpdateRequest(BaseModel):
    subject: Optional[str] = None
    details: Optional[str] = None
    recipient: Optional[str] = None
    due_date: Optional[str] = None
    priority: Optional[str] = None


def _validate_due_date(due_date: str):
    if not due_date or not _DATE_RE.match(due_date):
        raise HTTPException(400, "due_date must be YYYY-MM-DD, e.g. '2026-07-15'")


def _validate_priority(priority: str):
    if priority not in _PRIORITIES:
        raise HTTPException(400, f"priority must be one of {_PRIORITIES}")


def _row_to_dict(row: sqlite3.Row) -> dict:
    return {
        "id":           row["id"],
        "subject":      row["subject"],
        "details":      row["details"],
        "recipient":    row["recipient"],
        "due_date":     row["due_date"],
        "priority":     row["priority"],
        "status":       row["status"],
        "created_at":   row["created_at"],
        "completed_at": row["completed_at"],
    }


@router.get("/list")
async def list_jobs(status: str = Query("pending", description="pending | done | all")):
    if status not in ("pending", "done", "all"):
        raise HTTPException(400, "status must be 'pending', 'done', or 'all'")
    _db.init_db()
    conn = sqlite3.connect(_db.DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        if status == "all":
            cur = conn.execute("SELECT * FROM todo_jobs ORDER BY due_date ASC, id ASC")
        else:
            cur = conn.execute(
                "SELECT * FROM todo_jobs WHERE status=? ORDER BY due_date ASC, id ASC",
                (status,),
            )
        jobs = [_row_to_dict(r) for r in cur.fetchall()]
    finally:
        conn.close()
    return {"jobs": jobs, "count": len(jobs)}


@router.post("/add")
async def add_job(body: JobRequest):
    _validate_due_date(body.due_date)
    _validate_priority(body.priority)
    if not body.subject.strip():
        raise HTTPException(400, "subject is required")

    _db.init_db()
    conn = sqlite3.connect(_db.DB_PATH)
    try:
        cur = conn.execute(
            """INSERT INTO todo_jobs
               (subject, details, recipient, due_date, priority, status, created_at)
               VALUES (?, ?, ?, ?, ?, 'pending', ?)""",
            (body.subject.strip(), body.details, body.recipient, body.due_date,
             body.priority, datetime.now().isoformat()),
        )
        conn.commit()
        new_id = cur.lastrowid
    finally:
        conn.close()
    return {"status": "ok", "id": new_id}


@router.post("/{job_id}/update")
async def update_job(job_id: int, body: JobUpdateRequest):
    if body.due_date is not None:
        _validate_due_date(body.due_date)
    if body.priority is not None:
        _validate_priority(body.priority)

    fields, values = [], []
    for col in ("subject", "details", "recipient", "due_date", "priority"):
        val = getattr(body, col)
        if val is not None:
            fields.append(f"{col} = ?")
            values.append(val)
    if not fields:
        raise HTTPException(400, "No fields provided to update.")

    conn = sqlite3.connect(_db.DB_PATH)
    try:
        cur = conn.execute(
            f"UPDATE todo_jobs SET {', '.join(fields)} WHERE id = ?",
            (*values, job_id),
        )
        conn.commit()
        if cur.rowcount == 0:
            raise HTTPException(404, f"No job with id {job_id}")
    finally:
        conn.close()
    return {"status": "ok", "id": job_id}


@router.post("/{job_id}/complete")
async def complete_job(job_id: int):
    conn = sqlite3.connect(_db.DB_PATH)
    try:
        cur = conn.execute(
            "UPDATE todo_jobs SET status='done', completed_at=? WHERE id=?",
            (datetime.now().isoformat(), job_id),
        )
        conn.commit()
        if cur.rowcount == 0:
            raise HTTPException(404, f"No job with id {job_id}")
    finally:
        conn.close()
    return {"status": "ok", "id": job_id}


@router.post("/{job_id}/reopen")
async def reopen_job(job_id: int):
    conn = sqlite3.connect(_db.DB_PATH)
    try:
        cur = conn.execute(
            "UPDATE todo_jobs SET status='pending', completed_at=NULL WHERE id=?",
            (job_id,),
        )
        conn.commit()
        if cur.rowcount == 0:
            raise HTTPException(404, f"No job with id {job_id}")
    finally:
        conn.close()
    return {"status": "ok", "id": job_id}


@router.post("/{job_id}/delete")
async def delete_job(job_id: int):
    conn = sqlite3.connect(_db.DB_PATH)
    try:
        cur = conn.execute("DELETE FROM todo_jobs WHERE id=?", (job_id,))
        conn.commit()
        if cur.rowcount == 0:
            raise HTTPException(404, f"No job with id {job_id}")
    finally:
        conn.close()
    return {"status": "ok", "id": job_id}
