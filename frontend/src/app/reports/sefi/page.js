'use client';

import React, { useState, useEffect, useMemo, useRef, useCallback } from 'react';
import GlobalNavbar from '@/components/GlobalNavbar';

const API = process.env.NEXT_PUBLIC_API_URL || '';

// Display label → item_name in production_table (matches the SEFI template rows)
const ITEMS = [
  { label: 'Hot Metal',      key: 'Hot Metal' },
  { label: 'Crude Steel',    key: 'Total Crude Steel' },
  { label: 'Finished Steel', key: 'Finished Steel' },
  { label: 'Saleable Steel', key: 'Saleable Steel' },
];

const PLANTS_MAIN5 = ['BSP', 'DSP', 'RSP', 'BSL', 'ISP'];
const UNITS3       = ['ASP', 'SSP', 'VISL'];
const PLANTS_ALL8  = [...PLANTS_MAIN5, ...UNITS3];

const SCOPES = [
  { key: 'sail5', label: 'SAIL (5 Plants)',        plants: PLANTS_MAIN5, conv: false },
  { key: 'sail8', label: 'SAIL (8 Plants + Conv.)', plants: PLANTS_ALL8,  conv: true },
  ...PLANTS_MAIN5.map(p => ({ key: p, label: p, plants: [p], conv: false })),
  ...UNITS3.map(p => ({ key: p, label: p, plants: [p], conv: false })),
];

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

const TH = {
  padding: '8px 10px', border: '1px solid #cbd5e1', fontWeight: 700,
  fontSize: 13, backgroundColor: '#1e3a5f', color: '#fff', whiteSpace: 'nowrap',
};
const TD = {
  padding: '7px 10px', border: '1px solid #dadce0', fontSize: 13,
  textAlign: 'right', whiteSpace: 'nowrap', fontVariantNumeric: 'tabular-nums',
};

