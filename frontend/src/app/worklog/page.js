'use client';

import React, { useState, useEffect, useMemo } from 'react';
import GlobalNavbar from '@/components/GlobalNavbar';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://127.0.0.1:8082';

const WEEKDAYS = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday'];
const MONTH_NAMES = ['January', 'February', 'March', 'April', 'May', 'June',
  'July', 'August', 'September', 'October', 'November', 'December'];

function fmtDate(iso) {
  if (!iso) return '';
  const [y, m, d] = iso.split('-').map(Number);
  const dow = WEEKDAYS[new Date(y, m - 1, d).getDay()];
  return `${dow}, ${d} ${MONTH_NAMES[m - 1].slice(0, 3)} '${String(y).slice(2)}`;
}

function todayISO() {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
}

const emptyForm = { work_date: todayISO(), description: '', remarks: '' };

export default function WorklogPage() {
  const [entries, setEntries] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [month, setMonth] = useState(() => todayISO().slice(0, 7)); // YYYY-MM
  const [form, setForm] = useState(emptyForm);
  const [saving, setSaving] = useState(false);
  const [editingId, setEditingId] = useState(null);
  const [editForm, setEditForm] = useState(emptyForm);

  const loadEntries = async (m = month) => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`${API_BASE}/api/worklog/list?month=${m}`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const json = await res.json();
      setEntries(json.entries || []);
    } catch (err) {
      setError(err.message || 'Failed to load work log');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { loadEntries(month); }, [month]);

  // Group entries by work_date; list() already returns newest date first.
  const grouped = useMemo(() => {
    const map = new Map();
    entries.forEach((e) => {
      if (!map.has(e.work_date)) map.set(e.work_date, []);
      map.get(e.work_date).push(e);
    });
    return Array.from(map.entries());
  }, [entries]);

  const handleAdd = async (e) => {
    e.preventDefault();
    if (!form.description.trim() || !form.work_date) return;
    setSaving(true);
    setError(null);
    try {
      const res = await fetch(`${API_BASE}/api/worklog/add`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(form),
      });
      const json = await res.json();
      if (!res.ok) throw new Error(json.detail || 'Failed to add entry');
      setForm({ ...emptyForm, work_date: form.work_date });
      if (form.work_date.slice(0, 7) === month) await loadEntries();
      else setMonth(form.work_date.slice(0, 7));
    } catch (err) {
      setError(err.message || 'Failed to add entry');
    } finally {
      setSaving(false);
    }
  };

  const startEdit = (entry) => {
    setEditingId(entry.id);
    setEditForm({ work_date: entry.work_date, description: entry.description, remarks: entry.remarks || '' });
  };

  const handleUpdate = async (entryId) => {
    if (!editForm.description.trim()) return;
    setError(null);
    try {
      const res = await fetch(`${API_BASE}/api/worklog/${entryId}/update`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(editForm),
      });
      const json = await res.json();
      if (!res.ok) throw new Error(json.detail || 'Failed to update entry');
      setEditingId(null);
      await loadEntries();
    } catch (err) {
      setError(err.message || 'Failed to update entry');
    }
  };

  const handleDelete = async (entryId) => {
    if (!window.confirm('Delete this work log entry permanently?')) return;
    setError(null);
    try {
      const res = await fetch(`${API_BASE}/api/worklog/${entryId}/delete`, { method: 'POST' });
      if (!res.ok) {
        const json = await res.json().catch(() => ({}));
        throw new Error(json.detail || 'Failed to delete entry');
      }
      await loadEntries();
    } catch (err) {
      setError(err.message || 'Failed to delete entry');
    }
  };

  return (
    <div style={{ height: '100vh', display: 'flex', flexDirection: 'column', backgroundColor: '#ffffff' }}>
      <GlobalNavbar />
      <main style={{
        flex: 1, overflow: 'auto', padding: '32px', maxWidth: '1000px',
        margin: '0 auto', width: '100%', boxSizing: 'border-box',
      }}>
        <h1 style={{ fontSize: '20pt', fontWeight: 900, color: '#202124', margin: '0 0 6px' }}>
          📝 Daily Work Log
        </h1>
        <p style={{ fontSize: '11pt', color: '#5f6368', marginBottom: '20px' }}>
          Record the work you completed each day, grouped date-wise.
        </p>

        {/* Add-entry form */}
        <form onSubmit={handleAdd} style={{
          border: '1px solid #dadce0', borderRadius: '8px', padding: '16px 18px',
          marginBottom: '20px', backgroundColor: '#f8f9fa',
        }}>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 3fr auto', gap: '10px', alignItems: 'end' }}>
            <div>
              <label style={labelStyle}>Date</label>
              <input type="date" required value={form.work_date}
                onChange={(e) => setForm((f) => ({ ...f, work_date: e.target.value }))}
                style={inputStyle} />
            </div>
            <div>
              <label style={labelStyle}>Work Done</label>
              <input required value={form.description}
                onChange={(e) => setForm((f) => ({ ...f, description: e.target.value }))}
                placeholder="e.g. Compiled and sent May'26 OMI report to Corporate Office"
                style={inputStyle} />
            </div>
            <button type="submit" disabled={saving} style={{
              padding: '9px 18px', background: saving ? '#5f6368' : '#1a73e8', color: '#fff',
              border: 'none', borderRadius: '6px', fontSize: '10.5pt', fontWeight: 700,
              cursor: saving ? 'not-allowed' : 'pointer', whiteSpace: 'nowrap',
            }}>
              {saving ? 'Adding…' : '+ Add Entry'}
            </button>
          </div>
          <div style={{ marginTop: '10px' }}>
            <label style={labelStyle}>Remarks (optional)</label>
            <textarea value={form.remarks}
              onChange={(e) => setForm((f) => ({ ...f, remarks: e.target.value }))}
              placeholder="Any extra notes about this work…"
              rows={2}
              style={{ ...inputStyle, width: '100%', resize: 'vertical', fontFamily: 'inherit' }} />
          </div>
        </form>

        {error && (
          <div style={{
            padding: '10px 14px', border: '1px solid #f28b82', borderRadius: '6px',
            backgroundColor: '#fce8e6', color: '#c5221f', fontSize: '10.5pt', marginBottom: '16px',
          }}>
            {error}
          </div>
        )}

        {/* Month selector */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '14px' }}>
          <label style={{ ...labelStyle, marginBottom: 0 }}>Month</label>
          <input type="month" value={month} onChange={(e) => e.target.value && setMonth(e.target.value)}
            style={{ ...inputStyle, width: 'auto' }} />
          <span style={{ fontSize: '9.5pt', color: '#5f6368' }}>
            {entries.length} {entries.length === 1 ? 'entry' : 'entries'}
          </span>
        </div>

        {loading && <div style={{ color: '#5f6368', fontSize: '10.5pt', padding: '8px 0' }}>Loading…</div>}

        {!loading && grouped.length === 0 && (
          <div style={{ padding: '30px', textAlign: 'center', color: '#5f6368', fontSize: '11pt', border: '1px solid #dadce0', borderRadius: '8px' }}>
            No work logged for this month.
          </div>
        )}

        {!loading && grouped.map(([date, dayEntries]) => (
          <div key={date} style={{ marginBottom: '18px' }}>
            <div style={{
              fontSize: '10.5pt', fontWeight: 800, color: date === todayISO() ? '#1a73e8' : '#202124',
              padding: '4px 2px', marginBottom: '6px',
            }}>
              {fmtDate(date)}{date === todayISO() ? ' · Today' : ''}
            </div>
            <div style={{ border: '1px solid #dadce0', borderRadius: '8px', overflow: 'hidden' }}>
              {dayEntries.map((entry, idx) => (
                <div key={entry.id} style={{
                  padding: '11px 16px',
                  borderBottom: idx < dayEntries.length - 1 ? '1px solid #f1f3f4' : 'none',
                  backgroundColor: '#fff',
                }}>
                  {editingId === entry.id ? (
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                      <div style={{ display: 'grid', gridTemplateColumns: '1fr 3fr', gap: '8px' }}>
                        <input type="date" value={editForm.work_date}
                          onChange={(e) => setEditForm((f) => ({ ...f, work_date: e.target.value }))}
                          style={inputStyle} />
                        <input value={editForm.description}
                          onChange={(e) => setEditForm((f) => ({ ...f, description: e.target.value }))}
                          style={inputStyle} />
                      </div>
                      <textarea value={editForm.remarks} rows={2} placeholder="Remarks (optional)"
                        onChange={(e) => setEditForm((f) => ({ ...f, remarks: e.target.value }))}
                        style={{ ...inputStyle, width: '100%', resize: 'vertical', fontFamily: 'inherit' }} />
                      <div style={{ display: 'flex', gap: '8px' }}>
                        <button onClick={() => handleUpdate(entry.id)} style={smallBtnStyle('#1a73e8', '#fff')}>Save</button>
                        <button onClick={() => setEditingId(null)} style={smallBtnStyle('#fff', '#5f6368', '#dadce0')}>Cancel</button>
                      </div>
                    </div>
                  ) : (
                    <div style={{ display: 'flex', alignItems: 'flex-start', gap: '12px' }}>
                      <span style={{ color: '#34a853', fontSize: '11pt', lineHeight: '1.5' }}>✔</span>
                      <div style={{ flex: 1, minWidth: 0 }}>
                        <div style={{ fontSize: '10.5pt', fontWeight: 600, color: '#202124' }}>
                          {entry.description}
                        </div>
                        {entry.remarks && (
                          <div style={{ fontSize: '9pt', color: '#5f6368', marginTop: '2px', whiteSpace: 'pre-wrap' }}>
                            {entry.remarks}
                          </div>
                        )}
                      </div>
                      <button onClick={() => startEdit(entry)} title="Edit" style={{
                        background: 'none', border: 'none', color: '#9aa0a6', cursor: 'pointer', fontSize: '11pt', padding: '2px 6px',
                      }}>
                        ✏️
                      </button>
                      <button onClick={() => handleDelete(entry.id)} title="Delete" style={{
                        background: 'none', border: 'none', color: '#9aa0a6', cursor: 'pointer', fontSize: '13pt', padding: '2px 6px',
                      }}>
                        ✕
                      </button>
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>
        ))}
      </main>
    </div>
  );
}

const labelStyle = { display: 'block', fontSize: '9pt', fontWeight: 700, color: '#5f6368', marginBottom: '4px', textTransform: 'uppercase' };
const inputStyle = {
  width: '100%', padding: '8px 10px', fontSize: '10.5pt', border: '1px solid #dadce0',
  borderRadius: '6px', boxSizing: 'border-box', color: '#202124', background: '#fff',
};
const smallBtnStyle = (bg, color, border) => ({
  padding: '6px 16px', background: bg, color,
  border: border ? `1px solid ${border}` : 'none', borderRadius: '6px',
  fontSize: '9.5pt', fontWeight: 700, cursor: 'pointer',
});
