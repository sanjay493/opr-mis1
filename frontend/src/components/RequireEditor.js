'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { useAuth } from '@/providers/AuthProvider';
import { loginHref } from '@/components/auth/loginRedirect';

/** Gates any page needing insert/update/delete/upload capability. */
export default function RequireEditor({ children }) {
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
        <p style={{ color: '#5f6368', marginBottom: '20px' }}>
          This page requires an Editor or Administrator account.
        </p>
        <Link href={loginHref(pathname)} className="btn btn-primary">Log In</Link>
      </div>
    );
  }

  if (user.role !== 'editor' && user.role !== 'admin') {
    return (
      <div style={{ maxWidth: '480px', margin: '80px auto', textAlign: 'center', padding: '32px' }}>
        <h2 style={{ marginBottom: '8px' }}>Access denied</h2>
        <p style={{ color: '#5f6368' }}>
          Your account ({user.email}) doesn&apos;t have Editor access yet.
          Ask an administrator to assign you a role.
        </p>
      </div>
    );
  }

  return children;
}