export default function SefiReportPage() {
  const [fys, setFys]           = useState([]);
  const [scopeKey, setScopeKey] = useState('sail5');
  const [customStart, setCustomStart] = useState(null);
  const [customEnd, setCustomEnd]     = useState(null);
  const [fyCache, setFyCache]   = useState({});
  const [error, setError]       = useState(null);
  const inflight = useRef(new Set());

  // ── FY list; default range = start of the running FY … last available month ──
  useEffect(() => {
    (async () => {
      try {
        const r = await fetch(`${API}/api/production-fys`);
        const d = await r.json();
        const list = d.fys || [];
        setFys(list);
        if (list.length) {
          const now = new Date();
          const prev = new Date(now.getFullYear(), now.getMonth() - 1, 1);
          const prevKey = `${prev.getFullYear()}-${String(prev.getMonth() + 1).padStart(2, '0')}`;
          const prevFy = fyOfMonth(prevKey);
          const fy = list.some(f => f.fy_start === prevFy) ? prevFy : list[0].fy_start;
          setCustomStart(fyMonths(fy)[0]);
          setCustomEnd(prevKey);
        }
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

  const periodMonthList = useMemo(() => {
    if (!customStart || !customEnd) return [];
    const [s, e] = customStart <= customEnd ? [customStart, customEnd] : [customEnd, customStart];
    return allMonths.filter(m => m >= s && m <= e);
  }, [customStart, customEnd, allMonths]);

  // Corresponding period last year — same calendar months, one FY back
  const cplyMonthList = useMemo(
    () => periodMonthList.map(m => `${Number(m.slice(0, 4)) - 1}-${m.slice(5)}`),
    [periodMonthList],
  );

  const currentFy = periodMonthList.length ? fyOfMonth(periodMonthList[periodMonthList.length - 1]) : null;
  const prevFy    = currentFy != null ? currentFy - 1 : null;

  const neededFys = useMemo(() => {
    const s = new Set(periodMonthList.map(fyOfMonth));
    if (currentFy != null) s.add(currentFy);
    if (prevFy != null) s.add(prevFy);
    return [...s].sort();
  }, [periodMonthList, currentFy, prevFy]);

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

  const look = useCallback((plant, item, kind, month) => {
    const d = fyCache[fyOfMonth(month)];
    if (!d) return null;
    const it = d.plants?.find(p => p.plant === plant)?.items?.find(i => i.item_name === item);
    return it?.[kind]?.[month] ?? null;
  }, [fyCache]);

  const aggregate = useCallback((plants, itemKey, kind, monthList, includeConversion) => {
    let sum = null;
    monthList.forEach(m => {
      plants.forEach(p => {
        const v = look(p, itemKey, kind, m);
        if (v != null) sum = (sum ?? 0) + v;
      });
      if (includeConversion && itemKey === 'Finished Steel') {
        const cv = look('SAIL', 'Conversion', kind, m);
        if (cv != null) sum = (sum ?? 0) + cv;
      }
    });
    return sum != null ? Math.round(sum * 1000) / 1000 : null;
  }, [look]);

  const scope = SCOPES.find(s => s.key === scopeKey);

  const rows = useMemo(() => {
    if (currentFy == null || prevFy == null) return {};
    const out = {};
    ITEMS.forEach(({ key }) => {
      const fyActual = aggregate(scope.plants, key, 'actual', fyMonths(prevFy), scope.conv);
      const abpAnnual = aggregate(scope.plants, key, 'plan', fyMonths(currentFy), scope.conv);
      const periodAbp = aggregate(scope.plants, key, 'plan', periodMonthList, scope.conv);
      const periodAct = aggregate(scope.plants, key, 'actual', periodMonthList, scope.conv);
      const periodCply = aggregate(scope.plants, key, 'actual', cplyMonthList, scope.conv);
      const pctFul = periodAbp != null && periodAbp !== 0 && periodAct != null
        ? (periodAct / periodAbp) * 100 : null;
      const growthPct = periodCply != null && periodCply !== 0 && periodAct != null
        ? ((periodAct - periodCply) / periodCply) * 100 : null;
      out[key] = { fyActual, abpAnnual, periodAbp, periodAct, periodCply, pctFul, growthPct };
    });
    return out;
  }, [scope, currentFy, prevFy, periodMonthList, cplyMonthList, aggregate]);

  const hasAnyData = Object.values(rows).some(c =>
    c.fyActual != null || c.abpAnnual != null || c.periodAbp != null
    || c.periodAct != null || c.periodCply != null);

  const rangeLabel = (list) => {
    if (!list.length) return '';
    const s = list[0], e = list[list.length - 1];
    const sYear = s.slice(0, 4), eYear = e.slice(0, 4);
    const sAbbr = MONTH_ABBR[s.slice(5)], eAbbr = MONTH_ABBR[e.slice(5)];
    if (s === e) return `${sAbbr}'${sYear.slice(2)}`;
    if (sYear === eYear) return `${sAbbr}-${eAbbr}'${eYear.slice(2)}`;
    return `${sAbbr}'${sYear.slice(2)}-${eAbbr}'${eYear.slice(2)}`;
  };
  const periodRangeLabel = useMemo(() => rangeLabel(periodMonthList), [periodMonthList]);
  const cplyRangeLabel   = useMemo(() => rangeLabel(cplyMonthList),   [cplyMonthList]);

  const fmt = (v) => (v == null ? '—' : Math.round(v).toLocaleString('en-IN'));
  const fmtPct = (v) => (v == null ? '—' : `${v.toFixed(1)}%`);
  const fmtGrowth = (v) => (v == null ? '—' : `${v >= 0 ? '▲' : '▼'} ${Math.abs(v).toFixed(1)}%`);
  const pctColor = (v) => (v == null ? '#6b7280' : v >= 100 ? '#188038' : v >= 95 ? '#b45309' : '#c5221f');
  const growthColor = (v) => (v == null ? '#6b7280' : v >= 0 ? '#188038' : '#c5221f');

  const handlePrint = () => window.print();

  const handleDownloadExcel = () => {
    const escape = (s) => (/[",\r\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s);
    const header = ['Item', `FY ${fyLabel(prevFy)}`, `ABP ${fyLabel(currentFy)}`,
      `${periodRangeLabel} ABP`, `${periodRangeLabel} Act`, `${periodRangeLabel} % ful. ABP`,
      `CPLY ${cplyRangeLabel}`, `${periodRangeLabel} Growth %`];
    const body = ITEMS.map(({ label, key }) => {
      const c = rows[key] || {};
      return [label, fmt(c.fyActual), fmt(c.abpAnnual), fmt(c.periodAbp), fmt(c.periodAct),
        c.pctFul == null ? '' : c.pctFul.toFixed(1),
        fmt(c.periodCply), c.growthPct == null ? '' : c.growthPct.toFixed(1)];
    });
    const csv = [header, ...body].map(r => r.map(v => escape(String(v))).join(',')).join('\r\n');
    const blob = new Blob(['﻿' + csv], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `SEFI_Report_${scope.label.replace(/[^a-z0-9]+/gi, '_')}_${periodRangeLabel.replace(/[^a-z0-9]+/gi, '_')}.csv`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };

  const selectStyle = { padding: '7px 10px', fontSize: 14, border: '1px solid #d1d5db', borderRadius: 4 };
  const labelStyle  = { fontSize: 13, fontWeight: 600, color: '#374151' };

  return (
    <div style={{ minHeight: '100vh', background: '#ffffff', fontFamily: "-apple-system,BlinkMacSystemFont,'Segoe UI',Arial,sans-serif" }}>
      <style>{`
        html, body { overflow-y: auto; overflow-x: hidden; }
        @media print {
          @page { size: A4 landscape; margin: 10mm; }
          .sefi-table-wrap { overflow: visible !important; border: none !important; }
          .no-print { display: none !important; }
        }
      `}</style>

      <div className="no-print"><GlobalNavbar /></div>

      <div style={{ maxWidth: 1240, margin: '0 auto', padding: '22px 20px' }}>

        <div style={{ display: 'flex', alignItems: 'baseline', gap: 14, marginBottom: 18, flexWrap: 'wrap' }}>
          <h2 style={{ fontSize: '1.6rem', fontWeight: 700, color: '#202124', margin: 0 }}>
            SEFI Report
          </h2>
          <span style={{ fontSize: 13, color: '#5f6368' }}>
            {scope?.label} · {periodRangeLabel}
          </span>
        </div>

        <div className="no-print" style={{
          display: 'flex', gap: 10, alignItems: 'center', flexWrap: 'wrap',
          marginBottom: 18, border: '1px solid #dadce0', borderRadius: 8, padding: '14px 18px',
        }}>
          <label style={labelStyle}>Plant</label>
          <select value={scopeKey} onChange={e => setScopeKey(e.target.value)} style={selectStyle}>
            {SCOPES.map(s => <option key={s.key} value={s.key}>{s.label}</option>)}
          </select>

          <label style={{ ...labelStyle, marginLeft: 12 }}>From</label>
          <select value={customStart ?? ''} onChange={e => setCustomStart(e.target.value)} style={selectStyle}>
            {allMonths.map(m => (
              <option key={m} value={m}>{MONTH_LABEL[m.slice(5)]} {m.slice(0, 4)}</option>
            ))}
          </select>

          <label style={labelStyle}>To</label>
          <select value={customEnd ?? ''} onChange={e => setCustomEnd(e.target.value)} style={selectStyle}>
            {allMonths.map(m => (
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

        <div style={{ display: 'flex', justifyContent: 'flex-end', fontSize: 12, color: '#5f6368', marginBottom: 4 }}>
          Unit : &apos;000 T
        </div>

        {!loading && !hasAnyData ? (
          <div style={{ color: '#9ca3af', fontSize: 14, padding: '50px 0', textAlign: 'center', border: '2px dashed #dadce0', borderRadius: 8 }}>
            No production data for {periodRangeLabel}.
          </div>
        ) : (
          <div className="sefi-table-wrap" style={{ overflowX: 'auto', border: '1px solid #dadce0', borderRadius: 8 }}>
            <table style={{ width: '100%', borderCollapse: 'collapse' }}>
              <thead>
                <tr>
                  <th rowSpan={2} style={{ ...TH, textAlign: 'left', verticalAlign: 'middle' }}></th>
                  <th rowSpan={2} style={{ ...TH, textAlign: 'center', verticalAlign: 'middle' }}>
                    FY {currentFy != null ? fyLabel(prevFy) : ''}
                  </th>
                  <th rowSpan={2} style={{ ...TH, textAlign: 'center', verticalAlign: 'middle' }}>
                    ABP {currentFy != null ? fyLabel(currentFy) : ''}
                  </th>
                  <th colSpan={5} style={{ ...TH, textAlign: 'center', borderLeft: '2px solid #64748b' }}>
                    {periodRangeLabel}
                  </th>
                </tr>
                <tr>
                  <th style={{ ...TH, backgroundColor: '#3e6494', fontWeight: 500, fontSize: 11, textAlign: 'right', borderLeft: '2px solid #64748b' }}>ABP</th>
                  <th style={{ ...TH, backgroundColor: '#3e6494', fontWeight: 500, fontSize: 11, textAlign: 'right' }}>Act</th>
                  <th style={{ ...TH, backgroundColor: '#3e6494', fontWeight: 500, fontSize: 11, textAlign: 'right' }}>% ful. ABP</th>
                  <th style={{ ...TH, backgroundColor: '#3e6494', fontWeight: 500, fontSize: 11, textAlign: 'right' }}>
                    CPLY{cplyRangeLabel ? ` (${cplyRangeLabel})` : ''}
                  </th>
                  <th style={{ ...TH, backgroundColor: '#3e6494', fontWeight: 500, fontSize: 11, textAlign: 'right' }}>Growth %</th>
                </tr>
              </thead>
              <tbody>
                {ITEMS.map(({ label, key }, i) => {
                  const c = rows[key] || {};
                  return (
                    <tr key={key} style={{ background: i % 2 === 0 ? '#fff' : '#f8fafc' }}>
                      <td style={{ ...TD, textAlign: 'left', fontWeight: 600, color: '#202124' }}>{label}</td>
                      <td style={{ ...TD, color: '#6b7280' }}>{fmt(c.fyActual)}</td>
                      <td style={{ ...TD, fontWeight: 700 }}>{fmt(c.abpAnnual)}</td>
                      <td style={{ ...TD, color: '#6b7280', borderLeft: '2px solid #94a3b8' }}>{fmt(c.periodAbp)}</td>
                      <td style={{ ...TD, fontWeight: 700 }}>{fmt(c.periodAct)}</td>
                      <td style={{ ...TD, fontWeight: 600, color: pctColor(c.pctFul) }}>{fmtPct(c.pctFul)}</td>
                      <td style={{ ...TD, color: '#6b7280' }}>{fmt(c.periodCply)}</td>
                      <td style={{ ...TD, fontWeight: 600, color: growthColor(c.growthPct) }}>{fmtGrowth(c.growthPct)}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}

        <div style={{ marginTop: 14, fontSize: 12, color: '#9ca3af' }}>
          Values in &apos;000 tonnes. FY column = full-year actual of the preceding financial year; ABP column =
          annual plan (AAP) of the current financial year (production_plan_table, summed over all 12 months).
          Period ABP/Act = plan/actual summed over the selected From–To range; % ful. ABP = period Act ÷ period ABP.
          CPLY = actual over the same calendar months one financial year earlier; Growth % = (period Act − CPLY) ÷ CPLY.
          Plant selector sums the member plants of the chosen group (&quot;SAIL (8 Plants)&quot; also adds Conversion to
          Finished Steel); months without data are skipped when summing.
        </div>
      </div>
    </div>
  );
}
