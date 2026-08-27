'use client';

import RequireEditor from '@/components/RequireEditor';
import React, { useState, useEffect, useCallback } from 'react';
import GlobalNavbar from '@/components/GlobalNavbar';

const API = process.env.NEXT_PUBLIC_API_URL || '';
const FY_LIST = ['2025-26', '2026-27', '2027-28', '2028-29'];

function numOrNull(v) {
  const f = parseFloat(v);
  return Number.isNaN(f) ? null : f;
}
const s = (v) => (v === null || v === undefined ? '' : String(v));

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
  width: 78, padding: '5px 6px', border: '1px solid #dadce0', borderRadius: 4,
  textAlign: 'right', fontSize: 12.5,
};

function SpecialSteelPhysicalEntryInner() {
  const [fy, setFy] = useState('2026-27');
  const [meta, setMeta] = useState(null); // { financial_year, prev_fy, history_fys, rows[], notes[] }
  const [rows, setRows] = useState([]);   // editable copy, keyed by plant|series
  const [notes, setNotes] = useState([]);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [status, setStatus] = useState(null);

  const load = useCallback(async (targetFy) => {
    setLoading(true);
    setStatus(null);
    try {
      const res = await fetch(`${API}/api/special-steel-physical/grid?financial_year=${encodeURIComponent(targetFy)}`);
      if (!res.ok) throw new Error(await res.text());
      const d = await res.json();
      setMeta(d);
      setRows(d.rows.map((r) => ({
        plant: r.plant, series: r.series, series_label: r.series_label,
        capacity_kt: s(r.capacity_kt), best_actual_kt: s(r.best_actual_kt),
        best_year: s(r.best_year), remark: s(r.remark),
        history: Object.fromEntries((d.history_fys).map((f) => [f, s(r.history[f])])),
        prev_app_kt: s(r.prev_app_kt), prev_actual_kt: s(r.prev_actual_kt), abp_kt: s(r.abp_kt),
      })));
      setNotes((d.notes || []).map((n) => n.note_text));
    } catch (err) {
      setStatus({ type: 'error', text: `Load failed: ${err.message}` });
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(fy); }, [fy, load]);

  const set = (idx, patch) => setRows((prev) => prev.map((r, i) => (i === idx ? { ...r, ...patch } : r)));
  const setHist = (idx, f, v) => setRows((prev) => prev.map((r, i) => (i === idx ? { ...r, history: { ...r.history, [f]: v } } : r)));

  const save = async () => {
    setSaving(true);
    setStatus(null);
    try {
      const prevFy = meta.prev_fy;
      const metaOut = rows.map((r) => ({
        plant: r.plant, series: r.series,
        capacity_kt: numOrNull(r.capacity_kt), best_actual_kt: numOrNull(r.best_actual_kt),
        best_year: r.best_year, remark: r.remark,
      }));
      const perfOut = [];
      rows.forEach((r) => {
        meta.history_fys.forEach((f) => {
          perfOut.push({ financial_year: f, plant: r.plant, series: r.series, metric: 'actual', value_kt: numOrNull(r.history[f]) });
        });
        perfOut.push({ financial_year: prevFy, plant: r.plant, series: r.series, metric: 'plan', value_kt: numOrNull(r.prev_app_kt) });
        perfOut.push({ financial_year: prevFy, plant: r.plant, series: r.series, metric: 'actual', value_kt: numOrNull(r.prev_actual_kt) });
        perfOut.push({ financial_year: fy, plant: r.plant, series: r.series, metric: 'plan', value_kt: numOrNull(r.abp_kt) });
      });
      const notesOut = notes.map((t, i) => ({ sort_order: i + 1, note_text: t })).filter((n) => n.note_text.trim());
      const res = await fetch(`${API}/api/special-steel-physical/grid`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ financial_year: fy, prev_fy: prevFy, meta: metaOut, perf: perfOut, notes: notesOut }),
      });
      if (!res.ok) throw new Error(await res.text());
      setStatus({ type: 'success', text: 'Saved.' });
      await load(fy);
    } catch (err) {
      setStatus({ type: 'error', text: `Save failed: ${err.message}` });
    } finally {
      setSaving(false);
    }
  };

  const TH = { padding: '6px 6px', fontSize: 11, fontWeight: 700, color: '#5f6368', background: '#f8f9fa', borderBottom: '1px solid #dadce0', borderRight: '1px solid #eef1f4', textAlign: 'center', whiteSpace: 'nowrap' };
  const TD = { padding: '3px 4px', borderRight: '1px solid #eef1f4', borderBottom: '1px solid #f1f3f4', textAlign: 'center' };

  return (
    <div style={{ minHeight: '100vh', display: 'flex', flexDirection: 'column', background: '#fff' }}>
      <GlobalNavbar />
      <div style={{ flex: 1, maxWidth: 1700, margin: '0 auto', padding: '22px 20px', width: '100%', boxSizing: 'border-box' }}>
        <h2 style={{ fontSize: '1.6rem', fontWeight: 700, color: '#202124', margin: '0 0 4px' }}>
          Special Steel Plants — Physical Performance Entry
        </h2>
        <span style={{ fontSize: 13, color: '#5f6368' }}>
          Multi-year history grid (ASP / SSP / VISP), values in ’000 T. Seeded from the source workbook —
          edit to correct or extend. “APP / Actual” are for the previous FY, “ABP” for the selected FY.
        </span>

        <div style={{ display: 'flex', gap: 12, alignItems: 'center', flexWrap: 'wrap', margin: '18px 0', border: '1px solid #dadce0', borderRadius: 8, padding: '14px 18px' }}>
          <label style={{ fontSize: 13, fontWeight: 600, color: '#374151' }}>Financial Year</label>
          <select value={fy} onChange={(e) => setFy(e.target.value)}
            style={{ padding: '7px 10px', fontSize: 14, border: '1px solid #d1d5db', borderRadius: 4 }}>
            {FY_LIST.map((f) => <option key={f} value={f}>{f}</option>)}
          </select>
          <button onClick={save} disabled={saving || !meta}
            style={{ marginLeft: 'auto', padding: '8px 22px', fontSize: 14, fontWeight: 700, background: meta ? '#10b981' : '#9ca3af', color: '#fff', border: 'none', borderRadius: 6, cursor: meta ? 'pointer' : 'not-allowed' }}>
            {saving ? 'Saving…' : 'Save All'}
          </button>
        </div>

        <Notice type={status?.type} text={status?.text} />

        {loading && <div style={{ padding: 40, textAlign: 'center', color: '#5f6368' }}>Loading…</div>}

        {meta && !loading && (
          <>
            <div style={{ border: '1px solid #dadce0', borderRadius: 8, overflow: 'auto' }}>
              <table style={{ borderCollapse: 'collapse', width: '100%' }}>
                <thead>
                  <tr>
                    <th style={{ ...TH, textAlign: 'left' }}>Plant</th>
                    <th style={{ ...TH, textAlign: 'left' }}>Item</th>
                    <th style={TH}>Capacity</th>
                    <th style={TH}>Best Actual</th>
                    <th style={TH}>Best Year</th>
                    {meta.history_fys.map((f) => <th key={f} style={TH}>{f}</th>)}
                    <th style={TH}>{meta.prev_fy} APP</th>
                    <th style={TH}>{meta.prev_fy} Actual</th>
                    <th style={TH}>{fy} ABP</th>
                    <th style={{ ...TH, textAlign: 'left' }}>Remark</th>
                  </tr>
                </thead>
                <tbody>
                  {rows.map((r, idx) => (
                    <tr key={`${r.plant}-${r.series}`}>
                      <td style={{ ...TD, fontWeight: 700, textAlign: 'left' }}>{r.plant}</td>
                      <td style={{ ...TD, textAlign: 'left', fontWeight: 600, whiteSpace: 'nowrap' }}>{r.series_label}</td>
                      <td style={TD}><input value={r.capacity_kt} onChange={(e) => set(idx, { capacity_kt: e.target.value })} style={cellInput} /></td>
                      <td style={TD}><input value={r.best_actual_kt} onChange={(e) => set(idx, { best_actual_kt: e.target.value })} style={cellInput} /></td>
                      <td style={TD}><input value={r.best_year} onChange={(e) => set(idx, { best_year: e.target.value })} style={{ ...cellInput, width: 60, textAlign: 'center' }} /></td>
                      {meta.history_fys.map((f) => (
                        <td key={f} style={TD}><input value={r.history[f]} onChange={(e) => setHist(idx, f, e.target.value)} style={cellInput} /></td>
                      ))}
                      <td style={TD}><input value={r.prev_app_kt} onChange={(e) => set(idx, { prev_app_kt: e.target.value })} style={cellInput} /></td>
                      <td style={TD}><input value={r.prev_actual_kt} onChange={(e) => set(idx, { prev_actual_kt: e.target.value })} style={cellInput} /></td>
                      <td style={TD}><input value={r.abp_kt} onChange={(e) => set(idx, { abp_kt: e.target.value })} style={cellInput} /></td>
                      <td style={TD}><input value={r.remark} onChange={(e) => set(idx, { remark: e.target.value })} style={{ ...cellInput, width: 200, textAlign: 'left' }} /></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            <div style={{ marginTop: 24 }}>
              <div style={{ fontSize: 14, fontWeight: 700, color: '#1e293b', marginBottom: 6 }}>Footnotes ({fy})</div>
              {notes.map((t, i) => (
                <div key={i} style={{ display: 'flex', gap: 8, marginBottom: 6 }}>
                  <input value={t} onChange={(e) => setNotes((prev) => prev.map((x, j) => (j === i ? e.target.value : x)))}
                    style={{ flex: 1, padding: '7px 10px', border: '1px solid #dadce0', borderRadius: 4, fontSize: 13 }} />
                  <button onClick={() => setNotes((prev) => prev.filter((_, j) => j !== i))}
                    style={{ padding: '5px 12px', border: 'none', borderRadius: 4, background: '#ef4444', color: '#fff', fontSize: 13, cursor: 'pointer' }}>Del</button>
                </div>
              ))}
              <button onClick={() => setNotes((prev) => [...prev, ''])}
                style={{ padding: '6px 16px', fontSize: 13, fontWeight: 600, background: '#6366f1', color: '#fff', border: 'none', borderRadius: 4, cursor: 'pointer' }}>+ Add Note</button>
            </div>
          </>
        )}
      </div>
    </div>
  );
}

export default function SpecialSteelPhysicalEntryPage() {
  return (
    <RequireEditor>
      <SpecialSteelPhysicalEntryInner />
    </RequireEditor>
  );
}
