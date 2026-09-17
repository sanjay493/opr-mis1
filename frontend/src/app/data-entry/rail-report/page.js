'use client';

import RequireEditor from '@/components/RequireEditor';
import React, { useState, useEffect, useCallback } from 'react';
import GlobalNavbar from '@/components/GlobalNavbar';

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

function Notice({ type, text }) {
  if (!text) return null;
  const ok = type === 'success';
  return (
    <div style={{
      padding: '10px 16px', borderRadius: 6, margin: '14px 0', fontSize: 14,
      background: ok ? '#f0fdf4' : '#fef2f2', color: ok ? '#166534' : '#991b1b',
      border: `1px solid ${ok ? '#86efac' : '#fca5a5'}`,
    }}>{text}</div>
  );
}

const cellInput = {
  width: 110, padding: '5px 6px', border: '1px solid #dadce0', borderRadius: 4,
  textAlign: 'right', fontSize: 12.5,
};

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

  const TH = { padding: '8px 10px', fontSize: 12, fontWeight: 700, color: '#5f6368', background: '#f8f9fa', borderBottom: '1px solid #dadce0', textAlign: 'left' };
  const TD = { padding: '6px 10px', borderBottom: '1px solid #f1f3f4' };

  return (
    <div style={{ minHeight: '100vh', display: 'flex', flexDirection: 'column', background: '#fff' }}>
      <GlobalNavbar />
      <div style={{ flex: 1, maxWidth: 1100, margin: '0 auto', padding: '22px 20px', width: '100%', boxSizing: 'border-box' }}>
        <h2 style={{ fontSize: '1.6rem', fontWeight: 700, color: '#202124', margin: '0 0 4px' }}>
          Rail Production &amp; Dispatch Entry (Page 18.5)
        </h2>
        <span style={{ fontSize: 13, color: '#5f6368' }}>
          One financial year (Apr-Mar) at a time. For the FY that&rsquo;s currently open, enter the running
          Apr-&lt;report month&gt; cumulative &mdash; it will show on the report as &ldquo;Till &lt;Mon&gt;&rsquo;YY&rdquo;, not a full-year figure.
          R350HT Rails supplied can carry an optional note (e.g. &ldquo;9 Rakes&rdquo;).
        </span>

        <div style={{ display: 'flex', gap: 12, alignItems: 'center', flexWrap: 'wrap', margin: '18px 0', border: '1px solid #dadce0', borderRadius: 8, padding: '14px 18px' }}>
          <label style={{ fontSize: 13, fontWeight: 600, color: '#374151' }}>Financial Year</label>
          <select value={fy} onChange={(e) => setFy(e.target.value)}
            style={{ padding: '7px 10px', fontSize: 14, border: '1px solid #d1d5db', borderRadius: 4 }}>
            {FY_LIST.map((f) => <option key={f} value={f}>{f}</option>)}
          </select>
          <button onClick={save} disabled={saving || loading}
            style={{ marginLeft: 'auto', padding: '8px 22px', fontSize: 14, fontWeight: 700, background: !loading ? '#10b981' : '#9ca3af', color: '#fff', border: 'none', borderRadius: 6, cursor: !loading ? 'pointer' : 'not-allowed' }}>
            {saving ? 'Saving…' : 'Save All'}
          </button>
        </div>

        <Notice type={status?.type} text={status?.text} />

        {loading && <div style={{ padding: 40, textAlign: 'center', color: '#5f6368' }}>Loading…</div>}

        {!loading && (
          <>
            <div style={{ border: '1px solid #dadce0', borderRadius: 8, overflow: 'hidden' }}>
              <table style={{ borderCollapse: 'collapse', width: '100%' }}>
                <thead>
                  <tr>
                    <th style={TH}>Metric</th>
                    <th style={{ ...TH, textAlign: 'right' }}>Value ({fy})</th>
                    <th style={TH}>Note</th>
                  </tr>
                </thead>
                <tbody>
                  {rows.map((r, idx) => (
                    <tr key={r.metric}>
                      <td style={{ ...TD, fontWeight: 600 }}>{r.label}</td>
                      <td style={{ ...TD, textAlign: 'right' }}>
                        <input value={r.value} onChange={(e) => setRow(idx, { value: e.target.value })} style={cellInput} />
                      </td>
                      <td style={TD}>
                        <input value={r.note} onChange={(e) => setRow(idx, { note: e.target.value })}
                          placeholder={r.metric === 'r350ht_supplied' ? 'e.g. 9 Rakes' : ''}
                          style={{ width: 200, padding: '5px 6px', border: '1px solid #dadce0', borderRadius: 4, fontSize: 12.5 }} />
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            <div style={{ marginTop: 24 }}>
              <div style={{ fontSize: 14, fontWeight: 700, color: '#1e293b', marginBottom: 4 }}>Footer Remarks</div>
              <div style={{ fontSize: 12, color: '#5f6368', marginBottom: 8 }}>
                Standing footnotes shown under the table on every report — not tied to the FY selected above.
              </div>
              {notes.map((t, i) => (
                <div key={i} style={{ display: 'flex', gap: 8, marginBottom: 6 }}>
                  <input value={t} onChange={(e) => setNotes((prev) => prev.map((x, j) => (j === i ? e.target.value : x)))}
                    style={{ flex: 1, padding: '7px 10px', border: '1px solid #dadce0', borderRadius: 4, fontSize: 13 }} />
                  <button onClick={() => setNotes((prev) => prev.filter((_, j) => j !== i))}
                    style={{ padding: '5px 12px', border: 'none', borderRadius: 4, background: '#ef4444', color: '#fff', fontSize: 13, cursor: 'pointer' }}>Del</button>
                </div>
              ))}
              <button onClick={() => setNotes((prev) => [...prev, ''])}
                style={{ padding: '6px 16px', fontSize: 13, fontWeight: 600, background: '#6366f1', color: '#fff', border: 'none', borderRadius: 4, cursor: 'pointer' }}>+ Add Remark</button>
            </div>
          </>
        )}
      </div>
    </div>
  );
}

export default function RailReportEntryPage() {
  return (
    <RequireEditor>
      <RailReportEntryInner />
    </RequireEditor>
  );
}
