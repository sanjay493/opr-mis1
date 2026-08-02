'use client';

import React, { useState } from 'react';
import GlobalNavbar from '@/components/GlobalNavbar';

const API = process.env.NEXT_PUBLIC_API_URL || '';

export default function FinishedSteelReportPage() {
  const [downloading, setDownloading] = useState(false);
  const [error, setError] = useState(null);

  const handleDownload = async () => {
    setDownloading(true);
    setError(null);
    try {
      const res = await fetch(`${API}/api/finished-steel-report`);
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        throw new Error(body.detail || `HTTP ${res.status}`);
      }
      const blob = await res.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = 'finished_steel_month_plant_wise.csv';
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
            Finished Steel — Month-wise, Unit-wise
          </h1>
          <p style={{ fontSize: '11pt', color: '#5f6368', marginTop: '6px' }}>
            One row per report month, one column per plant (plus the SAIL total), from
            production_table&#39;s &lsquo;Finished Steel&rsquo; item — full history, no month picker needed.
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
          <button
            onClick={handleDownload}
            disabled={downloading}
            style={{
              padding: '10px 28px',
              fontSize: '11pt',
              fontWeight: 700,
              border: 'none',
              borderRadius: '6px',
              cursor: downloading ? 'not-allowed' : 'pointer',
              backgroundColor: downloading ? '#dadce0' : '#1a73e8',
              color: '#ffffff',
              transition: 'all 0.15s ease',
            }}
          >
            {downloading ? 'Generating…' : '⬇ Download CSV'}
          </button>
          <span style={{ fontSize: '9.5pt', color: '#9aa0a6' }}>
            Unit: &lsquo;000 T. Blank cells mean no figure recorded for that plant that month.
          </span>
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
