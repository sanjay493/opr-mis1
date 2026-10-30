import { redirect } from 'next/navigation';
import { tabHref } from '@/components/reports/reportGroups';

// Short URL for the OP vs APP vs Actual tab of Production Reports
// (components/reports/op-comparison/View.js).
export default function Page() {
  redirect(tabHref('op-comparison'));
}
