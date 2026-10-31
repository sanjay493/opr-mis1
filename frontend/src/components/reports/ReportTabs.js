'use client';

import { useCallback, useEffect, useRef, useState } from 'react';
import dynamic from 'next/dynamic';
import { usePathname, useRouter, useSearchParams } from 'next/navigation';
import GlobalNavbar from '@/components/GlobalNavbar';
import { EmbeddedContext } from '@/components/EmbeddedContext';
import { groupById, tabHref } from './reportGroups';
import s from './ReportTabs.module.css';

const loading = () => <div className={s.loading}>Loading…</div>;

// One lazily-loaded report per tab id (import paths must be static).
const VIEWS = {
  'production-fy': dynamic(() => import('./production-fy/View'), { loading }),
  'production-trend': dynamic(() => import('./production-trend/View'), { loading }),
  'production-query': dynamic(() => import('./production-query/View'), { loading }),
  'production-items': dynamic(() => import('./production-items/View'), { loading }),
  'op-comparison': dynamic(() => import('./op-comparison/View'), { loading }),
  'rmt-plan': dynamic(() => import('./rmt-plan/View'), { loading }),
  'special-steel-fy': dynamic(() => import('./special-steel-fy/View'), { loading }),
  'special-steel-physical': dynamic(() => import('./special-steel-physical/View'), { loading }),
  'ipt-fy': dynamic(() => import('./ipt-fy/View'), { loading }),
  'iron-ore-mines': dynamic(() => import('./iron-ore-mines/View'), { loading }),
  'mines-group-wise': dynamic(() => import('./mines-group-wise/View'), { loading }),
  'mines-performance': dynamic(() => import('./mines-performance/View'), { loading }),
  'production-cost': dynamic(() => import('./production-cost/View'), { loading }),
  'bf-benchmark': dynamic(() => import('./bf-benchmark/View'), { loading }),
  'production-loss-analysis': dynamic(() => import('./production-loss-analysis/View'), { loading }),
  'breakdown-analysis': dynamic(() => import('./breakdown-analysis/View'), { loading }),
  'capital-repair-calendar': dynamic(() => import('./capital-repair-calendar/View'), { loading }),
  'bd-cr-log': dynamic(() => import('./bd-cr-log/View'), { loading }),
  'highlights': dynamic(() => import('./highlights/View'), { loading }),
  'major-production': dynamic(() => import('./major-production/View'), { loading }),
  'records-matrix': dynamic(() => import('./records-matrix/View'), { loading }),
  'techno-records': dynamic(() => import('./techno-records/View'), { loading }),
  'unique-activities': dynamic(() => import('./unique-activities/View'), { loading }),
  'new-facilities': dynamic(() => import('./new-facilities/View'), { loading }),
  'do-letter': dynamic(() => import('./do-letter/View'), { loading }),
  'board-note': dynamic(() => import('./board-note/View'), { loading }),
  'secretary-review': dynamic(() => import('./secretary-review/View'), { loading }),
  'jpc-report': dynamic(() => import('./jpc-report/View'), { loading }),
  'one-page-report': dynamic(() => import('./one-page-report/View'), { loading }),
  'plant-performance-items': dynamic(() => import('./plant-performance-items/View'), { loading }),
  'pmix-fy': dynamic(() => import('./pmix-fy/View'), { loading }),
  'sefi': dynamic(() => import('./sefi/View'), { loading }),
  'steel-bulletin': dynamic(() => import('./steel-bulletin/View'), { loading }),
  'cmd-monthly-report': dynamic(() => import('./cmd-monthly-report/View'), { loading }),
};

/**
 * A grouped report page: one tab per report. The active tab is in the URL
 * (?tab=<id>) so every tab can be linked to and bookmarked. A tab is mounted
 * the first time it's opened and then kept mounted (hidden) while another
 * tab is shown, so switching tabs never discards a report's filters/selection.
 */
