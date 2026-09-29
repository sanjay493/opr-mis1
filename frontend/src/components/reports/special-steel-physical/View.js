'use client';

import React, { useState, useEffect } from 'react';
import GlobalNavbar from '@/components/GlobalNavbar';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || '';

const cellBase = {
  padding: '5px 8px',
  fontSize: '10pt',
  borderBottom: '1px solid #e8eaed',
  borderRight: '1px solid #f1f3f4',
  whiteSpace: 'nowrap',
  textAlign: 'right',
  fontVariantNumeric: 'tabular-nums',
};
const HEAD = {
  ...cellBase,
  position: 'sticky',
  top: 0,
  zIndex: 2,
  backgroundColor: '#e8f0fe',
  textAlign: 'center',
  fontWeight: 700,
  color: '#174ea6',
};
const sepLeft = { borderLeft: '2px solid #9aa7bd' };
// cur-FY ABP — the single planning-target column: warm tint.
// Apr-<report month> YTD block: cool tint.
const abpBg = { backgroundColor: '#fef3d6' };
const abpHead = { backgroundColor: '#fde3aa' };
const ytdBg = { backgroundColor: '#e7f4ea' };
const ytdHead = { backgroundColor: '#cbe8d2' };

export default function SpecialSteelPhysicalPage() {
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    fetch(`${API_BASE}/api/special-steel-physical`)
      .then((r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        return r.json();
      })
      .then(setData)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  const historyFys = data?.history_fys || [];
  const sections = data?.sections || [];

  return (
    <div style={{ minHeight: '100vh', display: 'flex', flexDirection: 'column', backgroundColor: '#ffffff' }}>
      <GlobalNavbar />
      <main style={{ flex: 1, maxWidth: 1800, width: '100%', margin: '0 auto', padding: 32, boxSizing: 'border-box' }}>
        <h1 style={{ fontSize: '20pt', fontWeight: 900, color: '#202124', margin: 0 }}>
          {data?.title || 'Special Steel Plants Physical Performance'}
        </h1>
        <p style={{ fontSize: '11pt', color: '#5f6368', marginTop: 6 }}>
          Unit: {data?.unit || 'Tonnes'}
        </p>

        {loading && <div style={{ padding: 40, color: '#5f6368' }}>Loading…</div>}
        {error && (
          <div style={{ padding: '14px 18px', border: '1px solid #f28b82', borderRadius: 8, backgroundColor: '#fce8e6', color: '#c5221f', fontSize: '11pt' }}>
            Failed to load: {error}
          </div>
        )}

        {data && !loading && (
          <>
            <div style={{ border: '1px solid #dadce0', borderRadius: 8, overflow: 'auto', marginTop: 16 }}>
              <table style={{ borderCollapse: 'separate', borderSpacing: 0, width: '100%' }}>
                <thead>
                  <tr>
                    <th rowSpan={2} style={{ ...HEAD, left: 0, zIndex: 3, textAlign: 'left', minWidth: 60 }}>Plant</th>
                    <th rowSpan={2} style={{ ...HEAD, left: 60, zIndex: 3, textAlign: 'left', minWidth: 120 }}>Item</th>
                    <th rowSpan={2} style={HEAD}>Capacity</th>
                    <th colSpan={2} style={HEAD}>Best Achieved</th>
                    {historyFys.map((fy) => <th key={fy} rowSpan={2} style={HEAD}>{fy}</th>)}
                    <th rowSpan={2} style={{ ...HEAD, ...sepLeft }}>{data.prev_fy}</th>
                    <th rowSpan={2} style={{ ...HEAD, ...sepLeft, ...abpHead }}>{data.cur_fy} ABP</th>
                    <th colSpan={5} style={{ ...HEAD, ...sepLeft, ...ytdHead }}>{data.ytd_label}</th>
                  </tr>
                  <tr>
                    <th style={{ ...HEAD, top: 31 }}>Actual</th>
                    <th style={{ ...HEAD, top: 31 }}>Year</th>
                    <th style={{ ...HEAD, top: 31, ...sepLeft, ...ytdHead }}>APP</th>
                    <th style={{ ...HEAD, top: 31, ...ytdHead }}>Actual</th>
                    <th style={{ ...HEAD, top: 31, ...ytdHead }}>%FF</th>
                    <th style={{ ...HEAD, top: 31, ...ytdHead }}>CPLY</th>
                    <th style={{ ...HEAD, top: 31, ...ytdHead }}>%Gr</th>
                  </tr>
                </thead>
                <tbody>
                  {sections.map((sec) => sec.rows.map((r, i) => (
                    <tr key={`${sec.plant}-${r.series_label}`}>
                      {i === 0 && (
                        <td rowSpan={sec.rows.length} style={{ ...cellBase, position: 'sticky', left: 0, textAlign: 'left', fontWeight: 700, background: '#f8f9fa' }}>
                          {sec.plant}
                        </td>
                      )}
                      <td style={{ ...cellBase, position: 'sticky', left: 60, textAlign: 'left', fontWeight: 600, background: '#fff' }}>{r.series_label}</td>
                      <td style={cellBase}>{r.capacity}</td>
                      <td style={cellBase}>{r.best_actual}</td>
                      <td style={{ ...cellBase, textAlign: 'center' }}>{r.best_year}</td>
                      {historyFys.map((fy) => <td key={fy} style={cellBase}>{r.history[fy]}</td>)}
                      <td style={{ ...cellBase, ...sepLeft }}>{r.prev_actual}</td>
                      <td style={{ ...cellBase, ...sepLeft, ...abpBg }}>{r.cur_abp}</td>
                      <td style={{ ...cellBase, ...sepLeft, ...ytdBg }}>{r.ytd_app}</td>
                      <td style={{ ...cellBase, ...ytdBg }}>{r.ytd_actual}</td>
                      <td style={{ ...cellBase, ...ytdBg }}>{r.ytd_pct_ful}</td>
                      <td style={{ ...cellBase, ...ytdBg }}>{r.ytd_cply}</td>
                      <td style={{ ...cellBase, ...ytdBg }}>{r.ytd_growth}</td>
                    </tr>
                  )))}
                </tbody>
              </table>
            </div>

            {(data.notes || []).length > 0 && (
              <ul style={{ marginTop: 14, fontSize: '10.5pt', color: '#3c4043' }}>
                {data.notes.map((n, i) => <li key={i} style={{ marginBottom: 4 }}>{n}</li>)}
              </ul>
            )}

            {(data.ipt_rows || []).length > 0 && (
              <div style={{ marginTop: 28 }}>
                <h2 style={{ fontSize: '13pt', fontWeight: 800, color: '#202124' }}>{data.ipt_title}</h2>
                <table style={{ borderCollapse: 'collapse', fontSize: '10.5pt', marginTop: 8 }}>
                  <thead>
                    <tr>
                      {['Item (‘000 T)', 'From', 'To', 'Plan'].map((h) => (
                        <th key={h} style={{ ...HEAD, position: 'static', padding: '6px 14px' }}>{h}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {data.ipt_rows.map((r, i) => (
                      <tr key={i}>
                        {r.item_rowspan > 0 && (
                          <td rowSpan={r.item_rowspan} style={{ padding: '6px 14px', border: '1px solid #dadce0', fontWeight: 600 }}>{r.item}</td>
                        )}
                        <td style={{ padding: '6px 14px', border: '1px solid #dadce0', textAlign: 'center' }}>{r.from}</td>
                        <td style={{ padding: '6px 14px', border: '1px solid #dadce0', textAlign: 'center' }}>{r.to}</td>
                        <td style={{ padding: '6px 14px', border: '1px solid #dadce0', textAlign: 'right', fontVariantNumeric: 'tabular-nums' }}>{r.plan}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </>
        )}
      </main>
    </div>
  );
}
