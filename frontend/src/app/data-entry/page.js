'use client';

import React, { useState, useCallback } from 'react';
import Link from 'next/link';

const PLANTS = ['BSP', 'DSP', 'ISP', 'RSP', 'BSL', 'ASP', 'SSP', 'VISL'];
const MONTHS = [
  'April', 'May', 'June', 'July', 'August', 'September',
  'October', 'November', 'December', 'January', 'February', 'March'
];
const YEARS = Array.from({ length: 8 }, (_, i) => (2023 + i).toString());

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || '';

function getDefaultPeriod() {
  const d = new Date();
  d.setMonth(d.getMonth() - 1);
  return { month: MONTHS[d.getMonth()], year: d.getFullYear().toString() };
}

export default function DataEntryPage() {
  const defaultPeriod = getDefaultPeriod();
  const [plant, setPlant] = useState('BSP');
  const [month, setMonth] = useState(defaultPeriod.month);
  const [year, setYear] = useState(defaultPeriod.year);
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [status, setStatus] = useState(null); // {type: 'success'|'error', text}
  const [loaded, setLoaded] = useState(false);

  const reportMonth = `${month} ${year}`;

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
        setStatus({ type: 'error', text: `No plan items found for ${plant} in ${reportMonth}. Upload ABP plan first.` });
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
      setStatus({ type: 'success', text: `Saved ${result.count} value(s) for ${plant} — ${reportMonth}.` });
      // Refresh to show updated values
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
    <main className="app-container">
      {/* Sidebar */}
      <div className="sidebar no-print">
        <div className="sidebar-header">
          <h1 style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" style={{ color: 'var(--primary)' }}>
              <rect x="3" y="3" width="18" height="18" rx="2" />
              <path d="M3 9h18M9 21V9" />
            </svg>
            SAIL MIS Portal
          </h1>
          <p>Production Data Entry</p>
        </div>

        <div className="control-section">
          <h2>Navigation</h2>
          <Link href="/" className="btn btn-secondary" style={{ width: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '8px', marginBottom: '8px', textDecoration: 'none' }}>
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><line x1="19" y1="12" x2="5" y2="12"/><polyline points="12 19 5 12 12 5"/></svg>
            Dashboard
          </Link>
          <Link href="/upload" className="btn btn-secondary" style={{ width: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '8px', marginBottom: '8px', textDecoration: 'none' }}>
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="17 8 12 3 7 8"/><line x1="12" y1="3" x2="12" y2="15"/></svg>
            Excel Upload
          </Link>
          <Link href="/report" className="btn btn-secondary" style={{ width: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '8px', textDecoration: 'none' }}>
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7.5L14.5 2z"/><polyline points="14 2 14 8 20 8"/></svg>
            Report Engine
          </Link>
        </div>

        <div className="control-section" style={{ marginTop: '15px' }}>
          <h2>Select Plant &amp; Period</h2>

          <div className="form-group" style={{ marginBottom: '12px' }}>
            <label>Plant</label>
            <select className="form-control" value={plant} onChange={e => { setPlant(e.target.value); setLoaded(false); setItems([]); }}>
              {PLANTS.map(p => <option key={p} value={p}>{p}</option>)}
            </select>
          </div>

          <div className="form-group" style={{ marginBottom: '12px' }}>
            <label>Month</label>
            <div style={{ display: 'flex', gap: '6px' }}>
              <select className="form-control" style={{ flex: 2 }} value={month} onChange={e => { setMonth(e.target.value); setLoaded(false); setItems([]); }}>
                {MONTHS.map(m => <option key={m} value={m}>{m}</option>)}
              </select>
              <select className="form-control" style={{ flex: 1 }} value={year} onChange={e => { setYear(e.target.value); setLoaded(false); setItems([]); }}>
                {YEARS.map(y => <option key={y} value={y}>{y}</option>)}
              </select>
            </div>
          </div>

          <button className="btn btn-primary" style={{ width: '100%', backgroundColor: '#6366f1', borderColor: '#6366f1' }} onClick={handleLoad} disabled={loading}>
            {loading ? 'Loading...' : 'Load Items'}
          </button>

          {loaded && (
            <button
              className="btn btn-primary"
              style={{ width: '100%', marginTop: '10px', backgroundColor: hasChanges ? '#10b981' : '#334155', borderColor: hasChanges ? '#10b981' : '#334155', cursor: hasChanges ? 'pointer' : 'default' }}
              onClick={handleSave}
              disabled={saving || !hasChanges}
            >
              {saving ? 'Saving...' : `Save to DB`}
            </button>
          )}
        </div>

        {status && (
          <div style={{ margin: '12px 0', padding: '10px 12px', borderRadius: '6px', fontSize: '0.8rem', backgroundColor: status.type === 'success' ? '#064e3b' : '#7f1d1d', color: status.type === 'success' ? '#6ee7b7' : '#fca5a5', border: `1px solid ${status.type === 'success' ? '#065f46' : '#991b1b'}` }}>
            {status.text}
          </div>
        )}

        <div style={{ marginTop: 'auto', fontSize: '0.75rem', color: '#64748b', textAlign: 'center', paddingTop: '15px' }}>
          SAIL Informatics Report Portal • v1.0.0
        </div>
      </div>

      {/* Main content area */}
      <div className="preview-area" style={{ padding: '30px', overflowY: 'auto', backgroundColor: '#f8fafc' }}>
        <div style={{ maxWidth: '900px', margin: '0 auto' }}>
          <div style={{ marginBottom: '24px' }}>
            <h1 style={{ fontSize: '18pt', fontWeight: '800', color: '#0f172a', margin: '0 0 4px 0' }}>
              Production Data Entry
            </h1>
            <p style={{ fontSize: '10pt', color: '#64748b', margin: 0 }}>
              Enter actual production values for each item. Plan values come from the uploaded ABP and can also be edited.
            </p>
          </div>

          {!loaded && !loading && (
            <div style={{ padding: '48px', textAlign: 'center', backgroundColor: '#fff', border: '1px solid #e2e8f0', borderRadius: '8px', color: '#94a3b8' }}>
              <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" style={{ margin: '0 auto 12px', display: 'block', color: '#cbd5e1' }}>
                <rect x="3" y="3" width="18" height="18" rx="2"/>
                <path d="M3 9h18M9 21V9"/>
              </svg>
              <p style={{ margin: 0, fontSize: '10pt' }}>Select a plant and period, then click <strong>Load Items</strong>.</p>
            </div>
          )}

          {loading && (
            <div style={{ padding: '48px', textAlign: 'center', color: '#64748b', fontSize: '10pt' }}>
              Fetching items from database...
            </div>
          )}

          {loaded && items.length > 0 && (
            <div style={{ backgroundColor: '#fff', border: '1px solid #e2e8f0', borderRadius: '8px', overflow: 'hidden' }}>
              <div style={{ padding: '14px 20px', backgroundColor: '#1e293b', color: '#f1f5f9', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <span style={{ fontWeight: '700', fontSize: '10pt' }}>{plant} — {reportMonth}</span>
                <span style={{ fontSize: '9pt', color: '#94a3b8' }}>{items.length} items</span>
              </div>
              <div style={{ overflowX: 'auto' }}>
                <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '9.5pt' }}>
                  <thead>
                    <tr style={{ backgroundColor: '#f1f5f9' }}>
                      <th style={{ padding: '10px 16px', textAlign: 'left', fontWeight: '700', color: '#475569', borderBottom: '1px solid #e2e8f0', width: '50%' }}>Item Name</th>
                      <th style={{ padding: '10px 12px', textAlign: 'center', fontWeight: '700', color: '#3b82f6', borderBottom: '1px solid #e2e8f0' }}>Plan (ABP)</th>
                      <th style={{ padding: '10px 12px', textAlign: 'center', fontWeight: '700', color: '#10b981', borderBottom: '1px solid #e2e8f0' }}>Actual</th>
                      <th style={{ padding: '10px 12px', textAlign: 'center', fontWeight: '700', color: '#64748b', borderBottom: '1px solid #e2e8f0' }}>% vs Plan</th>
                    </tr>
                  </thead>
                  <tbody>
                    {items.map((item, idx) => {
                      const planNum = parseFloat(item.plan_edit);
                      const actualNum = parseFloat(item.actual_edit);
                      const pct = (!isNaN(planNum) && planNum !== 0 && !isNaN(actualNum))
                        ? Math.round((actualNum / planNum) * 100)
                        : null;
                      const pctColor = pct === null ? '#94a3b8' : pct >= 100 ? '#059669' : pct >= 90 ? '#d97706' : '#dc2626';
                      const rowChanged =
                        item.actual_edit !== String(item.actual_value ?? '') ||
                        item.plan_edit !== String(item.plan_value ?? '');

                      return (
                        <tr key={item.item_name} style={{ backgroundColor: rowChanged ? '#fffbeb' : (idx % 2 === 0 ? '#fff' : '#f8fafc'), borderBottom: '1px solid #f1f5f9' }}>
                          <td style={{ padding: '8px 16px', color: '#1e293b', fontWeight: '500' }}>
                            {item.item_name}
                            {rowChanged && <span style={{ marginLeft: '6px', fontSize: '8pt', color: '#d97706', fontWeight: '600' }}>edited</span>}
                          </td>
                          <td style={{ padding: '6px 12px', textAlign: 'center' }}>
                            <input
                              type="number"
                              step="any"
                              value={item.plan_edit}
                              onChange={e => handlePlanChange(idx, e.target.value)}
                              style={{ width: '90px', padding: '4px 6px', border: '1px solid #cbd5e1', borderRadius: '4px', textAlign: 'right', fontSize: '9pt', color: '#1e40af', backgroundColor: '#eff6ff' }}
                            />
                          </td>
                          <td style={{ padding: '6px 12px', textAlign: 'center' }}>
                            <input
                              type="number"
                              step="any"
                              value={item.actual_edit}
                              onChange={e => handleActualChange(idx, e.target.value)}
                              placeholder="Enter actual"
                              style={{ width: '100px', padding: '4px 6px', border: `1px solid ${item.actual_edit ? '#6ee7b7' : '#cbd5e1'}`, borderRadius: '4px', textAlign: 'right', fontSize: '9pt', color: '#065f46', backgroundColor: item.actual_edit ? '#f0fdf4' : '#fff' }}
                            />
                          </td>
                          <td style={{ padding: '8px 12px', textAlign: 'center', fontWeight: '700', color: pctColor }}>
                            {pct !== null ? `${pct}%` : '—'}
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
              <div style={{ padding: '12px 20px', backgroundColor: '#f8fafc', borderTop: '1px solid #e2e8f0', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <span style={{ fontSize: '8.5pt', color: '#64748b' }}>
                  Rows highlighted in yellow have unsaved changes. Click <strong>Save to DB</strong> in the sidebar.
                </span>
                <button
                  className="btn btn-primary"
                  style={{ backgroundColor: hasChanges ? '#10b981' : '#94a3b8', borderColor: hasChanges ? '#10b981' : '#94a3b8', fontSize: '9pt', padding: '6px 16px' }}
                  onClick={handleSave}
                  disabled={saving || !hasChanges}
                >
                  {saving ? 'Saving...' : 'Save Changes'}
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
    </main>
  );
}
