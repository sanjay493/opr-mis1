'use client';

import { useEffect, useState, useCallback } from 'react';
import GlobalNavbar from '@/components/GlobalNavbar';
import RequireAdmin from '@/components/RequireAdmin';
import { API_BASE_URL } from '@/providers/AuthProvider';

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
      <main style={{ maxWidth: '700px', margin: '0 auto', padding: '40px 20px', height: 'calc(100vh - 72px)', overflowY: 'auto' }}>
        <h1 style={{ fontSize: '20pt', marginBottom: '4px' }}>Allowed Emails</h1>
        <p style={{ color: '#5f6368', marginBottom: '24px' }}>
          Only emails listed here (and not barred) may register an account.
        </p>

        <form onSubmit={addEmail} style={{ display: 'flex', gap: '8px', marginBottom: '20px' }}>
          <input
            type="email" className="form-control" placeholder="name@example.com" required
            value={newEmail} onChange={(e) => setNewEmail(e.target.value)}
            style={{ flex: 1 }}
          />
          <button type="submit" className="btn btn-primary" style={{ margin: 0 }}>Add</button>
        </form>

        {error && <p style={{ color: '#d93025', marginBottom: '12px' }}>{error}</p>}

        {loading ? (
          <p>Loading…</p>
        ) : (
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead>
              <tr style={{ textAlign: 'left', borderBottom: '2px solid #dadce0' }}>
                <th style={{ padding: '8px' }}>Email</th>
                <th style={{ padding: '8px' }}>Status</th>
                <th style={{ padding: '8px' }}>Added by</th>
                <th style={{ padding: '8px' }}></th>
              </tr>
            </thead>
            <tbody>
              {emails.map((e) => (
                <tr key={e.email} style={{ borderBottom: '1px solid #e8eaed' }}>
                  <td style={{ padding: '8px' }}>{e.email}</td>
                  <td style={{ padding: '8px' }}>
                    {e.barred ? (
                      <span style={{ color: '#c5221f', fontWeight: 600 }}>Barred</span>
                    ) : (
                      <span style={{ color: '#188038', fontWeight: 600 }}>Allowed</span>
                    )}
                  </td>
                  <td style={{ padding: '8px', fontSize: '9.5pt', color: '#5f6368' }}>{e.added_by || ''}</td>
                  <td style={{ padding: '8px', display: 'flex', gap: '8px' }}>
                    <button className="btn btn-secondary" onClick={() => toggleBar(e.email, e.barred)}>
                      {e.barred ? 'Unbar' : 'Bar'}
                    </button>
                    <button
                      className="btn btn-secondary"
                      style={{ color: '#c5221f', borderColor: '#c5221f' }}
                      onClick={() => removeEmail(e.email)}
                    >
                      Remove
                    </button>
                  </td>
                </tr>
              ))}
              {emails.length === 0 && (
                <tr><td colSpan={4} style={{ padding: '20px', textAlign: 'center', color: '#5f6368' }}>No emails on the list yet.</td></tr>
              )}
            </tbody>
          </table>
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
