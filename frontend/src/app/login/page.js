'use client';

import { useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import GlobalNavbar from '@/components/GlobalNavbar';
import { useAuth, API_BASE_URL } from '@/providers/AuthProvider';

export default function LoginPage() {
  const router = useRouter();
  const { refresh } = useAuth();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [submitting, setSubmitting] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setSubmitting(true);
    try {
      const res = await fetch(`${API_BASE_URL}/api/auth/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({ email, password }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Login failed.');
      await refresh();
      router.push('/');
    } catch (err) {
      setError(err.message);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <>
      <GlobalNavbar />
      <main style={{ maxWidth: '420px', margin: '80px auto', padding: '0 20px' }}>
        <h1 style={{ fontSize: '20pt', marginBottom: '4px' }}>Log In</h1>
        <p style={{ color: '#5f6368', marginBottom: '24px' }}>SAIL MIS Portal</p>

        <form onSubmit={handleSubmit}>
          <div className="form-group">
            <label>Email</label>
            <input
              type="email" className="form-control" required
              value={email} onChange={(e) => setEmail(e.target.value)}
              autoComplete="username"
            />
          </div>
          <div className="form-group">
            <label>Password</label>
            <input
              type="password" className="form-control" required
              value={password} onChange={(e) => setPassword(e.target.value)}
              autoComplete="current-password"
            />
          </div>

          {error && <p style={{ color: '#d93025', fontSize: '10pt', marginBottom: '12px' }}>{error}</p>}

          <button type="submit" className="btn btn-primary" style={{ width: '100%' }} disabled={submitting}>
            {submitting ? 'Logging in…' : 'Log In'}
          </button>
        </form>

        <div style={{ marginTop: '20px', fontSize: '10.5pt', display: 'flex', justifyContent: 'space-between' }}>
          <Link href="/register">Register a new account</Link>
          <Link href="/forgot-password">Forgot password?</Link>
        </div>
      </main>
    </>
  );
}
