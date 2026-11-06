'use client';

import React, { useEffect, useState } from 'react';
import { ReportPage } from '../ReportUI';

const API = process.env.NEXT_PUBLIC_API_URL || '';

// Saleable Steel & Mills performance for one FY (backend abp_mills.py): each
// plant's mills, then Finished Steel, Semis, Saleable Steel and % Finished
// Steel, and the same for the five plants. A past FY shows only with all 12
// months in the DB. The decimals choice only formats the figures here; the
// downloads ask the backend for it.

const FINISHED_BG = '#c5d9f1';   // colors_config.json abp_mill_finished_bg
const SALEABLE_BG = '#ffff00';   // abp_mill_saleable_bg
const ROW_BG = { finished: FINISHED_BG, pct: FINISHED_BG, saleable: SALEABLE_BG };
const RULE = '1px solid #000';

const fmt = (v, d) => {
  if (v == null) return '';
  const s = Number(v).toFixed(d);
  return /^-0(\.0*)?$/.test(s) ? s.slice(1) : s;
};

const btn = (disabled, primary) => ({
  padding: '8px 18px', fontSize: '10.5pt', fontWeight: 700, borderRadius: 6,
  cursor: disabled ? 'not-allowed' : 'pointer',
  border: primary ? 'none' : '1px solid #1a73e8',
  background: disabled ? '#dadce0' : primary ? '#1a73e8' : '#fff',
  color: primary ? '#fff' : '#1a73e8',
});

const selectStyle = { padding: '7px 10px', fontSize: '10.5pt', border: '1px solid #dadce0', borderRadius: 6, background: '#fff' };
const th = { border: RULE, padding: '2px 5px', fontSize: '8.5pt', fontWeight: 700, textAlign: 'center' };
const td = (extra) => ({ border: RULE, padding: '2px 5px', fontSize: '9pt', fontWeight: 700, textAlign: 'center', whiteSpace: 'nowrap', ...extra });

function Plant({ plant, decimals }) {
  return plant.rows.map((r, k) => {
    const top = k === 0 ? { borderTop: '2px solid #000' } : {};
    const bg = { background: ROW_BG[r.kind] };
    return (
      <tr key={r.label}>
        {k === 0 && (
          <td rowSpan={plant.rows.length} style={td({ ...top, fontSize: '10pt', whiteSpace: 'normal', width: 52 })}>{plant.plant}</td>
        )}
        <td style={td({ ...top, ...bg, textAlign: 'left' })}>{r.label}</td>
        <td style={td({ ...top, ...bg })}>{fmt(r.capacity, decimals)}</td>
        {r.past.map((v, i) => <td key={i} style={td({ ...top, ...bg })}>{fmt(v, decimals)}</td>)}
        <td style={td({ ...top, ...bg })}>{fmt(r.best_act, decimals)}</td>
        <td style={td({ ...top, ...bg })}>{r.best_period}</td>
        <td style={td({ ...top, ...bg })}>{fmt(r.abp, decimals)}</td>
        <td style={td({ ...top, ...bg })}>{fmt(r.likely, decimals)}</td>
        <td style={td({ ...top, ...bg })}>{fmt(r.best_month, decimals)}</td>
      </tr>
    );
  });
}

