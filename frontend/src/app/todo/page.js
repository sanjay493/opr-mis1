'use client';

import React, { useState, useEffect, useMemo } from 'react';
import GlobalNavbar from '@/components/GlobalNavbar';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://127.0.0.1:8082';

const PRIORITY = {
  high:   { label: 'High',   text: '#c5221f', bg: '#fce8e6', border: '#dc2626' },
  medium: { label: 'Medium', text: '#92400e', bg: '#fef3c7', border: '#f59e0b' },
  low:    { label: 'Low',    text: '#188038', bg: '#e6f4ea', border: '#34a853' },
};

const WEEKDAYS = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];
const MONTH_NAMES = ['January', 'February', 'March', 'April', 'May', 'June',
  'July', 'August', 'September', 'October', 'November', 'December'];

function fmtDate(iso) {
  if (!iso) return '';
  const [y, m, d] = iso.split('-').map(Number);
  return `${d} ${MONTH_NAMES[m - 1].slice(0, 3)} '${String(y).slice(2)}`;
}

function todayISO() {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
}

const emptyForm = { subject: '', details: '', recipient: '', due_date: todayISO(), priority: 'medium' };

export default function TodoPage() {
  const [jobs, setJobs] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [statusFilter, setStatusFilter] = useState('pending'); // pending | done | all
  const [viewMode, setViewMode] = useState('list'); // list | calendar
  const [form, setForm] = useState(emptyForm);
  const [saving, setSaving] = useState(false);
  const [calendarMonth, setCalendarMonth] = useState(() => {
    const d = new Date();
    return new Date(d.getFullYear(), d.getMonth(), 1);
  });

  const loadJobs = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`${API_BASE}/api/todo/list?status=all`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const json = await res.json();
      setJobs(json.jobs || []);
    } catch (err) {
      setError(err.message || 'Failed to load jobs');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { loadJobs(); }, []);

  const visibleJobs = useMemo(() => {
    if (statusFilter === 'all') return jobs;
    return jobs.filter((j) => j.status === statusFilter);
  }, [jobs, statusFilter]);

  const handleAdd = async (e) => {
    e.preventDefault();
    if (!form.subject.trim() || !form.due_date) return;
    setSaving(true);
    setError(null);
    try {
      const res = await fetch(`${API_BASE}/api/todo/add`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(form),
      });
      const json = await res.json();
      if (!res.ok) throw new Error(json.detail || 'Failed to add job');
      setForm(emptyForm);
      await loadJobs();
    } catch (err) {
      setError(err.message || 'Failed to add job');
    } finally {
      setSaving(false);
    }
  };

  const callAction = async (jobId, action) => {
    try {
      const res = await fetch(`${API_BASE}/api/todo/${jobId}/${action}`, { method: 'POST' });
      if (!res.ok) {
        const json = await res.json().catch(() => ({}));
        throw new Error(json.detail || `Failed to ${action}`);
      }
      await loadJobs();
    } catch (err) {
      setError(err.message || `Failed to ${action}`);
    }
  };

  const handleDelete = async (jobId) => {
    if (!window.confirm('Delete this job permanently?')) return;
    await callAction(jobId, 'delete');
  };

  return (
    <div style={{ height: '100vh', display: 'flex', flexDirection: 'column', backgroundColor: '#ffffff' }}>
      <GlobalNavbar />
      <main style={{
        flex: 1, overflow: 'auto', padding: '32px', maxWidth: '1200px',
        margin: '0 auto', width: '100%', boxSizing: 'border-box',
      }}>
        <h1 style={{ fontSize: '20pt', fontWeight: 900, color: '#202124', margin: '0 0 6px' }}>
          ✅ To-Do — Upcoming Jobs
        </h1>
        <p style={{ fontSize: '11pt', color: '#5f6368', marginBottom: '20px' }}>
          Track jobs that need to be sent out, with a due date, recipient, and priority.
        </p>

        {/* Add-job form */}
        <form onSubmit={handleAdd} style={{
          border: '1px solid #dadce0', borderRadius: '8px', padding: '16px 18px',
          marginBottom: '20px', backgroundColor: '#f8f9fa',
        }}>
          <div style={{ display: 'grid', gridTemplateColumns: '2fr 1.4fr 1fr 1fr auto', gap: '10px', alignItems: 'end' }}>
            <div>
              <label style={labelStyle}>Subject</label>
              <input required value={form.subject}
                onChange={(e) => setForm((f) => ({ ...f, subject: e.target.value }))}
                placeholder="e.g. Send May production summary"
                style={inputStyle} />
            </div>
            <div>
              <label style={labelStyle}>Where to send (recipient)</label>
              <input value={form.recipient}
                onChange={(e) => setForm((f) => ({ ...f, recipient: e.target.value }))}
                placeholder="e.g. SAIL Corporate Office"
                style={inputStyle} />
            </div>
            <div>
              <label style={labelStyle}>Due Date</label>
              <input type="date" required value={form.due_date}
                onChange={(e) => setForm((f) => ({ ...f, due_date: e.target.value }))}
                style={inputStyle} />
            </div>
            <div>
              <label style={labelStyle}>Priority</label>
              <select value={form.priority}
                onChange={(e) => setForm((f) => ({ ...f, priority: e.target.value }))}
                style={inputStyle}>
                <option value="high">High</option>
                <option value="medium">Medium</option>
                <option value="low">Low</option>
              </select>
            </div>
            <button type="submit" disabled={saving} style={{
              padding: '9px 18px', background: saving ? '#5f6368' : '#1a73e8', color: '#fff',
              border: 'none', borderRadius: '6px', fontSize: '10.5pt', fontWeight: 700,
              cursor: saving ? 'not-allowed' : 'pointer', whiteSpace: 'nowrap',
            }}>
              {saving ? 'Adding…' : '+ Add Job'}
            </button>
          </div>
          <div style={{ marginTop: '10px' }}>
            <label style={labelStyle}>Details (optional)</label>
            <textarea value={form.details}
              onChange={(e) => setForm((f) => ({ ...f, details: e.target.value }))}
              placeholder="Any extra notes about this job…"
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

        {/* Controls: view mode + status filter */}
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '14px', flexWrap: 'wrap', gap: '10px' }}>
          <div style={{ display: 'flex', gap: '8px' }}>
            {['list', 'calendar'].map((m) => (
              <button key={m} onClick={() => setViewMode(m)} style={{
                padding: '7px 16px', borderRadius: '6px',
                border: `2px solid ${viewMode === m ? '#1a73e8' : '#dadce0'}`,
                background: viewMode === m ? '#e8f0fe' : '#fff',
                color: viewMode === m ? '#1a73e8' : '#5f6368',
                fontSize: '10pt', fontWeight: viewMode === m ? 700 : 600, cursor: 'pointer',
              }}>
                {m === 'list' ? '📋 List' : '📅 Calendar'}
              </button>
            ))}
          </div>
          <div style={{ display: 'flex', gap: '6px' }}>
            {['pending', 'done', 'all'].map((s) => (
              <button key={s} onClick={() => setStatusFilter(s)} style={{
                padding: '6px 14px', borderRadius: '14px',
                border: `1px solid ${statusFilter === s ? '#1a73e8' : '#dadce0'}`,
                background: statusFilter === s ? '#1a73e8' : '#fff',
                color: statusFilter === s ? '#fff' : '#5f6368',
                fontSize: '9.5pt', fontWeight: 600, cursor: 'pointer', textTransform: 'capitalize',
              }}>
                {s}
              </button>
            ))}
          </div>
        </div>

        {loading && <div style={{ color: '#5f6368', fontSize: '10.5pt', padding: '8px 0' }}>Loading…</div>}

        {!loading && viewMode === 'list' && (
          <JobList jobs={visibleJobs} onComplete={(id) => callAction(id, 'complete')}
                   onReopen={(id) => callAction(id, 'reopen')} onDelete={handleDelete} />
        )}

        {!loading && viewMode === 'calendar' && (
          <JobCalendar jobs={visibleJobs} month={calendarMonth} setMonth={setCalendarMonth} />
        )}
      </main>
    </div>
  );
}

