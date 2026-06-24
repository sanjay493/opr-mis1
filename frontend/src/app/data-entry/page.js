'use client';

import React, { useState, useCallback, useEffect, useMemo } from 'react';
import Link from 'next/link';
import SpecialSteelManualEntry from '@/components/SpecialSteelManualEntry';
import HotMetalConsumptionEntry from '@/components/HotMetalConsumptionEntry';

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

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

function getDefaultPeriod() {
  const d = new Date();
  d.setMonth(d.getMonth() - 1);
  return { month: MONTHS[d.getMonth()], year: d.getFullYear().toString() };
}

const MONTH_SHORT = { '01':'Jan','02':'Feb','03':'Mar','04':'Apr','05':'May','06':'Jun','07':'Jul','08':'Aug','09':'Sep','10':'Oct','11':'Nov','12':'Dec' };
const FY_YEARS = Array.from({ length: 6 }, (_, i) => (2022 + i).toString());

const STOCK_PLANTS = ['BSP', 'DSP', 'RSP', 'BSL', 'ISP'];
const STOCK_ITEMS = [
  { item_type: 'SLABS',          stock_type: 'INPROCESS', label: 'SLABS — [a] INPROCESS' },
  { item_type: 'SLABS',          stock_type: 'FOR SALE',  label: 'SLABS — [b] FOR SALE' },
  { item_type: 'BLOOM/BILLETS',  stock_type: 'INPROCESS', label: 'BLOOM/BILLETS — [a] INPROCESS' },
  { item_type: 'BLOOM/BILLETS',  stock_type: 'FOR SALE',  label: 'BLOOM/BILLETS — [b] FOR SALE' },
  { item_type: 'FINISHED STEEL', stock_type: '',          label: 'FINISHED STEEL' },
  { item_type: 'PIG IRON',       stock_type: '',          label: 'PIG IRON' },
];

