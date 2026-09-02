'use client';

import { useEffect } from 'react';
import { usePathname } from 'next/navigation';
import { API_BASE_URL } from '@/providers/AuthProvider';

/** No UI — fires a beacon to /api/log-visit on mount and every route change,
 * so /admin/site-visits can show who (or which IP) visited which pages. */
export default function VisitLogger() {
  const pathname = usePathname();

  useEffect(() => {
    fetch(`${API_BASE_URL}/api/log-visit`, {
      method: 'POST',
      credentials: 'include',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ path: pathname }),
      keepalive: true,
    }).catch(() => {});
  }, [pathname]);

  return null;
}
