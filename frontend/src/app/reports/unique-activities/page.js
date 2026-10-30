import { redirect } from 'next/navigation';
import { tabHref } from '@/components/reports/reportGroups';

// Short URL for the Unique Activities tab of Highlights & Records
// (components/reports/unique-activities/View.js).
export default function Page() {
  redirect(tabHref('unique-activities'));
}
