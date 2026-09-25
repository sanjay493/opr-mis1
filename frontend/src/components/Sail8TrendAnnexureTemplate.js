'use client';

import React from 'react';

// Mirrors backend/page_templates/sail8_trend_annexure.html — Annexure-4,
// SAIL (8 Plants) Hot Metal / Crude Steel / Pig Iron / Saleable Steel
// (with Semi Finished / Finished Steel components, indented + dash-
// prefixed), two stacked FY-wise tables (top: FY2017-18 onward, bottom:
// the fixed FY2007-08..FY2016-17 decade).

const BORDER = '0.5pt solid #5f6368';
const NAVY = '#1e3a8a';
const SECONDARY = '#5f6368';

function TrendTable({ table }) {
  const { years = [], rows = [] } = table || {};
  return (
    <div>
      <div style={{ fontWeight: 700, fontSize: '10.5pt', color: NAVY, margin: '10px 0 4px 0' }}>
        FY {years[0]} to {years[years.length - 1]}
      </div>
      <table style={{ fontSize: '9.5pt', borderCollapse: 'collapse', width: '100%', lineHeight: 1.2 }}>
        <thead>
          <tr>
            <th style={{ border: BORDER, padding: '3px 5px', fontWeight: 700, textAlign: 'center' }}>Item</th>
            {years.map((y) => (
              <th key={y} style={{ border: BORDER, padding: '3px 5px', fontWeight: 700, textAlign: 'center' }}>{y}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.label}>
              <td style={{
                border: BORDER, padding: '3px 5px', textAlign: 'left',
                fontWeight: row.indent ? 400 : 600,
                color: row.indent ? SECONDARY : undefined,
                paddingLeft: row.indent ? 16 : 5,
              }}>
                {row.indent ? `- ${row.label}` : row.label}
              </td>
              {row.values.map((v, i) => (
                <td key={i} style={{
                  border: BORDER, padding: '3px 5px', textAlign: 'right',
                  whiteSpace: 'nowrap', fontVariantNumeric: 'tabular-nums',
                }}>
                  {v}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export default function Sail8TrendAnnexureTemplate({ data }) {
  const { unit, top_table: topTable, bottom_table: bottomTable } = data || {};

  return (
    <div>
      <div style={{ textAlign: 'center', fontWeight: 700, fontSize: '15pt', color: NAVY, textDecoration: 'underline', marginBottom: 2 }}>
        SAIL (8 Plants) — Production Trend
      </div>
      <div style={{ textAlign: 'center', fontWeight: 600, fontSize: '10.5pt', color: SECONDARY, marginBottom: 14 }}>
        Hot Metal / Crude Steel / Pig Iron / Saleable Steel (of which: Semi Finished &amp; Finished Steel) — FY-wise, {unit}
      </div>

      <TrendTable table={topTable} />
      <TrendTable table={bottomTable} />
    </div>
  );
}
