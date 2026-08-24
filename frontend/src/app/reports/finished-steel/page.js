'use client';

import React, { useState, useEffect } from 'react';
import GlobalNavbar from '@/components/GlobalNavbar';

const API = process.env.NEXT_PUBLIC_API_URL || '';

const MONTH_NAMES = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];

function monthLabel(ym) {
  // "2026-04" -> "Apr'26"
  const [y, m] = ym.split('-');
  return `${MONTH_NAMES[parseInt(m, 10) - 1]}'${y.slice(2)}`;
}

function fmt(v) {
  if (v == null) return '—';
  return Number(v).toLocaleString('en-IN', { maximumFractionDigits: 3 });
}

const cellBase = {
  padding: '6px 10px',
  fontSize: '10pt',
  borderBottom: '1px solid #e8eaed',
  whiteSpace: 'nowrap',
};

const HEAD = {
  ...cellBase,
  position: 'sticky',
  top: 0,
  zIndex: 2,
  backgroundColor: '#e8f0fe',
  textAlign: 'center',
  fontWeight: 700,
  color: '#174ea6',
};

async function downloadCsv(url, fallbackName) {
  const res = await fetch(url);
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail || `HTTP ${res.status}`);
  }
  const disposition = res.headers.get('Content-Disposition') || '';
  const match = disposition.match(/filename="([^"]+)"/);
  const filename = match ? match[1] : fallbackName;
  const blob = await res.blob();
  const objUrl = window.URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = objUrl;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  window.URL.revokeObjectURL(objUrl);
}

