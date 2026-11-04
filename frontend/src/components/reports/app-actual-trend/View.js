'use client';

import React, { useEffect, useState } from 'react';
import { ReportPage, Toggle } from '../ReportUI';

const API = process.env.NEXT_PUBLIC_API_URL || '';

// APP (or MoU) vs Actual performance trend for one FY (backend
// app_actual_trend.py): Hot Metal, Crude Steel, Saleable Steel, Saleable
// production (Saleable Steel + Pig Iron) and Finished Steel (+ Conversion and
// SAIL incl. Conv.), plant-wise with SAIL-5 PL and SAIL;
// Plan / Act / % ful over the months, Q1-Q4, H1, H2 and the FY. A cell with
// no DB data is blank. Excel and PDF downloads from the backend.

const BASES = [{ id: 'app', label: 'APP' }, { id: 'mou', label: 'MoU' }];
const BLUE = '#0000ff';
const RED = '#ff0000';
const PERIOD_BG = '#e2efda';   // colors_config.json trend_period_bg
const FY_BG = '#f2f2f2';       // trend_fy_bg
const RULE = '1px solid #000';
const DOT = '1px dotted #94a3b8';

const fmt = (v) => {
  if (v == null) return '';
  const s = String(Math.round(v));
  return s === '-0' ? '0' : s;
};

const colBg = (kind) => (kind === 'q' || kind === 'h' ? PERIOD_BG : kind === 'fy' ? FY_BG : undefined);

const btn = (disabled, primary) => ({
  padding: '8px 18px', fontSize: '10.5pt', fontWeight: 700, borderRadius: 6,
  cursor: disabled ? 'not-allowed' : 'pointer',
  border: primary ? 'none' : '1px solid #1a73e8',
  background: disabled ? '#dadce0' : primary ? '#1a73e8' : '#fff',
  color: primary ? '#fff' : '#1a73e8',
});

function Section({ section, rep }) {
  const cols = rep.columns;
  const kinds = [['plan', rep.plan_label], ['act', 'Act'], ['pct', '% ful']];
  const n = section.rows.length * 3;
  return section.rows.flatMap((r, k) => kinds.map(([kind, label], j) => {
    const top = j === 0 ? { borderTop: RULE } : {};
    return (
      <tr key={`${k}-${kind}`}>
        {k === 0 && j === 0 && (
          <td rowSpan={n} style={{ border: RULE, padding: 0, verticalAlign: 'middle', width: 30 }}>
            <div style={{ writingMode: 'vertical-rl', transform: 'rotate(180deg)', fontSize: '17pt', fontWeight: 700, margin: '0 auto', whiteSpace: 'nowrap' }}>
              {section.item}
            </div>
          </td>
        )}
        {j === 0 && (
          <td rowSpan={3} style={{ ...top, padding: '1px 4px', color: BLUE, fontWeight: 700, fontSize: '8pt', verticalAlign: 'top', whiteSpace: 'nowrap', borderLeft: DOT }}>
            {r.plant}
          </td>
        )}
        <td style={{ ...top, padding: '1px 4px', fontSize: '7.5pt', fontWeight: kind === 'act' ? 400 : 700, color: kind === 'plan' ? BLUE : undefined, borderLeft: DOT, borderBottom: DOT }}>
          {label}
        </td>
        {cols.map((c, i) => {
          const v = r[kind][i];
          const color = kind === 'plan' ? BLUE : kind === 'pct' && v != null && Math.round(v) < 100 ? RED : undefined;
          return (
            <td key={i} style={{
              ...top, padding: '1px 3px', textAlign: 'center', fontSize: '9pt', whiteSpace: 'nowrap',
              borderLeft: DOT, borderBottom: DOT, background: colBg(c.kind), color,
              fontWeight: kind !== 'act' || c.kind !== 'm' ? 700 : 400, fontStyle: kind === 'act' ? 'italic' : undefined,
            }}>
              {fmt(v)}
            </td>
          );
        })}
      </tr>
    );
  }));
}

