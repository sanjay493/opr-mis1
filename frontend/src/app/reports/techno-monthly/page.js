'use client';

import React, { useState, useEffect } from 'react';
import GlobalNavbar from '@/components/GlobalNavbar';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || '';

const PLANTS = ['BSP', 'DSP', 'RSP', 'BSL', 'ISP', 'SAIL'];
const MONTHS = [
  'April', 'May', 'June', 'July', 'August', 'September',
  'October', 'November', 'December', 'January', 'February', 'March',
];
const MONTH_NUM = {
  January: '01', February: '02', March: '03', April: '04',
  May: '05', June: '06', July: '07', August: '08',
  September: '09', October: '10', November: '11', December: '12',
};
const MONTH_ABBR = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
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
  const names = ['January','February','March','April','May','June','July','August','September','October','November','December'];
  return { monthName: names[d.getMonth()], year: String(d.getFullYear()) };
}

// "2026-07" -> "Jul'26"
function monthLabel(ym) {
  const [y, m] = ym.split('-');
  return `${MONTH_ABBR[parseInt(m, 10) - 1]}'${y.slice(2)}`;
}

// Inclusive, chronological list of "YYYY-MM" strings from `fromYm` to `toYm`.
// Empty if fromYm is after toYm (caller shows a friendly error for that).
function monthRange(fromYm, toYm) {
  const [fy, fm] = fromYm.split('-').map(Number);
  const [ty, tm] = toYm.split('-').map(Number);
  const out = [];
  let y = fy, m = fm;
  while (y < ty || (y === ty && m <= tm)) {
    out.push(`${y}-${String(m).padStart(2, '0')}`);
    m += 1;
    if (m > 12) { m = 1; y += 1; }
  }
  return out;
}

