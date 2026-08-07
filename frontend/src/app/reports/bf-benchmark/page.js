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

function fyMonthsOf(startYear) {
  const months = [];
  for (let i = 0; i < 12; i++) {
    let m = 4 + i, y = startYear;
    if (m > 12) { m -= 12; y += 1; }
    months.push(`${y}-${String(m).padStart(2, '0')}`);
  }
  return months;
}

function fmt(v) {
  if (v === null || v === undefined || v === '') return '—';
  const n = Number(v);
  if (Number.isNaN(n)) return String(v);
  return n.toLocaleString('en-IN', { maximumFractionDigits: 3 });
}

const cell = { padding: '6px 10px', fontSize: '9.5pt', borderBottom: '1px solid #e8eaed', whiteSpace: 'nowrap' };
const th = { ...cell, position: 'sticky', top: 0, backgroundColor: '#e8f0fe', fontWeight: 700, color: '#174ea6', textAlign: 'right' };

export default function BFBenchmarkReportPage() {
  const [params, setParams] = useState([]);
  const [sailBfs, setSailBfs] = useState([]);
  const [externalBfs, setExternalBfs] = useState([]);
  const [selectedBfKeys, setSelectedBfKeys] = useState([]);
  const [fyStart, setFyStart] = useState(CURRENT_FY_START);
  const [selectedMonths, setSelectedMonths] = useState(fyMonthsOf(CURRENT_FY_START));
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
      setSailBfs(pData.sail_bfs || []);
      setExternalBfs(bData.external_bfs || []);
      setSelectedBfKeys((pData.sail_bfs || []).map((b) => `sail:${b.plant}:${b.unit}`));
    } catch (err) {
      setError(err.message);
    }
  }, []);

  useEffect(() => { loadRegistry(); }, [loadRegistry]);
  useEffect(() => { setSelectedMonths(fyMonthsOf(fyStart)); }, [fyStart]);

  const toggleBf = (key) => setSelectedBfKeys((prev) => prev.includes(key) ? prev.filter((k) => k !== key) : [...prev, key]);
  const toggleMonth = (m) => setSelectedMonths((prev) => prev.includes(m) ? prev.filter((x) => x !== m) : [...prev, m]);

  const fetchCompare = async () => {
    if (selectedBfKeys.length === 0 || selectedMonths.length === 0) return;
    setLoading(true); setError('');
    try {
      const res = await fetch(`${API}/api/bf-benchmark/compare`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({ bf_keys: selectedBfKeys, months: selectedMonths }),
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
        body: JSON.stringify({ bf_keys: selectedBfKeys, months: selectedMonths }),
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

  return (
    <>
      <GlobalNavbar />
      <main style={{ maxWidth: '1200px', margin: '0 auto', padding: '32px 20px' }}>
        <h1 style={{ fontSize: '20pt', marginBottom: '4px' }}>Large BF Benchmarking</h1>
        <p style={{ color: '#5f6368', marginBottom: '20px' }}>
          Compare BSP BF-8, RSP BF-5, ISP BF-5 against non-SAIL large BFs.
          Add or edit non-SAIL BF data at <a href="/data-entry/bf-benchmark">BF Benchmarking Entry</a>.
        </p>

        {error && <p style={{ color: '#d93025', marginBottom: '12px' }}>{error}</p>}

        <div style={{ border: '1px solid #dadce0', borderRadius: '8px', padding: '16px', marginBottom: '20px' }}>
          <div style={{ marginBottom: '12px' }}>
            <div style={{ fontSize: '9pt', color: '#5f6368', marginBottom: '6px' }}>Blast Furnaces</div>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px' }}>
              {sailBfs.map((b) => {
                const key = `sail:${b.plant}:${b.unit}`;
                const on = selectedBfKeys.includes(key);
                return (
                  <button key={key} onClick={() => toggleBf(key)}
                    style={{
                      padding: '6px 14px', fontSize: '10pt', fontWeight: 600, borderRadius: '16px', cursor: 'pointer',
                      border: on ? '1px solid #f9ab00' : '1px solid #dadce0',
                      backgroundColor: on ? '#f9ab00' : '#fff', color: on ? '#3c2f00' : '#202124',
                    }}>
                    {b.label}
                  </button>
                );
              })}
              {externalBfs.map((b) => {
                const key = `ext:${b.id}`;
                const on = selectedBfKeys.includes(key);
                return (
                  <button key={key} onClick={() => toggleBf(key)}
                    style={{
                      padding: '6px 14px', fontSize: '10pt', fontWeight: 600, borderRadius: '16px', cursor: 'pointer',
                      border: on ? '1px solid #1a73e8' : '1px solid #dadce0',
                      backgroundColor: on ? '#1a73e8' : '#fff', color: on ? '#fff' : '#202124',
                    }}>
                    {b.name}{b.company ? ` (${b.company})` : ''}
                  </button>
                );
              })}
              {externalBfs.length === 0 && (
                <span style={{ fontSize: '9.5pt', color: '#5f6368' }}>No non-SAIL BFs added yet.</span>
              )}
            </div>
          </div>

          <div style={{ display: 'flex', gap: '16px', alignItems: 'flex-start', flexWrap: 'wrap' }}>
            <div>
              <div style={{ fontSize: '9pt', color: '#5f6368', marginBottom: '6px' }}>Financial Year</div>
              <select value={fyStart} onChange={(e) => setFyStart(Number(e.target.value))}
                style={{ padding: '8px 12px', fontSize: '11pt', border: '1px solid #dadce0', borderRadius: '6px' }}>
                {FY_START_YEARS.map((y) => (
                  <option key={y} value={y}>{`FY ${y}-${String((y + 1) % 100).padStart(2, '0')}`}</option>
                ))}
              </select>
            </div>
            <div style={{ flex: 1, minWidth: '260px' }}>
              <div style={{ fontSize: '9pt', color: '#5f6368', marginBottom: '6px' }}>Months (uncheck to narrow)</div>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px' }}>
                {fyMonthsOf(fyStart).map((m) => (
                  <label key={m} style={{ fontSize: '9.5pt', display: 'flex', alignItems: 'center', gap: '3px' }}>
                    <input type="checkbox" checked={selectedMonths.includes(m)} onChange={() => toggleMonth(m)} />
                    {m}
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
            <div style={{ overflowX: 'auto', marginBottom: '20px' }}>
              <table style={{ borderCollapse: 'collapse' }}>
                <tbody>
                  {result.rows.map((r) => (
                    <tr key={r.bf_key}>
                      <td style={{ ...cell, fontWeight: 600, backgroundColor: r.is_sail ? '#fff8e1' : undefined }}>{r.label}</td>
                      <td style={{ ...cell, textAlign: 'right' }}>{fmt(r.working_volume_m3)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            {dynamicParams.map((p) => (
              <div key={p.key} style={{ marginBottom: '24px' }}>
                <h3 style={{ fontSize: '11pt', marginBottom: '6px' }}>{p.label} ({p.unit})</h3>
                <div style={{ overflowX: 'auto' }}>
                  <table style={{ borderCollapse: 'collapse' }}>
                    <thead>
                      <tr>
                        <th style={{ ...th, textAlign: 'left' }}>BF</th>
                        {result.months.map((m) => <th key={m} style={th}>{m}</th>)}
                        <th style={{ ...th, backgroundColor: '#d2e3fc' }}>FY Avg</th>
                      </tr>
                    </thead>
                    <tbody>
                      {result.rows.map((r) => {
                        const pd = (r.params || {})[p.key] || {};
                        const mv = pd.month_values || {};
                        return (
                          <tr key={r.bf_key} style={{ backgroundColor: r.is_sail ? '#fff8e1' : undefined }}>
                            <td style={{ ...cell, fontWeight: 600, textAlign: 'left' }}>{r.label}</td>
                            {result.months.map((m) => <td key={m} style={{ ...cell, textAlign: 'right' }}>{fmt(mv[m])}</td>)}
                            <td style={{ ...cell, textAlign: 'right', fontWeight: 700 }}>{fmt(pd.avg)}</td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              </div>
            ))}
          </>
        )}
      </main>
    </>
  );
}
