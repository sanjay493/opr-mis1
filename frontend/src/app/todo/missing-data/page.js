'use client';

import RequireEditor from '@/components/RequireEditor';

import React, { useState, useEffect, useMemo, useCallback } from 'react';
import GlobalNavbar from '@/components/GlobalNavbar';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || '';

// FY-ordered (April first), same convention as data-entry/uploads/page.js.
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
  (_, i) => (YEAR_RANGE_START + i).toString()
);

function getDefaultPeriod() {
  const d = new Date();
  d.setMonth(d.getMonth() - 1);
  const names = ['January','February','March','April','May','June','July','August','September','October','November','December'];
  return { month: names[d.getMonth()], year: d.getFullYear().toString() };
}

function formatMonth(year, month) {
  return `${year}-${MONTH_NUM[month]}`;
}

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

function StatusBadge({ present }) {
  return (
    <span style={{
      display: 'inline-flex', alignItems: 'center', gap: 4,
      padding: '2px 9px', borderRadius: 12, fontSize: 11.5, fontWeight: 700,
      background: present ? '#f0fdf4' : '#fef2f2',
      color: present ? '#166534' : '#991b1b',
      border: `1px solid ${present ? '#86efac' : '#fca5a5'}`,
    }}>
      {present ? '✓ Present' : '✗ Missing'}
    </span>
  );
}

function SectionCard({ section }) {
  const missingCount = section.checks.filter(c => !c.present).length;
  return (
    <div style={{
      marginBottom: 14, background: '#fff', border: '1px solid #dadce0',
      borderRadius: 8, overflow: 'hidden',
    }}>
      <div style={{
        padding: '10px 16px', background: missingCount ? '#fffbeb' : '#f8f9fa',
        borderBottom: '1px solid #dadce0', display: 'flex', justifyContent: 'space-between',
        alignItems: 'center', flexWrap: 'wrap', gap: 6,
      }}>
        <div>
          <div style={{ fontSize: 14, fontWeight: 700, color: '#202124' }}>{section.title}</div>
          <div style={{ fontSize: 11.5, color: '#5f6368' }}>Report page(s): {section.report_pages}</div>
        </div>
        <div style={{ fontSize: 12, fontWeight: 600, color: missingCount ? '#92400e' : '#166534' }}>
          {missingCount ? `${missingCount} missing` : 'all present'}
        </div>
      </div>
      <table style={{ borderCollapse: 'collapse', width: '100%' }}>
        <tbody>
          {section.checks.map((c, i) => (
            <tr key={c.label + i} style={{ borderBottom: i === section.checks.length - 1 ? 'none' : '1px solid #f1f3f4' }}>
              <td style={{ padding: '7px 16px', fontSize: 13, fontWeight: 600, color: '#374151', width: 110 }}>{c.label}</td>
              <td style={{ padding: '7px 10px', width: 110 }}><StatusBadge present={c.present} /></td>
              <td style={{ padding: '7px 16px' }}>
                {!c.present && (
                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, alignItems: 'center' }}>
                    <span style={{ fontSize: 11.5, color: '#5f6368' }}>Go to:</span>
                    {c.data_entry.map((d, j) => (
                      <a key={j} href={d.link} style={{
                        fontSize: 12, color: '#1a73e8', textDecoration: 'none',
                        padding: '2px 8px', border: '1px solid #bfdbfe', borderRadius: 5,
                        background: '#eff6ff',
                      }}>
                        {d.label}
                      </a>
                    ))}
                  </div>
                )}
                {c.note && (
                  <div style={{ fontSize: 11, color: '#92400e', marginTop: c.present ? 0 : 4 }}>⚠ {c.note}</div>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function MissingDataInner() {
  const def = getDefaultPeriod();
  const [month, setMonth] = useState(def.month);
  const [year, setYear] = useState(def.year);
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [onlyMissing, setOnlyMissing] = useState(false);

  const reportMonth = useMemo(() => formatMonth(year, month), [year, month]);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`${API_BASE_URL}/api/missing-data?month=${reportMonth}`);
      const json = await parseJsonResponse(res);
      if (!res.ok) throw new Error(json.detail || 'Failed to load');
      setData(json);
    } catch (err) {
      setError(err.message);
      setData(null);
    } finally {
      setLoading(false);
    }
  }, [reportMonth]);

  useEffect(() => { load(); }, [load]);

  const visibleSections = useMemo(() => {
    if (!data) return [];
    if (!onlyMissing) return data.sections;
    return data.sections
      .map(s => ({ ...s, checks: s.checks.filter(c => !c.present) }))
      .filter(s => s.checks.length > 0);
  }, [data, onlyMissing]);

  return (
    <div style={{ height: '100vh', display: 'flex', flexDirection: 'column', background: '#f8f9fa' }}>
      <GlobalNavbar />

      <div style={{ flex: 1, overflow: 'auto', maxWidth: 1100, margin: '0 auto', padding: '22px 20px', width: '100%', boxSizing: 'border-box' }}>

        <div style={{ marginBottom: 18 }}>
          <h2 style={{ fontSize: '1.6rem', fontWeight: 700, color: '#202124', margin: '0 0 4px' }}>
            Missing Data Checklist — OMI Report
          </h2>
          <span style={{ fontSize: 13, color: '#5f6368' }}>
            For the selected month, which monthly data sources behind the OMI Report (<code style={{ fontSize: 12 }}>/report</code>)
            {' '}have and haven&apos;t been submitted yet — grouped by report page, broken down per plant/source where relevant,
            with the exact data-entry or upload page to visit. Covers the recurring monthly sources only — annual targets/plans,
            reference/master data, and a few pages not yet wired into the live report are intentionally left out (see the
            checklist&apos;s own scope note in <code style={{ fontSize: 12 }}>backend/page_missing_data.py</code>).
          </span>
        </div>

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

          <label style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 13, color: '#374151', marginLeft: 12, cursor: 'pointer' }}>
            <input type="checkbox" checked={onlyMissing} onChange={e => setOnlyMissing(e.target.checked)} />
            Show missing only
          </label>

          {data && (
            <span style={{
              marginLeft: 'auto', fontSize: 13, fontWeight: 700,
              color: data.missing_count ? '#b45309' : '#166534',
            }}>
              {data.missing_count} of {data.total_checks} sources missing for {reportMonth}
            </span>
          )}
        </div>

        {loading && <div style={{ fontSize: 13, color: '#5f6368' }}>Loading…</div>}
        {error && (
          <div style={{
            padding: '8px 14px', borderRadius: 6, marginBottom: 14, fontSize: 13,
            background: '#fef2f2', color: '#991b1b', border: '1px solid #fca5a5',
          }}>
            {error}
          </div>
        )}

        {!loading && !error && visibleSections.length === 0 && data && (
          <div style={{ fontSize: 13, color: '#166534', fontWeight: 600 }}>
            Nothing missing — every tracked source has data for {reportMonth}.
          </div>
        )}

        {!loading && visibleSections.map(s => <SectionCard key={s.id} section={s} />)}
      </div>
    </div>
  );
}

export default function MissingDataPage() {
  return (
    <RequireEditor>
      <MissingDataInner />
    </RequireEditor>
  );
}
