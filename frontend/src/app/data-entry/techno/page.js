'use client';

import RequireEditor from '@/components/RequireEditor';

import React, { useState, useCallback, useEffect, useMemo } from 'react';
import GlobalNavbar from '@/components/GlobalNavbar';
import BSLBFTechnoExtractor from '@/components/BSLBFTechnoExtractor';
import ui from '@/styles/ui.module.css';
import t from './techno.module.css';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || '';

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
const YEAR_RANGE_START = 2000;
const _now = new Date();
// FY start year: Apr..Dec -> this calendar year; Jan..Mar -> previous calendar year
const CURRENT_FY_END_YEAR = (_now.getMonth() >= 3 ? _now.getFullYear() : _now.getFullYear() - 1) + 1;

// Calendar years: 2000 through the current FY's end year (covers Jan-Mar
// report months that fall in the current FY but the next calendar year).
const YEARS = Array.from(
  { length: CURRENT_FY_END_YEAR - YEAR_RANGE_START + 1 },
  (_, i) => (YEAR_RANGE_START + i).toString()
);

function getDefaultPeriod() {
  const d = new Date();
  d.setMonth(d.getMonth() - 1);
  // MONTHS is FY-ordered (April-first) — can't index it with JS's
  // Jan-ordered getMonth(), so look the name up in a Jan-ordered array.
  const names = ['January','February','March','April','May','June','July','August','September','October','November','December'];
  return { month: names[d.getMonth()], year: d.getFullYear().toString() };
}

function formatMonth(year, month) {
  return `${year}-${MONTH_NUM[month]}`;
}

// A long-running request (a 12-month bulk save is dozens of DB writes and
// can take tens of seconds) is long enough to occasionally hit something
// that returns plain text instead of JSON — a proxy/dev-server error page,
// or a backend crash that slipped past its own JSON error handling. Calling
// res.json() directly on that throws a cryptic "Unexpected token '<char>'
// ... is not valid JSON", which surfaces as the error text with no hint of
// what actually went wrong. Read the body as text first so a non-JSON
// response becomes a readable message instead.
async function parseJsonResponse(res) {
  const text = await res.text();
  try {
    return JSON.parse(text);
  } catch {
    const snippet = text.slice(0, 200).replace(/\s+/g, ' ').trim();
    throw new Error(
      `Server returned an unexpected (non-JSON) response — HTTP ${res.status}`
      + (snippet ? `: "${snippet}${text.length > 200 ? '…' : ''}"` : '')
    );
  }
}

// ── Shared styled status message ──────────────────────────────────────────────
const STATUS_CLASS = { success: ui.alertSuccess, info: ui.alertWarning, error: ui.alertError };

function StatusMsg({ status }) {
  if (!status) return null;
  return (
    <div role={status.type === 'error' ? 'alert' : 'status'}
         className={`${ui.alert} ${STATUS_CLASS[status.type] || ui.alertError}`}
         style={{ marginTop: 8 }}>
      {status.text}
    </div>
  );
}

