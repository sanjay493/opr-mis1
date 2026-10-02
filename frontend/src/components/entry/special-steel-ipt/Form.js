'use client';

import RequireEditor from '@/components/RequireEditor';
import React, { useState, useEffect, useCallback, useRef } from 'react';
import { EntryPage, ContextBar, Field, Status, Section, SaveButton, Loading, cellClass, entryStyles as es, wb } from '../EntryUI';

const API = process.env.NEXT_PUBLIC_API_URL || '';

// Must match backend main.py's _IPT_PLANTS.
const PLANTS = ['BSP', 'DSP', 'ISP', 'RSP', 'BSL', 'ASP', 'SSP', 'VISL', 'CFP'];

function numOrNull(v) {
  const f = parseFloat(v);
  return Number.isNaN(f) ? null : f;
}

function Sel({ value, onChange, options, width = 90 }) {
  return (
    <select value={value} onChange={(e) => onChange(e.target.value)}
      className={es.control} style={{ width, fontWeight: 500 }}>
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

  const newCount = rows.filter((r) => r.orig_item == null).length;

  return (
    <EntryPage
      maxWidth={1000}
      title="Special Steel Plants — IPT Requirement Entry"
      description={<>
        Annual inter-plant-transfer requirement list for the Special Steel Plants Physical Performance report.
        Plan is in ’000 T. Distinct from the monthly IPT Status.
      </>}
    >
      <ContextBar actions={<>
        <button type="button" className={wb.btn} onClick={addRow}>+ Add Row</button>
        <SaveButton dirty={rows.length > 0} saving={saving} onClick={saveAll}>
          {`Save All${newCount ? ` (${newCount} new)` : ''}`}
        </SaveButton>
      </>}>
        <Field label="Financial year" htmlFor="ss-ipt-fy">
          <select id="ss-ipt-fy" className={es.control} style={{ minWidth: 120 }} value={fy} onChange={(e) => setFy(e.target.value)}>
            {fys.map((f) => <option key={f} value={f}>{f}</option>)}
            {fy && !fys.includes(fy) && <option value={fy}>{fy}</option>}
          </select>
        </Field>
      </ContextBar>

      <Status status={status} />

      {loading ? <Loading /> : (
        <Section title={`IPT requirement — FY ${fy}`} sub="New rows are highlighted until saved.">
          <table className={es.table}>
            <thead>
              <tr>
                <th>Item (’000 T)</th>
                <th className={es.c}>From</th>
                <th className={es.c}>To</th>
                <th className={es.c} style={{ width: 70 }}>Sort</th>
                <th className={es.r}>Plan</th>
                <th className={es.c} style={{ width: 70 }} />
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <tr key={r._uid} style={r.orig_item == null ? { background: 'var(--ui-warning-bg)' } : undefined}>
                  <td>
                    <input value={r.item} onChange={(e) => change(r._uid, { item: e.target.value })} aria-label="Item"
                           placeholder="e.g. CC Slabs" className={cellClass({ text: true })} style={{ width: 260 }} />
                  </td>
                  <td className={es.c}><Sel value={r.from_plant} onChange={(v) => change(r._uid, { from_plant: v })} options={PLANTS} /></td>
                  <td className={es.c}><Sel value={r.to_plant} onChange={(v) => change(r._uid, { to_plant: v })} options={PLANTS} /></td>
                  <td className={es.c}>
                    <input type="number" step="1" value={r.sort_order} onChange={(e) => change(r._uid, { sort_order: e.target.value })}
                           aria-label="Sort order" className={cellClass()} style={{ width: 56, textAlign: 'center' }} />
                  </td>
                  <td className={es.r}>
                    <input type="number" step="any" value={r.plan_kt} onChange={(e) => change(r._uid, { plan_kt: e.target.value })}
                           aria-label="Plan" className={cellClass({ filled: r.plan_kt !== '' && r.plan_kt != null })} />
                  </td>
                  <td className={es.c}>
                    <button type="button" onClick={() => del(r)} className={wb.iconBtn} title="Delete row" aria-label="Delete row">✕</button>
                  </td>
                </tr>
              ))}
              {!rows.length && (
                <tr><td colSpan={6} className={es.c} style={{ padding: 30, color: 'var(--ui-text-secondary)' }}>No rows. Click “+ Add Row”.</td></tr>
              )}
            </tbody>
          </table>
        </Section>
      )}
    </EntryPage>
  );
}

export default function SpecialSteelIptEntryPage() {
  return (
    <RequireEditor>
      <SpecialSteelIptEntryInner />
    </RequireEditor>
  );
}
