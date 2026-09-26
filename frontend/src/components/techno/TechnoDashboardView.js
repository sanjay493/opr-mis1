'use client';

import React, { useState, useEffect, useMemo } from 'react';
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer,
} from 'recharts';
import { API_BASE, MONTH_ABBR, ErrorBox, TabIntro } from './shared';

const PLANTS = ['BSP', 'DSP', 'RSP', 'BSL', 'ISP'];
const KEY_PARAMETERS = ['Coke Rate', 'BF Productivity', 'CDI Rate', 'Fuel Rate', 'O2 Enrichment'];

// Fixed identity color per plant — same slots TechnoPerformanceCharts uses,
// so a plant keeps its color across every techno chart. SAIL takes slot 7.
// Validated with the dataviz palette checker (CVD + normal-vision pass; the
// lighter hues need the legend/tooltip/table relief this view provides).
const SERIES_COLORS = {
  BSP: '#2a78d6', DSP: '#eb6834', RSP: '#1baf7a', BSL: '#eda100', ISP: '#e87ba4', SAIL: '#4a3aa7',
};

const monthLabel = (key) => {
  const [y, m] = key.split('-');
  return `${MONTH_ABBR[Number(m) - 1]} '${y.slice(2)}`;
};

const labelHead = {
  display: 'block', fontSize: '12px', fontWeight: '700', color: '#5f6368',
  marginBottom: '6px', textTransform: 'uppercase',
};

function chipStyle(on) {
  return {
    padding: '6px 14px', borderRadius: '4px',
    border: `2px solid ${on ? '#1a73e8' : '#dadce0'}`,
    background: on ? '#f0f9ff' : '#fff',
    color: on ? '#1a73e8' : '#5f6368',
    fontSize: '12px', fontWeight: on ? '700' : '600', cursor: 'pointer',
  };
}

