'use client';

import RequireEditor from '@/components/RequireEditor';
import React, { useState, useEffect, useCallback } from 'react';
import { EntryPage, ContextBar, Status, Section, SaveButton, Loading, cellClass, entryStyles as es } from '../EntryUI';

const API = process.env.NEXT_PUBLIC_API_URL || '';

// Mirrors backend/mining_leases.py SPAN_COLS: these cells can be merged down
// over several leases, as in the source sheet.
const SPAN_COLS = ['grp', 'mine', 'state', 'lease', 'mineral', 'area', 'reserves', 'status'];
const LABELS = { s_no: 'S.No.', grp: 'Category', mine: 'Name of Mines', state: 'State', lease: 'Name of Lease', mineral: 'Mineral',
  area: 'Area in Ha', reserves: 'Reserves & Resource (MT)', status: 'Current Status' };
const WIDTHS = { s_no: 56, grp: 120, mine: 170, state: 110, lease: 170, mineral: 110, area: 110, reserves: 130, status: 220 };

const s = (v) => (v === null || v === undefined ? '' : String(v));
const noneCovered = () => Object.fromEntries(SPAN_COLS.map((c) => [c, false]));
const emptyRow = () => ({ s_no: '', grp: '', mine: '', state: '', lease: '', mineral: '', area: '', reserves: '', status: '', covered: noneCovered() });

// Stored rows carry <col>_span (1 own row, N merged down, 0 covered by the cell
// above); the form keeps "covered by the cell above" flags and derives spans.
function fromServer(rows) {
  return rows.map((r) => ({
    ...Object.fromEntries(['s_no', ...SPAN_COLS].map((c) => [c, s(r[c])])),
    covered: Object.fromEntries(SPAN_COLS.map((c) => [c, Number(r[`${c}_span`]) === 0])),
  }));
}

function spanAt(rows, i, col) {
  if (rows[i].covered[col]) return 0;
  let n = 1;
  while (i + n < rows.length && rows[i + n].covered[col]) n += 1;
  return n;
}

function toServer(rows) {
  return rows.map((r, i) => {
    const out = { s_no: r.s_no };
    SPAN_COLS.forEach((c) => {
      out[c] = r.covered[c] ? '' : r[c];
      out[`${c}_span`] = spanAt(rows, i, c);
    });
    return out;
  });
}

// The first row has nothing above it to be covered by.
const fix = (rows) => rows.map((r, i) => (i === 0 ? { ...r, covered: noneCovered() } : r));

