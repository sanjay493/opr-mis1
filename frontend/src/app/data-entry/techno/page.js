'use client';

import React, { useState, useCallback, useEffect, useMemo } from 'react';
import GlobalNavbar from '@/components/GlobalNavbar';

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

// ── Single file-upload row used for each file type ────────────────────────────
function ExtractRow({ label, endpoint, reportMonth, apiBase, onSuccess, accent = '#1e3a5f' }) {
  const [file, setFile] = React.useState(null);
  const [busy,  setBusy]  = React.useState(false);
  const [status, setStatus] = React.useState(null);
  const inputRef = React.useRef();

  React.useEffect(() => {
    setFile(null);
    setStatus(null);
    if (inputRef.current) inputRef.current.value = '';
  }, [reportMonth]);

  const handleExtract = async () => {
    if (!file) return;
    setBusy(true);
    setStatus(null);
    const form = new FormData();
    form.append('file', file);
    form.append('report_month', reportMonth);
    try {
      const res  = await fetch(`${apiBase}${endpoint}`, { method: 'POST', body: form });
      const json = await res.json();
      if (!res.ok) throw new Error(json.detail || 'Extraction failed');
      setStatus({ type: 'success', text: `Extracted ${json.units_extracted} units for ${reportMonth}` });
      onSuccess();
    } catch (err) {
      setStatus({ type: 'error', text: err.message });
    } finally {
      setBusy(false);
    }
  };

  return (
    <div style={{ marginBottom: 10 }}>
      <div style={{
        display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap',
        padding: '10px 14px', background: '#f8fafc', border: '1px solid #e2e8f0', borderRadius: 7,
      }}>
        <span style={{ fontSize: 11, color: '#64748b', minWidth: 160, fontWeight: 600 }}>{label}</span>
        <input ref={inputRef} type="file" accept=".xlsx,.xls"
          onChange={e => { setFile(e.target.files[0]); setStatus(null); }}
          style={{ fontSize: 11, flex: 1 }}
        />
        <button onClick={handleExtract} disabled={!file || busy}
          style={{
            padding: '5px 16px', background: busy ? '#94a3b8' : accent,
            color: '#fff', border: 'none', borderRadius: 6, fontSize: 12,
            cursor: file && !busy ? 'pointer' : 'not-allowed', fontWeight: 600, whiteSpace: 'nowrap',
          }}
        >
          {busy ? 'Extracting…' : 'Extract & Save'}
        </button>
      </div>
      <StatusMsg status={status} />
    </div>
  );
}

