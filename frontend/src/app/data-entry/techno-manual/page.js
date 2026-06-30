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
const YEARS = Array.from({ length: 10 }, (_, i) => String(2022 + i));

function getDefaultPeriod() {
  const d = new Date(); d.setMonth(d.getMonth() - 1);
  return { monthName: MONTHS[d.getMonth()], year: String(d.getFullYear()) };
}

// ── Unit → Area grouping ──────────────────────────────────────────────────────
const AREA_ORDER = ['Blast Furnace','SMS','Rolling Mills','Coke Ovens','Sinter Plant','General'];

const BF_UNITS   = new Set(['BF_Shop','BF-1','BF-2','BF-3','BF-4','BF-5','BF-6','BF-7','BF-8']);
const SMS_UNITS  = new Set(['SMS','SMS-1','SMS-2','SMS-3','SMS-I','SMS-II']);
const MILL_UNITS = new Set([
  'PM','RSM','MM','URM','WRM','BRM','HSM-2','NPM','CRM 1&2','CRM 3',
  'ERW','SSM','SWP','BM','USM','MSM','Merchant Mill','Wheel Plant','Axle Plant',
]);
const COKE_UNITS = new Set(['COB','COB-old','COB-new','Coke Ovens']);
const SINT_UNITS = new Set(['SP','SP-1','SP-2','SP-3','Sinter']);

function unitArea(u) {
  if (BF_UNITS.has(u))   return 'Blast Furnace';
  if (SMS_UNITS.has(u))  return 'SMS';
  if (MILL_UNITS.has(u)) return 'Rolling Mills';
  if (COKE_UNITS.has(u)) return 'Coke Ovens';
  if (SINT_UNITS.has(u)) return 'Sinter Plant';
  return 'General';
}

const BF_ORDER = ['BF_Shop','BF-1','BF-2','BF-3','BF-4','BF-5','BF-6','BF-7','BF-8'];

function sortUnitsInArea(area, units) {
  if (area === 'Blast Furnace')
    return [...units].sort((a, b) => {
      const ia = BF_ORDER.indexOf(a), ib = BF_ORDER.indexOf(b);
      return (ia < 0 ? 99 : ia) - (ib < 0 ? 99 : ib);
    });
  return [...units].sort();
}

// ── Parameter templates per area ──────────────────────────────────────────────
const PARAM_TEMPLATES = {
  'Blast Furnace': [
    'coke_rate','nut_coke_rate','cdi','fuel_rate','bf_productivity',
    'hot_blast_temp','o2_enrichment','blast_moisture','blast_volume',
    'slag_rate','sinter_in_burden','pellet_in_burden','lump_in_burden',
    'tfe_in_sinter','tfe_in_pellet','tfe_in_lump','coal_to_hot_metal',
    'fe_in_ore',
  ],
  'SMS': [
    'specific_hm_consumption','hot_metal_consumption',
    'specific_scrap_consumption','scrap_consumption',
    'tmi','heat_size','concast_ratio','cc_ratio','yield_sms',
  ],
  'Coke Ovens': ['gross_coke_rate','net_coke_rate','coke_production','coking_time'],
  'Sinter Plant': ['sinter_production','productivity','basicity','tfe_in_sinter'],
  'Rolling Mills': ['rolling_yield','production'],
  'General': ['specific_energy_consumption'],
};

// ── Known units list for "Add Unit" modal ─────────────────────────────────────
const KNOWN_UNITS = [
  'BF_Shop','BF-1','BF-2','BF-3','BF-4','BF-5','BF-6','BF-7','BF-8',
  'SMS','SMS-1','SMS-2','SMS-3','SMS-I','SMS-II',
  'COB','COB-old','COB-new','SP','SP-1','SP-2','SP-3',
  'General','PM','RSM','MM','URM','WRM','BRM','CRM 1&2','CRM 3',
  'Merchant Mill','Wheel Plant','Axle Plant',
];

// ── Label helpers ─────────────────────────────────────────────────────────────
function labelOf(key) {
  return key
    .replace(/_/g, ' ')
    .replace(/\b\w/g, c => c.toUpperCase())
    .replace(/\bBf\b/g, 'BF').replace(/\bHm\b/g, 'HM').replace(/\bCdi\b/g, 'CDI')
    .replace(/\bTmi\b/g, 'TMI').replace(/\bFe\b/g, 'Fe').replace(/\bTfe\b/g, 'TFE')
    .replace(/\bCc\b/g, 'CC').replace(/\bO2\b/g, 'O₂');
}

// ── Shared styles ─────────────────────────────────────────────────────────────
const TH = { padding:'5px 8px', border:'1px solid #e2e8f0', fontWeight:700, fontSize:11 };
const TD = { padding:'3px 6px', border:'1px solid #e2e8f0', verticalAlign:'middle' };

