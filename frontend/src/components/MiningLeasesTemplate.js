'use client';

import React from 'react';

// Mirrors backend/page_templates/mining_leases.html — Annexure-1 "SAIL Mining
// at a Glance" (backend/page_mining_leases.py, mining_leases.py). Colours copied
// from colors_config.json (border_light / border_dark / mining_head_*).
const C = { title: 'rgb(0,0,255)', secondary: '#475569', light: '#cbd5e1', dark: '#334155', headBg: '#EAE1F5', headText: '#060177' };
const COL_WIDTHS = ['3.6%', '15%', '8%', '16%', '8.5%', '10%', '9.9%', '29%'];
const HEADERS = ['S.No.', 'Name of Mines', 'State', 'Name of Lease', 'Mineral', 'Area in Ha',
  'Reserves & Resource as on 01.04.2026 (MT)', 'Current Status (Operational / Non-Operational)'];
const td = { border: `1px solid ${C.light}`, padding: '0.8pt 2pt', textAlign: 'center', verticalAlign: 'middle' };

// One cell of a span column: nothing when a cell above covers it, else a rowSpan.
function Span({ cell, left, bold, pre }) {
  if (!cell || !cell.span) return null;
  return (
    <td rowSpan={cell.span > 1 ? cell.span : undefined}
        style={{ ...td, textAlign: left ? 'left' : 'center', fontWeight: bold ? 700 : undefined, whiteSpace: pre ? 'pre-line' : undefined }}>
      {cell.text}
    </td>
  );
}

export default function MiningLeasesTemplate({ data }) {
  const { title, available, rows = [] } = data || {};
  return (
    <div>
      <div style={{ textAlign: 'center', fontWeight: 700, fontSize: '11pt', textDecoration: 'underline', color: C.title, marginBottom: 6 }}>{title}</div>
      <div style={{ textAlign: 'right', fontSize: '9pt', fontStyle: 'italic', color: C.secondary, marginBottom: 3 }}>Details of SAIL Mining Leases</div>
      {!available ? (
        <div style={{ textAlign: 'center', fontSize: '11pt', color: C.secondary, marginTop: '60mm' }}>Mining lease details not yet entered</div>
      ) : (
        <table style={{ borderCollapse: 'collapse', width: '100%', tableLayout: 'fixed', fontSize: '6.6pt', lineHeight: 1.1 }}>
          <colgroup>{COL_WIDTHS.map((w, i) => <col key={i} style={{ width: w }} />)}</colgroup>
          <thead>
            <tr>{HEADERS.map((h) => (
              <th key={h} style={{ ...td, borderColor: C.dark, background: C.headBg, color: C.headText, fontWeight: 700 }}>{h}</th>
            ))}</tr>
          </thead>
          <tbody>
            {rows.map((r, i) => (
              <tr key={i}>
                <td style={td}>{r.s_no}</td>
                <Span cell={r.mine} left bold />
                <Span cell={r.state} />
                <Span cell={r.lease} left />
                <Span cell={r.mineral} />
                <Span cell={r.area} />
                <Span cell={r.reserves} pre />
                <Span cell={r.status} left />
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
