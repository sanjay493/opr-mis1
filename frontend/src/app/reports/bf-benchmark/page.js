'use client';

import { Fragment, useEffect, useState, useCallback } from 'react';
import GlobalNavbar from '@/components/GlobalNavbar';

const API = process.env.NEXT_PUBLIC_API_URL || '';

const YEAR_RANGE_START = 2000;
const _now = new Date();
const CURRENT_FY_START = _now.getMonth() >= 3 ? _now.getFullYear() : _now.getFullYear() - 1;
const FY_START_YEARS = Array.from(
  { length: CURRENT_FY_START - YEAR_RANGE_START + 1 },
  (_, i) => YEAR_RANGE_START + i
).reverse();

// FY-relative month slots: 0=April..11=March
const MONTH_SLOT_LABELS = ['Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec', 'Jan', 'Feb', 'Mar'];

function fyLabelOf(y) { return `${y}-${String((y + 1) % 100).padStart(2, '0')}`; }

function fmt(v) {
  if (v === null || v === undefined || v === '') return '—';
  const n = Number(v);
  if (Number.isNaN(n)) return String(v);
  return n.toLocaleString('en-IN', { maximumFractionDigits: 3 });
}

const th = {
  padding: '5px 8px', fontSize: '9pt', border: '1px solid #dadce0',
  backgroundColor: '#e8f0fe', color: '#174ea6', fontWeight: 700, textAlign: 'center', whiteSpace: 'nowrap',
};
const thAvg = { ...th, backgroundColor: '#d2e3fc' };
const td = { padding: '5px 8px', fontSize: '9pt', border: '1px solid #dadce0', textAlign: 'right', whiteSpace: 'nowrap' };
const tdAvg = { ...td, fontWeight: 700, backgroundColor: '#d2e3fc' };
const tdLabel = { ...td, textAlign: 'left', fontWeight: 600 };
const tdUnit = { ...td, textAlign: 'left', color: '#5f6368' };