// ── Change counter ────────────────────────────────────────────────────────────
function countChanges(current, initial) {
  let n = 0;
  for (const period of ['month','till_month']) {
    const cur = current?.[period] || {};
    const ini = initial?.[period] || {};
    const keys = new Set([...Object.keys(cur), ...Object.keys(ini)]);
    for (const k of keys) {
      if ((cur[k] ?? null) !== (ini[k] ?? null)) n++;
    }
  }
  return n;
}

// ── Tiny shared components ────────────────────────────────────────────────────
function Notice({ type, text, onClose }) {
  if (!text) return null;
  const ok   = type === 'success';
  const info = type === 'info';
  return (
    <div style={{
      padding:'8px 14px', borderRadius:6, marginBottom:12, fontSize:12,
      display:'flex', alignItems:'center', justifyContent:'space-between', gap:8,
      background: ok ? '#f0fdf4' : info ? '#eff6ff' : '#fef2f2',
      color:      ok ? '#166534' : info ? '#1e40af' : '#991b1b',
      border:`1px solid ${ok ? '#86efac' : info ? '#bfdbfe' : '#fca5a5'}`,
    }}>
      <span>{text}</span>
      {onClose && (
        <button onClick={onClose} style={{
          background:'none', border:'none', cursor:'pointer', fontSize:15,
          color:'inherit', opacity:0.5, padding:'0 2px', lineHeight:1,
        }}>×</button>
      )}
    </div>
  );
}

// ── Number input cell ─────────────────────────────────────────────────────────
function NumInput({ value, onChange, disabled, changed }) {
  return (
    <input
      type="number"
      step="any"
      value={value ?? ''}
      disabled={disabled}
      onChange={e => onChange(e.target.value === '' ? null : parseFloat(e.target.value))}
      style={{
        width:'100%', padding:'2px 5px', fontSize:11,
        border:`1px solid ${changed ? '#f59e0b' : '#d1d5db'}`,
        borderRadius:4,
        background: disabled ? '#f9fafb' : changed ? '#fffbeb' : '#fff',
        textAlign:'right',
      }}
    />
  );
}

// ── Parameter table for one unit ──────────────────────────────────────────────
function UnitForm({ unit, data, initialData, onChange, busy }) {
  const area        = unitArea(unit);
  const templateKeys = PARAM_TEMPLATES[area] || [];

  const dbKeys = Array.from(new Set([
    ...Object.keys(data?.month      || {}),
    ...Object.keys(data?.till_month || {}),
  ]));

  // Template params first (in order), then any extra DB keys not in template
  const allKeys = [
    ...templateKeys,
    ...dbKeys.filter(k => !templateKeys.includes(k)).sort(),
  ];

  if (!allKeys.length)
    return (
      <p style={{ color:'#6b7280', fontSize:12, margin:'16px 0' }}>
        No parameters. Use "Add Param" below to add custom keys.
      </p>
    );

  return (
    <table style={{ width:'100%', borderCollapse:'collapse', fontSize:11 }}>
      <thead>
        <tr style={{ background:'#f1f5f9' }}>
          <th style={{ ...TH, textAlign:'left', width:'44%' }}>Parameter</th>
          <th style={{ ...TH, width:'28%' }}>Month Value</th>
          <th style={{ ...TH, width:'28%' }}>YTD (Cumulative)</th>
        </tr>
      </thead>
      <tbody>
        {allKeys.map((key, i) => {
          const mv      = data?.month?.[key]      ?? null;
          const tv      = data?.till_month?.[key] ?? null;
          const initM   = initialData?.month?.[key]      ?? null;
          const initT   = initialData?.till_month?.[key] ?? null;
          const mChg    = mv !== initM;
          const tChg    = tv !== initT;
          const isTempl = templateKeys.includes(key);
          return (
            <tr key={key} style={{ background: i % 2 === 0 ? '#fff' : '#f8fafc' }}>
              <td style={{ ...TD, fontWeight: isTempl ? 500 : 400, color: isTempl ? '#1e293b' : '#64748b' }}>
                {labelOf(key)}
                <br /><span style={{ fontSize:9, color:'#b0b8c1' }}>{key}</span>
              </td>
              <td style={TD}>
                <NumInput value={mv} disabled={busy} changed={mChg}
                  onChange={v => onChange('month', key, v)} />
              </td>
              <td style={TD}>
                <NumInput value={tv} disabled={busy} changed={tChg}
                  onChange={v => onChange('till_month', key, v)} />
              </td>
            </tr>
          );
        })}
      </tbody>
    </table>
  );
}

