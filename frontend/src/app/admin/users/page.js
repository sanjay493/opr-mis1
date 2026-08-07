'use client';

import { Fragment, useEffect, useState, useCallback } from 'react';
import GlobalNavbar from '@/components/GlobalNavbar';
import RequireAdmin from '@/components/RequireAdmin';
import { API_BASE_URL } from '@/providers/AuthProvider';

function ManageUsersInner() {
  const [users, setUsers] = useState([]);
  const [pageModules, setPageModules] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [editingId, setEditingId] = useState(null);
  const [editForm, setEditForm] = useState({ allPages: true, selectedPages: [], canDelete: true });
  const [saving, setSaving] = useState(false);

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

  useEffect(() => {
    fetch(`${API_BASE_URL}/api/admin/page-modules`, { credentials: 'include' })
      .then((res) => res.json())
      .then((data) => setPageModules(data.modules || []))
      .catch(() => {});
  }, []);

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

  const openEdit = (u) => {
    setError('');
    setEditingId(u.id);
    setEditForm({
      allPages: !u.allowed_pages,
      selectedPages: u.allowed_pages || [],
      canDelete: u.can_delete !== false,
    });
  };

  const cancelEdit = () => setEditingId(null);

  const toggleModule = (key) => {
    setEditForm((f) => ({
      ...f,
      selectedPages: f.selectedPages.includes(key)
        ? f.selectedPages.filter((k) => k !== key)
        : [...f.selectedPages, key],
    }));
  };

  const savePermissions = async (id) => {
    setError('');
    setSaving(true);
    try {
      const res = await fetch(`${API_BASE_URL}/api/admin/users/${id}/permissions`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({
          allowed_pages: editForm.allPages ? null : editForm.selectedPages,
          can_delete: editForm.canDelete,
        }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Could not update permissions.');
      setEditingId(null);
      await load();
    } catch (err) {
      setError(err.message);
    } finally {
      setSaving(false);
    }
  };

  const permissionsSummary = (u) => {
    if (u.role !== 'editor') return '— full access —';
    const pagesText = u.allowed_pages ? `${u.allowed_pages.length} of ${pageModules.length} pages` : 'All pages';
    const deleteText = u.can_delete ? 'can delete' : 'no delete';
    return `${pagesText} · ${deleteText}`;
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
                <th style={{ padding: '8px' }}>Permissions</th>
                <th style={{ padding: '8px' }}>Registered</th>
                <th style={{ padding: '8px' }}></th>
              </tr>
            </thead>
            <tbody>
              {users.map((u) => (
                <Fragment key={u.id}>
                  <tr style={{ borderBottom: '1px solid #e8eaed' }}>
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
                      {u.role === 'editor' ? (
                        <>
                          {permissionsSummary(u)}
                          {' '}
                          <button
                            className="btn btn-secondary"
                            style={{ padding: '2px 8px', fontSize: '9.5pt' }}
                            onClick={() => openEdit(u)}
                          >
                            Edit
                          </button>
                        </>
                      ) : (
                        permissionsSummary(u)
                      )}
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
                  {editingId === u.id && (
                    <tr style={{ borderBottom: '1px solid #e8eaed', background: '#f8f9fa' }}>
                      <td colSpan={6} style={{ padding: '16px' }}>
                        <div style={{ maxWidth: '420px' }}>
                          <label style={{ display: 'block', marginBottom: '8px', fontWeight: 600 }}>
                            <input
                              type="checkbox"
                              checked={editForm.allPages}
                              onChange={(e) => setEditForm((f) => ({ ...f, allPages: e.target.checked }))}
                            />
                            {' '}All pages
                          </label>
                          {!editForm.allPages && (
                            <div style={{ marginLeft: '22px', marginBottom: '12px' }}>
                              {pageModules.map((m) => (
                                <label key={m.key} style={{ display: 'block', marginBottom: '4px' }}>
                                  <input
                                    type="checkbox"
                                    checked={editForm.selectedPages.includes(m.key)}
                                    onChange={() => toggleModule(m.key)}
                                  />
                                  {' '}{m.label}
                                </label>
                              ))}
                            </div>
                          )}
                          <label style={{ display: 'block', marginBottom: '16px' }}>
                            <input
                              type="checkbox"
                              checked={editForm.canDelete}
                              onChange={(e) => setEditForm((f) => ({ ...f, canDelete: e.target.checked }))}
                            />
                            {' '}Can delete
                          </label>
                          <button
                            className="btn btn-primary"
                            style={{ marginRight: '8px' }}
                            disabled={saving}
                            onClick={() => savePermissions(u.id)}
                          >
                            {saving ? 'Saving…' : 'Save'}
                          </button>
                          <button className="btn btn-secondary" onClick={cancelEdit}>Cancel</button>
                        </div>
                      </td>
                    </tr>
                  )}
                </Fragment>
              ))}
              {users.length === 0 && (
                <tr><td colSpan={6} style={{ padding: '20px', textAlign: 'center', color: '#5f6368' }}>No registered users yet.</td></tr>
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
