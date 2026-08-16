"""
Large BF Benchmarking API — compares SAIL's 3 large blast furnaces (BSP
BF-8, RSP BF-5, ISP BF-5) against admin-added non-SAIL large BFs, on the
parameters in bf_benchmark_registry.BF_BENCHMARK_PARAMS.

Endpoints:
  GET    /api/bf-benchmark/params                       – param + SAIL BF registry
  GET    /api/bf-benchmark/external-bfs                  – list non-SAIL BFs
  POST   /api/bf-benchmark/external-bfs                  – add a non-SAIL BF
  PATCH  /api/bf-benchmark/external-bfs/{id}              – edit name/company/Working Volume/active
  GET    /api/bf-benchmark/external-bfs/{id}/entry        – fetch one FY's entered data
  POST   /api/bf-benchmark/external-bfs/{id}/entry        – save one FY's entered data (merge)
  PATCH  /api/bf-benchmark/sail-meta                      – set Working Volume for a SAIL BF
  POST   /api/bf-benchmark/compare                        – SAIL FY/month periods + non-SAIL's own latest FY
  POST   /api/bf-benchmark/excel                          – comparison table as .xlsx
  POST   /api/bf-benchmark/pdf                             – comparison table as .pdf

SAIL-side values come straight from techno_data (already populated by the
existing extraction/manual-entry pipelines) — this module never writes to
techno_data, only reads it. Non-SAIL BFs only ever publish FY-level figures
(no monthly breakdown exists for them), so their data lives entirely in the
two bf_benchmark_external_* tables this feature owns as one flat
{param_key: value} set per BF per FY — no averaging/weighting needed, unlike
SAIL's month-to-month figures.
"""

import datetime
import json
from typing import Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query, Response
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel

import db as _db
import page_bf_benchmark_export as _export
from page_key_parameters import _COKE_UNITS
import bf_benchmark_registry as _registry
from bf_benchmark_registry import BF_BENCHMARK_PARAMS, DYNAMIC_PARAM_KEYS, PARAM_BY_KEY, SAIL_BFS

router = APIRouter(prefix="/api/bf-benchmark", tags=["bf-benchmark"])

_SAIL_BF_BY_KEY = {f"{b['plant']}:{b['unit']}": b for b in SAIL_BFS}


def _now() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


# ── Pydantic request bodies ──────────────────────────────────────────────────
class ExternalBFCreate(BaseModel):
    name: str
    company: str = ""       # e.g. "JSW", "TATA" — groups columns in the comparison table
    location: str = ""      # e.g. "Vijaynagar", "Jamshedpur" — child of company, parent of the furnace itself


class ExternalBFUpdate(BaseModel):
    name: Optional[str] = None
    company: Optional[str] = None
    location: Optional[str] = None
    working_volume_m3: Optional[float] = None
    active: Optional[bool] = None


class EntrySaveRequest(BaseModel):
    fy: str                    # "YYYY-YY" FY label, e.g. "2025-26" — non-SAIL BFs only publish FY figures
    param_data: Dict[str, Optional[float]] = {}


class SailMetaRequest(BaseModel):
    plant: str
    unit: str
    working_volume_m3: Optional[float] = None


class CompareRequest(BaseModel):
    sail_bf_keys: List[str] = []       # "PLANT:UNIT", e.g. "BSP:BF-8"
    years: List[int] = []              # FY start years, e.g. [2024, 2025] for FY2024-25/FY2025-26 — each
                                        # becomes one FY-cumulative period column (see build_compare)
    months: List[str] = []             # explicit "YYYY-MM" report months — each becomes one single-month
                                        # period column; freely combinable with `years` in the same request
    external_bf_ids: List[int] = []    # each shown for ITS OWN last-available FY, not `years`/`months`


def _validate_month(report_month: str):
    try:
        y, m = report_month.split('-')
        assert len(y) == 4 and 1 <= int(m) <= 12
    except Exception:
        raise HTTPException(400, "report_month must be YYYY-MM, e.g. '2026-05'")


def _validate_fy(fy: str):
    try:
        y, yy = fy.split('-')
        assert len(y) == 4 and len(yy) == 2
        assert int(yy) == (int(y) + 1) % 100
    except Exception:
        raise HTTPException(400, "fy must be 'YYYY-YY', e.g. '2025-26'")


def _fy_label(fy_start: int) -> str:
    return f"{fy_start}-{str((fy_start + 1) % 100).zfill(2)}"


