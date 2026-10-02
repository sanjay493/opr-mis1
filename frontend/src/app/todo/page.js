'use client';

import RequireEditor from '@/components/RequireEditor';

import React, { useState, useEffect, useMemo } from 'react';
import Link from 'next/link';
import GlobalNavbar from '@/components/GlobalNavbar';
import wb from '@/styles/wb.module.css';
import s from './todo.module.css';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || '';

const PRIORITY = {
  high:   { label: 'High',   text: '#c5221f', bg: '#fce8e6', border: '#d93025', badge: wb.badgeRed,   row: s.pHigh },
  medium: { label: 'Medium', text: '#92400e', bg: '#fef3c7', border: '#f9ab00', badge: wb.badgeAmber, row: s.pMedium },
  low:    { label: 'Low',    text: '#188038', bg: '#e6f4ea', border: '#188038', badge: wb.badgeGreen, row: s.pLow },
};

const WEEKDAYS = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];
const MONTH_NAMES = ['January', 'February', 'March', 'April', 'May', 'June',
  'July', 'August', 'September', 'October', 'November', 'December'];

function fmtDate(iso) {
  if (!iso) return '';
  const [y, m, d] = iso.split('-').map(Number);
  return `${d} ${MONTH_NAMES[m - 1].slice(0, 3)} '${String(y).slice(2)}`;
}

function isoOf(d) {
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
}
function todayISO() {
  return isoOf(new Date());
}
// Last day of the 7-day window starting today
function weekEndISO() {
  const d = new Date();
  d.setDate(d.getDate() + 6);
  return isoOf(d);
}

const emptyForm = { subject: '', details: '', recipient: '', due_date: todayISO(), priority: 'medium' };

// Status filters; 'overdue' and 'week' narrow the pending jobs by due date
const FILTERS = [
  { id: 'pending', label: 'Pending' },
  { id: 'week',    label: 'Due this week' },
  { id: 'overdue', label: 'Overdue' },
  { id: 'done',    label: 'Done' },
];

