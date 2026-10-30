'use client';

import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import Link from 'next/link';
import RequireEditor from '@/components/RequireEditor';
import DateTimeText from '@/components/DateTimeText';
import ActivityCard from '@/components/unique-activities/ActivityCard';
import TagInput from '@/components/unique-activities/TagInput';
import { uaApi } from '@/components/unique-activities/uaApi';
import ua from '@/components/unique-activities/ua.module.css';
import { EntryPage, Section, Status, Loading, SaveButton, wb } from '../EntryUI';

const EMPTY = { activity_date: '', plant_code: '', unit_name: '', title: '', description: '', tags: [] };

function draftOf(a) {
  return {
    activity_date: a.activity_date, plant_code: a.plant_code || '', unit_name: a.unit_name || '',
    title: a.title, description: a.description, tags: [...a.tags],
  };
}

function UniqueActivitiesInner() {
  const [activities, setActivities] = useState(null);
  const [meta, setMeta] = useState({ tags: [], suggested: [], plants: [] });
  const [draft, setDraft] = useState(EMPTY);
  const [editId, setEditId] = useState(null);       // null = new activity
  const [formKey, setFormKey] = useState(0);        // remounts the date box on reset / edit
  const [saving, setSaving] = useState(false);
  const [status, setStatus] = useState(null);
  const [q, setQ] = useState('');
  const formRef = useRef(null);

  const load = useCallback(() => Promise.all([uaApi.list(), uaApi.tags()])
    .then(([list, m]) => { setActivities(list); setMeta(m); })
    .catch((e) => setStatus({ type: 'error', text: e.message })), []);

  useEffect(() => { load(); }, [load]);

  const set = (patch) => setDraft((d) => ({ ...d, ...patch }));
  const reset = () => { setDraft(EMPTY); setEditId(null); setFormKey((k) => k + 1); };

  const startEdit = (a) => {
    setDraft(draftOf(a));
    setEditId(a.id);
    setFormKey((k) => k + 1);
    setStatus(null);
    formRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' });
  };

  const missing = !draft.activity_date ? 'Enter the activity date as dd/mm/yyyy'
    : !draft.title.trim() ? 'Enter a title'
    : !draft.description.trim() ? 'Write the description' : null;

  const save = async () => {
    if (missing) { setStatus({ type: 'error', text: missing }); return; }
    setSaving(true);
    setStatus(null);
    try {
      const body = { ...draft, plant_code: draft.plant_code || null, unit_name: draft.unit_name || null };
      if (editId) await uaApi.update(editId, body);
      else await uaApi.add(body);
      setStatus({ type: 'success', text: editId ? 'Activity updated.' : 'Activity recorded.' });
      reset();
      load();
    } catch (e) {
      setStatus({ type: 'error', text: e.message });
    } finally {
      setSaving(false);
    }
  };

  const remove = async (a) => {
    if (!window.confirm(`Delete "${a.title}"? This cannot be undone.`)) return;
    try {
      await uaApi.remove(a.id);
      if (editId === a.id) reset();
      setStatus({ type: 'success', text: `Deleted "${a.title}".` });
    } catch (e) {
      setStatus({ type: 'error', text: e.message });
    }
    load();
  };

  // Tags already in use first (most used), then the standard ones.
  const suggestions = useMemo(() => {
    const used = meta.tags.map((t) => t.tag);
    return [...used, ...meta.suggested.filter((t) => !used.some((u) => u.toLowerCase() === t.toLowerCase()))];
  }, [meta]);

  const shown = useMemo(() => {
    const needle = q.trim().toLowerCase();
    if (!activities || !needle) return activities;
    return activities.filter((a) => `${a.title} ${a.description} ${a.unit_name || ''} ${a.plant_code || ''} ${a.tags.join(' ')}`
      .toLowerCase().includes(needle));
  }, [activities, q]);

  return (
    <EntryPage
      title="Unique Activities"
      description={<>Record one-off events worth keeping: a new unit started, a unit revived after a prolonged capital repair, a first-ever product or a milestone. Give each a title, a paragraph and tags so it can be found later on the <Link href="/reports/highlights-records?tab=unique-activities">Unique Activities</Link> page.</>}
      maxWidth={1100}
    >
      <Status status={status} />

      <div ref={formRef} />
      <Section
        title={editId ? 'Edit activity' : 'New activity'}
        sub={editId ? 'Change the fields and save; Cancel leaves the activity as it was.' : 'Date, title and description are required.'}
        flush={false}
      >
        <div className={ua.form}>
          <div>
            <label className={wb.label} htmlFor="ua-date">Date</label>
            <DateTimeText key={formKey} id="ua-date" value={draft.activity_date}
                          onChange={(v) => set({ activity_date: v })}
                          inputClassName={wb.input} buttonClassName={`${wb.btn} ${wb.btnSm}`} />
          </div>
          <div>
            <label className={wb.label} htmlFor="ua-plant">Plant</label>
            <select id="ua-plant" className={wb.select} value={draft.plant_code}
                    onChange={(e) => set({ plant_code: e.target.value })}>
              <option value="">— none —</option>
              {meta.plants.map((p) => <option key={p} value={p}>{p}</option>)}
            </select>
          </div>
          <div>
            <label className={wb.label} htmlFor="ua-unit">Unit (optional)</label>
            <input id="ua-unit" className={wb.input} value={draft.unit_name} maxLength={64}
                   placeholder="e.g. BF-3, Sinter Plant-3, CRM-3" onChange={(e) => set({ unit_name: e.target.value })} />
          </div>
          <div className={ua.full}>
            <label className={wb.label} htmlFor="ua-title">Title</label>
            <input id="ua-title" className={wb.input} value={draft.title} maxLength={200}
                   placeholder="e.g. BF-3 blown in after 14-month capital repair"
                   onChange={(e) => set({ title: e.target.value })} />
          </div>
          <div className={ua.full}>
            <label className={wb.label} htmlFor="ua-text">Description</label>
            <textarea id="ua-text" className={wb.textarea} rows={6} value={draft.description}
                      placeholder="What happened, when, and why it matters."
                      onChange={(e) => set({ description: e.target.value })} />
          </div>
          <div className={ua.full}>
            <label className={wb.label} htmlFor="ua-tags">Tags</label>
            <TagInput id="ua-tags" value={draft.tags} onChange={(tags) => set({ tags })} suggestions={suggestions} />
          </div>
        </div>
        <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end', marginTop: 14 }}>
          {(editId || draft !== EMPTY) && (
            <button type="button" className={wb.btn} onClick={() => { reset(); setStatus(null); }}>Cancel</button>
          )}
          <SaveButton saving={saving} onClick={save}>{editId ? 'Save changes' : 'Record activity'}</SaveButton>
        </div>
      </Section>

      <Section
        title="Recorded activities"
        sub={activities ? `${activities.length} activit${activities.length === 1 ? 'y' : 'ies'}, newest first` : ''}
        actions={(
          <input className={wb.input} style={{ width: 240 }} value={q} placeholder="Search title, text or tag…"
                 onChange={(e) => setQ(e.target.value)} aria-label="Search recorded activities" />
        )}
        flush={false}
      >
        {shown === null ? <Loading /> : shown.length === 0 ? (
          <div className={wb.empty}>{activities.length === 0 ? 'No activities recorded yet.' : 'No activity matches the search.'}</div>
        ) : (
          <div className={ua.list}>
            {shown.map((a) => (
              <ActivityCard key={a.id} activity={a} onTag={setQ} actions={(
                <>
                  <button type="button" className={`${wb.btn} ${wb.btnSm}`} onClick={() => startEdit(a)}>Edit</button>
                  <button type="button" className={`${wb.btn} ${wb.btnSm} ${wb.btnDanger}`} onClick={() => remove(a)}>Delete</button>
                </>
              )} />
            ))}
          </div>
        )}
      </Section>
    </EntryPage>
  );
}

export default function UniqueActivitiesForm() {
  return (
    <RequireEditor>
      <UniqueActivitiesInner />
    </RequireEditor>
  );
}
