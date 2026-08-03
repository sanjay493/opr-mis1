'use client';

import React, { useState, useEffect, useMemo } from 'react';
import GlobalNavbar from '@/components/GlobalNavbar';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || '';

const PLANTS = ['BSP', 'DSP', 'RSP', 'BSL', 'ISP', 'SAIL'];

// The 12 "major" techno-economic parameters — same set and names page 27
// (and the backend's techno_period.MAJOR_TECHNO_PARAM_NAMES) use.
const MAJOR_PARAMS = [
  'Coal to Hot Metal Ratio', 'Coke Rate', 'Nut Coke Rate', 'CDI Rate', 'Fuel Rate',
  'Sinter in Burden', 'Pellet in Burden', 'BF Productivity',
  'Hot Metal Consumption', 'Scrap Consumption', 'TMI', 'Specific Energy Consumption',
];

const MONTH_NAMES_FULL = [
  'January', 'February', 'March', 'April', 'May', 'June',
  'July', 'August', 'September', 'October', 'November', 'December',
];
const MONTH_NUM = {
  January: '01', February: '02', March: '03', April: '04',
  May: '05', June: '06', July: '07', August: '08',
  September: '09', October: '10', November: '11', December: '12',
};
const MONTH_ABBR = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
const YEAR_RANGE_START = 2000;
const _now = new Date();
const CURRENT_FY_END_YEAR = (_now.getMonth() >= 3 ? _now.getFullYear() : _now.getFullYear() - 1) + 1;
const YEARS = Array.from(
  { length: CURRENT_FY_END_YEAR - YEAR_RANGE_START + 1 },
  (_, i) => String(YEAR_RANGE_START + i)
);

function getDefaultPeriod() {
  const d = new Date(); d.setMonth(d.getMonth() - 1);
  return { monthName: MONTH_NAMES_FULL[d.getMonth()], year: String(d.getFullYear()) };
}

function monthLabel(ym) {
  const [y, m] = ym.split('-');
  return `${MONTH_ABBR[parseInt(m, 10) - 1]}'${y.slice(2)}`;
}

// FY quarter convention used throughout the report: Q1=Apr-Jun, Q2=Jul-Sep,
// Q3=Oct-Dec, Q4=Jan-Mar (Jan-Mar belongs to the FY that started the
// previous April) — mirrors production-query/page.js's client-side helpers
// (no shared date-util module exists in this codebase).
const QUARTER_OF_MONTH = { 4: 1, 5: 1, 6: 1, 7: 2, 8: 2, 9: 2, 10: 3, 11: 3, 12: 3, 1: 4, 2: 4, 3: 4 };
function fyStartOf(ym) {
  const [y, m] = ym.split('-').map((n) => parseInt(n, 10));
  return m >= 4 ? y : y - 1;
}
function quarterNumOf(ym) {
  return QUARTER_OF_MONTH[parseInt(ym.split('-')[1], 10)];
}
function fyLabel(fyStart) {
  return `${fyStart}-${String((fyStart + 1) % 100).padStart(2, '0')}`;
}
function monthsOfQuarter(fyStart, q) {
  const startMonthIdx = [4, 7, 10, 1][q - 1];
  const startYear = q === 4 ? fyStart + 1 : fyStart;
  return [0, 1, 2].map((i) => {
    let mm = startMonthIdx + i, yy = startYear;
    if (mm > 12) { mm -= 12; yy += 1; }
    return `${yy}-${String(mm).padStart(2, '0')}`;
  });
}

