'use client';

import React, { useEffect, useState } from 'react';
import Link from 'next/link';
import { ReportPage } from '../ReportUI';

const API = process.env.NEXT_PUBLIC_API_URL || '';

// Same rows/columns as the PDF report's "Plant Wise Performance of Main
// Items" page (backend page4.py), twice: against APP, and against MoU (only
// the items with a MoU target). Unrounded tonnage shown to the chosen number
// of decimals; percentages as whole numbers. Excel (two sheets) and PDF (two
// pages) downloads from the backend.

const DECIMALS_KEY = 'pp-decimals';

function previousMonth() {
  const now = new Date();
  const m = now.getMonth(); // 0-based == last month, 1-based
  const y = m === 0 ? now.getFullYear() - 1 : now.getFullYear();
  return `${y}-${String(m === 0 ? 12 : m).padStart(2, '0')}`;
}

function fmtQty(v, d) {
  if (v == null) return '';
  return Number(v).toLocaleString('en-IN', { minimumFractionDigits: d, maximumFractionDigits: d });
}

function fmtPct(v) {
  if (v == null) return '';
  const s = String(Math.round(v));
  return s === '-0' ? '0' : s;
}

// Type matches the PDF's page 4 (page4_table.html + main.html's .page4-*
// rules): IBM Plex Sans 8.5pt body, Arial Narrow Bold 8.2pt headers (6.8pt
// for the narrow CPLY / %Gr. / CU% headers), Arial Narrow Bold 8pt items.
const FONT = "'IBM Plex Sans', sans-serif";
const NARROW = "'Arial Narrow', Arial, sans-serif";
const LINE = '1px solid #cbd5e1';
const RULE = '1px solid #000';

// Separate (not collapsed) borders: the table's own border is the black
// outer frame, and each cell draws only its right edge (light column line)
// plus a black top rule where a new item group or total row starts — no
// light line between the plant rows of an item.
const TH = {
  padding: '3px 4px', borderRight: LINE, background: '#dbeafe',
  fontFamily: NARROW, fontSize: '8.2pt', fontWeight: 700, lineHeight: 1.05,
  textTransform: 'uppercase', textAlign: 'center', whiteSpace: 'pre-line', verticalAlign: 'middle',
};
const TH_SMALL = { ...TH, fontSize: '6.8pt', lineHeight: 0.95 };
const TD = {
  padding: '2px 5px', borderRight: LINE, fontFamily: FONT, fontSize: '8.5pt',
  lineHeight: 1.15, textAlign: 'right', whiteSpace: 'nowrap',
};
const ACT_COLS = new Set([2, 9]);
const LAST_COL = 14;

const btn = (disabled, primary) => ({
  padding: '8px 18px', fontSize: '10.5pt', fontWeight: 700, borderRadius: 6,
  cursor: disabled ? 'not-allowed' : 'pointer',
  border: primary ? 'none' : '1px solid #1a73e8',
  background: disabled ? '#dadce0' : primary ? '#1a73e8' : '#fff',
  color: primary ? '#fff' : '#1a73e8',
});

