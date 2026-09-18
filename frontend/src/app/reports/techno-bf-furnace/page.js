'use client';

import React, { useState, useEffect, useMemo } from 'react';
import GlobalNavbar from '@/components/GlobalNavbar';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || '';

const MONTH_NAMES_FULL = [
  'January', 'February', 'March', 'April', 'May', 'June',
  'July', 'August', 'September', 'October', 'November', 'December',
];
const MONTH_NUM = {
  January: '01', February: '02', March: '03', April: '04',
  May: '05', June: '06', July: '07', August: '08',
  September: '09', October: '10', November: '11', December: '12',
};
const YEAR_RANGE_START = 2000;
const _now = new Date();
const CURRENT_FY_END_YEAR = (_now.getMonth() >= 3 ? _now.getFullYear() : _now.getFullYear() - 1) + 1;
const YEARS = Array.from(
  { length: CURRENT_FY_END_YEAR - YEAR_RANGE_START + 1 },
  (_, i) => String(YEAR_RANGE_START + i)
);
const FY_END_YEARS = Array.from(
  { length: CURRENT_FY_END_YEAR - YEAR_RANGE_START }, // FY needs a start year too, so one fewer
  (_, i) => YEAR_RANGE_START + 1 + i
).reverse();

function getDefaultPeriod() {
  const d = new Date(); d.setMonth(d.getMonth() - 1);
  return { monthName: MONTH_NAMES_FULL[d.getMonth()], year: String(d.getFullYear()) };
}

function fmtNum(v) {
  if (v === null || v === undefined || v === '') return '—';
  const n = Number(v);
  if (Number.isNaN(n)) return String(v);
  return n.toLocaleString('en-IN', { maximumFractionDigits: 2 });
}

const cell = {
  padding: '7px 12px',
  fontSize: '10.5pt',
  borderBottom: '1px solid #e8eaed',
  whiteSpace: 'nowrap',
};

const selStyle = {
  padding: '8px 12px', fontSize: '11pt', border: '1px solid #dadce0',
  borderRadius: '6px', backgroundColor: '#ffffff', color: '#202124', cursor: 'pointer',
};

const th = (extra = {}) => ({
  ...cell, position: 'sticky', top: 0, zIndex: 2, backgroundColor: '#e8f0fe',
  fontWeight: 700, color: '#174ea6', textAlign: 'right', ...extra,
});

function pillStyle(on) {
  return {
    padding: '6px 16px', fontSize: '10.5pt', fontWeight: 600,
    border: on ? '1px solid #1a73e8' : '1px solid #dadce0',
    borderRadius: '16px', cursor: 'pointer',
    backgroundColor: on ? '#1a73e8' : '#ffffff',
    color: on ? '#ffffff' : '#5f6368',
    transition: 'all 0.15s ease',
  };
}

function ExportButtons({ onDownload, downloading, disabled }) {
  return (
    <div style={{ display: 'flex', gap: '10px' }}>
      {['excel', 'pdf'].map((kind) => (
        <button
          key={kind}
          onClick={() => onDownload(kind)}
          disabled={disabled || downloading !== null}
          style={{
            padding: '8px 18px', fontSize: '10.5pt', fontWeight: 700,
            border: '1px solid #1a73e8', borderRadius: '6px',
            cursor: disabled || downloading !== null ? 'not-allowed' : 'pointer',
            backgroundColor: '#ffffff',
            color: disabled || downloading !== null ? '#9aa0a6' : '#1a73e8',
          }}
        >
          {downloading === kind ? 'Generating…' : `⬇ ${kind === 'excel' ? 'Excel' : 'PDF'}`}
        </button>
      ))}
    </div>
  );
}

