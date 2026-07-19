'use client';

import Link from 'next/link';
import { useAuth } from '@/providers/AuthProvider';

/** Gates any page that just needs a logged-in account, regardless of role
 * (e.g. the profile page — every registered user manages their own profile). */
export default function RequireAuth({ children }) {
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
        <Link href="/login" className="btn btn-primary">Log In</Link>
      </div>
    );
  }

  return children;
}