function MiningLeasesInner() {
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [dirty, setDirty] = useState(false);
  const [status, setStatus] = useState(null);

  const load = useCallback(async () => {
    setLoading(true);
    setStatus(null);
    try {
      const res = await fetch(`${API}/api/mining-leases`);
      if (!res.ok) throw new Error(await res.text());
      setRows(fromServer((await res.json()).rows));
      setDirty(false);
    } catch (err) {
      setStatus({ type: 'error', text: `Load failed: ${err.message}` });
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const change = (fn) => { setRows((prev) => fix(fn(prev))); setDirty(true); };
  const setCell = (i, col, v) => change((p) => p.map((r, k) => (k === i ? { ...r, [col]: v } : r)));

  // Make the cell at row i cover exactly n rows: the n-1 rows below are covered
  // (and blanked), and the row after them starts its own cell.
  const setSpan = (i, col, raw) => {
    change((p) => {
      const n = Math.max(1, Math.min(p.length - i, parseInt(raw, 10) || 1));
      return p.map((r, k) => {
        if (k <= i || k > i + n) return r;
        if (k === i + n) return { ...r, covered: { ...r.covered, [col]: false } };
        return { ...r, [col]: '', covered: { ...r.covered, [col]: true } };
      });
    });
  };

  const addBelow = (i) => change((p) => [...p.slice(0, i + 1), emptyRow(), ...p.slice(i + 1)]);

  // A deleted row that headed a merge hands the cell on: the next covered row starts its own.
  const remove = (i) => change((p) => p.filter((_r, k) => k !== i).map((r, k) => {
    if (k !== i) return r;
    const covered = { ...r.covered };
    SPAN_COLS.forEach((c) => { if (!p[i].covered[c] && r.covered[c]) covered[c] = false; });
    return { ...r, covered };
  }));

  // Moving a row resets the merges of the rows it touches, so no cell ends up
  // merged to the wrong lease.
  const move = (i, d) => {
    const j = i + d;
    if (j < 0 || j >= rows.length) return;
    change((p) => {
      const q = [...p];
      [q[i], q[j]] = [q[j], q[i]];
      const lo = Math.min(i, j);
      return q.map((r, k) => (k >= lo && k <= lo + 2 ? { ...r, covered: noneCovered() } : r));
    });
  };

  const save = async () => {
    setSaving(true);
    setStatus(null);
    try {
      const res = await fetch(`${API}/api/mining-leases`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ rows: toServer(rows) }),
      });
      if (!res.ok) {
        let text = await res.text();
        try { text = JSON.parse(text).detail || text; } catch { /* plain text */ }
        throw new Error(text);
      }
      setRows(fromServer((await res.json()).rows));
      setDirty(false);
      setStatus({ type: 'success', text: 'Saved.' });
    } catch (err) {
      setStatus({ type: 'error', text: `Save failed: ${err.message}` });
    } finally {
      setSaving(false);
    }
  };

  const cols = ['s_no', ...SPAN_COLS];
  return (
    <EntryPage
      maxWidth={1500}
      title="Mining Leases (Annexure-1: SAIL Mining at a Glance)"
      description={<>
        One row per lease, in print order. Under a cell, &ldquo;spans&rdquo; is how many rows it is merged down over
        (1 = its own row); the rows it covers go blank and show &uarr;. Area and reserves are free text
        (&ldquo;Un-Explored&rdquo;, &ldquo;208( Broken area- 11MT)&rdquo;). Moving a row resets the merges around it.
      </>}
    >
      <ContextBar actions={<SaveButton dirty={dirty && !loading} saving={saving} onClick={save}>Save</SaveButton>}>
        <button type="button" className={es.control} onClick={() => change((p) => [...p, emptyRow()])}>+ Add lease at end</button>
      </ContextBar>

      <Status status={status} />
      {loading && <Loading />}

      {!loading && (
        <Section title={`Leases (${rows.length})`}>
          <div style={{ overflowX: 'auto' }}>
            <table className={es.table}>
              <thead>
                <tr>{cols.map((c) => <th key={c} style={{ minWidth: WIDTHS[c] }}>{LABELS[c]}</th>)}<th>Row</th></tr>
              </thead>
              <tbody>
                {rows.map((r, i) => (
                  <tr key={i}>
                    {cols.map((c) => {
                      if (c === 's_no') {
                        return (
                          <td key={c}>
                            <input value={r.s_no} onChange={(e) => setCell(i, 's_no', e.target.value)} aria-label={`Row ${i + 1} S.No.`}
                                   className={cellClass({ filled: r.s_no !== '' })} style={{ width: 48 }} />
                          </td>
                        );
                      }
                      if (r.covered[c]) {
                        return <td key={c} style={{ textAlign: 'center', color: 'var(--ui-text-secondary)' }} title="Merged with the cell above">&uarr;</td>;
                      }
                      return (
                        <td key={c}>
                          <input value={r[c]} onChange={(e) => setCell(i, c, e.target.value)} aria-label={`Row ${i + 1} ${LABELS[c]}`}
                                 className={cellClass({ filled: r[c] !== '' })} style={{ width: '100%', minWidth: WIDTHS[c] - 20 }} />
                          <label style={{ fontSize: 11, color: 'var(--ui-text-secondary)' }}>
                            spans{' '}
                            <input type="number" min={1} max={rows.length - i} value={spanAt(rows, i, c)}
                                   onChange={(e) => setSpan(i, c, e.target.value)} aria-label={`Row ${i + 1} ${LABELS[c]} spans`}
                                   style={{ width: 44 }} />
                          </label>
                        </td>
                      );
                    })}
                    <td style={{ whiteSpace: 'nowrap' }}>
                      <button type="button" onClick={() => move(i, -1)} disabled={i === 0} aria-label={`Move row ${i + 1} up`}>↑</button>{' '}
                      <button type="button" onClick={() => move(i, 1)} disabled={i === rows.length - 1} aria-label={`Move row ${i + 1} down`}>↓</button>{' '}
                      <button type="button" onClick={() => addBelow(i)} aria-label={`Add a row below row ${i + 1}`}>+</button>{' '}
                      <button type="button" onClick={() => remove(i)} aria-label={`Delete row ${i + 1}`}>✕</button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Section>
      )}
    </EntryPage>
  );
}

export default function MiningLeasesEntryPage() {
  return (
    <RequireEditor>
      <MiningLeasesInner />
    </RequireEditor>
  );
}
