'use client';

import React, { Suspense, useState } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import GlobalNavbar from '@/components/GlobalNavbar';
import TechnoMonthlyView from '@/components/techno/TechnoMonthlyView';
import TechnoDashboardView from '@/components/techno/TechnoDashboardView';
import TechnoCustomView from '@/components/techno/TechnoCustomView';
import TechnoVerificationView from '@/components/techno/TechnoVerificationView';
import TechnoBfFurnaceView from '@/components/techno/TechnoBfFurnaceView';
import s from '@/components/reports/ReportTabs.module.css';
import wb from '@/styles/wb.module.css';

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
    <>
      <div className={s.header}>
        <div className={s.titleRow}>
          <h1 className={s.title}>Techno Reports</h1>
          <p className={s.lead}>Techno-economic parameters — plant-wise monthly, trends, custom reports, verification and furnace-wise.</p>
        </div>
        <div className={s.tabs} role="tablist" aria-label="Techno reports">
          {TECHNO_TABS.map((t) => (
            <button
              key={t.id}
              type="button"
              role="tab"
              aria-selected={t.id === active}
              className={s.tab}
              onClick={() => selectTab(t.id)}
            >
              <span style={{ marginRight: 6 }} aria-hidden="true">{t.icon}</span>{t.label}
            </button>
          ))}
        </div>
      </div>

      <div className={wb.page}>
        <div style={{ maxWidth: 1500, margin: '0 auto', padding: '18px 24px 32px' }}>
          {TECHNO_TABS.filter((t) => visited.has(t.id)).map(({ id, Component }) => (
            <div key={id} role="tabpanel" hidden={id !== active}>
              <Component />
            </div>
          ))}
        </div>
      </div>
    </>
  );
}

export default function TechnoReportsPage() {
  return (
    <div className={s.shell}>
      <GlobalNavbar />
      <Suspense fallback={<div className={s.loading}>Loading…</div>}>
        <TechnoReports />
      </Suspense>
    </div>
  );
}
