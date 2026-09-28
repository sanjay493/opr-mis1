'use client';

import { Fragment, useEffect, useState, useCallback } from 'react';
import GlobalNavbar from '@/components/GlobalNavbar';
import RequireAdmin from '@/components/RequireAdmin';
import { API_BASE_URL } from '@/providers/AuthProvider';
import ui from '@/styles/ui.module.css';

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
      <main className={ui.page}>
        <div className={ui.pageHeader}>
          <h1 className={ui.pageTitle}>Manage Users</h1>
          <p className={ui.pageLead}>
            Assign Editor or Administrator access, or remove an account. A blank role means view-only access.
          </p>
        </div>

        {error && <p role="alert" className={`${ui.alert} ${ui.alertError}`}>{error}</p>}
        {loading ? (
          <p className={ui.meta} aria-live="polite">Loading…</p>
        ) : (
          <div className={ui.tableWrap}>
          <table className={ui.table}>
            <thead>
              <tr>
                <th scope="col">Name</th>
                <th scope="col">Email</th>
                <th scope="col">Role</th>
                <th scope="col">Permissions</th>
                <th scope="col">Registered</th>
                <th scope="col"><span className={ui.srOnly}>Actions</span></th>
              </tr>
            </thead>
            <tbody>
              {users.map((u) => (
                <Fragment key={u.id}>
                  <tr>
                    <td>{u.name || '—'}</td>
                    <td>{u.email}</td>
                    <td>
                      <select
                        className="form-control"
                        value={u.role || ''}
                        onChange={(e) => setRole(u.id, e.target.value)}
                        aria-label={`Role for ${u.email}`}
                        style={{ padding: '4px 8px', minWidth: 170 }}
                      >
                        <option value="">(none — view only)</option>
                        <option value="editor">Editor</option>
                        <option value="admin">Administrator</option>
                      </select>
                    </td>
                    <td className={ui.muted}>
                      {u.role === 'editor' ? (
                        <div className={ui.actions} style={{ alignItems: 'center' }}>
                          <span>{permissionsSummary(u)}</span>
                          <button
                            type="button"
                            className={`${ui.btn} ${ui.btnSecondary} ${ui.btnSm}`}
                            aria-expanded={editingId === u.id}
                            aria-label={`Edit permissions for ${u.email}`}
                            onClick={() => (editingId === u.id ? cancelEdit() : openEdit(u))}
                          >
                            Edit
                          </button>
                        </div>
                      ) : (
                        permissionsSummary(u)
                      )}
                    </td>
                    <td className={`${ui.muted} ${ui.nowrap}`}>
                      {u.created_at ? u.created_at.slice(0, 10) : ''}
                    </td>
                    <td>
                      <button
                        type="button"
                        className={`${ui.btn} ${ui.btnDanger} ${ui.btnSm}`}
                        aria-label={`Delete account ${u.email}`}
                        onClick={() => deleteUser(u.id, u.email)}
                      >
                        Delete
                      </button>
                    </td>
                  </tr>
                  {editingId === u.id && (
                    <tr className={ui.expandRow}>
                      <td colSpan={6} style={{ padding: '16px 20px' }}>
                        <fieldset style={{ border: 'none', margin: 0, padding: 0, maxWidth: '420px' }}>
                          <legend className={ui.label}>Permissions for {u.email}</legend>
                          <label className={ui.checkRow} style={{ fontWeight: 600 }}>
                            <input
                              type="checkbox"
                              checked={editForm.allPages}
                              onChange={(e) => setEditForm((f) => ({ ...f, allPages: e.target.checked }))}
                            />
                            All pages
                          </label>
                          {!editForm.allPages && (
                            <div style={{ marginLeft: '24px', marginBottom: '8px' }}>
                              {pageModules.map((m) => (
                                <label key={m.key} className={ui.checkRow}>
                                  <input
                                    type="checkbox"
                                    checked={editForm.selectedPages.includes(m.key)}
                                    onChange={() => toggleModule(m.key)}
                                  />
                                  {m.label}
                                </label>
                              ))}
                            </div>
                          )}
                          <label className={ui.checkRow} style={{ marginBottom: '16px' }}>
                            <input
                              type="checkbox"
                              checked={editForm.canDelete}
                              onChange={(e) => setEditForm((f) => ({ ...f, canDelete: e.target.checked }))}
                            />
                            Can delete
                          </label>
                          <div className={ui.actions}>
                            <button
                              type="button"
                              className={`${ui.btn} ${ui.btnPrimary}`}
                              disabled={saving} aria-busy={saving}
                              onClick={() => savePermissions(u.id)}
                            >
                              {saving ? 'Saving…' : 'Save'}
                            </button>
                            <button type="button" className={`${ui.btn} ${ui.btnSecondary}`} onClick={cancelEdit}>
                              Cancel
                            </button>
                          </div>
                        </fieldset>
                      </td>
                    </tr>
                  )}
                </Fragment>
              ))}
              {users.length === 0 && (
                <tr><td colSpan={6} className={ui.emptyCell}>No registered users yet.</td></tr>
              )}
            </tbody>
          </table>
          </div>
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
