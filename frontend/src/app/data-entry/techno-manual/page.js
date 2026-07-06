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
    // Operating rates
    'coke_rate','nut_coke_rate','cdi','fuel_rate',
    'bf_productivity',
    // HM quality
    'silicon_in_hm','sulphur_in_hm','avg_hot_metal_temperature',
    // Blast
    'hot_blast_temp','o2_enrichment','blast_moisture','blast_volume',
    // Burden / slag
    'slag_rate','slag_offtake',
    'sinter_in_burden','pellet_in_burden','lump_in_burden',
    'tfe_in_sinter','tfe_in_pellet','tfe_in_lump','fe_in_ore',
    'coal_to_hm','furnace_availability',
  ],
  'SMS': [
    'specific_hm_consumption',
    'specific_scrap_consumption',
    'tmi','average_heat_weight','concast_ratio','cc_ratio','yield_sms',
    'average_blows_per_day','average_lining_life','caster_yield',
    'tap_to_tap_time','converter_availability','converter_utilisation',
    'refractory_consumption_sms','refractory_consumption_red',
    'specific_refractory_consumption','specific_lpg_consumption',
    'bof_gas_yield',
    'calcined_lime_consumption','limestone_consumption',
    'si-mn','fe-si','fe-mn','oxygen_blowing',
    'calcined_dolomite_consumption',
  ],
  'Coke Ovens': [
    'gross_coke_yield','bf_coke_yield',
    'gross_coke_rate','net_coke_rate','coke_production','coking_time',
    'specific_heat_coke_ovens','specific_power_coke_ovens',
    'crude_tar_yield','crude_benzol_yield','coke_oven_gas_yield','ammonium_sulphate_yield',
    'dry_coal_charge_oven',
    'm10','m40',
    'average_ash_in_coke','average_ash_in_coal_blend',
    'average_volatile_matter_in_coal_blend',
  ],
  'Sinter Plant': [
    'sinter_production','productivity','basicity','tfe_in_sinter',
  ],
  'Rolling Mills': ['rolling_yield','production'],
  'General': [
    'specific_energy_consumption',
    'bof_slag_utilisation','coke_screen_loss',
    'coal_to_hm',
    'specific_water_consumption','water_consumption',
    'specific_co2_emissions',
  ],
};

// Plant-specific params appended to an area template only for that plant
const PLANT_PARAM_EXTRAS = {
  DSP: { 'Sinter Plant': ['dsp_sp_1','dsp_sp_2'] },
};

// Params that are extensive totals — YTD cumulative = sum of monthly values.
// Everything else (rates, %, temperatures) defaults to arithmetic average.
const SUM_KEYS = new Set([
  'coke_production', 'sinter_production', 'production', 'water_consumption',
]);

// Cumulative = sum (SUM_KEYS) or average of prior FY-to-date monthly values
// plus the currently-entered month value. Returns null if nothing to base it on.
function computeCumulative(key, history, currentVal) {
  const vals = Object.values(history || {})
    .map(m => m?.[key])
    .filter(v => v !== null && v !== undefined);
  if (currentVal !== null && currentVal !== undefined) vals.push(currentVal);
  if (!vals.length) return null;
  const sum = vals.reduce((a, b) => a + b, 0);
  return SUM_KEYS.has(key) ? sum : sum / vals.length;
}

function templateFor(area, plant) {
  const base   = PARAM_TEMPLATES[area] || [];
  const extras = (PLANT_PARAM_EXTRAS[plant] || {})[area] || [];
  return [...base, ...extras];
}

// ── Known units list for "Add Unit" modal ─────────────────────────────────────
const KNOWN_UNITS = [
  'BF_Shop','BF-1','BF-2','BF-3','BF-4','BF-5','BF-6','BF-7','BF-8',
  'SMS','SMS-1','SMS-2','SMS-3','SMS-I','SMS-II',
  'COB','COB-old','COB-new','Coke Ovens',
  'SP','SP-1','SP-2','SP-3','Sinter',
  'General','PM','RSM','MM','URM','WRM','BRM','CRM 1&2','CRM 3','MSM',
  'Merchant Mill','Wheel Plant','Axle Plant',
];

