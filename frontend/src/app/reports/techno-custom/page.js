import { redirect } from 'next/navigation';

// Merged into the tabbed /reports/techno page — kept so old links still work.
export default function Page() {
  redirect('/reports/techno?tab=custom');
}
