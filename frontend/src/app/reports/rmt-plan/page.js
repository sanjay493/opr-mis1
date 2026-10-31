import { redirect } from 'next/navigation';
import { tabHref } from '@/components/reports/reportGroups';

// Short URL for the RMT Production Plan tab of Production Reports
// (components/reports/rmt-plan/View.js).
export default function Page() {
  redirect(tabHref('rmt-plan'));
}
