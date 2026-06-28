'use client';

import React, { useState, useEffect, useCallback } from 'react';
import GlobalNavbar from '@/components/GlobalNavbar';

const API = process.env.NEXT_PUBLIC_API_URL || 'http://127.0.0.1:8082';

const PLANTS = ['BSP', 'DSP', 'RSP', 'BSL', 'ISP', 'SAIL'];

const MONTHS = [
  'April','May','June','July','August','September',
  'October','November','December','January','February','March',
];
const MONTH_NUM = {
  January:'01', February:'02', March:'03', April:'04',
  May:'05', June:'06', July:'07', August:'08',
  September:'09', October:'10', November:'11', December:'12',
};
const YEARS = Array.from({ length: 8 }, (_, i) => String(2022 + i));

function getDefaultPeriod() {
  const d = new Date(); d.setMonth(d.getMonth() - 1);
  return { monthName: MONTHS[d.getMonth()], year: String(d.getFullYear()) };
}

// ── Unit → Area grouping ─────────────────────────────────────────────────────
const AREA_ORDER = ['Blast Furnace','SMS','Rolling Mills','Coke Ovens','Sinter Plant','General'];

const BF_UNITS    = new Set(['BF_Shop','BF-1','BF-2','BF-3','BF-4','BF-5','BF-6','BF-7','BF-8']);
const SMS_UNITS   = new Set(['SMS','SMS-1','SMS-2','SMS-3','SMS-I','SMS-II']);
const MILL_UNITS  = new Set([
  'PM','RSM','MM','URM','WRM','BRM','HSM-2','NPM','CRM 1&2','CRM 3',
  'ERW','SSM','SWP','BM','USM','MSM','Merchant Mill','Wheel Plant','Axle Plant',
]);
const COKE_UNITS  = new Set(['COB','COB-old','COB-new','Coke Ovens']);
const SINT_UNITS  = new Set(['SP','SP-1','SP-2','SP-3','Sinter']);

function unitArea(u) {
  if (BF_UNITS.has(u))   return 'Blast Furnace';
  if (SMS_UNITS.has(u))  return 'SMS';
  if (MILL_UNITS.has(u)) return 'Rolling Mills';
  if (COKE_UNITS.has(u)) return 'Coke Ovens';
  if (SINT_UNITS.has(u)) return 'Sinter Plant';
  return 'General';
}

// Preferred unit sort order within BF area
const BF_ORDER = ['BF_Shop','BF-1','BF-2','BF-3','BF-4','BF-5','BF-6','BF-7','BF-8'];

function sortUnitsInArea(area, units) {
  if (area === 'Blast Furnace')
    return [...units].sort((a, b) => {
      const ia = BF_ORDER.indexOf(a), ib = BF_ORDER.indexOf(b);
      return (ia < 0 ? 99 : ia) - (ib < 0 ? 99 : ib);
    });
  return [...units].sort();
}

// Pretty display label for a snake_case param key
function labelOf(key) {
  return key
    .replace(/_/g, ' ')
    .replace(/\b\w/g, c => c.toUpperCase())
    .replace(/\bBf\b/g, 'BF')
    .replace(/\bHm\b/g, 'HM')
    .replace(/\bCdi\b/g, 'CDI')
    .replace(/\bFe\b/g, 'Fe')
    .replace(/\bSi\b/g, 'Si')
    .replace(/\bMn\b/g, 'Mn')
    .replace(/\bO2\b/g, 'O₂');
}

// ── Tiny shared components ────────────────────────────────────────────────────
function Notice({ type, text }) {
  if (!text) return null;
  const ok = type === 'success';
  return (
    <div style={{
      padding:'8px 14px', borderRadius:6, marginBottom:12, fontSize:12,
      background: ok ? '#f0fdf4' : '#fef2f2',
      color:      ok ? '#166534' : '#991b1b',
      border:`1px solid ${ok ? '#86efac' : '#fca5a5'}`,
    }}>{text}</div>
  );
}

function Spinner() {
  return <span style={{ display:'inline-block', marginLeft:8, fontSize:10, color:'#6b7280' }}>loading…</span>;
}

// ── Number input cell ─────────────────────────────────────────────────────────
function NumInput({ value, onChange, disabled }) {
  return (
    <input
      type="number"
      step="any"
      value={value ?? ''}
      disabled={disabled}
      onChange={e => onChange(e.target.value === '' ? null : parseFloat(e.target.value))}
      style={{
        width:'100%', padding:'2px 4px', fontSize:11,
        border:'1px solid #d1d5db', borderRadius:4,
        background: disabled ? '#f9fafb' : '#fff',
        textAlign:'right',
      }}
    />
  );
}

