'use client';

import React, { useEffect, useMemo, useState } from 'react';
import { ReportPage } from '../ReportUI';

const API = process.env.NEXT_PUBLIC_API_URL || '';

// Shared shell of the three Parliament annexure tabs (backend
// parl_annexures.py / api_parl_annexures.py): FY + period (Apr..month)
// picker, number of past years, Excel / PDF downloads (this sheet, or all
// three), the report table (passed in as `Table`) and the data check —
// the units whose figure in the hard-coded history (the workbook) differs
// from the DB for the same period. Colours mirror colors_config.json's
// parl_* keys (the PDF's), which this preview does not read.

export const C = {
  item: '#CCFFFF', cap: '#E3FFAB', act: '#FFFF99', dev: '#F8CBAD', line: '1px solid #000', thick: '2px solid #000',
};
// A figure hard-coded in parl_annexures_history.json (not from the DB).
export const HARD = { color: '#1d4ed8', fontStyle: 'italic' };

export function HardKey() {
  return (
    <p style={{ fontSize: '8.5pt', color: '#5f6368', margin: '6px 0 0' }}>
      <span style={HARD}>Blue italics</span>: hard-coded from the workbook (parl_annexures_history.json) —
      every FY up to 2021-22, and later figures the DB does not hold. Everything else is from the DB.
    </p>
  );
}

const MON = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
const PERIOD_ENDS = [4, 5, 6, 7, 8, 9, 10, 11, 12, 1, 2, 3];

// Rounded half up like the backend's techno pages (page_techno._round_half_up:
// Decimal(str(v)), ROUND_HALF_UP) and the PDF of these annexures: 6.095 ->
// 6.10, as Excel shows it; toFixed alone gives 6.09 (binary 6.0949999...).
export function fmt(v, dp = 0) {
  if (v == null) return '';
  if (typeof v === 'string') return v;
  const n = Number(v);
  const r = Math.round(Number(`${Math.abs(n)}e${dp}`));
  const s = Number.isFinite(r) ? (Math.sign(n) * Number(`${r}e-${dp}`)).toFixed(dp) : n.toFixed(dp);
  return /^-0(\.0+)?$/.test(s) ? s.slice(1) : s;
}

// "Deviation" cells: key `${plant}|${item_key}|${col}` -> deviation rows.
export function devIndex(devs) {
  const m = new Map();
  (devs || []).forEach((d) => {
    const k = `${d.plant}|${d.item_key}|${d.col}`;
    m.set(k, [...(m.get(k) || []), d]);
  });
  return m;
}

export function devTitle(list) {
  return list.map((d) => `${d.measure}: workbook ${fmt(d.workbook, 3)}, DB ${fmt(d.db, 3)} (diff ${fmt(d.diff, 3)})`).join('\n');
}

function lastMonth() {
  const now = new Date();
  const m = now.getMonth();
  const y = m === 0 ? now.getFullYear() - 1 : now.getFullYear();
  return { y, m: m === 0 ? 12 : m };
}

function fyStartOf(y, m) { return m >= 4 ? y : y - 1; }
function fyLabel(s) { return `${s}-${String((s + 1) % 100).padStart(2, '0')}`; }
function monthOf(fyStart, end) {
  const y = end >= 4 ? fyStart : fyStart + 1;
  return `${y}-${String(end).padStart(2, '0')}`;
}

const sel = { padding: '6px 8px', fontSize: '10.5pt', border: '1px solid #dadce0', borderRadius: 6 };
const lbl = { fontSize: '10.5pt', fontWeight: 600, color: '#3c4043' };
const btn = (disabled, primary) => ({
  padding: '8px 16px', fontSize: '10.5pt', fontWeight: 700, borderRadius: 6,
  cursor: disabled ? 'not-allowed' : 'pointer',
  border: primary ? 'none' : '1px solid #1a73e8',
  background: disabled ? '#dadce0' : primary ? '#1a73e8' : '#fff',
  color: primary ? '#fff' : '#1a73e8',
});

