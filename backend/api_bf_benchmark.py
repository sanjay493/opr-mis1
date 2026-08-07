"""
Large BF Benchmarking API — compares SAIL's 3 large blast furnaces (BSP
BF-8, RSP BF-5, ISP BF-5) against admin-added non-SAIL large BFs, on the
parameters in bf_benchmark_registry.BF_BENCHMARK_PARAMS.

Endpoints:
  GET    /api/bf-benchmark/params                       – param + SAIL BF registry
  GET    /api/bf-benchmark/external-bfs                  – list non-SAIL BFs
  POST   /api/bf-benchmark/external-bfs                  – add a non-SAIL BF
  PATCH  /api/bf-benchmark/external-bfs/{id}              – edit name/company/Working Volume/active
  GET    /api/bf-benchmark/external-bfs/{id}/entry        – fetch one month's entered data
  POST   /api/bf-benchmark/external-bfs/{id}/entry        – save one month's entered data (merge)
  PATCH  /api/bf-benchmark/sail-meta                      – set Working Volume for a SAIL BF
  POST   /api/bf-benchmark/compare                        – month-by-month + FY-avg comparison table
  POST   /api/bf-benchmark/excel                          – comparison table as .xlsx
  POST   /api/bf-benchmark/pdf                             – comparison table as .pdf

SAIL-side monthly values come straight from techno_data (already populated
by the existing extraction/manual-entry pipelines) — this module never
writes to techno_data, only reads it. Non-SAIL data lives entirely in the
two bf_benchmark_external_* tables this feature owns.
"""

import datetime
import json
from typing import Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query, Response
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel

import db as _db
import page_bf_benchmark_export as _export
import techno_cumulative as _tc
from bf_benchmark_registry import (
    BF_BENCHMARK_PARAMS, DYNAMIC_PARAM_KEYS, HM_PRODUCTION_KEY, PARAM_BY_KEY, SAIL_BFS,
)

router = APIRouter(prefix="/api/bf-benchmark", tags=["bf-benchmark"])

_SAIL_BF_BY_KEY = {f"{b['plant']}:{b['unit']}": b for b in SAIL_BFS}


def _now() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


# ── Pydantic request bodies ──────────────────────────────────────────────────
class ExternalBFCreate(BaseModel):
    name: str
    company: str = ""


class ExternalBFUpdate(BaseModel):
    name: Optional[str] = None
    company: Optional[str] = None
    working_volume_m3: Optional[float] = None
    active: Optional[bool] = None


class EntrySaveRequest(BaseModel):
    report_month: str          # YYYY-MM
    param_data: Dict[str, Optional[float]] = {}


class SailMetaRequest(BaseModel):
    plant: str
    unit: str
    working_volume_m3: Optional[float] = None


class CompareRequest(BaseModel):
    sail_bf_keys: List[str] = []       # "PLANT:UNIT", e.g. "BSP:BF-8"
    years: List[int] = []              # FY start years, e.g. [2024, 2025] for FY2024-25/FY2025-26
    month_slots: List[int] = list(range(12))   # 0=Apr..11=Mar, which FY months to include
    external_bf_ids: List[int] = []    # each shown for ITS OWN last-available FY, not `years`


def _validate_month(report_month: str):
    try:
        y, m = report_month.split('-')
        assert len(y) == 4 and 1 <= int(m) <= 12
    except Exception:
        raise HTTPException(400, "report_month must be YYYY-MM, e.g. '2026-05'")


def _fy_start_of(report_month: str) -> int:
    y, m = int(report_month[:4]), int(report_month[5:7])
    return y if m >= 4 else y - 1


def _fy_label(fy_start: int) -> str:
    return f"{fy_start}-{str((fy_start + 1) % 100).zfill(2)}"


def _fy_months(fy_start: int, month_slots: List[int]) -> List[str]:
    """month_slots are FY-relative: 0=April..11=March."""
    out = []
    for slot in sorted(set(month_slots)):
        m, y = 4 + slot, fy_start
        if m > 12:
            m -= 12
            y += 1
        out.append(f"{y}-{m:02d}")
    return out


# ── Registry ──────────────────────────────────────────────────────────────────
@router.get("/params")
async def get_params():
    return {"params": BF_BENCHMARK_PARAMS, "sail_bfs": SAIL_BFS, "hm_production_key": HM_PRODUCTION_KEY}


