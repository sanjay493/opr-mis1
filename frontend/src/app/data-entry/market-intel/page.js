import { redirect } from 'next/navigation';
import { tabHref } from '@/components/entry/entryGroups';

// This form now lives as a tab of a grouped entry page
// (components/entry/market-intel/Form.js); keep the old URL working.
export default function Page() {
  redirect(tabHref('market-intel'));
}