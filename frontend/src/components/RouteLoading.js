import GlobalNavbar from '@/components/GlobalNavbar';

/**
 * Shared route-level loading UI (used by the app/<section>/loading.js files).
 * Shown the instant a link is clicked while the next page's code/data loads;
 * it keeps the navbar in place so the screen doesn't flash blank.
 */
export default function RouteLoading() {
  return (
    <>
      <GlobalNavbar />
      <div
        role="status"
        style={{ padding: '48px 16px', textAlign: 'center', fontSize: '14px', color: 'var(--ui-text-secondary)' }}
      >
        Loading…
      </div>
    </>
  );
}
