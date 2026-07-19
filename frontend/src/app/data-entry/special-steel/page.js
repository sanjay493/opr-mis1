'use client';

import RequireEditor from '@/components/RequireEditor';

import GlobalNavbar from '@/components/GlobalNavbar';
import SpecialSteelManualEntry from '@/components/SpecialSteelManualEntry';

const API = process.env.NEXT_PUBLIC_API_URL || '';

function SpecialSteelEntryPageInner() {
  return (
    <div style={{ minHeight: '100vh', background: '#ffffff', fontFamily: "-apple-system,BlinkMacSystemFont,'Segoe UI',Arial,sans-serif" }}>
      <GlobalNavbar />

      <div style={{ maxWidth: 1200, margin: '0 auto', padding: '22px 20px' }}>
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
