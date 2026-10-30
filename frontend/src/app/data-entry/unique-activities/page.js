import { redirect } from 'next/navigation';
import { tabHref } from '@/components/entry/entryGroups';

// Short URL for the Unique Activities tab of Reference & Records
// (components/entry/unique-activities/Form.js).
export default function Page() {
  redirect(tabHref('unique-activities'));
}
