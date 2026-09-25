'use client';

import React, { useState, useEffect } from 'react';
import GlobalNavbar from '@/components/GlobalNavbar';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || '';

function fmt(v) {
  if (v == null) return '—';
  return Number(v).toLocaleString('en-IN', { maximumFractionDigits: 0 });
}

const cellBase = {
  padding: '9px 14px',
  fontSize: '10.5pt',
  borderBottom: '1px solid #e8eaed',
  whiteSpace: 'nowrap',
};

const toggleBtn = (active) => ({
  padding: '8px 20px',
  fontSize: '11pt',
  fontWeight: 600,
  border: 'none',
  cursor: 'pointer',
  backgroundColor: active ? '#1a73e8' : 'transparent',
  color: active ? '#ffffff' : '#5f6368',
  transition: 'all 0.15s ease',
});

export default function ProductionTrendPage() {
  const [basis, setBasis] = useState('fy'); // 'fy' | 'cy'
  const [groups, setGroups] = useState([]);
  const [group, setGroup] = useState('sail5');
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    fetch(`${API_BASE}/api/production-trend/groups`)
      .then((r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        return r.json();
      })
      .then((d) => setGroups(d.groups || []))
      .catch((e) => setError(`Failed to load plant groups: ${e.message}`));
  }, []);

  useEffect(() => {
    setLoading(true);
    setError(null);
    fetch(`${API_BASE}/api/production-trend?basis=${basis}&group=${group}`)
      .then((r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        return r.json();
      })
      .then((d) => setData(d))
      .catch((e) => setError(`Failed to load production trend: ${e.message}`))
      .finally(() => setLoading(false));
  }, [basis, group]);

  const items = data?.items || [];
  const years = data?.years || [];

  return (
    <div style={{ height: '100vh', display: 'flex', flexDirection: 'column', backgroundColor: '#ffffff' }}>
      <GlobalNavbar />

      <main style={{
        flex: 1,
        minHeight: 0,
        overflow: 'hidden',
        display: 'flex',
        flexDirection: 'column',
        maxWidth: '1200px',
        margin: '0 auto',
        padding: '32px',
        width: '100%',
        boxSizing: 'border-box',
      }}>
        {/* Header */}
        <div style={{ marginBottom: '24px' }}>
          <h1 style={{ fontSize: '20pt', fontWeight: 900, color: '#202124', margin: 0 }}>
            Hot Metal / Crude Steel / Finished Steel / Saleable Steel — Trend
          </h1>
          <p style={{ fontSize: '11pt', color: '#5f6368', marginTop: '6px' }}>
            Year-wise production for {data?.group_label || '…'}, {basis === 'fy' ? 'financial year' : 'calendar year'} basis (&apos;000 T)
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
          {/* FY / CY toggle */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <label style={{ fontSize: '11pt', fontWeight: 600, color: '#202124' }}>Basis</label>
            <div style={{
              display: 'flex',
              border: '1px solid #dadce0',
              borderRadius: '6px',
              overflow: 'hidden',
              backgroundColor: '#ffffff',
            }}>
              <button onClick={() => setBasis('fy')} style={toggleBtn(basis === 'fy')}>Financial Year</button>
              <button onClick={() => setBasis('cy')} style={toggleBtn(basis === 'cy')}>Calendar Year</button>
            </div>
          </div>

          {/* Plant group selector */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <label style={{ fontSize: '11pt', fontWeight: 600, color: '#202124' }}>Plant</label>
            <select
              value={group}
              onChange={(e) => setGroup(e.target.value)}
              style={{
                padding: '8px 12px',
                fontSize: '11pt',
                border: '1px solid #dadce0',
                borderRadius: '6px',
                backgroundColor: '#ffffff',
                color: '#202124',
                cursor: 'pointer',
                minWidth: '160px',
              }}
            >
              {groups.map((g) => (
                <option key={g.value} value={g.value}>{g.label}</option>
              ))}
            </select>
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

        {!loading && !error && data && years.length === 0 && (
          <div style={{ padding: '40px', textAlign: 'center', color: '#5f6368', fontSize: '12pt' }}>
            No data available for {data.group_label}.
          </div>
        )}

        {/* Table */}
        {data && years.length > 0 && (
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
                    minWidth: '110px',
                    borderRight: '1px solid #dadce0',
                  }}>
                    {basis === 'fy' ? 'FY' : 'Year'}
                  </th>
                  {items.map((it) => (
                    <th key={it.key} style={{
                      ...cellBase,
                      position: 'sticky',
                      top: 0,
                      zIndex: 2,
                      backgroundColor: '#e8f0fe',
                      textAlign: 'right',
                      fontWeight: 700,
                      color: '#174ea6',
                      minWidth: '140px',
                    }}>
                      {it.item_name}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {years.map((row, idx) => {
                  const zebra = idx % 2 === 1 ? '#f8f9fa' : '#ffffff';
                  const isCurrent = idx === 0;
                  return (
                    <tr key={row.year_key}>
                      <td style={{
                        ...cellBase,
                        position: 'sticky',
                        left: 0,
                        zIndex: 1,
                        backgroundColor: isCurrent ? '#e8f0fe' : zebra,
                        fontWeight: 700,
                        color: '#202124',
                        borderRight: '1px solid #dadce0',
                      }}>
                        {row.year_label}
                      </td>
                      {items.map((it) => (
                        <td key={it.key} style={{
                          ...cellBase,
                          textAlign: 'right',
                          backgroundColor: isCurrent ? '#e8f0fe' : zebra,
                          color: row[it.key] == null ? '#bdc1c6' : '#202124',
                          fontVariantNumeric: 'tabular-nums',
                        }}>
                          {fmt(row[it.key])}
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
