// Return-to-page after login. A sign-in gate (RequireEditor / RequireAdmin /
// RequireAuth) sends the user to /login?next=<the page they were on>; the
// login page goes back there once signed in, instead of always to "/".

// "/login?next=<pathname + current query>" for the page being viewed.
export function loginHref(pathname) {
  const search = typeof window !== 'undefined' ? window.location.search : '';
  return `/login?next=${encodeURIComponent(`${pathname || '/'}${search}`)}`;
}

// The ?next= target to go to after login: only a path on this site (a single
// leading "/", so never "//evil.example" or "https://…"), and never an auth
// page itself. Anything else falls back to the home page.
export function safeNextPath(raw) {
  if (!raw || !raw.startsWith('/') || raw.startsWith('//') || raw.startsWith('/\\')) return '/';
  if (/^\/(login|register|forgot-password)(\/|\?|$)/.test(raw)) return '/';
  return raw;
}
