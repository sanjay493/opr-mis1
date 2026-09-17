'use client';

import RequireEditor from '@/components/RequireEditor';
import React, { useState, useEffect, useCallback } from 'react';
import GlobalNavbar from '@/components/GlobalNavbar';

const API = process.env.NEXT_PUBLIC_API_URL || '';

const thisMonth = () => new Date().toISOString().slice(0, 7);

const s = (v) => (v === null || v === undefined ? '' : String(v));
function numOrNull(v) {
  const f = parseFloat(v);
  return Number.isNaN(f) ? null : f;
}

function Notice({ type, text }) {
  if (!text) return null;
  const ok = type === 'success';
  return (
    <div style={{
      padding: '10px 16px', borderRadius: 6, margin: '14px 0', fontSize: 14,
      background: ok ? '#f0fdf4' : '#fef2f2', color: ok ? '#166534' : '#991b1b',
      border: `1px solid ${ok ? '#86efac' : '#fca5a5'}`,
    }}>{text}</div>
  );
}

const cellInput = {
  width: 110, padding: '5px 6px', border: '1px solid #dadce0', borderRadius: 4,
  textAlign: 'right', fontSize: 12.5,
};
const TH = { padding: '8px 10px', fontSize: 12, fontWeight: 700, color: '#5f6368', background: '#f8f9fa', borderBottom: '1px solid #dadce0', textAlign: 'left' };
const TD = { padding: '6px 10px', borderBottom: '1px solid #f1f3f4' };
const CATEGORY_LABEL = { raw_materials: 'Raw Materials', finished_steel: 'Finished Steel' };

