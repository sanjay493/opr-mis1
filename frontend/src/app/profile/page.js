'use client';

import { useState } from 'react';
import Link from 'next/link';
import GlobalNavbar from '@/components/GlobalNavbar';
import RequireAuth from '@/components/RequireAuth';
import { useAuth, API_BASE_URL } from '@/providers/AuthProvider';
import ui from '@/styles/ui.module.css';

function ProfilePageInner() {
  const { user, refresh } = useAuth();
  const [name, setName] = useState(user?.name || '');
  const [file, setFile] = useState(null);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');

  const picUrl = user?.profile_pic ? `${API_BASE_URL}/static/profile_pics/${user.profile_pic}` : null;

  const handleSave = async (e) => {
    e.preventDefault();
    setSaving(true);
    setError('');
    setMessage('');
    try {
      const form = new FormData();
      form.append('name', name);
      if (file) form.append('picture', file);
      const res = await fetch(`${API_BASE_URL}/api/auth/profile`, {
        method: 'PUT',
        credentials: 'include',
        body: form,
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Could not update profile.');
      await refresh();
      setMessage('Profile updated.');
      setFile(null);
    } catch (err) {
      setError(err.message);
    } finally {
      setSaving(false);
    }
  };

  return (
    <>
      <GlobalNavbar />
      <main className={ui.authShell}>
        <div className={`${ui.authCard} ${ui.authCardWide}`}>
          <div className={ui.pageHeader}>
            <h1 className={ui.pageTitle}>My Profile</h1>
            <p className={ui.pageLead}>{user?.email}</p>
          </div>

          <div className={ui.identity}>
            <div className={ui.avatar} aria-hidden={!picUrl}>
              {picUrl ? (
                // eslint-disable-next-line @next/next/no-img-element
                <img src={picUrl} alt="Your profile picture" />
              ) : (user?.name || user?.email || '?')[0].toUpperCase()}
            </div>
            <div>
              <div className={ui.identityName}>{user?.name || '(no name set)'}</div>
              <div style={{ marginTop: 4 }}>
                <span className={`${ui.badge} ${user?.role ? ui.badgeSuccess : ui.badgeNeutral}`}
                      style={{ textTransform: 'capitalize' }}>
                  {user?.role || 'View only (not yet assigned)'}
                </span>
              </div>
            </div>
          </div>

          <form onSubmit={handleSave}>
            <div className={ui.field}>
              <label htmlFor="profile-name" className={ui.label}>Name</label>
              <input
                id="profile-name" type="text" className="form-control"
                value={name} onChange={(e) => setName(e.target.value)}
                autoComplete="name"
              />
            </div>
            <div className={ui.field}>
              <label htmlFor="profile-picture" className={ui.label}>Profile picture</label>
              <input
                id="profile-picture" type="file" accept="image/*" className="form-control"
                onChange={(e) => setFile(e.target.files?.[0] || null)}
              />
            </div>
            {error && <p role="alert" className={`${ui.alert} ${ui.alertError}`}>{error}</p>}
            {message && <p role="status" className={`${ui.alert} ${ui.alertSuccess}`}>{message}</p>}
            <button type="submit" className={`${ui.btn} ${ui.btnPrimary}`}
                    disabled={saving} aria-busy={saving}>
              {saving ? 'Saving…' : 'Save Changes'}
            </button>
          </form>

          <div className={ui.cardFooter}>
            <Link href="/forgot-password" className={`${ui.btn} ${ui.btnSecondary}`}>Change Password</Link>
            <p className={ui.hint}>
              Password changes are always verified by a passcode emailed to you.
            </p>
          </div>
        </div>
      </main>
    </>
  );
}

export default function ProfilePage() {
  return (
    <RequireAuth>
      <ProfilePageInner />
    </RequireAuth>
  );
}
