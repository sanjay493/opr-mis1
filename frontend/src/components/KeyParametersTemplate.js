import React from 'react';

// Mirrors backend/page_templates/key_parameters.html — plain data table, no
// editing (every value here is computed from other tables' data, not a
// primary source itself). Rows come in 3 shapes (see page_key_parameters.py):
// section (group label spanning the full width), spacer (blank full-width
// row), and data (the normal Parameter/UoM/plant-values row, optionally
// `highlight`ed, or a `continuation` of the row above sharing its rowSpan-ed
// label cell). None of `parameter` (undefined on section/spacer rows, and
// explicitly null on continuation rows) is unique, so keys are index-based.
const C = {
  textHeadingDark: '#1e293b',
  textSecondary: '#475569',
  border: '#000000',
  sectionBg: '#f8fafc',
  highlightBg: '#eef2f6',
  // Max/min cell highlight within the Major Blast Furnace Techno-economic
  // Parameters section (see page_key_parameters.py's max_plants/min_plants)
  // — neutral colors (not green/red) since "highest value" isn't
  // consistently "better" across these rows (e.g. Coke Rate: lower is
  // better, so its max is the worse figure) — matches
  // highlight_actual_bg/highlight_target_band_bg in colors_config.json,
  // used the same way on the PDF side.
  maxBg: '#dbeafe',
  minBg: '#fef9c3',
};

export default function KeyParametersTemplate({ data }) {
  const { title = '', plants = [], rows = [] } = data || {};
  const cellStyle = { padding: '1.6px 5px', border: `1px solid ${C.border}`, textAlign: 'center' };
  const colSpan = 2 + plants.length;

  return (
    <div style={{ padding: 2, fontFamily: "'Roboto', sans-serif", fontSize: '8pt' }}>
      <div style={{ textAlign: 'center', fontWeight: 700, fontSize: '11pt', color: C.textHeadingDark, marginBottom: 3 }}>
        {title}
      </div>
      <table style={{ width: '100%', borderCollapse: 'collapse', border: `1px solid ${C.border}`, fontSize: '8pt' }}>
        <thead>
          <tr>
            <th style={{ ...cellStyle, textAlign: 'left', width: '30%' }}>Parameter</th>
            <th style={{ ...cellStyle, width: '10%' }}>UoM</th>
            {plants.map((p) => <th key={p} style={cellStyle}>{p}</th>)}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, i) => {
            if (row.type === 'section') {
              return (
                <tr key={i}>
                  <td colSpan={colSpan} style={{ ...cellStyle, textAlign: 'left', fontWeight: 700, background: C.sectionBg }}>
                    {row.label}
                  </td>
                </tr>
              );
            }
            if (row.type === 'spacer') {
              return (
                <tr key={i}>
                  <td colSpan={colSpan} style={{ padding: 0, height: 3, lineHeight: '3px', fontSize: 1, border: `1px solid ${C.border}` }}>&nbsp;</td>
                </tr>
              );
            }
            return (
              <tr key={i} style={{ background: row.highlight ? C.highlightBg : undefined }}>
                {!row.continuation && (
                  <td rowSpan={row.label_rowspan || undefined} style={{ ...cellStyle, textAlign: 'left' }}>
                    {row.parameter}
                    {row.note && (
                      <div style={{ fontSize: '6.5pt', fontStyle: 'italic', fontWeight: 400, color: C.textSecondary }}>
                        {row.note}
                      </div>
                    )}
                  </td>
                )}
                <td style={{ ...cellStyle, fontStyle: 'italic', color: C.textSecondary }}>{row.unit}</td>
                {plants.map((p) => {
                  const isMax = row.max_plants && row.max_plants.includes(p);
                  const isMin = row.min_plants && row.min_plants.includes(p);
                  const bg = isMax ? C.maxBg : (isMin ? C.minBg : undefined);
                  return (
                    <td key={p} style={{ ...cellStyle, background: bg, fontWeight: bg ? 700 : undefined }}>
                      {row.plant_values && row.plant_values[p] !== null && row.plant_values[p] !== undefined ? row.plant_values[p] : '—'}
                    </td>
                  );
                })}
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