function TodoPageInner() {
  const [jobs, setJobs] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [statusFilter, setStatusFilter] = useState('pending'); // pending | week | overdue | done | all
  const [viewMode, setViewMode] = useState('list'); // list | calendar
  const [query, setQuery] = useState('');
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

  const today = todayISO();
  const weekEnd = weekEndISO();
  const isOverdue = (j) => j.status !== 'done' && j.due_date < today;
  const isThisWeek = (j) => j.status !== 'done' && j.due_date >= today && j.due_date <= weekEnd;

  const counts = {
    pending: jobs.filter((j) => j.status !== 'done').length,
    week: jobs.filter(isThisWeek).length,
    overdue: jobs.filter(isOverdue).length,
    done: jobs.filter((j) => j.status === 'done').length,
  };

  const visibleJobs = (() => {
    let list = jobs;
    if (statusFilter === 'pending') list = list.filter((j) => j.status !== 'done');
    else if (statusFilter === 'done') list = list.filter((j) => j.status === 'done');
    else if (statusFilter === 'overdue') list = list.filter(isOverdue);
    else if (statusFilter === 'week') list = list.filter(isThisWeek);
    const q = query.trim().toLowerCase();
    if (q) {
      list = list.filter((j) => [j.subject, j.recipient, j.details, j.remark]
        .some((v) => (v || '').toLowerCase().includes(q)));
    }
    return [...list].sort((a, b) => (a.due_date || '').localeCompare(b.due_date || ''));
  })();

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

  const saveRemark = async (jobId, remark) => {
    try {
      const res = await fetch(`${API_BASE}/api/todo/${jobId}/update`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ remark }),
      });
      if (!res.ok) {
        const json = await res.json().catch(() => ({}));
        throw new Error(json.detail || 'Failed to save remark');
      }
      await loadJobs();
    } catch (err) {
      setError(err.message || 'Failed to save remark');
    }
  };

  const setField = (k) => (e) => setForm((f) => ({ ...f, [k]: e.target.value }));

  return (
    <div className={wb.shell}>
      <GlobalNavbar />
      <main className={wb.page}>
        <div className={wb.inner}>
          <div className={wb.head}>
            <div>
              <h1 className={wb.title}>To-Do — Upcoming Jobs</h1>
              <p className={wb.lead}>Track jobs that need to be sent out, with a due date, recipient and priority.</p>
            </div>
            <div className={wb.headActions}>
              <Link href="/todo/missing-data" className={wb.btn}>⚠ Missing data tasks</Link>
            </div>
          </div>

          <div className={wb.chips}>
            {FILTERS.map((f) => {
              const tone = f.id === 'overdue' && counts.overdue ? wb.chipDanger : f.id === 'done' ? wb.chipSuccess : '';
              return (
                <button key={f.id} type="button" onClick={() => setStatusFilter(f.id)}
                        className={`${wb.chip} ${statusFilter === f.id ? wb.chipActive : tone}`}
                        aria-pressed={statusFilter === f.id}>
                  {f.label} <span className={wb.chipCount}>{counts[f.id]}</span>
                </button>
              );
            })}
          </div>

          {error && <div role="alert" className={`${wb.alert} ${wb.alertError}`} style={{ marginTop: 14 }}>{error}</div>}

          <div className={s.layout}>
            {/* ── Add-job card ── */}
            <form onSubmit={handleAdd} className={`${wb.panel} ${s.formCard}`}>
              <div className={wb.panelHead}>
                <h2 className={wb.panelTitle}>Create upcoming job</h2>
              </div>
              <div className={wb.panelBody}>
                <div className={wb.field}>
                  <label className={wb.label} htmlFor="todo-subject">Subject *</label>
                  <input id="todo-subject" required className={wb.input} value={form.subject}
                         onChange={setField('subject')} placeholder="e.g. Send May production summary" />
                </div>
                <div className={wb.field}>
                  <label className={wb.label} htmlFor="todo-recipient">Where to send (recipient)</label>
                  <input id="todo-recipient" className={wb.input} value={form.recipient}
                         onChange={setField('recipient')} placeholder="e.g. SAIL Corporate Office" />
                </div>
                <div className={wb.fieldRow}>
                  <div>
                    <label className={wb.label} htmlFor="todo-due">Due date *</label>
                    <input id="todo-due" type="date" required className={wb.input} value={form.due_date}
                           onChange={setField('due_date')} />
                  </div>
                  <div>
                    <label className={wb.label} htmlFor="todo-priority">Priority</label>
                    <select id="todo-priority" className={wb.select} value={form.priority} onChange={setField('priority')}>
                      <option value="high">High</option>
                      <option value="medium">Medium</option>
                      <option value="low">Low</option>
                    </select>
                  </div>
                </div>
                <div className={wb.field} style={{ marginTop: 12 }}>
                  <label className={wb.label} htmlFor="todo-details">Details (optional)</label>
                  <textarea id="todo-details" rows={3} className={wb.textarea} value={form.details}
                            onChange={setField('details')} placeholder="Any extra notes about this job…" />
                </div>
                <button type="submit" disabled={saving} className={`${wb.btn} ${wb.btnPrimary} ${wb.btnBlock}`} style={{ marginTop: 14 }}>
                  {saving ? 'Adding…' : '+ Add Job'}
                </button>
              </div>
            </form>

            {/* ── Jobs ── */}
            <div className={wb.panel}>
              <div className={s.toolbar}>
                <div className={wb.seg} role="group" aria-label="View">
                  {[['list', '☰ List'], ['calendar', '📅 Calendar']].map(([m, label]) => (
                    <button key={m} type="button" onClick={() => setViewMode(m)} aria-pressed={viewMode === m}
                            className={`${wb.segBtn} ${viewMode === m ? wb.segBtnActive : ''}`}>{label}</button>
                  ))}
                </div>
                <input className={`${wb.input} ${s.search}`} type="search" value={query}
                       onChange={(e) => setQuery(e.target.value)} placeholder="Filter jobs by subject, recipient or notes…"
                       aria-label="Filter jobs" />
                <div className={`${wb.seg} ${s.toolbarEnd}`} role="group" aria-label="Status">
                  {['pending', 'done', 'all'].map((f) => (
                    <button key={f} type="button" onClick={() => setStatusFilter(f)} aria-pressed={statusFilter === f}
                            className={`${wb.segBtn} ${statusFilter === f ? wb.segBtnActive : ''}`}
                            style={{ textTransform: 'capitalize' }}>{f}</button>
                  ))}
                </div>
              </div>

              {loading && <div className={wb.panelBody}><span className={wb.muted}>Loading…</span></div>}

              {!loading && viewMode === 'list' && (
                <JobList jobs={visibleJobs} today={today} weekEnd={weekEnd}
                         onComplete={(id) => callAction(id, 'complete')}
                         onReopen={(id) => callAction(id, 'reopen')} onDelete={handleDelete}
                         onSaveRemark={saveRemark} />
              )}

              {!loading && viewMode === 'calendar' && (
                <JobCalendar jobs={visibleJobs} month={calendarMonth} setMonth={setCalendarMonth} />
              )}
            </div>
          </div>
        </div>
      </main>
    </div>
  );
}

