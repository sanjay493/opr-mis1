'use client';

import RequireEditor from '@/components/RequireEditor';

import React, { useState, useCallback, useEffect, useRef } from 'react';
import GlobalNavbar from '@/components/GlobalNavbar';

const API = process.env.NEXT_PUBLIC_API_URL || '';

const PLANTS = ['BSP', 'DSP', 'ISP', 'RSP', 'BSL', 'ASP', 'SSP', 'VISL', 'CFP'];
const UNITS  = ['T', 'Rake'];
const IPT_ITEMS = [
  'Screened Coke', 'Sinter', 'Pellet', 'Hot Metal', 'Liquid Steel',
  'CC Slabs', 'Blooms / Billets', 'Finished Steel', 'Wire Rod',
  'Rails', 'Plates / Coils', 'BF Gas', 'CO Gas', 'LD Slag',
];
const MON = ['','Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
const CUSTOM = '__custom__';

function defaultMonth() {
  const d = new Date();
  d.setDate(1);
  d.setMonth(d.getMonth() - 1);
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}`;
}

function prevMonthOf(m) {
  const [y, mo] = m.split('-').map(Number);
  const d = new Date(y, mo - 2, 1); // mo is 1-indexed; -2 lands one month back
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}`;
}

function monthDisplayOf(m) {
  const [y, mo] = m.split('-');
  return `${MON[parseInt(mo, 10)]}'${y.slice(2)}`;
}

function numOrNull(v) {
  const f = parseFloat(v);
  return isNaN(f) ? null : f;
}

function routeKey(r) {
  return `${r.item}|${r.from_plant}|${r.to_plant}`;
}

