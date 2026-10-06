'use client';

import React, { useState, useEffect } from 'react';
import { ReportPage } from '../ReportUI';

const API = process.env.NEXT_PUBLIC_API_URL || '';

// Plants that get a narrative box. SAIL has no "why production fell short"
// block in the note, so only its additional-highlights box is shown.
const PLANTS = [
  { code: 'SAIL', why: false },
  { code: 'BSP', why: true },
  { code: 'DSP', why: true },
  { code: 'RSP', why: true },
  { code: 'BSL', why: true },
  { code: 'ISP', why: true },
  { code: 'ASP', why: true },
  { code: 'SSP', why: true },
  { code: 'VISL', why: true },
];

const QUARTERS = [
  { value: 1, label: 'Q-1' },
  { value: 2, label: 'Q-2' },
  { value: 3, label: 'Q-3' },
  { value: 4, label: 'Q-4' },
];

const FY_RE = /^\d{4}-\d{2}$/;

// FY is named by its starting year: April of `start` to March of `start+1`.
function fyOf(date) {
  const start = date.getMonth() >= 3 ? date.getFullYear() : date.getFullYear() - 1;
  return `${start}-${String((start + 1) % 100).padStart(2, '0')}`;
}

// The note reports a quarter that has already closed, so the default is the
// most recently completed quarter (Apr-Jun is Q-1, so "last" is Q-4 of the
// previous FY).
function lastCompletedQuarter(date) {
  const fyMonth = (date.getMonth() - 3 + 12) % 12;
  const currentQ = Math.floor(fyMonth / 3) + 1;
  if (currentQ > 1) return { fy: fyOf(date), quarter: currentQ - 1 };
  const prev = new Date(date.getFullYear() - 1, 3, 1);
  return { fy: fyOf(prev), quarter: 4 };
}

function emptyText() {
  const out = {};
  for (const p of PLANTS) {
    out[p.code] = { additional_highlights: '', why_narrative: '' };
  }
  return out;
}

