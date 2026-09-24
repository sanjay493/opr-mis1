'use client';

import React from 'react';

// Mirrors backend/page_templates/major_unit_records_plant.html (Annexure-III,
// one page per ISP). The backend's *_display strings are built for that
// Jinja template: a number followed by `<span class="mur-period">(...)</span>`,
// or "—", or an HTML-escaped free-text remark (see page_major_unit_records.py's
// _fmt_pair/_fmt_daily). They're parsed here rather than injected as HTML.

const BORDER = '0.5pt solid #5f6368';
const NAVY = '#1e3a8a';
const RUST = '#B7410E';
const TEAL = '#0f766e';

const PERIOD_RE = /^(.*?)\s*<span class="mur-period">\((.*)\)<\/span>$/;

function unescapeHtml(s) {
  return s
    .replace(/&lt;/g, '<').replace(/&gt;/g, '>')
    .replace(/&quot;/g, '"').replace(/&#x27;/g, "'")
    .replace(/&amp;/g, '&');
}

function DisplayCell({ display, bold, bg }) {
  const text = display ?? '—';
  const m = PERIOD_RE.exec(text);
  return (
    <td style={{ border: BORDER, padding: '2.5px 6px', textAlign: 'center', whiteSpace: 'nowrap', fontWeight: bold ? 700 : undefined, background: bg }}>
      {m ? (
        <>
          {m[1]}{' '}
          <span style={{ color: TEAL, fontWeight: 600, fontSize: '0.93em' }}>({m[2]})</span>
        </>
      ) : unescapeHtml(text)}
    </td>
  );
}

export default function MajorUnitRecordsTemplate({ data }) {
  const { plant_name: plantName, rows = [] } = data || {};

  return (
    <div>
      <div style={{ textAlign: 'center', fontWeight: 700, fontSize: '15pt', color: NAVY, textDecoration: 'underline', marginBottom: 2 }}>
        {plantName}
      </div>
      <div style={{ textAlign: 'center', fontWeight: 600, fontSize: '10.5pt', color: '#5f6368', marginBottom: 10 }}>
        Major Units — Best Achieved (Annual / Monthly &apos;000 T, Daily T; Oven Pushing in Nos/day)
      </div>

      <table style={{ fontSize: '11pt', borderCollapse: 'collapse', width: '100%', lineHeight: 1.2 }}>
        <thead>
          <tr>
            {['Unit', 'Annual Best', 'Monthly Best', 'Daily Best'].map((h) => (
              <th key={h} style={{ border: BORDER, padding: '2.5px 6px', fontWeight: 700, textAlign: 'center' }}>{h}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, i) => {
            const pushing = row.row_class === 'mur-row-pushing';
            const total = row.row_class === 'mur-row-total';
            const bg = pushing ? '#fff7e0' : total ? '#eaf2fb' : undefined;
            return (
              <tr key={`${row.label}-${i}`}>
                <td style={{
                  border: BORDER, padding: '2.5px 6px', textAlign: 'left', background: bg,
                  borderLeft: pushing ? `3px solid ${RUST}` : total ? `3px solid ${NAVY}` : BORDER,
                  fontWeight: pushing ? 600 : total ? 700 : undefined,
                }}>
                  {row.label}
                </td>
                <DisplayCell display={row.annual_display} bold={total} bg={bg} />
                <DisplayCell display={row.monthly_display} bold={total} bg={bg} />
                <DisplayCell display={row.daily_display} bold={total} bg={bg} />
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
