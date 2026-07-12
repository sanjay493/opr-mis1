'use client';

import React, { useState, useCallback, useEffect, useMemo } from 'react';
import GlobalNavbar from '@/components/GlobalNavbar';
import BSLBFTechnoExtractor from '@/components/BSLBFTechnoExtractor';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://127.0.0.1:8082';

const PLANTS = ['BSP', 'DSP', 'RSP', 'BSL', 'ISP'];

const MONTHS = [
  'April', 'May', 'June', 'July', 'August', 'September',
  'October', 'November', 'December', 'January', 'February', 'March',
];
const MONTH_NUM = {
  January: '01', February: '02', March: '03', April: '04',
  May: '05', June: '06', July: '07', August: '08',
  September: '09', October: '10', November: '11', December: '12',
};
const YEARS = Array.from({ length: 8 }, (_, i) => (2022 + i).toString());

function getDefaultPeriod() {
  const d = new Date();
  d.setMonth(d.getMonth() - 1);
  return { month: MONTHS[d.getMonth()], year: d.getFullYear().toString() };
}

function formatMonth(year, month) {
  return `${year}-${MONTH_NUM[month]}`;
}

// ── Shared styled status message ──────────────────────────────────────────────
function StatusMsg({ status }) {
  if (!status) return null;
  const palette = {
    success: { bg: '#f0fdf4', fg: '#166534', border: '#86efac' },
    info:    { bg: '#eff6ff', fg: '#174ea6', border: '#bfdbfe' },
    error:   { bg: '#fef2f2', fg: '#991b1b', border: '#fca5a5' },
  }[status.type] || { bg: '#fef2f2', fg: '#991b1b', border: '#fca5a5' };
  return (
    <div style={{
      padding: '8px 14px', borderRadius: 6, marginBottom: 14, fontSize: 13,
      background: palette.bg, color: palette.fg, border: `1px solid ${palette.border}`,
    }}>
      {status.text}
    </div>
  );
}

// ── Bulk "Calculate Cumulative" step window — shows the full working (method,
// production weights from production_table, month-by-month rows, formula)
// for every parameter of every unit BEFORE anything is written to the DB. ────
function BulkCumulativeModal({ preview, onConfirm, onClose, busy, confirmLabel, noteText }) {
  const [expanded, setExpanded] = React.useState(null);
  if (!preview) return null;

  const methodLabel = {
    weighted_average: 'Production-weighted average',
    harmonic_mean:    'Production-weighted harmonic mean',
    simple_average:   'Simple average',
    sum:              'Sum of monthly values',
  };
  const fmt = v => (v == null ? '—' : Number(v).toLocaleString(undefined, { maximumFractionDigits: 4 }));
  const changed = (a, b) => a != null && b != null && Number(a) !== Number(b);

  const byUnit = {};
  for (const d of preview.details) (byUnit[d.unit] = byUnit[d.unit] || []).push(d);
  const units = Object.keys(byUnit);

  const th = { padding: '5px 10px', textAlign: 'left', color: '#5f6368', fontWeight: 600, fontSize: 12, borderBottom: '1px solid #dadce0' };
  const thR = { ...th, textAlign: 'right' };

  return (
    <div style={{
      position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.45)', zIndex: 300,
      display: 'flex', alignItems: 'center', justifyContent: 'center',
    }}>
      <div style={{
        background: '#fff', borderRadius: 10, padding: 24, width: 780, maxWidth: '94vw',
        maxHeight: '88vh', overflowY: 'auto', boxShadow: '0 8px 32px rgba(0,0,0,0.2)',
      }}>
        <h3 style={{ margin: '0 0 4px', fontSize: 18, color: '#202124' }}>
          Cumulative Calculation — {preview.plant} · April → {preview.report_month}
        </h3>
        <div style={{ fontSize: 13, color: '#5f6368', marginBottom: 14 }}>
          {preview.details.length} parameter{preview.details.length === 1 ? '' : 's'} across {units.length} unit{units.length === 1 ? '' : 's'}.
          Furnace-wise and BF_Shop production, and SMS-wise crude steel, are read from production_table for the weighting shown below.
          {' '}{noteText || 'Nothing is saved yet — review each calculation, then confirm.'}
        </div>

        {(preview.warnings || []).map((w, i) => (
          <div key={i} style={{ fontSize: 12.5, color: '#991b1b', background: '#fef2f2', border: '1px solid #fca5a5', borderRadius: 5, padding: '5px 10px', marginBottom: 6 }}>
            {w}
          </div>
        ))}

        {units.map(u => (
          <div key={u} style={{ marginBottom: 14, border: '1px solid #dadce0', borderRadius: 8, overflow: 'hidden' }}>
            <div style={{ padding: '8px 12px', background: '#f8f9fa', fontWeight: 700, fontSize: 13, color: '#174ea6', borderBottom: '1px solid #dadce0' }}>
              {u}
            </div>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12.5 }}>
              <thead>
                <tr>
                  <th style={th}>Parameter</th>
                  <th style={th}>Method</th>
                  <th style={thR}>Previous Cumulative</th>
                  <th style={thR}>New Cumulative</th>
                  <th style={th}></th>
                </tr>
              </thead>
              <tbody>
                {byUnit[u].map(d => {
                  const key = `${d.unit}::${d.param_key}`;
                  const isOpen = expanded === key;
                  const isChanged = changed(d.previous_till_month, d.result);
                  return (
                    <React.Fragment key={key}>
                      <tr style={{ borderTop: '1px solid #f1f3f4' }}>
                        <td style={{ padding: '5px 10px', color: '#202124' }}>
                          {d.param_key}
                          {d.warnings.length > 0 && (
                            <span title={d.warnings.join(' ')} style={{ color: '#b45309', marginLeft: 5, cursor: 'help' }}>⚠</span>
                          )}
                        </td>
                        <td style={{ padding: '5px 10px', color: '#5f6368' }}>{methodLabel[d.method] || d.method}</td>
                        <td style={{ padding: '5px 10px', textAlign: 'right', fontFamily: 'monospace', color: '#5f6368' }}>{fmt(d.previous_till_month)}</td>
                        <td style={{
                          padding: '5px 10px', textAlign: 'right', fontFamily: 'monospace',
                          fontWeight: isChanged ? 700 : 400, color: isChanged ? '#b06000' : '#166534',
                        }}>
                          {fmt(d.result)}
                        </td>
                        <td style={{ padding: '5px 10px', textAlign: 'right' }}>
                          <button onClick={() => setExpanded(isOpen ? null : key)} style={{
                            fontSize: 11, padding: '2px 9px', border: '1px solid #dadce0',
                            borderRadius: 4, background: '#fff', cursor: 'pointer', color: '#5f6368',
                          }}>
                            {isOpen ? 'Hide' : 'Steps'}
                          </button>
                        </td>
                      </tr>
                      {isOpen && (
                        <tr>
                          <td colSpan={5} style={{ padding: '10px 14px', background: '#f8f9fa', borderTop: '1px solid #f1f3f4' }}>
                            {d.weight_item && (
                              <div style={{ fontSize: 12, color: '#5f6368', marginBottom: 8 }}>Weights: {d.weight_item}</div>
                            )}
                            {d.rows.length > 0 && (
                              <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12, marginBottom: 8, background: '#fff' }}>
                                <thead>
                                  <tr>
                                    <th style={th}>Month</th>
                                    <th style={thR}>Value</th>
                                    <th style={thR}>Weight (production)</th>
                                    <th style={thR}>Product</th>
                                  </tr>
                                </thead>
                                <tbody>
                                  {d.rows.map(r => (
                                    <tr key={r.month}>
                                      <td style={{ padding: '3px 10px' }}>{r.month}</td>
                                      <td style={{ padding: '3px 10px', textAlign: 'right', fontFamily: 'monospace' }}>{fmt(r.value)}</td>
                                      <td style={{ padding: '3px 10px', textAlign: 'right', fontFamily: 'monospace', color: r.weight == null ? '#dc2626' : '#202124' }}>
                                        {r.weight == null ? 'missing' : fmt(r.weight)}
                                      </td>
                                      <td style={{ padding: '3px 10px', textAlign: 'right', fontFamily: 'monospace' }}>{r.product != null ? fmt(r.product) : '—'}</td>
                                    </tr>
                                  ))}
                                </tbody>
                              </table>
                            )}
                            <div style={{ fontFamily: 'Consolas, monospace', fontSize: 12, color: '#202124' }}>
                              {d.steps.map((s, i) => <div key={i} style={{ padding: '1px 0' }}>{i + 1}. {s}</div>)}
                            </div>
                          </td>
                        </tr>
                      )}
                    </React.Fragment>
                  );
                })}
              </tbody>
            </table>
          </div>
        ))}

        <div style={{
          display: 'flex', gap: 10, marginTop: 8, position: 'sticky', bottom: -24,
          background: '#fff', padding: '10px 0 0', borderTop: '1px solid #dadce0',
        }}>
          <button onClick={onClose} disabled={busy} style={{
            padding: '8px 18px', fontSize: 14, background: '#f8f9fa',
            border: '1px solid #dadce0', borderRadius: 5, cursor: busy ? 'not-allowed' : 'pointer',
          }}>
            Cancel
          </button>
          <button onClick={onConfirm} disabled={busy} style={{
            marginLeft: 'auto', padding: '8px 18px', fontSize: 14, fontWeight: 700,
            background: busy ? '#5f6368' : '#16a34a', color: '#fff', border: 'none',
            borderRadius: 5, cursor: busy ? 'not-allowed' : 'pointer',
          }}>
            {busy ? 'Working…' : (confirmLabel || `Confirm & Save (${preview.details.length} parameters)`)}
          </button>
        </div>
      </div>
    </div>
  );
}

