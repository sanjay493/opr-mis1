'use client';

import React from 'react';
import { chemSub } from '@/lib/chemFormat';

// Mirrors backend/page_templates/epi.html — see page_epi.py for the data
// shape (it wraps page_techno.py's already-computed page-27 figures for
// just the 3 EPI parameters, no new computation here).
const BORDER = '#334155';
const TITLE_COLOR = '#333333';
const NOTE_COLOR = '#475569';

const cellStyle = { border: `1px solid ${BORDER}`, padding: '6px 4px', textAlign: 'center', fontSize: '7.3pt' };
const thStyle = { ...cellStyle, fontWeight: 700 };

export default function EpiTemplate({ data }) {
  const {
    title = '', fy2_label = '', fy1_label = '', target_label = '',
    month_labels = [], cply_label = '', cum_label = '', cum_cply_label = '',
    sections = [],
  } = data || {};
  const totalCols = 5 + month_labels.length + 3;

  return (
    <div style={{ fontFamily: 'inherit' }}>
      <div style={{ textAlign: 'center', fontWeight: 700, fontSize: '11pt', textDecoration: 'underline', marginBottom: 6, color: TITLE_COLOR }}>
        {title}
      </div>

      <table style={{ width: '100%', borderCollapse: 'collapse' }}>
        <thead>
          <tr>
            <th style={thStyle} rowSpan={2}>Parameters</th>
            <th style={thStyle} rowSpan={2}>Plant</th>
            <th style={thStyle} colSpan={2}>Actual</th>
            <th style={thStyle} rowSpan={2}>{target_label}</th>
            <th style={thStyle} colSpan={month_labels.length}>Actual</th>
            <th style={thStyle} rowSpan={2}>{cply_label}<br />Actual</th>
            <th style={thStyle} colSpan={2}>Actual</th>
          </tr>
          <tr>
            <th style={thStyle}>{fy2_label}</th>
            <th style={thStyle}>{fy1_label}</th>
            {month_labels.map((m, i) => <th key={i} style={thStyle}>{m}</th>)}
            <th style={thStyle}>{cum_label}</th>
            <th style={thStyle}>{cum_cply_label}</th>
          </tr>
        </thead>
        <tbody>
          {sections.map((sec, si) => (
            <React.Fragment key={sec.label}>
              {sec.rows.map((row, i) => (
                <tr
                  key={row.label}
                  style={{
                    ...(i === sec.rows.length - 1 ? { borderBottom: `1px solid ${BORDER}` } : {}),
                    ...(row.label === 'SAIL' ? { fontWeight: 700 } : {}),
                  }}
                >
                  {i === 0 && (
                    <td style={{ ...cellStyle, fontWeight: 700, verticalAlign: 'middle' }} rowSpan={sec.rows.length}>
                      {chemSub(sec.label)}<br /><span style={{ fontWeight: 400, fontSize: '0.85em' }}>({chemSub(row.unit)})</span>
                    </td>
                  )}
                  <td style={{ ...cellStyle, textAlign: 'left', fontWeight: 600 }}>{row.label}</td>
                  <td style={cellStyle}>{row.fy2 || '—'}</td>
                  <td style={cellStyle}>{row.fy1 || '—'}</td>
                  <td style={cellStyle}>{row.target || '—'}</td>
                  {row.months.map((v, mi) => <td key={mi} style={cellStyle}>{v || '—'}</td>)}
                  <td style={cellStyle}>{row.cply || '—'}</td>
                  <td style={cellStyle}>{row.cum || '—'}</td>
                  <td style={cellStyle}>{row.cum_cply || '—'}</td>
                </tr>
              ))}
              {si < sections.length - 1 && (
                <tr>
                  <td colSpan={totalCols} style={{ border: 'none', height: 3, padding: 0 }} />
                </tr>
              )}
            </React.Fragment>
          ))}
        </tbody>
      </table>

      <div style={{ fontSize: '7.5pt', marginTop: 6, color: NOTE_COLOR }}>
        Environment Management Division (EMD)
      </div>
    </div>
  );
}
