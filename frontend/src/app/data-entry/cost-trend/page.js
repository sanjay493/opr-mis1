'use client';

import RequireEditor from '@/components/RequireEditor';
import React, { useState, useEffect, useCallback } from 'react';
import GlobalNavbar from '@/components/GlobalNavbar';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || '';

// Must match db.py's COST_TREND_ENTRY_PLANTS / COST_TREND_ENTRY_COST_TYPES
// and page_cost_trend.py's _PRODUCT_TITLE / _COST_TYPE_LABEL. TOTAL COST is
// computed on the report page (TOTAL = VARIABLE + FIXED) — never entered
// here. SAIL 5 ISPs is its own directly-entered row like every other
// plant, NOT a sum of the other 5 (that was tried and reverted).
const PRODUCTS = [
  { value: 'HM', label: 'Hot Metal' },
  { value: 'CS', label: 'Crude Steel' },
  { value: 'SS', label: 'Saleable Steel' },
];
const COST_TYPES = [
  { value: 'VARIABLE', label: 'Variable Cost' },
  { value: 'FIXED', label: 'Fixed Cost' },
];
const PLANTS = ['BSP', 'DSP', 'RSP', 'BSL', 'ISP', 'SAIL'];
const PLANT_LABEL = { SAIL: 'SAIL 5 ISPs' };
const FY_LIST = ['2020-21', '2021-22', '2022-23', '2023-24', '2024-25', '2025-26', '2026-27', '2027-28', '2028-29'];

const keyOf = (costType, plant) => `${costType}|${plant}`;
const thisMonth = () => new Date().toISOString().slice(0, 7);

