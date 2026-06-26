'use client';

import React, { useState, useCallback } from 'react';

export default function HotMetalConsumptionEntry({ apiBase }) {
  const [month, setMonth] = useState(() => {
    const d = new Date();
    return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}`;
  });

  const PLANTS = ['BSP', 'DSP', 'RSP', 'BSL', 'ISP', 'SAIL'];

  const [entries, setEntries] = useState({
    BSP: '',
    DSP: '',
    RSP: '',
    BSL: '',
    ISP: '',
    SAIL: ''
  });

  const [savedEntries, setSavedEntries] = useState({});
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [status, setStatus] = useState(null);
  const [loaded, setLoaded] = useState(false);

  const handleLoad = useCallback(async () => {
    setLoading(true);
    setStatus(null);
    setLoaded(false);
    try {
      const res = await fetch(
        `${apiBase}/api/techno-monthly-data?month=${encodeURIComponent(month)}&param_names=Hot Metal Consumption`
      );
      if (!res.ok) throw new Error(await res.text());
      const data = await res.json();

      const entriesMap = {};
      const savedMap = {};

      PLANTS.forEach(plant => {
        entriesMap[plant] = '';
        savedMap[plant] = '';
      });

      data.data.forEach(item => {
        if (entriesMap.hasOwnProperty(item.row_label)) {
          const val = item.actual !== null ? String(item.actual) : '';
          entriesMap[item.row_label] = val;
          savedMap[item.row_label] = val;
        }
      });

      setEntries(entriesMap);
      setSavedEntries(savedMap);
      setLoaded(true);
    } catch (err) {
      setStatus({ type: 'error', text: `Load failed: ${err.message}` });
    } finally {
      setLoading(false);
    }
  }, [month, apiBase]);

  const handleChange = (plant, value) => {
    setEntries(prev => ({ ...prev, [plant]: value }));
  };

  const handleSave = async () => {
    setSaving(true);
    setStatus(null);

    try {
      // Get param_ids for each plant
      const res = await fetch(`${apiBase}/api/techno-monthly-data?month=${encodeURIComponent(month)}&param_names=Hot Metal Consumption`);
      if (!res.ok) throw new Error(await res.text());
      const data = await res.json();

      const paramMap = {};
      data.data.forEach(item => {
        paramMap[item.row_label] = item.param_id;
      });

      const rows = PLANTS
        .filter(plant => entries[plant] !== '' && entries[plant] !== savedEntries[plant])
        .map(plant => ({
          param_id: paramMap[plant],
          actual: entries[plant] ? parseFloat(entries[plant]) : null
        }))
        .filter(row => row.actual !== null);

      if (rows.length === 0) {
        setStatus({ type: 'error', text: 'No changes to save.' });
        setSaving(false);
        return;
      }

      const saveRes = await fetch(`${apiBase}/api/techno-manual-save`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          month: month,
          rows: rows
        })
      });

      if (!saveRes.ok) throw new Error(await saveRes.text());
      const result = await saveRes.json();

      setStatus({ type: 'success', text: `Saved ${result.saved} Hot Metal Consumption value(s) for ${month}.` });

      const newSaved = { ...savedEntries };
      PLANTS.forEach(plant => {
        if (entries[plant] !== '') newSaved[plant] = entries[plant];
      });
      setSavedEntries(newSaved);
    } catch (err) {
      setStatus({ type: 'error', text: `Save failed: ${err.message}` });
    } finally {
      setSaving(false);
    }
  };

  const hasChanges = PLANTS.some(plant => entries[plant] !== (savedEntries[plant] || ''));

  return (
    <div style={{ backgroundColor: '#fff', border: '1px solid #e2e8f0', borderRadius: '8px', overflow: 'hidden', marginTop: '24px' }}>
      {/* Header */}
      <div style={{ padding: '14px 20px', backgroundColor: '#1e3a5f', color: '#f1f5f9', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <span style={{ fontWeight: 700, fontSize: '10pt' }}>Hot Metal Consumption — Manual Entry</span>
        <span style={{ fontSize: '8.5pt', color: '#94a3b8' }}>Values in Tonnes (T) per month</span>
      </div>

      {/* Controls */}
      <div style={{ padding: '14px 20px', backgroundColor: '#f8fafc', borderBottom: '1px solid #e2e8f0', display: 'flex', gap: 12, alignItems: 'flex-end', flexWrap: 'wrap' }}>
        <div>
          <div style={{ fontSize: '8pt', color: '#64748b', marginBottom: 4 }}>Report Month</div>
          <input
            type="month"
            value={month}
            onChange={e => { setMonth(e.target.value); setLoaded(false); setEntries(Object.fromEntries(PLANTS.map(p => [p, '']))); }}
            style={{ padding: '5px 10px', borderRadius: 4, border: '1px solid #cbd5e1', fontSize: '9pt', backgroundColor: '#fff' }}
          />
        </div>
        <button
          onClick={handleLoad}
          disabled={loading}
          style={{
            padding: '6px 16px',
            borderRadius: 4,
            border: 'none',
            backgroundColor: '#6366f1',
            color: '#fff',
            fontWeight: 600,
            fontSize: '9pt',
            cursor: 'pointer'
          }}
        >
          {loading ? 'Loading...' : 'Load'}
        </button>
      </div>

      {/* Grid */}
      {loaded && (
        <div style={{ overflowX: 'auto' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead>
              <tr>
                <th style={{ padding: '8px 14px', textAlign: 'left', fontWeight: 700, color: '#475569', borderBottom: '1px solid #e2e8f0', fontSize: '9pt', backgroundColor: '#f1f5f9' }}>Plant / Entity</th>
                <th style={{ padding: '8px 14px', textAlign: 'right', fontWeight: 700, color: '#475569', borderBottom: '1px solid #e2e8f0', fontSize: '9pt', backgroundColor: '#f1f5f9' }}>Hot Metal Consumption (T)</th>
                <th style={{ padding: '8px 14px', textAlign: 'center', fontWeight: 700, color: '#475569', borderBottom: '1px solid #e2e8f0', fontSize: '9pt', backgroundColor: '#f1f5f9' }}>Status</th>
              </tr>
            </thead>
            <tbody>
              {PLANTS.map((plant, i) => {
                const current = entries[plant] || '';
                const saved = savedEntries[plant] || '';
                const changed = current !== saved && current !== '';
                return (
                  <tr key={plant} style={{ backgroundColor: changed ? '#fffbeb' : i % 2 === 0 ? '#fff' : '#f8fafc' }}>
                    <td style={{ padding: '7px 14px', borderBottom: '1px solid #f1f5f9', fontSize: '9.5pt', fontWeight: 500, color: '#1e293b' }}>
                      {plant}
                    </td>
                    <td style={{ padding: '7px 14px', borderBottom: '1px solid #f1f5f9', textAlign: 'right' }}>
                      <input
                        type="number"
                        step="0.01"
                        value={current}
                        placeholder={saved ? saved : 'Enter value'}
                        onChange={e => handleChange(plant, e.target.value)}
                        style={{
                          width: 140,
                          padding: '4px 8px',
                          border: `1px solid ${changed ? '#fbbf24' : current ? '#6ee7b7' : '#cbd5e1'}`,
                          borderRadius: 4,
                          textAlign: 'right',
                          fontSize: '9pt',
                          color: '#065f46',
                          backgroundColor: changed ? '#fffbeb' : current ? '#f0fdf4' : '#fff'
                        }}
                      />
                    </td>
                    <td style={{ padding: '7px 14px', borderBottom: '1px solid #f1f5f9', textAlign: 'center', fontSize: '8.5pt' }}>
                      {changed ? (
                        <span style={{ color: '#d97706', fontWeight: 600 }}>edited</span>
                      ) : saved ? (
                        <span style={{ color: '#059669' }}>saved</span>
                      ) : (
                        <span style={{ color: '#94a3b8' }}>—</span>
                      )}
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
          Select month and click <strong>Load</strong> to view / edit hot metal consumption values.
        </div>
      )}

      {status && (
        <div style={{
          margin: '0 16px 12px',
          padding: '8px 12px',
          borderRadius: 6,
          fontSize: '8.5pt',
          backgroundColor: status.type === 'success' ? '#064e3b' : '#7f1d1d',
          color: status.type === 'success' ? '#6ee7b7' : '#fca5a5'
        }}>
          {status.text}
        </div>
      )}

      {loaded && (
        <div style={{ padding: '12px 20px', backgroundColor: '#f8fafc', borderTop: '1px solid #e2e8f0', display: 'flex', justifyContent: 'flex-end', gap: 8 }}>
          <button
            onClick={() => {
              setEntries(Object.fromEntries(PLANTS.map(p => [p, savedEntries[p] || ''])));
              setStatus(null);
            }}
            disabled={!hasChanges}
            style={{
              padding: '6px 14px',
              borderRadius: 4,
              border: '1px solid #cbd5e1',
              backgroundColor: '#fff',
              color: '#475569',
              fontSize: '9pt',
              cursor: hasChanges ? 'pointer' : 'default'
            }}
          >
            Reset
          </button>
          <button
            onClick={handleSave}
            disabled={saving || !hasChanges}
            style={{
              padding: '6px 16px',
              borderRadius: 4,
              border: 'none',
              backgroundColor: hasChanges ? '#10b981' : '#94a3b8',
              color: '#fff',
              fontWeight: 600,
              fontSize: '9pt',
              cursor: hasChanges ? 'pointer' : 'default'
            }}
          >
            {saving ? 'Saving...' : 'Save to DB'}
          </button>
        </div>
      )}
    </div>
  );
}
