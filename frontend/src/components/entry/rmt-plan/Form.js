'use client';

import { Fragment, useEffect, useMemo, useState } from 'react';
import Link from 'next/link';
import RequireEditor from '@/components/RequireEditor';
import { EntryPage, ContextBar, Field, Section, Status, Loading, SaveButton, cellClass, entryStyles as e, wb } from '../EntryUI';

const API = process.env.NEXT_PUBLIC_API_URL || '';
const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
const IPT_ITEMS = ['Sinter', 'BF Coke', 'Coke Breeze', 'CC Slabs', 'CC Blooms', 'Pig Iron', 'Hot Metal'];
const PLANTS = ['BSP', 'DSP', 'RSP', 'BSL', 'ISP', 'ASP', 'SSP', 'VISL'];
const EMPTY_IPT = { item: '', from_plant: '', to_plant: '', availability: '', requirement: '', remarks: '' };
const EMPTY_STOCK = { plant: '', bf_coke: '', slab: '', bloom: '' };

// The RMT plan is discussed before the month starts, so open on next month.
function nextMonth() {
  const d = new Date();
  d.setMonth(d.getMonth() + 1, 1);
  return { month: String(d.getMonth() + 1).padStart(2, '0'), year: String(d.getFullYear()) };
}

const txt = (v) => (v == null ? '' : String(v));
const toNum = (t) => (String(t).trim() === '' ? null : Number(t));

// The form state from GET /api/rmt-plan/form: every value as typed text.
function toState(body) {
  const notes = {};
  body.notes.forEach((n) => {
    notes[`${n.section}|${n.row_label}`] = { remarks: txt(n.remarks), coal_req_app: txt(n.coal_req_app), coal_req_op: txt(n.coal_req_op) };
  });
  return {
    notes,
    ipt: body.ipt.map((r) => Object.fromEntries(Object.keys(EMPTY_IPT).map((k) => [k, txt(r[k])]))),
    stock: body.stock.map((r) => Object.fromEntries(Object.keys(EMPTY_STOCK).map((k) => [k, txt(r[k])]))),
    stock_as_on: txt(body.stock_as_on),
    note: txt(body.note),
  };
}

// Move row i of a list by d (−1 up, +1 down).
function move(list, i, d) {
  const j = i + d;
  if (j < 0 || j >= list.length) return list;
  const out = [...list];
  [out[i], out[j]] = [out[j], out[i]];
  return out;
}

function RowButtons({ i, n, onMove, onDelete }) {
  return (
    <div style={{ display: 'flex', gap: 2 }}>
      <button type="button" className={wb.iconBtn} title="Move up" disabled={i === 0} onClick={() => onMove(i, -1)}>↑</button>
      <button type="button" className={wb.iconBtn} title="Move down" disabled={i === n - 1} onClick={() => onMove(i, 1)}>↓</button>
      <button type="button" className={wb.iconBtn} title="Delete row" onClick={() => onDelete(i)}>✕</button>
    </div>
  );
}

