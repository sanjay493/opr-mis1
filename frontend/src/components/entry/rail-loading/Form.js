'use client';

import RequireEditor from '@/components/RequireEditor';
import React, { useState, useEffect, useCallback } from 'react';
import { EntryPage, ContextBar, Field, Status, Section, SaveButton, Loading, cellClass, entryStyles as es, wb } from '../EntryUI';

const API = process.env.NEXT_PUBLIC_API_URL || '';

const thisMonth = () => new Date().toISOString().slice(0, 7);

const s = (v) => (v === null || v === undefined ? '' : String(v));
function numOrNull(v) {
  const f = parseFloat(v);
  return Number.isNaN(f) ? null : f;
}
const round1 = (v) => Math.round(v * 10) / 10;

// Mirrors backend/rail_loading.py OTHERS: each "Others" row is its total less
// the named rows entered. The server works these out again on save; this is
// only so the form shows them while typing.
const OTHERS = {
  flux_ls_other: ['flux_limestone', ['flux_ls_kuteswar', 'flux_ls_nandini', 'flux_ls_rsmml', 'flux_ls_wonder']],
  flux_dol_other: ['flux_dolomite', ['flux_dol_hirri']],
  misc_other: ['misc_total', ['misc_pellets']],
};

const INDENT = { subitem: 28, item: 14 };