// ── Parameter table for one unit ──────────────────────────────────────────────
function UnitForm({ unit, data, onChange, busy }) {
  const allKeys = Array.from(new Set([
    ...Object.keys(data?.month      || {}),
    ...Object.keys(data?.till_month || {}),
  ])).sort();

  if (!allKeys.length)
    return <p style={{ color:'#6b7280', fontSize:12, margin:'16px 0' }}>No parameters loaded. Enter values below to create new entries.</p>;

  return (
    <table style={{ width:'100%', borderCollapse:'collapse', fontSize:11 }}>
      <thead>
        <tr style={{ background:'#f1f5f9' }}>
          <th style={{ ...TH, textAlign:'left', width:'45%' }}>Parameter</th>
          <th style={{ ...TH, width:'27.5%' }}>Month Value</th>
          <th style={{ ...TH, width:'27.5%' }}>YTD Value</th>
        </tr>
      </thead>
      <tbody>
        {allKeys.map((key, i) => (
          <tr key={key} style={{ background: i % 2 === 0 ? '#fff' : '#f8fafc' }}>
            <td style={{ ...TD, fontWeight:500 }}>{labelOf(key)}<br /><span style={{ fontSize:9, color:'#6b7280' }}>{key}</span></td>
            <td style={TD}>
              <NumInput
                value={data?.month?.[key]}
                disabled={busy}
                onChange={v => onChange('month', key, v)}
              />
            </td>
            <td style={TD}>
              <NumInput
                value={data?.till_month?.[key]}
                disabled={busy}
                onChange={v => onChange('till_month', key, v)}
              />
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

const TH = { padding:'5px 8px', border:'1px solid #e2e8f0', fontWeight:700, fontSize:11 };
const TD = { padding:'3px 6px', border:'1px solid #e2e8f0', verticalAlign:'middle' };

// ── Add-param panel ───────────────────────────────────────────────────────────
function AddParam({ onAdd, disabled }) {
  const [key, setKey] = useState('');
  return (
    <div style={{ display:'flex', gap:6, alignItems:'center', marginTop:10 }}>
      <input
        placeholder="New parameter key (e.g. coke_rate)"
        value={key}
        onChange={e => setKey(e.target.value.trim().toLowerCase().replace(/\s+/g,'_'))}
        style={{ flex:1, padding:'4px 8px', fontSize:11, border:'1px solid #d1d5db', borderRadius:4 }}
      />
      <button
        disabled={disabled || !key}
        onClick={() => { if (key) { onAdd(key); setKey(''); } }}
        style={{ padding:'4px 12px', fontSize:11, background:'#3b82f6', color:'#fff',
                 border:'none', borderRadius:4, cursor: disabled || !key ? 'not-allowed' : 'pointer' }}
      >
        + Add
      </button>
    </div>
  );
}

// ── Main page ─────────────────────────────────────────────────────────────────
export default function TechnoManualPage() {
  const def = getDefaultPeriod();
  const [plant,     setPlant]     = useState('RSP');
  const [monthName, setMonthName] = useState(def.monthName);
  const [year,      setYear]      = useState(def.year);

  // {unit: {month: {...}, till_month: {...}}}
  const [unitData, setUnitData] = useState({});
  const [loading,  setLoading]  = useState(false);
  const [notice,   setNotice]   = useState(null);   // {type, text}
  const [saving,   setSaving]   = useState(false);

  // UI state
  const [area,    setArea]    = useState('Blast Furnace');
  const [selUnit, setSelUnit] = useState(null);

  const reportMonth = `${year}-${MONTH_NUM[monthName]}`;

  // ── Load data ─────────────────────────────────────────────────────────────
  const loadData = useCallback(async () => {
    setLoading(true);
    setNotice(null);
    try {
      const r = await fetch(`${API}/api/techno/manual/entry?plant=${plant}&report_month=${reportMonth}`);
      const d = await r.json();
      if (!r.ok) throw new Error(d.detail || 'fetch failed');
      setUnitData(d.units || {});
      if (!d.has_data) setNotice({ type:'info', text:`No data yet for ${plant} ${reportMonth}. Enter values and save.` });
    } catch (e) {
      setNotice({ type:'error', text:`Load failed: ${e.message}` });
      setUnitData({});
    } finally {
      setLoading(false);
    }
  }, [plant, reportMonth]);

  useEffect(() => { loadData(); }, [loadData]);

  // ── Grouped unit list ─────────────────────────────────────────────────────
  const areaUnits = {};
  AREA_ORDER.forEach(a => { areaUnits[a] = []; });
  Object.keys(unitData).forEach(u => {
    const a = unitArea(u);
    if (!areaUnits[a]) areaUnits[a] = [];
    areaUnits[a].push(u);
  });
  // Sort units within each area
  AREA_ORDER.forEach(a => { areaUnits[a] = sortUnitsInArea(a, areaUnits[a]); });

  const visibleUnits = areaUnits[area] || [];

  // Auto-select first unit in area if current selection not in area
  useEffect(() => {
    if (!visibleUnits.includes(selUnit)) setSelUnit(visibleUnits[0] || null);
  }, [area, visibleUnits.join(',')]);

  // ── Edit a value ──────────────────────────────────────────────────────────
  function handleChange(unit, period, key, val) {
    setUnitData(prev => ({
      ...prev,
      [unit]: {
        ...prev[unit],
        [period]: { ...(prev[unit]?.[period] || {}), [key]: val },
      },
    }));
  }

  // ── Add a new param to a unit ─────────────────────────────────────────────
  function handleAddParam(unit, key) {
    setUnitData(prev => ({
      ...prev,
      [unit]: {
        month:       { ...(prev[unit]?.month || {}),      [key]: null },
        till_month:  { ...(prev[unit]?.till_month || {}), [key]: null },
      },
    }));
  }

  // ── Save one unit ─────────────────────────────────────────────────────────
  async function saveUnit(unit) {
    setSaving(true);
    setNotice(null);
    try {
      const d = unitData[unit] || {};
      const r = await fetch(`${API}/api/techno/manual/save`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          plant,
          report_month: reportMonth,
          unit,
          month_data:      d.month      || {},
          till_month_data: d.till_month || {},
        }),
      });
      const res = await r.json();
      if (!r.ok) throw new Error(res.detail || 'save failed');
      setNotice({ type:'success', text:`Saved ${unit} — ${res.saved_month_params} month params, ${res.saved_till_params} YTD params.` });
    } catch (e) {
      setNotice({ type:'error', text:`Save failed: ${e.message}` });
    } finally {
      setSaving(false);
    }
  }

  // ── SAIL BF calculate ─────────────────────────────────────────────────────
  const [sailBusy,     setSailBusy]     = useState(false);
  const [sailPreview,  setSailPreview]  = useState(null);
  const [overwriteMan, setOverwriteMan] = useState(false);

  async function previewSail() {
    setSailBusy(true);
    setSailPreview(null);
    try {
      const r = await fetch(`${API}/api/techno/manual/sail/preview?report_month=${reportMonth}`);
      const d = await r.json();
      if (!r.ok) throw new Error(d.detail || 'preview failed');
      setSailPreview(d);
    } catch (e) {
      setNotice({ type:'error', text:`SAIL preview failed: ${e.message}` });
    } finally {
      setSailBusy(false);
    }
  }

  async function applySail() {
    setSailBusy(true);
    try {
      const r = await fetch(`${API}/api/techno/manual/sail/calculate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ report_month: reportMonth, overwrite_manual: overwriteMan }),
      });
      const d = await r.json();
      if (!r.ok) throw new Error(d.detail || 'calculation failed');
      setNotice({ type:'success', text:`SAIL BF_Shop calculated — ${d.params_calculated} params saved.` });
      setSailPreview(null);
      await loadData();
    } catch (e) {
      setNotice({ type:'error', text:`SAIL calc failed: ${e.message}` });
    } finally {
      setSailBusy(false);
    }
  }

  // ── Render ────────────────────────────────────────────────────────────────
  const isSail = plant === 'SAIL';

  return (
    <div style={{ minHeight:'100vh', background:'#f8fafc', fontFamily:"'Arial Narrow',Arial,sans-serif" }}>
      <GlobalNavbar />

      <div style={{ maxWidth:1100, margin:'0 auto', padding:'20px 16px' }}>
        <h2 style={{ fontSize:'1.1rem', fontWeight:700, color:'#1e3a5f', marginBottom:16 }}>
          Techno-Economic Parameters — Manual Entry
        </h2>

        {/* ── Period + plant selector ── */}
        <div style={{ display:'flex', gap:10, alignItems:'center', flexWrap:'wrap', marginBottom:16,
                      background:'#fff', border:'1px solid #e2e8f0', borderRadius:8, padding:'12px 14px' }}>
          <label style={{ fontSize:12, fontWeight:600, color:'#374151' }}>Plant</label>
          <select value={plant} onChange={e => setPlant(e.target.value)}
                  style={{ padding:'4px 8px', fontSize:12, border:'1px solid #d1d5db', borderRadius:4 }}>
            {PLANTS.map(p => <option key={p}>{p}</option>)}
          </select>

          <label style={{ fontSize:12, fontWeight:600, color:'#374151', marginLeft:10 }}>Period</label>
          <select value={monthName} onChange={e => setMonthName(e.target.value)}
                  style={{ padding:'4px 8px', fontSize:12, border:'1px solid #d1d5db', borderRadius:4 }}>
            {MONTHS.map(m => <option key={m}>{m}</option>)}
          </select>
          <select value={year} onChange={e => setYear(e.target.value)}
                  style={{ padding:'4px 8px', fontSize:12, border:'1px solid #d1d5db', borderRadius:4 }}>
            {YEARS.map(y => <option key={y}>{y}</option>)}
          </select>

          <button onClick={loadData} disabled={loading}
                  style={{ marginLeft:6, padding:'4px 16px', fontSize:12, fontWeight:600,
                           background:'#1e3a5f', color:'#fff', border:'none', borderRadius:4,
                           cursor: loading ? 'not-allowed' : 'pointer' }}>
            {loading ? 'Loading…' : 'Load / Refresh'}
          </button>

          <span style={{ fontSize:11, color:'#94a3b8', marginLeft:'auto' }}>
            {reportMonth} {loading && <Spinner />}
          </span>
        </div>

        <Notice type={notice?.type} text={notice?.text} />

        {/* ── SAIL calculation panel (visible only for SAIL plant + BF area) ── */}
        {isSail && area === 'Blast Furnace' && (
          <div style={{ background:'#eff6ff', border:'1px solid #bfdbfe', borderRadius:8,
                        padding:'12px 16px', marginBottom:16 }}>
            <div style={{ fontWeight:700, fontSize:12, color:'#1e40af', marginBottom:8 }}>
              SAIL BF Aggregate Calculator
            </div>
            <p style={{ fontSize:11, color:'#374151', margin:'0 0 10px' }}>
              Computes SAIL BF_Shop values as weighted averages (by Hot Metal production) across all plants.
              BF Productivity uses harmonic mean; Hot Blast uses arithmetic mean.
            </p>
            <div style={{ display:'flex', gap:10, alignItems:'center', flexWrap:'wrap' }}>
              <button onClick={previewSail} disabled={sailBusy}
                      style={{ padding:'5px 14px', fontSize:11, fontWeight:600,
                               background:'#3b82f6', color:'#fff', border:'none',
                               borderRadius:4, cursor: sailBusy ? 'not-allowed' : 'pointer' }}>
                {sailBusy ? 'Working…' : 'Preview SAIL Calculation'}
              </button>
              <label style={{ fontSize:11, display:'flex', alignItems:'center', gap:4 }}>
                <input type="checkbox" checked={overwriteMan}
                       onChange={e => setOverwriteMan(e.target.checked)} />
                Overwrite manually-entered SAIL values
              </label>
            </div>

            {sailPreview && (
              <div style={{ marginTop:14 }}>
                <div style={{ fontSize:11, fontWeight:600, color:'#1e40af', marginBottom:6 }}>
                  HM Production weights: {Object.entries(sailPreview.hm_weights || {}).map(([p,v]) =>
                    `${p}=${v?.toFixed(0)}`).join(' | ')} (kt)
                </div>
                <table style={{ width:'100%', borderCollapse:'collapse', fontSize:10 }}>
                  <thead>
                    <tr style={{ background:'#dbeafe' }}>
                      <th style={{ ...TH }}>Parameter</th>
                      <th style={{ ...TH }}>Calculated (Month)</th>
                      <th style={{ ...TH }}>Existing SAIL</th>
                      <th style={{ ...TH }}>Will Save</th>
                    </tr>
                  </thead>
                  <tbody>
                    {Object.keys(sailPreview.calculated?.month || {}).map((k, i) => {
                      const calc = sailPreview.calculated?.month?.[k];
                      const exist = sailPreview.existing_sail?.month?.[k];
                      const willSave = overwriteMan ? calc : (exist ?? calc);
                      return (
                        <tr key={k} style={{ background: i%2===0?'#fff':'#f0f9ff' }}>
                          <td style={TD}>{labelOf(k)}</td>
                          <td style={{ ...TD, textAlign:'right' }}>{calc?.toFixed(3) ?? '—'}</td>
                          <td style={{ ...TD, textAlign:'right', color: exist!=null?'#166534':'#9ca3af' }}>
                            {exist?.toFixed(3) ?? '—'}
                          </td>
                          <td style={{ ...TD, textAlign:'right', fontWeight:600, color:'#1e40af' }}>
                            {willSave?.toFixed(3) ?? '—'}
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
                <button onClick={applySail} disabled={sailBusy}
                        style={{ marginTop:10, padding:'6px 18px', fontSize:11, fontWeight:700,
                                 background:'#166534', color:'#fff', border:'none',
                                 borderRadius:4, cursor: sailBusy ? 'not-allowed' : 'pointer' }}>
                  {sailBusy ? 'Saving…' : 'Apply & Save SAIL BF_Shop'}
                </button>
              </div>
            )}
          </div>
        )}

        {/* ── Area tabs ── */}
        <div style={{ display:'flex', gap:0, borderBottom:'2px solid #e2e8f0', marginBottom:16 }}>
          {AREA_ORDER.map(a => (
            <button key={a} onClick={() => setArea(a)}
                    style={{
                      padding:'6px 14px', fontSize:11, fontWeight: a===area ? 700 : 400,
                      border:'none', borderBottom: a===area ? '3px solid #1e3a5f' : '3px solid transparent',
                      background:'transparent', color: a===area ? '#1e3a5f' : '#6b7280',
                      cursor:'pointer', marginBottom:-2,
                    }}>
              {a}
              {areaUnits[a]?.length > 0 && (
                <span style={{ marginLeft:4, fontSize:9, background:'#e2e8f0',
                               padding:'1px 5px', borderRadius:9 }}>
                  {areaUnits[a].length}
                </span>
              )}
            </button>
          ))}
        </div>

        <div style={{ display:'flex', gap:14 }}>
          {/* ── Unit sidebar ── */}
          <div style={{ width:130, flexShrink:0 }}>
            <div style={{ fontSize:10, fontWeight:600, color:'#9ca3af', textTransform:'uppercase',
                          letterSpacing:'0.05em', marginBottom:8 }}>
              Units
            </div>
            {visibleUnits.length === 0 ? (
              <div style={{ fontSize:11, color:'#9ca3af', fontStyle:'italic' }}>
                None loaded
              </div>
            ) : (
              visibleUnits.map(u => (
                <button key={u} onClick={() => setSelUnit(u)}
                        style={{
                          display:'block', width:'100%', textAlign:'left',
                          padding:'6px 10px', marginBottom:3, fontSize:11, fontWeight: u===selUnit ? 700 : 400,
                          background: u===selUnit ? '#1e3a5f' : '#fff',
                          color: u===selUnit ? '#fff' : '#374151',
                          border:'1px solid #e2e8f0', borderRadius:5, cursor:'pointer',
                        }}>
                  {u}
                </button>
              ))
            )}
          </div>

          {/* ── Param form ── */}
          <div style={{ flex:1, minWidth:0 }}>
            {!selUnit ? (
              <div style={{ color:'#9ca3af', fontSize:12, padding:'20px 0' }}>
                {visibleUnits.length === 0
                  ? `No ${area} units found for ${plant} ${reportMonth}. Load data first or units for this area are empty.`
                  : 'Select a unit from the left to view/edit parameters.'}
              </div>
            ) : (
              <div style={{ background:'#fff', border:'1px solid #e2e8f0', borderRadius:8, padding:'14px' }}>
                <div style={{ display:'flex', alignItems:'center', justifyContent:'space-between', marginBottom:10 }}>
                  <span style={{ fontWeight:700, fontSize:13, color:'#1e3a5f' }}>
                    {plant} › {selUnit}
                  </span>
                  <button onClick={() => saveUnit(selUnit)} disabled={saving}
                          style={{ padding:'5px 18px', fontSize:11, fontWeight:700,
                                   background:'#166534', color:'#fff', border:'none',
                                   borderRadius:5, cursor: saving ? 'not-allowed' : 'pointer' }}>
                    {saving ? 'Saving…' : `Save ${selUnit}`}
                  </button>
                </div>

                <UnitForm
                  unit={selUnit}
                  data={unitData[selUnit]}
                  onChange={(period, key, val) => handleChange(selUnit, period, key, val)}
                  busy={saving}
                />

                <AddParam
                  disabled={saving}
                  onAdd={key => handleAddParam(selUnit, key)}
                />
              </div>
            )}
          </div>
        </div>

        {/* ── Footer note ── */}
        <div style={{ marginTop:20, fontSize:10, color:'#9ca3af', textAlign:'right' }}>
          Data is saved per unit. Null values are not overwritten. File-uploaded data and manually-entered data coexist — last save wins per parameter.
        </div>
      </div>
    </div>
  );
}