_MON = ["", "Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def _month_label(report_month: str) -> str:
    y, m = report_month.split('-')
    return f"{_MON[int(m)]}'{y[2:]}"


# ── Registry ──────────────────────────────────────────────────────────────────
@router.get("/params")
async def get_params():
    return {"params": BF_BENCHMARK_PARAMS, "sail_bfs": SAIL_BFS}


# ── Non-SAIL BF registry ──────────────────────────────────────────────────────
@router.get("/external-bfs")
async def list_external_bfs(active_only: bool = Query(False)):
    conn = _db.connect()
    cur = conn.cursor()
    sql = (
        "SELECT b.id, b.name, b.company, b.location, b.working_volume_m3, b.active, b.created_at, "
        "(SELECT MAX(d.report_month) FROM bf_benchmark_external_data d WHERE d.external_bf_id=b.id) "
        "FROM bf_benchmark_external_bf b"
    )
    if active_only:
        sql += " WHERE b.active=1"
    sql += " ORDER BY b.name"
    cur.execute(sql)
    rows = [
        {"id": r[0], "name": r[1], "company": r[2], "location": r[3], "working_volume_m3": r[4],
         "active": bool(r[5]), "created_at": r[6], "latest_fy": r[7]}
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
        "INSERT INTO bf_benchmark_external_bf (name, company, location, active, created_at) VALUES (?, ?, ?, 1, ?)",
        (name, body.company.strip(), body.location.strip(), _now()),
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
    if body.location is not None:
        fields.append("location=?"); params.append(body.location.strip())
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


# ── Non-SAIL FY data entry ────────────────────────────────────────────────────
# Non-SAIL BFs only ever publish FY-level figures (no monthly breakdown
# exists for them) — one entry per BF per FY, not per month. The DB column
# is still named report_month (see db.init_db's comment); `fy` here is the
# "YYYY-YY" label stored into it.
@router.get("/external-bfs/{bf_id}/entry")
async def get_external_entry(bf_id: int, fy: str = Query(...)):
    _validate_fy(fy)
    conn = _db.connect()
    cur = conn.cursor()
    cur.execute(
        "SELECT param_json FROM bf_benchmark_external_data WHERE external_bf_id=? AND report_month=?",
        (bf_id, fy),
    )
    row = cur.fetchone()
    conn.close()
    param_data = json.loads(row[0]) if row and row[0] else {}
    return {"external_bf_id": bf_id, "fy": fy, "param_data": param_data}


@router.post("/external-bfs/{bf_id}/entry")
async def save_external_entry(bf_id: int, body: EntrySaveRequest):
    _validate_fy(body.fy)
    conn = _db.connect()
    cur = conn.cursor()
    cur.execute("SELECT id FROM bf_benchmark_external_bf WHERE id=?", (bf_id,))
    if not cur.fetchone():
        conn.close()
        raise HTTPException(404, "Non-SAIL BF not found.")

    cur.execute(
        "SELECT param_json FROM bf_benchmark_external_data WHERE external_bf_id=? AND report_month=?",
        (bf_id, body.fy),
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
            (json.dumps(merged), now, bf_id, body.fy),
        )
    else:
        cur.execute(
            "INSERT INTO bf_benchmark_external_data (external_bf_id, report_month, param_json, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (bf_id, body.fy, json.dumps(merged), now, now),
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
def _sail_period_values(plant: str, unit: str, report_month: str, period: str) -> Dict[str, Optional[float]]:
    """Read DYNAMIC_PARAM_KEYS straight from techno_data for one report_month
    — no re-aggregation. `period` is "month" (that month's own figure) or
    "till_month" (Apr->report_month cumulative, already weighted/summed
    correctly by db._maybe_recompute_derived_params whenever it's saved —
    see its docstring). For a Financial Year's total, the caller passes
    report_month=<FY's March> with period="till_month": SAIL's techno data
    already stores the full-FY cumulative there, so that IS the FY figure,
    not something to recompute from the 12 monthly values."""
    unit_data = _db.get_techno_data(plant, report_month, unit).get(unit, {})
    src = unit_data.get(period, {})
    out = {}
    for key in DYNAMIC_PARAM_KEYS:
        v = src.get(key)
        try:
            out[key] = float(v) if v is not None else None
        except (TypeError, ValueError):
            out[key] = None
    # HM Sulphur: some plants (confirmed for RSP) only report a shop-level
    # figure, not broken down per furnace — fall back to the plant's
    # BF_Shop unit when the furnace's own unit has no value. See
    # page_bf_large_annexure.py's _sail_bf_values for the same fallback and
    # its full rationale.
    if out.get("sulphur_in_hm") is None and unit != "BF_Shop":
        shop_src = _db.get_techno_data(plant, report_month, "BF_Shop").get("BF_Shop", {}).get(period, {})
        v = shop_src.get("sulphur_in_hm")
        try:
            out["sulphur_in_hm"] = float(v) if v is not None else None
        except (TypeError, ValueError):
            pass
    # Coke Ash: a plant-level figure stored under the coke-oven unit
    # (COB/Coke Ovens/COB-old/COB-new), never the BF's own unit — same
    # cross-unit lookup page_bf_large_annexure.py's Sinter Fe/Coke Ash row
    # already does for the annexure page, needed here too or a SAIL BF's
    # Coke Ash always shows blank on this comparison despite being on
    # record.
    if out.get("ash_in_coke") is None:
        for coke_unit in _COKE_UNITS:
            coke_src = _db.get_techno_data(plant, report_month, coke_unit).get(coke_unit, {}).get(period, {})
            v = coke_src.get("ash_in_coke") or coke_src.get("average_ash_in_coke")
            if v is not None:
                try:
                    out["ash_in_coke"] = float(v)
                    break
                except (TypeError, ValueError):
                    pass
    out["fuel_rate"] = _registry.compute_fuel_rate(out)
    return out


def _external_bf_values(bf_id: int, fy_label: str) -> "tuple[bool, Dict[str, Optional[float]]]":
    """(has_data, values) — the one flat {param_key: value} figure set a
    non-SAIL BF entered for this exact FY, no averaging (nothing to average
    across). has_data is False when this BF simply never entered anything
    for this particular FY (distinct from having entered it with some
    params left blank)."""
    conn = _db.connect()
    cur = conn.cursor()
    cur.execute(
        "SELECT param_json FROM bf_benchmark_external_data WHERE external_bf_id=? AND report_month=?",
        (bf_id, fy_label),
    )
    row = cur.fetchone()
    conn.close()
    if not row:
        return False, {}
    data = json.loads(row[0]) if row[0] else {}
    out = {}
    for key in DYNAMIC_PARAM_KEYS:
        v = data.get(key)
        try:
            out[key] = float(v) if v is not None else None
        except (TypeError, ValueError):
            out[key] = None
    out["fuel_rate"] = _registry.compute_fuel_rate(out)
    return True, out


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
    if (body.sail_bf_keys or body.external_bf_ids) and not body.years and not body.months:
        raise HTTPException(400, "Select at least one Financial Year or Month")

    sail_bfs = []
    for key in body.sail_bf_keys:
        if key not in _SAIL_BF_BY_KEY:
            raise HTTPException(400, f"Unknown SAIL BF: {key}")
        sail_bfs.append(_SAIL_BF_BY_KEY[key])
    sail_wv = _sail_working_volumes() if sail_bfs else {}

    ext_meta = {}
    if body.external_bf_ids:
        conn = _db.connect()
        cur = conn.cursor()
        ph = ",".join("?" * len(body.external_bf_ids))
        cur.execute(
            f"SELECT id, name, company, location, working_volume_m3 FROM bf_benchmark_external_bf WHERE id IN ({ph})",
            body.external_bf_ids,
        )
        ext_meta = {r[0]: {"name": r[1], "company": r[2], "location": r[3], "working_volume_m3": r[4]} for r in cur.fetchall()}
        conn.close()
        for bf_id in body.external_bf_ids:
            if bf_id not in ext_meta:
                raise HTTPException(400, f"Unknown non-SAIL BF id: {bf_id}")

    # `periods` — one column-group per selected FY plus one per selected
    # explicit month; `years` and `months` are independent and freely
    # combinable in the same request. Each row is one furnace's flat
    # {param_key: value} set, tagged with company/location so the frontend
    # can group columns Company -> Location -> Furnace within each period.
    #
    # FY periods carry BOTH SAIL and non-SAIL rows, the non-SAIL ones looked
    # up for that SAME FY (has_data=False, blank values, if that BF never
    # entered that particular FY) — company/location/furnace nest under one
    # shared "FY Year on top" grouping this way. Month periods are SAIL-only:
    # non-SAIL BFs only ever publish FY-level figures, never monthly ones,
    # so they have nothing to show under a Month period.
    periods = []
    for fy_start in body.years:
        march = f"{fy_start + 1}-03"
        fy_label = _fy_label(fy_start)
        rows = []
        for b in sail_bfs:
            key = f"{b['plant']}:{b['unit']}"
            values = _sail_period_values(b["plant"], b["unit"], march, "till_month")
            values["working_volume_m3"] = sail_wv.get(key)
            rows.append({
                "bf_key": key, "label": b["label"], "company": "SAIL", "location": b["plant"],
                "is_external": False, "has_data": True, "values": values,
            })
        for bf_id in body.external_bf_ids:
            meta = ext_meta[bf_id]
            has_data, values = _external_bf_values(bf_id, fy_label)
            if has_data:
                values["working_volume_m3"] = meta["working_volume_m3"]
            rows.append({
                "bf_key": f"ext:{bf_id}", "label": meta["name"],
                "company": meta["company"] or "—", "location": meta["location"] or "—",
                "is_external": True, "has_data": has_data, "values": values,
            })
        periods.append({"key": f"fy-{fy_start}", "label": f"FY {fy_label}", "type": "fy", "rows": rows})
    for m in body.months:
        _validate_month(m)
        rows = []
        for b in sail_bfs:
            key = f"{b['plant']}:{b['unit']}"
            values = _sail_period_values(b["plant"], b["unit"], m, "month")
            values["working_volume_m3"] = sail_wv.get(key)
            rows.append({
                "bf_key": key, "label": b["label"], "company": "SAIL", "location": b["plant"],
                "is_external": False, "has_data": True, "values": values,
            })
        periods.append({"key": f"m-{m}", "label": _month_label(m), "type": "month", "rows": rows})

    return {"params": BF_BENCHMARK_PARAMS, "sail_bfs": sail_bfs, "periods": periods}


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
