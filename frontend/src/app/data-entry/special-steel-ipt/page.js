'use client';

import RequireEditor from '@/components/RequireEditor';
import React, { useState, useEffect, useCallback, useRef } from 'react';
import GlobalNavbar from '@/components/GlobalNavbar';

const API = process.env.NEXT_PUBLIC_API_URL || '';

// Must match backend main.py's _IPT_PLANTS.
const PLANTS = ['BSP', 'DSP', 'ISP', 'RSP', 'BSL', 'ASP', 'SSP', 'VISL', 'CFP'];

function numOrNull(v) {
  const f = parseFloat(v);
  return Number.isNaN(f) ? null : f;
}

function Notice({ type, text }) {
  if (!text) return null;
  const ok = type === 'success';
  return (
    <div style={{
      padding: '10px 16px', borderRadius: 6, marginBottom: 14, fontSize: 14,
      background: ok ? '#f0fdf4' : '#fef2f2', color: ok ? '#166534' : '#991b1b',
      border: `1px solid ${ok ? '#86efac' : '#fca5a5'}`,
    }}>{text}</div>
  );
}

function Sel({ value, onChange, options, width = 90 }) {
  return (
    <select value={value} onChange={(e) => onChange(e.target.value)}
      style={{ width, padding: '6px 8px', border: '1px solid #dadce0', borderRadius: 4, fontSize: 13, background: '#fff' }}>
      {options.map((o) => <option key={o} value={o}>{o}</option>)}
      {!options.includes(value) && value !== '' && <option value={value}>{value}</option>}
    </select>
  );
}

