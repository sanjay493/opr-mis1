'use client';

import React from 'react';

// Mirrors backend/page_templates/rail_report.html — see
// backend/page_rail_report.py for the metric registry and the 4 computed
// rows. Genuine A4-landscape page (spliced in by pdf.py's
// _LANDSCAPE_TYPES handling).

const C = {
  text: '#333333',
  secondary: '#5f6368',
  border: '#b0b0b0',
  headerBg: '#e8eef7',
  bandGreen: '#dcfce7',
  bandYellow: '#fef9c3',
  bandOrange: '#fed7aa',
  bandBlue: '#e0f2fe',
  remarkRed: '#9a3412',
};

const cell = {
  border: `0.5pt solid ${C.border}`,
  padding: '3pt 4pt',
  textAlign: 'center',
  fontSize: '8pt',
  overflow: 'hidden',
};
const th = { ...cell, background: C.headerBg, fontWeight: 700 };
const bandBg = { green: C.bandGreen, yellow: C.bandYellow, orange: C.bandOrange, blue: C.bandBlue };

export default function RailReportTemplate({ data }) {
  const { title = '', columns = [], rows = [], notes = [] } = data || {};

  return (
    <div style={{ fontFamily: 'inherit', color: C.text }}>
      <div style={{ textAlign: 'center', fontWeight: 700, fontSize: '11pt', textDecoration: 'underline', marginBottom: 6 }}>
        {title}
      </div>

      <div style={{ overflowX: 'auto' }}>
        <table style={{ borderCollapse: 'collapse', width: '100%', tableLayout: 'fixed' }}>
          <colgroup>
            <col style={{ width: '15%' }} />
            {columns.map((c) => <col key={c.key} />)}
          </colgroup>
          <thead>
            <tr>
              <th style={th}>FY</th>
              {columns.map((c, i) => (
                <th key={c.key} style={th}>
                  {i === columns.length - 1 ? (
                    <span style={{ display: 'inline-block', background: C.bandOrange, fontWeight: 700, padding: '2pt 6pt', fontSize: '7.5pt', borderRadius: 2 }}>
                      {c.label}
                    </span>
                  ) : c.label}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((r, ri) => (
              <tr key={ri} style={r.bold ? { fontWeight: 700 } : undefined}>
                <td style={{ ...cell, textAlign: 'left', fontWeight: 600, whiteSpace: 'normal' }}>{r.label}</td>
                {columns.map((c) => (
                  <td key={c.key} style={{ ...cell, background: r.band ? bandBg[r.band] : undefined }}>
                    {r.cells?.[c.key]}
                    {r.notes?.[c.key] && (
                      <span style={{ display: 'block', fontSize: '6.4pt', fontStyle: 'italic', color: C.secondary }}>
                        ({r.notes[c.key]})
                      </span>
                    )}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {notes.length > 0 && (
        <ul style={{ margin: '8pt 0 4pt', paddingLeft: '16pt', fontSize: '8pt', color: C.remarkRed, fontWeight: 600 }}>
          {notes.map((n, i) => <li key={i} style={{ marginBottom: '2pt' }}>{n}</li>)}
        </ul>
      )}
    </div>
  );
}