export default function FinishedSteelReportPage() {
  const [fys, setFys] = useState([]);
  const [fyStart, setFyStart] = useState(null);
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [downloadingAll, setDownloadingAll] = useState(false);
  const [downloadingFy, setDownloadingFy] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    fetch(`${API}/api/finished-steel-fys`)
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
    fetch(`${API}/api/finished-steel-report/fy?fy_start=${fyStart}`)
      .then((r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        return r.json();
      })
      .then((d) => setData(d))
      .catch((e) => setError(`Failed to load Finished Steel data: ${e.message}`))
      .finally(() => setLoading(false));
  }, [fyStart]);

  const handleDownloadAll = async () => {
    setDownloadingAll(true);
    setError(null);
    try {
      await downloadCsv(`${API}/api/finished-steel-report`, 'finished_steel_month_plant_wise.csv');
    } catch (e) {
      setError(`Download failed: ${e.message}`);
    } finally {
      setDownloadingAll(false);
    }
  };

  const handleDownloadFy = async () => {
    if (fyStart == null) return;
    setDownloadingFy(true);
    setError(null);
    try {
      await downloadCsv(`${API}/api/finished-steel-report?fy_start=${fyStart}`, `finished_steel_FY${fyStart}.csv`);
    } catch (e) {
      setError(`Download failed: ${e.message}`);
    } finally {
      setDownloadingFy(false);
    }
  };

  const months = data?.months || [];
  const plants = data?.plants || [];
  const rows = data?.rows || {};

  const btnStyle = (disabled, primary = true) => ({
    padding: '9px 22px',
    fontSize: '11pt',
    fontWeight: 700,
    border: primary ? 'none' : '1px solid #1a73e8',
    borderRadius: '6px',
    cursor: disabled ? 'not-allowed' : 'pointer',
    backgroundColor: disabled ? '#dadce0' : (primary ? '#1a73e8' : '#ffffff'),
    color: disabled ? '#5f6368' : (primary ? '#ffffff' : '#1a73e8'),
  });

  return (
    <div style={{ height: '100vh', display: 'flex', flexDirection: 'column', backgroundColor: '#ffffff' }}>
      <GlobalNavbar />

      <main style={{
        flex: 1, minHeight: 0, overflow: 'hidden', display: 'flex', flexDirection: 'column',
        maxWidth: '1400px', margin: '0 auto', padding: '32px', width: '100%', boxSizing: 'border-box',
      }}>
        <div style={{ marginBottom: '24px' }}>
          <h1 style={{ fontSize: '20pt', fontWeight: 900, color: '#202124', margin: 0 }}>
            Finished Steel — Month-wise, Plant-wise
          </h1>
          <p style={{ fontSize: '11pt', color: '#5f6368', marginTop: '6px' }}>
            One row per month, one column per plant (plus the SAIL total), from production_table&#39;s
            &lsquo;Finished Steel&rsquo; item. Unit: &lsquo;000 T. Blank cells mean no figure recorded for
            that plant that month.
          </p>
        </div>

        {/* Controls */}
        <div style={{
          display: 'flex', alignItems: 'center', gap: '20px', flexWrap: 'wrap',
          padding: '16px 20px', border: '1px solid #dadce0', borderRadius: '8px',
          backgroundColor: '#f8f9fa', marginBottom: '24px',
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <label style={{ fontSize: '11pt', fontWeight: 600, color: '#202124' }}>Financial Year</label>
            <select
              value={fyStart ?? ''}
              onChange={(e) => setFyStart(parseInt(e.target.value, 10))}
              style={{
                padding: '8px 12px', fontSize: '11pt', border: '1px solid #dadce0',
                borderRadius: '6px', backgroundColor: '#ffffff', color: '#202124',
                cursor: 'pointer', minWidth: '130px',
              }}
            >
              {fys.map((fy) => (
                <option key={fy.fy_start} value={fy.fy_start}>{fy.label}</option>
              ))}
            </select>
          </div>

          <button onClick={handleDownloadFy} disabled={downloadingFy || fyStart == null} style={btnStyle(downloadingFy || fyStart == null)}>
            {downloadingFy ? 'Generating…' : `⬇ Download FY${fyStart != null ? ` ${fys.find((f) => f.fy_start === fyStart)?.label || ''}` : ''}`}
          </button>
          <button onClick={handleDownloadAll} disabled={downloadingAll} style={btnStyle(downloadingAll, false)}>
            {downloadingAll ? 'Generating…' : '⬇ Download All (full history)'}
          </button>

          {loading && <span style={{ fontSize: '10.5pt', color: '#5f6368' }}>Loading…</span>}
        </div>

        {error && (
          <div style={{
            padding: '14px 18px', border: '1px solid #f28b82', borderRadius: '8px',
            backgroundColor: '#fce8e6', color: '#c5221f', fontSize: '11pt', marginBottom: '24px',
          }}>
            {error}
          </div>
        )}

        {!loading && !error && data && months.length === 0 && (
          <div style={{ padding: '40px', textAlign: 'center', color: '#5f6368', fontSize: '12pt' }}>
            No Finished Steel data available for FY {data.fy_label}.
          </div>
        )}

        {data && months.length > 0 && (
          <div style={{
            border: '1px solid #dadce0', borderRadius: '8px', overflow: 'auto', flex: 1, minHeight: 0,
          }}>
            <table style={{ borderCollapse: 'separate', borderSpacing: 0, width: '100%' }}>
              <thead>
                <tr>
                  <th style={{ ...HEAD, left: 0, zIndex: 3, textAlign: 'left', minWidth: '90px', borderRight: '1px solid #dadce0' }}>
                    Month
                  </th>
                  {plants.map((p) => (
                    <th key={p} style={{ ...HEAD, minWidth: '90px', borderLeft: '1px solid #dadce0' }}>
                      {p}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {months.map((m, idx) => {
                  const zebra = idx % 2 === 1 ? '#f8f9fa' : '#ffffff';
                  const byPlant = rows[m] || {};
                  return (
                    <tr key={m}>
                      <td style={{
                        ...cellBase, position: 'sticky', left: 0, zIndex: 1,
                        backgroundColor: zebra, fontWeight: 600, borderRight: '1px solid #dadce0',
                      }}>
                        {monthLabel(m)}
                      </td>
                      {plants.map((p) => (
                        <td key={p} style={{
                          ...cellBase, textAlign: 'right', backgroundColor: zebra,
                          fontWeight: p === 'SAIL' ? 700 : 400,
                          color: byPlant[p] == null ? '#bdc1c6' : (p === 'SAIL' ? '#174ea6' : '#202124'),
                          fontVariantNumeric: 'tabular-nums', borderLeft: '1px solid #dadce0',
                        }}>
                          {fmt(byPlant[p])}
                        </td>
                      ))}
                    </tr>
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
