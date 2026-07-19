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

export default function TechnoMonthlyPage() {
  const def = getDefaultPeriod();
  const [monthName, setMonthName] = useState(def.monthName);
  const [year, setYear] = useState(def.year);
  const [view, setView] = useState('major');       // 'major' | 'db'
  const [plant, setPlant] = useState('BSP');       // db view only

  const [major, setMajor] = useState(null);
  const [dbData, setDbData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const reportMonth = `${year}-${MONTH_NUM[monthName]}`;

  useEffect(() => {
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
  }, [view, plant, reportMonth]);

  const selStyle = {
    padding: '8px 12px', fontSize: '11pt', border: '1px solid #dadce0',
    borderRadius: '6px', backgroundColor: '#ffffff', color: '#202124', cursor: 'pointer',
  };

  const th = (extra = {}) => ({
    ...cell, position: 'sticky', top: 0, zIndex: 2, backgroundColor: '#e8f0fe',
    fontWeight: 700, color: '#174ea6', textAlign: 'right', ...extra,
  });

  // DB view: flatten {unit: {month:{}, till_month:{}}} into ordered rows
  const dbUnits = dbData?.units || {};
  const dbUnitNames = Object.keys(dbUnits).sort();

  return (
    <div style={{ minHeight: '100vh', backgroundColor: '#ffffff' }}>
      <GlobalNavbar />
      <div style={{ maxWidth: '1300px', margin: '0 auto', padding: '32px' }}>

        <div style={{ marginBottom: '24px' }}>
          <h1 style={{ fontSize: '20pt', fontWeight: 900, color: '#202124', margin: 0 }}>
            Plant-wise Techno Parameters
          </h1>
          <p style={{ fontSize: '11pt', color: '#5f6368', marginTop: '6px' }}>
            For-the-month and till-the-month values —{' '}
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
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <label style={{ fontSize: '11pt', fontWeight: 600 }}>Month</label>
            <select value={monthName} onChange={(e) => setMonthName(e.target.value)} style={selStyle}>
              {MONTHS.map((m) => <option key={m}>{m}</option>)}
            </select>
            <select value={year} onChange={(e) => setYear(e.target.value)} style={selStyle}>
              {YEARS.map((y) => <option key={y}>{y}</option>)}
            </select>
          </div>

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
          <span style={{ marginLeft: 'auto', fontSize: '10.5pt', color: '#5f6368' }}>{reportMonth}</span>
        </div>

        {error && (
          <div style={{
            padding: '14px 18px', border: '1px solid #f28b82', borderRadius: '8px',
            backgroundColor: '#fce8e6', color: '#c5221f', fontSize: '11pt', marginBottom: '24px',
          }}>
            {error}
          </div>
        )}

        {/* ── MAJOR view ── */}
        {view === 'major' && !error && major && (
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

        {/* ── DB view ── */}
        {view === 'db' && !error && dbData && (
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
      </div>
    </div>
  );
}
