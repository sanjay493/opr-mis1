'use client';

// Shared body for /data-entry/coal-consumption and /data-entry/co2-water-pm —
// both are pure "as extracted" viewers over techno_data (unit="General",
// written by the Coal Consumption & CO2/Water/PM EPI extractor on
// /data-entry/techno), scoped to a fixed param list. No new backend code:
// reuses GET /api/techno/data the same way TechnoDataPanel and
// /reports/techno-monthly already do, fetched once per plant client-side
// since that endpoint takes a single plant per call.

import React, { useState, useEffect } from 'react';
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
const CURRENT_FY_END_YEAR = (_now.getMonth() >= 3 ? _now.getFullYear() : _now.getFullYear() - 1) + 1;
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
  return n.toLocaleString('en-IN', { maximumFractionDigits: 3 });
}

// FY runs April->March. Some params (e.g. coal consumption) are reported as
// a monthly figure only, with no cumulative column in the source report, so
// their "till month" has to be built here as a running sum of every month's
// figure from April through the selected month — there's nothing stored in
// techno_data's till_month for these keys to read directly.
function getFyMonths(reportMonth) {
  const [yStr, mStr] = reportMonth.split('-');
  const y = parseInt(yStr, 10);
  const m = parseInt(mStr, 10);
  const fyStartYear = m >= 4 ? y : y - 1;
  const months = [];
  let cy = fyStartYear;
  let cm = 4;
  for (let i = 0; i < 12; i += 1) {
    const key = `${cy}-${String(cm).padStart(2, '0')}`;
    months.push(key);
    if (key === reportMonth) break;
    cm += 1;
    if (cm > 12) { cm = 1; cy += 1; }
  }
  return months;
}

const cell = {
  padding: '7px 12px',
  fontSize: '10.5pt',
  borderBottom: '1px solid #e8eaed',
  whiteSpace: 'nowrap',
};

