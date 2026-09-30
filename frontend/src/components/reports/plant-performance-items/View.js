'use client';

import React, { useEffect, useState } from 'react';
import GlobalNavbar from '@/components/GlobalNavbar';

const API = process.env.NEXT_PUBLIC_API_URL || '';

// Same rows/columns as the PDF report's "Plant Wise Performance of Main
// Items" page (backend page4.py), but unrounded: tonnages to 3 decimals,
// percentages as whole numbers. Excel download from the backend (openpyxl).

function previousMonth() {
  const now = new Date();
  const m = now.getMonth(); // 0-based == last month, 1-based
  const y = m === 0 ? now.getFullYear() - 1 : now.getFullYear();
  return `${y}-${String(m === 0 ? 12 : m).padStart(2, '0')}`;
}

function fmtQty(v) {
  if (v == null) return '';
  return Number(v).toLocaleString('en-IN', { minimumFractionDigits: 3, maximumFractionDigits: 3 });
}

function fmtPct(v) {
  return v == null ? '' : String(Math.round(v));
}

const TH = {
  padding: '5px 6px', border: '1px solid #94a3b8', background: '#dbeafe',
  fontSize: '9pt', fontWeight: 700, textAlign: 'center', whiteSpace: 'pre-line',
};
const TD = { padding: '3px 6px', border: '1px solid #cbd5e1', fontSize: '9pt', textAlign: 'right', whiteSpace: 'nowrap' };
const ACT_COLS = new Set([2, 9]);

const btn = (disabled, primary) => ({
  padding: '8px 18px', fontSize: '10.5pt', fontWeight: 700, borderRadius: 6,
  cursor: disabled ? 'not-allowed' : 'pointer',
  border: primary ? 'none' : '1px solid #1a73e8',
  background: disabled ? '#dadce0' : primary ? '#1a73e8' : '#fff',
  color: primary ? '#fff' : '#1a73e8',
});

