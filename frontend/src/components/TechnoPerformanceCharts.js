'use client';

import React, { useState, useEffect } from 'react';
import { labelOf } from '@/lib/technoParamRegistry';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || '';

// One small bar chart per parameter — a plain magnitude comparison across 5
// plants reads far more directly than a normalized multi-axis radar (which
// needs the reader to decode relative axis position instead of just reading
// a number). See dataviz skill's choosing-a-form: "compare magnitude, low
// -> high" is a bar chart's job.
const PARAMS = [
  { key: 'coal_to_hm',                  unit: 'kg/thm' },
  { key: 'fuel_rate',                   unit: 'kg/thm' },
  { key: 'specific_energy_consumption', unit: 'Gcal/tcs' },
  { key: 'specific_co2_emissions',      unit: 'kg/tcs' },
];

// Same categorical color per plant across all 4 charts (identity encoding —
// small-multiples convention: hold the encoding constant across facets so a
// reader can track one plant across charts).
const PLANT_COLORS = {
  BSP: '#2a78d6',
  DSP: '#eb6834',
  RSP: '#1baf7a',
  BSL: '#eda100',
  ISP: '#e87ba4',
};
const PLANT_ORDER = ['BSP', 'DSP', 'RSP', 'BSL', 'ISP'];

const INK = '#202124';
const INK_MUTED = '#5f6368';
const INK_FAINT = '#94a3b8';
const BASELINE = '#cbd5e1';
const SEL = { padding: '3px 4px', fontSize: 10.5, border: '1px solid #d1d5db', borderRadius: 4, background: '#fff' };

const MONTHS = ['April', 'May', 'June', 'July', 'August', 'September',
                'October', 'November', 'December', 'January', 'February', 'March'];
const MONTH_NUM = {
  January: '01', February: '02', March: '03', April: '04',
  May: '05', June: '06', July: '07', August: '08',
  September: '09', October: '10', November: '11', December: '12',
};
const YEAR_RANGE_START = 2000;
const _now0 = new Date();
const CURRENT_FY_END_YEAR = (_now0.getMonth() >= 3 ? _now0.getFullYear() : _now0.getFullYear() - 1) + 1;
const YEARS = Array.from({ length: CURRENT_FY_END_YEAR - YEAR_RANGE_START + 1 }, (_, i) => String(YEAR_RANGE_START + i));

function formatMonth(year, monthName) {
  return `${year}-${MONTH_NUM[monthName]}`;
}

function getDefaultMonth() {
  const d = new Date(); d.setMonth(d.getMonth() - 1);
  const names = ['January', 'February', 'March', 'April', 'May', 'June',
                 'July', 'August', 'September', 'October', 'November', 'December'];
  return { monthName: names[d.getMonth()], year: String(d.getFullYear()) };
}

function shortLabel(key) {
  return labelOf(key).replace(' (GCal/TCS)', '');
}

function fmtVal(v) {
  return v == null ? '—' : v.toFixed(2);
}

// One rounded-top bar chart for a single parameter — 5 bars, one per plant.
function ParamBarChart({ param, plants }) {
  const vw = 200, vh = 150;
  const ml = 6, mr = 6, mt = 22, mb = 18;
  const cw = vw - ml - mr, ch = vh - mt - mb;
  const n = PLANT_ORDER.length;
  const slotW = cw / n;
  const barW = Math.max(14, slotW * 0.6);

  const vals = plants.map(p => p[param.key]).filter(v => v != null);
  const yhi = vals.length ? Math.max(...vals) * 1.25 : 1;

  return (
    <div style={{ border: '1px solid #e2e8f0', borderRadius: 8, padding: '6px 8px' }}>
      <svg viewBox={`0 0 ${vw} ${vh}`} style={{ width: '100%', height: 'auto', display: 'block' }}>
        <text x={vw / 2} y="10" textAnchor="middle" fontSize="8.5" fontWeight="700" fill={INK}>
          {shortLabel(param.key)}
        </text>
        <text x={vw / 2} y="19" textAnchor="middle" fontSize="7" fill={INK_FAINT}>
          ({param.unit})
        </text>
        <line x1={ml} y1={mt + ch} x2={vw - mr} y2={mt + ch} stroke={BASELINE} strokeWidth="0.75" />
        {PLANT_ORDER.map((code, i) => {
          const p = plants.find(x => x.plant === code);
          const val = p ? p[param.key] : null;
          const cx = ml + i * slotW + slotW / 2;
          if (val == null) {
            return (
              <g key={code}>
                <rect x={cx - barW / 2} y={mt + ch - 3} width={barW} height="3" fill="none"
                      stroke="#cbd5e1" strokeWidth="0.8" strokeDasharray="2,1.5" />
                <text x={cx} y={mt + ch + 12} textAnchor="middle" fontSize="7.5" fontWeight="700" fill={INK}>{code}</text>
              </g>
            );
          }
          const bh = Math.max(2, (ch - 4) * (val / yhi));
          const by = mt + ch - bh;
          const r = Math.min(barW / 2, bh);
          const color = PLANT_COLORS[code];
          return (
            <g key={code}>
              <path
                d={`M${cx - barW / 2},${mt + ch} L${cx - barW / 2},${by + r} A${r},${r} 0 0 1 ${cx - barW / 2 + r},${by} L${cx + barW / 2 - r},${by} A${r},${r} 0 0 1 ${cx + barW / 2},${by + r} L${cx + barW / 2},${mt + ch} Z`}
                fill={color}
              />
              <text x={cx} y={by - 4} textAnchor="middle" fontSize="7.5" fontWeight="700" fill={color}>
                {val.toFixed(2)}
              </text>
              <text x={cx} y={mt + ch + 12} textAnchor="middle" fontSize="7.5" fontWeight="700" fill={INK}>{code}</text>
            </g>
          );
        })}
      </svg>
    </div>
  );
}

