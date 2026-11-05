'use client';

import React, { useEffect, useState } from 'react';
import { ReportPage } from '../ReportUI';

const API = process.env.NEXT_PUBLIC_API_URL || '';

// BF Parameters for one FY (backend bf_report.py), after the "BF Report.xlsx"
// format: each furnace, its plant's shop row and SAIL, across the parameter
// sections (past FYs, APP, the 12 months, Cum). Static furnace data is in
// bf_report_config.json; a cell with no DB data is blank. Rows, past FYs and
// months can be hidden; APP and Cum always stay, and hiding never changes a
// figure. Excel from the backend, narrowed to what the page shows.

const APP_BG = '#e5e5ff';     // bf_report.py _APP_BG
const CUM_BG = '#ccecff';     // _CUM_BG
const TOTAL_BG = '#dce6f1';   // _TOTAL_BG
const RULE = '1px solid #000';
const GRID = '1px solid #94a3b8';
const STATIC_COLS = [
  ['working_volume', 'W/V (M3)'], ['tuyeres', 'No. of tuyeres'], ['tap_holes', 'No. of tap holes'],
  ['cast_houses', 'No. of cast houses'], ['chsgp', 'CHSGP (Y/N)'], ['blt', 'BLT (Y/N)'], ['stoves', 'No. of stoves'],
];
const PLANT_W = 54;
const BF_W = 52;

const cellBase = { border: GRID, padding: '2px 5px', fontSize: '8.5pt', textAlign: 'center', whiteSpace: 'nowrap' };
const stickyPlant = { position: 'sticky', left: 0, zIndex: 2, minWidth: PLANT_W, maxWidth: PLANT_W };
const stickyBf = { position: 'sticky', left: PLANT_W, zIndex: 2, minWidth: BF_W, maxWidth: BF_W };

function fmt(v, decimals) {
  return v === null || v === undefined ? '' : Number(v).toFixed(decimals);
}

function colBg(kind) {
  return kind === 'app' ? APP_BG : kind === 'cum' ? CUM_BG : undefined;
}

const linkBtn = {
  fontSize: '8.5pt', padding: '2px 8px', marginRight: 6, marginTop: 4, borderRadius: 10,
  border: '1px solid #dadce0', background: '#f8f9fa', cursor: 'pointer',
};

// One line of tick boxes. items: [[value, label]]; a value in `hidden` is unticked.
function Choices({ title, items, hidden, setHidden }) {
  const set = (values, hide) => setHidden((prev) => {
    const next = new Set(prev);
    values.forEach((v) => (hide ? next.add(v) : next.delete(v)));
    return next;
  });
  const values = items.map(([v]) => v);
  return (
    <div style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: '2px 10px', margin: '4px 0', fontSize: '9pt' }}>
      <strong style={{ minWidth: 70 }}>{title}</strong>
      {items.map(([v, label]) => (
        <label key={v} style={{ whiteSpace: 'nowrap', cursor: 'pointer' }}>
          <input type="checkbox" checked={!hidden.has(v)} onChange={(e) => set([v], !e.target.checked)} /> {label}
        </label>
      ))}
      {items.length > 1 && (
        <span>
          <button type="button" style={{ ...linkBtn, marginTop: 0 }} onClick={() => set(values, false)}>All</button>
          <button type="button" style={{ ...linkBtn, marginTop: 0 }} onClick={() => set(values, true)}>None</button>
        </span>
      )}
    </div>
  );
}

