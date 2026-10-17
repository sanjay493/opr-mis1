'use client';

import React, { useEffect, useState } from 'react';
import { ReportPage } from '../ReportUI';

const API = process.env.NEXT_PUBLIC_API_URL || '';

// Mines Production Performance (backend mines_performance.py): one block per
// mine, per group and for SAIL, pages 5-6 columns. Unrounded values from the
// API, shown to the chosen number of decimals; percentages whole numbers
// (Washery Yield's quantity columns use the row's own 1 decimal).

const DECIMALS_KEY = 'mp-decimals';

// Same type and rules as the Plant Wise Performance view and the PDF.
const FONT = "'IBM Plex Sans', sans-serif";
const NARROW = "'Arial Narrow', Arial, sans-serif";
const LINE = '1px solid #cbd5e1';
const RULE = '1px solid #000';
// pages 5-6 column tints (backend colors_config.json perf_* / mines_perf_total_bg)
const PLAN_BG = '#FFF2CC';
const ACT_BG = '#C6EFCE';
const GR_BG = '#e2e8f0';
const TOTAL_BG = '#FEF3C7';
const PLAN_IDX = new Set([0, 1, 6]);
const ACT_IDX = new Set([2, 7]);
const GR_IDX = new Set([5, 10]);
const LAST_COL = 10;

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

const TH = {
  padding: '3px 4px', borderRight: LINE, background: '#dbeafe',
  fontFamily: NARROW, fontSize: '8.2pt', fontWeight: 700, lineHeight: 1.05,
  textTransform: 'uppercase', textAlign: 'center', whiteSpace: 'pre-line', verticalAlign: 'middle',
};
const TD = {
  padding: '2px 5px', borderRight: LINE, fontFamily: FONT, fontSize: '8.5pt',
  lineHeight: 1.15, textAlign: 'right', whiteSpace: 'nowrap',
};
const LABEL = {
  heading: { fontFamily: NARROW, fontWeight: 700, textTransform: 'uppercase', color: '#1e3a8a', paddingLeft: 4 },
  subheading: { fontWeight: 700, fontStyle: 'italic', paddingLeft: 12 },
  item: { paddingLeft: 22 },
  total: { fontWeight: 700, paddingLeft: 12 },
};

const btn = (disabled, primary) => ({
  padding: '8px 18px', fontSize: '10.5pt', fontWeight: 700, borderRadius: 6,
  cursor: disabled ? 'not-allowed' : 'pointer',
  border: primary ? 'none' : '1px solid #1a73e8',
  background: disabled ? '#dadce0' : primary ? '#1a73e8' : '#fff',
  color: primary ? '#fff' : '#1a73e8',
});

function cellBg(vi) {
  if (PLAN_IDX.has(vi)) return PLAN_BG;
  if (ACT_IDX.has(vi)) return ACT_BG;
  if (GR_IDX.has(vi)) return GR_BG;
  return undefined;
}

