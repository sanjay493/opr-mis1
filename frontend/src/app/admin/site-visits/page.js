'use client';

import { useEffect, useState, useCallback, useMemo } from 'react';
import GlobalNavbar from '@/components/GlobalNavbar';
import RequireAdmin from '@/components/RequireAdmin';
import { API_BASE_URL } from '@/providers/AuthProvider';
import ui from '@/styles/ui.module.css';

const DAYS_OPTIONS = [
  { value: 1, label: 'Today' },
  { value: 7, label: 'Last 7 days' },
  { value: 30, label: 'Last 30 days' },
  { value: 90, label: 'Last 90 days' },
  { value: 0, label: 'All time' },
];

function fmt(ts) {
  return ts ? ts.replace('T', ' ').slice(0, 19) : '—';
}

function SiteVisitsInner() {
  const [visitors, setVisitors] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [days, setDays] = useState(30);
  const [search, setSearch] = useState('');

  const load = useCallback(async (d) => {
    setLoading(true);
    try {
      const res = await fetch(`${API_BASE_URL}/api/admin/site-visits?days=${d}`, { credentials: 'include' });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Could not load the site-visit log.');
      setVisitors(data.visitors);
      setError('');
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(days); }, [load, days]);

  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase();
    if (!q) return visitors;
    return visitors.filter((v) =>
      (v.user_name || '').toLowerCase().includes(q) ||
      (v.user_email || '').toLowerCase().includes(q) ||
      (v.ip_address || '').toLowerCase().includes(q)
    );
  }, [visitors, search]);

  return (
    <>
      <GlobalNavbar />
      <main className={`${ui.page} ${ui.pageWide}`}>
        <div className={ui.pageHeader}>
          <h1 className={ui.pageTitle}>Site Visits</h1>
          <p className={ui.pageLead}>
            Every visitor — logged-in users by name/email, anonymous viewers by IP address — and the pages they&apos;ve visited.
          </p>
        </div>

        <div className={ui.filterBar}>
          <div className={ui.field}>
            <label htmlFor="visits-days-filter" className={ui.label}>
              Window
            </label>
            <select
              id="visits-days-filter" className="form-control"
              value={days} onChange={(e) => setDays(Number(e.target.value))}
              style={{ minWidth: '160px' }}
            >
              {DAYS_OPTIONS.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
            </select>
          </div>
          <div className={ui.field}>
            <label htmlFor="visits-search" className={ui.label}>
              Search
            </label>
            <input
              id="visits-search" className="form-control" type="text"
              placeholder="Name, email, or IP" value={search}
              onChange={(e) => setSearch(e.target.value)}
              style={{ minWidth: '220px' }}
            />
          </div>
        </div>
        <p className={ui.meta} aria-live="polite">
          {loading ? 'Loading…' : `Showing ${filtered.length} visitor${filtered.length === 1 ? '' : 's'}${search ? ' matching your search' : ''}.`}
        </p>

        {error && <p role="alert" className={`${ui.alert} ${ui.alertError}`}>{error}</p>}

        {!loading && (
          <div className={ui.tableWrap}>
          <table className={ui.table}>
            <thead>
              <tr>
                <th scope="col">Visitor</th>
                <th scope="col">IP Address</th>
                <th scope="col">Status</th>
                <th scope="col">First seen</th>
                <th scope="col">Last seen</th>
                <th scope="col" className={ui.numeric}>Visits</th>
                <th scope="col">Pages visited</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((v) => (
                <tr key={v.key}>
                  <td>{v.user_name || v.user_email || 'Anonymous'}</td>
                  <td className={`${ui.nowrap} ${ui.mono}`}>{v.ip_address || '—'}</td>
                  <td>
                    <span className={`${ui.badge} ${v.is_logged_in ? ui.badgeSuccess : ui.badgeNeutral}`}>
                      {v.is_logged_in ? 'Logged in' : 'Anonymous'}
                    </span>
                  </td>
                  <td className={ui.nowrap}>{fmt(v.first_seen)}</td>
                  <td className={ui.nowrap}>{fmt(v.last_seen)}</td>
                  <td className={ui.numeric}>{v.visit_count}</td>
                  <td style={{ maxWidth: '340px' }}>
                    <div style={{ maxHeight: '110px', overflowY: 'auto' }}>
                      {v.pages.map((p) => (
                        <div key={p.path} className={ui.nowrap}>
                          {p.path} <span className={ui.muted}>×{p.count}</span>
                        </div>
                      ))}
                    </div>
                  </td>
                </tr>
              ))}
              {filtered.length === 0 && (
                <tr><td colSpan={7} className={ui.emptyCell}>No visits recorded in this window.</td></tr>
              )}
            </tbody>
          </table>
          </div>
        )}
      </main>
    </>
  );
}

export default function SiteVisitsPage() {
  return (
    <RequireAdmin>
      <SiteVisitsInner />
    </RequireAdmin>
  );
}
