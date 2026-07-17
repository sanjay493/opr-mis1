'use client';

import React, { useState, useEffect, useCallback, useMemo } from 'react';
import GlobalNavbar from '@/components/GlobalNavbar';

const API = process.env.NEXT_PUBLIC_API_URL || 'http://127.0.0.1:8082';

// ── Row definitions (Annexure-III: "Production Performance of new facilities") ──
// `sources` = production_table / production_plan_table (plant, item_name) pairs
// summed to produce that row's value. Mappings verified against the sample
// Annexure-III.pdf (Apr/May/Jun'25 actuals matched to the '000T decimal).
const SECTIONS = [
  {
    title: 'HOT METAL',
    rows: [
      { label: 'BSP BF-8',  indent: 0, sources: [{ plant: 'BSP', item: 'BF#8' }] },
      { label: 'RSP Total', indent: 0, bold: true, sources: [{ plant: 'RSP', item: 'Hot Metal' }] },
      { label: 'BF-1',      indent: 1, sources: [{ plant: 'RSP', item: 'BF#1' }] },
      { label: 'BF-5',      indent: 1, sources: [{ plant: 'RSP', item: 'BF#5' }] },
      { label: 'ISP BF-5',  indent: 0, sources: [{ plant: 'ISP', item: 'Hot Metal' }] },
    ],
    // Total = BSP BF-8 + RSP Total + ISP BF-5 (the three non-indented rows above)
    totalSources: [
      { plant: 'BSP', item: 'BF#8' },
      { plant: 'RSP', item: 'Hot Metal' },
      { plant: 'ISP', item: 'Hot Metal' },
    ],
  },
  {
    title: 'CRUDE STEEL',
    rows: [
      {
        label: 'BSP SMS-3', indent: 0,
        sources: [{ plant: 'BSP', item: 'SMS-3' }],
        // production_plan_table has no plain 'SMS-3' for BSP; its ABP plan is
        // split into these three product-grade sub-items instead.
        planSources: [
          { plant: 'BSP', item: 'SMS-3 BILLET105' },
          { plant: 'BSP', item: 'SMS-3 BILLET150' },
          { plant: 'BSP', item: 'SMS-3 BLOOM(CV1&2)' },
        ],
      },
      { label: 'DSP BRC',              indent: 0, sources: [{ plant: 'DSP', item: 'BRC' }] },
      { label: 'RSP SMS-2 Caster-3',   indent: 0, sources: [{ plant: 'RSP', item: 'SMS-2 CCM-3' }] },
      { label: 'BSL SMS-1 Caster-1',   indent: 0, sources: [{ plant: 'BSL', item: 'SMS-1 CCM-1' }] },
      { label: 'ISP SMS',              indent: 0, sources: [{ plant: 'ISP', item: 'Total Crude Steel' }] },
    ],
    totalSources: [
      { plant: 'BSP', item: 'SMS-3' },
      { plant: 'DSP', item: 'BRC' },
      { plant: 'RSP', item: 'SMS-2 CCM-3' },
      { plant: 'BSL', item: 'SMS-1 CCM-1' },
      { plant: 'ISP', item: 'Total Crude Steel' },
    ],
    totalPlanSources: [
      { plant: 'BSP', item: 'SMS-3 BILLET105' },
      { plant: 'BSP', item: 'SMS-3 BILLET150' },
      { plant: 'BSP', item: 'SMS-3 BLOOM(CV1&2)' },
      { plant: 'DSP', item: 'BRC' },
      { plant: 'RSP', item: 'SMS-2 CCM-3' },
      { plant: 'BSL', item: 'SMS-1 CCM-1' },
      { plant: 'ISP', item: 'Total Crude Steel' },
    ],
  },
  {
    title: 'SALEABLE STEEL',
    rows: [
      { label: 'BSP Total', indent: 0, bold: true, sources: [{ plant: 'BSP', item: 'URM_RAIL' }, { plant: 'BSP', item: 'BARS&RODMILL' }] },
      { label: 'URM',       indent: 1, sources: [{ plant: 'BSP', item: 'URM_RAIL' }] },
      { label: 'BRM',       indent: 1, sources: [{ plant: 'BSP', item: 'BARS&RODMILL' }] },
      { label: 'DSP MSM',   indent: 0, sources: [{ plant: 'DSP', item: 'MSM' }] },
      { label: 'RSP Total', indent: 0, bold: true, sources: [{ plant: 'RSP', item: 'HSM-2 Total HR Coil' }, { plant: 'RSP', item: 'NPM Plate' }] },
      { label: 'New HSM',   indent: 1, sources: [{ plant: 'RSP', item: 'HSM-2 Total HR Coil' }] },
      { label: 'NPM',       indent: 1, sources: [{ plant: 'RSP', item: 'NPM Plate' }] },
      { label: 'BSL CRM-III', indent: 0, sources: [{ plant: 'BSL', item: 'CRC(3)' }, { plant: 'BSL', item: 'CRC&S(1&2)' }] },
      { label: 'ISP WRM',      indent: 0, sources: [{ plant: 'ISP', item: 'WRMILL' }] },
      { label: 'BAR MILL',     indent: 1, sources: [{ plant: 'ISP', item: 'BARMILL' }] },
      { label: 'USM',          indent: 1, sources: [{ plant: 'ISP', item: 'USMILL' }] },
    ],
    totalSources: [
      { plant: 'BSP', item: 'URM_RAIL' }, { plant: 'BSP', item: 'BARS&RODMILL' },
      { plant: 'DSP', item: 'MSM' },
      { plant: 'RSP', item: 'HSM-2 Total HR Coil' }, { plant: 'RSP', item: 'NPM Plate' },
      { plant: 'BSL', item: 'CRC(3)' }, { plant: 'BSL', item: 'CRC&S(1&2)' },
      { plant: 'ISP', item: 'WRMILL' }, { plant: 'ISP', item: 'BARMILL' }, { plant: 'ISP', item: 'USMILL' },
    ],
  },
];

