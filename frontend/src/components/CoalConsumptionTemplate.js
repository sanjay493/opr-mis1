'use client';

import React from 'react';

// Mirrors backend/page_templates/coal_consumption.html — see
// page_coal_consumption.py for the data shape. Reproduces Report_format/
// Coal_co2/Coal Format.pdf's OIS-1 table (no computation here), split into
// two stacked portrait tables — (A) Consumption ('000 T) and (B) Blend % —
// per direct instruction, rather than one wide table with gap-columns
// (which needed landscape width to read cleanly).
const BORDER = '#334155';
const TITLE_COLOR = '#333333';
const NOTE_COLOR = '#475569';

const cellStyle = { border: `1px solid ${BORDER}`, padding: '6px 4px', textAlign: 'center', fontSize: '8pt' };
const thStyle = { ...cellStyle, fontWeight: 700 };

function fmt0(v) {
  return v === null || v === undefined ? '—' : Math.round(v).toString();
}
function fmtPct(v) {
  return v === null || v === undefined ? '—' : `${v.toFixed(1)}%`;
}

// Shared by both tables: the Plant (rowspan'd) + Month/Category label cells
// every data row starts with, so the two column sets after them are the
// only thing that differs between (A) and (B).
function LabelCells({ grp, sub, i }) {
  return (
    <>
      {i === 0 && (
        <td style={{ ...cellStyle, fontWeight: 700, verticalAlign: 'middle' }} rowSpan={grp.sub_rows.length}>{grp.plant}</td>
      )}
      <td style={{ ...cellStyle, textAlign: 'left', fontWeight: 600 }}>{sub.label}</td>
    </>
  );
}

function QuantityTable({ groups, qtyCols }) {
  return (
    <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '8pt' }}>
      <thead>
        <tr>
          <th style={thStyle} rowSpan={2} />
          <th style={thStyle} rowSpan={2}>Month / Category</th>
          <th style={thStyle} colSpan={3}>Indigenous Coking Coal</th>
          <th style={thStyle} colSpan={3}>Imported Coking Coal</th>
          <th style={thStyle} rowSpan={2}>Total Coking<br />Coal</th>
          <th style={thStyle} rowSpan={2}>CDI Coal</th>
        </tr>
        <tr>
          {qtyCols.map(([label], i) => <th key={i} style={thStyle}>{label}</th>)}
        </tr>
      </thead>
      <tbody>
        {groups.map((grp, gi) => (
          <React.Fragment key={grp.plant}>
            {grp.sub_rows.map((sub, i) => (
              <tr key={`${grp.plant}-${i}`} style={i === grp.sub_rows.length - 1 ? { borderBottom: `1px solid ${BORDER}` } : undefined}>
                <LabelCells grp={grp} sub={sub} i={i} />
                {qtyCols.map(([label, key], ci) => (
                  <td key={ci} style={cellStyle}>{fmt0(sub.vals[key])}</td>
                ))}
                <td style={cellStyle}>{fmt0(sub.vals.total_coking_coal)}</td>
                <td style={cellStyle}>{fmt0(sub.vals.cdi_coal)}</td>
              </tr>
            ))}
            {gi < groups.length - 1 && (
              <tr><td colSpan={10} style={{ border: 'none', height: 3, padding: 0 }} /></tr>
            )}
          </React.Fragment>
        ))}
      </tbody>
    </table>
  );
}

function BlendTable({ groups, pctCols }) {
  return (
    <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '8pt' }}>
      <thead>
        <tr>
          <th style={thStyle} rowSpan={2} />
          <th style={thStyle} rowSpan={2}>Month / Category</th>
          <th style={thStyle} colSpan={3}>Indigenous Coking Coal</th>
          <th style={thStyle} colSpan={3}>Imported Coking Coal</th>
        </tr>
        <tr>
          {pctCols.map(([label], i) => <th key={i} style={thStyle}>{label}</th>)}
        </tr>
      </thead>
      <tbody>
        {groups.map((grp, gi) => (
          <React.Fragment key={grp.plant}>
            {grp.sub_rows.map((sub, i) => (
              <tr key={`${grp.plant}-${i}`} style={i === grp.sub_rows.length - 1 ? { borderBottom: `1px solid ${BORDER}` } : undefined}>
                <LabelCells grp={grp} sub={sub} i={i} />
                {pctCols.map(([label, key], ci) => (
                  <td key={ci} style={cellStyle}>{fmtPct(sub.vals[key])}</td>
                ))}
              </tr>
            ))}
            {gi < groups.length - 1 && (
              <tr><td colSpan={8} style={{ border: 'none', height: 3, padding: 0 }} /></tr>
            )}
          </React.Fragment>
        ))}
      </tbody>
    </table>
  );
}

export default function CoalConsumptionTemplate({ data }) {
  const { title = '', qty_cols = [], pct_cols = [], groups = [] } = data || {};

  return (
    <div style={{ fontFamily: 'inherit' }}>
      <div style={{ textAlign: 'center', fontWeight: 700, fontSize: '11pt', textDecoration: 'underline', marginBottom: 6, color: TITLE_COLOR }}>
        {title}
      </div>

      <div style={{ fontWeight: 700, fontSize: '9.5pt', margin: '0 0 4px' }}>(A) Consumption (&apos;000 T)</div>
      <QuantityTable groups={groups} qtyCols={qty_cols} />

      <div style={{ fontWeight: 700, fontSize: '9.5pt', margin: '10px 0 4px' }}>(B) Blend %</div>
      <BlendTable groups={groups} pctCols={pct_cols} />

      <div style={{ fontSize: '7.5pt', marginTop: 6, color: NOTE_COLOR }}>
        Note: The above information is based on the reports from plants/CCSO
      </div>
    </div>
  );
}
