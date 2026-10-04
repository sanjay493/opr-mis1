'use client';

import RequireEditor from '@/components/RequireEditor';

import React, { useState, useMemo } from 'react';
import Link from 'next/link';
import GlobalNavbar from '@/components/GlobalNavbar';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || '';

const MON = ['', 'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
const monLabel = (ym) => `${MON[Number(ym.slice(5, 7))]}'${ym.slice(2, 4)}`;

// Commentary & Market PDF upload — the monthly CMO / BigMint deck. Extracts
// the Steel Sales "Key Performance Parameters" bullets (month + April-to-
// month, page 3.05) and the "Movement of Key Prices-International" chart
// (page 2.41); see backend/api_market_commentary_upload.py. The deck's
// India Macro Economic Indicators table is an image and is entered in
// Market Intelligence instead.
function CommentaryMarketUploadInner() {
  const [file, setFile] = useState(null);
  const [preview, setPreview] = useState(null);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState(null);
  const [result, setResult] = useState(null);

  const reset = () => { setPreview(null); setResult(null); setError(null); };

  const handlePreview = async () => {
    if (!file) return;
    setLoading(true);
    reset();
    try {
      const formData = new FormData();
      formData.append('file', file);
      const res = await fetch(`${API_BASE}/api/market-commentary-upload/preview`, { method: 'POST', body: formData });
      const text = await res.text();
      let json;
      try { json = JSON.parse(text); } catch { throw new Error(text.slice(0, 300)); }
      if (!res.ok) throw new Error(json.detail || 'Preview failed');
      setPreview(json);
    } catch (err) {
      setError(err.message || 'Preview failed');
    } finally {
      setLoading(false);
    }
  };

  const prices = preview?.market_prices;
  const changedCount = useMemo(() => {
    if (!prices) return 0;
    let n = 0;
    for (const [code, vals] of Object.entries(prices.series)) {
      for (const [m, v] of Object.entries(vals)) {
        if ((preview.stored.prices[m] || {})[code] !== v) n += 1;
      }
    }
    return n;
  }, [prices, preview]);

  const handleSave = async () => {
    const c = preview.commentary;
    const replacing = preview.stored.month_items.length + preview.stored.ytd_items.length > 0;
    if (!window.confirm(
      `Save ${monLabel(preview.report_month)}: ${c.month_items.length} month + ${c.ytd_items.length} YTD bullets`
      + `${replacing ? ' (replacing the bullets already saved)' : ''} and ${changedCount} new/changed price value(s)?`
    )) return;
    setSaving(true);
    setError(null);
    try {
      const res = await fetch(`${API_BASE}/api/market-commentary-upload/insert`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          report_month: preview.report_month,
          file_name: preview.file_name,
          month_items: c.month_items,
          ytd_items: c.ytd_items,
          prices: prices.series,
        }),
      });
      const json = await res.json();
      if (!res.ok) throw new Error(json.detail || 'Save failed');
      setResult(json);
      setPreview(null);
      setFile(null);
    } catch (err) {
      setError(err.message || 'Save failed');
    } finally {
      setSaving(false);
    }
  };

  const canSave = preview && preview.report_month
    && (preview.commentary.month_items.length || preview.commentary.ytd_items.length || Object.keys(prices.series).length);

  return (
    <div style={{ height: '100vh', display: 'flex', flexDirection: 'column', backgroundColor: '#ffffff' }}>
      <GlobalNavbar />
      <main style={{
        flex: 1, overflow: 'auto', padding: '32px', maxWidth: '1200px',
        margin: '0 auto', width: '100%', boxSizing: 'border-box',
      }}>
        <h1 style={{ fontSize: '20pt', fontWeight: 900, color: '#202124', margin: '0 0 6px' }}>
          📝 Commentary &amp; Market Upload
        </h1>
        <p style={{ fontSize: '11pt', color: '#5f6368', marginBottom: '20px', maxWidth: '860px' }}>
          Upload the monthly CMO / BigMint deck (PDF). Its &quot;Key Performance Parameters&quot; slides become the
          month and YTD bullets of Steel Sales Performance (page 3.05), and its &quot;Movement of Key
          Prices-International&quot; chart fills every month it shows on page 2.41 — a later deck replaces last
          month&apos;s spot price with its full-month figure. The India Macro Economic Indicators table in the deck
          is an image: enter its new month in{' '}
          <Link href="/data-entry/commentary?tab=market-intel" style={{ color: '#1a73e8' }}>Market Intelligence</Link>.
          Nothing is written until you click Save.
        </p>

        <div style={{
          border: '1px solid #dadce0', borderRadius: '8px', padding: '16px 18px',
          marginBottom: '20px', backgroundColor: '#f8f9fa',
          display: 'flex', alignItems: 'center', gap: '14px', flexWrap: 'wrap',
        }}>
          <input type="file" accept=".pdf"
            onChange={(e) => { setFile(e.target.files?.[0] || null); reset(); }}
            style={{ fontSize: '10pt' }} />
          <button onClick={handlePreview} disabled={!file || loading} style={btnStyle('#1a73e8', !file || loading)}>
            {loading ? 'Reading…' : 'Preview'}
          </button>
          {preview && (
            <button onClick={handleSave} disabled={!canSave || saving} style={btnStyle('#10b981', !canSave || saving)}>
              {saving ? 'Saving…' : 'Save'}
            </button>
          )}
        </div>

        {error && <Banner kind="error">{error}</Banner>}
        {result && (
          <Banner kind="ok">
            Saved {monLabel(result.report_month)}: {result.bullets} bullet(s) and {result.prices} price value(s).
          </Banner>
        )}

        {preview && (
          <>
            <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '14px', flexWrap: 'wrap' }}>
              <span style={chip('#1a73e8', '#e8f0fe')}>
                Report Month: {preview.report_month ? monLabel(preview.report_month) : 'not found'}
              </span>
              <span style={{ fontSize: '9.5pt', color: '#5f6368' }}>from {preview.file_name}</span>
              {preview.skipped_pages.length > 0 && (
                <span style={{ fontSize: '9.5pt', color: '#5f6368' }}>
                  · page {preview.skipped_pages.join(', ')} has no text (image) — not extracted
                </span>
              )}
            </div>

            {preview.warnings.length > 0 && (
              <Banner kind="warn">
                {preview.warnings.map((w, i) => <div key={i}>⚠ {w}</div>)}
              </Banner>
            )}

            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(420px, 1fr))', gap: '16px', marginBottom: '20px' }}>
              <BulletList title={`${preview.report_month ? monLabel(preview.report_month) : 'Month'} — Key Performance Parameters`}
                items={preview.commentary.month_items} storedCount={preview.stored.month_items.length} />
              <BulletList title="April-to-month — Key Performance Parameters"
                items={preview.commentary.ytd_items} storedCount={preview.stored.ytd_items.length} />
            </div>

            {prices.months.length > 0 && (
              <>
                <h2 style={{ fontSize: '12pt', fontWeight: 700, color: '#202124', margin: '0 0 6px' }}>
                  Movement of Key Prices — International (USD/T)
                </h2>
                <p style={{ fontSize: '9.5pt', color: '#5f6368', margin: '0 0 10px' }}>
                  {changedCount} new or changed value(s), highlighted with the stored value struck through.
                </p>
                <div style={{ border: '1px solid #dadce0', borderRadius: '8px', overflowX: 'auto', marginBottom: '20px' }}>
                  <table style={{ borderCollapse: 'collapse', backgroundColor: '#fff', width: '100%' }}>
                    <thead>
                      <tr style={{ backgroundColor: '#f8f9fa', borderBottom: '1px solid #dadce0' }}>
                        <th style={{ ...thStyle, minWidth: '260px' }}>Series</th>
                        {prices.months.map((m) => <th key={m} style={{ ...thStyle, textAlign: 'right' }}>{monLabel(m)}</th>)}
                      </tr>
                    </thead>
                    <tbody>
                      {preview.series_order.filter((c) => prices.series[c]).map((code) => (
                        <tr key={code} style={{ borderBottom: '1px solid #f1f3f4' }}>
                          <td style={tdStyle}>{preview.series_labels[code]}</td>
                          {prices.months.map((m) => {
                            const v = prices.series[code][m];
                            const old = (preview.stored.prices[m] || {})[code];
                            const changed = v != null && old !== v;
                            return (
                              <td key={m} style={{
                                ...tdStyle, textAlign: 'right', whiteSpace: 'nowrap',
                                backgroundColor: changed ? (old == null ? '#e6f4ea' : '#fef7e0') : undefined,
                                fontWeight: changed ? 700 : 400,
                              }}>
                                {changed && old != null && (
                                  <span style={{ textDecoration: 'line-through', color: '#9aa0a6', fontWeight: 400, marginRight: 4 }}>{old}</span>
                                )}
                                {v ?? '—'}
                              </td>
                            );
                          })}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </>
            )}
          </>
        )}

        {!preview && !result && (
          <div style={{ padding: '40px', textAlign: 'center', color: '#5f6368', fontSize: '11pt', border: '1px solid #dadce0', borderRadius: '8px' }}>
            Choose the deck PDF, then Preview.
          </div>
        )}
      </main>
    </div>
  );
}

