'use client';

import { useMemo, useRef, useState } from 'react';
import Link from 'next/link';
import RequireEditor from '@/components/RequireEditor';
import { EntryPage, ContextBar, Field, Section, Status, SaveButton, entryStyles as e, wb } from '../EntryUI';

const API = process.env.NEXT_PUBLIC_API_URL || '';
const PLANTS = ['BSP', 'DSP', 'RSP', 'BSL', 'ISP', 'ASP', 'SSP', 'VISL'];
const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];

const STATUS = {
  matched: { text: 'APP matches', cls: wb.badgeGreen, tip: 'Label recognised and the file’s APP equals the APP in the database' },
  check: { text: 'APP differs', cls: wb.badgeAmber, tip: 'Label recognised but the file’s APP differs from the database APP: check before saving' },
  'app-only': { text: 'by APP only', cls: wb.badgeAmber, tip: 'No label: matched only because the APP figure is unique' },
  manual: { text: 'chosen', cls: wb.badgeBlue, tip: 'Item chosen by you' },
  duplicate: { text: 'repeat', cls: wb.badgeGrey, tip: 'The same item appears on an earlier line' },
  unmatched: { text: 'not mapped', cls: wb.badgeGrey, tip: 'Not recognised as a production item' },
};

const num = (v, d = 3) => (v == null ? '—' : Number(v).toLocaleString('en-IN', { maximumFractionDigits: d }));
const monthLabel = (ym) => (ym ? `${MONTHS[Number(ym.slice(5)) - 1]} ${ym.slice(0, 4)}` : '');

