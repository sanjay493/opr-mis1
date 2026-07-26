'use client';

import React, { useState, useEffect } from 'react';
import GlobalNavbar from '@/components/GlobalNavbar';

const API = process.env.NEXT_PUBLIC_API_URL || '';

export default function PmixFyPage() {
  const [fys, setFys] = useState([]);
  const [fyStart, setFyStart] = useState(null);
  const [downloading, setDownloading] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    fetch(`${API}/api/production-fys`)
      .then((r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        return r.json();
      })
      .then((d) => {
        setFys(d.fys || []);
        if (d.fys && d.fys.length > 0) setFyStart(d.fys[0].fy_start);
      })
      .catch((e) => setError(`Failed to load financial years: ${e.message}`));
  }, []);

  const handleDownload = async () => {
    if (!fyStart) return;
    setDownloading(true);
    setError(null);
    try {
      const res = await fetch(`${API}/api/pmix-fy-report?fy_start=${fyStart}`);
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        throw new Error(body.detail || `HTTP ${res.status}`);
      }
      const blob = await res.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      const fyLabel = fys.find((fy) => fy.fy_start === fyStart)?.label || String(fyStart);
      a.download = `Pmix_${fyLabel}.xlsx`;
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

  return (
    <div style={{ minHeight: '100vh', backgroundColor: '#ffffff' }}>
      <GlobalNavbar />
      <main style={{ maxWidth: '900px', margin: '0 auto', padding: '32px' }}>
        <div style={{ marginBottom: '24px' }}>
          <h1 style={{ fontSize: '20pt', fontWeight: 900, color: '#202124', margin: 0 }}>
            Pmix Report (Year-wise)
          </h1>
          <p style={{ fontSize: '11pt', color: '#5f6368', marginTop: '6px' }}>
            Month-wise Product Mix Performance for a financial year (Apr&ndash;Mar), with
            quarterly and full-year cumulative columns — built entirely from data already
            in this app.
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
          gap: '16px',
          flexWrap: 'wrap',
        }}>
          <label style={{ fontSize: '11pt', fontWeight: 600, color: '#202124' }}>Financial Year</label>
          <select
            value={fyStart ?? ''}
            onChange={(e) => setFyStart(parseInt(e.target.value, 10))}
            style={{
              padding: '9px 14px',
              fontSize: '11pt',
              border: '1px solid #dadce0',
              borderRadius: '6px',
              backgroundColor: '#ffffff',
              cursor: 'pointer',
              minWidth: '140px',
            }}
          >
            {fys.map((fy) => (
              <option key={fy.fy_start} value={fy.fy_start}>{fy.label}</option>
            ))}
          </select>
          <button
            onClick={handleDownload}
            disabled={!fyStart || downloading}
            style={{
              padding: '10px 28px',
              fontSize: '11pt',
              fontWeight: 700,
              border: 'none',
              borderRadius: '6px',
              cursor: !fyStart || downloading ? 'not-allowed' : 'pointer',
              backgroundColor: !fyStart || downloading ? '#dadce0' : '#1a73e8',
              color: '#ffffff',
            }}
          >
            {downloading ? 'Generating…' : '⬇ Download Excel'}
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
          }}>
            {error}
          </div>
        )}
      </main>
    </div>
  );
}
