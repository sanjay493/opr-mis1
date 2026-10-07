"""Default (DB-derived) narrative for the Secretary Review deck's text
blocks, and the saved-or-default merge the page and renderer use.

- highlights: all-time best production for the FY-to-date period
  (board_note_common.best_ever)
- delays / breakdowns: breakdown_table events in the month, summed per unit,
  units with >= BD_MIN_HOURS lost; the longest event's cause is shown.
  Events linked to a capital repair are left out (they are CRs).
- capital repairs: capital_repair_table rows with actual dates up to the
  month end (current FY) or the CPLY month end (previous FY). With no
  structured rows for the previous FY, the latest text saved earlier in
  this FY is carried forward."""

import calendar
import datetime as dt
import re

import board_note_common as bnc
import db
import secretary_review_text as srt
from secretary_review_layout import BD_GROUPS, BD_PLANTS, BLOCKS, PLANTS, period_labels

BD_MIN_HOURS = 48
UNIT_GROUP = {"BF": "BF", "COKE": "BF", "SINTER": "BF", "SMS": "SMS", "MILL": "MILL"}
HMCS_TYPES = ("BF", "COKE", "SINTER", "SMS")
FS_TYPES = ("MILL",)


def _bounds(month):
    y, m = int(month[:4]), int(month[5:7])
    start = dt.datetime(y, m, 1)
    end = dt.datetime(y + 1, 1, 1) if m == 12 else dt.datetime(y, m + 1, 1)
    return start, end


