'use client';

import { useEffect, useState, useCallback } from 'react';
import GlobalNavbar from '@/components/GlobalNavbar';
import RequireAdmin from '@/components/RequireAdmin';
import { API_BASE_URL } from '@/providers/AuthProvider';

function ManageUsersInner() {
  const [users, setUsers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const res = await fetch(`${API_BASE_URL}/api/admin/users`, { credentials: 'include' });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Could not load users.');
      setUsers(data.users);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const setRole = async (id, role) => {
    setError('');
    try {
      const res = await fetch(`${API_BASE_URL}/api/admin/users/${id}/role`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({ role: role || null }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Could not update role.');
      await load();
    } catch (err) {
      setError(err.message);
    }
  };

  const deleteUser = async (id, email) => {
    if (!confirm(`Delete the account for ${email}? This cannot be undone.`)) return;
    setError('');
    try {
      const res = await fetch(`${API_BASE_URL}/api/admin/users/${id}`, {
        method: 'DELETE',
        credentials: 'include',
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Could not delete user.');
      await load();
    } catch (err) {
      setError(err.message);
    }
  };

  return (
    <>
      <GlobalNavbar />
      <main style={{ maxWidth: '900px', margin: '0 auto', padding: '40px 20px', height: 'calc(100vh - 72px)', overflowY: 'auto' }}>
        <h1 style={{ fontSize: '20pt', marginBottom: '4px' }}>Manage Users</h1>
        <p style={{ color: '#5f6368', marginBottom: '24px' }}>
          Assign Editor or Administrator access, or remove an account. A blank role means view-only access.
        </p>

        {error && <p style={{ color: '#d93025', marginBottom: '12px' }}>{error}</p>}
        {loading ? (
          <p>Loading…</p>
        ) : (
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead>
              <tr style={{ textAlign: 'left', borderBottom: '2px solid #dadce0' }}>
                <th style={{ padding: '8px' }}>Name</th>
                <th style={{ padding: '8px' }}>Email</th>
                <th style={{ padding: '8px' }}>Role</th>
                <th style={{ padding: '8px' }}>Registered</th>
                <th style={{ padding: '8px' }}></th>
              </tr>
            </thead>
            <tbody>
              {users.map((u) => (
                <tr key={u.id} style={{ borderBottom: '1px solid #e8eaed' }}>
                  <td style={{ padding: '8px' }}>{u.name || '—'}</td>
                  <td style={{ padding: '8px' }}>{u.email}</td>
                  <td style={{ padding: '8px' }}>
                    <select
                      className="form-control"
                      value={u.role || ''}
                      onChange={(e) => setRole(u.id, e.target.value)}
                      style={{ padding: '4px 8px' }}
                    >
                      <option value="">(none — view only)</option>
                      <option value="editor">Editor</option>
                      <option value="admin">Administrator</option>
                    </select>
                  </td>
                  <td style={{ padding: '8px', fontSize: '9.5pt', color: '#5f6368' }}>
                    {u.created_at ? u.created_at.slice(0, 10) : ''}
                  </td>
                  <td style={{ padding: '8px' }}>
                    <button
                      className="btn btn-secondary"
                      style={{ color: '#c5221f', borderColor: '#c5221f' }}
                      onClick={() => deleteUser(u.id, u.email)}
                    >
                      Delete
                    </button>
                  </td>
                </tr>
              ))}
              {users.length === 0 && (
                <tr><td colSpan={5} style={{ padding: '20px', textAlign: 'center', color: '#5f6368' }}>No registered users yet.</td></tr>
              )}
            </tbody>
          </table>
        )}
      </main>
    </>
  );
}

export default function ManageUsersPage() {
  return (
    <RequireAdmin>
      <ManageUsersInner />
    </RequireAdmin>
  );
}