export default function BoardNotePage() {
  const [init] = useState(() => lastCompletedQuarter(new Date()));
  const [fy, setFy] = useState(init.fy);
  const [quarter, setQuarter] = useState(init.quarter);
  const [text, setText] = useState(emptyText);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [downloading, setDownloading] = useState(false);
  const [error, setError] = useState(null);
  const [saveMsg, setSaveMsg] = useState(null);

  const validFy = FY_RE.test(fy);

  // Changing the period resets the page's messages and marks it as loading;
  // the effect below fetches the narrative for the new period.
  const changePeriod = (nextFy, nextQuarter) => {
    setFy(nextFy);
    setQuarter(nextQuarter);
    setLoading(true);
    setError(null);
    setSaveMsg(null);
  };

  useEffect(() => {
    if (!validFy) return undefined;
    let cancelled = false;
    fetch(`${API}/api/board-note/manual-text?fy=${encodeURIComponent(fy)}&quarter=${quarter}`)
      .then(async (res) => {
        const body = await res.json().catch(() => ({}));
        if (!res.ok) throw new Error(body.detail || `HTTP ${res.status}`);
        return body;
      })
      .then((body) => {
        if (cancelled) return;
        const next = emptyText();
        for (const plant of Object.keys(body)) {
          if (!next[plant]) next[plant] = { additional_highlights: '', why_narrative: '' };
          Object.assign(next[plant], body[plant]);
        }
        setText(next);
      })
      .catch((e) => {
        if (!cancelled) setError(`Failed to load narrative: ${e.message}`);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => { cancelled = true; };
  }, [fy, quarter, validFy]);

  const setField = (plant, field, value) => {
    setText((prev) => ({ ...prev, [plant]: { ...prev[plant], [field]: value } }));
  };

  const handleSave = async () => {
    setSaving(true);
    setError(null);
    setSaveMsg(null);
    try {
      const entries = [];
      for (const p of PLANTS) {
        const fields = p.why ? ['additional_highlights', 'why_narrative'] : ['additional_highlights'];
        for (const field of fields) {
          entries.push({ plant: p.code, field, text: (text[p.code]?.[field] || '').trim() });
        }
      }
      const res = await fetch(`${API}/api/board-note/manual-text`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ report_fy: fy, quarter, entries }),
      });
      const body = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(body.detail || `HTTP ${res.status}`);
      setSaveMsg(`Saved. This narrative goes into the ${QUARTERS[quarter - 1].label} ${fy} Board Note.`);
    } catch (e) {
      setError(`Save failed: ${e.message}`);
    } finally {
      setSaving(false);
    }
  };

  const handleDownload = async () => {
    setDownloading(true);
    setError(null);
    try {
      const res = await fetch(`${API}/api/board-note/docx?fy=${encodeURIComponent(fy)}&quarter=${quarter}`);
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        throw new Error(body.detail || `HTTP ${res.status}`);
      }
      const blob = await res.blob();
      const blobUrl = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = blobUrl;
      a.download = `BoardNote_${fy}_Q${quarter}.docx`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      window.URL.revokeObjectURL(blobUrl);
    } catch (e) {
      setError(`Download failed: ${e.message}`);
    } finally {
      setDownloading(false);
    }
  };

  const inputStyle = {
    padding: '9px 14px', fontSize: '11pt', border: '1px solid #dadce0',
    borderRadius: '6px', backgroundColor: '#ffffff', color: '#202124', minWidth: '120px',
  };

  const btnStyle = (disabled, color = '#1a73e8') => ({
    padding: '10px 24px', fontSize: '11pt', fontWeight: 700, border: 'none',
    borderRadius: '6px', cursor: disabled ? 'not-allowed' : 'pointer',
    backgroundColor: disabled ? '#dadce0' : color, color: '#ffffff',
  });

  const textareaStyle = {
    width: '100%', padding: '8px 10px', fontSize: '10pt',
    border: '1px solid #dadce0', borderRadius: '6px',
    fontFamily: 'inherit', resize: 'vertical',
  };

  return (
    <ReportPage
      maxWidth={900}
      title={<>Quarterly Board Note</>}
      description={<>Production performance Board Note (.docx) for any financial year and quarter, generated from data already in this app. Narrative typed below is saved per period and merged into the note when it is generated: <strong>extra highlights</strong> go into the quarter&apos;s highlights list, and <strong>why narrative</strong> replaces the production-shortfall text for each plant. Extra highlights only appear where the quarter&apos;s template has a highlights block for that plant.</>}
    >
      <div style={{
        padding: '20px 24px', border: '1px solid #dadce0', borderRadius: '8px',
        backgroundColor: '#ffffff', marginBottom: '24px',
        display: 'flex', alignItems: 'center', gap: '16px', flexWrap: 'wrap',
      }}>
        <label style={{ fontSize: '11pt', fontWeight: 600 }}>Financial year</label>
        <input
          type="text"
          value={fy}
          onChange={(e) => changePeriod(e.target.value.trim(), quarter)}
          placeholder="2026-27"
          style={{ ...inputStyle, borderColor: validFy ? '#dadce0' : '#f28b82' }}
        />
        <label style={{ fontSize: '11pt', fontWeight: 600 }}>Quarter</label>
        <select value={quarter} onChange={(e) => changePeriod(fy, parseInt(e.target.value, 10))} style={inputStyle}>
          {QUARTERS.map((q) => (
            <option key={q.value} value={q.value}>{q.label}</option>
          ))}
        </select>
        <button
          onClick={handleDownload}
          disabled={!validFy || downloading}
          style={btnStyle(!validFy || downloading)}
        >
          {downloading ? 'Generating…' : '⬇ Generate Board Note (.docx)'}
        </button>
      </div>

      {!validFy && (
        <div style={{ padding: '12px 16px', border: '1px solid #f28b82', borderRadius: '8px', backgroundColor: '#fce8e6', color: '#c5221f', fontSize: '10.5pt', marginBottom: '24px' }}>
          Enter the financial year as YYYY-YY, for example 2026-27.
        </div>
      )}

      {error && (
        <div style={{ padding: '14px 18px', border: '1px solid #f28b82', borderRadius: '8px', backgroundColor: '#fce8e6', color: '#c5221f', fontSize: '11pt', marginBottom: '24px' }}>
          {error}
        </div>
      )}

      <div style={{ padding: '20px 24px', border: '1px solid #dadce0', borderRadius: '8px', marginBottom: '24px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '14px', flexWrap: 'wrap', gap: '12px' }}>
          <div style={{ fontSize: '12pt', fontWeight: 700, color: '#202124' }}>
            Narrative — {QUARTERS[quarter - 1].label} {validFy ? fy : ''}
          </div>
          <button onClick={handleSave} disabled={!validFy || saving || loading} style={btnStyle(!validFy || saving || loading, '#0f9d58')}>
            {saving ? 'Saving…' : 'Save narrative'}
          </button>
        </div>
        <p style={{ fontSize: '9.5pt', color: '#9aa0a6', marginTop: 0, marginBottom: '16px' }}>
          A blank box means nothing is added for that plant. Each period starts blank; nothing is copied from another quarter.
        </p>

        {!validFy ? null : loading ? (
          <div style={{ fontSize: '10.5pt', color: '#5f6368' }}>Loading…</div>
        ) : (
          PLANTS.map((p) => {
            const hasText = !!(text[p.code]?.additional_highlights || text[p.code]?.why_narrative);
            return (
              <details key={`${fy}-${quarter}-${p.code}`} open={hasText} style={{ marginBottom: '14px' }}>
                <summary style={{ fontSize: '10.5pt', fontWeight: 700, color: '#1a73e8', cursor: 'pointer', padding: '6px 0' }}>
                  {p.code}{hasText ? ' · has narrative' : ''}
                </summary>
                <div style={{ display: 'grid', gridTemplateColumns: '1fr', gap: '10px', paddingTop: '8px' }}>
                  <label style={{ fontSize: '10pt', fontWeight: 600, color: '#202124' }}>
                    Extra highlights (one per line)
                    <textarea
                      value={text[p.code]?.additional_highlights || ''}
                      onChange={(e) => setField(p.code, 'additional_highlights', e.target.value)}
                      rows={3}
                      placeholder="No extra highlights"
                      style={{ ...textareaStyle, marginTop: '4px' }}
                    />
                  </label>
                  {p.why && (
                    <label style={{ fontSize: '10pt', fontWeight: 600, color: '#202124' }}>
                      Why production fell short (one point per line)
                      <textarea
                        value={text[p.code]?.why_narrative || ''}
                        onChange={(e) => setField(p.code, 'why_narrative', e.target.value)}
                        rows={5}
                        placeholder="Uses the placeholder line until text is entered"
                        style={{ ...textareaStyle, marginTop: '4px' }}
                      />
                    </label>
                  )}
                </div>
              </details>
            );
          })
        )}

        {saveMsg && (
          <div style={{ padding: '10px 14px', backgroundColor: '#e6f4ea', color: '#137333', borderRadius: '6px', fontSize: '10.5pt' }}>
            {saveMsg}
          </div>
        )}
      </div>
    </ReportPage>
  );
}
