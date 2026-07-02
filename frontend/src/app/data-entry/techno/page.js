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

// ── Single file-upload row used for each file type ────────────────────────────
function ExtractRow({ label, endpoint, reportMonth, apiBase, onSuccess, plant, accent = '#1e3a5f', accept = '.xlsx,.xls' }) {
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
    if (plant) form.append('plant', plant);
    try {
      const res = await fetch(`${apiBase}${endpoint}`, { method: 'POST', body: form });
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
        <span style={{ fontSize: 13, color: '#64748b', minWidth: 180, fontWeight: 600 }}>{label}</span>
        <input ref={inputRef} type="file" accept={accept}
          onChange={e => { setFile(e.target.files[0]); setStatus(null); }}
          style={{ fontSize: 13, flex: 1 }}
          suppressHydrationWarning
        />
        <button onClick={handleExtract} disabled={!file || busy}
          style={{
            padding: '7px 18px', background: busy ? '#94a3b8' : accent,
            color: '#fff', border: 'none', borderRadius: 6, fontSize: 13,
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
      {/* RSP: single file extract bar */}
      {isRsp && (
        <div style={{ marginBottom: 16 }}>
          <ExtractRow
            label="RSP Technopara Excel (page1-8 sheet)"
            endpoint="/api/techno/extract"
            plant="RSP"
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
          <div style={{ fontSize: 14, fontWeight: 700, color: '#92400e', marginBottom: 10 }}>
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

      {/* ISP: single file extract bar */}
      {plant === 'ISP' && (
        <div style={{ marginBottom: 16 }}>
          <ExtractRow
            label="ISP Technopara Excel"
            endpoint="/api/techno/extract"
            plant="ISP"
            reportMonth={reportMonth}
            apiBase={apiBase}
            onSuccess={loadData}
            accent="#7c3aed"
          />
        </div>
      )}

      {/* DSP: single file extract bar (PDF) */}
      {plant === 'DSP' && (
        <div style={{ marginBottom: 16 }}>
          <ExtractRow
            label="DSP Monthly Report PDF"
            endpoint="/api/techno/extract"
            plant="DSP"
            reportMonth={reportMonth}
            apiBase={apiBase}
            onSuccess={loadData}
            accent="#dc2626"
            accept=".pdf"
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
              endpoint="/api/techno/extract"
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
        <div style={{ display: 'flex', gap: 0, border: '1px solid #e2e8f0', borderRadius: 8, overflow: 'hidden', minHeight: 400 }}>
          {/* Unit list (left) */}
          <div style={{ width: 180, borderRight: '1px solid #e2e8f0', background: '#f8fafc', flexShrink: 0 }}>
            <div style={{ padding: '10px 14px', fontSize: 12, fontWeight: 700, color: '#94a3b8', textTransform: 'uppercase', letterSpacing: '0.05em', borderBottom: '1px solid #e2e8f0' }}>
              Units ({units.length})
            </div>
            {units.map(u => (
              <button
                key={u}
                onClick={() => setActiveUnit(u)}
                style={{
                  display: 'block', width: '100%', padding: '10px 14px', textAlign: 'left',
                  background: activeUnit === u ? '#1e3a5f' : 'transparent',
                  color: activeUnit === u ? '#fff' : '#334155',
                  border: 'none', borderBottom: '1px solid #e2e8f0',
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
                    const fmt = v => {
                      if (v == null || v === '') return '—';
                      if (typeof v === 'string' && v.includes(':')) return v;
                      return Number(v).toLocaleString(undefined, { maximumFractionDigits: 3 });
                    };
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

  const plantHint = {
    RSP: 'Extract from Technopara Excel (page1-8 sheet).',
    BSP: 'Upload BSP-3-page-Tech.xlsx and/or OISCO Excel. Both merged automatically.',
    ISP: 'Extract from multi-sheet ISP Technopara Excel.',
    DSP: 'Extract from DSP Monthly Report PDF.',
    BSL: 'Upload Techno Excel and/or BF Performance PDF. Both merged automatically.',
  }[plant] || `${plant} extraction coming soon.`;

  return (
    <div style={{ minHeight: '100vh', background: '#f8fafc' }}>
      <GlobalNavbar />

      <div style={{ maxWidth: 1400, margin: '0 auto', padding: '22px 20px' }}>

        {/* ── Page title ── */}
        <div style={{ marginBottom: 18 }}>
          <h2 style={{ fontSize: '1.6rem', fontWeight: 700, color: '#1e3a5f', margin: '0 0 4px' }}>
            Techno Data — View &amp; Extract
          </h2>
          <span style={{ fontSize: 13, color: '#94a3b8' }}>
            {reportMonth} · data stored in <code style={{ fontSize: 12 }}>techno_data</code> table
          </span>
        </div>

        {/* ── Controls bar ── */}
        <div style={{
          display: 'flex', gap: 10, alignItems: 'center', flexWrap: 'wrap',
          marginBottom: 18, background: '#fff', border: '1px solid #e2e8f0',
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

          <span style={{ marginLeft: 'auto', fontSize: 13, color: '#64748b', maxWidth: 420, textAlign: 'right' }}>
            {plantHint}
          </span>
        </div>

        <TechnoDataPanel plant={plant} reportMonth={reportMonth} apiBase={API_BASE_URL} />
      </div>
    </div>
  );
}