// ── Techno Data Panel — works for all 5 plants ───────────────────────────────
function TechnoDataPanel({ plant, reportMonth, apiBase }) {
  const [data, setData] = React.useState({});
  const [activeUnit, setActiveUnit] = React.useState(null);
  const [loading, setLoading] = React.useState(false);

  const loadData = React.useCallback(async () => {
    setLoading(true);
    try {
      const res = await fetch(
        `${apiBase}/api/rsp-techno/data?plant=${plant}&report_month=${reportMonth}`
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

  const units = Object.keys(data);
  const unitData = activeUnit ? data[activeUnit] : null;
  const monthParams = unitData?.month || {};
  const tillParams = unitData?.till_month || {};
  const isRsp = plant === 'RSP';
  const isBsp = plant === 'BSP';

  return (
    <div>
      {/* RSP: single file extract bar */}
      {isRsp && (
        <div style={{ marginBottom: 16 }}>
          <ExtractRow
            label="RSP Technopara Excel (page1-8 sheet)"
            endpoint="/api/rsp-techno/extract"
            reportMonth={reportMonth}
            apiBase={apiBase}
            onSuccess={loadData}
            accent="#1e3a5f"
          />
        </div>
      )}

      {/* BSP: two file extract bars (3-page-tech + OISCO) */}
      {isBsp && (
        <div style={{
          marginBottom: 16, padding: '12px 14px',
          background: '#fff7ed', border: '1px solid #fed7aa', borderRadius: 8,
        }}>
          <div style={{ fontSize: 12, fontWeight: 700, color: '#92400e', marginBottom: 10 }}>
            BSP Techno Excel Upload — both files contribute data for the same month (merged automatically)
          </div>
          <ExtractRow
            label="BSP-3-page-Tech.xlsx"
            endpoint="/api/bsp-techno/extract/techno"
            reportMonth={reportMonth}
            apiBase={apiBase}
            onSuccess={loadData}
            accent="#92400e"
          />
          <ExtractRow
            label="OISCO Excel"
            endpoint="/api/bsp-techno/extract/oisco"
            reportMonth={reportMonth}
            apiBase={apiBase}
            onSuccess={loadData}
            accent="#b45309"
          />
        </div>
      )}

      {loading && (
        <div style={{ textAlign: 'center', padding: 40, color: '#64748b', fontSize: 14 }}>
          Loading {plant} data…
        </div>
      )}

      {!loading && units.length === 0 && (
        <div style={{
          textAlign: 'center', padding: 60, color: '#94a3b8', fontSize: 14,
          border: '2px dashed #e2e8f0', borderRadius: 8,
        }}>
          No techno data for <strong>{plant}</strong> — <strong>{reportMonth}</strong>.
          {(isRsp || isBsp) && (
            <span style={{ fontSize: 12, marginTop: 8, display: 'block' }}>
              Upload the Excel file(s) above to extract and save data.
            </span>
          )}
          {!isRsp && !isBsp && (
            <span style={{ fontSize: 12, marginTop: 8, display: 'block' }}>
              {plant} extraction support coming soon.
            </span>
          )}
        </div>
      )}

      {!loading && units.length > 0 && (
        <div style={{ display: 'flex', gap: 0, border: '1px solid #e2e8f0', borderRadius: 8, overflow: 'hidden', minHeight: 400 }}>
          {/* Unit list (left) */}
          <div style={{ width: 160, borderRight: '1px solid #e2e8f0', background: '#f8fafc', flexShrink: 0 }}>
            <div style={{ padding: '8px 12px', fontSize: 10, fontWeight: 700, color: '#94a3b8', textTransform: 'uppercase', letterSpacing: '0.05em', borderBottom: '1px solid #e2e8f0' }}>
              Units ({units.length})
            </div>
            {units.map(u => (
              <button
                key={u}
                onClick={() => setActiveUnit(u)}
                style={{
                  display: 'block', width: '100%', padding: '9px 12px', textAlign: 'left',
                  background: activeUnit === u ? '#1e3a5f' : 'transparent',
                  color: activeUnit === u ? '#fff' : '#334155',
                  border: 'none', borderBottom: '1px solid #e2e8f0',
                  fontSize: 12, fontWeight: activeUnit === u ? 700 : 400,
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
              <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12 }}>
                <thead>
                  <tr style={{ background: '#f8fafc' }}>
                    <th style={{ padding: '7px 14px', textAlign: 'left', color: '#475569', fontWeight: 600, borderBottom: '2px solid #e2e8f0', minWidth: 200 }}>
                      Parameter
                    </th>
                    <th style={{ padding: '7px 12px', textAlign: 'right', color: '#1e3a5f', fontWeight: 600, borderBottom: '2px solid #e2e8f0', minWidth: 120 }}>
                      Month
                    </th>
                    <th style={{ padding: '7px 12px', textAlign: 'right', color: '#475569', fontWeight: 600, borderBottom: '2px solid #e2e8f0', minWidth: 120 }}>
                      Cumulative
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {Object.keys(monthParams).map((param, idx) => {
                    const mv = monthParams[param];
                    const tv = tillParams[param];
                    const fmt = v =>
                      (v != null && v !== '')
                        ? Number(v).toLocaleString(undefined, { maximumFractionDigits: 3 })
                        : '—';
                    return (
                      <tr key={param} style={{ background: idx % 2 === 0 ? '#fff' : '#f8fafc', borderBottom: '1px solid #f1f5f9' }}>
                        <td style={{ padding: '6px 14px', color: '#1e293b', fontWeight: 500 }}>{param}</td>
                        <td style={{ padding: '6px 12px', textAlign: 'right', fontFamily: 'monospace', color: mv != null ? '#1e3a5f' : '#94a3b8' }}>
                          {fmt(mv)}
                        </td>
                        <td style={{ padding: '6px 12px', textAlign: 'right', fontFamily: 'monospace', color: tv != null ? '#334155' : '#94a3b8' }}>
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

  return (
    <>
      <GlobalNavbar />
      <main className="app-container">

        {/* ── Sidebar ──────────────────────────────────────────────────────── */}
        <div className="sidebar no-print">
          <div className="sidebar-header">
            <h1 style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
                <path d="M12 20h9"/><path d="M16.5 3.5a2.121 2.121 0 013 3L7 19l-4 1 1-4L16.5 3.5z"/>
              </svg>
              Techno Data
            </h1>
            <p>View &amp; Extract</p>
          </div>

          <div className="control-section">
            <h2>Report Period</h2>
            <label className="control-label">Month</label>
            <select className="control-select" value={month} onChange={e => setMonth(e.target.value)}>
              {MONTHS.map(m => <option key={m}>{m}</option>)}
            </select>
            <label className="control-label">Year</label>
            <select className="control-select" value={year} onChange={e => setYear(e.target.value)}>
              {YEARS.map(y => <option key={y}>{y}</option>)}
            </select>
            <div style={{ fontSize: 11, color: '#64748b', marginTop: 4 }}>
              Report month: <strong>{reportMonth}</strong>
            </div>
          </div>

          <div className="control-section">
            <h2>Plant</h2>
            <select className="control-select" value={plant} onChange={e => setPlant(e.target.value)}>
              {PLANTS.map(p => <option key={p} value={p}>{p}</option>)}
            </select>
            <div style={{ fontSize: 11, color: '#64748b', marginTop: 6, lineHeight: 1.6 }}>
              Data stored in <code>techno_data</code> table.<br />
              {plant === 'RSP' && 'Extract from Technopara Excel (page1-8 sheet).'}
              {plant === 'BSP' && 'Upload BSP-3-page-Tech.xlsx and/or OISCO Excel. Both are merged automatically.'}
              {plant !== 'RSP' && plant !== 'BSP' && `${plant} extraction coming soon.`}
            </div>
          </div>
        </div>

        {/* ── Main content ─────────────────────────────────────────────────── */}
        <div className="main-content" style={{ padding: '20px 24px', overflowY: 'auto' }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 20 }}>
            <div>
              <h2 style={{ margin: 0, fontSize: 18, color: '#1e293b', fontWeight: 700 }}>
                {plant} — Technopara
              </h2>
              <p style={{ margin: '4px 0 0', fontSize: 12, color: '#64748b' }}>
                {reportMonth} · <code style={{ fontSize: 11 }}>techno_data</code> table
              </p>
            </div>
          </div>

          <TechnoDataPanel plant={plant} reportMonth={reportMonth} apiBase={API_BASE_URL} />
        </div>

      </main>
    </>
  );
}