const QUARTERS = [
  { q: 1, label: 'Q1 (Apr-Jun)',  months: [4, 5, 6] },
  { q: 2, label: 'Q2 (Jul-Sep)',  months: [7, 8, 9] },
  { q: 3, label: 'Q3 (Oct-Dec)',  months: [10, 11, 12] },
  { q: 4, label: 'Q4 (Jan-Mar)',  months: [1, 2, 3] },
];

const MONTH_NAME = {
  1: 'Jan', 2: 'Feb', 3: 'Mar', 4: 'Apr', 5: 'May', 6: 'Jun',
  7: 'Jul', 8: 'Aug', 9: 'Sep', 10: 'Oct', 11: 'Nov', 12: 'Dec',
};

// months 1-3 (Jan-Mar) belong to the calendar year AFTER fy_start
function quarterMonthKeys(fyStart, quarterDef) {
  return quarterDef.months.map(m => {
    const year = m >= 4 ? fyStart : fyStart + 1;
    return `${year}-${String(m).padStart(2, '0')}`;
  });
}

const ALL_FY_MONTH_NUMS = [4, 5, 6, 7, 8, 9, 10, 11, 12, 1, 2, 3];
function allFyMonthKeys(fyStart) {
  return ALL_FY_MONTH_NUMS.map(m => {
    const year = m >= 4 ? fyStart : fyStart + 1;
    return `${year}-${String(m).padStart(2, '0')}`;
  });
}

const TH = {
  padding: '6px 8px', border: '1px solid #cbd5e1', fontWeight: 700,
  fontSize: 12, backgroundColor: '#1e3a5f', color: '#fff', whiteSpace: 'nowrap',
};
const TD = {
  padding: '5px 8px', border: '1px solid #dadce0', fontSize: 12,
  textAlign: 'right', whiteSpace: 'nowrap', fontVariantNumeric: 'tabular-nums',
};

