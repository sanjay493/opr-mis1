'use client';

import React from 'react';

// Mirrors backend/page_templates/special_steel_donut.html (styles: the
// .ssd-* block in main.html) — per-plant FS/Semis/Spl. FS/Spl. Semis rows
// with merged SS / Spl. SS total cells, then the server-rendered
// value-addition bubble chart (bubble_svg, from page_special_steel_donut.py).
const C = {
  title: 'rgb(0,0,255)',
  black: '#000000',
  secondary: '#475569',
  dark: '#334155',
  darkest: '#1e293b',
  medium: '#94a3b8',
  sailBg: '#dcfce7',
  totalBg: '#f1f5f9',
  special: '#166534',
  rust: '#B7410E',
};

const th = { padding: '1.5px 5px', border: `1px solid ${C.dark}`, fontSize: '9.5pt', textAlign: 'center', whiteSpace: 'nowrap', color: C.black };
const side = { borderLeft: `1px solid ${C.medium}`, borderRight: `1px solid ${C.medium}`, textAlign: 'center', verticalAlign: 'middle' };

function Stats({ lines, bold }) {
  return (lines || []).map((line, i) => (
    <div key={i} style={{ fontSize: '7.5pt', lineHeight: 1.0, whiteSpace: 'nowrap', fontWeight: bold ? 700 : undefined }}>{line}</div>
  ));
}

export default function SpecialSteelDonutTemplate({ data }) {
  const { title = '', fy_label = '', month_label = '', cum_label = '', entities = [], bubble_svg } = data || {};

  return (
    <div style={{ padding: '2px 8px' }}>
      <div style={{ position: 'relative', padding: '2px 46px 2px 0', marginBottom: 1 }}>
        <div style={{ textAlign: 'center', fontWeight: 700, fontSize: '11.5pt', color: C.title }}>{title}</div>
        <div style={{ position: 'absolute', top: '50%', right: 0, transform: 'translateY(-50%)', fontSize: '7.5pt', fontWeight: 700, color: C.secondary }}>Unit: T</div>
      </div>

      <table style={{ margin: '0 auto', borderCollapse: 'collapse', border: `2px solid ${C.darkest}` }}>
        <thead>
          <tr>
            <th style={th}>Plant</th>
            <th colSpan={2} style={th}>Metric</th>
            <th colSpan={2} style={th}>Annual ABP Plan {fy_label}</th>
            <th colSpan={2} style={th}>{month_label} (Actual)</th>
            <th colSpan={2} style={th}>{cum_label} (Actual)</th>
          </tr>
        </thead>
        <tbody>
          {entities.map((ent) => ent.rows.map((row, ri) => {
            const borderTop = row.is_entity_first
              ? `2px solid ${C.darkest}`
              : row.special && row.is_block_first ? `1px dashed ${C.dark}` : undefined;
            const color = row.special ? C.special : undefined;
            const totalCell = { ...side, fontWeight: 700, background: C.totalBg, padding: '1px 5px', color, borderTop };
            return (
              <tr key={`${ent.label}-${ri}`}>
                {row.is_entity_first && (
                  <td rowSpan={ent.rowspan} style={{
                    fontWeight: 700, textAlign: 'center', verticalAlign: 'middle',
                    borderLeft: `1px solid ${C.dark}`, borderRight: `1px solid ${C.dark}`, borderBottom: `1px solid ${C.dark}`,
                    borderTop, fontSize: '11pt', whiteSpace: 'nowrap', padding: '0 5px',
                    background: ent.label === 'SAIL' ? C.sailBg : undefined,
                  }}>{ent.label}</td>
                )}
                <td style={{ ...side, fontWeight: 600, fontSize: '8.3pt', whiteSpace: 'nowrap', padding: '0 4px', color, borderTop }}>{row.metric_label}</td>
                {row.is_block_first && (
                  <td rowSpan={row.block_span} style={{ ...totalCell, fontSize: '8.3pt', whiteSpace: 'nowrap', padding: '0 4px' }}>{row.total_label}</td>
                )}
                {row.cells.map((cell, ci) => (
                  <React.Fragment key={ci}>
                    <td style={{ ...side, padding: '1px 5px', color, borderTop }}>
                      <Stats lines={cell} bold={row.emphasis} />
                    </td>
                    {row.is_block_first && (
                      <td rowSpan={row.block_span} style={totalCell}>
                        <Stats lines={row.total_cells?.[ci]} />
                      </td>
                    )}
                  </React.Fragment>
                ))}
              </tr>
            );
          }))}
        </tbody>
      </table>

      {bubble_svg && (
        <div style={{ marginTop: 5 }}>
          <div style={{ textAlign: 'center', fontWeight: 700, fontSize: '10pt', color: C.black }}>
            Value-Addition Positioning — {cum_label} (Actual)
          </div>
          <div style={{ textAlign: 'center', fontSize: '9.5pt', fontStyle: 'italic', color: C.rust, marginBottom: 1 }}>
            Bubble size &#8733; Saleable Steel Despatch (Tonnes)
          </div>
          <div style={{ width: '90%' }} dangerouslySetInnerHTML={{ __html: bubble_svg }} />
        </div>
      )}
    </div>
  );
}
