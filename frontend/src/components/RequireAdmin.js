'use client';

import Link from 'next/link';
import { useAuth } from '@/providers/AuthProvider';

/** Gates admin-only pages (user/whitelist management, activity log). */
export default function RequireAdmin({ children }) {
  const { user, loading } = useAuth();

  if (loading) {
    return (
      <div style={{ padding: '60px', textAlign: 'center', color: '#5f6368' }}>
        Checking your access…
      </div>
    );
  }

  if (!user) {
    return (
      <div style={{ maxWidth: '480px', margin: '80px auto', textAlign: 'center', padding: '32px' }}>
        <h2 style={{ marginBottom: '8px' }}>Sign in required</h2>
        <p style={{ color: '#5f6368', marginBottom: '20px' }}>This page is for administrators only.</p>
        <Link href="/login" className="btn btn-primary">Log In</Link>
      </div>
    );
  }

  if (user.role !== 'admin') {
    return (
      <div style={{ maxWidth: '480px', margin: '80px auto', textAlign: 'center', padding: '32px' }}>
        <h2 style={{ marginBottom: '8px' }}>Access denied</h2>
        <p style={{ color: '#5f6368' }}>This page is for administrators only.</p>
      </div>
    );
  }

  return children;
}
