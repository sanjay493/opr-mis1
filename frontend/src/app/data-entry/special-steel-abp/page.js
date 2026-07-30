'use client';

import RequireEditor from '@/components/RequireEditor';
import React, { useState, useEffect, useCallback } from 'react';
import GlobalNavbar from '@/components/GlobalNavbar';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || '';

const FY_LIST = ['2023-24', '2024-25', '2025-26', '2026-27', '2027-28', '2028-29'];
// Must match SPECIAL_STEEL_ABP_PLANTS in backend/main.py.
const PLANTS = ['BSP', 'DSP', 'RSP', 'BSL', 'ISP', 'SSPs'];
const MONTH_SHORT = { '01': 'Jan', '02': 'Feb', '03': 'Mar', '04': 'Apr', '05': 'May', '06': 'Jun', '07': 'Jul', '08': 'Aug', '09': 'Sep', '10': 'Oct', '11': 'Nov', '12': 'Dec' };

const monthLabel = (m) => `${MONTH_SHORT[m.slice(5, 7)]}'${m.slice(2, 4)}`;
const keyOf = (plant, month) => `${plant}|${month}`;

function SpecialSteelAbpPageInner() {
  const [fy, setFy] = useState('2026-27');
  const [months, setMonths] = useState([]);
  const [saved, setSaved] = useState({}); // plant -> month -> qty
  const [edits, setEdits] = useState({});
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [status, setStatus] = useState(null);

  const handleLoad = useCallback(async () => {
    setLoading(true);
    setStatus(null);
    try {
      const res = await fetch(`${API_BASE_URL}/api/special-steel-abp?financial_year=${encodeURIComponent(fy)}`);
      if (!res.ok) throw new Error((await res.json()).detail || 'Load failed');
      const json = await res.json();
      setMonths(json.months || []);
      setSaved(json.entries || {});
      const initial = {};
      Object.entries(json.entries || {}).forEach(([plant, byMonth]) => {
        Object.entries(byMonth || {}).forEach(([month, qty]) => {
          initial[keyOf(plant, month)] = qty != null ? String(qty) : '';
        });
      });
      setEdits(initial);
    } catch (err) {
      setStatus({ type: 'error', text: err.message });
      setMonths([]);
      setSaved({});
      setEdits({});
    } finally {
      setLoading(false);
    }
  }, [fy]);

  useEffect(() => { handleLoad(); }, [handleLoad]);

  const handleChange = (plant, month, value) => {
    setEdits((prev) => ({ ...prev, [keyOf(plant, month)]: value }));
  };

  const isChanged = (plant, month) => {
    const cur = edits[keyOf(plant, month)] ?? '';
    const savedVal = saved[plant]?.[month];
    const savedStr = savedVal != null ? String(savedVal) : '';
    return cur !== savedStr;
  };

  const hasChanges = () => PLANTS.some((p) => months.some((m) => isChanged(p, m)));

  const handleSave = async () => {
    setSaving(true);
    setStatus(null);
    const entries = [];
    PLANTS.forEach((plant) => {
      months.forEach((month) => {
        if (!isChanged(plant, month)) return;
        const val = edits[keyOf(plant, month)];
        const num = val === '' ? null : parseFloat(val);
        if (val !== '' && Number.isNaN(num)) return;
        entries.push({ plant_name: plant, report_month: month, abp_qty: num });
      });
    });
    if (!entries.length) {
      setStatus({ type: 'error', text: 'No changes to save.' });
      setSaving(false);
      return;
    }
    try {
      const res = await fetch(`${API_BASE_URL}/api/special-steel-abp`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ financial_year: fy, entries }),
      });
      if (!res.ok) throw new Error((await res.json()).detail || 'Save failed');
      const result = await res.json();
      setStatus({ type: 'success', text: `Saved ${result.saved} value(s) for FY ${fy}.` });
      await handleLoad();
    } catch (err) {
      setStatus({ type: 'error', text: `Save failed: ${err.message}` });
    } finally {
      setSaving(false);
    }
  };

  return (
    <div style={{ minHeight: '100vh', background: '#ffffff', fontFamily: "-apple-system,BlinkMacSystemFont,'Segoe UI',Arial,sans-serif" }}>
      <GlobalNavbar />

      <div style={{ maxWidth: 1200, margin: '0 auto', padding: '22px 20px' }}>
        <div style={{ display: 'flex', alignItems: 'baseline', gap: 14, marginBottom: 6, flexWrap: 'wrap' }}>
          <h2 style={{ fontSize: '1.6rem', fontWeight: 700, color: '#202124', margin: 0 }}>
            Special Steel ABP — Page 24
          </h2>
          <span style={{ fontSize: 13, color: '#5f6368' }}>
            Annual Business Plan target per plant, all 12 months of the FY — feeds the ABP FY / Month / Till-month columns on the SAIL Special Steel summary
          </span>
        </div>

        {/* Controls */}
        <div style={{
          display: 'flex', gap: 10, alignItems: 'center', flexWrap: 'wrap',
          marginBottom: 18, border: '1px solid #dadce0', borderRadius: 8, padding: '14px 18px',
        }}>
          <label style={{ fontSize: 13, fontWeight: 600, color: '#374151' }}>Financial Year</label>
          <select value={fy} onChange={(e) => setFy(e.target.value)}
                  style={{ padding: '7px 10px', fontSize: 14, border: '1px solid #d1d5db', borderRadius: 4 }}>
            {FY_LIST.map((f) => <option key={f} value={f}>{f}</option>)}
          </select>

          <button onClick={handleSave} disabled={saving || !hasChanges()} style={{
            marginLeft: 'auto', padding: '8px 20px', fontSize: 13, fontWeight: 700, borderRadius: 6,
            border: 'none', cursor: hasChanges() ? 'pointer' : 'default',
            background: hasChanges() ? '#10b981' : '#9ca3af', color: '#fff',
          }}>
            {saving ? 'Saving...' : 'Save All'}
          </button>
        </div>

        {status && (
          <div style={{
            padding: '10px 16px', borderRadius: 6, marginBottom: 14, fontSize: 14,
            background: status.type === 'success' ? '#e6f4ea' : '#fef2f2',
            color: status.type === 'success' ? '#188038' : '#991b1b',
            border: `1px solid ${status.type === 'success' ? '#a8dab5' : '#fca5a5'}`,
          }}>
            {status.text}
          </div>
        )}

        {loading && <div style={{ color: '#5f6368', fontSize: 14, padding: '30px 0', textAlign: 'center' }}>Loading…</div>}

        {!loading && months.length > 0 && (
          <div style={{ border: '1px solid #dadce0', borderRadius: 8, overflow: 'hidden' }}>
            <div style={{ overflowX: 'auto' }}>
              <table style={{ borderCollapse: 'collapse', width: '100%' }}>
                <thead>
                  <tr>
                    <th style={{
                      padding: '7px 12px', fontSize: 12, fontWeight: 600, color: '#374151',
                      background: '#f8fafc', borderBottom: '1px solid #dadce0', borderRight: '1px solid #eef1f4',
                      textAlign: 'left', whiteSpace: 'nowrap',
                    }}>Month</th>
                    {PLANTS.map((p) => (
                      <th key={p} style={{
                        padding: '7px 12px', fontSize: 12, fontWeight: 600, color: '#374151',
                        background: '#f8fafc', borderBottom: '1px solid #dadce0', borderRight: '1px solid #eef1f4',
                        whiteSpace: 'nowrap', textAlign: 'center',
                      }}>{p}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {months.map((m) => (
                    <tr key={m}>
                      <td style={{
                        padding: '8px 12px', fontSize: 13, fontWeight: 600, color: '#374151',
                        borderRight: '1px solid #eef1f4', borderBottom: '1px solid #f1f3f4', whiteSpace: 'nowrap',
                      }}>{monthLabel(m)}</td>
                      {PLANTS.map((p) => {
                        const changed = isChanged(p, m);
                        const savedVal = saved[p]?.[m];
                        return (
                          <td key={p} style={{ padding: '6px 8px', borderRight: '1px solid #eef1f4', borderBottom: '1px solid #f1f3f4', textAlign: 'center' }}>
                            <input
                              type="number" step="any"
                              value={edits[keyOf(p, m)] ?? ''}
                              onChange={(e) => handleChange(p, m, e.target.value)}
                              placeholder="–"
                              style={{
                                width: 90, padding: '5px 6px', fontSize: 13, textAlign: 'right', borderRadius: 4,
                                border: `1px solid ${changed ? '#fbbf24' : '#d1d5db'}`,
                                background: changed ? '#fffbeb' : savedVal != null ? '#f0fdf4' : '#fff',
                                color: changed ? '#92400e' : '#202124',
                              }}
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
      </div>
    </div>
  );
}

export default function SpecialSteelAbpPage() {
  return (
    <RequireEditor>
      <SpecialSteelAbpPageInner />
    </RequireEditor>
  );
}
