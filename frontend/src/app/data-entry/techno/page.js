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
  return (
    <div style={{
      padding: '8px 14px', borderRadius: 6, marginBottom: 14, fontSize: 13,
      background: status.type === 'success' ? '#f0fdf4' : '#fef2f2',
      color:      status.type === 'success' ? '#166534'  : '#991b1b',
      border: `1px solid ${status.type === 'success' ? '#86efac' : '#fca5a5'}`,
    }}>
      {status.text}
    </div>
  );
}

// ── Compact review table shown between Preview and Confirm & Save ─────────────
function PreviewReview({ preview }) {
  const [activeUnit, setActiveUnit] = React.useState(preview.records[0]?.unit || null);
  const rec = preview.records.find(r => r.unit === activeUnit) || preview.records[0];
  const monthParams = rec?.techno_json?.month || {};
  const tillParams  = rec?.techno_json?.till_month || {};
  const dbMonthParams = rec?.db_json?.month || {};
  const dbTillParams  = rec?.db_json?.till_month || {};
  const allParams = Array.from(new Set([...Object.keys(monthParams), ...Object.keys(dbMonthParams), ...Object.keys(dbTillParams)]));
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
          {preview.records.map(r => (
            <button key={r.unit} onClick={() => setActiveUnit(r.unit)}
              style={{
                display: 'block', width: '100%', padding: '6px 10px', textAlign: 'left',
                background: activeUnit === r.unit ? '#e8f0fe' : 'transparent',
                color: activeUnit === r.unit ? '#174ea6' : '#5f6368',
                border: 'none', borderBottom: '1px solid #f8f9fa', fontSize: 12,
                fontWeight: activeUnit === r.unit ? 700 : 400, cursor: 'pointer',
              }}
            >
              {r.unit}
            </button>
          ))}
        </div>
        <div style={{ flex: 1, overflowY: 'auto', background: '#fff' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12.5 }}>
            <thead>
              <tr style={{ background: '#f8f9fa' }}>
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
                return (
                  <tr key={param} style={{ background: idx % 2 === 0 ? '#fff' : '#f8f9fa' }}>
                    <td style={{ padding: '4px 10px', color: '#202124' }}>{param}</td>
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
    if (plant) form.append('plant', plant);
    try {
      const res = await fetch(`${apiBase}${previewEndpoint}`, { method: 'POST', body: form });
      const json = await res.json();
      if (!res.ok) throw new Error(json.detail || 'Preview failed');
      setPreview(json);
    } catch (err) {
      setStatus({ type: 'error', text: err.message });
    } finally {
      setBusy(false);
    }
  };

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
      setPreview(prev => ({ ...prev, records: json.records }));
      const warn = (json.warnings || []).length;
      setStatus({
        type: 'success',
        text: `Cumulative calculated for ${json.computed} parameter${json.computed === 1 ? '' : 's'}`
          + (warn ? ` — ${warn} skipped (e.g. ${json.warnings[0]})` : ''),
      });
    } catch (err) {
      setStatus({ type: 'error', text: err.message });
    } finally {
      setBusy(false);
    }
  };

  const handleConfirmSave = async () => {
    if (!preview) return;
    setBusy(true);
    setStatus(null);
    try {
      const doInsert = confirmReplace => fetch(`${apiBase}${insertEndpoint}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          plant,
          report_month: preview.report_month,
          source_file: preview.source_file,
          records: preview.records,
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
      {preview && <PreviewReview preview={preview} />}
      <StatusMsg status={status} />
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
  const handleCumulativeAll = async () => {
    if (!window.confirm(
      `Calculate the April→${reportMonth} cumulative for ALL ${plant} techno parameters ` +
      `and overwrite the stored Cumulative values?`
    )) return;
    setCumBusy(true);
    setCumStatus(null);
    try {
      const res = await fetch(`${apiBase}/api/mcr-techno/cumulative-all`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ plant, report_month: reportMonth, overwrite: true }),
      });
      const json = await res.json();
      if (!res.ok) throw new Error(json.detail || 'Cumulative calculation failed');
      const warn = (json.warnings || []).length;
      setCumStatus({
        type: 'success', plant, reportMonth,
        text: `Cumulative calculated for ${json.computed} parameter${json.computed === 1 ? '' : 's'} `
          + `across ${json.units.length} unit${json.units.length === 1 ? '' : 's'}`
          + (warn ? ` — ${warn} skipped (e.g. ${json.warnings[0]})` : ''),
      });
      loadData();
    } catch (err) {
      setCumStatus({ type: 'error', plant, reportMonth, text: err.message });
    } finally {
      setCumBusy(false);
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
            BSP Techno Excel Upload — all files contribute data for the same month (merged automatically). The month-end row accepts MIS-2 or PPC MIS (auto-detected, tentative data).
          </div>
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

      {/* ISP: single file extract bar */}
      {plant === 'ISP' && (
        <div style={{ marginBottom: 16 }}>
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

      {/* BSL: Show ONLY the unified extraction table (no separate data display) */}
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

          {/* Unified BSL BF Performance Extractor - ONLY TABLE (no separate data display below) */}
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
            Recomputes the Cumulative (Apr→{reportMonth}) column for every saved parameter of every {plant} unit,
            using the same rules as the manual-entry page (production-weighted where configured).
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

      {!loading && units.length > 0 && !isBsl && (
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
    BSP: 'Upload BSP-3-page-Tech.xlsx and/or OISCO Excel (final), or the month-end MIS-2 / PPC MIS Excel (tentative furnace & SMS data; month verified against the report date). All merged automatically.',
    ISP: 'Extract from multi-sheet ISP Technopara Excel.',
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
