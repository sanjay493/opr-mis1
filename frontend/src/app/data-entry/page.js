'use client';

import RequireEditor from '@/components/RequireEditor';

import React, { useMemo, useState } from 'react';
import Link from 'next/link';
import GlobalNavbar from '@/components/GlobalNavbar';
import { NAV_ITEMS } from '@/components/navItems';
import { ENTRY_GROUPS } from '@/components/entry/entryGroups';
import ui from '@/styles/ui.module.css';
import h from './hub.module.css';

// The navbar's "Data Entry" menu (components/navItems.js), group by group, as
// cards. A tabbed Manual Entry page has no `desc` there: its card lists its
// tabs (components/entry/entryGroups.js). Add a page in navItems.js and it
// shows here, in the navbar and on the sitemap.
const GROUPS = NAV_ITEMS.find((it) => it.label === 'Data Entry').groups.map((g) => ({
  title: g.groupLabel,
  sections: g.children.map((c) => {
    const tabs = ENTRY_GROUPS.find((eg) => eg.route === c.link)?.tabs;
    return {
      title: c.label, icon: c.icon, link: c.link,
      description: c.desc || (tabs ? `${tabs.length} tabs: ${tabs.map((t) => t.label).join(' · ')}` : ''),
    };
  }),
}));

const TOTAL = GROUPS.reduce((n, g) => n + g.sections.length, 0);

function DataEntryPageInner() {
  const [query, setQuery] = useState('');

  const visible = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return GROUPS;
    return GROUPS
      .map((g) => ({
        ...g,
        sections: g.sections.filter((s) =>
          `${s.title} ${s.description}`.toLowerCase().includes(q)),
      }))
      .filter((g) => g.sections.length > 0);
  }, [query]);
  const shown = visible.reduce((n, g) => n + g.sections.length, 0);

  return (
    <>
      <GlobalNavbar />

      <main className={ui.page} style={{ '--page-max': '1400px' }}>
        <div className={ui.pageHeader}>
          <h1 className={ui.pageTitle}>Data Entry Hub</h1>
          <p className={ui.pageLead}>
            All data entry tools — production, stock, uploads, techno-economic parameters, special steel, report
            commentary and reference data.
          </p>
        </div>

        <div className={h.search}>
          <label htmlFor="hub-search" className={ui.srOnly}>Find a data entry page</label>
          <input
            id="hub-search"
            type="search"
            className="form-control"
            placeholder={`Filter ${TOTAL} pages — e.g. "coal", "targets", "special steel"`}
            value={query}
            onChange={(e) => setQuery(e.target.value)}
          />
          <span className={ui.meta} style={{ margin: 0 }} aria-live="polite">
            {query ? `${shown} of ${TOTAL} pages` : `${TOTAL} pages`}
          </span>
        </div>

        {visible.map((group) => (
          <section key={group.title} className={h.group} aria-labelledby={`hub-${group.title}`}>
            <h2 id={`hub-${group.title}`} className={h.groupTitle}>{group.title}</h2>
            <ul className={h.grid}>
              {group.sections.map((section) => (
                <li key={section.link}>
                  <Link href={section.link} className={h.card}>
                    <span className={h.icon} aria-hidden="true">{section.icon}</span>
                    <span className={h.body}>
                      <span className={h.title}>{section.title}</span>
                      <span className={h.desc}>{section.description}</span>
                    </span>
                  </Link>
                </li>
              ))}
            </ul>
          </section>
        ))}

        {shown === 0 && (
          <p className={ui.meta}>No page matches &quot;{query}&quot;.</p>
        )}

        <p className={h.tip}>
          <strong>Tip:</strong> Data entered in these sections is cached automatically for faster access. Use the Report
          Engine to view and export compiled reports across all data sources.
        </p>
      </main>
    </>
  );
}

export default function DataEntryPage() {
  return (
    <RequireEditor>
      <DataEntryPageInner />
    </RequireEditor>
  );
}
