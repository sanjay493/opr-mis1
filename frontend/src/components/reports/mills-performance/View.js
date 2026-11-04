'use client';

import React, { useEffect, useState } from 'react';
import { ReportPage } from '../ReportUI';

const API = process.env.NEXT_PUBLIC_API_URL || '';

// SAIL Mill Production Performance for one FY (backend mills_performance.py):
// every major mill of the five plants with its capacity; Plan (APP) / Actual
// / %Ful over the months, Q1-Q4, H1, H2 (bold), the FY and Apr-to-latest-month.
// A cell with no DB data is blank. Excel and PDF downloads from the backend.

const BLUE = '#0000ff';
const RED = '#ff0000';
const PERIOD_BG = '#e2efda';   // colors_config.json trend_period_bg
const TOTAL_BG = '#f2f2f2';    // trend_fy_bg
const RULE = '1px solid #000';
const GRID = '1px solid #94a3b8';
const KINDS = [['plan', 'Plan'], ['act', 'Actual'], ['pct', '%Ful']];

// Same as mills_performance.fmt: a month's tonnage under 10 to one decimal.
const fmt = (v, colKind, kind) => {
  if (v == null) return '';
  const s = kind !== 'pct' && colKind === 'm' && Math.abs(v) < 10 ? v.toFixed(1) : String(Math.round(v));
  return Number(s) === 0 ? s.replace('-', '') : s;
};

// Same as mills_performance.cap_lines: '1300 (1000)' -> ['1300', '(1000)'].
const capLines = (cap) => (cap || '').replace('(', '\n(').split('\n').map((x) => x.trim()).filter(Boolean);

const colBg = (kind) => (kind === 'q' || kind === 'h' ? PERIOD_BG : kind === 'fy' || kind === 'cum' ? TOTAL_BG : undefined);

const btn = (disabled, primary) => ({
  padding: '8px 18px', fontSize: '10.5pt', fontWeight: 700, borderRadius: 6,
  cursor: disabled ? 'not-allowed' : 'pointer',
  border: primary ? 'none' : '1px solid #1a73e8',
  background: disabled ? '#dadce0' : primary ? '#1a73e8' : '#fff',
  color: primary ? '#fff' : '#1a73e8',
});

function Plant({ plant, cols }) {
  const n = plant.mills.length * 3;
  return plant.mills.flatMap((m, k) => KINDS.map(([kind, label], j) => {
    const top = j === 0 ? { borderTop: RULE } : {};
    return (
      <tr key={`${k}-${kind}`}>
        {k === 0 && j === 0 && (
          <td rowSpan={n} style={{ border: RULE, padding: '0 2px', width: 52, textAlign: 'center', fontWeight: 700, fontSize: '9pt' }}>
            {plant.plant}
            {plant.capacity && <div style={{ fontWeight: 400 }}>{plant.capacity}</div>}
            {plant.note && <div style={{ fontWeight: 400, fontSize: '8pt' }}>{plant.note}</div>}
          </td>
        )}
        {j === 0 && (
          <>
            <td rowSpan={3} style={{ border: RULE, padding: '0 2px', width: 52, textAlign: 'center', fontSize: '8.5pt' }}>{m.mill}</td>
            <td rowSpan={3} style={{ border: RULE, padding: '0 2px', width: 44, textAlign: 'center', fontSize: '8.5pt' }}>
              {capLines(m.capacity).map((x) => <div key={x}>{x}</div>)}
            </td>
          </>
        )}
        <td style={{ ...top, padding: '1px 4px', fontSize: '7.5pt', borderLeft: GRID, borderBottom: GRID }}>{label}</td>
        {cols.map((c, i) => {
          const v = m[kind][i];
          const color = kind === 'plan' ? BLUE : kind === 'pct' && v != null && Math.round(v) < 100 ? RED : undefined;
          return (
            <td key={i} style={{
              ...top, padding: '1px 3px', textAlign: 'center', fontSize: '8.5pt', whiteSpace: 'nowrap',
              borderLeft: GRID, borderBottom: GRID, background: colBg(c.kind), color,
              fontWeight: c.kind === 'm' ? 400 : 700,
            }}>
              {fmt(v, c.kind, kind)}
            </td>
          );
        })}
      </tr>
    );
  }));
}

