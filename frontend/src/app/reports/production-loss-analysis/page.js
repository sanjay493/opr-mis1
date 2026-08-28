'use client';

import React, { useState, useCallback, useMemo, useEffect } from 'react';
import GlobalNavbar from '@/components/GlobalNavbar';
import {
  ResponsiveContainer, ComposedChart, CartesianGrid, XAxis, YAxis,
  Tooltip, Legend, Bar, Line,
} from 'recharts';

const API = process.env.NEXT_PUBLIC_API_URL || '';

const PLANTS = [
  { code: 'BSP', label: 'Bhilai Steel Plant' },
  { code: 'DSP', label: 'Durgapur Steel Plant' },
  { code: 'RSP', label: 'Rourkela Steel Plant' },
  { code: 'BSL', label: 'Bokaro Steel Plant' },
  { code: 'ISP', label: 'IISCO Steel Plant' },
];

const ITEMS = [
  { code: 'HM', label: 'Hot Metal' },
  { code: 'CS', label: 'Crude Steel' },
  { code: 'FS', label: 'Finished Steel' },
];

// Validated (dataviz skill, node scripts/validate_palette.js) 3-hue set —
// worst-pair CVD ΔE 9.2, normal-vision ΔE 24.0, all-pairs, light mode.
// Aqua sits below 3:1 contrast on the surface (2.74) — the relief rule
// applies, so it is never used for text, only fills, and every value is
// also carried in the legend, tooltip, and the table below the chart.
const C = {
  actual: '#2a78d6',      // blue  — achieved production
  crOverrun: '#eb6834',   // orange — CR overrun loss
  breakdown: '#1baf7a',   // aqua  — breakdown loss
  residual: '#c3c2b7',    // neutral gray — unexplained residual
  plan: '#52514e',        // secondary ink — Plan reference line (not a series)
  compare: '#2a78d6',     // same hue as Actual, distinguished by dash + markers
  textPrimary: '#202124',
  textSecondary: '#5f6368',
  grid: '#e1e0d9',
};

const MONTH_NAMES = ['Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec', 'Jan', 'Feb', 'Mar'];
function monthLabel(m) {
  // 'YYYY-MM' -> 'Jun 2026'
  const [y, mm] = m.split('-');
  return `${MONTH_NAMES[(parseInt(mm, 10) - 4 + 12) % 12]} ${y}`;
}

// 'YYYY-MM' + n months (n may be negative) -> 'YYYY-MM'.
function shiftMonth(m, n) {
  let [y, mm] = m.split('-').map(Number);
  mm += n;
  y += Math.floor((mm - 1) / 12);
  mm = ((mm - 1) % 12 + 12) % 12 + 1;
  return `${String(y).padStart(4, '0')}-${String(mm).padStart(2, '0')}`;
}

// '2026-27' + n years -> '2025-26' (n=-1) etc.
function shiftFY(fy, n) {
  const startYear = parseInt(fy.slice(0, 4), 10) + n;
  return `${startYear}-${String((startYear + 1) % 100).padStart(2, '0')}`;
}

function monthCount(start, end) {
  const [y1, m1] = start.split('-').map(Number);
  const [y2, m2] = end.split('-').map(Number);
  return (y2 - y1) * 12 + (m2 - m1) + 1;
}

// Quarter/half-year presets for a given FY ('2026-27') — Indian FY (Apr-Mar):
// Q1 Apr-Jun, Q2 Jul-Sep, Q3 Oct-Dec, Q4 Jan-Mar; H1 Apr-Sep, H2 Oct-Mar.
const RANGE_PRESETS = [
  { code: 'Q1', label: 'Q1', offset: 0, len: 3 },
  { code: 'Q2', label: 'Q2', offset: 3, len: 3 },
  { code: 'Q3', label: 'Q3', offset: 6, len: 3 },
  { code: 'Q4', label: 'Q4', offset: 9, len: 3 },
  { code: 'H1', label: 'H1', offset: 0, len: 6 },
  { code: 'H2', label: 'H2', offset: 6, len: 6 },
];
function presetRange(fy, preset) {
  const fyStart = `${fy.slice(0, 4)}-04`; // April of the FY start year
  const start = shiftMonth(fyStart, preset.offset);
  const end = shiftMonth(start, preset.len - 1);
  return { start, end };
}

