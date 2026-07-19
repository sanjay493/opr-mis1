'use client';

import React, { useState, useEffect, useMemo, useRef, useCallback } from 'react';
import GlobalNavbar from '@/components/GlobalNavbar';

const API = process.env.NEXT_PUBLIC_API_URL || '';

// Display label → item_name in production_table
const ITEMS = [
  { label: 'Sinter',         key: 'Total Sinter' },
  { label: 'Hot Metal',      key: 'Hot Metal' },
  { label: 'Crude Steel',    key: 'Total Crude Steel' },
  { label: 'Saleable Steel', key: 'Saleable Steel' },
  { label: 'Pig Iron',       key: 'Pig Iron' },
  { label: 'Finished Steel', key: 'Finished Steel' },
];

const PLANTS_MAIN5 = ['BSP', 'DSP', 'RSP', 'BSL', 'ISP'];
const UNITS3       = ['ASP', 'SSP', 'VISL'];
const PLANTS_ALL8  = [...PLANTS_MAIN5, ...UNITS3];

const VIEWS = [
  { id: 'SAIL5', label: 'SAIL (5 Plants)' },
  { id: 'SAIL8', label: 'SAIL (8 Plants)' },
  { id: 'PLANT', label: 'Plant-wise' },
  { id: 'UNIT',  label: 'Unit-wise' },
];

const PERIOD_TYPES = [
  { id: 'month',   label: 'Monthly' },
  { id: 'quarter', label: 'Quarterly' },
  { id: 'half',    label: 'Half-Yearly' },
  { id: 'fy',      label: 'Financial Year' },
  { id: 'cy',      label: 'Calendar Year' },
];

// Scopes for the Records section — keys of /api/production-records
const RECORD_SCOPES = [
  { key: 'sail5', label: 'SAIL (5 Plants)', kind: 'Groups' },
  { key: 'all8',  label: 'SAIL (8 Plants)', kind: 'Groups' },
  ...PLANTS_MAIN5.map(p => ({ key: p, label: p, kind: 'Plants' })),
  ...UNITS3.map(p => ({ key: p, label: p, kind: 'Units' })),
];

const MONTH_LABEL = {
  '01': 'January', '02': 'February', '03': 'March', '04': 'April',
  '05': 'May', '06': 'June', '07': 'July', '08': 'August',
  '09': 'September', '10': 'October', '11': 'November', '12': 'December',
};

const QUARTERS = [
  { id: 1, label: 'Q1 (Apr–Jun)' },
  { id: 2, label: 'Q2 (Jul–Sep)' },
  { id: 3, label: 'Q3 (Oct–Dec)' },
  { id: 4, label: 'Q4 (Jan–Mar)' },
];
const HALVES = [
  { id: 1, label: 'H1 (Apr–Sep)' },
  { id: 2, label: 'H2 (Oct–Mar)' },
];

// FY months: April of fy_start … March of fy_start+1
const fyMonths = (fyStart) => [
  ...Array.from({ length: 9 }, (_, i) => `${fyStart}-${String(i + 4).padStart(2, '0')}`),
  ...Array.from({ length: 3 }, (_, i) => `${fyStart + 1}-${String(i + 1).padStart(2, '0')}`),
];
const cyMonths = (year) =>
  Array.from({ length: 12 }, (_, i) => `${year}-${String(i + 1).padStart(2, '0')}`);

const fyOfMonth = (m) => {
  const y = Number(m.slice(0, 4)), mo = Number(m.slice(5, 7));
  return mo >= 4 ? y : y - 1;
};
const shiftYear = (m, delta) => `${Number(m.slice(0, 4)) + delta}${m.slice(4)}`;
const fyLabel = (y) => `${y}-${String(y + 1).slice(2)}`;

