'use client';

import RequireEditor from '@/components/RequireEditor';

import React, { useCallback, useEffect, useState } from 'react';
import { EntryPage, ContextBar, Field, entryStyles as es, wb } from '../EntryUI';
import { API_BASE_URL } from '@/providers/AuthProvider';

// Structured data-entry form for the two "Ready Reckoner" tables (Unit-wise
// Capacity / Product Mix) per plant — see backend/page_ready_reckoner.py
// and db.py's ready_reckoner_pages table. The process-flow diagram itself
// is still only editable in the /report live preview (ReadyReckonerTemplate
// .js "Replace diagram" control), since that's a file upload, not a table
// this form covers.
//
// Per direct instruction, 2026-09-21: no HTML/markup/style stored in the
// DB — every field here is a plain text input/textarea/checkbox bound to
// React state (capacity_rows / product_mix_headers / product_mix_rows /
// product_mix_caption), so there is no way to type or paste formatting
// into a cell at all. Coloring/bold-total styling is applied purely at
// display time (here, in ReadyReckonerTemplate.js, and in the PDF
// template) from that same plain data.

function Notice({ type, text }) {
  if (!text) return null;
  return (
    <div role={type === 'success' ? 'status' : 'alert'}
         className={`${wb.alert} ${type === 'success' ? wb.alertSuccess : wb.alertError}`}>
      {text}
    </div>
  );
}

// Styled to the shared workbench look (--ui-* tokens, see styles/wb.module.css)
const S = {
  input: {
    width: '100%', border: '1px solid var(--ui-border)', borderRadius: 4, padding: '6px 8px',
    font: '13px var(--ui-font)', color: 'var(--ui-text)', boxSizing: 'border-box',
  },
  textarea: {
    width: '100%', border: '1px solid var(--ui-border)', borderRadius: 4, padding: '6px 8px',
    font: '13px var(--ui-font)', color: 'var(--ui-text)', boxSizing: 'border-box', resize: 'vertical', minHeight: 44,
  },
  th: {
    padding: '8px 10px', textAlign: 'left', fontSize: 10.5, fontWeight: 700, letterSpacing: '.05em', textTransform: 'uppercase',
    color: 'var(--ui-text-secondary)', background: 'var(--ui-bg-subtle)', borderBottom: '1px solid var(--ui-border)',
  },
  td: { padding: '6px 10px', verticalAlign: 'top', borderBottom: '1px solid var(--ui-border-subtle)' },
  addBtn: {
    padding: '7px 14px', font: '600 13px var(--ui-font)',
    background: 'var(--ui-surface)', color: 'var(--ui-primary)', border: '1px dashed var(--ui-primary)', borderRadius: 4, cursor: 'pointer',
  },
  delBtn: {
    width: 28, height: 28, lineHeight: '26px', textAlign: 'center', padding: 0, fontSize: 14, fontWeight: 700,
    background: 'none', color: 'var(--ui-text-tertiary)', border: 'none', borderRadius: 4, cursor: 'pointer',
  },
  saveBtn: (saving) => ({
    padding: '8px 16px', font: '600 13px var(--ui-font)',
    background: 'var(--ui-success)', color: '#fff', border: '1px solid var(--ui-success)', borderRadius: 4,
    opacity: saving ? 0.6 : 1, cursor: saving ? 'not-allowed' : 'pointer',
  }),
  panelHeader: {
    padding: '10px 16px', borderBottom: '1px solid var(--ui-border-subtle)',
    display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 8,
  },
  panel: { backgroundColor: 'var(--ui-surface)', border: '1px solid var(--ui-border)', borderRadius: 'var(--ui-radius)', overflow: 'hidden' },
};