function fmtNum(v) {
  if (v === null || v === undefined || v === '') return '—';
  const n = Number(v);
  if (Number.isNaN(n)) return String(v);
  return n.toLocaleString('en-IN', { maximumFractionDigits: 3 });
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

export default function TechnoCustomReportPage() {
  const def = getDefaultPeriod();
  const [mode, setMode] = useState('standard'); // 'standard' | 'custom'
  const [selectedPlants, setSelectedPlants] = useState([...PLANTS]);
  const [selectedParams, setSelectedParams] = useState([...MAJOR_PARAMS]);
  const [error, setError] = useState(null);
  const [downloading, setDownloading] = useState(null);

  // ── Standard mode state ──────────────────────────────────────────────────
  const [monthName, setMonthName] = useState(def.monthName);
  const [year, setYear] = useState(def.year);
  const [major, setMajor] = useState(null);
  const [loadingStandard, setLoadingStandard] = useState(false);
  const reportMonth = `${year}-${MONTH_NUM[monthName]}`;

  useEffect(() => {
    let cancelled = false;
    setLoadingStandard(true);
    setError(null);
    fetch(`${API_BASE}/api/techno-major-monthly?month=${reportMonth}`)
      .then((r) => { if (!r.ok) throw new Error(`HTTP ${r.status}`); return r.json(); })
      .then((d) => { if (!cancelled) setMajor(d); })
      .catch((e) => { if (!cancelled) setError(`Failed to load: ${e.message}`); })
      .finally(() => { if (!cancelled) setLoadingStandard(false); });
    return () => { cancelled = true; };
  }, [reportMonth]);

  const filteredSections = useMemo(() => {
    if (!major?.sections) return [];
    const paramSet = new Set(selectedParams);
    const plantSet = new Set(selectedPlants);
    return major.sections
      .filter((s) => paramSet.has(s.parameter))
      .map((s) => ({ ...s, rows: s.rows.filter((r) => plantSet.has(r.plant)) }))
      .filter((s) => s.rows.length > 0);
  }, [major, selectedParams, selectedPlants]);

  // ── Custom Period mode state ─────────────────────────────────────────────
  const [availableMonths, setAvailableMonths] = useState([]); // newest-first
  const [quickFy, setQuickFy] = useState('');
  const [customMonths, setCustomMonths] = useState([]);
  const [customLabel, setCustomLabel] = useState('');
  const [periods, setPeriods] = useState([]); // [{label, months}]
  const [periodData, setPeriodData] = useState(null);
  const [loadingPeriod, setLoadingPeriod] = useState(false);

  useEffect(() => {
    fetch(`${API_BASE}/api/production-query-meta`)
      .then((r) => { if (!r.ok) throw new Error(`HTTP ${r.status}`); return r.json(); })
      .then((d) => {
        const months = (d.months || []).filter((m) => /^\d{4}-\d{2}$/.test(m));
        setAvailableMonths(months);
        if (months.length) setQuickFy(String(fyStartOf(months[0])));
      })
      .catch((e) => setError(`Failed to load available months: ${e.message}`));
  }, []);

  const fyOptions = useMemo(() => {
    const set = new Set(availableMonths.map((m) => fyStartOf(m)));
    return [...set].sort((a, b) => b - a);
  }, [availableMonths]);

  const monthsByFy = useMemo(() => {
    const map = {};
    for (const m of availableMonths) {
      const fy = fyStartOf(m);
      (map[fy] = map[fy] || []).push(m);
    }
    Object.values(map).forEach((arr) => arr.sort());
    return map;
  }, [availableMonths]);

  const addPeriod = (label, months) => {
    const validMonths = months.filter((m) => availableMonths.includes(m));
    if (!label.trim() || validMonths.length === 0) return;
    setPeriods((prev) => {
      if (prev.some((p) => p.label === label)) return prev;
      return [...prev, { label, months: validMonths }];
    });
  };

  const addQuarter = (q) => {
    if (!quickFy) return;
    const fy = parseInt(quickFy, 10);
    addPeriod(`Q${q} ${fyLabel(fy)}`, monthsOfQuarter(fy, q));
  };

  const addHalf = (h) => {
    if (!quickFy) return;
    const fy = parseInt(quickFy, 10);
    const months = h === 1
      ? [...monthsOfQuarter(fy, 1), ...monthsOfQuarter(fy, 2)]
      : [...monthsOfQuarter(fy, 3), ...monthsOfQuarter(fy, 4)];
    addPeriod(`H${h} ${fyLabel(fy)}`, months);
  };

  const addCustom = () => {
    addPeriod(customLabel, customMonths);
    setCustomMonths([]);
    setCustomLabel('');
  };

  const removePeriod = (label) => setPeriods((prev) => prev.filter((p) => p.label !== label));

  const fetchPeriodData = () => {
    if (periods.length === 0 || selectedPlants.length === 0) return;
    setLoadingPeriod(true);
    setError(null);
    fetch(`${API_BASE}/api/techno-custom-period`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ plants: selectedPlants, params: selectedParams, periods }),
    })
      .then((r) => { if (!r.ok) throw new Error(`HTTP ${r.status}`); return r.json(); })
      .then((d) => setPeriodData(d))
      .catch((e) => setError(`Failed to load data: ${e.message}`))
      .finally(() => setLoadingPeriod(false));
  };

  // ── Shared toggles ────────────────────────────────────────────────────────
  const togglePlant = (p) => setSelectedPlants((prev) => prev.includes(p) ? prev.filter((x) => x !== p) : [...prev, p]);
  const toggleParam = (p) => setSelectedParams((prev) => prev.includes(p) ? prev.filter((x) => x !== p) : [...prev, p]);
  const toggleCustomMonth = (m) => setCustomMonths((prev) => prev.includes(m) ? prev.filter((x) => x !== m) : [...prev, m]);

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

  const handleStandardDownload = async (kind) => {
    setDownloading(kind);
    await downloadFile(
      `${API_BASE}/api/techno-custom-standard/${kind}`,
      { month: reportMonth, plants: selectedPlants, params: selectedParams },
      `Techno_Custom_Standard_${reportMonth}.${kind === 'excel' ? 'xlsx' : 'pdf'}`
    );
    setDownloading(null);
  };

  const handlePeriodDownload = async (kind) => {
    setDownloading(kind);
    await downloadFile(
      `${API_BASE}/api/techno-custom-period/${kind}`,
      { plants: selectedPlants, params: selectedParams, periods },
      `Techno_Custom_Period.${kind === 'excel' ? 'xlsx' : 'pdf'}`
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
            Techno Custom Report
          </h1>
          <p style={{ fontSize: '11pt', color: '#5f6368', marginTop: '6px' }}>
            The 12 major techno-economic parameters (page 27) for chosen plants &amp; SAIL — Standard
            (last 3 FYs, target, YTD months, CPLY) or a custom quarter / half-year / month range computed
            fresh (weighted average, harmonic mean, or plain average — whichever the parameter uses — with
            Hot Metal or Crude Steel production during that exact period as the weight).
          </p>
        </div>

        {/* Shared controls: plants + params + mode */}
        <div style={{
          padding: '16px 20px', border: '1px solid #dadce0', borderRadius: '8px',
          backgroundColor: '#f8f9fa', marginBottom: '20px',
        }}>
          <div style={{ marginBottom: '14px' }}>
            <div style={{ fontSize: '11pt', fontWeight: 600, color: '#202124', marginBottom: '8px' }}>Plants</div>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px' }}>
              {PLANTS.map((p) => (
                <button key={p} onClick={() => togglePlant(p)} style={pillStyle(selectedPlants.includes(p))}>
                  {p}
                </button>
              ))}
            </div>
          </div>

          <div style={{ marginBottom: '14px' }}>
            <div style={{ fontSize: '11pt', fontWeight: 600, color: '#202124', marginBottom: '8px' }}>Parameters</div>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: '4px 18px' }}>
              {MAJOR_PARAMS.map((p) => (
                <label key={p} style={{
                  display: 'inline-flex', alignItems: 'center', gap: '6px',
                  fontSize: '10pt', color: '#202124', cursor: 'pointer', padding: '3px 0',
                }}>
                  <input type="checkbox" checked={selectedParams.includes(p)} onChange={() => toggleParam(p)} style={{ cursor: 'pointer' }} />
                  {p}
                </label>
              ))}
            </div>
          </div>

          <div style={{
            display: 'inline-flex', border: '1px solid #dadce0', borderRadius: '6px',
            overflow: 'hidden', backgroundColor: '#ffffff',
          }}>
            {[['standard', 'Standard (Page 27 style)'], ['custom', 'Custom Period']].map(([v, lbl]) => (
              <button key={v} onClick={() => setMode(v)} style={{
                padding: '8px 20px', fontSize: '11pt', fontWeight: 600, border: 'none', cursor: 'pointer',
                backgroundColor: mode === v ? '#1a73e8' : 'transparent',
                color: mode === v ? '#ffffff' : '#5f6368',
              }}>
                {lbl}
              </button>
            ))}
          </div>
        </div>

        {error && (
          <div style={{
            padding: '14px 18px', border: '1px solid #f28b82', borderRadius: '8px',
            backgroundColor: '#fce8e6', color: '#c5221f', fontSize: '11pt', marginBottom: '20px',
          }}>
            {error}
          </div>
        )}

        {/* ── STANDARD MODE ── */}
        {mode === 'standard' && (
          <>
            <div style={{
              display: 'flex', alignItems: 'center', gap: '20px', flexWrap: 'wrap',
              padding: '14px 20px', border: '1px solid #dadce0', borderRadius: '8px',
              backgroundColor: '#ffffff', marginBottom: '20px',
            }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                <label style={{ fontSize: '11pt', fontWeight: 600 }}>Report Month</label>
                <select value={monthName} onChange={(e) => setMonthName(e.target.value)} style={selStyle}>
                  {MONTH_NAMES_FULL.map((m) => <option key={m}>{m}</option>)}
                </select>
                <select value={year} onChange={(e) => setYear(e.target.value)} style={selStyle}>
                  {YEARS.map((y) => <option key={y}>{y}</option>)}
                </select>
              </div>
              {loadingStandard && <span style={{ fontSize: '10.5pt', color: '#5f6368' }}>Loading…</span>}
              {major && filteredSections.length > 0 && (
                <div style={{ marginLeft: 'auto' }}>
                  <ExportButtons onDownload={handleStandardDownload} downloading={downloading} disabled={false} />
                </div>
              )}
            </div>

            {!loadingStandard && filteredSections.length === 0 && (
              <div style={{ padding: '40px', textAlign: 'center', color: '#5f6368', fontSize: '12pt' }}>
                No techno data for the selected plants/parameters in {reportMonth}.
              </div>
            )}

            {filteredSections.length > 0 && (
              <div style={{
                border: '1px solid #dadce0', borderRadius: '8px',
                overflowX: 'auto', maxHeight: 'calc(100vh - 420px)', overflowY: 'auto',
              }}>
                <table style={{ borderCollapse: 'separate', borderSpacing: 0, width: '100%' }}>
                  <thead>
                    <tr>
                      <th style={th({ textAlign: 'left', minWidth: '90px' })}>Plant</th>
                      <th style={th({ textAlign: 'left', minWidth: '70px' })}>Unit</th>
                      <th style={th({ minWidth: '70px' })}>FY {major.fy3_label}</th>
                      <th style={th({ minWidth: '70px' })}>FY {major.fy2_label}</th>
                      <th style={th({ minWidth: '70px' })}>FY {major.fy1_label}</th>
                      <th style={th({ minWidth: '80px' })}>{major.target_label || 'Target'}</th>
                      {(major.month_labels || []).map((ml) => (
                        <th key={ml} style={th({ minWidth: '65px' })}>{ml}</th>
                      ))}
                      <th style={th({ minWidth: '70px' })}>{major.cply_label} (CPLY)</th>
                      <th style={th({ minWidth: '80px' })}>{major.cum_label || 'Cum'}</th>
                      <th style={th({ minWidth: '90px' })}>{major.cum_cply_label} (CPLY)</th>
                    </tr>
                  </thead>
                  <tbody>
                    {filteredSections.map((sec) => (
                      <React.Fragment key={sec.parameter}>
                        <tr>
                          <td colSpan={7 + (major.month_labels || []).length} style={{
                            ...cell, backgroundColor: '#1a73e8', color: '#ffffff',
                            fontWeight: 800, fontSize: '11pt', letterSpacing: '0.02em',
                          }}>
                            {sec.parameter}
                          </td>
                        </tr>
                        {sec.rows.map((r, i) => {
                          const zebra = i % 2 === 1 ? '#f8f9fa' : '#ffffff';
                          const isSail = r.plant === 'SAIL';
                          return (
                            <tr key={r.plant} style={{ backgroundColor: isSail ? '#f9ab00' : zebra }}>
                              <td style={{ ...cell, fontWeight: isSail ? 800 : 600, color: isSail ? '#202124' : undefined }}>{r.plant}</td>
                              <td style={{ ...cell, color: isSail ? '#3c2f00' : '#5f6368' }}>{r.unit}</td>
                              <td style={{ ...cell, textAlign: 'right', color: isSail ? '#202124' : undefined }}>{fmtNum(r.fy3)}</td>
                              <td style={{ ...cell, textAlign: 'right', color: isSail ? '#202124' : undefined }}>{fmtNum(r.fy2)}</td>
                              <td style={{ ...cell, textAlign: 'right', color: isSail ? '#202124' : undefined }}>{fmtNum(r.fy1)}</td>
                              <td style={{ ...cell, textAlign: 'right', color: isSail ? '#202124' : undefined }}>{fmtNum(r.target)}</td>
                              {(r.months || []).map((mv, mi) => (
                                <td key={mi} style={{ ...cell, textAlign: 'right', color: isSail ? '#202124' : undefined }}>{fmtNum(mv)}</td>
                              ))}
                              <td style={{ ...cell, textAlign: 'right', color: isSail ? '#3c2f00' : '#5f6368' }}>{fmtNum(r.cply)}</td>
                              <td style={{ ...cell, textAlign: 'right', fontWeight: 700, color: isSail ? '#202124' : '#174ea6' }}>{fmtNum(r.till_month)}</td>
                              <td style={{ ...cell, textAlign: 'right', color: isSail ? '#3c2f00' : '#5f6368' }}>{fmtNum(r.cum_cply)}</td>
                            </tr>
                          );
                        })}
                      </React.Fragment>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </>
        )}

        {/* ── CUSTOM PERIOD MODE ── */}
        {mode === 'custom' && (
          <>
            <div style={{
              padding: '16px 20px', border: '1px solid #dadce0', borderRadius: '8px',
              backgroundColor: '#ffffff', marginBottom: '20px',
            }}>
              <div style={{ fontSize: '11pt', fontWeight: 600, color: '#202124', marginBottom: '10px' }}>
                Build periods to compare
              </div>

              <div style={{ display: 'flex', alignItems: 'center', gap: '14px', flexWrap: 'wrap', marginBottom: '14px' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <label style={{ fontSize: '10.5pt', fontWeight: 600 }}>FY</label>
                  <select value={quickFy} onChange={(e) => setQuickFy(e.target.value)} style={selStyle}>
                    {fyOptions.map((fy) => <option key={fy} value={fy}>{fyLabel(fy)}</option>)}
                  </select>
                </div>
                {[1, 2, 3, 4].map((q) => (
                  <button key={q} onClick={() => addQuarter(q)} style={pillStyle(false)}>+ Q{q}</button>
                ))}
                {[1, 2].map((h) => (
                  <button key={h} onClick={() => addHalf(h)} style={pillStyle(false)}>+ H{h}</button>
                ))}
              </div>

              <div style={{ marginBottom: '10px' }}>
                <div style={{ fontSize: '10.5pt', fontWeight: 600, color: '#202124', marginBottom: '6px' }}>
                  Or pick specific months for a custom period
                </div>
                <div style={{
                  display: 'flex', flexDirection: 'column', gap: '6px',
                  maxHeight: '160px', overflowY: 'auto', border: '1px solid #dadce0',
                  borderRadius: '6px', padding: '10px', backgroundColor: '#f8f9fa',
                }}>
                  {fyOptions.map((fy) => (
                    <div key={fy} style={{ display: 'flex', alignItems: 'center', gap: '10px', flexWrap: 'wrap' }}>
                      <span style={{ fontSize: '9.5pt', fontWeight: 700, color: '#174ea6', minWidth: '60px' }}>{fyLabel(fy)}</span>
                      {(monthsByFy[fy] || []).map((m) => (
                        <label key={m} style={{ display: 'inline-flex', alignItems: 'center', gap: '4px', fontSize: '9.5pt', cursor: 'pointer' }}>
                          <input type="checkbox" checked={customMonths.includes(m)} onChange={() => toggleCustomMonth(m)} style={{ cursor: 'pointer' }} />
                          {monthLabel(m)}
                        </label>
                      ))}
                    </div>
                  ))}
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginTop: '8px' }}>
                  <input
                    type="text"
                    placeholder="Label (e.g. Monsoon window)"
                    value={customLabel}
                    onChange={(e) => setCustomLabel(e.target.value)}
                    style={{ ...selStyle, cursor: 'text', minWidth: '220px' }}
                  />
                  <button
                    onClick={addCustom}
                    disabled={!customLabel.trim() || customMonths.length === 0}
                    style={{
                      ...pillStyle(false),
                      opacity: !customLabel.trim() || customMonths.length === 0 ? 0.5 : 1,
                      cursor: !customLabel.trim() || customMonths.length === 0 ? 'not-allowed' : 'pointer',
                    }}
                  >
                    + Add Custom Period
                  </button>
                </div>
              </div>

              {periods.length > 0 && (
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px', marginTop: '10px' }}>
                  {periods.map((p) => (
                    <span key={p.label} style={{
                      display: 'inline-flex', alignItems: 'center', gap: '8px',
                      padding: '5px 12px', fontSize: '10pt', fontWeight: 600,
                      backgroundColor: '#e8f0fe', color: '#174ea6', borderRadius: '14px',
                    }}>
                      {p.label} ({p.months.length}mo)
                      <button onClick={() => removePeriod(p.label)} style={{
                        border: 'none', background: 'none', cursor: 'pointer',
                        color: '#174ea6', fontWeight: 900, padding: 0, lineHeight: 1,
                      }}>×</button>
                    </span>
                  ))}
                </div>
              )}

              <div style={{ display: 'flex', alignItems: 'center', gap: '16px', marginTop: '16px' }}>
                <button
                  onClick={fetchPeriodData}
                  disabled={periods.length === 0 || loadingPeriod}
                  style={{
                    padding: '9px 28px', fontSize: '11pt', fontWeight: 700, border: 'none', borderRadius: '6px',
                    cursor: periods.length === 0 || loadingPeriod ? 'not-allowed' : 'pointer',
                    backgroundColor: periods.length === 0 || loadingPeriod ? '#dadce0' : '#1a73e8',
                    color: '#ffffff',
                  }}
                >
                  {loadingPeriod ? 'Generating…' : 'Generate Report'}
                </button>
                {periodData && (
                  <ExportButtons onDownload={handlePeriodDownload} downloading={downloading} disabled={periods.length === 0} />
                )}
              </div>
            </div>

            {periodData && periodData.sections?.length > 0 && (
              <div style={{
                border: '1px solid #dadce0', borderRadius: '8px',
                overflowX: 'auto', maxHeight: 'calc(100vh - 480px)', overflowY: 'auto',
              }}>
                <table style={{ borderCollapse: 'separate', borderSpacing: 0, width: '100%' }}>
                  <thead>
                    <tr>
                      <th style={th({ textAlign: 'left', minWidth: '100px' })}>Plant</th>
                      {periodData.periods.map((label) => (
                        <th key={label} style={th({ minWidth: '100px' })}>{label}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {periodData.sections.map((sec) => (
                      <React.Fragment key={sec.parameter}>
                        <tr>
                          <td colSpan={1 + periodData.periods.length} style={{
                            ...cell, backgroundColor: '#1a73e8', color: '#ffffff',
                            fontWeight: 800, fontSize: '11pt', letterSpacing: '0.02em',
                          }}>
                            {sec.parameter}{sec.unit ? ` (${sec.unit})` : ''}
                          </td>
                        </tr>
                        {sec.rows.map((r, i) => {
                          const zebra = i % 2 === 1 ? '#f8f9fa' : '#ffffff';
                          const isSail = r.plant === 'SAIL';
                          return (
                            <tr key={r.plant} style={{ backgroundColor: isSail ? '#f9ab00' : zebra }}>
                              <td style={{ ...cell, fontWeight: isSail ? 800 : 600, color: isSail ? '#202124' : undefined }}>
                                {r.plant}
                                {isSail && <span style={{ fontSize: '8.5pt', fontWeight: 400, color: '#3c2f00', marginLeft: 6 }}>(computed fresh)</span>}
                              </td>
                              {periodData.periods.map((label) => {
                                const cd = r.values?.[label] || {};
                                const fellBack = cd.method_used === 'average' && (cd.warnings || []).length > 0;
                                return (
                                  <td key={label} style={{
                                    ...cell, textAlign: 'right',
                                    color: isSail ? '#202124' : undefined,
                                    fontWeight: 700,
                                  }} title={fellBack ? cd.warnings.join(' ') : undefined}>
                                    {cd.display || '—'}{fellBack ? '*' : ''}
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
                  * production-weight data was incomplete for one or more months in that period — a simple average is shown instead of the weighted/harmonic figure (hover the cell for detail).
                </div>
              </div>
            )}

            {periodData && periodData.sections?.length === 0 && (
              <div style={{ padding: '40px', textAlign: 'center', color: '#5f6368', fontSize: '12pt' }}>
                No data for the selected plants/parameters in these periods.
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}