function BulletList({ title, items, storedCount }) {
  return (
    <div style={{ border: '1px solid #dadce0', borderRadius: '8px', padding: '12px 16px', backgroundColor: '#fff' }}>
      <div style={{ fontSize: '10.5pt', fontWeight: 700, color: '#202124', marginBottom: 4 }}>
        {title} <span style={{ fontWeight: 400, color: '#5f6368' }}>({items.length})</span>
      </div>
      {storedCount > 0 && (
        <div style={{ fontSize: '9pt', color: '#b06000', marginBottom: 6 }}>
          Replaces the {storedCount} bullet(s) already saved for this month.
        </div>
      )}
      {items.length === 0 ? (
        <div style={{ fontSize: '9.5pt', color: '#9aa0a6' }}>None found in the PDF.</div>
      ) : (
        <ul style={{ margin: 0, paddingLeft: '18px', fontSize: '9.5pt', color: '#202124', lineHeight: 1.45 }}>
          {items.map((t, i) => <li key={i} style={{ whiteSpace: 'pre-line', marginBottom: 3 }}>{t}</li>)}
        </ul>
      )}
    </div>
  );
}

function Banner({ kind, children }) {
  const c = {
    error: ['#f28b82', '#fce8e6', '#c5221f'],
    ok: ['#a8dab5', '#e6f4ea', '#188038'],
    warn: ['#fdd663', '#fef7e0', '#b06000'],
  }[kind];
  return (
    <div style={{
      padding: '10px 14px', border: `1px solid ${c[0]}`, borderRadius: '6px',
      backgroundColor: c[1], color: c[2], fontSize: '10.5pt', marginBottom: '16px',
    }}>
      {children}
    </div>
  );
}

export default function CommentaryMarketUploadPage() {
  return (
    <RequireEditor>
      <CommentaryMarketUploadInner />
    </RequireEditor>
  );
}

const thStyle = { padding: '10px 12px', textAlign: 'left', fontWeight: 700, fontSize: '9.5pt', color: '#5f6368' };
const tdStyle = { padding: '8px 12px', fontSize: '9.5pt', color: '#202124' };

function chip(color, bg) {
  return {
    padding: '6px 14px', borderRadius: '8px', border: `1px solid ${color}`,
    backgroundColor: bg, color, fontSize: '10pt', fontWeight: 700,
  };
}

function btnStyle(color, disabled) {
  return {
    padding: '9px 18px', background: disabled ? '#dadce0' : color, color: '#fff',
    border: 'none', borderRadius: '6px', fontSize: '10.5pt', fontWeight: 700,
    cursor: disabled ? 'not-allowed' : 'pointer', whiteSpace: 'nowrap',
  };
}
