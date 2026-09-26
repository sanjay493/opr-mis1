'use client';

import React, { Suspense, useState } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import GlobalNavbar from '@/components/GlobalNavbar';
import TechnoMonthlyView from '@/components/techno/TechnoMonthlyView';
import TechnoDashboardView from '@/components/techno/TechnoDashboardView';
import TechnoCustomView from '@/components/techno/TechnoCustomView';
import TechnoVerificationView from '@/components/techno/TechnoVerificationView';
import TechnoBfFurnaceView from '@/components/techno/TechnoBfFurnaceView';

// One page for every techno report. The old per-report URLs
// (/reports/techno-monthly, -dashboard, -custom, -verification, -bf-furnace)
// redirect here with ?tab=<id>, so bookmarks keep working.
const TECHNO_TABS = [
  { id: 'monthly', label: 'Plant-wise Monthly', icon: '⚙️', Component: TechnoMonthlyView },
  { id: 'dashboard', label: 'Trend Dashboard', icon: '🔬', Component: TechnoDashboardView },
  { id: 'custom', label: 'Custom Report', icon: '🧮', Component: TechnoCustomView },
  { id: 'verification', label: 'Verification', icon: '✅', Component: TechnoVerificationView },
  { id: 'bf-furnace', label: 'BF Furnace-wise', icon: '🌋', Component: TechnoBfFurnaceView },
];
const TAB_IDS = new Set(TECHNO_TABS.map((t) => t.id));

function TechnoReports() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const requested = searchParams.get('tab');
  const active = TAB_IDS.has(requested) ? requested : 'monthly';

  // Tabs mount on first visit and then stay mounted (hidden), so switching
  // back keeps each report's selections and loaded data.
  const [visited, setVisited] = useState(() => new Set([active]));
  if (!visited.has(active)) setVisited(new Set([...visited, active]));

  const selectTab = (id) => {
    router.replace(`/reports/techno?tab=${id}`, { scroll: false });
  };

  return (
    <div style={{ maxWidth: '1500px', margin: '0 auto', padding: '24px 32px 32px' }}>
      <h1 style={{ fontSize: '20pt', fontWeight: 900, color: '#202124', margin: '0 0 14px' }}>
        Techno Reports
      </h1>

      <div role="tablist" aria-label="Techno reports" style={{
        display: 'flex', gap: '4px', flexWrap: 'wrap',
        borderBottom: '2px solid #dadce0', marginBottom: '20px',
      }}>
        {TECHNO_TABS.map((t) => {
          const on = t.id === active;
          return (
            <button
              key={t.id}
              role="tab"
              aria-selected={on}
              onClick={() => selectTab(t.id)}
              style={{
                padding: '10px 18px', fontSize: '11pt', fontWeight: on ? 800 : 600,
                border: 'none', borderBottom: on ? '3px solid #1a73e8' : '3px solid transparent',
                marginBottom: '-2px', background: 'none', cursor: 'pointer',
                color: on ? '#1a73e8' : '#5f6368',
              }}
            >
              <span style={{ marginRight: 6 }}>{t.icon}</span>{t.label}
            </button>
          );
        })}
      </div>

      {TECHNO_TABS.filter((t) => visited.has(t.id)).map(({ id, Component }) => (
        <div key={id} role="tabpanel" hidden={id !== active}>
          <Component />
        </div>
      ))}
    </div>
  );
}

export default function TechnoReportsPage() {
  return (
    <div style={{ minHeight: '100vh', backgroundColor: '#ffffff' }}>
      <style>{`html, body { overflow-y: auto; overflow-x: hidden; }`}</style>
      <GlobalNavbar />
      <Suspense fallback={<div style={{ padding: 32, color: '#5f6368' }}>Loading…</div>}>
        <TechnoReports />
      </Suspense>
    </div>
  );
}
