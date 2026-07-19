'use client';
import React, { useState, useEffect } from 'react';
import GlobalNavbar from '@/components/GlobalNavbar';
import { LineChart, Line, BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer, ScatterChart, Scatter } from 'recharts';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || '';
const FY_LIST = ['2023-24', '2024-25', '2025-26', '2026-27', '2027-28', '2028-29'];

export default function TechnoSummaryPage() {
  const [fy, setFy] = useState('2026-27');
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const handleLoad = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`${API_BASE_URL}/api/techno-summary?fy=${fy}`);
      if (!res.ok) throw new Error('Failed to load techno summary');
      const result = await res.json();
      setData(result);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    handleLoad();
  }, [fy]);

  if (!data) {
    return (
      <div style={{ height: '100vh', display: 'flex', flexDirection: 'column', backgroundColor: '#ffffff' }}>
        <GlobalNavbar />
        <main style={{ flex: 1, overflow: 'auto', padding: '32px', maxWidth: '1400px', margin: '0 auto', width: '100%' }}>
          <h1 style={{ fontSize: '28pt', fontWeight: '900', color: '#202124' }}>📊 Techno Performance Summary</h1>
          <div style={{ marginBottom: '24px' }}>
            <label style={{ fontSize: '13pt', fontWeight: '600' }}>Financial Year: </label>
            <select value={fy} onChange={e => setFy(e.target.value)} style={{ padding: '8px 12px', fontSize: '13pt', borderRadius: '4px', border: '1px solid #dadce0', marginLeft: '8px' }}>
              {FY_LIST.map(f => <option key={f} value={f}>{f}</option>)}
            </select>
          </div>
          {loading && <p style={{ fontSize: '13pt' }}>Loading...</p>}
          {error && <p style={{ fontSize: '13pt', color: 'red' }}>Error: {error}</p>}
        </main>
      </div>
    );
  }

  // Prepare BF parameter comparison data
  const bfParams = ['Coke Rate', 'BF Productivity', 'Hot Metal Productivity'];
  const bfChartData = [];
  const plants = ['BSP', 'DSP', 'RSP', 'BSL', 'ISP'];

  plants.forEach(plant => {
    const record = { plant };
    bfParams.forEach(param => {
      const value = data.bf_targets[plant]?.[param]?.value || data.bf_targets[plant]?.[param];
      if (value !== undefined) {
        record[param] = parseFloat(value);
      }
    });
    if (Object.keys(record).length > 1) bfChartData.push(record);
  });

  // Prepare SMS parameter comparison data
  const smsParams = ['Hot Metal Consumption', 'Scrap Consumption'];
  const smsChartData = [];
  const smsShops = [
    "BSP SMS-2", "BSP SMS-3",
    "DSP SMS",
    "RSP SMS-1", "RSP SMS-2",
    "BSL SMS-1", "BSL SMS-2",
    "ISP SMS-1",
  ];

  smsShops.forEach(shop => {
    const record = { shop };
    smsParams.forEach(param => {
      const value = data.sms_targets[shop]?.[param]?.value || data.sms_targets[shop]?.[param];
      if (value !== undefined) {
        record[param] = parseFloat(value);
      }
    });
    if (Object.keys(record).length > 1) smsChartData.push(record);
  });

  return (
    <div style={{ height: '100vh', display: 'flex', flexDirection: 'column', backgroundColor: '#ffffff' }}>
      <GlobalNavbar />
      <main style={{ flex: 1, overflow: 'auto', padding: '32px', maxWidth: '1600px', margin: '0 auto', width: '100%' }}>

        {/* Header */}
        <div style={{ marginBottom: '32px' }}>
          <h1 style={{ fontSize: '28pt', fontWeight: '900', color: '#202124', margin: '0 0 8px 0' }}>
            📊 Techno Performance Summary
          </h1>
          <p style={{ fontSize: '13pt', color: '#5f6368', margin: '0' }}>
            FY {fy} | Plant-wise and SMS-wise Techno Targets with Production Context
          </p>
        </div>

        {/* Controls */}
        <div style={{ backgroundColor: '#fff', padding: '16px', borderRadius: '8px', border: '1px solid #dadce0', marginBottom: '24px' }}>
          <label style={{ fontSize: '13pt', fontWeight: '600', color: '#5f6368', marginRight: '12px' }}>
            Financial Year:
          </label>
          <select value={fy} onChange={e => setFy(e.target.value)} style={{ padding: '8px 12px', fontSize: '13pt', borderRadius: '4px', border: '1px solid #dadce0' }}>
            {FY_LIST.map(f => <option key={f} value={f}>{f}</option>)}
          </select>
          <button onClick={handleLoad} style={{ marginLeft: '12px', padding: '8px 16px', fontSize: '13pt', fontWeight: '600', borderRadius: '4px', border: 'none', backgroundColor: '#6366f1', color: '#fff', cursor: 'pointer' }}>
            Reload
          </button>
        </div>

        {/* BF Parameters Chart */}
        {bfChartData.length > 0 && (
          <div style={{ backgroundColor: '#fff', borderRadius: '8px', border: '1px solid #dadce0', padding: '24px', marginBottom: '24px' }}>
            <h2 style={{ fontSize: '16pt', fontWeight: '700', color: '#202124', marginBottom: '16px' }}>
              🏭 BF Parameters by Plant
            </h2>
            <ResponsiveContainer width="100%" height={300}>
              <BarChart data={bfChartData}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="plant" />
                <YAxis />
                <Tooltip />
                <Legend />
                {bfParams.map((param, i) => (
                  <Bar key={param} dataKey={param} fill={['#3b82f6', '#10b981', '#f59e0b'][i % 3]} />
                ))}
              </BarChart>
            </ResponsiveContainer>
          </div>
        )}

        {/* SMS Parameters Chart */}
        {smsChartData.length > 0 && (
          <div style={{ backgroundColor: '#fff', borderRadius: '8px', border: '1px solid #dadce0', padding: '24px', marginBottom: '24px' }}>
            <h2 style={{ fontSize: '16pt', fontWeight: '700', color: '#202124', marginBottom: '16px' }}>
              ⚙️ SMS Parameters by Shop
            </h2>
            <ResponsiveContainer width="100%" height={300}>
              <ScatterChart data={smsChartData}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="shop" />
                <YAxis />
                <Tooltip />
                <Legend />
                <Scatter name="HM Consumption" dataKey="Hot Metal Consumption" fill="#ef4444" />
                <Scatter name="Scrap Consumption" dataKey="Scrap Consumption" fill="#0ea5e9" />
              </ScatterChart>
            </ResponsiveContainer>
          </div>
        )}

        {/* SAIL Targets Summary */}
        {data.sail_targets && (
          <div style={{ backgroundColor: '#f0fdf4', borderRadius: '8px', border: '1px solid #d1fae5', padding: '24px', marginBottom: '24px' }}>
            <h2 style={{ fontSize: '16pt', fontWeight: '700', color: '#065f46', marginBottom: '16px' }}>
              🎯 SAIL Consolidated Targets
            </h2>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '16px' }}>
              {Object.entries(data.sail_targets).slice(0, 8).map(([param, value]) => (
                <div key={param} style={{ padding: '12px', backgroundColor: '#ecfdf5', borderRadius: '4px', border: '1px solid #a7f3d0' }}>
                  <div style={{ fontSize: '11pt', fontWeight: '600', color: '#065f46' }}>{param}</div>
                  <div style={{ fontSize: '16pt', fontWeight: '700', color: '#059669', marginTop: '4px' }}>
                    {typeof value === 'object' ? value.value || value : value}
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Production Context */}
        {data.production_context && (
          <div style={{ backgroundColor: '#f0f9ff', borderRadius: '8px', border: '1px solid #e0e7ff', padding: '24px' }}>
            <h2 style={{ fontSize: '16pt', fontWeight: '700', color: '#174ea6', marginBottom: '16px' }}>
              📈 Production Context
            </h2>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: '24px' }}>
              <div>
                <h3 style={{ fontSize: '13pt', fontWeight: '600', color: '#174ea6', marginBottom: '12px' }}>HM Production by Plant</h3>
                {Object.entries(data.production_context.hm_weights).map(([plant, weight]) => (
                  <div key={plant} style={{ fontSize: '12pt', padding: '4px 0', color: '#064e3b' }}>
                    {plant}: {weight?.toLocaleString() || '—'}
                  </div>
                ))}
              </div>
              <div>
                <h3 style={{ fontSize: '13pt', fontWeight: '600', color: '#174ea6', marginBottom: '12px' }}>CS Production by SMS Shop</h3>
                {Object.entries(data.production_context.sms_cs_weights).slice(0, 8).map(([shop, weight]) => (
                  <div key={shop} style={{ fontSize: '12pt', padding: '4px 0', color: '#064e3b' }}>
                    {shop}: {weight?.toLocaleString() || '—'}
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}

      </main>
    </div>
  );
}
