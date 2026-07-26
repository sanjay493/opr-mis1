'use client';

import React, { useState } from 'react';
import GlobalNavbar from '@/components/GlobalNavbar';

const API = process.env.NEXT_PUBLIC_API_URL || '';

const MONTH_NAMES = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];

function monthLabel(ym) {
  const [y, m] = ym.split('-');
  return `${MONTH_NAMES[parseInt(m, 10) - 1]}'${y.slice(2)}`;
}

function previousMonth() {
  const now = new Date();
  const y = now.getFullYear();
  const m = now.getMonth(); // 0-based == "last month" 1-based
  const py = m === 0 ? y - 1 : y;
  const pm = m === 0 ? 12 : m;
  return `${py}-${String(pm).padStart(2, '0')}`;
}

function fmt(v) {
  if (v == null) return '—';
  return Number(v).toLocaleString('en-IN', { maximumFractionDigits: 3 });
}

const cardStyle = {
  padding: '20px 24px',
  border: '1px solid #dadce0',
  borderRadius: '8px',
  backgroundColor: '#f8f9fa',
  marginBottom: '24px',
};

const btnStyle = (disabled) => ({
  padding: '9px 24px',
  fontSize: '11pt',
  fontWeight: 700,
  border: 'none',
  borderRadius: '6px',
  cursor: disabled ? 'not-allowed' : 'pointer',
  backgroundColor: disabled ? '#dadce0' : '#1a73e8',
  color: '#ffffff',
});