// ── Bulk "Calculate Cumulative" step window — shows the full working (method,
// production weights from production_table, month-by-month rows, formula)
// for every parameter of every unit BEFORE anything is written to the DB. ────
function BulkCumulativeModal({ preview, onConfirm, onClose, busy, confirmLabel, noteText }) {
  const [expanded, setExpanded] = React.useState(null);
  // Escape closes (unless a save is in flight), same as the other modals.
  React.useEffect(() => {
    if (!preview) return;
    const onKey = (e) => { if (e.key === 'Escape' && !busy) onClose(); };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [preview, busy, onClose]);
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

  return (
    <div className={t.overlay} onMouseDown={(e) => { if (e.target === e.currentTarget && !busy) onClose(); }}>
      <div role="dialog" aria-modal="true" aria-labelledby="tu-cum-title" className={t.modal}>
        <div className={t.modalScroll}>
          <h3 id="tu-cum-title" className={t.modalTitle}>
            Cumulative Calculation — {preview.plant} · April → {preview.report_month}
          </h3>
          <p className={ui.meta}>
            {preview.details.length} parameter{preview.details.length === 1 ? '' : 's'} across {units.length} unit{units.length === 1 ? '' : 's'}.
            Furnace-wise and BF_Shop production, and SMS-wise crude steel, are read from production_table for the weighting shown below.
            {' '}{noteText || 'Nothing is saved yet — review each calculation, then confirm.'}
          </p>

          {(preview.warnings || []).map((w, i) => (
            <div key={i} className={`${ui.alert} ${ui.alertError}`} style={{ marginBottom: 6, fontSize: 13 }}>{w}</div>
          ))}

          {units.map(u => (
            <div key={u} className={t.unitCard}>
              <div className={t.unitCardHead}>{u}</div>
              <table className={t.mini}>
                <thead>
                  <tr>
                    <th scope="col">Parameter</th>
                    <th scope="col">Method</th>
                    <th scope="col" className={t.num}>Previous Cumulative</th>
                    <th scope="col" className={t.num}>New Cumulative</th>
                    <th scope="col"><span className={ui.srOnly}>Working</span></th>
                  </tr>
                </thead>
                <tbody>
                  {byUnit[u].map(d => {
                    const key = `${d.unit}::${d.param_key}`;
                    const isOpen = expanded === key;
                    const isChanged = changed(d.previous_till_month, d.result);
                    return (
                      <React.Fragment key={key}>
                        <tr>
                          <td>
                            {d.param_key}
                            {d.warnings.length > 0 && (
                              <span title={d.warnings.join(' ')} className={t.warnIcon} aria-label={`Warning: ${d.warnings.join(' ')}`}>⚠</span>
                            )}
                          </td>
                          <td className={t.muted}>{methodLabel[d.method] || d.method}</td>
                          <td className={`${t.num} ${t.muted}`}>{fmt(d.previous_till_month)}</td>
                          <td className={`${t.num} ${isChanged ? t.diff : ''}`}>{fmt(d.result)}</td>
                          <td className={t.num}>
                            <button type="button" onClick={() => setExpanded(isOpen ? null : key)}
                                    aria-expanded={isOpen}
                                    className={`${ui.btn} ${ui.btnSecondary} ${ui.btnSm}`}>
                              {isOpen ? 'Hide' : 'Steps'}
                            </button>
                          </td>
                        </tr>
                        {isOpen && (
                          <tr className={t.stepsCell}>
                            <td colSpan={5}>
                              {d.weight_item && (
                                <p className={ui.meta} style={{ marginBottom: 8 }}>Weights: {d.weight_item}</p>
                              )}
                              {d.rows.length > 0 && (
                                <table className={t.mini} style={{ marginBottom: 8, background: 'var(--ui-surface)' }}>
                                  <thead>
                                    <tr>
                                      <th scope="col">Month</th>
                                      <th scope="col" className={t.num}>Value</th>
                                      <th scope="col" className={t.num}>Weight (production)</th>
                                      <th scope="col" className={t.num}>Product</th>
                                    </tr>
                                  </thead>
                                  <tbody>
                                    {d.rows.map(r => (
                                      <tr key={r.month}>
                                        <td className={ui.nowrap}>{r.month}</td>
                                        <td className={t.num}>{fmt(r.value)}</td>
                                        <td className={`${t.num} ${r.weight == null && d.method !== 'sum' ? t.missing : ''}`}>
                                          {r.weight == null ? (d.method === 'sum' ? '—' : 'missing') : fmt(r.weight)}
                                        </td>
                                        <td className={t.num}>{r.product != null ? fmt(r.product) : '—'}</td>
                                      </tr>
                                    ))}
                                  </tbody>
                                </table>
                              )}
                              <div className={t.steps}>
                                {d.steps.map((s, i) => <div key={i}>{i + 1}. {s}</div>)}
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
        </div>

        <div className={t.modalFoot}>
          {/* Initial focus: the confirm button only when it just fills the
              preview (confirmLabel given); when it writes to the DB, focus
              Cancel so a stray Enter can't save hundreds of values. */}
          <button type="button" onClick={onClose} disabled={busy} autoFocus={!confirmLabel}
                  className={`${ui.btn} ${ui.btnSecondary}`}>
            Cancel
          </button>
          <button type="button" onClick={onConfirm} disabled={busy} aria-busy={busy} autoFocus={!!confirmLabel}
                  className={`${ui.btn} ${ui.btnPrimary}`}>
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
  // Two or more sheets can legitimately share a unit name (e.g. ISP's
  // B-FCE, Coal to Hot Metal, and Maj Techno Summ all write "General" for
  // different, non-overlapping parameters). Each record's own techno_json
  // only carries the params ITS sheet extracted, but db_json carries the
  // FULL previously-saved set for that unit — so deciding blank/protect
  // per record (rather than per unit) means a later record that doesn't
  // own a given param sees it as "not extracted here" and marks it
  // auto-protected, clobbering an earlier record that genuinely extracted
  // it. Merge every record sharing a unit into one combined view first,
  // then decide blank/protect once per parameter from that merged view.
  const units = Array.from(new Set((records || []).map((r) => r.unit)));
  units.forEach((unit) => {
    const unitRecords = (records || []).filter((r) => r.unit === unit);
    const monthData = Object.assign({}, ...unitRecords.map((r) => r.techno_json?.month || {}));
    const dbMonth = Object.assign({}, ...unitRecords.map((r) => r.db_json?.month || {}));
    const allParams = new Set([...Object.keys(monthData), ...Object.keys(dbMonth)]);
    const checkedUnit = {};
    const autoUnit = {};
    allParams.forEach((p) => {
      const extracted = monthData[p];
      const dbVal = dbMonth[p];
      const blank = extracted == null || extracted === '';
      const dbHasValue = dbVal != null && dbVal !== '';
      const protect = blank && dbHasValue;
      checkedUnit[p] = !protect;
      autoUnit[p] = protect;
    });
    checked[unit] = checkedUnit;
    autoProtected[unit] = autoUnit;
  });
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
    <div className={t.review}>
      <div className={t.reviewHead}>
        Preview — {preview.units_extracted} unit{preview.units_extracted === 1 ? '' : 's'}, {preview.total_params} parameter{preview.total_params === 1 ? '' : 's'} for {preview.report_month}. Nothing saved yet.
      </div>
      <div className={t.reviewBody}>
        <div className={t.unitTabs} role="tablist" aria-label="Extracted units" aria-orientation="vertical">
          {uniqueUnits.map(unit => (
            <button key={unit} type="button" role="tab" aria-selected={activeUnit === unit}
                    className={t.unitTab} onClick={() => setActiveUnit(unit)}>
              {unit}
            </button>
          ))}
        </div>
        <div className={t.reviewTable}>
          <table className={t.mini}>
            <thead>
              <tr>
                <th scope="col" rowSpan={2} className={t.center}>Insert</th>
                <th scope="col" rowSpan={2}>Parameter</th>
                <th scope="colgroup" colSpan={2} className={t.center}>Month</th>
                <th scope="colgroup" colSpan={2} className={t.center}>Cumulative</th>
              </tr>
              <tr>
                <th scope="col" className={t.num}>In DB</th>
                <th scope="col" className={t.num}>Extracted</th>
                <th scope="col" className={t.num}>In DB</th>
                <th scope="col" className={t.num}>Extracted</th>
              </tr>
            </thead>
            <tbody>
              {allParams.map((param) => {
                const dbM = dbMonthParams[param], newM = monthParams[param];
                const dbT = dbTillParams[param],  newT = tillParams[param];
                const isChecked = unitChecked[param] !== false;
                const isAutoProtected = !!unitAutoProtected[param];
                return (
                  <tr key={param} className={isChecked ? undefined : t.skipped}>
                    <td className={t.center}>
                      <input type="checkbox" checked={isChecked} className={t.check}
                             onChange={(e) => onToggleParam(activeUnit, param, e.target.checked)}
                             aria-label={`Insert ${param}`}
                             title={isAutoProtected ? 'Extracted value was blank — unchecked to keep the existing DB value' : 'Include this parameter in the save'} />
                    </td>
                    <td>
                      {param}
                      {isAutoProtected && <span className={t.protectNote}>kept existing — extracted was blank</span>}
                    </td>
                    <td className={`${t.num} ${t.muted}`}>{fmt(dbM)}</td>
                    <td className={`${t.num} ${changed(dbM, newM) ? t.diff : t.extracted}`}>{fmt(newM)}</td>
                    <td className={`${t.num} ${t.muted}`}>{fmt(dbT)}</td>
                    <td className={`${t.num} ${changed(dbT, newT) ? t.diff : t.extracted}`}>{fmt(newT)}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>
      <div className={t.reviewFoot}>
        <span className={t.diff}>Amber</span> = extracted value differs from what&apos;s currently in the DB.
        Unchecked rows are skipped on save and keep their current DB value — rows where the
        extraction came back blank are unchecked automatically so a bad file can&apos;t wipe out a good value; uncheck any other row yourself to keep the DB value instead.
      </div>
    </div>
  );
}

// ── Single file-upload row used for each file type ────────────────────────────
// `bulkMonths`: when true, shows a "Backfill all months" checkbox that swaps
// Preview/Confirm&Save over to /api/techno/preview-months + /insert-months —
// extracts every FY month April..reportMonth from one uploaded workbook
// instead of just reportMonth (ISP's workbook carries every month as its own
// column, so a later cumulative upload can refresh/backfill earlier months
// whose figures were revised before the FY closed). Unchecked, this row
// behaves exactly as before.
function ExtractRow({ label, previewEndpoint, insertEndpoint, cumulativeEndpoint, reportMonth, apiBase, onSuccess, plant, accept = '.xlsx,.xls', bulkMonths = false }) {
  const rowId = React.useId();
  const [file, setFile] = React.useState(null);
  const [busy,  setBusy]  = React.useState(false);
  const [status, setStatus] = React.useState(null);
  const [preview, setPreview] = React.useState(null);
  const [cumPreview, setCumPreview] = React.useState(null);
  const [paramChecked, setParamChecked] = React.useState({});
  const [autoProtected, setAutoProtected] = React.useState({});
  const inputRef = React.useRef();

  // ── Bulk "all months" mode state ──
  const [bulkMode, setBulkMode] = React.useState(false);
  const [bulkPreview, setBulkPreview] = React.useState(null); // { months, skipped_months, source_file, per_month }
  const [activeBulkMonth, setActiveBulkMonth] = React.useState(null);
  const [bulkParamState, setBulkParamState] = React.useState({}); // { [month]: { checked, autoProtected } }
  // Separate from `busy` (shared with the single-month path) so the UI can
  // show an unmissable, save-specific progress banner — a bulk save writes
  // one DB row per (month, unit), which can genuinely take tens of seconds
  // for a dozen months; without a clear in-progress state a user has no way
  // to tell "still working" from "did nothing", and re-submits, which is
  // harmless (merge-safe) but wasteful and confusing.
  const [bulkSaving, setBulkSaving] = React.useState(false);

  // Warn before leaving/reloading mid-save — the save keeps running
  // server-side either way, but a user who navigates away and comes back
  // has no way to tell that, and is likely to just re-submit.
  React.useEffect(() => {
    if (!bulkSaving) return;
    const handler = (e) => { e.preventDefault(); e.returnValue = ''; };
    window.addEventListener('beforeunload', handler);
    return () => window.removeEventListener('beforeunload', handler);
  }, [bulkSaving]);

  React.useEffect(() => {
    setFile(null);
    setStatus(null);
    setPreview(null);
    setBulkPreview(null);
    if (inputRef.current) inputRef.current.value = '';
  }, [reportMonth]);

  const toggleParam = (unit, param, checked) => {
    setParamChecked(prev => ({ ...prev, [unit]: { ...(prev[unit] || {}), [param]: checked } }));
  };

  const toggleBulkParam = (month, unit, param, checked) => {
    setBulkParamState(prev => ({
      ...prev,
      [month]: {
        ...(prev[month] || { checked: {}, autoProtected: {} }),
        checked: {
          ...(prev[month]?.checked || {}),
          [unit]: { ...(prev[month]?.checked?.[unit] || {}), [param]: checked },
        },
      },
    }));
  };

  const handleBulkPreview = async () => {
    if (!file) return;
    setBusy(true);
    setStatus(null);
    setBulkPreview(null);
    const form = new FormData();
    form.append('file', file);
    form.append('upto_month', reportMonth);
    if (plant) form.append('plant', plant);
    try {
      const res = await fetch(`${apiBase}/api/techno/preview-months`, { method: 'POST', body: form });
      const json = await parseJsonResponse(res);
      if (!res.ok) throw new Error(json.detail || 'Preview failed');
      setBulkPreview(json);
      setActiveBulkMonth(json.months?.[0] || null);
      const nextState = {};
      for (const [month, d] of Object.entries(json.per_month || {})) {
        const { checked, autoProtected: auto } = computeParamDefaults(d.records || []);
        nextState[month] = { checked, autoProtected: auto };
      }
      setBulkParamState(nextState);
    } catch (err) {
      setStatus({ type: 'error', text: err.message });
    } finally {
      setBusy(false);
    }
  };

  const handleBulkConfirmSave = async () => {
    if (!bulkPreview) return;
    setBusy(true);
    setBulkSaving(true);
    setStatus(null);
    try {
      const months = Object.entries(bulkPreview.per_month || {}).map(([month, d]) => {
        const unitChecked = bulkParamState[month]?.checked || {};
        const recordsToSave = d.records.map(rec => {
          const checkedForUnit = unitChecked[rec.unit] || {};
          const keep = (obj) => Object.fromEntries(
            Object.entries(obj || {}).filter(([p]) => checkedForUnit[p] !== false)
          );
          return {
            unit: rec.unit,
            techno_json: {
              month: keep(rec.techno_json?.month),
              till_month: keep(rec.techno_json?.till_month),
            },
          };
        });
        return { report_month: month, records: recordsToSave };
      });
      const res = await fetch(`${apiBase}/api/techno/insert-months`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ plant, source_file: bulkPreview.source_file, months }),
      });
      const json = await parseJsonResponse(res);
      if (!res.ok) throw new Error(json.detail || 'Save failed');
      const savedEntries = Object.entries(json.saved || {});
      const totalUnits = savedEntries.reduce((sum, [, n]) => sum + n, 0);
      const savedText = savedEntries.map(([m, n]) => `${m}: ${n}`).join(', ');
      setStatus({
        type: 'success',
        text: `✓ Saved ${savedEntries.length} month${savedEntries.length === 1 ? '' : 's'} `
          + `(${totalUnits} units total) — ${savedText}`,
      });
      setBulkPreview(null);
      setBulkMode(false);
      setFile(null);
      if (inputRef.current) inputRef.current.value = '';
      onSuccess();
    } catch (err) {
      setStatus({ type: 'error', text: err.message });
    } finally {
      setBusy(false);
      setBulkSaving(false);
    }
  };

  const handleBulkCancelPreview = () => {
    setBulkPreview(null);
    setStatus(null);
  };

  const handlePreview = async () => {
    if (bulkMonths && bulkMode) return handleBulkPreview();
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
      const json = await parseJsonResponse(res);
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
      const json = await parseJsonResponse(res);
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
      let json = await parseJsonResponse(res);
      if (res.status === 409) {
        // Existing data would be replaced — ask for user consent, then retry
        if (!window.confirm(`${json.detail}\n\nReplace the existing values?`)) {
          setBusy(false);
          return;
        }
        res = await doInsert(true);
        json = await parseJsonResponse(res);
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

  const busyLocked = !!(preview || bulkPreview);

  return (
    <div className={t.extract}>
      <div className={t.row}>
        <label htmlFor={`${rowId}-file`} className={t.rowLabel}>{label}</label>
        <input id={`${rowId}-file`} ref={inputRef} type="file" accept={accept} className={t.file}
          onChange={e => { setFile(e.target.files[0]); setStatus(null); setPreview(null); setBulkPreview(null); }}
          suppressHydrationWarning
        />
        {bulkMonths && (
          <label className={ui.checkRow} style={{ fontSize: 13, whiteSpace: 'nowrap' }}>
            <input type="checkbox" checked={bulkMode} disabled={busyLocked}
              onChange={e => setBulkMode(e.target.checked)} />
            Backfill all months (Apr → {reportMonth})
          </label>
        )}
        <div className={t.rowActions}>
          {!busyLocked && (
            <button type="button" onClick={handlePreview} disabled={!file || busy} aria-busy={busy}
                    className={`${ui.btn} ${ui.btnPrimary} ${ui.btnSm}`}>
              {busy ? (bulkMode ? 'Extracting all months…' : 'Extracting…') : 'Preview'}
            </button>
          )}
          {preview && (
            <>
              {cumulativeEndpoint && (
                <button type="button" onClick={handleCalcCumulative} disabled={busy}
                        className={`${ui.btn} ${ui.btnSecondary} ${ui.btnSm}`}>
                  {busy ? 'Working…' : 'Calc Cumulative'}
                </button>
              )}
              <button type="button" onClick={handleConfirmSave} disabled={busy} aria-busy={busy}
                      className={`${ui.btn} ${ui.btnPrimary} ${ui.btnSm}`}>
                {busy ? 'Saving…' : 'Confirm & Save'}
              </button>
              <button type="button" onClick={handleCancelPreview} disabled={busy}
                      className={`${ui.btn} ${ui.btnSecondary} ${ui.btnSm}`}>
                Cancel
              </button>
            </>
          )}
          {bulkPreview && (
            <>
              <button type="button" onClick={handleBulkConfirmSave} disabled={busy} aria-busy={bulkSaving}
                      className={`${ui.btn} ${ui.btnPrimary} ${ui.btnSm}`}>
                {bulkSaving ? 'Saving, please wait…' : `Confirm & Save all ${bulkPreview.months.length} months`}
              </button>
              <button type="button" onClick={handleBulkCancelPreview} disabled={busy}
                      className={`${ui.btn} ${ui.btnSecondary} ${ui.btnSm}`}>
                Cancel
              </button>
            </>
          )}
        </div>
      </div>
      {bulkSaving && (
        <div className={t.progress} role="status">
          <span className={t.spinner} aria-hidden="true" />
          <span>
            Saving {bulkPreview?.months?.length} month{bulkPreview?.months?.length === 1 ? '' : 's'} — this
            writes one database row per unit per month and can take up to a minute.
            Please don&apos;t close or refresh this page; a green confirmation will appear here when it&apos;s done.
          </span>
        </div>
      )}
      {preview && (preview.warnings || []).length > 0 && (
        <div className={t.note} role="status">
          {preview.warnings.map((w, i) => <div key={i}>⚠ {w}</div>)}
        </div>
      )}
      {preview && (
        <PreviewReview preview={preview} paramChecked={paramChecked}
                       autoProtected={autoProtected} onToggleParam={toggleParam} />
      )}

      {bulkPreview && (bulkPreview.skipped_months || []).length > 0 && (
        <div className={t.note} role="status">
          ⚠ This file has no column for: {bulkPreview.skipped_months.join(', ')} — skipped.
        </div>
      )}
      {bulkPreview && (
        <div>
          <div className={t.monthTabs} role="tablist" aria-label="Backfilled months">
            {bulkPreview.months.map(month => (
              <button key={month} type="button" role="tab" aria-selected={activeBulkMonth === month}
                      onClick={() => setActiveBulkMonth(month)}
                      className={`${ui.btn} ${ui.btnSm} ${activeBulkMonth === month ? ui.btnPrimary : ui.btnSecondary}`}>
                {month}
              </button>
            ))}
          </div>
          {activeBulkMonth && bulkPreview.per_month[activeBulkMonth] && (
            <PreviewReview
              preview={{ ...bulkPreview.per_month[activeBulkMonth], report_month: activeBulkMonth }}
              paramChecked={bulkParamState[activeBulkMonth]?.checked || {}}
              autoProtected={bulkParamState[activeBulkMonth]?.autoProtected || {}}
              onToggleParam={(unit, param, checked) => toggleBulkParam(activeBulkMonth, unit, param, checked)}
            />
          )}
        </div>
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
// ── "Last saved" log — same extraction_log table /upload reads, filtered to
// this plant's techno_data writes so it shows when each unit/month was last
// saved and from what file (or "(manual entry)"). ────────────────────────────
function TechnoSaveLog({ plant, reportMonth, apiBase, refreshKey }) {
  const [logs, setLogs] = React.useState([]);
  const [expanded, setExpanded] = React.useState(false);
  const [loadingLog, setLoadingLog] = React.useState(false);

  const fetchLog = React.useCallback(async () => {
    setLoadingLog(true);
    try {
      const res = await fetch(
        `${apiBase}/api/extraction-log?plant=${plant}&source_type=${encodeURIComponent('Techno Data')}&limit=20`
      );
      const json = await parseJsonResponse(res);
      setLogs(json.logs || []);
    } catch {
      setLogs([]);
    } finally {
      setLoadingLog(false);
    }
  }, [plant, apiBase]);

  useEffect(() => { fetchLog(); }, [fetchLog, refreshKey]);

  const latest = logs[0];

  return (
    <div className={t.log}>
      <button type="button" className={t.logToggle} aria-expanded={expanded}
              onClick={() => setExpanded(e => !e)}>
        <svg className={t.chevron} width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor"
             strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
          <polyline points="9 6 15 12 9 18" />
        </svg>
        <strong>Last saved:</strong>
        {loadingLog && <span>checking…</span>}
        {!loadingLog && latest && (
          <span>
            {latest.logged_at} — {latest.sheet_name} ({latest.report_month}) — {latest.items_extracted} params
            {latest.file_name && latest.file_name !== '(manual entry)' ? ` — ${latest.file_name}` : ' — manual entry'}
          </span>
        )}
        {!loadingLog && !latest && <span>no save history yet for {plant}</span>}
      </button>
      {expanded && logs.length > 0 && (
        <div className={t.logBody}>
          <table className={t.mini}>
            <thead>
              <tr>
                <th scope="col">When</th>
                <th scope="col">Unit</th>
                <th scope="col">Report month</th>
                <th scope="col">Source</th>
                <th scope="col" className={t.num}>Params</th>
              </tr>
            </thead>
            <tbody>
              {logs.map(l => (
                <tr key={l.id}>
                  <td className={ui.nowrap}>{l.logged_at}</td>
                  <td>{l.sheet_name}</td>
                  <td>{l.report_month}</td>
                  <td className={t.muted}>{l.file_name || 'manual entry'}</td>
                  <td className={t.num}>{l.items_extracted}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

function TechnoDataPanel({ plant, reportMonth, apiBase }) {
  const [data, setData] = React.useState({});
  const [activeUnit, setActiveUnit] = React.useState(null);
  const [loading, setLoading] = React.useState(false);
  const [cumBusy, setCumBusy] = React.useState(false);
  const [cumStatus, setCumStatus] = React.useState(null);
  const [cumPreviewAll, setCumPreviewAll] = React.useState(null);
  const [cumConfirmBusy, setCumConfirmBusy] = React.useState(false);
  const [logTick, setLogTick] = React.useState(0);

  const loadData = React.useCallback(async () => {
    setLoading(true);
    setLogTick(n => n + 1);
    try {
      const res = await fetch(
        `${apiBase}/api/techno/data?plant=${plant}&report_month=${reportMonth}`
      );
      if (res.ok) {
        const json = await parseJsonResponse(res);
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
      const json = await parseJsonResponse(res);
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
      const json = await parseJsonResponse(res);
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
      <TechnoSaveLog plant={plant} reportMonth={reportMonth} apiBase={apiBase} refreshKey={logTick} />
      {/* RSP: Technopara Excel (final) + month-end Morning Report (tentative) */}
      {isRsp && (
        <section className={t.section} aria-labelledby="tu-sec-title">
          <h2 id="tu-sec-title" className={t.sectionTitle}>
            RSP Techno Upload
            <span className={t.sectionNote}>Technopara Excel (final), BF Department GLANCE workbook (final) and/or Month-End Morning Report (tentative) — all merged into the same table.</span>
          </h2>
          <ExtractRow
            label="RSP Technopara Excel (page1-8 sheet)"
            previewEndpoint="/api/techno/preview"
            insertEndpoint="/api/techno/insert"
            plant="RSP"
            reportMonth={reportMonth}
            apiBase={apiBase}
            onSuccess={loadData}
          />
          <ExtractRow
            label="RSP BF Department GLANCE workbook (DETAIL + per-month sheet)"
            previewEndpoint="/api/rsp-bf-glance/preview"
            insertEndpoint="/api/rsp-bf-glance/insert"
            plant="RSP"
            reportMonth={reportMonth}
            apiBase={apiBase}
            onSuccess={loadData}
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
          />
        </section>
      )}

      {/* BSP: two file extract bars (3-page-tech + OISCO) */}
      {isBsp && (
        <section className={t.section} aria-labelledby="tu-sec-title">
          <h2 id="tu-sec-title" className={t.sectionTitle}>
            BSP Techno Upload
            <span className={t.sectionNote}>All files contribute data for the same month (merged automatically). The month-end row accepts MIS-2 or PPC MIS (auto-detected, tentative data).</span>
          </h2>
          <ExtractRow
            label="BSP Flash Monthly PDF (flash-<mon>YY.pdf)"
            previewEndpoint="/api/bsp-techno/preview/flash-pdf"
            insertEndpoint="/api/bsp-techno/insert"
            plant="BSP"
            reportMonth={reportMonth}
            apiBase={apiBase}
            onSuccess={loadData}
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
          />
          <ExtractRow
            label="OISCO Excel"
            previewEndpoint="/api/bsp-techno/preview/oisco"
            insertEndpoint="/api/bsp-techno/insert"
            plant="BSP"
            reportMonth={reportMonth}
            apiBase={apiBase}
            onSuccess={loadData}
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
          />
        </section>
      )}

      {/* ISP: Technopara Excel (final) + month-end Morning Report (tentative) */}
      {isIsp && (
        <section className={t.section} aria-labelledby="tu-sec-title">
          <h2 id="tu-sec-title" className={t.sectionTitle}>
            ISP Techno Upload
            <span className={t.sectionNote}>Technopara Excel (final) and/or Month-End Morning Report (tentative, merged into the same table).</span>
          </h2>
          <ExtractRow
            label="ISP Technopara Excel"
            previewEndpoint="/api/techno/preview"
            insertEndpoint="/api/techno/insert"
            plant="ISP"
            reportMonth={reportMonth}
            apiBase={apiBase}
            onSuccess={loadData}
            bulkMonths
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
          />
        </section>
      )}

      {/* DSP: monthly PDF + month-end MCR techno page (both merged) */}
      {plant === 'DSP' && (
        <section className={t.section} aria-labelledby="tu-sec-title">
          <h2 id="tu-sec-title" className={t.sectionTitle}>
            DSP Techno Upload
            <span className={t.sectionNote}>Monthly PDF (final) and/or Month-End MCR Excel (tentative, merged into the same table).</span>
          </h2>
          <ExtractRow
            label="DSP Monthly Report PDF"
            previewEndpoint="/api/techno/preview"
            insertEndpoint="/api/techno/insert"
            plant="DSP"
            reportMonth={reportMonth}
            apiBase={apiBase}
            onSuccess={loadData}
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
            accept=".xlsx,.xls"
          />
        </section>
      )}

      {/* BSL: upload bar + BF Performance extractor. Existing DB data is
          still shown below via the shared units.length > 0 panel, same as
          every other plant. */}
      {isBsl && (
        <div>
          <section className={t.section} aria-labelledby="tu-sec-title">
            <h2 id="tu-sec-title" className={t.sectionTitle}>
              BSL Techno Upload
              <span className={t.sectionNote}>Upload Techno Excel, BF Performance PDF and/or the month-end DPR Mail Excel (tentative) — all merged automatically.</span>
            </h2>
            <ExtractRow
              label="BSL Techno Excel (.xls/.xlsx)"
              previewEndpoint="/api/techno/preview"
              insertEndpoint="/api/techno/insert"
              plant="BSL"
              reportMonth={reportMonth}
              apiBase={apiBase}
              onSuccess={loadData}
            />
            <ExtractRow
              label="BSL DPR Mail — BF Parameter sheet, month-end (tentative)"
              previewEndpoint="/api/mcr-techno/preview"
              insertEndpoint="/api/mcr-techno/insert"
              cumulativeEndpoint="/api/mcr-techno/cumulative"
              plant="BSL"
              reportMonth={reportMonth}
              apiBase={apiBase}
              onSuccess={loadData}
              accept=".xlsx"
            />
          </section>

          {/* Unified BSL BF Performance Extractor */}
          <BSLBFTechnoExtractor
            reportMonth={reportMonth}
            apiBase={apiBase}
            onSuccess={loadData}
          />
        </div>
      )}

      {!loading && units.length > 0 && (
        <div className={t.cumBar}>
          <button type="button" onClick={handleCumulativeAll} disabled={cumBusy} aria-busy={cumBusy}
                  className={`${ui.btn} ${ui.btnSecondary}`}>
            {cumBusy ? 'Calculating…' : 'Calculate Cumulative — all techno'}
          </button>
          <p>
            Computes the Cumulative (Apr→{reportMonth}) for every saved parameter of every {plant} unit and opens a
            step-by-step review window (method, production weights, month-by-month working) — nothing is saved
            until you confirm.
          </p>
        </div>
      )}
      <StatusMsg status={cumStatusShown} />

      {loading && (
        <p className={ui.meta} aria-live="polite" style={{ textAlign: 'center', padding: 40 }}>
          Loading {plant} data…
        </p>
      )}

      {!loading && units.length === 0 && (
        <div className={t.empty}>
          No techno data for <strong>{plant}</strong> — <strong>{reportMonth}</strong>.
          <br />
          {hasExtraction
            ? `Upload the ${isDsp ? 'PDF' : 'Excel'} file above to extract and save data.`
            : `${plant} extraction support coming soon.`}
        </div>
      )}

      {!loading && units.length > 0 && (
        <section className={t.browser} aria-label={`Saved techno data for ${plant} ${reportMonth}`}>
          {/* Unit list (left) */}
          <div className={t.browserUnits}>
            <div className={t.browserHead}>Units ({units.length})</div>
            {units.map(u => (
              <button key={u} type="button" aria-current={activeUnit === u ? 'true' : undefined}
                      className={t.unitTab} onClick={() => setActiveUnit(u)}>
                {u}
              </button>
            ))}
          </div>

          {/* Parameter table (right) */}
          <div className={t.browserTable}>
            {unitData && (
              <table className={t.mini} style={{ fontSize: 14 }}>
                <thead>
                  <tr>
                    <th scope="col" style={{ minWidth: 200 }}>Parameter</th>
                    <th scope="col" className={t.num} style={{ minWidth: 120 }}>Month</th>
                    <th scope="col" className={t.num} style={{ minWidth: 120 }}>Cumulative</th>
                  </tr>
                </thead>
                <tbody>
                  {Object.keys(monthParams).map((param) => {
                    const mv = monthParams[param];
                    const tv = tillParams[param];
                    const fmt = v => {
                      if (v == null || v === '') return '—';
                      if (typeof v === 'string' && v.includes(':')) return v;
                      return Number(v).toLocaleString(undefined, { maximumFractionDigits: 3 });
                    };
                    return (
                      <tr key={param}>
                        <td style={{ fontWeight: 500 }}>{param}</td>
                        <td className={`${t.num} ${mv == null ? t.muted : ''}`}>{fmt(mv)}</td>
                        <td className={`${t.num} ${tv == null ? t.muted : ''}`}>{fmt(tv)}</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            )}
          </div>
        </section>
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
function TechnoDataEntryInner() {
  const def = getDefaultPeriod();
  const [month, setMonth] = useState(def.month);
  const [year, setYear] = useState(def.year);
  const [plant, setPlant] = useState('RSP');

  const reportMonth = useMemo(() => formatMonth(year, month), [year, month]);

  const plantHint = {
    RSP: 'Upload the Technopara Excel (final), or the month-end Daily Morning Report (tentative furnace/SMS data; month verified against the report date in A2).',
    BSP: 'Upload the BSP Flash Monthly PDF (one file: coke yield, SP-2/3, BF shop + per-furnace CDI/productivity, SMS-2/3, all mills, energy — month auto-detected from the cover), BSP-3-page-Tech.xlsx and/or OISCO Excel (final), or the month-end MIS-2 / PPC MIS Excel (tentative furnace & SMS data). All merged automatically.',
    ISP: 'Upload the multi-sheet ISP Technopara Excel (final — check "Backfill all months" to extract every month from April through the selected month out of one file, e.g. a later cumulative upload), or the month-end Morning Report (tentative furnace/SMS/energy data; month verified against the report date in J5/K5). Both merged automatically.',
    DSP: 'Upload the Monthly Report PDF (final) and/or the month-end MCR Excel (tentative for-the-month values; month is verified against the report date in C1).',
    BSL: 'Upload Techno Excel and/or BF Performance PDF (final), or the month-end DPR Mail Excel (tentative furnace-wise and BF shop coke rate, nut coke, CDI, productivity, sinter/pellet in burden, HBT, O2 enrichment and slag rate from the "BF Parameter" sheet, Till Date column; month verified against the sheet dates). All merged automatically.',
  }[plant] || `${plant} extraction coming soon.`;

  return (
    <>
      <GlobalNavbar />

      <main className={ui.page} style={{ '--page-max': '1400px' }}>

        {/* ── Page title ── */}
        <div className={ui.pageHeader}>
          <h1 className={ui.pageTitle}>Techno Data — View &amp; Extract</h1>
          <p className={ui.pageLead}>
            {reportMonth} · data stored in the <code>techno_data</code>{' '}table. Looking for the Coal Consumption,
            CO2/Water/PM EPI or Power-OIS uploads (all 5 plants at once)? They&apos;ve moved
            to <a href="/data-entry/uploads" className={t.leadLink}>Uploads &amp; Extraction</a>.
          </p>
        </div>

        {/* ── Controls bar ── */}
        <div className={t.toolbar}>
          <div className={ui.field} style={{ marginBottom: 0 }}>
            <label htmlFor="tu-plant" className={ui.label}>Plant</label>
            <select id="tu-plant" className="form-control" value={plant} onChange={e => setPlant(e.target.value)}>
              {PLANTS.map(p => <option key={p} value={p}>{p}</option>)}
            </select>
          </div>
          <div className={ui.field} style={{ marginBottom: 0 }}>
            <label htmlFor="tu-month" className={ui.label}>Month</label>
            <select id="tu-month" className="form-control" value={month} onChange={e => setMonth(e.target.value)}>
              {MONTHS.map(mo => <option key={mo}>{mo}</option>)}
            </select>
          </div>
          <div className={ui.field} style={{ marginBottom: 0 }}>
            <label htmlFor="tu-year" className={ui.label}>Year</label>
            <select id="tu-year" className="form-control" value={year} onChange={e => setYear(e.target.value)}>
              {YEARS.map(y => <option key={y}>{y}</option>)}
            </select>
          </div>
          <p className={t.plantHint}>{plantHint}</p>
        </div>

        <TechnoDataPanel plant={plant} reportMonth={reportMonth} apiBase={API_BASE_URL} />
      </main>
    </>
  );
}

export default function TechnoDataEntry() {
  return (
    <RequireEditor>
      <TechnoDataEntryInner />
    </RequireEditor>
  );
}