export default function PlantPerformanceItemsView() {
  const [month, setMonth] = useState(previousMonth());
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [downloading, setDownloading] = useState(false);

  useEffect(() => {
    let cancelled = false;
    fetch(`${API}/api/plant-performance-main-items?month=${encodeURIComponent(month)}`)
      .then((r) => (r.ok ? r.json() : r.json().then((b) => { throw new Error(b.detail || r.statusText); })))
      .then((d) => { if (!cancelled) { setData(d); setError(null); } })
      .catch((e) => { if (!cancelled) { setData(null); setError(e.message); } })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [month]);

  const changeMonth = (m) => {
    if (!m || m === month) return;
    setLoading(true);
    setMonth(m);
  };

  const download = async () => {
    setDownloading(true);
    try {
      const res = await fetch(`${API}/api/plant-performance-main-items/xlsx?month=${encodeURIComponent(month)}`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const blob = await res.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `Plant_Performance_Main_Items_${month}.xlsx`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      window.URL.revokeObjectURL(url);
    } catch (e) {
      setError(`Download failed: ${e.message}`);
    } finally {
      setDownloading(false);
    }
  };

  const L = data?.labels;
  const pctIdx = new Set(data?.pct_idx || []);
  const rows = data?.rows || [];

  // rowspan for each item group (conversion rows stand alone)
  const spans = rows.map((r, i) => {
    if (r.is_conversion || r.is_sail_incl_conv) return 0;
    if (i > 0 && rows[i - 1].item === r.item && !rows[i - 1].is_conversion) return -1;
    let n = 1;
    while (i + n < rows.length && rows[i + n].item === r.item) n += 1;
    return n;
  });

  return (
    <>
      <GlobalNavbar />
      <main style={{ padding: '28px 32px', background: '#fff', minHeight: 'calc(100vh - 70px)' }}>
        <div style={{ maxWidth: 1500, margin: '0 auto' }}>
          <h1 style={{ fontSize: 24, fontWeight: 900, color: '#202124', margin: '0 0 6px' }}>
            Plant Wise Performance of Main Items
          </h1>
          <p style={{ fontSize: 12.5, color: '#5f6368', margin: '0 0 18px', maxWidth: 820, lineHeight: 1.6 }}>
            Same layout as the PDF report page, with actual tonnage to 3 decimal places (&apos;000 T; Oven Pushing in
            nos/day). Percentages are whole numbers. Download it as an Excel file for external submission.
          </p>

          <div style={{ display: 'flex', gap: 12, alignItems: 'center', flexWrap: 'wrap', marginBottom: 16 }}>
            <label htmlFor="pp-month" style={{ fontSize: '10.5pt', fontWeight: 600, color: '#3c4043' }}>Report month</label>
            <input id="pp-month" type="month" value={month} onChange={(e) => changeMonth(e.target.value)}
                   style={{ padding: '6px 8px', fontSize: '10.5pt', border: '1px solid #dadce0', borderRadius: 6 }} />
            <button type="button" onClick={download} disabled={downloading || !data} style={btn(downloading || !data, true)}>
              {downloading ? 'Preparing…' : 'Download Excel'}
            </button>
          </div>

          {loading && <div style={{ padding: 40, textAlign: 'center', color: '#5f6368' }}>Loading…</div>}
          {error && (
            <div style={{ padding: '12px 16px', background: '#fef2f2', border: '1px solid #fca5a5', borderRadius: 8, color: '#991b1b', fontSize: 13, marginBottom: 12 }}>
              {error}
            </div>
          )}

          {!loading && L && (
            <>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-end', borderBottom: '1.5px solid #0f172a', paddingBottom: 3, marginBottom: 4 }}>
                <h2 style={{ fontSize: '12pt', fontWeight: 800, color: '#1e3a8a', margin: 0 }}>{L.title}</h2>
                <h2 style={{ fontSize: '12pt', fontWeight: 800, margin: 0 }}>w.r.t APP</h2>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '9pt', fontStyle: 'italic', color: '#475569', marginBottom: 4 }}>
                <span>Tentative</span><span>Unit: &apos;000 T</span>
              </div>
              <div style={{ overflowX: 'auto' }}>
                <table style={{ borderCollapse: 'collapse', width: '100%', minWidth: 1250 }}>
                  <thead>
                    <tr>
                      <th rowSpan={2} style={{ ...TH, textAlign: 'left' }}>Items</th>
                      <th rowSpan={2} style={TH}>Plant</th>
                      <th rowSpan={2} style={TH}>{'Ann.\nCap.'}</th>
                      <th rowSpan={2} style={TH}>{`APP\n${L.fy}`}</th>
                      <th colSpan={4} style={TH}>{L.month}</th>
                      <th rowSpan={2} style={TH}>{`${L.cply}\nAct.`}</th>
                      <th rowSpan={2} style={TH}>{`%Gr.\n${L.cply}`}</th>
                      <th rowSpan={2} style={TH}>CU%</th>
                      <th colSpan={4} style={TH}>{L.ytd}</th>
                      <th rowSpan={2} style={TH}>{`${L.ytd_cply}\nAct.`}</th>
                      <th rowSpan={2} style={TH}>{`%Gr.\n${L.ytd_cply}`}</th>
                      <th rowSpan={2} style={TH}>CU%</th>
                    </tr>
                    <tr>
                      {['APP', 'Act.', 'Var', '%Ful.', 'APP', 'Act.', 'Var', '%Ful.'].map((h, i) => (
                        <th key={i} style={TH}>{h}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {rows.map((r, i) => {
                      const isSail = r.plant === 'SAIL' || r.plant === '5 Plants' || r.is_conversion || r.is_sail_incl_conv;
                      const rowStyle = isSail ? { background: '#fef3c7', fontWeight: 700 } : {};
                      return (
                        <tr key={i} style={rowStyle}>
                          {r.is_conversion && <td colSpan={3} style={{ ...TD, textAlign: 'left', fontWeight: 700 }}>Conversion</td>}
                          {r.is_sail_incl_conv && <td colSpan={2} style={{ ...TD, textAlign: 'left', fontWeight: 700 }}>SAIL incl. conversion</td>}
                          {spans[i] > 0 && (
                            <td rowSpan={spans[i]} style={{ ...TD, textAlign: 'left', fontWeight: 700, whiteSpace: 'normal', background: '#fff', verticalAlign: 'middle' }}>
                              {r.item}
                            </td>
                          )}
                          {!r.is_conversion && !r.is_sail_incl_conv && <td style={{ ...TD, textAlign: 'center', fontWeight: 600 }}>{r.plant}</td>}
                          {!r.is_conversion && <td style={TD}>{fmtQty(r.capacity)}</td>}
                          {r.values.map((v, vi) => (
                            <td key={vi} style={{ ...TD, ...(ACT_COLS.has(vi) && !isSail ? { background: '#ecfdf5', fontWeight: 700 } : {}) }}>
                              {pctIdx.has(vi) ? fmtPct(v) : fmtQty(v)}
                            </td>
                          ))}
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </>
          )}
        </div>
      </main>
    </>
  );
}