export default function TodoPage() {
  return (
    <RequireEditor>
      <TodoPageInner />
    </RequireEditor>
  );
}

// ── List view ──────────────────────────────────────────────────────────────
// Pending jobs are grouped by due date (overdue / next 7 days / later);
// completed jobs go in their own group at the end.
function JobList({ jobs, today, weekEnd, onComplete, onReopen, onDelete, onSaveRemark }) {
  if (jobs.length === 0) {
    return <div className={wb.panelBody}><div className={wb.empty}>No jobs to show.</div></div>;
  }
  const groups = [
    { id: 'overdue', label: 'Overdue', cls: s.gOverdue, note: 'Past the due date', test: (j) => j.status !== 'done' && j.due_date < today },
    { id: 'week', label: 'This week', cls: s.gWeek, note: 'Due in the next 7 days', test: (j) => j.status !== 'done' && j.due_date >= today && j.due_date <= weekEnd },
    { id: 'later', label: 'Later', cls: s.gLater, note: 'Due after this week', test: (j) => j.status !== 'done' && j.due_date > weekEnd },
    { id: 'done', label: 'Done', cls: s.gDone, note: 'Completed', test: (j) => j.status === 'done' },
  ];
  return (
    <div>
      {groups.map((g) => {
        const list = jobs.filter(g.test);
        if (!list.length) return null;
        return (
          <section key={g.id} className={s.group}>
            <div className={`${s.groupHead} ${g.cls}`}>
              {g.label} <span className={`${wb.badge} ${wb.badgeGrey}`}>{list.length}</span>
              <span className={s.groupNote}>{g.note}</span>
            </div>
            {list.map((job) => (
              <JobRow key={job.id} job={job} overdue={g.id === 'overdue'}
                      onComplete={onComplete} onReopen={onReopen} onDelete={onDelete} onSaveRemark={onSaveRemark} />
            ))}
          </section>
        );
      })}
    </div>
  );
}

