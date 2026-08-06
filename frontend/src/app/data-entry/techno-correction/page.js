'use client';

import RequireEditor from '@/components/RequireEditor';

import React, { useState } from 'react';
import GlobalNavbar from '@/components/GlobalNavbar';
import {
  PLANTS, AREA_ORDER, templateFor, KNOWN_UNITS, unitArea, sortUnitsInArea, labelOf,
} from '@/lib/technoParamRegistry';

const API = process.env.NEXT_PUBLIC_API_URL || '';

// Same shape as techno-manual/page.js's errText — FastAPI validation errors
// come back as detail: [{loc, msg, type}, ...], not a plain string.
function errText(detail, fallback) {
  if (!detail) return fallback;
  if (typeof detail === 'string') return detail;
  if (Array.isArray(detail)) {
    return detail.map(e => {
      if (typeof e === 'string') return e;
      const field = Array.isArray(e?.loc) ? e.loc.filter(p => p !== 'body').join('.') : '';
      return field ? `${field}: ${e?.msg || 'invalid value'}` : (e?.msg || 'invalid value');
    }).join('; ') || fallback;
  }
  return fallback;
}

const MONTHS = [
  'April','May','June','July','August','September',
  'October','November','December','January','February','March',
];
const MONTH_NUM = {
  January:'01', February:'02', March:'03', April:'04',
  May:'05', June:'06', July:'07', August:'08',
  September:'09', October:'10', November:'11', December:'12',
};
const MONTH_NAME_BY_NUM = Object.fromEntries(Object.entries(MONTH_NUM).map(([k, v]) => [v, k]));
const YEAR_RANGE_START = 2000;
const _now = new Date();
const CURRENT_FY_END_YEAR = (_now.getMonth() >= 3 ? _now.getFullYear() : _now.getFullYear() - 1) + 1;
const YEARS = Array.from(
  { length: CURRENT_FY_END_YEAR - YEAR_RANGE_START + 1 },
  (_, i) => String(YEAR_RANGE_START + i)
);

function formatMonth(year, monthName) {
  return `${year}-${MONTH_NUM[monthName]}`;
}
function monthLabel(reportMonth) {
  const [y, m] = reportMonth.split('-');
  return `${MONTH_NAME_BY_NUM[m].slice(0, 3)}'${y.slice(2)}`;
}

// FY-start-to-last-month default range, same convention as the rest of the
// techno pages (getDefaultPeriod in techno-manual/page.js).
function getDefaultRange() {
  const d = new Date(); d.setMonth(d.getMonth() - 1);
  const toYear = d.getFullYear(), toMonthIdx = d.getMonth(); // JS: 0=Jan..11=Dec
  const fyStartYear = toMonthIdx >= 3 ? toYear : toYear - 1;
  return {
    fromMonthName: 'April', fromYear: String(fyStartYear),
    // MONTHS is FY-ordered (April-first) — can't index it with JS's
    // Jan-ordered getMonth(); go through MONTH_NAME_BY_NUM instead.
    toMonthName: MONTH_NAME_BY_NUM[String(toMonthIdx + 1).padStart(2, '0')],
    toYear: String(toYear),
  };
}

// ── Small shared UI bits (page-local, same convention as every other techno page) ──
function Notice({ type, text, onClose }) {
  if (!text) return null;
  const ok = type === 'success';
  return (
    <div style={{
      padding:'10px 16px', borderRadius:6, marginBottom:14, fontSize:14,
      display:'flex', alignItems:'center', justifyContent:'space-between', gap:8,
      background: ok ? '#f0fdf4' : '#fef2f2',
      color:      ok ? '#166534' : '#991b1b',
      border:`1px solid ${ok ? '#86efac' : '#fca5a5'}`,
    }}>
      <span>{text}</span>
      {onClose && (
        <button onClick={onClose} style={{
          background:'none', border:'none', cursor:'pointer', fontSize:18,
          color:'inherit', opacity:0.5, padding:'0 2px', lineHeight:1,
        }}>×</button>
      )}
    </div>
  );
}

function NumInput({ value, onChange, changed }) {
  return (
    <input
      type="number"
      step="any"
      value={value ?? ''}
      onChange={e => onChange(e.target.value === '' ? null : parseFloat(e.target.value))}
      style={{
        width:'100%', padding:'6px 10px', fontSize:14,
        border:`1px solid ${changed ? '#f59e0b' : '#d1d5db'}`,
        borderRadius:4,
        background: changed ? '#fffbeb' : '#fff',
        textAlign:'right',
      }}
    />
  );
}

