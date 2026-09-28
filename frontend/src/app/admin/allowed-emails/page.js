'use client';

import { useEffect, useState, useCallback } from 'react';
import GlobalNavbar from '@/components/GlobalNavbar';
import RequireAdmin from '@/components/RequireAdmin';
import { API_BASE_URL } from '@/providers/AuthProvider';
import ui from '@/styles/ui.module.css';

function AllowedEmailsInner() {
  const [emails, setEmails] = useState([]);
  const [newEmail, setNewEmail] = useState('');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const res = await fetch(`${API_BASE_URL}/api/admin/allowed-emails`, { credentials: 'include' });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Could not load list.');
      setEmails(data.emails);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const addEmail = async (e) => {
    e.preventDefault();
    setError('');
    try {
      const res = await fetch(`${API_BASE_URL}/api/admin/allowed-emails`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({ email: newEmail }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Could not add email.');
      setNewEmail('');
      await load();
    } catch (err) {
      setError(err.message);
    }
  };

  const toggleBar = async (email, barred) => {
    setError('');
    try {
      const res = await fetch(`${API_BASE_URL}/api/admin/allowed-emails/${encodeURIComponent(email)}/bar`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({ barred: !barred }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Could not update.');
      await load();
    } catch (err) {
      setError(err.message);
    }
  };

  const removeEmail = async (email) => {
    if (!confirm(`Remove ${email} from the allow-list? They will need to be re-added to register again.`)) return;
    setError('');
    try {
      const res = await fetch(`${API_BASE_URL}/api/admin/allowed-emails/${encodeURIComponent(email)}`, {
        method: 'DELETE',
        credentials: 'include',
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Could not remove.');
      await load();
    } catch (err) {
      setError(err.message);
    }
  };

  return (
    <>
      <GlobalNavbar />
      <main className={`${ui.page} ${ui.pageNarrow}`}>
        <div className={ui.pageHeader}>
          <h1 className={ui.pageTitle}>Allowed Emails</h1>
          <p className={ui.pageLead}>
            Only emails listed here (and not barred) may register an account.
          </p>
        </div>

        <form onSubmit={addEmail} className={ui.inlineForm}>
          <label htmlFor="allowed-email-new" className={ui.srOnly}>Email to allow</label>
          <input
            id="allowed-email-new" type="email" className="form-control" placeholder="name@example.com" required
            value={newEmail} onChange={(e) => setNewEmail(e.target.value)}
          />
          <button type="submit" className={`${ui.btn} ${ui.btnPrimary}`}>Add</button>
        </form>

        {error && <p role="alert" className={`${ui.alert} ${ui.alertError}`}>{error}</p>}

        {loading ? (
          <p className={ui.meta} aria-live="polite">Loading…</p>
        ) : (
          <div className={ui.tableWrap}>
          <table className={ui.table}>
            <thead>
              <tr>
                <th scope="col">Email</th>
                <th scope="col">Status</th>
                <th scope="col">Added by</th>
                <th scope="col"><span className={ui.srOnly}>Actions</span></th>
              </tr>
            </thead>
            <tbody>
              {emails.map((e) => (
                <tr key={e.email}>
                  <td>{e.email}</td>
                  <td>
                    {e.barred ? (
                      <span className={`${ui.badge} ${ui.badgeDanger}`}>Barred</span>
                    ) : (
                      <span className={`${ui.badge} ${ui.badgeSuccess}`}>Allowed</span>
                    )}
                  </td>
                  <td className={ui.muted}>{e.added_by || ''}</td>
                  <td>
                    <div className={ui.actions}>
                      <button type="button" className={`${ui.btn} ${ui.btnSecondary} ${ui.btnSm}`}
                              aria-label={`${e.barred ? 'Unbar' : 'Bar'} ${e.email}`}
                              onClick={() => toggleBar(e.email, e.barred)}>
                        {e.barred ? 'Unbar' : 'Bar'}
                      </button>
                      <button type="button" className={`${ui.btn} ${ui.btnDanger} ${ui.btnSm}`}
                              aria-label={`Remove ${e.email}`}
                              onClick={() => removeEmail(e.email)}>
                        Remove
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
              {emails.length === 0 && (
                <tr><td colSpan={4} className={ui.emptyCell}>No emails on the list yet.</td></tr>
              )}
            </tbody>
          </table>
          </div>
        )}
      </main>
    </>
  );
}

export default function AllowedEmailsPage() {
  return (
    <RequireAdmin>
      <AllowedEmailsInner />
    </RequireAdmin>
  );
}