export default function TechnoExtractedParams({ title, description, paramRows, sumTillMonthKeys = [], renderExtra }) {
  const def = getDefaultPeriod();
  const [monthName, setMonthName] = useState(def.monthName);
  const [year, setYear] = useState(def.year);
  // {plant: {monthKey: {month:{}, till_month:{}}}} — a single month when no
  // param needs the summed till-month, else every FY-to-date month so the
  // sum can be computed below.
  const [dataByPlant, setDataByPlant] = useState({});
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const reportMonth = `${year}-${MONTH_NUM[monthName]}`;
  const fyMonths = sumTillMonthKeys.length ? getFyMonths(reportMonth) : [reportMonth];

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    Promise.all(
      PLANTS.flatMap((p) =>
        fyMonths.map((m) =>
          fetch(`${API_BASE_URL}/api/techno/data?plant=${p}&report_month=${m}&unit=General`)
            .then((r) => (r.ok ? r.json() : { data: {} }))
            .then((j) => [p, m, j.data?.General || {}])
            .catch(() => [p, m, {}])
        )
      )
    )
      .then((entries) => {
        if (cancelled) return;
        const byPlant = {};
        for (const [p, m, d] of entries) {
          if (!byPlant[p]) byPlant[p] = {};
          byPlant[p][m] = d;
        }
        setDataByPlant(byPlant);
      })
      .catch((e) => { if (!cancelled) setError(`Failed to load: ${e.message}`); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [reportMonth, sumTillMonthKeys]);

  // Sums the "month" figure across every FY-to-date month for a plant/key.
  // Returns null (renders as "—") if not one of those months has a value,
  // rather than reporting a misleading 0.
  function summedTillMonth(plant, key) {
    let sum = 0;
    let found = false;
    for (const m of fyMonths) {
      const v = dataByPlant[plant]?.[m]?.month?.[key];
      if (v !== null && v !== undefined && v !== '') {
        sum += Number(v);
        found = true;
      }
    }
    return found ? sum : null;
  }

  const selStyle = {
    padding: '8px 12px', fontSize: '11pt', border: '1px solid #dadce0',
    borderRadius: '6px', backgroundColor: '#ffffff', color: '#202124', cursor: 'pointer',
  };

  const th = (extra = {}) => ({
    ...cell, position: 'sticky', top: 0, zIndex: 2, backgroundColor: '#e8f0fe',
    fontWeight: 700, color: '#174ea6', textAlign: 'right', ...extra,
  });

  const hasAnyData = PLANTS.some((p) => {
    const d = dataByPlant[p]?.[reportMonth];
    return d && (Object.keys(d.month || {}).length || Object.keys(d.till_month || {}).length);
  });

  return (
    <div style={{ minHeight: '100vh', backgroundColor: '#ffffff' }}>
      <GlobalNavbar />
      <div style={{ maxWidth: '1100px', margin: '0 auto', padding: '32px' }}>

        <div style={{ marginBottom: '24px' }}>
          <h1 style={{ fontSize: '20pt', fontWeight: 900, color: '#202124', margin: 0 }}>{title}</h1>
          <p style={{ fontSize: '11pt', color: '#5f6368', marginTop: '6px' }}>
            {description} For-the-month values as extracted, uploaded from{' '}
            <a href="/data-entry/techno" style={{ color: '#1a73e8' }}>Techno Upload</a>.
            {sumTillMonthKeys.length > 0 && ' Till-month is a running sum of April through the selected month (the source report has no cumulative column for these).'}
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

        {!error && (
          hasAnyData ? (
            <div style={{
              border: '1px solid #dadce0', borderRadius: '8px',
              overflowX: 'auto', maxHeight: 'calc(100vh - 320px)', overflowY: 'auto',
            }}>
              <table style={{ borderCollapse: 'separate', borderSpacing: 0, width: '100%' }}>
                <thead>
                  <tr>
                    <th style={th({ textAlign: 'left', minWidth: '160px' })}>Parameter / Plant</th>
                    <th style={th({ textAlign: 'left', minWidth: '90px' })}>Unit</th>
                    <th style={th()}>{monthName} (Month)</th>
                    <th style={th()}>Till Month</th>
                  </tr>
                </thead>
                <tbody>
                  {paramRows.map((param) => (
                    <React.Fragment key={param.key}>
                      <tr>
                        <td colSpan={4} style={{
                          ...cell, backgroundColor: '#1a73e8', color: '#ffffff',
                          fontWeight: 800, fontSize: '11pt', letterSpacing: '0.02em',
                        }}>
                          {param.label}
                        </td>
                      </tr>
                      {PLANTS.map((p, i) => {
                        const d = dataByPlant[p]?.[reportMonth] || {};
                        // Prefer the stored till_month (now computed server-side at
                        // insert time by the Coal OMI extractor) when present; fall
                        // back to the client-side April-to-date sum only for months
                        // whose earlier-FY history predates that extractor (still
                        // only ever populated by the older PDF/docx path, which
                        // never wrote till_month for these keys).
                        const isSummed = sumTillMonthKeys.includes(param.key);
                        const stored = d.till_month?.[param.key];
                        const tillMonth = stored !== undefined && stored !== null
                          ? stored
                          : (isSummed ? summedTillMonth(p, param.key) : stored);
                        return (
                          <tr key={p} style={{ backgroundColor: i % 2 === 1 ? '#f8f9fa' : '#ffffff' }}>
                            <td style={{ ...cell, fontWeight: 600 }}>{p}</td>
                            <td style={{ ...cell, color: '#5f6368' }}>{param.unit || '—'}</td>
                            <td style={{ ...cell, textAlign: 'right', fontWeight: 700 }}>{fmtNum(d.month?.[param.key])}</td>
                            <td style={{ ...cell, textAlign: 'right', fontWeight: 700, color: '#174ea6' }}>{fmtNum(tillMonth)}</td>
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
              No data for {reportMonth} — upload the EPI report on{' '}
              <a href="/data-entry/techno" style={{ color: '#1a73e8' }}>Techno Upload</a>.
            </div>
          )
        )}

        {renderExtra && renderExtra(reportMonth)}
      </div>
    </div>
  );
}
