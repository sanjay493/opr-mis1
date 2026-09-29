import { redirect } from 'next/navigation';
import { tabHref } from '@/components/reports/reportGroups';

// This report now lives as a tab of a grouped report page
// (components/reports/one-page-report/View.js); keep the old URL working.
export default function Page() {
  redirect(tabHref('one-page-report'));
}