function MarketIntelEntryInner() {
  const [reportMonth, setReportMonth] = useState(thisMonth());
  const [priceRows, setPriceRows] = useState([]);
  const [macroRows, setMacroRows] = useState([]);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [status, setStatus] = useState(null);

  const load = useCallback(async (month) => {
    setLoading(true);
    setStatus(null);
    try {
      const res = await fetch(`${API}/api/market-intel/grid?report_month=${encodeURIComponent(month)}`);
      if (!res.ok) throw new Error(await res.text());
      const d = await res.json();
      setPriceRows(d.market_price_rows.map((r) => ({ ...r, value: s(r.value) })));
      setMacroRows(d.macro_rows.map((r) => ({ ...r, value: s(r.value) })));
    } catch (err) {
      setStatus({ type: 'error', text: `Load failed: ${err.message}` });
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(reportMonth); }, [reportMonth, load]);

  const setPriceRow = (idx, patch) => setPriceRows((prev) => prev.map((r, i) => (i === idx ? { ...r, ...patch } : r)));
  const setMacroRow = (idx, patch) => setMacroRows((prev) => prev.map((r, i) => (i === idx ? { ...r, ...patch } : r)));

  const save = async () => {
    setSaving(true);
    setStatus(null);
    try {
      const res = await fetch(`${API}/api/market-intel/grid`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          report_month: reportMonth,
          market_price_rows: priceRows.map((r) => ({ series_code: r.series_code, value: numOrNull(r.value) })),
          macro_rows: macroRows.map((r) => ({ metric_code: r.metric_code, value: numOrNull(r.value) })),
        }),
      });
      if (!res.ok) throw new Error(await res.text());
      setStatus({ type: 'success', text: 'Saved.' });
      await load(reportMonth);
    } catch (err) {
      setStatus({ type: 'error', text: `Save failed: ${err.message}` });
    } finally {
      setSaving(false);
    }
  };

  let lastCategory = null;

  return (
    <div style={{ minHeight: '100vh', display: 'flex', flexDirection: 'column', background: '#fff' }}>
      <GlobalNavbar />
      <div style={{ flex: 1, maxWidth: 1100, margin: '0 auto', padding: '22px 20px', width: '100%', boxSizing: 'border-box' }}>
        <h2 style={{ fontSize: '1.6rem', fontWeight: 700, color: '#202124', margin: '0 0 4px' }}>
          Market Intelligence Entry (Pages 2.41 / 2.42)
        </h2>
        <span style={{ fontSize: 13, color: '#5f6368' }}>
          One month at a time — this month&rsquo;s BigMint price series (USD/T) and India macro-economic figures.
          The report itself shows a rolling 12-month window for prices and a 13-month window (lagged one month,
          matching how these government/industry stats are published) for the macro table.
        </span>

        <div style={{ display: 'flex', gap: 12, alignItems: 'center', flexWrap: 'wrap', margin: '18px 0', border: '1px solid #dadce0', borderRadius: 8, padding: '14px 18px' }}>
          <label style={{ fontSize: 13, fontWeight: 600, color: '#374151' }}>Report Month</label>
          <input type="month" value={reportMonth} onChange={(e) => setReportMonth(e.target.value)}
                 style={{ padding: '6px 10px', fontSize: 14, border: '1px solid #d1d5db', borderRadius: 4 }} />
          <button onClick={save} disabled={saving || loading}
            style={{ marginLeft: 'auto', padding: '8px 22px', fontSize: 14, fontWeight: 700, background: !loading ? '#10b981' : '#9ca3af', color: '#fff', border: 'none', borderRadius: 6, cursor: !loading ? 'pointer' : 'not-allowed' }}>
            {saving ? 'Saving…' : 'Save All'}
          </button>
        </div>

        <Notice type={status?.type} text={status?.text} />

        {loading && <div style={{ padding: 40, textAlign: 'center', color: '#5f6368' }}>Loading…</div>}

        {!loading && (
          <>
            <div style={{ fontSize: 14, fontWeight: 700, color: '#1e293b', margin: '18px 0 8px' }}>
              Movement of Key Prices - International (USD/T)
            </div>
            <div style={{ border: '1px solid #dadce0', borderRadius: 8, overflow: 'hidden' }}>
              <table style={{ borderCollapse: 'collapse', width: '100%' }}>
                <thead>
                  <tr>
                    <th style={TH}>Series</th>
                    <th style={{ ...TH, textAlign: 'right' }}>Value ({reportMonth})</th>
                  </tr>
                </thead>
                <tbody>
                  {priceRows.map((r, idx) => {
                    const showHeader = r.category !== lastCategory;
                    lastCategory = r.category;
                    return (
                      <React.Fragment key={r.series_code}>
                        {showHeader && (
                          <tr>
                            <td colSpan={2} style={{ ...TD, background: '#eff6ff', fontWeight: 700, fontSize: 12 }}>
                              {CATEGORY_LABEL[r.category] || r.category}
                            </td>
                          </tr>
                        )}
                        <tr>
                          <td style={{ ...TD, fontWeight: 600 }}>{r.label}</td>
                          <td style={{ ...TD, textAlign: 'right' }}>
                            <input value={r.value} onChange={(e) => setPriceRow(idx, { value: e.target.value })} style={cellInput} />
                          </td>
                        </tr>
                      </React.Fragment>
                    );
                  })}
                </tbody>
              </table>
            </div>

            <div style={{ fontSize: 14, fontWeight: 700, color: '#1e293b', margin: '26px 0 8px' }}>
              India Macro Economic Indicators
            </div>
            <div style={{ border: '1px solid #dadce0', borderRadius: 8, overflow: 'hidden' }}>
              <table style={{ borderCollapse: 'collapse', width: '100%' }}>
                <thead>
                  <tr>
                    <th style={TH}>Key Parameter</th>
                    <th style={TH}>Unit</th>
                    <th style={{ ...TH, textAlign: 'right' }}>Value ({reportMonth})</th>
                  </tr>
                </thead>
                <tbody>
                  {macroRows.map((r, idx) => (
                    <tr key={r.metric_code}>
                      <td style={{ ...TD, fontWeight: 600 }}>{r.label}</td>
                      <td style={{ ...TD, fontStyle: 'italic', color: '#5f6368', fontSize: 12 }}>{r.unit}</td>
                      <td style={{ ...TD, textAlign: 'right' }}>
                        <input value={r.value} onChange={(e) => setMacroRow(idx, { value: e.target.value })} style={cellInput} />
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </>
        )}
      </div>
    </div>
  );
}

export default function MarketIntelEntryPage() {
  return (
    <RequireEditor>
      <MarketIntelEntryInner />
    </RequireEditor>
  );
}