// ── Label helpers ─────────────────────────────────────────────────────────────
const _LABEL_MAP = {
  // Coal / energy
  coal_to_hm:                           'Coal to Hot Metal (kg/kg)',
  specific_water_consumption:           'Specific Water Consumption',
  water_consumption:                    'Water Consumption',
  specific_co2_emissions:               'Specific CO₂ Emissions',
  coke_screen_loss:                     'Coke Screen Loss (%)',
  specific_energy_consumption:          'Specific Energy Consumption (GCal/TCS)',
  bof_slag_utilisation:                 'BOF Slag Utilisation (%)',
  // BF quality & operating
  silicon_in_hm:                        'Silicon in HM (%)',
  sulphur_in_hm:                        'Sulphur in HM (%)',
  avg_hot_metal_temperature:            'Avg. Hot Metal Temperature (°C)',
  hot_blast_temp:                       'Hot Blast Temperature (°C)',
  o2_enrichment:                        'O₂ Enrichment (%)',
  slag_offtake:                         'Slag Offtake (%)',
  sinter_in_burden:                     'Sinter in Burden (%)',
  pellet_in_burden:                     'Pellet in Burden (%)',
  furnace_availability:                 'Furnace Availability (%)',
  // SMS
  specific_hm_consumption:             'Specific HM Consumption (kg/TCS)',
  specific_scrap_consumption:          'Specific Scrap Consumption (kg/TCS)',
  average_heat_weight:                  'Average Heat Weight (t)',
  average_blows_per_day:                'Average Blows per Day',
  average_lining_life:                  'Average Lining Life (Heats)',
  caster_yield:                         'Caster Yield (%)',
  tap_to_tap_time:                      'Tap-to-Tap Time (min)',
  converter_availability:               'Converter Availability (%)',
  converter_utilisation:                'Converter Utilisation (%)',
  refractory_consumption_sms:           'Refractory Consumption SMS (kg/TCS)',
  refractory_consumption_red:           'Refractory Consumption RED (kg/TCS)',
  specific_refractory_consumption:      'Specific Refractory Consumption (kg/TCS)',
  specific_lpg_consumption:             'Specific LPG Consumption',
  bof_gas_yield:                        'BOF Gas Yield (Nm³/TCS)',
  calcined_lime_consumption:            'Calcined Lime Consumption (kg/TCS)',
  limestone_consumption:                'Limestone Consumption (kg/TCS)',
  'si-mn':                               'Si-Mn Consumption (kg/t)',
  'fe-si':                               'Fe-Si Consumption (kg/t)',
  'fe-mn':                               'Fe-Mn Consumption (kg/t)',
  oxygen_blowing:                        'Oxygen Blowing (Nm³/TCS)',
  calcined_dolomite_consumption:        'Calcined Dolomite Consumption (kg/TCS)',
  // Coke Ovens
  gross_coke_yield:                     'Gross Coke Yield (%)',
  bf_coke_yield:                        'B.F. Coke Yield (%)',
  specific_heat_coke_ovens:             'Specific Heat – Coke Ovens (M.Cal/T)',
  specific_power_coke_ovens:            'Specific Power – Coke Ovens (KWH/T)',
  crude_tar_yield:                       'Crude Tar Yield (kg/TDC)',
  crude_benzol_yield:                    'Crude Benzol Yield (Kg/TDC)',
  coke_oven_gas_yield:                  'Coke Oven Gas Yield (Nm³/T)',
  ammonium_sulphate_yield:               'Ammonium Sulphate Yield (Kg/TDC)',
  dry_coal_charge_oven:                 'Dry Coal Charge / Oven (T)',
  m10:                                  'M10 (%)',
  m40:                                  'M40 (%)',
  average_ash_in_coke:                  'Average Ash in Coke (%)',
  average_ash_in_coal_blend:            'Average Ash in Coal Blend (%)',
  average_volatile_matter_in_coal_blend:'Average Volatile Matter in Coal Blend (%)',
  // Sinter
  dsp_sp_1:                             'DSP SP-1 Productivity (T/m²/hr)',
  dsp_sp_2:                             'DSP SP-2 Productivity (T/m²/hr)',
};