function prettyKey(key) {
  return String(key)
    .replace(/_/g, ' ')
    .replace(/\b\w/g, (c) => c.toUpperCase())
    .replace(/\bBf\b/g, 'BF').replace(/\bHm\b/g, 'HM').replace(/\bCdi\b/g, 'CDI')
    .replace(/\bTmi\b/g, 'TMI').replace(/\bTfe\b/g, 'TFE').replace(/\bCc\b/g, 'CC')
    .replace(/\bO2\b/g, 'O₂').replace(/\bSms\b/g, 'SMS').replace(/\bLpg\b/g, 'LPG')
    .replace(/\bBof\b/g, 'BOF');
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

const METRIC_LABEL = { month: 'Actual (Month)', cply: 'CPLY', till_month: 'Cumulative (Till Month)' };

export default function TechnoMonthlyPage() {
  const def = getDefaultPeriod();
  const [mode, setMode] = useState('single');       // 'single' | 'period'
  const [monthName, setMonthName] = useState(def.monthName);
  const [year, setYear] = useState(def.year);

  // Period mode: defaults to a 3-month range ending at the single-month default.
  const [fromMonthName, setFromMonthName] = useState(MONTHS[(MONTHS.indexOf(def.monthName) - 2 + 12) % 12]);
  const [fromYear, setFromYear] = useState(def.year);
  const [toMonthName, setToMonthName] = useState(def.monthName);
  const [toYear, setToYear] = useState(def.year);
  const [metric, setMetric] = useState('month');     // 'month' | 'cply' | 'till_month'

  const [view, setView] = useState('major');       // 'major' | 'db'
  const [plant, setPlant] = useState('BSP');       // db view only

  const [major, setMajor] = useState(null);
  const [dbData, setDbData] = useState(null);
  const [periodMonths, setPeriodMonths] = useState([]);
  const [periodMajor, setPeriodMajor] = useState([]); // parallel to periodMonths
  const [periodDb, setPeriodDb] = useState([]);       // parallel to periodMonths
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const reportMonth = `${year}-${MONTH_NUM[monthName]}`;
  const fromReportMonth = `${fromYear}-${MONTH_NUM[fromMonthName]}`;
  const toReportMonth = `${toYear}-${MONTH_NUM[toMonthName]}`;

  // ── Single-month fetch (unchanged behavior) ──
  useEffect(() => {
    if (mode !== 'single') return;
    let cancelled = false;
    setLoading(true);
    setError(null);
    const url = view === 'major'
      ? `${API_BASE}/api/techno-major-monthly?month=${reportMonth}`
      : `${API_BASE}/api/techno/manual/entry?plant=${plant}&report_month=${reportMonth}`;
    fetch(url)
      .then((r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        return r.json();
      })
      .then((d) => {
        if (cancelled) return;
        if (view === 'major') setMajor(d); else setDbData(d);
      })
      .catch((e) => { if (!cancelled) setError(`Failed to load: ${e.message}`); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [mode, view, plant, reportMonth]);

  // ── Period (From–To) fetch — one request per month in the range, reusing
  // the same single-month endpoints (no bulk endpoint needed: each month's
  // response already carries month/cply/till_month per parameter/plant). ──
  useEffect(() => {
    if (mode !== 'period') return;
    const months = monthRange(fromReportMonth, toReportMonth);
    setPeriodMonths(months);
    if (months.length === 0) {
      setError('"From" month must be on or before "To" month.');
      return;
    }
    let cancelled = false;
    setLoading(true);
    setError(null);
    const urls = months.map((m) => (view === 'major'
      ? `${API_BASE}/api/techno-major-monthly?month=${m}`
      : `${API_BASE}/api/techno/manual/entry?plant=${plant}&report_month=${m}`));
    Promise.all(urls.map((u) => fetch(u).then((r) => (r.ok ? r.json() : null)).catch(() => null)))
      .then((results) => {
        if (cancelled) return;
        if (view === 'major') setPeriodMajor(results); else setPeriodDb(results);
      })
      .catch((e) => { if (!cancelled) setError(`Failed to load: ${e.message}`); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [mode, view, plant, fromReportMonth, toReportMonth]);

  // The DB view has no CPLY figure — if 'cply' was selected while on the
  // Major view, switching to DB view would leave `metric` pointing at a
  // field that doesn't exist there (the <select> falls back to showing its
  // first option, silently hiding the mismatch, while every DB cell lookup
  // keyed on the stale 'cply' would just come back blank).
  useEffect(() => {
    if (view === 'db' && metric === 'cply') setMetric('month');
  }, [view, metric]);

  const selStyle = {
    padding: '8px 12px', fontSize: '11pt', border: '1px solid #dadce0',
    borderRadius: '6px', backgroundColor: '#ffffff', color: '#202124', cursor: 'pointer',
  };

  const th = (extra = {}) => ({
    ...cell, position: 'sticky', top: 0, zIndex: 2, backgroundColor: '#e8f0fe',
    fontWeight: 700, color: '#174ea6', textAlign: 'right', ...extra,
  });

  const modeBtn = (active) => ({
    padding: '8px 20px', fontSize: '11pt', fontWeight: 600, border: 'none',
    cursor: 'pointer', backgroundColor: active ? '#1a73e8' : 'transparent',
    color: active ? '#ffffff' : '#5f6368',
  });

  // DB view: flatten {unit: {month:{}, till_month:{}}} into ordered rows
  const dbUnits = dbData?.units || {};
  const dbUnitNames = Object.keys(dbUnits).sort();

  // ── Period-mode row lists — built from whichever fetched month is the
  // first with data, since a parameter/unit set is expected to be stable
  // across a period but isn't guaranteed to be (e.g. a unit added mid-FY);
  // any month's own row/key that isn't in this canonical list is silently
  // not shown, same "don't guess" tradeoff the rest of this page's single-
  // month view already makes for missing data. ──
  const firstMajor = periodMajor.find((d) => d && d.sections?.length);
  const periodMajorSections = firstMajor?.sections || [];

  const firstDb = periodDb.find((d) => d && Object.keys(d.units || {}).length);
  const periodDbUnitNames = Object.keys(firstDb?.units || {}).sort();

  const metricOptions = view === 'major'
    ? ['month', 'cply', 'till_month']
    : ['month', 'till_month']; // the DB view's own data has no CPLY figure

  return (
    <div style={{ minHeight: '100vh', backgroundColor: '#ffffff' }}>
      <GlobalNavbar />
      <div style={{ maxWidth: '1400px', margin: '0 auto', padding: '32px' }}>

        <div style={{ marginBottom: '24px' }}>
          <h1 style={{ fontSize: '20pt', fontWeight: 900, color: '#202124', margin: 0 }}>
            Plant-wise Techno Parameters
          </h1>
          <p style={{ fontSize: '11pt', color: '#5f6368', marginTop: '6px' }}>
            {mode === 'single' ? 'For-the-month and till-the-month values' : `${METRIC_LABEL[metric]} across ${periodMonths.length || 0} month(s)`} —{' '}
            {view === 'major'
              ? 'major parameters exactly as on page 27 of the PDF report'
              : `all parameters stored in the database for ${plant}`}
          </p>
        </div>

        {/* Controls */}
        <div style={{
          display: 'flex', alignItems: 'center', gap: '20px', flexWrap: 'wrap',
          padding: '16px 20px', border: '1px solid #dadce0', borderRadius: '8px',
          backgroundColor: '#f8f9fa', marginBottom: '24px',
        }}>
          {/* Mode toggle */}
          <div style={{
            display: 'flex', border: '1px solid #dadce0', borderRadius: '6px',
            overflow: 'hidden', backgroundColor: '#ffffff',
          }}>
            {[['single', 'Single Month'], ['period', 'Period (From–To)']].map(([v, lbl]) => (
              <button key={v} onClick={() => setMode(v)} style={modeBtn(mode === v)}>
                {lbl}
              </button>
            ))}
          </div>

          {mode === 'single' ? (
            <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
              <label style={{ fontSize: '11pt', fontWeight: 600 }}>Month</label>
              <select value={monthName} onChange={(e) => setMonthName(e.target.value)} style={selStyle}>
                {MONTHS.map((m) => <option key={m}>{m}</option>)}
              </select>
              <select value={year} onChange={(e) => setYear(e.target.value)} style={selStyle}>
                {YEARS.map((y) => <option key={y}>{y}</option>)}
              </select>
            </div>
          ) : (
            <>
              <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                <label style={{ fontSize: '11pt', fontWeight: 600 }}>From</label>
                <select value={fromMonthName} onChange={(e) => setFromMonthName(e.target.value)} style={selStyle}>
                  {MONTHS.map((m) => <option key={m}>{m}</option>)}
                </select>
                <select value={fromYear} onChange={(e) => setFromYear(e.target.value)} style={selStyle}>
                  {YEARS.map((y) => <option key={y}>{y}</option>)}
                </select>
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                <label style={{ fontSize: '11pt', fontWeight: 600 }}>To</label>
                <select value={toMonthName} onChange={(e) => setToMonthName(e.target.value)} style={selStyle}>
                  {MONTHS.map((m) => <option key={m}>{m}</option>)}
                </select>
                <select value={toYear} onChange={(e) => setToYear(e.target.value)} style={selStyle}>
                  {YEARS.map((y) => <option key={y}>{y}</option>)}
                </select>
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                <label style={{ fontSize: '11pt', fontWeight: 600 }}>Show</label>
                <select value={metric} onChange={(e) => setMetric(e.target.value)} style={selStyle}>
                  {metricOptions.map((m) => <option key={m} value={m}>{METRIC_LABEL[m]}</option>)}
                </select>
              </div>
            </>
          )}

          {/* View toggle */}
          <div style={{
            display: 'flex', border: '1px solid #dadce0', borderRadius: '6px',
            overflow: 'hidden', backgroundColor: '#ffffff',
          }}>
            {[['major', 'Major (PDF Report)'], ['db', 'All Parameters (DB)']].map(([v, lbl]) => (
              <button key={v} onClick={() => setView(v)} style={{
                padding: '8px 20px', fontSize: '11pt', fontWeight: 600, border: 'none',
                cursor: 'pointer',
                backgroundColor: view === v ? '#1a73e8' : 'transparent',
                color: view === v ? '#ffffff' : '#5f6368',
              }}>
                {lbl}
              </button>
            ))}
          </div>

          {view === 'db' && (
            <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
              <label style={{ fontSize: '11pt', fontWeight: 600 }}>Plant</label>
              <select value={plant} onChange={(e) => setPlant(e.target.value)} style={selStyle}>
                {PLANTS.map((p) => <option key={p}>{p}</option>)}
              </select>
            </div>
          )}

          {loading && <span style={{ fontSize: '10.5pt', color: '#5f6368' }}>Loading…</span>}
          <span style={{ marginLeft: 'auto', fontSize: '10.5pt', color: '#5f6368' }}>
            {mode === 'single' ? reportMonth : (periodMonths.length ? `${monthLabel(periodMonths[0])} – ${monthLabel(periodMonths[periodMonths.length - 1])}` : '')}
          </span>
        </div>

        {error && (
          <div style={{
            padding: '14px 18px', border: '1px solid #f28b82', borderRadius: '8px',
            backgroundColor: '#fce8e6', color: '#c5221f', fontSize: '11pt', marginBottom: '24px',
          }}>
            {error}
          </div>
        )}

        {/* ── SINGLE MONTH · MAJOR view (unchanged) ── */}
        {mode === 'single' && view === 'major' && !error && major && (
          major.sections?.length ? (
            <div style={{
              border: '1px solid #dadce0', borderRadius: '8px',
              overflowX: 'auto', maxHeight: 'calc(100vh - 280px)', overflowY: 'auto',
            }}>
              <table style={{ borderCollapse: 'separate', borderSpacing: 0, width: '100%' }}>
                <thead>
                  <tr>
                    <th style={th({ textAlign: 'left', minWidth: '160px' })}>Parameter / Plant</th>
                    <th style={th({ textAlign: 'left', minWidth: '80px' })}>Unit</th>
                    <th style={th()}>{major.target_label || 'Target'}</th>
                    <th style={th()}>{major.month_label} (Month)</th>
                    <th style={th()}>{major.cum_label || 'Till Month'}</th>
                    <th style={th()}>{major.cply_label} (CPLY)</th>
                    <th style={th()}>{major.cum_cply_label} (CPLY YTD)</th>
                  </tr>
                </thead>
                <tbody>
                  {major.sections.map((sec) => (
                    <React.Fragment key={sec.parameter}>
                      <tr>
                        <td colSpan={7} style={{
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
                            <td style={{ ...cell, textAlign: 'right', color: isSail ? '#202124' : undefined }}>{fmtNum(r.target)}</td>
                            <td style={{ ...cell, textAlign: 'right', fontWeight: 700, color: isSail ? '#202124' : undefined }}>{fmtNum(r.month)}</td>
                            <td style={{ ...cell, textAlign: 'right', fontWeight: 700, color: isSail ? '#202124' : '#174ea6' }}>{fmtNum(r.till_month)}</td>
                            <td style={{ ...cell, textAlign: 'right', color: isSail ? '#3c2f00' : '#5f6368' }}>{fmtNum(r.cply)}</td>
                            <td style={{ ...cell, textAlign: 'right', color: isSail ? '#3c2f00' : '#5f6368' }}>{fmtNum(r.cum_cply)}</td>
                          </tr>
                        );
                      })}
                    </React.Fragment>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <div style={{ padding: '40px', textAlign: 'center', color: '#5f6368', fontSize: '12pt' }}>
              No techno data for {reportMonth}.
            </div>
          )
        )}

        {/* ── SINGLE MONTH · DB view (unchanged) ── */}
        {mode === 'single' && view === 'db' && !error && dbData && (
          dbUnitNames.length ? (
            <div style={{
              border: '1px solid #dadce0', borderRadius: '8px',
              overflowX: 'auto', maxHeight: 'calc(100vh - 280px)', overflowY: 'auto',
            }}>
              <table style={{ borderCollapse: 'separate', borderSpacing: 0, width: '100%' }}>
                <thead>
                  <tr>
                    <th style={th({ textAlign: 'left', minWidth: '300px' })}>Unit › Parameter</th>
                    <th style={th({ minWidth: '130px' })}>Month</th>
                    <th style={th({ minWidth: '130px' })}>Till Month</th>
                  </tr>
                </thead>
                <tbody>
                  {dbUnitNames.map((u) => {
                    const mo = dbUnits[u]?.month || {};
                    const tm = dbUnits[u]?.till_month || {};
                    const keys = Array.from(new Set([...Object.keys(mo), ...Object.keys(tm)])).sort();
                    return (
                      <React.Fragment key={u}>
                        <tr>
                          <td colSpan={3} style={{
                            ...cell, backgroundColor: '#1a73e8', color: '#ffffff',
                            fontWeight: 800, fontSize: '11pt',
                          }}>
                            {plant} › {u}
                          </td>
                        </tr>
                        {keys.map((k, i) => (
                          <tr key={k} style={{ backgroundColor: i % 2 === 1 ? '#f8f9fa' : '#ffffff' }}>
                            <td style={{ ...cell, whiteSpace: 'normal' }}>
                              <span style={{ fontWeight: 600 }}>{prettyKey(k)}</span>
                              <span style={{ fontSize: '9pt', color: '#9aa0a6', marginLeft: 8 }}>{k}</span>
                            </td>
                            <td style={{ ...cell, textAlign: 'right', fontWeight: 700 }}>{fmtNum(mo[k])}</td>
                            <td style={{ ...cell, textAlign: 'right', fontWeight: 700, color: '#174ea6' }}>{fmtNum(tm[k])}</td>
                          </tr>
                        ))}
                      </React.Fragment>
                    );
                  })}
                </tbody>
              </table>
            </div>
          ) : (
            <div style={{ padding: '40px', textAlign: 'center', color: '#5f6368', fontSize: '12pt' }}>
              No techno data saved for {plant} {reportMonth}.
            </div>
          )
        )}

        {/* ── PERIOD · MAJOR view — one column per month, showing `metric` ── */}
        {mode === 'period' && view === 'major' && !error && periodMonths.length > 0 && (
          periodMajorSections.length ? (
            <div style={{
              border: '1px solid #dadce0', borderRadius: '8px',
              overflowX: 'auto', maxHeight: 'calc(100vh - 280px)', overflowY: 'auto',
            }}>
              <table style={{ borderCollapse: 'separate', borderSpacing: 0, width: '100%' }}>
                <thead>
                  <tr>
                    <th style={th({ textAlign: 'left', minWidth: '160px', left: 0, zIndex: 3 })}>Parameter / Plant</th>
                    <th style={th({ textAlign: 'left', minWidth: '80px' })}>Unit</th>
                    {periodMonths.map((m) => (
                      <th key={m} style={th({ minWidth: '90px' })}>{monthLabel(m)}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {periodMajorSections.map((sec) => (
                    <React.Fragment key={sec.parameter}>
                      <tr>
                        <td colSpan={2 + periodMonths.length} style={{
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
                            {periodMonths.map((m, mi) => {
                              const monthData = periodMajor[mi];
                              const monthSec = monthData?.sections?.find((s) => s.parameter === sec.parameter);
                              const monthRow = monthSec?.rows?.find((row) => row.plant === r.plant);
                              return (
                                <td key={m} style={{ ...cell, textAlign: 'right', fontWeight: 700, color: isSail ? '#202124' : undefined }}>
                                  {fmtNum(monthRow?.[metric])}
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
            </div>
          ) : !loading && (
            <div style={{ padding: '40px', textAlign: 'center', color: '#5f6368', fontSize: '12pt' }}>
              No techno data for {monthLabel(periodMonths[0])} – {monthLabel(periodMonths[periodMonths.length - 1])}.
            </div>
          )
        )}

        {/* ── PERIOD · DB view — one column per month, showing `metric` ── */}
        {mode === 'period' && view === 'db' && !error && periodMonths.length > 0 && (
          periodDbUnitNames.length ? (
            <div style={{
              border: '1px solid #dadce0', borderRadius: '8px',
              overflowX: 'auto', maxHeight: 'calc(100vh - 280px)', overflowY: 'auto',
            }}>
              <table style={{ borderCollapse: 'separate', borderSpacing: 0, width: '100%' }}>
                <thead>
                  <tr>
                    <th style={th({ textAlign: 'left', minWidth: '300px', left: 0, zIndex: 3 })}>Unit › Parameter</th>
                    {periodMonths.map((m) => (
                      <th key={m} style={th({ minWidth: '100px' })}>{monthLabel(m)}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {periodDbUnitNames.map((u) => {
                    const firstUnit = firstDb.units[u] || {};
                    const keys = Array.from(new Set([
                      ...Object.keys(firstUnit.month || {}),
                      ...Object.keys(firstUnit.till_month || {}),
                    ])).sort();
                    return (
                      <React.Fragment key={u}>
                        <tr>
                          <td colSpan={1 + periodMonths.length} style={{
                            ...cell, backgroundColor: '#1a73e8', color: '#ffffff',
                            fontWeight: 800, fontSize: '11pt',
                          }}>
                            {plant} › {u}
                          </td>
                        </tr>
                        {keys.map((k, i) => (
                          <tr key={k} style={{ backgroundColor: i % 2 === 1 ? '#f8f9fa' : '#ffffff' }}>
                            <td style={{ ...cell, whiteSpace: 'normal' }}>
                              <span style={{ fontWeight: 600 }}>{prettyKey(k)}</span>
                              <span style={{ fontSize: '9pt', color: '#9aa0a6', marginLeft: 8 }}>{k}</span>
                            </td>
                            {periodMonths.map((m, mi) => {
                              const monthUnits = periodDb[mi]?.units || {};
                              const v = monthUnits[u]?.[metric]?.[k];
                              return (
                                <td key={m} style={{ ...cell, textAlign: 'right', fontWeight: 700 }}>{fmtNum(v)}</td>
                              );
                            })}
                          </tr>
                        ))}
                      </React.Fragment>
                    );
                  })}
                </tbody>
              </table>
            </div>
          ) : !loading && (
            <div style={{ padding: '40px', textAlign: 'center', color: '#5f6368', fontSize: '12pt' }}>
              No techno data saved for {plant} across {monthLabel(periodMonths[0])} – {monthLabel(periodMonths[periodMonths.length - 1])}.
            </div>
          )
        )}
      </div>
    </div>
  );
}
