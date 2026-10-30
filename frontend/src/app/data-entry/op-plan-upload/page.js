import { redirect } from 'next/navigation';
import { tabHref } from '@/components/entry/entryGroups';

// Short URL for the OP Upload tab of Production & Techno Entry
// (components/entry/op-plan-upload/Form.js).
export default function Page() {
  redirect(tabHref('op-plan-upload'));
}
