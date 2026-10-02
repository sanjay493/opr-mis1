'use client';

import RequireEditor from '@/components/RequireEditor';

import SpecialSteelManualEntry from '@/components/SpecialSteelManualEntry';
import { EntryPage } from '../EntryUI';

const API = process.env.NEXT_PUBLIC_API_URL || '';

function SpecialSteelEntryPageInner() {
  return (
    <EntryPage
      title="Special Steel — Manual Entry"
      description="ISP entry & corrections — other plants are auto-extracted from uploaded files."
    >
      <SpecialSteelManualEntry apiBase={API} defaultPlant="ISP" />
    </EntryPage>
  );
}

export default function SpecialSteelEntryPage() {
  return (
    <RequireEditor>
      <SpecialSteelEntryPageInner />
    </RequireEditor>
  );
}
