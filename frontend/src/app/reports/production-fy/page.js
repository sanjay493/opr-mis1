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
  return Number(v).toLocaleString('en-IN', { maximumFractionDigits: 3 });
}

// Items expressed as a daily rate — a yearly sum is meaningless, show average instead.
// COB# battery items (e.g. "COB#1-8", "COB#6") are oven-pushing counts in nos/day,
// same unit family as "Oven Pushing (nos/day)", just without the unit in the name.
function isRateItem(name) {
  return /\/day|\/d\)/i.test(name) || /^COB#/i.test(name);
}

function rowTotal(itemName, values, months) {
  const nums = months.map((m) => values[m]).filter((v) => v != null);
  if (nums.length === 0) return null;
  const sum = nums.reduce((a, b) => a + b, 0);
  return isRateItem(itemName) ? sum / nums.length : sum;
}

const cellBase = {
  padding: '7px 10px',
  fontSize: '10pt',
  borderBottom: '1px solid #e8eaed',
  whiteSpace: 'nowrap',
};

export default function ProductionFYPage() {
  const [fys, setFys] = useState([]);
  const [fyStart, setFyStart] = useState(null);
  const [mode, setMode] = useState('actual'); // 'actual' | 'plan'
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    fetch(`${API_BASE}/api/production-fys`)
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
    fetch(`${API_BASE}/api/production-fy?fy_start=${fyStart}`)
      .then((r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        return r.json();
      })
      .then((d) => setData(d))
      .catch((e) => setError(`Failed to load production data: ${e.message}`))
      .finally(() => setLoading(false));
  }, [fyStart]);

  const months = data?.months || [];

  // In Plan view, hide plants that have no plan rows at all for this FY
  const visiblePlants = (data?.plants || [])
    .map((p) => ({
      ...p,
      items: p.items.filter((it) =>
        months.some((m) => it[mode][m] != null)
      ),
    }))
    .filter((p) => p.items.length > 0);

  return (
    <div style={{ height: '100vh', display: 'flex', flexDirection: 'column', backgroundColor: '#ffffff' }}>
      <GlobalNavbar />

      <main style={{
        flex: 1,
        overflow: 'auto',
        maxWidth: '1600px',
        margin: '0 auto',
        padding: '32px',
        width: '100%',
        boxSizing: 'border-box',
      }}>
        {/* Header */}
        <div style={{ marginBottom: '24px' }}>
          <h1 style={{ fontSize: '20pt', fontWeight: 900, color: '#202124', margin: 0 }}>
            Month-wise Production {mode === 'actual' ? '(Actual)' : '(Plan)'}
          </h1>
          <p style={{ fontSize: '11pt', color: '#5f6368', marginTop: '6px' }}>
            All plants, all items — monthly {mode} figures for the selected financial year ('000 T unless stated)
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

          {/* Actual / Plan toggle */}
          <div style={{
            display: 'flex',
            border: '1px solid #dadce0',
            borderRadius: '6px',
            overflow: 'hidden',
            backgroundColor: '#ffffff',
          }}>
            {['actual', 'plan'].map((m) => (
              <button
                key={m}
                onClick={() => setMode(m)}
                style={{
                  padding: '8px 22px',
                  fontSize: '11pt',
                  fontWeight: 600,
                  border: 'none',
                  cursor: 'pointer',
                  backgroundColor: mode === m ? '#1a73e8' : 'transparent',
                  color: mode === m ? '#ffffff' : '#5f6368',
                  transition: 'all 0.15s ease',
                }}
              >
                {m === 'actual' ? 'Actual' : 'Plan'}
              </button>
            ))}
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

        {!loading && !error && data && visiblePlants.length === 0 && (
          <div style={{ padding: '40px', textAlign: 'center', color: '#5f6368', fontSize: '12pt' }}>
            No {mode} data available for FY {data.fy_label}.
          </div>
        )}

        {/* Table */}
        {data && visiblePlants.length > 0 && (
          <div style={{
            border: '1px solid #dadce0',
            borderRadius: '8px',
            overflowX: 'auto',
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
                    Item
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
                {visiblePlants.map((plant) => (
                  <React.Fragment key={plant.plant}>
                    {/* Plant section header */}
                    <tr>
                      <td colSpan={months.length + 2} style={{
                        ...cellBase,
                        position: 'sticky',
                        left: 0,
                        backgroundColor: '#1a73e8',
                        color: '#ffffff',
                        fontWeight: 800,
                        fontSize: '11pt',
                        letterSpacing: '0.03em',
                      }}>
                        {plant.plant}
                      </td>
                    </tr>
                    {plant.items.map((item, idx) => {
                      const values = item[mode];
                      const total = rowTotal(item.item_name, values, months);
                      const zebra = idx % 2 === 1 ? '#f8f9fa' : '#ffffff';
                      return (
                        <tr key={item.item_name}>
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
                            {item.item_name}
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
                            {fmt(total)}{total != null && isRateItem(item.item_name) ? ' (avg)' : ''}
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
