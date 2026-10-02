'use client';

// Shared building blocks for the manual-entry forms so every tab under
// /data-entry/* has the same Stitch "Data Workbench" look. Styles live in
// entryUI.module.css (entry-specific) and styles/wb.module.css (generic).

import GlobalNavbar from '@/components/GlobalNavbar';
import wb from '@/styles/wb.module.css';
import e from './entryUI.module.css';

export { e as entryStyles, wb };

// Page frame: full-height scroll area (fills the tab panel when embedded),
// with an optional title + description line above the form.
export function EntryPage({ title, description, maxWidth, children }) {
  return (
    <div className={wb.shell}>
      <GlobalNavbar />
      <div className={wb.page}>
        <div className={e.inner} style={maxWidth ? { maxWidth } : undefined}>
          {(title || description) && (
            <div className={e.intro}>
              {title && <h2 className={e.title}>{title}</h2>}
              {description && <p className={e.desc}>{description}</p>}
            </div>
          )}
          {children}
        </div>
      </div>
    </div>
  );
}

// Bar of selectors (month, plant …) with right-aligned actions.
export function ContextBar({ children, actions }) {
  return (
    <div className={e.ctxBar}>
      {children}
      {actions && <div className={e.ctxEnd}>{actions}</div>}
    </div>
  );
}

export function Field({ label, htmlFor, children }) {
  return (
    <div className={e.ctxField}>
      {label && <label className={e.ctxLabel} htmlFor={htmlFor}>{label}</label>}
      <div className={e.ctxRow}>{children}</div>
    </div>
  );
}

// status = { type: 'success' | 'error' | 'info', text } | null
export function Status({ status, style }) {
  if (!status || !status.text) return null;
  const cls = status.type === 'success' ? wb.alertSuccess : status.type === 'info' ? wb.alertInfo : wb.alertError;
  return (
    <div role={status.type === 'error' ? 'alert' : 'status'} className={`${wb.alert} ${cls}`} style={style}>
      {status.text}
    </div>
  );
}

export function Section({ title, sub, actions, children, flush = true }) {
  return (
    <section className={e.section}>
      {(title || actions) && (
        <div className={e.sectionHead}>
          <div>
            {title && <h3 className={e.sectionTitle}>{title}</h3>}
            {sub && <p className={e.sectionSub}>{sub}</p>}
          </div>
          {actions}
        </div>
      )}
      {flush ? <div className={e.tableWrap}>{children}</div> : <div className={e.sectionBody}>{children}</div>}
    </section>
  );
}

// Green save button that only lights up when there is something to save.
export function SaveButton({ dirty = true, saving, onClick, children = 'Save', savingText = 'Saving…', type = 'button' }) {
  return (
    <button type={type} onClick={onClick} disabled={saving || !dirty} aria-busy={saving}
            className={`${wb.btn} ${wb.btnSuccess}`}>
      {saving ? savingText : children}
    </button>
  );
}

// Class for a table-cell input given its edit state.
export function cellClass({ changed, filled, text } = {}) {
  return [e.cell, text && e.cellText, changed ? e.cellChanged : filled ? e.cellFilled : ''].filter(Boolean).join(' ');
}

export function Loading({ children = 'Loading…' }) {
  return <div className={e.loading}>{children}</div>;
}