export default function NewFacilitiesPage() {
  const [fys, setFys] = useState([]);
  const [fyStart, setFyStart] = useState(null);
  const [quarter, setQuarter] = useState(1);
  const [curData, setCurData] = useState(null);   // this FY, from /api/production-fy
  const [prevData, setPrevData] = useState(null); // FY-1, same endpoint
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    (async () => {
      try {
        const r = await fetch(`${API}/api/production-fys`);
        const d = await r.json();
        setFys(d.fys || []);
        if (d.fys?.length) setFyStart(d.fys[0].fy_start);
      } catch (e) {
        setError(`Could not load financial years: ${e.message}`);
      }
    })();
  }, []);

  const loadData = useCallback(async () => {
    if (fyStart == null) return;
    setLoading(true); setError(null);
    try {
      const [rCur, rPrev] = await Promise.all([
        fetch(`${API}/api/production-fy?fy_start=${fyStart}`),
        fetch(`${API}/api/production-fy?fy_start=${fyStart - 1}`),
      ]);
      if (!rCur.ok) throw new Error(await rCur.text());
      setCurData(await rCur.json());
      setPrevData(rPrev.ok ? await rPrev.json() : null);
    } catch (e) {
      setError(`Load failed: ${e.message}`);
      setCurData(null); setPrevData(null);
    } finally {
      setLoading(false);
    }
  }, [fyStart]);

  useEffect(() => { loadData(); }, [loadData]);

  const quarterDef = QUARTERS[quarter - 1];
  const qMonths = fyStart != null ? quarterMonthKeys(fyStart, quarterDef) : [];
  const prevQMonths = fyStart != null ? quarterMonthKeys(fyStart - 1, quarterDef) : [];
  const annualMonths = fyStart != null ? allFyMonthKeys(fyStart) : [];

  const findItem = (dataset, plantName, itemName) =>
    (dataset?.plants || []).find(p => p.plant === plantName)?.items?.find(i => i.item_name === itemName);

  const sumSources = (dataset, sources, month, kind) => {
    let sum = null;
    sources.forEach(({ plant, item }) => {
      const v = findItem(dataset, plant, item)?.[kind]?.[month];
      if (v != null) sum = (sum ?? 0) + v;
    });
    return sum != null ? Math.round(sum * 1000) / 1000 : null;
  };

  const sumOverMonths = (dataset, sources, months, kind) => {
    let sum = null;
    months.forEach(m => {
      const v = sumSources(dataset, sources, m, kind);
      if (v != null) sum = (sum ?? 0) + v;
    });
    return sum != null ? Math.round(sum * 1000) / 1000 : null;
  };

  // Build the full computed row list (leaf rows + section total rows)
  const computedSections = useMemo(() => {
    if (!curData) return [];
    return SECTIONS.map(sec => {
      const buildRow = (label, indent, bold, sources, planSources) => {
        const pSources = planSources || sources;
        const monthCells = qMonths.map(m => {
          const plan = sumSources(curData, pSources, m, 'plan');
          const actual = sumSources(curData, sources, m, 'actual');
          const pctFul = plan ? Math.round((actual ?? 0) / plan * 100) : null;
          return { plan, actual, pctFul };
        });
        const qPlan = sumOverMonths(curData, pSources, qMonths, 'plan');
        const qActual = sumOverMonths(curData, sources, qMonths, 'actual');
        const qPctFul = qPlan ? Math.round((qActual ?? 0) / qPlan * 100) : null;
        const appAnnual = sumOverMonths(curData, pSources, annualMonths, 'plan');
        const prevQActual = prevData ? sumOverMonths(prevData, sources, prevQMonths, 'actual') : null;
        const pctGrowth = (prevQActual != null && prevQActual !== 0 && qActual != null)
          ? Math.round((qActual - prevQActual) / prevQActual * 100) : null;
        return { label, indent, bold, sources, monthCells, qPlan, qActual, qPctFul, appAnnual, prevQActual, pctGrowth };
      };

      const rows = sec.rows.map(r => buildRow(r.label, r.indent, !!r.bold, r.sources, r.planSources));
      const total = buildRow('Total', 0, true, sec.totalSources, sec.totalPlanSources);
      return { title: sec.title, rows, total };
    });
  }, [curData, prevData, qMonths, prevQMonths, annualMonths]);

  const hasAnyData = computedSections.some(sec =>
    sec.rows.some(r => r.monthCells.some(c => c.actual != null || c.plan != null)) ||
    sec.total.monthCells.some(c => c.actual != null || c.plan != null));

  const fmt = (v) => (v == null ? '—' : Math.round(v).toLocaleString('en-IN'));
  const fmtPct = (v) => (v == null ? '—' : `${v}`);
  const fmtGrowth = (v) => (v == null ? '—' : `${v > 0 ? '+' : ''}${v}`);

  const fyLabel = curData?.fy_label || '';
  const prevFyLabel = fys.find(f => f.fy_start === fyStart - 1)?.label
    || (fyStart != null ? `${fyStart - 1}-${String(fyStart)[2] + String(fyStart)[3]}` : '');

  const handlePrint = () => window.print();

  const handleDownloadExcel = () => {
    const escape = (s) => (/[",\r\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s);
    const csvNum = (v) => (v == null ? '' : String(Math.round(v)));

    const header = ['Section', 'Item', 'Annual Capacity', `APP ${fyLabel}`];
    qMonths.forEach(m => {
      const [y, mm] = m.split('-');
      const label = `${MONTH_NAME[Number(mm)]}'${y.slice(2)}`;
      header.push(`${label} APP`, `${label} Actual`, `${label} %Ful`);
    });
    header.push(`Q${quarter} APP`, `Q${quarter} Actual`, `Q${quarter} %Ful`, `Q${quarter} ${prevFyLabel} Actual`, '% Gr. over prev yr');

    const rows = [];
    computedSections.forEach(sec => {
      sec.rows.forEach(r => {
        const row = [sec.title, r.indent ? `  ${r.label}` : r.label, '', csvNum(r.appAnnual)];
        r.monthCells.forEach(c => row.push(csvNum(c.plan), csvNum(c.actual), c.pctFul == null ? '' : String(c.pctFul)));
        row.push(csvNum(r.qPlan), csvNum(r.qActual), r.qPctFul == null ? '' : String(r.qPctFul), csvNum(r.prevQActual), r.pctGrowth == null ? '' : String(r.pctGrowth));
        rows.push(row);
      });
      const t = sec.total;
      const row = [sec.title, 'Total', '', csvNum(t.appAnnual)];
      t.monthCells.forEach(c => row.push(csvNum(c.plan), csvNum(c.actual), c.pctFul == null ? '' : String(c.pctFul)));
      row.push(csvNum(t.qPlan), csvNum(t.qActual), t.qPctFul == null ? '' : String(t.qPctFul), csvNum(t.prevQActual), t.pctGrowth == null ? '' : String(t.pctGrowth));
      rows.push(row);
    });

    const csv = [header, ...rows].map(r => r.map(v => escape(String(v))).join(',')).join('\r\n');
    const blob = new Blob(['﻿' + csv], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `Annexure_III_New_Facilities_Q${quarter}_${fyLabel}.csv`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };

  const monthHeaderLabel = (m) => {
    const [y, mm] = m.split('-');
    return `${MONTH_NAME[Number(mm)]}'${y.slice(2)}`;
  };

  return (
    <div style={{ minHeight: '100vh', background: '#ffffff', fontFamily: "-apple-system,BlinkMacSystemFont,'Segoe UI',Arial,sans-serif" }}>
      <style>{`
        @media print {
          @page { size: A4 landscape; margin: 8mm; }
          .nf-table-wrap { overflow: visible !important; border: none !important; }
        }
      `}</style>

      <div className="no-print"><GlobalNavbar /></div>

      <div style={{ maxWidth: 1700, margin: '0 auto', padding: '22px 20px' }}>

        {/* ── Title ── */}
        <div style={{ display: 'flex', alignItems: 'baseline', gap: 14, marginBottom: 18, flexWrap: 'wrap' }}>
          <h2 style={{ fontSize: '1.6rem', fontWeight: 700, color: '#202124', margin: 0 }}>
            Annexure-III: Production Performance of New Facilities
          </h2>
          <span style={{ fontSize: 13, color: '#5f6368' }}>w.r.t. APP · Unit: '000 T</span>
        </div>

        {/* ── Controls ── */}
        <div className="no-print" style={{
          display: 'flex', gap: 10, alignItems: 'center', flexWrap: 'wrap',
          marginBottom: 18, border: '1px solid #dadce0', borderRadius: 8, padding: '14px 18px',
        }}>
          <label style={{ fontSize: 13, fontWeight: 600, color: '#374151' }}>Financial Year</label>
          <select value={fyStart ?? ''} onChange={e => setFyStart(Number(e.target.value))}
                  style={{ padding: '7px 10px', fontSize: 14, border: '1px solid #d1d5db', borderRadius: 4 }}>
            {fys.map(f => <option key={f.fy_start} value={f.fy_start}>{f.label}</option>)}
          </select>

          <label style={{ fontSize: 13, fontWeight: 600, color: '#374151', marginLeft: 10 }}>Quarter</label>
          <select value={quarter} onChange={e => setQuarter(Number(e.target.value))}
                  style={{ padding: '7px 10px', fontSize: 14, border: '1px solid #d1d5db', borderRadius: 4 }}>
            {QUARTERS.map(q => <option key={q.q} value={q.q}>{q.label}</option>)}
          </select>

          <button onClick={handlePrint} disabled={!curData || !hasAnyData} style={{
            marginLeft: 18, padding: '7px 16px', fontSize: 13, fontWeight: 600, borderRadius: 6,
            border: '1px solid #d1d5db', cursor: curData && hasAnyData ? 'pointer' : 'not-allowed',
            background: '#fff', color: '#374151', opacity: curData && hasAnyData ? 1 : 0.5,
          }}>🖨 Print / Save as PDF</button>

          <button onClick={handleDownloadExcel} disabled={!curData || !hasAnyData} style={{
            padding: '7px 16px', fontSize: 13, fontWeight: 600, borderRadius: 6,
            border: '1px solid #188038', cursor: curData && hasAnyData ? 'pointer' : 'not-allowed',
            background: '#e6f4ea', color: '#188038', opacity: curData && hasAnyData ? 1 : 0.5,
          }}>⬇ Download Excel</button>

          <span style={{ marginLeft: 'auto', fontSize: 13, color: '#5f6368' }}>
            Q{quarter} {fyLabel}{loading && ' ⟳ loading…'}
          </span>
        </div>

        {error && (
          <div style={{ padding: '10px 16px', borderRadius: 6, marginBottom: 14, fontSize: 14, background: '#fef2f2', color: '#991b1b', border: '1px solid #fca5a5' }}>
            {error}
          </div>
        )}

        {!loading && curData && !hasAnyData ? (
          <div style={{ color: '#9ca3af', fontSize: 14, padding: '50px 0', textAlign: 'center', border: '2px dashed #dadce0', borderRadius: 8 }}>
            No production data for Q{quarter} {fyLabel}.
          </div>
        ) : curData && (
          <div className="nf-table-wrap" style={{ overflowX: 'auto', border: '1px solid #dadce0', borderRadius: 8 }}>
            <table style={{ width: '100%', borderCollapse: 'collapse' }}>
              <thead>
                <tr>
                  <th rowSpan={2} style={{ ...TH, textAlign: 'left', verticalAlign: 'middle' }}>Item</th>
                  <th rowSpan={2} style={{ ...TH, textAlign: 'center', verticalAlign: 'middle' }}>Annual<br />Capacity</th>
                  <th rowSpan={2} style={{ ...TH, textAlign: 'center', verticalAlign: 'middle' }}>APP<br />{fyLabel}</th>
                  {qMonths.map((m) => (
                    <th key={m} colSpan={3} style={{ ...TH, textAlign: 'center', borderLeft: '2px solid #64748b' }}>{monthHeaderLabel(m)}</th>
                  ))}
                  <th colSpan={3} style={{ ...TH, textAlign: 'center', borderLeft: '2px solid #64748b', backgroundColor: '#0f2942' }}>Q{quarter} {fyLabel}</th>
                  <th rowSpan={2} style={{ ...TH, textAlign: 'center', verticalAlign: 'middle', borderLeft: '2px solid #64748b' }}>Q{quarter}<br />{prevFyLabel}<br />Actual</th>
                  <th rowSpan={2} style={{ ...TH, textAlign: 'center', verticalAlign: 'middle' }}>% Gr.<br />over prev yr</th>
                </tr>
                <tr>
                  {qMonths.map((m) => (
                    <React.Fragment key={m}>
                      <th style={{ ...TH, backgroundColor: '#3e6494', fontWeight: 500, fontSize: 11, borderLeft: '2px solid #64748b' }}>APP</th>
                      <th style={{ ...TH, backgroundColor: '#3e6494', fontWeight: 500, fontSize: 11 }}>Actual</th>
                      <th style={{ ...TH, backgroundColor: '#3e6494', fontWeight: 500, fontSize: 11 }}>%Ful</th>
                    </React.Fragment>
                  ))}
                  <th style={{ ...TH, backgroundColor: '#1d4b78', fontWeight: 500, fontSize: 11, borderLeft: '2px solid #64748b' }}>APP</th>
                  <th style={{ ...TH, backgroundColor: '#1d4b78', fontWeight: 500, fontSize: 11 }}>Actual</th>
                  <th style={{ ...TH, backgroundColor: '#1d4b78', fontWeight: 500, fontSize: 11 }}>%Ful</th>
                </tr>
              </thead>
              <tbody>
                {computedSections.map((sec) => (
                  <React.Fragment key={sec.title}>
                    <tr>
                      <td colSpan={7 + qMonths.length * 3} style={{
                        ...TD, textAlign: 'left', fontWeight: 700, color: '#1e3a5f',
                        background: '#eef2f7', fontSize: 12.5, letterSpacing: 0.4,
                      }}>{sec.title}</td>
                    </tr>
                    {sec.rows.map((r, rIdx) => (
                      <tr key={rIdx} style={{ background: rIdx % 2 === 0 ? '#fff' : '#f8fafc' }}>
                        <td style={{
                          ...TD, textAlign: 'left', paddingLeft: 10 + r.indent * 22,
                          fontWeight: r.bold ? 700 : 400, color: r.bold ? '#1e3a5f' : '#202124',
                        }}>{r.label}</td>
                        <td style={{ ...TD, color: '#c1c7cf' }}>—</td>
                        <td style={{ ...TD, fontWeight: r.bold ? 600 : 400 }}>{fmt(r.appAnnual)}</td>
                        {r.monthCells.map((c, i) => (
                          <React.Fragment key={i}>
                            <td style={{ ...TD, color: '#6b7280', borderLeft: '2px solid #94a3b8' }}>{fmt(c.plan)}</td>
                            <td style={{ ...TD, fontWeight: r.bold ? 600 : 400 }}>{fmt(c.actual)}</td>
                            <td style={{ ...TD, color: '#6b7280' }}>{fmtPct(c.pctFul)}</td>
                          </React.Fragment>
                        ))}
                        <td style={{ ...TD, color: '#6b7280', borderLeft: '2px solid #94a3b8', backgroundColor: '#f0f7ff' }}>{fmt(r.qPlan)}</td>
                        <td style={{ ...TD, fontWeight: r.bold ? 700 : 600, backgroundColor: '#f0f7ff' }}>{fmt(r.qActual)}</td>
                        <td style={{ ...TD, color: '#6b7280', backgroundColor: '#f0f7ff' }}>{fmtPct(r.qPctFul)}</td>
                        <td style={{ ...TD, borderLeft: '2px solid #94a3b8' }}>{fmt(r.prevQActual)}</td>
                        <td style={{ ...TD, color: r.pctGrowth < 0 ? '#b91c1c' : '#15803d', fontWeight: 600 }}>{fmtGrowth(r.pctGrowth)}</td>
                      </tr>
                    ))}
                    <tr style={{ background: '#fff7ed', borderTop: '2px solid #f59e0b' }}>
                      <td style={{ ...TD, textAlign: 'left', fontWeight: 700, color: '#9a3412' }}>Total</td>
                      <td style={{ ...TD, color: '#c1c7cf' }}>—</td>
                      <td style={{ ...TD, fontWeight: 700, color: '#9a3412' }}>{fmt(sec.total.appAnnual)}</td>
                      {sec.total.monthCells.map((c, i) => (
                        <React.Fragment key={i}>
                          <td style={{ ...TD, fontWeight: 600, color: '#9a3412', borderLeft: '2px solid #94a3b8' }}>{fmt(c.plan)}</td>
                          <td style={{ ...TD, fontWeight: 700, color: '#9a3412' }}>{fmt(c.actual)}</td>
                          <td style={{ ...TD, fontWeight: 600, color: '#9a3412' }}>{fmtPct(c.pctFul)}</td>
                        </React.Fragment>
                      ))}
                      <td style={{ ...TD, fontWeight: 600, color: '#9a3412', borderLeft: '2px solid #94a3b8', backgroundColor: '#ffedd5' }}>{fmt(sec.total.qPlan)}</td>
                      <td style={{ ...TD, fontWeight: 700, color: '#9a3412', backgroundColor: '#ffedd5' }}>{fmt(sec.total.qActual)}</td>
                      <td style={{ ...TD, fontWeight: 600, color: '#9a3412', backgroundColor: '#ffedd5' }}>{fmtPct(sec.total.qPctFul)}</td>
                      <td style={{ ...TD, fontWeight: 700, color: '#9a3412', borderLeft: '2px solid #94a3b8' }}>{fmt(sec.total.prevQActual)}</td>
                      <td style={{ ...TD, fontWeight: 700, color: sec.total.pctGrowth < 0 ? '#b91c1c' : '#15803d' }}>{fmtGrowth(sec.total.pctGrowth)}</td>
                    </tr>
                  </React.Fragment>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {/* ── Footer note ── */}
        <div style={{ marginTop: 14, fontSize: 12, color: '#9ca3af' }}>
          Values in '000 tonnes, rounded. APP = Annual Production Plan (production_plan_table); Actual = uploaded/entered
          production (production_table). %Ful = Actual ÷ APP for that period. Annual Capacity is left blank (not tracked
          in this application). RSP Total (Hot Metal) and BSL/RSP Saleable Steel "Total" rows are computed sums of their
          listed sub-items; section "Total" rows sum only the non-indented top-level items so sub-items are not double-counted.
          ISP has a single blast furnace, so "ISP BF-5" reflects the plant's total Hot Metal. ISP SMS uses ISP's Total Crude
          Steel (its only SMS shop). Source: Annexure-III.pdf column layout, mapped to this application's production tables.
        </div>
      </div>
    </div>
  );
}
