'use client';

import RequireEditor from '@/components/RequireEditor';
import React, { useState, useEffect, useCallback } from 'react';
import { EntryPage, ContextBar, Field, Status, Section, SaveButton, Loading, cellClass, entryStyles as es, wb } from '../EntryUI';

const API = process.env.NEXT_PUBLIC_API_URL || '';

// BSP/DSP/RSP/BSL/ISP order, matching backend/page_major_unit_records.py's
// ISP_PLANTS — DSP has a registry (given directly, no source workbook) but
// no backfilled Daily figures, so its rows load with blank value/date,
// filled in here unit-by-unit going forward.
const PLANTS = [
  { code: 'BSP', name: 'Bhilai Steel Plant' },
  { code: 'DSP', name: 'Durgapur Steel Plant' },
  { code: 'RSP', name: 'Rourkela Steel Plant' },
  { code: 'BSL', name: 'Bokaro Steel Plant' },
  { code: 'ISP', name: 'IISCO Steel Plant' },
];

const s = (v) => (v === null || v === undefined ? '' : String(v));
function numOrNull(v) {
  const t = String(v).trim();
  if (t === '') return null;
  const f = parseFloat(t);
  return Number.isNaN(f) ? null : f;
}

function MajorUnitDailyEntryInner() {
  const [plant, setPlant] = useState('BSP');
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [status, setStatus] = useState(null);

  const load = useCallback(async (code) => {
    setLoading(true);
    setStatus(null);
    try {
      const res = await fetch(`${API}/api/major-unit-daily/${code}`);
      if (!res.ok) throw new Error(await res.text());
      const d = await res.json();
      setRows(d.rows.map((r) => ({
        unit_label: r.unit_label, unit_of_measure: r.unit_of_measure,
        value: s(r.value), record_date: s(r.record_date), remarks: s(r.remarks),
      })));
    } catch (err) {
      setStatus({ type: 'error', text: `Load failed: ${err.message}` });
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(plant); }, [plant, load]);

  const set = (idx, patch) => setRows((prev) => prev.map((r, i) => (i === idx ? { ...r, ...patch } : r)));

  const save = async () => {
    setSaving(true);
    setStatus(null);
    try {
      const rowsOut = rows.map((r) => ({
        unit_label: r.unit_label, value: numOrNull(r.value),
        record_date: r.record_date.trim() || null, remarks: r.remarks.trim() || null,
      }));
      const res = await fetch(`${API}/api/major-unit-daily/${plant}`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ rows: rowsOut }),
      });
      if (!res.ok) throw new Error(await res.text());
      setStatus({ type: 'success', text: 'Saved.' });
      await load(plant);
    } catch (err) {
      setStatus({ type: 'error', text: `Save failed: ${err.message}` });
    } finally {
      setSaving(false);
    }
  };

  return (
    <EntryPage
      maxWidth={1100}
      title="5 ISPs Major Units — Daily Best Record Entry"
      description={<>
        Best-ever single-day production figure per major unit, with the date it was achieved — feeds
        Annexure-3 of the report. Annual/Monthly bests aren&apos;t entered here; they&apos;re computed
        automatically from the plant&apos;s monthly production data.
      </>}
    >
      <ContextBar actions={<SaveButton dirty={!loading && rows.length > 0} saving={saving} onClick={save}>Save All</SaveButton>}>
        <Field label="Plant" htmlFor="mud-plant">
          <select id="mud-plant" className={es.control} value={plant} onChange={(e) => setPlant(e.target.value)}>
            {PLANTS.map((p) => <option key={p.code} value={p.code}>{p.name}</option>)}
          </select>
        </Field>
      </ContextBar>

      <Status status={status} />

      {loading && <Loading />}

      {!loading && rows.length === 0 && (
        <div className={wb.empty}>No major-unit registry for {plant} yet.</div>
      )}

      {!loading && rows.length > 0 && (
        <Section title={`Daily best records — ${plant}`}>
          <table className={es.table}>
            <thead>
              <tr>
                <th>Unit</th>
                <th>Unit of Measure</th>
                <th className={es.r}>Best Value</th>
                <th>Date (YYYY-MM-DD)</th>
                <th>Remarks</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r, idx) => (
                <tr key={r.unit_label}>
                  <td className={es.itemCell}>{r.unit_label}</td>
                  <td style={{ color: 'var(--ui-text-secondary)' }}>{r.unit_of_measure}</td>
                  <td className={es.r}>
                    <input value={r.value} onChange={(e) => set(idx, { value: e.target.value })} aria-label={`${r.unit_label} best value`}
                           className={cellClass({ filled: r.value !== '' })} style={{ width: 110 }} />
                  </td>
                  <td>
                    <input value={r.record_date} placeholder="YYYY-MM-DD" onChange={(e) => set(idx, { record_date: e.target.value })}
                           aria-label={`${r.unit_label} date`} className={cellClass()} style={{ width: 130, textAlign: 'left' }} />
                  </td>
                  <td>
                    <input value={r.remarks} onChange={(e) => set(idx, { remarks: e.target.value })} aria-label={`${r.unit_label} remarks`}
                           className={cellClass({ text: true })} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </Section>
      )}
    </EntryPage>
  );
}

export default function MajorUnitDailyEntryPage() {
  return (
    <RequireEditor>
      <MajorUnitDailyEntryInner />
    </RequireEditor>
  );
}
