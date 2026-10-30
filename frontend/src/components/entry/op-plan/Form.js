'use client';

import { useEffect, useMemo, useState } from 'react';
import RequireEditor from '@/components/RequireEditor';
import { EntryPage, ContextBar, Field, Section, Status, Loading, SaveButton, cellClass, entryStyles as e, wb } from '../EntryUI';

const API = process.env.NEXT_PUBLIC_API_URL || '';

const PLANT_NAMES = {
  BSP: 'Bhilai Steel Plant', DSP: 'Durgapur Steel Plant', RSP: 'Rourkela Steel Plant', BSL: 'Bokaro Steel Plant',
  ISP: 'IISCO Steel Plant', ASP: 'Alloy Steels Plant', SSP: 'Salem Steel Plant', VISL: 'Visvesvaraya Iron & Steel Plant',
};
const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];

// The OP is finalised before the month starts, so open on next month.
function nextMonth() {
  const d = new Date();
  d.setMonth(d.getMonth() + 1, 1);
  return { month: String(d.getMonth() + 1).padStart(2, '0'), year: String(d.getFullYear()) };
}

async function fetchOpPlan(plant, month) {
  const res = await fetch(`${API}/api/op-plan?plant=${encodeURIComponent(plant)}&month=${encodeURIComponent(month)}`);
  const body = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(typeof body.detail === 'string' ? body.detail : `Load failed (${res.status})`);
  return body;
}

const toText = (v) => (v == null ? '' : String(v));
const toNum = (t) => (t.trim() === '' ? null : Number(t));
const fmt = (v, digits = 2) => (v == null || Number.isNaN(v) ? '—'
  : v.toLocaleString('en-IN', { maximumFractionDigits: digits }));