// ── Add-param panel ───────────────────────────────────────────────────────────
function AddParam({ onAdd, disabled }) {
  const [key, setKey] = useState('');
  return (
    <div style={{ display:'flex', gap:6, alignItems:'center', marginTop:10 }}>
      <input
        placeholder="Custom param key (e.g. hot_blast_temp)"
        value={key}
        onChange={e => setKey(e.target.value.trim().toLowerCase().replace(/\s+/g,'_'))}
        style={{ flex:1, padding:'4px 8px', fontSize:11, border:'1px solid #d1d5db', borderRadius:4 }}
      />
      <button
        disabled={disabled || !key}
        onClick={() => { if (key) { onAdd(key); setKey(''); } }}
        style={{
          padding:'4px 12px', fontSize:11, background:'#3b82f6', color:'#fff',
          border:'none', borderRadius:4, cursor: disabled || !key ? 'not-allowed' : 'pointer',
        }}
      >+ Param</button>
    </div>
  );
}

// ── Add Unit modal ────────────────────────────────────────────────────────────
function AddUnitModal({ existingUnits, onAdd, onClose }) {
  const [unitName, setUnitName] = useState('');
  const [custom,   setCustom]   = useState(false);

  const available = KNOWN_UNITS.filter(u => !existingUnits.includes(u));

  function submit() {
    const name = unitName.trim();
    if (!name) return;
    onAdd(name);
    onClose();
  }

  return (
    <div style={{
      position:'fixed', inset:0, background:'rgba(0,0,0,0.45)', zIndex:200,
      display:'flex', alignItems:'center', justifyContent:'center',
    }}>
      <div style={{
        background:'#fff', borderRadius:10, padding:24, width:380,
        boxShadow:'0 8px 32px rgba(0,0,0,0.18)',
      }}>
        <h3 style={{ margin:'0 0 14px', fontSize:14, color:'#1e3a5f' }}>Add Unit</h3>

        <label style={{ fontSize:11, fontWeight:600, color:'#374151', display:'block', marginBottom:4 }}>
          Select from known units
        </label>
        <select
          value={custom ? '__custom__' : unitName}
          onChange={e => {
            if (e.target.value === '__custom__') { setCustom(true); setUnitName(''); }
            else { setCustom(false); setUnitName(e.target.value); }
          }}
          style={{ width:'100%', padding:'5px 8px', fontSize:12, border:'1px solid #d1d5db', borderRadius:4, marginBottom:10 }}
        >
          <option value="">— Select unit —</option>
          {available.map(u => <option key={u} value={u}>{u}</option>)}
          <option value="__custom__">Custom (type below)…</option>
        </select>

        {custom && (
          <input
            autoFocus
            placeholder="Unit name (e.g. BF-9)"
            value={unitName}
            onChange={e => setUnitName(e.target.value)}
            style={{ width:'100%', padding:'5px 8px', fontSize:12, border:'1px solid #d1d5db', borderRadius:4, marginBottom:10, boxSizing:'border-box' }}
          />
        )}

        <p style={{ fontSize:10, color:'#6b7280', margin:'0 0 16px' }}>
          Standard template parameters for this unit type will appear as blank rows ready for input.
        </p>

        <div style={{ display:'flex', gap:8, justifyContent:'flex-end' }}>
          <button onClick={onClose} style={{
            padding:'5px 14px', fontSize:11, background:'#f1f5f9',
            border:'1px solid #e2e8f0', borderRadius:4, cursor:'pointer',
          }}>Cancel</button>
          <button onClick={submit} disabled={!unitName.trim()} style={{
            padding:'5px 14px', fontSize:11, fontWeight:600,
            background: unitName.trim() ? '#1e3a5f' : '#94a3b8',
            color:'#fff', border:'none', borderRadius:4,
            cursor: unitName.trim() ? 'pointer' : 'not-allowed',
          }}>Add Unit</button>
        </div>
      </div>
    </div>
  );
}