export default function MillsPerformanceView() {
  const [fys, setFys] = useState([]);
  const [fy, setFy] = useState('');
  // The loaded report and the fy it is for; loading = it is for another.
  const [result, setResult] = useState({ key: '', rep: null, error: null });
  const [busy, setBusy] = useState('');
  const [error, setError] = useState(null);
  const loading = !!fy && result.key !== fy;
  const rep = result.rep;

  useEffect(() => {
    fetch(`${API}/api/mills-performance/fys`)
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error(`HTTP ${r.status}`))))
      .then((d) => {
        setFys(d.fys || []);
        if (d.fys && d.fys.length) setFy(String(d.fys[0]));
      })
      .catch((e) => setError(`Could not load financial years: ${e.message}`));
  }, []);

  useEffect(() => {
    if (!fy) return undefined;
    let live = true;
    fetch(`${API}/api/mills-performance?fy=${fy}`)
      .then(async (r) => {
        const body = await r.json().catch(() => ({}));
        if (!r.ok) throw new Error(body.detail || `HTTP ${r.status}`);
        return body;
      })
      .then((d) => { if (live) setResult({ key: fy, rep: d, error: null }); })
      .catch((e) => { if (live) setResult({ key: fy, rep: null, error: e.message }); });
    return () => { live = false; };
  }, [fy]);

  const download = async (ext) => {
    setBusy(ext);
    setError(null);
    try {
      const res = await fetch(`${API}/api/mills-performance/${ext}?fy=${fy}`);
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        throw new Error(body.detail || `HTTP ${res.status}`);
      }
      const cd = res.headers.get('content-disposition') || '';
      const name = (cd.match(/filename="([^"]+)"/) || [])[1] || `Mills_Performance_${fy}.${ext}`;
      const url = window.URL.createObjectURL(await res.blob());
      const a = document.createElement('a');
      a.href = url;
      a.download = name;
      document.body.appendChild(a);
      a.click();
      a.remove();
      window.URL.revokeObjectURL(url);
    } catch (e) {
      setError(`Download failed: ${e.message}`);
    } finally {
      setBusy('');
    }
  };

  const ready = !!fy && !loading && !!rep;
  const fyLabel = (y) => `${y}-${String((Number(y) + 1) % 100).padStart(2, '0')}`;

  return (
    <ReportPage
      title="Mills Performance"
      description="Mill-wise production of BSP, DSP, RSP, BSL and ISP against the APP monthly plan, with capacity, quarter, half-year, FY and Apr-to-date totals. Cells with no data in the database are left blank."
      actions={(
        <>
          <label htmlFor="mills-fy" style={{ fontWeight: 600, fontSize: '10.5pt' }}>FY</label>
          <select id="mills-fy" value={fy} onChange={(e) => setFy(e.target.value)}
                  style={{ padding: '7px 10px', fontSize: '10.5pt', border: '1px solid #dadce0', borderRadius: 6, background: '#fff' }}>
            {fys.map((y) => <option key={y} value={y}>{fyLabel(y)}</option>)}
          </select>
          <button type="button" onClick={() => download('xlsx')} disabled={!ready || !!busy} style={btn(!ready || !!busy, true)}>
            {busy === 'xlsx' ? 'Preparing…' : '⬇ Excel'}
          </button>
          <button type="button" onClick={() => download('pdf')} disabled={!ready || !!busy} style={btn(!ready || !!busy, false)}>
            {busy === 'pdf' ? 'Preparing…' : '⬇ PDF'}
          </button>
        </>
      )}
    >
      {(error || result.error) && (
        <div style={{ padding: '10px 14px', border: '1px solid #f28b82', borderRadius: 6, background: '#fce8e6', color: '#c5221f', marginBottom: 12 }}>
          {error || result.error}
        </div>
      )}
      {loading && !rep && <div style={{ padding: 16 }}>Loading…</div>}
      {rep && (
        <div style={{ background: '#fff', padding: 12, borderRadius: 8, border: '1px solid #e2e8f0', opacity: loading ? 0.5 : 1 }}>
          <div style={{ fontFamily: "'Times New Roman', serif", fontSize: '13pt', fontWeight: 700, textAlign: 'center' }}>{rep.title}</div>
          <div style={{ fontSize: '8pt', marginBottom: 4, textAlign: 'right' }}>Unit: &apos;000 T</div>
          {!rep.has_plan && (
            <div style={{ padding: '8px 12px', background: '#fffbeb', border: '1px solid #fde68a', borderRadius: 6, color: '#92400e', fontSize: 13, marginBottom: 6 }}>
              No APP data in the database for FY {rep.fy_label}.
            </div>
          )}
          <div style={{ overflowX: 'auto' }}>
            <table style={{ borderCollapse: 'collapse', border: RULE, width: '100%', minWidth: 1200, fontFamily: "'Times New Roman', serif" }}>
              <thead>
                <tr>
                  {['Plant', 'Mill', 'Capacity', ''].map((h, i) => (
                    <th key={i} style={{ border: RULE, padding: '2px 4px', fontSize: '8.5pt' }}>{h}</th>
                  ))}
                  {rep.columns.map((c) => (
                    <th key={c.label} style={{ border: RULE, padding: '2px 3px', fontSize: '8.5pt', whiteSpace: 'nowrap', background: colBg(c.kind) }}>{c.label}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {rep.plants.map((p) => <Plant key={p.plant} plant={p} cols={rep.columns} />)}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </ReportPage>
  );
}
