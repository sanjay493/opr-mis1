'use client';

import React, { useState, useEffect, useCallback } from 'react';
import GlobalNavbar from '@/components/GlobalNavbar';

const API = process.env.NEXT_PUBLIC_API_URL || 'http://127.0.0.1:8082';

// Display label → item_name in production_table
const ITEMS = [
  { label: 'Sinter',         key: 'Total Sinter' },
  { label: 'Hot Metal',      key: 'Hot Metal' },
  { label: 'Crude Steel',    key: 'Total Crude Steel' },
  { label: 'Saleable Steel', key: 'Saleable Steel' },
  { label: 'Pig Iron',       key: 'Pig Iron' },
  { label: 'Finished Steel', key: 'Finished Steel' },
];

const PLANT_ORDER = ['SAIL', 'BSP', 'DSP', 'RSP', 'BSL', 'ISP', 'ASP', 'SSP', 'VISL'];

// Computed client-side by summing all plants. The uploaded 'SAIL' rows are
// rounded whole numbers and miss some items/months, so the sum is the
// full-precision default.
const SUM_PLANT = 'SAIL (Sum of Plants)';

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
  const [plant, setPlant]   = useState(SUM_PLANT);
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
  const availablePlants = [
    SUM_PLANT,
    ...(data?.plants || []).map(p => p.plant)
      .sort((a, b) => {
        const ia = PLANT_ORDER.indexOf(a), ib = PLANT_ORDER.indexOf(b);
        return (ia < 0 ? 99 : ia) - (ib < 0 ? 99 : ib);
      }),
  ];

  // monthly[itemKey][month] = value ('000 T)
  const monthly = {};
  if (plant === SUM_PLANT) {
    const realPlants = (data?.plants || []).filter(p => p.plant !== 'SAIL');
    ITEMS.forEach(({ key }) => {
      monthly[key] = {};
      months.forEach(m => {
        let sum = null;
        realPlants.forEach(p => {
          const v = p.items?.find(i => i.item_name === key)?.actual?.[m];
          if (v != null) sum = (sum ?? 0) + v;
        });
        monthly[key][m] = sum != null ? Math.round(sum * 1000) / 1000 : null;
      });
    });
  } else {
    const plantData = (data?.plants || []).find(p => p.plant === plant);
    ITEMS.forEach(({ key }) => {
      const it = plantData?.items?.find(i => i.item_name === key);
      monthly[key] = it?.actual || {};
    });
  }

  // Cumulative April → month; null until the first month with data
  const cumulative = {};
  ITEMS.forEach(({ key }) => {
    cumulative[key] = {};
    let run = null;
    months.forEach(m => {
      const v = monthly[key][m];
      if (v != null) run = (run ?? 0) + v;
      cumulative[key][m] = v != null ? run : null;
    });
  });

  const hasAnyData = ITEMS.some(({ key }) => Object.values(monthly[key]).some(v => v != null));

  const fmt = (v) => {
    if (v == null) return '—';
    if (inTonnes) return Math.round(v * 1000).toLocaleString('en-IN');
    return v.toFixed(3);
  };

  return (
    <div style={{ minHeight: '100vh', background: '#ffffff', fontFamily: "-apple-system,BlinkMacSystemFont,'Segoe UI',Arial,sans-serif" }}>
      <GlobalNavbar />

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
        <div style={{
          display: 'flex', gap: 10, alignItems: 'center', flexWrap: 'wrap',
          marginBottom: 18, border: '1px solid #dadce0', borderRadius: 8, padding: '14px 18px',
        }}>
          <label style={{ fontSize: 13, fontWeight: 600, color: '#374151' }}>Plant</label>
          <select value={plant} onChange={e => setPlant(e.target.value)}
                  style={{ padding: '7px 10px', fontSize: 14, border: '1px solid #d1d5db', borderRadius: 4 }}>
            {(availablePlants.length ? availablePlants : ['SAIL']).map(p => <option key={p}>{p}</option>)}
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
          <div style={{ overflowX: 'auto', border: '1px solid #dadce0', borderRadius: 8 }}>
            <table style={{ width: '100%', borderCollapse: 'collapse' }}>
              <thead>
                <tr>
                  <th rowSpan={2} style={{ ...TH, textAlign: 'left', verticalAlign: 'middle' }}>Month</th>
                  {ITEMS.map(({ label }) => (
                    <th key={label} colSpan={2} style={{ ...TH, textAlign: 'center' }}>{label}</th>
                  ))}
                </tr>
                <tr>
                  {ITEMS.map(({ label }) => (
                    <React.Fragment key={label}>
                      <th style={{ ...TH, backgroundColor: '#2d5382', fontWeight: 600, fontSize: 12, textAlign: 'right' }}>Month</th>
                      <th style={{ ...TH, backgroundColor: '#2d5382', fontWeight: 600, fontSize: 12, textAlign: 'right' }}>Till Month</th>
                    </React.Fragment>
                  ))}
                </tr>
              </thead>
              <tbody>
                {months.map((m, i) => {
                  const rowHasData = ITEMS.some(({ key }) => monthly[key][m] != null);
                  return (
                    <tr key={m} style={{ background: i % 2 === 0 ? '#fff' : '#f8fafc', opacity: rowHasData ? 1 : 0.45 }}>
                      <td style={{ ...TD, textAlign: 'left', fontWeight: 600, color: '#202124' }}>
                        {MONTH_LABEL[m.slice(5)]} <span style={{ color: '#9ca3af', fontWeight: 400 }}>{m.slice(0, 4)}</span>
                      </td>
                      {ITEMS.map(({ key }) => (
                        <React.Fragment key={key}>
                          <td style={TD}>{fmt(monthly[key][m])}</td>
                          <td style={{ ...TD, fontWeight: 600, backgroundColor: i % 2 === 0 ? '#f0f7ff' : '#e8f0fe' }}>
                            {fmt(cumulative[key][m])}
                          </td>
                        </React.Fragment>
                      ))}
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}

        {/* ── Footer note ── */}
        <div style={{ marginTop: 14, fontSize: 12, color: '#9ca3af' }}>
          Values stored in '000 tonnes. "Till Month" = cumulative from April up to that month (months without data are skipped).
          Tonnes view multiplies by 1000. "SAIL (Sum of Plants)" is computed by adding all plants; the "SAIL" option shows
          rounded figures as uploaded from the SAIL flash. Source: production_table (file uploads &amp; production entry).
        </div>
      </div>
    </div>
  );
}
