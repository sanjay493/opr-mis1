'use client';

import React, { useState, useMemo } from 'react';
import GlobalNavbar from '@/components/GlobalNavbar';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://127.0.0.1:8082';

const STATUS_META = {
  new:       { label: 'New',       text: '#188038', bg: '#e6f4ea', border: '#34a853' },
  changed:   { label: 'Changed',   text: '#c5221f', bg: '#fce8e6', border: '#dc2626' },
  unchanged: { label: 'Unchanged', text: '#5f6368', bg: '#f1f3f4', border: '#9aa0a6' },
  blank:     { label: 'Blank',     text: '#9aa0a6', bg: '#fafafa', border: '#dadce0' },
  invalid:   { label: 'Invalid',   text: '#c5221f', bg: '#fce8e6', border: '#dc2626' },
};

function fmtNum(v) {
  if (v == null) return '—';
  return Number(v).toLocaleString('en-IN', { maximumFractionDigits: 3 });
}

export default function LegacySmsCrudePage() {
  const [file, setFile] = useState(null);
  const [rows, setRows] = useState(null);
  const [counts, setCounts] = useState(null);
  const [loadingPreview, setLoadingPreview] = useState(false);
  const [confirming, setConfirming] = useState(false);
  const [error, setError] = useState(null);
  const [result, setResult] = useState(null);
  const [viewFilter, setViewFilter] = useState('actionable'); // actionable | all | invalid

  const handleDownloadTemplate = () => {
    window.location.href = `${API_BASE}/api/legacy-sms-crude/template`;
  };

  const handlePreview = async () => {
    if (!file) return;
    setLoadingPreview(true);
    setError(null);
    setResult(null);
    try {
      const formData = new FormData();
      formData.append('file', file);
      const res = await fetch(`${API_BASE}/api/legacy-sms-crude/preview`, {
        method: 'POST',
        body: formData,
      });
      const text = await res.text();
      let json;
      try { json = JSON.parse(text); } catch { throw new Error(text.slice(0, 300)); }
      if (!res.ok) throw new Error(json.detail || 'Preview failed');
      const withApply = json.rows.map((r) => ({ ...r, apply: r.status === 'new' || r.status === 'changed' }));
      setRows(withApply);
      setCounts(json.counts);
    } catch (err) {
      setError(err.message || 'Preview failed');
    } finally {
      setLoadingPreview(false);
    }
  };

  const toggleApply = (idx) => {
    setRows((prev) => prev.map((r, i) => (i === idx ? { ...r, apply: !r.apply } : r)));
  };

  const applyCount = useMemo(() => (rows || []).filter((r) => r.apply).length, [rows]);

  const handleConfirm = async () => {
    if (!rows || applyCount === 0) return;
    if (!window.confirm(`Write ${applyCount} row(s) into production_table? This overwrites any existing values for those months.`)) return;
    setConfirming(true);
    setError(null);
    try {
      const res = await fetch(`${API_BASE}/api/legacy-sms-crude/confirm`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ rows }),
      });
      const json = await res.json();
      if (!res.ok) throw new Error(json.detail || 'Insert failed');
      setResult(json);
      setRows(null);
      setCounts(null);
      setFile(null);
    } catch (err) {
      setError(err.message || 'Insert failed');
    } finally {
      setConfirming(false);
    }
  };

  const visibleRows = useMemo(() => {
    if (!rows) return [];
    if (viewFilter === 'all') return rows;
    if (viewFilter === 'invalid') return rows.filter((r) => r.status === 'invalid');
    return rows.filter((r) => r.status === 'new' || r.status === 'changed');
  }, [rows, viewFilter]);

  return (
    <div style={{ height: '100vh', display: 'flex', flexDirection: 'column', backgroundColor: '#ffffff' }}>
      <GlobalNavbar />
      <main style={{
        flex: 1, overflow: 'auto', padding: '32px', maxWidth: '1200px',
        margin: '0 auto', width: '100%', boxSizing: 'border-box',
      }}>
        <h1 style={{ fontSize: '20pt', fontWeight: 900, color: '#202124', margin: '0 0 6px' }}>
          🗂️ Legacy SMS / Crude Steel Backfill
        </h1>
        <p style={{ fontSize: '11pt', color: '#5f6368', marginBottom: '20px', maxWidth: '820px' }}>
          Download the CSV template (SMS-shop items + Total Crude Steel, per plant, from 2022-04),
          fill in the blank cells from paper legacy records and correct any Total Crude Steel value
          that looks wrong, then upload it here to preview a diff against the database before writing
          anything.
        </p>

        <div style={{
          border: '1px solid #dadce0', borderRadius: '8px', padding: '16px 18px',
          marginBottom: '20px', backgroundColor: '#f8f9fa',
          display: 'flex', alignItems: 'center', gap: '14px', flexWrap: 'wrap',
        }}>
          <button onClick={handleDownloadTemplate} style={btnStyle('#5f6368')}>
            ⬇ Download CSV Template
          </button>
          <input type="file" accept=".csv"
            onChange={(e) => { setFile(e.target.files?.[0] || null); setRows(null); setCounts(null); setResult(null); setError(null); }}
            style={{ fontSize: '10pt' }} />
          <button onClick={handlePreview} disabled={!file || loadingPreview} style={btnStyle('#1a73e8', !file || loadingPreview)}>
            {loadingPreview ? 'Parsing…' : 'Preview Diff'}
          </button>
        </div>

        {error && (
          <div style={{
            padding: '10px 14px', border: '1px solid #f28b82', borderRadius: '6px',
            backgroundColor: '#fce8e6', color: '#c5221f', fontSize: '10.5pt', marginBottom: '16px',
          }}>
            {error}
          </div>
        )}

        {result && (
          <div style={{
            padding: '10px 14px', border: '1px solid #a8dab5', borderRadius: '6px',
            backgroundColor: '#e6f4ea', color: '#188038', fontSize: '10.5pt', marginBottom: '16px',
          }}>
            Saved {result.saved} row(s) to production_table ({result.skipped} skipped).
          </div>
        )}

        {counts && (
          <div style={{ display: 'flex', gap: '10px', marginBottom: '14px', flexWrap: 'wrap' }}>
            {Object.entries(counts).map(([status, n]) => {
              const meta = STATUS_META[status];
              return (
                <div key={status} style={{
                  padding: '6px 14px', borderRadius: '8px', border: `1px solid ${meta.border}`,
                  backgroundColor: meta.bg, color: meta.text, fontSize: '10pt', fontWeight: 700,
                }}>
                  {meta.label}: {n}
                </div>
              );
            })}
          </div>
        )}

        {rows && (
          <>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px', flexWrap: 'wrap', gap: '10px' }}>
              <div style={{ display: 'flex', gap: '6px' }}>
                {[
                  { key: 'actionable', label: 'New + Changed' },
                  { key: 'invalid', label: 'Invalid' },
                  { key: 'all', label: 'All rows' },
                ].map((f) => (
                  <button key={f.key} onClick={() => setViewFilter(f.key)} style={{
                    padding: '6px 14px', borderRadius: '14px',
                    border: `1px solid ${viewFilter === f.key ? '#1a73e8' : '#dadce0'}`,
                    background: viewFilter === f.key ? '#1a73e8' : '#fff',
                    color: viewFilter === f.key ? '#fff' : '#5f6368',
                    fontSize: '9.5pt', fontWeight: 600, cursor: 'pointer',
                  }}>
                    {f.label}
                  </button>
                ))}
              </div>
              <button onClick={handleConfirm} disabled={applyCount === 0 || confirming} style={btnStyle('#10b981', applyCount === 0 || confirming)}>
                {confirming ? 'Writing…' : `Confirm & Insert (${applyCount})`}
              </button>
            </div>

            <div style={{ border: '1px solid #dadce0', borderRadius: '8px', overflow: 'hidden' }}>
              <table style={{ width: '100%', borderCollapse: 'collapse', backgroundColor: '#fff' }}>
                <thead>
                  <tr style={{ backgroundColor: '#f8f9fa', borderBottom: '1px solid #dadce0' }}>
                    <th style={thStyle}>Apply</th>
                    <th style={thStyle}>Month</th>
                    <th style={thStyle}>Plant</th>
                    <th style={thStyle}>Item</th>
                    <th style={{ ...thStyle, textAlign: 'right' }}>CSV Value</th>
                    <th style={{ ...thStyle, textAlign: 'right' }}>DB Value</th>
                    <th style={thStyle}>Status</th>
                  </tr>
                </thead>
                <tbody>
                  {visibleRows.length === 0 && (
                    <tr><td colSpan={7} style={{ padding: '24px', textAlign: 'center', color: '#5f6368', fontSize: '10.5pt' }}>No rows in this view.</td></tr>
                  )}
                  {visibleRows.map((r) => {
                    const meta = STATUS_META[r.status];
                    const idx = rows.indexOf(r);
                    const canApply = r.status === 'new' || r.status === 'changed';
                    return (
                      <tr key={idx} style={{ borderBottom: '1px solid #f1f3f4' }}>
                        <td style={tdStyle}>
                          <input type="checkbox" checked={r.apply} disabled={!canApply}
                            onChange={() => toggleApply(idx)}
                            style={{ cursor: canApply ? 'pointer' : 'not-allowed' }} />
                        </td>
                        <td style={tdStyle}>{r.report_month}</td>
                        <td style={tdStyle}>{r.plant_name}</td>
                        <td style={tdStyle}>{r.item_name}{r.reason ? <div style={{ fontSize: '8.5pt', color: '#c5221f' }}>{r.reason}</div> : null}</td>
                        <td style={{ ...tdStyle, textAlign: 'right' }}>{fmtNum(r.csv_value)}</td>
                        <td style={{ ...tdStyle, textAlign: 'right' }}>{fmtNum(r.db_value)}</td>
                        <td style={tdStyle}>
                          <span style={{
                            padding: '2px 9px', borderRadius: '10px', fontSize: '8.5pt', fontWeight: 700,
                            color: meta.text, backgroundColor: meta.bg, whiteSpace: 'nowrap',
                          }}>
                            {meta.label}
                          </span>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </>
        )}

        {!rows && !result && (
          <div style={{ padding: '40px', textAlign: 'center', color: '#5f6368', fontSize: '11pt', border: '1px solid #dadce0', borderRadius: '8px' }}>
            Download the template, fill it in, then upload it to preview the diff.
          </div>
        )}
      </main>
    </div>
  );
}

const thStyle = { padding: '10px 12px', textAlign: 'left', fontWeight: 700, fontSize: '9.5pt', color: '#5f6368' };
const tdStyle = { padding: '8px 12px', fontSize: '9.5pt', color: '#202124' };

function btnStyle(color, disabled) {
  return {
    padding: '9px 18px', background: disabled ? '#dadce0' : color, color: '#fff',
    border: 'none', borderRadius: '6px', fontSize: '10.5pt', fontWeight: 700,
    cursor: disabled ? 'not-allowed' : 'pointer', whiteSpace: 'nowrap',
  };
}