export default function TechnoPerformanceCharts() {
  const def = getDefaultMonth();
  const [fromMonthName, setFromMonthName] = useState(def.monthName);
  const [fromYear, setFromYear]           = useState(def.year);
  const [toMonthName, setToMonthName]     = useState(def.monthName);
  const [toYear, setToYear]               = useState(def.year);

  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    const start = formatMonth(fromYear, fromMonthName);
    const end = formatMonth(toYear, toMonthName);
    setLoading(true); setError(null);
    fetch(`${API_BASE}/api/techno/plant-radar-summary?start=${start}&end=${end}`)
      .then(r => r.json())
      .then(d => setData(d))
      .catch(e => setError(e.message))
      .finally(() => setLoading(false));
  }, [fromMonthName, fromYear, toMonthName, toYear]);

  const plants = data?.plants || [];

  const picker = (
    <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px 8px', alignItems: 'center', justifyContent: 'center', marginBottom: 8 }}>
      <span style={{ fontSize: 10.5, fontWeight: 600, color: INK_MUTED }}>From</span>
      <select value={fromMonthName} onChange={e => setFromMonthName(e.target.value)} style={SEL}>
        {MONTHS.map(m => <option key={m}>{m}</option>)}
      </select>
      <select value={fromYear} onChange={e => setFromYear(e.target.value)} style={SEL}>
        {YEARS.map(y => <option key={y}>{y}</option>)}
      </select>
      <span style={{ fontSize: 10.5, fontWeight: 600, color: INK_MUTED }}>To</span>
      <select value={toMonthName} onChange={e => setToMonthName(e.target.value)} style={SEL}>
        {MONTHS.map(m => <option key={m}>{m}</option>)}
      </select>
      <select value={toYear} onChange={e => setToYear(e.target.value)} style={SEL}>
        {YEARS.map(y => <option key={y}>{y}</option>)}
      </select>
    </div>
  );

  return (
    <div style={{ fontFamily: "-apple-system,BlinkMacSystemFont,'Segoe UI',Arial,sans-serif" }}>
      {picker}

      {loading && <div style={{ padding: 24, textAlign: 'center', color: INK_MUTED, fontSize: 13 }}>Loading techno performance…</div>}
      {!loading && (error || !data || plants.length === 0) && (
        <div style={{ padding: 24, textAlign: 'center', color: INK_FAINT, fontSize: 13 }}>Techno performance data unavailable.</div>
      )}

      {!loading && data && plants.length > 0 && (
        <>
          <div style={{ fontSize: 11, color: INK_MUTED, textAlign: 'center', marginBottom: 8 }}>
            {data.start === data.end ? 'Cumulative ' : ''}{data.period_label}
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: 8 }}>
            {PARAMS.map(param => (
              <ParamBarChart key={param.key} param={param} plants={plants} />
            ))}
          </div>

          {/* Legend */}
          <div style={{ display: 'flex', flexWrap: 'wrap', justifyContent: 'center', gap: '6px 14px', marginTop: 10 }}>
            {PLANT_ORDER.map(code => (
              <span key={code} style={{ display: 'inline-flex', alignItems: 'center', gap: 5, fontSize: 11, fontWeight: 700, color: INK }}>
                <span style={{ width: 9, height: 9, borderRadius: 2, background: PLANT_COLORS[code], display: 'inline-block' }} />
                {code}
              </span>
            ))}
          </div>
        </>
      )}
    </div>
  );
}