function CostTrendPageInner() {
  const [product, setProduct] = useState('HM');
  const [mode, setMode] = useState('monthly'); // 'monthly' | 'annual'
  const [reportMonth, setReportMonth] = useState(thisMonth());
  const [fy, setFy] = useState('2026-27');

  const [saved, setSaved] = useState({}); // key -> {month,till_month} or {value}
  const [edits, setEdits] = useState({});
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [status, setStatus] = useState(null);

  const handleLoad = useCallback(async () => {
    setLoading(true);
    setStatus(null);
    try {
      const url = mode === 'monthly'
        ? `${API_BASE_URL}/api/cost-trend/monthly?product=${product}&report_month=${reportMonth}`
        : `${API_BASE_URL}/api/cost-trend/annual?product=${product}&fy=${fy}`;
      const res = await fetch(url);
      if (!res.ok) throw new Error((await res.json()).detail || 'Load failed');
      const json = await res.json();
      const entries = json.entries || {};
      const nextSaved = {};
      const nextEdits = {};
      COST_TYPES.forEach(({ value: ct }) => {
        PLANTS.forEach((p) => {
          const cell = entries[ct]?.[p];
          const k = keyOf(ct, p);
          if (mode === 'monthly') {
            const monthVal = cell?.month ?? null;
            const tillVal = cell?.till_month ?? null;
            nextSaved[k] = { month: monthVal, till_month: tillVal };
            nextEdits[k] = {
              month: monthVal != null ? String(monthVal) : '',
              till_month: tillVal != null ? String(tillVal) : '',
            };
          } else {
            const v = cell ?? null;
            nextSaved[k] = { value: v };
            nextEdits[k] = { value: v != null ? String(v) : '' };
          }
        });
      });
      setSaved(nextSaved);
      setEdits(nextEdits);
    } catch (err) {
      setStatus({ type: 'error', text: err.message });
      setSaved({});
      setEdits({});
    } finally {
      setLoading(false);
    }
  }, [product, mode, reportMonth, fy]);

  useEffect(() => { handleLoad(); }, [handleLoad]);

  const handleChange = (costType, plant, field, value) => {
    const k = keyOf(costType, plant);
    setEdits((prev) => ({ ...prev, [k]: { ...prev[k], [field]: value } }));
  };

  const isChanged = (costType, plant) => {
    const k = keyOf(costType, plant);
    const e = edits[k] || {};
    const s = saved[k] || {};
    if (mode === 'monthly') {
      const sMonth = s.month != null ? String(s.month) : '';
      const sTill = s.till_month != null ? String(s.till_month) : '';
      return (e.month ?? '') !== sMonth || (e.till_month ?? '') !== sTill;
    }
    const sVal = s.value != null ? String(s.value) : '';
    return (e.value ?? '') !== sVal;
  };

  const hasChanges = () => COST_TYPES.some(({ value: ct }) => PLANTS.some((p) => isChanged(ct, p)));

  const handleSave = async () => {
    setSaving(true);
    setStatus(null);
    const entries = [];
    COST_TYPES.forEach(({ value: ct }) => {
      PLANTS.forEach((p) => {
        if (!isChanged(ct, p)) return;
        const e = edits[keyOf(ct, p)] || {};
        if (mode === 'monthly') {
          const mv = e.month === '' ? null : parseFloat(e.month);
          const tv = e.till_month === '' ? null : parseFloat(e.till_month);
          if ((e.month !== '' && Number.isNaN(mv)) || (e.till_month !== '' && Number.isNaN(tv))) return;
          entries.push({ cost_type: ct, plant: p, month_value: mv, till_month_value: tv });
        } else {
          const v = e.value === '' ? null : parseFloat(e.value);
          if (e.value !== '' && Number.isNaN(v)) return;
          entries.push({ cost_type: ct, plant: p, value: v });
        }
      });
    });
    if (!entries.length) {
      setStatus({ type: 'error', text: 'No changes to save.' });
      setSaving(false);
      return;
    }
    try {
      const url = mode === 'monthly' ? `${API_BASE_URL}/api/cost-trend/monthly` : `${API_BASE_URL}/api/cost-trend/annual`;
      const body = mode === 'monthly'
        ? { report_month: reportMonth, product, entries }
        : { fy, product, entries };
      const res = await fetch(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });
      if (!res.ok) throw new Error((await res.json()).detail || 'Save failed');
      const result = await res.json();
      setStatus({ type: 'success', text: `Saved ${result.saved} value(s).` });
      await handleLoad();
    } catch (err) {
      setStatus({ type: 'error', text: `Save failed: ${err.message}` });
    } finally {
      setSaving(false);
    }
  };

  const inputStyle = (changed, hasValue) => ({
    width: 90, padding: '5px 6px', fontSize: 13, textAlign: 'right', borderRadius: 4,
    border: `1px solid ${changed ? '#fbbf24' : '#d1d5db'}`,
    background: changed ? '#fffbeb' : hasValue ? '#f0fdf4' : '#fff',
    color: changed ? '#92400e' : '#202124',
  });

  return (
    <div style={{ height: '100vh', display: 'flex', flexDirection: 'column', background: '#ffffff', fontFamily: "-apple-system,BlinkMacSystemFont,'Segoe UI',Arial,sans-serif" }}>
      <GlobalNavbar />

      <div style={{ flex: 1, overflowY: 'auto', maxWidth: 1200, width: '100%', margin: '0 auto', padding: '22px 20px' }}>
        <div style={{ display: 'flex', alignItems: 'baseline', gap: 14, marginBottom: 6, flexWrap: 'wrap' }}>
          <h2 style={{ fontSize: '1.6rem', fontWeight: 700, color: '#202124', margin: 0 }}>
            Cost Trend Entry — Pages 3.61-3.63
          </h2>
          <span style={{ fontSize: 13, color: '#5f6368' }}>
            Trend in Cost of Production (Hot Metal / Crude Steel / Saleable Steel) — Variable / Fixed Cost per plant, including SAIL 5 ISPs (entered directly, not summed from the plants), annual history and current-FY month + till-month. Total Cost is computed automatically on the report. Have an "ELHM CS SS ..." workbook instead? Use the <a href="/data-entry/cost-trend-extract" style={{ color: '#1a73e8' }}>Excel Extractor</a> to pull these values automatically.
          </span>
        </div>

        {/* Controls */}
        <div style={{
          display: 'flex', gap: 14, alignItems: 'center', flexWrap: 'wrap',
          marginBottom: 18, border: '1px solid #dadce0', borderRadius: 8, padding: '14px 18px',
        }}>
          <label style={{ fontSize: 13, fontWeight: 600, color: '#374151' }}>Product</label>
          <select value={product} onChange={(e) => setProduct(e.target.value)}
                  style={{ padding: '7px 10px', fontSize: 14, border: '1px solid #d1d5db', borderRadius: 4 }}>
            {PRODUCTS.map((p) => <option key={p.value} value={p.value}>{p.label}</option>)}
          </select>

          <div style={{ display: 'flex', border: '1px solid #d1d5db', borderRadius: 6, overflow: 'hidden' }}>
            {['monthly', 'annual'].map((m) => (
              <button key={m} onClick={() => setMode(m)} style={{
                padding: '7px 14px', fontSize: 13, fontWeight: 600, border: 'none', cursor: 'pointer',
                background: mode === m ? '#1d4ed8' : '#fff', color: mode === m ? '#fff' : '#374151',
              }}>
                {m === 'monthly' ? 'Monthly / Till-Month' : 'Annual (Yearly)'}
              </button>
            ))}
          </div>

          {mode === 'monthly' ? (
            <>
              <label style={{ fontSize: 13, fontWeight: 600, color: '#374151' }}>Report Month</label>
              <input type="month" value={reportMonth} onChange={(e) => setReportMonth(e.target.value)}
                     style={{ padding: '6px 10px', fontSize: 14, border: '1px solid #d1d5db', borderRadius: 4 }} />
            </>
          ) : (
            <>
              <label style={{ fontSize: 13, fontWeight: 600, color: '#374151' }}>Financial Year</label>
              <select value={fy} onChange={(e) => setFy(e.target.value)}
                      style={{ padding: '7px 10px', fontSize: 14, border: '1px solid #d1d5db', borderRadius: 4 }}>
                {FY_LIST.map((f) => <option key={f} value={f}>{f}</option>)}
              </select>
            </>
          )}

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

        {!loading && COST_TYPES.map(({ value: ct, label: ctLabel }) => (
          <div key={ct} style={{ marginBottom: 22 }}>
            <div style={{ fontSize: 14, fontWeight: 700, color: '#1e293b', marginBottom: 6 }}>{ctLabel}</div>
            <div style={{ border: '1px solid #dadce0', borderRadius: 8, overflow: 'hidden' }}>
              <table style={{ borderCollapse: 'collapse', width: '100%' }}>
                <thead>
                  <tr>
                    <th style={{
                      padding: '7px 12px', fontSize: 12, fontWeight: 600, color: '#374151',
                      background: '#f8fafc', borderBottom: '1px solid #dadce0', borderRight: '1px solid #eef1f4',
                      textAlign: 'left', whiteSpace: 'nowrap',
                    }}>Plant</th>
                    {mode === 'monthly' ? (
                      <>
                        <th style={{ padding: '7px 12px', fontSize: 12, fontWeight: 600, color: '#374151', background: '#f8fafc', borderBottom: '1px solid #dadce0', borderRight: '1px solid #eef1f4', textAlign: 'center' }}>Month ({reportMonth})</th>
                        <th style={{ padding: '7px 12px', fontSize: 12, fontWeight: 600, color: '#374151', background: '#f8fafc', borderBottom: '1px solid #dadce0', textAlign: 'center' }}>Till Month (Apr-{reportMonth})</th>
                      </>
                    ) : (
                      <th style={{ padding: '7px 12px', fontSize: 12, fontWeight: 600, color: '#374151', background: '#f8fafc', borderBottom: '1px solid #dadce0', textAlign: 'center' }}>Value (FY {fy})</th>
                    )}
                  </tr>
                </thead>
                <tbody>
                  {PLANTS.map((p) => {
                    const changed = isChanged(ct, p);
                    const e = edits[keyOf(ct, p)] || {};
                    return (
                      <tr key={p}>
                        <td style={{
                          padding: '8px 12px', fontSize: 13, fontWeight: 600, color: '#374151',
                          borderRight: '1px solid #eef1f4', borderBottom: '1px solid #f1f3f4', whiteSpace: 'nowrap',
                        }}>{PLANT_LABEL[p] || p}</td>
                        {mode === 'monthly' ? (
                          <>
                            <td style={{ padding: '6px 8px', borderRight: '1px solid #eef1f4', borderBottom: '1px solid #f1f3f4', textAlign: 'center' }}>
                              <input type="number" step="any" value={e.month ?? ''} placeholder="–"
                                     onChange={(ev) => handleChange(ct, p, 'month', ev.target.value)}
                                     style={inputStyle(changed, e.month)} />
                            </td>
                            <td style={{ padding: '6px 8px', borderBottom: '1px solid #f1f3f4', textAlign: 'center' }}>
                              <input type="number" step="any" value={e.till_month ?? ''} placeholder="–"
                                     onChange={(ev) => handleChange(ct, p, 'till_month', ev.target.value)}
                                     style={inputStyle(changed, e.till_month)} />
                            </td>
                          </>
                        ) : (
                          <td style={{ padding: '6px 8px', borderBottom: '1px solid #f1f3f4', textAlign: 'center' }}>
                            <input type="number" step="any" value={e.value ?? ''} placeholder="–"
                                   onChange={(ev) => handleChange(ct, p, 'value', ev.target.value)}
                                   style={inputStyle(changed, e.value)} />
                          </td>
                        )}
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

export default function CostTrendPage() {
  return (
    <RequireEditor>
      <CostTrendPageInner />
    </RequireEditor>
  );
}
