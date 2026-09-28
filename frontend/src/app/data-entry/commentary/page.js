import { Suspense } from 'react';
import EntryTabs from '@/components/entry/EntryTabs';

// Grouped entry page — tabs are defined in components/entry/entryGroups.js.
// EntryTabs reads ?tab= via useSearchParams, hence the Suspense boundary.
export default function Page() {
  return (
    <Suspense fallback={null}>
      <EntryTabs groupId="commentary" />
    </Suspense>
  );
}