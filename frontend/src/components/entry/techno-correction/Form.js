'use client';

import RequireEditor from '@/components/RequireEditor';

import React, { useState, useEffect } from 'react';
import { EntryPage } from '../EntryUI';
import {
  PLANTS, AREA_ORDER, templateFor, KNOWN_UNITS, unitArea, sortUnitsInArea, labelOf,
} from '@/lib/technoParamRegistry';
import ui from '@/styles/ui.module.css';
import c from './correction.module.css';

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
    <div role={ok ? 'status' : 'alert'} className={`${ui.alert} ${ok ? ui.alertSuccess : ui.alertError}`}
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

// Display only: at most 2 decimals (trailing zeros dropped), or the key's own
// DISPLAY_DP — same rule as techno-manual and bf-large-snapshot. The stored
// value keeps full precision and is only re-saved if the user edits the cell.
const DISPLAY_DP = { sulphur_in_hm: 3 };
function fmtDisplay(v, dp = 2) {
  if (typeof v !== 'number' || !Number.isFinite(v)) return v ?? '';
  return String(Math.round(v * 10 ** dp) / 10 ** dp);
}

function NumInput({ value, onChange, changed, label, dp }) {
  // Text typed in this box, shown as-is while editing; blur returns to the
  // rounded view.
  const [draft, setDraft] = useState(null);
  return (
    <input
      type="number"
      step="any"
      inputMode="decimal"
      aria-label={label}
      value={draft ?? fmtDisplay(value, dp)}
      onChange={e => {
        setDraft(e.target.value);
        onChange(e.target.value === '' ? null : parseFloat(e.target.value));
      }}
      onBlur={() => setDraft(null)}
      className={`${c.cell} ${changed ? c.cellChanged : ''}`}
    />
  );
}

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
  // The plant/unit/param the grid was loaded for. Save always writes there,
  // never to whatever the filters say now.
  const [loadedFor, setLoadedFor] = useState(null);

  // Units this plant actually has data for (from techno_data), keyed by
  // plant; falls back to the generic KNOWN_UNITS list until it loads or if
  // the request fails.
  const [unitsByPlant, setUnitsByPlant] = useState({});
  useEffect(() => {
    if (unitsByPlant[plant]) return;
    let cancelled = false;
    fetch(`${API}/api/techno/manual/units?plant=${encodeURIComponent(plant)}`)
      .then(r => (r.ok ? r.json() : null))
      .then(d => { if (!cancelled && d?.units) setUnitsByPlant(prev => ({ ...prev, [plant]: d.units })); })
      .catch(() => {});
    return () => { cancelled = true; };
  }, [plant, unitsByPlant]);

  const unitsFor = (p, a) => {
    const all = unitsByPlant[p] || KNOWN_UNITS;
    return sortUnitsInArea(a, all.filter(u => unitArea(u) === a));
  };
  const areaUnits = unitsFor(plant, area);
  // The chosen unit may not exist at a newly picked plant (e.g. BF-8 at
  // ISP); fall back to that plant's first unit in the area.
  const effectiveUnit = areaUnits.includes(unit) ? unit : (areaUnits[0] || '');
  const paramKeys = templateFor(area, plant, effectiveUnit);
  const effectiveParamKey = paramKeys.includes(paramKey) ? paramKey : (paramKeys[0] || '');

  // Any filter change invalidates the loaded grid, so edits can never be
  // saved against a different plant/unit/parameter than they were made for.
  function resetGrid() {
    setRows(null); setInitialRows(null); setLoadedFor(null); setNotice(null);
  }

  function handlePlantChange(newPlant) {
    setPlant(newPlant);
    resetGrid();
  }

  function handleAreaChange(newArea) {
    setArea(newArea);
    const units = unitsFor(plant, newArea);
    setUnit(units[0] || newArea);
    const params = templateFor(newArea, plant, units[0]);
    setParamKey(params[0] || '');
    resetGrid();
  }

  async function loadData() {
    setLoading(true); setNotice(null); setRows(null); setLoadedFor(null);
    try {
      const fromMonth = formatMonth(fromYear, fromMonthName);
      const toMonth   = formatMonth(toYear, toMonthName);
      const target = { plant, unit: effectiveUnit, paramKey: effectiveParamKey };
      const qs = new URLSearchParams({ plant, unit: effectiveUnit, param_key: effectiveParamKey, from_month: fromMonth, to_month: toMonth });
      const r = await fetch(`${API}/api/techno/manual/param-history?${qs}`);
      const d = await r.json();
      if (!r.ok) throw new Error(errText(d.detail, 'Failed to load data'));
      setRows(d.rows);
      setInitialRows(d.rows.map(x => ({ ...x })));
      setLoadedFor(target);
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
    if (!loadedFor) return;
    const { plant: savePlant, unit: saveUnit, paramKey: saveKey } = loadedFor;
    setSaving(true); setNotice(null);
    try {
      for (const r of changedMonths) {
        const init = initialRows.find(x => x.report_month === r.report_month);
        const month_data = {};
        const till_month_data = {};
        // A box cleared to empty is sent as an explicit delete — the save
        // endpoint otherwise treats a missing/null value as "untouched", so
        // the old figure would silently come back on the next load (same
        // fix as techno-manual's clearedKeys).
        const clear_month_keys = [];
        const clear_till_keys = [];
        if (r.month_value !== init.month_value) {
          if (r.month_value === null) clear_month_keys.push(saveKey);
          else month_data[saveKey] = r.month_value;
        }
        if (r.till_month_value !== init.till_month_value) {
          if (r.till_month_value === null) clear_till_keys.push(saveKey);
          else till_month_data[saveKey] = r.till_month_value;
        }

        const resp = await fetch(`${API}/api/techno/manual/save`, {
          method: 'POST', headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            plant: savePlant, report_month: r.report_month, unit: saveUnit,
            month_data, till_month_data, clear_month_keys, clear_till_keys,
          }),
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
    <EntryPage
      maxWidth={1100}
      title="Techno Data Correction"
      description={<>Find one parameter across a month range and correct it inline.</>}
    >

        {/* ── What to correct ── */}
        <div className={c.filters}>
          <div className={ui.field} style={{ marginBottom:0 }}>
            <label htmlFor="tc-plant" className={ui.label}>Plant</label>
            <select id="tc-plant" className="form-control" value={plant} onChange={e => handlePlantChange(e.target.value)}>
              {PLANTS.map(p => <option key={p}>{p}</option>)}
            </select>
          </div>
          <div className={ui.field} style={{ marginBottom:0 }}>
            <label htmlFor="tc-area" className={ui.label}>Area</label>
            <select id="tc-area" className="form-control" value={area} onChange={e => handleAreaChange(e.target.value)}>
              {AREA_ORDER.map(a => <option key={a}>{a}</option>)}
            </select>
          </div>
          <div className={ui.field} style={{ marginBottom:0 }}>
            <label htmlFor="tc-unit" className={ui.label}>Unit</label>
            <select id="tc-unit" className="form-control" value={effectiveUnit} onChange={e => { setUnit(e.target.value); resetGrid(); }}>
              {areaUnits.length === 0 && <option value="">— no {area} units for {plant} —</option>}
              {areaUnits.map(u => <option key={u}>{u}</option>)}
            </select>
          </div>
          <div className={ui.field} style={{ marginBottom:0, flex:'1 1 240px' }}>
            <label htmlFor="tc-param" className={ui.label}>Parameter</label>
            <select id="tc-param" className="form-control" value={effectiveParamKey} onChange={e => { setParamKey(e.target.value); resetGrid(); }}>
              {paramKeys.map(k => <option key={k} value={k}>{labelOf(k)}</option>)}
            </select>
          </div>
        </div>

        {/* ── Month range + actions ── */}
        <div className={c.filters}>
          <fieldset className={c.group} style={{ border:'none', margin:0, padding:0 }}>
            <legend className={ui.label}>From</legend>
            <label htmlFor="tc-from-month" className={ui.srOnly}>From month</label>
            <select id="tc-from-month" className="form-control" value={fromMonthName} onChange={e => setFromMonthName(e.target.value)}>
              {MONTHS.map(mo => <option key={mo}>{mo}</option>)}
            </select>
            <label htmlFor="tc-from-year" className={ui.srOnly}>From year</label>
            <select id="tc-from-year" className="form-control" value={fromYear} onChange={e => setFromYear(e.target.value)}>
              {YEARS.map(y => <option key={y}>{y}</option>)}
            </select>
          </fieldset>
          <fieldset className={c.group} style={{ border:'none', margin:0, padding:0 }}>
            <legend className={ui.label}>To</legend>
            <label htmlFor="tc-to-month" className={ui.srOnly}>To month</label>
            <select id="tc-to-month" className="form-control" value={toMonthName} onChange={e => setToMonthName(e.target.value)}>
              {MONTHS.map(mo => <option key={mo}>{mo}</option>)}
            </select>
            <label htmlFor="tc-to-year" className={ui.srOnly}>To year</label>
            <select id="tc-to-year" className="form-control" value={toYear} onChange={e => setToYear(e.target.value)}>
              {YEARS.map(y => <option key={y}>{y}</option>)}
            </select>
          </fieldset>

          <button type="button" onClick={loadData} disabled={loading} aria-busy={loading}
                  className={`${ui.btn} ${ui.btnSecondary}`}>
            {loading ? 'Loading…' : 'Load'}
          </button>

          <span className={c.spacer} />
          {changedMonths.length > 0 && (
            <button type="button" onClick={saveChanges} disabled={saving} aria-busy={saving}
                    className={`${ui.btn} ${ui.btnPrimary}`}>
              {saving ? 'Saving…' : `Save Changes (${changedMonths.length})`}
            </button>
          )}
        </div>

        {notice && <Notice type={notice.type} text={notice.text} onClose={() => setNotice(null)} />}

        {rows && loadedFor && (
          <p className={c.target} aria-live="polite">
            <strong>{loadedFor.plant} › {loadedFor.unit} › {labelOf(loadedFor.paramKey)}</strong>
            {' '}· {rows.length} month{rows.length === 1 ? '' : 's'}
            {changedMonths.length > 0 && ` · ${changedMonths.length} unsaved`}
          </p>
        )}

        {rows && rows.length > 0 && (
          <div className={ui.tableWrap}>
            <table className={ui.table}>
              <thead>
                <tr>
                  <th scope="col">Report Month</th>
                  <th scope="col" className={ui.numeric}>Month Value</th>
                  <th scope="col" className={ui.numeric}>Till Month Value</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((r, i) => {
                  const init = initialRows[i];
                  const mLabel = monthLabel(r.report_month);
                  const dp = DISPLAY_DP[loadedFor?.paramKey];
                  return (
                    <tr key={r.report_month}>
                      <th scope="row" className={c.monthCell}>{mLabel}</th>
                      <td>
                        <NumInput
                          value={r.month_value}
                          dp={dp}
                          label={`${mLabel}, month value`}
                          changed={r.month_value !== init.month_value}
                          onChange={v => updateCell(r.report_month, 'month_value', v)}
                        />
                      </td>
                      <td>
                        <NumInput
                          value={r.till_month_value}
                          dp={dp}
                          label={`${mLabel}, till month value`}
                          changed={r.till_month_value !== init.till_month_value}
                          onChange={v => updateCell(r.report_month, 'till_month_value', v)}
                        />
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}

        {rows && rows.length === 0 && (
          <p className={ui.meta}>No months in the selected range.</p>
        )}

        <p className={ui.hint} style={{ marginTop:14 }}>
          Changed boxes are highlighted until saved. Clearing a box and saving removes that value.
        </p>
    </EntryPage>
  );
}

export default function TechnoCorrectionPage() {
  return (
    <RequireEditor>
      <TechnoCorrectionInner />
    </RequireEditor>
  );
}
