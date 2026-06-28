'use client';
import React, { useState, useEffect, useCallback } from 'react';
import GlobalNavbar from '@/components/GlobalNavbar';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://127.0.0.1:8082';

const FY_LIST = ['2023-24', '2024-25', '2025-26', '2026-27', '2027-28', '2028-29'];
const PLANTS = ['BSP', 'DSP', 'RSP', 'BSL', 'ISP', 'SAIL'];

export default function TechnoTargetsPage() {
  const [fy, setFy] = useState('2026-27');
  const [bfParams, setBfParams] = useState([]);
  const [smsParams, setSmsParams] = useState([]);
  const [smsShops, setSmsShops] = useState([]);
  const [plantTargets, setPlantTargets] = useState({});
  const [smsTargets, setSmsTargets] = useState({});
  const [sailTargets, setSailTargets] = useState({});
  const [edits, setEdits] = useState({});
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [recalculating, setRecalculating] = useState(false);
  const [status, setStatus] = useState(null);
  const [bfCalcDetails, setBfCalcDetails] = useState({});
  const [smsCalcDetails, setSmsCalcDetails] = useState({});
  const [prodMetadata, setProdMetadata] = useState(null);

  // Load parameters and targets
  const handleLoad = useCallback(async () => {
    setLoading(true);
    setStatus(null);
    try {
      const [paramsRes, plantRes, smsRes, sailRes] = await Promise.all([
        fetch(`${API_BASE_URL}/api/techno-major-parameters`),
        fetch(`${API_BASE_URL}/api/techno-plant-targets?fy=${encodeURIComponent(fy)}`),
        fetch(`${API_BASE_URL}/api/techno-sms-targets?fy=${encodeURIComponent(fy)}`),
        fetch(`${API_BASE_URL}/api/techno-sail-targets?fy=${encodeURIComponent(fy)}`),
      ]);

      if (!paramsRes.ok || !plantRes.ok || !smsRes.ok || !sailRes.ok) {
        throw new Error('Failed to load data');
      }

      const paramsData = await paramsRes.json();
      const plantData = await plantRes.json();
      const smsData = await smsRes.json();
      const sailData = await sailRes.json();

      setBfParams(paramsData.bf_params || []);
      setSmsParams(paramsData.sms_params || []);
      setSmsShops(paramsData.sms_shops || []);
      setPlantTargets(plantData.plants || {});
      setSmsTargets(smsData.sms_shops || {});
      setSailTargets(sailData.targets || {});

      // Initialize edits
      const initialEdits = {};
      Object.entries(plantData.plants || {}).forEach(([plant, params]) => {
        Object.entries(params || {}).forEach(([param, value]) => {
          initialEdits[`plant|${plant}|${param}`] = value?.toString() || '';
        });
      });
      Object.entries(smsData.sms_shops || {}).forEach(([shop, params]) => {
        Object.entries(params || {}).forEach(([param, value]) => {
          initialEdits[`sms|${shop}|${param}`] = value?.toString() || '';
        });
      });
      Object.entries(sailData.targets || {}).forEach(([param, value]) => {
        initialEdits[`sail|${param}`] = value?.toString() || '';
      });
      setEdits(initialEdits);
    } catch (err) {
      setStatus({ type: 'error', text: `Load failed: ${err.message}` });
    } finally {
      setLoading(false);
    }
  }, [fy]);

  useEffect(() => {
    handleLoad();
  }, [fy, handleLoad]);

  const handleChange = (type, key1, key2, value) => {
    const fullKey = type === 'plant' ? `plant|${key1}|${key2}` :
                    type === 'sms' ? `sms|${key1}|${key2}` :
                    `sail|${key1}`;

    const newEdits = { ...edits, [fullKey]: value };

    // Auto-calculate derived values
    if (type === 'plant') {
      // Calculate Fuel Rate = Coke Rate + Nut Coke Rate + CDI Rate
      if (['Coke Rate', 'Nut Coke Rate', 'CDI Rate'].includes(key2)) {
        const coke = parseFloat(newEdits[`plant|${key1}|Coke Rate`]) || 0;
        const nutCoke = parseFloat(newEdits[`plant|${key1}|Nut Coke Rate`]) || 0;
        const cdi = parseFloat(newEdits[`plant|${key1}|CDI Rate`]) || 0;
        if (coke > 0 || nutCoke > 0 || cdi > 0) {
          newEdits[`plant|${key1}|Fuel Rate`] = (coke + nutCoke + cdi).toFixed(3);
        }
      }
    } else if (type === 'sms') {
      // Calculate TMI = HM Consumption + Scrap Consumption
      if (['Hot Metal Consumption', 'Scrap Consumption'].includes(key2)) {
        const hm = parseFloat(newEdits[`sms|${key1}|Hot Metal Consumption`]) || 0;
        const scrap = parseFloat(newEdits[`sms|${key1}|Scrap Consumption`]) || 0;
        if (hm > 0 || scrap > 0) {
          newEdits[`sms|${key1}|TMI`] = (hm + scrap).toFixed(3);
        }
      }
    }

    setEdits(newEdits);
  };

  const handleRecalculate = async () => {
    setRecalculating(true);
    setStatus(null);
    try {
      const res = await fetch(`${API_BASE_URL}/api/techno-recalculate-sail-weighted`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ fy }),
      });

      if (!res.ok) throw new Error(await res.text());
      const result = await res.json();

      const newEdits = { ...edits };
      Object.entries(result.sail_bf || {}).forEach(([param, value]) => {
        newEdits[`sail|${param}`] = value?.toString() || '';
      });
      Object.entries(result.sail_sms || {}).forEach(([param, value]) => {
        newEdits[`sail|${param}`] = value?.toString() || '';
      });
      setEdits(newEdits);
      setBfCalcDetails(result.bf_calculations || {});
      setSmsCalcDetails(result.sms_calculations || {});
      setProdMetadata(result.production_metadata || null);
      setStatus({ type: 'success', text: 'SAIL targets recalculated using HM/CS production weights' });
    } catch (err) {
      setStatus({ type: 'error', text: `Recalculation failed: ${err.message}` });
    } finally {
      setRecalculating(false);
    }
  };

  const handleSave = async () => {
    setSaving(true);
    setStatus(null);

    const plantData = {};
    const smsData = {};
    const sailData = {};

    Object.entries(edits).forEach(([key, val]) => {
      if (val === '' || val === null) return;
      try {
        const numVal = parseFloat(val);
        const parts = key.split('|');

        if (parts[0] === 'plant') {
          const [, plant, param] = parts;
          if (!plantData[plant]) plantData[plant] = {};
          plantData[plant][param] = numVal;
        } else if (parts[0] === 'sms') {
          const [, shop, param] = parts;
          if (!smsData[shop]) smsData[shop] = {};
          smsData[shop][param] = numVal;
        } else if (parts[0] === 'sail') {
          const [, param] = parts;
          sailData[param] = numVal;
        }
      } catch {
        // Skip invalid values
      }
    });

    try {
      const requests = [];

      if (Object.keys(plantData).length > 0) {
        requests.push(
          fetch(`${API_BASE_URL}/api/techno-plant-targets`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ fy, plants: plantData }),
          })
        );
      }

      if (Object.keys(smsData).length > 0) {
        requests.push(
          fetch(`${API_BASE_URL}/api/techno-sms-targets`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ fy, sms_shops: smsData }),
          })
        );
      }

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

      setStatus({ type: 'success', text: `Saved all targets for FY ${fy}` });
      setPlantTargets(plantData);
      setSmsTargets(smsData);
      setSailTargets(sailData);
    } catch (err) {
      setStatus({ type: 'error', text: `Save failed: ${err.message}` });
    } finally {
      setSaving(false);
    }
  };

  const getValue = (type, key1, key2) => {
    if (type === 'plant') return edits[`plant|${key1}|${key2}`] ?? '';
    if (type === 'sms') return edits[`sms|${key1}|${key2}`] ?? '';
    return edits[`sail|${key1}`] ?? '';
  };

  const getSavedValue = (type, key1, key2) => {
    if (type === 'plant') return plantTargets[key1]?.[key2];
    if (type === 'sms') return smsTargets[key1]?.[key2];
    return sailTargets[key1];
  };

  const isChanged = (type, key1, key2) => {
    return getValue(type, key1, key2) !== getSavedValue(type, key1, key2)?.toString();
  };

  const hasChanges = () => {
    return Object.values(edits).some(v => v !== '');
  };

  const renderCalcDetails = (param, calcData) => {
    if (!calcData) return null;

    if (param === 'Coke Rate') {
      return (
        <div style={{ padding: '12px 16px', backgroundColor: '#f0f9ff', borderTop: '1px solid #e0e7ff' }}>
          <div style={{ fontSize: '10pt', fontWeight: '600', color: '#0c4a6e', marginBottom: '8px' }}>{calcData.formula}</div>
          <table style={{ width: '100%', fontSize: '9pt', borderCollapse: 'collapse' }}>
            <thead>
              <tr style={{ borderBottom: '1px solid #cbd5e1' }}>
                <th style={{ padding: '4px 8px', textAlign: 'left' }}>Plant</th>
                <th style={{ padding: '4px 8px', textAlign: 'right' }}>Value</th>
                <th style={{ padding: '4px 8px', textAlign: 'right' }}>HM Weight</th>
                <th style={{ padding: '4px 8px', textAlign: 'right' }}>Product</th>
              </tr>
            </thead>
            <tbody>
              {calcData.values?.map((v, i) => (
                <tr key={i} style={{ borderBottom: '1px solid #f1f5f9' }}>
                  <td style={{ padding: '4px 8px' }}>{v.plant}</td>
                  <td style={{ padding: '4px 8px', textAlign: 'right' }}>{v.value}</td>
                  <td style={{ padding: '4px 8px', textAlign: 'right' }}>{v.hm_weight}</td>
                  <td style={{ padding: '4px 8px', textAlign: 'right' }}>{v.product}</td>
                </tr>
              ))}
              <tr style={{ backgroundColor: '#e0f2fe', fontWeight: '600' }}>
                <td colSpan="2" style={{ padding: '6px 8px' }}>SAIL = Σ(Products) / Σ(Weights)</td>
                <td style={{ padding: '6px 8px', textAlign: 'right' }}>{calcData.sum_weights}</td>
                <td style={{ padding: '6px 8px', textAlign: 'right' }}>{calcData.sum_products} / {calcData.sum_weights} = <strong>{calcData.result}</strong></td>
              </tr>
            </tbody>
          </table>
        </div>
      );
    }

    if (param === 'BF Productivity') {
      return (
        <div style={{ padding: '12px 16px', backgroundColor: '#f0f9ff', borderTop: '1px solid #e0e7ff' }}>
          <div style={{ fontSize: '10pt', fontWeight: '600', color: '#0c4a6e', marginBottom: '8px' }}>{calcData.formula}</div>
          <table style={{ width: '100%', fontSize: '9pt', borderCollapse: 'collapse' }}>
            <thead>
              <tr style={{ borderBottom: '1px solid #cbd5e1' }}>
                <th style={{ padding: '4px 8px', textAlign: 'left' }}>Plant</th>
                <th style={{ padding: '4px 8px', textAlign: 'right' }}>Productivity</th>
                <th style={{ padding: '4px 8px', textAlign: 'right' }}>HM Weight</th>
                <th style={{ padding: '4px 8px', textAlign: 'right' }}>Reciprocal (W/P)</th>
              </tr>
            </thead>
            <tbody>
              {calcData.values?.map((v, i) => (
                <tr key={i} style={{ borderBottom: '1px solid #f1f5f9' }}>
                  <td style={{ padding: '4px 8px' }}>{v.plant}</td>
                  <td style={{ padding: '4px 8px', textAlign: 'right' }}>{v.value}</td>
                  <td style={{ padding: '4px 8px', textAlign: 'right' }}>{v.hm_weight}</td>
                  <td style={{ padding: '4px 8px', textAlign: 'right' }}>{v.reciprocal}</td>
                </tr>
              ))}
              <tr style={{ backgroundColor: '#e0f2fe', fontWeight: '600' }}>
                <td colSpan="2" style={{ padding: '6px 8px' }}>SAIL = Total HM / Σ(Reciprocals)</td>
                <td style={{ padding: '6px 8px', textAlign: 'right' }}>{calcData.total_hm}</td>
                <td style={{ padding: '6px 8px', textAlign: 'right' }}>{calcData.total_hm} / {calcData.sum_reciprocal} = <strong>{calcData.result}</strong></td>
              </tr>
            </tbody>
          </table>
        </div>
      );
    }

    if (param === 'Hot Metal Consumption' || param === 'Scrap Consumption') {
      return (
        <div style={{ padding: '12px 16px', backgroundColor: '#f0fdf4', borderTop: '1px solid #d1fae5' }}>
          <div style={{ fontSize: '10pt', fontWeight: '600', color: '#065f46', marginBottom: '8px' }}>{calcData.formula}</div>
          <div style={{ fontSize: '9pt', color: '#047857', marginBottom: '8px', fontStyle: 'italic' }}>{calcData.description}</div>
          <table style={{ width: '100%', fontSize: '9pt', borderCollapse: 'collapse' }}>
            <thead>
              <tr style={{ borderBottom: '1px solid #cbd5e1' }}>
                <th style={{ padding: '4px 8px', textAlign: 'left' }}>Shop</th>
                <th style={{ padding: '4px 8px', textAlign: 'left' }}>Plant</th>
                <th style={{ padding: '4px 8px', textAlign: 'right' }}>Value</th>
                <th style={{ padding: '4px 8px', textAlign: 'right' }}>CS Weight</th>
                <th style={{ padding: '4px 8px', textAlign: 'right' }}>Product</th>
              </tr>
            </thead>
            <tbody>
              {calcData.shops?.map((s, i) => (
                <tr key={i} style={{ borderBottom: '1px solid #f1f5f9' }}>
                  <td style={{ padding: '4px 8px' }}>{s.shop}</td>
                  <td style={{ padding: '4px 8px' }}>{s.plant}</td>
                  <td style={{ padding: '4px 8px', textAlign: 'right' }}>{s.value}</td>
                  <td style={{ padding: '4px 8px', textAlign: 'right' }}>{s.cs_weight}</td>
                  <td style={{ padding: '4px 8px', textAlign: 'right' }}>{s.product}</td>
                </tr>
              ))}
              <tr style={{ backgroundColor: '#dcfce7', fontWeight: '600' }}>
                <td colSpan="3" style={{ padding: '6px 8px' }}>SAIL = Σ(Products) / Σ(Weights)</td>
                <td style={{ padding: '6px 8px', textAlign: 'right' }}>{calcData.sum_weights}</td>
                <td style={{ padding: '6px 8px', textAlign: 'right' }}>{calcData.sum_products} / {calcData.sum_weights} = <strong>{calcData.result}</strong></td>
              </tr>
            </tbody>
          </table>
        </div>
      );
    }

    return null;
  };

  const isDerivedField = (type, key2) => {
    if (type === 'plant') return key2 === 'Fuel Rate';
    if (type === 'sms') return key2 === 'TMI';
    return false;
  };

  const renderCell = (type, key1, key2) => {
    const isDerived = isDerivedField(type, key2);
    const value = getValue(type, key1, key2);
    const saved = getSavedValue(type, key1, key2);
    const changed = isChanged(type, key1, key2);

    return (
      <div style={{ position: 'relative' }}>
        <input
          type="number"
          step="0.001"
          value={value}
          onChange={e => !isDerived && handleChange(type, key1, key2, e.target.value)}
          readOnly={isDerived}
          style={{
            width: '100%', padding: '6px 8px', fontSize: '10pt', textAlign: 'right',
            border: `1px solid ${isDerived ? '#cbd5e1' : changed ? '#fbbf24' : '#cbd5e1'}`,
            borderRadius: '4px',
            backgroundColor: isDerived ? '#f5f5f5' : changed ? '#fffbeb' : saved ? '#f0fdf4' : '#fff',
            color: isDerived ? '#9ca3af' : changed ? '#92400e' : saved ? '#065f46' : '#1e293b',
            cursor: isDerived ? 'not-allowed' : 'text'
          }}
          placeholder="–"
          title={isDerived ? 'Auto-calculated' : ''}
        />
        {isDerived && (
          <span style={{ position: 'absolute', right: '8px', top: '6px', fontSize: '8pt', color: '#9ca3af', pointerEvents: 'none' }}>🔒</span>
        )}
      </div>
    );
  };

  return (
    <div style={{ minHeight: '100vh', backgroundColor: '#f8fafc' }}>
      <GlobalNavbar />

      <main style={{ padding: '32px', maxWidth: '1400px', margin: '0 auto' }}>
        <div style={{ marginBottom: '32px' }}>
          <h1 style={{ fontSize: '24pt', fontWeight: '900', color: '#0f172a', margin: '0 0 8px 0' }}>
            📊 Techno-Economic Annual Targets
          </h1>
          <p style={{ fontSize: '11pt', color: '#64748b', margin: '0' }}>
            BF parameters weighted by HM production | SMS parameters weighted by Crude Steel production | SAIL auto-calculated
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
            <select value={fy} onChange={e => setFy(e.target.value)} style={{ padding: '8px 12px', fontSize: '11pt', borderRadius: '4px', border: '1px solid #cbd5e1' }}>
              {FY_LIST.map(f => <option key={f} value={f}>{f}</option>)}
            </select>
          </div>
          <button onClick={handleLoad} disabled={loading} style={{ padding: '8px 16px', fontSize: '11pt', fontWeight: '600', borderRadius: '4px', border: 'none', backgroundColor: '#6366f1', color: '#fff', cursor: 'pointer', marginTop: '18px' }}>
            {loading ? 'Loading...' : 'Load'}
          </button>
          <button onClick={handleRecalculate} disabled={recalculating || (bfParams.length === 0 && smsParams.length === 0)} style={{ padding: '8px 16px', fontSize: '11pt', fontWeight: '600', borderRadius: '4px', border: 'none', backgroundColor: '#0891b2', color: '#fff', cursor: 'pointer', marginTop: '18px' }}>
            {recalculating ? 'Calculating...' : 'Recalculate SAIL'}
          </button>
          <button onClick={handleSave} disabled={saving || !hasChanges()} style={{ padding: '8px 16px', fontSize: '11pt', fontWeight: '600', borderRadius: '4px', border: 'none', backgroundColor: hasChanges() ? '#10b981' : '#94a3b8', color: '#fff', cursor: hasChanges() ? 'pointer' : 'default', marginTop: '18px' }}>
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

        {/* Production Data Source */}
        {prodMetadata && (
          <div style={{
            padding: '12px 16px', marginBottom: '16px', borderRadius: '6px', fontSize: '10pt',
            backgroundColor: '#f0f9ff', color: '#0c4a6e', border: '1px solid #e0e7ff'
          }}>
            <div style={{ fontWeight: '600', marginBottom: '8px' }}>📊 Production Plan Data Source</div>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px' }}>
              <div>
                <strong>Source Table:</strong> production_plan_table
              </div>
              <div>
                <strong>Financial Year:</strong> {prodMetadata.fy}
              </div>
              <div>
                <strong>HM Weight (item):</strong> {prodMetadata.hm_item}
              </div>
              <div>
                <strong>CS Weight (item):</strong> {prodMetadata.cs_item}
              </div>
            </div>
            <div style={{ marginTop: '8px', paddingTop: '8px', borderTop: '1px solid #e0e7ff' }}>
              <strong>Months Included (FY {prodMetadata.fy}):</strong>
              <div style={{ fontSize: '9pt', color: '#0c4a6e', marginTop: '4px' }}>
                {prodMetadata.months_included?.join(' • ')}
              </div>
            </div>
            <div style={{ marginTop: '8px', paddingTop: '8px', borderTop: '1px solid #e0e7ff' }}>
              <strong>HM Production by Plant (Annual):</strong>
              <div style={{ fontSize: '9pt', display: 'grid', gridTemplateColumns: 'repeat(5, 1fr)', gap: '8px', marginTop: '4px' }}>
                {Object.entries(prodMetadata.hm_weights || {}).map(([plant, weight]) => (
                  <div key={plant} style={{ padding: '4px 8px', backgroundColor: '#e0f2fe', borderRadius: '4px' }}>
                    {plant}: {weight.toLocaleString()}
                  </div>
                ))}
              </div>
            </div>
            <div style={{ marginTop: '8px', paddingTop: '8px', borderTop: '1px solid #e0e7ff' }}>
              <strong>CS Production by Plant (Annual):</strong>
              <div style={{ fontSize: '9pt', display: 'grid', gridTemplateColumns: 'repeat(5, 1fr)', gap: '8px', marginTop: '4px' }}>
                {Object.entries(prodMetadata.cs_weights || {}).map(([plant, weight]) => (
                  <div key={plant} style={{ padding: '4px 8px', backgroundColor: '#e0f2fe', borderRadius: '4px' }}>
                    {plant}: {weight.toLocaleString()}
                  </div>
                ))}
              </div>
            </div>
            <div style={{ marginTop: '8px', paddingTop: '8px', borderTop: '1px solid #e0e7ff' }}>
              <strong>SMS Shop-wise Crude Steel Production (Weighted Average):</strong>
              <div style={{ fontSize: '9pt', marginTop: '4px' }}>
                <div style={{ marginBottom: '8px', padding: '8px', backgroundColor: '#e0f2fe', borderRadius: '4px', fontStyle: 'italic' }}>
                  Multi-shop plants use specific SMS items | Single-shop plants (DSP, ISP) use Total Crude Steel
                </div>
                {Object.entries(prodMetadata.shop_to_plant || {}).map(([shop, plant]) => {
                  const weight = prodMetadata.shop_cs_weights?.[shop];
                  const isSingleShop = ['DSP', 'ISP'].includes(plant);
                  const source = isSingleShop ? 'Total Crude Steel' : `${shop}`;
                  return (
                    <div key={shop} style={{ padding: '6px 8px', backgroundColor: '#bfdbfe', borderRadius: '3px', marginBottom: '4px' }}>
                      <strong>{shop}</strong>
                      <div style={{ fontSize: '8pt', color: '#0c4a6e', marginTop: '2px' }}>
                        Source: {source} | Weight: {weight?.toLocaleString() || '0'}
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          </div>
        )}

        {/* BF Parameters Table */}
        {bfParams.length > 0 && (
          <div style={{ marginBottom: '32px' }}>
            <h2 style={{ fontSize: '14pt', fontWeight: '700', color: '#1e293b', marginBottom: '12px' }}>⚒️ BF / Iron-Making Parameters</h2>
            <p style={{ fontSize: '10pt', color: '#64748b', marginBottom: '12px' }}>Weighted by Plant Hot Metal Production Target</p>
            <div style={{ backgroundColor: '#fff', borderRadius: '8px', border: '1px solid #e2e8f0', overflow: 'hidden', maxHeight: 'calc(100vh - 400px)', display: 'flex', flexDirection: 'column' }}>
              <div style={{ overflowX: 'auto', overflowY: 'auto', flex: 1 }}>
                <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                  <thead style={{ position: 'sticky', top: 0, zIndex: 10 }}>
                    <tr style={{ backgroundColor: '#1e3a5f', color: '#fff' }}>
                      <th style={{ padding: '12px 16px', textAlign: 'left', fontWeight: '700', fontSize: '11pt' }}>Parameter</th>
                      <th style={{ padding: '12px 16px', textAlign: 'center', fontWeight: '700', fontSize: '11pt', minWidth: '80px' }}>Unit</th>
                      {PLANTS.map(plant => (
                        <th key={plant} style={{ padding: '12px 16px', textAlign: 'center', fontWeight: '700', fontSize: '11pt', backgroundColor: plant === 'SAIL' ? '#166534' : '#1e3a5f', minWidth: '110px' }}>
                          {plant}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {bfParams.map((param, idx) => (
                      <tr key={param.name} style={{ borderBottom: '1px solid #e2e8f0', backgroundColor: idx % 2 === 0 ? '#f8fafc' : '#fff' }}>
                        <td style={{ padding: '10px 16px', fontSize: '11pt', fontWeight: '500', color: '#1e293b' }}>{param.name}</td>
                        <td style={{ padding: '10px 16px', textAlign: 'center', fontSize: '10pt', color: '#475569' }}>{param.unit}</td>
                        {PLANTS.map(plant => (
                          <td key={`${plant}-${param.name}`} style={{ padding: '8px 12px', textAlign: 'right' }}>
                            {plant === 'SAIL' ? renderCell('sail', param.name, null) : renderCell('plant', plant, param.name)}
                          </td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
            {/* BF Calculation Details */}
            {(bfCalcDetails['Coke Rate'] || bfCalcDetails['BF Productivity']) && (
              <div style={{ marginTop: '16px' }}>
                <h3 style={{ fontSize: '11pt', fontWeight: '600', color: '#0c4a6e', margin: '0 0 12px 0' }}>📐 Calculation Details</h3>
                {bfCalcDetails['Coke Rate'] && (
                  <div style={{ marginBottom: '12px' }}>
                    <div style={{ fontSize: '10pt', fontWeight: '600', color: '#0c4a6e', marginBottom: '8px' }}>Coke Rate SAIL</div>
                    {renderCalcDetails('Coke Rate', bfCalcDetails['Coke Rate'])}
                  </div>
                )}
                {bfCalcDetails['BF Productivity'] && (
                  <div>
                    <div style={{ fontSize: '10pt', fontWeight: '600', color: '#0c4a6e', marginBottom: '8px' }}>BF Productivity SAIL</div>
                    {renderCalcDetails('BF Productivity', bfCalcDetails['BF Productivity'])}
                  </div>
                )}
              </div>
            )}
          </div>
        )}

        {/* SMS Parameters Table */}
        {smsParams.length > 0 && (
          <div>
            <h2 style={{ fontSize: '14pt', fontWeight: '700', color: '#1e293b', marginBottom: '12px' }}>🏭 SMS / Steel Making Parameters</h2>
            <p style={{ fontSize: '10pt', color: '#64748b', marginBottom: '12px' }}>Shop-wise values with SAIL as weighted average by Crude Steel Production</p>
            <div style={{ backgroundColor: '#fff', borderRadius: '8px', border: '1px solid #e2e8f0', overflow: 'hidden', maxHeight: 'calc(100vh - 400px)', display: 'flex', flexDirection: 'column' }}>
              <div style={{ overflowX: 'auto', overflowY: 'auto', flex: 1 }}>
                <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                  <thead style={{ position: 'sticky', top: 0, zIndex: 10 }}>
                    <tr style={{ backgroundColor: '#1e3a5f', color: '#fff' }}>
                      <th style={{ padding: '12px 16px', textAlign: 'left', fontWeight: '700', fontSize: '11pt', minWidth: '150px' }}>SMS Shop</th>
                      {smsParams.map(param => (
                        <th key={param.name} style={{ padding: '12px 16px', textAlign: 'center', fontWeight: '700', fontSize: '11pt', minWidth: '120px' }}>
                          {param.name}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {smsShops.map((shop, idx) => (
                      <tr key={shop} style={{ borderBottom: '1px solid #e2e8f0', backgroundColor: idx % 2 === 0 ? '#f8fafc' : '#fff' }}>
                        <td style={{ padding: '10px 16px', fontSize: '11pt', fontWeight: '500', color: '#1e293b' }}>{shop}</td>
                        {smsParams.map(param => (
                          <td key={`${shop}-${param.name}`} style={{ padding: '8px 12px', textAlign: 'right' }}>
                            {renderCell('sms', shop, param.name)}
                          </td>
                        ))}
                      </tr>
                    ))}
                    {/* SAIL Row */}
                    <tr style={{ borderBottom: 'none', backgroundColor: '#f0fdf4', borderTop: '2px solid #e2e8f0' }}>
                      <td style={{ padding: '10px 16px', fontSize: '11pt', fontWeight: '700', color: '#166534', backgroundColor: '#ecfdf5' }}>SAIL</td>
                      {smsParams.map(param => (
                        <td key={`sail-${param.name}`} style={{ padding: '8px 12px', textAlign: 'right' }}>
                          {renderCell('sail', param.name, null)}
                        </td>
                      ))}
                    </tr>
                  </tbody>
                </table>
              </div>
            </div>
            {/* SMS Calculation Details */}
            {(smsCalcDetails['Hot Metal Consumption'] || smsCalcDetails['Scrap Consumption']) && (
              <div style={{ marginTop: '16px' }}>
                <h3 style={{ fontSize: '11pt', fontWeight: '600', color: '#065f46', margin: '0 0 12px 0' }}>📐 Calculation Details</h3>
                {smsCalcDetails['Hot Metal Consumption'] && (
                  <div style={{ marginBottom: '12px' }}>
                    <div style={{ fontSize: '10pt', fontWeight: '600', color: '#065f46', marginBottom: '8px' }}>HM Consumption SAIL</div>
                    {renderCalcDetails('Hot Metal Consumption', smsCalcDetails['Hot Metal Consumption'])}
                  </div>
                )}
                {smsCalcDetails['Scrap Consumption'] && (
                  <div>
                    <div style={{ fontSize: '10pt', fontWeight: '600', color: '#065f46', marginBottom: '8px' }}>Scrap Consumption SAIL</div>
                    {renderCalcDetails('Scrap Consumption', smsCalcDetails['Scrap Consumption'])}
                  </div>
                )}
              </div>
            )}
          </div>
        )}
      </main>
    </div>
  );
}