// Native HTML5 drag-and-drop row reordering (no extra dependency) — drag
// the handle cell (⠿) at the start of a row to move it, e.g. to reposition
// a "Total Finished Steel"/"Total Saleable"/"Total Hot Metal" summary row
// relative to the unit rows it sums. `setItems` is the owning editor's own
// setRows, called once on drop with the reordered array; nothing is saved
// until that editor's own Save button is clicked, same as every other
// edit here.
function useRowDrag(setItems) {
  const [dragIndex, setDragIndex] = useState(null);
  const [overIndex, setOverIndex] = useState(null);

  const dragHandleProps = (i) => ({
    draggable: true,
    onDragStart: (e) => {
      setDragIndex(i);
      e.dataTransfer.effectAllowed = 'move';
      e.dataTransfer.setData('text/plain', String(i));
    },
    onDragEnd: () => { setDragIndex(null); setOverIndex(null); },
  });

  const rowDropProps = (i) => ({
    onDragOver: (e) => {
      if (dragIndex === null) return;
      e.preventDefault();
      e.dataTransfer.dropEffect = 'move';
      if (overIndex !== i) setOverIndex(i);
    },
    onDrop: (e) => {
      e.preventDefault();
      const from = dragIndex;
      setDragIndex(null);
      setOverIndex(null);
      if (from === null || from === i) return;
      setItems(items => {
        const copy = [...items];
        const [moved] = copy.splice(from, 1);
        copy.splice(i, 0, moved);
        return copy;
      });
    },
  });

  const rowStyle = (i) => (
    dragIndex === i
      ? { opacity: 0.4 }
      : overIndex === i && dragIndex !== null
        ? { boxShadow: 'inset 0 2px 0 #1a73e8' }
        : undefined
  );

  return { dragHandleProps, rowDropProps, rowStyle };
}

function DragHandleCell({ dragHandleProps }) {
  return (
    <td style={{ padding: '6px 4px', verticalAlign: 'top', borderBottom: '1px solid var(--ui-border-subtle)', textAlign: 'center', width: 22, cursor: 'grab', color: 'var(--ui-text-tertiary)', fontSize: 14 }}
      {...dragHandleProps} title="Drag to reorder">
      ⠿
    </td>
  );
}

function SavedLabel({ savedAt, updatedBy, updatedAt }) {
  if (!savedAt && !updatedAt) return null;
  return (
    <span style={{ fontSize: 12, color: 'var(--ui-text-secondary)' }}>
      {savedAt ? `Saved ${savedAt.toLocaleTimeString()}` : `Last updated ${updatedAt}${updatedBy ? ` by ${updatedBy}` : ''}`}
    </span>
  );
}

function emptyCapacityRow() {
  return { item: '', details: '', capacity: '', is_total: false };
}

