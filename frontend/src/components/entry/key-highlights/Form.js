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

const emptyAchievement = () => ({ text: '', subsText: '' });
const emptyFocusArea = () => ({ title: '', description: '' });

function KeyHighlightsManualInner() {
  const def = getDefaultPeriod();
  const [monthName, setMonthName] = useState(def.monthName);
  const [year, setYear] = useState(def.year);
  const [achievements, setAchievements] = useState([emptyAchievement()]);
  const [shortfalls, setShortfalls] = useState(['']);
  const [focusAreas, setFocusAreas] = useState([emptyFocusArea()]);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [status, setStatus] = useState(null);
  const [meta, setMeta] = useState(null);

  const reportMonth = `${year}-${MONTH_NUM[monthName]}`;

  const load = useCallback(async () => {
    setLoading(true);
    setStatus(null);
    try {
      const res = await fetch(`${API_BASE_URL}/api/key-highlights?report_month=${reportMonth}`);
      const json = await res.json();
      if (!res.ok) throw new Error(json.detail || 'Load failed');
      setAchievements(
        json.achievements?.length
          ? json.achievements.map((a) => ({ text: a.text || '', subsText: (a.subs || []).join('\n') }))
          : [emptyAchievement()]
      );
      setShortfalls(json.shortfalls?.length ? json.shortfalls : ['']);
      setFocusAreas(json.focus_areas?.length ? json.focus_areas : [emptyFocusArea()]);
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
        achievements: achievements
          .filter((a) => a.text.trim())
          .map((a) => ({
            text: a.text.trim(),
            subs: a.subsText.split('\n').map((s) => s.trim()).filter(Boolean),
          })),
        shortfalls: shortfalls.map((s) => s.trim()).filter(Boolean),
        focus_areas: focusAreas
          .filter((f) => f.title.trim() || f.description.trim())
          .map((f) => ({ title: f.title.trim(), description: f.description.trim() })),
      };
      const res = await fetch(`${API_BASE_URL}/api/key-highlights/save`, {
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

  const rowStyle = { display: 'flex', gap: 8, alignItems: 'flex-start', marginBottom: 10 };
  const removeBtn = (onClick) => (
    <button type="button" className={wb.iconBtn} onClick={onClick} title="Remove" aria-label="Remove">✕</button>
  );
  const accent = (color) => ({ borderTop: `3px solid ${color}` });

  return (
    <EntryPage
      maxWidth={900}
      title="Key Highlights & Variances — Manual Entry"
      description={<>
        Major Achievements, Major Shortfalls / Areas of Concern, and Focus Areas Going Forward for the{' '}
        <a href="/report">Key Highlights &amp; Variances</a>{' '}report page. These are a
        written read of the month — nothing here is computed, so the report page shows exactly what&apos;s saved
        here for the selected month, and stays blank until something is.
      </>}
    >
      <ContextBar actions={<>
        {loading && <span className={es.ctxNote}>Loading…</span>}
        {meta && <span className={es.ctxNote}>Last saved by {meta.updated_by || 'unknown'} at {meta.updated_at}</span>}
        <SaveButton saving={saving} dirty={!loading} onClick={handleSave} />
      </>}>
        <Field label="Report month" htmlFor="kh-month">
          <select id="kh-month" className={es.control} value={monthName} onChange={(e) => setMonthName(e.target.value)}>
            {MONTHS.map((m) => <option key={m}>{m}</option>)}
          </select>
          <select className={es.control} value={year} onChange={(e) => setYear(e.target.value)} aria-label="Year">
            {YEARS.map((y) => <option key={y}>{y}</option>)}
          </select>
        </Field>
      </ContextBar>

      <Status status={status} />

      {/* Major Achievements */}
      <div style={accent('var(--ui-success)')} className={es.section}>
        <div className={es.sectionHead}>
          <div>
            <h3 className={es.sectionTitle} style={{ color: 'var(--ui-success)' }}>Major Achievements</h3>
            <p className={es.sectionSub}>One line per achievement. Optional sub-points (e.g. record breakdown) — one per line, indented under the achievement.</p>
          </div>
        </div>
        <div className={es.sectionBody}>
          {achievements.map((a, i) => (
            <div key={i} style={rowStyle}>
              <div style={{ flex: 1 }}>
                <input type="text" className={wb.input} placeholder="Achievement" aria-label={`Achievement ${i + 1}`}
                       value={a.text}
                       onChange={(e) => setAchievements((v) => v.map((x, j) => (j === i ? { ...x, text: e.target.value } : x)))} />
                <textarea className={wb.textarea} style={{ marginTop: 6, minHeight: 44 }}
                          placeholder="Sub-points (optional, one per line)" aria-label={`Achievement ${i + 1} sub-points`}
                          value={a.subsText}
                          onChange={(e) => setAchievements((v) => v.map((x, j) => (j === i ? { ...x, subsText: e.target.value } : x)))} />
              </div>
              {removeBtn(() => setAchievements((v) => v.filter((_, j) => j !== i)))}
            </div>
          ))}
          <button type="button" className={wb.btn} onClick={() => setAchievements((v) => [...v, emptyAchievement()])}>+ Add achievement</button>
        </div>
      </div>

      {/* Major Shortfalls */}
      <div style={accent('var(--ui-danger)')} className={es.section}>
        <div className={es.sectionHead}>
          <div>
            <h3 className={es.sectionTitle} style={{ color: 'var(--ui-danger)' }}>Major Shortfalls / Areas of Concern</h3>
            <p className={es.sectionSub}>One line per shortfall/concern.</p>
          </div>
        </div>
        <div className={es.sectionBody}>
          {shortfalls.map((s, i) => (
            <div key={i} style={{ ...rowStyle, alignItems: 'center' }}>
              <input type="text" className={wb.input} placeholder="Shortfall / area of concern" aria-label={`Shortfall ${i + 1}`}
                     value={s}
                     onChange={(e) => setShortfalls((v) => v.map((x, j) => (j === i ? e.target.value : x)))} />
              {removeBtn(() => setShortfalls((v) => v.filter((_, j) => j !== i)))}
            </div>
          ))}
          <button type="button" className={wb.btn} onClick={() => setShortfalls((v) => [...v, ''])}>+ Add shortfall</button>
        </div>
      </div>

      {/* Focus Areas Going Forward */}
      <div style={accent('var(--ui-primary)')} className={es.section}>
        <div className={es.sectionHead}>
          <div>
            <h3 className={es.sectionTitle} style={{ color: 'var(--ui-primary)' }}>Focus Areas Going Forward</h3>
            <p className={es.sectionSub}>Short title + one-line description for each focus area.</p>
          </div>
        </div>
        <div className={es.sectionBody}>
          {focusAreas.map((f, i) => (
            <div key={i} style={rowStyle}>
              <div style={{ flex: 1 }}>
                <input type="text" className={wb.input} placeholder="Title (e.g. Improve BF Productivity)" aria-label={`Focus area ${i + 1} title`}
                       value={f.title}
                       onChange={(e) => setFocusAreas((v) => v.map((x, j) => (j === i ? { ...x, title: e.target.value } : x)))} />
                <input type="text" className={wb.input} style={{ marginTop: 6 }} placeholder="Description" aria-label={`Focus area ${i + 1} description`}
                       value={f.description}
                       onChange={(e) => setFocusAreas((v) => v.map((x, j) => (j === i ? { ...x, description: e.target.value } : x)))} />
              </div>
              {removeBtn(() => setFocusAreas((v) => v.filter((_, j) => j !== i)))}
            </div>
          ))}
          <button type="button" className={wb.btn} onClick={() => setFocusAreas((v) => [...v, emptyFocusArea()])}>+ Add focus area</button>
        </div>
      </div>

      <div className={es.foot}>
        <SaveButton saving={saving} dirty={!loading} onClick={handleSave} />
      </div>
    </EntryPage>
  );
}

export default function KeyHighlightsManualPage() {
  return (
    <RequireEditor>
      <KeyHighlightsManualInner />
    </RequireEditor>
  );
}
