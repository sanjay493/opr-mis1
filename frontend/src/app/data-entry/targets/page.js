'use client';
import React, { useState, useEffect, useCallback } from 'react';
import GlobalNavbar from '@/components/GlobalNavbar';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://127.0.0.1:8082';

const FY_LIST = ['2023-24', '2024-25', '2025-26', '2026-27', '2027-28', '2028-29'];
const PLANTS = ['BSP', 'DSP', 'RSP', 'BSL', 'ISP', 'SAIL'];

export default function TechnoTargetsPage() {
  const [fy, setFy] = useState('2026-27');
  const [parameters, setParameters] = useState([]);
  const [plantTargets, setPlantTargets] = useState({});
  const [sailTargets, setSailTargets] = useState({});
  const [edits, setEdits] = useState({});
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [recalculating, setRecalculating] = useState(false);
  const [status, setStatus] = useState(null);

  // Load parameters and targets
  const handleLoad = useCallback(async () => {
    setLoading(true);
    setStatus(null);
    try {
      const [paramsRes, plantRes, sailRes] = await Promise.all([
        fetch(`${API_BASE_URL}/api/techno-major-parameters`),
        fetch(`${API_BASE_URL}/api/techno-plant-targets?fy=${encodeURIComponent(fy)}`),
        fetch(`${API_BASE_URL}/api/techno-sail-targets?fy=${encodeURIComponent(fy)}`),
      ]);

      if (!paramsRes.ok || !plantRes.ok || !sailRes.ok) {
        throw new Error('Failed to load parameters or targets');
      }

      const paramsData = await paramsRes.json();
      const plantData = await plantRes.json();
      const sailData = await sailRes.json();

      setParameters(paramsData.parameters || []);
      setPlantTargets(plantData.plants || {});
      setSailTargets(sailData.targets || {});

      // Initialize edits with loaded data
      const initialEdits = {};
      Object.entries(plantData.plants || {}).forEach(([plant, params]) => {
        Object.entries(params || {}).forEach(([param, value]) => {
          initialEdits[`${plant}|${param}`] = value?.toString() || '';
        });
      });
      Object.entries(sailData.targets || {}).forEach(([param, value]) => {
        initialEdits[`SAIL|${param}`] = value?.toString() || '';
      });
      setEdits(initialEdits);
    } catch (err) {
      setStatus({ type: 'error', text: `Load failed: ${err.message}` });
    } finally {
      setLoading(false);
    }
  }, [fy]);

  // Auto-load on FY change
  useEffect(() => {
    handleLoad();
  }, [fy, handleLoad]);

  // Handle parameter value change
  const handleChange = (plant, param, value) => {
    setEdits(prev => ({ ...prev, [`${plant}|${param}`]: value }));
  };

  // Recalculate SAIL targets
  const handleRecalculate = async () => {
    setRecalculating(true);
    setStatus(null);
    try {
      const res = await fetch(`${API_BASE_URL}/api/techno-recalculate-sail`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ fy }),
      });

      if (!res.ok) throw new Error(await res.text());
      const result = await res.json();

      // Update SAIL values with computed values
      const newEdits = { ...edits };
      Object.entries(result.computed || {}).forEach(([param, value]) => {
        newEdits[`SAIL|${param}`] = value?.toString() || '';
      });
      setEdits(newEdits);
      setStatus({ type: 'success', text: 'SAIL targets recalculated from plant-level values' });
    } catch (err) {
      setStatus({ type: 'error', text: `Recalculation failed: ${err.message}` });
    } finally {
      setRecalculating(false);
    }
  };

  // Save all targets
  const handleSave = async () => {
    setSaving(true);
    setStatus(null);

    // Organize edits by plant
    const plantData = {};
    const sailData = {};

    Object.entries(edits).forEach(([key, val]) => {
      if (val === '' || val === null) return;
      const [plant, param] = key.split('|');
      try {
        const numVal = parseFloat(val);
        if (plant === 'SAIL') {
          sailData[param] = numVal;
        } else {
          if (!plantData[plant]) plantData[plant] = {};
          plantData[plant][param] = numVal;
        }
      } catch {
        // Skip invalid values
      }
    });

    try {
      const requests = [];

      // Save plant targets if any
      if (Object.keys(plantData).length > 0) {
        requests.push(
          fetch(`${API_BASE_URL}/api/techno-plant-targets`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ fy, plants: plantData }),
          })
        );
      }

      // Save SAIL targets if any
      if (Object.keys(sailData).length > 0) {
        requests.push(
          fetch(`${API_BASE_URL}/api/techno-sail-targets`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ fy, targets: sailData }),
          })
        );
      }

      if (requests.length === 0) {
        setStatus({ type: 'error', text: 'No values to save.' });
        setSaving(false);
        return;
      }

      const responses = await Promise.all(requests);
      for (const res of responses) {
        if (!res.ok) throw new Error(await res.text());
      }

      setStatus({ type: 'success', text: `Saved targets for FY ${fy}` });
      setPlantTargets(plantData);
      setSailTargets(sailData);
    } catch (err) {
      setStatus({ type: 'error', text: `Save failed: ${err.message}` });
    } finally {
      setSaving(false);
    }
  };

  // Check for changes
  const hasChanges = () => {
    return Object.entries(edits).some(([key, val]) => {
      if (val === '' || val === null) return false;
      const [plant, param] = key.split('|');
      if (plant === 'SAIL') {
        return sailTargets[param]?.toString() !== val;
      } else {
        return plantTargets[plant]?.[param]?.toString() !== val;
      }
    });
  };

  const getValue = (plant, param) => edits[`${plant}|${param}`] ?? '';
  const getSavedValue = (plant, param) => {
    if (plant === 'SAIL') {
      return sailTargets[param];
    }
    return plantTargets[plant]?.[param];
  };
  const isChanged = (plant, param) => getValue(plant, param) !== getSavedValue(plant, param)?.toString();

  return (
    <div style={{ minHeight: '100vh', backgroundColor: '#f8fafc' }}>
      <GlobalNavbar />

      <main style={{ padding: '32px', maxWidth: '1400px', margin: '0 auto' }}>
        <div style={{ marginBottom: '32px' }}>
          <h1 style={{ fontSize: '24pt', fontWeight: '900', color: '#0f172a', margin: '0 0 8px 0' }}>
            📊 Techno-Economic Annual Targets
          </h1>
          <p style={{ fontSize: '11pt', color: '#64748b', margin: '0' }}>
            Enter targets for each parameter by plant. SAIL can be recalculated from plant-level targets or edited manually.
          </p>
        </div>

        {/* Controls */}
        <div style={{
          display: 'flex', gap: '12px', alignItems: 'center', marginBottom: '24px',
          flexWrap: 'wrap', backgroundColor: '#fff', padding: '16px', borderRadius: '8px', border: '1px solid #e2e8f0'
        }}>
          <div>
            <label style={{ fontSize: '10pt', fontWeight: '600', color: '#475569', display: 'block', marginBottom: '4px' }}>
              Financial Year
            </label>
            <select
              value={fy}
              onChange={e => setFy(e.target.value)}
              style={{ padding: '8px 12px', fontSize: '11pt', borderRadius: '4px', border: '1px solid #cbd5e1' }}
            >
              {FY_LIST.map(f => <option key={f} value={f}>{f}</option>)}
            </select>
          </div>

          <button
            onClick={handleLoad}
            disabled={loading}
            style={{
              padding: '8px 16px', fontSize: '11pt', fontWeight: '600', borderRadius: '4px',
              border: 'none', backgroundColor: '#6366f1', color: '#fff', cursor: 'pointer',
              marginTop: '18px'
            }}
          >
            {loading ? 'Loading...' : 'Load'}
          </button>

          <button
            onClick={handleRecalculate}
            disabled={recalculating || parameters.length === 0}
            style={{
              padding: '8px 16px', fontSize: '11pt', fontWeight: '600', borderRadius: '4px',
              border: 'none', backgroundColor: '#0891b2', color: '#fff', cursor: 'pointer',
              marginTop: '18px'
            }}
          >
            {recalculating ? 'Calculating...' : 'Recalculate SAIL'}
          </button>

          <button
            onClick={handleSave}
            disabled={saving || !hasChanges()}
            style={{
              padding: '8px 16px', fontSize: '11pt', fontWeight: '600', borderRadius: '4px',
              border: 'none', backgroundColor: hasChanges() ? '#10b981' : '#94a3b8', color: '#fff',
              cursor: hasChanges() ? 'pointer' : 'default', marginTop: '18px'
            }}
          >
            {saving ? 'Saving...' : 'Save All'}
          </button>
        </div>

        {/* Status */}
        {status && (
          <div style={{
            padding: '12px 16px', marginBottom: '16px', borderRadius: '6px', fontSize: '11pt',
            backgroundColor: status.type === 'success' ? '#dcfce7' : '#fee2e2',
            color: status.type === 'success' ? '#166534' : '#991b1b',
            border: `1px solid ${status.type === 'success' ? '#bbf7d0' : '#fecaca'}`
          }}>
            {status.text}
          </div>
        )}

        {/* Parameters Table */}
        {parameters.length > 0 && (
          <div style={{ backgroundColor: '#fff', borderRadius: '8px', border: '1px solid #e2e8f0', overflow: 'hidden' }}>
            <div style={{ overflowX: 'auto' }}>
              <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                <thead>
                  <tr style={{ backgroundColor: '#1e3a5f', color: '#fff' }}>
                    <th style={{ padding: '12px 16px', textAlign: 'left', fontWeight: '700', fontSize: '11pt' }}>Parameter</th>
                    <th style={{ padding: '12px 16px', textAlign: 'center', fontWeight: '700', fontSize: '11pt', minWidth: '80px' }}>Unit</th>
                    {PLANTS.map(plant => (
                      <th key={plant}
                        style={{
                          padding: '12px 16px', textAlign: 'center', fontWeight: '700', fontSize: '11pt',
                          backgroundColor: plant === 'SAIL' ? '#166534' : '#1e3a5f', minWidth: '110px'
                        }}
                      >
                        {plant}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {parameters.map((param, idx) => (
                    <tr key={param.name} style={{ borderBottom: '1px solid #e2e8f0', backgroundColor: idx % 2 === 0 ? '#f8fafc' : '#fff' }}>
                      <td style={{ padding: '10px 16px', fontSize: '11pt', fontWeight: '500', color: '#1e293b' }}>
                        {param.name}
                      </td>
                      <td style={{ padding: '10px 16px', textAlign: 'center', fontSize: '10pt', color: '#475569' }}>
                        {param.unit}
                      </td>
                      {PLANTS.map(plant => {
                        const value = getValue(plant, param.name);
                        const saved = getSavedValue(plant, param.name);
                        const changed = isChanged(plant, param.name);
                        return (
                          <td key={`${plant}-${param.name}`} style={{ padding: '8px 12px', textAlign: 'right' }}>
                            <input
                              type="number"
                              step="0.001"
                              value={value}
                              onChange={e => handleChange(plant, param.name, e.target.value)}
                              style={{
                                width: '100%', padding: '6px 8px', fontSize: '10pt', textAlign: 'right',
                                border: `1px solid ${changed ? '#fbbf24' : '#cbd5e1'}`,
                                borderRadius: '4px',
                                backgroundColor: changed ? '#fffbeb' : saved ? '#f0fdf4' : '#fff',
                                color: changed ? '#92400e' : saved ? '#065f46' : '#1e293b'
                              }}
                              placeholder="–"
                            />
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

        {parameters.length === 0 && !loading && (
          <div style={{
            padding: '32px', textAlign: 'center', color: '#94a3b8', fontSize: '11pt',
            backgroundColor: '#fff', borderRadius: '6px', border: '1px solid #e2e8f0'
          }}>
            Select a financial year and click <strong>Load</strong> to view parameters.
          </div>
        )}
      </main>
    </div>
  );
}
