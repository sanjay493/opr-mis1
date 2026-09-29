'use client';

import React, { useState, useEffect } from 'react';
import GlobalNavbar from '@/components/GlobalNavbar';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || '';

const MONTH_NAMES = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];

function monthLabel(ym) {
  // "2026-04" -> "Apr'26"
  const [y, m] = ym.split('-');
  return `${MONTH_NAMES[parseInt(m, 10) - 1]}'${y.slice(2)}`;
}

function fmt(v) {
  if (v == null) return '—';
  return Number(v).toLocaleString('en-IN', { maximumFractionDigits: 1 });
}

function rowTotal(values, months) {
  const nums = months.map((m) => values[m]).filter((v) => v != null);
  if (nums.length === 0) return null;
  return nums.reduce((a, b) => a + b, 0);
}

const cellBase = {
  padding: '7px 10px',
  fontSize: '10pt',
  borderBottom: '1px solid #e8eaed',
  whiteSpace: 'nowrap',
};

const ROW_LABELS = [
  { key: 'order', label: 'Order Qty' },
  { key: 'actual', label: 'Actual Despatch' },
];

export default function SpecialSteelFYPage() {
  const [fys, setFys] = useState([]);
  const [fyStart, setFyStart] = useState(null);
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [downloading, setDownloading] = useState(null); // 'excel' | 'pdf' | null

  useEffect(() => {
    fetch(`${API_BASE}/api/special-steel-fys`)
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

  useEffect(() => {
    if (fyStart == null) return;
    setLoading(true);
    setError(null);
    fetch(`${API_BASE}/api/special-steel-fy?fy_start=${fyStart}`)
      .then((r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        return r.json();
      })
      .then((d) => setData(d))
      .catch((e) => setError(`Failed to load special steel data: ${e.message}`))
      .finally(() => setLoading(false));
  }, [fyStart]);

  const handleDownload = async (kind) => {
    if (!fyStart) return;
    setDownloading(kind);
    setError(null);
    try {
      const res = await fetch(`${API_BASE}/api/special-steel-fy/${kind}?fy_start=${fyStart}`);
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        throw new Error(body.detail || `HTTP ${res.status}`);
      }
      const blob = await res.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      const fyLabel = fys.find((fy) => fy.fy_start === fyStart)?.label || String(fyStart);
      a.download = `SpecialSteel_${fyLabel}.${kind === 'excel' ? 'xlsx' : 'pdf'}`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      window.URL.revokeObjectURL(url);
    } catch (e) {
      setError(`Download failed: ${e.message}`);
    } finally {
      setDownloading(null);
    }
  };

  const months = data?.months || [];
  const plants = data?.plants || [];

  return (
    <div style={{ height: '100vh', display: 'flex', flexDirection: 'column', backgroundColor: '#ffffff' }}>
      <GlobalNavbar />

      <main style={{
        flex: 1,
        minHeight: 0,
        overflow: 'hidden',
        display: 'flex',
        flexDirection: 'column',
        maxWidth: '1600px',
        margin: '0 auto',
        padding: '32px',
        width: '100%',
        boxSizing: 'border-box',
      }}>
        {/* Header */}
        <div style={{ marginBottom: '24px' }}>
          <h1 style={{ fontSize: '20pt', fontWeight: 900, color: '#202124', margin: 0 }}>
            Special Steel — Order &amp; Actual Despatch
          </h1>
          <p style={{ fontSize: '11pt', color: '#5f6368', marginTop: '6px' }}>
            Month-wise, plant-wise Order Qty and Actual Despatch for the selected financial year (T)
          </p>
        </div>

        {/* Controls */}
        <div style={{
          display: 'flex',
          alignItems: 'center',
          gap: '24px',
          flexWrap: 'wrap',
          padding: '16px 20px',
          border: '1px solid #dadce0',
          borderRadius: '8px',
          backgroundColor: '#f8f9fa',
          marginBottom: '24px',
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <label style={{ fontSize: '11pt', fontWeight: 600, color: '#202124' }}>Financial Year</label>
            <select
              value={fyStart ?? ''}
              onChange={(e) => setFyStart(parseInt(e.target.value, 10))}
              style={{
                padding: '8px 12px',
                fontSize: '11pt',
                border: '1px solid #dadce0',
                borderRadius: '6px',
                backgroundColor: '#ffffff',
                color: '#202124',
                cursor: 'pointer',
                minWidth: '130px',
              }}
            >
              {fys.map((fy) => (
                <option key={fy.fy_start} value={fy.fy_start}>{fy.label}</option>
              ))}
            </select>
          </div>

          {/* Download buttons */}
          <div style={{ display: 'flex', gap: '10px', marginLeft: 'auto' }}>
            <button
              onClick={() => handleDownload('excel')}
              disabled={!fyStart || downloading !== null}
              style={{
                padding: '8px 18px',
                fontSize: '10.5pt',
                fontWeight: 700,
                border: '1px solid #1a73e8',
                borderRadius: '6px',
                cursor: !fyStart || downloading !== null ? 'not-allowed' : 'pointer',
                backgroundColor: '#ffffff',
                color: downloading !== null ? '#9aa0a6' : '#1a73e8',
                transition: 'all 0.15s ease',
              }}
            >
              {downloading === 'excel' ? 'Generating…' : '⬇ Excel'}
            </button>
            <button
              onClick={() => handleDownload('pdf')}
              disabled={!fyStart || downloading !== null}
              style={{
                padding: '8px 18px',
                fontSize: '10.5pt',
                fontWeight: 700,
                border: '1px solid #1a73e8',
                borderRadius: '6px',
                cursor: !fyStart || downloading !== null ? 'not-allowed' : 'pointer',
                backgroundColor: '#ffffff',
                color: downloading !== null ? '#9aa0a6' : '#1a73e8',
                transition: 'all 0.15s ease',
              }}
            >
              {downloading === 'pdf' ? 'Generating…' : '⬇ PDF'}
            </button>
          </div>

          {loading && <span style={{ fontSize: '10.5pt', color: '#5f6368' }}>Loading…</span>}
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

        {!loading && !error && data && plants.length === 0 && (
          <div style={{ padding: '40px', textAlign: 'center', color: '#5f6368', fontSize: '12pt' }}>
            No Special Steel data available for FY {data.fy_label}.
          </div>
        )}

        {/* Table */}
        {data && plants.length > 0 && (
          <div style={{
            border: '1px solid #dadce0',
            borderRadius: '8px',
            overflow: 'auto',
            flex: 1,
            minHeight: 0,
          }}>
            <table style={{ borderCollapse: 'separate', borderSpacing: 0, width: '100%' }}>
              <thead>
                <tr>
                  <th style={{
                    ...cellBase,
                    position: 'sticky',
                    top: 0,
                    left: 0,
                    zIndex: 3,
                    backgroundColor: '#e8f0fe',
                    textAlign: 'left',
                    fontWeight: 700,
                    color: '#174ea6',
                    minWidth: '200px',
                    borderRight: '1px solid #dadce0',
                  }}>
                    Plant
                  </th>
                  {months.map((m) => (
                    <th key={m} style={{
                      ...cellBase,
                      position: 'sticky',
                      top: 0,
                      zIndex: 2,
                      backgroundColor: '#e8f0fe',
                      textAlign: 'right',
                      fontWeight: 700,
                      color: '#174ea6',
                      minWidth: '76px',
                    }}>
                      {monthLabel(m)}
                    </th>
                  ))}
                  <th style={{
                    ...cellBase,
                    position: 'sticky',
                    top: 0,
                    zIndex: 2,
                    backgroundColor: '#e8f0fe',
                    textAlign: 'right',
                    fontWeight: 700,
                    color: '#174ea6',
                    minWidth: '90px',
                    borderLeft: '1px solid #dadce0',
                  }}>
                    Total
                  </th>
                </tr>
              </thead>
              <tbody>
                {plants.map((plant) => {
                  const isSail = plant.plant === 'SAIL';
                  return (
                    <React.Fragment key={plant.plant}>
                      {/* Plant section header */}
                      <tr>
                        <td colSpan={months.length + 2} style={{
                          ...cellBase,
                          position: 'sticky',
                          left: 0,
                          backgroundColor: isSail ? '#174ea6' : '#1a73e8',
                          color: '#ffffff',
                          fontWeight: 800,
                          fontSize: '11pt',
                          letterSpacing: '0.03em',
                        }}>
                          {plant.plant}
                        </td>
                      </tr>
                      {ROW_LABELS.map(({ key, label }, idx) => {
                        const values = plant[key];
                        const total = rowTotal(values, months);
                        const zebra = idx % 2 === 1 ? '#f8f9fa' : '#ffffff';
                        return (
                          <tr key={key}>
                            <td style={{
                              ...cellBase,
                              position: 'sticky',
                              left: 0,
                              zIndex: 1,
                              backgroundColor: zebra,
                              fontWeight: 600,
                              color: '#202124',
                              borderRight: '1px solid #dadce0',
                            }}>
                              {label}
                            </td>
                            {months.map((m) => (
                              <td key={m} style={{
                                ...cellBase,
                                textAlign: 'right',
                                backgroundColor: zebra,
                                color: values[m] == null ? '#bdc1c6' : '#202124',
                                fontVariantNumeric: 'tabular-nums',
                              }}>
                                {fmt(values[m])}
                              </td>
                            ))}
                            <td style={{
                              ...cellBase,
                              textAlign: 'right',
                              backgroundColor: zebra,
                              fontWeight: 700,
                              color: total == null ? '#bdc1c6' : '#174ea6',
                              fontVariantNumeric: 'tabular-nums',
                              borderLeft: '1px solid #dadce0',
                            }}>
                              {fmt(total)}
                            </td>
                          </tr>
                        );
                      })}
                    </React.Fragment>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </main>
    </div>
  );
}