function labelOf(key) {
  if (_LABEL_MAP[key]) return _LABEL_MAP[key];
  return key
    .replace(/_/g, ' ')
    .replace(/\b\w/g, c => c.toUpperCase())
    .replace(/\bBf\b/g, 'BF').replace(/\bHm\b/g, 'HM').replace(/\bCdi\b/g, 'CDI')
    .replace(/\bTmi\b/g, 'TMI').replace(/\bFe\b/g, 'Fe').replace(/\bTfe\b/g, 'TFE')
    .replace(/\bCc\b/g, 'CC').replace(/\bO2\b/g, 'O₂');
}

// ── Shared styles ─────────────────────────────────────────────────────────────
const TH = { padding:'9px 12px', border:'1px solid #e2e8f0', fontWeight:700, fontSize:14 };
const TD = { padding:'7px 10px', border:'1px solid #e2e8f0', verticalAlign:'middle', fontSize:14 };

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
      padding:'10px 16px', borderRadius:6, marginBottom:14, fontSize:14,
      display:'flex', alignItems:'center', justifyContent:'space-between', gap:8,
      background: ok ? '#f0fdf4' : info ? '#eff6ff' : '#fef2f2',
      color:      ok ? '#166534' : info ? '#1e40af' : '#991b1b',
      border:`1px solid ${ok ? '#86efac' : info ? '#bfdbfe' : '#fca5a5'}`,
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
        width:'100%', padding:'6px 10px', fontSize:14,
        border:`1px solid ${changed ? '#f59e0b' : '#d1d5db'}`,
        borderRadius:4,
        background: disabled ? '#f9fafb' : changed ? '#fffbeb' : '#fff',
        textAlign:'right',
      }}
    />
  );
}

// ── Parameter table for one unit ──────────────────────────────────────────────
function UnitForm({ unit, plant, data, initialData, onChange, busy }) {
  const area        = unitArea(unit);
  const templateKeys = templateFor(area, plant);

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
      <p style={{ color:'#6b7280', fontSize:14, margin:'16px 0' }}>
        No parameters. Use "Add Param" below to add custom keys.
      </p>
    );

  return (
    <div style={{
      border:'1px solid #e2e8f0', borderRadius:6, overflow:'hidden',
      maxHeight:'calc(100vh - 380px)', display:'flex', flexDirection:'column',
    }}>
      <div style={{ overflowY:'auto', overflowX:'auto', flex:1 }}>
        <table style={{ width:'100%', borderCollapse:'collapse', fontSize:14 }}>
          <thead>
            <tr style={{ background:'#f1f5f9', position:'sticky', top:0, zIndex:1 }}>
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
                    <br /><span style={{ fontSize:11, color:'#94a3b8' }}>{key}</span>
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
      </div>
    </div>
  );
}

