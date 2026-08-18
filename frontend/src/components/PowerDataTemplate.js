'use client';

import React from 'react';

// Mirrors backend/page_templates/power_data.html — see page_power_data.py
// for the data shape. Reproduces Report_format/Power-OIS/*.xlsx's own
// full-FY grid (all 12 months x all plants) as ONE dense portrait table:
// the header (group row + sub-header row) prints once, and each plant's 13
// rows (12 months + Cum.) sit under a single rowSpan'd, vertical-text plant
// name cell instead of repeating the plant name/header per block.
const BORDER = '#334155';
const TITLE_COLOR = '#333333';

const GROUP_BG = {
  plan: '#eef2ff',
  actual: '#ecfdf5',
  grid: '#fff7ed',
  last_year: '#f5f5f4',
};
const GROUP_HEAD_BG = {
  plan: '#c7d2fe',
  actual: '#a7f3d0',
  grid: '#fed7aa',
  last_year: '#d6d3d1',
};

// [item_key, abbreviated column header] — order matches the source
// workbook's own left-to-right column order.
const PLAN_COLS = [
  ['own', 'Own'], ['new_pbs', 'N.P&BS'], ['jv_pp2', 'JV2'], ['drawal_jv_pp3', 'D.PP3'], ['total', 'Total'],
];
const ACTUAL_COLS = PLAN_COLS;
const GRID_COLS = [
  ['wheeling_px', 'Whl'], ['purchase_px', 'Pur'], ['renewable_gdam', 'RE'],
  ['drawal_grid', 'D.Gr'], ['export_grid', 'Exp'], ['total_power_consump', 'TPC'],
  ['decarbon_nos', 'D.No'], ['decarbon_hrs', 'D.Hr'], ['specific_power_cons', 'SPC'],
];
const LAST_YEAR_COLS = [
  ['own_cpp', 'Own'], ['jv_cpp', 'JV'], ['drawal_pp3', 'D.PP3'], ['total_gen', 'T.Gen'], ['total_power_consump', 'TPC'],
];

const GROUPS = [
  { key: 'plan', label: 'PLAN (MW)', cols: PLAN_COLS },
  { key: 'actual', label: 'ACTUAL (MW)', cols: ACTUAL_COLS },
  { key: 'grid', label: 'GRID & CONSUMPTION', cols: GRID_COLS },
  { key: 'last_year', label: 'LAST YEAR (MW)', cols: LAST_YEAR_COLS },
];

const ROWS_PER_PLANT = 13; // 12 months + Cum.

// Horizontal rules removed within each plant's own 13-row block — every
// cell only carries its own LEFT border (column separators), and the
// table's own outer border plus each header/Cum. row's explicit
// borderBottom below are the only horizontal lines left, marking section
// boundaries (header/body, one plant's block from the next) without a
// rule under every single month row.
const th = {
  borderLeft: `1px solid ${BORDER}`, padding: '0px 1px', textAlign: 'center',
  fontSize: '5.5pt', fontWeight: 700, whiteSpace: 'nowrap', lineHeight: 1.15,
};
const td = {
  borderLeft: `1px solid ${BORDER}`, padding: '0px 1px', textAlign: 'right',
  fontSize: '5.5pt', fontVariantNumeric: 'tabular-nums', lineHeight: 1.15,
};
const plantCellStyle = {
  border: `1px solid ${BORDER}`, textAlign: 'center', verticalAlign: 'middle',
  fontWeight: 700, fontSize: '6.5pt', background: '#e2e8f0',
  writingMode: 'vertical-rl', transform: 'rotate(180deg)', padding: '2px 1px',
};

function fmt2(v) {
  return v === null || v === undefined ? '' : v.toFixed(2);
}

export default function PowerDataTemplate({ data }) {
  const { title = '', plants = [] } = data || {};

  return (
    <div style={{ fontFamily: 'inherit' }}>
      <div style={{ textAlign: 'center', fontWeight: 700, fontSize: '11pt', textDecoration: 'underline', marginBottom: 4, color: TITLE_COLOR }}>
        {title}
      </div>
      <table style={{ width: '100%', tableLayout: 'fixed', borderCollapse: 'collapse', border: `1px solid ${BORDER}` }}>
        <colgroup>
          <col style={{ width: 14 }} />
          <col style={{ width: 22 }} />
          {GROUPS.flatMap((g) => g.cols.map((_, i) => <col key={`${g.key}-${i}`} style={{ width: 19 }} />))}
        </colgroup>
        <thead>
          <tr>
            <th style={{ ...th, background: '#e2e8f0' }} rowSpan={2}>Plant</th>
            <th style={{ ...th, background: '#e2e8f0' }} rowSpan={2}>Mon</th>
            {GROUPS.map((g) => (
              <th key={g.key} style={{ ...th, background: GROUP_HEAD_BG[g.key] }} colSpan={g.cols.length}>{g.label}</th>
            ))}
          </tr>
          <tr>
            {GROUPS.flatMap((g) => g.cols.map(([key, label]) => (
              <th key={`${g.key}-${key}`} style={{ ...th, background: GROUP_BG[g.key], borderBottom: `1px solid ${BORDER}` }}>{label}</th>
            )))}
          </tr>
        </thead>
        <tbody>
          {plants.map((plant) => (
            <React.Fragment key={plant.name}>
              {plant.rows.map((row, i) => (
                <tr key={row.month}>
                  {i === 0 && (
                    <td style={plantCellStyle} rowSpan={ROWS_PER_PLANT}>{plant.name}</td>
                  )}
                  <td style={{ ...td, textAlign: 'left', fontWeight: 600, background: '#f8fafc' }}>{row.month}</td>
                  {GROUPS.flatMap((g) => g.cols.map(([key]) => (
                    <td key={`${g.key}-${key}`} style={{ ...td, background: row.has_data ? undefined : '#fafafa' }}>
                      {fmt2(row[g.key]?.[key])}
                    </td>
                  )))}
                </tr>
              ))}
              <tr>
                <td style={{ ...td, textAlign: 'left', fontWeight: 700, background: '#e2e8f0', borderBottom: `1px solid ${BORDER}` }}>Cum.</td>
                {GROUPS.flatMap((g) => g.cols.map(([key]) => (
                  <td key={`cum-${g.key}-${key}`} style={{ ...td, fontWeight: 700, background: '#e2e8f0', borderBottom: `1px solid ${BORDER}` }}>
                    {fmt2(plant.cum[g.key]?.[key])}
                  </td>
                )))}
              </tr>
            </React.Fragment>
          ))}
        </tbody>
      </table>
    </div>
  );
}
