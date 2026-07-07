'use client';

import React, { useState, useCallback } from 'react';
import GlobalNavbar from '@/components/GlobalNavbar';

const API = process.env.NEXT_PUBLIC_API_URL || '';

const PLANTS = ['BSP', 'DSP', 'ISP', 'RSP', 'BSL', 'ASP', 'SSP', 'VISL'];
const UNITS  = ['T', 'Rake'];
const IPT_ITEMS = [
  'Screened Coke', 'Sinter', 'Pellet', 'Hot Metal', 'Liquid Steel',
  'CC Slabs', 'Blooms / Billets', 'Finished Steel', 'Wire Rod',
  'Rails', 'Plates / Coils', 'BF Gas', 'CO Gas', 'LD Slag',
];

function defaultMonth() {
  const d = new Date();
  d.setDate(1);
  d.setMonth(d.getMonth() - 1);
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}`;
}

function numOrNull(v) {
  const f = parseFloat(v);
  return isNaN(f) ? null : f;
}

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

function Sel({ value, onChange, options, width = 80 }) {
  return (
    <select value={value} onChange={e => onChange(e.target.value)}
      style={{ width, padding: '6px 8px', border: '1px solid #dadce0', borderRadius: 4, fontSize: 13, backgroundColor: '#fff' }}>
      {options.map(o => <option key={o} value={o}>{o}</option>)}
      {!options.includes(value) && <option value={value}>{value}</option>}
    </select>
  );
}

function Num({ value, onChange, width = 82 }) {
  return (
    <input type="number" step="any" value={value ?? ''}
      onChange={e => onChange(e.target.value)}
      style={{ width, padding: '6px 8px', border: '1px solid #dadce0', borderRadius: 4,
               textAlign: 'right', fontSize: 13, backgroundColor: '#fff' }} />
  );
}

function RouteRow({ row, month, onSaved, onDeleted }) {
  const [r, setR]     = useState(row);
  const [saving, setSaving]   = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [msg, setMsg] = useState(null);

  const set = (k, v) => setR(prev => ({ ...prev, [k]: v }));
  const isRake = r.unit === 'Rake';

  const handleSave = async () => {
    setSaving(true);
    setMsg(null);
    try {
      const res = await fetch(`${API}/api/ipt-entry`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          month,
          item: r.item, from_plant: r.from_plant, to_plant: r.to_plant,
          unit: r.unit, sort_order: parseInt(r.sort_order) || 0,
          plan: numOrNull(r.plan), actual: numOrNull(r.actual),
          plan_tonnage: isRake ? numOrNull(r.plan_tonnage) : null,
          actual_tonnage: isRake ? numOrNull(r.actual_tonnage) : null,
        }),
      });
      if (!res.ok) throw new Error(await res.text());
      setMsg('saved');
      onSaved(r);
      setTimeout(() => setMsg(null), 1500);
    } catch (err) {
      setMsg('err:' + err.message);
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async () => {
    if (!confirm(`Delete: ${r.item} ${r.from_plant} → ${r.to_plant}?`)) return;
    setDeleting(true);
    try {
      const res = await fetch(`${API}/api/ipt-delete`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ month, item: row.item, from_plant: row.from_plant, to_plant: row.to_plant }),
      });
      if (!res.ok) throw new Error(await res.text());
      onDeleted();
    } catch (err) {
      setMsg('err:' + err.message);
      setDeleting(false);
    }
  };

  const rowBg = msg === 'saved' ? '#f0fdf4' : msg?.startsWith('err') ? '#fef2f2' : '#fff';

  return (
    <tr style={{ backgroundColor: rowBg }}>
      <td style={S.TD}><Sel value={r.item} onChange={v => set('item', v)} options={IPT_ITEMS} width={160} /></td>
      <td style={{ ...S.TD, textAlign: 'center' }}><Sel value={r.from_plant} onChange={v => set('from_plant', v)} options={PLANTS} width={72} /></td>
      <td style={{ ...S.TD, textAlign: 'center' }}><Sel value={r.to_plant}   onChange={v => set('to_plant',   v)} options={PLANTS} width={72} /></td>
      <td style={{ ...S.TD, textAlign: 'center' }}><Sel value={r.unit} onChange={v => set('unit', v)} options={UNITS} width={66} /></td>
      <td style={{ ...S.TD, textAlign: 'center' }}>
        <input type="number" step="1" value={r.sort_order ?? 0} onChange={e => set('sort_order', e.target.value)}
          style={{ width: 52, padding: '6px 8px', border: '1px solid #dadce0', borderRadius: 4, textAlign: 'center', fontSize: 13 }} />
      </td>
      <td style={{ ...S.TD, textAlign: 'right' }}><Num value={r.plan}            onChange={v => set('plan', v)} /></td>
      <td style={{ ...S.TD, textAlign: 'right' }}><Num value={r.actual}          onChange={v => set('actual', v)} /></td>
      <td style={{ ...S.TD, textAlign: 'right' }}>
        {isRake ? <Num value={r.plan_tonnage}   onChange={v => set('plan_tonnage', v)} /> : <span style={{ color: '#5f6368' }}>—</span>}
      </td>
      <td style={{ ...S.TD, textAlign: 'right' }}>
        {isRake ? <Num value={r.actual_tonnage} onChange={v => set('actual_tonnage', v)} /> : <span style={{ color: '#5f6368' }}>—</span>}
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
      <td style={{ ...S.TD, textAlign: 'center' }}>
        <button onClick={handleDelete} disabled={deleting}
          style={{ padding: '5px 12px', border: 'none', borderRadius: 4,
                   backgroundColor: '#ef4444', color: '#fff', fontSize: 13, cursor: 'pointer' }}>
          {deleting ? '…' : 'Del'}
        </button>
      </td>
    </tr>
  );
}

function NewRouteRow({ month, onAdded }) {
  const [r, setR] = useState({
    item: IPT_ITEMS[0], from_plant: 'BSP', to_plant: 'DSP',
    unit: 'T', sort_order: 0,
    plan: '', actual: '', plan_tonnage: '', actual_tonnage: '',
  });
  const [saving, setSaving] = useState(false);
  const [err, setErr]       = useState(null);

  const set    = (k, v) => setR(prev => ({ ...prev, [k]: v }));
  const isRake = r.unit === 'Rake';

  const handleAdd = async () => {
    if (r.from_plant === r.to_plant) { setErr('From and To must differ.'); return; }
    setSaving(true);
    setErr(null);
    try {
      const res = await fetch(`${API}/api/ipt-entry`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          month,
          item: r.item, from_plant: r.from_plant, to_plant: r.to_plant,
          unit: r.unit, sort_order: parseInt(r.sort_order) || 0,
          plan: numOrNull(r.plan), actual: numOrNull(r.actual),
          plan_tonnage: isRake ? numOrNull(r.plan_tonnage) : null,
          actual_tonnage: isRake ? numOrNull(r.actual_tonnage) : null,
        }),
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
    <>
      <tr style={{ backgroundColor: '#fffbeb', borderTop: '2px solid #f59e0b' }}>
        <td style={S.TD}><Sel value={r.item} onChange={v => set('item', v)} options={IPT_ITEMS} width={160} /></td>
        <td style={{ ...S.TD, textAlign: 'center' }}><Sel value={r.from_plant} onChange={v => set('from_plant', v)} options={PLANTS} width={72} /></td>
        <td style={{ ...S.TD, textAlign: 'center' }}><Sel value={r.to_plant}   onChange={v => set('to_plant',   v)} options={PLANTS} width={72} /></td>
        <td style={{ ...S.TD, textAlign: 'center' }}><Sel value={r.unit} onChange={v => set('unit', v)} options={UNITS} width={66} /></td>
        <td style={{ ...S.TD, textAlign: 'center' }}>
          <input type="number" step="1" value={r.sort_order} onChange={e => set('sort_order', e.target.value)}
            style={{ width: 52, padding: '6px 8px', border: '1px solid #dadce0', borderRadius: 4, textAlign: 'center', fontSize: 13 }} />
        </td>
        <td style={{ ...S.TD, textAlign: 'right' }}><Num value={r.plan}   onChange={v => set('plan', v)} /></td>
        <td style={{ ...S.TD, textAlign: 'right' }}><Num value={r.actual} onChange={v => set('actual', v)} /></td>
        <td style={{ ...S.TD, textAlign: 'right' }}>
          {isRake ? <Num value={r.plan_tonnage}   onChange={v => set('plan_tonnage', v)} /> : <span style={{ color: '#5f6368' }}>—</span>}
        </td>
        <td style={{ ...S.TD, textAlign: 'right' }}>
          {isRake ? <Num value={r.actual_tonnage} onChange={v => set('actual_tonnage', v)} /> : <span style={{ color: '#5f6368' }}>—</span>}
        </td>
        <td colSpan={2} style={{ ...S.TD, textAlign: 'center' }}>
          <button onClick={handleAdd} disabled={saving}
            style={{ padding: '6px 16px', border: 'none', borderRadius: 4,
                     backgroundColor: '#6366f1', color: '#fff', fontSize: 13,
                     cursor: 'pointer', fontWeight: 600 }}>
            {saving ? '…' : '+ Add Route'}
          </button>
        </td>
      </tr>
      {err && (
        <tr>
          <td colSpan={11} style={{ padding: '6px 12px', color: '#dc2626', fontSize: 13, backgroundColor: '#fef2f2' }}>
            {err}
          </td>
        </tr>
      )}
    </>
  );
}

export default function IptDataEntryPage() {
  const [month, setMonth]     = useState(defaultMonth);
  const [rows, setRows]       = useState([]);
  const [loading, setLoading] = useState(false);
  const [status, setStatus]   = useState(null);
  const [loaded, setLoaded]   = useState(false);
  const [showNew, setShowNew] = useState(false);

  const load = useCallback(async (m) => {
    const target = m || month;
    setLoading(true);
    setStatus(null);
    setLoaded(false);
    setShowNew(false);
    try {
      const res = await fetch(`${API}/api/ipt-entries?month=${encodeURIComponent(target)}`);
      if (!res.ok) throw new Error(await res.text());
      const data = await res.json();
      setRows(data.rows.map(r => ({
        ...r,
        plan:            r.plan            ?? '',
        actual:          r.actual          ?? '',
        plan_tonnage:    r.plan_tonnage    ?? '',
        actual_tonnage:  r.actual_tonnage  ?? '',
      })));
      setLoaded(true);
    } catch (err) {
      setStatus({ type: 'error', text: `Load failed: ${err.message}` });
    } finally {
      setLoading(false);
    }
  }, [month]);

  const handleAdded = () => {
    setShowNew(false);
    load(month);
    setStatus({ type: 'success', text: 'Route added.' });
    setTimeout(() => setStatus(null), 2000);
  };

  const handleRowSaved  = (idx, updated) => setRows(prev => prev.map((r, i) => i === idx ? updated : r));
  const handleRowDelete = (idx) => setRows(prev => prev.filter((_, i) => i !== idx));

  const [y, mo] = month.split('-');
  const MON = ['','Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
  const monthDisplay = `${MON[parseInt(mo)]}'${y.slice(2)}`;

  return (
    <div style={{ height: '100vh', display: 'flex', flexDirection: 'column', background: '#ffffff' }}>
      <GlobalNavbar />

      <div style={{ flex: 1, overflow: 'auto', maxWidth: 1400, margin: '0 auto', padding: '22px 20px', width: '100%', boxSizing: 'border-box' }}>

        {/* ── Page title ── */}
        <div style={{ marginBottom: 18 }}>
          <h2 style={{ fontSize: '1.6rem', fontWeight: 700, color: '#202124', margin: '0 0 4px' }}>
            IPT Status — Data Entry
          </h2>
          <span style={{ fontSize: 13, color: '#5f6368' }}>
            Inter-Plant Transfer routes for page 26. Select month and click Load Records.
          </span>
        </div>

        {/* ── Controls bar ── */}
        <div style={{
          display: 'flex', gap: 10, alignItems: 'center', flexWrap: 'wrap',
          marginBottom: 18, background: '#fff', border: '1px solid #dadce0',
          borderRadius: 8, padding: '14px 18px',
        }}>
          <label style={{ fontSize: 13, fontWeight: 600, color: '#374151' }}>Month</label>
          <input type="month" value={month}
            onChange={e => { setMonth(e.target.value); setLoaded(false); setRows([]); }}
            style={{ padding: '7px 10px', fontSize: 14, border: '1px solid #d1d5db', borderRadius: 4 }} />

          <button onClick={() => load(month)} disabled={loading} style={{
            padding: '7px 20px', fontSize: 14, fontWeight: 600,
            background: '#1a73e8', color: '#fff', border: 'none', borderRadius: 4,
            cursor: loading ? 'not-allowed' : 'pointer',
          }}>
            {loading ? 'Loading…' : 'Load Records'}
          </button>

          {loaded && (
            <button onClick={() => setShowNew(v => !v)} style={{
              padding: '7px 20px', fontSize: 14, fontWeight: 600,
              background: showNew ? '#f8f9fa' : '#6366f1', color: showNew ? '#374151' : '#fff',
              border: `1px solid ${showNew ? '#dadce0' : '#6366f1'}`, borderRadius: 4, cursor: 'pointer',
            }}>
              {showNew ? 'Cancel New Route' : '+ Add New Route'}
            </button>
          )}

          <span style={{ marginLeft: 'auto', fontSize: 13, color: '#5f6368' }}>
            {monthDisplay}{loading && ' ⟳'}
          </span>
        </div>

        {/* ── Notice ── */}
        <Notice type={status?.type} text={status?.text} />

        {!loaded && !loading && (
          <div style={{
            padding: 48, textAlign: 'center', backgroundColor: '#fff',
            border: '2px dashed #dadce0', borderRadius: 8, color: '#5f6368',
          }}>
            <p style={{ margin: 0, fontSize: 14 }}>
              Select a month and click <strong>Load Records</strong>.
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
            {/* Table header */}
            <div style={{
              padding: '14px 18px', backgroundColor: '#f8f9fa', color: '#202124',
              display: 'flex', justifyContent: 'space-between', alignItems: 'center',
            }}>
              <span style={{ fontWeight: 700, fontSize: 14 }}>
                IPT Status — {monthDisplay}
              </span>
              <span style={{ fontSize: 13, color: '#5f6368' }}>
                {rows.length} route{rows.length !== 1 ? 's' : ''}
              </span>
            </div>

            <div style={{ overflowX: 'auto', maxHeight: 'calc(100vh - 420px)', overflowY: 'auto' }}>
              <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 14 }}>
                <thead>
                  <tr style={{ position: 'sticky', top: 0, zIndex: 1 }}>
                    <th style={{ ...S.H, textAlign: 'left', width: 160 }}>Item</th>
                    <th style={S.H}>From</th>
                    <th style={S.H}>To</th>
                    <th style={S.H}>Unit</th>
                    <th style={S.H}>Sort #</th>
                    <th style={S.H}>Plan</th>
                    <th style={S.H}>Actual</th>
                    <th style={S.H}>Plan (T)</th>
                    <th style={S.H}>Actual (T)</th>
                    <th style={S.H} colSpan={2}>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {rows.length === 0 && !showNew && (
                    <tr>
                      <td colSpan={11} style={{ padding: 24, textAlign: 'center', color: '#5f6368', fontSize: 14 }}>
                        No routes for {monthDisplay}. Click <strong>+ Add New Route</strong> to create one.
                      </td>
                    </tr>
                  )}
                  {rows.map((row, idx) => (
                    <RouteRow
                      key={`${row.item}|${row.from_plant}|${row.to_plant}`}
                      row={row}
                      month={month}
                      onSaved={updated => handleRowSaved(idx, updated)}
                      onDeleted={() => handleRowDelete(idx)}
                    />
                  ))}
                  {showNew && (
                    <NewRouteRow month={month} onAdded={handleAdded} />
                  )}
                </tbody>
              </table>
            </div>

            <div style={{
              padding: '12px 18px', backgroundColor: '#f8f9fa', borderTop: '1px solid #dadce0',
              display: 'flex', justifyContent: 'space-between', alignItems: 'center',
            }}>
              <span style={{ fontSize: 13, color: '#5f6368' }}>
                Save each row individually. Plan (T) and Actual (T) apply only to Rake unit routes.
              </span>
              <button onClick={() => setShowNew(v => !v)}
                style={{
                  padding: '7px 18px', border: '1px solid #6366f1', borderRadius: 4,
                  backgroundColor: showNew ? '#f8f9fa' : '#6366f1',
                  color: showNew ? '#6366f1' : '#fff', fontSize: 14, cursor: 'pointer',
                }}>
                {showNew ? 'Cancel' : '+ Add Route'}
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
