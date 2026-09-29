'use client';

import React, { useState, useEffect, useMemo, useRef, useCallback } from 'react';
import GlobalNavbar from '@/components/GlobalNavbar';

const API = process.env.NEXT_PUBLIC_API_URL || '';

// Steel Bulletin "3.1 Performance" block — four SAIL-level production items.
// key = item_name in production_table (see page_one_page_report.py / sefi/page.js).
const ITEMS = [
  { label: 'Hot Metal\nProduction',      key: 'Hot Metal' },
  { label: 'Crude Steel\nProduction',    key: 'Total Crude Steel' },
  { label: 'Finished Steel\nProduction', key: 'Finished Steel' },
  { label: 'Saleable Steel\nProduction', key: 'Saleable Steel' },
];

// SAIL = the eight producing units. Hot Metal only has rows for the five
// integrated plants, so the null-skipped sum naturally becomes a 5-plant total.
const SAIL_PLANTS = ['BSP', 'DSP', 'RSP', 'BSL', 'ISP', 'ASP', 'SSP', 'VISL'];

const MONTH_LABEL = {
  '01': 'January', '02': 'February', '03': 'March', '04': 'April',
  '05': 'May', '06': 'June', '07': 'July', '08': 'August',
  '09': 'September', '10': 'October', '11': 'November', '12': 'December',
};
const MONTH_ABBR = {
  '01': 'Jan', '02': 'Feb', '03': 'Mar', '04': 'Apr', '05': 'May', '06': 'Jun',
  '07': 'Jul', '08': 'Aug', '09': 'Sep', '10': 'Oct', '11': 'Nov', '12': 'Dec',
};

const fyMonths = (fyStart) => [
  ...Array.from({ length: 9 }, (_, i) => `${fyStart}-${String(i + 4).padStart(2, '0')}`),
  ...Array.from({ length: 3 }, (_, i) => `${fyStart + 1}-${String(i + 1).padStart(2, '0')}`),
];
const fyOfMonth = (m) => {
  const y = Number(m.slice(0, 4)), mo = Number(m.slice(5, 7));
  return mo >= 4 ? y : y - 1;
};
const fyLabel = (y) => `${y}-${String(y + 1).slice(2)}`;
const prevMonthOf = (m) => {
  const y = Number(m.slice(0, 4)), mo = Number(m.slice(5, 7));
  return mo === 1 ? `${y - 1}-12` : `${y}-${String(mo - 1).padStart(2, '0')}`;
};
const sameMonthLastYear = (m) => `${Number(m.slice(0, 4)) - 1}-${m.slice(5)}`;
const mAbbr = (m) => `${MONTH_ABBR[m.slice(5)]}'${m.slice(2, 4)}`;

const TH = {
  padding: '8px 10px', border: '1px solid #cbd5e1', fontWeight: 700,
  fontSize: 12.5, backgroundColor: '#1e3a5f', color: '#fff', whiteSpace: 'pre-line',
  textAlign: 'center', verticalAlign: 'middle',
};
const TD = {
  padding: '7px 10px', border: '1px solid #dadce0', fontSize: 13,
  textAlign: 'right', whiteSpace: 'nowrap', fontVariantNumeric: 'tabular-nums',
};

