import { redirect } from 'next/navigation';
import { tabHref } from '@/components/reports/reportGroups';

// This report now lives as a tab of a grouped report page
// (components/reports/bf-benchmark/View.js); keep the old URL working.
export default function Page() {
  redirect(tabHref('bf-benchmark'));
}