const TH = { padding:'9px 12px', border:'1px solid #dadce0', fontWeight:700, fontSize:14, textAlign:'left' };
const TD = { padding:'7px 10px', border:'1px solid #dadce0', verticalAlign:'middle', fontSize:14 };
const SELECT_STYLE = { padding:'7px 10px', fontSize:14, border:'1px solid #d1d5db', borderRadius:4 };
const LABEL_STYLE = { fontSize:13, fontWeight:600, color:'#374151' };

function TechnoCorrectionInner() {
  const [plant, setPlant]   = useState('BSP');
  const [area, setArea]     = useState('General');
  const [unit, setUnit]     = useState('General');
  const [paramKey, setParamKey] = useState('specific_energy_consumption');

  const def = getDefaultRange();
  const [fromMonthName, setFromMonthName] = useState(def.fromMonthName);
  const [fromYear, setFromYear]           = useState(def.fromYear);
  const [toMonthName, setToMonthName]     = useState(def.toMonthName);
  const [toYear, setToYear]               = useState(def.toYear);

  const [rows, setRows]         = useState(null);   // [{report_month, month_value, till_month_value}]
  const [initialRows, setInitialRows] = useState(null);
  const [loading, setLoading]   = useState(false);
  const [saving, setSaving]     = useState(false);
  const [notice, setNotice]     = useState(null);

  const areaUnits = sortUnitsInArea(area, KNOWN_UNITS.filter(u => unitArea(u) === area));
  const paramKeys = templateFor(area, plant);

  function handleAreaChange(newArea) {
    setArea(newArea);
    const units = sortUnitsInArea(newArea, KNOWN_UNITS.filter(u => unitArea(u) === newArea));
    setUnit(units[0] || newArea);
    const params = templateFor(newArea, plant);
    setParamKey(params[0] || '');
  }

  async function loadData() {
    setLoading(true); setNotice(null); setRows(null);
    try {
      const fromMonth = formatMonth(fromYear, fromMonthName);
      const toMonth   = formatMonth(toYear, toMonthName);
      const qs = new URLSearchParams({ plant, unit, param_key: paramKey, from_month: fromMonth, to_month: toMonth });
      const r = await fetch(`${API}/api/techno/manual/param-history?${qs}`);
      const d = await r.json();
      if (!r.ok) throw new Error(errText(d.detail, 'Failed to load data'));
      setRows(d.rows);
      setInitialRows(d.rows.map(x => ({ ...x })));
    } catch (e) {
      setNotice({ type:'error', text: e.message });
    } finally {
      setLoading(false);
    }
  }

  function updateCell(reportMonth, field, value) {
    setRows(prev => prev.map(r => r.report_month === reportMonth ? { ...r, [field]: value } : r));
  }

  const changedMonths = rows
    ? rows.filter((r, i) => {
        const init = initialRows[i];
        return r.month_value !== init.month_value || r.till_month_value !== init.till_month_value;
      })
    : [];

  async function saveChanges() {
    setSaving(true); setNotice(null);
    try {
      for (const r of changedMonths) {
        const init = initialRows.find(x => x.report_month === r.report_month);
        const month_data = {};
        const till_month_data = {};
        if (r.month_value !== init.month_value && r.month_value !== null) month_data[paramKey] = r.month_value;
        if (r.till_month_value !== init.till_month_value && r.till_month_value !== null) till_month_data[paramKey] = r.till_month_value;
        if (Object.keys(month_data).length === 0 && Object.keys(till_month_data).length === 0) continue;

        const resp = await fetch(`${API}/api/techno/manual/save`, {
          method: 'POST', headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ plant, report_month: r.report_month, unit, month_data, till_month_data }),
        });
        const d = await resp.json();
        if (!resp.ok) throw new Error(errText(d.detail, `Save failed for ${r.report_month}`));
      }
      setNotice({ type:'success', text: `Saved ${changedMonths.length} month(s).` });
      setInitialRows(rows.map(x => ({ ...x })));
    } catch (e) {
      setNotice({ type:'error', text: e.message });
    } finally {
      setSaving(false);
    }
  }

  return (
    <div style={{ height:'100vh', display:'flex', flexDirection:'column', background:'#ffffff', fontFamily:"-apple-system,BlinkMacSystemFont,'Segoe UI',Arial,sans-serif" }}>
      <GlobalNavbar />

      <div style={{ flex: 1, overflow: 'auto', maxWidth:1100, margin:'0 auto', padding:'22px 20px', width: '100%', boxSizing: 'border-box' }}>

        <div style={{ display:'flex', alignItems:'baseline', gap:14, marginBottom:18 }}>
          <h2 style={{ fontSize:'1.6rem', fontWeight:700, color:'#202124', margin:0 }}>
            Techno Data Correction
          </h2>
          <span style={{ fontSize:13, color:'#5f6368' }}>
            Find one parameter across a month range and correct it inline
          </span>
        </div>

        {/* ── Filters ── */}
        <div style={{
          display:'flex', gap:10, alignItems:'center', flexWrap:'wrap',
          marginBottom:18, background:'#fff', border:'1px solid #dadce0',
          borderRadius:8, padding:'14px 18px',
        }}>
          <label style={LABEL_STYLE}>Plant</label>
          <select value={plant} onChange={e => setPlant(e.target.value)} style={SELECT_STYLE}>
            {PLANTS.map(p => <option key={p}>{p}</option>)}
          </select>

          <label style={LABEL_STYLE}>Area</label>
          <select value={area} onChange={e => handleAreaChange(e.target.value)} style={SELECT_STYLE}>
            {AREA_ORDER.map(a => <option key={a}>{a}</option>)}
          </select>

          <label style={LABEL_STYLE}>Unit</label>
          <select value={unit} onChange={e => setUnit(e.target.value)} style={SELECT_STYLE}>
            {areaUnits.map(u => <option key={u}>{u}</option>)}
          </select>

          <label style={LABEL_STYLE}>Parameter</label>
          <select value={paramKey} onChange={e => setParamKey(e.target.value)} style={{ ...SELECT_STYLE, minWidth:220 }}>
            {paramKeys.map(k => <option key={k} value={k}>{labelOf(k)}</option>)}
          </select>
        </div>

        <div style={{
          display:'flex', gap:10, alignItems:'center', flexWrap:'wrap',
          marginBottom:18, background:'#fff', border:'1px solid #dadce0',
          borderRadius:8, padding:'14px 18px',
        }}>
          <label style={LABEL_STYLE}>From</label>
          <select value={fromMonthName} onChange={e => setFromMonthName(e.target.value)} style={SELECT_STYLE}>
            {MONTHS.map(m => <option key={m}>{m}</option>)}
          </select>
          <select value={fromYear} onChange={e => setFromYear(e.target.value)} style={SELECT_STYLE}>
            {YEARS.map(y => <option key={y}>{y}</option>)}
          </select>

          <label style={{ ...LABEL_STYLE, marginLeft:10 }}>To</label>
          <select value={toMonthName} onChange={e => setToMonthName(e.target.value)} style={SELECT_STYLE}>
            {MONTHS.map(m => <option key={m}>{m}</option>)}
          </select>
          <select value={toYear} onChange={e => setToYear(e.target.value)} style={SELECT_STYLE}>
            {YEARS.map(y => <option key={y}>{y}</option>)}
          </select>

          <button onClick={loadData} disabled={loading} style={{
            padding:'7px 20px', fontSize:14, fontWeight:600,
            background:'#1a73e8', color:'#fff', border:'none', borderRadius:4,
            cursor: loading ? 'not-allowed' : 'pointer',
          }}>
            {loading ? 'Loading…' : 'Load'}
          </button>

          {changedMonths.length > 0 && (
            <button onClick={saveChanges} disabled={saving} style={{
              padding:'7px 20px', fontSize:14, fontWeight:700,
              background: saving ? '#5f6368' : '#166534', color:'#fff',
              border:'none', borderRadius:4, cursor: saving ? 'not-allowed' : 'pointer',
            }}>
              {saving ? 'Saving…' : `Save Changes (${changedMonths.length})`}
            </button>
          )}
        </div>

        {notice && <Notice type={notice.type} text={notice.text} onClose={() => setNotice(null)} />}

        {rows && (
          <table style={{ width:'100%', borderCollapse:'collapse', background:'#fff' }}>
            <thead>
              <tr>
                <th style={TH}>Report Month</th>
                <th style={{ ...TH, textAlign:'right' }}>Month Value</th>
                <th style={{ ...TH, textAlign:'right' }}>Till Month Value</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r, i) => {
                const init = initialRows[i];
                return (
                  <tr key={r.report_month}>
                    <td style={TD}>{monthLabel(r.report_month)}</td>
                    <td style={TD}>
                      <NumInput
                        value={r.month_value}
                        changed={r.month_value !== init.month_value}
                        onChange={v => updateCell(r.report_month, 'month_value', v)}
                      />
                    </td>
                    <td style={TD}>
                      <NumInput
                        value={r.till_month_value}
                        changed={r.till_month_value !== init.till_month_value}
                        onChange={v => updateCell(r.report_month, 'till_month_value', v)}
                      />
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}

        {rows && rows.length === 0 && (
          <p style={{ color:'#5f6368', fontSize:14 }}>No months in the selected range.</p>
        )}
      </div>
    </div>
  );
}

export default function TechnoCorrectionPage() {
  return (
    <RequireEditor>
      <TechnoCorrectionInner />
    </RequireEditor>
  );
}
