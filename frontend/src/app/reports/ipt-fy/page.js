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

export default function IptFYPage() {
  const [fys, setFys] = useState([]);
  const [fyStart, setFyStart] = useState(null);
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    fetch(`${API_BASE}/api/ipt-fys`)
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
    fetch(`${API_BASE}/api/ipt-fy?fy_start=${fyStart}`)
      .then((r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        return r.json();
      })
      .then((d) => setData(d))
      .catch((e) => setError(`Failed to load IPT data: ${e.message}`))
      .finally(() => setLoading(false));
  }, [fyStart]);

  const months = data?.months || [];
  const sections = data?.sections || [];

  return (
    <div style={{ height: '100vh', display: 'flex', flexDirection: 'column', backgroundColor: '#ffffff' }}>
      <GlobalNavbar />

      <main style={{
        flex: 1,
        minHeight: 0,
        overflow: 'hidden',
        display: 'flex',
        flexDirection: 'column',
        maxWidth: '1800px',
        margin: '0 auto',
        padding: '32px',
        width: '100%',
        boxSizing: 'border-box',
      }}>
        {/* Header */}
        <div style={{ marginBottom: '24px' }}>
          <h1 style={{ fontSize: '20pt', fontWeight: 900, color: '#202124', margin: 0 }}>
            IPT — Month-wise Plan &amp; Actual (FY)
          </h1>
          <p style={{ fontSize: '11pt', color: '#5f6368', marginTop: '6px' }}>
            Month-wise Plan and Actual for every item and From→To route, for the selected financial year
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

        {!loading && !error && data && sections.length === 0 && (
          <div style={{ padding: '40px', textAlign: 'center', color: '#5f6368', fontSize: '12pt' }}>
            No IPT data available for FY {data.fy_label}.
          </div>
        )}

        {/* Table */}
        {data && sections.length > 0 && (
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
                  <th rowSpan={2} style={{
                    ...HEAD, left: 0, zIndex: 3, textAlign: 'left', minWidth: '160px',
                    borderRight: '1px solid #dadce0',
                  }}>
                    Item
                  </th>
                  <th rowSpan={2} style={{
                    ...HEAD, left: 160, zIndex: 3, minWidth: '64px',
                    borderRight: '1px solid #dadce0',
                  }}>
                    From
                  </th>
                  <th rowSpan={2} style={{
                    ...HEAD, left: 224, zIndex: 3, minWidth: '64px',
                    borderRight: '1px solid #dadce0',
                  }}>
                    To
                  </th>
                  <th rowSpan={2} style={{
                    ...HEAD, left: 288, zIndex: 3, minWidth: '52px',
                    borderRight: '1px solid #dadce0',
                  }}>
                    Unit
                  </th>
                  {months.map((m) => (
                    <th key={m} colSpan={2} style={{ ...HEAD, borderLeft: '1px solid #dadce0' }}>
                      {monthLabel(m)}
                    </th>
                  ))}
                  <th colSpan={2} style={{ ...HEAD, borderLeft: '1px solid #dadce0' }}>
                    Total
                  </th>
                </tr>
                <tr>
                  {months.map((m) => (
                    <React.Fragment key={m}>
                      <th style={{ ...HEAD, top: 33, minWidth: '68px', borderLeft: '1px solid #dadce0' }}>Plan</th>
                      <th style={{ ...HEAD, top: 33, minWidth: '68px' }}>Actual</th>
                    </React.Fragment>
                  ))}
                  <th style={{ ...HEAD, top: 33, minWidth: '76px', borderLeft: '1px solid #dadce0' }}>Plan</th>
                  <th style={{ ...HEAD, top: 33, minWidth: '76px' }}>Actual</th>
                </tr>
              </thead>
              <tbody>
                {sections.map((section) => (
                  <React.Fragment key={section.item}>
                    {/* Item section header */}
                    <tr>
                      <td colSpan={4 + months.length * 2 + 2} style={{
                        ...cellBase,
                        position: 'sticky',
                        left: 0,
                        backgroundColor: '#174ea6',
                        color: '#ffffff',
                        fontWeight: 800,
                        fontSize: '11pt',
                        letterSpacing: '0.03em',
                      }}>
                        {section.item}
                      </td>
                    </tr>
                    {section.routes.map((route, idx) => {
                      const planTotal = rowTotal(route.plan, months);
                      const actualTotal = rowTotal(route.actual, months);
                      const zebra = idx % 2 === 1 ? '#f8f9fa' : '#ffffff';
                      return (
                        <tr key={`${route.from}|${route.to}`}>
                          <td style={{
                            ...cellBase, position: 'sticky', left: 0, zIndex: 1,
                            backgroundColor: zebra, borderRight: '1px solid #dadce0',
                          }} />
                          <td style={{
                            ...cellBase, position: 'sticky', left: 160, zIndex: 1,
                            backgroundColor: zebra, textAlign: 'center', fontWeight: 600,
                            borderRight: '1px solid #dadce0',
                          }}>
                            {route.from}
                          </td>
                          <td style={{
                            ...cellBase, position: 'sticky', left: 224, zIndex: 1,
                            backgroundColor: zebra, textAlign: 'center', fontWeight: 600,
                            borderRight: '1px solid #dadce0',
                          }}>
                            {route.to}
                          </td>
                          <td style={{
                            ...cellBase, position: 'sticky', left: 288, zIndex: 1,
                            backgroundColor: zebra, textAlign: 'center', color: '#5f6368',
                            borderRight: '1px solid #dadce0',
                          }}>
                            {route.unit}
                          </td>
                          {months.map((m) => (
                            <React.Fragment key={m}>
                              <td style={{
                                ...cellBase, textAlign: 'right', backgroundColor: zebra,
                                color: route.plan[m] == null ? '#bdc1c6' : '#202124',
                                fontVariantNumeric: 'tabular-nums', borderLeft: '1px solid #dadce0',
                              }}>
                                {fmt(route.plan[m])}
                              </td>
                              <td style={{
                                ...cellBase, textAlign: 'right', backgroundColor: zebra,
                                color: route.actual[m] == null ? '#bdc1c6' : '#202124',
                                fontVariantNumeric: 'tabular-nums',
                              }}>
                                {fmt(route.actual[m])}
                              </td>
                            </React.Fragment>
                          ))}
                          <td style={{
                            ...cellBase, textAlign: 'right', backgroundColor: zebra,
                            fontWeight: 700, color: planTotal == null ? '#bdc1c6' : '#174ea6',
                            fontVariantNumeric: 'tabular-nums', borderLeft: '1px solid #dadce0',
                          }}>
                            {fmt(planTotal)}
                          </td>
                          <td style={{
                            ...cellBase, textAlign: 'right', backgroundColor: zebra,
                            fontWeight: 700, color: actualTotal == null ? '#bdc1c6' : '#174ea6',
                            fontVariantNumeric: 'tabular-nums',
                          }}>
                            {fmt(actualTotal)}
                          </td>
                        </tr>
                      );
                    })}
                  </React.Fragment>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </main>
    </div>
  );
}