// ── Copy-from-month panel ─────────────────────────────────────────────────────
function CopyFromPanel({ currentMonth, plant, onCopy }) {
  const [open,      setOpen]      = useState(false);
  const [monthName, setMonthName] = useState(MONTHS[0]);
  const [year,      setYear]      = useState(String(new Date().getFullYear() - 1));
  const [loading,   setLoading]   = useState(false);
  const [status,    setStatus]    = useState(null);

  const srcMonth = `${year}-${MONTH_NUM[monthName]}`;

  async function doCopy() {
    if (srcMonth === currentMonth) {
      setStatus({ type:'error', text:'Source and target months are the same.' });
      return;
    }
    setLoading(true); setStatus(null);
    try {
      const r = await fetch(`${API}/api/techno/manual/entry?plant=${plant}&report_month=${srcMonth}`);
      const d = await r.json();
      if (!r.ok) throw new Error(d.detail || 'fetch failed');
      if (!d.has_data) {
        setStatus({ type:'error', text:`No data for ${plant} ${srcMonth}.` });
        return;
      }
      onCopy(d.units);
      setStatus({ type:'success', text:`Copied from ${srcMonth}. Review & save.` });
    } catch (e) {
      setStatus({ type:'error', text:e.message });
    } finally {
      setLoading(false);
    }
  }

  if (!open) return (
    <button onClick={() => setOpen(true)} style={{
      width:'100%', padding:'5px 8px', fontSize:10, fontWeight:600,
      background:'#eff6ff', border:'1px solid #bfdbfe', borderRadius:4,
      color:'#1e40af', cursor:'pointer', marginBottom:8,
    }}>
      Copy from Month…
    </button>
  );

  return (
    <div style={{ background:'#eff6ff', border:'1px solid #bfdbfe', borderRadius:6, padding:'10px', marginBottom:8 }}>
      <div style={{ fontSize:10, fontWeight:700, color:'#1e40af', marginBottom:6 }}>
        Copy values from:
      </div>
      <select value={monthName} onChange={e => setMonthName(e.target.value)}
              style={{ width:'100%', fontSize:10, padding:'3px 6px', marginBottom:4, border:'1px solid #bfdbfe', borderRadius:3 }}>
        {MONTHS.map(m => <option key={m}>{m}</option>)}
      </select>
      <select value={year} onChange={e => setYear(e.target.value)}
              style={{ width:'100%', fontSize:10, padding:'3px 6px', marginBottom:6, border:'1px solid #bfdbfe', borderRadius:3 }}>
        {YEARS.map(y => <option key={y}>{y}</option>)}
      </select>
      {status && <Notice type={status.type} text={status.text} />}
      <div style={{ display:'flex', gap:4 }}>
        <button onClick={doCopy} disabled={loading} style={{
          flex:1, padding:'4px 0', fontSize:10, fontWeight:600,
          background: loading ? '#94a3b8' : '#1e40af', color:'#fff',
          border:'none', borderRadius:3, cursor: loading ? 'not-allowed' : 'pointer',
        }}>{loading ? 'Loading…' : `Copy from ${srcMonth}`}</button>
        <button onClick={() => { setOpen(false); setStatus(null); }} style={{
          padding:'4px 8px', fontSize:10, background:'#f1f5f9',
          border:'1px solid #e2e8f0', borderRadius:3, cursor:'pointer',
        }}>×</button>
      </div>
    </div>
  );
}