export default function TechnoBfFurnaceReportPage() {
  const def = getDefaultPeriod();
  const [meta, setMeta] = useState(null);
  const [metaError, setMetaError] = useState(null);
  const [selectedFurnaces, setSelectedFurnaces] = useState([]);
  const [selectedParams, setSelectedParams] = useState([]);
  const [mode, setMode] = useState('month_till'); // 'range' | 'month_till' | 'annual'
  const [error, setError] = useState(null);
  const [downloading, setDownloading] = useState(null);
  const [loading, setLoading] = useState(false);
  const [data, setData] = useState(null);

  // Duration inputs
  const [startMonthName, setStartMonthName] = useState(def.monthName);
  const [startYear, setStartYear] = useState(def.year);
  const [endMonthName, setEndMonthName] = useState(def.monthName);
  const [endYear, setEndYear] = useState(def.year);
  const [monthName, setMonthName] = useState(def.monthName);
  const [year, setYear] = useState(def.year);
  const [fyEndYear, setFyEndYear] = useState(String(CURRENT_FY_END_YEAR));

  useEffect(() => {
    fetch(`${API_BASE}/api/techno-bf-furnace/meta`)
      .then((r) => { if (!r.ok) throw new Error(`HTTP ${r.status}`); return r.json(); })
      .then((d) => {
        setMeta(d);
        setSelectedFurnaces(d.furnace_keys || []);
        setSelectedParams((d.params || []).map((p) => p.key));
      })
      .catch((e) => setMetaError(`Failed to load furnace/parameter list: ${e.message}`));
  }, []);

  const toggleFurnace = (key) => setSelectedFurnaces((prev) =>
    prev.includes(key) ? prev.filter((x) => x !== key) : [...prev, key]);
  const toggleParam = (key) => setSelectedParams((prev) =>
    prev.includes(key) ? prev.filter((x) => x !== key) : [...prev, key]);

  const allFurnaceKeys = meta?.furnace_keys || [];
  const allParamKeys = useMemo(() => (meta?.params || []).map((p) => p.key), [meta]);

  const buildBody = () => {
    const body = {
      furnaces: selectedFurnaces,
      params: selectedParams.length === allParamKeys.length ? null : selectedParams,
      mode,
    };
    if (mode === 'range') {
      body.start_month = `${startYear}-${MONTH_NUM[startMonthName]}`;
      body.end_month = `${endYear}-${MONTH_NUM[endMonthName]}`;
    } else if (mode === 'month_till') {
      body.month = `${year}-${MONTH_NUM[monthName]}`;
    } else if (mode === 'annual') {
      body.fy_end_year = parseInt(fyEndYear, 10);
    }
    return body;
  };

  const fetchReport = () => {
    if (selectedFurnaces.length === 0) { setError('Select at least one furnace.'); return; }
    setLoading(true);
    setError(null);
    fetch(`${API_BASE}/api/techno-bf-furnace/report`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(buildBody()),
    })
      .then(async (r) => {
        if (!r.ok) { const b = await r.json().catch(() => ({})); throw new Error(b.detail || `HTTP ${r.status}`); }
        return r.json();
      })
      .then((d) => setData(d))
      .catch((e) => setError(`Failed to load data: ${e.message}`))
      .finally(() => setLoading(false));
  };

  const downloadFile = async (url, body, filename) => {
    try {
      const res = await fetch(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });
      if (!res.ok) {
        const b = await res.json().catch(() => ({}));
        throw new Error(b.detail || `HTTP ${res.status}`);
      }
      const blob = await res.blob();
      const objUrl = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = objUrl;
      a.download = filename;
      document.body.appendChild(a);
      a.click();
      a.remove();
      window.URL.revokeObjectURL(objUrl);
    } catch (e) {
      setError(`Download failed: ${e.message}`);
    }
  };

  const handleDownload = async (kind) => {
    setDownloading(kind);
    await downloadFile(
      `${API_BASE}/api/techno-bf-furnace/${kind}`,
      buildBody(),
      `BF_Techno_Report.${kind === 'excel' ? 'xlsx' : 'pdf'}`
    );
    setDownloading(null);
  };

  return (
    <div style={{ minHeight: '100vh', backgroundColor: '#ffffff' }}>
      <style>{`html, body { overflow-y: auto; overflow-x: hidden; }`}</style>
      <GlobalNavbar />
      <div style={{ maxWidth: '1500px', margin: '0 auto', padding: '32px' }}>

        <div style={{ marginBottom: '24px' }}>
          <h1 style={{ fontSize: '20pt', fontWeight: 900, color: '#202124', margin: 0 }}>
            Blast Furnace Techno Report
          </h1>
          <p style={{ fontSize: '11pt', color: '#5f6368', marginTop: '6px' }}>
            Furnace-wise techno-economic parameters for any SAIL blast furnace — a custom month range
            (weighted average, harmonic mean, or sum, whichever the parameter uses, weighted by that
            furnace&apos;s own production during exactly that range), a single month alongside its
            April-to-that-month cumulative, or a full financial year (April-March).
          </p>
        </div>

        {metaError && (
          <div style={{
            padding: '14px 18px', border: '1px solid #f28b82', borderRadius: '8px',
            backgroundColor: '#fce8e6', color: '#c5221f', fontSize: '11pt', marginBottom: '20px',
          }}>
            {metaError}
          </div>
        )}

        {meta && (
          <div style={{
            padding: '16px 20px', border: '1px solid #dadce0', borderRadius: '8px',
            backgroundColor: '#f8f9fa', marginBottom: '20px',
          }}>
            {/* Furnace picker, grouped by plant */}
            <div style={{ marginBottom: '14px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '8px' }}>
                <span style={{ fontSize: '11pt', fontWeight: 600, color: '#202124' }}>Furnaces</span>
                <button onClick={() => setSelectedFurnaces(allFurnaceKeys)} style={{ ...pillStyle(false), padding: '3px 10px', fontSize: '9pt' }}>All</button>
                <button onClick={() => setSelectedFurnaces([])} style={{ ...pillStyle(false), padding: '3px 10px', fontSize: '9pt' }}>None</button>
              </div>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: '18px' }}>
                {Object.entries(meta.furnaces_by_plant || {}).map(([plant, units]) => (
                  <div key={plant}>
                    <div style={{ fontSize: '9.5pt', fontWeight: 700, color: '#174ea6', marginBottom: '4px' }}>{plant}</div>
                    <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px' }}>
                      {units.map((u) => {
                        const key = `${plant}:${u}`;
                        return (
                          <button key={key} onClick={() => toggleFurnace(key)} style={{ ...pillStyle(selectedFurnaces.includes(key)), padding: '5px 12px', fontSize: '9.5pt' }}>
                            {u}
                          </button>
                        );
                      })}
                    </div>
                  </div>
                ))}
              </div>
            </div>

            {/* Parameter picker */}
            <div style={{ marginBottom: '14px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '8px' }}>
                <span style={{ fontSize: '11pt', fontWeight: 600, color: '#202124' }}>Parameters</span>
                <button onClick={() => setSelectedParams(allParamKeys)} style={{ ...pillStyle(false), padding: '3px 10px', fontSize: '9pt' }}>All</button>
                <button onClick={() => setSelectedParams([])} style={{ ...pillStyle(false), padding: '3px 10px', fontSize: '9pt' }}>None</button>
              </div>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: '4px 18px', maxHeight: '140px', overflowY: 'auto', border: '1px solid #dadce0', borderRadius: '6px', padding: '10px', backgroundColor: '#ffffff' }}>
                {(meta.params || []).map((p) => (
                  <label key={p.key} style={{
                    display: 'inline-flex', alignItems: 'center', gap: '6px',
                    fontSize: '10pt', color: '#202124', cursor: 'pointer', padding: '3px 0',
                  }}>
                    <input type="checkbox" checked={selectedParams.includes(p.key)} onChange={() => toggleParam(p.key)} style={{ cursor: 'pointer' }} />
                    {p.label}{p.unit ? ` (${p.unit})` : ''}
                  </label>
                ))}
              </div>
            </div>

            {/* Duration mode */}
            <div style={{ marginBottom: '10px' }}>
              <div style={{ fontSize: '11pt', fontWeight: 600, color: '#202124', marginBottom: '8px' }}>Duration</div>
              <div style={{
                display: 'inline-flex', border: '1px solid #dadce0', borderRadius: '6px',
                overflow: 'hidden', backgroundColor: '#ffffff', marginBottom: '12px',
              }}>
                {[['range', 'Start - End Month'], ['month_till', 'Month + Till-Month'], ['annual', 'Annual (Apr-Mar)']].map(([v, lbl]) => (
                  <button key={v} onClick={() => setMode(v)} style={{
                    padding: '8px 20px', fontSize: '10.5pt', fontWeight: 600, border: 'none', cursor: 'pointer',
                    backgroundColor: mode === v ? '#1a73e8' : 'transparent',
                    color: mode === v ? '#ffffff' : '#5f6368',
                  }}>
                    {lbl}
                  </button>
                ))}
              </div>

              {mode === 'range' && (
                <div style={{ display: 'flex', alignItems: 'center', gap: '16px', flexWrap: 'wrap' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                    <label style={{ fontSize: '10.5pt', fontWeight: 600 }}>From</label>
                    <select value={startMonthName} onChange={(e) => setStartMonthName(e.target.value)} style={selStyle}>
                      {MONTH_NAMES_FULL.map((m) => <option key={m}>{m}</option>)}
                    </select>
                    <select value={startYear} onChange={(e) => setStartYear(e.target.value)} style={selStyle}>
                      {YEARS.map((y) => <option key={y}>{y}</option>)}
                    </select>
                  </div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                    <label style={{ fontSize: '10.5pt', fontWeight: 600 }}>To</label>
                    <select value={endMonthName} onChange={(e) => setEndMonthName(e.target.value)} style={selStyle}>
                      {MONTH_NAMES_FULL.map((m) => <option key={m}>{m}</option>)}
                    </select>
                    <select value={endYear} onChange={(e) => setEndYear(e.target.value)} style={selStyle}>
                      {YEARS.map((y) => <option key={y}>{y}</option>)}
                    </select>
                  </div>
                </div>
              )}

              {mode === 'month_till' && (
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <label style={{ fontSize: '10.5pt', fontWeight: 600 }}>Month</label>
                  <select value={monthName} onChange={(e) => setMonthName(e.target.value)} style={selStyle}>
                    {MONTH_NAMES_FULL.map((m) => <option key={m}>{m}</option>)}
                  </select>
                  <select value={year} onChange={(e) => setYear(e.target.value)} style={selStyle}>
                    {YEARS.map((y) => <option key={y}>{y}</option>)}
                  </select>
                  <span style={{ fontSize: '9.5pt', color: '#5f6368' }}>
                    → shows this month&apos;s own figure and the Apr-to-this-month cumulative, side by side.
                  </span>
                </div>
              )}

              {mode === 'annual' && (
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <label style={{ fontSize: '10.5pt', fontWeight: 600 }}>Financial Year ending March</label>
                  <select value={fyEndYear} onChange={(e) => setFyEndYear(e.target.value)} style={selStyle}>
                    {FY_END_YEARS.map((y) => <option key={y} value={y}>{y} (FY {y - 1}-{String(y % 100).padStart(2, '0')})</option>)}
                  </select>
                </div>
              )}
            </div>

            <div style={{ display: 'flex', alignItems: 'center', gap: '16px', marginTop: '16px' }}>
              <button
                onClick={fetchReport}
                disabled={selectedFurnaces.length === 0 || loading}
                style={{
                  padding: '9px 28px', fontSize: '11pt', fontWeight: 700, border: 'none', borderRadius: '6px',
                  cursor: selectedFurnaces.length === 0 || loading ? 'not-allowed' : 'pointer',
                  backgroundColor: selectedFurnaces.length === 0 || loading ? '#dadce0' : '#1a73e8',
                  color: '#ffffff',
                }}
              >
                {loading ? 'Generating…' : 'Generate Report'}
              </button>
              {data && (
                <ExportButtons onDownload={handleDownload} downloading={downloading} disabled={selectedFurnaces.length === 0} />
              )}
            </div>
          </div>
        )}

        {error && (
          <div style={{
            padding: '14px 18px', border: '1px solid #f28b82', borderRadius: '8px',
            backgroundColor: '#fce8e6', color: '#c5221f', fontSize: '11pt', marginBottom: '20px',
          }}>
            {error}
          </div>
        )}

        {data && data.sections?.length > 0 && (
          <div style={{
            border: '1px solid #dadce0', borderRadius: '8px',
            overflowX: 'auto', maxHeight: 'calc(100vh - 480px)', overflowY: 'auto',
          }}>
            <table style={{ borderCollapse: 'separate', borderSpacing: 0, width: '100%' }}>
              <thead>
                <tr>
                  <th style={th({ textAlign: 'left', minWidth: '120px' })}>Furnace</th>
                  {data.periods.map((label) => (
                    <th key={label} style={th({ minWidth: '110px' })}>{label}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {data.sections.map((sec) => (
                  <React.Fragment key={sec.parameter}>
                    <tr>
                      <td colSpan={1 + data.periods.length} style={{
                        ...cell, backgroundColor: '#1a73e8', color: '#ffffff',
                        fontWeight: 800, fontSize: '11pt', letterSpacing: '0.02em',
                      }}>
                        {sec.parameter}{sec.unit ? ` (${sec.unit})` : ''}
                      </td>
                    </tr>
                    {sec.rows.map((r, i) => {
                      const zebra = i % 2 === 1 ? '#f8f9fa' : '#ffffff';
                      return (
                        <tr key={r.furnace} style={{ backgroundColor: zebra }}>
                          <td style={{ ...cell, fontWeight: 600 }}>{r.furnace}</td>
                          {data.periods.map((label) => {
                            const cd = r.values?.[label] || {};
                            const fellBack = cd.method_used === 'average' && (cd.warnings || []).length > 0;
                            return (
                              <td key={label} style={{ ...cell, textAlign: 'right', fontWeight: 700 }}
                                title={fellBack ? cd.warnings.join(' ') : undefined}>
                                {cd.display !== undefined && cd.display !== '' ? cd.display : fmtNum(cd.value)}{fellBack ? '*' : ''}
                              </td>
                            );
                          })}
                        </tr>
                      );
                    })}
                  </React.Fragment>
                ))}
              </tbody>
            </table>
            <div style={{ padding: '8px 12px', fontSize: '9pt', color: '#5f6368', borderTop: '1px solid #e8eaed' }}>
              * production-weight data was incomplete for one or more months in that range — a simple average is shown instead of the weighted/harmonic figure (hover the cell for detail).
            </div>
          </div>
        )}

        {data && data.sections?.length === 0 && (
          <div style={{ padding: '40px', textAlign: 'center', color: '#5f6368', fontSize: '12pt' }}>
            No data for the selected furnaces/parameters in this period.
          </div>
        )}
      </div>
    </div>
  );
}
