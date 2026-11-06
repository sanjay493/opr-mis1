'use client';

import React, { useEffect, useState } from 'react';
import { ReportPage } from '../ReportUI';

const API = process.env.NEXT_PUBLIC_API_URL || '';

// SAIL production projection for one FY (backend abp_projection.py): Hot Metal,
// Crude Steel, Saleable Steel and Finished Steel, plant-wise with capacities,
// the three past FYs (highest in green), APP, MoU, best month, actual to date,
// and the full-year Projection (actual + running month OP + remaining APP) and
// Pro-rated estimates. A cell with no DB data is blank. The decimals choice
// only formats the figures here; the downloads ask the backend for it.

const PLAN_BG = '#dce6f1';     // colors_config.json abp_plan_bg
const PROJ_BG = '#f2dcdb';     // abp_projection_bg
const BEST_BG = '#92d050';     // abp_best_fy_bg
const RULE = '1px solid #000';
const AFTER_PAST = ['app', 'mou', 'best', 'avg3', 'ytd', 'projection', 'proj_app', 'proj_mou', 'prorated', 'pro_app', 'pro_mou'];
const PINK_FROM = AFTER_PAST.indexOf('projection');

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
const th = (extra) => ({ border: RULE, padding: '2px 5px', fontSize: '8.5pt', fontWeight: 700, textAlign: 'center', ...extra });
const td = (extra) => ({ border: RULE, padding: '2px 5px', fontSize: '9pt', textAlign: 'center', whiteSpace: 'nowrap', ...extra });

function Head({ rep }) {
  const nowrap = { whiteSpace: 'nowrap' };
  return (
    <thead>
      <tr>
        <th rowSpan={3} style={th()}>Items</th>
        <th rowSpan={3} style={th()}>Plant</th>
        <th rowSpan={3} style={th()}>Installed<br />Capacity</th>
        <th rowSpan={3} style={th()}>Operating<br />Capacity<br />{rep.short_fy}</th>
        {rep.past_labels.map((l) => <th key={l} style={th(nowrap)}>{l}</th>)}
        <th colSpan={4} style={th({ background: PLAN_BG })}>{rep.short_fy}</th>
        <th rowSpan={3} style={th(nowrap)}>{rep.ytd_label}</th>
        <th colSpan={6} style={th({ background: PROJ_BG })}>{rep.short_fy}</th>
      </tr>
      <tr>
        {rep.past_labels.map((l) => <th key={l} rowSpan={2} style={th()}>Act</th>)}
        <th rowSpan={2} style={th({ background: PLAN_BG })}>APP</th>
        <th rowSpan={2} style={th()}>MoU</th>
        <th rowSpan={2} style={th()}>Best<br />Month</th>
        <th rowSpan={2} style={th()}>Avg of<br />3 best<br />months</th>
        <th colSpan={3} style={th({ background: PROJ_BG })}>{rep.projection_label}</th>
        <th colSpan={3} style={th({ background: PROJ_BG })}>Pro-rated</th>
      </tr>
      <tr>
        {[0, 1].flatMap((k) => ['Projection', '%APP', '%MoU'].map((l) => (
          <th key={`${k}-${l}`} style={th({ background: PROJ_BG })}>{l}</th>
        )))}
      </tr>
    </thead>
  );
}

function Section({ section, decimals }) {
  return section.rows.map((r, k) => {
    const weight = r.total ? { fontWeight: 700 } : {};
    const top = k === 0 ? { borderTop: '2px solid #000' } : {};
    return (
      <tr key={r.plant}>
        {k === 0 && (
          <td rowSpan={section.rows.length} style={{ border: RULE, borderTop: '2px solid #000', padding: 0, width: 30 }}>
            <div style={{ writingMode: 'vertical-rl', transform: 'rotate(180deg)', fontSize: '11pt', fontWeight: 700, margin: '0 auto', whiteSpace: 'nowrap' }}>
              {section.item}
            </div>
          </td>
        )}
        <td style={td({ ...weight, ...top, textAlign: 'left' })}>{r.plant}</td>
        <td style={td({ ...weight, ...top })}>{fmt(r.installed, decimals)}</td>
        <td style={td({ ...weight, ...top })}>{fmt(r.operating, decimals)}</td>
        {r.past.map((v, i) => (
          <td key={i} style={td({ ...weight, ...top, background: r.past_max[i] ? BEST_BG : undefined })}>{fmt(v, decimals)}</td>
        ))}
        {AFTER_PAST.map((c, i) => (
          <td key={c} style={td({ ...weight, ...top, background: c === 'app' ? PLAN_BG : i >= PINK_FROM ? PROJ_BG : undefined })}>
            {fmt(r[c], decimals)}
          </td>
        ))}
      </tr>
    );
  });
}

export default function ProductionProjectionView() {
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
    fetch(`${API}/api/abp-projection/fys`)
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
    fetch(`${API}/api/abp-projection?fy=${fy}`)
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
      const res = await fetch(`${API}/api/abp-projection/${ext}?fy=${fy}&decimals=${decimals}`);
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        throw new Error(body.detail || `HTTP ${res.status}`);
      }
      const cd = res.headers.get('content-disposition') || '';
      const name = (cd.match(/filename="([^"]+)"/) || [])[1] || `ABP_Production_Projection_${fy}.${ext}`;
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
      title="Production Projection"
      description="Hot Metal, Crude Steel, Saleable Steel and Finished Steel for the selected FY: capacities, the last three years (highest in green), APP, MoU, best months and the full-year estimate. In the middle of an FY the Projection is the actual to date, plus the running month's OP, plus APP for the remaining months."
      actions={(
        <>
          <label htmlFor="abp-fy" style={label}>FY</label>
          <select id="abp-fy" value={fy} onChange={(e) => setFy(e.target.value)} style={selectStyle}>
            {fys.map((y) => <option key={y} value={y}>{fyLabel(y)}</option>)}
          </select>
          <label htmlFor="abp-decimals" style={label}>Decimals</label>
          <select id="abp-decimals" value={decimals} onChange={(e) => setDecimals(Number(e.target.value))} style={selectStyle}>
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
              No APP / MoU data in the database for FY {rep.fy_label}.
            </div>
          )}
          <div style={{ overflowX: 'auto' }}>
            <table style={{ borderCollapse: 'collapse', border: RULE, width: '100%', minWidth: 1100, fontFamily: 'Arial, sans-serif' }}>
              <Head rep={rep} />
              <tbody>
                {rep.sections.map((s) => <Section key={s.item} section={s} decimals={decimals} />)}
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
