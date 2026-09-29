'use client';

import { useEffect, useState, useCallback } from 'react';
import GlobalNavbar from '@/components/GlobalNavbar';

const API = process.env.NEXT_PUBLIC_API_URL || '';

const YEAR_RANGE_START = 2000;
const _now = new Date();
const CURRENT_FY_START = _now.getMonth() >= 3 ? _now.getFullYear() : _now.getFullYear() - 1;
const FY_START_YEARS = Array.from(
  { length: CURRENT_FY_START - YEAR_RANGE_START + 1 },
  (_, i) => YEAR_RANGE_START + i
).reverse();

function fyLabelOf(y) { return `${y}-${String((y + 1) % 100).padStart(2, '0')}`; }

// BF Productivity, O2 Enrichment and Production (Million T — too small a
// scale for a whole number to mean anything) read to 2 decimal places;
// every other param (Working Volume, rates, HBT, etc.) is a whole number.
const TWO_DECIMAL_KEYS = new Set(['bf_productivity', 'o2_enrichment', 'production']);

function fmt(v, key) {
  if (v === null || v === undefined || v === '') return '—';
  const n = Number(v);
  if (Number.isNaN(n)) return String(v);
  const decimals = TWO_DECIMAL_KEYS.has(key) ? 2 : 0;
  return n.toLocaleString('en-IN', { minimumFractionDigits: decimals, maximumFractionDigits: decimals });
}

function monthLabel(ym) {
  const [y, m] = ym.split('-').map(Number);
  const MON = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
  return `${MON[m - 1]}'${String(y).slice(2)}`;
}

// One furnace column per row -> group into Company -> Location -> [rows],
// preserving first-seen order (not alphabetical), matching
// page_bf_benchmark_export.py's _group_rows so the on-screen table and the
// Excel/PDF exports always agree on column order.
function groupRows(rows) {
  const companies = [];
  const byCompany = {};
  for (const r of rows) {
    if (!byCompany[r.company]) { byCompany[r.company] = []; companies.push(r.company); }
    byCompany[r.company].push(r);
  }
  return companies.map((company) => {
    const locations = [];
    const byLoc = {};
    for (const r of byCompany[company]) {
      if (!byLoc[r.location]) { byLoc[r.location] = []; locations.push(r.location); }
      byLoc[r.location].push(r);
    }
    return { company, locations: locations.map((location) => ({ location, rows: byLoc[location] })) };
  });
}

function flatRows(period) {
  return groupRows(period.rows).flatMap((c) => c.locations.flatMap((l) => l.rows));
}

// Best value for a param row, across every furnace column currently shown
// (all periods, SAIL and non-SAIL together) — the whole point of a
// benchmarking table is comparing SAIL against everyone else, so "best for
// the period" is read as best across the whole displayed comparison.
function bestValueFor(paramKey, better, periods) {
  if (!better) return null;
  let best = null;
  for (const period of periods) {
    for (const r of period.rows) {
      if (!r.has_data) continue;
      const v = r.values[paramKey];
      if (v === null || v === undefined) continue;
      if (best === null) best = v;
      else if (better === 'low' && v < best) best = v;
      else if (better === 'high' && v > best) best = v;
    }
  }
  return best;
}

// Three size classes by Working Volume, not four arbitrary bands — chosen
// against SAIL's own fleet (16 furnaces, 1204-3551 m³): the 1650 cut sits in
// the clear gap between DSP BF-4/RSP's smaller furnaces (<=1539) and BSL's
// (>=1758); the 2800 cut sits in the much wider gap between BSP BF-7/BSL
// (<=2250) and the 3 flagship furnaces (>=3445) — which is exactly
// bf_benchmark_registry.SAIL_BFS, so "Large" here reproduces this feature's
// original 3-furnace comparison as one selectable class rather than a
// separate concept.
const WV_SLABS = [
  { key: 'small', label: 'Small (< 1650 m³)', color: '#188038', min: -Infinity, max: 1650 },
  { key: 'medium', label: 'Medium (1650–2800 m³)', color: '#1a73e8', min: 1650, max: 2800 },
  { key: 'large', label: 'Large (≥ 2800 m³)', color: '#7b1fa2', min: 2800, max: Infinity },
];

