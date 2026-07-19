'use client';

import React, { useState, useEffect } from 'react';
import GlobalNavbar from '@/components/GlobalNavbar';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || '';

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
  const names = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December'];
  return { monthName: names[d.getMonth()], year: String(d.getFullYear()) };
}

function fmtNum(v) {
  if (v === null || v === undefined || v === '') return '—';
  const n = Number(v);
  if (Number.isNaN(n)) return String(v);
  return n.toLocaleString('en-IN', { maximumFractionDigits: 4 });
}

const cell = {
  padding: '7px 12px',
  fontSize: '10.5pt',
  borderBottom: '1px solid #e8eaed',
  whiteSpace: 'nowrap',
};

const METHOD_LABEL = {
  weighted_average: 'Production-weighted average',
  harmonic_mean:    'Production-weighted harmonic mean',
  simple_average:   'Simple average',
  sum:              'Sum of monthly values',
};

// Calculation-step breakdown for one row's Calculated value — same table
// shape (rows/steps/weight_item) and layout as the "Calculate Cumulative"
// step window on data-entry/techno, so the two features read consistently.
function CalcStepsDetail({ detail }) {
  if (!detail) return null;
  const th = { padding: '5px 10px', textAlign: 'left', color: '#5f6368', fontWeight: 600, fontSize: 12, borderBottom: '1px solid #dadce0' };
  const thR = { ...th, textAlign: 'right' };
  return (
    <div style={{ padding: '10px 14px 14px' }}>
      <div style={{ fontSize: 12.5, fontWeight: 700, color: '#174ea6', marginBottom: 4 }}>
        {METHOD_LABEL[detail.method] || detail.method}
      </div>
      {detail.weight_item && (
        <div style={{ fontSize: 12, color: '#5f6368', marginBottom: 8 }}>Weights: {detail.weight_item}</div>
      )}
      {(detail.warnings || []).map((w, i) => (
        <div key={i} style={{ fontSize: 12, color: '#991b1b', background: '#fef2f2', border: '1px solid #fca5a5', borderRadius: 5, padding: '4px 9px', marginBottom: 6 }}>
          {w}
        </div>
      ))}
      {detail.rows?.length > 0 && (
        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12, marginBottom: 8, background: '#fff' }}>
          <thead>
            <tr>
              <th style={th}>Month / Plant</th>
              <th style={thR}>Value</th>
              <th style={thR}>Weight</th>
              <th style={thR}>Product</th>
            </tr>
          </thead>
          <tbody>
            {detail.rows.map((r, i) => (
              <tr key={i} style={{ borderTop: '1px solid #f1f3f4' }}>
                <td style={{ padding: '4px 10px', color: '#202124' }}>{r.label}</td>
                <td style={{ padding: '4px 10px', textAlign: 'right', fontFamily: 'monospace' }}>{fmtNum(r.value)}</td>
                <td style={{ padding: '4px 10px', textAlign: 'right', fontFamily: 'monospace', color: '#5f6368' }}>{r.weight == null ? '—' : fmtNum(r.weight)}</td>
                <td style={{ padding: '4px 10px', textAlign: 'right', fontFamily: 'monospace', color: '#5f6368' }}>{r.product == null ? '—' : fmtNum(r.product)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
      <div style={{ fontSize: 11.5, color: '#5f6368', fontFamily: 'monospace' }}>
        {(detail.steps || []).map((s, i) => <div key={i}>{s}</div>)}
      </div>
    </div>
  );
}

export default function TechnoVerificationPage() {
  const def = getDefaultPeriod();
  const [monthName, setMonthName] = useState(def.monthName);
  const [year, setYear] = useState(def.year);

  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [expanded, setExpanded] = useState(null); // "sectionLabel::rowLabel" or null

  const reportMonth = `${year}-${MONTH_NUM[monthName]}`;

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    fetch(`${API_BASE}/api/techno-major-verification?month=${reportMonth}`)
      .then((r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        return r.json();
      })
      .then((d) => { if (!cancelled) setData(d); })
      .catch((e) => { if (!cancelled) setError(`Failed to load: ${e.message}`); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [reportMonth]);

  const selStyle = {
    padding: '8px 12px', fontSize: '11pt', border: '1px solid #dadce0',
    borderRadius: '6px', backgroundColor: '#ffffff', color: '#202124', cursor: 'pointer',
  };

  const th = (extra = {}) => ({
    ...cell, position: 'sticky', top: 0, zIndex: 2, backgroundColor: '#e8f0fe',
    fontWeight: 700, color: '#174ea6', textAlign: 'right', ...extra,
  });

  const monthLabels = data?.month_labels || [];

  return (
    <div style={{ minHeight: '100vh', backgroundColor: '#ffffff' }}>
      <GlobalNavbar />
      <div style={{ maxWidth: '1400px', margin: '0 auto', padding: '32px' }}>

        <div style={{ marginBottom: '24px' }}>
          <h1 style={{ fontSize: '20pt', fontWeight: 900, color: '#202124', margin: 0 }}>
            Techno Verification — Reported vs Calculated
          </h1>
          <p style={{ fontSize: '11pt', color: '#5f6368', marginTop: '6px' }}>
            Every MAJOR page (27) parameter, for every plant and the SAIL rollup: this FY&apos;s monthly
            actuals, the Reported till-month cumulative (as stored), and a Calculated till-month
            cumulative freshly recomputed from the monthly actuals — the same production-weighted
            rules the &quot;Calculate Cumulative&quot; feature uses. A deviation between the two is
            highlighted amber.
          </p>
        </div>

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

        {!error && data && (
          data.sections?.length ? (
            <div style={{
              border: '1px solid #dadce0', borderRadius: '8px',
              overflowX: 'auto', maxHeight: 'calc(100vh - 320px)', overflowY: 'auto',
            }}>
              <table style={{ borderCollapse: 'separate', borderSpacing: 0, width: '100%' }}>
                <thead>
                  <tr>
                    <th style={th({ textAlign: 'left', minWidth: '160px' })}>Parameter / Plant</th>
                    <th style={th({ textAlign: 'left', minWidth: '70px' })}>Unit</th>
                    {monthLabels.map((ml) => (
                      <th key={ml} style={th({ minWidth: '90px' })}>{ml}</th>
                    ))}
                    <th style={th({ minWidth: '110px' })}>{data.cum_label} (Reported)</th>
                    <th style={th({ minWidth: '110px' })}>{data.cum_label} (Calculated)</th>
                    <th style={th({ minWidth: '70px' })}></th>
                  </tr>
                </thead>
                <tbody>
                  {data.sections.map((sec) => (
                    <React.Fragment key={sec.label}>
                      <tr>
                        <td colSpan={5 + monthLabels.length} style={{
                          ...cell, backgroundColor: '#1a73e8', color: '#ffffff',
                          fontWeight: 800, fontSize: '11pt', letterSpacing: '0.02em',
                        }}>
                          {sec.label}
                        </td>
                      </tr>
                      {sec.rows.map((r, i) => {
                        const zebra = i % 2 === 1 ? '#f8f9fa' : '#ffffff';
                        const isSail = r.label === 'SAIL';
                        const rowBg = isSail ? '#f9ab00' : zebra;
                        const textColor = isSail ? '#202124' : undefined;
                        const rowKey = `${sec.label}::${r.label}`;
                        const isOpen = expanded === rowKey;
                        return (
                          <React.Fragment key={r.label}>
                            <tr style={{ backgroundColor: rowBg }}>
                              <td style={{ ...cell, fontWeight: isSail ? 800 : 600, color: textColor }}>{r.label}</td>
                              <td style={{ ...cell, color: isSail ? '#3c2f00' : '#5f6368' }}>{r.unit}</td>
                              {r.months.map((mv, mi) => (
                                <td key={mi} style={{ ...cell, textAlign: 'right', color: textColor ?? '#5f6368' }}>
                                  {fmtNum(mv)}
                                </td>
                              ))}
                              <td style={{ ...cell, textAlign: 'right', fontWeight: 700, color: isSail ? '#202124' : '#174ea6' }}>
                                {fmtNum(r.reported)}
                              </td>
                              <td style={{
                                ...cell, textAlign: 'right', fontWeight: 700,
                                backgroundColor: r.deviation && !isSail ? '#fbbc04' : undefined,
                                boxShadow: r.deviation && isSail ? 'inset 0 0 0 3px #ea4335' : undefined,
                                color: r.deviation && !isSail ? '#202124' : (isSail ? '#202124' : '#174ea6'),
                              }}>
                                {fmtNum(r.calculated)}
                              </td>
                              <td style={{ ...cell, textAlign: 'right' }}>
                                {r.calc_detail && (
                                  <button
                                    onClick={() => setExpanded(isOpen ? null : rowKey)}
                                    style={{
                                      fontSize: 11, padding: '2px 9px', border: '1px solid #dadce0',
                                      borderRadius: 4, background: '#fff', cursor: 'pointer', color: '#174ea6',
                                    }}
                                  >
                                    {isOpen ? 'Hide' : 'Steps'}
                                  </button>
                                )}
                              </td>
                            </tr>
                            {isOpen && r.calc_detail && (
                              <tr>
                                <td colSpan={5 + monthLabels.length} style={{ background: '#f8f9fa', borderBottom: '1px solid #dadce0', padding: 0 }}>
                                  <CalcStepsDetail detail={r.calc_detail} />
                                </td>
                              </tr>
                            )}
                          </React.Fragment>
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
      </div>
    </div>
  );
}