// Default checked = true, EXCEPT auto-unchecked ("kept existing — extracted
// was blank") when the extracted month value is null/blank and the DB
// already has a non-null value for that parameter — the auto-protect
// default agreed for this feature. One checkbox per parameter governs both
// its month and till_month (cumulative) value together.
function computeParamDefaults(records) {
  const checked = {};
  const autoProtected = {};
  for (const rec of records || []) {
    const monthData = rec.techno_json?.month || {};
    const dbMonth = rec.db_json?.month || {};
    const allParams = new Set([...Object.keys(monthData), ...Object.keys(dbMonth)]);
    // Two sheets can legitimately share a unit name (e.g. ISP's B-FCE and
    // Maj Techno Summ both write "General" for different, non-overlapping
    // parameters) — start from whatever's already accumulated for this unit
    // instead of a fresh object, so a second record for the same unit adds
    // to it rather than wiping out the first one's params.
    const checkedUnit = checked[rec.unit] || {};
    const autoUnit = autoProtected[rec.unit] || {};
    allParams.forEach((p) => {
      const extracted = monthData[p];
      const dbVal = dbMonth[p];
      const blank = extracted == null || extracted === '';
      const dbHasValue = dbVal != null && dbVal !== '';
      const protect = blank && dbHasValue;
      checkedUnit[p] = !protect;
      autoUnit[p] = protect;
    });
    checked[rec.unit] = checkedUnit;
    autoProtected[rec.unit] = autoUnit;
  }
  return { checked, autoProtected };
}