function RailLoadingEntryInner() {
  const [reportMonth, setReportMonth] = useState(thisMonth());
  const [rows, setRows] = useState([]);
  const [values, setValues] = useState({});
  const [egom, setEgom] = useState({ code: '', file: null });
  const [note, setNote] = useState({ text: '', title: '', lines: 3, lineMax: 120 });
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [dirty, setDirty] = useState(false);
  const [status, setStatus] = useState(null);

  const fill = (d) => {
    setEgom({ code: d.egom, file: d.egom_file });
    setNote({ text: d.note || '', title: d.note_title, lines: d.note_lines, lineMax: d.note_line_max });
    setRows(d.rows);
    setValues(Object.fromEntries(d.rows.map((r) => [r.code, s(r.value)])));
    setDirty(false);
  };

  const load = useCallback(async (month) => {
    setLoading(true);
    setStatus(null);
    try {
      const res = await fetch(`${API}/api/rail-loading?month=${encodeURIComponent(month)}`);
      if (!res.ok) throw new Error(await res.text());
      fill(await res.json());
    } catch (err) {
      setStatus({ type: 'error', text: `Load failed: ${err.message}` });
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(reportMonth); }, [reportMonth, load]);

  // EGOM is typed as reported; where the mines' rake file covers the month,
  // its OGOM + JGOM is shown beside it when the two differ.
  const egomTyped = numOrNull(values[egom.code]);
  const egomDiffers = egom.file !== null && egomTyped !== null && egomTyped !== egom.file;

  const noteLines = note.text.split('\n').map((l) => l.trim()).filter(Boolean);
  const noteTooBig = noteLines.length > note.lines || noteLines.some((l) => l.length > note.lineMax);

  const derived = (code) => {
    const rule = OTHERS[code];
    if (!rule) return null;
    const total = numOrNull(values[rule[0]]);
    const named = rule[1].map((c) => numOrNull(values[c])).filter((v) => v !== null);
    return total === null || named.length === 0 ? null : round1(total - named.reduce((a, b) => a + b, 0));
  };

  const set = (code, v) => {
    setValues((prev) => ({ ...prev, [code]: v }));
    setDirty(true);
  };

  const save = async () => {
    if (noteTooBig) {
      setStatus({ type: 'error', text: `The note: up to ${note.lines} lines of ${note.lineMax} characters each.` });
      return;
    }
    const bad = rows.find((r) => values[r.code] !== undefined && values[r.code].trim() !== '' && !/^\d+(\.\d+)?$/.test(values[r.code].trim()));
    if (bad) {
      setStatus({ type: 'error', text: `${bad.label}: enter a number of rakes, 0 or more.` });
      return;
    }
    setSaving(true);
    setStatus(null);
    try {
      const body = {};
      rows.forEach((r) => {
        if (r.kind === 'group' || r.kind === 'sub' || r.derived || r.from_file) return;
        body[r.code] = numOrNull(values[r.code]);
      });
      const res = await fetch(`${API}/api/rail-loading`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ report_month: reportMonth, values: body, note: note.text }),
      });
      if (!res.ok) {
        let text = await res.text();
        try { text = JSON.parse(text).detail || text; } catch { /* plain text */ }
        throw new Error(text);
      }
      fill(await res.json());
      setStatus({ type: 'success', text: 'Saved.' });
    } catch (err) {
      setStatus({ type: 'error', text: `Save failed: ${err.message}` });
    } finally {
      setSaving(false);
    }
  };

  return (
    <EntryPage
      maxWidth={760}
      title="Monthly Rail Loading (Rail Logistics, page 40.05)"
      description={<>
        Rakes loaded in one month, as in the Rail Movement Cell&rsquo;s monthly highlights. Totals are entered as
        reported, not added up here. OGOM and JGOM come from the mines&rsquo; rake file (Data Entry › Uploads) for
        every month it covers; each &ldquo;Others&rdquo; row is its total less the rows named above it. A blank cell
        prints as &ldquo;–&rdquo;.
      </>}
    >
      <ContextBar actions={<SaveButton dirty={dirty && !loading} saving={saving} onClick={save}>Save</SaveButton>}>
        <Field label="Report month" htmlFor="rl-month">
          <input id="rl-month" type="month" className={es.control} value={reportMonth} onChange={(e) => setReportMonth(e.target.value)} />
        </Field>
      </ContextBar>

      <Status status={status} />

      {loading && <Loading />}

      {!loading && (
        <Section title={`Rakes loaded (${reportMonth})`}>
          <table className={es.table}>
            <thead>
              <tr>
                <th>Item</th>
                <th className={es.r}>Rakes</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => {
                if (r.kind === 'group') {
                  return <tr key={r.code} className={es.subRow}><td colSpan={2}>{r.label}</td></tr>;
                }
                if (r.kind === 'sub') {
                  return <tr key={r.code}><td colSpan={2} style={{ paddingLeft: INDENT.item, fontWeight: 700 }}>{r.label}</td></tr>;
                }
                const auto = r.derived || r.from_file;
                const shown = r.derived ? s(derived(r.code)) : values[r.code] ?? '';
                const strong = r.kind === 'total' || r.kind === 'grand';
                return (
                  <tr key={r.code}>
                    <td className={es.itemCell} style={{ paddingLeft: INDENT[r.kind] || 6, fontWeight: strong ? 700 : undefined }}>
                      {r.label}
                      {auto && <span style={{ fontStyle: 'italic', fontWeight: 400, color: 'var(--ui-text-secondary)', fontSize: 12 }}> {r.from_file ? '(from the mines file)' : '(worked out)'}</span>}
                      {r.code === egom.code && egomDiffers && (
                        <div style={{ fontWeight: 400, color: 'var(--ui-text-secondary)', fontSize: 12 }}>
                          The mines file has {egom.file} rakes for OGOM + JGOM.
                        </div>
                      )}
                    </td>
                    <td className={es.r}>
                      <input value={shown} onChange={(e) => set(r.code, e.target.value)} aria-label={r.label}
                             readOnly={auto} tabIndex={auto ? -1 : undefined} inputMode="decimal"
                             className={cellClass({ filled: shown !== '' })}
                             style={{ width: 120, ...(auto ? { background: 'transparent', fontStyle: 'italic' } : {}) }} />
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </Section>
      )}

      {!loading && (
        <Section title={note.title} sub="printed under the table, one bullet per line">
          <textarea className={wb.textarea} style={{ minHeight: 80 }} rows={note.lines} value={note.text}
                    aria-label={note.title}
                    onChange={(e) => { setNote((n) => ({ ...n, text: e.target.value })); setDirty(true); }} />
          <div style={{ fontSize: 12, marginTop: 4, color: noteTooBig ? 'var(--ui-danger, #b42318)' : 'var(--ui-text-secondary)' }}>
            Up to {note.lines} lines of {note.lineMax} characters each; the page has room for no more.
          </div>
        </Section>
      )}
    </EntryPage>
  );
}

export default function RailLoadingEntryPage() {
  return (
    <RequireEditor>
      <RailLoadingEntryInner />
    </RequireEditor>
  );
}
