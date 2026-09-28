'use client';

import RequireEditor from '@/components/RequireEditor';

import React, { useState, useEffect, useCallback } from 'react';
import GlobalNavbar from '@/components/GlobalNavbar';
import {
  PLANTS, AREA_ORDER, PARAM_TEMPLATES, PLANT_PARAM_EXTRAS, templateFor,
  KNOWN_UNITS, unitArea, BF_ORDER, sortUnitsInArea, _LABEL_MAP, labelOf,
} from '@/lib/technoParamRegistry';
import ui from '@/styles/ui.module.css';
import m from './manual.module.css';

const API = process.env.NEXT_PUBLIC_API_URL || '';

// FastAPI's own validation errors (Pydantic type mismatches, missing
// fields, etc.) come back as detail: [{loc, msg, type}, ...], not a plain
// string — `new Error(detail)` on an array stringifies each object via
// toString(), producing the unreadable "Save failed: [object Object],
// [object Object]". Join the real .msg (with which field, from .loc, when
// present) into one readable line instead; a plain string detail (the
// common HTTPException(...) case elsewhere in this app) passes through
// unchanged.
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
const YEAR_RANGE_START = 2000;
const _now = new Date();
// FY start year: Apr..Dec -> this calendar year; Jan..Mar -> previous calendar year
const CURRENT_FY_END_YEAR = (_now.getMonth() >= 3 ? _now.getFullYear() : _now.getFullYear() - 1) + 1;

// Calendar years: 2000 through the current FY's end year (covers Jan-Mar
// report months that fall in the current FY but the next calendar year).
const YEARS = Array.from(
  { length: CURRENT_FY_END_YEAR - YEAR_RANGE_START + 1 },
  (_, i) => String(YEAR_RANGE_START + i)
);

function getDefaultPeriod() {
  const d = new Date(); d.setMonth(d.getMonth() - 1);
  // MONTHS is FY-ordered (April-first) — can't index it with JS's
  // Jan-ordered getMonth(), so look the name up in a Jan-ordered array.
  const names = ['January','February','March','April','May','June','July','August','September','October','November','December'];
  return { monthName: names[d.getMonth()], year: String(d.getFullYear()) };
}

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

// Keys the user explicitly blanked out this session (had a real saved
// value in `initial`, now null/missing in `current`) — the backend's
// merge-upsert otherwise treats a null incoming value as "field wasn't
// touched, keep whatever's in the DB", so clearing an input and saving
// silently did nothing and the old value kept reappearing on reload (e.g.
// ISP's Average Lining Life). These get sent as an explicit delete list
// alongside the normal month_data/till_month_data payload — see
// api_techno_manual.py's SaveRequest.clear_month_keys/clear_till_keys.
function clearedKeys(current, initial, period) {
  const cur = current?.[period] || {};
  const ini = initial?.[period] || {};
  return Object.keys(ini).filter(k => ini[k] !== null && ini[k] !== undefined && (cur[k] === null || cur[k] === undefined));
}

// ── Tiny shared components ────────────────────────────────────────────────────
const NOTICE_CLASS = { success: ui.alertSuccess, error: ui.alertError, info: ui.alertWarning };

function Notice({ type, text, onClose }) {
  if (!text) return null;
  return (
    <div role={type === 'error' ? 'alert' : 'status'}
         className={`${ui.alert} ${NOTICE_CLASS[type] || ui.alertWarning}`}
         style={{ display:'flex', alignItems:'center', justifyContent:'space-between', gap:8 }}>
      <span>{text}</span>
      {onClose && (
        <button type="button" onClick={onClose} aria-label="Dismiss message"
                className={`${ui.btn} ${ui.btnSm}`}
                style={{ background:'none', border:'none', color:'inherit', padding:'0 6px', fontSize:18 }}>
          ×
        </button>
      )}
    </div>
  );
}

// ── Number input cell ─────────────────────────────────────────────────────────
function NumInput({ value, onChange, disabled, changed, label }) {
  return (
    <input
      type="number"
      step="any"
      inputMode="decimal"
      value={value ?? ''}
      disabled={disabled}
      aria-label={label}
      onChange={e => onChange(e.target.value === '' ? null : parseFloat(e.target.value))}
      className={`${m.cell} ${changed ? m.cellChanged : ''}`}
    />
  );
}