export default function BfParametersView() {
  const [fys, setFys] = useState([]);
  const [fy, setFy] = useState('');
  const [section, setSection] = useState('all');
  const [hiddenRows, setHiddenRows] = useState(() => new Set());     // row ids
  const [hiddenFys, setHiddenFys] = useState(() => new Set());       // FY start years
  const [hiddenMonths, setHiddenMonths] = useState(() => new Set()); // calendar months, '04'
  const [result, setResult] = useState({ key: '', rep: null, error: null });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const loading = !!fy && result.key !== fy;
  const rep = result.rep;

  useEffect(() => {
    fetch(`${API}/api/bf-report/fys`)
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
    fetch(`${API}/api/bf-report?fy=${fy}`)
      .then(async (r) => {
        const body = await r.json().catch(() => ({}));
        if (!r.ok) throw new Error(body.detail || `HTTP ${r.status}`);
        return body;
      })
      .then((d) => { if (live) setResult({ key: fy, rep: d, error: null }); })
      .catch((e) => { if (live) setResult({ key: fy, rep: null, error: e.message }); });
    return () => { live = false; };
  }, [fy]);

  const download = async () => {
    setBusy(true);
    setError(null);
    try {
      const query = new URLSearchParams({ fy });
      if (hiddenRows.size) query.set('hide_rows', [...hiddenRows].join(','));
      if (hiddenFys.size) query.set('hide_fys', [...hiddenFys].join(','));
      if (hiddenMonths.size) query.set('hide_months', [...hiddenMonths].join(','));
      if (section !== 'all') query.set('sections', section);
      const res = await fetch(`${API}/api/bf-report/xlsx?${query}`);
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        throw new Error(body.detail || `HTTP ${res.status}`);
      }
      const cd = res.headers.get('content-disposition') || '';
      const name = (cd.match(/filename="([^"]+)"/) || [])[1] || `BF_Report_${fy}.xlsx`;
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
      setBusy(false);
    }
  };

  const ready = !!fy && !loading && !!rep;
  const fyLabel = (y) => `${y}-${String((Number(y) + 1) % 100).padStart(2, '0')}`;
  const colShown = ({ c }) => !((c.kind === 'fy' && hiddenFys.has(c.fy))
    || (c.kind === 'month' && hiddenMonths.has(c.month.slice(5))));
  // `i` is the column's place in the row's cells, whatever else is hidden.
  const shown = rep ? rep.sections.filter((s) => section === 'all' || s.key === section).map((s) => ({
    ...s, visible: s.columns.map((c, i) => ({ c, i })).filter(colShown),
  })) : [];
  const rows = rep ? rep.rows.filter((r) => !hiddenRows.has(r.id)) : [];
  const plantCount = {};
  rows.forEach((r) => { plantCount[r.plant] = (plantCount[r.plant] || 0) + 1; });
  const seenPlant = new Set();
  // Every past FY any section shows, and the FY's months (all sections have them all).
  const fyChoices = rep ? [...new Map(rep.sections.flatMap((s) => s.columns)
    .filter((c) => c.kind === 'fy').map((c) => [c.fy, c.label])).entries()].sort((a, b) => a[0] - b[0]) : [];
  const monthChoices = rep ? rep.sections[0].columns.filter((c) => c.kind === 'month')
    .map((c) => [c.month.slice(5), c.label]) : [];
  const rowChoices = rep ? [...new Set(rep.rows.map((r) => r.plant))]
    .map((plant) => [plant, rep.rows.filter((r) => r.plant === plant)]) : [];
  const hiddenCount = hiddenRows.size + hiddenFys.size + hiddenMonths.size;

  return (
    <ReportPage
      title="BF Parameters"
      description="Blast furnace parameters month-wise for the selected FY, furnace by furnace with shop and SAIL rows, past FYs, APP and Cum. Cells with no data in the database are left blank."
      actions={(
        <>
          <label htmlFor="bf-fy" style={{ fontWeight: 600, fontSize: '10.5pt' }}>FY</label>
          <select id="bf-fy" value={fy} onChange={(e) => setFy(e.target.value)}
                  style={{ padding: '7px 10px', fontSize: '10.5pt', border: '1px solid #dadce0', borderRadius: 6, background: '#fff' }}>
            {fys.map((y) => <option key={y} value={y}>{fyLabel(y)}</option>)}
          </select>
          <button type="button" onClick={download} disabled={!ready || busy} style={{
            padding: '7px 14px', fontSize: '10.5pt', fontWeight: 600, borderRadius: 6, border: 'none',
            background: !ready || busy ? '#9aa0a6' : '#1e7e34', color: '#fff', cursor: !ready || busy ? 'not-allowed' : 'pointer',
          }}>
            {busy ? 'Preparing…' : '⬇ Excel'}
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
          <div style={{ fontSize: '13pt', fontWeight: 700, textAlign: 'center', marginBottom: 8 }}>{rep.title}</div>
          {!rep.has_plan && (
            <div style={{ padding: '8px 12px', background: '#fffbeb', border: '1px solid #fde68a', borderRadius: 6, color: '#92400e', fontSize: 13, marginBottom: 8 }}>
              No APP data in the database for FY {rep.fy_label}.
            </div>
          )}
          <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', marginBottom: 8 }}>
            {[{ key: 'all', label: 'All parameters' }, ...rep.sections].map((s) => (
              <button key={s.key} type="button" onClick={() => setSection(s.key)} style={{
                fontSize: '8.5pt', padding: '3px 10px', borderRadius: 12, cursor: 'pointer',
                border: section === s.key ? '1px solid #1a73e8' : '1px solid #dadce0',
                background: section === s.key ? '#1a73e8' : '#f8f9fa',
                color: section === s.key ? '#fff' : '#202124',
              }}>{s.label}</button>
            ))}
          </div>
          <details style={{ marginBottom: 8, border: '1px solid #dadce0', borderRadius: 6, padding: '6px 10px' }}>
            <summary style={{ cursor: 'pointer', fontSize: '9.5pt', fontWeight: 600 }}>
              Choose rows, years and months{hiddenCount ? ` (${hiddenCount} hidden)` : ''}
            </summary>
            <div style={{ fontSize: '8.5pt', color: '#5f6368', margin: '6px 0' }}>
              Hiding only changes what is listed: a shop or SAIL row still includes a hidden furnace, and Cum still
              includes a hidden month. The Excel download follows these choices.
            </div>
            <Choices title="Past years" items={fyChoices} hidden={hiddenFys} setHidden={setHiddenFys} />
            <Choices title="Months" items={monthChoices} hidden={hiddenMonths} setHidden={setHiddenMonths} />
            {rowChoices.map(([plant, list]) => (
              <Choices key={plant} title={plant} items={list.map((r) => [r.id, r.kind === 'sail' ? 'SAIL' : r.bf.replace('\n', ' ')])}
                       hidden={hiddenRows} setHidden={setHiddenRows} />
            ))}
            <button type="button" style={linkBtn} onClick={() => {
              setHiddenRows(new Set(rep.rows.filter((r) => r.kind === 'furnace' && r.plant !== 'ISP').map((r) => r.id)));
            }}>Shop and SAIL rows only</button>
            {hiddenCount > 0 && (
              <button type="button" style={linkBtn} onClick={() => {
                setHiddenRows(new Set()); setHiddenFys(new Set()); setHiddenMonths(new Set());
              }}>Show everything</button>
            )}
          </details>
          <div style={{ overflowX: 'auto' }}>
            <table style={{ borderCollapse: 'separate', borderSpacing: 0, fontFamily: "'Arial Narrow', Arial, sans-serif" }}>
              <thead>
                <tr>
                  <th rowSpan={2} style={{ ...cellBase, ...stickyPlant, background: '#fff', border: RULE }}>Plant</th>
                  <th rowSpan={2} style={{ ...cellBase, ...stickyBf, background: '#fff', border: RULE }}>BF#</th>
                  <th colSpan={STATIC_COLS.length} style={{ ...cellBase, border: RULE }}>Furnace</th>
                  {shown.map((s) => (
                    <th key={s.key} colSpan={s.visible.length + (s.aux ? 1 : 0) + (s.pct_label ? 1 : 0)}
                        style={{ ...cellBase, border: RULE, fontSize: '10pt', fontWeight: 700 }}>
                      {s.label}
                    </th>
                  ))}
                </tr>
                <tr>
                  {STATIC_COLS.map(([k, label]) => (
                    <th key={k} style={{ ...cellBase, whiteSpace: 'normal', minWidth: 52, fontWeight: 600 }}>{label}</th>
                  ))}
                  {shown.map((s) => (
                    <React.Fragment key={s.key}>
                      {s.aux && <th style={{ ...cellBase, borderLeft: RULE, fontWeight: 600, whiteSpace: 'normal' }}>Auxiliary Fuel</th>}
                      {s.visible.map(({ c }, j) => (
                        <th key={c.label} style={{
                          ...cellBase, background: colBg(c.kind), fontWeight: c.kind === 'month' || c.kind === 'cum' ? 700 : 400,
                          borderLeft: j === 0 && !s.aux ? RULE : GRID,
                        }}>{c.label}</th>
                      ))}
                      {s.pct_label && (
                        <th style={{ ...cellBase, whiteSpace: 'normal', minWidth: 54, fontWeight: 700, background: s.key === 'production' ? TOTAL_BG : CUM_BG }}>
                          {s.pct_label}
                        </th>
                      )}
                    </React.Fragment>
                  ))}
                </tr>
              </thead>
              <tbody>
                {rows.map((row) => {
                  const firstOfPlant = !seenPlant.has(row.plant);
                  seenPlant.add(row.plant);
                  const total = row.kind !== 'furnace';
                  const bg = row.kind === 'sail' ? TOTAL_BG : undefined;
                  const weight = total ? 700 : 400;
                  const top = firstOfPlant ? RULE : GRID;
                  return (
                    <tr key={`${row.plant}-${row.bf}`} style={{ fontWeight: weight }}>
                      {row.kind === 'sail' ? (
                        <td colSpan={2} style={{ ...cellBase, position: 'sticky', left: 0, zIndex: 2, background: bg, borderTop: RULE, fontWeight: 700 }}>SAIL</td>
                      ) : (
                        <>
                          {firstOfPlant && (
                            <td rowSpan={plantCount[row.plant]} style={{ ...cellBase, ...stickyPlant, background: '#fff', borderTop: RULE, fontWeight: 700, fontSize: '11pt' }}>
                              {row.plant}
                            </td>
                          )}
                          <td style={{ ...cellBase, ...stickyBf, background: '#fff', borderTop: top, whiteSpace: 'normal' }}>{row.bf}</td>
                        </>
                      )}
                      {STATIC_COLS.map(([k]) => (
                        <td key={k} style={{ ...cellBase, background: bg, borderTop: top }}>{row.static[k] ?? ''}</td>
                      ))}
                      {shown.map((s) => {
                        const sec = row.sections[s.key];
                        return (
                          <React.Fragment key={s.key}>
                            {s.aux && <td style={{ ...cellBase, background: bg, borderTop: top, borderLeft: RULE }}>{row.aux_fuel ?? ''}</td>}
                            {s.visible.map(({ c, i }, j) => (
                              <td key={c.label} style={{
                                ...cellBase, background: bg || colBg(c.kind), borderTop: top,
                                borderLeft: j === 0 && !s.aux ? RULE : GRID, fontWeight: c.kind === 'cum' ? 700 : weight,
                              }}>{fmt(sec.cells[i], s.decimals)}</td>
                            ))}
                            {s.pct_label && (
                              <td style={{ ...cellBase, background: bg || (s.key === 'production' ? TOTAL_BG : CUM_BG), borderTop: top }}>
                                {fmt(sec.pct, 0)}
                              </td>
                            )}
                          </React.Fragment>
                        );
                      })}
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </ReportPage>
  );
}
