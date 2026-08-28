'use client';

import React, { useState, useEffect, useMemo } from 'react';
import Link from 'next/link';
import GlobalNavbar from '@/components/GlobalNavbar';
import {
  ResponsiveContainer, ComposedChart, BarChart, CartesianGrid, XAxis, YAxis,
  Tooltip, Bar, Line, Cell,
} from 'recharts';

const API = process.env.NEXT_PUBLIC_API_URL || '';

const PLANTS = [
  { code: 'BSP', label: 'Bhilai Steel Plant' },
  { code: 'DSP', label: 'Durgapur Steel Plant' },
  { code: 'RSP', label: 'Rourkela Steel Plant' },
  { code: 'BSL', label: 'Bokaro Steel Plant' },
  { code: 'ISP', label: 'IISCO Steel Plant' },
];
const PLANT_LABEL = Object.fromEntries(PLANTS.map(p => [p.code, p.label]));

const UNIT_TYPES = [
  { code: 'BF', label: 'Blast Furnace' },
  { code: 'SMS', label: 'SMS (Converter/Caster)' },
  { code: 'MILL', label: 'Rolling Mill' },
  { code: 'COKE', label: 'Coke Oven' },
  { code: 'SINTER', label: 'Sinter Plant' },
  { code: 'GENERAL', label: 'Plant-Level General' },
];
const UNIT_TYPE_LABEL = Object.fromEntries(UNIT_TYPES.map(t => [t.code, t.label]));

// Validated categorical hues (dataviz skill palette, light mode).
const C = {
  a: '#2a78d6', b: '#eb6834', c: '#1baf7a', d: '#f2b134', e: '#9b59b6', f: '#5a6b7b',
  ink: '#202124', sub: '#5f6368', grid: '#e1e0d9',
};
const TYPE_COLOR = { BF: C.a, SMS: C.b, MILL: C.c, COKE: C.d, SINTER: C.e, GENERAL: C.f };

const MONTH_NAMES = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];

function parseTs(ts) {
  if (!ts) return null;
  const d = new Date(String(ts).replace(' ', 'T'));
  return Number.isNaN(d.getTime()) ? null : d;
}

function spanHours(startTs, endTs, isOngoing) {
  const s = parseTs(startTs);
  if (!s) return null;
  const e = isOngoing ? new Date() : parseTs(endTs);
  if (!e) return null;
  return Math.max(0, (e.getTime() - s.getTime()) / 3600000);
}

function fmtDuration(hours) {
  if (hours == null) return '—';
  const totalMin = Math.round(hours * 60);
  const d = Math.floor(totalMin / 1440);
  const h = Math.floor((totalMin % 1440) / 60);
  const m = totalMin % 60;
  const parts = [];
  if (d) parts.push(`${d}d`);
  if (h) parts.push(`${h}h`);
  if (m && !d) parts.push(`${m}m`);
  return parts.join(' ') || '0m';
}

function fmtHrs(h, dp = 1) {
  if (h == null) return '—';
  return Number(h).toLocaleString('en-IN', { maximumFractionDigits: dp });
}

function fmtDateShort(ts) {
  const d = parseTs(ts);
  if (!d) return ts || '—';
  return d.toLocaleString('en-IN', { day: '2-digit', month: 'short', year: '2-digit', hour: '2-digit', minute: '2-digit', hour12: false });
}

function fyOf(ts) {
  if (!ts) return null;
  const y = parseInt(String(ts).slice(0, 4), 10);
  const mo = parseInt(String(ts).slice(5, 7), 10);
  if (!y || !mo) return null;
  const start = mo >= 4 ? y : y - 1;
  return `${start}-${String((start + 1) % 100).padStart(2, '0')}`;
}

function monthKey(ts) { return String(ts).slice(0, 7); } // YYYY-MM
function monthLabel(ym) {
  const [y, m] = ym.split('-');
  return `${MONTH_NAMES[parseInt(m, 10) - 1]} '${y.slice(2)}`;
}

