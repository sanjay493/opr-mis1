'use client';

import { useEffect, useState, useCallback } from 'react';
import GlobalNavbar from '@/components/GlobalNavbar';
import RequireAdmin from '@/components/RequireAdmin';
import { API_BASE_URL } from '@/providers/AuthProvider';
import ui from '@/styles/ui.module.css';

// Activity timestamps are stored as UTC ISO strings (auth.py's
// log_activity: datetime.now(timezone.utc).isoformat()); show them in
// Indian Standard Time regardless of the viewer's own timezone. A value
// without an offset is treated as UTC too.
const IST_FORMAT = new Intl.DateTimeFormat('en-IN', {
  timeZone: 'Asia/Kolkata',
  year: 'numeric', month: '2-digit', day: '2-digit',
  hour: '2-digit', minute: '2-digit', second: '2-digit',
  hour12: false,
});

function formatIST(ts) {
  if (!ts) return '';
  const iso = /[zZ]|[+-]\d{2}:?\d{2}$/.test(ts) ? ts : `${ts}Z`;
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? ts : IST_FORMAT.format(d);
}

function ActivityLogInner() {
  const [entries, setEntries] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [userFilter, setUserFilter] = useState('');
  const [actionFilter, setActionFilter] = useState('');
  const [users, setUsers] = useState([]);
  const [actions, setActions] = useState([]);

  useEffect(() => {
    fetch(`${API_BASE_URL}/api/admin/activity-log/filters`, { credentials: 'include' })
      .then((res) => res.json())
      .then((data) => { setUsers(data.users || []); setActions(data.actions || []); })
      .catch(() => {});
  }, []);

  const load = useCallback(async (email, action) => {
    setLoading(true);
    try {
      const params = new URLSearchParams();
      if (email) params.set('user_email', email);
      if (action) params.set('action', action);
      const qs = params.toString() ? `?${params.toString()}` : '';
      const res = await fetch(`${API_BASE_URL}/api/admin/activity-log${qs}`, { credentials: 'include' });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Could not load activity log.');
      setEntries(data.entries);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(userFilter, actionFilter); }, [load, userFilter, actionFilter]);

  const hasFilter = userFilter || actionFilter;
  const clearFilters = () => { setUserFilter(''); setActionFilter(''); };

  return (
    <>
      <GlobalNavbar />
      <main className={`${ui.page} ${ui.pageWide}`}>
        <div className={ui.pageHeader}>
          <h1 className={ui.pageTitle}>Activity Log</h1>
          <p className={ui.pageLead}>
            Every insert, update, or delete performed through a data-entry or admin action.
          </p>
        </div>

        <div className={ui.filterBar}>
          <div className={ui.field}>
            <label htmlFor="activity-user-filter" className={ui.label}>
              User
            </label>
            <select
              id="activity-user-filter" className="form-control"
              value={userFilter} onChange={(e) => setUserFilter(e.target.value)}
              style={{ minWidth: '220px' }}
            >
              <option value="">All users</option>
              {users.map((u) => <option key={u} value={u}>{u}</option>)}
            </select>
          </div>
          <div className={ui.field}>
            <label htmlFor="activity-action-filter" className={ui.label}>
              Action
            </label>
            <select
              id="activity-action-filter" className="form-control"
              value={actionFilter} onChange={(e) => setActionFilter(e.target.value)}
              style={{ minWidth: '180px' }}
            >
              <option value="">All actions</option>
              {actions.map((a) => <option key={a} value={a}>{a}</option>)}
            </select>
          </div>
          {hasFilter && (
            <button type="button" className={`${ui.btn} ${ui.btnSecondary}`} onClick={clearFilters}>
              Clear filters
            </button>
          )}
        </div>
        <p className={ui.meta} aria-live="polite">
          {loading ? 'Loading…' : `Showing ${entries.length} entr${entries.length === 1 ? 'y' : 'ies'}${hasFilter ? ' matching the filters above' : ''}.`}
        </p>

        {error && <p role="alert" className={`${ui.alert} ${ui.alertError}`}>{error}</p>}

        {!loading && (
          <div className={ui.tableWrap}>
          <table className={ui.table}>
            <thead>
              <tr>
                <th scope="col">When (IST)</th>
                <th scope="col">User</th>
                <th scope="col">Action</th>
                <th scope="col">Where</th>
                <th scope="col">Details</th>
              </tr>
            </thead>
            <tbody>
              {entries.map((entry) => (
                <tr key={entry.id}>
                  <td className={ui.nowrap}>{formatIST(entry.timestamp)}</td>
                  <td>{entry.user_name || entry.user_email || '—'}</td>
                  <td>{entry.action}</td>
                  <td>{entry.entity}</td>
                  <td className={ui.muted}>{entry.details}</td>
                </tr>
              ))}
              {entries.length === 0 && (
                <tr><td colSpan={5} className={ui.emptyCell}>No activity recorded yet.</td></tr>
              )}
            </tbody>
          </table>
          </div>
        )}
      </main>
    </>
  );
}

export default function ActivityLogPage() {
  return (
    <RequireAdmin>
      <ActivityLogInner />
    </RequireAdmin>
  );
}