// Default period shape: { kind: 'fy'|'month'|'range', value, start, end }
function defaultPeriod(kind, seed) {
  if (kind === 'fy') return { kind, value: seed || '2026-27', start: '', end: '' };
  if (kind === 'month') return { kind, value: seed || '2026-06', start: '', end: '' };
  return { kind: 'range', value: '', start: seed?.start || '2026-04', end: seed?.end || '2026-06' };
}

// Derive Period B from Period A for the CPLY/CPLM quick-compare modes —
// pure date math, resolved client-side into a concrete month/fy/range period
// before the request is sent, so the backend never needs to know what
// "CPLY"/"CPLM" mean.
function deriveComparePeriod(periodA, mode) {
  if (mode === 'cply') {
    if (periodA.kind === 'fy') return { kind: 'fy', value: shiftFY(periodA.value, -1) };
    if (periodA.kind === 'month') return { kind: 'month', value: shiftMonth(periodA.value, -12) };
    return { kind: 'range', start: shiftMonth(periodA.start, -12), end: shiftMonth(periodA.end, -12) };
  }
  if (mode === 'cplm') {
    if (periodA.kind === 'month') return { kind: 'month', value: shiftMonth(periodA.value, -1) };
    if (periodA.kind === 'range') {
      const len = monthCount(periodA.start, periodA.end);
      return { kind: 'range', end: shiftMonth(periodA.start, -1), start: shiftMonth(periodA.start, -len) };
    }
    return null; // CPLM isn't offered for a Full-FY period — see the mode filter below
  }
  return null;
}

function periodLabel(p) {
  if (!p) return '';
  if (p.kind === 'fy') return `FY ${p.value}`;
  if (p.kind === 'month') return monthLabel(p.value);
  return `${monthLabel(p.start)} – ${monthLabel(p.end)}`;
}

function fmt(n) {
  if (n === null || n === undefined) return '—';
  return Math.round(n).toLocaleString('en-IN');
}

const S = {
  card: { background: '#fff', border: '1px solid #dadce0', borderRadius: 8, padding: '16px 18px' },
  label: { fontSize: 13, fontWeight: 600, color: '#374151' },
  select: { padding: '7px 10px', fontSize: 14, border: '1px solid #d1d5db', borderRadius: 4 },
  statTile: { flex: '1 1 140px', border: '1px solid #dadce0', borderRadius: 8, padding: '12px 14px', background: '#fff' },
  statLabel: { fontSize: 12, color: '#5f6368', marginBottom: 4 },
  statValue: { fontSize: 20, fontWeight: 700, color: '#202124' },
};

function StatTile({ label, value, color }) {
  return (
    <div style={S.statTile}>
      <div style={S.statLabel}>{label}</div>
      <div style={{ ...S.statValue, color: color || S.statValue.color }}>{fmt(value)} <span style={{ fontSize: 12, fontWeight: 500, color: '#9aa0a6' }}>T</span></div>
    </div>
  );
}

function CustomTooltip({ active, payload, label }) {
  if (!active || !payload || !payload.length) return null;
  return (
    <div style={{ background: '#fff', border: '1px solid #dadce0', borderRadius: 6, padding: '10px 12px', fontSize: 12.5, boxShadow: '0 2px 8px rgba(0,0,0,0.08)' }}>
      <div style={{ fontWeight: 700, marginBottom: 6 }}>{label}</div>
      {payload.map(p => (
        <div key={p.dataKey} style={{ display: 'flex', justifyContent: 'space-between', gap: 16, color: '#374151' }}>
          <span style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
            <span style={{ width: 8, height: 8, borderRadius: 4, background: p.color, display: 'inline-block' }} />
            {p.name}
          </span>
          <span style={{ fontWeight: 600 }}>{fmt(p.value)} T</span>
        </div>
      ))}
    </div>
  );
}

function unitLabel(ev) {
  if (!ev.sms_subtag) return ev.unit_name;
  return `${ev.unit_name} (${ev.sms_subtag.charAt(0)}${ev.sms_subtag.slice(1).toLowerCase()})`;
}