function Deviations({ devs }) {
  if (!devs) return null;
  return (
    <div style={{ marginTop: 20 }}>
      <h3 style={{ fontSize: '11pt', margin: '0 0 4px', color: '#1e3a8a' }}>
        Data check: workbook / history figures that differ from the DB ({devs.length})
      </h3>
      <p style={{ fontSize: '9.5pt', color: '#5f6368', margin: '0 0 6px' }}>
        Each past FY shown from the hard-coded history (where the DB holds the full year), and the
        workbook&apos;s own current-period figures, compared with the DB for the same unit and period.
        Marked cells in the table above are shaded <span style={{ background: C.dev, padding: '0 4px' }}>like this</span>;
        hover for the figures.
      </p>
      {devs.length === 0 ? (
        <div style={{ fontSize: '10pt', color: '#137333' }}>No deviations: the DB agrees with the history for every period shown.</div>
      ) : (
        <div style={{ overflowX: 'auto', maxHeight: 420, overflowY: 'auto', border: '1px solid #dadce0' }}>
          <table style={{ borderCollapse: 'collapse', fontSize: '9.5pt', width: '100%' }}>
            <thead>
              <tr>
                {['Plant', 'Item', 'Period', 'Measure', 'Workbook', 'DB', 'DB − Workbook'].map((h) => (
                  <th key={h} style={{ position: 'sticky', top: 0, background: '#dbeafe', padding: '4px 8px', textAlign: 'left', borderBottom: '1px solid #94a3b8' }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {devs.map((d, i) => (
                <tr key={i} style={{ borderBottom: '1px solid #e2e8f0' }}>
                  <td style={{ padding: '3px 8px', fontWeight: 600 }}>{d.plant}</td>
                  <td style={{ padding: '3px 8px' }}>{d.item}</td>
                  <td style={{ padding: '3px 8px' }}>{d.period}</td>
                  <td style={{ padding: '3px 8px' }}>{d.measure}</td>
                  <td style={{ padding: '3px 8px', textAlign: 'right' }}>{fmt(d.workbook, 3)}</td>
                  <td style={{ padding: '3px 8px', textAlign: 'right' }}>{fmt(d.db, 3)}</td>
                  <td style={{ padding: '3px 8px', textAlign: 'right', color: d.diff < 0 ? '#b91c1c' : '#137333', fontWeight: 600 }}>{fmt(d.diff, 3)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

export default function ParlAnnexure({ slug, title, description, defaultYears, fileBase, Table }) {
  const init = lastMonth();
  const [fyStart, setFyStart] = useState(fyStartOf(init.y, init.m));
  const [end, setEnd] = useState(init.m);
  const [years, setYears] = useState(defaultYears);
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [downloading, setDownloading] = useState(null);

  const month = monthOf(fyStart, end);
  const query = `month=${month}&years=${years}`;

  useEffect(() => {
    let cancelled = false;
    fetch(`${API}/api/parl-annexures/${slug}?${query}`)
      .then((r) => (r.ok ? r.json() : r.json().then((b) => { throw new Error(b.detail || r.statusText); })))
      .then((d) => { if (!cancelled) { setData(d); setError(null); } })
      .catch((e) => { if (!cancelled) { setData(null); setError(e.message); } })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [slug, query]);

  const change = (fn) => (e) => { setLoading(true); fn(Number(e.target.value)); };

  const fyOptions = useMemo(() => {
    const out = [];
    for (let s = fyStartOf(init.y, init.m); s >= 2021; s -= 1) out.push(s);
    return out;
  }, [init.y, init.m]);

  const download = async (which, kind) => {
    setDownloading(`${which}-${kind}`);
    try {
      const q = which === 'all' ? `month=${month}` : query;
      const res = await fetch(`${API}/api/parl-annexures/${which}/${kind}?${q}`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const blob = await res.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `${which === 'all' ? 'Parliament_Annexures' : fileBase}_${month}.${kind}`;
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
  const devs = useMemo(() => devIndex(data?.deviations), [data]);

  return (
    <ReportPage maxWidth={1600} title={title} description={description}>
      <div style={{ display: 'flex', gap: 12, alignItems: 'center', flexWrap: 'wrap', marginBottom: 16 }}>
        <label htmlFor={`${slug}-fy`} style={lbl}>FY</label>
        <select id={`${slug}-fy`} value={fyStart} onChange={change(setFyStart)} style={sel}>
          {fyOptions.map((s) => <option key={s} value={s}>{fyLabel(s)}</option>)}
        </select>
        <label htmlFor={`${slug}-period`} style={lbl}>Period</label>
        <select id={`${slug}-period`} value={end} onChange={change(setEnd)} style={sel}>
          {PERIOD_ENDS.map((m) => <option key={m} value={m}>{m === 4 ? 'Apr' : `Apr-${MON[m - 1]}`}</option>)}
        </select>
        <label htmlFor={`${slug}-years`} style={lbl}>Past years</label>
        <select id={`${slug}-years`} value={years} onChange={change(setYears)} style={sel}>
          {[3, 4, 5, 6, 7, 8, 10, 12, 15].map((n) => <option key={n} value={n}>{n}</option>)}
        </select>
        <button type="button" onClick={() => download(slug, 'xlsx')} disabled={busy} style={btn(busy, true)}>
          {downloading === `${slug}-xlsx` ? 'Preparing…' : 'Excel'}
        </button>
        <button type="button" onClick={() => download(slug, 'pdf')} disabled={busy} style={btn(busy, false)}>
          {downloading === `${slug}-pdf` ? 'Preparing…' : 'PDF'}
        </button>
        <span style={{ width: 1, height: 26, background: '#dadce0' }} />
        <button type="button" onClick={() => download('all', 'xlsx')} disabled={busy} style={btn(busy, false)}
                title="All three annexures (each with its default number of past years) and the data check">
          {downloading === 'all-xlsx' ? 'Preparing…' : 'All 3 — Excel'}
        </button>
        <button type="button" onClick={() => download('all', 'pdf')} disabled={busy} style={btn(busy, false)}>
          {downloading === 'all-pdf' ? 'Preparing…' : 'All 3 — PDF'}
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
          <div style={{ overflowX: 'auto' }}><Table data={data} devs={devs} /></div>
          <HardKey />
          <Deviations devs={data.deviations} />
        </>
      )}
    </ReportPage>
  );
}
