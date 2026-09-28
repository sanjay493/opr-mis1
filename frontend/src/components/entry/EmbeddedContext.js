'use client';

import { createContext, useContext } from 'react';

// True while a data-entry form is rendered inside a tab of a grouped entry
// page (EntryTabs). GlobalNavbar reads it and renders nothing, so the form's
// own <GlobalNavbar /> doesn't duplicate the page's navbar.
export const EmbeddedContext = createContext(false);

export function useEmbedded() {
  return useContext(EmbeddedContext);
}