// Crisp one-line summary: "<unit> under CR/BD for <detail> — <days> ...",
// with the overrun day count called out specifically for CR (that's the
// only source where "days" is ambiguous between total duration and the
// days that actually count toward loss).
function crispEventText(ev) {
  const unit = unitLabel(ev);
  if (ev.source === 'cr') {
    const detail = ev.activity || 'Capital Repair';
    if (ev.overrun_days_this_month) {
      return `${unit} under CR for ${detail} — ${ev.overrun_days_this_month} day(s) overrun`;
    }
    if (ev.planned_days_missing) {
      return `${unit} under CR for ${detail} — planned days not set, can't assess overrun`;
    }
    if (ev.status === 'overrun') return `${unit} under CR for ${detail} — overrun (outside this period)`;
    if (ev.status === 'ongoing') return `${unit} under CR for ${detail} — ongoing, within schedule`;
    if (ev.status === 'on-schedule') return `${unit} under CR for ${detail} — on schedule (no loss)`;
    return `${unit} under CR for ${detail} — not started`;
  }
  const detail = ev.cause_text || 'breakdown';
  if (ev.days_this_month) {
    return `${unit} under BD for ${detail} — ${ev.days_this_month} day(s)`;
  }
  return `${unit} under BD for ${detail} — ${ev.is_ongoing ? 'ongoing, outside this period' : 'outside this period'}`;
}

// A CR/breakdown row is repeated across every month of the report (so its
// per-month overlap can be attributed), which would otherwise flood the list
// with "outside this period" duplicates for events that never contribute a
// loss. Keep one line per (event, month) only where the event is actually
// relevant that month; collapse everything else — CR rows that stay
// on-schedule all period, breakdowns outside this date range — into a
// single summary line per event, so nothing is dropped but nothing repeats
// needlessly either.
function dedupeEvents(monthly) {
  const isRelevant = ev => (ev.source === 'cr' ? !!ev.overrun_days_this_month : !!ev.days_this_month);

  // Pass 1 — every (event, month) where the event actually contributes a
  // loss that month, plus the set of event keys that are relevant *somewhere*.
  const relevantRows = [];
  const relevantKeys = new Set();
  monthly.forEach(m => {
    m.events.forEach(ev => {
      if (!isRelevant(ev)) return;
      relevantRows.push({ month: m.month, relevant: true, ...ev });
      relevantKeys.add(`${ev.source}-${ev.id}`);
    });
  });

  // Pass 2 — one summary line for events that never contribute a loss in
  // this period. An event already shown in pass 1 is skipped entirely, so
  // it never doubles up as a greyed "outside this period" row.
  const seenNonRelevant = new Map();
  monthly.forEach(m => {
    m.events.forEach(ev => {
      const key = `${ev.source}-${ev.id}`;
      if (relevantKeys.has(key) || seenNonRelevant.has(key)) return;
      seenNonRelevant.set(key, { month: null, relevant: false, ...ev });
    });
  });

  const rows = [...relevantRows, ...seenNonRelevant.values()];
  rows.sort((a, b) => (b.relevant - a.relevant) || (b.month || '').localeCompare(a.month || ''));
  return rows;
}