function CapacityEditor({ plantCode, initialRows, updatedBy, updatedAt }) {
  const [rows, setRows] = useState(() => (initialRows && initialRows.length ? initialRows : [emptyCapacityRow()]));
  const [saving, setSaving] = useState(false);
  const [savedAt, setSavedAt] = useState(null);
  const [err, setErr] = useState(null);
  const { dragHandleProps, rowDropProps, rowStyle } = useRowDrag(setRows);

  const updateCell = (i, field, value) => {
    setRows(rs => rs.map((r, idx) => (idx === i ? { ...r, [field]: value } : r)));
  };
  const addRow = () => setRows(rs => [...rs, emptyCapacityRow()]);
  const deleteRow = (i) => {
    if (!confirm('Delete this row?')) return;
    setRows(rs => rs.filter((_, idx) => idx !== i));
  };

  const handleSave = async () => {
    setSaving(true);
    setErr(null);
    try {
      const res = await fetch(`${API_BASE_URL}/api/ready-reckoner/${plantCode}`, {
        method: 'POST',
        credentials: 'include',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ capacity_rows: rows }),
      });
      if (!res.ok) throw new Error(await res.text());
      setSavedAt(new Date());
    } catch (e) {
      setErr(e.message);
    } finally {
      setSaving(false);
    }
  };

  return (
    <div style={S.panel}>
      <div style={S.panelHeader}>
        <span style={{ fontWeight: 700, fontSize: 14, color: '#202124' }}>Unit-wise Capacity</span>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <SavedLabel savedAt={savedAt} updatedBy={updatedBy} updatedAt={updatedAt} />
          <button onClick={addRow} style={S.addBtn}>+ Add Row (unit)</button>
          <button onClick={handleSave} disabled={saving} style={S.saveBtn(saving)}>{saving ? 'Saving…' : 'Save'}</button>
        </div>
      </div>
      {err && <div style={{ padding: '8px 16px' }}><Notice type="error" text={err} /></div>}
      <div style={{ padding: '6px 16px 0', fontSize: 11, color: '#5f6368' }}>
        Drag <strong>⠿</strong> to reorder rows — e.g. to move a &ldquo;Total Finished Steel&rdquo;/&ldquo;Total Saleable&rdquo;/&ldquo;Total Hot Metal&rdquo; row next to the units it sums.
      </div>
      <div style={{ overflowX: 'auto', padding: '10px 16px 16px' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse' }}>
          <thead>
            <tr>
              <th style={{ ...S.th, width: 22 }} />
              <th style={{ ...S.th, width: '18%' }}>Facility</th>
              <th style={{ ...S.th, width: '52%' }}>Details</th>
              <th style={{ ...S.th, width: '20%' }}>Capacity</th>
              <th style={{ ...S.th, width: '5%' }}>Total?</th>
              <th style={{ ...S.th, width: '5%' }} />
            </tr>
          </thead>
          <tbody>
            {rows.map((row, i) => (
              <tr key={i} {...rowDropProps(i)} style={rowStyle(i)}>
                <DragHandleCell dragHandleProps={dragHandleProps(i)} />
                <td style={S.td}>
                  <input style={{ ...S.input, color: '#8b4513' }} value={row.item}
                    onChange={e => updateCell(i, 'item', e.target.value)} />
                </td>
                <td style={S.td}>
                  <textarea style={{ ...S.textarea, color: '#1a56db' }} value={row.details}
                    onChange={e => updateCell(i, 'details', e.target.value)} />
                </td>
                <td style={S.td}>
                  <textarea style={S.textarea} value={row.capacity}
                    onChange={e => updateCell(i, 'capacity', e.target.value)} />
                </td>
                <td style={{ ...S.td, textAlign: 'center' }}>
                  <input type="checkbox" checked={!!row.is_total}
                    onChange={e => updateCell(i, 'is_total', e.target.checked)}
                    title="Bold this row as a summary/total" />
                </td>
                <td style={{ ...S.td, textAlign: 'center' }}>
                  <button onClick={() => deleteRow(i)} style={S.delBtn} title="Delete row">✕</button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function ProductMixEditor({ plantCode, initialHeaders, initialRows, initialCaption, updatedBy, updatedAt }) {
  const [headers, setHeaders] = useState(() => (initialHeaders && initialHeaders.length ? initialHeaders : ['Column 1', 'Column 2']));
  const [rows, setRows] = useState(() => {
    if (initialRows && initialRows.length) return initialRows;
    const n = (initialHeaders && initialHeaders.length) || 2;
    return [{ cells: Array(n).fill(''), is_total: false }];
  });
  const [caption, setCaption] = useState(initialCaption || '');
  const [saving, setSaving] = useState(false);
  const [savedAt, setSavedAt] = useState(null);
  const [err, setErr] = useState(null);
  const { dragHandleProps, rowDropProps, rowStyle } = useRowDrag(setRows);

  const updateHeader = (i, value) => setHeaders(hs => hs.map((h, idx) => (idx === i ? value : h)));
  const updateCell = (rowIdx, colIdx, value) => {
    setRows(rs => rs.map((r, idx) => (idx === rowIdx
      ? { ...r, cells: r.cells.map((c, ci) => (ci === colIdx ? value : c)) }
      : r)));
  };
  const setRowTotal = (rowIdx, value) => {
    setRows(rs => rs.map((r, idx) => (idx === rowIdx ? { ...r, is_total: value } : r)));
  };

  const addColumn = () => {
    setHeaders(hs => [...hs, `Column ${hs.length + 1}`]);
    setRows(rs => rs.map(r => ({ ...r, cells: [...r.cells, ''] })));
  };
  const deleteColumn = (colIdx) => {
    if (headers.length <= 1) { alert('A table needs at least one column.'); return; }
    if (!confirm(`Delete column "${headers[colIdx]}"? This removes that cell from every row.`)) return;
    setHeaders(hs => hs.filter((_, i) => i !== colIdx));
    setRows(rs => rs.map(r => ({ ...r, cells: r.cells.filter((_, i) => i !== colIdx) })));
  };
  const addRow = () => setRows(rs => [...rs, { cells: Array(headers.length).fill(''), is_total: false }]);
  const deleteRow = (rowIdx) => {
    if (!confirm('Delete this row?')) return;
    setRows(rs => rs.filter((_, i) => i !== rowIdx));
  };

  const handleSave = async () => {
    setSaving(true);
    setErr(null);
    try {
      const res = await fetch(`${API_BASE_URL}/api/ready-reckoner/${plantCode}`, {
        method: 'POST',
        credentials: 'include',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          product_mix_headers: headers,
          product_mix_rows: rows,
          product_mix_caption: caption,
        }),
      });
      if (!res.ok) throw new Error(await res.text());
      setSavedAt(new Date());
    } catch (e) {
      setErr(e.message);
    } finally {
      setSaving(false);
    }
  };

  return (
    <div style={S.panel}>
      <div style={S.panelHeader}>
        <span style={{ fontWeight: 700, fontSize: 14, color: '#202124' }}>Product Mix</span>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <SavedLabel savedAt={savedAt} updatedBy={updatedBy} updatedAt={updatedAt} />
          <button onClick={addColumn} style={S.addBtn}>+ Add Column</button>
          <button onClick={addRow} style={S.addBtn}>+ Add Row</button>
          <button onClick={handleSave} disabled={saving} style={S.saveBtn(saving)}>{saving ? 'Saving…' : 'Save'}</button>
        </div>
      </div>
      {err && <div style={{ padding: '8px 16px' }}><Notice type="error" text={err} /></div>}
      <div style={{ padding: '10px 16px 0' }}>
        <label style={{ fontSize: 11.5, fontWeight: 600, color: '#374151', display: 'block', marginBottom: 4 }}>
          Caption (optional — a note shown above the table, e.g. &ldquo;representative grade families only&rdquo;)
        </label>
        <input style={S.input} value={caption} onChange={e => setCaption(e.target.value)} />
      </div>
      <div style={{ overflowX: 'auto', padding: '10px 16px 16px' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse', minWidth: 480 }}>
          <thead>
            <tr>
              <th style={{ ...S.th, width: 22 }} />
              {headers.map((h, i) => (
                <th key={i} style={S.th}>
                  <div style={{ display: 'flex', gap: 4, alignItems: 'center' }}>
                    <input style={S.input} value={h} onChange={e => updateHeader(i, e.target.value)} />
                    <button onClick={() => deleteColumn(i)} style={S.delBtn} title="Delete column">✕</button>
                  </div>
                </th>
              ))}
              <th style={{ ...S.th, width: '5%' }}>Total?</th>
              <th style={{ ...S.th, width: '5%' }} />
            </tr>
          </thead>
          <tbody>
            {rows.map((row, ri) => (
              <tr key={ri} {...rowDropProps(ri)} style={rowStyle(ri)}>
                <DragHandleCell dragHandleProps={dragHandleProps(ri)} />
                {row.cells.map((cell, ci) => (
                  <td key={ci} style={S.td}>
                    <textarea style={S.textarea} value={cell} onChange={e => updateCell(ri, ci, e.target.value)} />
                  </td>
                ))}
                <td style={{ ...S.td, textAlign: 'center' }}>
                  <input type="checkbox" checked={!!row.is_total} onChange={e => setRowTotal(ri, e.target.checked)}
                    title="Bold this row as a summary/total" />
                </td>
                <td style={{ ...S.td, textAlign: 'center' }}>
                  <button onClick={() => deleteRow(ri)} style={S.delBtn} title="Delete row">✕</button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function ReadyReckonerDataEntryPageInner() {
  const [rows, setRows] = useState([]);
  const [selectedPlant, setSelectedPlant] = useState('');
  const [loading, setLoading] = useState(false);
  const [status, setStatus] = useState(null);

  const load = useCallback(async () => {
    setLoading(true);
    setStatus(null);
    try {
      const res = await fetch(`${API_BASE_URL}/api/ready-reckoner`, { credentials: 'include' });
      if (!res.ok) throw new Error(await res.text());
      const data = await res.json();
      const rows = data.rows || [];
      setRows(rows);
      setSelectedPlant(prev => (prev && rows.some(r => r.plant_code === prev)) ? prev : (rows[0]?.plant_code || ''));
    } catch (err) {
      setStatus({ type: 'error', text: `Load failed: ${err.message}` });
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const ispRows = rows.filter(r => r.plant_group === 'ISP');
  const sspRows = rows.filter(r => r.plant_group === 'SSP');
  const current = rows.find(r => r.plant_code === selectedPlant);

  return (
    <EntryPage
      maxWidth={1200}
      title="Ready Reckoner — Unit-wise Capacity & Product Mix"
      description={<>
        Edit the &ldquo;Unit-wise Capacity&rdquo; and &ldquo;Product Mix&rdquo; reference tables shown on each plant&apos;s Ready
        Reckoner pages at the end of the report. Plain fields only — coloring and bold totals in the report
        are applied automatically, not typed in here. Not month-scoped &mdash; content here applies to every
        report until changed again. To replace a plant&apos;s process-flow diagram, use the &ldquo;Replace
        diagram&rdquo; control on that page in the report preview instead.
      </>}
    >
      <ContextBar actions={loading ? <span className={es.ctxNote}>Loading… ⟳</span> : null}>
        <Field label="Plant" htmlFor="rr-plant">
          <select id="rr-plant" className={es.control} value={selectedPlant} onChange={e => setSelectedPlant(e.target.value)}>
            {ispRows.length > 0 && (
              <optgroup label="Integrated Steel Plants">
                {ispRows.map(r => <option key={r.plant_code} value={r.plant_code}>{r.plant_name}</option>)}
              </optgroup>
            )}
            {sspRows.length > 0 && (
              <optgroup label="Special Steel Plants">
                {sspRows.map(r => <option key={r.plant_code} value={r.plant_code}>{r.plant_name}</option>)}
              </optgroup>
            )}
          </select>
        </Field>
      </ContextBar>

      <Notice type={status?.type} text={status?.text} />

      {current && (
        <div key={current.plant_code} style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
          <CapacityEditor
            plantCode={current.plant_code}
            initialRows={current.capacity_rows}
            updatedBy={current.updated_by}
            updatedAt={current.updated_at}
          />
          <ProductMixEditor
            plantCode={current.plant_code}
            initialHeaders={current.product_mix_headers}
            initialRows={current.product_mix_rows}
            initialCaption={current.product_mix_caption}
            updatedBy={current.updated_by}
            updatedAt={current.updated_at}
          />
        </div>
      )}

      {!loading && !current && <div className={wb.empty}>No plants found.</div>}
    </EntryPage>
  );
}

export default function ReadyReckonerDataEntryPage() {
  return (
    <RequireEditor>
      <ReadyReckonerDataEntryPageInner />
    </RequireEditor>
  );
}