// ── Add-param panel ───────────────────────────────────────────────────────────
function AddParam({ onAdd, disabled }) {
  const [key, setKey] = useState('');
  return (
    <div style={{ display:'flex', gap:8, alignItems:'center', marginTop:12 }}>
      <input
        placeholder="Custom param key (e.g. hot_blast_temp)"
        value={key}
        onChange={e => setKey(e.target.value.trim().toLowerCase().replace(/\s+/g,'_'))}
        style={{ flex:1, padding:'7px 10px', fontSize:14, border:'1px solid #d1d5db', borderRadius:4 }}
      />
      <button
        disabled={disabled || !key}
        onClick={() => { if (key) { onAdd(key); setKey(''); } }}
        style={{
          padding:'7px 16px', fontSize:14, background:'#3b82f6', color:'#fff',
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
        background:'#fff', borderRadius:10, padding:28, width:440,
        boxShadow:'0 8px 32px rgba(0,0,0,0.18)',
      }}>
        <h3 style={{ margin:'0 0 16px', fontSize:18, color:'#1e3a5f' }}>Add Unit</h3>

        <label style={{ fontSize:13, fontWeight:600, color:'#374151', display:'block', marginBottom:6 }}>
          Select from known units
        </label>
        <select
          value={custom ? '__custom__' : unitName}
          onChange={e => {
            if (e.target.value === '__custom__') { setCustom(true); setUnitName(''); }
            else { setCustom(false); setUnitName(e.target.value); }
          }}
          style={{ width:'100%', padding:'8px 10px', fontSize:14, border:'1px solid #d1d5db', borderRadius:4, marginBottom:12 }}
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
            style={{ width:'100%', padding:'8px 10px', fontSize:14, border:'1px solid #d1d5db', borderRadius:4, marginBottom:12, boxSizing:'border-box' }}
          />
        )}

        <p style={{ fontSize:12, color:'#6b7280', margin:'0 0 18px' }}>
          Standard template parameters for this unit type will appear as blank rows ready for input.
        </p>

        <div style={{ display:'flex', gap:10, justifyContent:'flex-end' }}>
          <button onClick={onClose} style={{
            padding:'7px 18px', fontSize:14, background:'#f1f5f9',
            border:'1px solid #e2e8f0', borderRadius:4, cursor:'pointer',
          }}>Cancel</button>
          <button onClick={submit} disabled={!unitName.trim()} style={{
            padding:'7px 18px', fontSize:14, fontWeight:600,
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
      width:'100%', padding:'7px 10px', fontSize:12, fontWeight:600,
      background:'#eff6ff', border:'1px solid #bfdbfe', borderRadius:4,
      color:'#1e40af', cursor:'pointer', marginBottom:10,
    }}>
      Copy from Month…
    </button>
  );

  return (
    <div style={{ background:'#eff6ff', border:'1px solid #bfdbfe', borderRadius:6, padding:'12px', marginBottom:10 }}>
      <div style={{ fontSize:12, fontWeight:700, color:'#1e40af', marginBottom:8 }}>
        Copy values from:
      </div>
      <select value={monthName} onChange={e => setMonthName(e.target.value)}
              style={{ width:'100%', fontSize:12, padding:'5px 8px', marginBottom:6, border:'1px solid #bfdbfe', borderRadius:3 }}>
        {MONTHS.map(m => <option key={m}>{m}</option>)}
      </select>
      <select value={year} onChange={e => setYear(e.target.value)}
              style={{ width:'100%', fontSize:12, padding:'5px 8px', marginBottom:8, border:'1px solid #bfdbfe', borderRadius:3 }}>
        {YEARS.map(y => <option key={y}>{y}</option>)}
      </select>
      {status && <Notice type={status.type} text={status.text} />}
      <div style={{ display:'flex', gap:6 }}>
        <button onClick={doCopy} disabled={loading} style={{
          flex:1, padding:'6px 0', fontSize:12, fontWeight:600,
          background: loading ? '#94a3b8' : '#1e40af', color:'#fff',
          border:'none', borderRadius:3, cursor: loading ? 'not-allowed' : 'pointer',
        }}>{loading ? 'Loading…' : `Copy from ${srcMonth}`}</button>
        <button onClick={() => { setOpen(false); setStatus(null); }} style={{
          padding:'6px 10px', fontSize:12, background:'#f1f5f9',
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
  // ytdHistory: {unit: {"2026-04": {param_key: val}, ...}} — FY-to-date monthly
  //   values (excluding the currently-selected month). Only read when the user
  //   clicks "Calculate Cumulative" — never applied automatically.
  const [ytdHistory,  setYtdHistory]  = useState({});
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
      setYtdHistory(d.ytd_history || {});

      if (!d.has_data)
        setNotice({ type:'info', text:`No data yet for ${plant} ${reportMonth}. Click "+ Add Unit" to begin.` });
    } catch (e) {
      setNotice({ type:'error', text:`Load failed: ${e.message}` });
      setUnitData({}); setInitData({}); setYtdHistory({});
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

  // ── Calculate Cumulative (button-triggered, current unit only) ─────────────
  // Fills in ONLY YTD boxes that are currently blank, from Apr→current monthly
  // history. Never overwrites a value already present — whether it came from
  // file upload/extraction or a prior manual entry — so that data always
  // prevails and the user can still edit the result afterwards.
  function calculateCumulative(unit) {
    const history = ytdHistory[unit] || {};
    const monthData = unitData[unit]?.month || {};
    const tillData  = unitData[unit]?.till_month || {};
    const keys = new Set([...Object.keys(monthData), ...Object.keys(tillData)]);

    let filled = 0;
    const nextTill = { ...tillData };
    for (const key of keys) {
      if (nextTill[key] !== null && nextTill[key] !== undefined) continue; // prevails — skip
      const calc = computeCumulative(key, history, monthData[key] ?? null);
      if (calc !== null) { nextTill[key] = calc; filled++; }
    }

    setUnitData(prev => ({
      ...prev,
      [unit]: { ...prev[unit], till_month: nextTill },
    }));
    setSavedUnits(prev => { const s = new Set(prev); s.delete(unit); return s; });
    setNotice(filled
      ? { type:'success', text:`Calculated ${filled} blank YTD value(s) for ${unit}. Review and Save.` }
      : { type:'info', text:`No blank YTD boxes to calculate for ${unit} (or no Month Values entered yet).` });
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
    const tmpl   = templateFor(a, plant);
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
    <div style={{ minHeight:'100vh', background:'#f8fafc', fontFamily:"-apple-system,BlinkMacSystemFont,'Segoe UI',Arial,sans-serif" }}>
      <GlobalNavbar />

      {showAddUnit && (
        <AddUnitModal
          existingUnits={Object.keys(unitData)}
          onAdd={handleAddUnit}
          onClose={() => setShowAddUnit(false)}
        />
      )}

      <div style={{ maxWidth:1500, margin:'0 auto', padding:'22px 20px' }}>

        {/* ── Page title ── */}
        <div style={{ display:'flex', alignItems:'baseline', gap:14, marginBottom:18 }}>
          <h2 style={{ fontSize:'1.6rem', fontWeight:700, color:'#1e3a5f', margin:0 }}>
            Techno Parameters — Universal Entry
          </h2>
          <span style={{ fontSize:13, color:'#94a3b8' }}>
            Insert legacy data · revise uploaded values · manual corrections
          </span>
        </div>

        {/* ── Controls bar ── */}
        <div style={{
          display:'flex', gap:10, alignItems:'center', flexWrap:'wrap',
          marginBottom:18, background:'#fff', border:'1px solid #e2e8f0',
          borderRadius:8, padding:'14px 18px',
        }}>
          <label style={{ fontSize:13, fontWeight:600, color:'#374151' }}>Plant</label>
          <select value={plant} onChange={e => setPlant(e.target.value)}
                  style={{ padding:'7px 10px', fontSize:14, border:'1px solid #d1d5db', borderRadius:4 }}>
            {PLANTS.map(p => <option key={p}>{p}</option>)}
          </select>

          <label style={{ fontSize:13, fontWeight:600, color:'#374151', marginLeft:10 }}>Month</label>
          <select value={monthName} onChange={e => setMonthName(e.target.value)}
                  style={{ padding:'7px 10px', fontSize:14, border:'1px solid #d1d5db', borderRadius:4 }}>
            {MONTHS.map(m => <option key={m}>{m}</option>)}
          </select>
          <select value={year} onChange={e => setYear(e.target.value)}
                  style={{ padding:'7px 10px', fontSize:14, border:'1px solid #d1d5db', borderRadius:4 }}>
            {YEARS.map(y => <option key={y}>{y}</option>)}
          </select>

          <button onClick={loadData} disabled={loading} style={{
            padding:'7px 20px', fontSize:14, fontWeight:600,
            background:'#1e3a5f', color:'#fff', border:'none', borderRadius:4,
            cursor: loading ? 'not-allowed' : 'pointer',
          }}>
            {loading ? 'Loading…' : 'Load'}
          </button>

          {totalChanges > 0 && (
            <button onClick={saveAll} disabled={saving} style={{
              padding:'7px 20px', fontSize:14, fontWeight:700,
              background: saving ? '#94a3b8' : '#166534', color:'#fff',
              border:'none', borderRadius:4, cursor: saving ? 'not-allowed' : 'pointer',
            }}>
              {saving ? 'Saving…' : `Save All (${totalChanges} changes)`}
            </button>
          )}

          <span style={{ marginLeft:'auto', fontSize:13, color:'#94a3b8' }}>
            {reportMonth}{loading && ' ⟳'}
          </span>
        </div>

        {/* ── Notice ── */}
        {notice && <Notice type={notice.type} text={notice.text} onClose={() => setNotice(null)} />}

        {/* ── SAIL BF calculator (SAIL plant, BF area only) ── */}
        {isSail && area === 'Blast Furnace' && (
          <div style={{ background:'#eff6ff', border:'1px solid #bfdbfe', borderRadius:8, padding:'16px 20px', marginBottom:18 }}>
            <div style={{ fontWeight:700, fontSize:15, color:'#1e40af', marginBottom:8 }}>
              SAIL BF Aggregate Calculator
            </div>
            <p style={{ fontSize:13, color:'#374151', margin:'0 0 12px' }}>
              Computes SAIL BF_Shop as HM-weighted averages across all plants. BF Productivity uses harmonic mean.
            </p>
            <div style={{ display:'flex', gap:12, alignItems:'center', flexWrap:'wrap' }}>
              <button onClick={previewSail} disabled={sailBusy} style={{
                padding:'7px 18px', fontSize:13, fontWeight:600,
                background:'#3b82f6', color:'#fff', border:'none',
                borderRadius:4, cursor: sailBusy ? 'not-allowed' : 'pointer',
              }}>
                {sailBusy ? 'Working…' : 'Preview SAIL Calculation'}
              </button>
              <label style={{ fontSize:13, display:'flex', alignItems:'center', gap:6, cursor:'pointer' }}>
                <input type="checkbox" checked={overwriteMan}
                       onChange={e => setOverwriteMan(e.target.checked)} />
                Overwrite manually-entered SAIL values
              </label>
            </div>

            {sailPreview && (
              <div style={{ marginTop:14 }}>
                <div style={{ fontSize:13, fontWeight:600, color:'#1e40af', marginBottom:8 }}>
                  HM weights: {Object.entries(sailPreview.hm_weights || {})
                    .map(([p, v]) => `${p}=${v?.toFixed(0) ?? '?'}`).join(' | ')} (kt)
                </div>
                <table style={{ width:'100%', borderCollapse:'collapse', fontSize:13 }}>
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
                  marginTop:10, padding:'7px 20px', fontSize:13, fontWeight:700,
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
        <div style={{ display:'flex', gap:0, borderBottom:'2px solid #e2e8f0', marginBottom:18 }}>
          {AREA_ORDER.map(a => (
            <button key={a} onClick={() => setArea(a)} style={{
              padding:'8px 18px', fontSize:14, fontWeight: a === area ? 700 : 400,
              border:'none', borderBottom: a === area ? '3px solid #1e3a5f' : '3px solid transparent',
              background:'transparent', color: a === area ? '#1e3a5f' : '#6b7280',
              cursor:'pointer', marginBottom:-2,
            }}>
              {a}
              {areaUnits[a]?.length > 0 && (
                <span style={{ marginLeft:6, fontSize:11, background:'#e2e8f0', padding:'2px 7px', borderRadius:9 }}>
                  {areaUnits[a].length}
                </span>
              )}
            </button>
          ))}
        </div>

        {/* ── Two-column layout ── */}
        <div style={{ display:'flex', gap:18 }}>

          {/* ── Unit sidebar ── */}
          <div style={{ width:190, flexShrink:0, display:'flex', flexDirection:'column', maxHeight:'calc(100vh - 260px)' }}>
            <div style={{ fontSize:12, fontWeight:600, color:'#9ca3af', textTransform:'uppercase', letterSpacing:'0.05em', marginBottom:8 }}>
              Units
            </div>

            {/* Add unit */}
            <button onClick={() => setShowAddUnit(true)} style={{
              width:'100%', padding:'7px 10px', fontSize:12, fontWeight:600,
              background:'#f0fdf4', border:'1px solid #86efac', borderRadius:4,
              color:'#166534', cursor:'pointer', marginBottom:10,
            }}>
              + Add Unit
            </button>

            {/* Copy from month */}
            <CopyFromPanel currentMonth={reportMonth} plant={plant} onCopy={handleCopyFrom} />

            {/* Unit list */}
            <div style={{ overflowY:'auto', flex:1 }}>
              {visibleUnits.length === 0 ? (
                <div style={{ fontSize:13, color:'#9ca3af', fontStyle:'italic', lineHeight:1.5 }}>
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
                      padding:'8px 12px', marginBottom:4, fontSize:13,
                      fontWeight: u === selUnit ? 700 : 400,
                      background: u === selUnit ? '#1e3a5f' : '#fff',
                      color: u === selUnit ? '#fff' : '#374151',
                      border:`1px solid ${chg > 0 ? '#f59e0b' : '#e2e8f0'}`,
                      borderRadius:5, cursor:'pointer',
                    }}>
                      {u}
                      {chg > 0 && (
                        <span style={{
                          float:'right', fontSize:11, background:'#f59e0b',
                          color:'#fff', padding:'1px 5px', borderRadius:8,
                        }}>{chg}</span>
                      )}
                      {isSaved && (
                        <span style={{ float:'right', fontSize:12, color:'#16a34a' }}>✓</span>
                      )}
                    </button>
                  );
                })
              )}
            </div>
          </div>

          {/* ── Param form ── */}
          <div style={{ flex:1, minWidth:0 }}>
            {!selUnit ? (
              <div style={{
                color:'#9ca3af', fontSize:14, padding:'50px 0',
                textAlign:'center', border:'2px dashed #e2e8f0', borderRadius:8,
              }}>
                {visibleUnits.length === 0
                  ? `No ${area} units for ${plant} ${reportMonth}. Click "+ Add Unit" to begin.`
                  : 'Select a unit from the left to view or edit its parameters.'}
              </div>
            ) : (
              <div style={{ background:'#fff', border:'1px solid #e2e8f0', borderRadius:8, padding:'18px' }}>
                {/* Unit header */}
                <div style={{ display:'flex', alignItems:'center', justifyContent:'space-between', marginBottom:14, flexWrap:'wrap', gap:10 }}>
                  <div>
                    <span style={{ fontWeight:700, fontSize:17, color:'#1e3a5f' }}>
                      {plant} › {selUnit}
                    </span>
                    <span style={{ fontSize:13, color:'#64748b', marginLeft:12 }}>{reportMonth}</span>
                  </div>
                  <div style={{ display:'flex', gap:10, alignItems:'center' }}>
                    {countChanges(unitData[selUnit], initData[selUnit]) > 0 && (
                      <span style={{
                        fontSize:12, color:'#b45309', background:'#fffbeb',
                        border:'1px solid #f59e0b', padding:'3px 10px', borderRadius:9,
                      }}>
                        {countChanges(unitData[selUnit], initData[selUnit])} unsaved
                      </span>
                    )}
                    <button onClick={() => calculateCumulative(selUnit)} disabled={saving} style={{
                      padding:'7px 18px', fontSize:14, fontWeight:600,
                      background:'#3b82f6', color:'#fff', border:'none',
                      borderRadius:5, cursor: saving ? 'not-allowed' : 'pointer',
                    }}>
                      Calculate Cumulative
                    </button>
                    <button onClick={() => saveUnit(selUnit)} disabled={saving} style={{
                      padding:'7px 22px', fontSize:14, fontWeight:700,
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
                  plant={plant}
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
        <div style={{ marginTop:18, fontSize:12, color:'#9ca3af', display:'flex', justifyContent:'space-between', flexWrap:'wrap', gap:6 }}>
          <span>Amber cells = unsaved changes vs last-loaded DB values. Click “Calculate Cumulative” to fill blank YTD boxes from Apr→current monthly history — existing values (file-uploaded or manual) are never overwritten, and results stay editable.</span>
          <span>Null values are not overwritten on save. File-uploaded and manual data coexist — last write wins per parameter.</span>
        </div>
      </div>
    </div>
  );
}