function OpPlanInner() {
  const start = nextMonth();
  const [plant, setPlant] = useState('BSP');
  const [month, setMonth] = useState(start.month);
  const [year, setYear] = useState(start.year);
  const [data, setData] = useState(null);            // last loaded GET /api/op-plan
  const [edits, setEdits] = useState({});            // item_name -> text typed
  const [reloadKey, setReloadKey] = useState(0);
  const [loadError, setLoadError] = useState(null);
  const [saving, setSaving] = useState(false);
  const [status, setStatus] = useState(null);

  const reportMonth = `${year}-${month}`;
  const years = useMemo(() => {
    const y = new Date().getFullYear();
    return Array.from({ length: 8 }, (_, i) => String(y - 5 + i));
  }, []);

  useEffect(() => {
    let live = true;
    fetchOpPlan(plant, reportMonth)
      .then((body) => { if (live) { setData(body); setEdits({}); setLoadError(null); } })
      .catch((err) => { if (live) setLoadError({ key: `${plant}|${reportMonth}`, text: err.message }); });
    return () => { live = false; };
  }, [plant, reportMonth, reloadKey]);

  // The table shown belongs to the selected plant and month.
  const error = loadError?.key === `${plant}|${reportMonth}` ? loadError.text : null;
  const loading = !error && (!data || data.plant !== plant || data.month !== reportMonth);

  const items = data?.items ?? [];
  const textOf = (it) => (it.item_name in edits ? edits[it.item_name] : toText(it.op_plan));
  const isDirty = (it) => it.item_name in edits && toNum(edits[it.item_name]) !== it.op_plan;
  const dirty = items.filter(isDirty);
  const invalid = dirty.filter((it) => { const v = toNum(edits[it.item_name]); return v !== null && (Number.isNaN(v) || v < 0); });

  // Leaving with unsaved edits: ask first.
  const guard = (fn) => (...args) => {
    if (dirty.length && !window.confirm(`Discard ${dirty.length} unsaved OP change${dirty.length === 1 ? '' : 's'}?`)) return;
    setStatus(null);
    fn(...args);
  };

  const copyApp = () => {
    const next = { ...edits };
    let n = 0;
    items.forEach((it) => {
      if (it.app_plan != null && textOf(it).trim() === '') { next[it.item_name] = toText(it.app_plan); n += 1; }
    });
    setEdits(next);
    setStatus({ type: 'info', text: n ? `Copied the APP into ${n} empty OP cell${n === 1 ? '' : 's'}. Adjust and save.` : 'No empty OP cell has an APP value to copy.' });
  };

  const save = async () => {
    if (invalid.length) {
      setStatus({ type: 'error', text: `Enter a number ≥ 0 for: ${invalid.map((it) => it.item_name).join(', ')}` });
      return;
    }
    setSaving(true);
    setStatus(null);
    try {
      const res = await fetch(`${API}/api/op-plan`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          plant, month: reportMonth,
          entries: dirty.map((it) => ({ item_name: it.item_name, op_plan: toNum(edits[it.item_name]) })),
        }),
      });
      const body = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(typeof body.detail === 'string' ? body.detail : `Save failed (${res.status})`);
      setReloadKey((k) => k + 1);
      const parts = [body.saved && `${body.saved} saved`, body.cleared && `${body.cleared} cleared`].filter(Boolean);
      setStatus({ type: 'success', text: `OP for ${plant}, ${MONTHS[Number(month) - 1]} ${year}: ${parts.join(', ') || 'no change'}.` });
    } catch (err) {
      setStatus({ type: 'error', text: err.message });
    } finally {
      setSaving(false);
    }
  };

  const counts = data?.plant_counts ?? {};
  const plants = data?.plants ?? Object.keys(PLANT_NAMES);
  const filled = items.filter((it) => toNum(textOf(it)) != null).length;
  const monthLabel = `${MONTHS[Number(month) - 1]} ${year}`;

  return (
    <EntryPage
      title="Operating Plan (OP)"
      description="The month's production plan finalised before the month starts, for every production unit of each plant. It is kept separately from the Annual Plan (APP), which is shown alongside for reference, using the same items and units."
    >
      <ContextBar actions={(
        <>
          <button type="button" className={wb.btn} onClick={copyApp} disabled={loading || !items.length}>Copy APP into empty OP</button>
          <SaveButton dirty={dirty.length > 0} saving={saving} onClick={save}>
            {dirty.length ? `Save OP (${dirty.length})` : 'Save OP'}
          </SaveButton>
        </>
      )}>
        <Field label="Month" htmlFor="op-month">
          <select id="op-month" className={wb.select} value={month} onChange={guard((ev) => setMonth(ev.target.value))}>
            {MONTHS.map((m, i) => <option key={m} value={String(i + 1).padStart(2, '0')}>{m}</option>)}
          </select>
          <select className={wb.select} value={year} aria-label="Year" onChange={guard((ev) => setYear(ev.target.value))}>
            {years.map((y) => <option key={y} value={y}>{y}</option>)}
          </select>
        </Field>
        <Field label={`Plants with an OP for ${monthLabel}`}>
          <div className={wb.chips} role="group" aria-label="Plant">
            {plants.map((p) => (
              <button key={p} type="button" aria-pressed={p === plant} title={PLANT_NAMES[p]}
                      className={`${wb.chip} ${p === plant ? wb.chipActive : ''}`}
                      onClick={guard(() => setPlant(p))}>
                {p}
                <span className={wb.chipCount}>{counts[p] ? counts[p] : '–'}</span>
              </button>
            ))}
          </div>
        </Field>
      </ContextBar>

      <Status status={status} />

      <Section
        title={`${plant} — ${PLANT_NAMES[plant]} · ${monthLabel}`}
        sub={data ? `${filled} of ${items.length} items have an OP${data.last_updated ? ` · last saved ${data.last_updated.at}${data.last_updated.by ? ` by ${data.last_updated.by}` : ''}` : ''}` : ''}
      >
        {error ? <div className={wb.empty}>Could not load the OP: {error}</div>
          : loading ? <Loading /> : !items.length ? (
          <div className={wb.empty}>
            No production items for {plant} in {monthLabel}. Items come from the uploaded APP for that month; upload the APP first.
          </div>
        ) : (
          <table className={e.table}>
            <thead>
              <tr>
                <th>Production unit / item</th>
                <th className={e.r}>APP</th>
                <th className={e.r} style={{ width: 150 }}>OP</th>
                <th className={e.r}>OP − APP</th>
                <th className={e.r}>OP ÷ APP</th>
              </tr>
            </thead>
            <tbody>
              {items.map((it) => {
                const text = textOf(it);
                const op = toNum(text);
                const valid = op != null && !Number.isNaN(op);
                const diff = valid && it.app_plan != null ? op - it.app_plan : null;
                const pct = valid && it.app_plan ? (op / it.app_plan) * 100 : null;
                return (
                  <tr key={it.item_name}>
                    <td className={e.itemCell}>{it.item_name}</td>
                    <td className={e.r}>{fmt(it.app_plan)}</td>
                    <td className={e.r}>
                      <input type="number" inputMode="decimal" min="0" step="any" value={text}
                             aria-label={`OP for ${it.item_name}`}
                             className={cellClass({ changed: isDirty(it), filled: text !== '' })}
                             onChange={(ev) => setEdits((m) => ({ ...m, [it.item_name]: ev.target.value }))} />
                    </td>
                    <td className={e.r} style={{ color: diff == null ? undefined : diff < 0 ? 'var(--ui-danger)' : 'var(--ui-success)' }}>
                      {diff == null ? '—' : `${diff > 0 ? '+' : ''}${fmt(diff)}`}
                    </td>
                    <td className={e.r}>{pct == null ? '—' : `${fmt(pct, 1)}%`}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}
      </Section>
      <p className={wb.muted} style={{ fontSize: 12 }}>
        Values are in the same units as the APP for each item. Clear a cell and save to remove that item&apos;s OP.
      </p>
    </EntryPage>
  );
}

export default function OpPlanForm() {
  return (
    <RequireEditor>
      <OpPlanInner />
    </RequireEditor>
  );
}
