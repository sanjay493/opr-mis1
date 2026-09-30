import { Suspense } from 'react';
import ReportTabs from '@/components/reports/ReportTabs';

// Grouped report page — tabs are defined in components/reports/reportGroups.js.
// ReportTabs reads ?tab= via useSearchParams, hence the Suspense boundary.
export default function Page() {
  return (
    <Suspense fallback={null}>
      <ReportTabs groupId="special-steel-ipt" />
    </Suspense>
  );
}
