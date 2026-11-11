'use client';

import React, { useMemo, useState } from 'react';
import Link from 'next/link';
import GlobalNavbar from '@/components/GlobalNavbar';
import { NAV_ITEMS, ACCOUNT_LINKS, ADMIN_LINKS } from '@/components/navItems';
import { ENTRY_GROUPS } from '@/components/entry/entryGroups';
import { REPORT_GROUPS } from '@/components/reports/reportGroups';
import { TECHNO_TABS } from '@/components/techno/technoTabs';
import s from './sitemap.module.css';

// Every page of the portal, parent to child, drawn from the same data the
// app navigates with: the navbar's menu (components/navItems.js), the tabs of
// each grouped entry page (entryGroups.js), report page (reportGroups.js) and
// the techno reports (technoTabs.js). A page added there shows up here.

const SELF = '/sitemap';

// A navbar link's own tabs, if it is a grouped page.
function tabsOf(link) {
  const entry = ENTRY_GROUPS.find((g) => g.route === link);
  if (entry) return entry.tabs.map((t) => ({ label: t.label, link: `${entry.route}?tab=${t.id}`, desc: t.description }));
  const report = REPORT_GROUPS.find((g) => g.route === link);
  if (report) {
    // Tabs sharing a `menu` sit under one node, like the tab strip's dropdown.
    const out = [];
    report.tabs.forEach((t) => {
      const node = { label: t.label, link: `${report.route}?tab=${t.id}`, desc: t.description };
      if (!t.menu) { out.push(node); return; }
      let menu = out.find((n) => n.menu === t.menu);
      if (!menu) { menu = { label: t.menu, menu: t.menu, children: [] }; out.push(menu); }
      menu.children.push(node);
    });
    return out;
  }
  if (link === '/reports/techno') {
    return TECHNO_TABS.map((t) => ({ label: t.label, icon: t.icon, link: `/reports/techno?tab=${t.id}` }));
  }
  return [];
}

function page(item) {
  const children = tabsOf(item.link);
  return { label: item.label, icon: item.icon, link: item.link, children };
}

function buildTree() {
  const sections = NAV_ITEMS.filter((it) => it.link !== SELF).map((it) => {
    if (it.groups) {
      return {
        label: it.label, icon: it.icon,
        link: it.label === 'Data Entry' ? '/data-entry' : undefined,
        children: it.groups.map((g) => ({ label: g.groupLabel, children: g.children.map(page) })),
      };
    }
    if (it.submenu) return { label: it.label, icon: it.icon, children: it.submenu.map(page) };
    return page(it);
  });
  sections.push({
    label: 'Account & Admin', icon: '👤',
    children: [
      ...ACCOUNT_LINKS.map(page),
      { label: 'Admin', icon: '🛡️', children: ADMIN_LINKS.map(page) },
      { label: 'Sign in', icon: '🔑', children: [
        { label: 'Login', link: '/login' }, { label: 'Register', link: '/register' },
        { label: 'Forgot Password', link: '/forgot-password' },
      ] },
    ],
  });
  // Stable ids for expand / collapse.
  const number = (nodes, prefix) => nodes.forEach((n, i) => {
    n.id = `${prefix}${i}`;
    if (n.children) number(n.children, `${n.id}.`);
  });
  number(sections, '');
  return sections;
}

const count = (n) => (n.link ? 1 : 0) + (n.children || []).reduce((a, c) => a + count(c), 0);

// The tree cut to the nodes matching `q` (label, link or description) and
// their ancestors; a matching node keeps all its children.
function filterTree(nodes, q) {
  if (!q) return nodes;
  const out = [];
  nodes.forEach((n) => {
    const hit = [n.label, n.link, n.desc].some((x) => x && x.toLowerCase().includes(q));
    if (hit) { out.push({ ...n, hit: true }); return; }
    const kids = filterTree(n.children || [], q);
    if (kids.length) out.push({ ...n, children: kids });
  });
  return out;
}