function EventsList({ monthly, label }) {
  const rows = useMemo(() => dedupeEvents(monthly), [monthly]);

  return (
    <div>
      {label && <div style={{ fontWeight: 700, fontSize: 13, color: '#374151', marginBottom: 8 }}>{label}</div>}
      {rows.length === 0 ? (
        <div style={{ padding: 20, textAlign: 'center', color: '#5f6368', fontSize: 13 }}>
          No Capital Repair or Breakdown events found for these months.
        </div>
      ) : (
        <div style={{ maxHeight: 420, overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: 1 }}>
          {rows.map((ev, i) => (
            <div key={i} style={{
              display: 'flex', gap: 8, alignItems: 'baseline', padding: '6px 8px',
              borderLeft: `3px solid ${ev.relevant ? (ev.source === 'cr' ? C.crOverrun : C.breakdown) : '#e1e0d9'}`,
              background: ev.relevant ? (ev.source === 'cr' ? '#fff7ed' : '#f0fdfa') : '#fff',
            }}>
              <span style={{ fontSize: 11, color: '#9aa0a6', minWidth: 62, flexShrink: 0 }}>{ev.month || '—'}</span>
              <span style={{ fontSize: 13, lineHeight: 1.4, maxWidth: 820, fontWeight: ev.relevant ? 600 : 400, color: ev.relevant ? '#202124' : '#9aa0a6' }}>
                {crispEventText(ev)}
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function PeriodFields({ period, onChange }) {
  const [presetFY, setPresetFY] = useState(period.kind === 'fy' ? period.value : '2026-27');

  const setKind = (kind) => onChange(defaultPeriod(kind, kind === 'range' ? { start: period.start, end: period.end } : period.value));

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
      <select style={S.select} value={period.kind} onChange={e => setKind(e.target.value)}>
        <option value="fy">Full FY</option>
        <option value="month">Single month</option>
        <option value="range">Custom range (quarter / half-year / N months)</option>
      </select>

      {period.kind === 'fy' && (
        <input style={{ ...S.select, width: 100 }} value={period.value}
          onChange={e => onChange({ ...period, value: e.target.value })} placeholder="2026-27" />
      )}

      {period.kind === 'month' && (
        <input type="month" style={{ ...S.select, width: 140 }} value={period.value}
          onChange={e => onChange({ ...period, value: e.target.value })} />
      )}

      {period.kind === 'range' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
          <div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
            <input type="month" style={{ ...S.select, width: 140 }} value={period.start}
              onChange={e => onChange({ ...period, start: e.target.value })} />
            <span style={{ color: '#9aa0a6' }}>–</span>
            <input type="month" style={{ ...S.select, width: 140 }} value={period.end}
              onChange={e => onChange({ ...period, end: e.target.value })} />
          </div>
          <div style={{ display: 'flex', gap: 4, alignItems: 'center', flexWrap: 'wrap' }}>
            <span style={{ fontSize: 11.5, color: '#9aa0a6' }}>presets for FY</span>
            <input style={{ ...S.select, width: 66, padding: '3px 6px', fontSize: 12 }} value={presetFY}
              onChange={e => setPresetFY(e.target.value)} placeholder="2026-27" />
            {RANGE_PRESETS.map(p => (
              <button key={p.code} type="button"
                onClick={() => onChange({ ...period, ...presetRange(presetFY, p) })}
                style={{ padding: '3px 8px', fontSize: 11.5, border: '1px solid #d1d5db', borderRadius: 4,
                         background: '#f8f9fa', color: '#374151', cursor: 'pointer' }}>
                {p.label}
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

function ProductionLossAnalysisInner() {
  const [plant, setPlant] = useState('BSP');
  const [item, setItem] = useState('HM');
  const [periodA, setPeriodA] = useState(() => defaultPeriod('fy', '2026-27'));
  // compareMode: 'none' | 'cply' | 'cplm' | 'custom'
  const [compareMode, setCompareMode] = useState('none');
  const [periodBCustom, setPeriodBCustom] = useState(() => defaultPeriod('fy', '2025-26'));

  const [report, setReport] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  // Frozen at load time (not live-reactive to periodA/periodBCustom edits
  // the user makes afterward, before clicking Load Analysis again) so the
  // header/legend always describes the report actually on screen.
  const [loadedLabelA, setLoadedLabelA] = useState('');
  const [loadedLabelB, setLoadedLabelB] = useState('');

  // CPLM has no meaning for a Full-FY period (there's no "previous FY-length
  // window immediately before a FY" distinct from "the prior FY", which CPLY
  // already covers) — hide it from the dropdown in that case.
  const compareOptions = useMemo(() => {
    const opts = [{ v: 'none', label: 'None' }, { v: 'cply', label: 'CPLY (same period, last year)' }];
    if (periodA.kind !== 'fy') opts.push({ v: 'cplm', label: 'CPLM (immediately preceding period)' });
    opts.push({ v: 'custom', label: 'Custom period' });
    return opts;
  }, [periodA.kind]);

  useEffect(() => {
    if (periodA.kind === 'fy' && compareMode === 'cplm') setCompareMode('none');
  }, [periodA.kind, compareMode]);

  const resolvedPeriodB = useMemo(() => {
    if (compareMode === 'none') return null;
    if (compareMode === 'custom') return periodBCustom;
    return deriveComparePeriod(periodA, compareMode);
  }, [compareMode, periodA, periodBCustom]);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const addPeriod = (params, prefix, p) => {
        params.set(`${prefix}_kind`, p.kind);
        if (p.kind === 'range') {
          params.set(`${prefix}_start`, p.start);
          params.set(`${prefix}_end`, p.end);
        } else {
          params.set(`${prefix}_value`, p.value);
        }
      };
      const params = new URLSearchParams({ plant, item });
      addPeriod(params, 'period_a', periodA);
      if (resolvedPeriodB) addPeriod(params, 'period_b', resolvedPeriodB);
      const res = await fetch(`${API}/api/production-loss-analysis?${params.toString()}`);
      if (!res.ok) throw new Error(await res.text());
      setReport(await res.json());
      setLoadedLabelA(periodLabel(periodA));
      setLoadedLabelB(resolvedPeriodB ? periodLabel(resolvedPeriodB) : '');
    } catch (err) {
      setError(err.message);
      setReport(null);
    } finally {
      setLoading(false);
    }
  }, [plant, item, periodA, resolvedPeriodB]);

  const chartData = useMemo(() => {
    if (!report) return [];
    const a = report.series_a.monthly;
    const b = report.series_b?.monthly || [];
    return a.map((m, i) => {
      // A month with no reported Actual yet contributes nothing to the
      // stacked bar or the to-date totals — only its Plan point and any
      // comparison Actual are still meaningful. (The loss the engine can
      // derive off the ABP rate for such a month would otherwise draw a
      // bar the totals row deliberately excludes — see `totals`.)
      const reported = m.actual !== null && m.actual !== undefined;
      return {
        x: monthLabel(m.month),
        plan: m.plan,
        actual: reported ? m.actual : null,
        cr_overrun_loss_t: reported ? m.cr_overrun_loss_t : null,
        breakdown_loss_t: reported ? m.breakdown_loss_t : null,
        residual_t: reported && m.residual_t != null ? Math.max(0, m.residual_t) : null,
        compareActual: b[i] ? b[i].actual : null,
        compareMonth: b[i] ? b[i].month : null,
      };
    });
  }, [report]);

  const totals = useMemo(() => {
    if (!report) return null;
    // Summing Plan across all 12 FY months while Actual is only reported for
    // the months so far (production_table has no row yet for future months)
    // would compare a full-year Plan against a partial-year Actual and make
    // the shortfall look far larger than it is. Total only over "reported"
    // months — those with a non-null actual — so Plan and Actual cover the
    // same window; a reported 0 still counts (only a genuinely missing row
    // is excluded).
    const all = report.series_a.monthly;
    const reported = all.filter(m => m.actual !== null && m.actual !== undefined);
    const sum = (rows, k) => rows.reduce((s, m) => s + (m[k] || 0), 0);
    return {
      plan: sum(reported, 'plan'), actual: sum(reported, 'actual'),
      cr_overrun_loss_t: sum(reported, 'cr_overrun_loss_t'), breakdown_loss_t: sum(reported, 'breakdown_loss_t'),
      residual_t: sum(reported, 'residual_t'),
      reportedCount: reported.length, totalCount: all.length,
    };
  }, [report]);

  const unclassifiedCount = useMemo(() => {
    if (!report) return 0;
    const ids = new Set();
    report.series_a.monthly.forEach(m => m.unclassified_events.forEach(e => ids.add(`${e.source}-${e.id}`)));
    return ids.size;
  }, [report]);

  const allMonthly = useMemo(() => report ? report.series_a.monthly : [], [report]);
  const plantLabel = PLANTS.find(p => p.code === plant)?.label || plant;
  const itemLabel = ITEMS.find(i => i.code === item)?.label || item;

  return (
    <div style={{ height: '100vh', display: 'flex', flexDirection: 'column', background: '#ffffff' }}>
      <GlobalNavbar />
      <div style={{ flex: 1, overflow: 'auto', maxWidth: 1500, margin: '0 auto', padding: '22px 20px', width: '100%', boxSizing: 'border-box' }}>

        <div style={{ marginBottom: 18 }}>
          <h2 style={{ fontSize: '1.6rem', fontWeight: 700, color: '#202124', margin: '0 0 4px' }}>
            Production Loss Analysis
          </h2>
          <span style={{ fontSize: 13, color: '#5f6368' }}>
            Hot Metal / Crude Steel / Finished Steel vs. ABP, with the Capital Repair overrun and Breakdown
            events that explain a shortfall. The ABP already accounts for on-schedule Capital Repair — only
            the days a repair runs <em>beyond</em> its planned schedule count here, alongside the full span
            of any breakdown.
          </span>
        </div>

        <div style={{ ...S.card, display: 'flex', gap: 14, alignItems: 'flex-start', flexWrap: 'wrap', marginBottom: 18 }}>
          <div>
            <div style={S.label}>Plant</div>
            <select style={S.select} value={plant} onChange={e => setPlant(e.target.value)}>
              {PLANTS.map(p => <option key={p.code} value={p.code}>{p.code} — {p.label}</option>)}
            </select>
          </div>
          <div>
            <div style={S.label}>Item</div>
            <select style={S.select} value={item} onChange={e => setItem(e.target.value)}>
              {ITEMS.map(i => <option key={i.code} value={i.code}>{i.label}</option>)}
            </select>
          </div>
          <div>
            <div style={S.label}>Period</div>
            <PeriodFields period={periodA} onChange={setPeriodA} />
          </div>
          <div>
            <div style={S.label}>Compare with</div>
            <select style={S.select} value={compareMode} onChange={e => setCompareMode(e.target.value)}>
              {compareOptions.map(o => <option key={o.v} value={o.v}>{o.label}</option>)}
            </select>
            {compareMode === 'custom' && (
              <div style={{ marginTop: 6 }}>
                <PeriodFields period={periodBCustom} onChange={setPeriodBCustom} />
              </div>
            )}
            {(compareMode === 'cply' || compareMode === 'cplm') && resolvedPeriodB && (
              <div style={{ fontSize: 11.5, color: '#5f6368', marginTop: 6 }}>
                → {periodLabel(resolvedPeriodB)}
              </div>
            )}
          </div>
          <div>
            <div style={{ ...S.label, visibility: 'hidden' }}>Run</div>
            <button onClick={load} disabled={loading} style={{
              padding: '8px 22px', fontSize: 14, fontWeight: 600,
              background: '#1a73e8', color: '#fff', border: 'none', borderRadius: 4,
              cursor: loading ? 'not-allowed' : 'pointer',
            }}>
              {loading ? 'Loading…' : 'Load Analysis'}
            </button>
          </div>
        </div>

        {error && (
          <div style={{ padding: '10px 16px', borderRadius: 6, marginBottom: 14, fontSize: 14, background: '#fef2f2', color: '#991b1b', border: '1px solid #fca5a5' }}>
            {error}
          </div>
        )}

        {!report && !loading && !error && (
          <div style={{ padding: 48, textAlign: 'center', backgroundColor: '#fff', border: '2px dashed #dadce0', borderRadius: 8, color: '#5f6368' }}>
            Choose a plant, item and period, then click <strong>Load Analysis</strong>.
          </div>
        )}

        {report && totals && (
          <>
            <div style={{ fontSize: 12.5, color: '#5f6368', marginBottom: 8 }}>
              Totals below are <strong>to-date</strong> — {totals.reportedCount} of {totals.totalCount} month
              {totals.totalCount !== 1 ? 's' : ''} in {loadedLabelA} have reported Actual production
              {totals.reportedCount < totals.totalCount && ' (remaining months have no data yet, so they\'re excluded from both Plan and Actual here)'}.
            </div>
            <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap', marginBottom: 18 }}>
              <StatTile label={`Plan to-date — ${plantLabel} (${itemLabel})`} value={totals.plan} />
              <StatTile label="Actual to-date" value={totals.actual} color={C.actual} />
              <StatTile label="Shortfall vs Plan" value={totals.plan - totals.actual} color="#6b6a64" />
              <StatTile label="CR Overrun Loss" value={totals.cr_overrun_loss_t} color={C.crOverrun} />
              <StatTile label="Breakdown Loss" value={totals.breakdown_loss_t} color={C.breakdown} />
              <StatTile label="Residual — net, unexplained" value={totals.residual_t} color="#6b6a64" />
            </div>
            <div style={{ fontSize: 11.5, color: '#9aa0a6', marginTop: -10, marginBottom: 18 }}>
              Shortfall vs Plan = CR Overrun Loss + Breakdown Loss + Residual. Residual is a{' '}
              <em>net</em> figure — months that beat plan offset months that miss it; a negative value
              means Actual ran ahead of Plan overall.
            </div>

            {unclassifiedCount > 0 && (
              <div style={{ padding: '10px 16px', borderRadius: 6, marginBottom: 14, fontSize: 13, background: '#fffbeb', color: '#92400e', border: '1px solid #fde68a' }}>
                {unclassifiedCount}{' '}Capital Repair / Breakdown row(s) in this period have no unit classification yet,
                so they aren&apos;t counted above — assign a Unit on the{' '}
                <a href="/data-entry/capital-repair" style={{ color: '#92400e', fontWeight: 600 }}>Capital Repair</a> or{' '}
                <a href="/data-entry/breakdown" style={{ color: '#92400e', fontWeight: 600 }}>Breakdown</a> data-entry page to include them.
              </div>
            )}

            <div style={{ ...S.card, marginBottom: 18 }}>
              <div style={{ fontWeight: 700, fontSize: 14, marginBottom: 4 }}>
                {itemLabel} — {plantLabel} — {loadedLabelA}
                {report.series_b && <span style={{ fontWeight: 500, color: '#5f6368' }}> vs. {loadedLabelB}</span>}
              </div>
              <div style={{ fontSize: 12, color: '#5f6368', marginBottom: 10 }}>
                Stacked bar = Actual + CR Overrun Loss + Breakdown Loss + Residual (reconciles up toward the Plan line).
              </div>
              <ResponsiveContainer width="100%" height={360}>
                <ComposedChart data={chartData} margin={{ top: 10, right: 20, left: 0, bottom: 4 }}>
                  <CartesianGrid stroke={C.grid} vertical={false} />
                  <XAxis dataKey="x" tick={{ fontSize: 12, fill: C.textSecondary }} axisLine={{ stroke: '#c3c2b7' }} tickLine={false} />
                  <YAxis tick={{ fontSize: 12, fill: C.textSecondary }} axisLine={false} tickLine={false}
                    tickFormatter={v => v.toLocaleString('en-IN')} width={64} />
                  <Tooltip content={<CustomTooltip />} />
                  <Legend wrapperStyle={{ fontSize: 12.5 }} />
                  <Bar dataKey="actual" name="Actual" stackId="s" fill={C.actual} maxBarSize={24} />
                  <Bar dataKey="cr_overrun_loss_t" name="CR Overrun Loss" stackId="s" fill={C.crOverrun} maxBarSize={24} />
                  <Bar dataKey="breakdown_loss_t" name="Breakdown Loss" stackId="s" fill={C.breakdown} maxBarSize={24} />
                  <Bar dataKey="residual_t" name="Residual (net, unexplained)" stackId="s" fill={C.residual} maxBarSize={24} radius={[4, 4, 0, 0]} />
                  <Line dataKey="plan" name="Plan (ABP)" stroke={C.plan} strokeWidth={2} strokeDasharray="4 3" dot={false} />
                  {report.series_b && (
                    <Line dataKey="compareActual" name={`Actual (${loadedLabelB})`}
                      stroke={C.compare} strokeWidth={2} strokeDasharray="2 2" dot={{ r: 4, fill: C.compare, stroke: '#fff', strokeWidth: 2 }} />
                  )}
                </ComposedChart>
              </ResponsiveContainer>
            </div>

            <div style={S.card}>
              <div style={{ fontWeight: 700, fontSize: 14, marginBottom: 10 }}>
                Capital Repair &amp; Breakdown events
              </div>
              {report.series_b ? (
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
                  <EventsList monthly={report.series_a.monthly} label={loadedLabelA} />
                  <EventsList monthly={report.series_b.monthly} label={loadedLabelB} />
                </div>
              ) : (
                <EventsList monthly={allMonthly} />
              )}
            </div>
          </>
        )}
      </div>
    </div>
  );
}

export default function ProductionLossAnalysisPage() {
  return <ProductionLossAnalysisInner />;
}