function StockEntryCard({ apiBase }) {
  const defaultMonth = () => {
    const d = new Date();
    d.setDate(1);
    return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}`;
  };
  const [plant, setPlant] = useState('BSP');
  const [stockMonth, setStockMonth] = useState(defaultMonth);
  const [values, setValues] = useState({});   // key: `${item_type}||${stock_type}` → edit string
  const [savedValues, setSavedValues] = useState({});
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [status, setStatus] = useState(null);
  const [loaded, setLoaded] = useState(false);

  const key = (item_type, stock_type) => `${item_type}||${stock_type}`;

  const handleLoad = async () => {
    setLoading(true);
    setStatus(null);
    setLoaded(false);
    try {
      const res = await fetch(`${apiBase}/api/stock-data?plant=${encodeURIComponent(plant)}&stock_month=${encodeURIComponent(stockMonth)}`);
      if (!res.ok) throw new Error(await res.text());
      const json = await res.json();
      const map = {};
      json.data.forEach(r => { map[key(r.item_type, r.stock_type)] = String(r.stock ?? ''); });
      setSavedValues(map);
      const edits = {};
      STOCK_ITEMS.forEach(it => { edits[key(it.item_type, it.stock_type)] = map[key(it.item_type, it.stock_type)] ?? ''; });
      setValues(edits);
      setLoaded(true);
    } catch (err) {
      setStatus({ type: 'error', text: `Load failed: ${err.message}` });
    } finally {
      setLoading(false);
    }
  };

  const handleSave = async () => {
    const entries = STOCK_ITEMS
      .filter(it => {
        const v = values[key(it.item_type, it.stock_type)];
        return v !== '' && v !== undefined && !isNaN(parseFloat(v));
      })
      .map(it => ({
        plant, stock_month: stockMonth,
        item_type: it.item_type, stock_type: it.stock_type,
        stock: parseFloat(values[key(it.item_type, it.stock_type)]),
      }));
    if (!entries.length) { setStatus({ type: 'error', text: 'No values to save.' }); return; }
    setSaving(true);
    setStatus(null);
    try {
      const res = await fetch(`${apiBase}/api/stock-entry`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ entries }),
      });
      if (!res.ok) throw new Error(await res.text());
      const json = await res.json();
      setStatus({ type: 'success', text: json.message });
      const newSaved = { ...savedValues };
      entries.forEach(e => { newSaved[key(e.item_type, e.stock_type)] = String(e.stock); });
      setSavedValues(newSaved);
    } catch (err) {
      setStatus({ type: 'error', text: `Save failed: ${err.message}` });
    } finally {
      setSaving(false);
    }
  };

  const hasChanges = STOCK_ITEMS.some(it => {
    const k = key(it.item_type, it.stock_type);
    const cur = values[k] ?? '';
    const saved = savedValues[k] ?? '';
    return cur !== saved && cur !== '';
  });

  const H = { padding: '8px 14px', textAlign: 'left', fontWeight: 700, color: '#475569', borderBottom: '1px solid #e2e8f0', fontSize: '9pt', backgroundColor: '#f1f5f9' };
  const TD = { padding: '7px 14px', borderBottom: '1px solid #f1f5f9', fontSize: '9.5pt' };

  return (
    <div style={{ backgroundColor: '#fff', border: '1px solid #e2e8f0', borderRadius: '8px', overflow: 'hidden', marginTop: '24px' }}>
      {/* Header */}
      <div style={{ padding: '14px 20px', backgroundColor: '#1e3a5f', color: '#f1f5f9', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <span style={{ fontWeight: 700, fontSize: '10pt' }}>Opening Stock — Manual Entry</span>
        <span style={{ fontSize: '8.5pt', color: '#94a3b8' }}>Values in '000T · upserts stock_table</span>
      </div>

      {/* Controls */}
      <div style={{ padding: '14px 20px', backgroundColor: '#f8fafc', borderBottom: '1px solid #e2e8f0', display: 'flex', gap: 12, alignItems: 'flex-end', flexWrap: 'wrap' }}>
        <div>
          <div style={{ fontSize: '8pt', color: '#64748b', marginBottom: 4 }}>Plant</div>
          <select value={plant} onChange={e => { setPlant(e.target.value); setLoaded(false); setValues({}); setSavedValues({}); }}
            style={{ padding: '5px 10px', borderRadius: 4, border: '1px solid #cbd5e1', fontSize: '9pt', backgroundColor: '#fff' }}>
            {STOCK_PLANTS.map(p => <option key={p} value={p}>{p}</option>)}
          </select>
        </div>
        <div>
          <div style={{ fontSize: '8pt', color: '#64748b', marginBottom: 4 }}>Stock as on 1st of</div>
          <input type="month" value={stockMonth} onChange={e => { setStockMonth(e.target.value); setLoaded(false); setValues({}); setSavedValues({}); }}
            style={{ padding: '5px 10px', borderRadius: 4, border: '1px solid #cbd5e1', fontSize: '9pt', backgroundColor: '#fff' }} />
        </div>
        <button onClick={handleLoad} disabled={loading}
          style={{ padding: '6px 16px', borderRadius: 4, border: 'none', backgroundColor: '#6366f1', color: '#fff', fontWeight: 600, fontSize: '9pt', cursor: 'pointer' }}>
          {loading ? 'Loading...' : 'Load'}
        </button>
      </div>

      {/* Grid */}
      {loaded && (
        <div style={{ overflowX: 'auto' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead>
              <tr>
                <th style={H}>Item</th>
                <th style={{ ...H, textAlign: 'right' }}>Value ('000T)</th>
                <th style={{ ...H, textAlign: 'center' }}>Status</th>
              </tr>
            </thead>
            <tbody>
              {STOCK_ITEMS.map((it, i) => {
                const k = key(it.item_type, it.stock_type);
                const cur = values[k] ?? '';
                const saved = savedValues[k] ?? '';
                const changed = cur !== saved && cur !== '';
                const hasVal = saved !== '';
                return (
                  <tr key={k} style={{ backgroundColor: changed ? '#fffbeb' : i % 2 === 0 ? '#fff' : '#f8fafc' }}>
                    <td style={{ ...TD, fontWeight: 500, color: '#1e293b' }}>{it.label}</td>
                    <td style={{ ...TD, textAlign: 'right' }}>
                      <input type="number" step="0.001" value={cur} placeholder={hasVal ? saved : 'Enter value'}
                        onChange={e => setValues(prev => ({ ...prev, [k]: e.target.value }))}
                        style={{ width: 120, padding: '4px 8px', border: `1px solid ${changed ? '#fbbf24' : cur ? '#6ee7b7' : '#cbd5e1'}`,
                                 borderRadius: 4, textAlign: 'right', fontSize: '9pt',
                                 color: '#065f46', backgroundColor: changed ? '#fffbeb' : cur ? '#f0fdf4' : '#fff' }} />
                    </td>
                    <td style={{ ...TD, textAlign: 'center', fontSize: '8.5pt' }}>
                      {changed
                        ? <span style={{ color: '#d97706', fontWeight: 600 }}>edited</span>
                        : hasVal
                        ? <span style={{ color: '#059669' }}>{parseFloat(saved).toFixed(3)}</span>
                        : <span style={{ color: '#94a3b8' }}>—</span>}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      {!loaded && !loading && (
        <div style={{ padding: '32px', textAlign: 'center', color: '#94a3b8', fontSize: '9.5pt' }}>
          Select plant and month, then click <strong>Load</strong> to view / edit stock values.
        </div>
      )}

      {status && (
        <div style={{ margin: '0 16px 12px', padding: '8px 12px', borderRadius: 6, fontSize: '8.5pt',
                      backgroundColor: status.type === 'success' ? '#064e3b' : '#7f1d1d',
                      color: status.type === 'success' ? '#6ee7b7' : '#fca5a5' }}>
          {status.text}
        </div>
      )}

      {loaded && (
        <div style={{ padding: '12px 20px', backgroundColor: '#f8fafc', borderTop: '1px solid #e2e8f0', display: 'flex', justifyContent: 'flex-end', gap: 8 }}>
          <button onClick={() => { setValues(Object.fromEntries(STOCK_ITEMS.map(it => [key(it.item_type, it.stock_type), savedValues[key(it.item_type, it.stock_type)] ?? '']))); setStatus(null); }}
            disabled={!hasChanges}
            style={{ padding: '6px 14px', borderRadius: 4, border: '1px solid #cbd5e1', backgroundColor: '#fff', color: '#475569', fontSize: '9pt', cursor: hasChanges ? 'pointer' : 'default' }}>
            Reset
          </button>
          <button onClick={handleSave} disabled={saving || !hasChanges}
            style={{ padding: '6px 16px', borderRadius: 4, border: 'none',
                     backgroundColor: hasChanges ? '#10b981' : '#94a3b8', color: '#fff',
                     fontWeight: 600, fontSize: '9pt', cursor: hasChanges ? 'pointer' : 'default' }}>
            {saving ? 'Saving...' : 'Save to DB'}
          </button>
        </div>
      )}
    </div>
  );
}

function ConversionCard({ apiBase }) {
  const getDefaultFy = () => {
    const d = new Date();
    return (d.getMonth() + 1 >= 4 ? d.getFullYear() : d.getFullYear() - 1).toString();
  };
  const [fyStart, setFyStart] = useState(getDefaultFy);
  const [convData, setConvData] = useState({});
  const [edits, setEdits] = useState({});
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [status, setStatus] = useState(null);

  const fyMonths = useMemo(() => {
    const y = parseInt(fyStart);
    return [`${y}-04`,`${y}-05`,`${y}-06`,`${y}-07`,`${y}-08`,`${y}-09`,`${y}-10`,`${y}-11`,`${y}-12`,`${y+1}-01`,`${y+1}-02`,`${y+1}-03`];
  }, [fyStart]);

  const loadData = useCallback(async () => {
    setLoading(true);
    setEdits({});
    try {
      const res = await fetch(`${apiBase}/api/conversion-data?fy_start=${fyStart}`);
      if (!res.ok) throw new Error(await res.text());
      const json = await res.json();
      setConvData(json.data);
    } catch (err) {
      setStatus({ type: 'error', text: `Load failed: ${err.message}` });
    } finally {
      setLoading(false);
    }
  }, [fyStart, apiBase]);

  useEffect(() => { loadData(); }, [loadData]);

  const currentVal = m => edits[m] !== undefined ? edits[m] : String(convData[m] ?? '');
  const hasEdits = fyMonths.some(m => edits[m] !== undefined && edits[m] !== String(convData[m] ?? ''));

  const handleSave = async () => {
    setSaving(true);
    setStatus(null);
    const entries = fyMonths
      .filter(m => edits[m] !== undefined && edits[m] !== '')
      .map(m => ({ month: m, value: parseFloat(edits[m]) }))
      .filter(e => !isNaN(e.value));
    try {
      const res = await fetch(`${apiBase}/api/conversion-entry`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ entries }),
      });
      if (!res.ok) throw new Error(await res.text());
      setStatus({ type: 'success', text: `Saved ${entries.length} conversion value(s).` });
      await loadData();
    } catch (err) {
      setStatus({ type: 'error', text: `Save failed: ${err.message}` });
    } finally {
      setSaving(false);
    }
  };

  return (
    <div style={{ backgroundColor: '#fff', border: '1px solid #e2e8f0', borderRadius: '8px', overflow: 'hidden', marginTop: '24px' }}>
      <div style={{ padding: '14px 20px', backgroundColor: '#1e3a5f', color: '#f1f5f9', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <span style={{ fontWeight: '700', fontSize: '10pt' }}>Conversion (SAIL) — Monthly Actuals</span>
        <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
          <span style={{ fontSize: '9pt', color: '#94a3b8' }}>FY:</span>
          <select value={fyStart} onChange={e => setFyStart(e.target.value)}
            style={{ fontSize: '9pt', padding: '2px 6px', borderRadius: '4px', border: '1px solid #475569', backgroundColor: '#334155', color: '#f1f5f9' }}>
            {FY_YEARS.map(y => <option key={y} value={y}>{y}-{String(parseInt(y)+1).slice(2)}</option>)}
          </select>
        </div>
      </div>

      {loading ? (
        <div style={{ padding: '24px', textAlign: 'center', color: '#64748b', fontSize: '10pt' }}>Loading...</div>
      ) : (
        <div style={{ overflowX: 'auto' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '9.5pt' }}>
            <thead>
              <tr style={{ backgroundColor: '#f1f5f9' }}>
                <th style={{ padding: '8px 16px', textAlign: 'left', fontWeight: '700', color: '#475569', borderBottom: '1px solid #e2e8f0', width: '50%' }}>Month</th>
                <th style={{ padding: '8px 12px', textAlign: 'center', fontWeight: '700', color: '#10b981', borderBottom: '1px solid #e2e8f0' }}>Actual ('000 T)</th>
              </tr>
            </thead>
            <tbody>
              {fyMonths.map((m, idx) => {
                const [y, mo] = m.split('-');
                const label = `${MONTH_SHORT[mo]}'${y.slice(2)}`;
                const val = currentVal(m);
                const isEdited = edits[m] !== undefined && edits[m] !== String(convData[m] ?? '');
                return (
                  <tr key={m} style={{ backgroundColor: isEdited ? '#fffbeb' : idx % 2 === 0 ? '#fff' : '#f8fafc', borderBottom: '1px solid #f1f5f9' }}>
                    <td style={{ padding: '6px 16px', color: '#1e293b', fontWeight: '500' }}>
                      {label}
                      {isEdited && <span style={{ marginLeft: '6px', fontSize: '8pt', color: '#d97706', fontWeight: '600' }}>edited</span>}
                    </td>
                    <td style={{ padding: '6px 12px', textAlign: 'center' }}>
                      <input type="number" step="0.001" value={val}
                        onChange={e => setEdits(prev => ({ ...prev, [m]: e.target.value }))}
                        placeholder="Enter actual"
                        style={{ width: '120px', padding: '4px 6px', border: `1px solid ${val ? '#6ee7b7' : '#cbd5e1'}`, borderRadius: '4px', textAlign: 'right', fontSize: '9pt', color: '#065f46', backgroundColor: val ? '#f0fdf4' : '#fff' }} />
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      {status && (
        <div style={{ margin: '0 16px 12px', padding: '8px 12px', borderRadius: '6px', fontSize: '0.8rem', backgroundColor: status.type === 'success' ? '#064e3b' : '#7f1d1d', color: status.type === 'success' ? '#6ee7b7' : '#fca5a5' }}>
          {status.text}
        </div>
      )}

      <div style={{ padding: '12px 20px', backgroundColor: '#f8fafc', borderTop: '1px solid #e2e8f0', display: 'flex', justifyContent: 'flex-end' }}>
        <button onClick={handleSave} disabled={saving || !hasEdits}
          style={{ padding: '6px 16px', fontSize: '9pt', backgroundColor: hasEdits ? '#10b981' : '#94a3b8', color: '#fff', border: 'none', borderRadius: '4px', cursor: hasEdits ? 'pointer' : 'default', fontWeight: '600' }}>
          {saving ? 'Saving...' : 'Save Conversion Data'}
        </button>
      </div>
    </div>
  );
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
          <Link href="/report" className="btn btn-secondary" style={{ width: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '8px', marginBottom: '8px', textDecoration: 'none' }}>
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7.5L14.5 2z"/><polyline points="14 2 14 8 20 8"/></svg>
            Report Engine
          </Link>
          <Link href="/data-entry/targets" className="btn btn-secondary" style={{ width: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '8px', marginBottom: '8px', textDecoration: 'none' }}>
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>
            TE Annual Targets
          </Link>
          <Link href="/data-entry/techno" className="btn btn-secondary" style={{ width: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '8px', marginBottom: '8px', textDecoration: 'none' }}>
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M12 20h9"/><path d="M16.5 3.5a2.121 2.121 0 013 3L7 19l-4 1 1-4L16.5 3.5z"/></svg>
            Techno Data Entry
          </Link>
          <Link href="/data-entry/ipt" className="btn btn-secondary" style={{ width: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '8px', marginBottom: '8px', textDecoration: 'none' }}>
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M17 1l4 4-4 4"/><path d="M3 11V9a4 4 0 0 1 4-4h14"/><path d="M7 23l-4-4 4-4"/><path d="M21 13v2a4 4 0 0 1-4 4H3"/></svg>
            IPT Data Entry
          </Link>
          <Link href="/records" className="btn btn-secondary" style={{ width: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '8px', textDecoration: 'none' }}>
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><polyline points="23 6 13.5 15.5 8.5 10.5 1 18"/><polyline points="17 6 23 6 23 12"/></svg>
            Production Records
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
                <span style={{ fontWeight: '700', fontSize: '10pt' }}>{plant} — {reportMonthDisplay}</span>
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

          <StockEntryCard apiBase={API_BASE_URL} />

          <HotMetalConsumptionEntry apiBase={API_BASE_URL} />

          <SpecialSteelManualEntry apiBase={API_BASE_URL} />

          <ConversionCard apiBase={API_BASE_URL} />
        </div>
      </div>
    </main>
  );
}
