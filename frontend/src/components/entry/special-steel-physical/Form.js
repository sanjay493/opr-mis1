'use client';

import RequireEditor from '@/components/RequireEditor';
import React, { useState, useEffect, useCallback } from 'react';
import { EntryPage, ContextBar, Field, Status, Section, SaveButton, Loading, cellClass, entryStyles as es, wb } from '../EntryUI';

const API = process.env.NEXT_PUBLIC_API_URL || '';
const FY_LIST = ['2025-26', '2026-27', '2027-28', '2028-29'];

function numOrNull(v) {
  const f = parseFloat(v);
  return Number.isNaN(f) ? null : f;
}
const s = (v) => (v === null || v === undefined ? '' : String(v));

function SpecialSteelPhysicalEntryInner() {
  const [fy, setFy] = useState('2026-27');
  const [meta, setMeta] = useState(null); // { financial_year, prev_fy, history_fys, rows[], notes[] }
  const [rows, setRows] = useState([]);   // editable copy, keyed by plant|series
  const [notes, setNotes] = useState([]);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [status, setStatus] = useState(null);

  const load = useCallback(async (targetFy) => {
    setLoading(true);
    setStatus(null);
    try {
      const res = await fetch(`${API}/api/special-steel-physical/grid?financial_year=${encodeURIComponent(targetFy)}`);
      if (!res.ok) throw new Error(await res.text());
      const d = await res.json();
      setMeta(d);
      setRows(d.rows.map((r) => ({
        plant: r.plant, series: r.series, series_label: r.series_label,
        capacity_kt: s(r.capacity_kt), best_actual_kt: s(r.best_actual_kt),
        best_year: s(r.best_year), remark: s(r.remark),
        history: Object.fromEntries((d.history_fys).map((f) => [f, s(r.history[f])])),
        prev_app_kt: s(r.prev_app_kt), prev_actual_kt: s(r.prev_actual_kt), abp_kt: s(r.abp_kt),
      })));
      setNotes((d.notes || []).map((n) => n.note_text));
    } catch (err) {
      setStatus({ type: 'error', text: `Load failed: ${err.message}` });
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(fy); }, [fy, load]);

  const set = (idx, patch) => setRows((prev) => prev.map((r, i) => (i === idx ? { ...r, ...patch } : r)));
  const setHist = (idx, f, v) => setRows((prev) => prev.map((r, i) => (i === idx ? { ...r, history: { ...r.history, [f]: v } } : r)));

  const save = async () => {
    setSaving(true);
    setStatus(null);
    try {
      const prevFy = meta.prev_fy;
      const metaOut = rows.map((r) => ({
        plant: r.plant, series: r.series,
        capacity_kt: numOrNull(r.capacity_kt), best_actual_kt: numOrNull(r.best_actual_kt),
        best_year: r.best_year, remark: r.remark,
      }));
      const perfOut = [];
      rows.forEach((r) => {
        meta.history_fys.forEach((f) => {
          perfOut.push({ financial_year: f, plant: r.plant, series: r.series, metric: 'actual', value_kt: numOrNull(r.history[f]) });
        });
        perfOut.push({ financial_year: prevFy, plant: r.plant, series: r.series, metric: 'plan', value_kt: numOrNull(r.prev_app_kt) });
        perfOut.push({ financial_year: prevFy, plant: r.plant, series: r.series, metric: 'actual', value_kt: numOrNull(r.prev_actual_kt) });
        perfOut.push({ financial_year: fy, plant: r.plant, series: r.series, metric: 'plan', value_kt: numOrNull(r.abp_kt) });
      });
      const notesOut = notes.map((t, i) => ({ sort_order: i + 1, note_text: t })).filter((n) => n.note_text.trim());
      const res = await fetch(`${API}/api/special-steel-physical/grid`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ financial_year: fy, prev_fy: prevFy, meta: metaOut, perf: perfOut, notes: notesOut }),
      });
      if (!res.ok) throw new Error(await res.text());
      setStatus({ type: 'success', text: 'Saved.' });
      await load(fy);
    } catch (err) {
      setStatus({ type: 'error', text: `Save failed: ${err.message}` });
    } finally {
      setSaving(false);
    }
  };

  const num = cellClass();
  const numW = { width: 88 };

  return (
    <EntryPage
      maxWidth={1700}
      title="Special Steel Plants — Physical Performance Entry"
      description={<>
        Multi-year history grid (ASP / SSP / VISP), values in ’000 T. Seeded from the source workbook —
        edit to correct or extend. “APP / Actual” are for the previous FY, “ABP” for the selected FY.
      </>}
    >
      <ContextBar actions={<SaveButton dirty={!!meta} saving={saving} onClick={save}>Save All</SaveButton>}>
        <Field label="Financial year" htmlFor="ssp-phys-fy">
          <select id="ssp-phys-fy" className={es.control} value={fy} onChange={(e) => setFy(e.target.value)}>
            {FY_LIST.map((f) => <option key={f} value={f}>{f}</option>)}
          </select>
        </Field>
      </ContextBar>

      <Status status={status} />

      {loading && <Loading />}

      {meta && !loading && (
        <>
          <Section title={`Physical performance — FY ${fy}`} sub="Values in ’000 T">
            <table className={es.table}>
              <thead>
                <tr>
                  <th>Plant</th>
                  <th>Item</th>
                  <th className={es.c}>Capacity</th>
                  <th className={es.c}>Best Actual</th>
                  <th className={es.c}>Best Year</th>
                  {meta.history_fys.map((f) => <th key={f} className={es.c}>{f}</th>)}
                  <th className={es.c}>{meta.prev_fy} APP</th>
                  <th className={es.c}>{meta.prev_fy} Actual</th>
                  <th className={es.c}>{fy} ABP</th>
                  <th>Remark</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((r, idx) => (
                  <tr key={`${r.plant}-${r.series}`}>
                    <td className={es.itemCell}>{r.plant}</td>
                    <td className={es.itemCell}>{r.series_label}</td>
                    <td className={es.c}><input value={r.capacity_kt} onChange={(e) => set(idx, { capacity_kt: e.target.value })} className={num} style={numW} /></td>
                    <td className={es.c}><input value={r.best_actual_kt} onChange={(e) => set(idx, { best_actual_kt: e.target.value })} className={num} style={numW} /></td>
                    <td className={es.c}><input value={r.best_year} onChange={(e) => set(idx, { best_year: e.target.value })} className={num} style={{ width: 84, textAlign: 'center' }} /></td>
                    {meta.history_fys.map((f) => (
                      <td key={f} className={es.c}><input value={r.history[f]} onChange={(e) => setHist(idx, f, e.target.value)} className={num} style={numW} /></td>
                    ))}
                    <td className={es.c}><input value={r.prev_app_kt} onChange={(e) => set(idx, { prev_app_kt: e.target.value })} className={num} style={numW} /></td>
                    <td className={es.c}><input value={r.prev_actual_kt} onChange={(e) => set(idx, { prev_actual_kt: e.target.value })} className={num} style={numW} /></td>
                    <td className={es.c}><input value={r.abp_kt} onChange={(e) => set(idx, { abp_kt: e.target.value })} className={num} style={numW} /></td>
                    <td><input value={r.remark} onChange={(e) => set(idx, { remark: e.target.value })} className={cellClass({ text: true })} style={{ minWidth: 200 }} /></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </Section>

          <Section title={`Footnotes (${fy})`} flush={false}>
            {notes.map((t, i) => (
              <div key={i} style={{ display: 'flex', gap: 8, marginBottom: 8 }}>
                <input value={t} aria-label={`Footnote ${i + 1}`} className={wb.input}
                       onChange={(e) => setNotes((prev) => prev.map((x, j) => (j === i ? e.target.value : x)))} />
                <button type="button" className={`${wb.btn} ${wb.btnDanger}`}
                        onClick={() => setNotes((prev) => prev.filter((_, j) => j !== i))}>Delete</button>
              </div>
            ))}
            <button type="button" className={wb.btn} onClick={() => setNotes((prev) => [...prev, ''])}>+ Add Note</button>
          </Section>
        </>
      )}
    </EntryPage>
  );
}

export default function SpecialSteelPhysicalEntryPage() {
  return (
    <RequireEditor>
      <SpecialSteelPhysicalEntryInner />
    </RequireEditor>
  );
}
