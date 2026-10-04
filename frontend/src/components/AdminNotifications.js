'use client';

import { useCallback, useEffect, useRef, useState } from 'react';
import Link from 'next/link';
import { API_BASE_URL } from '@/providers/AuthProvider';

/** Admin-only navbar bell: sign-ins and new anonymous visitors, polled from
 * GET /api/admin/notifications (see backend db.add_admin_notification).
 * Unread state is the last-seen event id, kept per browser. */

const POLL_MS = 30000;
const TOAST_MS = 6000;
const SEEN_KEY = 'adminNotifLastSeenId';

function readSeen() {
  try { return Number(localStorage.getItem(SEEN_KEY)) || 0; } catch { return 0; }
}

function writeSeen(id) {
  try { localStorage.setItem(SEEN_KEY, String(id)); } catch { /* private mode */ }
}

function ago(ts) {
  const s = Math.max(0, Math.round((Date.now() - new Date(ts).getTime()) / 1000));
  if (s < 60) return 'just now';
  if (s < 3600) return `${Math.floor(s / 60)} min ago`;
  if (s < 86400) return `${Math.floor(s / 3600)} h ago`;
  return `${Math.floor(s / 86400)} d ago`;
}

function describe(n) {
  if (n.kind === 'sign_in') {
    return { icon: '🔑', title: `${n.user_name || n.user_email} signed in`, sub: n.ip_address || '' };
  }
  return {
    icon: '👁️',
    title: 'Anonymous visitor',
    sub: [n.ip_address, n.path && `→ ${n.path}`].filter(Boolean).join(' '),
  };
}

export default function AdminNotifications() {
  const [items, setItems] = useState([]);
  const [seenId, setSeenId] = useState(readSeen);
  const [open, setOpen] = useState(false);
  const [toasts, setToasts] = useState([]);
  const maxIdRef = useRef(null); // null until the first load, so old events don't toast
  const wrapRef = useRef(null);

  const load = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE_URL}/api/admin/notifications?limit=30`, { credentials: 'include' });
      if (!res.ok) return;
      const data = await res.json();
      const list = data.notifications || [];
      const prevMax = maxIdRef.current;
      if (prevMax !== null) {
        const fresh = list.filter((n) => n.id > prevMax).slice(0, 3);
        if (fresh.length) {
          setToasts((t) => [...fresh, ...t].slice(0, 3));
          setTimeout(() => {
            setToasts((t) => t.filter((x) => !fresh.some((f) => f.id === x.id)));
          }, TOAST_MS);
        }
      }
      maxIdRef.current = list.length ? Math.max(list[0].id, prevMax || 0) : (prevMax || 0);
      setItems(list);
    } catch { /* backend unreachable — try again next poll */ }
  }, []);

  useEffect(() => {
    load();
    const timer = setInterval(() => {
      if (document.visibilityState === 'visible') load();
    }, POLL_MS);
    const onVisible = () => { if (document.visibilityState === 'visible') load(); };
    document.addEventListener('visibilitychange', onVisible);
    return () => {
      clearInterval(timer);
      document.removeEventListener('visibilitychange', onVisible);
    };
  }, [load]);

  useEffect(() => {
    if (!open) return;
    const onDown = (e) => { if (wrapRef.current && !wrapRef.current.contains(e.target)) setOpen(false); };
    document.addEventListener('mousedown', onDown);
    return () => document.removeEventListener('mousedown', onDown);
  }, [open]);

  const unread = items.filter((n) => n.id > seenId).length;

  const toggle = () => {
    const next = !open;
    setOpen(next);
    if (next && items.length) {
      setSeenId(items[0].id);
      writeSeen(items[0].id);
    }
  };

  return (
    <div ref={wrapRef} style={{ position: 'relative', marginLeft: 'auto' }}>
      <button
        type="button"
        onClick={toggle}
        aria-label={unread ? `Notifications, ${unread} unread` : 'Notifications'}
        aria-expanded={open}
        style={{
          position: 'relative', border: 'none', cursor: 'pointer', fontSize: '18px',
          padding: '8px 10px', borderRadius: '6px',
          backgroundColor: open ? 'rgba(26, 115, 232, 0.08)' : 'transparent',
        }}
      >
        🔔
        {unread > 0 && (
          <span style={{
            position: 'absolute', top: '2px', right: '2px', minWidth: '18px', height: '18px',
            padding: '0 5px', borderRadius: '9px', backgroundColor: '#d93025', color: '#fff',
            fontSize: '8.5pt', fontWeight: 700, lineHeight: '18px', textAlign: 'center',
          }}>
            {unread > 99 ? '99+' : unread}
          </span>
        )}
      </button>

      {open && (
        <div style={{
          position: 'absolute', right: 0, top: '100%', marginTop: '4px', width: '360px',
          backgroundColor: '#fff', border: '1px solid #dadce0', borderRadius: '8px',
          boxShadow: '0 4px 16px rgba(0,0,0,0.12)', zIndex: 200, overflow: 'hidden',
        }}>
          <div style={{ padding: '10px 14px', fontWeight: 700, borderBottom: '1px solid #eee', color: '#202124' }}>
            Notifications
          </div>
          <div style={{ maxHeight: '380px', overflowY: 'auto' }}>
            {items.length === 0 && (
              <div style={{ padding: '18px 14px', color: '#5f6368', fontSize: '11pt' }}>No sign-ins or visitors yet.</div>
            )}
            {items.map((n) => {
              const d = describe(n);
              return (
                <div key={n.id} style={{ display: 'flex', gap: '10px', padding: '10px 14px', borderBottom: '1px solid #f1f3f4' }}>
                  <span aria-hidden="true">{d.icon}</span>
                  <div style={{ minWidth: 0 }}>
                    <div style={{ fontSize: '11pt', color: '#202124', fontWeight: 600 }}>{d.title}</div>
                    <div style={{ fontSize: '9.5pt', color: '#5f6368', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                      {d.sub}{d.sub ? ' · ' : ''}{ago(n.created_at)}
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
          <Link
            href="/admin/site-visits"
            onClick={() => setOpen(false)}
            style={{ display: 'block', padding: '10px 14px', fontSize: '10.5pt', color: '#1a73e8', textDecoration: 'none', borderTop: '1px solid #eee' }}
          >
            View all site visits →
          </Link>
        </div>
      )}

      <div aria-live="polite" style={{ position: 'fixed', right: '20px', bottom: '20px', zIndex: 1000, display: 'flex', flexDirection: 'column', gap: '8px' }}>
        {toasts.map((n) => {
          const d = describe(n);
          return (
            <div key={n.id} role="status" style={{
              display: 'flex', gap: '10px', alignItems: 'flex-start', width: '320px', padding: '12px 14px',
              backgroundColor: '#202124', color: '#fff', borderRadius: '8px', boxShadow: '0 4px 16px rgba(0,0,0,0.25)',
            }}>
              <span aria-hidden="true">{d.icon}</span>
              <div style={{ minWidth: 0, flex: 1 }}>
                <div style={{ fontSize: '11pt', fontWeight: 600 }}>{d.title}</div>
                {d.sub && <div style={{ fontSize: '9.5pt', opacity: 0.8 }}>{d.sub}</div>}
              </div>
              <button
                type="button" aria-label="Dismiss"
                onClick={() => setToasts((t) => t.filter((x) => x.id !== n.id))}
                style={{ background: 'none', border: 'none', color: '#fff', cursor: 'pointer', fontSize: '14px', opacity: 0.7 }}
              >
                ✕
              </button>
            </div>
          );
        })}
      </div>
    </div>
  );
}