export default function AbpMillsView() {
  const [fys, setFys] = useState([]);
  const [fy, setFy] = useState('');
  const [decimals, setDecimals] = useState(0);
  // The loaded report and the fy it is for; loading = it is for another.
  const [result, setResult] = useState({ fy: '', rep: null, error: null });
  const [busy, setBusy] = useState('');
  const [error, setError] = useState(null);
  const loading = !!fy && result.fy !== fy;
  const rep = result.rep;

  useEffect(() => {
    fetch(`${API}/api/abp-mills/fys`)
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
    fetch(`${API}/api/abp-mills?fy=${fy}`)
      .then(async (r) => {
        const body = await r.json().catch(() => ({}));
        if (!r.ok) throw new Error(body.detail || `HTTP ${r.status}`);
        return body;
      })
      .then((d) => { if (live) setResult({ fy, rep: d, error: null }); })
      .catch((e) => { if (live) setResult({ fy, rep: null, error: e.message }); });
    return () => { live = false; };
  }, [fy]);

  const download = async (ext) => {
    setBusy(ext);
    setError(null);
    try {
      const res = await fetch(`${API}/api/abp-mills/${ext}?fy=${fy}&decimals=${decimals}`);
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        throw new Error(body.detail || `HTTP ${res.status}`);
      }
      const cd = res.headers.get('content-disposition') || '';
      const name = (cd.match(/filename="([^"]+)"/) || [])[1] || `Saleable_Steel_Mills_Performance_${fy}.${ext}`;
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
  const label = { fontWeight: 600, fontSize: '10.5pt' };

  return (
    <ReportPage
      title="Saleable Steel & Mills Performance"
      description="Mill-wise production with each plant's Finished Steel, Semis, Saleable Steel and % Finished Steel for the selected FY. Likely is the actual to date, plus the running month's OP, plus APP for the remaining months. A past year shows only when the database has all 12 months for it."
      actions={(
        <>
          <label htmlFor="abp-mills-fy" style={label}>FY</label>
          <select id="abp-mills-fy" value={fy} onChange={(e) => setFy(e.target.value)} style={selectStyle}>
            {fys.map((y) => <option key={y} value={y}>{fyLabel(y)}</option>)}
          </select>
          <label htmlFor="abp-mills-decimals" style={label}>Decimals</label>
          <select id="abp-mills-decimals" value={decimals} onChange={(e) => setDecimals(Number(e.target.value))} style={selectStyle}>
            {[0, 1, 2, 3].map((d) => <option key={d} value={d}>{d}</option>)}
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
          <div style={{ fontFamily: "'Times New Roman', serif", fontSize: '13pt', fontWeight: 700 }}>{rep.title}</div>
          <div style={{ fontSize: '8pt', marginBottom: 4 }}>Unit: &apos;000 T</div>
          {!rep.has_plan && (
            <div style={{ padding: '8px 12px', background: '#fffbeb', border: '1px solid #fde68a', borderRadius: 6, color: '#92400e', fontSize: 13, marginBottom: 6 }}>
              No APP data in the database for FY {rep.fy_label}.
            </div>
          )}
          <div style={{ overflowX: 'auto' }}>
            <table style={{ borderCollapse: 'collapse', border: RULE, width: '100%', minWidth: 900, fontFamily: 'Arial, sans-serif' }}>
              <thead>
                <tr>
                  <th rowSpan={2} style={th}>Plants</th>
                  <th rowSpan={2} style={th}>Mills</th>
                  <th rowSpan={2} style={th}>Installed<br />Capacity</th>
                  {rep.past_labels.map((l) => <th key={l} style={th}>{l}</th>)}
                  <th colSpan={2} style={th}>Best Achieved</th>
                  <th colSpan={3} style={th}>{rep.short_fy}</th>
                </tr>
                <tr>
                  {rep.past_labels.map((l) => <th key={l} style={th}>Act</th>)}
                  <th style={th}>Act</th>
                  <th style={th}>Period</th>
                  <th style={th}>ABP</th>
                  <th style={{ ...th, maxWidth: 170 }}>Likely<br />{rep.likely_label}</th>
                  <th style={th}>Best<br />Month</th>
                </tr>
              </thead>
              <tbody>
                {rep.plants.map((p) => <Plant key={p.plant} plant={p} decimals={decimals} />)}
              </tbody>
            </table>
          </div>
          {rep.op_missing.length > 0 && (
            <div style={{ fontSize: '8.5pt', marginTop: 6 }}>
              No OP for the running month, APP used: {rep.op_missing.join('; ')}.
            </div>
          )}
        </div>
      )}
    </ReportPage>
  );
}
