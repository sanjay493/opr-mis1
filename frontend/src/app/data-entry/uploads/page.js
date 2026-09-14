'use client';

import RequireEditor from '@/components/RequireEditor';

import React, { useState, useMemo } from 'react';
import GlobalNavbar from '@/components/GlobalNavbar';

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

// A long-running request is long enough to occasionally hit something that
// returns plain text instead of JSON — a proxy/dev-server error page, or a
// backend crash that slipped past its own JSON error handling. Calling
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

// ── CO2/Water/PM EPI extractor ────────────────────────────────────────────────
// Unlike a per-plant extractor, one uploaded PDF/.docx/.xlsx here covers all
// 5 plants (BSP/DSP/RSP/BSL/ISP) at once plus their shared FY annual target,
// so this is a standalone component (no `plant` prop) — /api/coal-co2/preview
// and /insert return/accept a `plants: [...]` array instead of one plant's
// `records`. Coal Consumption is NOT part of this card — see the dedicated
// Coal OMI Excel extractor below (backend/coal_co2_epi_extractor.py's module
// docstring explains why the two are kept from ever writing the same field).
const _COAL_CO2_PARAM_ROWS = [
  { key: 'sp_co2_emission', label: 'Sp. CO2 Emission', targetLabel: 'Sp. CO2 Emission' },
  { key: 'sp_water_consumption', label: 'Sp. Water Consumption', targetLabel: 'Sp. Water Consumption' },
  { key: 'sp_pm_emission', label: 'Sp. PM Emission', targetLabel: 'Sp. PM Emission' },
];

// Loose-enough float compare that "2.600000001"-style round-trip noise from
// JSON doesn't get flagged as a mismatch against a DB value that started
// life as the plain "2.6" a person typed into the manual-entry page.
function _valuesDiffer(a, b) {
  if (a === null || a === undefined || b === null || b === undefined) return false;
  return Math.abs(Number(a) - Number(b)) > 1e-6;
}

