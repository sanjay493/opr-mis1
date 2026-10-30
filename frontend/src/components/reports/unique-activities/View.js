'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import DateTimeText from '@/components/DateTimeText';
import ActivityCard from '@/components/unique-activities/ActivityCard';
import { uaApi } from '@/components/unique-activities/uaApi';
import ua from '@/components/unique-activities/ua.module.css';
import { ReportPage, FilterBar, Field, Status, Loading, Empty, wb } from '../ReportUI';

const NO_FILTERS = { q: '', tag: '', plant: '', from: '', to: '' };

export default function UniqueActivitiesView() {
  const [filters, setFilters] = useState(NO_FILTERS);
  const [text, setText] = useState('');             // search box, applied after a pause
  const [activities, setActivities] = useState(null);
  const [meta, setMeta] = useState({ tags: [], plants: [] });
  const [status, setStatus] = useState(null);
  const [resetKey, setResetKey] = useState(0);      // remounts the date boxes on Clear

  useEffect(() => {
    uaApi.tags().then(setMeta).catch(() => {});
  }, []);

  useEffect(() => {
    const t = setTimeout(() => setFilters((f) => (f.q === text.trim() ? f : { ...f, q: text.trim() })), 300);
    return () => clearTimeout(t);
  }, [text]);

  useEffect(() => {
    let live = true;
    uaApi.list(filters)
      .then((list) => { if (live) { setActivities(list); setStatus(null); } })
      .catch((e) => { if (live) setStatus({ type: 'error', text: e.message }); });
    return () => { live = false; };
  }, [filters]);

  const set = (patch) => setFilters((f) => ({ ...f, ...patch }));
  const toggleTag = (tag) => set({ tag: filters.tag.toLowerCase() === tag.toLowerCase() ? '' : tag });
  const clear = () => { setFilters(NO_FILTERS); setText(''); setResetKey((k) => k + 1); };
  const filtered = Object.values(filters).some(Boolean);

  return (
    <ReportPage
      title="Unique Activities"
      description="One-off events on record: new units started, revivals after prolonged capital repair, first-ever products and other milestones. Search the text, or pick a tag."
      actions={<Link href="/data-entry/reference?tab=unique-activities" className={`${wb.btn} ${wb.btnSm}`}>＋ Record an activity</Link>}
      maxWidth={1100}
    >
      <FilterBar actions={filtered && <button type="button" className={`${wb.btn} ${wb.btnSm}`} onClick={clear}>Clear</button>}>
        <Field label="Search" htmlFor="ua-q">
          <input id="ua-q" className={wb.input} style={{ width: 260 }} value={text}
                 placeholder="Title, text, unit or tag…" onChange={(e) => setText(e.target.value)} />
        </Field>
        <Field label="Plant" htmlFor="ua-plant">
          <select id="ua-plant" className={wb.select} value={filters.plant} onChange={(e) => set({ plant: e.target.value })}>
            <option value="">All</option>
            {meta.plants.map((p) => <option key={p} value={p}>{p}</option>)}
          </select>
        </Field>
        <Field label="From">
          <DateTimeText key={`f${resetKey}`} value={filters.from} onChange={(v) => set({ from: v })}
                        inputClassName={wb.input} inputStyle={{ width: 120 }} buttonClassName={`${wb.btn} ${wb.btnSm}`} />
        </Field>
        <Field label="To">
          <DateTimeText key={`t${resetKey}`} value={filters.to} onChange={(v) => set({ to: v })}
                        inputClassName={wb.input} inputStyle={{ width: 120 }} buttonClassName={`${wb.btn} ${wb.btnSm}`} />
        </Field>
      </FilterBar>

      {meta.tags.length > 0 && (
        <div className={wb.chips} style={{ margin: '0 0 14px' }} role="group" aria-label="Filter by tag">
          {meta.tags.map(({ tag, count }) => {
            const on = filters.tag.toLowerCase() === tag.toLowerCase();
            return (
              <button key={tag} type="button" aria-pressed={on} onClick={() => toggleTag(tag)}
                      className={`${wb.chip} ${on ? wb.chipActive : ''}`}>
                #{tag}<span className={wb.chipCount}>{count}</span>
              </button>
            );
          })}
        </div>
      )}

      <Status status={status} />
      {activities === null ? <Loading /> : activities.length === 0 ? (
        <Empty>{filtered ? 'No activity matches these filters.' : 'No activities recorded yet.'}</Empty>
      ) : (
        <>
          <div className={wb.muted} style={{ fontSize: 12, margin: '0 0 8px' }}>
            {activities.length} activit{activities.length === 1 ? 'y' : 'ies'}, newest first
          </div>
          <div className={ua.list}>
            {activities.map((a) => <ActivityCard key={a.id} activity={a} onTag={toggleTag} />)}
          </div>
        </>
      )}
    </ReportPage>
  );
}