export default function ReportTabs({ groupId }) {
  const group = groupById(groupId);
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();

  const requested = searchParams.get('tab');
  const active = group.tabs.some((t) => t.id === requested) ? requested : group.tabs[0].id;

  // A ?tab= that now belongs to another group (a report moved to a different
  // page, e.g. an old /reports/production-analysis?tab=ipt-fy bookmark) is
  // sent on to that group's page.
  const movedTo = requested && requested !== active && tabHref(requested) !== '/reports' ? tabHref(requested) : null;
  useEffect(() => {
    if (movedTo) router.replace(movedTo);
  }, [movedTo, router]);

  // Tabs opened so far (kept mounted). Updated during render when a new tab
  // becomes active — React's "adjust state on prop change" pattern.
  const [opened, setOpened] = useState(() => [active]);
  if (!opened.includes(active)) setOpened([...opened, active]);

  const select = useCallback((id) => {
    router.replace(`${pathname}?tab=${id}`, { scroll: false });
  }, [router, pathname]);

  // The tab strip: one entry per report, except that tabs sharing a `menu`
  // name collapse into a single dropdown entry.
  const strip = [];
  for (const t of group.tabs) {
    if (!t.menu) { strip.push({ key: t.id, tab: t }); continue; }
    const m = strip.find((x) => x.menu === t.menu);
    if (m) m.tabs.push(t);
    else strip.push({ key: `menu-${strip.length}`, menu: t.menu, tabs: [t] });
  }
  const stripKeyOf = (id) => strip.find((x) => (x.tab ? x.tab.id === id : x.tabs.some((t) => t.id === id))).key;
  const activeKey = stripKeyOf(active);
  const tabRefs = useRef({});

  // The open dropdown (its strip key). The strip scrolls horizontally, which
  // would clip an absolutely positioned menu, so the menu is position: fixed
  // under its button.
  const [openMenu, setOpenMenu] = useState(null);
  const [menuPos, setMenuPos] = useState(null);
  const menuRef = useRef(null);
  const openMenuAt = (key) => {
    const r = tabRefs.current[key]?.getBoundingClientRect();
    if (r) setMenuPos({ top: r.bottom, left: r.left });
    setOpenMenu(key);
  };
  const closeMenu = (refocus) => {
    if (refocus) tabRefs.current[openMenu]?.focus();
    setOpenMenu(null);
  };
  useEffect(() => {
    if (!openMenu) return undefined;
    const onDown = (e) => {
      if (menuRef.current?.contains(e.target) || tabRefs.current[openMenu]?.contains(e.target)) return;
      setOpenMenu(null);
    };
    const onResize = () => setOpenMenu(null);
    document.addEventListener('mousedown', onDown);
    window.addEventListener('resize', onResize);
    // Focus the current report's item, else the first.
    const items = menuRef.current?.querySelectorAll('[role="menuitemradio"]') || [];
    ([...items].find((el) => el.getAttribute('aria-checked') === 'true') || items[0])?.focus();
    return () => {
      document.removeEventListener('mousedown', onDown);
      window.removeEventListener('resize', onResize);
    };
  }, [openMenu]);

  // Arrow-key navigation between strip entries (WAI-ARIA tabs pattern).
  // Moving onto a dropdown shows its first report; ArrowDown / Enter opens it.
  const onKeyDown = (e) => {
    if (openMenu) return;
    const keys = strip.map((x) => x.key);
    const i = keys.indexOf(activeKey);
    let next = null;
    if (e.key === 'ArrowRight') next = keys[(i + 1) % keys.length];
    else if (e.key === 'ArrowLeft') next = keys[(i - 1 + keys.length) % keys.length];
    else if (e.key === 'Home') next = keys[0];
    else if (e.key === 'End') next = keys[keys.length - 1];
    if (next) {
      e.preventDefault();
      const entry = strip.find((x) => x.key === next);
      select(entry.tab ? entry.tab.id : entry.tabs[0].id);
      tabRefs.current[next]?.focus();
    }
  };

  const onMenuKeyDown = (e) => {
    const items = [...(menuRef.current?.querySelectorAll('[role="menuitemradio"]') || [])];
    const i = items.indexOf(document.activeElement);
    let to = null;
    if (e.key === 'Escape' || e.key === 'Tab') { e.preventDefault(); closeMenu(true); return; }
    if (e.key === 'ArrowDown') to = items[(i + 1) % items.length];
    else if (e.key === 'ArrowUp') to = items[(i - 1 + items.length) % items.length];
    else if (e.key === 'Home') to = items[0];
    else if (e.key === 'End') to = items[items.length - 1];
    if (to) { e.preventDefault(); to.focus(); }
  };

  const mounted = opened.includes(active) ? opened : [...opened, active];

  return (
    <div className={s.shell}>
      <GlobalNavbar />

      <div className={s.header}>
        <div className={s.titleRow}>
          <h1 className={s.title}>{group.title}</h1>
          <p className={s.lead}>{group.description}</p>
        </div>
        <div className={s.tabs} role="tablist" aria-label={group.title} onKeyDown={onKeyDown}>
          {strip.map((x) => {
            if (x.tab) {
              const t = x.tab;
              return (
                <button
                  key={x.key}
                  ref={(el) => { tabRefs.current[x.key] = el; }}
                  type="button"
                  role="tab"
                  id={`tab-${t.id}`}
                  aria-selected={t.id === active}
                  aria-controls={`panel-${t.id}`}
                  tabIndex={t.id === active ? 0 : -1}
                  title={t.description}
                  className={s.tab}
                  onClick={() => select(t.id)}
                >
                  {t.label}
                </button>
              );
            }
            const current = x.tabs.find((t) => t.id === active);
            const isOpen = openMenu === x.key;
            return (
              <button
                key={x.key}
                ref={(el) => { tabRefs.current[x.key] = el; }}
                type="button"
                role="tab"
                id={`tab-${x.key}`}
                aria-selected={x.key === activeKey}
                aria-controls={current ? `panel-${current.id}` : undefined}
                aria-haspopup="menu"
                aria-expanded={isOpen}
                tabIndex={x.key === activeKey ? 0 : -1}
                title={x.tabs.map((t) => t.label).join(' · ')}
                className={s.tab}
                onClick={() => (isOpen ? closeMenu(false) : openMenuAt(x.key))}
                onKeyDown={(e) => {
                  if (e.key === 'ArrowDown' || e.key === 'Enter' || e.key === ' ') {
                    e.preventDefault();
                    e.stopPropagation();
                    openMenuAt(x.key);
                  }
                }}
              >
                {x.menu}
                {current && <span className={s.menuCurrent}>: {current.label}</span>}
                <span className={s.caret} aria-hidden="true">▾</span>
              </button>
            );
          })}
        </div>
      </div>

      {openMenu && menuPos && (
        <div
          ref={menuRef}
          role="menu"
          aria-labelledby={`tab-${openMenu}`}
          className={s.menu}
          style={{ top: menuPos.top, left: menuPos.left }}
          onKeyDown={onMenuKeyDown}
        >
          {strip.find((x) => x.key === openMenu).tabs.map((t) => (
            <button
              key={t.id}
              type="button"
              role="menuitemradio"
              aria-checked={t.id === active}
              tabIndex={-1}
              title={t.description}
              className={s.menuItem}
              onClick={() => { select(t.id); closeMenu(true); }}
            >
              {t.label}
            </button>
          ))}
        </div>
      )}

      <div className={s.panels}>
        <EmbeddedContext.Provider value={true}>
          {group.tabs.filter((t) => mounted.includes(t.id)).map((t) => {
            const View = VIEWS[t.id];
            return (
              <div
                key={t.id}
                id={`panel-${t.id}`}
                role="tabpanel"
                aria-labelledby={`tab-${t.menu ? stripKeyOf(t.id) : t.id}`}
                hidden={t.id !== active}
                className={s.panel}
              >
                <View />
              </div>
            );
          })}
        </EmbeddedContext.Provider>
      </div>
    </div>
  );
}