function PerfTable({ section, decimals }) {
  const L = section.labels;
  const B = L.basis;
  const pctIdx = new Set(section.pct_idx || []);
  const rows = section.rows || [];

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
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-end', borderBottom: '1.5px solid #0f172a', paddingBottom: 3, marginBottom: 4, fontFamily: FONT }}>
        <h2 style={{ fontSize: '10pt', fontWeight: 700, color: '#1e3a8a', margin: 0 }}>{L.title}</h2>
        <h2 style={{ fontSize: '10pt', fontWeight: 700, margin: 0 }}>w.r.t {B}</h2>
      </div>
      <div style={{ display: 'flex', justifyContent: 'space-between', fontFamily: FONT, fontSize: '8.5pt', fontWeight: 500, color: '#475569', marginBottom: 4 }}>
        <span>Tentative</span><span>Unit: &apos;000 T</span>
      </div>
      {!section.has_plan && (
        <div style={{ padding: '8px 12px', background: '#fffbeb', border: '1px solid #fde68a', borderRadius: 6, color: '#92400e', fontSize: 13, marginBottom: 6 }}>
          No {B} data uploaded for FY {L.fy}. Upload the MoU workbook on the{' '}
          <Link href="/data-entry/uploads" style={{ color: '#1a73e8', fontWeight: 700 }}>Uploads page</Link>.
        </div>
      )}
      <div style={{ overflowX: 'auto' }}>
        <table style={{ borderCollapse: 'separate', borderSpacing: 0, border: RULE, width: '100%', minWidth: 1250 }}>
          <thead>
            <tr>
              <th rowSpan={2} style={{ ...TH, textAlign: 'left', borderBottom: RULE }}>Items</th>
              <th rowSpan={2} style={{ ...TH, borderBottom: RULE }}>Plant</th>
              <th rowSpan={2} style={{ ...TH, borderBottom: RULE }}>{'Ann.\nCap.'}</th>
              <th rowSpan={2} style={{ ...TH, borderBottom: RULE }}>{`${B}\n${L.fy}`}</th>
              <th colSpan={4} style={{ ...TH, borderBottom: LINE }}>{L.month}</th>
              <th rowSpan={2} style={{ ...TH_SMALL, borderBottom: RULE }}>{`${L.cply}\nAct.`}</th>
              <th rowSpan={2} style={{ ...TH_SMALL, borderBottom: RULE }}>{`%Gr.\n${L.cply}`}</th>
              <th rowSpan={2} style={{ ...TH_SMALL, borderBottom: RULE }}>CU%</th>
              <th colSpan={4} style={{ ...TH, borderBottom: LINE }}>{L.ytd}</th>
              <th rowSpan={2} style={{ ...TH_SMALL, borderBottom: RULE }}>{`${L.ytd_cply}\nAct.`}</th>
              <th rowSpan={2} style={{ ...TH_SMALL, borderBottom: RULE }}>{`%Gr.\n${L.ytd_cply}`}</th>
              <th rowSpan={2} style={{ ...TH_SMALL, borderBottom: RULE, borderRight: 'none' }}>CU%</th>
            </tr>
            <tr>
              {[B, 'Act.', 'Var', '%Ful.', B, 'Act.', 'Var', '%Ful.'].map((h, i) => (
                <th key={i} style={{ ...TH, borderBottom: RULE }}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((r, i) => {
              const isSail = r.plant === 'SAIL' || r.plant === '5 Plants' || r.is_conversion || r.is_sail_incl_conv;
              const rowStyle = isSail ? { background: '#fef3c7', fontWeight: 700 } : {};
              // Black rule above each item group and each total row, as in
              // the PDF; none on the first row (the header's rule is there).
              const top = i > 0 && (spans[i] > 0 || isSail) ? { borderTop: RULE } : {};
              const cell = { ...TD, ...top };
              const label = { ...cell, textAlign: 'left', fontFamily: NARROW, fontSize: '8pt', fontWeight: 700 };
              return (
                <tr key={i} style={rowStyle}>
                  {r.is_conversion && <td colSpan={3} style={label}>Conversion</td>}
                  {r.is_sail_incl_conv && <td colSpan={2} style={label}>SAIL incl. conversion</td>}
                  {spans[i] > 0 && (
                    <td rowSpan={spans[i]} style={{ ...label, borderRight: RULE, whiteSpace: 'normal', background: '#fff', fontWeight: 700, verticalAlign: 'middle' }}>
                      {r.item}
                    </td>
                  )}
                  {!r.is_conversion && !r.is_sail_incl_conv && <td style={{ ...cell, textAlign: 'center', fontWeight: 600 }}>{r.plant}</td>}
                  {!r.is_conversion && <td style={{ ...cell, ...(isSail ? {} : { fontWeight: 500 }) }}>{fmtQty(r.capacity, decimals)}</td>}
                  {r.values.map((v, vi) => (
                    <td key={vi} style={{
                      ...cell,
                      ...(ACT_COLS.has(vi) && !isSail ? { background: '#ecfdf5' } : {}),
                      ...(vi === LAST_COL ? { borderRight: 'none' } : {}),
                    }}>
                      {pctIdx.has(vi) ? fmtPct(v) : fmtQty(v, decimals)}
                    </td>
                  ))}
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </>
  );
}

export default function PlantPerformanceItemsView() {
  const [month, setMonth] = useState(previousMonth());
  const [decimals, setDecimals] = useState(3);
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [downloading, setDownloading] = useState(null); // null | 'xlsx' | 'pdf'

  // The saved choice is applied after mount, not in useState's initialiser:
  // the server prerenders with 3, and an initialiser reading localStorage
  // would leave the select showing 3 while downloads used the saved value.
  // Storage can be unavailable (private window), leaving the default.
  useEffect(() => {
    try {
      const saved = window.localStorage.getItem(DECIMALS_KEY);
      // eslint-disable-next-line react-hooks/set-state-in-effect -- one-time sync from browser storage
      if (['0', '1', '2', '3'].includes(saved)) setDecimals(Number(saved));
    } catch { /* keep the default */ }
  }, []);

  const changeDecimals = (d) => {
    setDecimals(d);
    try { window.localStorage.setItem(DECIMALS_KEY, String(d)); } catch { /* not remembered */ }
  };

  useEffect(() => {
    let cancelled = false;
    const get = (basis) => fetch(`${API}/api/plant-performance-main-items?month=${encodeURIComponent(month)}&basis=${basis}`)
      .then((r) => (r.ok ? r.json() : r.json().then((b) => { throw new Error(b.detail || r.statusText); })));
    Promise.all([get('app'), get('mou')])
      .then(([app, mou]) => { if (!cancelled) { setData({ app, mou }); setError(null); } })
      .catch((e) => { if (!cancelled) { setData(null); setError(e.message); } })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [month]);

  const changeMonth = (m) => {
    if (!m || m === month) return;
    setLoading(true);
    setMonth(m);
  };

  const download = async (kind) => {
    setDownloading(kind);
    try {
      const res = await fetch(`${API}/api/plant-performance-main-items/${kind}?month=${encodeURIComponent(month)}&decimals=${decimals}`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const blob = await res.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `Plant_Performance_APP_MoU_${month}.${kind}`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      window.URL.revokeObjectURL(url);
    } catch (e) {
      setError(`Download failed: ${e.message}`);
    } finally {
      setDownloading(null);
    }
  };

  const busy = downloading !== null || !data;

  return (
    <ReportPage
      maxWidth={1500}
      title={<>Plant Wise Performance of Main Items (APP &amp; MoU)</>}
      description={<>Page 1 against APP, page 2 against MoU (only items with a MoU target). Tonnage in &apos;000 T with the chosen decimals; percentages are whole numbers. Download both pages as Excel (two sheets) or PDF.</>}
    >

        <div style={{ display: 'flex', gap: 12, alignItems: 'center', flexWrap: 'wrap', marginBottom: 16 }}>
            <label htmlFor="pp-month" style={{ fontSize: '10.5pt', fontWeight: 600, color: '#3c4043' }}>Report month</label>
            <input id="pp-month" type="month" value={month} onChange={(e) => changeMonth(e.target.value)}
                   style={{ padding: '6px 8px', fontSize: '10.5pt', border: '1px solid #dadce0', borderRadius: 6 }} />
            <label htmlFor="pp-decimals" style={{ fontSize: '10.5pt', fontWeight: 600, color: '#3c4043' }}>Decimals</label>
            <select id="pp-decimals" value={decimals} onChange={(e) => changeDecimals(Number(e.target.value))}
                    style={{ padding: '6px 8px', fontSize: '10.5pt', border: '1px solid #dadce0', borderRadius: 6 }}>
              {[0, 1, 2, 3].map((d) => <option key={d} value={d}>{d}</option>)}
            </select>
            <button type="button" onClick={() => download('xlsx')} disabled={busy} style={btn(busy, true)}>
              {downloading === 'xlsx' ? 'Preparing…' : 'Download Excel'}
            </button>
            <button type="button" onClick={() => download('pdf')} disabled={busy} style={btn(busy, false)}>
              {downloading === 'pdf' ? 'Preparing…' : 'Download PDF'}
            </button>
          </div>

          {loading && <div style={{ padding: 40, textAlign: 'center', color: '#5f6368' }}>Loading…</div>}
          {error && (
            <div style={{ padding: '12px 16px', background: '#fef2f2', border: '1px solid #fca5a5', borderRadius: 8, color: '#991b1b', fontSize: 13, marginBottom: 12 }}>
              {error}
            </div>
          )}

          {!loading && data && (
            <>
              <PerfTable section={data.app} decimals={decimals} />
              <div style={{ height: 24 }} />
              <PerfTable section={data.mou} decimals={decimals} />
            </>
          )}
    </ReportPage>
  );
}
