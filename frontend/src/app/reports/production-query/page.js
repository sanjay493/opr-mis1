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

// Items expressed as a daily rate — a cumulative sum is meaningless, show average instead.
// COB# battery items (e.g. "COB#1-8", "COB#6") are oven-pushing counts in nos/day.
function isRateItem(name) {
  return /\/day|\/d\)/i.test(name) || /^COB#/i.test(name);
}

function cumulative(itemName, values, months) {
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

const headCell = {
  ...cellBase,
  position: 'sticky',
  top: 0,
  zIndex: 2,
  backgroundColor: '#e8f0fe',
  fontWeight: 700,
  color: '#174ea6',
};

export default function ProductionQueryPage() {
  const [meta, setMeta] = useState(null);            // { plants: [], months: [] (newest first) }
  const [selectedPlants, setSelectedPlants] = useState([]);
  const [itemsByPlant, setItemsByPlant] = useState({});   // { plant: [item, ...] }
  const [selectedUnits, setSelectedUnits] = useState([]); // [{plant, item}] in click order
  const [startMonth, setStartMonth] = useState('');
  const [endMonth, setEndMonth] = useState('');
  const [data, setData] = useState(null);            // { months, series }
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  // Load plants + available months
  useEffect(() => {
    fetch(`${API_BASE}/api/production-query-meta`)
      .then((r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        return r.json();
      })
      .then((d) => {
        setMeta(d);
        const months = d.months || [];
        if (months.length > 0) {
          const latest = months[0];
          setEndMonth(latest);
          // Default start = April of the latest month's financial year
          const [y, m] = [parseInt(latest.slice(0, 4), 10), parseInt(latest.slice(5, 7), 10)];
          const fyStart = m >= 4 ? y : y - 1;
          const aprilOfFy = `${fyStart}-04`;
          setStartMonth(months.includes(aprilOfFy) ? aprilOfFy : months[months.length - 1]);
        }
      })
      .catch((e) => setError(`Failed to load plants/months: ${e.message}`));
  }, []);

  // Load unit lists whenever the plant selection changes (cache is kept for
  // deselected plants; rendering only reads entries for selected plants)
  useEffect(() => {
    if (selectedPlants.length === 0) return;
    fetch(`${API_BASE}/api/production-query-items?plants=${encodeURIComponent(selectedPlants.join(','))}`)
      .then((r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        return r.json();
      })
      .then((d) => setItemsByPlant((prev) => ({ ...prev, ...(d.items || {}) })))
      .catch((e) => setError(`Failed to load units: ${e.message}`));
  }, [selectedPlants]);

  const togglePlant = (plant) => {
    setSelectedPlants((prev) => {
      const next = prev.includes(plant) ? prev.filter((p) => p !== plant) : [...prev, plant];
      if (prev.includes(plant)) {
        // Drop units of a deselected plant
        setSelectedUnits((units) => units.filter((u) => u.plant !== plant));
      }
      return next;
    });
  };

  const toggleUnit = (plant, item) => {
    setSelectedUnits((prev) => {
      const exists = prev.some((u) => u.plant === plant && u.item === item);
      return exists
        ? prev.filter((u) => !(u.plant === plant && u.item === item))
        : [...prev, { plant, item }];
    });
  };

  const isUnitSelected = (plant, item) =>
    selectedUnits.some((u) => u.plant === plant && u.item === item);

  const fetchData = () => {
    if (selectedUnits.length === 0 || !startMonth || !endMonth) return;
    setLoading(true);
    setError(null);
    fetch(`${API_BASE}/api/production-query`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ start: startMonth, end: endMonth, units: selectedUnits }),
    })
      .then((r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        return r.json();
      })
      .then((d) => setData(d))
      .catch((e) => setError(`Failed to load data: ${e.message}`))
      .finally(() => setLoading(false));
  };

  // Month options, oldest → newest, for the range dropdowns
  const monthOptions = [...(meta?.months || [])].sort();

  const months = data?.months || [];
  const series = data?.series || [];

  const selectStyle = {
    padding: '8px 12px',
    fontSize: '11pt',
    border: '1px solid #dadce0',
    borderRadius: '6px',
    backgroundColor: '#ffffff',
    color: '#202124',
    cursor: 'pointer',
    minWidth: '110px',
  };

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
            Unit-wise Production Query
          </h1>
          <p style={{ fontSize: '11pt', color: '#5f6368', marginTop: '6px' }}>
            Pick plants, units and a month range — get month-wise APP &amp; Actual with cumulative (&#39;000 T unless stated)
          </p>
        </div>

        {/* Controls */}
        <div style={{
          padding: '16px 20px',
          border: '1px solid #dadce0',
          borderRadius: '8px',
          backgroundColor: '#f8f9fa',
          marginBottom: '24px',
        }}>
          {/* Plants */}
          <div style={{ marginBottom: '14px' }}>
            <div style={{ fontSize: '11pt', fontWeight: 600, color: '#202124', marginBottom: '8px' }}>Plants</div>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px' }}>
              {(meta?.plants || []).map((plant) => {
                const on = selectedPlants.includes(plant);
                return (
                  <button
                    key={plant}
                    onClick={() => togglePlant(plant)}
                    style={{
                      padding: '6px 16px',
                      fontSize: '10.5pt',
                      fontWeight: 600,
                      border: on ? '1px solid #1a73e8' : '1px solid #dadce0',
                      borderRadius: '16px',
                      cursor: 'pointer',
                      backgroundColor: on ? '#1a73e8' : '#ffffff',
                      color: on ? '#ffffff' : '#5f6368',
                      transition: 'all 0.15s ease',
                    }}
                  >
                    {plant}
                  </button>
                );
              })}
            </div>
          </div>

          {/* Units per selected plant */}
          {selectedPlants.length > 0 && (
            <div style={{ marginBottom: '14px' }}>
              <div style={{ fontSize: '11pt', fontWeight: 600, color: '#202124', marginBottom: '8px' }}>Units</div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
                {selectedPlants.map((plant) => (
                  <div key={plant} style={{
                    border: '1px solid #dadce0',
                    borderRadius: '8px',
                    backgroundColor: '#ffffff',
                    padding: '10px 14px',
                  }}>
                    <div style={{ fontSize: '10pt', fontWeight: 700, color: '#174ea6', marginBottom: '6px' }}>
                      {plant}
                    </div>
                    <div style={{ display: 'flex', flexWrap: 'wrap', gap: '4px 16px' }}>
                      {(itemsByPlant[plant] || []).map((item) => (
                        <label key={item} style={{
                          display: 'inline-flex',
                          alignItems: 'center',
                          gap: '6px',
                          fontSize: '10pt',
                          color: '#202124',
                          cursor: 'pointer',
                          padding: '3px 0',
                          whiteSpace: 'nowrap',
                        }}>
                          <input
                            type="checkbox"
                            checked={isUnitSelected(plant, item)}
                            onChange={() => toggleUnit(plant, item)}
                            style={{ cursor: 'pointer' }}
                          />
                          {item}
                        </label>
                      ))}
                      {(itemsByPlant[plant] || []).length === 0 && (
                        <span style={{ fontSize: '10pt', color: '#bdc1c6' }}>Loading units…</span>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Month range + fetch */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '20px', flexWrap: 'wrap' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
              <label style={{ fontSize: '11pt', fontWeight: 600, color: '#202124' }}>From</label>
              <select value={startMonth} onChange={(e) => setStartMonth(e.target.value)} style={selectStyle}>
                {monthOptions.map((m) => (
                  <option key={m} value={m}>{monthLabel(m)}</option>
                ))}
              </select>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
              <label style={{ fontSize: '11pt', fontWeight: 600, color: '#202124' }}>To</label>
              <select value={endMonth} onChange={(e) => setEndMonth(e.target.value)} style={selectStyle}>
                {monthOptions.map((m) => (
                  <option key={m} value={m}>{monthLabel(m)}</option>
                ))}
              </select>
            </div>
            <button
              onClick={fetchData}
              disabled={selectedUnits.length === 0 || loading}
              style={{
                padding: '9px 28px',
                fontSize: '11pt',
                fontWeight: 700,
                border: 'none',
                borderRadius: '6px',
                cursor: selectedUnits.length === 0 || loading ? 'not-allowed' : 'pointer',
                backgroundColor: selectedUnits.length === 0 || loading ? '#dadce0' : '#1a73e8',
                color: '#ffffff',
                transition: 'all 0.15s ease',
              }}
            >
              {loading ? 'Loading…' : 'Get Data'}
            </button>
            {selectedUnits.length > 0 && (
              <span style={{ fontSize: '10.5pt', color: '#5f6368' }}>
                {selectedUnits.length} unit{selectedUnits.length > 1 ? 's' : ''} selected
              </span>
            )}
          </div>
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

        {/* Result table: months as rows, one APP/Actual column pair per unit */}
        {data && series.length > 0 && (
          <div style={{
            border: '1px solid #dadce0',
            borderRadius: '8px',
            overflowX: 'auto',
          }}>
            <table style={{ borderCollapse: 'separate', borderSpacing: 0, width: '100%' }}>
              <thead>
                <tr>
                  <th rowSpan={2} style={{
                    ...headCell,
                    left: 0,
                    zIndex: 3,
                    textAlign: 'left',
                    minWidth: '110px',
                    borderRight: '1px solid #dadce0',
                    verticalAlign: 'bottom',
                  }}>
                    Month
                  </th>
                  {series.map((s) => (
                    <th key={`${s.plant}|${s.item}`} colSpan={2} style={{
                      ...headCell,
                      textAlign: 'center',
                      borderLeft: '1px solid #dadce0',
                    }}>
                      {s.plant} · {s.item}
                    </th>
                  ))}
                </tr>
                <tr>
                  {series.map((s) => (
                    <React.Fragment key={`${s.plant}|${s.item}`}>
                      <th style={{
                        ...headCell,
                        top: '33px',
                        textAlign: 'right',
                        minWidth: '85px',
                        borderLeft: '1px solid #dadce0',
                        fontWeight: 600,
                      }}>
                        APP
                      </th>
                      <th style={{
                        ...headCell,
                        top: '33px',
                        textAlign: 'right',
                        minWidth: '85px',
                        fontWeight: 600,
                      }}>
                        Actual
                      </th>
                    </React.Fragment>
                  ))}
                </tr>
              </thead>
              <tbody>
                {months.map((m, idx) => {
                  const zebra = idx % 2 === 1 ? '#f8f9fa' : '#ffffff';
                  return (
                    <tr key={m}>
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
                        {monthLabel(m)}
                      </td>
                      {series.map((s) => (
                        <React.Fragment key={`${s.plant}|${s.item}`}>
                          <td style={{
                            ...cellBase,
                            textAlign: 'right',
                            backgroundColor: zebra,
                            color: s.plan[m] == null ? '#bdc1c6' : '#202124',
                            fontVariantNumeric: 'tabular-nums',
                            borderLeft: '1px solid #dadce0',
                          }}>
                            {fmt(s.plan[m])}
                          </td>
                          <td style={{
                            ...cellBase,
                            textAlign: 'right',
                            backgroundColor: zebra,
                            color: s.actual[m] == null ? '#bdc1c6' : '#202124',
                            fontVariantNumeric: 'tabular-nums',
                          }}>
                            {fmt(s.actual[m])}
                          </td>
                        </React.Fragment>
                      ))}
                    </tr>
                  );
                })}
                {/* Cumulative row */}
                <tr>
                  <td style={{
                    ...cellBase,
                    position: 'sticky',
                    left: 0,
                    zIndex: 1,
                    backgroundColor: '#e8f0fe',
                    fontWeight: 800,
                    color: '#174ea6',
                    borderRight: '1px solid #dadce0',
                    borderTop: '2px solid #1a73e8',
                  }}>
                    Cumulative
                  </td>
                  {series.map((s) => {
                    const cumPlan = cumulative(s.item, s.plan, months);
                    const cumActual = cumulative(s.item, s.actual, months);
                    const avgTag = isRateItem(s.item) ? ' (avg)' : '';
                    return (
                      <React.Fragment key={`${s.plant}|${s.item}`}>
                        <td style={{
                          ...cellBase,
                          textAlign: 'right',
                          backgroundColor: '#e8f0fe',
                          fontWeight: 700,
                          color: cumPlan == null ? '#bdc1c6' : '#174ea6',
                          fontVariantNumeric: 'tabular-nums',
                          borderLeft: '1px solid #dadce0',
                          borderTop: '2px solid #1a73e8',
                        }}>
                          {fmt(cumPlan)}{cumPlan != null ? avgTag : ''}
                        </td>
                        <td style={{
                          ...cellBase,
                          textAlign: 'right',
                          backgroundColor: '#e8f0fe',
                          fontWeight: 700,
                          color: cumActual == null ? '#bdc1c6' : '#174ea6',
                          fontVariantNumeric: 'tabular-nums',
                          borderTop: '2px solid #1a73e8',
                        }}>
                          {fmt(cumActual)}{cumActual != null ? avgTag : ''}
                        </td>
                      </React.Fragment>
                    );
                  })}
                </tr>
              </tbody>
            </table>
          </div>
        )}

        {data && series.length === 0 && (
          <div style={{ padding: '40px', textAlign: 'center', color: '#5f6368', fontSize: '12pt' }}>
            No units in the query — select at least one unit and click Get Data.
          </div>
        )}
      </main>
    </div>
  );
}
