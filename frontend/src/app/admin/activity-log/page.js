'use client';

import { useEffect, useState, useCallback } from 'react';
import GlobalNavbar from '@/components/GlobalNavbar';
import RequireAdmin from '@/components/RequireAdmin';
import { API_BASE_URL } from '@/providers/AuthProvider';

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
      <main style={{ maxWidth: '1000px', margin: '0 auto', padding: '40px 20px', height: 'calc(100vh - 72px)', overflowY: 'auto' }}>
        <h1 style={{ fontSize: '20pt', marginBottom: '4px' }}>Activity Log</h1>
        <p style={{ color: '#5f6368', marginBottom: '20px' }}>
          Every insert, update, or delete performed through a data-entry or admin action.
        </p>

        <div style={{ display: 'flex', gap: '16px', alignItems: 'flex-end', flexWrap: 'wrap', marginBottom: '12px' }}>
          <div>
            <label htmlFor="activity-user-filter" style={{ display: 'block', fontSize: '9pt', fontWeight: 600, color: '#5f6368', marginBottom: '4px' }}>
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
          <div>
            <label htmlFor="activity-action-filter" style={{ display: 'block', fontSize: '9pt', fontWeight: 600, color: '#5f6368', marginBottom: '4px' }}>
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
            <button type="button" className="btn btn-secondary" onClick={clearFilters} style={{ margin: 0 }}>
              Clear filters
            </button>
          )}
        </div>
        <p style={{ color: '#5f6368', fontSize: '9pt', marginBottom: '20px' }}>
          {loading ? 'Loading…' : `Showing ${entries.length} entr${entries.length === 1 ? 'y' : 'ies'}${hasFilter ? ' matching the filters above' : ''}.`}
        </p>

        {error && <p style={{ color: '#d93025', marginBottom: '12px' }}>{error}</p>}

        {loading ? (
          <p>Loading…</p>
        ) : (
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '10pt' }}>
            <thead>
              <tr style={{ textAlign: 'left', borderBottom: '2px solid #dadce0' }}>
                <th style={{ padding: '8px' }}>When</th>
                <th style={{ padding: '8px' }}>User</th>
                <th style={{ padding: '8px' }}>Action</th>
                <th style={{ padding: '8px' }}>Where</th>
                <th style={{ padding: '8px' }}>Details</th>
              </tr>
            </thead>
            <tbody>
              {entries.map((entry) => (
                <tr key={entry.id} style={{ borderBottom: '1px solid #e8eaed' }}>
                  <td style={{ padding: '8px', whiteSpace: 'nowrap' }}>{entry.timestamp?.replace('T', ' ').slice(0, 19)}</td>
                  <td style={{ padding: '8px' }}>{entry.user_name || entry.user_email || '—'}</td>
                  <td style={{ padding: '8px' }}>{entry.action}</td>
                  <td style={{ padding: '8px' }}>{entry.entity}</td>
                  <td style={{ padding: '8px', color: '#5f6368' }}>{entry.details}</td>
                </tr>
              ))}
              {entries.length === 0 && (
                <tr><td colSpan={5} style={{ padding: '20px', textAlign: 'center', color: '#5f6368' }}>No activity recorded yet.</td></tr>
              )}
            </tbody>
          </table>
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