function SpecialSteelIptEntryInner() {
  const [fys, setFys] = useState([]);
  const [fy, setFy] = useState('');
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [status, setStatus] = useState(null);
  const uid = useRef(0);
  const nextUid = () => (uid.current += 1);

  useEffect(() => {
    fetch(`${API}/api/special-steel-ipt-requirement/fys`)
      .then((r) => r.json())
      .then((d) => {
        setFys(d.fys || []);
        if (d.fys && d.fys.length) setFy((prev) => prev || d.fys[0]);
      })
      .catch(() => {});
  }, []);

  const load = useCallback(async (targetFy) => {
    if (!targetFy) return;
    setLoading(true);
    setStatus(null);
    try {
      const res = await fetch(`${API}/api/special-steel-ipt-requirement?fy=${encodeURIComponent(targetFy)}`);
      if (!res.ok) throw new Error(await res.text());
      const d = await res.json();
      setRows((d.rows || []).map((r) => ({
        _uid: nextUid(),
        item: r.item, from_plant: r.from_plant, to_plant: r.to_plant,
        plan_kt: r.plan_kt ?? '', sort_order: r.sort_order ?? 0,
        orig_item: r.item, orig_from_plant: r.from_plant, orig_to_plant: r.to_plant,
      })));
    } catch (err) {
      setStatus({ type: 'error', text: `Load failed: ${err.message}` });
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { if (fy) load(fy); }, [fy, load]);

  const addRow = () => {
    const maxSort = rows.reduce((mx, r) => Math.max(mx, parseInt(r.sort_order, 10) || 0), 0);
    setRows((prev) => [...prev, {
      _uid: nextUid(), item: '', from_plant: 'BSP', to_plant: 'SSP',
      plan_kt: '', sort_order: maxSort + 1,
      orig_item: null, orig_from_plant: null, orig_to_plant: null,
    }]);
  };

  const change = (u, patch) => setRows((prev) => prev.map((r) => (r._uid === u ? { ...r, ...patch } : r)));

  const del = async (row) => {
    if (row.orig_item == null) {
      setRows((prev) => prev.filter((r) => r._uid !== row._uid));
      return;
    }
    if (!confirm(`Delete: ${row.item} ${row.from_plant} → ${row.to_plant}?`)) return;
    try {
      const res = await fetch(`${API}/api/special-steel-ipt-requirement/delete`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ fy, item: row.orig_item, from_plant: row.orig_from_plant, to_plant: row.orig_to_plant }),
      });
      if (!res.ok) throw new Error(await res.text());
      setRows((prev) => prev.filter((r) => r._uid !== row._uid));
    } catch (err) {
      setStatus({ type: 'error', text: `Delete failed: ${err.message}` });
    }
  };

  const saveAll = async () => {
    const valid = rows.filter((r) => r.item.trim() && r.from_plant && r.to_plant && r.from_plant !== r.to_plant);
    if (!valid.length) {
      setStatus({ type: 'error', text: 'Nothing to save — need Item, From, To (From ≠ To).' });
      return;
    }
    setSaving(true);
    setStatus(null);
    try {
      const entries = valid.map((r) => ({
        item: r.item.trim(), from_plant: r.from_plant, to_plant: r.to_plant,
        plan_kt: numOrNull(r.plan_kt), sort_order: parseInt(r.sort_order, 10) || 0,
        orig_item: r.orig_item, orig_from_plant: r.orig_from_plant, orig_to_plant: r.orig_to_plant,
      }));
      const res = await fetch(`${API}/api/special-steel-ipt-requirement/bulk`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ fy, entries }),
      });
      if (!res.ok) throw new Error(await res.text());
      const d = await res.json();
      setStatus({ type: 'success', text: `Saved ${d.saved} row(s).` });
      await load(fy);
    } catch (err) {
      setStatus({ type: 'error', text: `Save failed: ${err.message}` });
    } finally {
      setSaving(false);
    }
  };

  const TD = { padding: '6px 8px', borderBottom: '1px solid #f0f4f8', fontSize: 14 };
  const TH = { padding: '10px 8px', textAlign: 'left', fontWeight: 700, color: '#5f6368', fontSize: 13, background: '#f8f9fa', borderBottom: '1px solid #dadce0' };
  const newCount = rows.filter((r) => r.orig_item == null).length;

  return (
    <div style={{ minHeight: '100vh', display: 'flex', flexDirection: 'column', background: '#fff' }}>
      <GlobalNavbar />
      <div style={{ flex: 1, maxWidth: 1000, margin: '0 auto', padding: '22px 20px', width: '100%', boxSizing: 'border-box' }}>
        <h2 style={{ fontSize: '1.6rem', fontWeight: 700, color: '#202124', margin: '0 0 4px' }}>
          Special Steel Plants — IPT Requirement Entry
        </h2>
        <span style={{ fontSize: 13, color: '#5f6368' }}>
          Annual inter-plant-transfer requirement list for the Special Steel Plants Physical Performance report.
          Plan is in ’000 T. Distinct from the monthly IPT Status.
        </span>

        <div style={{ display: 'flex', gap: 10, alignItems: 'center', flexWrap: 'wrap', margin: '18px 0', border: '1px solid #dadce0', borderRadius: 8, padding: '14px 18px' }}>
          <label style={{ fontSize: 13, fontWeight: 600, color: '#374151' }}>Financial Year</label>
          <select value={fy} onChange={(e) => setFy(e.target.value)}
            style={{ padding: '7px 10px', fontSize: 14, border: '1px solid #d1d5db', borderRadius: 4, minWidth: 120 }}>
            {fys.map((f) => <option key={f} value={f}>{f}</option>)}
            {fy && !fys.includes(fy) && <option value={fy}>{fy}</option>}
          </select>
          <button onClick={addRow} style={{ padding: '7px 18px', fontSize: 14, fontWeight: 600, background: '#6366f1', color: '#fff', border: 'none', borderRadius: 4, cursor: 'pointer' }}>+ Add Row</button>
          <button onClick={saveAll} disabled={saving || !rows.length}
            style={{ marginLeft: 'auto', padding: '7px 22px', fontSize: 14, fontWeight: 700, background: rows.length ? '#10b981' : '#9ca3af', color: '#fff', border: 'none', borderRadius: 4, cursor: rows.length ? 'pointer' : 'not-allowed' }}>
            {saving ? 'Saving…' : `Save All${newCount ? ` (${newCount} new)` : ''}`}
          </button>
        </div>

        <Notice type={status?.type} text={status?.text} />

        {loading ? (
          <div style={{ padding: 40, textAlign: 'center', color: '#5f6368' }}>Loading…</div>
        ) : (
          <div style={{ border: '1px solid #dadce0', borderRadius: 8, overflow: 'hidden' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse' }}>
              <thead>
                <tr>
                  <th style={TH}>Item (’000 T)</th>
                  <th style={{ ...TH, textAlign: 'center' }}>From</th>
                  <th style={{ ...TH, textAlign: 'center' }}>To</th>
                  <th style={{ ...TH, textAlign: 'center', width: 70 }}>Sort</th>
                  <th style={{ ...TH, textAlign: 'right' }}>Plan</th>
                  <th style={{ ...TH, textAlign: 'center', width: 60 }} />
                </tr>
              </thead>
              <tbody>
                {rows.map((r) => (
                  <tr key={r._uid} style={{ background: r.orig_item == null ? '#fffbeb' : '#fff' }}>
                    <td style={TD}>
                      <input value={r.item} onChange={(e) => change(r._uid, { item: e.target.value })}
                        placeholder="e.g. CC Slabs"
                        style={{ width: 260, padding: '6px 8px', border: '1px solid #dadce0', borderRadius: 4, fontSize: 13 }} />
                    </td>
                    <td style={{ ...TD, textAlign: 'center' }}><Sel value={r.from_plant} onChange={(v) => change(r._uid, { from_plant: v })} options={PLANTS} /></td>
                    <td style={{ ...TD, textAlign: 'center' }}><Sel value={r.to_plant} onChange={(v) => change(r._uid, { to_plant: v })} options={PLANTS} /></td>
                    <td style={{ ...TD, textAlign: 'center' }}>
                      <input type="number" step="1" value={r.sort_order} onChange={(e) => change(r._uid, { sort_order: e.target.value })}
                        style={{ width: 52, padding: '6px', border: '1px solid #dadce0', borderRadius: 4, textAlign: 'center', fontSize: 13 }} />
                    </td>
                    <td style={{ ...TD, textAlign: 'right' }}>
                      <input type="number" step="any" value={r.plan_kt} onChange={(e) => change(r._uid, { plan_kt: e.target.value })}
                        style={{ width: 90, padding: '6px 8px', border: '1px solid #dadce0', borderRadius: 4, textAlign: 'right', fontSize: 13 }} />
                    </td>
                    <td style={{ ...TD, textAlign: 'center' }}>
                      <button onClick={() => del(r)} style={{ padding: '5px 12px', border: 'none', borderRadius: 4, background: '#ef4444', color: '#fff', fontSize: 13, cursor: 'pointer' }}>Del</button>
                    </td>
                  </tr>
                ))}
                {!rows.length && (
                  <tr><td colSpan={6} style={{ ...TD, textAlign: 'center', color: '#5f6368', padding: 30 }}>No rows. Click “+ Add Row”.</td></tr>
                )}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}

export default function SpecialSteelIptEntryPage() {
  return (
    <RequireEditor>
      <SpecialSteelIptEntryInner />
    </RequireEditor>
  );
}