const TH = {
  padding: '8px 10px', border: '1px solid #cbd5e1', fontWeight: 700,
  fontSize: 13, backgroundColor: '#1e3a5f', color: '#fff', whiteSpace: 'nowrap',
};
const TD = {
  padding: '6px 10px', border: '1px solid #dadce0', fontSize: 13,
  textAlign: 'right', whiteSpace: 'nowrap', fontVariantNumeric: 'tabular-nums',
};

export default function HighlightsPage() {
  const [fys, setFys]             = useState([]);
  const [view, setView]           = useState('SAIL5');
  const [periodType, setPeriodType] = useState('month');
  const [fyStart, setFyStart]     = useState(null);
  const [monthIdx, setMonthIdx]   = useState(0);   // 0 = April … 11 = March
  const [quarter, setQuarter]     = useState(1);
  const [half, setHalf]           = useState(1);
  const [cyYear, setCyYear]       = useState(null);
  const [fyCache, setFyCache]     = useState({});  // fy_start -> /api/production-fy response
  const [error, setError]         = useState(null);
  const [inTonnes, setInTonnes]   = useState(false);
  const [records, setRecords]     = useState(null);   // /api/production-records response
  const [recordsError, setRecordsError] = useState(null);
  const [recordScope, setRecordScope]   = useState('sail5');
  const inflight = useRef(new Set());

  // ── FY list; default selection = period containing last month ──────────────
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
          setFyStart(fy);
          setCyYear(Number(prevKey.slice(0, 4)));
          const idx = fyMonths(fy).indexOf(prevKey);
          if (idx >= 0) {
            setMonthIdx(idx);
            setQuarter(Math.floor(idx / 3) + 1);
            setHalf(idx < 6 ? 1 : 2);
          }
        }
      } catch (e) {
        setError(`Could not load financial years: ${e.message}`);
      }
    })();
  }, []);

  // ── Records (best-ever) data — one fetch, all scopes ────────────────────────
  useEffect(() => {
    (async () => {
      try {
        const r = await fetch(`${API}/api/production-records`);
        if (!r.ok) throw new Error(await r.text());
        setRecords(await r.json());
      } catch (e) {
        setRecordsError(`Could not load records: ${e.message}`);
      }
    })();
  }, []);

  // Calendar-year options derived from FY list (each FY touches two years)
  const cyOptions = useMemo(() => {
    const s = new Set();
    fys.forEach(f => { s.add(f.fy_start); s.add(f.fy_start + 1); });
    return [...s].sort((a, b) => b - a);
  }, [fys]);

  // ── Months of the selected period, and same period last year (CPLY) ────────
  const periodMonthList = useMemo(() => {
    if (periodType === 'cy') return cyYear != null ? cyMonths(cyYear) : [];
    if (fyStart == null) return [];
    const all = fyMonths(fyStart);
    if (periodType === 'month')   return [all[monthIdx]];
    if (periodType === 'quarter') return all.slice((quarter - 1) * 3, quarter * 3);
    if (periodType === 'half')    return half === 1 ? all.slice(0, 6) : all.slice(6, 12);
    return all; // fy
  }, [periodType, fyStart, monthIdx, quarter, half, cyYear]);

  const cplyMonthList = useMemo(
    () => periodMonthList.map(m => shiftYear(m, -1)), [periodMonthList]);

  // ── Fetch every FY dataset the two periods touch ───────────────────────────
  const neededFys = useMemo(() => {
    const s = new Set([...periodMonthList, ...cplyMonthList].map(fyOfMonth));
    return [...s].sort();
  }, [periodMonthList, cplyMonthList]);

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

  // ── Value lookup / aggregation ─────────────────────────────────────────────
  const look = useCallback((plant, item, kind, month) => {
    const d = fyCache[fyOfMonth(month)];
    if (!d) return null;
    const it = d.plants?.find(p => p.plant === plant)?.items?.find(i => i.item_name === item);
    return it?.[kind]?.[month] ?? null;
  }, [fyCache]);

  // Sum an item over plants × months; Conversion (plant 'SAIL') only ever adds
  // to Finished Steel, mirroring the Major Production page's SAIL Total.
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

  // ── Column groups for the active view ──────────────────────────────────────
  const groups = useMemo(() => {
    if (view === 'SAIL5') return [{ label: 'SAIL (5 Plants)', plants: PLANTS_MAIN5, conv: false }];
    if (view === 'SAIL8') return [{ label: 'SAIL (8 Plants + Conv.)', plants: PLANTS_ALL8, conv: true }];
    if (view === 'PLANT') return [
      ...PLANTS_MAIN5.map(p => ({ label: p, plants: [p], conv: false })),
      { label: 'Total (5 Plants)', plants: PLANTS_MAIN5, conv: false, isTotal: true },
    ];
    return [
      ...UNITS3.map(p => ({ label: p, plants: [p], conv: false })),
      { label: 'Total (3 Units)', plants: UNITS3, conv: false, isTotal: true },
    ];
  }, [view]);

  const singleGroup = groups.length === 1; // summary views also show CPLY value column

  // rows[item][group] = { plan, actual, ach, cply, growth }
  const rows = useMemo(() => {
    const out = {};
    ITEMS.forEach(({ key }) => {
      out[key] = groups.map(g => {
        const plan   = aggregate(g.plants, key, 'plan',   periodMonthList, g.conv);
        const actual = aggregate(g.plants, key, 'actual', periodMonthList, g.conv);
        const cply   = aggregate(g.plants, key, 'actual', cplyMonthList,   g.conv);
        const ach    = plan != null && plan !== 0 && actual != null ? (actual / plan) * 100 : null;
        const growth = cply != null && cply !== 0 && actual != null ? ((actual - cply) / cply) * 100 : null;
        return { plan, actual, ach, cply, growth };
      });
    });
    return out;
  }, [groups, aggregate, periodMonthList, cplyMonthList]);

  const hasAnyData = ITEMS.some(({ key }) =>
    rows[key].some(c => c.plan != null || c.actual != null));

  // ── Labels & formatting ─────────────────────────────────────────────────────
  const periodLabel = useMemo(() => {
    if (periodType === 'cy') return `Calendar Year ${cyYear ?? ''}`;
    if (fyStart == null) return '';
    if (periodType === 'month') {
      const m = fyMonths(fyStart)[monthIdx];
      return `${MONTH_LABEL[m.slice(5)]} ${m.slice(0, 4)}`;
    }
    if (periodType === 'quarter') return `${QUARTERS[quarter - 1].label} FY ${fyLabel(fyStart)}`;
    if (periodType === 'half')    return `${HALVES[half - 1].label} FY ${fyLabel(fyStart)}`;
    return `Financial Year ${fyLabel(fyStart)}`;
  }, [periodType, fyStart, monthIdx, quarter, half, cyYear]);

  const fmt = (v) => {
    if (v == null) return '—';
    if (inTonnes) return Math.round(v * 1000).toLocaleString('en-IN');
    return v.toFixed(3);
  };
  const fmtPct = (v) => (v == null ? '—' : `${v.toFixed(1)}%`);
  const pctColor = (v, good = 100) =>
    v == null ? '#6b7280' : v >= good ? '#188038' : v >= good - 5 ? '#b45309' : '#c5221f';
  const growthColor = (v) => (v == null ? '#6b7280' : v >= 0 ? '#188038' : '#c5221f');

  // ── Items shown in the Records table for the selected scope ────────────────
  // Single-plant scopes report every unit/item of that plant (BF#1, SMS-2,
  // URM …); group scopes carry only the summary items. Friendly labels are
  // used where an item matches the summary list, raw names otherwise.
  const scopeItems = useMemo(() => {
    const names = records?.[recordScope]?.items;
    if (!names || !names.length) return ITEMS;
    return names.map(name => ITEMS.find(i => i.key === name) || { label: name, key: name });
  }, [records, recordScope]);

  // ── Best-ever records for the selected scope ────────────────────────────────
  // recordRows[itemKey] = { month, quarter, half, fy, cy }, each
  // { best, second } where best/second = {period, total, end} | null —
  // end = last month of the record period, used to flag fresh records.
  // The per-period top-2 sets from the API always contain the global #1 and
  // #2 (the global #2 is either the same period's runner-up or another
  // period's #1), so sorting their union gives both.
  const recordRows = useMemo(() => {
    const scope = records?.[recordScope];
    if (!scope) return null;
    const qEnd = (fy, q) => (q === 4 ? `${fy + 1}-03` : `${fy}-${String(q * 3 + 3).padStart(2, '0')}`);
    const top2 = (arr) => {
      const sorted = [...arr].sort((a, b) => (b.total ?? -Infinity) - (a.total ?? -Infinity));
      return { best: sorted[0] ?? null, second: sorted[1] ?? null };
    };
    const out = {};
    scopeItems.forEach(({ key }) => {
      const monFlat = Object.values(scope.cal_months?.[key] || {}).flat()
        .filter(r => r.total != null)
        .map(r => ({ period: r.period, total: r.total, end: r.month }));

      const qFlat = Object.entries(scope.fy_quarters?.[key] || {}).flatMap(([label, rows]) =>
        (rows || []).filter(r => r.total != null).map(r => ({
          period: `${r.period} ${label}`,
          total: r.total,
          end: qEnd(r.fy_start, Number(label[1])),
        })));

      const hFlat = Object.entries(scope.fy_halves?.[key] || {}).flatMap(([label, rows]) =>
        (rows || []).filter(r => r.total != null).map(r => ({
          period: `${label} ${r.period}`,
          total: r.total,
          end: label.startsWith('H1') ? `${r.fy_start}-09` : `${r.fy_start + 1}-03`,
        })));

      const fyRows = (scope.top5_fy?.[key] || [])
        .map(r => ({ ...r, end: `${parseInt(r.period, 10) + 1}-03` }));
      const cyRows = (scope.top5_cy?.[key] || [])
        .map(r => ({ ...r, end: `${r.period}-12` }));

      out[key] = {
        month:   top2(monFlat),
        quarter: top2(qFlat),
        half:    top2(hFlat),
        fy:      { best: fyRows[0] ?? null, second: fyRows[1] ?? null },
        cy:      { best: cyRows[0] ?? null, second: cyRows[1] ?? null },
      };
    });
    return out;
  }, [records, recordScope, scopeItems]);

  // Months between the record period's end and the newest data month;
  // a record is "just set" when its period ended within the last 3 months.
  const monthsAgo = useCallback((end) => {
    const latest = records?.latest_month;
    if (!latest || !end) return null;
    return (Number(latest.slice(0, 4)) - Number(end.slice(0, 4))) * 12 +
           (Number(latest.slice(5, 7)) - Number(end.slice(5, 7)));
  }, [records]);
  const isFreshRecord = (rec) => {
    const ago = monthsAgo(rec?.end);
    return ago != null && ago >= 0 && ago <= 3;
  };

  const recordsHaveData = recordRows && scopeItems.some(({ key }) =>
    Object.values(recordRows[key] || {}).some(v => v?.best != null));

  const handlePrint = () => window.print();

  const handleDownloadExcel = () => {
    const csvVal = (v) => (v == null ? '' : inTonnes ? String(Math.round(v * 1000)) : v.toFixed(3));
    const escape = (s) => (/[",\r\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s);
    const header = ['Item'];
    groups.forEach(g => {
      header.push(`${g.label} Plan`, `${g.label} Actual`, `${g.label} % Ach`);
      if (singleGroup) header.push(`${g.label} CPLY`);
      header.push(`${g.label} Growth %`);
    });
    const body = ITEMS.map(({ label, key }) => {
      const row = [label];
      rows[key].forEach(c => {
        row.push(csvVal(c.plan), csvVal(c.actual), c.ach == null ? '' : c.ach.toFixed(1));
        if (singleGroup) row.push(csvVal(c.cply));
        row.push(c.growth == null ? '' : c.growth.toFixed(1));
      });
      return row;
    });
    const csv = [header, ...body].map(r => r.map(v => escape(String(v))).join(',')).join('\r\n');
    const blob = new Blob(['﻿' + csv], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `Highlights_${VIEWS.find(v => v.id === view).label.replace(/[^a-z0-9]+/gi, '_')}_${periodLabel.replace(/[^a-z0-9]+/gi, '_')}.csv`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };

  const selectStyle = { padding: '7px 10px', fontSize: 14, border: '1px solid #d1d5db', borderRadius: 4 };
  const labelStyle  = { fontSize: 13, fontWeight: 600, color: '#374151' };
  const groupCols   = singleGroup ? 5 : 4;

  return (
    <div style={{ minHeight: '100vh', background: '#ffffff', fontFamily: "-apple-system,BlinkMacSystemFont,'Segoe UI',Arial,sans-serif" }}>
      <style>{`
        html, body { overflow-y: auto; overflow-x: hidden; }
        @media print {
          @page { size: A4 landscape; margin: 10mm; }
          .hl-table-wrap { overflow: visible !important; border: none !important; }
          .no-print { display: none !important; }
        }
      `}</style>

      <div className="no-print"><GlobalNavbar /></div>

      <div style={{ maxWidth: 1500, margin: '0 auto', padding: '22px 20px' }}>

        {/* ── Title ── */}
        <div style={{ display: 'flex', alignItems: 'baseline', gap: 14, marginBottom: 18, flexWrap: 'wrap' }}>
          <h2 style={{ fontSize: '1.6rem', fontWeight: 700, color: '#202124', margin: 0 }}>
            Production Highlights
          </h2>
          <span style={{ fontSize: 13, color: '#5f6368' }}>
            {VIEWS.find(v => v.id === view).label} · {periodLabel}
          </span>
        </div>

        {/* ── Controls ── */}
        <div className="no-print" style={{
          display: 'flex', gap: 10, alignItems: 'center', flexWrap: 'wrap',
          marginBottom: 18, border: '1px solid #dadce0', borderRadius: 8, padding: '14px 18px',
        }}>
          <label style={labelStyle}>View</label>
          <div style={{ display: 'flex', border: '1px solid #d1d5db', borderRadius: 6, overflow: 'hidden' }}>
            {VIEWS.map(v => (
              <button key={v.id} onClick={() => setView(v.id)} style={{
                padding: '7px 14px', fontSize: 13, fontWeight: 600, border: 'none', cursor: 'pointer',
                background: view === v.id ? '#1a73e8' : '#fff',
                color: view === v.id ? '#fff' : '#374151',
              }}>{v.label}</button>
            ))}
          </div>

          <label style={{ ...labelStyle, marginLeft: 12 }}>Period</label>
          <select value={periodType} onChange={e => setPeriodType(e.target.value)} style={selectStyle}>
            {PERIOD_TYPES.map(p => <option key={p.id} value={p.id}>{p.label}</option>)}
          </select>

          {periodType === 'cy' ? (
            <select value={cyYear ?? ''} onChange={e => setCyYear(Number(e.target.value))} style={selectStyle}>
              {cyOptions.map(y => <option key={y} value={y}>{y}</option>)}
            </select>
          ) : (
            <>
              <select value={fyStart ?? ''} onChange={e => setFyStart(Number(e.target.value))} style={selectStyle}>
                {fys.map(f => <option key={f.fy_start} value={f.fy_start}>FY {f.label}</option>)}
              </select>
              {periodType === 'month' && (
                <select value={monthIdx} onChange={e => setMonthIdx(Number(e.target.value))} style={selectStyle}>
                  {fyStart != null && fyMonths(fyStart).map((m, i) => (
                    <option key={m} value={i}>{MONTH_LABEL[m.slice(5)]} {m.slice(0, 4)}</option>
                  ))}
                </select>
              )}
              {periodType === 'quarter' && (
                <select value={quarter} onChange={e => setQuarter(Number(e.target.value))} style={selectStyle}>
                  {QUARTERS.map(q => <option key={q.id} value={q.id}>{q.label}</option>)}
                </select>
              )}
              {periodType === 'half' && (
                <select value={half} onChange={e => setHalf(Number(e.target.value))} style={selectStyle}>
                  {HALVES.map(h => <option key={h.id} value={h.id}>{h.label}</option>)}
                </select>
              )}
            </>
          )}

          {/* Unit toggle */}
          <div style={{ marginLeft: 12, display: 'flex', border: '1px solid #d1d5db', borderRadius: 6, overflow: 'hidden' }}>
            {[
              { on: false, text: "'000 T" },
              { on: true,  text: 'Tonnes' },
            ].map(({ on, text }) => (
              <button key={text} onClick={() => setInTonnes(on)} style={{
                padding: '7px 14px', fontSize: 13, fontWeight: 600, border: 'none', cursor: 'pointer',
                background: inTonnes === on ? '#1a73e8' : '#fff',
                color: inTonnes === on ? '#fff' : '#374151',
              }}>{text}</button>
            ))}
          </div>

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

        {/* ── Error ── */}
        {error && (
          <div style={{ padding: '10px 16px', borderRadius: 6, marginBottom: 14, fontSize: 14, background: '#fef2f2', color: '#991b1b', border: '1px solid #fca5a5' }}>
            {error}
          </div>
        )}

        {/* ── Table ── */}
        {!loading && !hasAnyData ? (
          <div style={{ color: '#9ca3af', fontSize: 14, padding: '50px 0', textAlign: 'center', border: '2px dashed #dadce0', borderRadius: 8 }}>
            No production data for {periodLabel}.
          </div>
        ) : (
          <div className="hl-table-wrap" style={{ overflowX: 'auto', border: '1px solid #dadce0', borderRadius: 8 }}>
            <table style={{ width: '100%', borderCollapse: 'collapse' }}>
              <thead>
                <tr>
                  <th rowSpan={2} style={{ ...TH, textAlign: 'left', verticalAlign: 'middle' }}>Item</th>
                  {groups.map((g, idx) => (
                    <th key={g.label} colSpan={groupCols} style={{
                      ...TH, textAlign: 'center',
                      backgroundColor: g.isTotal ? '#7c2d12' : TH.backgroundColor,
                      borderLeft: idx > 0 ? '2px solid #64748b' : TH.border,
                    }}>{g.label}</th>
                  ))}
                </tr>
                <tr>
                  {groups.map((g, idx) => (
                    <React.Fragment key={g.label}>
                      <th style={{ ...TH, backgroundColor: '#3e6494', fontWeight: 500, fontSize: 11, textAlign: 'right', borderLeft: idx > 0 ? '2px solid #64748b' : TH.border }}>Plan</th>
                      <th style={{ ...TH, backgroundColor: '#3e6494', fontWeight: 500, fontSize: 11, textAlign: 'right' }}>Actual</th>
                      <th style={{ ...TH, backgroundColor: '#3e6494', fontWeight: 500, fontSize: 11, textAlign: 'right' }}>% Ach</th>
                      {singleGroup && <th style={{ ...TH, backgroundColor: '#3e6494', fontWeight: 500, fontSize: 11, textAlign: 'right' }}>CPLY</th>}
                      <th style={{ ...TH, backgroundColor: '#3e6494', fontWeight: 500, fontSize: 11, textAlign: 'right' }}>Gr %</th>
                    </React.Fragment>
                  ))}
                </tr>
              </thead>
              <tbody>
                {ITEMS.map(({ label, key }, i) => (
                  <tr key={key} style={{ background: i % 2 === 0 ? '#fff' : '#f8fafc' }}>
                    <td style={{ ...TD, textAlign: 'left', fontWeight: 600, color: '#202124' }}>{label}</td>
                    {rows[key].map((c, idx) => (
                      <React.Fragment key={groups[idx].label}>
                        <td style={{ ...TD, color: '#6b7280', borderLeft: idx > 0 ? '2px solid #94a3b8' : TD.border, backgroundColor: groups[idx].isTotal ? '#fff7ed' : undefined }}>{fmt(c.plan)}</td>
                        <td style={{ ...TD, fontWeight: 700, backgroundColor: groups[idx].isTotal ? '#fff7ed' : undefined }}>{fmt(c.actual)}</td>
                        <td style={{ ...TD, fontWeight: 600, color: pctColor(c.ach), backgroundColor: groups[idx].isTotal ? '#fff7ed' : undefined }}>{fmtPct(c.ach)}</td>
                        {singleGroup && <td style={{ ...TD, color: '#6b7280' }}>{fmt(c.cply)}</td>}
                        <td style={{ ...TD, fontWeight: 600, color: growthColor(c.growth), backgroundColor: groups[idx].isTotal ? '#fff7ed' : undefined }}>{fmtPct(c.growth)}</td>
                      </React.Fragment>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {/* ── Footer note ── */}
        <div style={{ marginTop: 14, fontSize: 12, color: '#9ca3af' }}>
          Values stored in '000 tonnes; the Tonnes view multiplies by 1000. Plan = AAP plan (production_plan_table);
          Actual = uploaded/entered production (production_table); months without data are skipped when summing.
          % Ach = Actual ÷ Plan. CPLY = actual of the corresponding period last year; Gr % = growth over CPLY.
          "SAIL (5 Plants)" sums BSP, DSP, RSP, BSL, ISP; "Unit-wise" covers ASP, SSP, VISL; "SAIL (8 Plants)" sums all
          eight plus Conversion (Finished Steel only). Quarters and halves follow the financial year (Q1 = Apr–Jun,
          H1 = Apr–Sep); Calendar Year = Jan–Dec.
        </div>

        {/* ══ Records — best-ever performance (separate section) ══ */}
        <div style={{ marginTop: 34, borderTop: '2px solid #e8eaed', paddingTop: 22 }}>
          <div style={{ display: 'flex', alignItems: 'baseline', gap: 14, marginBottom: 14, flexWrap: 'wrap' }}>
            <h2 style={{ fontSize: '1.35rem', fontWeight: 700, color: '#202124', margin: 0 }}>
              🏆 Best-Ever Records
            </h2>
            <span style={{ fontSize: 13, color: '#5f6368' }}>
              {RECORD_SCOPES.find(s => s.key === recordScope)?.label} · all-time highest production per period
            </span>
          </div>

          {/* Scope selector: groups | plants | units */}
          <div className="no-print" style={{
            display: 'flex', gap: 14, alignItems: 'center', flexWrap: 'wrap',
            marginBottom: 14, border: '1px solid #dadce0', borderRadius: 8, padding: '12px 18px',
          }}>
            {['Groups', 'Plants', 'Units'].map(kind => (
              <div key={kind} style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
                <span style={{ fontSize: 12, fontWeight: 700, color: '#5f6368', textTransform: 'uppercase' }}>{kind}</span>
                <div style={{ display: 'flex', border: '1px solid #d1d5db', borderRadius: 6, overflow: 'hidden' }}>
                  {RECORD_SCOPES.filter(s => s.kind === kind).map(s => (
                    <button key={s.key} onClick={() => setRecordScope(s.key)} style={{
                      padding: '6px 12px', fontSize: 13, fontWeight: 600, border: 'none', cursor: 'pointer',
                      background: recordScope === s.key ? '#188038' : '#fff',
                      color: recordScope === s.key ? '#fff' : '#374151',
                    }}>{s.label}</button>
                  ))}
                </div>
              </div>
            ))}
          </div>

          {recordsError && (
            <div style={{ padding: '10px 16px', borderRadius: 6, marginBottom: 14, fontSize: 14, background: '#fef2f2', color: '#991b1b', border: '1px solid #fca5a5' }}>
              {recordsError}
            </div>
          )}

          {!records && !recordsError ? (
            <div style={{ color: '#9ca3af', fontSize: 14, padding: '30px 0', textAlign: 'center' }}>⟳ Loading records…</div>
          ) : recordRows && !recordsHaveData ? (
            <div style={{ color: '#9ca3af', fontSize: 14, padding: '40px 0', textAlign: 'center', border: '2px dashed #dadce0', borderRadius: 8 }}>
              No production records for {RECORD_SCOPES.find(s => s.key === recordScope)?.label}.
            </div>
          ) : recordRows && (
            <div style={{ overflowX: 'auto', border: '1px solid #dadce0', borderRadius: 8 }}>
              <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                <thead>
                  <tr>
                    <th style={{ ...TH, backgroundColor: '#14532d', textAlign: 'left' }}>Item</th>
                    {['Best Month', 'Best Quarter', 'Best Half', 'Best Financial Year', 'Best Calendar Year'].map(h => (
                      <th key={h} style={{ ...TH, backgroundColor: '#14532d', textAlign: 'center' }}>{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {scopeItems.map(({ label, key }, i) => (
                    <tr key={key} style={{ background: i % 2 === 0 ? '#fff' : '#f8fafc' }}>
                      <td style={{ ...TD, textAlign: 'left', fontWeight: 600, color: '#202124' }}>{label}</td>
                      {['month', 'quarter', 'half', 'fy', 'cy'].map(k => {
                        const rec = recordRows[key]?.[k];
                        const best = rec?.best ?? null;
                        const fresh = best != null && isFreshRecord(best);
                        return (
                          <td key={k} style={{
                            ...TD, textAlign: 'center', verticalAlign: 'top',
                            ...(fresh && {
                              backgroundColor: '#fef3c7',
                              boxShadow: 'inset 0 0 0 2px #f59e0b',
                            }),
                          }}>
                            {best == null ? '—' : (
                              <>
                                {fresh && (
                                  <span style={{
                                    display: 'inline-block', marginRight: 6, padding: '0 6px',
                                    borderRadius: 8, background: '#f59e0b', color: '#fff',
                                    fontSize: 10, fontWeight: 800, verticalAlign: 'middle',
                                  }}>★ NEW</span>
                                )}
                                <span style={{ fontWeight: 700, color: fresh ? '#92400e' : '#14532d' }}>{fmt(best.total)}</span>
                                <br />
                                <span style={{ fontSize: 11, color: fresh ? '#b45309' : '#5f6368' }}>{best.period}</span>
                                {rec.second != null && (
                                  <div style={{
                                    marginTop: 4, paddingTop: 3,
                                    borderTop: '1px dashed #d1d5db',
                                    fontSize: 11, color: '#6b7280',
                                  }}>
                                    <span style={{ fontWeight: 700 }}>2nd · {fmt(rec.second.total)}</span>
                                    <br />
                                    <span style={{ fontSize: 10.5 }}>{rec.second.period}</span>
                                  </div>
                                )}
                              </>
                            )}
                          </td>
                        );
                      })}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          <div style={{ marginTop: 12, fontSize: 12, color: '#9ca3af' }}>
            <span style={{ background: '#fef3c7', border: '1px solid #f59e0b', borderRadius: 4, padding: '0 5px', color: '#92400e', fontWeight: 700 }}>★ NEW</span>{' '}
            marks records just set — the record period ended within the last 3 months of available data.
            Each cell shows the all-time best and, below it, the 2nd best of that period type.
            All-time records from production_table (since Apr 2000), in '000 tonnes (Tonnes view multiplies by 1000).
            Quarters/halves/years count only complete periods (3, 6 or 12 months of data). Best Half/FY/CY show the
            highest complete FY half, financial year and calendar year. Groups sum the member plants and show the
            summary items; selecting a single plant/unit lists every item that plant reports (BF, SMS, mills …).
            Conversion is not included.
          </div>
        </div>
      </div>
    </div>
  );
}
