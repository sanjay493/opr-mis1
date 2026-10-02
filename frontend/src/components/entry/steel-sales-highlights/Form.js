'use client';

import RequireEditor from '@/components/RequireEditor';
import { useState, useEffect, useCallback } from 'react';
import { EntryPage, ContextBar, Field, Status, SaveButton, entryStyles as es, wb } from '../EntryUI';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || '';

const MONTHS = [
  'April', 'May', 'June', 'July', 'August', 'September',
  'October', 'November', 'December', 'January', 'February', 'March',
];
const MONTH_NUM = {
  January: '01', February: '02', March: '03', April: '04',
  May: '05', June: '06', July: '07', August: '08',
  September: '09', October: '10', November: '11', December: '12',
};
const YEAR_RANGE_START = 2000;
const _now = new Date();
const CURRENT_FY_END_YEAR = (_now.getMonth() >= 3 ? _now.getFullYear() : _now.getFullYear() - 1) + 1;
const YEARS = Array.from(
  { length: CURRENT_FY_END_YEAR - YEAR_RANGE_START + 1 },
  (_, i) => String(YEAR_RANGE_START + i)
);

function getDefaultPeriod() {
  const d = new Date(); d.setMonth(d.getMonth() - 1);
  const names = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December'];
  return { monthName: names[d.getMonth()], year: String(d.getFullYear()) };
}

function SteelSalesHighlightsInner() {
  const def = getDefaultPeriod();
  const [monthName, setMonthName] = useState(def.monthName);
  const [year, setYear] = useState(def.year);
  const [monthItems, setMonthItems] = useState(['']);
  const [ytdItems, setYtdItems] = useState(['']);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [status, setStatus] = useState(null);
  const [meta, setMeta] = useState(null);

  const reportMonth = `${year}-${MONTH_NUM[monthName]}`;

  const load = useCallback(async () => {
    setLoading(true);
    setStatus(null);
    try {
      const res = await fetch(`${API_BASE_URL}/api/steel-sales-highlights?report_month=${reportMonth}`);
      const json = await res.json();
      if (!res.ok) throw new Error(json.detail || 'Load failed');
      setMonthItems(json.month_items?.length ? json.month_items : ['']);
      setYtdItems(json.ytd_items?.length ? json.ytd_items : ['']);
      setMeta(json.has_data ? { updated_by: json.updated_by, updated_at: json.updated_at } : null);
    } catch (err) {
      setStatus({ type: 'error', text: err.message });
    } finally {
      setLoading(false);
    }
  }, [reportMonth]);

  useEffect(() => { load(); }, [load]);

  const handleSave = async () => {
    setSaving(true);
    setStatus(null);
    try {
      const body = {
        report_month: reportMonth,
        month_items: monthItems.map((s) => s.trim()).filter(Boolean),
        ytd_items: ytdItems.map((s) => s.trim()).filter(Boolean),
      };
      const res = await fetch(`${API_BASE_URL}/api/steel-sales-highlights/save`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify(body),
      });
      const json = await res.json();
      if (!res.ok) throw new Error(json.detail || 'Save failed');
      setStatus({ type: 'success', text: `✓ Saved for ${reportMonth}` });
      load();
    } catch (err) {
      setStatus({ type: 'error', text: err.message });
    } finally {
      setSaving(false);
    }
  };

  const renderBulletList = (items, setItems) => (
    <>
      {items.map((s, i) => (
        <div key={i} style={{ display: 'flex', gap: 8, alignItems: 'flex-start', marginBottom: 8 }}>
          <textarea
            className={wb.textarea} style={{ minHeight: 38 }} aria-label={`Bullet ${i + 1}`}
            placeholder="Highlight bullet (e.g. Cash Collection ~11,868 Cr (23% YoY growth; CPLY : 9,665 Cr))"
            value={s}
            onChange={(e) => setItems((v) => v.map((x, j) => (j === i ? e.target.value : x)))}
          />
          <button type="button" className={wb.iconBtn} title="Remove" aria-label="Remove"
                  onClick={() => setItems((v) => v.filter((_, j) => j !== i))}>✕</button>
        </div>
      ))}
      <button type="button" className={wb.btn} onClick={() => setItems((v) => [...v, ''])}>+ Add bullet</button>
    </>
  );

  const card = (color, title, sub, body) => (
    <div className={es.section} style={{ borderTop: `3px solid ${color}` }}>
      <div className={es.sectionHead}>
        <div>
          <h3 className={es.sectionTitle} style={{ color }}>{title}</h3>
          <p className={es.sectionSub}>{sub}</p>
        </div>
      </div>
      <div className={es.sectionBody}>{body}</div>
    </div>
  );

  return (
    <EntryPage
      maxWidth={900}
      title="Steel Sales Performance — Manual Entry"
      description={<>
        Report-month and Apr-to-report-month (YTD) Key Performance Parameter bullets for the{' '}
        <a href="/report">Steel Sales Performance</a>{' '}report page. These are a
        written bulletin — nothing here is computed, so the report page shows exactly what&apos;s saved here for
        the selected month, and stays blank until something is. One bullet per box; a bullet can span multiple
        lines (press Enter) if it needs to wrap the way it will print — e.g. a comma-list of products.
      </>}
    >
      <ContextBar actions={<>
        {loading && <span className={es.ctxNote}>Loading…</span>}
        {meta && <span className={es.ctxNote}>Last saved by {meta.updated_by || 'unknown'} at {meta.updated_at}</span>}
        <SaveButton saving={saving} dirty={!loading} onClick={handleSave} />
      </>}>
        <Field label="Report month" htmlFor="ssh-month">
          <select id="ssh-month" className={es.control} value={monthName} onChange={(e) => setMonthName(e.target.value)}>
            {MONTHS.map((m) => <option key={m}>{m}</option>)}
          </select>
          <select className={es.control} value={year} onChange={(e) => setYear(e.target.value)} aria-label="Year">
            {YEARS.map((y) => <option key={y}>{y}</option>)}
          </select>
        </Field>
      </ContextBar>

      <Status status={status} />

      {card('var(--ui-primary)', <>{monthName}&apos;{year.slice(2)} Key Performance Parameters</>,
        'One bullet per line item (Cash Collection, Total Sales, Tier-1/Tier-2 sales, despatch figures, etc.) for the report month itself.',
        renderBulletList(monthItems, setMonthItems))}

      {card('var(--ui-success)', <>April-{monthName}&apos;{year.slice(2)} Key Performance Parameters</>,
        'Same bullets, cumulative Apr-to-report-month (YTD).',
        renderBulletList(ytdItems, setYtdItems))}

      <div className={es.foot}>
        <SaveButton saving={saving} dirty={!loading} onClick={handleSave} />
      </div>
    </EntryPage>
  );
}

export default function SteelSalesHighlightsPage() {
  return (
    <RequireEditor>
      <SteelSalesHighlightsInner />
    </RequireEditor>
  );
}