function JobRow({ job, overdue, onComplete, onReopen, onDelete, onSaveRemark }) {
  const [showRemark, setShowRemark] = useState(Boolean(job.remark));
  const [draft, setDraft] = useState(job.remark || '');
  const [saving, setSaving] = useState(false);

  useEffect(() => { setDraft(job.remark || ''); }, [job.remark]);

  const p = PRIORITY[job.priority] || PRIORITY.medium;
  const done = job.status === 'done';
  const dirty = draft !== (job.remark || '');

  const handleSave = async () => {
    setSaving(true);
    try {
      await onSaveRemark(job.id, draft);
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className={`${s.row} ${done ? s.rowDone : ''}`}>
      <div className={`${s.rowMain} ${p.row}`}>
        <input type="checkbox" className={s.check} checked={done}
               onChange={() => (done ? onReopen(job.id) : onComplete(job.id))}
               title={done ? 'Mark as pending again' : 'Mark as done'}
               aria-label={done ? `Mark "${job.subject}" as pending` : `Mark "${job.subject}" as done`} />
        <div className={`${s.date} ${overdue ? s.dateOverdue : ''}`}>{overdue ? '⚠ ' : ''}{fmtDate(job.due_date)}</div>
        <div className={s.body}>
          <div className={s.subject}>{job.subject}</div>
          {(job.recipient || job.details) && (
            <div className={s.meta}>
              {job.recipient && <span className={s.recipient}>→ {job.recipient}</span>}
              {job.details && <span>{job.details}</span>}
            </div>
          )}
        </div>
        <span className={`${wb.badge} ${p.badge}`}>{p.label}</span>
        <button type="button" onClick={() => setShowRemark((v) => !v)} title="Write / view remark"
                className={`${wb.btn} ${wb.btnSm} ${showRemark ? s.remarkOn : ''}`}>
          📝 Remark{job.remark ? ' ✓' : ''}
        </button>
        <button type="button" onClick={() => onDelete(job.id)} title="Delete" aria-label={`Delete "${job.subject}"`}
                className={wb.iconBtn}>✕</button>
      </div>
      {showRemark && (
        <div className={s.remarkBox}>
          <textarea value={draft} onChange={(e) => setDraft(e.target.value)} rows={2} className={wb.textarea}
                    placeholder="Write a remark — progress notes, blockers, or how/when it was completed…" />
          <div className={s.remarkActions}>
            <button type="button" onClick={handleSave} disabled={!dirty || saving}
                    className={`${wb.btn} ${wb.btnPrimary} ${wb.btnSm}`}>
              {saving ? 'Saving…' : 'Save Remark'}
            </button>
          </div>
        </div>
      )}
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
    <div>
      <div className={s.calHead}>
        <button type="button" onClick={() => goMonth(-1)} className={`${wb.btn} ${wb.btnSm}`}>‹ Prev</button>
        <div className={s.calMonth}>{MONTH_NAMES[mIdx]} {year}</div>
        <button type="button" onClick={() => goMonth(1)} className={`${wb.btn} ${wb.btnSm}`}>Next ›</button>
      </div>
      <div className={s.calGrid}>
        {WEEKDAYS.map((wd) => <div key={wd} className={s.calWd}>{wd}</div>)}
        {cells.map((d, idx) => {
          const iso = d ? `${year}-${String(mIdx + 1).padStart(2, '0')}-${String(d).padStart(2, '0')}` : null;
          const dayJobs = iso ? (jobsByDate[iso] || []) : [];
          const isToday = iso === todayStr;
          return (
            <div key={idx} className={`${s.calCell} ${!d ? s.calBlank : isToday ? s.calToday : ''}`}>
              {d && (
                <>
                  <div className={s.calDay}>{d}</div>
                  {dayJobs.slice(0, 3).map((j) => {
                    const p = PRIORITY[j.priority] || PRIORITY.medium;
                    return (
                      <div key={j.id} title={`${j.subject}${j.recipient ? ' → ' + j.recipient : ''}`}
                           className={`${s.calJob} ${j.status === 'done' ? s.calJobDone : ''}`}
                           style={{ color: p.text, backgroundColor: p.bg, borderLeftColor: p.border }}>
                        {j.subject}
                      </div>
                    );
                  })}
                  {dayJobs.length > 3 && <div className={s.calMore}>+{dayJobs.length - 3} more</div>}
                </>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