function RmtPlanInner() {
  const start = nextMonth();
  const [month, setMonth] = useState(start.month);
  const [year, setYear] = useState(start.year);
  const [data, setData] = useState(null);       // last GET /api/rmt-plan/form
  const [form, setForm] = useState(null);       // what is being edited
  const [reloadKey, setReloadKey] = useState(0);
  const [loadError, setLoadError] = useState(null);
  const [saving, setSaving] = useState(false);
  const [status, setStatus] = useState(null);

  const reportMonth = `${year}-${month}`;
  const monthLabel = `${MONTHS[Number(month) - 1]} ${year}`;
  const years = useMemo(() => {
    const y = new Date().getFullYear();
    return Array.from({ length: 8 }, (_, i) => String(y - 5 + i));
  }, []);

  useEffect(() => {
    let live = true;
    fetch(`${API}/api/rmt-plan/form?month=${encodeURIComponent(reportMonth)}`)
      .then(async (res) => {
        const body = await res.json().catch(() => ({}));
        if (!res.ok) throw new Error(typeof body.detail === 'string' ? body.detail : `Load failed (${res.status})`);
        return body;
      })
      .then((body) => { if (live) { setData(body); setForm(toState(body)); setLoadError(null); } })
      .catch((err) => { if (live) setLoadError({ key: reportMonth, text: err.message }); });
    return () => { live = false; };
  }, [reportMonth, reloadKey]);

  const error = loadError?.key === reportMonth ? loadError.text : null;
  const loading = !error && (!data || data.month !== reportMonth || !form);
  // A month with nothing saved opens with last month's IPT / stock rows: unsaved until Save.
  const dirty = !loading && (data.copied_from != null || JSON.stringify(form) !== JSON.stringify(toState(data)));

  const guard = (fn) => (...args) => {
    if (dirty && !window.confirm('Discard the unsaved RMT entries?')) return;
    setStatus(null);
    fn(...args);
  };

  const note = (section, row) => form.notes[`${section}|${row}`] ?? { remarks: '', coal_req_app: '', coal_req_op: '' };
  const setNote = (section, row, field, value) => setForm((f) => ({
    ...f, notes: { ...f.notes, [`${section}|${row}`]: { ...note(section, row), [field]: value } },
  }));
  const setList = (key, fn) => setForm((f) => ({ ...f, [key]: fn(f[key]) }));
  const setCell = (key, i, field, value) => setList(key, (l) => l.map((r, k) => (k === i ? { ...r, [field]: value } : r)));

  const save = async () => {
    const notes = [];
    for (const [k, v] of Object.entries(form.notes)) {
      const [section, row_label] = k.split('|');
      const app = toNum(v.coal_req_app);
      const op = toNum(v.coal_req_op);
      if ([app, op].some((x) => x != null && (Number.isNaN(x) || x < 0))) {
        setStatus({ type: 'error', text: `Coal requirement for ${row_label} must be a number ≥ 0.` });
        return;
      }
      notes.push({ section, row_label, remarks: v.remarks, coal_req_app: app, coal_req_op: op });
    }
    setSaving(true);
    setStatus(null);
    try {
      const res = await fetch(`${API}/api/rmt-plan`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ month: reportMonth, stock_as_on: form.stock_as_on || null, note: form.note, notes, ipt: form.ipt, stock: form.stock }),
      });
      const body = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(typeof body.detail === 'string' ? body.detail : `Save failed (${res.status})`);
      setReloadKey((k) => k + 1);
      setStatus({ type: 'success', text: `RMT plan for ${monthLabel} saved: ${body.notes} remark rows, ${body.ipt} IPT rows, ${body.stock} stock rows.` });
    } catch (err) {
      setStatus({ type: 'error', text: err.message });
    } finally {
      setSaving(false);
    }
  };

  return (
    <EntryPage
      title="RMT Production Plan — remarks, IPT & stock"
      description="The manual parts of the RMT 'Production Plan for <month>' report: shutdown remarks per plant, the coal requirement per day, the IPT requirement / availability and the stock table. APP, OP and actuals come from the database."
    >
      <ContextBar actions={(
        <>
          <Link href="/reports/production-analysis?tab=rmt-plan" className={wb.btn}>View report</Link>
          <SaveButton dirty={dirty} saving={saving} onClick={save}>Save</SaveButton>
        </>
      )}>
        <Field label="Report month" htmlFor="rmt-month">
          <select id="rmt-month" className={wb.select} value={month} onChange={guard((ev) => setMonth(ev.target.value))}>
            {MONTHS.map((m, i) => <option key={m} value={String(i + 1).padStart(2, '0')}>{m}</option>)}
          </select>
          <select className={wb.select} value={year} aria-label="Year" onChange={guard((ev) => setYear(ev.target.value))}>
            {years.map((y) => <option key={y} value={y}>{y}</option>)}
          </select>
        </Field>
      </ContextBar>

      <Status status={status} />
      {error && <Status status={{ type: 'error', text: `Could not load: ${error}` }} />}
      {!loading && data.copied_from && (
        <Status status={{ type: 'info', text: `Nothing saved for ${monthLabel} yet: the IPT and stock rows below are copied from ${data.copied_from}. Edit them and save.` }} />
      )}
      {!loading && data.updated_at && (
        <p className={wb.muted} style={{ fontSize: 12, margin: '0 0 8px' }}>Last saved {data.updated_at}{data.updated_by ? ` by ${data.updated_by}` : ''}.</p>
      )}

      {loading ? (!error && <Loading />) : (
        <>
          <Section title="Remarks (pages 1 & 2)" sub="Shutdown / capital repair plan, requirements, … per plant. Wrap text in **double stars** to print it bold; line breaks are kept.">
            <table className={e.table}>
              <thead>
                <tr>
                  <th style={{ width: 90 }}>Plant</th>
                  <th className={e.r} style={{ width: 130 }}>Coal req. APP (T/day)</th>
                  <th className={e.r} style={{ width: 130 }}>Coal req. OP (T/day)</th>
                  <th>Remarks</th>
                </tr>
              </thead>
              <tbody>
                {data.sections.map((s) => (
                  <Fragment key={s.key}>
                    <tr className={e.subRow}><td colSpan={4}>{s.label}</td></tr>
                    {s.rows.map((r) => {
                      const n = note(s.key, r);
                      const coal = s.coal && !['5 ISPs', 'SAIL'].includes(r);
                      return (
                        <tr key={r}>
                          <td className={e.itemCell}>{r}</td>
                          {['coal_req_app', 'coal_req_op'].map((f) => (
                            <td key={f} className={e.r}>
                              {coal ? (
                                <input type="number" inputMode="decimal" min="0" step="any" value={n[f]}
                                       aria-label={`${f === 'coal_req_app' ? 'APP' : 'OP'} coal requirement for ${r}`}
                                       className={cellClass({ filled: n[f] !== '' })}
                                       onChange={(ev) => setNote(s.key, r, f, ev.target.value)} />
                              ) : <span className={wb.muted}>{s.coal ? 'sum' : ''}</span>}
                            </td>
                          ))}
                          <td>
                            <textarea className={e.textarea} rows={n.remarks.includes('\n') || n.remarks.length > 90 ? 3 : 1}
                                      value={n.remarks} aria-label={`${s.label} remarks for ${r}`}
                                      onChange={(ev) => setNote(s.key, r, 'remarks', ev.target.value)} />
                          </td>
                        </tr>
                      );
                    })}
                  </Fragment>
                ))}
              </tbody>
            </table>
          </Section>

          <Section
            title="IPT Requirement / Availability (page 3)"
            sub="Unit: T, or rakes as text ('8 Rakes'). Consecutive rows with the same item print as one group."
            actions={<button type="button" className={`${wb.btn} ${wb.btnSm}`} onClick={() => setList('ipt', (l) => [...l, { ...EMPTY_IPT }])}>+ Add row</button>}
          >
            <datalist id="rmt-ipt-items">{IPT_ITEMS.map((x) => <option key={x} value={x} />)}</datalist>
            <datalist id="rmt-plants">{PLANTS.map((x) => <option key={x} value={x} />)}</datalist>
            {form.ipt.length === 0 ? <div className={wb.empty}>No IPT rows. Add one.</div> : (
              <table className={e.table}>
                <thead>
                  <tr>
                    <th style={{ width: 130 }}>Item</th><th style={{ width: 80 }}>From</th><th style={{ width: 80 }}>To</th>
                    <th style={{ width: 110 }}>Availability</th><th style={{ width: 110 }}>Requirement</th><th>Remarks</th><th style={{ width: 90 }} />
                  </tr>
                </thead>
                <tbody>
                  {form.ipt.map((r, i) => (
                    <tr key={i}>
                      <td><input className={cellClass({ text: true, filled: r.item !== '' })} list="rmt-ipt-items" value={r.item} aria-label="Item" onChange={(ev) => setCell('ipt', i, 'item', ev.target.value)} /></td>
                      <td><input className={cellClass({ text: true, filled: r.from_plant !== '' })} list="rmt-plants" value={r.from_plant} aria-label="From plant" onChange={(ev) => setCell('ipt', i, 'from_plant', ev.target.value)} /></td>
                      <td><input className={cellClass({ text: true, filled: r.to_plant !== '' })} list="rmt-plants" value={r.to_plant} aria-label="To plant" onChange={(ev) => setCell('ipt', i, 'to_plant', ev.target.value)} /></td>
                      <td><input className={cellClass({ text: true, filled: r.availability !== '' })} value={r.availability} aria-label="Availability" onChange={(ev) => setCell('ipt', i, 'availability', ev.target.value)} /></td>
                      <td><input className={cellClass({ text: true, filled: r.requirement !== '' })} value={r.requirement} aria-label="Requirement" onChange={(ev) => setCell('ipt', i, 'requirement', ev.target.value)} /></td>
                      <td><textarea className={e.textarea} rows={r.remarks.includes('\n') ? 3 : 1} value={r.remarks} aria-label="Remarks" onChange={(ev) => setCell('ipt', i, 'remarks', ev.target.value)} /></td>
                      <td><RowButtons i={i} n={form.ipt.length} onMove={(k, d) => setList('ipt', (l) => move(l, k, d))} onDelete={(k) => setList('ipt', (l) => l.filter((_, j) => j !== k))} /></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </Section>

          <Section
            title="Stock (page 3)"
            sub="Unit: T. Text is printed as typed, e.g. '0(RSP), 1500(SSP)'."
            actions={<button type="button" className={`${wb.btn} ${wb.btnSm}`} onClick={() => setList('stock', (l) => [...l, { ...EMPTY_STOCK }])}>+ Add row</button>}
          >
            <div style={{ display: 'flex', gap: 16, flexWrap: 'wrap', padding: '8px 12px' }}>
              <label className={wb.label}>
                Stock as on{' '}
                <input type="date" className={wb.input} value={form.stock_as_on} onChange={(ev) => setForm((f) => ({ ...f, stock_as_on: ev.target.value }))} />
              </label>
            </div>
            {form.stock.length === 0 ? <div className={wb.empty}>No stock rows. Add one.</div> : (
              <table className={e.table}>
                <thead>
                  <tr><th style={{ width: 110 }}>Plant</th><th>BF Coke</th><th>Slab</th><th>Bloom</th><th style={{ width: 90 }} /></tr>
                </thead>
                <tbody>
                  {form.stock.map((r, i) => (
                    <tr key={i}>
                      <td><input className={cellClass({ text: true, filled: r.plant !== '' })} list="rmt-plants" value={r.plant} aria-label="Plant" onChange={(ev) => setCell('stock', i, 'plant', ev.target.value)} /></td>
                      {['bf_coke', 'slab', 'bloom'].map((f) => (
                        <td key={f}><input className={cellClass({ text: true, filled: r[f] !== '' })} value={r[f]} aria-label={f} onChange={(ev) => setCell('stock', i, f, ev.target.value)} /></td>
                      ))}
                      <td><RowButtons i={i} n={form.stock.length} onMove={(k, d) => setList('stock', (l) => move(l, k, d))} onDelete={(k) => setList('stock', (l) => l.filter((_, j) => j !== k))} /></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </Section>

          <Section title="Footnote (page 1)" sub="Printed under the first table, e.g. 'Note: figures are provisional'.">
            <div style={{ padding: '8px 12px' }}>
              <input className={wb.input} style={{ width: '100%' }} maxLength={255} value={form.note} aria-label="Footnote"
                     onChange={(ev) => setForm((f) => ({ ...f, note: ev.target.value }))} />
            </div>
          </Section>
        </>
      )}
    </EntryPage>
  );
}

export default function RmtPlanForm() {
  return (
    <RequireEditor>
      <RmtPlanInner />
    </RequireEditor>
  );
}