export default function OnePageReportPage() {
  const [dlMonth, setDlMonth] = useState(previousMonth());
  const [downloading, setDownloading] = useState(false);
  const [dlError, setDlError] = useState(null);

  const [srcMonth, setSrcMonth] = useState(previousMonth());
  const [file, setFile] = useState(null);
  const [preview, setPreview] = useState(null);
  const [extracting, setExtracting] = useState(false);
  const [saving, setSaving] = useState(false);
  const [saveResult, setSaveResult] = useState(null);
  const [error, setError] = useState(null);

  const handleDownload = async () => {
    setDownloading(true);
    setDlError(null);
    try {
      const res = await fetch(`${API}/api/sail-1page-report?month=${encodeURIComponent(dlMonth)}`);
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        throw new Error(body.detail || `HTTP ${res.status}`);
      }
      const blob = await res.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `1_page_report_${dlMonth}.xlsx`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      window.URL.revokeObjectURL(url);
    } catch (e) {
      setDlError(`Download failed: ${e.message}`);
    } finally {
      setDownloading(false);
    }
  };

  const handleExtract = async () => {
    if (!file) return;
    setExtracting(true);
    setError(null);
    setPreview(null);
    setSaveResult(null);
    try {
      const fd = new FormData();
      fd.append('file', file);
      fd.append('month', srcMonth);
      const res = await fetch(`${API}/api/sail-1page/preview`, { method: 'POST', body: fd });
      const body = await res.json();
      if (!res.ok) throw new Error(body.detail || `HTTP ${res.status}`);
      setPreview(body);
    } catch (e) {
      setError(`Extraction failed: ${e.message}`);
    } finally {
      setExtracting(false);
    }
  };

  const handleSave = async () => {
    if (!preview) return;
    setSaving(true);
    setError(null);
    try {
      const res = await fetch(`${API}/api/sail-1page/confirm`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          report_month: srcMonth,
          sales_rows: preview.sales_rows,
          stock_rows: preview.stock_rows,
        }),
      });
      const body = await res.json();
      if (!res.ok) throw new Error(body.detail || `HTTP ${res.status}`);
      setSaveResult(body);
    } catch (e) {
      setError(`Save failed: ${e.message}`);
    } finally {
      setSaving(false);
    }
  };

  const selectStyle = {
    padding: '9px 14px',
    fontSize: '11pt',
    border: '1px solid #dadce0',
    borderRadius: '6px',
    backgroundColor: '#ffffff',
    minWidth: '140px',
  };

  return (
    <div style={{ minHeight: '100vh', backgroundColor: '#ffffff' }}>
      <GlobalNavbar />
      <main style={{ maxWidth: '1100px', margin: '0 auto', padding: '32px' }}>
        <div style={{ marginBottom: '24px' }}>
          <h1 style={{ fontSize: '20pt', fontWeight: 900, color: '#202124', margin: 0 }}>
            SAIL 1-Page Report
          </h1>
          <p style={{ fontSize: '11pt', color: '#5f6368', marginTop: '6px' }}>
            Sales &amp; Stock (Tables A &amp; D) come from the external report you upload below;
            Production &amp; Techno-Economic Parameters (Tables B &amp; C) are computed fresh from
            data already in this app.
          </p>
        </div>

        {/* Download combined report */}
        <div style={cardStyle}>
          <div style={{ fontSize: '11pt', fontWeight: 700, color: '#202124', marginBottom: '12px' }}>
            Download combined report
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '16px', flexWrap: 'wrap' }}>
            <label style={{ fontSize: '11pt', fontWeight: 600 }}>Month</label>
            <input
              type="month"
              value={dlMonth}
              onChange={(e) => setDlMonth(e.target.value)}
              style={selectStyle}
            />
            <button onClick={handleDownload} disabled={!dlMonth || downloading} style={btnStyle(!dlMonth || downloading)}>
              {downloading ? 'Generating…' : '⬇ Download Excel'}
            </button>
          </div>
          {dlError && <div style={{ color: '#c5221f', fontSize: '10.5pt', marginTop: '10px' }}>{dlError}</div>}
        </div>

        {/* Upload / extract Sales + Stock source */}
        <div style={cardStyle}>
          <div style={{ fontSize: '11pt', fontWeight: 700, color: '#202124', marginBottom: '12px' }}>
            Extract Sales &amp; Stock from source report
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '16px', flexWrap: 'wrap' }}>
            <label style={{ fontSize: '11pt', fontWeight: 600 }}>Report month</label>
            <input
              type="month"
              value={srcMonth}
              onChange={(e) => setSrcMonth(e.target.value)}
              style={selectStyle}
            />
            <input
              type="file"
              accept=".xlsx,.xls"
              onChange={(e) => setFile(e.target.files?.[0] || null)}
              style={{ fontSize: '10.5pt' }}
            />
            <button onClick={handleExtract} disabled={!file || extracting} style={btnStyle(!file || extracting)}>
              {extracting ? 'Extracting…' : 'Extract'}
            </button>
          </div>
          <p style={{ fontSize: '9.5pt', color: '#9aa0a6', marginTop: '8px' }}>
            Accepts the same layout as the SAIL &quot;1 page report&quot; workbook (Excel only for now —
            PDF/image sources aren&#39;t supported yet).
          </p>
        </div>

        {error && (
          <div style={{ padding: '14px 18px', border: '1px solid #f28b82', borderRadius: '8px', backgroundColor: '#fce8e6', color: '#c5221f', fontSize: '11pt', marginBottom: '24px' }}>
            {error}
          </div>
        )}

        {preview && (
          <div style={cardStyle}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '14px' }}>
              <div style={{ fontSize: '11pt', fontWeight: 700, color: '#202124' }}>
                Preview — review before saving
              </div>
              <button onClick={handleSave} disabled={saving} style={btnStyle(saving)}>
                {saving ? 'Saving…' : 'Save to database'}
              </button>
            </div>

            {saveResult && (
              <div style={{ padding: '10px 14px', backgroundColor: '#e6f4ea', color: '#137333', borderRadius: '6px', fontSize: '10.5pt', marginBottom: '14px' }}>
                Saved {saveResult.saved_sales} sales values and {saveResult.saved_stock} stock snapshots.
              </div>
            )}

            <div style={{ fontSize: '10.5pt', fontWeight: 700, marginBottom: '8px' }}>Sales</div>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '10pt', marginBottom: '20px' }}>
              <thead>
                <tr style={{ backgroundColor: '#e8f0fe' }}>
                  <th style={{ textAlign: 'left', padding: '6px 10px' }}>Item</th>
                  <th style={{ textAlign: 'right', padding: '6px 10px' }}>ABP</th>
                  <th style={{ textAlign: 'right', padding: '6px 10px' }}>Actual</th>
                  <th style={{ textAlign: 'left', padding: '6px 10px' }}>Status</th>
                </tr>
              </thead>
              <tbody>
                {preview.sales_rows.map((r) => (
                  <tr key={r.item_name} style={{ borderBottom: '1px solid #e8eaed' }}>
                    <td style={{ padding: '5px 10px' }}>{r.item_name}</td>
                    <td style={{ padding: '5px 10px', textAlign: 'right' }}>{fmt(r.month_abp)}</td>
                    <td style={{ padding: '5px 10px', textAlign: 'right' }}>{fmt(r.month_actual)}</td>
                    <td style={{ padding: '5px 10px', color: r.status === 'ok' ? '#137333' : '#c5221f' }}>{r.status}</td>
                  </tr>
                ))}
              </tbody>
            </table>

            <div style={{ fontSize: '10.5pt', fontWeight: 700, marginBottom: '8px' }}>
              Stock ({preview.stock_rows.length} snapshot values)
            </div>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '10pt' }}>
              <thead>
                <tr style={{ backgroundColor: '#e8f0fe' }}>
                  <th style={{ textAlign: 'left', padding: '6px 10px' }}>Item</th>
                  <th style={{ textAlign: 'left', padding: '6px 10px' }}>Snapshot date</th>
                  <th style={{ textAlign: 'right', padding: '6px 10px' }}>Value</th>
                </tr>
              </thead>
              <tbody>
                {preview.stock_rows.filter((r) => r.status === 'ok').map((r, i) => (
                  <tr key={`${r.item_name}-${r.snapshot_date}-${i}`} style={{ borderBottom: '1px solid #e8eaed' }}>
                    <td style={{ padding: '5px 10px' }}>{r.item_name}</td>
                    <td style={{ padding: '5px 10px' }}>{r.snapshot_date}</td>
                    <td style={{ padding: '5px 10px', textAlign: 'right' }}>{fmt(r.value)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </main>
    </div>
  );
}
