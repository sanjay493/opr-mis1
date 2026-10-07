'use client';

import React, { useState, useEffect } from 'react';
import { ReportPage } from '../ReportUI';

const API = process.env.NEXT_PUBLIC_API_URL || '';
const SECTIONS = ['Highlights', 'Delays', 'Capital Repairs', 'Breakdowns'];
const MONTH_RE = /^\d{4}-(0[1-9]|1[0-2])$/;

async function getJson(url, opts) {
  const res = await fetch(url, opts);
  const body = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(body.detail || `HTTP ${res.status}`);
  return body;
}

function badge(b) {
  if (b.edited) return { text: 'Edited – not saved', color: '#b06000', bg: '#fef7e0' };
  if (b.saved) return { text: 'Saved', color: '#137333', bg: '#e6f4ea' };
  return { text: 'From DB – not saved', color: '#5f6368', bg: '#f1f3f4' };
}

const fmt = (v) => (v === null || v === undefined ? '–' : Math.round(v).toLocaleString('en-IN'));

export default function SecretaryReviewPage() {
  const [month, setMonth] = useState('');
  const [ctx, setCtx] = useState(null);
  const [blocks, setBlocks] = useState([]);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState('');
  const [error, setError] = useState(null);
  const [msg, setMsg] = useState(null);

  // First load: the backend picks the latest month with production data.
  useEffect(() => {
    let cancelled = false;
    getJson(`${API}/api/secretary-review/context`)
      .then((c) => { if (!cancelled) setMonth(c.labels.month); })
      .catch((e) => {
        if (!cancelled) {
          setError(`Failed to load: ${e.message}`);
          setLoading(false);
        }
      });
    return () => { cancelled = true; };
  }, []);

  useEffect(() => {
    if (!MONTH_RE.test(month)) return undefined;
    let cancelled = false;
    Promise.all([
      getJson(`${API}/api/secretary-review/context?month=${month}`),
      getJson(`${API}/api/secretary-review/texts?month=${month}`),
    ])
      .then(([c, t]) => {
        if (cancelled) return;
        setCtx(c);
        setBlocks(t.blocks.map((b) => ({ ...b, edited: false })));
      })
      .catch((e) => { if (!cancelled) setError(`Failed to load ${month}: ${e.message}`); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [month]);

  const changeMonth = (m) => {
    setMonth(m);
    setLoading(true);
    setError(null);
    setMsg(null);
  };

  const setText = (key, text) => {
    setBlocks((prev) => prev.map((b) => (b.key === key ? { ...b, text, edited: true } : b)));
  };

  const textsPayload = () => Object.fromEntries(blocks.map((b) => [b.key, b.text]));

  const resetBlock = async (key) => {
    setError(null);
    try {
      const body = await getJson(`${API}/api/secretary-review/default-text?month=${month}&block=${key}`);
      setText(key, body.text);
    } catch (e) {
      setError(`Reset failed: ${e.message}`);
    }
  };

  const saveAll = async () => {
    setBusy('saving');
    setError(null);
    setMsg(null);
    try {
      await getJson(`${API}/api/secretary-review/texts`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ month, texts: textsPayload() }),
      });
      setBlocks((prev) => prev.map((b) => ({ ...b, saved: true, edited: false })));
      setMsg(`Saved narrative for ${ctx?.labels?.mon || month}.`);
    } catch (e) {
      setError(`Save failed: ${e.message}`);
    } finally {
      setBusy('');
    }
  };

  const download = async () => {
    setBusy('downloading');
    setError(null);
    try {
      const res = await fetch(`${API}/api/secretary-review/pptx`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ month, texts: textsPayload() }),
      });
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        throw new Error(body.detail || `HTTP ${res.status}`);
      }
      const blob = await res.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = ctx?.filename || `Secretary_Review_${month}.pptx`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      window.URL.revokeObjectURL(url);
    } catch (e) {
      setError(`Download failed: ${e.message}`);
    } finally {
      setBusy('');
    }
  };

  const box = { padding: '20px 24px', border: '1px solid #dadce0', borderRadius: '8px', backgroundColor: '#ffffff', marginBottom: '24px' };
  const btn = (disabled, color = '#1a73e8') => ({
    padding: '10px 24px', fontSize: '11pt', fontWeight: 700, border: 'none', borderRadius: '6px',
    cursor: disabled ? 'not-allowed' : 'pointer', backgroundColor: disabled ? '#dadce0' : color, color: '#ffffff',
  });
  const ready = MONTH_RE.test(month) && !loading;

  return (
    <ReportPage
      maxWidth={960}
      title={<>Secretary Review (PPTX)</>}
      description={<>Monthly &ldquo;SECRETARY REVIEW Operations Inputs&rdquo; deck. Tables and charts come from the database for the chosen month. The narrative below starts from the database (breakdowns, capital repairs, best-ever records); edit it, save it for the month, then download. Download uses the text on screen, saved or not.</>}
    >
      <div style={{ ...box, display: 'flex', alignItems: 'center', gap: '16px', flexWrap: 'wrap' }}>
        <label style={{ fontSize: '11pt', fontWeight: 600 }} htmlFor="sr-month">Month</label>
        <input
          id="sr-month"
          type="month"
          value={month}
          onChange={(e) => changeMonth(e.target.value)}
          style={{ padding: '9px 14px', fontSize: '11pt', border: '1px solid #dadce0', borderRadius: '6px' }}
        />
        <button onClick={download} disabled={!ready || !!busy} style={btn(!ready || !!busy)}>
          {busy === 'downloading' ? 'Generating…' : '⬇ Download PPTX'}
        </button>
        <button onClick={saveAll} disabled={!ready || !!busy} style={btn(!ready || !!busy, '#0f9d58')}>
          {busy === 'saving' ? 'Saving…' : 'Save all text'}
        </button>
      </div>

      {error && (
        <div style={{ padding: '14px 18px', border: '1px solid #f28b82', borderRadius: '8px', backgroundColor: '#fce8e6', color: '#c5221f', marginBottom: '24px' }}>
          {error}
        </div>
      )}
      {msg && (
        <div style={{ padding: '10px 14px', backgroundColor: '#e6f4ea', color: '#137333', borderRadius: '6px', marginBottom: '24px' }}>
          {msg}
        </div>
      )}

      {loading ? (
        <div style={{ color: '#5f6368' }}>Loading…</div>
      ) : ctx && (
        <>
          <div style={box}>
            <div style={{ fontSize: '12pt', fontWeight: 700, marginBottom: '10px' }}>
              SAIL — {ctx.labels.mon} &amp; {ctx.labels.ytd} (&apos;000 T)
            </div>
            <table style={{ borderCollapse: 'collapse', fontSize: '10pt', width: '100%' }}>
              <thead>
                <tr style={{ textAlign: 'right', color: '#5f6368' }}>
                  <th style={{ textAlign: 'left' }}>Item</th><th>APP {ctx.labels.mon}</th><th>Actual</th><th>APP {ctx.labels.ytd}</th><th>Actual</th>
                </tr>
              </thead>
              <tbody>
                {ctx.summary.map((r) => (
                  <tr key={r.item} style={{ textAlign: 'right', borderTop: '1px solid #eee' }}>
                    <td style={{ textAlign: 'left' }}>{r.item}</td>
                    <td>{fmt(r.app_m)}</td><td>{fmt(r.act_m)}</td><td>{fmt(r.app_ytd)}</td><td>{fmt(r.act_ytd)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            {ctx.warnings.length > 0 && (
              <div style={{ marginTop: '14px', padding: '10px 14px', backgroundColor: '#fef7e0', borderRadius: '6px', fontSize: '10pt' }}>
                <strong>Data check ({ctx.warnings.length})</strong>
                <ul style={{ margin: '6px 0 0 18px', padding: 0 }}>
                  {ctx.warnings.map((w) => <li key={w}>{w}</li>)}
                </ul>
              </div>
            )}
          </div>

          {SECTIONS.map((section) => (
            <div key={section} style={box}>
              <div style={{ fontSize: '12pt', fontWeight: 700, marginBottom: '12px' }}>{section}</div>
              {blocks.filter((b) => b.section === section).map((b) => {
                const bd = badge(b);
                return (
                  <div key={`${month}-${b.key}`} style={{ marginBottom: '16px' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '4px', flexWrap: 'wrap' }}>
                      <label htmlFor={`sr-${b.key}`} style={{ fontSize: '10pt', fontWeight: 600 }}>{b.label}</label>
                      <span style={{ fontSize: '8.5pt', padding: '2px 8px', borderRadius: '10px', color: bd.color, backgroundColor: bd.bg }}>{bd.text}</span>
                      <button
                        onClick={() => resetBlock(b.key)}
                        style={{ marginLeft: 'auto', fontSize: '9pt', border: '1px solid #dadce0', borderRadius: '4px', background: '#fff', padding: '3px 10px', cursor: 'pointer' }}
                      >
                        Reset from DB
                      </button>
                    </div>
                    <textarea
                      id={`sr-${b.key}`}
                      value={b.text}
                      onChange={(e) => setText(b.key, e.target.value)}
                      rows={Math.min(Math.max(b.text.split('\n').length + 1, 3), 12)}
                      placeholder="Empty — this block is left out of the deck"
                      style={{ width: '100%', padding: '8px 10px', fontSize: '10pt', border: '1px solid #dadce0', borderRadius: '6px', fontFamily: 'inherit', resize: 'vertical' }}
                    />
                  </div>
                );
              })}
            </div>
          ))}
        </>
      )}
    </ReportPage>
  );
}
