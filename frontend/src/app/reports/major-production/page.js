'use client';

import React, { useState, useEffect, useCallback } from 'react';
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
const PLANTS_SSP3  = ['ASP', 'SSP', 'VISL'];
const PLANTS_ALL8  = [...PLANTS_MAIN5, ...PLANTS_SSP3];

// Conversion agents produce only Finished Steel; their actuals are stored
// under plant 'SAIL', item 'Conversion' in production_table.
const CONVERSION    = 'Conversion';
const GROUP_5PLANTS = 'Group of 5 Plants (BSP, DSP, RSP, BSL, ISP)';
const GROUP_3SSP    = 'Group of 3 SSPs (ASP, SSP, VISL)';
const SAIL_TOTAL    = 'SAIL Total (8 Plants + Conversion)';

const PLANT_OPTIONS = [...PLANTS_ALL8, CONVERSION, GROUP_5PLANTS, GROUP_3SSP, SAIL_TOTAL];

const MONTH_LABEL = {
  '04': 'April', '05': 'May', '06': 'June', '07': 'July', '08': 'August',
  '09': 'September', '10': 'October', '11': 'November', '12': 'December',
  '01': 'January', '02': 'February', '03': 'March',
};

const TH = {
  padding: '8px 10px', border: '1px solid #cbd5e1', fontWeight: 700,
  fontSize: 13, backgroundColor: '#1e3a5f', color: '#fff', whiteSpace: 'nowrap',
};
const TD = {
  padding: '6px 10px', border: '1px solid #dadce0', fontSize: 13,
  textAlign: 'right', whiteSpace: 'nowrap', fontVariantNumeric: 'tabular-nums',
};

