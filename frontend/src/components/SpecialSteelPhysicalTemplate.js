'use client';

import React from 'react';

// Mirrors backend/page_templates/special_steel_physical.html — see
// backend/page_special_steel_physical.py for the column definitions and how
// each %FF / %Growth figure is computed. Genuine A4-landscape page (spliced
// in by pdf.py's _LANDSCAPE_TYPES handling).

const C = {
  text: '#333333',
  secondary: '#5f6368',
  border: '#b0b0b0',
  borderDark: '#5f6368',
  headerBg: '#e8eef7',
};

const cell = {
  border: `0.5pt solid ${C.border}`,
  padding: '1.6pt 2pt',
  textAlign: 'center',
  fontSize: '6.8pt',
  overflow: 'hidden',
};
const th = { ...cell, background: C.headerBg, fontWeight: 700 };
const num = { ...cell, textAlign: 'right', fontVariantNumeric: 'tabular-nums' };
const sep = { borderLeft: `1.2pt solid ${C.borderDark}` };

export default function SpecialSteelPhysicalTemplate({ data }) {
  const {
    title = '', unit = 'Tonnes', prev_fy: prevFy = '', cur_fy: curFy = '',
    ytd_label: ytdLabel = '', history_fys: historyFys = [],
    sections = [], notes = [], ipt_title: iptTitle = '', ipt_rows: iptRows = [],
  } = data || {};

  return (
    <div style={{ fontFamily: 'inherit', color: C.text }}>
      <div style={{ textAlign: 'center', fontWeight: 700, fontSize: '11pt', textDecoration: 'underline', marginBottom: 4 }}>
        {title}
      </div>
      <div style={{ textAlign: 'right', fontSize: '8pt', fontStyle: 'italic', color: C.secondary, marginBottom: 6 }}>
        Unit: {unit}
      </div>

      <div style={{ overflowX: 'auto' }}>
        <table style={{ borderCollapse: 'collapse', width: '100%', tableLayout: 'fixed' }}>
          <thead>
            <tr>
              <th rowSpan={2} style={th}>Plant</th>
              <th rowSpan={2} style={th}>Item</th>
              <th rowSpan={2} style={th}>Capacity</th>
              <th colSpan={2} style={th}>Best Achieved</th>
              {historyFys.map((fy) => <th key={fy} rowSpan={2} style={th}>{fy}</th>)}
              <th rowSpan={2} style={{ ...th, ...sep }}>{prevFy} Actual</th>
              <th rowSpan={2} style={{ ...th, ...sep }}>{curFy} ABP</th>
              <th colSpan={5} style={{ ...th, ...sep }}>{ytdLabel}</th>
            </tr>
            <tr>
              <th style={th}>Actual</th>
              <th style={th}>Year</th>
              <th style={{ ...th, ...sep }}>APP</th>
              <th style={th}>Actual</th>
              <th style={th}>%FF</th>
              <th style={th}>CPLY</th>
              <th style={th}>%Gr</th>
            </tr>
          </thead>
          <tbody>
            {sections.map((sec) => sec.rows.map((r, i) => (
              <tr key={`${sec.plant}-${r.series_label}`}>
                {i === 0 && (
                  <td rowSpan={sec.rows.length} style={{ ...cell, fontWeight: 700, background: C.headerBg }}>
                    {sec.plant}
                  </td>
                )}
                <td style={{ ...cell, textAlign: 'left', fontWeight: 600, whiteSpace: 'nowrap' }}>{r.series_label}</td>
                <td style={num}>{r.capacity}</td>
                <td style={num}>{r.best_actual}</td>
                <td style={cell}>{r.best_year}</td>
                {historyFys.map((fy) => <td key={fy} style={num}>{r.history[fy]}</td>)}
                <td style={{ ...num, ...sep }}>{r.prev_actual}</td>
                <td style={{ ...num, ...sep }}>{r.cur_abp}</td>
                <td style={{ ...num, ...sep }}>{r.ytd_app}</td>
                <td style={num}>{r.ytd_actual}</td>
                <td style={num}>{r.ytd_pct_ful}</td>
                <td style={num}>{r.ytd_cply}</td>
                <td style={num}>{r.ytd_growth}</td>
              </tr>
            )))}
          </tbody>
        </table>
      </div>

      {notes.length > 0 && (
        <ul style={{ margin: '6pt 0 4pt', paddingLeft: '16pt', fontSize: '7.5pt' }}>
          {notes.map((n, i) => <li key={i} style={{ marginBottom: '1.5pt' }}>{n}</li>)}
        </ul>
      )}

      {iptRows.length > 0 && (
        <div style={{ marginTop: '6pt' }}>
          <div style={{ fontWeight: 700, fontSize: '8.5pt', marginBottom: '3pt' }}>{iptTitle}</div>
          <table style={{ borderCollapse: 'collapse', fontSize: '7.5pt' }}>
            <thead>
              <tr>
                {['Item (‘000 T)', 'From', 'To', 'Plan'].map((h) => (
                  <th key={h} style={{ ...th, padding: '2pt 10pt' }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {iptRows.map((r, i) => (
                <tr key={i}>
                  {r.item_rowspan > 0 && (
                    <td rowSpan={r.item_rowspan} style={{ ...cell, padding: '2pt 10pt', textAlign: 'left' }}>{r.item}</td>
                  )}
                  <td style={{ ...cell, padding: '2pt 10pt' }}>{r.from}</td>
                  <td style={{ ...cell, padding: '2pt 10pt' }}>{r.to}</td>
                  <td style={{ ...num, padding: '2pt 10pt' }}>{r.plan}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