function OpPlanUploadInner() {
  const [file, setFile] = useState(null);
  const [plant, setPlant] = useState('');            // '' = from the file
  const [month, setMonth] = useState('');            // 'YYYY-MM' or ''
  const [result, setResult] = useState(null);        // POST /api/op-plan/extract
  const [rows, setRows] = useState([]);              // editable copy of result.rows
  const [showAll, setShowAll] = useState(false);
  const [busy, setBusy] = useState(false);
  const [saving, setSaving] = useState(false);
  const [status, setStatus] = useState(null);
  const fileRef = useRef(null);

  const years = useMemo(() => {
    const y = new Date().getFullYear();
    return Array.from({ length: 4 }, (_, i) => String(y - 1 + i));
  }, []);

  const extract = async (f = file, p = plant, m = month) => {
    if (!f) return;
    setBusy(true);
    setStatus(null);
    try {
      const fd = new FormData();
      fd.append('file', f);
      if (p) fd.append('plant', p);
      if (m) fd.append('month', m);
      const res = await fetch(`${API}/api/op-plan/extract`, { method: 'POST', body: fd });
      const body = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(typeof body.detail === 'string' ? body.detail : `Extraction failed (${res.status})`);
      setResult(body);
      setRows(body.rows.map((r, i) => ({ ...r, id: i, opText: r.op_value == null ? '' : String(r.op_value) })));
      setPlant(body.plant);
      setMonth(body.month);
    } catch (err) {
      setResult(null);
      setRows([]);
      setStatus({ type: 'error', text: err.message });
    } finally {
      setBusy(false);
    }
  };

  const pick = (f) => {
    setFile(f);
    setPlant('');
    setMonth('');
    extract(f, '', '');
  };

  const appOf = useMemo(() => Object.fromEntries((result?.items ?? []).map((i) => [i.item_name, i.app_plan])), [result]);
  const currentOf = useMemo(() => Object.fromEntries((result?.items ?? []).map((i) => [i.item_name, i.op_plan])), [result]);

  const update = (id, patch) => setRows((rs) => rs.map((r) => (r.id === id ? { ...r, ...patch } : r)));
  const chooseItem = (r, item) => {
    if (!item) { update(r.id, { item: null, selected: false, status: 'unmatched' }); return; }
    const op = r.op * (r.scale || 1);
    update(r.id, { item, selected: true, status: 'manual', db_app: appOf[item], current_op: currentOf[item],
                   opText: r.opText || String(Math.round(op * 1000) / 1000) });
  };

  const chosen = rows.filter((r) => r.selected && r.item);
  const dupItems = Object.entries(chosen.reduce((m, r) => ({ ...m, [r.item]: (m[r.item] || 0) + 1 }), {}))
    .filter(([, n]) => n > 1).map(([i]) => i);
  const bad = chosen.filter((r) => r.opText.trim() === '' || Number.isNaN(Number(r.opText)) || Number(r.opText) < 0);
  const shown = showAll ? rows : rows.filter((r) => r.item || r.selected);
  const hidden = rows.length - shown.length;
  const missing = (result?.items ?? []).filter((i) => !chosen.some((r) => r.item === i.item_name));

  const save = async () => {
    if (dupItems.length) { setStatus({ type: 'error', text: `Each item can be saved once; chosen twice: ${dupItems.join(', ')}` }); return; }
    if (bad.length) { setStatus({ type: 'error', text: `Enter an OP ≥ 0 for: ${bad.map((r) => r.item).join(', ')}` }); return; }
    const overwrite = chosen.filter((r) => r.current_op != null && Number(r.opText) !== r.current_op);
    if (overwrite.length && !window.confirm(
      `${overwrite.length} item${overwrite.length === 1 ? ' already has' : 's already have'} a different OP for ${result.plant} ${monthLabel(result.month)} `
      + `(${overwrite.slice(0, 5).map((r) => r.item).join(', ')}${overwrite.length > 5 ? ', …' : ''}). Replace with the file's values?`)) return;
    setSaving(true);
    setStatus(null);
    try {
      const res = await fetch(`${API}/api/op-plan`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ plant: result.plant, month: result.month,
                               entries: chosen.map((r) => ({ item_name: r.item, op_plan: Number(r.opText) })) }),
      });
      const body = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(typeof body.detail === 'string' ? body.detail : `Save failed (${res.status})`);
      setStatus({ type: 'success', text: `Saved the OP of ${body.saved} items for ${result.plant}, ${monthLabel(result.month)}.` });
      await extract(file, result.plant, result.month);   // refresh "current OP"
    } catch (err) {
      setStatus({ type: 'error', text: err.message });
    } finally {
      setSaving(false);
    }
  };

  const detected = result?.detected;
  const overridden = result && detected && (detected.plant !== result.plant || detected.month !== result.month);

  return (
    <EntryPage
      title="Operating Plan (OP) — Upload"
      description={<>Upload a plant&apos;s monthly plan file (Excel, or a PDF with text) to read its OP figures. Each line is mapped to a production item and checked against the item&apos;s APP; review, correct and save. Saved values appear on the <Link href="/data-entry/production-techno?tab=op-plan">Operating Plan (OP)</Link> tab. A photo or scanned plan has no text: enter it there by hand.</>}
    >
      <ContextBar actions={result && (
        <SaveButton dirty={chosen.length > 0} saving={saving} onClick={save}>
          {`Save ${chosen.length} OP value${chosen.length === 1 ? '' : 's'}`}
        </SaveButton>
      )}>
        <Field label="Plan file">
          <button type="button" className={`${wb.btn} ${wb.btnPrimary}`} disabled={busy} onClick={() => fileRef.current?.click()}>
            {busy ? 'Reading…' : file ? 'Choose another file' : '⬆ Choose plan file'}
          </button>
          <input ref={fileRef} type="file" hidden accept=".xlsx,.xlsm,.pdf"
                 onChange={(ev) => { const f = ev.target.files?.[0]; ev.target.value = ''; if (f) pick(f); }} />
          {file && <span className={wb.muted} style={{ fontSize: 12 }}>{file.name}</span>}
        </Field>
        {result && (
          <>
            <Field label="Plant" htmlFor="opu-plant">
              <select id="opu-plant" className={wb.select} value={plant} disabled={busy}
                      onChange={(ev) => { setPlant(ev.target.value); extract(file, ev.target.value, month); }}>
                {PLANTS.map((p) => <option key={p} value={p}>{p}</option>)}
              </select>
            </Field>
            <Field label="Month" htmlFor="opu-month">
              <select id="opu-month" className={wb.select} value={month.slice(5)} disabled={busy}
                      onChange={(ev) => { const m = `${month.slice(0, 4)}-${ev.target.value}`; setMonth(m); extract(file, plant, m); }}>
                {MONTHS.map((m, i) => <option key={m} value={String(i + 1).padStart(2, '0')}>{m}</option>)}
              </select>
              <select className={wb.select} value={month.slice(0, 4)} aria-label="Year" disabled={busy}
                      onChange={(ev) => { const m = `${ev.target.value}-${month.slice(5)}`; setMonth(m); extract(file, plant, m); }}>
                {years.map((y) => <option key={y} value={y}>{y}</option>)}
              </select>
            </Field>
          </>
        )}
      </ContextBar>

      <Status status={status} />
      {overridden && (
        <Status status={{ type: 'info', text: `The file reads as ${detected.plant || '?'} ${monthLabel(detected.month) || '?'}; mapped as ${result.plant} ${monthLabel(result.month)} as you chose.` }} />
      )}

      {result && (
        <Section
          title={`${result.plant} · ${monthLabel(result.month)} · ${result.file}`}
          sub={`${chosen.length} of ${result.items.length} items will be saved · ${rows.length} lines read from the file`}
          actions={hidden > 0 || showAll ? (
            <label style={{ fontSize: 12.5, display: 'flex', gap: 6, alignItems: 'center' }}>
              <input type="checkbox" checked={showAll} onChange={(ev) => setShowAll(ev.target.checked)} />
              Show lines not mapped ({rows.filter((r) => !r.item && !r.selected).length})
            </label>
          ) : null}
        >
          <table className={e.table}>
            <thead>
              <tr>
                <th className={e.c} style={{ width: 36 }}>Save</th>
                <th>Line in the file</th>
                <th className={e.r}>File APP</th>
                <th>Production item</th>
                <th className={e.r}>DB APP</th>
                <th>Check</th>
                <th className={e.r} style={{ width: 120 }}>OP to save</th>
                <th className={e.r}>OP now</th>
              </tr>
            </thead>
            <tbody>
              {shown.map((r) => {
                const st = STATUS[r.status] || STATUS.unmatched;
                const dup = r.selected && dupItems.includes(r.item);
                return (
                  <tr key={r.id} style={r.selected ? undefined : { opacity: 0.6 }}>
                    <td className={e.c}>
                      <input type="checkbox" checked={r.selected} disabled={!r.item} aria-label={`Save ${r.item || r.label}`}
                             onChange={(ev) => update(r.id, { selected: ev.target.checked })} />
                    </td>
                    <td style={{ maxWidth: 280 }} title={r.label}>
                      {r.label || <span className={wb.muted}>(no label)</span>}
                      {r.scale !== 1 && <span className={wb.muted} style={{ fontSize: 11 }}> · tonnes ÷ 1000</span>}
                    </td>
                    <td className={e.r}>{num(r.app * (r.scale || 1))}</td>
                    <td>
                      <select className={wb.select} style={{ minWidth: 190, ...(dup ? { borderColor: 'var(--ui-danger)' } : {}) }}
                              value={r.item || ''} onChange={(ev) => chooseItem(r, ev.target.value)} aria-label={`Item for ${r.label}`}>
                        <option value="">— not saved —</option>
                        {result.items.map((i) => <option key={i.item_name} value={i.item_name}>{i.item_name}</option>)}
                      </select>
                    </td>
                    <td className={e.r}>{num(r.item ? appOf[r.item] : null)}</td>
                    <td><span className={`${wb.badge} ${st.cls}`} title={st.tip}>{dup ? 'chosen twice' : st.text}</span></td>
                    <td className={e.r}>
                      <input type="number" step="any" min="0" className={wb.input} style={{ textAlign: 'right' }}
                             value={r.opText} disabled={!r.item} aria-label={`OP for ${r.item || r.label}`}
                             onChange={(ev) => update(r.id, { opText: ev.target.value })} />
                    </td>
                    <td className={e.r}>{num(r.item ? currentOf[r.item] : null)}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </Section>
      )}
      {result && missing.length > 0 && (
        <p className={wb.muted} style={{ fontSize: 12 }}>
          Items with no line in this file: {missing.map((i) => i.item_name).join(', ')}. Enter them on the Operating Plan (OP) tab if needed.
        </p>
      )}
    </EntryPage>
  );
}

export default function OpPlanUploadForm() {
  return (
    <RequireEditor>
      <OpPlanUploadInner />
    </RequireEditor>
  );
}