# ── Non-SAIL BF registry ──────────────────────────────────────────────────────
@router.get("/external-bfs")
async def list_external_bfs(active_only: bool = Query(False)):
    conn = _db.connect()
    cur = conn.cursor()
    sql = (
        "SELECT b.id, b.name, b.company, b.working_volume_m3, b.active, b.created_at, "
        "(SELECT MAX(d.report_month) FROM bf_benchmark_external_data d WHERE d.external_bf_id=b.id) "
        "FROM bf_benchmark_external_bf b"
    )
    if active_only:
        sql += " WHERE b.active=1"
    sql += " ORDER BY b.name"
    cur.execute(sql)
    rows = [
        {"id": r[0], "name": r[1], "company": r[2], "working_volume_m3": r[3],
         "active": bool(r[4]), "created_at": r[5], "latest_report_month": r[6]}
        for r in cur.fetchall()
    ]
    conn.close()
    return {"external_bfs": rows}


@router.post("/external-bfs")
async def add_external_bf(body: ExternalBFCreate):
    name = body.name.strip()
    if not name:
        raise HTTPException(400, "name is required")
    conn = _db.connect()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO bf_benchmark_external_bf (name, company, active, created_at) VALUES (?, ?, 1, ?)",
        (name, body.company.strip(), _now()),
    )
    conn.commit()
    new_id = cur.lastrowid
    conn.close()
    return {"status": "ok", "id": new_id}


@router.patch("/external-bfs/{bf_id}")
async def update_external_bf(bf_id: int, body: ExternalBFUpdate):
    conn = _db.connect()
    cur = conn.cursor()
    cur.execute("SELECT id FROM bf_benchmark_external_bf WHERE id=?", (bf_id,))
    if not cur.fetchone():
        conn.close()
        raise HTTPException(404, "Non-SAIL BF not found.")

    fields, params = [], []
    if body.name is not None:
        fields.append("name=?"); params.append(body.name.strip())
    if body.company is not None:
        fields.append("company=?"); params.append(body.company.strip())
    if body.working_volume_m3 is not None:
        fields.append("working_volume_m3=?"); params.append(body.working_volume_m3)
    if body.active is not None:
        fields.append("active=?"); params.append(1 if body.active else 0)
    if fields:
        params.append(bf_id)
        cur.execute(f"UPDATE bf_benchmark_external_bf SET {', '.join(fields)} WHERE id=?", params)
        conn.commit()
    conn.close()
    return {"status": "ok"}


# ── Non-SAIL monthly data entry ───────────────────────────────────────────────
@router.get("/external-bfs/{bf_id}/entry")
async def get_external_entry(bf_id: int, report_month: str = Query(...)):
    _validate_month(report_month)
    conn = _db.connect()
    cur = conn.cursor()
    cur.execute(
        "SELECT param_json FROM bf_benchmark_external_data WHERE external_bf_id=? AND report_month=?",
        (bf_id, report_month),
    )
    row = cur.fetchone()
    conn.close()
    param_data = json.loads(row[0]) if row and row[0] else {}
    return {"external_bf_id": bf_id, "report_month": report_month, "param_data": param_data}


@router.post("/external-bfs/{bf_id}/entry")
async def save_external_entry(bf_id: int, body: EntrySaveRequest):
    _validate_month(body.report_month)
    conn = _db.connect()
    cur = conn.cursor()
    cur.execute("SELECT id FROM bf_benchmark_external_bf WHERE id=?", (bf_id,))
    if not cur.fetchone():
        conn.close()
        raise HTTPException(404, "Non-SAIL BF not found.")

    cur.execute(
        "SELECT param_json FROM bf_benchmark_external_data WHERE external_bf_id=? AND report_month=?",
        (bf_id, body.report_month),
    )
    row = cur.fetchone()
    merged = json.loads(row[0]) if row and row[0] else {}
    # Non-null values win; existing non-null kept if the new value is null
    # (mirrors db.merge_upsert_techno_data's convention elsewhere in the app)
    # so a partial save never wipes params the user isn't currently editing.
    for k, v in body.param_data.items():
        if v is not None:
            merged[k] = v

    now = _now()
    if row:
        cur.execute(
            "UPDATE bf_benchmark_external_data SET param_json=?, updated_at=? "
            "WHERE external_bf_id=? AND report_month=?",
            (json.dumps(merged), now, bf_id, body.report_month),
        )
    else:
        cur.execute(
            "INSERT INTO bf_benchmark_external_data (external_bf_id, report_month, param_json, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (bf_id, body.report_month, json.dumps(merged), now, now),
        )
    conn.commit()
    conn.close()
    return {"status": "ok", "param_data": merged}


