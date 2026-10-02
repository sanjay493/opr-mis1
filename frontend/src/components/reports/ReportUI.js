'use client';

// Shared building blocks for the report views (components/reports/<slug>/
// View.js and components/techno/*View.js) so every /reports/* tab has the
// same Stitch "workbench" look as the data-entry forms. The pieces are the
// entry ones (EntryUI) plus a `fill` page mode for reports whose table
// should take the remaining height and scroll on its own.

import GlobalNavbar from '@/components/GlobalNavbar';
import wb from '@/styles/wb.module.css';
import e from '../entry/entryUI.module.css';
import r from './reportUI.module.css';

export { ContextBar as FilterBar, Field, Status, Section, Loading } from '../entry/EntryUI';
export { e as entryStyles, r as reportStyles, wb };

// Page frame. `fill` makes the content a full-height flex column — give the
// element that should scroll className={reportStyles.grow}.
export function ReportPage({ title, description, actions, maxWidth, fill = false, children }) {
  return (
    <div className={wb.shell}>
      <GlobalNavbar />
      <div className={`${wb.page} ${fill ? r.fillPage : ''}`}>
        <div className={`${e.inner} ${fill ? r.fillInner : ''}`} style={maxWidth ? { maxWidth } : undefined}>
          {(title || description || actions) && (
            <div className={e.intro} style={actions ? { display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 16, flexWrap: 'wrap' } : undefined}>
              <div>
                {title && <h2 className={e.title}>{title}</h2>}
                {description && <p className={e.desc}>{description}</p>}
              </div>
              {actions && <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'center' }}>{actions}</div>}
            </div>
          )}
          {children}
        </div>
      </div>
    </div>
  );
}

// Segmented toggle: options = [{ id, label }]
export function Toggle({ options, value, onChange, label }) {
  return (
    <div className={wb.seg} role="group" aria-label={label}>
      {options.map((o) => (
        <button key={String(o.id)} type="button" aria-pressed={value === o.id}
                className={`${wb.segBtn} ${value === o.id ? wb.segBtnActive : ''}`}
                onClick={() => onChange(o.id)}>
          {o.label}
        </button>
      ))}
    </div>
  );
}

export function Empty({ children }) {
  return <div className={wb.empty}>{children}</div>;
}