const th = {
  padding: '5px 8px', fontSize: '9pt', border: '1px solid #dadce0',
  backgroundColor: '#e8f0fe', color: '#174ea6', fontWeight: 700, textAlign: 'center', whiteSpace: 'nowrap',
};
const thExt = { ...th, backgroundColor: '#fce8e6', color: '#a50e0e' };
const td = { padding: '5px 8px', fontSize: '9pt', border: '1px solid #dadce0', textAlign: 'right', whiteSpace: 'nowrap' };
const tdExt = { ...td, backgroundColor: '#fef7f6' };
const tdBest = { ...td, backgroundColor: '#e6f4ea', color: '#0d652d', fontWeight: 700 };
const tdBestExt = { ...tdBest, backgroundColor: '#d9f0df' };
const tdLabel = { ...td, textAlign: 'left', fontWeight: 600 };
const tdUnit = { ...td, textAlign: 'left', color: '#5f6368' };

// Which WV_SLABS bucket a Working Volume falls into, or null if unknown.
function slabFor(wv) {
  if (wv == null) return null;
  return WV_SLABS.find((s) => wv >= s.min && wv < s.max) || null;
}

export default function BFBenchmarkReportPage() {
  const [params, setParams] = useState([]);
  const [sailBfsAll, setSailBfsAll] = useState([]); // every SAIL furnace, each with working_volume_m3
  const [externalBfsAll, setExternalBfsAll] = useState([]);

  const [selectedSailKeys, setSelectedSailKeys] = useState([]);
  const [selectedExtIds, setSelectedExtIds] = useState([]);
  const [activeSlab, setActiveSlab] = useState(null);

  const [selectedYears, setSelectedYears] = useState([CURRENT_FY_START]);
  const [selectedMonths, setSelectedMonths] = useState([]);
  const [monthInput, setMonthInput] = useState('');

  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [downloading, setDownloading] = useState(null);
  const [error, setError] = useState('');

  const loadRegistry = useCallback(async () => {
    try {
      const [pRes, bRes] = await Promise.all([
        fetch(`${API}/api/bf-benchmark/params`, { credentials: 'include' }),
        fetch(`${API}/api/bf-benchmark/external-bfs?active_only=true`, { credentials: 'include' }),
      ]);
      const pData = await pRes.json();
      const bData = await bRes.json();
      setParams(pData.params || []);
      setSailBfsAll(pData.sail_bfs_all || []);
      setExternalBfsAll(bData.external_bfs || []);
      // Default selection: the 3 flagship furnaces this feature originally
      // shipped with (SAIL's "Large" class) — the size buttons below swap
      // this out for Medium/Small, or any furnace can be toggled by hand.
      setSelectedSailKeys((pData.sail_bfs || []).map((b) => `${b.plant}:${b.unit}`));
    } catch (err) {
      setError(err.message);
    }
  }, []);

  useEffect(() => { loadRegistry(); }, [loadRegistry]);

  const toggleSail = (key) => { setActiveSlab(null); setSelectedSailKeys((prev) => prev.includes(key) ? prev.filter((k) => k !== key) : [...prev, key]); };
  const toggleExt = (id) => { setActiveSlab(null); setSelectedExtIds((prev) => prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]); };
  const toggleYear = (y) => setSelectedYears((prev) => prev.includes(y) ? prev.filter((x) => x !== y) : [...prev, y].sort((a, b) => a - b));

  const applySlab = (slab) => {
    if (activeSlab === slab.key) { setActiveSlab(null); return; }
    const inSlab = (wv) => wv != null && wv >= slab.min && wv < slab.max;
    setSelectedSailKeys(sailBfsAll.filter((b) => inSlab(b.working_volume_m3)).map((b) => `${b.plant}:${b.unit}`));
    setSelectedExtIds(externalBfsAll.filter((b) => inSlab(b.working_volume_m3)).map((b) => b.id));
    setActiveSlab(slab.key);
  };

  const addMonth = () => {
    if (!monthInput) return;
    setSelectedMonths((prev) => prev.includes(monthInput) ? prev : [...prev, monthInput].sort());
    setMonthInput('');
  };
  const removeMonth = (m) => setSelectedMonths((prev) => prev.filter((x) => x !== m));

  const requestBody = () => ({
    sail_bf_keys: selectedSailKeys,
    years: selectedYears,
    months: selectedMonths,
    external_bf_ids: selectedExtIds,
  });

  const fetchCompare = async () => {
    if (selectedSailKeys.length === 0 && selectedExtIds.length === 0) return;
    if (selectedYears.length === 0 && selectedMonths.length === 0) {
      setError('Select at least one Financial Year or Month.');
      return;
    }
    setLoading(true); setError('');
    try {
      const res = await fetch(`${API}/api/bf-benchmark/compare`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify(requestBody()),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Could not load comparison.');
      setResult(data);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const downloadFile = async (kind) => {
    setDownloading(kind); setError('');
    try {
      const res = await fetch(`${API}/api/bf-benchmark/${kind}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify(requestBody()),
      });
      if (!res.ok) {
        const b = await res.json().catch(() => ({}));
        throw new Error(b.detail || `HTTP ${res.status}`);
      }
      const blob = await res.blob();
      const objUrl = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = objUrl;
      a.download = `BF_Benchmarking.${kind === 'excel' ? 'xlsx' : 'pdf'}`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      window.URL.revokeObjectURL(objUrl);
    } catch (err) {
      setError(`Download failed: ${err.message}`);
    } finally {
      setDownloading(null);
    }
  };

  const periods = result ? result.periods || [] : [];
  const allParams = result ? result.params : [];
  const periodFlat = periods.map((p) => ({ period: p, rows: flatRows(p) }));

  return (
    <>
      <GlobalNavbar />
      <main style={{
        maxWidth: '1400px', margin: '0 auto', padding: '32px 20px',
        height: 'calc(100vh - 72px)', overflowY: 'auto',
      }}>
        <h1 style={{ fontSize: '20pt', marginBottom: '4px' }}>BF Benchmarking</h1>
        <p style={{ color: '#5f6368', marginBottom: '20px' }}>
          Compare any of SAIL&apos;s 16 blast furnaces against non-SAIL BFs, grouped Company → Location → Furnace.
          Use the Working Volume buttons to jump straight to all Large, Medium or Small furnaces on both sides —
          SAIL&apos;s 3 flagship furnaces (BSP BF-8, RSP BF-5, ISP BF-5) are the Large class.
          Non-SAIL BFs show data for the same Financial Year(s) selected below (blank if that BF hasn&apos;t entered that year).
          Add or edit furnace Working Volume / non-SAIL BF data at <a href="/data-entry/bf-benchmark">BF Benchmarking Entry</a>.
        </p>

        {error && <p style={{ color: '#d93025', marginBottom: '12px' }}>{error}</p>}

        <div style={{ border: '1px solid #dadce0', borderRadius: '8px', padding: '16px', marginBottom: '20px' }}>
          <div style={{ marginBottom: '12px' }}>
            <div style={{ fontSize: '9pt', color: '#5f6368', marginBottom: '6px' }}>
              Select by Working Volume — replaces the furnace selection below with every SAIL and non-SAIL furnace in that size class
            </div>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px' }}>
              {WV_SLABS.map((slab) => {
                const on = activeSlab === slab.key;
                return (
                  <button key={slab.key} onClick={() => applySlab(slab)}
                    style={{
                      padding: '5px 12px', fontSize: '9.5pt', fontWeight: 600, borderRadius: '14px', cursor: 'pointer',
                      border: `1px solid ${slab.color}`,
                      backgroundColor: on ? slab.color : '#fff', color: on ? '#fff' : slab.color,
                    }}>
                    {slab.label}
                  </button>
                );
              })}
            </div>
          </div>

          <div style={{ marginBottom: '12px' }}>
            <div style={{ fontSize: '9pt', color: '#5f6368', marginBottom: '6px' }}>
              SAIL Blast Furnaces — all {sailBfsAll.length}, badge shows size class
            </div>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px' }}>
              {sailBfsAll.map((b) => {
                const key = `${b.plant}:${b.unit}`;
                const on = selectedSailKeys.includes(key);
                const wv = b.working_volume_m3;
                const slab = slabFor(wv);
                return (
                  <button key={key} onClick={() => toggleSail(key)}
                    style={{
                      padding: '6px 14px', fontSize: '10pt', fontWeight: 600, borderRadius: '16px', cursor: 'pointer',
                      border: on ? '1px solid #f9ab00' : '1px solid #dadce0',
                      backgroundColor: on ? '#f9ab00' : '#fff', color: on ? '#3c2f00' : '#202124',
                    }}>
                    {b.label}{wv != null ? ` (${fmt(wv)} m³` : ''}
                    {slab && (
                      <span style={{
                        marginLeft: 4, padding: '1px 5px', borderRadius: '8px', fontSize: '8pt',
                        backgroundColor: on ? 'rgba(0,0,0,0.12)' : slab.color, color: on ? '#3c2f00' : '#fff',
                      }}>
                        {slab.key[0].toUpperCase()}
                      </span>
                    )}
                    {wv != null ? ')' : ''}
                  </button>
                );
              })}
            </div>
          </div>

          <div style={{ marginBottom: '12px' }}>
            <div style={{ fontSize: '9pt', color: '#5f6368', marginBottom: '6px' }}>Non-SAIL Blast Furnaces</div>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px' }}>
              {externalBfsAll.map((b) => {
                const on = selectedExtIds.includes(b.id);
                return (
                  <button key={b.id} onClick={() => toggleExt(b.id)}
                    style={{
                      padding: '6px 14px', fontSize: '10pt', fontWeight: 600, borderRadius: '16px', cursor: 'pointer',
                      border: on ? '1px solid #a50e0e' : '1px solid #dadce0',
                      backgroundColor: on ? '#a50e0e' : '#fff', color: on ? '#fff' : '#202124',
                    }}>
                    {b.name}{b.company ? ` (${b.company}${b.location ? ` – ${b.location}` : ''})` : ''}
                    {b.working_volume_m3 != null ? ` · ${fmt(b.working_volume_m3)} m³` : ''}
                    {b.latest_fy ? '' : ' — no data yet'}
                  </button>
                );
              })}
              {externalBfsAll.length === 0 && (
                <span style={{ fontSize: '9.5pt', color: '#5f6368' }}>No non-SAIL BFs added yet.</span>
              )}
            </div>
          </div>

          <div style={{ fontSize: '9pt', color: '#5f6368', marginBottom: '10px' }}>
            Period(s). Pick any mix of Financial Years and/or specific Month-Years; each becomes its own column group.
            Non-SAIL BFs only ever appear under Financial Year columns (they don&apos;t publish monthly figures).
          </div>
          <div style={{ display: 'flex', gap: '28px', flexWrap: 'wrap' }}>
            <div>
              <div style={{ fontSize: '9pt', fontWeight: 700, color: '#374151', marginBottom: '4px' }}>Financial Year(s)</div>
              <div style={{ fontSize: '8.5pt', color: '#9aa0a6', marginBottom: '6px' }}>
                Each FY shows that year's full-year cumulative (Apr→Mar), as stored against March.
              </div>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px', maxWidth: '460px' }}>
                {FY_START_YEARS.slice(0, 15).map((y) => {
                  const on = selectedYears.includes(y);
                  return (
                    <button key={y} onClick={() => toggleYear(y)}
                      style={{
                        padding: '4px 10px', fontSize: '9.5pt', fontWeight: 600, borderRadius: '14px', cursor: 'pointer',
                        border: on ? '1px solid #1a73e8' : '1px solid #dadce0',
                        backgroundColor: on ? '#1a73e8' : '#fff', color: on ? '#fff' : '#202124',
                      }}>
                      {fyLabelOf(y)}
                    </button>
                  );
                })}
              </div>
            </div>

            <div>
              <div style={{ fontSize: '9pt', fontWeight: 700, color: '#374151', marginBottom: '4px' }}>Month-Year(s)</div>
              <div style={{ fontSize: '8.5pt', color: '#9aa0a6', marginBottom: '6px' }}>
                Each month shows that single month's own techno data (SAIL only).
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '8px' }}>
                <input type="month" value={monthInput} onChange={(e) => setMonthInput(e.target.value)}
                  style={{ padding: '5px 8px', fontSize: '9.5pt', border: '1px solid #dadce0', borderRadius: '4px' }} />
                <button className="btn btn-secondary" onClick={addMonth} disabled={!monthInput}>Add</button>
              </div>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px', maxWidth: '460px' }}>
                {selectedMonths.map((m) => (
                  <span key={m} style={{
                    display: 'inline-flex', alignItems: 'center', gap: '6px',
                    padding: '4px 10px', fontSize: '9.5pt', fontWeight: 600, borderRadius: '14px',
                    border: '1px solid #1a73e8', backgroundColor: '#1a73e8', color: '#fff',
                  }}>
                    {monthLabel(m)}
                    <span onClick={() => removeMonth(m)} style={{ cursor: 'pointer', fontWeight: 700 }}>×</span>
                  </span>
                ))}
                {selectedMonths.length === 0 && (
                  <span style={{ fontSize: '9pt', color: '#5f6368' }}>No months selected yet.</span>
                )}
              </div>
            </div>
          </div>

          <div style={{ marginTop: '16px', display: 'flex', gap: '10px' }}>
            <button className="btn btn-primary" onClick={fetchCompare} disabled={loading}>
              {loading ? 'Loading…' : 'Compare'}
            </button>
            {result && (
              <>
                <button className="btn btn-secondary" disabled={!!downloading} onClick={() => downloadFile('excel')}>
                  {downloading === 'excel' ? 'Downloading…' : 'Download Excel'}
                </button>
                <button className="btn btn-secondary" disabled={!!downloading} onClick={() => downloadFile('pdf')}>
                  {downloading === 'pdf' ? 'Downloading…' : 'Download PDF'}
                </button>
              </>
            )}
          </div>
        </div>

        {result && (
          <div style={{ overflowX: 'auto', marginBottom: '24px' }}>
            <div style={{ display: 'flex', gap: '16px', marginBottom: '8px', fontSize: '8.5pt', color: '#5f6368' }}>
              <span><span style={{ display: 'inline-block', width: 12, height: 12, backgroundColor: '#fef7f6', border: '1px solid #a50e0e', verticalAlign: 'middle', marginRight: 4 }} />Non-SAIL</span>
              <span><span style={{ display: 'inline-block', width: 12, height: 12, backgroundColor: '#e6f4ea', border: '1px solid #0d652d', verticalAlign: 'middle', marginRight: 4 }} />Best value in row</span>
            </div>
            <table style={{ borderCollapse: 'collapse' }}>
              <thead>
                <tr>
                  <th style={{ ...th, textAlign: 'left' }} rowSpan={4}>Techno Parameter</th>
                  <th style={{ ...th, textAlign: 'left' }} rowSpan={4}>Unit</th>
                  {periodFlat.map(({ period, rows }) => (
                    rows.length === 0 ? null :
                    <th key={period.key} style={th} colSpan={rows.length}>{period.label}</th>
                  ))}
                </tr>
                <tr>
                  {periodFlat.flatMap(({ period, rows }) => {
                    if (rows.length === 0) return [];
                    return groupRows(rows).map(({ company, locations }) => {
                      const width = locations.reduce((n, l) => n + l.rows.length, 0);
                      const isExt = locations[0].rows[0].is_external;
                      return <th key={`${period.key}-${company}`} style={isExt ? thExt : th} colSpan={width}>{company}</th>;
                    });
                  })}
                </tr>
                <tr>
                  {periodFlat.flatMap(({ period, rows }) => {
                    if (rows.length === 0) return [];
                    return groupRows(rows).flatMap(({ locations }) => locations.map(({ location, rows: locRows }) => (
                      <th key={`${period.key}-${location}`} style={locRows[0].is_external ? thExt : th} colSpan={locRows.length}>{location}</th>
                    )));
                  })}
                </tr>
                <tr>
                  {periodFlat.flatMap(({ period, rows }) => rows.map((r) => (
                    <th key={`${period.key}-${r.bf_key}`} style={r.is_external ? thExt : th}>{r.label}</th>
                  )))}
                </tr>
              </thead>
              <tbody>
                {allParams.map((p) => {
                  const best = bestValueFor(p.key, p.better, periods);
                  return (
                    <tr key={p.key}>
                      <td style={tdLabel}>{p.label}</td>
                      <td style={tdUnit}>{p.unit}</td>
                      {periodFlat.flatMap(({ period, rows }) => rows.map((r) => {
                        if (!r.has_data) {
                          return <td key={`${period.key}-${r.bf_key}-${p.key}`} style={r.is_external ? tdExt : td}>—</td>;
                        }
                        const v = r.values[p.key];
                        const isBest = best !== null && v === best;
                        const style = isBest ? (r.is_external ? tdBestExt : tdBest) : (r.is_external ? tdExt : td);
                        return <td key={`${period.key}-${r.bf_key}-${p.key}`} style={style}>{fmt(v, p.key)}</td>;
                      }))}
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </main>
    </>
  );
}
