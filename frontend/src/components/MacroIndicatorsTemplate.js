'use client';

import React from 'react';

// Mirrors backend/page_templates/macro_indicators.html — see
// backend/page_macro_indicators.py for the metric registry and the
// per-row sequential heatmap (bg/fg computed server-side per cell).
// Genuine A4-landscape page (spliced in by pdf.py's _LANDSCAPE_TYPES
// handling).

const C = { border: '#b0b0b0', headerBg: '#e8eef7', secondary: '#5f6368' };

const cell = { border: `0.5pt solid ${C.border}`, padding: '3pt 3pt', textAlign: 'center', overflow: 'hidden', fontSize: '7.6pt' };
const th = { ...cell, background: C.headerBg, fontWeight: 700, fontSize: '7.8pt' };

export default function MacroIndicatorsTemplate({ data }) {
  const {
    title = '', period_label: periodLabel = '', column_labels: columnLabels = [],
    rows = [], source = '', footnote = '',
  } = data || {};

  return (
    <div style={{ fontFamily: 'inherit', color: '#333333' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', marginBottom: 6 }}>
        <div style={{ textAlign: 'center', fontWeight: 700, fontSize: '11pt', textDecoration: 'underline', color: 'rgb(0,0,255)' }}>
          {title}
        </div>
        <div style={{ fontSize: '9pt', fontStyle: 'italic', color: C.secondary }}>{periodLabel}</div>
      </div>

      <table style={{ borderCollapse: 'collapse', width: '100%', tableLayout: 'fixed' }}>
        <colgroup>
          <col style={{ width: '15%' }} />
          <col style={{ width: '9%' }} />
          {columnLabels.map((_, i) => <col key={i} />)}
        </colgroup>
        <thead>
          <tr>
            <th style={{ ...th, textAlign: 'left' }}>Key Parameters</th>
            <th style={th}>Unit</th>
            {columnLabels.map((lab) => <th key={lab} style={th}>{lab}</th>)}
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.label}>
              <td style={{ ...cell, textAlign: 'left', fontWeight: 600 }}>{r.label}</td>
              <td style={{ ...cell, textAlign: 'left', fontStyle: 'italic', color: C.secondary, fontSize: '6.6pt' }}>{r.unit}</td>
              {r.cells.map((c, i) => (
                <td key={i} style={{
                  ...cell, fontWeight: 600, fontVariantNumeric: 'tabular-nums',
                  background: c.bg || undefined, color: c.fg || undefined,
                }}>{c.value}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>

      <div style={{ marginTop: 6, fontSize: '7.4pt', color: C.secondary }}>
        {source}<br />
        <span style={{ fontStyle: 'italic' }}>{footnote}</span>
      </div>
    </div>
  );
}
