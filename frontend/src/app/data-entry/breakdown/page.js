'use client';

import RequireEditor from '@/components/RequireEditor';

import React, { useState, useCallback, useEffect, useMemo } from 'react';
import GlobalNavbar from '@/components/GlobalNavbar';

const API = process.env.NEXT_PUBLIC_API_URL || '';

const PLANTS = [
  { code: 'BSP', label: 'Bhilai Steel Plant' },
  { code: 'DSP', label: 'Durgapur Steel Plant' },
  { code: 'RSP', label: 'Rourkela Steel Plant' },
  { code: 'BSL', label: 'Bokaro Steel Plant' },
  { code: 'ISP', label: 'IISCO Steel Plant' },
];

const UNIT_TYPES = [
  { code: 'BF', label: 'Blast Furnace' },
  { code: 'SMS', label: 'SMS (Converter/Caster)' },
  { code: 'MILL', label: 'Rolling Mill' },
  { code: 'COKE', label: 'Coke Oven' },
  { code: 'SINTER', label: 'Sinter Plant' },
  { code: 'GENERAL', label: 'Plant-Level General' },
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

// 'YYYY-MM-DD HH:MM' <-> the 'YYYY-MM-DDTHH:MM' shape <input type="datetime-local"> needs.
const toInputTs = (ts) => (ts || '').replace(' ', 'T');
const toApiTs = (v) => (v || '').replace('T', ' ');

function emptyDraft(defaults = {}) {
  return {
    plant: defaults.plant || 'BSP',
    unit_type: '', unit_name: '', sms_subtag: '',
    start_ts: '', end_ts: '', is_ongoing: false,
    cause: '', hours_lost_override: '',
  };
}

function UnitFields({ draft, setDraft, units }) {
  const unitOptions = useMemo(
    () => units.filter(u => u.unit_type === draft.unit_type && !u.is_shop),
    [units, draft.unit_type]
  );
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 4, minWidth: 170 }}>
      <select style={S.SEL} value={draft.unit_type}
        onChange={e => setDraft(d => ({ ...d, unit_type: e.target.value, unit_name: '', sms_subtag: '' }))}>
        <option value="">— unit type —</option>
        {UNIT_TYPES.map(t => <option key={t.code} value={t.code}>{t.label}</option>)}
      </select>
      {draft.unit_type && (
        <select style={S.SEL} value={draft.unit_name} onChange={e => setDraft(d => ({ ...d, unit_name: e.target.value }))}>
          <option value="">— unit —</option>
          {unitOptions.map(u => <option key={u.unit_name} value={u.unit_name}>{u.unit_name}</option>)}
        </select>
      )}
      {draft.unit_type === 'SMS' && (
        <select style={S.SEL} value={draft.sms_subtag} onChange={e => setDraft(d => ({ ...d, sms_subtag: e.target.value }))}>
          <option value="">— converter/caster —</option>
          <option value="CONVERTER">Converter</option>
          <option value="CASTER">Caster</option>
        </select>
      )}
    </div>
  );
}

function TimeFields({ draft, setDraft }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 4, minWidth: 260 }}>
      <div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
        <input type="datetime-local" style={S.INPUT} value={toInputTs(draft.start_ts)}
          onChange={e => setDraft(d => ({ ...d, start_ts: toApiTs(e.target.value) }))} />
        <span style={{ color: '#9aa0a6' }}>–</span>
        <input type="datetime-local" style={S.INPUT} value={toInputTs(draft.end_ts)} disabled={draft.is_ongoing}
          onChange={e => setDraft(d => ({ ...d, end_ts: toApiTs(e.target.value) }))} />
      </div>
      <label style={{ fontSize: 12, color: '#5f6368', display: 'flex', alignItems: 'center', gap: 4 }}>
        <input type="checkbox" checked={draft.is_ongoing}
          onChange={e => setDraft(d => ({ ...d, is_ongoing: e.target.checked, end_ts: e.target.checked ? '' : d.end_ts }))} />
        Ongoing (not yet resolved)
      </label>
    </div>
  );
}

function validateDraft(draft) {
  if (!draft.unit_type) return 'Unit type is required';
  if (!draft.unit_name) return 'Unit is required';
  if (draft.unit_type === 'SMS' && !draft.sms_subtag) return 'Converter or Caster must be chosen for an SMS unit';
  if (!draft.start_ts) return 'Start date/time is required';
  if (!draft.is_ongoing && !draft.end_ts) return 'End date/time is required unless Ongoing is checked';
  if (!draft.is_ongoing && draft.end_ts && draft.end_ts < draft.start_ts) return 'End must not be before start';
  if (!draft.cause.trim()) return 'Cause is required';
  return null;
}

