'use client';

import React, { useState, useEffect } from 'react';
import GlobalNavbar from '@/components/GlobalNavbar';
import { useStockData, useSaveStockEntry } from '@/hooks/useDataEntryAPI';

const STOCK_PLANTS = ['BSP', 'DSP', 'RSP', 'BSL', 'ISP'];
const STOCK_ITEMS = [
  { item_type: 'SLABS',          stock_type: 'INPROCESS', label: 'SLABS — [a] INPROCESS' },
  { item_type: 'SLABS',          stock_type: 'FOR SALE',  label: 'SLABS — [b] FOR SALE' },
  { item_type: 'BLOOM/BILLETS',  stock_type: 'INPROCESS', label: 'BLOOM/BILLETS — [a] INPROCESS' },
  { item_type: 'BLOOM/BILLETS',  stock_type: 'FOR SALE',  label: 'BLOOM/BILLETS — [b] FOR SALE' },
  { item_type: 'FINISHED STEEL', stock_type: '',          label: 'FINISHED STEEL' },
  { item_type: 'PIG IRON',       stock_type: '',          label: 'PIG IRON' },
];

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://127.0.0.1:8082';

function StockEntryCard({ apiBase }) {
  const defaultMonth = () => {
    const d = new Date();
    d.setDate(1);
    return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}`;
  };
  const [plant, setPlant] = useState('BSP');
  const [stockMonth, setStockMonth] = useState(defaultMonth);
  const [values, setValues] = useState({});
  const [savedValues, setSavedValues] = useState({});
  const [status, setStatus] = useState(null);
  const [shouldLoad, setShouldLoad] = useState(false);

  const key = (item_type, stock_type) => `${item_type}||${stock_type}`;

  // Use React Query to fetch stock data
  const { data: stockData, isLoading: loading, error: loadError } = useStockData(plant, stockMonth, shouldLoad);
  const { mutate: saveEntry, isPending: saving } = useSaveStockEntry();

  // Update local state when stock data loads
  useEffect(() => {
    if (stockData?.data) {
      const map = {};
      stockData.data.forEach(r => { map[key(r.item_type, r.stock_type)] = String(r.stock ?? ''); });
      setSavedValues(map);
      const edits = {};
      STOCK_ITEMS.forEach(it => { edits[key(it.item_type, it.stock_type)] = map[key(it.item_type, it.stock_type)] ?? ''; });
      setValues(edits);
      setStatus(null);
    }
  }, [stockData]);

  // Show load error
  useEffect(() => {
    if (loadError) {
      setStatus({ type: 'error', text: `Load failed: ${loadError.message}` });
    }
  }, [loadError]);

  const handleLoad = () => {
    setShouldLoad(true);
  };

  const handleSave = () => {
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
    setStatus(null);
    saveEntry(
      { entries },
      {
        onSuccess: (json) => {
          setStatus({ type: 'success', text: json.message || 'Saved successfully!' });
          const newSaved = { ...savedValues };
          entries.forEach(e => { newSaved[key(e.item_type, e.stock_type)] = String(e.stock); });
          setSavedValues(newSaved);
        },
        onError: (err) => {
          setStatus({ type: 'error', text: `Save failed: ${err.message}` });
        },
      }
    );
  };

  const hasChanges = STOCK_ITEMS.some(it => {
    const k = key(it.item_type, it.stock_type);
    const cur = values[k] ?? '';
    const saved = savedValues[k] ?? '';
    return cur !== saved && cur !== '';
  });

  const H = { padding: '8px 14px', textAlign: 'left', fontWeight: 700, color: '#5f6368', borderBottom: '1px solid #dadce0', fontSize: '9pt', backgroundColor: '#f8f9fa' };
  const TD = { padding: '7px 14px', borderBottom: '1px solid #f1f3f4', fontSize: '9.5pt' };

  return (
    <>
      <GlobalNavbar />
      <main style={{ padding: '40px 32px', maxWidth: '1200px', margin: '0 auto' }}>
        <h1 style={{ fontSize: '24px', fontWeight: '800', color: '#202124', marginBottom: '24px' }}>📦 Opening Stock</h1>

        <div style={{ backgroundColor: '#fff', border: '1px solid #dadce0', borderRadius: '8px', overflow: 'hidden' }}>
          {/* Header */}
          <div style={{ padding: '14px 20px', backgroundColor: '#e8f0fe', color: '#174ea6', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <span style={{ fontWeight: 700, fontSize: '10pt' }}>Opening Stock — Manual Entry</span>
            <span style={{ fontSize: '8.5pt', color: '#174ea6' }}>Values in '000T · upserts stock_table</span>
          </div>

          {/* Controls */}
          <div style={{ padding: '14px 20px', backgroundColor: '#f8f9fa', borderBottom: '1px solid #dadce0', display: 'flex', gap: 12, alignItems: 'flex-end', flexWrap: 'wrap' }}>
            <div>
              <div style={{ fontSize: '8pt', color: '#5f6368', marginBottom: 4 }}>Plant</div>
              <select value={plant} onChange={e => { setPlant(e.target.value); setValues({}); setSavedValues({}); setShouldLoad(false); }}
                style={{ padding: '5px 10px', borderRadius: 4, border: '1px solid #dadce0', fontSize: '9pt', backgroundColor: '#fff', color: '#202124' }}>
                {STOCK_PLANTS.map(p => <option key={p} value={p}>{p}</option>)}
              </select>
            </div>
            <div>
              <div style={{ fontSize: '8pt', color: '#5f6368', marginBottom: 4 }}>Stock as on 1st of</div>
              <input type="month" value={stockMonth} onChange={e => { setStockMonth(e.target.value); setValues({}); setSavedValues({}); setShouldLoad(false); }}
                style={{ padding: '5px 10px', borderRadius: 4, border: '1px solid #dadce0', fontSize: '9pt', backgroundColor: '#fff', color: '#202124' }} />
            </div>
            <button onClick={handleLoad} disabled={loading}
              style={{ padding: '6px 16px', borderRadius: 4, border: 'none', backgroundColor: '#6366f1', color: '#fff', fontWeight: 600, fontSize: '9pt', cursor: 'pointer' }}>
              {loading ? 'Loading...' : 'Load'}
            </button>
          </div>

          {/* Grid */}
          {stockData && (
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
                      <tr key={k} style={{ backgroundColor: changed ? '#fef7e0' : i % 2 === 0 ? '#fff' : '#f8f9fa' }}>
                        <td style={{ ...TD, fontWeight: 500, color: '#202124' }}>{it.label}</td>
                        <td style={{ ...TD, textAlign: 'right' }}>
                          <input type="number" step="0.001" value={cur} placeholder={hasVal ? saved : 'Enter value'}
                            onChange={e => setValues(prev => ({ ...prev, [k]: e.target.value }))}
                            style={{ width: 120, padding: '4px 8px', border: `1px solid ${changed ? '#fbbf24' : cur ? '#a8dab5' : '#dadce0'}`,
                                     borderRadius: 4, textAlign: 'right', fontSize: '9pt',
                                     color: '#065f46', backgroundColor: changed ? '#fffbeb' : cur ? '#f0fdf4' : '#fff' }} />
                        </td>
                        <td style={{ ...TD, textAlign: 'center', fontSize: '8.5pt' }}>
                          {changed
                            ? <span style={{ color: '#d97706', fontWeight: 600 }}>edited</span>
                            : hasVal
                            ? <span style={{ color: '#059669' }}>{parseFloat(saved).toFixed(3)}</span>
                            : <span style={{ color: '#5f6368' }}>—</span>}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}

          {!stockData && !loading && (
            <div style={{ padding: '32px', textAlign: 'center', color: '#5f6368', fontSize: '9.5pt' }}>
              Select plant and month, then click <strong>Load</strong> to view / edit stock values.
            </div>
          )}

          {status && (
            <div style={{ margin: '0 16px 12px', padding: '8px 12px', borderRadius: 6, fontSize: '8.5pt',
                          backgroundColor: status.type === 'success' ? '#e6f4ea' : '#fce8e6',
                          color: status.type === 'success' ? '#188038' : '#d93025' }}>
              {status.text}
            </div>
          )}

          {stockData && (
            <div style={{ padding: '12px 20px', backgroundColor: '#f8f9fa', borderTop: '1px solid #dadce0', display: 'flex', justifyContent: 'flex-end', gap: 8 }}>
              <button onClick={() => { setValues(Object.fromEntries(STOCK_ITEMS.map(it => [key(it.item_type, it.stock_type), savedValues[key(it.item_type, it.stock_type)] ?? '']))); setStatus(null); }}
                disabled={!hasChanges}
                style={{ padding: '6px 14px', borderRadius: 4, border: '1px solid #dadce0', backgroundColor: '#fff', color: '#5f6368', fontSize: '9pt', cursor: hasChanges ? 'pointer' : 'default' }}>
                Reset
              </button>
              <button onClick={handleSave} disabled={saving || !hasChanges}
                style={{ padding: '6px 16px', borderRadius: 4, border: 'none',
                         backgroundColor: hasChanges ? '#10b981' : '#5f6368', color: '#fff',
                         fontWeight: 600, fontSize: '9pt', cursor: hasChanges ? 'pointer' : 'default' }}>
                {saving ? 'Saving...' : 'Save to DB'}
              </button>
            </div>
          )}
        </div>
      </main>
    </>
  );
}

export default function OpeningStockPage() {
  return <StockEntryCard apiBase={API_BASE_URL} />;
}