const S = {
  card: { background: '#fff', border: '1px solid #dadce0', borderRadius: 8, padding: '16px 18px' },
  label: { fontSize: 12, fontWeight: 700, color: '#5f6368', textTransform: 'uppercase', letterSpacing: '0.03em' },
  select: { padding: '8px 10px', fontSize: 13.5, border: '1px solid #d1d5db', borderRadius: 6, background: '#fff' },
  input: { padding: '8px 10px', fontSize: 13.5, border: '1px solid #d1d5db', borderRadius: 6, background: '#fff' },
  H: { padding: '9px 11px', textAlign: 'left', fontWeight: 700, color: '#5f6368', borderBottom: '1px solid #dadce0', fontSize: 12, backgroundColor: '#f8f9fa', whiteSpace: 'nowrap', textTransform: 'uppercase', letterSpacing: '0.02em', position: 'sticky', top: 0, cursor: 'pointer' },
  TD: { padding: '9px 11px', borderBottom: '1px solid #f0f4f8', fontSize: 13, verticalAlign: 'top' },
};

function StatTile({ label, value, sub, color }) {
  return (
    <div style={{ flex: '1 1 150px', border: '1px solid #dadce0', borderRadius: 8, padding: '12px 14px', background: '#fff' }}>
      <div style={{ fontSize: 11.5, color: '#5f6368', marginBottom: 4 }}>{label}</div>
      <div style={{ fontSize: 20, fontWeight: 700, color: color || '#202124' }}>{value}</div>
      {sub && <div style={{ fontSize: 11.5, color: '#9aa0a6', marginTop: 2 }}>{sub}</div>}
    </div>
  );
}

function ChartCard({ title, note, children, height = 280 }) {
  return (
    <div style={{ ...S.card }}>
      <div style={{ fontWeight: 700, fontSize: 13.5, color: '#202124' }}>{title}</div>
      {note && <div style={{ fontSize: 11.5, color: '#5f6368', marginTop: 2, marginBottom: 6 }}>{note}</div>}
      <div style={{ marginTop: note ? 0 : 8 }}>
        <ResponsiveContainer width="100%" height={height}>{children}</ResponsiveContainer>
      </div>
    </div>
  );
}

function TooltipBox({ active, payload, label, unit }) {
  if (!active || !payload || !payload.length) return null;
  return (
    <div style={{ background: '#fff', border: '1px solid #dadce0', borderRadius: 6, padding: '9px 11px', fontSize: 12, boxShadow: '0 2px 8px rgba(0,0,0,0.08)' }}>
      <div style={{ fontWeight: 700, marginBottom: 5 }}>{label}</div>
      {payload.map(p => (
        <div key={p.dataKey} style={{ display: 'flex', justifyContent: 'space-between', gap: 14, color: '#374151' }}>
          <span style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
            <span style={{ width: 8, height: 8, borderRadius: 4, background: p.color, display: 'inline-block' }} />
            {p.name}
          </span>
          <span style={{ fontWeight: 600 }}>{fmtHrs(p.value, 1)}{unit ? ` ${unit}` : ''}</span>
        </div>
      ))}
    </div>
  );
}

const SORTS = {
  start_ts: (r) => r.start_ts || '',
  plant: (r) => r.plant || '',
  unit_name: (r) => r.unit_name || '',
  unit_type: (r) => r.unit_type || '',
  _span: (r) => r._span ?? -1,
  _counted: (r) => r._counted ?? -1,
};