function Node({ node, depth, collapsed, toggle, forceOpen }) {
  const kids = node.children || [];
  const open = forceOpen || !collapsed.has(node.id);
  const label = (
    <>
      {node.icon && <span className={s.icon} aria-hidden>{node.icon}</span>}
      <span>{node.label}</span>
    </>
  );
  return (
    <li className={s.item}>
      <div className={s.row}>
        {kids.length > 0 ? (
          <button type="button" className={s.twist} onClick={() => toggle(node.id)}
                  aria-expanded={open} aria-label={`${open ? 'Collapse' : 'Expand'} ${node.label}`}>
            {open ? '▾' : '▸'}
          </button>
        ) : <span className={s.twistGap} />}
        {node.link ? (
          <Link href={node.link} className={`${s.node} ${depth === 0 ? s.nodeTop : ''} ${node.hit ? s.hit : ''}`}
                title={node.desc ? `${node.desc}\n${node.link}` : node.link}>
            {label}
          </Link>
        ) : (
          <span className={`${s.node} ${s.nodeGroup} ${depth === 0 ? s.nodeTop : ''} ${node.hit ? s.hit : ''}`}>{label}</span>
        )}
        {kids.length > 0 && <span className={s.badge}>{count(node) - (node.link ? 1 : 0)}</span>}
      </div>
      {kids.length > 0 && open && (
        <ul className={s.children}>
          {kids.map((c) => <Node key={c.id} node={c} depth={depth + 1} collapsed={collapsed} toggle={toggle} forceOpen={forceOpen} />)}
        </ul>
      )}
    </li>
  );
}

export default function SitemapPage() {
  const tree = useMemo(() => buildTree(), []);
  const [query, setQuery] = useState('');
  const [collapsed, setCollapsed] = useState(() => new Set());
  const q = query.trim().toLowerCase();
  const shown = useMemo(() => filterTree(tree, q), [tree, q]);
  const total = tree.reduce((a, n) => a + count(n), 0);

  const allIds = useMemo(() => {
    const ids = [];
    const walk = (ns, depth) => ns.forEach((n) => {
      if (n.children?.length) { if (depth > 0) ids.push(n.id); walk(n.children, depth + 1); }
    });
    walk(tree, 0);
    return ids;
  }, [tree]);

  const toggle = (id) => setCollapsed((prev) => {
    const next = new Set(prev);
    if (next.has(id)) next.delete(id); else next.add(id);
    return next;
  });

  return (
    <div className={s.shell}>
      <GlobalNavbar />
      <div className={s.scroll}>
      <main className={s.page}>
        <header className={s.head}>
          <div>
            <h1 className={s.title}>Sitemap</h1>
            <p className={s.sub}>Every page and tab of the SAIL MIS Portal, parent to child — {total} pages. Click any page to open it.</p>
          </div>
          <div className={s.tools}>
            <input type="search" className={s.search} placeholder="Find a page…" value={query}
                   onChange={(e) => setQuery(e.target.value)} aria-label="Find a page" />
            <button type="button" className={s.btn} onClick={() => setCollapsed(new Set())}>Expand all</button>
            <button type="button" className={s.btn} onClick={() => setCollapsed(new Set(allIds))}>Collapse all</button>
          </div>
        </header>

        <div className={s.rootRow}>
          <Link href="/" className={s.root}><span aria-hidden>📊</span> SAIL MIS Portal</Link>
        </div>

        {shown.length === 0 ? (
          <p className={s.empty}>No page matches “{query}”.</p>
        ) : (
          <div className={s.grid}>
            {shown.map((sec) => (
              <section key={sec.id} className={s.card}>
                <ul className={s.tree}>
                  <Node node={sec} depth={0} collapsed={collapsed} toggle={toggle} forceOpen={!!q} />
                </ul>
              </section>
            ))}
          </div>
        )}
      </main>
      </div>
    </div>
  );
}
