'use client';

import { useCallback, useRef, useState } from 'react';
import dynamic from 'next/dynamic';
import { usePathname, useRouter, useSearchParams } from 'next/navigation';
import GlobalNavbar from '@/components/GlobalNavbar';
import RequireEditor from '@/components/RequireEditor';
import { EmbeddedContext } from '@/components/EmbeddedContext';
import { groupById } from './entryGroups';
import s from './EntryTabs.module.css';

const loading = () => <div className={s.loading}>Loading…</div>;

// One lazily-loaded form per tab id (import paths must be static).
const FORMS = {
  'production': dynamic(() => import('./production/Form'), { loading }),
  'production-range': dynamic(() => import('./production-range/Form'), { loading }),
  'techno-manual': dynamic(() => import('./techno-manual/Form'), { loading }),
  'techno-correction': dynamic(() => import('./techno-correction/Form'), { loading }),
  'bf-large-snapshot': dynamic(() => import('./bf-large-snapshot/Form'), { loading }),
  'key-parameters-manual': dynamic(() => import('./key-parameters-manual/Form'), { loading }),
  'co2-water-pm-manual': dynamic(() => import('./co2-water-pm-manual/Form'), { loading }),
  'sail-mines': dynamic(() => import('./sail-mines/Form'), { loading }),
  'mines-production-despatch': dynamic(() => import('./mines-production-despatch/Form'), { loading }),
  'special-steel': dynamic(() => import('./special-steel/Form'), { loading }),
  'special-steel-grade-clubs': dynamic(() => import('./special-steel-grade-clubs/Form'), { loading }),
  'special-steel-physical': dynamic(() => import('./special-steel-physical/Form'), { loading }),
  'special-steel-ipt': dynamic(() => import('./special-steel-ipt/Form'), { loading }),
  'key-highlights': dynamic(() => import('./key-highlights/Form'), { loading }),
  'steel-sales-highlights': dynamic(() => import('./steel-sales-highlights/Form'), { loading }),
  'market-intel': dynamic(() => import('./market-intel/Form'), { loading }),
  'bf-benchmark': dynamic(() => import('./bf-benchmark/Form'), { loading }),
  'rail-report': dynamic(() => import('./rail-report/Form'), { loading }),
  'ready-reckoner': dynamic(() => import('./ready-reckoner/Form'), { loading }),
  'major-unit-daily': dynamic(() => import('./major-unit-daily/Form'), { loading }),
  'cover-photos': dynamic(() => import('./cover-photos/Form'), { loading }),
};

/**
 * A grouped entry page: one tab per form. The active tab is in the URL
 * (?tab=<id>) so every tab can be linked to and bookmarked. A tab is mounted
 * the first time it's opened and then kept mounted (hidden) while another
 * tab is shown, so switching tabs never discards unsaved edits in a form.
 */
export default function EntryTabs({ groupId }) {
  const group = groupById(groupId);
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();

  const requested = searchParams.get('tab');
  const active = group.tabs.some((t) => t.id === requested) ? requested : group.tabs[0].id;

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
    <RequireEditor>
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
              const Form = FORMS[t.id];
              return (
                <div
                  key={t.id}
                  id={`panel-${t.id}`}
                  role="tabpanel"
                  aria-labelledby={`tab-${t.id}`}
                  hidden={t.id !== active}
                  className={s.panel}
                >
                  <Form />
                </div>
              );
            })}
          </EmbeddedContext.Provider>
        </div>
      </div>
    </RequireEditor>
  );
}
