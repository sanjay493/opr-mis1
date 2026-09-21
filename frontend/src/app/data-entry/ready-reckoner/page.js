'use client';

import RequireEditor from '@/components/RequireEditor';

import React, { useCallback, useEffect, useState } from 'react';
import GlobalNavbar from '@/components/GlobalNavbar';
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
  const ok = type === 'success';
  return (
    <div style={{
      padding: '10px 16px', borderRadius: 6, marginBottom: 14, fontSize: 14,
      background: ok ? '#f0fdf4' : '#fef2f2',
      color: ok ? '#166534' : '#991b1b',
      border: `1px solid ${ok ? '#86efac' : '#fca5a5'}`,
    }}>
      {text}
    </div>
  );
}

const S = {
  input: {
    width: '100%', border: '1px solid #dadce0', borderRadius: 4, padding: '5px 7px',
    fontSize: 12.5, fontFamily: 'inherit', boxSizing: 'border-box',
  },
  textarea: {
    width: '100%', border: '1px solid #dadce0', borderRadius: 4, padding: '5px 7px',
    fontSize: 12.5, fontFamily: 'inherit', boxSizing: 'border-box', resize: 'vertical', minHeight: 44,
  },
  th: { padding: '6px 8px', textAlign: 'left', fontSize: 12, fontWeight: 700, color: '#374151', borderBottom: '1px solid #dadce0' },
  td: { padding: '6px 8px', verticalAlign: 'top', borderBottom: '1px solid #f0f4f8' },
  addBtn: {
    padding: '6px 14px', fontSize: 12.5, fontWeight: 600,
    background: '#eef2ff', color: '#3730a3', border: 'none', borderRadius: 4, cursor: 'pointer',
  },
  delBtn: {
    width: 26, height: 26, lineHeight: '24px', textAlign: 'center', padding: 0, fontSize: 14, fontWeight: 700,
    background: '#fef2f2', color: '#991b1b', border: 'none', borderRadius: 4, cursor: 'pointer',
  },
  saveBtn: (saving) => ({
    padding: '6px 16px', fontSize: 13, fontWeight: 600,
    background: '#1a73e8', color: '#fff', border: 'none', borderRadius: 4,
    cursor: saving ? 'not-allowed' : 'pointer',
  }),
  panelHeader: {
    padding: '12px 16px', backgroundColor: '#f8f9fa',
    display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 8,
  },
  panel: { backgroundColor: '#fff', border: '1px solid #dadce0', borderRadius: 8, overflow: 'hidden' },
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
    <td style={{ padding: '6px 4px', verticalAlign: 'top', borderBottom: '1px solid #f0f4f8', textAlign: 'center', width: 22, cursor: 'grab', color: '#9aa0a6', fontSize: 14 }}
      {...dragHandleProps} title="Drag to reorder">
      ⠿
    </td>
  );
}

function SavedLabel({ savedAt, updatedBy, updatedAt }) {
  if (!savedAt && !updatedAt) return null;
  return (
    <span style={{ fontSize: 11.5, color: '#5f6368' }}>
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
    <div style={{ height: '100vh', display: 'flex', flexDirection: 'column', background: '#ffffff' }}>
      <GlobalNavbar />

      <div style={{ flex: 1, overflow: 'auto', maxWidth: 1200, margin: '0 auto', padding: '22px 20px', width: '100%', boxSizing: 'border-box' }}>

        <div style={{ marginBottom: 18 }}>
          <h2 style={{ fontSize: '1.6rem', fontWeight: 700, color: '#202124', margin: '0 0 4px' }}>
            Ready Reckoner — Unit-wise Capacity &amp; Product Mix
          </h2>
          <span style={{ fontSize: 13, color: '#5f6368' }}>
            Edit the &ldquo;Unit-wise Capacity&rdquo; and &ldquo;Product Mix&rdquo; reference tables shown on each plant&apos;s Ready
            Reckoner pages at the end of the report. Plain fields only — coloring and bold totals in the report
            are applied automatically, not typed in here. Not month-scoped &mdash; content here applies to every
            report until changed again. To replace a plant&apos;s process-flow diagram, use the &ldquo;Replace
            diagram&rdquo; control on that page in the report preview instead.
          </span>
        </div>

        <div style={{
          display: 'flex', gap: 10, alignItems: 'center', flexWrap: 'wrap',
          marginBottom: 18, background: '#fff', border: '1px solid #dadce0',
          borderRadius: 8, padding: '14px 18px',
        }}>
          <label style={{ fontSize: 13, fontWeight: 600, color: '#374151' }}>Plant</label>
          <select value={selectedPlant} onChange={e => setSelectedPlant(e.target.value)}
            style={{ padding: '7px 10px', fontSize: 14, border: '1px solid #d1d5db', borderRadius: 4 }}>
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

          <span style={{ marginLeft: 'auto', fontSize: 13, color: '#5f6368' }}>
            {loading && 'Loading… ⟳'}
          </span>
        </div>

        <Notice type={status?.type} text={status?.text} />

        {current && (
          <div key={current.plant_code} style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
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

        {!loading && !current && (
          <div style={{ padding: 40, textAlign: 'center', color: '#5f6368', fontSize: 14 }}>
            No plants found.
          </div>
        )}
      </div>
    </div>
  );
}

export default function ReadyReckonerDataEntryPage() {
  return (
    <RequireEditor>
      <ReadyReckonerDataEntryPageInner />
    </RequireEditor>
  );
}
