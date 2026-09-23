'use client';

import RequireEditor from '@/components/RequireEditor';
import React, { useState, useEffect, useCallback } from 'react';
import GlobalNavbar from '@/components/GlobalNavbar';

const API = process.env.NEXT_PUBLIC_API_URL || '';

// BSP/DSP/RSP/BSL/ISP order, matching backend/page_major_unit_records.py's
// ISP_PLANTS — DSP has a registry (given directly, no source workbook) but
// no backfilled Daily figures, so its rows load with blank value/date,
// filled in here unit-by-unit going forward.
const PLANTS = [
  { code: 'BSP', name: 'Bhilai Steel Plant' },
  { code: 'DSP', name: 'Durgapur Steel Plant' },
  { code: 'RSP', name: 'Rourkela Steel Plant' },
  { code: 'BSL', name: 'Bokaro Steel Plant' },
  { code: 'ISP', name: 'IISCO Steel Plant' },
];

const s = (v) => (v === null || v === undefined ? '' : String(v));
function numOrNull(v) {
  const t = String(v).trim();
  if (t === '') return null;
  const f = parseFloat(t);
  return Number.isNaN(f) ? null : f;
}

function Notice({ type, text }) {
  if (!text) return null;
  const ok = type === 'success';
  return (
    <div style={{
      padding: '10px 16px', borderRadius: 6, margin: '14px 0', fontSize: 14,
      background: ok ? '#f0fdf4' : '#fef2f2', color: ok ? '#166534' : '#991b1b',
      border: `1px solid ${ok ? '#86efac' : '#fca5a5'}`,
    }}>{text}</div>
  );
}

const cellInput = {
  padding: '5px 6px', border: '1px solid #dadce0', borderRadius: 4, fontSize: 12.5,
};

function MajorUnitDailyEntryInner() {
  const [plant, setPlant] = useState('BSP');
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [status, setStatus] = useState(null);

  const load = useCallback(async (code) => {
    setLoading(true);
    setStatus(null);
    try {
      const res = await fetch(`${API}/api/major-unit-daily/${code}`);
      if (!res.ok) throw new Error(await res.text());
      const d = await res.json();
      setRows(d.rows.map((r) => ({
        unit_label: r.unit_label, unit_of_measure: r.unit_of_measure,
        value: s(r.value), record_date: s(r.record_date), remarks: s(r.remarks),
      })));
    } catch (err) {
      setStatus({ type: 'error', text: `Load failed: ${err.message}` });
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(plant); }, [plant, load]);

  const set = (idx, patch) => setRows((prev) => prev.map((r, i) => (i === idx ? { ...r, ...patch } : r)));

  const save = async () => {
    setSaving(true);
    setStatus(null);
    try {
      const rowsOut = rows.map((r) => ({
        unit_label: r.unit_label, value: numOrNull(r.value),
        record_date: r.record_date.trim() || null, remarks: r.remarks.trim() || null,
      }));
      const res = await fetch(`${API}/api/major-unit-daily/${plant}`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ rows: rowsOut }),
      });
      if (!res.ok) throw new Error(await res.text());
      setStatus({ type: 'success', text: 'Saved.' });
      await load(plant);
    } catch (err) {
      setStatus({ type: 'error', text: `Save failed: ${err.message}` });
    } finally {
      setSaving(false);
    }
  };

  const TH = { padding: '6px 6px', fontSize: 11, fontWeight: 700, color: '#5f6368', background: '#f8f9fa', borderBottom: '1px solid #dadce0', borderRight: '1px solid #eef1f4', textAlign: 'left', whiteSpace: 'nowrap' };
  const TD = { padding: '3px 4px', borderRight: '1px solid #eef1f4', borderBottom: '1px solid #f1f3f4' };

  return (
    <div style={{ minHeight: '100vh', display: 'flex', flexDirection: 'column', background: '#fff' }}>
      <GlobalNavbar />
      <div style={{ flex: 1, maxWidth: 1100, margin: '0 auto', padding: '22px 20px', width: '100%', boxSizing: 'border-box' }}>
        <h2 style={{ fontSize: '1.6rem', fontWeight: 700, color: '#202124', margin: '0 0 4px' }}>
          5 ISPs Major Units — Daily Best Record Entry
        </h2>
        <span style={{ fontSize: 13, color: '#5f6368' }}>
          Best-ever single-day production figure per major unit, with the date it was achieved — feeds
          Annexure-III of the report. Annual/Monthly bests aren&apos;t entered here; they&apos;re computed
          automatically from the plant&apos;s monthly production data.
        </span>

        <div style={{ display: 'flex', gap: 12, alignItems: 'center', flexWrap: 'wrap', margin: '18px 0', border: '1px solid #dadce0', borderRadius: 8, padding: '14px 18px' }}>
          <label style={{ fontSize: 13, fontWeight: 600, color: '#374151' }}>Plant</label>
          <select value={plant} onChange={(e) => setPlant(e.target.value)}
            style={{ padding: '7px 10px', fontSize: 14, border: '1px solid #d1d5db', borderRadius: 4 }}>
            {PLANTS.map((p) => <option key={p.code} value={p.code}>{p.name}</option>)}
          </select>
          <button onClick={save} disabled={saving || loading || rows.length === 0}
            style={{ marginLeft: 'auto', padding: '8px 22px', fontSize: 14, fontWeight: 700, background: rows.length ? '#10b981' : '#9ca3af', color: '#fff', border: 'none', borderRadius: 6, cursor: rows.length ? 'pointer' : 'not-allowed' }}>
            {saving ? 'Saving…' : 'Save All'}
          </button>
        </div>

        <Notice type={status?.type} text={status?.text} />

        {loading && <div style={{ padding: 40, textAlign: 'center', color: '#5f6368' }}>Loading…</div>}

        {!loading && rows.length === 0 && (
          <div style={{ padding: 40, textAlign: 'center', color: '#5f6368' }}>
            No major-unit registry for {plant} yet.
          </div>
        )}

        {!loading && rows.length > 0 && (
          <div style={{ border: '1px solid #dadce0', borderRadius: 8, overflow: 'auto' }}>
            <table style={{ borderCollapse: 'collapse', width: '100%' }}>
              <thead>
                <tr>
                  <th style={TH}>Unit</th>
                  <th style={TH}>Unit of Measure</th>
                  <th style={TH}>Best Value</th>
                  <th style={TH}>Date (YYYY-MM-DD)</th>
                  <th style={TH}>Remarks</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((r, idx) => (
                  <tr key={r.unit_label}>
                    <td style={{ ...TD, fontWeight: 600 }}>{r.unit_label}</td>
                    <td style={{ ...TD, color: '#5f6368' }}>{r.unit_of_measure}</td>
                    <td style={TD}><input value={r.value} onChange={(e) => set(idx, { value: e.target.value })} style={{ ...cellInput, width: 100, textAlign: 'right' }} /></td>
                    <td style={TD}><input value={r.record_date} placeholder="YYYY-MM-DD" onChange={(e) => set(idx, { record_date: e.target.value })} style={{ ...cellInput, width: 120 }} /></td>
                    <td style={TD}><input value={r.remarks} onChange={(e) => set(idx, { remarks: e.target.value })} style={{ ...cellInput, width: '100%', boxSizing: 'border-box' }} /></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}

export default function MajorUnitDailyEntryPage() {
  return (
    <RequireEditor>
      <MajorUnitDailyEntryInner />
    </RequireEditor>
  );
}