export default function BreakdownAnalysisPage() {
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const [fPlant, setFPlant] = useState('');
  const [fFy, setFFy] = useState('');
  const [fType, setFType] = useState('');
  const [fUnit, setFUnit] = useState('');
  const [fStatus, setFStatus] = useState('all');
  const [fFrom, setFFrom] = useState('');
  const [fTo, setFTo] = useState('');
  const [q, setQ] = useState('');
  const [sort, setSort] = useState({ col: 'start_ts', dir: 'desc' });

  useEffect(() => {
    setLoading(true);
    fetch(`${API}/api/breakdown`)
      .then(r => { if (!r.ok) throw new Error(`HTTP ${r.status}`); return r.json(); })
      .then(d => setRows(d.rows || []))
      .catch(e => setError(`Failed to load breakdowns: ${e.message}`))
      .finally(() => setLoading(false));
  }, []);

  const enriched = useMemo(() => rows.map(r => {
    const span = spanHours(r.start_ts, r.end_ts, r.is_ongoing);
    const counted = r.hours_lost_override != null ? Number(r.hours_lost_override) : span;
    return { ...r, _span: span, _counted: counted, _fy: fyOf(r.start_ts), _month: monthKey(r.start_ts) };
  }), [rows]);

  const fyOptions = useMemo(
    () => [...new Set(enriched.map(r => r._fy).filter(Boolean))].sort().reverse(),
    [enriched],
  );

  const unitOptions = useMemo(() => {
    const pool = enriched.filter(r => (!fPlant || r.plant === fPlant) && (!fType || r.unit_type === fType));
    return [...new Set(pool.map(r => r.unit_name).filter(Boolean))].sort();
  }, [enriched, fPlant, fType]);

  const filtered = useMemo(() => {
    const needle = q.trim().toLowerCase();
    return enriched.filter(r => {
      if (fPlant && r.plant !== fPlant) return false;
      if (fFy && r._fy !== fFy) return false;
      if (fType && r.unit_type !== fType) return false;
      if (fUnit && r.unit_name !== fUnit) return false;
      if (fStatus === 'ongoing' && !r.is_ongoing) return false;
      if (fStatus === 'resolved' && r.is_ongoing) return false;
      if (fFrom && (r.start_ts || '').slice(0, 10) < fFrom) return false;
      if (fTo && (r.start_ts || '').slice(0, 10) > fTo) return false;
      if (needle) {
        const hay = `${r.plant} ${r.unit_name} ${r.unit_type} ${r.sms_subtag || ''} ${r.cause || ''}`.toLowerCase();
        if (!hay.includes(needle)) return false;
      }
      return true;
    });
  }, [enriched, fPlant, fFy, fType, fUnit, fStatus, fFrom, fTo, q]);

  const sorted = useMemo(() => {
    const fn = SORTS[sort.col] || SORTS.start_ts;
    const mul = sort.dir === 'asc' ? 1 : -1;
    return [...filtered].sort((a, b) => {
      const av = fn(a), bv = fn(b);
      if (typeof av === 'string') return av.localeCompare(bv) * mul;
      return (av - bv) * mul;
    });
  }, [filtered, sort]);

  const stats = useMemo(() => {
    const n = filtered.length;
    const ongoing = filtered.filter(r => r.is_ongoing).length;
    const totalCounted = filtered.reduce((s, r) => s + (r._counted || 0), 0);
    const durations = filtered.map(r => r._span).filter(v => v != null);
    const avg = durations.length ? durations.reduce((s, v) => s + v, 0) / durations.length : null;
    const longest = filtered.reduce((mx, r) => (r._span != null && (!mx || r._span > mx._span) ? r : mx), null);
    const units = new Set(filtered.map(r => `${r.plant}|${r.unit_name}`)).size;
    return { n, ongoing, totalCounted, avg, longest, units };
  }, [filtered]);

  const byType = useMemo(() => {
    const m = {};
    filtered.forEach(r => {
      const k = r.unit_type || '—';
      m[k] = m[k] || { type: k, label: UNIT_TYPE_LABEL[k] || k, events: 0, hours: 0 };
      m[k].events += 1;
      m[k].hours += r._counted || 0;
    });
    return Object.values(m).sort((a, b) => b.hours - a.hours);
  }, [filtered]);

  const byPlant = useMemo(() => {
    const m = {};
    PLANTS.forEach(p => { m[p.code] = { plant: p.code, events: 0, hours: 0 }; });
    filtered.forEach(r => {
      m[r.plant] = m[r.plant] || { plant: r.plant, events: 0, hours: 0 };
      m[r.plant].events += 1;
      m[r.plant].hours += r._counted || 0;
    });
    return Object.values(m).filter(x => x.events > 0 || !fPlant);
  }, [filtered, fPlant]);

  const byMonth = useMemo(() => {
    const m = {};
    filtered.forEach(r => {
      const k = r._month;
      if (!k || k.length !== 7) return;
      m[k] = m[k] || { month: k, events: 0, hours: 0 };
      m[k].events += 1;
      m[k].hours += r._counted || 0;
    });
    return Object.values(m).sort((a, b) => a.month.localeCompare(b.month))
      .map(x => ({ ...x, label: monthLabel(x.month) }));
  }, [filtered]);

  const topUnits = useMemo(() => {
    const m = {};
    filtered.forEach(r => {
      const k = `${r.plant} · ${r.unit_name}`;
      m[k] = m[k] || { unit: k, events: 0, hours: 0 };
      m[k].events += 1;
      m[k].hours += r._counted || 0;
    });
    return Object.values(m).sort((a, b) => b.hours - a.hours).slice(0, 10).reverse();
  }, [filtered]);

  const anyFilter = fPlant || fFy || fType || fUnit || fStatus !== 'all' || fFrom || fTo || q;
  const clearAll = () => {
    setFPlant(''); setFFy(''); setFType(''); setFUnit(''); setFStatus('all'); setFFrom(''); setFTo(''); setQ('');
  };

  const exportCsv = () => {
    const head = ['id', 'plant', 'unit_type', 'unit_name', 'sms_subtag', 'start_ts', 'end_ts', 'is_ongoing', 'span_hours', 'hours_counted', 'hours_lost_override', 'cause', 'created_by', 'updated_by'];
    const esc = (v) => {
      const s = v == null ? '' : String(v);
      return /[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
    };
    const lines = [head.join(',')];
    sorted.forEach(r => {
      lines.push([
        r.id, r.plant, r.unit_type, r.unit_name, r.sms_subtag || '', r.start_ts || '', r.end_ts || '',
        r.is_ongoing ? 'yes' : 'no',
        r._span != null ? r._span.toFixed(2) : '',
        r._counted != null ? r._counted.toFixed(2) : '',
        r.hours_lost_override ?? '', r.cause || '', r.created_by || '', r.updated_by || '',
      ].map(esc).join(','));
    });
    const blob = new Blob([lines.join('\n')], { type: 'text/csv;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `breakdown_analysis_${new Date().toISOString().slice(0, 10)}.csv`;
    document.body.appendChild(a); a.click(); a.remove();
    URL.revokeObjectURL(url);
  };

  const th = (label, col, extra) => {
    const active = sort.col === col;
    return (
      <th style={{ ...S.H, ...extra }}
        onClick={() => setSort(s => ({ col, dir: s.col === col && s.dir === 'asc' ? 'desc' : 'asc' }))}>
        {label}{active ? (sort.dir === 'asc' ? ' ▲' : ' ▼') : ''}
      </th>
    );
  };

  return (
    <div style={{ height: '100vh', display: 'flex', flexDirection: 'column', background: '#fff' }}>
      <GlobalNavbar />
      <div style={{ flex: 1, overflow: 'auto', maxWidth: 1500, margin: '0 auto', padding: '22px 20px', width: '100%', boxSizing: 'border-box' }}>

        <div style={{ marginBottom: 16, display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 16, flexWrap: 'wrap' }}>
          <div>
            <h2 style={{ fontSize: '1.6rem', fontWeight: 700, color: '#202124', margin: '0 0 4px' }}>
              Breakdown Analysis
            </h2>
            <span style={{ fontSize: 13, color: '#5f6368' }}>
              Every logged unplanned-downtime event across all plants — filter, sort and slice by plant, unit, FY,
              date range and status. &ldquo;Hours counted&rdquo; is the manual override where set, otherwise the full span
              (to now, for ongoing events).
            </span>
          </div>
          <Link href="/data-entry/breakdown" style={{
            fontSize: 13, fontWeight: 600, color: '#1a73e8', textDecoration: 'none',
            border: '1px solid #bfdbfe', background: '#eff6ff', borderRadius: 6, padding: '8px 14px', whiteSpace: 'nowrap',
          }}>
            ✏️ Log / edit breakdowns →
          </Link>
        </div>

        {/* Filters */}
        <div style={{ ...S.card, marginBottom: 16, display: 'flex', gap: 12, flexWrap: 'wrap', alignItems: 'flex-end' }}>
          <div>
            <div style={S.label}>Plant</div>
            <select style={S.select} value={fPlant} onChange={e => { setFPlant(e.target.value); setFUnit(''); }}>
              <option value="">All plants</option>
              {PLANTS.map(p => <option key={p.code} value={p.code}>{p.code} — {p.label}</option>)}
            </select>
          </div>
          <div>
            <div style={S.label}>Financial year</div>
            <select style={S.select} value={fFy} onChange={e => setFFy(e.target.value)}>
              <option value="">All FYs</option>
              {fyOptions.map(fy => <option key={fy} value={fy}>FY {fy}</option>)}
            </select>
          </div>
          <div>
            <div style={S.label}>Unit type</div>
            <select style={S.select} value={fType} onChange={e => { setFType(e.target.value); setFUnit(''); }}>
              <option value="">All types</option>
              {UNIT_TYPES.map(t => <option key={t.code} value={t.code}>{t.label}</option>)}
            </select>
          </div>
          <div>
            <div style={S.label}>Unit</div>
            <select style={S.select} value={fUnit} onChange={e => setFUnit(e.target.value)}>
              <option value="">All units</option>
              {unitOptions.map(u => <option key={u} value={u}>{u}</option>)}
            </select>
          </div>
          <div>
            <div style={S.label}>Status</div>
            <select style={S.select} value={fStatus} onChange={e => setFStatus(e.target.value)}>
              <option value="all">All</option>
              <option value="ongoing">Ongoing</option>
              <option value="resolved">Resolved</option>
            </select>
          </div>
          <div>
            <div style={S.label}>Started between</div>
            <div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
              <input type="date" style={S.input} value={fFrom} onChange={e => setFFrom(e.target.value)} />
              <span style={{ color: '#9aa0a6' }}>–</span>
              <input type="date" style={S.input} value={fTo} onChange={e => setFTo(e.target.value)} />
            </div>
          </div>
          <div>
            <div style={S.label}>Search</div>
            <input style={{ ...S.input, width: 220 }} value={q} onChange={e => setQ(e.target.value)}
              placeholder="unit or cause text…" />
          </div>
          {anyFilter && (
            <button onClick={clearAll} style={{ padding: '8px 16px', fontSize: 13, fontWeight: 600, background: '#f1f3f4', color: '#374151', border: 'none', borderRadius: 6, cursor: 'pointer' }}>
              Clear filters
            </button>
          )}
        </div>

        {error && (
          <div style={{ padding: '12px 16px', border: '1px solid #f28b82', borderRadius: 8, background: '#fce8e6', color: '#c5221f', fontSize: 13, marginBottom: 16 }}>
            {error}
          </div>
        )}
        {loading && <div style={{ padding: 40, textAlign: 'center', color: '#5f6368' }}>Loading breakdown events…</div>}

        {!loading && !error && (
          <>
            {/* Stat tiles */}
            <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap', marginBottom: 16 }}>
              <StatTile label="Events" value={stats.n} sub={`${stats.units} distinct unit${stats.units !== 1 ? 's' : ''}`} />
              <StatTile label="Ongoing now" value={stats.ongoing} color={stats.ongoing ? '#b45309' : '#202124'} />
              <StatTile label="Total hours counted" value={`${fmtHrs(stats.totalCounted, 0)} h`} sub={fmtDuration(stats.totalCounted)} color={C.b} />
              <StatTile label="Avg duration" value={stats.avg == null ? '—' : fmtDuration(stats.avg)} sub={stats.avg == null ? null : `${fmtHrs(stats.avg)} h`} />
              <StatTile label="Longest single event"
                value={stats.longest ? fmtDuration(stats.longest._span) : '—'}
                sub={stats.longest ? `${stats.longest.plant} · ${stats.longest.unit_name}` : null}
                color={C.e} />
            </div>

            {filtered.length === 0 ? (
              <div style={{ ...S.card, textAlign: 'center', color: '#5f6368', padding: 40 }}>
                No breakdown events match the current filters.
              </div>
            ) : (
              <>
                {/* Charts */}
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(420px, 1fr))', gap: 16, marginBottom: 16 }}>
                  <ChartCard title="Hours lost & events by unit type" note="Bars: hours counted · line: event count">
                    <ComposedChart data={byType} margin={{ top: 8, right: 12, left: 0, bottom: 4 }}>
                      <CartesianGrid stroke={C.grid} vertical={false} />
                      <XAxis dataKey="label" tick={{ fontSize: 11, fill: C.sub }} tickLine={false} axisLine={{ stroke: '#c3c2b7' }} interval={0} angle={-12} textAnchor="end" height={50} />
                      <YAxis yAxisId="l" tick={{ fontSize: 11, fill: C.sub }} axisLine={false} tickLine={false} width={52} />
                      <YAxis yAxisId="r" orientation="right" tick={{ fontSize: 11, fill: C.sub }} axisLine={false} tickLine={false} width={34} allowDecimals={false} />
                      <Tooltip content={<TooltipBox />} />
                      <Bar yAxisId="l" dataKey="hours" name="Hours counted" maxBarSize={46} radius={[4, 4, 0, 0]}>
                        {byType.map((d, i) => <Cell key={i} fill={TYPE_COLOR[d.type] || C.f} />)}
                      </Bar>
                      <Line yAxisId="r" dataKey="events" name="Events" stroke={C.ink} strokeWidth={2} dot={{ r: 3 }} />
                    </ComposedChart>
                  </ChartCard>

                  <ChartCard title="Hours lost by plant" note="Hours counted across all units">
                    <BarChart data={byPlant} margin={{ top: 8, right: 12, left: 0, bottom: 4 }}>
                      <CartesianGrid stroke={C.grid} vertical={false} />
                      <XAxis dataKey="plant" tick={{ fontSize: 12, fill: C.sub }} tickLine={false} axisLine={{ stroke: '#c3c2b7' }} />
                      <YAxis tick={{ fontSize: 11, fill: C.sub }} axisLine={false} tickLine={false} width={52} />
                      <Tooltip content={<TooltipBox />} />
                      <Bar dataKey="hours" name="Hours counted" fill={C.a} maxBarSize={54} radius={[4, 4, 0, 0]} />
                    </BarChart>
                  </ChartCard>

                  <ChartCard title="Monthly trend" note="Bars: hours counted (by start month) · line: events">
                    <ComposedChart data={byMonth} margin={{ top: 8, right: 12, left: 0, bottom: 4 }}>
                      <CartesianGrid stroke={C.grid} vertical={false} />
                      <XAxis dataKey="label" tick={{ fontSize: 11, fill: C.sub }} tickLine={false} axisLine={{ stroke: '#c3c2b7' }} interval="preserveStartEnd" />
                      <YAxis yAxisId="l" tick={{ fontSize: 11, fill: C.sub }} axisLine={false} tickLine={false} width={52} />
                      <YAxis yAxisId="r" orientation="right" tick={{ fontSize: 11, fill: C.sub }} axisLine={false} tickLine={false} width={34} allowDecimals={false} />
                      <Tooltip content={<TooltipBox />} />
                      <Bar yAxisId="l" dataKey="hours" name="Hours counted" fill={C.b} maxBarSize={34} radius={[4, 4, 0, 0]} />
                      <Line yAxisId="r" dataKey="events" name="Events" stroke={C.ink} strokeWidth={2} dot={{ r: 3 }} />
                    </ComposedChart>
                  </ChartCard>

                  <ChartCard title="Top units by hours lost" note="Highest 10 units in the current selection">
                    <BarChart data={topUnits} layout="vertical" margin={{ top: 8, right: 16, left: 8, bottom: 4 }}>
                      <CartesianGrid stroke={C.grid} horizontal={false} />
                      <XAxis type="number" tick={{ fontSize: 11, fill: C.sub }} axisLine={false} tickLine={false} />
                      <YAxis type="category" dataKey="unit" tick={{ fontSize: 10.5, fill: C.sub }} width={130} axisLine={false} tickLine={false} />
                      <Tooltip content={<TooltipBox />} />
                      <Bar dataKey="hours" name="Hours counted" fill={C.c} maxBarSize={18} radius={[0, 4, 4, 0]} />
                    </BarChart>
                  </ChartCard>
                </div>

                {/* Detail table */}
                <div style={{ ...S.card, padding: 0, overflow: 'hidden' }}>
                  <div style={{ padding: '12px 16px', display: 'flex', justifyContent: 'space-between', alignItems: 'center', background: '#f8f9fa', borderBottom: '1px solid #dadce0' }}>
                    <span style={{ fontWeight: 700, fontSize: 13.5 }}>
                      {sorted.length} event{sorted.length !== 1 ? 's' : ''}
                    </span>
                    <button onClick={exportCsv} style={{ padding: '7px 16px', fontSize: 12.5, fontWeight: 700, border: '1px solid #1a73e8', borderRadius: 6, background: '#fff', color: '#1a73e8', cursor: 'pointer' }}>
                      ⬇ Export CSV
                    </button>
                  </div>
                  <div style={{ overflowX: 'auto', maxHeight: '60vh', overflowY: 'auto' }}>
                    <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                      <thead>
                        <tr>
                          {th('Plant', 'plant')}
                          {th('Unit', 'unit_name')}
                          {th('Type', 'unit_type')}
                          {th('Start', 'start_ts')}
                          <th style={{ ...S.H, cursor: 'default' }}>End</th>
                          {th('Duration', '_span', { textAlign: 'right' })}
                          {th('Hrs counted', '_counted', { textAlign: 'right' })}
                          <th style={{ ...S.H, cursor: 'default', minWidth: 260 }}>Cause</th>
                          <th style={{ ...S.H, cursor: 'default' }}>Logged by</th>
                        </tr>
                      </thead>
                      <tbody>
                        {sorted.map(r => {
                          const subtag = r.sms_subtag ? ` (${r.sms_subtag.charAt(0)}${r.sms_subtag.slice(1).toLowerCase()})` : '';
                          const overridden = r.hours_lost_override != null;
                          return (
                            <tr key={r.id} style={{ background: r.is_ongoing ? '#fffdf5' : '#fff' }}>
                              <td style={{ ...S.TD, fontWeight: 600 }} title={PLANT_LABEL[r.plant] || ''}>{r.plant}</td>
                              <td style={{ ...S.TD, fontWeight: 600 }}>{r.unit_name}{subtag}</td>
                              <td style={{ ...S.TD, color: '#5f6368' }} title={UNIT_TYPE_LABEL[r.unit_type] || ''}>{r.unit_type}</td>
                              <td style={{ ...S.TD, whiteSpace: 'nowrap' }}>{fmtDateShort(r.start_ts)}</td>
                              <td style={{ ...S.TD, whiteSpace: 'nowrap' }}>
                                {r.is_ongoing
                                  ? <span style={{ padding: '2px 8px', borderRadius: 999, fontSize: 11, fontWeight: 700, background: '#fef3c7', color: '#92400e' }}>ONGOING</span>
                                  : fmtDateShort(r.end_ts)}
                              </td>
                              <td style={{ ...S.TD, textAlign: 'right', whiteSpace: 'nowrap', fontVariantNumeric: 'tabular-nums' }}>
                                {fmtDuration(r._span)}{r.is_ongoing && <span style={{ color: '#b45309' }}> +</span>}
                              </td>
                              <td style={{ ...S.TD, textAlign: 'right', fontVariantNumeric: 'tabular-nums' }}>
                                {fmtHrs(r._counted)}
                                {overridden && <span title="manual override" style={{ color: '#7c3aed', marginLeft: 3 }}>✎</span>}
                              </td>
                              <td style={{ ...S.TD, whiteSpace: 'pre-wrap', maxWidth: 380 }}>{r.cause}</td>
                              <td style={{ ...S.TD, fontSize: 11.5, color: '#5f6368', whiteSpace: 'nowrap' }}>{r.created_by || '—'}</td>
                            </tr>
                          );
                        })}
                      </tbody>
                    </table>
                  </div>
                </div>
              </>
            )}
          </>
        )}
      </div>
    </div>
  );
}