# ── SAIL BF static Working Volume ────────────────────────────────────────────
@router.patch("/sail-meta")
async def set_sail_meta(body: SailMetaRequest):
    key = f"{body.plant.upper()}:{body.unit}"
    if key not in _SAIL_BF_BY_KEY:
        raise HTTPException(400, f"Unknown SAIL BF: {body.plant}/{body.unit}")
    conn = _db.connect()
    cur = conn.cursor()
    now = _now()
    cur.execute(
        "INSERT INTO bf_benchmark_sail_meta (plant, unit, working_volume_m3, updated_at) VALUES (?, ?, ?, ?) "
        "ON CONFLICT(plant, unit) DO UPDATE SET working_volume_m3=excluded.working_volume_m3, updated_at=excluded.updated_at",
        (body.plant.upper(), body.unit, body.working_volume_m3, now),
    )
    conn.commit()
    conn.close()
    return {"status": "ok"}


def _sail_working_volumes() -> Dict[str, Optional[float]]:
    conn = _db.connect()
    cur = conn.cursor()
    cur.execute("SELECT plant, unit, working_volume_m3 FROM bf_benchmark_sail_meta")
    result = {f"{p}:{u}": wv for p, u, wv in cur.fetchall()}
    conn.close()
    return result


# ── Comparison ────────────────────────────────────────────────────────────────
def _aggregate_param(values: Dict[str, float], weights: Dict[str, float],
                      param_key: str, months: List[str], weight_desc: str) -> Dict:
    """Wraps techno_cumulative.aggregate_values with graceful empty-input
    handling — the benchmarking view routinely has partial data (a BF with
    only 2 of 12 months entered), unlike compute_cumulative_from_values'
    callers which raise ValueError on no data."""
    if not values:
        return {"month_values": {}, "avg": None, "avg_method": None}
    method, basis = _tc.get_rule(param_key)
    agg = _tc.aggregate_values(values, weights, method, months, weight_desc,
                               warnings=[], weight_basis=bool(basis))
    return {"month_values": values, "avg": agg["result"], "avg_method": agg["method"]}


def _compare_sail_bf(plant: str, unit: str, months: List[str]) -> Dict:
    weights = _tc._unit_production(plant, unit, months)
    weight_desc = f"{unit} monthly Hot Metal production (production data)"
    params_out = {}
    for key in DYNAMIC_PARAM_KEYS:
        values = {}
        for m in months:
            unit_data = _db.get_techno_data(plant, m, unit).get(unit, {})
            v = unit_data.get("month", {}).get(key)
            if v is not None:
                try:
                    values[m] = float(v)
                except (TypeError, ValueError):
                    pass
        params_out[key] = _aggregate_param(values, weights, key, months, weight_desc)
    return params_out


def _compare_external_bf(bf_id: int, months: List[str]) -> Dict:
    conn = _db.connect()
    cur = conn.cursor()
    ph = ",".join("?" * len(months))
    cur.execute(
        f"SELECT report_month, param_json FROM bf_benchmark_external_data "
        f"WHERE external_bf_id=? AND report_month IN ({ph})",
        [bf_id, *months],
    )
    by_month = {m: (json.loads(pj) if pj else {}) for m, pj in cur.fetchall()}
    conn.close()

    weights = {m: d[HM_PRODUCTION_KEY] for m, d in by_month.items() if d.get(HM_PRODUCTION_KEY) is not None}
    weight_desc = "entered Hot Metal Production"
    params_out = {}
    for key in DYNAMIC_PARAM_KEYS:
        values = {m: d[key] for m, d in by_month.items() if d.get(key) is not None}
        params_out[key] = _aggregate_param(values, weights, key, months, weight_desc)
    return params_out


def _external_bf_latest_month(bf_id: int) -> Optional[str]:
    conn = _db.connect()
    cur = conn.cursor()
    cur.execute("SELECT MAX(report_month) FROM bf_benchmark_external_data WHERE external_bf_id=?", (bf_id,))
    row = cur.fetchone()
    conn.close()
    return row[0] if row and row[0] else None


