'use client';

import { useState } from 'react';
import Link from 'next/link';
import GlobalNavbar from '@/components/GlobalNavbar';
import RequireAuth from '@/components/RequireAuth';
import { useAuth, API_BASE_URL } from '@/providers/AuthProvider';

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
      <main style={{ maxWidth: '480px', margin: '60px auto', padding: '0 20px' }}>
        <h1 style={{ fontSize: '20pt', marginBottom: '4px' }}>My Profile</h1>
        <p style={{ color: '#5f6368', marginBottom: '24px' }}>{user?.email}</p>

        <div style={{ display: 'flex', alignItems: 'center', gap: '16px', marginBottom: '24px' }}>
          <div style={{
            width: '72px', height: '72px', borderRadius: '50%', overflow: 'hidden',
            background: '#f1f3f4', display: 'flex', alignItems: 'center', justifyContent: 'center',
            fontSize: '24pt', color: '#5f6368', flexShrink: 0,
          }}>
            {picUrl ? (
              // eslint-disable-next-line @next/next/no-img-element
              <img src={picUrl} alt="Profile" style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
            ) : (user?.name || user?.email || '?')[0].toUpperCase()}
          </div>
          <div>
            <div style={{ fontWeight: 700 }}>{user?.name || '(no name set)'}</div>
            <div style={{ fontSize: '10pt', color: '#5f6368', textTransform: 'capitalize' }}>
              Role: {user?.role || 'view only (not yet assigned)'}
            </div>
          </div>
        </div>

        <form onSubmit={handleSave}>
          <div className="form-group">
            <label>Name</label>
            <input
              type="text" className="form-control"
              value={name} onChange={(e) => setName(e.target.value)}
            />
          </div>
          <div className="form-group">
            <label>Profile picture</label>
            <input
              type="file" accept="image/*"
              onChange={(e) => setFile(e.target.files?.[0] || null)}
            />
          </div>
          {error && <p style={{ color: '#d93025', fontSize: '10pt', marginBottom: '12px' }}>{error}</p>}
          {message && <p style={{ color: '#188038', fontSize: '10pt', marginBottom: '12px' }}>{message}</p>}
          <button type="submit" className="btn btn-primary" disabled={saving}>
            {saving ? 'Saving…' : 'Save Changes'}
          </button>
        </form>

        <div style={{ marginTop: '24px', paddingTop: '20px', borderTop: '1px solid #e8eaed' }}>
          <Link href="/forgot-password" className="btn btn-secondary">Change Password</Link>
          <p style={{ fontSize: '9.5pt', color: '#5f6368', marginTop: '8px' }}>
            Password changes are always verified by a passcode emailed to you.
          </p>
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
