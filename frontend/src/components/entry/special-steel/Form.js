'use client';

import RequireEditor from '@/components/RequireEditor';

import GlobalNavbar from '@/components/GlobalNavbar';
import SpecialSteelManualEntry from '@/components/SpecialSteelManualEntry';

const API = process.env.NEXT_PUBLIC_API_URL || '';

function SpecialSteelEntryPageInner() {
  // globals.css sets html/body overflow:hidden, so the page must provide its
  // own scroll container (same pattern as the other data-entry pages).
  return (
    <div style={{ height: '100vh', display: 'flex', flexDirection: 'column', overflow: 'hidden', background: '#ffffff', fontFamily: "-apple-system,BlinkMacSystemFont,'Segoe UI',Arial,sans-serif" }}>
      <GlobalNavbar />

      <div style={{ flex: 1, overflowY: 'auto', maxWidth: 1200, margin: '0 auto', padding: '22px 20px', width: '100%' }}>

        <div style={{ display: 'flex', alignItems: 'baseline', gap: 14, marginBottom: 18 }}>
          <h2 style={{ fontSize: '1.6rem', fontWeight: 700, color: '#202124', margin: 0 }}>
            Special Steel — Manual Entry
          </h2>
          <span style={{ fontSize: 13, color: '#5f6368' }}>
            ISP entry &amp; corrections — other plants are auto-extracted from uploaded files
          </span>
        </div>

        <SpecialSteelManualEntry apiBase={API} defaultPlant="ISP" />
      </div>
    </div>
  );
}

export default function SpecialSteelEntryPage() {
  return (
    <RequireEditor>
      <SpecialSteelEntryPageInner />
    </RequireEditor>
  );
}
