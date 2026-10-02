'use client';

import RequireEditor from '@/components/RequireEditor';
import React, { useState, useCallback, useMemo, useEffect } from 'react';
import { EntryPage, ContextBar, Field, Status, Section, SaveButton, cellClass, entryStyles as es, wb } from '../EntryUI';

const PLANTS = ['BSP', 'DSP', 'ISP', 'RSP', 'BSL', 'ASP', 'SSP', 'VISL'];
const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || '';

const MON_LABEL = ['', 'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];

function monthLabel(reportMonth) {
  const [y, m] = reportMonth.split('-');
  return `${MON_LABEL[parseInt(m, 10)]}'${y.slice(2)}`;
}

/** Every 'YYYY-MM' from `from` to `to` inclusive, chronological order. */
function monthsBetween(from, to) {
  const [fy, fm] = from.split('-').map(Number);
  const [ty, tm] = to.split('-').map(Number);
  const out = [];
  let y = fy, m = fm;
  while (y < ty || (y === ty && m <= tm)) {
    out.push(`${y}-${String(m).padStart(2, '0')}`);
    m += 1;
    if (m > 12) { m = 1; y += 1; }
  }
  return out;
}

function getDefaultRange() {
  const now = new Date();
  const to = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}`;
  const fromDate = new Date(now.getFullYear(), now.getMonth() - 11, 1);
  const from = `${fromDate.getFullYear()}-${String(fromDate.getMonth() + 1).padStart(2, '0')}`;
  return { from, to };
}

function ProductionRangeEntryInner() {
  const defaultRange = getDefaultRange();
  const [plant, setPlant] = useState('BSP');
  const [item, setItem] = useState('');
  const [knownItems, setKnownItems] = useState([]);
  const [from, setFrom] = useState(defaultRange.from);
  const [to, setTo] = useState(defaultRange.to);
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [loaded, setLoaded] = useState(false);
  const [status, setStatus] = useState(null);

  useEffect(() => {
    let cancelled = false;
    fetch(`${API_BASE_URL}/api/item-mapping-suggestions?plant=${encodeURIComponent(plant)}`)
      .then((r) => (r.ok ? r.json() : { items: [] }))
      .then((d) => {
        if (cancelled) return;
        const items = d.items ?? [];
        setKnownItems(items);
        setItem((cur) => (items.includes(cur) ? cur : (items[0] ?? '')));
      })
      .catch(() => { if (!cancelled) { setKnownItems([]); setItem(''); } });
    return () => { cancelled = true; };
  }, [plant]);

  const monthsWanted = useMemo(() => {
    if (!from || !to || from > to) return [];
    return monthsBetween(from, to);
  }, [from, to]);

  const handleLoad = useCallback(async () => {
    const trimmedItem = item.trim();
    if (!trimmedItem) {
      setStatus({ type: 'error', text: 'Select a unit first.' });
      return;
    }
    if (monthsWanted.length === 0) {
      setStatus({ type: 'error', text: '"From" must be on or before "To".' });
      return;
    }
    setLoading(true);
    setStatus(null);
    setLoaded(false);
    try {
      const res = await fetch(
        `${API_BASE_URL}/api/production-item-range?plant=${encodeURIComponent(plant)}` +
        `&item=${encodeURIComponent(trimmedItem)}&months=${monthsWanted.join(',')}`
      );
      if (!res.ok) throw new Error(await res.text());
      const data = await res.json();
      setRows(data.rows.map((r) => ({
        report_month: r.report_month,
        value: r.value,
        edit: r.value === null || r.value === undefined ? '' : String(r.value),
      })));
      setLoaded(true);
    } catch (err) {
      setStatus({ type: 'error', text: `Load failed: ${err.message}` });
    } finally {
      setLoading(false);
    }
  }, [plant, item, monthsWanted]);

  const setEdit = (idx, val) => setRows((prev) => prev.map((r, i) => (i === idx ? { ...r, edit: val } : r)));

  const hasChanges = rows.some((r) => r.edit !== (r.value === null || r.value === undefined ? '' : String(r.value)));

  const handleSave = async () => {
    setSaving(true);
    setStatus(null);
    const entries = rows
      .filter((r) => r.edit !== (r.value === null || r.value === undefined ? '' : String(r.value)))
      .map((r) => ({
        report_month: r.report_month,
        value: r.edit.trim() === '' ? null : parseFloat(r.edit),
      }));
    if (entries.length === 0) {
      setSaving(false);
      setStatus({ type: 'error', text: 'Nothing changed.' });
      return;
    }
    try {
      const res = await fetch(`${API_BASE_URL}/api/production-item-range`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ plant, item: item.trim(), entries }),
      });
      if (!res.ok) throw new Error(await res.text());
      const result = await res.json();
      setStatus({ type: 'success', text: `Saved ${result.count} month(s) for ${plant} — ${item.trim()}.` });
      await handleLoad();
    } catch (err) {
      setStatus({ type: 'error', text: `Save failed: ${err.message}` });
    } finally {
      setSaving(false);
    }
  };

  const reset = () => setRows((prev) => prev.map((r) => ({ ...r, edit: r.value === null || r.value === undefined ? '' : String(r.value) })));

  return (
    <EntryPage
      maxWidth={960}
      title="Production Data Entry — Month Range"
      description={<>
        Enter or correct one plant/unit&apos;s actual production across several months at once — writes straight
        to <code>production_table</code>, the same table every report page reads. For entering a whole month&apos;s
        items at once, use <a href="/data-entry/production">Production Data Entry</a> instead.
      </>}
    >
      <ContextBar actions={
        <button type="button" className={`${wb.btn} ${wb.btnPrimary}`} onClick={handleLoad} disabled={loading}>
          {loading ? 'Loading…' : `Load ${monthsWanted.length || ''} month(s)`}
        </button>
      }>
        <Field label="Plant" htmlFor="pr-plant">
          <select id="pr-plant" className={es.control} value={plant} onChange={(e) => { setPlant(e.target.value); setLoaded(false); setRows([]); }}>
            {PLANTS.map((p) => <option key={p} value={p}>{p}</option>)}
          </select>
        </Field>
        <Field label="Unit / Item" htmlFor="pr-item">
          {/* Units are this plant's own item names in production_table
              (via /api/item-mapping-suggestions), in process order. */}
          <select id="pr-item" className={es.control} style={{ minWidth: 200 }}
                  value={item}
                  onChange={(e) => { setItem(e.target.value); setLoaded(false); setRows([]); }}
                  disabled={knownItems.length === 0}>
            {knownItems.length === 0 && <option value="">No units in production_table</option>}
            {knownItems.map((n) => <option key={n} value={n}>{n}</option>)}
          </select>
        </Field>
        <Field label="From" htmlFor="pr-from">
          <input id="pr-from" type="month" className={es.control} value={from} onChange={(e) => { setFrom(e.target.value); setLoaded(false); setRows([]); }} />
        </Field>
        <Field label="To" htmlFor="pr-to">
          <input id="pr-to" type="month" className={es.control} value={to} onChange={(e) => { setTo(e.target.value); setLoaded(false); setRows([]); }} />
        </Field>
      </ContextBar>

      <Status status={status} />

      {loaded && rows.length > 0 && (
        <>
          <Section title={`${plant} — ${item}`} sub="Actual production, one row per month. Edited rows are highlighted until saved.">
            <table className={es.table}>
              <thead>
                <tr>
                  <th>Month</th>
                  <th className={es.r}>Actual Value</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((r, idx) => {
                  const changed = r.edit !== (r.value === null || r.value === undefined ? '' : String(r.value));
                  return (
                    <tr key={r.report_month}>
                      <td className={es.itemCell}>
                        {monthLabel(r.report_month)} <span className={wb.muted} style={{ fontSize: 11.5, fontWeight: 500 }}>({r.report_month})</span>
                      </td>
                      <td className={es.r}>
                        <input type="number" step="0.001" value={r.edit} aria-label={`${r.report_month} actual`}
                               onChange={(e) => setEdit(idx, e.target.value)}
                               className={cellClass({ changed, filled: r.edit !== '' })} style={{ width: 140 }} />
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </Section>

          <div className={es.foot}>
            <button type="button" className={wb.btn} onClick={reset} disabled={!hasChanges}>Reset</button>
            <SaveButton dirty={hasChanges} saving={saving} onClick={handleSave}>Save All</SaveButton>
          </div>
        </>
      )}

      {!loaded && !loading && (
        <div className={wb.empty}>
          Select a plant, a unit/item, and a month range, then click <strong>Load</strong>.
        </div>
      )}
    </EntryPage>
  );
}

export default function ProductionRangeEntryPage() {
  return (
    <RequireEditor>
      <ProductionRangeEntryInner />
    </RequireEditor>
  );
}
