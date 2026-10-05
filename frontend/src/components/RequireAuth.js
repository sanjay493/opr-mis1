'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { useAuth } from '@/providers/AuthProvider';
import { loginHref } from '@/components/auth/loginRedirect';

/** Gates any page that just needs a logged-in account, regardless of role
 * (e.g. the profile page — every registered user manages their own profile). */
export default function RequireAuth({ children }) {
  const { user, loading } = useAuth();
  const pathname = usePathname();

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
        <Link href={loginHref(pathname)} className="btn btn-primary">Log In</Link>
      </div>
    );
  }

  return children;
}