export default function BFBenchmarkReportPage() {
  const [params, setParams] = useState([]);
  const [sailBfsAll, setSailBfsAll] = useState([]);
  const [externalBfsAll, setExternalBfsAll] = useState([]);

  const [selectedSailKeys, setSelectedSailKeys] = useState([]);
  const [selectedExtIds, setSelectedExtIds] = useState([]);
  const [selectedYears, setSelectedYears] = useState([CURRENT_FY_START]);
  const [selectedMonthSlots, setSelectedMonthSlots] = useState(Array.from({ length: 12 }, (_, i) => i));

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
      setSailBfsAll(pData.sail_bfs || []);
      setExternalBfsAll(bData.external_bfs || []);
      setSelectedSailKeys((pData.sail_bfs || []).map((b) => `${b.plant}:${b.unit}`));
    } catch (err) {
      setError(err.message);
    }
  }, []);

  useEffect(() => { loadRegistry(); }, [loadRegistry]);

  const toggleSail = (key) => setSelectedSailKeys((prev) => prev.includes(key) ? prev.filter((k) => k !== key) : [...prev, key]);
  const toggleExt = (id) => setSelectedExtIds((prev) => prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]);
  const toggleYear = (y) => setSelectedYears((prev) => prev.includes(y) ? prev.filter((x) => x !== y) : [...prev, y].sort((a, b) => a - b));
  const toggleSlot = (s) => setSelectedMonthSlots((prev) => prev.includes(s) ? prev.filter((x) => x !== s) : [...prev, s].sort((a, b) => a - b));

  const requestBody = () => ({
    sail_bf_keys: selectedSailKeys,
    years: selectedYears,
    month_slots: selectedMonthSlots,
    external_bf_ids: selectedExtIds,
  });

  const fetchCompare = async () => {
    if (selectedSailKeys.length === 0 && selectedExtIds.length === 0) return;
    if (selectedSailKeys.length > 0 && selectedYears.length === 0) {
      setError('Select at least one Financial Year for the SAIL BFs.');
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

  const dynamicParams = params.filter((p) => !p.static);
  const years = result ? Object.keys(result.year_blocks).sort((a, b) => Number(a) - Number(b)) : [];
  const extIds = result ? Object.keys(result.external_blocks) : [];
  const nSail = result ? result.sail_bfs.length : 0;

  return (
    <>
      <GlobalNavbar />
      <main style={{
        maxWidth: '1400px', margin: '0 auto', padding: '32px 20px',
        height: 'calc(100vh - 72px)', overflowY: 'auto',
      }}>
        <h1 style={{ fontSize: '20pt', marginBottom: '4px' }}>Large BF Benchmarking</h1>
        <p style={{ color: '#5f6368', marginBottom: '20px' }}>
          Compare BSP BF-8, RSP BF-5, ISP BF-5 against non-SAIL large BFs. Non-SAIL BFs show their own
          most recent data year. Add or edit non-SAIL BF data at <a href="/data-entry/bf-benchmark">BF Benchmarking Entry</a>.
        </p>

        {error && <p style={{ color: '#d93025', marginBottom: '12px' }}>{error}</p>}

        <div style={{ border: '1px solid #dadce0', borderRadius: '8px', padding: '16px', marginBottom: '20px' }}>
          <div style={{ marginBottom: '12px' }}>
            <div style={{ fontSize: '9pt', color: '#5f6368', marginBottom: '6px' }}>SAIL Blast Furnaces</div>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px' }}>
              {sailBfsAll.map((b) => {
                const key = `${b.plant}:${b.unit}`;
                const on = selectedSailKeys.includes(key);
                return (
                  <button key={key} onClick={() => toggleSail(key)}
                    style={{
                      padding: '6px 14px', fontSize: '10pt', fontWeight: 600, borderRadius: '16px', cursor: 'pointer',
                      border: on ? '1px solid #f9ab00' : '1px solid #dadce0',
                      backgroundColor: on ? '#f9ab00' : '#fff', color: on ? '#3c2f00' : '#202124',
                    }}>
                    {b.label}
                  </button>
                );
              })}
            </div>
          </div>

          <div style={{ marginBottom: '12px' }}>
            <div style={{ fontSize: '9pt', color: '#5f6368', marginBottom: '6px' }}>Non-SAIL Blast Furnaces (shown for their own last-available year)</div>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px' }}>
              {externalBfsAll.map((b) => {
                const on = selectedExtIds.includes(b.id);
                return (
                  <button key={b.id} onClick={() => toggleExt(b.id)}
                    style={{
                      padding: '6px 14px', fontSize: '10pt', fontWeight: 600, borderRadius: '16px', cursor: 'pointer',
                      border: on ? '1px solid #1a73e8' : '1px solid #dadce0',
                      backgroundColor: on ? '#1a73e8' : '#fff', color: on ? '#fff' : '#202124',
                    }}>
                    {b.name}{b.company ? ` (${b.company})` : ''}
                    {b.latest_report_month ? '' : ' — no data'}
                  </button>
                );
              })}
              {externalBfsAll.length === 0 && (
                <span style={{ fontSize: '9.5pt', color: '#5f6368' }}>No non-SAIL BFs added yet.</span>
              )}
            </div>
          </div>

          <div style={{ display: 'flex', gap: '24px', flexWrap: 'wrap' }}>
            <div>
              <div style={{ fontSize: '9pt', color: '#5f6368', marginBottom: '6px' }}>Financial Year(s) — applies to SAIL BFs</div>
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
              <div style={{ fontSize: '9pt', color: '#5f6368', marginBottom: '6px' }}>Months — applies to SAIL BFs (uncheck to narrow)</div>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px', maxWidth: '360px' }}>
                {MONTH_SLOT_LABELS.map((label, slot) => (
                  <label key={slot} style={{ fontSize: '9.5pt', display: 'flex', alignItems: 'center', gap: '3px' }}>
                    <input type="checkbox" checked={selectedMonthSlots.includes(slot)} onChange={() => toggleSlot(slot)} />
                    {label}
                  </label>
                ))}
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
          <>
            <h3 style={{ fontSize: '11pt' }}>Working Volume (m³)</h3>
            <div style={{ overflowX: 'auto', marginBottom: '24px' }}>
              <table style={{ borderCollapse: 'collapse' }}>
                <tbody>
                  {years.flatMap((y) => result.year_blocks[y].rows.map((r) => (
                    <tr key={`wv-${y}-${r.bf_key}`}>
                      <td style={{ ...tdLabel, backgroundColor: '#fff8e1' }}>{r.label} <span style={{ color: '#5f6368', fontWeight: 400 }}>(FY {result.year_blocks[y].fy_label})</span></td>
                      <td style={td}>{fmt(r.working_volume_m3)}</td>
                    </tr>
                  )))}
                  {extIds.map((id) => {
                    const eb = result.external_blocks[id];
                    return (
                      <tr key={`wv-ext-${id}`}>
                        <td style={tdLabel}>{eb.label}{eb.fy_label ? ` (FY ${eb.fy_label})` : ''}</td>
                        <td style={td}>{fmt(eb.working_volume_m3)}</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>

            <div style={{ overflowX: 'auto', marginBottom: '24px' }}>
              <table style={{ borderCollapse: 'collapse' }}>
                <thead>
                  <tr>
                    <th style={{ ...th, textAlign: 'left' }} rowSpan={3}>Techno Parameter</th>
                    <th style={{ ...th, textAlign: 'left' }} rowSpan={3}>Unit</th>
                    {years.map((y) => {
                      const yb = result.year_blocks[y];
                      const width = (yb.months.length + 1) * nSail;
                      return <th key={y} style={th} colSpan={width}>{`FY ${yb.fy_label}`}</th>;
                    })}
                    {extIds.map((id) => {
                      const eb = result.external_blocks[id];
                      const width = eb.has_data ? eb.months.length + 1 : 1;
                      return (
                        <th key={id} style={th} colSpan={width}>
                          {eb.has_data ? `${eb.label} (FY ${eb.fy_label})` : `${eb.label} (no data)`}
                        </th>
                      );
                    })}
                  </tr>
                  <tr>
                    {years.flatMap((y) => {
                      const yb = result.year_blocks[y];
                      return [...yb.months, 'FY Avg'].map((m, i) => (
                        <th key={`${y}-m-${i}`} style={m === 'FY Avg' ? thAvg : th} colSpan={nSail}>{m}</th>
                      ));
                    })}
                    {extIds.map((id) => {
                      const eb = result.external_blocks[id];
                      if (!eb.has_data) return <th key={id} style={th} rowSpan={2}>—</th>;
                      return [...eb.months, 'FY Avg'].map((m, i) => (
                        <th key={`${id}-m-${i}`} style={m === 'FY Avg' ? thAvg : th} rowSpan={2}>{m}</th>
                      ));
                    })}
                  </tr>
                  <tr>
                    {years.flatMap((y) => {
                      const yb = result.year_blocks[y];
                      return Array.from({ length: yb.months.length + 1 }).flatMap((_, gi) =>
                        result.sail_bfs.map((b) => (
                          <th key={`${y}-${gi}-${b.plant}`} style={gi === yb.months.length ? thAvg : th}>{b.plant}</th>
                        ))
                      );
                    })}
                  </tr>
                </thead>
                <tbody>
                  {dynamicParams.map((p) => (
                    <tr key={p.key}>
                      <td style={tdLabel}>{p.label}</td>
                      <td style={tdUnit}>{p.unit}</td>
                      {years.flatMap((y) => {
                        const yb = result.year_blocks[y];
                        const monthCells = yb.months.flatMap((m) =>
                          result.sail_bfs.map((b, bidx) => {
                            const pd = yb.rows[bidx].params[p.key] || {};
                            return <td key={`${y}-${m}-${b.plant}-${p.key}`} style={td}>{fmt((pd.month_values || {})[m])}</td>;
                          })
                        );
                        const avgCells = result.sail_bfs.map((b, bidx) => {
                          const pd = yb.rows[bidx].params[p.key] || {};
                          return <td key={`${y}-avg-${b.plant}-${p.key}`} style={tdAvg}>{fmt(pd.avg)}</td>;
                        });
                        return [...monthCells, ...avgCells];
                      })}
                      {extIds.map((id) => {
                        const eb = result.external_blocks[id];
                        if (!eb.has_data) return <td key={id} style={td}>—</td>;
                        const pd = eb.params[p.key] || {};
                        const mv = pd.month_values || {};
                        return (
                          <Fragment key={`${id}-${p.key}`}>
                            {eb.months.map((m) => <td key={`${id}-${m}-${p.key}`} style={td}>{fmt(mv[m])}</td>)}
                            <td style={tdAvg}>{fmt(pd.avg)}</td>
                          </Fragment>
                        );
                      })}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </>
        )}
      </main>
    </>
  );
}