export default function SteelBulletinPage() {
  const [fys, setFys]         = useState([]);
  const [reportMonth, setReportMonth] = useState(null);
  const [fyCache, setFyCache] = useState({});
  const [error, setError]     = useState(null);
  const inflight = useRef(new Set());

  // ── month list from the FYs that have data; default = latest month ──
  useEffect(() => {
    (async () => {
      try {
        const r = await fetch(`${API}/api/production-fys`);
        const d = await r.json();
        const list = d.fys || [];
        setFys(list);
      } catch (e) {
        setError(`Could not load financial years: ${e.message}`);
      }
    })();
  }, []);

  const allMonths = useMemo(() => {
    const s = new Set();
    fys.forEach(f => fyMonths(f.fy_start).forEach(m => s.add(m)));
    return [...s].sort();
  }, [fys]);

  const currentFy = reportMonth ? fyOfMonth(reportMonth) : null;
  const prevFy    = currentFy != null ? currentFy - 1 : null;
  const prevMonth = reportMonth ? prevMonthOf(reportMonth) : null;
  const cplyMonth = reportMonth ? sameMonthLastYear(reportMonth) : null;

  const neededFys = useMemo(() => {
    if (currentFy == null) return [];
    return [prevFy, currentFy];
  }, [currentFy, prevFy]);

  useEffect(() => {
    neededFys.forEach(fy => {
      if (fyCache[fy] !== undefined || inflight.current.has(fy)) return;
      inflight.current.add(fy);
      (async () => {
        try {
          const r = await fetch(`${API}/api/production-fy?fy_start=${fy}`);
          if (!r.ok) throw new Error(await r.text());
          const d = await r.json();
          setFyCache(prev => ({ ...prev, [fy]: d }));
        } catch (e) {
          setError(`Load failed for FY ${fyLabel(fy)}: ${e.message}`);
          setFyCache(prev => ({ ...prev, [fy]: null }));
        } finally {
          inflight.current.delete(fy);
        }
      })();
    });
  }, [neededFys, fyCache]);

  const loading = neededFys.some(fy => fyCache[fy] === undefined);

  // default the selector once FY data lands: latest month that has production
  useEffect(() => {
    if (reportMonth || !allMonths.length) return;
    const latest = [...allMonths].reverse()[0];
    setReportMonth(latest);
  }, [allMonths, reportMonth]);

  const look = useCallback((plant, item, month) => {
    const d = fyCache[fyOfMonth(month)];
    if (!d) return null;
    const it = d.plants?.find(p => p.plant === plant)?.items?.find(i => i.item_name === item);
    return it?.actual?.[month] ?? null;
  }, [fyCache]);

  // SAIL total for one item in one month — null-skipped sum of the units.
  // Finished Steel also picks up the SAIL-level Conversion figure (matches
  // the one-page report / SEFI "8 Plants + Conv." rollup).
  const sailMonth = useCallback((itemKey, month) => {
    let sum = null;
    SAIL_PLANTS.forEach(p => {
      const v = look(p, itemKey, month);
      if (v != null) sum = (sum ?? 0) + v;
    });
    if (itemKey === 'Finished Steel') {
      const cv = look('SAIL', 'Conversion', month);
      if (cv != null) sum = (sum ?? 0) + cv;
    }
    return sum == null ? null : Math.round(sum * 1000) / 1000;
  }, [look]);

  // SAIL cumulative Apr..endMonth (inclusive)
  const sailCum = useCallback((itemKey, fyStart, endMonth) => {
    const months = fyMonths(fyStart).filter(m => m <= endMonth);
    let sum = null;
    months.forEach(m => {
      const v = sailMonth(itemKey, m);
      if (v != null) sum = (sum ?? 0) + v;
    });
    return sum == null ? null : Math.round(sum * 1000) / 1000;
  }, [sailMonth]);

  const rows = useMemo(() => {
    if (currentFy == null) return [];
    return ITEMS.map(({ label, key }) => {
      const cply    = sailMonth(key, cplyMonth);
      const prev    = sailMonth(key, prevMonth);
      const current = sailMonth(key, reportMonth);
      const cumPrev = sailCum(key, prevFy, cplyMonth);
      const cumCurr = sailCum(key, currentFy, reportMonth);
      const chg = (a, b) => (a == null || b == null || b === 0 ? null : ((a - b) / b) * 100);
      return {
        label, key, cply, prev, current, cumPrev, cumCurr,
        chgCply: chg(current, cply),
        chgPrev: chg(current, prev),
        chgCumCply: chg(cumCurr, cumPrev),
      };
    });
  }, [currentFy, prevFy, reportMonth, prevMonth, cplyMonth, sailMonth, sailCum]);

  const hasAnyData = rows.some(r =>
    r.cply != null || r.prev != null || r.current != null || r.cumPrev != null || r.cumCurr != null);

  // stored in '000 tonnes; displayed in lakh tonnes (1 lakh T = 100 '000 T)
  const fmt = (v) => (v == null ? '—' : (v / 100).toLocaleString('en-IN', {
    minimumFractionDigits: 2, maximumFractionDigits: 2,
  }));
  const fmtPct = (v) => (v == null ? '—' : `${v >= 0 ? '▲' : '▼'} ${Math.abs(v).toFixed(2)}%`);
  const pctColor = (v) => (v == null ? '#6b7280' : v >= 0 ? '#188038' : '#c5221f');

  const handlePrint = () => window.print();

  const handleDownloadExcel = () => {
    const esc = (s) => (/[",\r\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s);
    const header = [
      'Item', mAbbr(cplyMonth), mAbbr(prevMonth), mAbbr(reportMonth),
      `Change over ${mAbbr(cplyMonth)} (%)`, `Change over ${mAbbr(prevMonth)} (%)`,
      `FY ${fyLabel(prevFy)} (till ${mAbbr(cplyMonth)})`,
      `FY ${fyLabel(currentFy)} (till ${mAbbr(reportMonth)})`,
      'Change over CPLY (%)',
    ];
    const body = rows.map(r => [
      r.label.replace('\n', ' '),
      fmt(r.cply), fmt(r.prev), fmt(r.current),
      r.chgCply == null ? '' : r.chgCply.toFixed(2),
      r.chgPrev == null ? '' : r.chgPrev.toFixed(2),
      fmt(r.cumPrev), fmt(r.cumCurr),
      r.chgCumCply == null ? '' : r.chgCumCply.toFixed(2),
    ]);
    const meta = [[`SAIL — Inputs for Steel Bulletin — ${reportLabel}`], ['Unit: Lakh Tonne'], []];
    const csv = [...meta, header, ...body].map(r => r.map(v => esc(String(v))).join(',')).join('\r\n');
    const blob = new Blob(['﻿' + csv], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `Steel_Bulletin_SAIL_${reportMonth}.csv`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };

  const selectStyle = { padding: '7px 10px', fontSize: 14, border: '1px solid #d1d5db', borderRadius: 4 };
  const labelStyle  = { fontSize: 13, fontWeight: 600, color: '#374151' };

  const reportLabel = reportMonth
    ? `${MONTH_LABEL[reportMonth.slice(5)]} ${reportMonth.slice(0, 4)}`
    : '';

  return (
    <div style={{ minHeight: '100vh', background: '#ffffff', fontFamily: "-apple-system,BlinkMacSystemFont,'Segoe UI',Arial,sans-serif" }}>
      <style>{`
        html, body { overflow-y: auto; overflow-x: hidden; }
        @media print {
          @page { size: A4 landscape; margin: 12mm; }
          .sb-table-wrap { overflow: visible !important; border: none !important; }
          .no-print { display: none !important; }
        }
      `}</style>

      <div className="no-print"><GlobalNavbar /></div>

      <div style={{ maxWidth: 1180, margin: '0 auto', padding: '22px 20px' }}>

        <div style={{ display: 'flex', alignItems: 'baseline', gap: 14, marginBottom: 6, flexWrap: 'wrap' }}>
          <h2 style={{ fontSize: '1.6rem', fontWeight: 700, color: '#202124', margin: 0 }}>
            Inputs for Steel Bulletin
          </h2>
          <span style={{ fontSize: 13, color: '#5f6368' }}>SAIL · {reportLabel}</span>
        </div>
        <div style={{ fontSize: 13, color: '#5f6368', marginBottom: 16 }}>
          3. Steel Authority of India Limited (SAIL) — 3.1 Performance
        </div>

        <div className="no-print" style={{
          display: 'flex', gap: 10, alignItems: 'center', flexWrap: 'wrap',
          marginBottom: 18, border: '1px solid #dadce0', borderRadius: 8, padding: '14px 18px',
        }}>
          <label style={labelStyle}>Report month</label>
          <select value={reportMonth ?? ''} onChange={e => setReportMonth(e.target.value)} style={selectStyle}>
            {[...allMonths].reverse().map(m => (
              <option key={m} value={m}>{MONTH_LABEL[m.slice(5)]} {m.slice(0, 4)}</option>
            ))}
          </select>

          <button onClick={handlePrint} disabled={loading || !hasAnyData} style={{
            marginLeft: 12, padding: '7px 16px', fontSize: 13, fontWeight: 600, borderRadius: 6,
            border: '1px solid #d1d5db', cursor: !loading && hasAnyData ? 'pointer' : 'not-allowed',
            background: '#fff', color: '#374151', opacity: !loading && hasAnyData ? 1 : 0.5,
          }}>🖨 Print</button>

          <button onClick={handleDownloadExcel} disabled={loading || !hasAnyData} style={{
            padding: '7px 16px', fontSize: 13, fontWeight: 600, borderRadius: 6,
            border: '1px solid #188038', cursor: !loading && hasAnyData ? 'pointer' : 'not-allowed',
            background: '#e6f4ea', color: '#188038', opacity: !loading && hasAnyData ? 1 : 0.5,
          }}>⬇ Download Excel</button>

          <span style={{ marginLeft: 'auto', fontSize: 13, color: '#5f6368' }}>
            {loading && '⟳ loading…'}
          </span>
        </div>

        {error && (
          <div style={{ padding: '10px 16px', borderRadius: 6, marginBottom: 14, fontSize: 14, background: '#fef2f2', color: '#991b1b', border: '1px solid #fca5a5' }}>
            {error}
          </div>
        )}

        {reportMonth && (
          <p style={{ fontSize: 13.5, color: '#374151', margin: '0 0 10px' }}>
            As of {reportLabel}, performance of SAIL is summarized below:
          </p>
        )}

        <div style={{ display: 'flex', justifyContent: 'flex-end', fontSize: 12, color: '#5f6368', marginBottom: 4 }}>
          Unit : Lakh Tonne
        </div>

        {!loading && !hasAnyData ? (
          <div style={{ color: '#9ca3af', fontSize: 14, padding: '50px 0', textAlign: 'center', border: '2px dashed #dadce0', borderRadius: 8 }}>
            No production data for {reportLabel}.
          </div>
        ) : reportMonth && (
          <div className="sb-table-wrap" style={{ overflowX: 'auto', border: '1px solid #dadce0', borderRadius: 8 }}>
            <table style={{ width: '100%', borderCollapse: 'collapse' }}>
              <thead>
                <tr>
                  <th style={{ ...TH, textAlign: 'left' }}>Item</th>
                  <th style={TH}>{mAbbr(cplyMonth)}</th>
                  <th style={TH}>{mAbbr(prevMonth)}</th>
                  <th style={TH}>{mAbbr(reportMonth)}</th>
                  <th style={{ ...TH, borderLeft: '2px solid #64748b' }}>{`Change over\n${mAbbr(cplyMonth)} (%)`}</th>
                  <th style={TH}>{`Change over\n${mAbbr(prevMonth)} (%)`}</th>
                  <th style={{ ...TH, borderLeft: '2px solid #64748b' }}>{`FY ${fyLabel(prevFy)}\n(till ${mAbbr(cplyMonth)})`}</th>
                  <th style={TH}>{`FY ${fyLabel(currentFy)}\n(till ${mAbbr(reportMonth)})`}</th>
                  <th style={TH}>{'Change over\nCPLY (%)'}</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((r, i) => (
                  <tr key={r.key} style={{ background: i % 2 === 0 ? '#fff' : '#f8fafc' }}>
                    <td style={{ ...TD, textAlign: 'left', fontWeight: 600, color: '#202124', whiteSpace: 'pre-line' }}>{r.label}</td>
                    <td style={{ ...TD, color: '#6b7280' }}>{fmt(r.cply)}</td>
                    <td style={{ ...TD, color: '#6b7280' }}>{fmt(r.prev)}</td>
                    <td style={{ ...TD, fontWeight: 700 }}>{fmt(r.current)}</td>
                    <td style={{ ...TD, fontWeight: 600, color: pctColor(r.chgCply), borderLeft: '2px solid #94a3b8' }}>{fmtPct(r.chgCply)}</td>
                    <td style={{ ...TD, fontWeight: 600, color: pctColor(r.chgPrev) }}>{fmtPct(r.chgPrev)}</td>
                    <td style={{ ...TD, color: '#6b7280', borderLeft: '2px solid #94a3b8' }}>{fmt(r.cumPrev)}</td>
                    <td style={{ ...TD, fontWeight: 700 }}>{fmt(r.cumCurr)}</td>
                    <td style={{ ...TD, fontWeight: 600, color: pctColor(r.chgCumCply) }}>{fmtPct(r.chgCumCply)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        <div style={{ marginTop: 14, fontSize: 12, color: '#9ca3af' }}>
          Values in lakh tonnes (stored as &apos;000 T, shown &divide; 100). SAIL = null-skipped sum of the producing units
          (BSP, DSP, RSP, BSL, ISP, ASP, SSP, VISL; Hot Metal has only the five integrated
          plants). Finished Steel also includes the SAIL-level Conversion figure. Columns mirror &quot;Inputs for Steel Bulletin&quot; 3.1 Performance:
          same month last year (CPLY), previous month, report month, their %-changes,
          the April&ndash;to&ndash;date cumulatives for the current and previous financial
          years, and the change over CPLY on the cumulative. Source: production_table via
          /api/production-fy. Months without data are skipped when summing.
        </div>
      </div>
    </div>
  );
}
