'use client';

import { useEffect, useState, useCallback, useMemo } from 'react';
import GlobalNavbar from '@/components/GlobalNavbar';
import RequireAdmin from '@/components/RequireAdmin';
import { API_BASE_URL } from '@/providers/AuthProvider';

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
      <main style={{ maxWidth: '1100px', margin: '0 auto', padding: '40px 20px', height: 'calc(100vh - 72px)', overflowY: 'auto' }}>
        <h1 style={{ fontSize: '20pt', marginBottom: '4px' }}>Site Visits</h1>
        <p style={{ color: '#5f6368', marginBottom: '20px' }}>
          Every visitor — logged-in users by name/email, anonymous viewers by IP address — and the pages they've visited.
        </p>

        <div style={{ display: 'flex', gap: '16px', alignItems: 'flex-end', flexWrap: 'wrap', marginBottom: '12px' }}>
          <div>
            <label htmlFor="visits-days-filter" style={{ display: 'block', fontSize: '9pt', fontWeight: 600, color: '#5f6368', marginBottom: '4px' }}>
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
          <div>
            <label htmlFor="visits-search" style={{ display: 'block', fontSize: '9pt', fontWeight: 600, color: '#5f6368', marginBottom: '4px' }}>
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
        <p style={{ color: '#5f6368', fontSize: '9pt', marginBottom: '20px' }}>
          {loading ? 'Loading…' : `Showing ${filtered.length} visitor${filtered.length === 1 ? '' : 's'}${search ? ' matching your search' : ''}.`}
        </p>

        {error && <p style={{ color: '#d93025', marginBottom: '12px' }}>{error}</p>}

        {loading ? (
          <p>Loading…</p>
        ) : (
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '10pt' }}>
            <thead>
              <tr style={{ textAlign: 'left', borderBottom: '2px solid #dadce0' }}>
                <th style={{ padding: '8px' }}>Visitor</th>
                <th style={{ padding: '8px' }}>IP Address</th>
                <th style={{ padding: '8px' }}>Status</th>
                <th style={{ padding: '8px' }}>First seen</th>
                <th style={{ padding: '8px' }}>Last seen</th>
                <th style={{ padding: '8px' }}>Visits</th>
                <th style={{ padding: '8px' }}>Pages visited</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((v) => (
                <tr key={v.key} style={{ borderBottom: '1px solid #e8eaed' }}>
                  <td style={{ padding: '8px' }}>{v.user_name || v.user_email || 'Anonymous'}</td>
                  <td style={{ padding: '8px', whiteSpace: 'nowrap' }}>{v.ip_address || '—'}</td>
                  <td style={{ padding: '8px' }}>
                    <span style={{
                      padding: '2px 8px', borderRadius: '10px', fontSize: '8pt', fontWeight: 600,
                      backgroundColor: v.is_logged_in ? '#e6f4ea' : '#fce8e6',
                      color: v.is_logged_in ? '#188038' : '#c5221f',
                    }}>
                      {v.is_logged_in ? 'Logged in' : 'Anonymous'}
                    </span>
                  </td>
                  <td style={{ padding: '8px', whiteSpace: 'nowrap' }}>{fmt(v.first_seen)}</td>
                  <td style={{ padding: '8px', whiteSpace: 'nowrap' }}>{fmt(v.last_seen)}</td>
                  <td style={{ padding: '8px', textAlign: 'right' }}>{v.visit_count}</td>
                  <td style={{ padding: '8px', maxWidth: '340px' }}>
                    <div style={{ maxHeight: '110px', overflowY: 'auto' }}>
                      {v.pages.map((p) => (
                        <div key={p.path} style={{ whiteSpace: 'nowrap', color: '#3c4043' }}>
                          {p.path} <span style={{ color: '#5f6368' }}>×{p.count}</span>
                        </div>
                      ))}
                    </div>
                  </td>
                </tr>
              ))}
              {filtered.length === 0 && (
                <tr><td colSpan={7} style={{ padding: '20px', textAlign: 'center', color: '#5f6368' }}>No visits recorded in this window.</td></tr>
              )}
            </tbody>
          </table>
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