@router.post("/compare")
async def compare(body: CompareRequest):
    # build_compare does one DB round-trip per BF×param×month (up to a few
    # hundred for a multi-year, multi-BF comparison) — same order of
    # magnitude as techno_custom_period (main.py), which run_in_threadpool
    # for the same reason: keep that off the event loop.
    return await run_in_threadpool(build_compare, body)


def build_compare(body: CompareRequest) -> Dict:
    if not body.sail_bf_keys and not body.external_bf_ids:
        raise HTTPException(400, "At least one BF is required")
    if body.sail_bf_keys and not body.years:
        raise HTTPException(400, "At least one year is required for SAIL BFs")

    month_slots = sorted(set(s for s in body.month_slots if 0 <= s <= 11)) or list(range(12))

    sail_bfs = []
    for key in body.sail_bf_keys:
        if key not in _SAIL_BF_BY_KEY:
            raise HTTPException(400, f"Unknown SAIL BF: {key}")
        sail_bfs.append(_SAIL_BF_BY_KEY[key])
    sail_wv = _sail_working_volumes() if sail_bfs else {}

    year_blocks = {}
    for fy_start in body.years:
        months = _fy_months(fy_start, month_slots)
        rows = []
        for b in sail_bfs:
            key = f"{b['plant']}:{b['unit']}"
            rows.append({
                "bf_key": key, "label": b["label"],
                "working_volume_m3": sail_wv.get(key),
                "params": _compare_sail_bf(b["plant"], b["unit"], months),
            })
        year_blocks[str(fy_start)] = {"fy_label": _fy_label(fy_start), "months": months, "rows": rows}

    external_blocks = {}
    if body.external_bf_ids:
        conn = _db.connect()
        cur = conn.cursor()
        ph = ",".join("?" * len(body.external_bf_ids))
        cur.execute(f"SELECT id, name, company, working_volume_m3 FROM bf_benchmark_external_bf WHERE id IN ({ph})", body.external_bf_ids)
        ext_meta = {r[0]: {"name": r[1], "company": r[2], "working_volume_m3": r[3]} for r in cur.fetchall()}
        conn.close()

        for bf_id in body.external_bf_ids:
            if bf_id not in ext_meta:
                raise HTTPException(400, f"Unknown non-SAIL BF id: {bf_id}")
            meta = ext_meta[bf_id]
            label = f"{meta['name']} ({meta['company']})" if meta["company"] else meta["name"]
            latest = _external_bf_latest_month(bf_id)
            if latest is None:
                external_blocks[str(bf_id)] = {
                    "label": label, "fy_label": None, "months": [],
                    "working_volume_m3": meta["working_volume_m3"], "params": {}, "has_data": False,
                }
                continue
            fy_start = _fy_start_of(latest)
            # Non-SAIL gets its own last-available FY, shown in full — not
            # narrowed by month_slots (that narrowing only applies to the
            # SAIL year blocks, which share a common selected FY).
            months = _fy_months(fy_start, list(range(12)))
            external_blocks[str(bf_id)] = {
                "label": label, "fy_label": _fy_label(fy_start), "months": months,
                "working_volume_m3": meta["working_volume_m3"],
                "params": _compare_external_bf(bf_id, months), "has_data": True,
            }

    return {"params": BF_BENCHMARK_PARAMS, "sail_bfs": sail_bfs,
            "year_blocks": year_blocks, "external_blocks": external_blocks}


@router.post("/excel")
async def compare_excel(body: CompareRequest):
    try:
        data = await run_in_threadpool(build_compare, body)
        content = await run_in_threadpool(_export.build_excel_bytes, data)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"BF Benchmarking Excel export failed: {type(e).__name__}: {e}")
    return Response(
        content=content,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": 'attachment; filename="BF_Benchmarking.xlsx"'},
    )


@router.post("/pdf")
async def compare_pdf(body: CompareRequest):
    import asyncio, concurrent.futures
    try:
        data = await run_in_threadpool(build_compare, body)
        html = _export.build_pdf_html(data)
        loop = asyncio.get_event_loop()
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            content = await loop.run_in_executor(pool, _export.render_pdf_bytes, html)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"BF Benchmarking PDF export failed: {type(e).__name__}: {e}")
    return Response(
        content=content,
        media_type="application/pdf",
        headers={"Content-Disposition": 'attachment; filename="BF_Benchmarking.pdf"'},
    )