export default function MajorProductionPage() {
  const [fys, setFys]       = useState([]);
  const [fyStart, setFyStart] = useState(null);
  const [plant, setPlant]   = useState(SAIL_TOTAL);
  const [data, setData]     = useState(null);   // /api/production-fy response
  const [loading, setLoading] = useState(false);
  const [error, setError]   = useState(null);
  const [inTonnes, setInTonnes] = useState(false); // false = '000 T (3 dp), true = ×1000

  // ── FY list ────────────────────────────────────────────────────────────────
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

  // ── FY data ────────────────────────────────────────────────────────────────
  const loadData = useCallback(async () => {
    if (fyStart == null) return;
    setLoading(true); setError(null);
    try {
      const r = await fetch(`${API}/api/production-fy?fy_start=${fyStart}`);
      if (!r.ok) throw new Error(await r.text());
      setData(await r.json());
    } catch (e) {
      setError(`Load failed: ${e.message}`);
      setData(null);
    } finally {
      setLoading(false);
    }
  }, [fyStart]);

  useEffect(() => { loadData(); }, [loadData]);

  // ── Derived table ──────────────────────────────────────────────────────────
  const months = data?.months || [];

  const findItem = (plantName, key) =>
    (data?.plants || []).find(p => p.plant === plantName)?.items?.find(i => i.item_name === key);

  // series[itemKey][month] = value ('000 T), for 'actual' and 'plan'
  const buildMonthly = (kind) => {
    const out = {};
    const groupPlants =
      plant === GROUP_5PLANTS ? PLANTS_MAIN5 :
      plant === GROUP_3SSP    ? PLANTS_SSP3 :
      plant === SAIL_TOTAL    ? PLANTS_ALL8 :
      null;

    ITEMS.forEach(({ key }) => {
      out[key] = {};
      months.forEach(m => {
        let value = null;
        if (plant === CONVERSION) {
          // Conversion only produces Finished Steel.
          value = key === 'Finished Steel' ? (findItem('SAIL', 'Conversion')?.[kind]?.[m] ?? null) : null;
        } else if (groupPlants) {
          let sum = null;
          groupPlants.forEach(pn => {
            const v = findItem(pn, key)?.[kind]?.[m];
            if (v != null) sum = (sum ?? 0) + v;
          });
          if (plant === SAIL_TOTAL && key === 'Finished Steel') {
            const cv = findItem('SAIL', 'Conversion')?.[kind]?.[m];
            if (cv != null) sum = (sum ?? 0) + cv;
          }
          value = sum != null ? Math.round(sum * 1000) / 1000 : null;
        } else {
          value = findItem(plant, key)?.[kind]?.[m] ?? null;
        }
        out[key][m] = value;
      });
    });
    return out;
  };

  // Cumulative April → month; null for months with no data
  const buildCumulative = (mon) => {
    const out = {};
    ITEMS.forEach(({ key }) => {
      out[key] = {};
      let run = null;
      months.forEach(m => {
        const v = mon[key][m];
        if (v != null) run = (run ?? 0) + v;
        out[key][m] = v != null ? run : null;
      });
    });
    return out;
  };

  const monthly    = buildMonthly('actual');
  const monthlyPl  = buildMonthly('plan');
  const cumulative   = buildCumulative(monthly);
  const cumulativePl = buildCumulative(monthlyPl);

  const hasAnyData = ITEMS.some(({ key }) =>
    Object.values(monthly[key]).some(v => v != null) ||
    Object.values(monthlyPl[key]).some(v => v != null));

  // FY total per item — shared by the Total row and the Excel export.
  const totals = {};
  ITEMS.forEach(({ key }) => {
    const sumOf = (mon) => {
      let s = null;
      months.forEach(m => { const v = mon[key][m]; if (v != null) s = (s ?? 0) + v; });
      return s != null ? Math.round(s * 1000) / 1000 : null;
    };
    totals[key] = { plan: sumOf(monthlyPl), actual: sumOf(monthly) };
  });

  const fmt = (v) => {
    if (v == null) return '—';
    if (inTonnes) return Math.round(v * 1000).toLocaleString('en-IN');
    return v.toFixed(3);
  };

  const handlePrint = () => window.print();

  const handleDownloadExcel = () => {
    const csvVal = (v) => (v == null ? '' : inTonnes ? String(Math.round(v * 1000)) : v.toFixed(3));
    const escape = (s) => (/[",\r\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s);

    const header = ['Month'];
    ITEMS.forEach(({ label }) => {
      header.push(`${label} Month Plan`, `${label} Month Actual`, `${label} Till Month Plan`, `${label} Till Month Actual`);
    });

    const rows = months.map(m => {
      const row = [`${MONTH_LABEL[m.slice(5)]} ${m.slice(0, 4)}`];
      ITEMS.forEach(({ key }) => {
        row.push(csvVal(monthlyPl[key][m]), csvVal(monthly[key][m]), csvVal(cumulativePl[key][m]), csvVal(cumulative[key][m]));
      });
      return row;
    });

    const totalRow = ['Total'];
    ITEMS.forEach(({ key }) => {
      const { plan, actual } = totals[key];
      totalRow.push(csvVal(plan), csvVal(actual), csvVal(plan), csvVal(actual));
    });
    rows.push(totalRow);

    const csv = [header, ...rows].map(r => r.map(v => escape(String(v))).join(',')).join('\r\n');
    const blob = new Blob(['﻿' + csv], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `Major_Production_${plant.replace(/[^a-z0-9]+/gi, '_')}_${data?.fy_label || ''}.csv`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };

  return (
    <div style={{ minHeight: '100vh', background: '#ffffff', fontFamily: "-apple-system,BlinkMacSystemFont,'Segoe UI',Arial,sans-serif" }}>
      <style>{`
        @media print {
          @page { size: A4 landscape; margin: 10mm; }
          .mp-table-wrap { overflow: visible !important; border: none !important; }
        }
      `}</style>

      <div className="no-print"><GlobalNavbar /></div>

      <div style={{ maxWidth: 1500, margin: '0 auto', padding: '22px 20px' }}>

        {/* ── Title ── */}
        <div style={{ display: 'flex', alignItems: 'baseline', gap: 14, marginBottom: 18, flexWrap: 'wrap' }}>
          <h2 style={{ fontSize: '1.6rem', fontWeight: 700, color: '#202124', margin: 0 }}>
            Major Production — Month &amp; Till Month
          </h2>
          <span style={{ fontSize: 13, color: '#5f6368' }}>
            Sinter · Hot Metal · Crude Steel · Saleable Steel · Pig Iron · Finished Steel
          </span>
        </div>

        {/* ── Controls ── */}
        <div className="no-print" style={{
          display: 'flex', gap: 10, alignItems: 'center', flexWrap: 'wrap',
          marginBottom: 18, border: '1px solid #dadce0', borderRadius: 8, padding: '14px 18px',
        }}>
          <label style={{ fontSize: 13, fontWeight: 600, color: '#374151' }}>Plant</label>
          <select value={plant} onChange={e => setPlant(e.target.value)}
                  style={{ padding: '7px 10px', fontSize: 14, border: '1px solid #d1d5db', borderRadius: 4 }}>
            {PLANT_OPTIONS.map(p => <option key={p}>{p}</option>)}
          </select>

          <label style={{ fontSize: 13, fontWeight: 600, color: '#374151', marginLeft: 10 }}>Financial Year</label>
          <select value={fyStart ?? ''} onChange={e => setFyStart(Number(e.target.value))}
                  style={{ padding: '7px 10px', fontSize: 14, border: '1px solid #d1d5db', borderRadius: 4 }}>
            {fys.map(f => <option key={f.fy_start} value={f.fy_start}>{f.label}</option>)}
          </select>

          {/* Unit toggle */}
          <div style={{ marginLeft: 18, display: 'flex', border: '1px solid #d1d5db', borderRadius: 6, overflow: 'hidden' }}>
            {[
              { on: false, text: "'000 Tonnes (3 dp)" },
              { on: true,  text: 'Tonnes (×1000)' },
            ].map(({ on, text }) => (
              <button key={text} onClick={() => setInTonnes(on)} style={{
                padding: '7px 16px', fontSize: 13, fontWeight: 600, border: 'none', cursor: 'pointer',
                background: inTonnes === on ? '#1a73e8' : '#fff',
                color: inTonnes === on ? '#fff' : '#374151',
              }}>{text}</button>
            ))}
          </div>

          <button onClick={handlePrint} disabled={!data || !hasAnyData} style={{
            marginLeft: 18, padding: '7px 16px', fontSize: 13, fontWeight: 600, borderRadius: 6,
            border: '1px solid #d1d5db', cursor: data && hasAnyData ? 'pointer' : 'not-allowed',
            background: '#fff', color: '#374151', opacity: data && hasAnyData ? 1 : 0.5,
          }}>🖨 Print</button>

          <button onClick={handleDownloadExcel} disabled={!data || !hasAnyData} style={{
            padding: '7px 16px', fontSize: 13, fontWeight: 600, borderRadius: 6,
            border: '1px solid #188038', cursor: data && hasAnyData ? 'pointer' : 'not-allowed',
            background: '#e6f4ea', color: '#188038', opacity: data && hasAnyData ? 1 : 0.5,
          }}>⬇ Download Excel</button>

          <span style={{ marginLeft: 'auto', fontSize: 13, color: '#5f6368' }}>
            {data?.fy_label || ''}{loading && ' ⟳ loading…'}
          </span>
        </div>

        {/* ── Error ── */}
        {error && (
          <div style={{ padding: '10px 16px', borderRadius: 6, marginBottom: 14, fontSize: 14, background: '#fef2f2', color: '#991b1b', border: '1px solid #fca5a5' }}>
            {error}
          </div>
        )}

        {/* ── Table ── */}
        {!loading && data && !hasAnyData ? (
          <div style={{ color: '#9ca3af', fontSize: 14, padding: '50px 0', textAlign: 'center', border: '2px dashed #dadce0', borderRadius: 8 }}>
            No production data for {plant} in {data.fy_label}.
          </div>
        ) : data && (
          <div className="mp-table-wrap" style={{ overflowX: 'auto', border: '1px solid #dadce0', borderRadius: 8 }}>
            <table style={{ width: '100%', borderCollapse: 'collapse' }}>
              <thead>
                <tr>
                  <th rowSpan={3} style={{ ...TH, textAlign: 'left', verticalAlign: 'middle' }}>Month</th>
                  {ITEMS.map(({ label }, idx) => (
                    <th key={label} colSpan={4} style={{
                      ...TH, textAlign: 'center',
                      borderLeft: idx > 0 ? '2px solid #64748b' : TH.border,
                    }}>{label}</th>
                  ))}
                </tr>
                <tr>
                  {ITEMS.map(({ label }, idx) => (
                    <React.Fragment key={label}>
                      <th colSpan={2} style={{ ...TH, backgroundColor: '#2d5382', fontWeight: 600, fontSize: 12, textAlign: 'center', borderLeft: idx > 0 ? '2px solid #64748b' : TH.border }}>Month</th>
                      <th colSpan={2} style={{ ...TH, backgroundColor: '#2d5382', fontWeight: 600, fontSize: 12, textAlign: 'center' }}>Till Month</th>
                    </React.Fragment>
                  ))}
                </tr>
                <tr>
                  {ITEMS.map(({ label }, idx) => (
                    <React.Fragment key={label}>
                      <th style={{ ...TH, backgroundColor: '#3e6494', fontWeight: 500, fontSize: 11, textAlign: 'right', borderLeft: idx > 0 ? '2px solid #64748b' : TH.border }}>Plan</th>
                      <th style={{ ...TH, backgroundColor: '#3e6494', fontWeight: 500, fontSize: 11, textAlign: 'right' }}>Actual</th>
                      <th style={{ ...TH, backgroundColor: '#3e6494', fontWeight: 500, fontSize: 11, textAlign: 'right' }}>Plan</th>
                      <th style={{ ...TH, backgroundColor: '#3e6494', fontWeight: 500, fontSize: 11, textAlign: 'right' }}>Actual</th>
                    </React.Fragment>
                  ))}
                </tr>
              </thead>
              <tbody>
                {months.map((m, i) => {
                  const rowHasData = ITEMS.some(({ key }) => monthly[key][m] != null || monthlyPl[key][m] != null);
                  const cumBg = i % 2 === 0 ? '#f0f7ff' : '#e8f0fe';
                  return (
                    <tr key={m} style={{ background: i % 2 === 0 ? '#fff' : '#f8fafc', opacity: rowHasData ? 1 : 0.45 }}>
                      <td style={{ ...TD, textAlign: 'left', fontWeight: 600, color: '#202124' }}>
                        {MONTH_LABEL[m.slice(5)]} <span style={{ color: '#9ca3af', fontWeight: 400 }}>{m.slice(0, 4)}</span>
                      </td>
                      {ITEMS.map(({ key }, idx) => (
                        <React.Fragment key={key}>
                          <td style={{ ...TD, color: '#6b7280', borderLeft: idx > 0 ? '2px solid #94a3b8' : TD.border }}>{fmt(monthlyPl[key][m])}</td>
                          <td style={{ ...TD, fontWeight: 600 }}>{fmt(monthly[key][m])}</td>
                          <td style={{ ...TD, color: '#6b7280', backgroundColor: cumBg }}>{fmt(cumulativePl[key][m])}</td>
                          <td style={{ ...TD, fontWeight: 600, backgroundColor: cumBg }}>{fmt(cumulative[key][m])}</td>
                        </React.Fragment>
                      ))}
                    </tr>
                  );
                })}
                {/* ── Total row: FY sum of monthly values; Till Month shows the
                       same figure (= cumulative up to the last month with data) ── */}
                <tr style={{ background: '#fff7ed', borderTop: '2px solid #f59e0b' }}>
                  <td style={{ ...TD, textAlign: 'left', fontWeight: 700, color: '#9a3412' }}>Total</td>
                  {ITEMS.map(({ key }, idx) => {
                    const { plan: totPl, actual: totAc } = totals[key];
                    return (
                      <React.Fragment key={key}>
                        <td style={{ ...TD, fontWeight: 600, color: '#9a3412', borderLeft: idx > 0 ? '2px solid #94a3b8' : TD.border }}>{fmt(totPl)}</td>
                        <td style={{ ...TD, fontWeight: 700, color: '#9a3412' }}>{fmt(totAc)}</td>
                        <td style={{ ...TD, fontWeight: 600, color: '#9a3412', backgroundColor: '#ffedd5' }}>{fmt(totPl)}</td>
                        <td style={{ ...TD, fontWeight: 700, color: '#9a3412', backgroundColor: '#ffedd5' }}>{fmt(totAc)}</td>
                      </React.Fragment>
                    );
                  })}
                </tr>
              </tbody>
            </table>
          </div>
        )}

        {/* ── Footer note ── */}
        <div style={{ marginTop: 14, fontSize: 12, color: '#9ca3af' }}>
          Values stored in '000 tonnes. Plan = AAP plan (production_plan_table); Actual = uploaded/entered production.
          "Till Month" = cumulative from April up to that month (months without data are skipped).
          Tonnes view multiplies by 1000. Group/Total options are computed client-side: "Group of 5 Plants" sums BSP, DSP,
          RSP, BSL, ISP; "Group of 3 SSPs" sums ASP, SSP, VISL; "SAIL Total" sums all 8 plants plus Conversion. "Conversion"
          shows Conversion (SAIL) actuals under Finished Steel only, since Conversion agents only produce Finished Steel.
          Source: production_table (file uploads &amp; production entry).
        </div>
      </div>
    </div>
  );
}
