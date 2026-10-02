'use client';

import RequireEditor from '@/components/RequireEditor';
import React, { useState, useEffect, useCallback } from 'react';
import { EntryPage, ContextBar, Field, Status, Section, SaveButton, Loading, cellClass, entryStyles as es, wb } from '../EntryUI';

const API = process.env.NEXT_PUBLIC_API_URL || '';

// First FY column on the report (page_rail_report.RAIL_HISTORY_START_FY_YEAR)
// through 2 FYs ahead of the current one, so next year's entry is always
// available a year early.
const CURRENT_YEAR = new Date().getFullYear();
const FY_LIST = [];
for (let y = 2015; y <= CURRENT_YEAR + 2; y++) {
  FY_LIST.push(`${y}-${String((y + 1) % 100).padStart(2, '0')}`);
}

const s = (v) => (v === null || v === undefined ? '' : String(v));
function numOrNull(v) {
  const f = parseFloat(v);
  return Number.isNaN(f) ? null : f;
}

function RailReportEntryInner() {
  const [fy, setFy] = useState(FY_LIST[FY_LIST.length - 3]);
  const [rows, setRows] = useState([]);
  const [notes, setNotes] = useState([]);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [status, setStatus] = useState(null);

  const load = useCallback(async (targetFy) => {
    setLoading(true);
    setStatus(null);
    try {
      const res = await fetch(`${API}/api/rail-report/grid?financial_year=${encodeURIComponent(targetFy)}`);
      if (!res.ok) throw new Error(await res.text());
      const d = await res.json();
      setRows(d.rows.map((r) => ({ metric: r.metric, label: r.label, value: s(r.value), note: s(r.note) })));
      setNotes((d.notes || []).map((n) => n.note_text));
    } catch (err) {
      setStatus({ type: 'error', text: `Load failed: ${err.message}` });
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(fy); }, [fy, load]);

  const setRow = (idx, patch) => setRows((prev) => prev.map((r, i) => (i === idx ? { ...r, ...patch } : r)));

  const save = async () => {
    setSaving(true);
    setStatus(null);
    try {
      const rowsOut = rows.map((r) => ({ metric: r.metric, value: numOrNull(r.value), note: r.note }));
      const notesOut = notes.map((t, i) => ({ sort_order: i + 1, note_text: t })).filter((n) => n.note_text.trim());
      const res = await fetch(`${API}/api/rail-report/grid`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ financial_year: fy, rows: rowsOut, notes: notesOut }),
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

  return (
    <EntryPage
      maxWidth={1100}
      title="Rail Production & Dispatch Entry (Page 18.5)"
      description={<>
        One financial year (Apr-Mar) at a time. For the FY that&rsquo;s currently open, enter the running
        Apr-&lt;report month&gt; cumulative &mdash; it will show on the report as &ldquo;Till &lt;Mon&gt;&rsquo;YY&rdquo;, not a full-year figure.
        R350HT Rails supplied can carry an optional note (e.g. &ldquo;9 Rakes&rdquo;).
      </>}
    >
      <ContextBar actions={<SaveButton dirty={!loading} saving={saving} onClick={save}>Save All</SaveButton>}>
        <Field label="Financial year" htmlFor="rail-fy">
          <select id="rail-fy" className={es.control} value={fy} onChange={(e) => setFy(e.target.value)}>
            {FY_LIST.map((f) => <option key={f} value={f}>{f}</option>)}
          </select>
        </Field>
      </ContextBar>

      <Status status={status} />

      {loading && <Loading />}

      {!loading && (
        <>
          <Section title={`Rail production & dispatch — FY ${fy}`}>
            <table className={es.table}>
              <thead>
                <tr>
                  <th>Metric</th>
                  <th className={es.r}>Value ({fy})</th>
                  <th>Note</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((r, idx) => (
                  <tr key={r.metric}>
                    <td className={es.itemCell}>{r.label}</td>
                    <td className={es.r}>
                      <input value={r.value} onChange={(e) => setRow(idx, { value: e.target.value })} aria-label={r.label}
                             className={cellClass({ filled: r.value !== '' })} style={{ width: 120 }} />
                    </td>
                    <td>
                      <input value={r.note} onChange={(e) => setRow(idx, { note: e.target.value })} aria-label={`${r.label} note`}
                             placeholder={r.metric === 'r350ht_supplied' ? 'e.g. 9 Rakes' : ''}
                             className={cellClass({ text: true })} style={{ width: 220 }} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </Section>

          <Section title="Footer Remarks" sub="Standing footnotes shown under the table on every report — not tied to the FY selected above." flush={false}>
            {notes.map((t, i) => (
              <div key={i} style={{ display: 'flex', gap: 8, marginBottom: 8 }}>
                <input value={t} aria-label={`Remark ${i + 1}`} className={wb.input}
                       onChange={(e) => setNotes((prev) => prev.map((x, j) => (j === i ? e.target.value : x)))} />
                <button type="button" className={`${wb.btn} ${wb.btnDanger}`}
                        onClick={() => setNotes((prev) => prev.filter((_, j) => j !== i))}>Delete</button>
              </div>
            ))}
            <button type="button" className={wb.btn} onClick={() => setNotes((prev) => [...prev, ''])}>+ Add Remark</button>
          </Section>
        </>
      )}
    </EntryPage>
  );
}

export default function RailReportEntryPage() {
  return (
    <RequireEditor>
      <RailReportEntryInner />
    </RequireEditor>
  );
}
