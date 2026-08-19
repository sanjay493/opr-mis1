'use client';

import RequireEditor from '@/components/RequireEditor';

import React, { useState, useCallback, useEffect } from 'react';
import GlobalNavbar from '@/components/GlobalNavbar';

const API = process.env.NEXT_PUBLIC_API_URL || '';

const PLANTS = ['BSP', 'DSP', 'RSP', 'BSL', 'ISP', 'ASP', 'SSP', 'VISL'];

// { value: db_item, label } — kept in sync with backend api_capacity.py's
// CAPACITY_ITEMS / page4.py's PAGE4_ITEMS `has_capacity` flags.
const ITEMS = [
  { value: 'Hot Metal', label: 'Hot Metal' },
  { value: 'Total Crude Steel', label: 'Crude Steel' },
  { value: 'Saleable Steel', label: 'Saleable Steel' },
  { value: 'Finished Steel', label: 'Finished Steel' },
];

const S = {
  H:  { padding: '10px 8px', textAlign: 'center', fontWeight: 700, color: '#5f6368',
        borderBottom: '1px solid #dadce0', fontSize: 13, backgroundColor: '#f8f9fa',
        whiteSpace: 'nowrap' },
  TD: { padding: '7px 8px', borderBottom: '1px solid #f0f4f8', fontSize: 14, verticalAlign: 'middle' },
  SEL: { padding: '5px 6px', fontSize: 12.5, border: '1px solid #dadce0', borderRadius: 4, width: '100%' },
  INPUT: { padding: '5px 6px', fontSize: 12.5, border: '1px solid #dadce0', borderRadius: 4, width: '100%' },
  BTN_SM: { padding: '4px 10px', border: 'none', borderRadius: 4, fontSize: 12.5, cursor: 'pointer', fontWeight: 600 },
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

function emptyDraft(defaults = {}) {
  return {
    plant: defaults.plant || 'BSP',
    item: defaults.item || ITEMS[0].value,
    effective_month: '', annual_capacity: '', reason: '',
  };
}

function EntryFields({ draft, setDraft }) {
  return (
    <>
      <td style={S.TD}>
        <select style={S.SEL} value={draft.plant} onChange={e => setDraft(d => ({ ...d, plant: e.target.value }))}>
          {PLANTS.map(p => <option key={p} value={p}>{p}</option>)}
        </select>
      </td>
      <td style={S.TD}>
        <select style={S.SEL} value={draft.item} onChange={e => setDraft(d => ({ ...d, item: e.target.value }))}>
          {ITEMS.map(it => <option key={it.value} value={it.value}>{it.label}</option>)}
        </select>
      </td>
      <td style={S.TD}>
        <input type="month" style={S.INPUT} value={draft.effective_month}
          onChange={e => setDraft(d => ({ ...d, effective_month: e.target.value }))} />
      </td>
      <td style={S.TD}>
        <input type="number" step="0.01" style={S.INPUT} value={draft.annual_capacity}
          onChange={e => setDraft(d => ({ ...d, annual_capacity: e.target.value }))} placeholder="'000 T / yr" />
      </td>
      <td style={S.TD}>
        <input type="text" style={S.INPUT} value={draft.reason}
          onChange={e => setDraft(d => ({ ...d, reason: e.target.value }))}
          placeholder="e.g. New BF-3 commissioned" />
      </td>
    </>
  );
}

function validateDraft(draft) {
  if (!draft.plant) return 'Plant is required';
  if (!draft.item) return 'Item is required';
  if (!draft.effective_month) return 'Effective month is required';
  const cap = Number(draft.annual_capacity);
  if (!draft.annual_capacity || !(cap > 0)) return 'Annual capacity must be greater than 0';
  return null;
}

function draftPayload(draft) {
  return {
    plant: draft.plant,
    item: draft.item,
    effective_month: draft.effective_month,
    annual_capacity: Number(draft.annual_capacity),
    reason: draft.reason.trim(),
  };
}

function AddEntryForm({ defaults, onAdded, onCancel }) {
  const [draft, setDraft] = useState(() => emptyDraft(defaults));
  const [saving, setSaving] = useState(false);
  const [err, setErr] = useState(null);

  const handleAdd = async () => {
    const v = validateDraft(draft);
    if (v) { setErr(v); return; }
    setSaving(true); setErr(null);
    try {
      const res = await fetch(`${API}/api/capacity`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(draftPayload(draft)),
      });
      if (!res.ok) throw new Error(await res.text());
      onAdded();
    } catch (e) {
      setErr(e.message);
    } finally {
      setSaving(false);
    }
  };

  return (
    <tr style={{ backgroundColor: '#eff6ff' }}>
      <EntryFields draft={draft} setDraft={setDraft} />
      <td style={{ ...S.TD, textAlign: 'center', whiteSpace: 'nowrap' }}>
        <button onClick={handleAdd} disabled={saving}
          style={{ ...S.BTN_SM, backgroundColor: '#10b981', color: '#fff', marginRight: 6 }}>
          {saving ? '…' : 'Add'}
        </button>
        <button onClick={onCancel} style={{ ...S.BTN_SM, backgroundColor: '#f1f3f4', color: '#374151' }}>Cancel</button>
        {err && <div style={{ color: '#dc2626', fontSize: 11.5, marginTop: 4 }}>{err}</div>}
      </td>
    </tr>
  );
}

