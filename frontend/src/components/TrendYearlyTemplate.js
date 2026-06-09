'use client';
import React from 'react';

// Header cell styles
const HDR  = { fontSize: '7pt',   padding: '3px 2px', background: '#1e3a5f', color: '#fff',    textAlign: 'center', border: '0.4px solid #334155', whiteSpace: 'nowrap', fontWeight: '700' };
const QHDR = { ...HDR, background: '#2d4f7f' };
const THDR = { ...HDR, background: '#1a3050' };

// Data cell styles
const CELL  = { fontSize: '9pt',  padding: '2px 3px',  textAlign: 'right',  border: '0.3px solid #e2e8f0' };
const QCELL = { ...CELL, background: '#f0f5ff', fontWeight: '600' };
const TCELL = { ...CELL, background: '#e8f0fb', fontWeight: '700' };
const YCELL = { ...CELL, fontSize: '8pt', textAlign: 'left', paddingLeft: '3px', whiteSpace: 'nowrap', fontWeight: '400' };

// Colours for aggregate / special rows
const PLAN_BG = '#dbeafe';   // light blue  — plan row
const SAIL_BG = '#dcfce7';   // light green — SAIL / aggregate row
const FP_BG   = '#fef9c3';   // light yellow — 5 Plants aggregate

const AGGREGATES = new Set(['SAIL', '5 Plants']);

function rowColors(row) {
  if (row.is_plan)             return { bg: PLAN_BG, fw: '700' };
  if (row.plant === 'SAIL')    return { bg: SAIL_BG, fw: '700' };
  if (row.plant === '5 Plants') return { bg: FP_BG,  fw: '700' };
  return { bg: undefined, fw: '400' };
}

function TrendTable({ rows, item_display, unit }) {
  return (
    <div style={{ width: '100%' }}>
      <div style={{
        display: 'flex', justifyContent: 'space-between', alignItems: 'flex-end',
        borderBottom: '2px solid #0f172a', paddingBottom: '4px', marginBottom: '6px',
      }}>
        <h2 style={{ fontSize: '10pt', fontWeight: '800', color: '#060177', margin: 0, textTransform: 'uppercase' }}>
          MONTH-WISE PRODUCTION TREND : {item_display}
        </h2>
        <span style={{ fontSize: '8pt', fontWeight: '600', color: '#475569' }}>Unit: {unit}</span>
      </div>

      {/* Table */}
      <table style={{ width: '100%', borderCollapse: 'collapse', tableLayout: 'fixed' }}>
        <colgroup>
          <col style={{ width: '4.5%' }} />
          <col style={{ width: '10%' }} />
          <col style={{ width: '4.5%' }} /><col style={{ width: '4.5%' }} /><col style={{ width: '4.5%' }} /><col style={{ width: '5%' }} />
          <col style={{ width: '4.5%' }} /><col style={{ width: '4.5%' }} /><col style={{ width: '4.5%' }} /><col style={{ width: '5%' }} />
          <col style={{ width: '4.5%' }} /><col style={{ width: '4.5%' }} /><col style={{ width: '4.5%' }} /><col style={{ width: '5%' }} />
          <col style={{ width: '4.5%' }} /><col style={{ width: '4.5%' }} /><col style={{ width: '4.5%' }} /><col style={{ width: '5%' }} />
          <col style={{ width: '5.5%' }} />
        </colgroup>

        <thead>
          <tr>
            <th style={HDR}>Plant</th>
            <th style={HDR}>Year</th>
            <th style={HDR}>Apr</th><th style={HDR}>May</th><th style={HDR}>Jun</th>
            <th style={QHDR}>Q1</th>
            <th style={HDR}>Jul</th><th style={HDR}>Aug</th><th style={HDR}>Sep</th>
            <th style={QHDR}>Q2</th>
            <th style={HDR}>Oct</th><th style={HDR}>Nov</th><th style={HDR}>Dec</th>
            <th style={QHDR}>Q3</th>
            <th style={HDR}>Jan</th><th style={HDR}>Feb</th><th style={HDR}>Mar</th>
            <th style={QHDR}>Q4</th>
            <th style={THDR}>Total</th>
          </tr>
        </thead>

        <tbody>
          {rows.map((row, idx) => {
            const v = row.values || [];
            const { bg, fw } = rowColors(row);
            const isAggregate = AGGREGATES.has(row.plant);
            const topBorder = row.is_first_in_plant ? '2px solid #64748b' : undefined;

            const plantCellStyle = {
              verticalAlign: 'middle',
              fontWeight: '700',
              textAlign: 'center',
              fontSize: isAggregate ? '8pt' : '9pt',
              background: isAggregate ? (row.plant === 'SAIL' ? '#bbf7d0' : '#fef08a') : '#e8edf3',
              color: '#1e3a5f',
              border: '0.5px solid #94a3b8',
              padding: '2px 1px',
              lineHeight: '1.2',
            };

            return (
              <tr key={idx} style={{ background: bg, fontWeight: fw, borderTop: topBorder }}>
                {row.is_first_in_plant && (
                  <td rowSpan={row.plant_row_count} style={plantCellStyle}>
                    {row.plant}
                  </td>
                )}
                <td style={{ ...YCELL, fontWeight: row.is_plan ? '700' : '400' }}>{row.year_label}</td>
                <td style={CELL}>{v[0]}</td>
                <td style={CELL}>{v[1]}</td>
                <td style={CELL}>{v[2]}</td>
                <td style={QCELL}>{v[3]}</td>
                <td style={CELL}>{v[4]}</td>
                <td style={CELL}>{v[5]}</td>
                <td style={CELL}>{v[6]}</td>
                <td style={QCELL}>{v[7]}</td>
                <td style={CELL}>{v[8]}</td>
                <td style={CELL}>{v[9]}</td>
                <td style={CELL}>{v[10]}</td>
                <td style={QCELL}>{v[11]}</td>
                <td style={CELL}>{v[12]}</td>
                <td style={CELL}>{v[13]}</td>
                <td style={CELL}>{v[14]}</td>
                <td style={QCELL}>{v[15]}</td>
                <td style={TCELL}>{v[16]}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

export default function TrendYearlyTemplate({ data }) {
  const { rows = [], item_display = '', unit = '', items = [] } = data || {};

  // Combined page (e.g. Pig Iron + Finished Steel): render one table per sub-item
  if (items.length > 0) {
    return (
      <div style={{ width: '100%' }}>
        {items.map((item, idx) => (
          <div key={idx} style={{ marginBottom: idx < items.length - 1 ? '18px' : 0 }}>
            {idx > 0 && <hr style={{ border: 'none', borderTop: '1.5px solid #0f172a', margin: '10px 0 8px 0' }} />}
            <TrendTable rows={item.rows || []} item_display={item.item_display || ''} unit={item.unit || ''} />
          </div>
        ))}
      </div>
    );
  }

  // Single-item page (pages 7-10, 12)
  return <TrendTable rows={rows} item_display={item_display} unit={unit} />;
}