// ── Main page ─────────────────────────────────────────────────────────────────
export default function TechnoManualPage() {
  const def = getDefaultPeriod();
  const [plant,     setPlant]     = useState('RSP');
  const [monthName, setMonthName] = useState(def.monthName);
  const [year,      setYear]      = useState(def.year);

  // unitData: current editable state  {unit: {month:{...}, till_month:{...}}}
  // initData: snapshot from last DB load/save (used for change detection)
  const [unitData,    setUnitData]    = useState({});
  const [initData,    setInitData]    = useState({});
  const [loading,     setLoading]     = useState(false);
  const [notice,      setNotice]      = useState(null);
  const [saving,      setSaving]      = useState(false);
  const [savedUnits,  setSavedUnits]  = useState(new Set());

  const [area,        setArea]        = useState('Blast Furnace');
  const [selUnit,     setSelUnit]     = useState(null);
  const [showAddUnit, setShowAddUnit] = useState(false);

  const reportMonth = `${year}-${MONTH_NUM[monthName]}`;

  // ── Load data ───────────────────────────────────────────────────────────────
  const loadData = useCallback(async () => {
    setLoading(true); setNotice(null); setSavedUnits(new Set());
    try {
      const r = await fetch(`${API}/api/techno/manual/entry?plant=${plant}&report_month=${reportMonth}`);
      const d = await r.json();
      if (!r.ok) throw new Error(d.detail || 'fetch failed');
      const units = d.units || {};
      setUnitData(units);
      setInitData(JSON.parse(JSON.stringify(units)));
      if (!d.has_data)
        setNotice({ type:'info', text:`No data yet for ${plant} ${reportMonth}. Click "+ Add Unit" to begin.` });
    } catch (e) {
      setNotice({ type:'error', text:`Load failed: ${e.message}` });
      setUnitData({}); setInitData({});
    } finally {
      setLoading(false);
    }
  }, [plant, reportMonth]);

  useEffect(() => { loadData(); }, [loadData]);

  // ── Grouped unit list ───────────────────────────────────────────────────────
  const areaUnits = {};
  AREA_ORDER.forEach(a => { areaUnits[a] = []; });
  Object.keys(unitData).forEach(u => {
    const a = unitArea(u);
    (areaUnits[a] = areaUnits[a] || []).push(u);
  });
  AREA_ORDER.forEach(a => { areaUnits[a] = sortUnitsInArea(a, areaUnits[a] || []); });

  const visibleUnits = areaUnits[area] || [];

  useEffect(() => {
    if (!visibleUnits.includes(selUnit)) setSelUnit(visibleUnits[0] || null);
  }, [area, visibleUnits.join(',')]);

  // ── Edit value ──────────────────────────────────────────────────────────────
  function handleChange(unit, period, key, val) {
    setSavedUnits(prev => { const s = new Set(prev); s.delete(unit); return s; });
    setUnitData(prev => ({
      ...prev,
      [unit]: {
        ...prev[unit],
        [period]: { ...(prev[unit]?.[period] || {}), [key]: val },
      },
    }));
  }

  // ── Add param to unit ───────────────────────────────────────────────────────
  function handleAddParam(unit, key) {
    setUnitData(prev => ({
      ...prev,
      [unit]: {
        month:      { ...(prev[unit]?.month      || {}), [key]: null },
        till_month: { ...(prev[unit]?.till_month || {}), [key]: null },
      },
    }));
  }

  // ── Add unit (with template params) ────────────────────────────────────────
  function handleAddUnit(unitName) {
    const a      = unitArea(unitName);
    const tmpl   = PARAM_TEMPLATES[a] || [];
    const empty  = Object.fromEntries(tmpl.map(k => [k, null]));
    setUnitData(prev => ({
      ...prev,
      [unitName]: { month: { ...empty }, till_month: { ...empty } },
    }));
    setArea(a);
    setSelUnit(unitName);
  }

  // ── Copy values from another month ──────────────────────────────────────────
  function handleCopyFrom(srcUnits) {
    setUnitData(prev => {
      const merged = { ...prev };
      for (const [unit, data] of Object.entries(srcUnits)) {
        if (!merged[unit]) merged[unit] = { month:{}, till_month:{} };
        for (const period of ['month','till_month']) {
          const src = data?.[period] || {};
          const dst = merged[unit]?.[period] || {};
          // Source fills nulls/missing; existing non-null values are kept
          merged[unit][period] = {
            ...src,
            ...Object.fromEntries(Object.entries(dst).filter(([, v]) => v !== null)),
          };
        }
      }
      return merged;
    });
    // Mark all as unsaved after copy
    setSavedUnits(new Set());
  }

  // ── Save one unit ───────────────────────────────────────────────────────────
  async function saveUnit(unit) {
    setSaving(true); setNotice(null);
    try {
      const d = unitData[unit] || {};
      const r = await fetch(`${API}/api/techno/manual/save`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          plant, report_month: reportMonth, unit,
          month_data:      d.month      || {},
          till_month_data: d.till_month || {},
        }),
      });
      const res = await r.json();
      if (!r.ok) throw new Error(res.detail || 'save failed');
      // Update snapshot so change indicators reset
      setInitData(prev => ({ ...prev, [unit]: JSON.parse(JSON.stringify(unitData[unit])) }));
      setSavedUnits(prev => new Set([...prev, unit]));
      setNotice({ type:'success', text:`Saved ${unit} — ${res.saved_month_params} month, ${res.saved_till_params} YTD params.` });
    } catch (e) {
      setNotice({ type:'error', text:`Save failed: ${e.message}` });
    } finally {
      setSaving(false);
    }
  }

  // ── Save all units with unsaved changes ─────────────────────────────────────
  async function saveAll() {
    const changed = Object.keys(unitData).filter(u => countChanges(unitData[u], initData[u]) > 0);
    if (!changed.length) { setNotice({ type:'info', text:'No unsaved changes.' }); return; }
    setSaving(true); setNotice(null);
    let ok = 0;
    const errors = [];
    for (const unit of changed) {
      try {
        const d = unitData[unit] || {};
        const r = await fetch(`${API}/api/techno/manual/save`, {
          method:'POST', headers:{'Content-Type':'application/json'},
          body: JSON.stringify({
            plant, report_month: reportMonth, unit,
            month_data: d.month || {}, till_month_data: d.till_month || {},
          }),
        });
        const res = await r.json();
        if (!r.ok) throw new Error(res.detail || 'save failed');
        setInitData(prev => ({ ...prev, [unit]: JSON.parse(JSON.stringify(unitData[unit])) }));
        setSavedUnits(prev => new Set([...prev, unit]));
        ok++;
      } catch (e) {
        errors.push(`${unit}: ${e.message}`);
      }
    }
    setSaving(false);
    if (errors.length)
      setNotice({ type:'error', text:`Saved ${ok}/${changed.length}. Errors: ${errors.join('; ')}` });
    else
      setNotice({ type:'success', text:`All ${ok} unit(s) saved successfully.` });
  }

  // ── SAIL BF calculator ──────────────────────────────────────────────────────
  const [sailBusy,     setSailBusy]     = useState(false);
  const [sailPreview,  setSailPreview]  = useState(null);
  const [overwriteMan, setOverwriteMan] = useState(false);

  async function previewSail() {
    setSailBusy(true); setSailPreview(null);
    try {
      const r = await fetch(`${API}/api/techno/manual/sail/preview?report_month=${reportMonth}`);
      const d = await r.json();
      if (!r.ok) throw new Error(d.detail || 'preview failed');
      setSailPreview(d);
    } catch (e) { setNotice({ type:'error', text:`SAIL preview: ${e.message}` }); }
    finally { setSailBusy(false); }
  }

  async function applySail() {
    setSailBusy(true);
    try {
      const r = await fetch(`${API}/api/techno/manual/sail/calculate`, {
        method:'POST', headers:{'Content-Type':'application/json'},
        body: JSON.stringify({ report_month: reportMonth, overwrite_manual: overwriteMan }),
      });
      const d = await r.json();
      if (!r.ok) throw new Error(d.detail || 'calc failed');
      setNotice({ type:'success', text:`SAIL BF_Shop saved — ${d.params_calculated} params.` });
      setSailPreview(null);
      await loadData();
    } catch (e) { setNotice({ type:'error', text:`SAIL calc: ${e.message}` }); }
    finally { setSailBusy(false); }
  }

  // ── Derived ─────────────────────────────────────────────────────────────────
  const isSail       = plant === 'SAIL';
  const totalChanges = Object.keys(unitData).reduce((n, u) => n + countChanges(unitData[u], initData[u]), 0);

  // ── Render ───────────────────────────────────────────────────────────────────
  return (
    <div style={{ minHeight:'100vh', background:'#f8fafc', fontFamily:"'Arial Narrow',Arial,sans-serif" }}>
      <GlobalNavbar />

      {showAddUnit && (
        <AddUnitModal
          existingUnits={Object.keys(unitData)}
          onAdd={handleAddUnit}
          onClose={() => setShowAddUnit(false)}
        />
      )}

      <div style={{ maxWidth:1160, margin:'0 auto', padding:'18px 16px' }}>

        {/* ── Page title ── */}
        <div style={{ display:'flex', alignItems:'baseline', gap:12, marginBottom:14 }}>
          <h2 style={{ fontSize:'1.1rem', fontWeight:700, color:'#1e3a5f', margin:0 }}>
            Techno Parameters — Universal Entry
          </h2>
          <span style={{ fontSize:11, color:'#94a3b8' }}>
            Insert legacy data · revise uploaded values · manual corrections
          </span>
        </div>

        {/* ── Controls bar ── */}
        <div style={{
          display:'flex', gap:8, alignItems:'center', flexWrap:'wrap',
          marginBottom:14, background:'#fff', border:'1px solid #e2e8f0',
          borderRadius:8, padding:'10px 14px',
        }}>
          <label style={{ fontSize:11, fontWeight:600, color:'#374151' }}>Plant</label>
          <select value={plant} onChange={e => setPlant(e.target.value)}
                  style={{ padding:'4px 8px', fontSize:12, border:'1px solid #d1d5db', borderRadius:4 }}>
            {PLANTS.map(p => <option key={p}>{p}</option>)}
          </select>

          <label style={{ fontSize:11, fontWeight:600, color:'#374151', marginLeft:8 }}>Month</label>
          <select value={monthName} onChange={e => setMonthName(e.target.value)}
                  style={{ padding:'4px 8px', fontSize:12, border:'1px solid #d1d5db', borderRadius:4 }}>
            {MONTHS.map(m => <option key={m}>{m}</option>)}
          </select>
          <select value={year} onChange={e => setYear(e.target.value)}
                  style={{ padding:'4px 8px', fontSize:12, border:'1px solid #d1d5db', borderRadius:4 }}>
            {YEARS.map(y => <option key={y}>{y}</option>)}
          </select>

          <button onClick={loadData} disabled={loading} style={{
            padding:'4px 16px', fontSize:11, fontWeight:600,
            background:'#1e3a5f', color:'#fff', border:'none', borderRadius:4,
            cursor: loading ? 'not-allowed' : 'pointer',
          }}>
            {loading ? 'Loading…' : 'Load'}
          </button>

          {totalChanges > 0 && (
            <button onClick={saveAll} disabled={saving} style={{
              padding:'4px 16px', fontSize:11, fontWeight:700,
              background: saving ? '#94a3b8' : '#166534', color:'#fff',
              border:'none', borderRadius:4, cursor: saving ? 'not-allowed' : 'pointer',
            }}>
              {saving ? 'Saving…' : `Save All (${totalChanges} changes)`}
            </button>
          )}

          <span style={{ marginLeft:'auto', fontSize:11, color:'#94a3b8' }}>
            {reportMonth}{loading && ' ⟳'}
          </span>
        </div>

        {/* ── Notice ── */}
        {notice && <Notice type={notice.type} text={notice.text} onClose={() => setNotice(null)} />}

        {/* ── SAIL BF calculator (SAIL plant, BF area only) ── */}
        {isSail && area === 'Blast Furnace' && (
          <div style={{ background:'#eff6ff', border:'1px solid #bfdbfe', borderRadius:8, padding:'12px 16px', marginBottom:14 }}>
            <div style={{ fontWeight:700, fontSize:12, color:'#1e40af', marginBottom:6 }}>
              SAIL BF Aggregate Calculator
            </div>
            <p style={{ fontSize:11, color:'#374151', margin:'0 0 10px' }}>
              Computes SAIL BF_Shop as HM-weighted averages across all plants. BF Productivity uses harmonic mean.
            </p>
            <div style={{ display:'flex', gap:10, alignItems:'center', flexWrap:'wrap' }}>
              <button onClick={previewSail} disabled={sailBusy} style={{
                padding:'5px 14px', fontSize:11, fontWeight:600,
                background:'#3b82f6', color:'#fff', border:'none',
                borderRadius:4, cursor: sailBusy ? 'not-allowed' : 'pointer',
              }}>
                {sailBusy ? 'Working…' : 'Preview SAIL Calculation'}
              </button>
              <label style={{ fontSize:11, display:'flex', alignItems:'center', gap:4, cursor:'pointer' }}>
                <input type="checkbox" checked={overwriteMan}
                       onChange={e => setOverwriteMan(e.target.checked)} />
                Overwrite manually-entered SAIL values
              </label>
            </div>

            {sailPreview && (
              <div style={{ marginTop:12 }}>
                <div style={{ fontSize:11, fontWeight:600, color:'#1e40af', marginBottom:6 }}>
                  HM weights: {Object.entries(sailPreview.hm_weights || {})
                    .map(([p, v]) => `${p}=${v?.toFixed(0) ?? '?'}`).join(' | ')} (kt)
                </div>
                <table style={{ width:'100%', borderCollapse:'collapse', fontSize:10 }}>
                  <thead>
                    <tr style={{ background:'#dbeafe' }}>
                      <th style={TH}>Parameter</th>
                      <th style={TH}>Calculated (Month)</th>
                      <th style={TH}>Existing SAIL</th>
                      <th style={TH}>Will Save</th>
                    </tr>
                  </thead>
                  <tbody>
                    {Object.keys(sailPreview.calculated?.month || {}).map((k, i) => {
                      const calc     = sailPreview.calculated?.month?.[k];
                      const exist    = sailPreview.existing_sail?.month?.[k];
                      const willSave = overwriteMan ? calc : (exist ?? calc);
                      return (
                        <tr key={k} style={{ background: i % 2 === 0 ? '#fff' : '#f0f9ff' }}>
                          <td style={TD}>{labelOf(k)}</td>
                          <td style={{ ...TD, textAlign:'right' }}>{calc?.toFixed(3) ?? '—'}</td>
                          <td style={{ ...TD, textAlign:'right', color: exist != null ? '#166534' : '#9ca3af' }}>
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
                <button onClick={applySail} disabled={sailBusy} style={{
                  marginTop:8, padding:'5px 16px', fontSize:11, fontWeight:700,
                  background:'#166534', color:'#fff', border:'none',
                  borderRadius:4, cursor: sailBusy ? 'not-allowed' : 'pointer',
                }}>
                  {sailBusy ? 'Saving…' : 'Apply & Save SAIL BF_Shop'}
                </button>
              </div>
            )}
          </div>
        )}

        {/* ── Area tabs ── */}
        <div style={{ display:'flex', gap:0, borderBottom:'2px solid #e2e8f0', marginBottom:14 }}>
          {AREA_ORDER.map(a => (
            <button key={a} onClick={() => setArea(a)} style={{
              padding:'6px 14px', fontSize:11, fontWeight: a === area ? 700 : 400,
              border:'none', borderBottom: a === area ? '3px solid #1e3a5f' : '3px solid transparent',
              background:'transparent', color: a === area ? '#1e3a5f' : '#6b7280',
              cursor:'pointer', marginBottom:-2,
            }}>
              {a}
              {areaUnits[a]?.length > 0 && (
                <span style={{ marginLeft:4, fontSize:9, background:'#e2e8f0', padding:'1px 5px', borderRadius:9 }}>
                  {areaUnits[a].length}
                </span>
              )}
            </button>
          ))}
        </div>

        {/* ── Two-column layout ── */}
        <div style={{ display:'flex', gap:14 }}>

          {/* ── Unit sidebar ── */}
          <div style={{ width:148, flexShrink:0 }}>
            <div style={{ fontSize:10, fontWeight:600, color:'#9ca3af', textTransform:'uppercase', letterSpacing:'0.05em', marginBottom:6 }}>
              Units
            </div>

            {/* Add unit */}
            <button onClick={() => setShowAddUnit(true)} style={{
              width:'100%', padding:'5px 8px', fontSize:10, fontWeight:600,
              background:'#f0fdf4', border:'1px solid #86efac', borderRadius:4,
              color:'#166534', cursor:'pointer', marginBottom:8,
            }}>
              + Add Unit
            </button>

            {/* Copy from month */}
            <CopyFromPanel currentMonth={reportMonth} plant={plant} onCopy={handleCopyFrom} />

            {/* Unit list */}
            {visibleUnits.length === 0 ? (
              <div style={{ fontSize:11, color:'#9ca3af', fontStyle:'italic', lineHeight:1.5 }}>
                No {area} units.
                <br />Click "+ Add Unit" to start.
              </div>
            ) : (
              visibleUnits.map(u => {
                const chg     = countChanges(unitData[u], initData[u]);
                const isSaved = savedUnits.has(u) && chg === 0;
                return (
                  <button key={u} onClick={() => setSelUnit(u)} style={{
                    display:'block', width:'100%', textAlign:'left',
                    padding:'6px 10px', marginBottom:3, fontSize:11,
                    fontWeight: u === selUnit ? 700 : 400,
                    background: u === selUnit ? '#1e3a5f' : '#fff',
                    color: u === selUnit ? '#fff' : '#374151',
                    border:`1px solid ${chg > 0 ? '#f59e0b' : '#e2e8f0'}`,
                    borderRadius:5, cursor:'pointer',
                  }}>
                    {u}
                    {chg > 0 && (
                      <span style={{
                        float:'right', fontSize:9, background:'#f59e0b',
                        color:'#fff', padding:'1px 4px', borderRadius:8,
                      }}>{chg}</span>
                    )}
                    {isSaved && (
                      <span style={{ float:'right', fontSize:10, color:'#16a34a' }}>✓</span>
                    )}
                  </button>
                );
              })
            )}
          </div>

          {/* ── Param form ── */}
          <div style={{ flex:1, minWidth:0 }}>
            {!selUnit ? (
              <div style={{
                color:'#9ca3af', fontSize:12, padding:'40px 0',
                textAlign:'center', border:'2px dashed #e2e8f0', borderRadius:8,
              }}>
                {visibleUnits.length === 0
                  ? `No ${area} units for ${plant} ${reportMonth}. Click "+ Add Unit" to begin.`
                  : 'Select a unit from the left to view or edit its parameters.'}
              </div>
            ) : (
              <div style={{ background:'#fff', border:'1px solid #e2e8f0', borderRadius:8, padding:'14px' }}>
                {/* Unit header */}
                <div style={{ display:'flex', alignItems:'center', justifyContent:'space-between', marginBottom:10, flexWrap:'wrap', gap:8 }}>
                  <div>
                    <span style={{ fontWeight:700, fontSize:13, color:'#1e3a5f' }}>
                      {plant} › {selUnit}
                    </span>
                    <span style={{ fontSize:10, color:'#64748b', marginLeft:10 }}>{reportMonth}</span>
                  </div>
                  <div style={{ display:'flex', gap:8, alignItems:'center' }}>
                    {countChanges(unitData[selUnit], initData[selUnit]) > 0 && (
                      <span style={{
                        fontSize:10, color:'#b45309', background:'#fffbeb',
                        border:'1px solid #f59e0b', padding:'2px 8px', borderRadius:9,
                      }}>
                        {countChanges(unitData[selUnit], initData[selUnit])} unsaved
                      </span>
                    )}
                    <button onClick={() => saveUnit(selUnit)} disabled={saving} style={{
                      padding:'5px 18px', fontSize:11, fontWeight:700,
                      background: saving ? '#94a3b8' : '#166534', color:'#fff',
                      border:'none', borderRadius:5, cursor: saving ? 'not-allowed' : 'pointer',
                    }}>
                      {saving ? 'Saving…' : `Save ${selUnit}`}
                    </button>
                  </div>
                </div>

                {/* Parameter table */}
                <UnitForm
                  unit={selUnit}
                  data={unitData[selUnit]}
                  initialData={initData[selUnit]}
                  onChange={(period, key, val) => handleChange(selUnit, period, key, val)}
                  busy={saving}
                />

                {/* Add custom param */}
                <AddParam disabled={saving} onAdd={key => handleAddParam(selUnit, key)} />
              </div>
            )}
          </div>
        </div>

        {/* ── Footer note ── */}
        <div style={{ marginTop:16, fontSize:10, color:'#9ca3af', display:'flex', justifyContent:'space-between', flexWrap:'wrap', gap:4 }}>
          <span>Amber cells = unsaved changes vs last-loaded DB values.</span>
          <span>Null values are not overwritten on save. File-uploaded and manual data coexist — last write wins per parameter.</span>
        </div>
      </div>
    </div>
  );
}
