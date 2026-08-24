'use client';

import React from 'react';

// Mirrors backend/page_templates/cost_trend_macro.html — shared renderer for
// one Cost Trend product (title + Total/Variable/Fixed blocks), one page
// each for Hot Metal/Crude Steel/Saleable Steel. Column widths are computed
// from page.periods.length so HM/CS/SS always share identical proportions
// for the same report month.
const C = {
  textSecondary: '#475569',
  textHeadingDark: '#1e293b',
  textBlack: '#000000',
  borderDarkest: '#1e293b',
  borderDark: '#334155',
  borderMedium: '#94a3b8',
  tableHeaderBg: 'transparent',
  highlightCumulativeBg: '#d1fae5',
  highlightTargetBandBg: '#fef9c3',
  highlightBoldRowBg: '#eef2f6',
  highlightBoxBg: '#f8fafc',
};

function fmtCell(v) {
  return v === null || v === undefined || v === '' ? '—' : v;
}

export function CostTrendProduct({ page }) {
  if (!page) return null;
  const periods = page.periods || [];
  const plantPct = 9;
  const periodPct = periods.length ? (100 - plantPct) / periods.length : 0;

  return (
    <div>
      <div style={{ textAlign: 'center', fontWeight: 700, fontSize: '13pt', marginBottom: 3 }}>
        {page.title}
        <span style={{ fontWeight: 500, fontStyle: 'italic', fontSize: '9pt', color: C.textSecondary }}>
          &nbsp;(Unit: {page.unit})
        </span>
      </div>
      {(page.blocks || []).map((block, bi) => (
        <div key={bi}>
          <div style={{ fontWeight: 700, fontSize: '10pt', color: C.textHeadingDark, margin: '10px 0 4px' }}>
            {block.label}
          </div>
          <table style={{ borderCollapse: 'collapse', border: `1px solid ${C.borderDarkest}`, fontSize: '8.5pt', width: '100%', marginBottom: 3, tableLayout: 'fixed' }}>
            <colgroup>
              <col style={{ width: `${plantPct}%` }} />
              {periods.map((p, i) => <col key={i} style={{ width: `${periodPct}%` }} />)}
            </colgroup>
            <thead>
              <tr style={{ background: C.tableHeaderBg, color: C.textBlack }}>
                <th style={{ padding: '4px 7px', border: `1px solid ${C.borderDark}`, textAlign: 'left', verticalAlign: 'middle' }}>Plant</th>
                {periods.map((p, i) => (
                  <th key={i} style={{
                    padding: '4px 7px', border: `1px solid ${C.borderDark}`, verticalAlign: 'middle',
                    background: p.kind === 'till' ? C.highlightCumulativeBg : p.kind === 'annual' ? C.highlightTargetBandBg : undefined,
                  }}>
                    {p.label}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {(block.rows || []).map((row, ri) => (
                <tr key={ri} style={{
                  fontWeight: row.plant === 'SAIL 5 ISPs' ? 700 : undefined,
                  background: row.plant === 'SAIL 5 ISPs' ? C.highlightBoldRowBg : (ri % 2 === 1 ? C.highlightBoxBg : undefined),
                }}>
                  <td style={{ padding: '3px 6px', border: `1px solid ${C.borderMedium}`, textAlign: 'left', fontWeight: 600, verticalAlign: 'middle' }}>
                    {row.plant}
                  </td>
                  {periods.map((p, i) => (
                    <td key={i} style={{
                      padding: '3px 6px', border: `1px solid ${C.borderMedium}`, textAlign: 'right', verticalAlign: 'middle',
                      background: p.kind === 'till' ? `${C.highlightCumulativeBg}66` : p.kind === 'annual' ? `${C.highlightTargetBandBg}66` : undefined,
                    }}>
                      {fmtCell(row.cells?.[p.key])}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ))}
    </div>
  );
}

export default function CostTrendTemplate({ data }) {
  return (
    <div style={{ padding: 6, fontFamily: 'Arial, sans-serif', fontSize: '8pt' }}>
      <CostTrendProduct page={data} />
      <div style={{ fontSize: '8pt', fontStyle: 'italic', color: C.textSecondary, marginTop: 6 }}>
        (-) indicates decrease in cost
      </div>
    </div>
  );
}
