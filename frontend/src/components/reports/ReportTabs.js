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
  'special-steel-fy': dynamic(() => import('./special-steel-fy/View'), { loading }),
  'special-steel-physical': dynamic(() => import('./special-steel-physical/View'), { loading }),
  'ipt-fy': dynamic(() => import('./ipt-fy/View'), { loading }),
  'iron-ore-mines': dynamic(() => import('./iron-ore-mines/View'), { loading }),
  'bf-benchmark': dynamic(() => import('./bf-benchmark/View'), { loading }),
  'production-loss-analysis': dynamic(() => import('./production-loss-analysis/View'), { loading }),
  'breakdown-analysis': dynamic(() => import('./breakdown-analysis/View'), { loading }),
  'capital-repair-calendar': dynamic(() => import('./capital-repair-calendar/View'), { loading }),
  'highlights': dynamic(() => import('./highlights/View'), { loading }),
  'major-production': dynamic(() => import('./major-production/View'), { loading }),
  'records-matrix': dynamic(() => import('./records-matrix/View'), { loading }),
  'techno-records': dynamic(() => import('./techno-records/View'), { loading }),
  'new-facilities': dynamic(() => import('./new-facilities/View'), { loading }),
  'do-letter': dynamic(() => import('./do-letter/View'), { loading }),
  'jpc-report': dynamic(() => import('./jpc-report/View'), { loading }),
  'one-page-report': dynamic(() => import('./one-page-report/View'), { loading }),
  'pmix-fy': dynamic(() => import('./pmix-fy/View'), { loading }),
  'sefi': dynamic(() => import('./sefi/View'), { loading }),
  'steel-bulletin': dynamic(() => import('./steel-bulletin/View'), { loading }),
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

  // Arrow-key navigation between tabs (WAI-ARIA tabs pattern).
  const tabRefs = useRef({});
  const onKeyDown = (e) => {
    const ids = group.tabs.map((t) => t.id);
    const i = ids.indexOf(active);
    let next = null;
    if (e.key === 'ArrowRight') next = ids[(i + 1) % ids.length];
    else if (e.key === 'ArrowLeft') next = ids[(i - 1 + ids.length) % ids.length];
    else if (e.key === 'Home') next = ids[0];
    else if (e.key === 'End') next = ids[ids.length - 1];
    if (next) {
      e.preventDefault();
      select(next);
      tabRefs.current[next]?.focus();
    }
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
          {group.tabs.map((t) => (
            <button
              key={t.id}
              ref={(el) => { tabRefs.current[t.id] = el; }}
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
          ))}
        </div>
      </div>

      <div className={s.panels}>
        <EmbeddedContext.Provider value={true}>
          {group.tabs.filter((t) => mounted.includes(t.id)).map((t) => {
            const View = VIEWS[t.id];
            return (
              <div
                key={t.id}
                id={`panel-${t.id}`}
                role="tabpanel"
                aria-labelledby={`tab-${t.id}`}
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