// One Extracted-vs-Existing-in-DB table for a single month (used for the
// main report month's Till Month, and — when the source report carries one
// — its Comparable-Prior-Year month's Month and Till Month) — shared via
// the `field` prop. `sail` (optional, {month:{}, till_month:{}}) renders an
// extra, non-editable "SAIL (reported)" column from the report's own SAIL
// row — informational only, since SAIL is never saved from this report
// (see backend module docstring): no existing-DB comparison for it.
function EpiCompareTable({ plants, field, sail, warnStyle, cellStyle, labelCellStyle, fmt }) {
  const sailCellStyle = { ...cellStyle, color: '#5f6368', fontStyle: 'italic' };
  return (
    <div style={{ overflowX: 'auto' }}>
      <table style={{ borderCollapse: 'collapse', width: '100%', background: '#fff', borderRadius: 6, overflow: 'hidden' }}>
        <thead>
          <tr style={{ background: '#f8f9fa' }}>
            <th style={{ ...labelCellStyle, fontWeight: 700, textAlign: 'left' }}>Parameter</th>
            {PLANTS.map(p => <th key={p} style={{ ...cellStyle, fontWeight: 700 }}>{p}</th>)}
            {sail && <th style={{ ...cellStyle, fontWeight: 700 }} title="Reported by EMD, not saved — computed separately elsewhere">SAIL (reported)</th>}
          </tr>
        </thead>
        <tbody>
          {_COAL_CO2_PARAM_ROWS.map(row => (
            <tr key={row.key}>
              <td style={labelCellStyle}>{row.label}</td>
              {PLANTS.map(p => {
                const rec = plants.find(r => r.plant === p);
                const extracted = rec?.techno_json?.[field]?.[row.key];
                const existing = rec?.existing?.[field]?.[row.key];
                const mismatch = _valuesDiffer(extracted, existing);
                return (
                  <td key={p} style={cellStyle}>
                    {fmt(extracted)}
                    {mismatch && (
                      <span style={warnStyle} title={`Existing DB value: ${existing}`}>⚠</span>
                    )}
                  </td>
                );
              })}
              {sail && <td style={sailCellStyle}>{fmt(sail[field]?.[row.key])}</td>}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function CoalCo2ExtractRow({ reportMonth, apiBase, onSuccess }) {
  const [file, setFile] = React.useState(null);
  const [busy, setBusy] = React.useState(false);
  const [status, setStatus] = React.useState(null);
  const [preview, setPreview] = React.useState(null);
  const [includeCply, setIncludeCply] = React.useState(false);
  const inputRef = React.useRef();

  React.useEffect(() => {
    setFile(null);
    setStatus(null);
    setPreview(null);
    setIncludeCply(false);
    if (inputRef.current) inputRef.current.value = '';
  }, [reportMonth]);

  const handlePreview = async () => {
    if (!file) return;
    setBusy(true);
    setStatus(null);
    setPreview(null);
    setIncludeCply(false);
    const form = new FormData();
    form.append('file', file);
    form.append('report_month', reportMonth);
    try {
      const res = await fetch(`${apiBase}/api/coal-co2/preview`, { method: 'POST', body: form });
      const json = await parseJsonResponse(res);
      if (!res.ok) throw new Error(json.detail || 'Preview failed');
      setPreview(json);
    } catch (err) {
      setStatus({ type: 'error', text: err.message });
    } finally {
      setBusy(false);
    }
  };

  const doSave = async (confirmReplace) => {
    const res = await fetch(`${apiBase}/api/coal-co2/insert`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        report_month: preview.report_month,
        source_file: preview.source_file,
        plants: preview.plants,
        targets: preview.targets,
        ...(includeCply && preview.cply
          ? { cply: { report_month: preview.cply.report_month, plants: preview.cply.plants } }
          : {}),
        ...(confirmReplace ? { confirm_replace: true } : {}),
      }),
    });
    return { res, json: await parseJsonResponse(res) };
  };

  const handleConfirmSave = async () => {
    if (!preview) return;
    setBusy(true);
    setStatus(null);
    try {
      let { res, json } = await doSave(false);
      if (res.status === 409) {
        if (!window.confirm(`${json.detail}\n\nReplace the existing values?`)) {
          setBusy(false);
          return;
        }
        ({ res, json } = await doSave(true));
      }
      if (!res.ok) throw new Error(json.detail || 'Save failed');
      setStatus({
        type: 'success',
        text: `✓ Saved ${json.plants_saved.length} plants for ${json.report_month}`
          + (json.targets_saved.length ? ` + FY targets for ${json.targets_saved.length}` : '')
          + (json.cply_plants_saved.length ? ` + ${json.cply_plants_saved.length} plants for ${json.cply_report_month}` : ''),
      });
      setPreview(null);
      setFile(null);
      setIncludeCply(false);
      if (inputRef.current) inputRef.current.value = '';
      onSuccess();
    } catch (err) {
      setStatus({ type: 'error', text: err.message });
    } finally {
      setBusy(false);
    }
  };

  const handleCancel = () => { setPreview(null); setStatus(null); setIncludeCply(false); };

  const fmt = (v) => (v === null || v === undefined ? '—' : v);
  const cellStyle = { padding: '4px 8px', fontSize: 12.5, textAlign: 'right', borderBottom: '1px solid #f1f3f4' };
  const labelCellStyle = { padding: '4px 8px', fontSize: 12.5, borderBottom: '1px solid #f1f3f4', color: '#374151' };
  const warnStyle = { color: '#b45309', fontWeight: 700, marginLeft: 4, cursor: 'help' };

  return (
    <div style={{
      marginBottom: 16, padding: '12px 14px',
      background: '#f0fdf4', border: '1px solid #86efac', borderRadius: 8,
    }}>
      <div style={{ fontSize: 14, fontWeight: 700, color: '#166534', marginBottom: 4 }}>
        CO2/Water/PM EPI Report — all 5 plants at once
      </div>
      <div style={{ fontSize: 12, color: '#5f6368', marginBottom: 10 }}>
        One "Major Environmental Performance Indicators (EPIs)" report (PDF, the "EMD Flash Report" .docx, the newer
        "Major EPIs" .docx, or the "Major EPIs" .xlsx workbook) covers BSP/DSP/RSP/BSL/ISP for {reportMonth}, plus
        their shared FY annual target (not carried by the .xlsx, or by the older Flash Report .docx). The Flash
        Report .docx carries only Sp. CO2 Emission and Sp. Water Consumption (no Sp. PM Emission) — those fields are
        left as-is. Coal Consumption is handled by the dedicated Coal OMI extractor below, not here. Saved into the
        same techno_data table (unit=&quot;General&quot;) as the rest of the Techno Data page. ⚠ next to a value
        means it differs from what&apos;s already saved for that month — hover for the existing figure.
      </div>
      <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap' }}>
        <input ref={inputRef} type="file" accept=".pdf,.docx,.xlsx"
          onChange={e => { setFile(e.target.files[0]); setStatus(null); setPreview(null); }}
          style={{ fontSize: 13, flex: 1, minWidth: 200 }}
          suppressHydrationWarning
        />
        {!preview && (
          <button onClick={handlePreview} disabled={!file || busy}
            style={{
              padding: '7px 18px', background: busy ? '#5f6368' : '#16a34a',
              color: '#fff', border: 'none', borderRadius: 6, fontSize: 13,
              cursor: file && !busy ? 'pointer' : 'not-allowed', fontWeight: 600, whiteSpace: 'nowrap',
            }}
          >
            {busy ? 'Extracting…' : 'Preview'}
          </button>
        )}
        {preview && (
          <>
            <button onClick={handleConfirmSave} disabled={busy}
              style={{
                padding: '7px 18px', background: busy ? '#5f6368' : '#16a34a',
                color: '#fff', border: 'none', borderRadius: 6, fontSize: 13,
                cursor: busy ? 'not-allowed' : 'pointer', fontWeight: 600, whiteSpace: 'nowrap',
              }}
            >
              {busy ? 'Saving…' : 'Confirm & Save'}
            </button>
            <button onClick={handleCancel} disabled={busy}
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

      <div style={{ marginTop: 10 }}><StatusMsg status={status} /></div>

      {preview && (
        <div style={{ marginTop: 6 }}>
          {preview.has_existing && (
            <div style={{
              marginBottom: 8, padding: '6px 12px', borderRadius: 6, fontSize: 12,
              background: '#fffbeb', color: '#92400e', border: '1px solid #fde68a',
            }}>
              ⚠ {preview.report_month} already has values for {preview.existing_conflicts.map(c => c.plant).join(', ')} —
              saving will ask to confirm overwriting them.
            </div>
          )}
          <div style={{ fontSize: 11.5, fontWeight: 700, color: '#374151', marginBottom: 4 }}>
            Month ({preview.report_month})
          </div>
          <div style={{ overflowX: 'auto' }}>
            <table style={{ borderCollapse: 'collapse', width: '100%', background: '#fff', borderRadius: 6, overflow: 'hidden' }}>
              <thead>
                <tr style={{ background: '#f8f9fa' }}>
                  <th style={{ ...labelCellStyle, fontWeight: 700, textAlign: 'left' }}>Parameter</th>
                  {PLANTS.map(p => <th key={p} style={{ ...cellStyle, fontWeight: 700 }}>{p}</th>)}
                  <th style={{ ...cellStyle, fontWeight: 700 }} title="Reported by EMD, not saved — computed separately elsewhere">SAIL (reported)</th>
                  <th style={{ ...cellStyle, fontWeight: 700 }}>FY Target (SAIL)</th>
                </tr>
              </thead>
              <tbody>
                {_COAL_CO2_PARAM_ROWS.map(row => {
                  const sailTarget = row.targetLabel
                    ? preview.targets?.SAIL?.[row.targetLabel]?.value
                    : null;
                  return (
                    <tr key={row.key}>
                      <td style={labelCellStyle}>{row.label}</td>
                      {PLANTS.map(p => {
                        const rec = preview.plants.find(r => r.plant === p);
                        const extracted = rec?.techno_json?.month?.[row.key];
                        const existing = rec?.existing?.month?.[row.key];
                        const mismatch = _valuesDiffer(extracted, existing);
                        return (
                          <td key={p} style={cellStyle}>
                            {fmt(extracted)}
                            {mismatch && (
                              <span style={warnStyle} title={`Existing DB value: ${existing}`}>⚠</span>
                            )}
                          </td>
                        );
                      })}
                      <td style={{ ...cellStyle, color: '#5f6368', fontStyle: 'italic' }}>{fmt(preview.sail?.month?.[row.key])}</td>
                      <td style={cellStyle}>{fmt(sailTarget)}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>

          <div style={{ fontSize: 11.5, fontWeight: 700, color: '#374151', margin: '10px 0 4px' }}>
            Till Month (FY cumulative through {preview.report_month})
          </div>
          <EpiCompareTable plants={preview.plants} field="till_month" sail={preview.sail}
            warnStyle={warnStyle} cellStyle={cellStyle} labelCellStyle={labelCellStyle} fmt={fmt} />

          {preview.cply && (
            <div style={{ marginTop: 14, paddingTop: 12, borderTop: '1px dashed #86efac' }}>
              <label style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 12.5, fontWeight: 600, color: '#166534', marginBottom: 8, cursor: 'pointer' }}>
                <input type="checkbox" checked={includeCply} onChange={e => setIncludeCply(e.target.checked)} />
                Also update Comparable-Prior-Year data for {preview.cply.report_month} (this report&apos;s own year-over-year column)
              </label>
              {preview.cply.has_existing && (
                <div style={{
                  marginBottom: 8, padding: '6px 12px', borderRadius: 6, fontSize: 12,
                  background: '#fffbeb', color: '#92400e', border: '1px solid #fde68a',
                }}>
                  ⚠ {preview.cply.report_month} already has values for {preview.cply.existing_conflicts.map(c => c.plant).join(', ')} —
                  saving will ask to confirm overwriting them.
                </div>
              )}
              <div style={{ fontSize: 11.5, fontWeight: 700, color: '#374151', marginBottom: 4 }}>
                CPLY Month ({preview.cply.report_month})
              </div>
              <EpiCompareTable plants={preview.cply.plants} field="month" sail={preview.cply.sail}
                warnStyle={warnStyle} cellStyle={cellStyle} labelCellStyle={labelCellStyle} fmt={fmt} />
              <div style={{ fontSize: 11.5, fontWeight: 700, color: '#374151', margin: '8px 0 4px' }}>
                CPLY Till Month (FY cumulative through {preview.cply.report_month})
              </div>
              <EpiCompareTable plants={preview.cply.plants} field="till_month" sail={preview.cply.sail}
                warnStyle={warnStyle} cellStyle={cellStyle} labelCellStyle={labelCellStyle} fmt={fmt} />
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// ── Coal OMI Excel extractor ─────────────────────────────────────────────────
// The sole source of Coal Consumption data (Indigenous PCC/MCC, Imported
// Hard/Soft coking coal) — read directly from the "Coal OMI - <Mon><YY>.xlsx"
// workbook's decimal cells instead of a PDF table, plus till_month (computed
// server-side by summing this FY's monthly values) and a new SAIL-only
// Receipt/Consumption/Stock record. See backend/api_coal_omi_techno.py.
// (The CO2/Water/PM EPI card above used to also extract these same 4 keys
// from some report formats' own Coal Consumption table, but that's been
// removed — see coal_co2_epi_extractor.py's module docstring — so this is
// now the only writer for them, and the two cards never race each other.)
const _COAL_OMI_ROWS = [
  { key: 'indigenous_pcc', label: 'Indigenous PCC' },
  { key: 'indigenous_mcc', label: 'Indigenous MCC' },
  { key: 'imported_hard_coal', label: 'Imported Hard Coal' },
  { key: 'imported_soft_coal', label: 'Imported Soft Coal' },
];
const _COAL_OMI_PLANTS = ['BSP', 'DSP', 'RSP', 'BSL', 'ISP'];

function CoalOmiExtractRow({ reportMonth, apiBase, onSuccess }) {
  const [file, setFile] = React.useState(null);
  const [busy, setBusy] = React.useState(false);
  const [status, setStatus] = React.useState(null);
  const [preview, setPreview] = React.useState(null);
  const inputRef = React.useRef();

  React.useEffect(() => {
    setFile(null);
    setStatus(null);
    setPreview(null);
    if (inputRef.current) inputRef.current.value = '';
  }, [reportMonth]);

  const handlePreview = async () => {
    if (!file) return;
    setBusy(true);
    setStatus(null);
    setPreview(null);
    const form = new FormData();
    form.append('file', file);
    form.append('report_month', reportMonth);
    try {
      const res = await fetch(`${apiBase}/api/coal-omi/preview`, { method: 'POST', body: form });
      const json = await parseJsonResponse(res);
      if (!res.ok) throw new Error(json.detail || 'Preview failed');
      setPreview(json);
    } catch (err) {
      setStatus({ type: 'error', text: err.message });
    } finally {
      setBusy(false);
    }
  };

  const doSave = async (confirmReplace) => {
    const res = await fetch(`${apiBase}/api/coal-omi/insert`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        report_month: preview.report_month,
        source_file: preview.source_file,
        plants: preview.plants,
        sail: preview.sail,
        ois2: preview.ois2,
        detail: preview.detail,
        ...(confirmReplace ? { confirm_replace: true } : {}),
      }),
    });
    return { res, json: await parseJsonResponse(res) };
  };

  const handleConfirmSave = async () => {
    if (!preview) return;
    setBusy(true);
    setStatus(null);
    try {
      let { res, json } = await doSave(false);
      if (res.status === 409) {
        if (!window.confirm(`${json.detail}\n\nReplace the existing values?`)) {
          setBusy(false);
          return;
        }
        ({ res, json } = await doSave(true));
      }
      if (!res.ok) throw new Error(json.detail || 'Save failed');
      setStatus({ type: 'success', text: `✓ Saved ${json.saved.length} records for ${json.report_month}` });
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

  const handleCancel = () => { setPreview(null); setStatus(null); };

  const fmt = (v) => (v === null || v === undefined ? '—' : v);
  const cellStyle = { padding: '4px 8px', fontSize: 12.5, textAlign: 'right', borderBottom: '1px solid #f1f3f4' };
  const labelCellStyle = { padding: '4px 8px', fontSize: 12.5, borderBottom: '1px solid #f1f3f4', color: '#374151' };
  const warnStyle = { color: '#b45309', fontWeight: 700, marginLeft: 4, cursor: 'help' };

  const tillMismatch = (plant, key) => (preview?.validation_warnings || [])
    .find(w => w.type === 'till_month_mismatch' && w.plant === plant && w.key === key);
  const sailMismatch = (key) => (preview?.validation_warnings || [])
    .find(w => w.type === 'sail_mismatch' && w.key === key);

  return (
    <div style={{
      marginBottom: 16, padding: '12px 14px',
      background: '#eff6ff', border: '1px solid #bfdbfe', borderRadius: 8,
    }}>
      <div style={{ fontSize: 14, fontWeight: 700, color: '#1e40af', marginBottom: 4 }}>
        Coal OMI Report (Excel) — higher-precision Coal Consumption + Receipt/Stock — all 5 plants at once
      </div>
      <div style={{ fontSize: 12, color: '#5f6368', marginBottom: 10 }}>
        The monthly "Coal OMI" workbook (2 sheets: coking coal consumption, and SAIL-level receipt/consumption/stock).
        Till-month is computed as a running sum of April through {reportMonth} from what's already saved — the report's
        own printed cumulative is shown only as a cross-check, flagged (⚠) if it disagrees. SAIL is computed as the sum
        of the 5 plants, cross-checked against the report's own SAIL row the same way.
      </div>
      <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap' }}>
        <input ref={inputRef} type="file" accept=".xlsx"
          onChange={e => { setFile(e.target.files[0]); setStatus(null); setPreview(null); }}
          style={{ fontSize: 13, flex: 1, minWidth: 200 }}
          suppressHydrationWarning
        />
        {!preview && (
          <button onClick={handlePreview} disabled={!file || busy}
            style={{
              padding: '7px 18px', background: busy ? '#5f6368' : '#1a73e8',
              color: '#fff', border: 'none', borderRadius: 6, fontSize: 13,
              cursor: file && !busy ? 'pointer' : 'not-allowed', fontWeight: 600, whiteSpace: 'nowrap',
            }}
          >
            {busy ? 'Extracting…' : 'Preview'}
          </button>
        )}
        {preview && (
          <>
            <button onClick={handleConfirmSave} disabled={busy}
              style={{
                padding: '7px 18px', background: busy ? '#5f6368' : '#1a73e8',
                color: '#fff', border: 'none', borderRadius: 6, fontSize: 13,
                cursor: busy ? 'not-allowed' : 'pointer', fontWeight: 600, whiteSpace: 'nowrap',
              }}
            >
              {busy ? 'Saving…' : 'Confirm & Save'}
            </button>
            <button onClick={handleCancel} disabled={busy}
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

      <div style={{ marginTop: 10 }}><StatusMsg status={status} /></div>

      {preview && (
        <div style={{ marginTop: 6 }}>
          {preview.has_existing && (
            <div style={{
              marginBottom: 8, padding: '6px 12px', borderRadius: 6, fontSize: 12,
              background: '#fffbeb', color: '#92400e', border: '1px solid #fde68a',
            }}>
              ⚠ {preview.report_month} already has values for {preview.existing_conflicts.map(c => `${c.plant}/${c.unit}`).join(', ')} —
              saving will ask to confirm overwriting them.
            </div>
          )}

          <div style={{ overflowX: 'auto' }}>
            <table style={{ borderCollapse: 'collapse', width: '100%', background: '#fff', borderRadius: 6, overflow: 'hidden', marginBottom: 10 }}>
              <thead>
                <tr style={{ background: '#f8f9fa' }}>
                  <th style={{ ...labelCellStyle, fontWeight: 700, textAlign: 'left' }}>Parameter / Plant</th>
                  <th style={{ ...cellStyle, fontWeight: 700 }}>Month</th>
                  <th style={{ ...cellStyle, fontWeight: 700 }}>Till Month (computed)</th>
                </tr>
              </thead>
              <tbody>
                {_COAL_OMI_ROWS.map(row => (
                  <React.Fragment key={row.key}>
                    <tr>
                      <td colSpan={3} style={{ ...labelCellStyle, fontWeight: 700, background: '#eff6ff' }}>{row.label}</td>
                    </tr>
                    {_COAL_OMI_PLANTS.map(p => {
                      const rec = preview.plants.find(r => r.plant === p);
                      const mismatch = tillMismatch(p, row.key);
                      return (
                        <tr key={p}>
                          <td style={{ ...labelCellStyle, paddingLeft: 20 }}>{p}</td>
                          <td style={cellStyle}>{fmt(rec?.techno_json?.month?.[row.key])}</td>
                          <td style={cellStyle}>
                            {fmt(rec?.techno_json?.till_month?.[row.key])}
                            {mismatch && (
                              <span style={warnStyle} title={`Report's own cumulative: ${mismatch.reported} (diff ${mismatch.diff})`}>⚠</span>
                            )}
                          </td>
                        </tr>
                      );
                    })}
                    <tr>
                      <td style={{ ...labelCellStyle, paddingLeft: 20, fontWeight: 700 }}>SAIL (computed sum)</td>
                      <td style={{ ...cellStyle, fontWeight: 700 }}>
                        {fmt(preview.sail?.techno_json?.month?.[row.key])}
                        {sailMismatch(row.key) && (
                          <span style={warnStyle} title={`Report's own SAIL row: ${sailMismatch(row.key).reported} (diff ${sailMismatch(row.key).diff})`}>⚠</span>
                        )}
                      </td>
                      <td style={{ ...cellStyle, fontWeight: 700 }}>{fmt(preview.sail?.techno_json?.till_month?.[row.key])}</td>
                    </tr>
                  </React.Fragment>
                ))}
              </tbody>
            </table>
          </div>

          <div style={{ fontSize: 12.5, fontWeight: 700, color: '#374151', marginBottom: 4 }}>
            Receipt / Consumption / Stock (SAIL, {preview.ois2?.techno_json?.month?.stock_as_of_month || reportMonth})
          </div>
          <div style={{ overflowX: 'auto' }}>
            <table style={{ borderCollapse: 'collapse', width: '100%', background: '#fff', borderRadius: 6, overflow: 'hidden' }}>
              <tbody>
                {[
                  ['Receipt Plan (TPD)', 'receipt_plan_indigenous', 'receipt_plan_imported', 'receipt_plan_total'],
                  ['Receipt Actual (TPD)', 'receipt_actual_indigenous', 'receipt_actual_imported', 'receipt_actual_total'],
                  ['Consumption Actual (\'000 T)', 'consumption_actual_indigenous', 'consumption_actual_imported', 'consumption_actual_total'],
                  ['Consumption Average (TPD)', 'consumption_avg_indigenous', 'consumption_avg_imported', 'consumption_avg_total'],
                  ['Stock (\'000 T)', 'stock_indigenous', 'stock_imported', 'stock_total'],
                ].map(([label, ind, imp, tot]) => {
                  const m = preview.ois2?.techno_json?.month || {};
                  return (
                    <tr key={label}>
                      <td style={labelCellStyle}>{label}</td>
                      <td style={cellStyle}>Ind: {fmt(m[ind])}</td>
                      <td style={cellStyle}>Imp: {fmt(m[imp])}</td>
                      <td style={{ ...cellStyle, fontWeight: 700 }}>Total: {fmt(m[tot])}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
          {(() => {
            const hist = preview.ois2?.techno_json?.month?.stock_history || {};
            const months = Object.keys(hist).sort();
            return months.length > 0 && (
              <div style={{ fontSize: 11.5, color: '#5f6368', margin: '4px 0 10px' }}>
                This file's OIS-2 sheet also carries stock for {months.length} month{months.length === 1 ? '' : 's'}
                {' '}({months.join(', ')}) — all of them are saved, backfilling table (C) on the report page for
                any of those months that don&apos;t already have a figure.
              </div>
            );
          })()}

          <div style={{ fontSize: 12.5, fontWeight: 700, color: '#374151', margin: '10px 0 4px' }}>
            Consumption of Coking Coal and CDI Coal (per plant — feeds the landscape report page)
          </div>
          <div style={{ overflowX: 'auto' }}>
            <table style={{ borderCollapse: 'collapse', width: '100%', background: '#fff', borderRadius: 6, overflow: 'hidden' }}>
              <thead>
                <tr style={{ background: '#f8f9fa' }}>
                  <th style={{ ...labelCellStyle, fontWeight: 700, textAlign: 'left' }}>Plant</th>
                  <th style={{ ...cellStyle, fontWeight: 700 }}>Total Coking Coal</th>
                  <th style={{ ...cellStyle, fontWeight: 700 }}>CDI Coal</th>
                  <th style={{ ...cellStyle, fontWeight: 700 }}>Imported Blend %</th>
                  <th style={{ ...cellStyle, fontWeight: 700 }}>Imported Soft %</th>
                </tr>
              </thead>
              <tbody>
                {(preview.detail || []).map(rec => (
                  <tr key={rec.plant}>
                    <td style={{ ...labelCellStyle, fontWeight: rec.plant === 'SAIL' ? 700 : 400 }}>{rec.plant}</td>
                    <td style={cellStyle}>{fmt(rec.techno_json?.month?.total_coking_coal)}</td>
                    <td style={cellStyle}>{fmt(rec.techno_json?.month?.cdi_coal)}</td>
                    <td style={cellStyle}>{fmt(rec.techno_json?.month?.imported_total_pct)}%</td>
                    <td style={cellStyle}>{fmt(rec.techno_json?.month?.soft_pct)}%</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}

// Power-OIS monthly workbook — feeds the dedicated power_data_table (not
// techno_data), see backend/api_power_omi.py and
// excel_extractors/excel_extractor_power_omi.py. Unlike CoalOmiExtractRow
// above, this doesn't key off reportMonth at all — a single upload spans
// the whole FY (PLAN is pre-filled for all 12 months, ACTUAL only as far as
// the report has actually progressed), so the preview shows every month
// found in the file rather than just the selected one.
const _POWER_OMI_PLANTS = ['BSP', 'DSP', 'RSP', 'BSL', 'ISP', 'SSP', 'VISP', 'CFP', 'SAIL'];

function PowerOmiExtractRow({ apiBase, onSuccess }) {
  const [file, setFile] = React.useState(null);
  const [busy, setBusy] = React.useState(false);
  const [status, setStatus] = React.useState(null);
  const [preview, setPreview] = React.useState(null);
  const inputRef = React.useRef();

  const handlePreview = async () => {
    if (!file) return;
    setBusy(true);
    setStatus(null);
    setPreview(null);
    const form = new FormData();
    form.append('file', file);
    try {
      const res = await fetch(`${apiBase}/api/power-omi/preview`, { method: 'POST', body: form });
      const json = await parseJsonResponse(res);
      if (!res.ok) throw new Error(json.detail || 'Preview failed');
      setPreview(json);
    } catch (err) {
      setStatus({ type: 'error', text: err.message });
    } finally {
      setBusy(false);
    }
  };

  const doSave = async (confirmReplace) => {
    const res = await fetch(`${apiBase}/api/power-omi/insert`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        records: preview.records,
        source_file: preview.source_file,
        ...(confirmReplace ? { confirm_replace: true } : {}),
      }),
    });
    return { res, json: await parseJsonResponse(res) };
  };

  const handleConfirmSave = async () => {
    if (!preview) return;
    setBusy(true);
    setStatus(null);
    try {
      let { res, json } = await doSave(false);
      if (res.status === 409) {
        if (!window.confirm(`${json.detail}\n\nReplace the existing values?`)) {
          setBusy(false);
          return;
        }
        ({ res, json } = await doSave(true));
      }
      if (!res.ok) throw new Error(json.detail || 'Save failed');
      setStatus({ type: 'success', text: `✓ Saved ${json.saved} value(s)` });
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

  const handleCancel = () => { setPreview(null); setStatus(null); };

  const cellStyle = { padding: '4px 8px', fontSize: 12.5, textAlign: 'right', borderBottom: '1px solid #f1f3f4' };
  const labelCellStyle = { padding: '4px 8px', fontSize: 12.5, borderBottom: '1px solid #f1f3f4', color: '#374151' };
  const fmt = (v) => (v === null || v === undefined ? '—' : v);

  // "Actual Total" (MW) per plant per month — a representative slice of the
  // ~24 columns actually saved, just for a sanity-check glance before commit.
  const actualByPlantMonth = React.useMemo(() => {
    if (!preview) return {};
    const out = {};
    for (const rec of preview.records) {
      if (rec.item_name !== 'actual_total') continue;
      out[rec.plant_name] = out[rec.plant_name] || {};
      out[rec.plant_name][rec.report_month] = rec.value;
    }
    return out;
  }, [preview]);

  return (
    <div style={{
      marginBottom: 16, padding: '12px 14px',
      background: '#eff6ff', border: '1px solid #bfdbfe', borderRadius: 8,
    }}>
      <div style={{ fontSize: 14, fontWeight: 700, color: '#1e40af', marginBottom: 4 }}>
        Power-OIS Report (Excel) — Monthly Summary of Power Data — all plants, whole FY at once
      </div>
      <div style={{ fontSize: 12, color: '#5f6368', marginBottom: 10 }}>
        The monthly "Power-OIS" workbook — one sheet per FY, PLAN/ACTUAL generation, grid transactions,
        specific power consumption, and a previous-FY comparison, per plant per month. Not tied to the
        report month selector above — every month found in the file is extracted at once.
      </div>
      <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap' }}>
        <input ref={inputRef} type="file" accept=".xlsx"
          onChange={e => { setFile(e.target.files[0]); setStatus(null); setPreview(null); }}
          style={{ fontSize: 13, flex: 1, minWidth: 200 }}
          suppressHydrationWarning
        />
        {!preview && (
          <button onClick={handlePreview} disabled={!file || busy}
            style={{
              padding: '7px 18px', background: busy ? '#5f6368' : '#1a73e8',
              color: '#fff', border: 'none', borderRadius: 6, fontSize: 13,
              cursor: file && !busy ? 'pointer' : 'not-allowed', fontWeight: 600, whiteSpace: 'nowrap',
            }}
          >
            {busy ? 'Extracting…' : 'Preview'}
          </button>
        )}
        {preview && (
          <>
            <button onClick={handleConfirmSave} disabled={busy}
              style={{
                padding: '7px 18px', background: busy ? '#5f6368' : '#1a73e8',
                color: '#fff', border: 'none', borderRadius: 6, fontSize: 13,
                cursor: busy ? 'not-allowed' : 'pointer', fontWeight: 600, whiteSpace: 'nowrap',
              }}
            >
              {busy ? 'Saving…' : 'Confirm & Save'}
            </button>
            <button onClick={handleCancel} disabled={busy}
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

      <div style={{ marginTop: 10 }}><StatusMsg status={status} /></div>

      {preview && (
        <div style={{ marginTop: 6 }}>
          {preview.has_existing && (
            <div style={{
              marginBottom: 8, padding: '6px 12px', borderRadius: 6, fontSize: 12,
              background: '#fffbeb', color: '#92400e', border: '1px solid #fde68a',
            }}>
              ⚠ {preview.existing_conflicts_count} value(s) already exist for months in this file —
              saving will ask to confirm overwriting them.
            </div>
          )}
          {preview.warnings.length > 0 && (
            <div style={{
              marginBottom: 8, padding: '6px 12px', borderRadius: 6, fontSize: 12,
              background: '#fef2f2', color: '#991b1b', border: '1px solid #fecaca',
            }}>
              {preview.warnings.map((w, i) => <div key={i}>⚠ {w}</div>)}
            </div>
          )}
          <div style={{ fontSize: 12.5, color: '#374151', marginBottom: 6 }}>
            {preview.record_count} value(s) found across {preview.months.length} month(s)
            ({preview.months[0]} – {preview.months[preview.months.length - 1]}) for {preview.plants_found.length} plant(s).
          </div>

          <div style={{ fontSize: 12.5, fontWeight: 700, color: '#374151', marginBottom: 4 }}>
            Actual Total Generation (MW) — sanity check
          </div>
          <div style={{ overflowX: 'auto' }}>
            <table style={{ borderCollapse: 'collapse', width: '100%', background: '#fff', borderRadius: 6, overflow: 'hidden' }}>
              <thead>
                <tr style={{ background: '#f8f9fa' }}>
                  <th style={{ ...labelCellStyle, fontWeight: 700, textAlign: 'left' }}>Plant</th>
                  {preview.months.map(mo => (
                    <th key={mo} style={{ ...cellStyle, fontWeight: 700 }}>{mo}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {_POWER_OMI_PLANTS.filter(p => preview.plants_found.includes(p)).map(p => (
                  <tr key={p}>
                    <td style={{ ...labelCellStyle, fontWeight: p === 'SAIL' ? 700 : 400 }}>{p}</td>
                    {preview.months.map(mo => (
                      <td key={mo} style={cellStyle}>{fmt(actualByPlantMonth[p]?.[mo])}</td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}

// ── Main page ─────────────────────────────────────────────────────────────────
function UploadsExtractionInner() {
  const def = getDefaultPeriod();
  const [month, setMonth] = useState(def.month);
  const [year, setYear] = useState(def.year);

  const reportMonth = useMemo(() => formatMonth(year, month), [year, month]);

  return (
    <div style={{ height: '100vh', display: 'flex', flexDirection: 'column', background: '#ffffff' }}>
      <GlobalNavbar />

      <div style={{ flex: 1, overflow: 'auto', maxWidth: 1400, margin: '0 auto', padding: '22px 20px', width: '100%', boxSizing: 'border-box' }}>

        {/* ── Page title ── */}
        <div style={{ marginBottom: 18 }}>
          <h2 style={{ fontSize: '1.6rem', fontWeight: 700, color: '#202124', margin: '0 0 4px' }}>
            Uploads &amp; Extraction — Coal, CO2/Water/PM &amp; Power
          </h2>
          <span style={{ fontSize: 13, color: '#5f6368' }}>
            All-5-plants-at-once report uploads: coal consumption, CO2/Water/PM EPI, and power. Written into
            {' '}<code style={{ fontSize: 12 }}>techno_data</code> (coal/CO2/water/PM) and <code style={{ fontSize: 12 }}>power_data_table</code> (power).
          </span>
        </div>

        {/* ── Controls bar ── */}
        <div style={{
          display: 'flex', gap: 10, alignItems: 'center', flexWrap: 'wrap',
          marginBottom: 18, background: '#fff', border: '1px solid #dadce0',
          borderRadius: 8, padding: '14px 18px',
        }}>
          <label style={{ fontSize: 13, fontWeight: 600, color: '#374151' }}>Month</label>
          <select value={month} onChange={e => setMonth(e.target.value)}
                  style={{ padding: '7px 10px', fontSize: 14, border: '1px solid #d1d5db', borderRadius: 4 }}>
            {MONTHS.map(m => <option key={m}>{m}</option>)}
          </select>
          <select value={year} onChange={e => setYear(e.target.value)}
                  style={{ padding: '7px 10px', fontSize: 14, border: '1px solid #d1d5db', borderRadius: 4 }}>
            {YEARS.map(y => <option key={y}>{y}</option>)}
          </select>

          <span style={{ marginLeft: 'auto', fontSize: 13, color: '#5f6368' }}>
            {reportMonth} — used by the Coal Consumption/CO2/Water/PM report cards below (Power-OIS below extracts every month from its own workbook regardless of this selection).
          </span>
        </div>

        <CoalCo2ExtractRow reportMonth={reportMonth} apiBase={API_BASE_URL} onSuccess={() => {}} />

        <CoalOmiExtractRow reportMonth={reportMonth} apiBase={API_BASE_URL} onSuccess={() => {}} />

        <PowerOmiExtractRow apiBase={API_BASE_URL} onSuccess={() => {}} />
      </div>
    </div>
  );
}

export default function UploadsExtractionPage() {
  return (
    <RequireEditor>
      <UploadsExtractionInner />
    </RequireEditor>
  );
}