function EntryRow({ row, onChanged }) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(() => ({
    plant: row.plant_name, item: row.item_name, effective_month: row.effective_month,
    annual_capacity: String(row.annual_capacity), reason: row.reason || '',
  }));
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState(null);

  const handleSave = async () => {
    const v = validateDraft(draft);
    if (v) { setErr(v); return; }
    setBusy(true); setErr(null);
    try {
      const res = await fetch(`${API}/api/capacity/${row.id}`, {
        method: 'PATCH', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(draftPayload(draft)),
      });
      if (!res.ok) throw new Error(await res.text());
      setEditing(false);
      onChanged();
    } catch (e) {
      setErr(e.message);
    } finally {
      setBusy(false);
    }
  };

  const handleDelete = async () => {
    if (!confirm('Delete this capacity entry? This cannot be undone.')) return;
    setBusy(true); setErr(null);
    try {
      const res = await fetch(`${API}/api/capacity/${row.id}`, { method: 'DELETE' });
      if (!res.ok) throw new Error(await res.text());
      onChanged();
    } catch (e) {
      setErr(e.message);
      setBusy(false);
    }
  };

  if (editing) {
    return (
      <tr style={{ backgroundColor: '#fffbeb' }}>
        <EntryFields draft={draft} setDraft={setDraft} />
        <td style={{ ...S.TD, textAlign: 'center', whiteSpace: 'nowrap' }}>
          <button onClick={handleSave} disabled={busy}
            style={{ ...S.BTN_SM, backgroundColor: '#10b981', color: '#fff', marginRight: 6 }}>
            {busy ? '…' : 'Save'}
          </button>
          <button onClick={() => setEditing(false)} style={{ ...S.BTN_SM, backgroundColor: '#f1f3f4', color: '#374151' }}>Cancel</button>
          {err && <div style={{ color: '#dc2626', fontSize: 11.5, marginTop: 4 }}>{err}</div>}
        </td>
      </tr>
    );
  }

  const itemLabel = ITEMS.find(it => it.value === row.item_name)?.label || row.item_name;

  return (
    <tr>
      <td style={{ ...S.TD, textAlign: 'center', fontWeight: 600 }}>{row.plant_name}</td>
      <td style={S.TD}>{itemLabel}</td>
      <td style={{ ...S.TD, textAlign: 'center' }}>{row.effective_month}</td>
      <td style={{ ...S.TD, textAlign: 'center' }}>{row.annual_capacity}</td>
      <td style={S.TD}>{row.reason || <span style={{ color: '#9aa0a6' }}>—</span>}</td>
      <td style={{ ...S.TD, textAlign: 'center', whiteSpace: 'nowrap' }}>
        <button onClick={() => setEditing(true)}
          style={{ ...S.BTN_SM, backgroundColor: '#eef2ff', color: '#3730a3', marginRight: 6 }}>Edit</button>
        <button onClick={handleDelete} disabled={busy}
          style={{ ...S.BTN_SM, backgroundColor: '#fef2f2', color: '#991b1b' }}>Delete</button>
        {err && <div style={{ color: '#dc2626', fontSize: 11.5, marginTop: 4 }}>{err}</div>}
      </td>
    </tr>
  );
}