function draftPayload(draft) {
  return {
    plant: draft.plant,
    unit_type: draft.unit_type,
    unit_name: draft.unit_name,
    sms_subtag: draft.unit_type === 'SMS' ? draft.sms_subtag : null,
    start_ts: draft.start_ts,
    end_ts: draft.is_ongoing ? null : draft.end_ts,
    is_ongoing: draft.is_ongoing,
    cause: draft.cause.trim(),
    hours_lost_override: draft.hours_lost_override === '' ? null : Number(draft.hours_lost_override),
  };
}

function AddBreakdownForm({ plant, units, onAdded, onCancel }) {
  const [draft, setDraft] = useState(() => emptyDraft({ plant }));
  const [saving, setSaving] = useState(false);
  const [err, setErr] = useState(null);

  const handleAdd = async () => {
    const v = validateDraft(draft);
    if (v) { setErr(v); return; }
    setSaving(true); setErr(null);
    try {
      const res = await fetch(`${API}/api/breakdown`, {
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
      <td style={S.TD}><UnitFields draft={draft} setDraft={setDraft} units={units} /></td>
      <td style={S.TD}><TimeFields draft={draft} setDraft={setDraft} /></td>
      <td style={S.TD}>
        <textarea style={{ ...S.INPUT, minHeight: 44, resize: 'vertical' }} value={draft.cause}
          onChange={e => setDraft(d => ({ ...d, cause: e.target.value }))} placeholder="cause / description" />
      </td>
      <td style={{ ...S.TD, width: 90 }}>
        <input type="number" step="0.1" style={S.INPUT} value={draft.hours_lost_override}
          onChange={e => setDraft(d => ({ ...d, hours_lost_override: e.target.value }))} placeholder="hrs" />
      </td>
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

function BreakdownRow({ row, units, onChanged }) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(() => ({
    plant: row.plant, unit_type: row.unit_type || '', unit_name: row.unit_name || '',
    sms_subtag: row.sms_subtag || '', start_ts: row.start_ts || '', end_ts: row.end_ts || '',
    is_ongoing: !!row.is_ongoing, cause: row.cause || '',
    hours_lost_override: row.hours_lost_override != null ? String(row.hours_lost_override) : '',
  }));
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState(null);

  const handleSave = async () => {
    const v = validateDraft(draft);
    if (v) { setErr(v); return; }
    setBusy(true); setErr(null);
    try {
      const res = await fetch(`${API}/api/breakdown/${row.id}`, {
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
    if (!confirm('Delete this breakdown event? This cannot be undone.')) return;
    setBusy(true); setErr(null);
    try {
      const res = await fetch(`${API}/api/breakdown/${row.id}`, { method: 'DELETE' });
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
        <td style={S.TD}><UnitFields draft={draft} setDraft={setDraft} units={units} /></td>
        <td style={S.TD}><TimeFields draft={draft} setDraft={setDraft} /></td>
        <td style={S.TD}>
          <textarea style={{ ...S.INPUT, minHeight: 44, resize: 'vertical' }} value={draft.cause}
            onChange={e => setDraft(d => ({ ...d, cause: e.target.value }))} />
        </td>
        <td style={{ ...S.TD, width: 90 }}>
          <input type="number" step="0.1" style={S.INPUT} value={draft.hours_lost_override}
            onChange={e => setDraft(d => ({ ...d, hours_lost_override: e.target.value }))} />
        </td>
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

  const unitLabel = [row.unit_name, row.sms_subtag ? `(${row.sms_subtag.charAt(0)}${row.sms_subtag.slice(1).toLowerCase()})` : null]
    .filter(Boolean).join(' ');

  return (
    <tr>
      <td style={S.TD}>
        <div style={{ fontWeight: 600 }}>{unitLabel || '—'}</div>
        <div style={{ fontSize: 11.5, color: '#5f6368' }}>{row.unit_type}</div>
      </td>
      <td style={S.TD}>
        <div>{row.start_ts} – {row.is_ongoing ? <strong style={{ color: '#b45309' }}>ongoing</strong> : row.end_ts}</div>
      </td>
      <td style={S.TD}>{row.cause}</td>
      <td style={{ ...S.TD, textAlign: 'center' }}>{row.hours_lost_override ?? ''}</td>
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

function BreakdownDataEntryPageInner() {
  const [plant, setPlant]         = useState('BSP');
  const [rows, setRows]           = useState([]);
  const [units, setUnits]         = useState([]);
  const [loading, setLoading]     = useState(false);
  const [status, setStatus]       = useState(null);
  const [adding, setAdding]       = useState(false);

  useEffect(() => {
    fetch(`${API}/api/plant-units?plant_code=${encodeURIComponent(plant)}`)
      .then(res => res.json())
      .then(data => setUnits(data.units || []))
      .catch(() => setUnits([]));
  }, [plant]);

  const load = useCallback(async () => {
    setLoading(true);
    setStatus(null);
    try {
      const res = await fetch(`${API}/api/breakdown?plant=${encodeURIComponent(plant)}`);
      if (!res.ok) throw new Error(await res.text());
      const data = await res.json();
      setRows(data.rows || []);
    } catch (err) {
      setStatus({ type: 'error', text: `Load failed: ${err.message}` });
    } finally {
      setLoading(false);
    }
  }, [plant]);

  useEffect(() => { load(); }, [load]);

  const plantLabel = PLANTS.find(p => p.code === plant)?.label || plant;

  return (
    <div style={{ height: '100vh', display: 'flex', flexDirection: 'column', background: '#ffffff' }}>
      <GlobalNavbar />

      <div style={{ flex: 1, overflow: 'auto', maxWidth: 1500, margin: '0 auto', padding: '22px 20px', width: '100%', boxSizing: 'border-box' }}>

        <div style={{ marginBottom: 18 }}>
          <h2 style={{ fontSize: '1.6rem', fontWeight: 700, color: '#202124', margin: '0 0 4px' }}>
            Breakdown — Data Entry
          </h2>
          <span style={{ fontSize: 13, color: '#5f6368' }}>
            Log unplanned equipment downtime, plant-wise and unit-wise. Unlike Capital Repair (a pre-planned
            annual schedule), every breakdown here counts fully toward the Production Loss Analysis report —
            add, edit, or delete events as they occur.
          </span>
        </div>

        <div style={{
          display: 'flex', gap: 10, alignItems: 'center', flexWrap: 'wrap',
          marginBottom: 18, background: '#fff', border: '1px solid #dadce0',
          borderRadius: 8, padding: '14px 18px',
        }}>
          <label style={{ fontSize: 13, fontWeight: 600, color: '#374151' }}>Plant</label>
          <select value={plant} onChange={e => { setPlant(e.target.value); setAdding(false); }}
            style={{ padding: '7px 10px', fontSize: 14, border: '1px solid #d1d5db', borderRadius: 4 }}>
            {PLANTS.map(p => <option key={p.code} value={p.code}>{p.code} — {p.label}</option>)}
          </select>

          <button onClick={() => setAdding(true)} disabled={adding} style={{
            padding: '7px 20px', fontSize: 14, fontWeight: 600,
            background: '#1a73e8', color: '#fff', border: 'none', borderRadius: 4,
            cursor: adding ? 'not-allowed' : 'pointer',
          }}>
            + Add Breakdown
          </button>

          <span style={{ marginLeft: 'auto', fontSize: 13, color: '#5f6368' }}>
            {plantLabel}{loading && ' ⟳'}
          </span>
        </div>

        <Notice type={status?.type} text={status?.text} />

        <div style={{ backgroundColor: '#fff', border: '1px solid #dadce0', borderRadius: 8, overflow: 'hidden' }}>
          <div style={{
            padding: '14px 18px', backgroundColor: '#f8f9fa', color: '#202124',
            display: 'flex', justifyContent: 'space-between', alignItems: 'center',
          }}>
            <span style={{ fontWeight: 700, fontSize: 14 }}>Breakdown Log — {plantLabel}</span>
            <span style={{ fontSize: 13, color: '#5f6368' }}>
              {rows.length} event{rows.length !== 1 ? 's' : ''}
            </span>
          </div>

          <div style={{ overflowX: 'auto', maxHeight: 'calc(100vh - 380px)', overflowY: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 14 }}>
              <thead>
                <tr style={{ position: 'sticky', top: 0, zIndex: 1 }}>
                  <th style={S.H}>Unit</th>
                  <th style={S.H}>Start – End</th>
                  <th style={{ ...S.H, textAlign: 'left' }}>Cause</th>
                  <th style={S.H}>Hours (override)</th>
                  <th style={S.H}>Actions</th>
                </tr>
              </thead>
              <tbody>
                {adding && (
                  <AddBreakdownForm plant={plant} units={units}
                    onAdded={() => { setAdding(false); load(); }}
                    onCancel={() => setAdding(false)} />
                )}
                {!adding && rows.length === 0 && (
                  <tr>
                    <td colSpan={5} style={{ padding: 24, textAlign: 'center', color: '#5f6368', fontSize: 14 }}>
                      No breakdown events logged for {plantLabel}. Click <strong>+ Add Breakdown</strong> to add one.
                    </td>
                  </tr>
                )}
                {rows.map(row => (
                  <BreakdownRow key={row.id} row={row} units={units} onChanged={load} />
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  );
}

export default function BreakdownDataEntryPage() {
  return (
    <RequireEditor>
      <BreakdownDataEntryPageInner />
    </RequireEditor>
  );
}
