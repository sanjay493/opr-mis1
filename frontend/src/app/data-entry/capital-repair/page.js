'use client';

import RequireEditor from '@/components/RequireEditor';

import React, { useState, useCallback } from 'react';
import GlobalNavbar from '@/components/GlobalNavbar';

const API = process.env.NEXT_PUBLIC_API_URL || '';

const PLANTS = [
  { code: 'BSP', label: 'Bhilai Steel Plant' },
  { code: 'DSP', label: 'Durgapur Steel Plant' },
  { code: 'RSP', label: 'Rourkela Steel Plant' },
  { code: 'BSL', label: 'Bokaro Steel Plant' },
  { code: 'ISP', label: 'IISCO Steel Plant' },
];

const S = {
  H:  { padding: '10px 10px', textAlign: 'center', fontWeight: 700, color: '#5f6368',
        borderBottom: '1px solid #dadce0', fontSize: 13, backgroundColor: '#f8f9fa',
        whiteSpace: 'nowrap' },
  TD: { padding: '7px 8px', borderBottom: '1px solid #f0f4f8', fontSize: 14, verticalAlign: 'middle' },
};

function Notice({ type, text }) {
  if (!text) return null;
  const ok = type === 'success';
  return (
    <div style={{
      padding: '10px 16px', borderRadius: 6, marginBottom: 14, fontSize: 14,
      background: ok ? '#f0fdf4' : '#fef2f2',
      color: ok ? '#166534' : '#991b1b',
      border: `1px solid ${ok ? '#86efac' : '#fca5a5'}`,
    }}>
      {text}
    </div>
  );
}

function EntryRow({ row, onSaved }) {
  const [actual, setActual] = useState(row.actual || '');
  const [saving, setSaving] = useState(false);
  const [msg, setMsg]       = useState(null);

  const handleSave = async () => {
    setSaving(true);
    setMsg(null);
    try {
      const res = await fetch(`${API}/api/capital-repair-entry`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ id: row.id, actual }),
      });
      if (!res.ok) throw new Error(await res.text());
      setMsg('saved');
      onSaved({ ...row, actual });
      setTimeout(() => setMsg(null), 1500);
    } catch (err) {
      setMsg('err:' + err.message);
    } finally {
      setSaving(false);
    }
  };

  const rowBg = msg === 'saved' ? '#f0fdf4' : msg?.startsWith('err') ? '#fef2f2' : '#fff';

  return (
    <tr style={{ backgroundColor: rowBg }}>
      <td style={{ ...S.TD, fontWeight: 600 }}>{row.shop}</td>
      <td style={{ ...S.TD, textAlign: 'center' }}>{row.equipment}</td>
      <td style={S.TD}>{row.activity}</td>
      <td style={{ ...S.TD, textAlign: 'center' }}>{row.schedule_days}</td>
      <td style={{ ...S.TD, textAlign: 'center' }}>{row.period}</td>
      <td style={{ ...S.TD, textAlign: 'center' }}>
        <input type="text" value={actual} onChange={e => setActual(e.target.value)}
          placeholder="e.g. 12.5.26-20.5.26"
          style={{ width: 180, padding: '6px 8px', border: '1px solid #dadce0', borderRadius: 4, fontSize: 13 }} />
      </td>
      <td style={{ ...S.TD, textAlign: 'center' }}>
        {msg === 'saved'
          ? <span style={{ color: '#059669', fontWeight: 700, fontSize: 14 }}>✓</span>
          : msg?.startsWith('err')
          ? <span style={{ color: '#dc2626', fontSize: 12 }} title={msg.slice(4)}>✗</span>
          : (
          <button onClick={handleSave} disabled={saving}
            style={{ padding: '5px 14px', border: 'none', borderRadius: 4,
                     backgroundColor: '#10b981', color: '#fff', fontSize: 13,
                     cursor: 'pointer', fontWeight: 600 }}>
            {saving ? '…' : 'Save'}
          </button>
        )}
      </td>
    </tr>
  );
}