const S = {
  H:  { padding: '10px 10px', textAlign: 'center', fontWeight: 700, color: '#5f6368',
        borderBottom: '1px solid #dadce0', fontSize: 13, backgroundColor: '#f8f9fa',
        whiteSpace: 'nowrap' },
  TD: { padding: '6px 8px', borderBottom: '1px solid #f0f4f8', fontSize: 14, verticalAlign: 'middle' },
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

function ItemSel({ value, onChange, options, width = 160 }) {
  const [custom, setCustom] = useState(value !== '' && !options.includes(value));

  return custom ? (
    <div style={{ display: 'flex', gap: 4, alignItems: 'center' }}>
      <input autoFocus placeholder="Item name" value={value}
        onChange={e => onChange(e.target.value)}
        style={{ width: width - 22, padding: '6px 8px', border: '1px solid #dadce0', borderRadius: 4, fontSize: 13, backgroundColor: '#fff' }} />
      <button type="button" title="Choose from list" onClick={() => setCustom(false)}
        style={{ border: '1px solid #dadce0', borderRadius: 4, background: '#f8f9fa', cursor: 'pointer', fontSize: 12, padding: '5px 6px' }}>
        ▾
      </button>
    </div>
  ) : (
    <select value={options.includes(value) ? value : ''} onChange={e => {
        if (e.target.value === CUSTOM) { setCustom(true); onChange(''); }
        else onChange(e.target.value);
      }}
      style={{ width, padding: '6px 8px', border: '1px solid #dadce0', borderRadius: 4, fontSize: 13, backgroundColor: '#fff' }}>
      {!options.includes(value) && <option value="" disabled>— Select item —</option>}
      {options.map(o => <option key={o} value={o}>{o}</option>)}
      <option value={CUSTOM}>Custom (type new item)…</option>
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

function EntryRow({ row, itemOptions, onChange, onDelete }) {
  const isRake = row.unit === 'Rake';
  const isNew  = row.orig_item == null;
  const rowBg  = isNew ? '#fffbeb' : '#fff';
  const set = (k, v) => onChange({ ...row, [k]: v });

  return (
    <tr style={{ backgroundColor: rowBg }}>
      <td style={S.TD}><ItemSel value={row.item} onChange={v => set('item', v)} options={itemOptions} width={160} /></td>
      <td style={{ ...S.TD, textAlign: 'center' }}><Sel value={row.from_plant} onChange={v => set('from_plant', v)} options={PLANTS} width={72} /></td>
      <td style={{ ...S.TD, textAlign: 'center' }}><Sel value={row.to_plant}   onChange={v => set('to_plant',   v)} options={PLANTS} width={72} /></td>
      <td style={{ ...S.TD, textAlign: 'center' }}><Sel value={row.unit} onChange={v => set('unit', v)} options={UNITS} width={66} /></td>
      <td style={{ ...S.TD, textAlign: 'center' }}>
        <input type="number" step="1" value={row.sort_order ?? 0} onChange={e => set('sort_order', e.target.value)}
          style={{ width: 52, padding: '6px 8px', border: '1px solid #dadce0', borderRadius: 4, textAlign: 'center', fontSize: 13 }} />
      </td>
      <td style={{ ...S.TD, textAlign: 'right' }}><Num value={row.plan}   onChange={v => set('plan', v)} /></td>
      <td style={{ ...S.TD, textAlign: 'right' }}><Num value={row.actual} onChange={v => set('actual', v)} /></td>
      <td style={{ ...S.TD, textAlign: 'right' }}>
        {isRake ? <Num value={row.plan_tonnage}   onChange={v => set('plan_tonnage', v)} /> : <span style={{ color: '#5f6368' }}>—</span>}
      </td>
      <td style={{ ...S.TD, textAlign: 'right' }}>
        {isRake ? <Num value={row.actual_tonnage} onChange={v => set('actual_tonnage', v)} /> : <span style={{ color: '#5f6368' }}>—</span>}
      </td>
      <td style={{ ...S.TD, textAlign: 'center' }}>
        {isNew && <span title="Not yet saved" style={{ color: '#b45309', fontSize: 11, fontWeight: 700 }}>NEW</span>}
      </td>
      <td style={{ ...S.TD, textAlign: 'center' }}>
        <button onClick={onDelete}
          style={{ padding: '5px 12px', border: 'none', borderRadius: 4,
                   backgroundColor: '#ef4444', color: '#fff', fontSize: 13, cursor: 'pointer' }}>
          Del
        </button>
      </td>
    </tr>
  );
}

function IptDataEntryPageInner() {
  const [month, setMonth]     = useState(defaultMonth);
  const [rows, setRows]       = useState([]);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving]   = useState(false);
  const [copying, setCopying] = useState(false);
  const [status, setStatus]   = useState(null);
  const [loaded, setLoaded]   = useState(false);
  const [itemOptions, setItemOptions] = useState(IPT_ITEMS);
  const uidRef = useRef(0);
  const nextUid = () => (uidRef.current += 1);

  useEffect(() => {
    fetch(`${API}/api/ipt-items`)
      .then(res => res.ok ? res.json() : Promise.reject(new Error(res.statusText)))
      .then(data => {
        const fromDb = data.items || [];
        setItemOptions(Array.from(new Set([...IPT_ITEMS, ...fromDb])));
      })
      .catch(() => {}); // fall back to the static item list
  }, []);

  const addItemOption = useCallback((item) => {
    if (!item) return;
    setItemOptions(prev => prev.includes(item) ? prev : [...prev, item]);
  }, []);

  const rowFromDb = useCallback((r) => ({
    _uid: nextUid(),
    item: r.item, from_plant: r.from_plant, to_plant: r.to_plant,
    unit: r.unit, sort_order: r.sort_order ?? 0,
    plan:           r.plan           ?? '',
    actual:         r.actual         ?? '',
    plan_tonnage:   r.plan_tonnage   ?? '',
    actual_tonnage: r.actual_tonnage ?? '',
    orig_item: r.item, orig_from_plant: r.from_plant, orig_to_plant: r.to_plant,
  }), []);

  const load = useCallback(async (m) => {
    const target = m || month;
    setLoading(true);
    setStatus(null);
    setLoaded(false);
    try {
      const res = await fetch(`${API}/api/ipt-entries?month=${encodeURIComponent(target)}`);
      if (!res.ok) throw new Error(await res.text());
      const data = await res.json();
      setRows(data.rows.map(rowFromDb));
      setLoaded(true);
    } catch (err) {
      setStatus({ type: 'error', text: `Load failed: ${err.message}` });
    } finally {
      setLoading(false);
    }
  }, [month, rowFromDb]);

  const handleAddRow = () => {
    const maxSort = rows.reduce((mx, r) => Math.max(mx, parseInt(r.sort_order) || 0), 0);
    setRows(prev => [...prev, {
      _uid: nextUid(),
      item: '', from_plant: 'BSP', to_plant: 'DSP', unit: 'T', sort_order: maxSort + 1,
      plan: '', actual: '', plan_tonnage: '', actual_tonnage: '',
      orig_item: null, orig_from_plant: null, orig_to_plant: null,
    }]);
  };

  const handleCopyPrevious = async () => {
    const pm = prevMonthOf(month);
    setCopying(true);
    setStatus(null);
    try {
      const res = await fetch(`${API}/api/ipt-entries?month=${encodeURIComponent(pm)}`);
      if (!res.ok) throw new Error(await res.text());
      const data = await res.json();
      const existingKeys = new Set(rows.map(routeKey));
      const added = [];
      for (const r of data.rows) {
        const key = routeKey(r);
        if (existingKeys.has(key)) continue;
        existingKeys.add(key);
        added.push({
          _uid: nextUid(),
          item: r.item, from_plant: r.from_plant, to_plant: r.to_plant,
          unit: r.unit, sort_order: r.sort_order ?? 0,
          plan: '', actual: '', plan_tonnage: '', actual_tonnage: '',
          orig_item: null, orig_from_plant: null, orig_to_plant: null,
        });
      }
      if (added.length === 0) {
        setStatus({ type: 'error', text: `No new routes to copy from ${monthDisplayOf(pm)} — all already present, or that month has no routes.` });
      } else {
        setRows(prev => [...prev, ...added]);
        setStatus({ type: 'success', text: `Copied ${added.length} route(s) from ${monthDisplayOf(pm)}. Fill in Plan/Actual, then Save All.` });
      }
    } catch (err) {
      setStatus({ type: 'error', text: `Copy failed: ${err.message}` });
    } finally {
      setCopying(false);
    }
  };

  const handleRowChange = (uid, updated) =>
    setRows(prev => prev.map(r => r._uid === uid ? updated : r));

  const handleDelete = async (row) => {
    if (row.orig_item == null) {
      setRows(prev => prev.filter(r => r._uid !== row._uid));
      return;
    }
    if (!confirm(`Delete: ${row.item} ${row.from_plant} → ${row.to_plant}?`)) return;
    try {
      const res = await fetch(`${API}/api/ipt-delete`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          month, item: row.orig_item, from_plant: row.orig_from_plant, to_plant: row.orig_to_plant,
        }),
      });
      if (!res.ok) throw new Error(await res.text());
      setRows(prev => prev.filter(r => r._uid !== row._uid));
    } catch (err) {
      setStatus({ type: 'error', text: `Delete failed: ${err.message}` });
    }
  };

  const handleSaveAll = async () => {
    const valid = rows.filter(r =>
      r.item.trim() && r.from_plant && r.to_plant && r.from_plant !== r.to_plant);
    if (valid.length === 0) {
      setStatus({ type: 'error', text: 'Nothing to save — add at least one complete route (Item, From, To with From ≠ To).' });
      return;
    }
    setSaving(true);
    setStatus(null);
    try {
      const entries = valid.map(r => ({
        item: r.item.trim(), from_plant: r.from_plant, to_plant: r.to_plant,
        unit: r.unit, sort_order: parseInt(r.sort_order) || 0,
        plan: numOrNull(r.plan), actual: numOrNull(r.actual),
        plan_tonnage:   r.unit === 'Rake' ? numOrNull(r.plan_tonnage)   : null,
        actual_tonnage: r.unit === 'Rake' ? numOrNull(r.actual_tonnage) : null,
        orig_item: r.orig_item, orig_from_plant: r.orig_from_plant, orig_to_plant: r.orig_to_plant,
      }));
      const res = await fetch(`${API}/api/ipt-entries/bulk`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ month, entries }),
      });
      if (!res.ok) throw new Error(await res.text());
      const result = await res.json();
      entries.forEach(e => addItemOption(e.item));
      const skipped = rows.length - valid.length;
      setStatus({
        type: 'success',
        text: `Saved ${result.saved} route(s)${skipped ? ` — ${skipped} incomplete row(s) skipped` : ''}.`,
      });
      await load(month);
    } catch (err) {
      setStatus({ type: 'error', text: `Save failed: ${err.message}` });
    } finally {
      setSaving(false);
    }
  };

  const monthDisplay = monthDisplayOf(month);
  const newCount = rows.filter(r => r.orig_item == null).length;

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
            Inter-Plant Transfer routes for page 26. Select a month, click Load Records, edit rows inline, then Save All.
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
            <>
              <button onClick={handleAddRow} style={{
                padding: '7px 20px', fontSize: 14, fontWeight: 600,
                background: '#6366f1', color: '#fff', border: '1px solid #6366f1', borderRadius: 4, cursor: 'pointer',
              }}>
                + Add Row
              </button>

              <button onClick={handleCopyPrevious} disabled={copying} title={`Pull in routes from ${monthDisplayOf(prevMonthOf(month))} (numbers left blank for you to fill in)`} style={{
                padding: '7px 20px', fontSize: 14, fontWeight: 600,
                background: '#fff', color: '#6366f1', border: '1px solid #6366f1', borderRadius: 4,
                cursor: copying ? 'not-allowed' : 'pointer',
              }}>
                {copying ? 'Copying…' : `↻ Copy Routes from ${monthDisplayOf(prevMonthOf(month))}`}
              </button>

              <button onClick={handleSaveAll} disabled={saving || rows.length === 0} style={{
                marginLeft: 'auto', padding: '7px 22px', fontSize: 14, fontWeight: 700,
                background: rows.length === 0 ? '#9ca3af' : '#10b981', color: '#fff', border: 'none', borderRadius: 4,
                cursor: (saving || rows.length === 0) ? 'not-allowed' : 'pointer',
              }}>
                {saving ? 'Saving…' : `Save All${newCount ? ` (${newCount} new)` : ''}`}
              </button>
            </>
          )}

          <span style={{ marginLeft: loaded ? 0 : 'auto', fontSize: 13, color: '#5f6368' }}>
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
                {rows.length} route{rows.length !== 1 ? 's' : ''}{newCount ? `, ${newCount} unsaved` : ''}
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
                    <th style={S.H}></th>
                    <th style={S.H}>Del</th>
                  </tr>
                </thead>
                <tbody>
                  {rows.length === 0 && (
                    <tr>
                      <td colSpan={11} style={{ padding: 24, textAlign: 'center', color: '#5f6368', fontSize: 14 }}>
                        No routes for {monthDisplay}. Click <strong>+ Add Row</strong>, or{' '}
                        <strong>↻ Copy Routes from {monthDisplayOf(prevMonthOf(month))}</strong> if last month had similar routes.
                      </td>
                    </tr>
                  )}
                  {rows.map((row) => (
                    <EntryRow
                      key={row._uid}
                      row={row}
                      itemOptions={itemOptions}
                      onChange={updated => handleRowChange(row._uid, updated)}
                      onDelete={() => handleDelete(row)}
                    />
                  ))}
                </tbody>
              </table>
            </div>

            <div style={{
              padding: '12px 18px', backgroundColor: '#f8f9fa', borderTop: '1px solid #dadce0',
              display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 10,
            }}>
              <span style={{ fontSize: 13, color: '#5f6368' }}>
                Edit values directly in the grid, then click <strong>Save All</strong> — deletes still apply immediately. Plan (T) / Actual (T) apply only to Rake routes.
              </span>
              <button onClick={handleSaveAll} disabled={saving || rows.length === 0}
                style={{
                  padding: '7px 18px', border: 'none', borderRadius: 4,
                  backgroundColor: rows.length === 0 ? '#9ca3af' : '#10b981',
                  color: '#fff', fontSize: 14, fontWeight: 700,
                  cursor: (saving || rows.length === 0) ? 'not-allowed' : 'pointer',
                }}>
                {saving ? 'Saving…' : 'Save All'}
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

export default function IptDataEntryPage() {
  return (
    <RequireEditor>
      <IptDataEntryPageInner />
    </RequireEditor>
  );
}