function AnnualCapacityDataEntryPageInner() {
  const [plantFilter, setPlantFilter] = useState('');
  const [itemFilter, setItemFilter]   = useState('');
  const [rows, setRows]               = useState([]);
  const [loading, setLoading]         = useState(false);
  const [status, setStatus]           = useState(null);
  const [adding, setAdding]           = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    setStatus(null);
    try {
      const params = new URLSearchParams();
      if (plantFilter) params.set('plant', plantFilter);
      if (itemFilter) params.set('item', itemFilter);
      const res = await fetch(`${API}/api/capacity?${params.toString()}`);
      if (!res.ok) throw new Error(await res.text());
      const data = await res.json();
      setRows(data.rows || []);
    } catch (err) {
      setStatus({ type: 'error', text: `Load failed: ${err.message}` });
    } finally {
      setLoading(false);
    }
  }, [plantFilter, itemFilter]);

  useEffect(() => { load(); }, [load]);

  return (
    <div style={{ height: '100vh', display: 'flex', flexDirection: 'column', background: '#ffffff' }}>
      <GlobalNavbar />

      <div style={{ flex: 1, overflow: 'auto', maxWidth: 1500, margin: '0 auto', padding: '22px 20px', width: '100%', boxSizing: 'border-box' }}>

        <div style={{ marginBottom: 18 }}>
          <h2 style={{ fontSize: '1.6rem', fontWeight: 700, color: '#202124', margin: '0 0 4px' }}>
            Annual Capacity — Data Entry
          </h2>
          <span style={{ fontSize: 13, color: '#5f6368' }}>
            Rated annual capacity ('000 T/yr) per plant/item, used to compute the Capacity and CU% (Capacity
            Utilisation %) columns on the Plant Wise Performance of Main Items page. By default, one entry
            (dated to FY-start) covers the whole FY — add another entry with a later Effective Month only
            when a mid-year commissioning/decommissioning actually changes the rated capacity; from that
            month onward the new rate applies, and it carries forward until the next change or FY entry.
          </span>
        </div>

        <div style={{
          display: 'flex', gap: 10, alignItems: 'center', flexWrap: 'wrap',
          marginBottom: 18, background: '#fff', border: '1px solid #dadce0',
          borderRadius: 8, padding: '14px 18px',
        }}>
          <label style={{ fontSize: 13, fontWeight: 600, color: '#374151' }}>Plant</label>
          <select value={plantFilter} onChange={e => setPlantFilter(e.target.value)}
            style={{ padding: '7px 10px', fontSize: 14, border: '1px solid #d1d5db', borderRadius: 4 }}>
            <option value="">All plants</option>
            {PLANTS.map(p => <option key={p} value={p}>{p}</option>)}
          </select>

          <label style={{ fontSize: 13, fontWeight: 600, color: '#374151' }}>Item</label>
          <select value={itemFilter} onChange={e => setItemFilter(e.target.value)}
            style={{ padding: '7px 10px', fontSize: 14, border: '1px solid #d1d5db', borderRadius: 4 }}>
            <option value="">All items</option>
            {ITEMS.map(it => <option key={it.value} value={it.value}>{it.label}</option>)}
          </select>

          <button onClick={() => setAdding(true)} disabled={adding} style={{
            padding: '7px 20px', fontSize: 14, fontWeight: 600,
            background: '#1a73e8', color: '#fff', border: 'none', borderRadius: 4,
            cursor: adding ? 'not-allowed' : 'pointer',
          }}>
            + Add Capacity Entry
          </button>

          <span style={{ marginLeft: 'auto', fontSize: 13, color: '#5f6368' }}>
            {loading && 'Loading… ⟳'}
          </span>
        </div>

        <Notice type={status?.type} text={status?.text} />

        <div style={{ backgroundColor: '#fff', border: '1px solid #dadce0', borderRadius: 8, overflow: 'hidden' }}>
          <div style={{
            padding: '14px 18px', backgroundColor: '#f8f9fa', color: '#202124',
            display: 'flex', justifyContent: 'space-between', alignItems: 'center',
          }}>
            <span style={{ fontWeight: 700, fontSize: 14 }}>Capacity Entries</span>
            <span style={{ fontSize: 13, color: '#5f6368' }}>
              {rows.length} entr{rows.length !== 1 ? 'ies' : 'y'}
            </span>
          </div>

          <div style={{ overflowX: 'auto', maxHeight: 'calc(100vh - 380px)', overflowY: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 14 }}>
              <thead>
                <tr style={{ position: 'sticky', top: 0, zIndex: 1 }}>
                  <th style={S.H}>Plant</th>
                  <th style={{ ...S.H, textAlign: 'left' }}>Item</th>
                  <th style={S.H}>Effective Month</th>
                  <th style={S.H}>Annual Capacity ('000 T)</th>
                  <th style={{ ...S.H, textAlign: 'left' }}>Reason</th>
                  <th style={S.H}>Actions</th>
                </tr>
              </thead>
              <tbody>
                {adding && (
                  <AddEntryForm defaults={{ plant: plantFilter || 'BSP', item: itemFilter || ITEMS[0].value }}
                    onAdded={() => { setAdding(false); load(); }}
                    onCancel={() => setAdding(false)} />
                )}
                {!adding && rows.length === 0 && (
                  <tr>
                    <td colSpan={6} style={{ padding: 24, textAlign: 'center', color: '#5f6368', fontSize: 14 }}>
                      No capacity entries yet. Click <strong>+ Add Capacity Entry</strong> to add one.
                    </td>
                  </tr>
                )}
                {rows.map(row => (
                  <EntryRow key={row.id} row={row} onChanged={load} />
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  );
}

export default function AnnualCapacityDataEntryPage() {
  return (
    <RequireEditor>
      <AnnualCapacityDataEntryPageInner />
    </RequireEditor>
  );
}
