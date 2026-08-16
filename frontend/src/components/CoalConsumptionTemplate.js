'use client';

import React from 'react';

// Mirrors backend/page_templates/coal_consumption.html — see
// page_coal_consumption.py for the data shape. Reproduces Report_format/
// Coal_co2/Coal Format.pdf's OIS-1 table verbatim (no computation here).
const BORDER = '#334155';
const TITLE_COLOR = '#333333';
const NOTE_COLOR = '#475569';

const cellStyle = { border: `1px solid ${BORDER}`, padding: '2px 5px', textAlign: 'center', fontSize: '8pt' };
const thStyle = { ...cellStyle, fontWeight: 700 };
// Blank divider cells either side of CDI Coal — no border at all, so they
// read as pure whitespace framed by their neighbours' own borders rather
// than an extra ruled column. Width differs (thinner before CDI, since
// it's still "inside" the quantity block; wider after, the real divider
// ahead of Blend%).
const gapCellThin = { border: 'none', padding: 0, width: '1%' };
const gapCellWide = { border: 'none', padding: 0, width: '2%' };

function fmt0(v) {
  return v === null || v === undefined ? '—' : Math.round(v).toString();
}
function fmtPct(v) {
  return v === null || v === undefined ? '—' : `${v.toFixed(1)}%`;
}

export default function CoalConsumptionTemplate({ data }) {
  const { title = '', qty_cols = [], pct_cols = [], groups = [] } = data || {};
  const totalCols = 2 + qty_cols.length + pct_cols.length + 4;

  return (
    <div style={{ fontFamily: 'inherit' }}>
      <div style={{ textAlign: 'center', fontWeight: 700, fontSize: '11pt', textDecoration: 'underline', marginBottom: 6, color: TITLE_COLOR }}>
        {title}
      </div>

      <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '8pt' }}>
        <thead>
          <tr>
            <td colSpan={2} style={{ border: 'none' }} />
            <td colSpan={qty_cols.length + 3} style={{ border: 'none', fontSize: '7.5pt', fontStyle: 'italic', textDecoration: 'underline', textAlign: 'right', padding: '0 5px 2px' }}>Quantity in &apos;000 T</td>
            <td style={gapCellWide} />
            <td colSpan={pct_cols.length} style={{ border: 'none', fontSize: '7.5pt', fontStyle: 'italic', textDecoration: 'underline', textAlign: 'right', padding: '0 5px 2px' }}>Blend %</td>
          </tr>
          <tr>
            <th style={thStyle} rowSpan={2} />
            <th style={thStyle} rowSpan={2}>Month / Category</th>
            <th style={thStyle} colSpan={3}>Indigenous Coking Coal</th>
            <th style={thStyle} colSpan={3}>Imported Coking Coal</th>
            <th style={thStyle} rowSpan={2}>Total Coking<br />Coal</th>
            <th style={{ ...thStyle, ...gapCellThin }} rowSpan={2} />
            <th style={thStyle} rowSpan={2}>CDI Coal</th>
            <th style={{ ...thStyle, ...gapCellWide }} rowSpan={2} />
            <th style={thStyle} colSpan={3}>Indigenous Coking Coal</th>
            <th style={thStyle} colSpan={3}>Imported Coking Coal</th>
          </tr>
          <tr>
            {qty_cols.map(([label], i) => <th key={`q${i}`} style={thStyle}>{label}</th>)}
            {pct_cols.map(([label], i) => <th key={`p${i}`} style={thStyle}>{label}</th>)}
          </tr>
        </thead>
        <tbody>
          {groups.map((grp, gi) => (
            <React.Fragment key={grp.plant}>
              {grp.sub_rows.map((sub, i) => (
                <tr key={`${grp.plant}-${i}`} style={i === grp.sub_rows.length - 1 ? { borderBottom: `1px solid ${BORDER}` } : undefined}>
                  {i === 0 && (
                    <td style={{ ...cellStyle, fontWeight: 700, verticalAlign: 'middle' }} rowSpan={grp.sub_rows.length}>{grp.plant}</td>
                  )}
                  <td style={{ ...cellStyle, textAlign: 'left', fontWeight: 600 }}>{sub.label}</td>
                  {qty_cols.map(([label, key], ci) => (
                    <td key={ci} style={cellStyle}>{fmt0(sub.vals[key])}</td>
                  ))}
                  <td style={cellStyle}>{fmt0(sub.vals.total_coking_coal)}</td>
                  <td style={gapCellThin} />
                  <td style={cellStyle}>{fmt0(sub.vals.cdi_coal)}</td>
                  <td style={gapCellWide} />
                  {pct_cols.map(([label, key], ci) => (
                    <td key={ci} style={cellStyle}>{fmtPct(sub.vals[key])}</td>
                  ))}
                </tr>
              ))}
              {gi < groups.length - 1 && (
                <tr>
                  <td colSpan={totalCols} style={{ border: 'none', height: 3, padding: 0 }} />
                </tr>
              )}
            </React.Fragment>
          ))}
        </tbody>
      </table>

      <div style={{ fontSize: '7.5pt', marginTop: 6, color: NOTE_COLOR }}>
        Note: The above information is based on the reports from plants/CCSO
      </div>
    </div>
  );
}