export default function AppActualTrendView() {
  const [fys, setFys] = useState([]);
  const [fy, setFy] = useState('');
  const [basis, setBasis] = useState('app');
  // The loaded report and the fy/basis it is for; loading = it is for another.
  const [result, setResult] = useState({ key: '', rep: null, error: null });
  const [busy, setBusy] = useState('');
  const [error, setError] = useState(null);
  const key = `${fy}|${basis}`;
  const loading = !!fy && result.key !== key;
  const rep = result.rep;

  useEffect(() => {
    fetch(`${API}/api/app-actual-trend/fys`)
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
    const k = `${fy}|${basis}`;
    fetch(`${API}/api/app-actual-trend?fy=${fy}&basis=${basis}`)
      .then(async (r) => {
        const body = await r.json().catch(() => ({}));
        if (!r.ok) throw new Error(body.detail || `HTTP ${r.status}`);
        return body;
      })
      .then((d) => { if (live) setResult({ key: k, rep: d, error: null }); })
      .catch((e) => { if (live) setResult({ key: k, rep: null, error: e.message }); });
    return () => { live = false; };
  }, [fy, basis]);

  const download = async (ext) => {
    setBusy(ext);
    setError(null);
    try {
      const res = await fetch(`${API}/api/app-actual-trend/${ext}?fy=${fy}&basis=${basis}`);
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        throw new Error(body.detail || `HTTP ${res.status}`);
      }
      const cd = res.headers.get('content-disposition') || '';
      const name = (cd.match(/filename="([^"]+)"/) || [])[1] || `Performance_Trend_${fy}.${ext}`;
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
      title="APP / MoU vs Actual Performance Trend"
      description="Plant-wise monthly plan against actual for Hot Metal, Crude Steel, Saleable Steel, Saleable production (Saleable Steel + Pig Iron) and Finished Steel (with Conversion and SAIL incl. Conversion), with quarter, half-year and FY totals. Plan is the APP or the MoU monthly target. Cells with no data in the database are left blank."
      actions={(
        <>
          <label htmlFor="trend-fy" style={{ fontWeight: 600, fontSize: '10.5pt' }}>FY</label>
          <select id="trend-fy" value={fy} onChange={(e) => setFy(e.target.value)}
                  style={{ padding: '7px 10px', fontSize: '10.5pt', border: '1px solid #dadce0', borderRadius: 6, background: '#fff' }}>
            {fys.map((y) => <option key={y} value={y}>{fyLabel(y)}</option>)}
          </select>
          <Toggle options={BASES} value={basis} onChange={setBasis} label="Plan basis" />
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
          <div style={{ fontFamily: "'Times New Roman', serif", fontSize: '13pt', fontWeight: 700 }}>{rep.title}</div>
          <div style={{ fontSize: '8pt', marginBottom: 4 }}>Unit: &apos;000 T</div>
          {!rep.has_plan && (
            <div style={{ padding: '8px 12px', background: '#fffbeb', border: '1px solid #fde68a', borderRadius: 6, color: '#92400e', fontSize: 13, marginBottom: 6 }}>
              No {rep.plan_label} data in the database for FY {rep.fy_label}.
            </div>
          )}
          <div style={{ overflowX: 'auto' }}>
            <table style={{ borderCollapse: 'collapse', border: RULE, width: '100%', minWidth: 1100, fontFamily: 'Arial, sans-serif' }}>
              <thead>
                <tr>
                  <th colSpan={3} style={{ border: RULE, textAlign: 'left', padding: '2px 4px', fontSize: '8.5pt' }}>Items</th>
                  {rep.columns.map((c) => (
                    <th key={c.label} style={{ border: RULE, padding: '2px 3px', fontSize: '8.5pt', whiteSpace: 'nowrap', background: colBg(c.kind) }}>{c.label}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {rep.sections.map((s) => <Section key={s.item} section={s} rep={rep} />)}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </ReportPage>
  );
}