def _parse_ts(s):
    for f in ("%Y-%m-%d %H:%M", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            return dt.datetime.strptime(str(s).strip(), f)
        except (ValueError, TypeError):
            pass
    return None


def event_hours(ev, month):
    s, e = _bounds(month)
    start = _parse_ts(ev["start_ts"])
    if start is None:
        return 0.0
    if ev.get("hours_lost_override") is not None:
        return float(ev["hours_lost_override"]) if s <= start < e else 0.0
    if ev.get("is_ongoing") or not ev.get("end_ts"):
        end = e
    else:
        end = _parse_ts(ev["end_ts"]) or start
    lo, hi = max(start, s), min(end, e)
    return max((hi - lo).total_seconds() / 3600.0, 0.0)


def clean_cause(cause, unit_name):
    s = re.sub(r"\s+", " ", cause or "").strip()
    s = re.sub(r"\s*w\.?\s*e\.?\s*f\.?\b.*$", "", s, flags=re.I)
    if unit_name and s.lower().startswith(unit_name.lower()):
        s = s[len(unit_name):].lstrip(" :-")
    s = s.rstrip(" ,;-")
    return s[:90].rstrip() + "…" if len(s) > 90 else s


def unit_summaries(events, month):
    agg = {}
    for ev in events:
        h = event_hours(ev, month)
        if h <= 0:
            continue
        k = (ev["plant"], ev["unit_type"], ev["unit_name"])
        a = agg.setdefault(k, {"plant": k[0], "unit_type": k[1], "unit_name": k[2], "hours": 0.0, "_top": (0.0, "")})
        a["hours"] += h
        if h > a["_top"][0]:
            a["_top"] = (h, ev.get("cause") or "")
    out = []
    for a in agg.values():
        if a["hours"] >= BD_MIN_HOURS:
            top = a.pop("_top")
            a["cause"] = clean_cause(top[1], a["unit_name"])
            out.append(a)
    out.sort(key=lambda a: (a["plant"], a["unit_type"], a["unit_name"]))
    return out


def _days(hours):
    d = round(hours / 24)
    return f"{d} day" if d == 1 else f"{d} days"


def _unit_line(a):
    head = f"{a['unit_name']}: {a['cause']}" if a["cause"] else a["unit_name"]
    return f"{head} – {_days(a['hours'])}"


def delay_text(summaries, unit_types, mon):
    lines = []
    for p in PLANTS:
        rows = [a for a in summaries if a["plant"] == p and a["unit_type"] in unit_types]
        if rows:
            lines.append(f"{p} ({mon}):")
            lines += [_unit_line(a) for a in rows]
    return "\n".join(lines)


def bd_group_text(summaries, plant, group):
    return "\n".join(_unit_line(a) for a in summaries
                     if a["plant"] == plant and UNIT_GROUP.get(a["unit_type"]) == group)


def _mon(d):
    return calendar.month_abbr[d.month]


def _mon_span(a, b):
    if (a.year, a.month) == (b.year, b.month):
        return f"{_mon(a)}’{a.year % 100:02d}"
    if a.year == b.year:
        return f"{_mon(a)}-{_mon(b)}’{b.year % 100:02d}"
    return f"{_mon(a)}’{a.year % 100:02d}-{_mon(b)}’{b.year % 100:02d}"


def cr_line(row, upto):
    start = dt.date.fromisoformat(str(row["actual_start"])[:10])
    end = dt.date.fromisoformat(str(row["actual_end"])[:10]) if row.get("actual_end") else None
    ongoing = bool(row.get("actual_ongoing")) or end is None or end > upto
    stop = upto if (end is None or end > upto) else end
    days = (stop - start).days + 1
    label = " ".join(x for x in (row.get("shop"), row.get("equipment")) if x).strip()
    return f"{label} ({days} days in {_mon_span(start, stop)}{', contd.' if ongoing else ''})"


def _fetch_breakdowns(cur, month):
    s, e = _bounds(month)
    cur.execute(
        "SELECT plant, unit_type, unit_name, start_ts, end_ts, is_ongoing, cause, hours_lost_override "
        "FROM breakdown_table WHERE capital_repair_id IS NULL AND start_ts < ? "
        "AND (end_ts IS NULL OR end_ts >= ? OR is_ongoing = 1)",
        (e.strftime("%Y-%m-%d"), s.strftime("%Y-%m-%d")),
    )
    cols = ("plant", "unit_type", "unit_name", "start_ts", "end_ts", "is_ongoing", "cause", "hours_lost_override")
    return [dict(zip(cols, r)) for r in cur.fetchall()]


def _fetch_cr(cur, plant, fy_label, upto):
    cur.execute(
        "SELECT shop, equipment, actual_start, actual_end, actual_ongoing FROM capital_repair_table "
        "WHERE plant=? AND fy=? AND actual_start IS NOT NULL AND actual_start <> '' AND actual_start <= ? "
        "ORDER BY actual_start",
        (plant, fy_label, upto.isoformat()),
    )
    cols = ("shop", "equipment", "actual_start", "actual_end", "actual_ongoing")
    return [dict(zip(cols, r)) for r in cur.fetchall()]


def highlight_text(cur, scope, labels):
    fy_start, n = labels["fy_start"], labels["n"]

    def months_fn(fy):
        return bnc.fy_months(fy)[:n]

    lines = []
    for label, db_item in bnc.ITEMS_FOR_PLANT.get(scope, []):
        add_conv = scope == "SAIL" and label == "Finished Steel"
        r = bnc.best_ever(cur, scope, db_item, months_fn, fy_start, add_conv)
        if r:
            cur_v, prev_v, prev_fy = r
            lines.append(f"{label} {cur_v / 1000:.3f} MT (Previous best {prev_v / 1000:.3f} MT in "
                         f"{labels['period_short']} {prev_fy}-{(prev_fy + 1) % 100:02d})")
    if not lines:
        return ""
    who = "SAIL achieved best ever" if scope == "SAIL" else f"{scope} achieved best"
    rng = f"Apr-{labels['abbr']}" if labels["n"] > 1 else "Apr"
    period = labels["period_short"] if labels["period_short"] == rng else f"{labels['period_short']} ({rng})"
    return "\n".join([f"{who} {period} {labels['fy_label']} production for following:-"] + lines)


def default_texts(month):
    labels = period_labels(month)
    y, m = int(month[:4]), int(month[5:7])
    upto = dt.date(y, m, calendar.monthrange(y, m)[1])
    upto_prev = dt.date(y - 1, m, calendar.monthrange(y - 1, m)[1])
    fy_window = bnc.fy_months(labels["fy_start"])
    out = {}
    conn = db.connect()
    cur = conn.cursor()
    try:
        out["hl_SAIL"] = highlight_text(cur, "SAIL", labels)
        for p in PLANTS:
            out[f"hl_{p}"] = highlight_text(cur, p, labels)
        summaries = unit_summaries(_fetch_breakdowns(cur, month), month)
        out["delay_hmcs"] = delay_text(summaries, HMCS_TYPES, labels["mon"])
        out["delay_fs"] = delay_text(summaries, FS_TYPES, labels["mon"])
        for p in BD_PLANTS:
            for g, _ in BD_GROUPS:
                out[f"bd_{p}_{g}"] = bd_group_text(summaries, p, g)
        for p in PLANTS:
            out[f"cr_{p}_cur"] = "\n".join(cr_line(r, upto) for r in _fetch_cr(cur, p, labels["fy_label"], upto))
            prev = "\n".join(cr_line(r, upto_prev) for r in _fetch_cr(cur, p, labels["fy_prev_label"], upto_prev))
            out[f"cr_{p}_prev"] = prev or (srt.latest_saved_before(f"cr_{p}_prev", month, fy_window) or "")
    finally:
        conn.close()
    return {k: out.get(k, "") for k, _, _ in BLOCKS}


def effective_texts(month):
    saved = srt.get_texts(month)
    defaults = default_texts(month)
    return {k: {"text": saved[k] if k in saved else defaults.get(k, ""), "saved": k in saved}
            for k, _, _ in BLOCKS}
