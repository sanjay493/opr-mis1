'use client';

import { createContext, useContext } from 'react';

// True while a page is rendered inside a tab of a grouped page (EntryTabs,
// ReportTabs). GlobalNavbar reads it and renders nothing, so the tabbed
// page's own <GlobalNavbar /> doesn't duplicate the group page's navbar.
export const EmbeddedContext = createContext(false);

export function useEmbedded() {
  return useContext(EmbeddedContext);
}
