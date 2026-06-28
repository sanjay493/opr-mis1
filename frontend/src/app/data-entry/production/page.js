'use client';

import React, { useState, useCallback, useMemo } from 'react';
import GlobalNavbar from '@/components/GlobalNavbar';

const PLANTS = ['BSP', 'DSP', 'ISP', 'RSP', 'BSL', 'ASP', 'SSP', 'VISL'];
const MONTHS = [
  'April', 'May', 'June', 'July', 'August', 'September',
  'October', 'November', 'December', 'January', 'February', 'March'
];

const MONTH_NUM = {
  'January': '01', 'February': '02', 'March': '03', 'April': '04',
  'May': '05', 'June': '06', 'July': '07', 'August': '08',
  'September': '09', 'October': '10', 'November': '11', 'December': '12',
};
const YEARS = Array.from({ length: 8 }, (_, i) => (2023 + i).toString());

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://127.0.0.1:8082';

function getDefaultPeriod() {
  const d = new Date();
  d.setMonth(d.getMonth() - 1);
  return { month: MONTHS[d.getMonth()], year: d.getFullYear().toString() };
}

export default function ProductionDataEntryPage() {
  const defaultPeriod = getDefaultPeriod();
  const [plant, setPlant] = useState('BSP');
  const [month, setMonth] = useState(defaultPeriod.month);
  const [year, setYear] = useState(defaultPeriod.year);
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [status, setStatus] = useState(null);
  const [loaded, setLoaded] = useState(false);

  const reportMonth = `${year}-${MONTH_NUM[month]}`;
  const reportMonthDisplay = `${month} ${year}`;

  const handleLoad = useCallback(async () => {
    setLoading(true);
    setStatus(null);
    setLoaded(false);
    try {
      const res = await fetch(
        `${API_BASE_URL}/api/production-items?plant=${encodeURIComponent(plant)}&month=${encodeURIComponent(reportMonth)}`
      );
      if (!res.ok) throw new Error(await res.text());
      const data = await res.json();
      if (data.items.length === 0) {
        setStatus({ type: 'error', text: `No plan items found for ${plant} in ${reportMonthDisplay}. Upload ABP plan first.` });
        setItems([]);
      } else {
        setItems(data.items.map(it => ({
          item_name: it.item_name,
          plan_value: it.plan_value ?? '',
          actual_value: it.actual_value ?? '',
          plan_edit: String(it.plan_value ?? ''),
          actual_edit: String(it.actual_value ?? ''),
        })));
        setLoaded(true);
      }
    } catch (err) {
      setStatus({ type: 'error', text: `Load failed: ${err.message}` });
    } finally {
      setLoading(false);
    }
  }, [plant, reportMonth]);

  const handleActualChange = (idx, val) => {
    setItems(prev => prev.map((it, i) => i === idx ? { ...it, actual_edit: val } : it));
  };

  const handlePlanChange = (idx, val) => {
    setItems(prev => prev.map((it, i) => i === idx ? { ...it, plan_edit: val } : it));
  };

  const handleSave = async () => {
    setSaving(true);
    setStatus(null);
    const entries = items.map(it => ({
      item_name: it.item_name,
      actual_value: it.actual_edit !== '' && it.actual_edit !== null ? parseFloat(it.actual_edit) : null,
      plan_value: it.plan_edit !== '' && it.plan_edit !== null ? parseFloat(it.plan_edit) : null,
    })).filter(e => e.actual_value !== null || e.plan_value !== null);

    try {
      const res = await fetch(`${API_BASE_URL}/api/production-entry`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ plant, month: reportMonth, entries }),
      });
      if (!res.ok) throw new Error(await res.text());
      const result = await res.json();
      setStatus({ type: 'success', text: `Saved ${result.count} value(s) for ${plant} — ${reportMonthDisplay}.` });
      await handleLoad();
    } catch (err) {
      setStatus({ type: 'error', text: `Save failed: ${err.message}` });
    } finally {
      setSaving(false);
    }
  };

  const hasChanges = items.some(it =>
    it.actual_edit !== String(it.actual_value ?? '') ||
    it.plan_edit !== String(it.plan_value ?? '')
  );

  return (
    <div style={{
      height: '100vh',
      backgroundColor: '#f8fafc',
      display: 'flex',
      flexDirection: 'column',
      overflow: 'hidden'
    }}>
      <GlobalNavbar />

      <div style={{ flex: 1, overflow: 'auto', padding: '40px 32px', display: 'flex', flexDirection: 'column' }}>
        <div style={{ maxWidth: '1000px', margin: '0 auto', width: '100%', flex: 1, display: 'flex', flexDirection: 'column' }}>
          <div style={{ marginBottom: '32px', flexShrink: 0 }}>
            <h1 style={{ fontSize: '28pt', fontWeight: '800', color: '#0f172a', margin: '0 0 4px 0' }}>
              📊 Production Data Entry
            </h1>
            <p style={{ fontSize: '14pt', color: '#64748b', margin: '0 0 16px 0' }}>
              Enter actual production values for each item. Plan values come from the uploaded ABP and can also be edited.
            </p>

            <div style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))',
              gap: '16px',
              marginBottom: '16px'
            }}>
              <div>
                <label style={{ fontSize: '13pt', fontWeight: '600', color: '#475569', display: 'block', marginBottom: '6px' }}>Plant</label>
                <select
                  value={plant}
                  onChange={e => { setPlant(e.target.value); setLoaded(false); setItems([]); }}
                  style={{ padding: '10px 14px', fontSize: '13pt', width: '100%', borderRadius: '4px', border: '1px solid #cbd5e1' }}
                >
                  {PLANTS.map(p => <option key={p} value={p}>{p}</option>)}
                </select>
              </div>

              <div>
                <label style={{ fontSize: '13pt', fontWeight: '600', color: '#475569', display: 'block', marginBottom: '6px' }}>Month</label>
                <select
                  value={month}
                  onChange={e => { setMonth(e.target.value); setLoaded(false); setItems([]); }}
                  style={{ padding: '10px 14px', fontSize: '13pt', width: '100%', borderRadius: '4px', border: '1px solid #cbd5e1' }}
                >
                  {MONTHS.map(m => <option key={m} value={m}>{m}</option>)}
                </select>
              </div>

              <div>
                <label style={{ fontSize: '13pt', fontWeight: '600', color: '#475569', display: 'block', marginBottom: '6px' }}>Year</label>
                <select
                  value={year}
                  onChange={e => { setYear(e.target.value); setLoaded(false); setItems([]); }}
                  style={{ padding: '10px 14px', fontSize: '13pt', width: '100%', borderRadius: '4px', border: '1px solid #cbd5e1' }}
                >
                  {YEARS.map(y => <option key={y} value={y}>{y}</option>)}
                </select>
              </div>

              <div style={{ display: 'flex', alignItems: 'flex-end' }}>
                <button
                  style={{ width: '100%', backgroundColor: '#6366f1', color: '#fff', border: 'none', padding: '10px 14px', fontSize: '13pt', borderRadius: '4px', fontWeight: '600', cursor: 'pointer' }}
                  onClick={handleLoad}
                  disabled={loading}
                >
                  {loading ? 'Loading...' : 'Load Items'}
                </button>
              </div>
            </div>

            {status && (
              <div style={{
                padding: '14px 18px',
                marginBottom: '16px',
                borderRadius: '6px',
                fontSize: '13pt',
                backgroundColor: status.type === 'success' ? '#dcfce7' : '#fee2e2',
                color: status.type === 'success' ? '#166534' : '#991b1b',
                border: `1px solid ${status.type === 'success' ? '#bbf7d0' : '#fecaca'}`
              }}>
                {status.text}
              </div>
            )}

            {loaded && items.length > 0 && (
              <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
                <div style={{ flex: 1, overflowX: 'auto', overflowY: 'auto', marginBottom: '16px', border: '1px solid #e2e8f0', borderRadius: '6px' }}>
                  <table style={{ width: '100%', borderCollapse: 'collapse', backgroundColor: '#fff' }}>
                    <thead style={{ position: 'sticky', top: 0, zIndex: 10 }}>
                      <tr style={{ backgroundColor: '#f1f5f9', borderBottom: '1px solid #e2e8f0' }}>
                        <th style={{ padding: '12px 14px', textAlign: 'left', fontWeight: '700', fontSize: '12pt', color: '#475569' }}>Item</th>
                        <th style={{ padding: '12px 14px', textAlign: 'right', fontWeight: '700', fontSize: '12pt', color: '#475569' }}>Plan ('000T)</th>
                        <th style={{ padding: '12px 14px', textAlign: 'right', fontWeight: '700', fontSize: '12pt', color: '#475569' }}>Actual ('000T)</th>
                        <th style={{ padding: '12px 14px', textAlign: 'center', fontWeight: '700', fontSize: '12pt', color: '#475569' }}>Variance</th>
                      </tr>
                    </thead>
                    <tbody>
                      {items.map((item, idx) => {
                        const planVal = item.plan_edit !== '' ? parseFloat(item.plan_edit) : 0;
                        const actualVal = item.actual_edit !== '' ? parseFloat(item.actual_edit) : 0;
                        const variance = planVal !== 0 ? (((actualVal - planVal) / planVal) * 100).toFixed(1) : 0;
                        const varColor = variance > 0 ? '#059669' : variance < 0 ? '#dc2626' : '#6b7280';

                        return (
                          <tr key={idx} style={{ borderBottom: '1px solid #f1f5f9' }}>
                            <td style={{ padding: '12px 14px', fontSize: '13pt', color: '#1e293b', fontWeight: '500' }}>
                              {item.item_name}
                            </td>
                            <td style={{ padding: '12px 14px', textAlign: 'right' }}>
                              <input
                                type="number"
                                step="0.001"
                                value={item.plan_edit}
                                onChange={e => handlePlanChange(idx, e.target.value)}
                                style={{ width: '120px', padding: '8px 10px', border: '1px solid #cbd5e1', borderRadius: '4px', textAlign: 'right', fontSize: '12pt' }}
                              />
                            </td>
                            <td style={{ padding: '12px 14px', textAlign: 'right' }}>
                              <input
                                type="number"
                                step="0.001"
                                value={item.actual_edit}
                                onChange={e => handleActualChange(idx, e.target.value)}
                                style={{ width: '120px', padding: '8px 10px', border: '1px solid #cbd5e1', borderRadius: '4px', textAlign: 'right', fontSize: '12pt' }}
                              />
                            </td>
                            <td style={{ padding: '12px 14px', textAlign: 'center', fontSize: '12pt', color: varColor, fontWeight: '600' }}>
                              {variance}%
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>

                <div style={{ display: 'flex', gap: '12px', justifyContent: 'flex-end', marginTop: 'auto', paddingTop: '16px' }}>
                  <button
                    onClick={() => { setItems(items.map(it => ({ ...it, plan_edit: String(it.plan_value ?? ''), actual_edit: String(it.actual_value ?? '') }))); setStatus(null); }}
                    disabled={!hasChanges}
                    style={{ padding: '10px 20px', borderRadius: '4px', border: '1px solid #cbd5e1', backgroundColor: '#fff', color: '#475569', fontSize: '12pt', fontWeight: '600', cursor: hasChanges ? 'pointer' : 'default' }}
                  >
                    Reset
                  </button>
                  <button
                    onClick={handleSave}
                    disabled={saving || !hasChanges}
                    style={{ padding: '10px 20px', borderRadius: '4px', border: 'none', backgroundColor: hasChanges ? '#10b981' : '#94a3b8', color: '#fff', fontSize: '12pt', fontWeight: '600', cursor: hasChanges ? 'pointer' : 'default' }}
                  >
                    {saving ? 'Saving...' : 'Save to DB'}
                  </button>
                </div>
              </div>
            )}

            {!loaded && !loading && (
              <div style={{ padding: '50px', textAlign: 'center', color: '#94a3b8', fontSize: '13pt', backgroundColor: '#fff', borderRadius: '6px', border: '1px solid #e2e8f0', flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                Select plant, month, and year, then click <strong>Load Items</strong> to enter production data.
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
