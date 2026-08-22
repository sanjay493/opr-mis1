'use client';

import RequireEditor from '@/components/RequireEditor';

import React, { useState, useMemo } from 'react';
import GlobalNavbar from '@/components/GlobalNavbar';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || '';

const STATUS_META = {
  new:       { label: 'New',       text: '#188038', bg: '#e6f4ea', border: '#34a853' },
  changed:   { label: 'Changed',   text: '#c5221f', bg: '#fce8e6', border: '#dc2626' },
  unchanged: { label: 'Unchanged', text: '#5f6368', bg: '#f1f3f4', border: '#9aa0a6' },
  blank:     { label: 'Blank',     text: '#9aa0a6', bg: '#fafafa', border: '#dadce0' },
};

const PRODUCT_LABEL = { HM: 'Hot Metal', CS: 'Crude Steel', SS: 'Saleable Steel' };
const PLANT_LABEL = { SAIL: 'SAIL 5 ISPs' };

function fmtNum(v) {
  if (v == null) return '—';
  return Number(v).toLocaleString('en-IN', { maximumFractionDigits: 3 });
}

function CostTrendExtractPageInner() {
  const [file, setFile] = useState(null);
  const [meta, setMeta] = useState(null); // {report_month, is_till_month, field, filename}
  const [rows, setRows] = useState(null);
  const [counts, setCounts] = useState(null);
  const [loadingPreview, setLoadingPreview] = useState(false);
  const [confirming, setConfirming] = useState(false);
  const [error, setError] = useState(null);
  const [result, setResult] = useState(null);
  const [viewFilter, setViewFilter] = useState('actionable'); // actionable | all

  const handlePreview = async () => {
    if (!file) return;
    setLoadingPreview(true);
    setError(null);
    setResult(null);
    try {
      const formData = new FormData();
      formData.append('file', file);
      const res = await fetch(`${API_BASE}/api/cost-trend-extract/preview`, {
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
      setMeta({
        report_month: json.report_month, is_till_month: json.is_till_month,
        field: json.field, filename: json.filename,
      });
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
    if (!rows || applyCount === 0 || !meta) return;
    const fieldLabel = meta.is_till_month ? 'Till Month' : 'Month';
    if (!window.confirm(
      `Write ${applyCount} value(s) into Cost Trend for ${meta.report_month} (${fieldLabel} column)? `
      + `This overwrites any existing value for those cells.`
    )) return;
    setConfirming(true);
    setError(null);
    try {
      const res = await fetch(`${API_BASE}/api/cost-trend-extract/confirm`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ report_month: meta.report_month, field: meta.field, rows }),
      });
      const json = await res.json();
      if (!res.ok) throw new Error(json.detail || 'Save failed');
      setResult(json);
      setRows(null);
      setCounts(null);
      setMeta(null);
      setFile(null);
    } catch (err) {
      setError(err.message || 'Save failed');
    } finally {
      setConfirming(false);
    }
  };

  const visibleRows = useMemo(() => {
    if (!rows) return [];
    if (viewFilter === 'all') return rows;
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
          📊 Cost Trend Excel Extractor
        </h1>
        <p style={{ fontSize: '11pt', color: '#5f6368', marginBottom: '20px', maxWidth: '820px' }}>
          Upload one "ELHM CS SS ..." elementwise cost workbook (Report_format/Cost/ — one file per
          month for the Month column, one "APRIL-&lt;month&gt;" cumulative file per month for the
          Till Month column). Pulls Variable and Fixed cost (Rs/T) for BSP/DSP/RSP/BSL/ISP/SAIL across
          Hot Metal, Crude Steel and Saleable Steel from each sheet&apos;s TOTAL COST row, then previews a
          diff against the database before writing anything. Total Cost stays computed on the report,
          same as manual entry.
        </p>

        <div style={{
          border: '1px solid #dadce0', borderRadius: '8px', padding: '16px 18px',
          marginBottom: '20px', backgroundColor: '#f8f9fa',
          display: 'flex', alignItems: 'center', gap: '14px', flexWrap: 'wrap',
        }}>
          <input type="file" accept=".xlsx"
            onChange={(e) => { setFile(e.target.files?.[0] || null); setRows(null); setCounts(null); setMeta(null); setResult(null); setError(null); }}
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
            Saved {result.saved} value(s) to Cost Trend ({result.skipped} skipped).
          </div>
        )}

        {meta && (
          <div style={{
            display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '14px', flexWrap: 'wrap',
          }}>
            <span style={{
              padding: '6px 14px', borderRadius: '8px', border: '1px solid #1a73e8',
              backgroundColor: '#e8f0fe', color: '#1a73e8', fontSize: '10pt', fontWeight: 700,
            }}>
              Report Month: {meta.report_month}
            </span>
            <span style={{
              padding: '6px 14px', borderRadius: '8px', border: `1px solid ${meta.is_till_month ? '#8430ce' : '#0284c7'}`,
              backgroundColor: meta.is_till_month ? '#f3e8fd' : '#e0f2fe',
              color: meta.is_till_month ? '#8430ce' : '#0284c7', fontSize: '10pt', fontWeight: 700,
            }}>
              {meta.is_till_month ? 'Till Month (cumulative)' : 'Month'} column
            </span>
            <span style={{ fontSize: '9.5pt', color: '#5f6368' }}>from {meta.filename}</span>
          </div>
        )}

        {counts && (
          <div style={{ display: 'flex', gap: '10px', marginBottom: '14px', flexWrap: 'wrap' }}>
            {Object.entries(counts).map(([status, n]) => {
              const stMeta = STATUS_META[status];
              return (
                <div key={status} style={{
                  padding: '6px 14px', borderRadius: '8px', border: `1px solid ${stMeta.border}`,
                  backgroundColor: stMeta.bg, color: stMeta.text, fontSize: '10pt', fontWeight: 700,
                }}>
                  {stMeta.label}: {n}
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
                {confirming ? 'Writing…' : `Confirm & Save (${applyCount})`}
              </button>
            </div>

            <div style={{ border: '1px solid #dadce0', borderRadius: '8px', overflow: 'hidden' }}>
              <table style={{ width: '100%', borderCollapse: 'collapse', backgroundColor: '#fff' }}>
                <thead>
                  <tr style={{ backgroundColor: '#f8f9fa', borderBottom: '1px solid #dadce0' }}>
                    <th style={thStyle}>Apply</th>
                    <th style={thStyle}>Product</th>
                    <th style={thStyle}>Plant</th>
                    <th style={thStyle}>Cost Type</th>
                    <th style={{ ...thStyle, textAlign: 'right' }}>Extracted Value</th>
                    <th style={{ ...thStyle, textAlign: 'right' }}>DB Value</th>
                    <th style={thStyle}>Status</th>
                  </tr>
                </thead>
                <tbody>
                  {visibleRows.length === 0 && (
                    <tr><td colSpan={7} style={{ padding: '24px', textAlign: 'center', color: '#5f6368', fontSize: '10.5pt' }}>No rows in this view.</td></tr>
                  )}
                  {visibleRows.map((r) => {
                    const stMeta = STATUS_META[r.status];
                    const idx = rows.indexOf(r);
                    const canApply = r.status === 'new' || r.status === 'changed';
                    return (
                      <tr key={idx} style={{ borderBottom: '1px solid #f1f3f4' }}>
                        <td style={tdStyle}>
                          <input type="checkbox" checked={r.apply} disabled={!canApply}
                            onChange={() => toggleApply(idx)}
                            style={{ cursor: canApply ? 'pointer' : 'not-allowed' }} />
                        </td>
                        <td style={tdStyle}>{PRODUCT_LABEL[r.product] || r.product}</td>
                        <td style={tdStyle}>{PLANT_LABEL[r.plant] || r.plant}</td>
                        <td style={tdStyle}>{r.cost_type === 'VARIABLE' ? 'Variable' : 'Fixed'}</td>
                        <td style={{ ...tdStyle, textAlign: 'right' }}>{fmtNum(r.extracted_value)}</td>
                        <td style={{ ...tdStyle, textAlign: 'right' }}>{fmtNum(r.db_value)}</td>
                        <td style={tdStyle}>
                          <span style={{
                            padding: '2px 9px', borderRadius: '10px', fontSize: '8.5pt', fontWeight: 700,
                            color: stMeta.text, backgroundColor: stMeta.bg, whiteSpace: 'nowrap',
                          }}>
                            {stMeta.label}
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
            Choose an "ELHM CS SS ..." workbook, then Preview Diff.
          </div>
        )}
      </main>
    </div>
  );
}

export default function CostTrendExtractPage() {
  return (
    <RequireEditor>
      <CostTrendExtractPageInner />
    </RequireEditor>
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
