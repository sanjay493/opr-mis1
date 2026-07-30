import React from 'react';

// Mirrors backend/page_templates/key_parameters.html — plain data table, no
// editing (every value here is computed from other tables' data, not a
// primary source itself).
const C = {
  textHeadingDark: '#1e293b',
  textSecondary: '#475569',
  border: '#000000',
  zebraBg: '#f8fafc',
};

export default function KeyParametersTemplate({ data }) {
  const { title = '', plants = [], rows = [] } = data || {};
  const cellStyle = { padding: '2px 5px', border: `1px solid ${C.border}`, textAlign: 'center' };

  return (
    <div style={{ padding: 6, fontFamily: "'Roboto', sans-serif", fontSize: '8pt' }}>
      <div style={{ textAlign: 'center', fontWeight: 700, fontSize: '11pt', color: C.textHeadingDark, marginBottom: 6 }}>
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
          {rows.map((row, i) => (
            <tr key={row.parameter} style={{ background: i % 2 === 1 ? C.zebraBg : undefined }}>
              <td style={{ ...cellStyle, textAlign: 'left' }}>{row.parameter}</td>
              <td style={{ ...cellStyle, fontStyle: 'italic', color: C.textSecondary }}>{row.unit}</td>
              {plants.map((p) => (
                <td key={p} style={cellStyle}>
                  {row.plant_values && row.plant_values[p] !== null && row.plant_values[p] !== undefined ? row.plant_values[p] : '—'}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
