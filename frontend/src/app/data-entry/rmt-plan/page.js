import { redirect } from 'next/navigation';
import { tabHref } from '@/components/entry/entryGroups';

// Short URL for the RMT Plan remarks / IPT tab of Production & Techno Entry
// (components/entry/rmt-plan/Form.js).
export default function Page() {
  redirect(tabHref('rmt-plan'));
}
