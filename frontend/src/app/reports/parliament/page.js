import { redirect } from 'next/navigation';
import { tabHref } from '@/components/reports/reportGroups';

// The Parliament annexures are tabs of External Reports
// (components/reports/parl-*/View.js); keep the old URL working.
export default function Page() {
  redirect(tabHref('parl-production-performance'));
}
