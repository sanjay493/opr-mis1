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


def event_interval(ev, month):
    """Clipped [lo, hi) of a time-based event in the month, or None."""
    if ev.get("hours_lost_override") is not None:
        return None
    s, e = _bounds(month)
    start = _parse_ts(ev["start_ts"])
    if start is None:
        return None
    if ev.get("is_ongoing") or not ev.get("end_ts"):
        end = e
    else:
        end = _parse_ts(ev["end_ts"]) or start
    lo, hi = max(start, s), min(end, e)
    return (lo, hi) if hi > lo else None


def event_hours(ev, month):
    if ev.get("hours_lost_override") is not None:
        s, e = _bounds(month)
        start = _parse_ts(ev["start_ts"])
        if start is None:
            return 0.0
        return float(ev["hours_lost_override"]) if s <= start < e else 0.0
    iv = event_interval(ev, month)
    return (iv[1] - iv[0]).total_seconds() / 3600.0 if iv else 0.0


def _merged_hours(intervals):
    total, cur_lo, cur_hi = 0.0, None, None
    for lo, hi in sorted(intervals):
        if cur_hi is None or lo > cur_hi:
            if cur_hi is not None:
                total += (cur_hi - cur_lo).total_seconds() / 3600.0
            cur_lo, cur_hi = lo, hi
        elif hi > cur_hi:
            cur_hi = hi
    if cur_hi is not None:
        total += (cur_hi - cur_lo).total_seconds() / 3600.0
    return total


def clean_cause(cause, unit_name):
    s = re.sub(r"\s+", " ", cause or "").strip()
    s = re.sub(r"\s*w\.?\s*e\.?\s*f\.?\b.*$", "", s, flags=re.I)
    if unit_name and s.lower().startswith(unit_name.lower()):
        s = s[len(unit_name):].lstrip(" :-")
    s = s.rstrip(" ,;-")
    return s[:90].rstrip() + "…" if len(s) > 90 else s


def unit_summaries(events, month):
    s, e = _bounds(month)
    cap = (e - s).total_seconds() / 3600.0
    agg = {}
    for ev in events:
        h = event_hours(ev, month)
        if h <= 0:
            continue
        k = (ev["plant"], ev["unit_type"], ev["unit_name"])
        a = agg.setdefault(k, {"plant": k[0], "unit_type": k[1], "unit_name": k[2], "hours": 0.0,
                               "_top": (0.0, ""), "_iv": [], "_pt": 0.0})
        iv = event_interval(ev, month)
        if iv:
            a["_iv"].append(iv)
        else:
            a["_pt"] += h
        if h > a["_top"][0]:
            a["_top"] = (h, ev.get("cause") or "")
    out = []
    for a in agg.values():
        a["hours"] = min(_merged_hours(a.pop("_iv")) + a.pop("_pt"), cap)
        if a["hours"] >= BD_MIN_HOURS:
            top = a.pop("_top")
            a["cause"] = clean_cause(top[1], a["unit_name"])
            out.append(a)
    out.sort(key=lambda a: (a["plant"], a["unit_type"], a["unit_name"]))
    return out


def _days(hours):
    d = round(hours / 24)
    return f"{d} day" if d == 1 else f"{d} days"


def _unit_label(name):
    """'Shop: BF' -> 'BF', so the line doesn't read 'Shop: BF: cause'."""
    return re.sub(r"^\s*shop\s*:\s*", "", name or "", flags=re.I)


def _unit_line(a):
    name = _unit_label(a["unit_name"])
    head = f"{name}: {a['cause']}" if a["cause"] else name
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


def _hl_texts(cur, month, labels):
    out = {"hl_SAIL": highlight_text(cur, "SAIL", labels)}
    for p in PLANTS:
        out[f"hl_{p}"] = highlight_text(cur, p, labels)
    return out


def _bd_texts(cur, month, labels):
    """Delay (slides 4, 6) and breakdown (slides 21-24) blocks."""
    summaries = unit_summaries(_fetch_breakdowns(cur, month), month)
    out = {"delay_hmcs": delay_text(summaries, HMCS_TYPES, labels["mon"]),
           "delay_fs": delay_text(summaries, FS_TYPES, labels["mon"])}
    for p in BD_PLANTS:
        for g, _ in BD_GROUPS:
            out[f"bd_{p}_{g}"] = bd_group_text(summaries, p, g)
    return out


def _cr_texts(cur, month, labels):
    y, m = int(month[:4]), int(month[5:7])
    upto = dt.date(y, m, calendar.monthrange(y, m)[1])
    upto_prev = dt.date(y - 1, m, calendar.monthrange(y - 1, m)[1])
    fy_window = bnc.fy_months(labels["fy_start"])
    out = {}
    for p in PLANTS:
        out[f"cr_{p}_cur"] = "\n".join(cr_line(r, upto) for r in _fetch_cr(cur, p, labels["fy_label"], upto))
        prev = "\n".join(cr_line(r, upto_prev) for r in _fetch_cr(cur, p, labels["fy_prev_label"], upto_prev))
        out[f"cr_{p}_prev"] = prev or (srt.latest_saved_before(f"cr_{p}_prev", month, fy_window) or "")
    return out


def _kind_fn(key):
    if key.startswith("hl_"):
        return _hl_texts
    if key.startswith(("delay_", "bd_")):
        return _bd_texts
    return _cr_texts


def default_texts(month, keys=None):
    """DB-derived text for every block, or only for the kinds (highlights,
    delays/breakdowns, capital repairs) that `keys` needs. Returns all 30
    keys; blocks outside `keys`' kinds are ''."""
    labels = period_labels(month)
    wanted = [k for k, _, _ in BLOCKS] if keys is None else list(keys)
    fns = []
    for k in wanted:
        fn = _kind_fn(k)
        if fn not in fns:
            fns.append(fn)
    out = {}
    if fns:
        conn = db.connect()
        cur = conn.cursor()
        try:
            for fn in fns:
                out.update(fn(cur, month, labels))
        finally:
            conn.close()
    return {k: out.get(k, "") for k, _, _ in BLOCKS}


def default_text(month, key):
    """One block's DB-derived text, computing only that block's kind."""
    return default_texts(month, [key]).get(key, "")


def effective_texts(month, keys=None):
    """{key: {"text", "saved"}} for every block, or only `keys`. Defaults are
    computed only for requested blocks with no saved text."""
    wanted = [k for k, _, _ in BLOCKS] if keys is None else [k for k, _, _ in BLOCKS if k in set(keys)]
    saved = srt.get_texts(month)
    missing = [k for k in wanted if k not in saved]
    defaults = default_texts(month, missing) if missing else {}
    return {k: {"text": saved[k] if k in saved else defaults.get(k, ""), "saved": k in saved}
            for k in wanted}