function ParamChart({ param, series, months, data }) {
  const rows = months.map((m) => {
    const row = { month: m.label };
    series.forEach((s) => {
      const raw = data[s]?.[param]?.[m.key];
      row[s] = raw == null || raw === '' ? null : Number(raw);
    });
    return row;
  });
  const hasAny = rows.some((r) => series.some((s) => r[s] != null));
  return (
    <div style={{ border: '1px solid #dadce0', borderRadius: '8px', padding: '12px 12px 4px', background: '#fff' }}>
      <div style={{ fontSize: '13px', fontWeight: 700, color: '#202124', marginBottom: '6px' }}>{param}</div>
      {!hasAny ? (
        <div style={{ height: 240, display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#9aa0a6', fontSize: '12px' }}>
          No data in the selected month range
        </div>
      ) : (
        <ResponsiveContainer width="100%" height={240}>
          <LineChart data={rows} margin={{ top: 6, right: 12, bottom: 0, left: 0 }}>
            <CartesianGrid stroke="#eceff1" vertical={false} />
            <XAxis dataKey="month" tick={{ fontSize: 11, fill: '#5f6368' }} tickLine={false} axisLine={{ stroke: '#dadce0' }} minTickGap={16} />
            <YAxis tick={{ fontSize: 11, fill: '#5f6368' }} tickLine={false} axisLine={false} width={48} domain={['auto', 'auto']} />
            <Tooltip
              formatter={(v) => (v == null ? '—' : Number(v).toLocaleString('en-IN', { maximumFractionDigits: 2 }))}
              contentStyle={{ fontSize: 12, borderRadius: 6, borderColor: '#dadce0' }}
              labelStyle={{ fontWeight: 700, color: '#202124' }}
              itemStyle={{ color: '#202124' }}
            />
            {series.length > 1 && <Legend wrapperStyle={{ fontSize: 12, color: '#202124' }} iconType="plainline" />}
            {series.map((s) => (
              <Line
                key={s} type="linear" dataKey={s} name={s}
                stroke={SERIES_COLORS[s]} strokeWidth={s === 'SAIL' ? 3 : 2}
                dot={months.length <= 24 ? { r: 3 } : false} activeDot={{ r: 5, stroke: '#fff', strokeWidth: 2 }}
                connectNulls={false} isAnimationActive={false}
              />
            ))}
          </LineChart>
        </ResponsiveContainer>
      )}
    </div>
  );
}

export default function TechnoDashboardView() {
  const [selectedPlant, setSelectedPlant] = useState('all');
  const [selectedParams, setSelectedParams] = useState(KEY_PARAMETERS);
  const [range, setRange] = useState({ from: null, to: null });   // 'YYYY-MM' keys
  const [allParameters, setAllParameters] = useState([]);
  const [paramFilter, setParamFilter] = useState('');
  const [data, setData] = useState({});
  const [sailMissing, setSailMissing] = useState({});
  const [loading, setLoading] = useState(false);
  const [viewMode, setViewMode] = useState('table');
  const [error, setError] = useState(null);

  // Load available parameters
  useEffect(() => {
    const loadParameters = async () => {
      try {
        const res = await fetch(`${API_BASE}/api/techno-parameters`);
        if (res.ok) {
          const json = await res.json();
          setAllParameters(json.parameters || KEY_PARAMETERS);
        } else {
          setAllParameters(KEY_PARAMETERS);
        }
      } catch {
        setAllParameters(KEY_PARAMETERS);
      }
    };
    loadParameters();
  }, []);

  // Chart and Compare views plot every plant side by side, so they always
  // fetch all plants; only the Table view narrows to the chosen plant.
  const fetchAllPlants = selectedPlant === 'all' || viewMode !== 'table';

  // Load techno data
  useEffect(() => {
    if (selectedParams.length === 0) return;
    let cancelled = false;
    const loadData = async () => {
      setLoading(true);
      setError(null);
      try {
        const plants = fetchAllPlants ? PLANTS : [selectedPlant];
        const params = selectedParams.join(',');
        const url = `${API_BASE}/api/techno-data?plants=${encodeURIComponent(plants.join(','))}&parameters=${encodeURIComponent(params)}`;
        const res = await fetch(url);
        if (!res.ok) {
          const errorText = await res.text();
          throw new Error(`API Error ${res.status}: ${errorText}`);
        }
        const json = await res.json();
        if (cancelled) return;
        setData(json.data || {});
        setSailMissing(json.sail_missing || {});
      } catch (err) {
        if (!cancelled) setError(err.message || 'Failed to load data');
      } finally {
        if (!cancelled) setLoading(false);
      }
    };
    loadData();
    return () => { cancelled = true; };
  }, [selectedPlant, selectedParams, fetchAllPlants]);

  const handleParamToggle = (param) => {
    setSelectedParams(prev =>
      prev.includes(param)
        ? prev.filter(p => p !== param)
        : [...prev, param]
    );
  };

  const visibleParameters = useMemo(() => {
    const q = paramFilter.trim().toLowerCase();
    return q ? allParameters.filter(p => p.toLowerCase().includes(q)) : allParameters;
  }, [allParameters, paramFilter]);

  // Every 'YYYY-MM' that the loaded data actually carries a value for.
  const availableMonths = useMemo(() => {
    const s = new Set();
    Object.values(data).forEach(params =>
      Object.values(params || {}).forEach(months =>
        Object.keys(months || {}).forEach(m => s.add(m))));
    return [...s].sort();
  }, [data]);

  // Keep the range valid as the available months change (param/plant switch);
  // default to the most recent 12 months of data.
  useEffect(() => {
    if (availableMonths.length === 0) return;
    setRange(r => {
      const last = availableMonths[availableMonths.length - 1];
      const from = r.from && availableMonths.includes(r.from)
        ? r.from : availableMonths[Math.max(0, availableMonths.length - 12)];
      const to = r.to && availableMonths.includes(r.to) ? r.to : last;
      return (from === r.from && to === r.to) ? r : { from, to };
    });
  }, [availableMonths]);

  const applyPreset = (kind) => {
    if (!availableMonths.length) return;
    const first = availableMonths[0];
    const last = availableMonths[availableMonths.length - 1];
    const nthFromEnd = (n) => availableMonths[Math.max(0, availableMonths.length - n)];
    if (kind === 'all') setRange({ from: first, to: last });
    else if (kind === 'last6') setRange({ from: nthFromEnd(6), to: last });
    else if (kind === 'last12') setRange({ from: nthFromEnd(12), to: last });
    else if (kind === 'fy') {
      const [y, m] = last.split('-').map(Number);
      const fyFrom = `${m >= 4 ? y : y - 1}-04`;
      setRange({ from: availableMonths.find(x => x >= fyFrom) || first, to: last });
    }
  };

  const displayMonths = useMemo(() => {
    if (!range.from || !range.to) return [];
    const [lo, hi] = range.from <= range.to ? [range.from, range.to] : [range.to, range.from];
    return availableMonths.filter(m => m >= lo && m <= hi).map(k => ({ key: k, label: monthLabel(k) }));
  }, [availableMonths, range]);

  // Most recent month (within the selected range) that has a value for this
  // plant/parameter — used by the Compare view so each card shows a real,
  // current-ish snapshot per plant instead of always the very latest month
  // (which may still be blank for plants that haven't reported yet).
  const getLatestValue = (plant, param) => {
    for (let i = displayMonths.length - 1; i >= 0; i--) {
      const month = displayMonths[i];
      const raw = data[plant]?.[param]?.[month.key];
      if (raw != null && raw !== '') {
        return { value: parseFloat(raw).toFixed(2), monthLabel: month.label };
      }
    }
    return null;
  };

  // Remark data for the Table/Chart views: which selected parameters are
  // missing a SAIL figure for one or more of the currently displayed months,
  // and which plant(s) are most often the reason (union across those months).
  const sailMissingSummary = selectedPlant === 'all'
    ? selectedParams
        .map(param => {
          const monthsMissing = displayMonths.filter(m => data['SAIL']?.[param]?.[m.key] == null);
          if (monthsMissing.length === 0) return null;
          const plantsInvolved = new Set();
          monthsMissing.forEach(m => (sailMissing[param]?.[m.key] || []).forEach(p => plantsInvolved.add(p)));
          return { param, missingCount: monthsMissing.length, totalCount: displayMonths.length, plants: Array.from(plantsInvolved) };
        })
        .filter(Boolean)
    : [];

  // Chart series: every plant + SAIL when "SAIL (all plants)" is selected,
  // otherwise just the chosen plant.
  const chartSeries = selectedPlant === 'all' ? [...PLANTS, 'SAIL'] : [selectedPlant];

  const sailRemark = sailMissingSummary.length > 0 && (
    <div style={{
      marginTop: '12px', padding: '10px 14px', background: '#fef7e0',
      border: '1px solid #fde68a', borderRadius: '6px', fontSize: '12px', color: '#92400e',
    }}>
      <strong>⚠️ Remark:</strong> a SAIL figure is only shown for a month when all 5 plants
      (BSP, DSP, RSP, BSL, ISP) have reported both the parameter and its production weight
      (Hot Metal, or Crude Steel for Specific Energy Consumption) for that month — never a
      partial-plant average. SAIL is computed only for Coke Rate, CDI Rate, Fuel Rate,
      BF Productivity and Specific Energy Consumption. Currently incomplete for the shown range:
      <ul style={{ margin: '6px 0 0 18px', padding: 0 }}>
        {sailMissingSummary.map(s => (
          <li key={s.param}>
            {s.param}: missing in {s.missingCount} of {s.totalCount} shown months
            {s.plants.length > 0 && ` (plants involved: ${s.plants.join(', ')})`}
          </li>
        ))}
      </ul>
    </div>
  );

  return (
    <div>
      <TabIntro>
        Month-by-month trend of any techno parameter stored in the database, for SAIL or one plant —
        as a table, a line chart per parameter, or a side-by-side plant comparison of the latest value.
      </TabIntro>

      {/* Controls Section */}
      <div style={{
        backgroundColor: '#fff', border: '1px solid #dadce0', borderRadius: '12px',
        padding: '16px', marginBottom: '16px', boxShadow: '0 1px 3px rgba(0,0,0,0.08)',
      }}>
        {/* Plant Selection */}
        <div style={{ marginBottom: '14px' }}>
          <label style={labelHead}>🏭 Plant Selection</label>
          <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap' }}>
            <button onClick={() => setSelectedPlant('all')} style={chipStyle(selectedPlant === 'all')}>
              SAIL (all plants)
            </button>
            {PLANTS.map(plant => (
              <button key={plant} onClick={() => setSelectedPlant(plant)} style={chipStyle(selectedPlant === plant)}>
                {plant}
              </button>
            ))}
          </div>
        </div>

        {/* Parameter Selection */}
        <div style={{ marginBottom: '14px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '6px', flexWrap: 'wrap' }}>
            <label style={{ ...labelHead, marginBottom: 0 }}>📈 Parameters ({selectedParams.length} selected)</label>
            <input
              type="search" placeholder="Filter parameters…" value={paramFilter}
              onChange={(e) => setParamFilter(e.target.value)}
              style={{ fontSize: '12px', padding: '4px 8px', border: '1px solid #dadce0', borderRadius: '4px', minWidth: '200px' }}
            />
            <button onClick={() => setSelectedParams(KEY_PARAMETERS)} style={{ ...chipStyle(false), padding: '3px 10px', fontSize: '11px' }}>Reset</button>
            <button onClick={() => setSelectedParams([])} style={{ ...chipStyle(false), padding: '3px 10px', fontSize: '11px' }}>Clear</button>
          </div>
          <div style={{ maxHeight: '150px', overflowY: 'auto', border: '1px solid #dadce0', borderRadius: '4px', padding: '8px' }}>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(220px, 1fr))', gap: '4px' }}>
              {allParameters.length > 0 ? (
                visibleParameters.map(param => (
                  <label key={param} style={{ display: 'flex', alignItems: 'center', gap: '6px', cursor: 'pointer', fontSize: '12px', padding: '2px' }}>
                    <input
                      type="checkbox"
                      checked={selectedParams.includes(param)}
                      onChange={() => handleParamToggle(param)}
                      style={{ width: '14px', height: '14px', cursor: 'pointer' }}
                    />
                    <span style={{ color: '#202124' }}>{param}</span>
                  </label>
                ))
              ) : (
                <div style={{ fontSize: '12px', color: '#5f6368', gridColumn: '1 / -1' }}>Loading parameters...</div>
              )}
            </div>
          </div>
        </div>

        {/* Month Range Selection */}
        <div>
          <label style={labelHead}>📅 Month Range</label>
          {availableMonths.length === 0 ? (
            <div style={{ fontSize: '12px', color: '#9aa0a6' }}>
              {loading ? 'Loading months…' : 'No data for the current plant / parameter selection.'}
            </div>
          ) : (
            <div style={{ display: 'flex', gap: '8px', alignItems: 'center', flexWrap: 'wrap' }}>
              <select
                value={range.from ?? ''}
                onChange={(e) => setRange(r => ({ ...r, from: e.target.value }))}
                style={{ fontSize: '13px', padding: '5px 8px', border: '1px solid #dadce0', borderRadius: '4px', color: '#202124' }}
              >
                {availableMonths.map(m => <option key={m} value={m}>{monthLabel(m)}</option>)}
              </select>
              <span style={{ fontSize: '12px', color: '#5f6368' }}>to</span>
              <select
                value={range.to ?? ''}
                onChange={(e) => setRange(r => ({ ...r, to: e.target.value }))}
                style={{ fontSize: '13px', padding: '5px 8px', border: '1px solid #dadce0', borderRadius: '4px', color: '#202124' }}
              >
                {availableMonths.map(m => <option key={m} value={m}>{monthLabel(m)}</option>)}
              </select>

              <div style={{ display: 'flex', gap: '4px', marginLeft: '6px' }}>
                {[
                  { k: 'last6', l: 'Last 6' },
                  { k: 'last12', l: 'Last 12' },
                  { k: 'fy', l: 'This FY' },
                  { k: 'all', l: 'All' },
                ].map(({ k, l }) => (
                  <button
                    key={k}
                    onClick={() => applyPreset(k)}
                    style={{ fontSize: '12px', fontWeight: '600', padding: '4px 10px', borderRadius: '4px', border: '1px solid #dadce0', background: '#f8f9fa', color: '#5f6368', cursor: 'pointer' }}
                  >
                    {l}
                  </button>
                ))}
              </div>

              <span style={{ fontSize: '12px', color: '#9aa0a6', marginLeft: '4px' }}>
                {displayMonths.length} month{displayMonths.length === 1 ? '' : 's'}
              </span>
            </div>
          )}
        </div>
      </div>

      {/* View Mode Selector */}
      <div style={{ display: 'flex', gap: '8px', marginBottom: '16px', flexWrap: 'wrap' }}>
        {[
          { mode: 'table', label: '📋 Table' },
          { mode: 'chart', label: '📈 Chart' },
          { mode: 'comparison', label: '🔄 Compare' },
        ].map(({ mode, label }) => (
          <button
            key={mode}
            onClick={() => setViewMode(mode)}
            style={{
              padding: '6px 14px', borderRadius: '6px',
              border: `2px solid ${viewMode === mode ? '#10b981' : '#dadce0'}`,
              background: viewMode === mode ? '#f0fdf4' : '#fff',
              color: viewMode === mode ? '#047857' : '#5f6368',
              fontSize: '13px', fontWeight: viewMode === mode ? '700' : '600', cursor: 'pointer',
            }}
          >
            {label}
          </button>
        ))}
      </div>

      {/* Loading & Error States */}
      {loading && (
        <div style={{ textAlign: 'center', padding: '20px', color: '#5f6368', fontSize: '13px' }}>
          ⏳ Loading data...
        </div>
      )}

      <ErrorBox>{error && `Error: ${error}`}</ErrorBox>

      {!loading && !error && selectedParams.length === 0 && (
        <div style={{
          backgroundColor: '#fef3c7', border: '1px solid #fcd34d', borderRadius: '8px',
          padding: '12px 16px', color: '#92400e', textAlign: 'center', fontSize: '13px',
        }}>
          ⚠️ Select at least one parameter to display data
        </div>
      )}

      {/* Table View */}
      {!loading && viewMode === 'table' && selectedParams.length > 0 && (
        <>
          <div style={{
            backgroundColor: '#fff', border: '1px solid #dadce0', borderRadius: '8px',
            overflow: 'hidden', boxShadow: '0 1px 3px rgba(0,0,0,0.08)',
          }}>
            <div style={{ overflowX: 'auto' }}>
              <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '12px' }}>
                <thead>
                  <tr style={{ backgroundColor: '#f8f9fa', borderBottom: '1px solid #dadce0' }}>
                    <th style={{ padding: '8px 10px', textAlign: 'left', fontWeight: '700', color: '#5f6368', minWidth: '160px', position: 'sticky', left: 0, background: '#f8f9fa' }}>
                      {selectedPlant === 'all' ? 'SAIL · Parameter' : `${selectedPlant} · Parameter`}
                    </th>
                    {displayMonths.map(month => (
                      <th
                        key={month.key}
                        style={{
                          padding: '8px 6px', textAlign: 'center', fontWeight: '700', color: '#5f6368',
                          borderRight: '1px solid #dadce0', whiteSpace: 'nowrap', minWidth: '64px',
                        }}
                      >
                        {month.label}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {selectedParams.map((param, idx) => (
                    <tr key={param} style={{ borderBottom: '1px solid #f1f3f4', backgroundColor: idx % 2 === 0 ? '#fff' : '#f8f9fa' }}>
                      <td style={{ padding: '7px 10px', fontWeight: '600', color: '#202124', position: 'sticky', left: 0, background: idx % 2 === 0 ? '#fff' : '#f8f9fa' }}>
                        {param}
                      </td>
                      {displayMonths.map(month => {
                        let value = null;
                        let tooltip = '';

                        if (selectedPlant === 'all') {
                          // The backend only fills this in when all 5 plants have
                          // BOTH the parameter and its production weight (Hot Metal /
                          // Crude Steel) for the month — never a partial-plant average.
                          const raw = data['SAIL']?.[param]?.[month.key];
                          if (raw !== null && raw !== undefined) {
                            value = parseFloat(raw).toFixed(2);
                            tooltip = 'SAIL — weighted across all 5 plants';
                          } else {
                            const missingPlants = sailMissing[param]?.[month.key];
                            tooltip = missingPlants
                              ? `SAIL not shown — missing ${param} and/or production data for: ${missingPlants.join(', ')}`
                              : 'No data';
                          }
                        } else {
                          value = data[selectedPlant]?.[param]?.[month.key];
                          if (value !== null && value !== undefined) {
                            value = parseFloat(value).toFixed(2);
                          }
                        }

                        return (
                          <td
                            key={`${param}-${month.key}`}
                            title={tooltip}
                            style={{
                              padding: '7px 6px', textAlign: 'right',
                              color: value ? '#1a73e8' : '#5f6368',
                              borderRight: '1px solid #dadce0',
                              fontWeight: value ? '600' : '400',
                            }}
                          >
                            {value || '—'}
                          </td>
                        );
                      })}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
          {sailRemark}
        </>
      )}

      {/* Chart View — one small chart per parameter (units differ per
          parameter, so they never share a y-axis). */}
      {!loading && viewMode === 'chart' && selectedParams.length > 0 && (
        displayMonths.length === 0 ? (
          <div style={{ padding: '40px', textAlign: 'center', color: '#5f6368', fontSize: '13px' }}>
            No data in the selected month range.
          </div>
        ) : (
          <>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(440px, 1fr))', gap: '14px' }}>
              {selectedParams.map(param => (
                <ParamChart key={param} param={param} series={chartSeries} months={displayMonths} data={data} />
              ))}
            </div>
            {sailRemark}
          </>
        )
      )}

      {/* Plant Comparison View */}
      {!loading && viewMode === 'comparison' && selectedParams.length > 0 && (
        <div style={{
          backgroundColor: '#fff', border: '1px solid #dadce0', borderRadius: '8px',
          padding: '16px', boxShadow: '0 1px 3px rgba(0,0,0,0.08)',
        }}>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(260px, 1fr))', gap: '12px' }}>
            {selectedParams.map(param => (
              <div key={param} style={{ border: '1px solid #dadce0', borderRadius: '6px', padding: '12px', backgroundColor: '#f8f9fa' }}>
                <h3 style={{ fontSize: '13px', fontWeight: '700', color: '#202124', margin: '0 0 8px' }}>
                  {param}
                </h3>
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: '6px' }}>
                  {PLANTS.map(plant => {
                    const latest = getLatestValue(plant, param);
                    return (
                      <div key={plant} title={latest ? `As of ${latest.monthLabel}` : 'No data in the selected month range'} style={{
                        backgroundColor: '#fff', border: '1px solid #dadce0', borderRadius: '4px',
                        padding: '6px', textAlign: 'center', fontSize: '12px',
                      }}>
                        <div style={{ fontWeight: '600', color: '#5f6368', marginBottom: '2px' }}>{plant}</div>
                        <div style={{ fontSize: '15px', fontWeight: '700', color: latest ? '#1a73e8' : '#bdc1c6' }}>
                          {latest ? latest.value : '—'}
                        </div>
                        {latest && (
                          <div style={{ fontSize: '10px', color: '#9aa0a6', marginTop: '1px' }}>{latest.monthLabel}</div>
                        )}
                      </div>
                    );
                  })}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