function MinesTable({ data, decimals }) {
  const L = data.labels;
  const pct = new Set(data.pct_idx);
  return (
    <div style={{ overflowX: 'auto' }}>
      <table style={{ borderCollapse: 'separate', borderSpacing: 0, border: RULE, width: '100%', minWidth: 1100 }}>
        <thead>
          <tr>
            <th rowSpan={2} style={{ ...TH, width: 34, borderBottom: RULE }} />
            <th rowSpan={2} style={{ ...TH, textAlign: 'left', borderBottom: RULE }}>Item</th>
            <th rowSpan={2} style={{ ...TH, background: PLAN_BG, borderBottom: RULE }}>{`${L.fy}\nPlan`}</th>
            <th colSpan={3} style={{ ...TH, borderBottom: LINE }}>{L.month}</th>
            <th rowSpan={2} style={{ ...TH, borderBottom: RULE }}>{`${L.cply}\nAct.`}</th>
            <th rowSpan={2} style={{ ...TH, background: GR_BG, borderBottom: RULE }}>{`%Gr.\n${L.cply}`}</th>
            <th colSpan={3} style={{ ...TH, borderBottom: LINE }}>{L.ytd}</th>
            <th rowSpan={2} style={{ ...TH, borderBottom: RULE }}>{`${L.ytd_cply}\nAct.`}</th>
            <th rowSpan={2} style={{ ...TH, background: GR_BG, borderBottom: RULE, borderRight: 'none' }}>{`%Gr.\n${L.ytd_cply}`}</th>
          </tr>
          <tr>
            {['Plan', 'Actual', '%Ful', 'Plan', 'Actual', '%Ful'].map((h, i) => (
              <th key={i} style={{ ...TH, borderBottom: RULE, background: h === 'Plan' ? PLAN_BG : h === 'Actual' ? ACT_BG : TH.background }}>{h}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {data.blocks.map((b, bi) => b.rows.map((r, ri) => {
            // Black rule above every block, section heading and total row
            // (none on the very first row: the header's rule is there).
            const ruled = (bi > 0 || ri > 0) && (ri === 0 || r.kind === 'heading' || r.kind === 'total');
            const top = ruled ? { borderTop: RULE } : {};
            const qd = r.decimals ?? decimals;
            const isTotal = r.kind === 'total';
            return (
              <tr key={`${bi}-${ri}`}>
                {ri === 0 && (
                  <td rowSpan={b.rows.length} style={{ ...TD, ...top, borderRight: RULE, textAlign: 'center', verticalAlign: 'middle', background: '#fff', padding: '2px 0' }}>
                    <div style={{ writingMode: 'vertical-rl', transform: 'rotate(180deg)', margin: '0 auto', fontFamily: NARROW, fontWeight: 700, fontSize: '8.5pt' }}>
                      {b.name}
                    </div>
                  </td>
                )}
                <td style={{ ...TD, ...top, textAlign: 'left', whiteSpace: 'normal', ...LABEL[r.kind], ...(isTotal ? { background: TOTAL_BG } : {}) }}>
                  {r.label}
                </td>
                {r.values.map((v, vi) => (
                  <td key={vi} style={{
                    ...TD, ...top,
                    background: isTotal ? TOTAL_BG : cellBg(vi),
                    fontWeight: isTotal ? 700 : 400,
                    ...(vi === LAST_COL ? { borderRight: 'none' } : {}),
                  }}>
                    {pct.has(vi) ? fmtPct(v) : fmtQty(v, qd)}
                  </td>
                ))}
              </tr>
            );
          }))}
        </tbody>
      </table>
      {data.blocks.filter((b) => b.note).map((b) => (
        <p key={b.name} style={{ fontFamily: FONT, fontSize: '8.5pt', fontStyle: 'italic', color: '#475569', margin: '4px 0 0' }}>
          {b.name}: {b.note}
        </p>
      ))}
    </div>
  );
}

export default function MinesPerformanceView() {
  const [month, setMonth] = useState(previousMonth());
  const [decimals, setDecimals] = useState(0);
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [downloading, setDownloading] = useState(null); // null | 'xlsx' | 'pdf'

  // The saved choice is applied after mount (the server prerenders with 0).
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
    fetch(`${API}/api/mines-performance?month=${encodeURIComponent(month)}`)
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

  const download = async (kind) => {
    setDownloading(kind);
    try {
      const res = await fetch(`${API}/api/mines-performance/${kind}?month=${encodeURIComponent(month)}&decimals=${decimals}`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const blob = await res.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `Mines_Performance_${month}.${kind}`;
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
      title={<>Mines Production Performance</>}
      description={<>Each iron-ore mine, its group and SAIL: fresh production, despatch by end use, reported production and booked quantity, against plan and last year. Coal and flux at SAIL level. Tonnage in &apos;000 T.</>}
    >
      <div style={{ display: 'flex', gap: 12, alignItems: 'center', flexWrap: 'wrap', marginBottom: 16 }}>
        <label htmlFor="mp-month" style={{ fontSize: '10.5pt', fontWeight: 600, color: '#3c4043' }}>Report month</label>
        <input id="mp-month" type="month" value={month} onChange={(e) => changeMonth(e.target.value)}
               style={{ padding: '6px 8px', fontSize: '10.5pt', border: '1px solid #dadce0', borderRadius: 6 }} />
        <label htmlFor="mp-decimals" style={{ fontSize: '10.5pt', fontWeight: 600, color: '#3c4043' }}>Decimals</label>
        <select id="mp-decimals" value={decimals} onChange={(e) => changeDecimals(Number(e.target.value))}
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

      {!loading && data && data.blocks.length === 0 && (
        <div style={{ padding: 24, textAlign: 'center', color: '#5f6368' }}>No mines data for {data.labels.month}.</div>
      )}
      {!loading && data && data.blocks.length > 0 && (
        <>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-end', borderBottom: '1.5px solid #0f172a', paddingBottom: 3, marginBottom: 4, fontFamily: FONT }}>
            <h2 style={{ fontSize: '10pt', fontWeight: 700, color: '#1e3a8a', margin: 0 }}>{data.labels.title}</h2>
            <span style={{ fontSize: '8.5pt', fontWeight: 500 }}>Unit: &apos;000 T</span>
          </div>
          <MinesTable data={data} decimals={decimals} />
        </>
      )}
    </ReportPage>
  );
}
