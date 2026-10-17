'use client';

import React from 'react';

// Mirrors backend/page_templates/mines_performance.html — one row block per
// mine / group / SAIL (see backend/mines_performance.py). The PDF splits the
// blocks across physical pages (pdf.py's _plan_mines_performance_layout);
// the preview shows them as one continuous table on a page that grows to fit.
const C = {
  title: 'rgb(0,0,255)',
  primary: '#0f172a',
  black: '#000000',
  medium: '#94a3b8',
  light: '#cbd5e1',
  totalBg: '#FEF3C7',
  planBg: '#FFF2CC',
  actBg: '#C6EFCE',
  grBg: '#e2e8f0',
};
const COL_BG = { plan: C.planBg, act: C.actBg, gr: C.grBg };
const NARROW = "'Arial Narrow', Arial, sans-serif";

const th = {
  fontFamily: NARROW, fontSize: '8.2pt', fontWeight: 700, textTransform: 'uppercase', textAlign: 'center',
  padding: '1.8px 1px', border: `1px solid ${C.medium}`, color: C.black, lineHeight: 1.1, whiteSpace: 'nowrap',
};
const thSm = { ...th, fontSize: '6.8pt', lineHeight: 0.95, padding: '1px 0', whiteSpace: 'normal' };
const td = {
  fontSize: '8.5pt', padding: '1.8px 2px', textAlign: 'right', color: C.black, lineHeight: 1.1,
  whiteSpace: 'nowrap', overflow: 'hidden', borderRight: `1px solid ${C.light}`,
};

const LABEL_STYLE = {
  heading: { fontFamily: NARROW, fontWeight: 700, textTransform: 'uppercase', padding: '1.8px 2px 1.8px 3px' },
  subheading: { fontWeight: 700, fontStyle: 'italic', padding: '1.8px 2px 1.8px 8px' },
  item: { padding: '1.8px 2px 1.8px 14px' },
  total: { fontWeight: 700, padding: '1.8px 2px 1.8px 8px' },
  subtotal: { fontWeight: 700, padding: '1.8px 2px 1.8px 8px' },
};

export default function MinesPerformanceTemplate({ data }) {
  const { labels = {}, blocks = [], val_classes = [] } = data || {};

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-end', borderBottom: `1.5px solid ${C.primary}`, paddingBottom: 3, marginBottom: 4 }}>
        <h2 style={{ fontSize: '10pt', fontWeight: 700, color: C.title, margin: 0 }}>{labels.title}</h2>
        <span style={{ fontSize: '8.5pt', fontWeight: 500 }}>Unit: &apos;000 T</span>
      </div>

      {!blocks.length ? (
        <p style={{ fontSize: '10pt', fontWeight: 700, marginTop: 12 }}>No mines data for {labels.month}.</p>
      ) : (
        <table style={{ tableLayout: 'fixed', width: '100%', borderCollapse: 'collapse', border: `1px solid ${C.black}` }}>
          <colgroup>
            <col style={{ width: '3.5%' }} /><col style={{ width: '21%' }} />
            {Array.from({ length: 11 }, (_, i) => <col key={i} style={{ width: '6.86%' }} />)}
          </colgroup>
          <thead style={{ borderBottom: `1px solid ${C.black}` }}>
            <tr>
              <th rowSpan={2} style={th} />
              <th rowSpan={2} style={{ ...th, textAlign: 'left', padding: '1.8px 1px 1.8px 3px' }}>Item</th>
              <th rowSpan={2} style={{ ...th, background: C.planBg }}>{labels.fy}<br />Plan</th>
              <th colSpan={3} style={th}>{labels.month}</th>
              <th rowSpan={2} style={thSm}>{labels.cply}<br />Act.</th>
              <th rowSpan={2} style={{ ...thSm, background: C.grBg }}>%Gr.<br />{labels.cply}</th>
              <th colSpan={3} style={th}>{labels.ytd}</th>
              <th rowSpan={2} style={thSm}>{labels.ytd_cply}<br />Act.</th>
              <th rowSpan={2} style={{ ...thSm, background: C.grBg }}>%Gr.<br />{labels.ytd_cply}</th>
            </tr>
            <tr>
              <th style={th}>Plan</th><th style={{ ...th, background: C.actBg }}>Actual</th><th style={th}>%Ful</th>
              <th style={th}>Plan</th><th style={{ ...th, background: C.actBg }}>Actual</th><th style={th}>%Ful</th>
            </tr>
          </thead>
          {blocks.map((block, bi) => (
            <tbody key={bi} style={{ borderBottom: `1px solid ${C.black}` }}>
              {block.rows.map((row, ri) => {
                const isTotal = row.kind === 'total' || row.kind === 'subtotal';
                // Black rule above section headings and the grand total,
                // but not on the block's first row nor above subtotals.
                const ruleTop = ri > 0 && (row.kind === 'heading' || row.kind === 'total') ? `1px solid ${C.black}` : undefined;
                return (
                  <tr key={ri}>
                    {ri === 0 && (
                      <td rowSpan={block.rows.length} style={{ ...td, textAlign: 'center', verticalAlign: 'middle', padding: '2px 0', borderRight: `1px solid ${C.black}` }}>
                        <div style={{ writingMode: 'vertical-rl', transform: 'rotate(180deg)', margin: '0 auto', fontFamily: NARROW, fontSize: '8.5pt', fontWeight: 700 }}>
                          {block.name}
                        </div>
                      </td>
                    )}
                    <td style={{ ...td, textAlign: 'left', whiteSpace: 'normal', borderTop: ruleTop, background: isTotal ? C.totalBg : undefined, ...LABEL_STYLE[row.kind] }}>
                      {row.label}
                    </td>
                    {(row.display || []).map((v, vi) => (
                      <td key={vi} style={{
                        ...td, borderTop: ruleTop, fontWeight: isTotal ? 700 : undefined,
                        background: isTotal ? C.totalBg : COL_BG[val_classes[vi]],
                      }}>{v}</td>
                    ))}
                  </tr>
                );
              })}
            </tbody>
          ))}
        </table>
      )}
      {blocks.filter((b) => b.note).map((b, i) => (
        <p key={i} style={{ fontSize: '8pt', fontStyle: 'italic', margin: '2px 0 0' }}>{b.note}</p>
      ))}
    </div>
  );
}
