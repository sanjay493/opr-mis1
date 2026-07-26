'use client';

import React, { useState, useEffect } from 'react';
import GlobalNavbar from '@/components/GlobalNavbar';

const API = process.env.NEXT_PUBLIC_API_URL || '';

const MONTH_NAMES = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];

function monthLabel(ym) {
  const [y, m] = ym.split('-');
  return `${MONTH_NAMES[parseInt(m, 10) - 1]}'${y.slice(2)}`;
}

// Previous calendar month, e.g. run in July → "2026-06" — this report is
// always for "last month", sent on the 1st of the following month.
function previousMonth() {
  const now = new Date();
  const y = now.getFullYear();
  const m = now.getMonth(); // 0-based, so `m` alone is "last month" (1-based)
  const py = m === 0 ? y - 1 : y;
  const pm = m === 0 ? 12 : m;
  return `${py}-${String(pm).padStart(2, '0')}`;
}

export default function JpcReportPage() {
  const [months, setMonths] = useState([]);
  const [month, setMonth] = useState(previousMonth());
  const [downloading, setDownloading] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    fetch(`${API}/api/production-query-meta`)
      .then((r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        return r.json();
      })
      .then((d) => {
        const list = (d.months || []).slice().sort().reverse();
        setMonths(list);
        if (list.length > 0 && !list.includes(previousMonth())) {
          setMonth(list[0]);
        }
      })
      .catch((e) => setError(`Failed to load available months: ${e.message}`));
  }, []);

  const handleDownload = async () => {
    if (!month) return;
    setDownloading(true);
    setError(null);
    try {
      const res = await fetch(`${API}/api/jpc-report?month=${encodeURIComponent(month)}`);
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        throw new Error(body.detail || `HTTP ${res.status}`);
      }
      const blob = await res.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `JPC_report_${month}.xlsx`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      window.URL.revokeObjectURL(url);
    } catch (e) {
      setError(`Download failed: ${e.message}`);
    } finally {
      setDownloading(false);
    }
  };

  const selectStyle = {
    padding: '9px 14px',
    fontSize: '11pt',
    border: '1px solid #dadce0',
    borderRadius: '6px',
    backgroundColor: '#ffffff',
    color: '#202124',
    cursor: 'pointer',
    minWidth: '140px',
  };

  const noteItems = [
    'MoU / Var / % Ful. columns on the MoU report sheet are always blank — this app has no MoU-target data source.',
    "Some ASP special-steel items (Semis, C.Q., SSP Semis(slabs), VISL Semis) aren't tracked in the database yet and are left blank.",
    'A few plant mill-split rows (e.g. DSP Med Structurals (SM), ISP TMT Coils(WRM), RSP New HR Plate/Coils) share their DB source with another row or have none yet — blank until a dedicated source is extracted.',
  ];

  return (
    <div style={{ minHeight: '100vh', backgroundColor: '#ffffff' }}>
      <GlobalNavbar />

      <main style={{
        maxWidth: '900px',
        margin: '0 auto',
        padding: '32px',
      }}>
        <div style={{ marginBottom: '24px' }}>
          <h1 style={{ fontSize: '20pt', fontWeight: 900, color: '#202124', margin: 0 }}>
            JPC Monthly Report
          </h1>
          <p style={{ fontSize: '11pt', color: '#5f6368', marginTop: '6px' }}>
            Pick the reporting month — the workbook shows that month&#39;s Actual vs the CPLY
            (same month, prior year) Actual, in the JPC report format (Pmix report, Special
            Steel plants, Sinter, MoU report sheets).
          </p>
        </div>

        <div style={{
          padding: '20px 24px',
          border: '1px solid #dadce0',
          borderRadius: '8px',
          backgroundColor: '#f8f9fa',
          marginBottom: '24px',
          display: 'flex',
          alignItems: 'center',
          gap: '20px',
          flexWrap: 'wrap',
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <label style={{ fontSize: '11pt', fontWeight: 600, color: '#202124' }}>Month</label>
            <select value={month} onChange={(e) => setMonth(e.target.value)} style={selectStyle}>
              {!months.includes(month) && month && (
                <option value={month}>{monthLabel(month)}</option>
              )}
              {months.map((m) => (
                <option key={m} value={m}>{monthLabel(m)}</option>
              ))}
            </select>
          </div>

          <button
            onClick={handleDownload}
            disabled={!month || downloading}
            style={{
              padding: '10px 28px',
              fontSize: '11pt',
              fontWeight: 700,
              border: 'none',
              borderRadius: '6px',
              cursor: !month || downloading ? 'not-allowed' : 'pointer',
              backgroundColor: !month || downloading ? '#dadce0' : '#1a73e8',
              color: '#ffffff',
              transition: 'all 0.15s ease',
            }}
          >
            {downloading ? 'Generating…' : 'Download Excel'}
          </button>
        </div>

        {error && (
          <div style={{
            padding: '14px 18px',
            border: '1px solid #f28b82',
            borderRadius: '8px',
            backgroundColor: '#fce8e6',
            color: '#c5221f',
            fontSize: '11pt',
            marginBottom: '24px',
          }}>
            {error}
          </div>
        )}

        <div style={{
          padding: '16px 20px',
          border: '1px solid #dadce0',
          borderRadius: '8px',
          backgroundColor: '#fffbf0',
        }}>
          <div style={{ fontSize: '10.5pt', fontWeight: 700, color: '#202124', marginBottom: '8px' }}>
            Known gaps in this report
          </div>
          <ul style={{ margin: 0, paddingLeft: '20px' }}>
            {noteItems.map((n, i) => (
              <li key={i} style={{ fontSize: '10pt', color: '#5f6368', marginBottom: '4px' }}>{n}</li>
            ))}
          </ul>
        </div>
      </main>
    </div>
  );
}
