'use client';

import RequireEditor from '@/components/RequireEditor';
import { useState, useEffect, useCallback } from 'react';
import GlobalNavbar from '@/components/GlobalNavbar';

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

  const selStyle = {
    padding: '8px 12px', fontSize: '11pt', border: '1px solid #dadce0',
    borderRadius: '6px', backgroundColor: '#ffffff', color: '#202124', cursor: 'pointer',
  };
  const inputStyle = {
    width: '100%', padding: '7px 10px', fontSize: '10.5pt',
    border: '1px solid #dadce0', borderRadius: '4px', boxSizing: 'border-box',
  };
  const sectionCard = (borderColor) => ({
    border: `1px solid ${borderColor}`, borderRadius: '8px', padding: '16px 18px', marginBottom: '20px',
  });
  const removeBtn = {
    background: 'none', border: 'none', color: '#d93025', cursor: 'pointer',
    fontSize: '10pt', padding: '2px 6px', flexShrink: 0,
  };
  const addBtn = {
    padding: '6px 14px', fontSize: '10pt', fontWeight: 600, border: '1px solid #1a73e8',
    borderRadius: '6px', background: '#fff', color: '#1a73e8', cursor: 'pointer',
  };

  return (
    <div style={{ minHeight: '100vh', backgroundColor: '#ffffff' }}>
      <GlobalNavbar />
      <div style={{ maxWidth: '820px', margin: '0 auto', padding: '32px' }}>
        <h1 style={{ fontSize: '20pt', fontWeight: 900, color: '#202124', margin: 0 }}>
          Key Highlights &amp; Variances — Manual Entry
        </h1>
        <p style={{ fontSize: '11pt', color: '#5f6368', marginTop: '6px', marginBottom: '24px' }}>
          Major Achievements, Major Shortfalls / Areas of Concern, and Focus Areas Going Forward for the{' '}
          <a href="/report" style={{ color: '#1a73e8' }}>Key Highlights &amp; Variances</a> report page. These are a
          written read of the month — nothing here is computed, so the report page shows exactly what&apos;s saved
          here for the selected month, and stays blank until something is.
        </p>

        <div style={{
          display: 'flex', alignItems: 'center', gap: '16px', flexWrap: 'wrap',
          padding: '16px 20px', border: '1px solid #dadce0', borderRadius: '8px',
          backgroundColor: '#f8f9fa', marginBottom: '24px',
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <label style={{ fontSize: '11pt', fontWeight: 600 }}>Report Month</label>
            <select value={monthName} onChange={(e) => setMonthName(e.target.value)} style={selStyle}>
              {MONTHS.map((m) => <option key={m}>{m}</option>)}
            </select>
            <select value={year} onChange={(e) => setYear(e.target.value)} style={selStyle}>
              {YEARS.map((y) => <option key={y}>{y}</option>)}
            </select>
          </div>
          {loading && <span style={{ fontSize: '10.5pt', color: '#5f6368' }}>Loading…</span>}
          {meta && (
            <span style={{ fontSize: '9.5pt', color: '#5f6368' }}>
              Last saved by {meta.updated_by || 'unknown'} at {meta.updated_at}
            </span>
          )}
        </div>

        {status && (
          <p style={{
            marginBottom: '16px', fontSize: '11pt',
            color: status.type === 'error' ? '#d93025' : '#188038',
          }}>
            {status.text}
          </p>
        )}

        {/* Major Achievements */}
        <div style={sectionCard('#86efac')}>
          <h2 style={{ fontSize: '13pt', fontWeight: 800, color: '#1e7e34', margin: '0 0 4px' }}>Major Achievements</h2>
          <p style={{ fontSize: '9.5pt', color: '#5f6368', margin: '0 0 12px' }}>
            One line per achievement. Optional sub-points (e.g. record breakdown) — one per line, indented under the achievement.
          </p>
          {achievements.map((a, i) => (
            <div key={i} style={{ display: 'flex', gap: '8px', alignItems: 'flex-start', marginBottom: '10px' }}>
              <div style={{ flex: 1 }}>
                <input
                  type="text" style={inputStyle} placeholder="Achievement"
                  value={a.text}
                  onChange={(e) => setAchievements((v) => v.map((x, j) => (j === i ? { ...x, text: e.target.value } : x)))}
                />
                <textarea
                  style={{ ...inputStyle, marginTop: '6px', minHeight: '44px', resize: 'vertical' }}
                  placeholder="Sub-points (optional, one per line)"
                  value={a.subsText}
                  onChange={(e) => setAchievements((v) => v.map((x, j) => (j === i ? { ...x, subsText: e.target.value } : x)))}
                />
              </div>
              <button style={removeBtn} onClick={() => setAchievements((v) => v.filter((_, j) => j !== i))}>✕</button>
            </div>
          ))}
          <button style={addBtn} onClick={() => setAchievements((v) => [...v, emptyAchievement()])}>+ Add achievement</button>
        </div>

        {/* Major Shortfalls */}
        <div style={sectionCard('#fca5a5')}>
          <h2 style={{ fontSize: '13pt', fontWeight: 800, color: '#b91c1c', margin: '0 0 4px' }}>Major Shortfalls / Areas of Concern</h2>
          <p style={{ fontSize: '9.5pt', color: '#5f6368', margin: '0 0 12px' }}>One line per shortfall/concern.</p>
          {shortfalls.map((s, i) => (
            <div key={i} style={{ display: 'flex', gap: '8px', alignItems: 'center', marginBottom: '8px' }}>
              <input
                type="text" style={inputStyle} placeholder="Shortfall / area of concern"
                value={s}
                onChange={(e) => setShortfalls((v) => v.map((x, j) => (j === i ? e.target.value : x)))}
              />
              <button style={removeBtn} onClick={() => setShortfalls((v) => v.filter((_, j) => j !== i))}>✕</button>
            </div>
          ))}
          <button style={addBtn} onClick={() => setShortfalls((v) => [...v, ''])}>+ Add shortfall</button>
        </div>

        {/* Focus Areas Going Forward */}
        <div style={sectionCard('#93c5fd')}>
          <h2 style={{ fontSize: '13pt', fontWeight: 800, color: '#0f2a5c', margin: '0 0 4px' }}>Focus Areas Going Forward</h2>
          <p style={{ fontSize: '9.5pt', color: '#5f6368', margin: '0 0 12px' }}>Short title + one-line description for each focus area.</p>
          {focusAreas.map((f, i) => (
            <div key={i} style={{ display: 'flex', gap: '8px', alignItems: 'flex-start', marginBottom: '10px' }}>
              <div style={{ flex: 1 }}>
                <input
                  type="text" style={inputStyle} placeholder="Title (e.g. Improve BF Productivity)"
                  value={f.title}
                  onChange={(e) => setFocusAreas((v) => v.map((x, j) => (j === i ? { ...x, title: e.target.value } : x)))}
                />
                <input
                  type="text" style={{ ...inputStyle, marginTop: '6px' }} placeholder="Description"
                  value={f.description}
                  onChange={(e) => setFocusAreas((v) => v.map((x, j) => (j === i ? { ...x, description: e.target.value } : x)))}
                />
              </div>
              <button style={removeBtn} onClick={() => setFocusAreas((v) => v.filter((_, j) => j !== i))}>✕</button>
            </div>
          ))}
          <button style={addBtn} onClick={() => setFocusAreas((v) => [...v, emptyFocusArea()])}>+ Add focus area</button>
        </div>

        <button
          onClick={handleSave}
          disabled={saving || loading}
          style={{
            padding: '10px 24px', fontSize: '11pt', fontWeight: 700, border: 'none', borderRadius: '6px',
            backgroundColor: saving ? '#9aa0a6' : '#1a73e8', color: '#fff',
            cursor: saving || loading ? 'not-allowed' : 'pointer',
          }}
        >
          {saving ? 'Saving…' : 'Save'}
        </button>
      </div>
    </div>
  );
}

export default function KeyHighlightsManualPage() {
  return (
    <RequireEditor>
      <KeyHighlightsManualInner />
    </RequireEditor>
  );
}
