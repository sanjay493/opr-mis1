'use client';

import React, { useState, useEffect, useMemo } from 'react';
import GlobalNavbar from '@/components/GlobalNavbar';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || '';
const PLANTS = ['BSP', 'DSP', 'RSP', 'BSL', 'ISP'];
const KEY_PARAMETERS = ['Coke Rate', 'BF Productivity', 'CDI Rate', 'Fuel Rate', 'O2 Enrichment'];
const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];

function TechnoDashboard() {
  const [selectedPlant, setSelectedPlant] = useState('all');
  const [selectedParams, setSelectedParams] = useState(KEY_PARAMETERS);
  const [monthRange, setMonthRange] = useState({ from: 0, to: 11 });
  const [allParameters, setAllParameters] = useState([]);
  const [data, setData] = useState({});
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

  // Load techno data
  useEffect(() => {
    const loadData = async () => {
      setLoading(true);
      setError(null);
      try {
        const plants = selectedPlant === 'all' ? PLANTS : [selectedPlant];
        const params = selectedParams.join(',');
        const url = `${API_BASE}/api/techno-data?plants=${encodeURIComponent(plants.join(','))}&parameters=${encodeURIComponent(params)}`;

        console.log('Fetching:', url);
        const res = await fetch(url);

        if (!res.ok) {
          const errorText = await res.text();
          throw new Error(`API Error ${res.status}: ${errorText}`);
        }
        const json = await res.json();
        console.log('Data received:', json);
        setData(json.data || {});
      } catch (err) {
        console.error('Error loading data:', err);
        setError(err.message || 'Failed to load data');
      } finally {
        setLoading(false);
      }
    };

    if (selectedParams.length > 0) {
      loadData();
    }
  }, [selectedPlant, selectedParams]);

  const handleParamToggle = (param) => {
    setSelectedParams(prev =>
      prev.includes(param)
        ? prev.filter(p => p !== param)
        : [...prev, param]
    );
  };

  const getLastMonths = (count) => {
    const now = new Date();
    const months = [];
    for (let i = count - 1; i >= 0; i--) {
      const d = new Date(now.getFullYear(), now.getMonth() - i, 1);
      months.push({
        label: `${MONTHS[d.getMonth()]} '${d.getFullYear().toString().slice(-2)}`,
        key: `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}`
      });
    }
    return months;
  };

  const displayMonths = getLastMonths(12).slice(monthRange.from, monthRange.to + 1);

  return (
    <>
      <GlobalNavbar />
      <main style={{
        padding: '32px 32px',
        maxWidth: '1600px',
        margin: '0 auto',
        width: '100%',
        display: 'flex',
        flexDirection: 'column'
      }}>
        <h1 style={{ fontSize: '24px', fontWeight: '900', color: '#0f172a', marginBottom: '20px' }}>
          📊 Techno Parameters Dashboard
        </h1>

        {/* Controls Section */}
        <div style={{
          backgroundColor: '#fff',
          border: '1px solid #e2e8f0',
          borderRadius: '12px',
          padding: '16px',
          marginBottom: '16px',
          boxShadow: '0 1px 3px rgba(0,0,0,0.08)',
          width: '100%'
        }}>
          {/* Plant Selection */}
          <div style={{ marginBottom: '12px' }}>
            <label style={{ display: 'block', fontSize: '11px', fontWeight: '700', color: '#475569', marginBottom: '6px', textTransform: 'uppercase' }}>
              🏭 Plant Selection
            </label>
            <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap' }}>
              <button
                onClick={() => setSelectedPlant('all')}
                style={{
                  padding: '5px 10px',
                  borderRadius: '4px',
                  border: `2px solid ${selectedPlant === 'all' ? '#0284c7' : '#e2e8f0'}`,
                  background: selectedPlant === 'all' ? '#f0f9ff' : '#fff',
                  color: selectedPlant === 'all' ? '#0284c7' : '#475569',
                  fontSize: '9px',
                  fontWeight: selectedPlant === 'all' ? '700' : '600',
                  cursor: 'pointer'
                }}
              >
                All 5
              </button>
              {PLANTS.map(plant => (
                <button
                  key={plant}
                  onClick={() => setSelectedPlant(plant)}
                  style={{
                    padding: '5px 10px',
                    borderRadius: '4px',
                    border: `2px solid ${selectedPlant === plant ? '#0284c7' : '#e2e8f0'}`,
                    background: selectedPlant === plant ? '#f0f9ff' : '#fff',
                    color: selectedPlant === plant ? '#0284c7' : '#475569',
                    fontSize: '9px',
                    fontWeight: selectedPlant === plant ? '700' : '600',
                    cursor: 'pointer'
                  }}
                >
                  {plant}
                </button>
              ))}
            </div>
          </div>

          {/* Parameter Selection */}
          <div style={{ marginBottom: '12px', maxHeight: '120px', overflowY: 'auto', border: '1px solid #e2e8f0', borderRadius: '4px', padding: '8px' }}>
            <label style={{ display: 'block', fontSize: '11px', fontWeight: '700', color: '#475569', marginBottom: '6px', textTransform: 'uppercase' }}>
              📈 Parameters ({selectedParams.length} selected)
            </label>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: '4px' }}>
              {allParameters.length > 0 ? (
                allParameters.map(param => (
                  <label key={param} style={{ display: 'flex', alignItems: 'center', gap: '4px', cursor: 'pointer', fontSize: '9px', padding: '2px' }}>
                    <input
                      type="checkbox"
                      checked={selectedParams.includes(param)}
                      onChange={() => handleParamToggle(param)}
                      style={{ width: '12px', height: '12px', cursor: 'pointer' }}
                    />
                    <span style={{ color: '#475569' }}>{param}</span>
                  </label>
                ))
              ) : (
                <div style={{ fontSize: '9px', color: '#94a3b8', gridColumn: '1 / -1' }}>Loading parameters...</div>
              )}
            </div>
          </div>

          {/* Month Range Selection */}
          <div style={{ marginBottom: '0' }}>
            <label style={{ display: 'block', fontSize: '11px', fontWeight: '700', color: '#475569', marginBottom: '8px', textTransform: 'uppercase' }}>
              📅 Month Range (Drag Slider)
            </label>
            <div style={{ display: 'block' }}>
              <input
                type="range"
                min="0"
                max="11"
                value={monthRange.from}
                onChange={(e) => setMonthRange(prev => ({ ...prev, from: Math.min(parseInt(e.target.value), prev.to) }))}
                style={{ width: '100%', height: '6px' }}
              />
              <div style={{ fontSize: '9px', color: '#64748b', marginTop: '6px', textAlign: 'center' }}>
                {displayMonths[0]?.label || 'Loading...'} to {displayMonths[displayMonths.length - 1]?.label || 'Loading...'}
              </div>
            </div>
          </div>
        </div>

        {/* View Mode Selector */}
        <div style={{ display: 'flex', gap: '8px', marginBottom: '16px', flexWrap: 'wrap' }}>
          {[
            { mode: 'table', label: '📋 Table', icon: '📊' },
            { mode: 'chart', label: '📈 Chart', icon: '📈' },
            { mode: 'comparison', label: '🔄 Compare', icon: '🔄' }
          ].map(({ mode, label }) => (
            <button
              key={mode}
              onClick={() => setViewMode(mode)}
              style={{
                padding: '6px 12px',
                borderRadius: '6px',
                border: `2px solid ${viewMode === mode ? '#10b981' : '#e2e8f0'}`,
                background: viewMode === mode ? '#f0fdf4' : '#fff',
                color: viewMode === mode ? '#10b981' : '#475569',
                fontSize: '10px',
                fontWeight: viewMode === mode ? '700' : '600',
                cursor: 'pointer'
              }}
            >
              {label}
            </button>
          ))}
        </div>

        {/* Loading & Error States */}
        {loading && (
          <div style={{ textAlign: 'center', padding: '20px', color: '#94a3b8', fontSize: '12px' }}>
            ⏳ Loading data...
          </div>
        )}

        {error && (
          <div style={{
            backgroundColor: '#fee2e2',
            border: '1px solid #fca5a5',
            borderRadius: '8px',
            padding: '12px 16px',
            color: '#991b1b',
            marginBottom: '20px',
            fontSize: '12px'
          }}>
            ❌ Error: {error}
            <div style={{ fontSize: '10px', marginTop: '6px', opacity: 0.8 }}>
              Check console (F12) for details. Parameters selected: {selectedParams.join(', ') || 'none'}
            </div>
          </div>
        )}

        {!loading && !error && selectedParams.length === 0 && (
          <div style={{
            backgroundColor: '#fef3c7',
            border: '1px solid #fcd34d',
            borderRadius: '8px',
            padding: '12px 16px',
            color: '#92400e',
            textAlign: 'center',
            fontSize: '12px'
          }}>
            ⚠️ Select at least one parameter to display data
          </div>
        )}

        {/* Table View */}
        {!loading && viewMode === 'table' && selectedParams.length > 0 && (
          <div style={{
            backgroundColor: '#fff',
            border: '1px solid #e2e8f0',
            borderRadius: '8px',
            overflow: 'hidden',
            boxShadow: '0 1px 3px rgba(0,0,0,0.08)'
          }}>
            <div style={{ overflowX: 'auto' }}>
              <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '9px' }}>
                <thead>
                  <tr style={{ backgroundColor: '#f1f5f9', borderBottom: '1px solid #e2e8f0', position: 'sticky', top: 0 }}>
                    <th style={{ padding: '6px 10px', textAlign: 'left', fontWeight: '700', color: '#475569', minWidth: '120px' }}>
                      Parameter
                    </th>
                    {displayMonths.map(month => (
                      <th
                        key={month.key}
                        style={{
                          padding: '6px 6px',
                          textAlign: 'center',
                          fontWeight: '700',
                          color: '#475569',
                          borderRight: '1px solid #e2e8f0',
                          whiteSpace: 'nowrap',
                          minWidth: '60px'
                        }}
                      >
                        {month.label}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {selectedParams.map((param, idx) => (
                    <tr key={param} style={{ borderBottom: '1px solid #f1f5f9', backgroundColor: idx % 2 === 0 ? '#fff' : '#f8fafc' }}>
                      <td style={{ padding: '6px 10px', fontWeight: '600', color: '#1e293b' }}>
                        {param}
                      </td>
                      {displayMonths.map(month => {
                        // Try to find data for this parameter and month across all plants
                        let value = null;
                        let dataSource = '';

                        if (selectedPlant === 'all') {
                          // Priority 1: Use SAIL consolidated value if available
                          if (data['SAIL']?.[param]?.[month.key]) {
                            value = data['SAIL'][param][month.key];
                            dataSource = '(SAIL)';
                          } else {
                            // Priority 2: Calculate weighted average based on production
                            // For now, use simple average as fallback
                            const plantData = [];
                            PLANTS.forEach(plant => {
                              if (data[plant]?.[param]?.[month.key]) {
                                plantData.push(data[plant][param][month.key]);
                              }
                            });
                            if (plantData.length > 0) {
                              value = (plantData.reduce((a, b) => a + b, 0) / plantData.length).toFixed(2);
                              dataSource = `(avg ${plantData.length})`;
                            }
                          }
                          // Format value if found
                          if (value !== null && value !== undefined) {
                            value = parseFloat(value).toFixed(2);
                          }
                        } else {
                          // For specific plant, get exact value
                          value = data[selectedPlant]?.[param]?.[month.key];
                          if (value !== null && value !== undefined) {
                            value = parseFloat(value).toFixed(2);
                          }
                        }

                        return (
                          <td
                            key={`${param}-${month.key}`}
                            style={{
                              padding: '6px 6px',
                              textAlign: 'right',
                              color: value ? '#0284c7' : '#94a3b8',
                              borderRight: '1px solid #e2e8f0',
                              fontSize: '9px',
                              fontWeight: value ? '600' : '400',
                              title: dataSource
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
        )}

        {/* Chart View */}
        {!loading && viewMode === 'chart' && selectedParams.length > 0 && (
          <div style={{
            backgroundColor: '#fff',
            border: '1px solid #e2e8f0',
            borderRadius: '8px',
            padding: '20px',
            boxShadow: '0 1px 3px rgba(0,0,0,0.08)',
            minHeight: '300px',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center'
          }}>
            <div style={{ textAlign: 'center', color: '#94a3b8' }}>
              📈 Chart visualization coming soon...
            </div>
          </div>
        )}

        {/* Plant Comparison View */}
        {!loading && viewMode === 'comparison' && selectedParams.length > 0 && (
          <div style={{
            backgroundColor: '#fff',
            border: '1px solid #e2e8f0',
            borderRadius: '8px',
            padding: '16px',
            boxShadow: '0 1px 3px rgba(0,0,0,0.08)',
            width: '100%'
          }}>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: '12px', width: '100%' }}>
              {selectedParams.map(param => (
                <div key={param} style={{
                  border: '1px solid #e2e8f0',
                  borderRadius: '6px',
                  padding: '12px',
                  backgroundColor: '#f8fafc'
                }}>
                  <h3 style={{ fontSize: '10px', fontWeight: '700', color: '#1e293b', marginBottom: '8px' }}>
                    {param}
                  </h3>
                  <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: '6px' }}>
                    {PLANTS.map(plant => (
                      <div key={plant} style={{
                        backgroundColor: '#fff',
                        border: '1px solid #e2e8f0',
                        borderRadius: '4px',
                        padding: '6px',
                        textAlign: 'center',
                        fontSize: '9px'
                      }}>
                        <div style={{ fontWeight: '600', color: '#475569', marginBottom: '2px' }}>{plant}</div>
                        <div style={{ fontSize: '12px', fontWeight: '700', color: '#0284c7' }}>—</div>
                      </div>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}
      </main>
    </>
  );
}

export default TechnoDashboard;