// ── Compact review table shown between Preview and Confirm & Save ─────────────
function PreviewReview({ preview, paramChecked, autoProtected, onToggleParam }) {
  // Two sheets can legitimately share a unit name (e.g. ISP's B-FCE and Maj
  // Techno Summ both write "General" for different, non-overlapping
  // parameters) — the sidebar tab list must be de-duplicated by unit (React
  // needs unique keys, and each unit should appear once), and every record
  // sharing the active unit gets merged together so the preview shows the
  // union of both sources' parameters, matching what the merge-safe save
  // will actually store.
  const uniqueUnits = Array.from(new Set(preview.records.map(r => r.unit)));
  const [activeUnit, setActiveUnit] = React.useState(uniqueUnits[0] || null);
  const activeRecords = preview.records.filter(r => r.unit === activeUnit);
  const mergeOf = (source, period) => Object.assign(
    {}, ...activeRecords.map(r => (source === 'db' ? r.db_json : r.techno_json)?.[period] || {})
  );
  const monthParams = mergeOf('techno', 'month');
  const tillParams  = mergeOf('techno', 'till_month');
  const dbMonthParams = mergeOf('db', 'month');
  const dbTillParams  = mergeOf('db', 'till_month');
  const allParams = Array.from(new Set([...Object.keys(monthParams), ...Object.keys(dbMonthParams), ...Object.keys(dbTillParams)]));
  const unitChecked = paramChecked[activeUnit] || {};
  const unitAutoProtected = autoProtected[activeUnit] || {};
  const fmt = v => {
    if (v == null || v === '') return '—';
    if (typeof v === 'string' && v.includes(':')) return v;
    return Number(v).toLocaleString(undefined, { maximumFractionDigits: 3 });
  };
  const changed = (a, b) => a != null && b != null && Number(a) !== Number(b);

  return (
    <div style={{ marginTop: 8, border: '1px solid #bfdbfe', borderRadius: 7, background: '#eff6ff', overflow: 'hidden' }}>
      <div style={{ padding: '8px 12px', fontSize: 12.5, fontWeight: 600, color: '#174ea6', borderBottom: '1px solid #bfdbfe' }}>
        Preview — {preview.units_extracted} unit{preview.units_extracted === 1 ? '' : 's'}, {preview.total_params} parameter{preview.total_params === 1 ? '' : 's'} for {preview.report_month}. Nothing saved yet.
      </div>
      <div style={{ display: 'flex', maxHeight: 260 }}>
        <div style={{ width: 140, flexShrink: 0, borderRight: '1px solid #bfdbfe', overflowY: 'auto', background: '#fff' }}>
          {uniqueUnits.map(unit => (
            <button key={unit} onClick={() => setActiveUnit(unit)}
              style={{
                display: 'block', width: '100%', padding: '6px 10px', textAlign: 'left',
                background: activeUnit === unit ? '#e8f0fe' : 'transparent',
                color: activeUnit === unit ? '#174ea6' : '#5f6368',
                border: 'none', borderBottom: '1px solid #f8f9fa', fontSize: 12,
                fontWeight: activeUnit === unit ? 700 : 400, cursor: 'pointer',
              }}
            >
              {unit}
            </button>
          ))}
        </div>
        <div style={{ flex: 1, overflowY: 'auto', background: '#fff' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12.5 }}>
            <thead>
              <tr style={{ background: '#f8f9fa' }}>
                <th rowSpan={2} style={{ padding: '5px 8px', textAlign: 'center', color: '#5f6368', borderBottom: '1px solid #dadce0', verticalAlign: 'bottom' }}>Insert</th>
                <th rowSpan={2} style={{ padding: '5px 10px', textAlign: 'left', color: '#5f6368', borderBottom: '1px solid #dadce0', verticalAlign: 'bottom' }}>Parameter</th>
                <th colSpan={2} style={{ padding: '4px 10px', textAlign: 'center', color: '#5f6368', borderBottom: '1px solid #f1f3f4', fontWeight: 600 }}>Month</th>
                <th colSpan={2} style={{ padding: '4px 10px', textAlign: 'center', color: '#5f6368', borderBottom: '1px solid #f1f3f4', fontWeight: 600 }}>Cumulative</th>
              </tr>
              <tr style={{ background: '#f8f9fa' }}>
                <th style={{ padding: '4px 10px', textAlign: 'right', color: '#5f6368', borderBottom: '1px solid #dadce0', fontWeight: 500 }}>In DB</th>
                <th style={{ padding: '4px 10px', textAlign: 'right', color: '#1a73e8', borderBottom: '1px solid #dadce0', fontWeight: 600 }}>Extracted</th>
                <th style={{ padding: '4px 10px', textAlign: 'right', color: '#5f6368', borderBottom: '1px solid #dadce0', fontWeight: 500 }}>In DB</th>
                <th style={{ padding: '4px 10px', textAlign: 'right', color: '#1a73e8', borderBottom: '1px solid #dadce0', fontWeight: 600 }}>Extracted</th>
              </tr>
            </thead>
            <tbody>
              {allParams.map((param, idx) => {
                const dbM = dbMonthParams[param], newM = monthParams[param];
                const dbT = dbTillParams[param],  newT = tillParams[param];
                const isChecked = unitChecked[param] !== false;
                const isAutoProtected = !!unitAutoProtected[param];
                return (
                  <tr key={param} style={{ background: idx % 2 === 0 ? '#fff' : '#f8f9fa', opacity: isChecked ? 1 : 0.6 }}>
                    <td style={{ padding: '4px 8px', textAlign: 'center' }}>
                      <input type="checkbox" checked={isChecked}
                             onChange={(e) => onToggleParam(activeUnit, param, e.target.checked)}
                             title={isAutoProtected ? 'Extracted value was blank — unchecked to keep the existing DB value' : 'Include this parameter in the save'}
                             style={{ accentColor: '#10b981', cursor: 'pointer' }} />
                    </td>
                    <td style={{ padding: '4px 10px', color: '#202124' }}>
                      {param}
                      {isAutoProtected && (
                        <div style={{ fontSize: 10, color: '#92400e', fontStyle: 'italic' }}>kept existing — extracted was blank</div>
                      )}
                    </td>
                    <td style={{ padding: '4px 10px', textAlign: 'right', fontFamily: 'monospace', color: '#5f6368' }}>{fmt(dbM)}</td>
                    <td style={{ padding: '4px 10px', textAlign: 'right', fontFamily: 'monospace', color: changed(dbM, newM) ? '#b06000' : '#1a73e8', fontWeight: changed(dbM, newM) ? 700 : 400 }}>{fmt(newM)}</td>
                    <td style={{ padding: '4px 10px', textAlign: 'right', fontFamily: 'monospace', color: '#5f6368' }}>{fmt(dbT)}</td>
                    <td style={{ padding: '4px 10px', textAlign: 'right', fontFamily: 'monospace', color: changed(dbT, newT) ? '#b06000' : '#1a73e8', fontWeight: changed(dbT, newT) ? 700 : 400 }}>{fmt(newT)}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>
      <div style={{ padding: '6px 12px', fontSize: 11, color: '#5f6368', borderTop: '1px solid #bfdbfe' }}>
        <span style={{ color: '#b06000', fontWeight: 700 }}>Amber</span> = extracted value differs from what's currently in the DB.
        Unchecked rows are skipped on save and keep their current DB value — rows where the
        extraction came back blank are unchecked automatically so a bad file can't wipe out a good value; uncheck any other row yourself to keep the DB value instead.
      </div>
    </div>
  );
}

// ── Single file-upload row used for each file type ────────────────────────────
function ExtractRow({ label, previewEndpoint, insertEndpoint, cumulativeEndpoint, reportMonth, apiBase, onSuccess, plant, accent = '#e8f0fe', accept = '.xlsx,.xls' }) {
  const [file, setFile] = React.useState(null);
  const [busy,  setBusy]  = React.useState(false);
  const [status, setStatus] = React.useState(null);
  const [preview, setPreview] = React.useState(null);
  const [cumPreview, setCumPreview] = React.useState(null);
  const [paramChecked, setParamChecked] = React.useState({});
  const [autoProtected, setAutoProtected] = React.useState({});
  const inputRef = React.useRef();

  React.useEffect(() => {
    setFile(null);
    setStatus(null);
    setPreview(null);
    if (inputRef.current) inputRef.current.value = '';
  }, [reportMonth]);

  const toggleParam = (unit, param, checked) => {
    setParamChecked(prev => ({ ...prev, [unit]: { ...(prev[unit] || {}), [param]: checked } }));
  };

  const handlePreview = async () => {
    if (!file) return;
    setBusy(true);
    setStatus(null);
    setPreview(null);
    const form = new FormData();
    form.append('file', file);
    form.append('report_month', reportMonth);
    if (plant) form.append('plant', plant);
    try {
      const res = await fetch(`${apiBase}${previewEndpoint}`, { method: 'POST', body: form });
      const json = await res.json();
      if (!res.ok) throw new Error(json.detail || 'Preview failed');
      setPreview(json);
      const { checked, autoProtected: auto } = computeParamDefaults(json.records || []);
      setParamChecked(checked);
      setAutoProtected(auto);
    } catch (err) {
      setStatus({ type: 'error', text: err.message });
    } finally {
      setBusy(false);
    }
  };

  // Computes the Cumulative for every parameter and opens the calculation-
  // step window (method, production weights, month-by-month working) —
  // nothing is applied to the preview below until the user confirms.
  const handleCalcCumulative = async () => {
    if (!preview) return;
    setBusy(true);
    setStatus(null);
    try {
      const res = await fetch(`${apiBase}${cumulativeEndpoint}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          plant,
          report_month: preview.report_month,
          records: preview.records,
        }),
      });
      const json = await res.json();
      if (!res.ok) throw new Error(json.detail || 'Cumulative calculation failed');
      if (!json.details || json.details.length === 0) {
        setStatus({ type: 'info', text: 'Nothing to calculate — no monthly values to compute a cumulative from.' });
        return;
      }
      setCumPreview({ ...json, plant, report_month: preview.report_month });
    } catch (err) {
      setStatus({ type: 'error', text: err.message });
    } finally {
      setBusy(false);
    }
  };

  // Applies the reviewed Cumulative values into the preview's records
  // (still not saved to the DB — that only happens via Confirm & Save below).
  const handleApplyCumulative = () => {
    if (!cumPreview) return;
    setPreview(prev => ({ ...prev, records: cumPreview.records }));
    const { checked, autoProtected: auto } = computeParamDefaults(cumPreview.records || []);
    setParamChecked(checked);
    setAutoProtected(auto);
    const warn = (cumPreview.warnings || []).length;
    setStatus({
      type: 'success',
      text: `Cumulative applied for ${cumPreview.computed} parameter${cumPreview.computed === 1 ? '' : 's'}`
        + (warn ? ` — ${warn} skipped (e.g. ${cumPreview.warnings[0]})` : ''),
    });
    setCumPreview(null);
  };

  const handleConfirmSave = async () => {
    if (!preview) return;
    setBusy(true);
    setStatus(null);
    try {
      // Drop unchecked params from each record before saving — the backend's
      // merge-safe upsert (merge_upsert_techno_data) keeps the existing DB
      // value for any parameter omitted here, so unchecking a row never
      // clobbers a good stored value with a blank/unwanted extracted one.
      const recordsToSave = preview.records.map(rec => {
        const unitChecked = paramChecked[rec.unit] || {};
        const keep = (obj) => Object.fromEntries(
          Object.entries(obj || {}).filter(([p]) => unitChecked[p] !== false)
        );
        return {
          unit: rec.unit,
          techno_json: {
            month: keep(rec.techno_json?.month),
            till_month: keep(rec.techno_json?.till_month),
          },
        };
      });
      const doInsert = confirmReplace => fetch(`${apiBase}${insertEndpoint}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          plant,
          report_month: preview.report_month,
          source_file: preview.source_file,
          records: recordsToSave,
          ...(confirmReplace ? { confirm_replace: true } : {}),
        }),
      });
      let res = await doInsert(false);
      let json = await res.json();
      if (res.status === 409) {
        // Existing data would be replaced — ask for user consent, then retry
        if (!window.confirm(`${json.detail}\n\nReplace the existing values?`)) {
          setBusy(false);
          return;
        }
        res = await doInsert(true);
        json = await res.json();
      }
      if (!res.ok) throw new Error(json.detail || 'Save failed');
      setStatus({ type: 'success', text: `Saved ${json.units_saved} units for ${preview.report_month}` });
      setPreview(null);
      setFile(null);
      if (inputRef.current) inputRef.current.value = '';
      onSuccess();
    } catch (err) {
      setStatus({ type: 'error', text: err.message });
    } finally {
      setBusy(false);
    }
  };

  const handleCancelPreview = () => {
    setPreview(null);
    setStatus(null);
  };

  return (
    <div style={{ marginBottom: 10 }}>
      <div style={{
        display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap',
        padding: '10px 14px', background: '#f8f9fa', border: '1px solid #dadce0', borderRadius: 7,
      }}>
        <span style={{ fontSize: 13, color: '#5f6368', minWidth: 180, fontWeight: 600 }}>{label}</span>
        <input ref={inputRef} type="file" accept={accept}
          onChange={e => { setFile(e.target.files[0]); setStatus(null); setPreview(null); }}
          style={{ fontSize: 13, flex: 1 }}
          suppressHydrationWarning
        />
        {!preview && (
          <button onClick={handlePreview} disabled={!file || busy}
            style={{
              padding: '7px 18px', background: busy ? '#5f6368' : accent,
              color: '#fff', border: 'none', borderRadius: 6, fontSize: 13,
              cursor: file && !busy ? 'pointer' : 'not-allowed', fontWeight: 600, whiteSpace: 'nowrap',
            }}
          >
            {busy ? 'Extracting…' : 'Preview'}
          </button>
        )}
        {preview && (
          <>
            {cumulativeEndpoint && (
              <button onClick={handleCalcCumulative} disabled={busy}
                style={{
                  padding: '7px 14px', background: busy ? '#5f6368' : '#1a73e8',
                  color: '#fff', border: 'none', borderRadius: 6, fontSize: 13,
                  cursor: busy ? 'not-allowed' : 'pointer', fontWeight: 600, whiteSpace: 'nowrap',
                }}
              >
                {busy ? 'Working…' : 'Calc Cumulative'}
              </button>
            )}
            <button onClick={handleConfirmSave} disabled={busy}
              style={{
                padding: '7px 18px', background: busy ? '#5f6368' : '#16a34a',
                color: '#fff', border: 'none', borderRadius: 6, fontSize: 13,
                cursor: busy ? 'not-allowed' : 'pointer', fontWeight: 600, whiteSpace: 'nowrap',
              }}
            >
              {busy ? 'Saving…' : 'Confirm & Save'}
            </button>
            <button onClick={handleCancelPreview} disabled={busy}
              style={{
                padding: '7px 14px', background: '#fff', color: '#5f6368',
                border: '1px solid #dadce0', borderRadius: 6, fontSize: 13,
                cursor: busy ? 'not-allowed' : 'pointer', fontWeight: 600, whiteSpace: 'nowrap',
              }}
            >
              Cancel
            </button>
          </>
        )}
      </div>
      {preview && (preview.warnings || []).length > 0 && (
        <div style={{
          marginTop: 6, padding: '6px 12px', borderRadius: 6, fontSize: 12,
          background: '#fffbeb', color: '#92400e', border: '1px solid #fde68a',
        }}>
          {preview.warnings.map((w, i) => <div key={i}>⚠ {w}</div>)}
        </div>
      )}
      {preview && (
        <PreviewReview preview={preview} paramChecked={paramChecked}
                       autoProtected={autoProtected} onToggleParam={toggleParam} />
      )}
      <StatusMsg status={status} />

      <BulkCumulativeModal
        preview={cumPreview}
        busy={false}
        onConfirm={handleApplyCumulative}
        onClose={() => setCumPreview(null)}
        confirmLabel={cumPreview ? `Apply to preview (${cumPreview.details.length} parameters)` : ''}
        noteText="Nothing is saved to the database yet — this only fills the Cumulative column in the preview below; you still need to review and click Confirm & Save to write it."
      />
    </div>
  );
}

// ── Techno Data Panel — works for all 5 plants ───────────────────────────────
function TechnoDataPanel({ plant, reportMonth, apiBase }) {
  const [data, setData] = React.useState({});
  const [activeUnit, setActiveUnit] = React.useState(null);
  const [loading, setLoading] = React.useState(false);
  const [cumBusy, setCumBusy] = React.useState(false);
  const [cumStatus, setCumStatus] = React.useState(null);
  const [cumPreviewAll, setCumPreviewAll] = React.useState(null);
  const [cumConfirmBusy, setCumConfirmBusy] = React.useState(false);

  const loadData = React.useCallback(async () => {
    setLoading(true);
    try {
      const res = await fetch(
        `${apiBase}/api/techno/data?plant=${plant}&report_month=${reportMonth}`
      );
      if (res.ok) {
        const json = await res.json();
        const d = json.data || {};
        setData(d);
        const units = Object.keys(d);
        setActiveUnit(prev => (units.includes(prev) ? prev : units[0] || null));
      } else {
        setData({});
        setActiveUnit(null);
      }
    } catch {
      setData({});
      setActiveUnit(null);
    } finally {
      setLoading(false);
    }
  }, [plant, reportMonth, apiBase]);

  useEffect(() => { loadData(); }, [loadData]);

  // Bulk cumulative — same rules engine as techno-manual's per-field
  // "Calculate Cumulative", applied to every saved parameter of every unit.
  // Step 1: compute-only (preview=true, nothing written) and show the full
  // calculation-step window; Step 2: user reviews and clicks "Confirm & Save"
  // (handleConfirmCumulativeAll) before anything is written to the DB.
  const handleCumulativeAll = async () => {
    setCumBusy(true);
    setCumStatus(null);
    try {
      const res = await fetch(`${apiBase}/api/mcr-techno/cumulative-all`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ plant, report_month: reportMonth, overwrite: true, preview: true }),
      });
      const json = await res.json();
      if (!res.ok) throw new Error(json.detail || 'Cumulative calculation failed');
      if (!json.details || json.details.length === 0) {
        setCumStatus({
          type: 'info', plant, reportMonth,
          text: 'Nothing to calculate — no monthly values found for this plant/month.',
        });
        return;
      }
      setCumPreviewAll({ ...json, plant, report_month: reportMonth });
    } catch (err) {
      setCumStatus({ type: 'error', plant, reportMonth, text: err.message });
    } finally {
      setCumBusy(false);
    }
  };

  const handleConfirmCumulativeAll = async () => {
    if (!cumPreviewAll) return;
    setCumConfirmBusy(true);
    try {
      const res = await fetch(`${apiBase}/api/mcr-techno/cumulative-all`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ plant, report_month: reportMonth, overwrite: true, preview: false }),
      });
      const json = await res.json();
      if (!res.ok) throw new Error(json.detail || 'Cumulative save failed');
      const warn = (json.warnings || []).length;
      setCumStatus({
        type: 'success', plant, reportMonth,
        text: `Cumulative saved for ${json.computed} parameter${json.computed === 1 ? '' : 's'} `
          + `across ${json.units.length} unit${json.units.length === 1 ? '' : 's'}`
          + (warn ? ` — ${warn} skipped (e.g. ${json.warnings[0]})` : ''),
      });
      setCumPreviewAll(null);
      loadData();
    } catch (err) {
      setCumStatus({ type: 'error', plant, reportMonth, text: err.message });
    } finally {
      setCumConfirmBusy(false);
    }
  };
  // Only show the status for the plant/month it was produced for
  const cumStatusShown = cumStatus && cumStatus.plant === plant && cumStatus.reportMonth === reportMonth
    ? cumStatus : null;

  const units = Object.keys(data);
  const unitData = activeUnit ? data[activeUnit] : null;
  const monthParams = unitData?.month || {};
  const tillParams = unitData?.till_month || {};
  const isRsp = plant === 'RSP';
  const isBsp = plant === 'BSP';
  const isIsp = plant === 'ISP';
  const isDsp = plant === 'DSP';
  const isBsl = plant === 'BSL';
  const hasExtraction = isRsp || isBsp || isIsp || isDsp || isBsl;

  return (
    <div>
      {/* RSP: Technopara Excel (final) + month-end Morning Report (tentative) */}
      {isRsp && (
        <div style={{
          marginBottom: 16, padding: '12px 14px',
          background: '#eff6ff', border: '1px solid #bfdbfe', borderRadius: 8,
        }}>
          <div style={{ fontSize: 14, fontWeight: 700, color: '#174ea6', marginBottom: 10 }}>
            RSP Techno Upload — Technopara Excel (final) and/or Month-End Morning Report (tentative, merged into the same table)
          </div>
          <ExtractRow
            label="RSP Technopara Excel (page1-8 sheet)"
            previewEndpoint="/api/techno/preview"
            insertEndpoint="/api/techno/insert"
            plant="RSP"
            reportMonth={reportMonth}
            apiBase={apiBase}
            onSuccess={loadData}
            accent="#1a73e8"
          />
          <ExtractRow
            label="RSP Morning Report — month-end (tentative)"
            previewEndpoint="/api/mcr-techno/preview"
            insertEndpoint="/api/mcr-techno/insert"
            cumulativeEndpoint="/api/mcr-techno/cumulative"
            plant="RSP"
            reportMonth={reportMonth}
            apiBase={apiBase}
            onSuccess={loadData}
            accent="#174ea6"
          />
        </div>
      )}

      {/* BSP: two file extract bars (3-page-tech + OISCO) */}
      {isBsp && (
        <div style={{
          marginBottom: 16, padding: '12px 14px',
          background: '#fff7ed', border: '1px solid #fed7aa', borderRadius: 8,
        }}>
          <div style={{ fontSize: 14, fontWeight: 700, color: '#92400e', marginBottom: 10 }}>
            BSP Techno Upload — all files contribute data for the same month (merged automatically). The month-end row accepts MIS-2 or PPC MIS (auto-detected, tentative data).
          </div>
          <ExtractRow
            label="BSP Flash Monthly PDF (flash-<mon>YY.pdf)"
            previewEndpoint="/api/bsp-techno/preview/flash-pdf"
            insertEndpoint="/api/bsp-techno/insert"
            plant="BSP"
            reportMonth={reportMonth}
            apiBase={apiBase}
            onSuccess={loadData}
            accent="#7c2d12"
            accept=".pdf"
          />
          <ExtractRow
            label="BSP-3-page-Tech.xlsx"
            previewEndpoint="/api/bsp-techno/preview/techno"
            insertEndpoint="/api/bsp-techno/insert"
            plant="BSP"
            reportMonth={reportMonth}
            apiBase={apiBase}
            onSuccess={loadData}
            accent="#92400e"
          />
          <ExtractRow
            label="OISCO Excel"
            previewEndpoint="/api/bsp-techno/preview/oisco"
            insertEndpoint="/api/bsp-techno/insert"
            plant="BSP"
            reportMonth={reportMonth}
            apiBase={apiBase}
            onSuccess={loadData}
            accent="#b45309"
          />
          <ExtractRow
            label="Month-End Excel — MIS-2 or PPC MIS (tentative)"
            previewEndpoint="/api/mcr-techno/preview"
            insertEndpoint="/api/mcr-techno/insert"
            cumulativeEndpoint="/api/mcr-techno/cumulative"
            plant="BSP"
            reportMonth={reportMonth}
            apiBase={apiBase}
            onSuccess={loadData}
            accent="#c2410c"
          />
        </div>
      )}

      {/* ISP: Technopara Excel (final) + month-end Morning Report (tentative) */}
      {isIsp && (
        <div style={{
          marginBottom: 16, padding: '12px 14px',
          background: '#f5f3ff', border: '1px solid #ddd6fe', borderRadius: 8,
        }}>
          <div style={{ fontSize: 14, fontWeight: 700, color: '#5b21b6', marginBottom: 10 }}>
            ISP Techno Upload — Technopara Excel (final) and/or Month-End Morning Report (tentative, merged into the same table)
          </div>
          <ExtractRow
            label="ISP Technopara Excel"
            previewEndpoint="/api/techno/preview"
            insertEndpoint="/api/techno/insert"
            plant="ISP"
            reportMonth={reportMonth}
            apiBase={apiBase}
            onSuccess={loadData}
            accent="#7c3aed"
          />
          <ExtractRow
            label="ISP Morning Report — month-end (tentative)"
            previewEndpoint="/api/mcr-techno/preview"
            insertEndpoint="/api/mcr-techno/insert"
            cumulativeEndpoint="/api/mcr-techno/cumulative"
            plant="ISP"
            reportMonth={reportMonth}
            apiBase={apiBase}
            onSuccess={loadData}
            accent="#5b21b6"
          />
        </div>
      )}

      {/* DSP: monthly PDF + month-end MCR techno page (both merged) */}
      {plant === 'DSP' && (
        <div style={{
          marginBottom: 16, padding: '12px 14px',
          background: '#fef2f2', border: '1px solid #fecaca', borderRadius: 8,
        }}>
          <div style={{ fontSize: 14, fontWeight: 700, color: '#991b1b', marginBottom: 10 }}>
            DSP Techno Upload — Monthly PDF (final) and/or Month-End MCR Excel (tentative, merged into the same table)
          </div>
          <ExtractRow
            label="DSP Monthly Report PDF"
            previewEndpoint="/api/techno/preview"
            insertEndpoint="/api/techno/insert"
            plant="DSP"
            reportMonth={reportMonth}
            apiBase={apiBase}
            onSuccess={loadData}
            accent="#dc2626"
            accept=".pdf"
          />
          <ExtractRow
            label="DSP MCR Month-End Excel (mcr1_*.xlsx)"
            previewEndpoint="/api/mcr-techno/preview"
            insertEndpoint="/api/mcr-techno/insert"
            cumulativeEndpoint="/api/mcr-techno/cumulative"
            plant="DSP"
            reportMonth={reportMonth}
            apiBase={apiBase}
            onSuccess={loadData}
            accent="#b91c1c"
            accept=".xlsx,.xls"
          />
        </div>
      )}

      {/* BSL: upload bar + BF Performance extractor. Existing DB data is
          still shown below via the shared units.length > 0 panel, same as
          every other plant. */}
      {isBsl && (
        <div>
          <div style={{
            marginBottom: 16, padding: '12px 14px',
            background: '#f0fdf4', border: '1px solid #86efac', borderRadius: 8,
          }}>
            <div style={{ fontSize: 14, fontWeight: 700, color: '#166534', marginBottom: 10 }}>
              BSL Techno Upload — upload Techno Excel and/or BF Performance PDF (both merged automatically)
            </div>
            <ExtractRow
              label="BSL Techno Excel (.xls/.xlsx)"
              previewEndpoint="/api/techno/preview"
              insertEndpoint="/api/techno/insert"
              plant="BSL"
              reportMonth={reportMonth}
              apiBase={apiBase}
              onSuccess={loadData}
              accent="#166534"
            />
          </div>

          {/* Unified BSL BF Performance Extractor */}
          <BSLBFTechnoExtractor
            reportMonth={reportMonth}
            apiBase={apiBase}
            onSuccess={loadData}
          />
        </div>
      )}

      {!loading && units.length > 0 && (
        <div style={{
          display: 'flex', alignItems: 'center', gap: 12, flexWrap: 'wrap',
          marginBottom: 10, padding: '8px 12px',
          background: '#f0fdf4', border: '1px solid #bbf7d0', borderRadius: 7,
        }}>
          <button onClick={handleCumulativeAll} disabled={cumBusy}
            style={{
              padding: '7px 16px', background: cumBusy ? '#5f6368' : '#16a34a',
              color: '#fff', border: 'none', borderRadius: 6, fontSize: 13,
              cursor: cumBusy ? 'not-allowed' : 'pointer', fontWeight: 600, whiteSpace: 'nowrap',
            }}
          >
            {cumBusy ? 'Calculating…' : 'Calculate Cumulative — all techno'}
          </button>
          <span style={{ fontSize: 12, color: '#166534' }}>
            Computes the Cumulative (Apr→{reportMonth}) for every saved parameter of every {plant} unit and opens a
            step-by-step review window (method, production weights, month-by-month working) — nothing is saved
            until you confirm.
          </span>
        </div>
      )}
      <StatusMsg status={cumStatusShown} />

      {loading && (
        <div style={{ textAlign: 'center', padding: 40, color: '#5f6368', fontSize: 14 }}>
          Loading {plant} data…
        </div>
      )}

      {!loading && units.length === 0 && (
        <div style={{
          textAlign: 'center', padding: 60, color: '#5f6368', fontSize: 14,
          border: '2px dashed #dadce0', borderRadius: 8,
        }}>
          No techno data for <strong>{plant}</strong> — <strong>{reportMonth}</strong>.
          {hasExtraction && (
            <span style={{ fontSize: 13, marginTop: 8, display: 'block' }}>
              Upload the {isDsp ? 'PDF' : 'Excel'} file above to extract and save data.
            </span>
          )}
          {!hasExtraction && (
            <span style={{ fontSize: 13, marginTop: 8, display: 'block' }}>
              {plant} extraction support coming soon.
            </span>
          )}
        </div>
      )}

      {!loading && units.length > 0 && (
        <div style={{ display: 'flex', gap: 0, border: '1px solid #dadce0', borderRadius: 8, overflow: 'hidden', minHeight: 400 }}>
          {/* Unit list (left) */}
          <div style={{ width: 180, borderRight: '1px solid #dadce0', background: '#f8f9fa', flexShrink: 0 }}>
            <div style={{ padding: '10px 14px', fontSize: 12, fontWeight: 700, color: '#5f6368', textTransform: 'uppercase', letterSpacing: '0.05em', borderBottom: '1px solid #dadce0' }}>
              Units ({units.length})
            </div>
            {units.map(u => (
              <button
                key={u}
                onClick={() => setActiveUnit(u)}
                style={{
                  display: 'block', width: '100%', padding: '10px 14px', textAlign: 'left',
                  background: activeUnit === u ? '#e8f0fe' : 'transparent',
                  color: activeUnit === u ? '#174ea6' : '#5f6368',
                  border: 'none', borderBottom: '1px solid #dadce0',
                  fontSize: 13, fontWeight: activeUnit === u ? 700 : 400,
                  cursor: 'pointer',
                }}
              >
                {u}
              </button>
            ))}
          </div>

          {/* Parameter table (right) */}
          <div style={{ flex: 1, overflowX: 'auto' }}>
            {unitData && (
              <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 14 }}>
                <thead>
                  <tr style={{ background: '#f8f9fa' }}>
                    <th style={{ padding: '7px 14px', textAlign: 'left', color: '#5f6368', fontWeight: 600, borderBottom: '2px solid #dadce0', minWidth: 200 }}>
                      Parameter
                    </th>
                    <th style={{ padding: '7px 12px', textAlign: 'right', color: '#1a73e8', fontWeight: 600, borderBottom: '2px solid #dadce0', minWidth: 120 }}>
                      Month
                    </th>
                    <th style={{ padding: '7px 12px', textAlign: 'right', color: '#5f6368', fontWeight: 600, borderBottom: '2px solid #dadce0', minWidth: 120 }}>
                      Cumulative
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {Object.keys(monthParams).map((param, idx) => {
                    const mv = monthParams[param];
                    const tv = tillParams[param];
                    const fmt = v => {
                      if (v == null || v === '') return '—';
                      if (typeof v === 'string' && v.includes(':')) return v;
                      return Number(v).toLocaleString(undefined, { maximumFractionDigits: 3 });
                    };
                    return (
                      <tr key={param} style={{ background: idx % 2 === 0 ? '#fff' : '#f8f9fa', borderBottom: '1px solid #f8f9fa' }}>
                        <td style={{ padding: '6px 14px', color: '#202124', fontWeight: 500 }}>{param}</td>
                        <td style={{ padding: '6px 12px', textAlign: 'right', fontFamily: 'monospace', color: mv != null ? '#1a73e8' : '#9aa0a6' }}>
                          {fmt(mv)}
                        </td>
                        <td style={{ padding: '6px 12px', textAlign: 'right', fontFamily: 'monospace', color: tv != null ? '#202124' : '#9aa0a6' }}>
                          {fmt(tv)}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            )}
          </div>
        </div>
      )}

      <BulkCumulativeModal
        preview={cumPreviewAll}
        busy={cumConfirmBusy}
        onConfirm={handleConfirmCumulativeAll}
        onClose={() => setCumPreviewAll(null)}
      />
    </div>
  );
}

// ── Main page ─────────────────────────────────────────────────────────────────
export default function TechnoDataEntry() {
  const def = getDefaultPeriod();
  const [month, setMonth] = useState(def.month);
  const [year, setYear] = useState(def.year);
  const [plant, setPlant] = useState('RSP');

  const reportMonth = useMemo(() => formatMonth(year, month), [year, month]);

  const plantHint = {
    RSP: 'Upload the Technopara Excel (final), or the month-end Daily Morning Report (tentative furnace/SMS data; month verified against the report date in A2).',
    BSP: 'Upload the BSP Flash Monthly PDF (one file: coke yield, SP-2/3, BF shop + per-furnace CDI/productivity, SMS-2/3, all mills, energy — month auto-detected from the cover), BSP-3-page-Tech.xlsx and/or OISCO Excel (final), or the month-end MIS-2 / PPC MIS Excel (tentative furnace & SMS data). All merged automatically.',
    ISP: 'Upload the multi-sheet ISP Technopara Excel (final), or the month-end Morning Report (tentative furnace/SMS/energy data; month verified against the report date in J5/K5). Both merged automatically.',
    DSP: 'Upload the Monthly Report PDF (final) and/or the month-end MCR Excel (tentative for-the-month values; month is verified against the report date in C1).',
    BSL: 'Upload Techno Excel and/or BF Performance PDF. Both merged automatically.',
  }[plant] || `${plant} extraction coming soon.`;

  return (
    <div style={{ height: '100vh', display: 'flex', flexDirection: 'column', background: '#ffffff' }}>
      <GlobalNavbar />

      <div style={{ flex: 1, overflow: 'auto', maxWidth: 1400, margin: '0 auto', padding: '22px 20px', width: '100%', boxSizing: 'border-box' }}>

        {/* ── Page title ── */}
        <div style={{ marginBottom: 18 }}>
          <h2 style={{ fontSize: '1.6rem', fontWeight: 700, color: '#202124', margin: '0 0 4px' }}>
            Techno Data — View &amp; Extract
          </h2>
          <span style={{ fontSize: 13, color: '#5f6368' }}>
            {reportMonth} · data stored in <code style={{ fontSize: 12 }}>techno_data</code> table
          </span>
        </div>

        {/* ── Controls bar ── */}
        <div style={{
          display: 'flex', gap: 10, alignItems: 'center', flexWrap: 'wrap',
          marginBottom: 18, background: '#fff', border: '1px solid #dadce0',
          borderRadius: 8, padding: '14px 18px',
        }}>
          <label style={{ fontSize: 13, fontWeight: 600, color: '#374151' }}>Plant</label>
          <select value={plant} onChange={e => setPlant(e.target.value)}
                  style={{ padding: '7px 10px', fontSize: 14, border: '1px solid #d1d5db', borderRadius: 4 }}>
            {PLANTS.map(p => <option key={p} value={p}>{p}</option>)}
          </select>

          <label style={{ fontSize: 13, fontWeight: 600, color: '#374151', marginLeft: 10 }}>Month</label>
          <select value={month} onChange={e => setMonth(e.target.value)}
                  style={{ padding: '7px 10px', fontSize: 14, border: '1px solid #d1d5db', borderRadius: 4 }}>
            {MONTHS.map(m => <option key={m}>{m}</option>)}
          </select>
          <select value={year} onChange={e => setYear(e.target.value)}
                  style={{ padding: '7px 10px', fontSize: 14, border: '1px solid #d1d5db', borderRadius: 4 }}>
            {YEARS.map(y => <option key={y}>{y}</option>)}
          </select>

          <span style={{ marginLeft: 'auto', fontSize: 13, color: '#5f6368', maxWidth: 420, textAlign: 'right' }}>
            {plantHint}
          </span>
        </div>

        <TechnoDataPanel plant={plant} reportMonth={reportMonth} apiBase={API_BASE_URL} />
      </div>
    </div>
  );
}