// Modal shell: Escape or a click on the backdrop closes it.
function Modal({ titleId, wide, onClose, children }) {
  useEffect(() => {
    const onKey = (e) => { if (e.key === 'Escape') onClose(); };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [onClose]);
  return (
    <div className={m.overlay} onMouseDown={(e) => { if (e.target === e.currentTarget) onClose(); }}>
      <div role="dialog" aria-modal="true" aria-labelledby={titleId}
           className={`${m.modal} ${wide ? m.modalWide : ''}`}>
        {children}
      </div>
    </div>
  );
}

// ── Parameter table for one unit ──────────────────────────────────────────────
function UnitForm({ unit, plant, data, initialData, onChange, busy, selParam, onSelectParam }) {
  const area        = unitArea(unit);
  const templateKeys = templateFor(area, plant, unit);

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
      <p className={m.emptyHint} style={{ margin:'16px 0' }}>
        No parameters. Use &quot;Add parameter&quot; below to add custom keys.
      </p>
    );

  return (
    <div className={m.gridWrap}>
      <table className={m.grid}>
        <thead>
          <tr>
            <th scope="col" style={{ width:'44%' }}>Parameter (select for Calculate Cumulative)</th>
            <th scope="col" style={{ width:'28%' }}>Month Value</th>
            <th scope="col" style={{ width:'28%' }}>YTD (Cumulative)</th>
          </tr>
        </thead>
        <tbody>
          {allKeys.map((key) => {
            const mv      = data?.month?.[key]      ?? null;
            const tv      = data?.till_month?.[key] ?? null;
            const initM   = initialData?.month?.[key]      ?? null;
            const initT   = initialData?.till_month?.[key] ?? null;
            const isTempl = templateKeys.includes(key);
            const isSel   = key === selParam;
            const label   = labelOf(key);
            return (
              <tr key={key} className={isSel ? m.rowSelected : undefined}>
                <td>
                  <button type="button" aria-pressed={isSel}
                          className={`${m.paramBtn} ${isTempl ? '' : m.paramExtra}`}
                          onClick={() => onSelectParam(isSel ? null : key)}
                          title="Select this field for Calculate Cumulative">
                    <span className={m.radio} aria-hidden="true" />
                    <span>
                      <span className={m.paramName}>{label}</span>
                      <span className={m.paramKey}>{key}</span>
                    </span>
                  </button>
                </td>
                <td>
                  <NumInput value={mv} disabled={busy} changed={mv !== initM} label={`${label}, month value`}
                    onChange={v => onChange('month', key, v)} />
                </td>
                <td>
                  <NumInput value={tv} disabled={busy} changed={tv !== initT} label={`${label}, YTD cumulative`}
                    onChange={v => onChange('till_month', key, v)} />
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

// ── Add-param panel ───────────────────────────────────────────────────────────
function AddParam({ onAdd, disabled }) {
  const [key, setKey] = useState('');
  return (
    <form className={m.addParam}
          onSubmit={e => { e.preventDefault(); if (key) { onAdd(key); setKey(''); } }}>
      <label htmlFor="tm-add-param" className={ui.srOnly}>Custom parameter key</label>
      <input
        id="tm-add-param"
        className="form-control"
        placeholder="Custom param key (e.g. hot_blast_temp)"
        value={key}
        onChange={e => setKey(e.target.value.trim().toLowerCase().replace(/\s+/g,'_'))}
      />
      <button type="submit" className={`${ui.btn} ${ui.btnSecondary}`} disabled={disabled || !key}>
        + Add parameter
      </button>
    </form>
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
    <Modal titleId="tm-add-unit-title" onClose={onClose}>
      <form onSubmit={e => { e.preventDefault(); submit(); }}>
        <h3 id="tm-add-unit-title" className={m.modalTitle} style={{ marginBottom:16 }}>Add Unit</h3>

        <div className={ui.field}>
          <label htmlFor="tm-unit-select" className={ui.label}>Select from known units</label>
          <select
            id="tm-unit-select"
            className="form-control"
            autoFocus
            value={custom ? '__custom__' : unitName}
            onChange={e => {
              if (e.target.value === '__custom__') { setCustom(true); setUnitName(''); }
              else { setCustom(false); setUnitName(e.target.value); }
            }}
          >
            <option value="">— Select unit —</option>
            {available.map(u => <option key={u} value={u}>{u}</option>)}
            <option value="__custom__">Custom (type below)…</option>
          </select>
        </div>

        {custom && (
          <div className={ui.field}>
            <label htmlFor="tm-unit-custom" className={ui.label}>Unit name</label>
            <input
              id="tm-unit-custom"
              className="form-control"
              autoFocus
              placeholder="e.g. BF-9"
              value={unitName}
              onChange={e => setUnitName(e.target.value)}
            />
          </div>
        )}

        <p className={ui.hint}>
          Standard template parameters for this unit type will appear as blank rows ready for input.
        </p>

        <div className={m.modalActions}>
          <button type="button" className={`${ui.btn} ${ui.btnSecondary}`} onClick={onClose}>Cancel</button>
          <button type="submit" className={`${ui.btn} ${ui.btnPrimary}`} disabled={!unitName.trim()}>Add Unit</button>
        </div>
      </form>
    </Modal>
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
      if (!r.ok) throw new Error(errText(d.detail, 'fetch failed'));
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
    <button type="button" onClick={() => setOpen(true)} aria-expanded={false}
            className={`${ui.btn} ${ui.btnSecondary} ${ui.btnSm} ${ui.btnBlock}`}>
      Copy from Month…
    </button>
  );

  return (
    <div className={m.copyPanel}>
      <div className={ui.label}>Copy values from</div>
      <label htmlFor="tm-copy-month" className={ui.srOnly}>Source month</label>
      <select id="tm-copy-month" className="form-control" value={monthName} onChange={e => setMonthName(e.target.value)}>
        {MONTHS.map(mo => <option key={mo}>{mo}</option>)}
      </select>
      <label htmlFor="tm-copy-year" className={ui.srOnly}>Source year</label>
      <select id="tm-copy-year" className="form-control" value={year} onChange={e => setYear(e.target.value)}>
        {YEARS.map(y => <option key={y}>{y}</option>)}
      </select>
      {status && <Notice type={status.type} text={status.text} />}
      <div className={ui.actions} style={{ flexWrap:'nowrap' }}>
        <button type="button" onClick={doCopy} disabled={loading} aria-busy={loading}
                className={`${ui.btn} ${ui.btnPrimary} ${ui.btnSm}`} style={{ flex:1 }}>
          {loading ? 'Loading…' : `Copy from ${srcMonth}`}
        </button>
        <button type="button" onClick={() => { setOpen(false); setStatus(null); }} aria-label="Close copy panel"
                className={`${ui.btn} ${ui.btnSecondary} ${ui.btnSm}`}>
          ×
        </button>
      </div>
    </div>
  );
}

// ── Cumulative calculation preview modal ──────────────────────────────────────
function CumulativeModal({ preview, onApply, onClose }) {
  if (!preview) return null;
  const hasWeights = preview.method === 'weighted_average' || preview.method === 'harmonic_mean';
  const methodLabel = {
    weighted_average: 'Production-weighted average',
    harmonic_mean:    'Production-weighted harmonic mean',
    simple_average:   'Simple average of monthly values',
    sum:              'Sum of monthly values',
  }[preview.method] || preview.method;

  return (
    <Modal titleId="tm-cum-title" wide onClose={onClose}>
      <h3 id="tm-cum-title" className={m.modalTitle}>
        Cumulative Calculation — {labelOf(preview.param_key)}
      </h3>
      <p className={ui.meta}>
        {preview.plant} › {preview.unit} · April → {preview.report_month} · {methodLabel}
        {hasWeights && preview.weight_item && (
          <><br />Weights: {preview.weight_item}</>
        )}
      </p>

      {(preview.warnings || []).map((w, i) => (
        <Notice key={i} type="info" text={w} />
      ))}

      {/* Month-by-month table */}
      <div className={ui.tableWrap}>
        <table className={ui.table}>
          <thead>
            <tr>
              <th scope="col">Month</th>
              <th scope="col" className={ui.numeric}>Monthly Value</th>
              {hasWeights && <th scope="col" className={ui.numeric}>Production (weight)</th>}
              {hasWeights && (
                <th scope="col" className={ui.numeric}>
                  {preview.method === 'harmonic_mean' ? 'Production ÷ Value' : 'Value × Production'}
                </th>
              )}
            </tr>
          </thead>
          <tbody>
            {(preview.rows || []).map((r) => (
              <tr key={r.month}>
                <td className={ui.nowrap}>{r.month}</td>
                <td className={ui.numeric}>{r.value ?? '—'}</td>
                {hasWeights && (
                  <td className={`${ui.numeric} ${r.weight == null ? m.missing : ''}`}>
                    {r.weight ?? 'missing'}
                  </td>
                )}
                {hasWeights && <td className={ui.numeric}>{r.product ?? '—'}</td>}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Step-by-step working */}
      <div className={m.steps}>
        <div className={m.stepsTitle}>Calculation steps</div>
        {(preview.steps || []).map((s, i) => (
          <div key={i} className={m.step}>{i + 1}. {s}</div>
        ))}
      </div>

      {/* Result + actions */}
      <div className={m.modalActions}>
        <div className={m.result}>Cumulative = {preview.result}</div>
        <button type="button" className={`${ui.btn} ${ui.btnSecondary}`} onClick={onClose}>Close</button>
        <button type="button" className={`${ui.btn} ${ui.btnPrimary}`} autoFocus
                onClick={() => onApply(preview.param_key, preview.result)}>
          Apply to YTD box
        </button>
      </div>
    </Modal>
  );
}

// ── Main page ─────────────────────────────────────────────────────────────────
function TechnoManualPageInner() {
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

  // Selected parameter row — "Calculate Cumulative" acts on this field only
  const [selParam,    setSelParam]    = useState(null);
  const [cumBusy,     setCumBusy]     = useState(false);
  const [cumPreview,  setCumPreview]  = useState(null);

  const reportMonth = `${year}-${MONTH_NUM[monthName]}`;

  // ── Load data ───────────────────────────────────────────────────────────────
  const loadData = useCallback(async () => {
    setLoading(true); setNotice(null); setSavedUnits(new Set());
    try {
      const r = await fetch(`${API}/api/techno/manual/entry?plant=${plant}&report_month=${reportMonth}`);
      const d = await r.json();
      if (!r.ok) throw new Error(errText(d.detail, 'fetch failed'));
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
    // BSL's "SMS" unit is a shop-level rollup (LD Slag/Refractory/overall
    // consumption figures), not a 3rd converter shop alongside SMS-I/SMS-II
    // - unlike every other plant, which only ever has its real converter
    // shops here. Hide it from the tab list so it doesn't look like a bogus
    // extra shop; the data itself, extraction, and page 30's report
    // generation (which already knows to fold this into SMS-I/SMS-II) are
    // untouched - this unit is simply never selected, so it's never edited
    // or saved over.
    if (plant === 'BSL' && u === 'SMS') return;
    const a = unitArea(u);
    (areaUnits[a] = areaUnits[a] || []).push(u);
  });
  AREA_ORDER.forEach(a => { areaUnits[a] = sortUnitsInArea(a, areaUnits[a] || []); });

  const visibleUnits = areaUnits[area] || [];

  useEffect(() => {
    if (!visibleUnits.includes(selUnit)) setSelUnit(visibleUnits[0] || null);
  }, [area, visibleUnits.join(',')]);

  // Clear field selection when switching unit / plant / month
  useEffect(() => { setSelParam(null); setCumPreview(null); }, [selUnit, plant, reportMonth]);

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

  // ── Calculate Cumulative (button-triggered, SELECTED FIELD only) ────────────
  // Asks the backend to compute the YTD for the selected parameter from
  // Apr→current monthly values (weighted by monthly crude steel production for
  // per-TCS params) and shows the full working in a modal. Nothing is written
  // until the user clicks "Apply to YTD box" — and the box stays editable.
  async function calculateCumulative(unit) {
    if (!selParam) {
      setNotice({ type:'info', text:'Select a parameter row first (click its name) — the button calculates that field only.' });
      return;
    }
    setCumBusy(true); setNotice(null);
    try {
      const currentVal  = unitData[unit]?.month?.[selParam];
      const currentProd = unitData[unit]?.month?.production;
      const qs = new URLSearchParams({
        plant, unit, param_key: selParam, report_month: reportMonth,
        ...(currentVal !== null && currentVal !== undefined ? { current_value: currentVal } : {}),
        ...(currentProd !== null && currentProd !== undefined ? { current_production: currentProd } : {}),
      });
      const r = await fetch(`${API}/api/techno/manual/cumulative-preview?${qs}`);
      const d = await r.json();
      if (!r.ok) throw new Error(errText(d.detail, 'calculation failed'));
      setCumPreview(d);
    } catch (e) {
      setNotice({ type:'error', text:`Cumulative calculation: ${e.message}` });
    } finally {
      setCumBusy(false);
    }
  }

  // Write the previewed result into the selected field's YTD box (still editable)
  function applyCumulative(key, result) {
    if (selUnit) handleChange(selUnit, 'till_month', key, result);
    setCumPreview(null);
    setNotice({ type:'success', text:`YTD (Cumulative) for ${labelOf(key)} set to ${result}. Review and Save.` });
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
    const tmpl   = templateFor(a, plant, unitName);
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
      const init = initData[unit] || {};
      const r = await fetch(`${API}/api/techno/manual/save`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          plant, report_month: reportMonth, unit,
          month_data:      d.month      || {},
          till_month_data: d.till_month || {},
          clear_month_keys: clearedKeys(d, init, 'month'),
          clear_till_keys:  clearedKeys(d, init, 'till_month'),
        }),
      });
      const res = await r.json();
      if (!r.ok) throw new Error(errText(res.detail, 'save failed'));
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
        const init = initData[unit] || {};
        const r = await fetch(`${API}/api/techno/manual/save`, {
          method:'POST', headers:{'Content-Type':'application/json'},
          body: JSON.stringify({
            plant, report_month: reportMonth, unit,
            month_data: d.month || {}, till_month_data: d.till_month || {},
            clear_month_keys: clearedKeys(d, init, 'month'),
            clear_till_keys:  clearedKeys(d, init, 'till_month'),
          }),
        });
        const res = await r.json();
        if (!r.ok) throw new Error(errText(res.detail, 'save failed'));
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
      if (!r.ok) throw new Error(errText(d.detail, 'preview failed'));
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
      if (!r.ok) throw new Error(errText(d.detail, 'calc failed'));
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
    <>
      <GlobalNavbar />

      {showAddUnit && (
        <AddUnitModal
          existingUnits={Object.keys(unitData)}
          onAdd={handleAddUnit}
          onClose={() => setShowAddUnit(false)}
        />
      )}

      {cumPreview && (
        <CumulativeModal
          preview={cumPreview}
          onApply={applyCumulative}
          onClose={() => setCumPreview(null)}
        />
      )}

      <main className={ui.page} style={{ maxWidth:1500 }}>

        {/* ── Page title ── */}
        <div className={ui.pageHeader}>
          <h1 className={ui.pageTitle}>Techno Parameters — Universal Entry</h1>
          <p className={ui.pageLead}>Insert legacy data · revise uploaded values · manual corrections</p>
        </div>

        {/* ── Controls bar ── */}
        <div className={m.toolbar}>
          <div className={ui.field} style={{ marginBottom:0 }}>
            <label htmlFor="tm-plant" className={ui.label}>Plant</label>
            <select id="tm-plant" className="form-control" value={plant} onChange={e => setPlant(e.target.value)}>
              {PLANTS.map(p => <option key={p}>{p}</option>)}
            </select>
          </div>
          <div className={ui.field} style={{ marginBottom:0 }}>
            <label htmlFor="tm-month" className={ui.label}>Month</label>
            <select id="tm-month" className="form-control" value={monthName} onChange={e => setMonthName(e.target.value)}>
              {MONTHS.map(mo => <option key={mo}>{mo}</option>)}
            </select>
          </div>
          <div className={ui.field} style={{ marginBottom:0 }}>
            <label htmlFor="tm-year" className={ui.label}>Year</label>
            <select id="tm-year" className="form-control" value={year} onChange={e => setYear(e.target.value)}>
              {YEARS.map(y => <option key={y}>{y}</option>)}
            </select>
          </div>

          <button type="button" onClick={loadData} disabled={loading} aria-busy={loading}
                  className={`${ui.btn} ${ui.btnSecondary}`}>
            {loading ? 'Loading…' : 'Reload'}
          </button>

          <span className={m.spacer} />
          <span className={m.monthTag} aria-live="polite">
            {reportMonth}{totalChanges > 0 ? ` · ${totalChanges} unsaved change${totalChanges === 1 ? '' : 's'}` : ''}
          </span>
          {totalChanges > 0 && (
            <button type="button" onClick={saveAll} disabled={saving} aria-busy={saving}
                    className={`${ui.btn} ${ui.btnPrimary}`}>
              {saving ? 'Saving…' : `Save All (${totalChanges})`}
            </button>
          )}
        </div>

        {/* ── Notice ── */}
        {notice && <Notice type={notice.type} text={notice.text} onClose={() => setNotice(null)} />}

        {/* ── SAIL BF calculator (SAIL plant, BF area only) ── */}
        {isSail && area === 'Blast Furnace' && (
          <section className={m.sailBox} aria-labelledby="tm-sail-title">
            <h2 id="tm-sail-title" className={m.sailTitle}>SAIL BF Aggregate Calculator</h2>
            <p className={ui.meta}>
              Computes SAIL BF_Shop as HM-weighted averages across all plants. BF Productivity uses harmonic mean.
            </p>
            <div className={ui.actions} style={{ alignItems:'center' }}>
              <button type="button" onClick={previewSail} disabled={sailBusy} aria-busy={sailBusy}
                      className={`${ui.btn} ${ui.btnSecondary}`}>
                {sailBusy ? 'Working…' : 'Preview SAIL Calculation'}
              </button>
              <label className={ui.checkRow}>
                <input type="checkbox" checked={overwriteMan}
                       onChange={e => setOverwriteMan(e.target.checked)} />
                Overwrite manually-entered SAIL values
              </label>
            </div>

            {sailPreview && (
              <div style={{ marginTop:14 }}>
                <p className={ui.meta}>
                  HM weights: {Object.entries(sailPreview.hm_weights || {})
                    .map(([p, v]) => `${p}=${v?.toFixed(0) ?? '?'}`).join(' | ')} (kt)
                </p>
                <div className={ui.tableWrap}>
                  <table className={ui.table}>
                    <thead>
                      <tr>
                        <th scope="col">Parameter</th>
                        <th scope="col" className={ui.numeric}>Calculated (Month)</th>
                        <th scope="col" className={ui.numeric}>Existing SAIL</th>
                        <th scope="col" className={ui.numeric}>Will Save</th>
                      </tr>
                    </thead>
                    <tbody>
                      {Object.keys(sailPreview.calculated?.month || {}).map((k) => {
                        const calc     = sailPreview.calculated?.month?.[k];
                        const exist    = sailPreview.existing_sail?.month?.[k];
                        const willSave = overwriteMan ? calc : (exist ?? calc);
                        return (
                          <tr key={k}>
                            <td>{labelOf(k)}</td>
                            <td className={ui.numeric}>{calc?.toFixed(3) ?? '—'}</td>
                            <td className={`${ui.numeric} ${exist != null ? '' : ui.muted}`}>{exist?.toFixed(3) ?? '—'}</td>
                            <td className={ui.numeric} style={{ fontWeight:600 }}>{willSave?.toFixed(3) ?? '—'}</td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
                <div style={{ marginTop:12 }}>
                  <button type="button" onClick={applySail} disabled={sailBusy} aria-busy={sailBusy}
                          className={`${ui.btn} ${ui.btnPrimary}`}>
                    {sailBusy ? 'Saving…' : 'Apply & Save SAIL BF_Shop'}
                  </button>
                </div>
              </div>
            )}
          </section>
        )}

        {/* ── Area tabs ── */}
        <div className={m.tabs} role="tablist" aria-label="Shop area">
          {AREA_ORDER.map(a => (
            <button key={a} type="button" role="tab" aria-selected={a === area}
                    className={m.tab} onClick={() => setArea(a)}>
              {a}
              {areaUnits[a]?.length > 0 && (
                <span className={m.count} aria-label={`${areaUnits[a].length} units`}>{areaUnits[a].length}</span>
              )}
            </button>
          ))}
        </div>

        {/* ── Two-column layout ── */}
        <div className={m.layout}>

          {/* ── Unit sidebar ── */}
          <nav className={m.sidebar} aria-label={`${area} units`}>
            <div className={m.sideLabel}>Units</div>

            <button type="button" onClick={() => setShowAddUnit(true)}
                    className={`${ui.btn} ${ui.btnSecondary} ${ui.btnSm} ${ui.btnBlock}`}>
              + Add Unit
            </button>

            <CopyFromPanel currentMonth={reportMonth} plant={plant} onCopy={handleCopyFrom} />

            <div className={m.unitList}>
              {visibleUnits.length === 0 ? (
                <div className={m.emptyHint}>
                  No {area} units.
                  <br />Click &quot;+ Add Unit&quot; to start.
                </div>
              ) : (
                visibleUnits.map(u => {
                  const chg     = countChanges(unitData[u], initData[u]);
                  const isSaved = savedUnits.has(u) && chg === 0;
                  return (
                    <button key={u} type="button" onClick={() => setSelUnit(u)}
                            aria-current={u === selUnit ? 'true' : undefined}
                            className={`${m.unitBtn} ${chg > 0 ? m.unitBtnDirty : ''}`}>
                      <span>{u}</span>
                      {chg > 0 && <span className={m.dirtyBadge} aria-label={`${chg} unsaved`}>{chg}</span>}
                      {isSaved && <span className={m.savedMark} aria-label="saved">✓</span>}
                    </button>
                  );
                })
              )}
            </div>
          </nav>

          {/* ── Param form ── */}
          <div className={m.main}>
            {!selUnit ? (
              <div className={m.emptyState}>
                {visibleUnits.length === 0
                  ? `No ${area} units for ${plant} ${reportMonth}. Click "+ Add Unit" to begin.`
                  : 'Select a unit from the left to view or edit its parameters.'}
              </div>
            ) : (
              <section className={m.panel} aria-labelledby="tm-unit-title">
                {/* Unit header */}
                <div className={m.panelHead}>
                  <div>
                    <h2 id="tm-unit-title" className={m.panelTitle} style={{ display:'inline', margin:0 }}>
                      {plant} › {selUnit}
                    </h2>
                    <span className={m.panelSub}>{reportMonth}</span>
                  </div>
                  <div className={ui.actions} style={{ alignItems:'center' }}>
                    {countChanges(unitData[selUnit], initData[selUnit]) > 0 && (
                      <span className={m.dirtyBadge}>
                        {countChanges(unitData[selUnit], initData[selUnit])} unsaved
                      </span>
                    )}
                    <button
                      type="button"
                      onClick={() => calculateCumulative(selUnit)}
                      disabled={saving || cumBusy || !selParam}
                      aria-busy={cumBusy}
                      title={selParam ? `Calculate YTD for ${labelOf(selParam)}` : 'Select a parameter row first'}
                      className={`${ui.btn} ${ui.btnSecondary}`}
                    >
                      {cumBusy ? 'Calculating…'
                        : selParam ? `Calculate Cumulative — ${labelOf(selParam)}`
                        : 'Calculate Cumulative (select a field)'}
                    </button>
                    <button type="button" onClick={() => saveUnit(selUnit)} disabled={saving} aria-busy={saving}
                            className={`${ui.btn} ${ui.btnPrimary}`}>
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
                  selParam={selParam}
                  onSelectParam={setSelParam}
                />

                {/* Add custom param */}
                <AddParam disabled={saving} onAdd={key => handleAddParam(selUnit, key)} />
              </section>
            )}
          </div>
        </div>

        {/* ── Footer note ── */}
        <div className={m.footer}>
          <span>Amber cells = unsaved changes vs last-loaded values. Select a parameter, then &quot;Calculate Cumulative&quot; computes that field&apos;s YTD from Apr→current monthly values — BF rates are HM-production weighted (BF productivity: harmonic mean), per-TCS params are crude-steel weighted; shop units (BF_Shop/SMS) weight by plant production, other units by their own monthly production. Every step is shown before you apply; applied values stay editable.</span>
          <span>Clearing a box and saving removes that value. File-uploaded and manual data coexist — last write wins per parameter.</span>
        </div>
      </main>
    </>
  );
}

export default function TechnoManualPage() {
  return (
    <RequireEditor>
      <TechnoManualPageInner />
    </RequireEditor>
  );
}