const labelStyle = { display: 'block', fontSize: '9pt', fontWeight: 700, color: '#5f6368', marginBottom: '4px', textTransform: 'uppercase' };
const inputStyle = {
  width: '100%', padding: '8px 10px', fontSize: '10.5pt', border: '1px solid #dadce0',
  borderRadius: '6px', boxSizing: 'border-box', color: '#202124', background: '#fff',
};

// ── List view ──────────────────────────────────────────────────────────────
function JobList({ jobs, onComplete, onReopen, onDelete }) {
  if (jobs.length === 0) {
    return (
      <div style={{ padding: '30px', textAlign: 'center', color: '#5f6368', fontSize: '11pt', border: '1px solid #dadce0', borderRadius: '8px' }}>
        No jobs to show.
      </div>
    );
  }
  return (
    <div style={{ border: '1px solid #dadce0', borderRadius: '8px', overflow: 'hidden' }}>
      {jobs.map((job, idx) => {
        const p = PRIORITY[job.priority] || PRIORITY.medium;
        const done = job.status === 'done';
        return (
          <div key={job.id} style={{
            display: 'flex', alignItems: 'center', gap: '14px',
            padding: '12px 16px', borderLeft: `5px solid ${p.border}`,
            borderBottom: idx < jobs.length - 1 ? '1px solid #f1f3f4' : 'none',
            backgroundColor: done ? '#f8f9fa' : '#fff', opacity: done ? 0.7 : 1,
          }}>
            <input type="checkbox" checked={done} onChange={() => (done ? onReopen(job.id) : onComplete(job.id))}
              title={done ? 'Mark as pending again' : 'Mark as done'}
              style={{ width: '16px', height: '16px', cursor: 'pointer', accentColor: '#10b981' }} />
            <div style={{ width: '90px', flexShrink: 0, fontSize: '9.5pt', fontWeight: 700, color: '#202124' }}>
              {fmtDate(job.due_date)}
            </div>
            <div style={{ flex: 1, minWidth: 0 }}>
              <div style={{ fontSize: '10.5pt', fontWeight: 600, color: '#202124', textDecoration: done ? 'line-through' : 'none' }}>
                {job.subject}
              </div>
              {(job.recipient || job.details) && (
                <div style={{ fontSize: '9pt', color: '#5f6368', marginTop: '2px' }}>
                  {job.recipient && <span>→ {job.recipient}</span>}
                  {job.recipient && job.details && <span> · </span>}
                  {job.details}
                </div>
              )}
            </div>
            <span style={{
              padding: '3px 10px', borderRadius: '12px', fontSize: '9pt', fontWeight: 700,
              color: p.text, backgroundColor: p.bg, whiteSpace: 'nowrap',
            }}>
              {p.label}
            </span>
            <button onClick={() => onDelete(job.id)} title="Delete" style={{
              background: 'none', border: 'none', color: '#9aa0a6', cursor: 'pointer', fontSize: '13pt', padding: '2px 6px',
            }}>
              ✕
            </button>
          </div>
        );
      })}
    </div>
  );
}