function CapitalRepairDataEntryPageInner() {
  const [plant, setPlant]     = useState('BSP');
  const [fy, setFy]           = useState('2026-27');
  const [rows, setRows]       = useState([]);
  const [loading, setLoading] = useState(false);
  const [status, setStatus]   = useState(null);
  const [loaded, setLoaded]   = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    setStatus(null);
    setLoaded(false);
    try {
      const res = await fetch(`${API}/api/capital-repair?plant=${encodeURIComponent(plant)}&fy=${encodeURIComponent(fy)}`);
      if (!res.ok) throw new Error(await res.text());
      const data = await res.json();
      setRows(data.rows);
      setLoaded(true);
    } catch (err) {
      setStatus({ type: 'error', text: `Load failed: ${err.message}` });
    } finally {
      setLoading(false);
    }
  }, [plant, fy]);

  const handleRowSaved = (idx, updated) => setRows(prev => prev.map((r, i) => i === idx ? updated : r));

  const plantLabel = PLANTS.find(p => p.code === plant)?.label || plant;

  return (
    <div style={{ height: '100vh', display: 'flex', flexDirection: 'column', background: '#ffffff' }}>
      <GlobalNavbar />

      <div style={{ flex: 1, overflow: 'auto', maxWidth: 1400, margin: '0 auto', padding: '22px 20px', width: '100%', boxSizing: 'border-box' }}>

        <div style={{ marginBottom: 18 }}>
          <h2 style={{ fontSize: '1.6rem', fontWeight: 700, color: '#202124', margin: '0 0 4px' }}>
            Capital Repair — Data Entry
          </h2>
          <span style={{ fontSize: 13, color: '#5f6368' }}>
            Update the &quot;Actual&quot; column for pages 36-40 as Capital Repair jobs are executed.
            Shop, Equipment, Activity, Schedule and Period are the fixed yearly plan and are not editable here.
          </span>
        </div>

        <div style={{
          display: 'flex', gap: 10, alignItems: 'center', flexWrap: 'wrap',
          marginBottom: 18, background: '#fff', border: '1px solid #dadce0',
          borderRadius: 8, padding: '14px 18px',
        }}>
          <label style={{ fontSize: 13, fontWeight: 600, color: '#374151' }}>Plant</label>
          <select value={plant} onChange={e => { setPlant(e.target.value); setLoaded(false); setRows([]); }}
            style={{ padding: '7px 10px', fontSize: 14, border: '1px solid #d1d5db', borderRadius: 4 }}>
            {PLANTS.map(p => <option key={p.code} value={p.code}>{p.code} — {p.label}</option>)}
          </select>

          <label style={{ fontSize: 13, fontWeight: 600, color: '#374151' }}>FY</label>
          <input type="text" value={fy} onChange={e => { setFy(e.target.value); setLoaded(false); setRows([]); }}
            placeholder="2026-27"
            style={{ width: 90, padding: '7px 10px', fontSize: 14, border: '1px solid #d1d5db', borderRadius: 4 }} />

          <button onClick={load} disabled={loading} style={{
            padding: '7px 20px', fontSize: 14, fontWeight: 600,
            background: '#1a73e8', color: '#fff', border: 'none', borderRadius: 4,
            cursor: loading ? 'not-allowed' : 'pointer',
          }}>
            {loading ? 'Loading…' : 'Load Records'}
          </button>

          <span style={{ marginLeft: 'auto', fontSize: 13, color: '#5f6368' }}>
            {plantLabel}{loading && ' ⟳'}
          </span>
        </div>

        <Notice type={status?.type} text={status?.text} />

        {!loaded && !loading && (
          <div style={{
            padding: 48, textAlign: 'center', backgroundColor: '#fff',
            border: '2px dashed #dadce0', borderRadius: 8, color: '#5f6368',
          }}>
            <p style={{ margin: 0, fontSize: 14 }}>
              Select a plant and FY, then click <strong>Load Records</strong>.
            </p>
          </div>
        )}

        {loading && (
          <div style={{ padding: 48, textAlign: 'center', color: '#5f6368', fontSize: 14 }}>
            Loading…
          </div>
        )}

        {loaded && (
          <div style={{ backgroundColor: '#fff', border: '1px solid #dadce0', borderRadius: 8, overflow: 'hidden' }}>
            <div style={{
              padding: '14px 18px', backgroundColor: '#f8f9fa', color: '#202124',
              display: 'flex', justifyContent: 'space-between', alignItems: 'center',
            }}>
              <span style={{ fontWeight: 700, fontSize: 14 }}>
                Capital Repair — {plantLabel} (FY {fy})
              </span>
              <span style={{ fontSize: 13, color: '#5f6368' }}>
                {rows.length} row{rows.length !== 1 ? 's' : ''}
              </span>
            </div>

            <div style={{ overflowX: 'auto', maxHeight: 'calc(100vh - 420px)', overflowY: 'auto' }}>
              <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 14 }}>
                <thead>
                  <tr style={{ position: 'sticky', top: 0, zIndex: 1 }}>
                    <th style={{ ...S.H, textAlign: 'left', width: 150 }}>Shop</th>
                    <th style={S.H}>Equipment</th>
                    <th style={{ ...S.H, textAlign: 'left' }}>Activity</th>
                    <th style={S.H}>Schedule (days)</th>
                    <th style={S.H}>Period</th>
                    <th style={S.H}>Actual</th>
                    <th style={S.H}>Save</th>
                  </tr>
                </thead>
                <tbody>
                  {rows.length === 0 && (
                    <tr>
                      <td colSpan={7} style={{ padding: 24, textAlign: 'center', color: '#5f6368', fontSize: 14 }}>
                        No Capital Repair rows for {plantLabel}, FY {fy}.
                      </td>
                    </tr>
                  )}
                  {rows.map((row, idx) => (
                    <EntryRow
                      key={row.id}
                      row={row}
                      onSaved={updated => handleRowSaved(idx, updated)}
                    />
                  ))}
                </tbody>
              </table>
            </div>

            <div style={{
              padding: '12px 18px', backgroundColor: '#f8f9fa', borderTop: '1px solid #dadce0',
            }}>
              <span style={{ fontSize: 13, color: '#5f6368' }}>
                Save each row individually. The Actual field is free text — enter a date range (e.g. &quot;12.5.26-20.5.26&quot;) as repairs happen.
              </span>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

export default function CapitalRepairDataEntryPage() {
  return (
    <RequireEditor>
      <CapitalRepairDataEntryPageInner />
    </RequireEditor>
  );
}