// ── Calendar view ────────────────────────────────────────────────────────────
function JobCalendar({ jobs, month, setMonth }) {
  const jobsByDate = useMemo(() => {
    const map = {};
    jobs.forEach((j) => {
      (map[j.due_date] = map[j.due_date] || []).push(j);
    });
    return map;
  }, [jobs]);

  const year = month.getFullYear();
  const mIdx = month.getMonth();
  const firstDow = new Date(year, mIdx, 1).getDay();
  const daysInMonth = new Date(year, mIdx + 1, 0).getDate();
  const todayStr = todayISO();

  const cells = [];
  for (let i = 0; i < firstDow; i++) cells.push(null);
  for (let d = 1; d <= daysInMonth; d++) cells.push(d);
  while (cells.length % 7 !== 0) cells.push(null);

  const goMonth = (delta) => setMonth(new Date(year, mIdx + delta, 1));

  return (
    <div style={{ border: '1px solid #dadce0', borderRadius: '8px', overflow: 'hidden' }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '10px 16px', backgroundColor: '#f8f9fa', borderBottom: '1px solid #dadce0' }}>
        <button onClick={() => goMonth(-1)} style={navBtnStyle}>‹ Prev</button>
        <div style={{ fontSize: '12pt', fontWeight: 800, color: '#202124' }}>
          {MONTH_NAMES[mIdx]} {year}
        </div>
        <button onClick={() => goMonth(1)} style={navBtnStyle}>Next ›</button>
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(7, 1fr)' }}>
        {WEEKDAYS.map((wd) => (
          <div key={wd} style={{ padding: '6px', textAlign: 'center', fontSize: '9pt', fontWeight: 700, color: '#5f6368', borderBottom: '1px solid #dadce0', backgroundColor: '#fafbfc' }}>
            {wd}
          </div>
        ))}
        {cells.map((d, idx) => {
          const iso = d ? `${year}-${String(mIdx + 1).padStart(2, '0')}-${String(d).padStart(2, '0')}` : null;
          const dayJobs = iso ? (jobsByDate[iso] || []) : [];
          const isToday = iso === todayStr;
          return (
            <div key={idx} style={{
              minHeight: '92px', padding: '6px', borderBottom: '1px solid #f1f3f4',
              borderRight: (idx % 7 !== 6) ? '1px solid #f1f3f4' : 'none',
              backgroundColor: d ? (isToday ? '#e8f0fe' : '#fff') : '#fafbfc',
            }}>
              {d && (
                <>
                  <div style={{ fontSize: '9.5pt', fontWeight: isToday ? 800 : 600, color: isToday ? '#1a73e8' : '#202124', marginBottom: '4px' }}>
                    {d}
                  </div>
                  {dayJobs.slice(0, 3).map((j) => {
                    const p = PRIORITY[j.priority] || PRIORITY.medium;
                    return (
                      <div key={j.id} title={`${j.subject}${j.recipient ? ' → ' + j.recipient : ''}`} style={{
                        fontSize: '8pt', fontWeight: 600, color: p.text, backgroundColor: p.bg,
                        borderLeft: `3px solid ${p.border}`, borderRadius: '3px',
                        padding: '2px 4px', marginBottom: '2px', overflow: 'hidden',
                        textOverflow: 'ellipsis', whiteSpace: 'nowrap',
                        textDecoration: j.status === 'done' ? 'line-through' : 'none',
                      }}>
                        {j.subject}
                      </div>
                    );
                  })}
                  {dayJobs.length > 3 && (
                    <div style={{ fontSize: '7.5pt', color: '#5f6368' }}>+{dayJobs.length - 3} more</div>
                  )}
                </>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

const navBtnStyle = {
  padding: '5px 12px', background: '#fff', border: '1px solid #dadce0', borderRadius: '5px',
  color: '#1a73e8', fontSize: '9.5pt', fontWeight: 700, cursor: 'pointer',
};
