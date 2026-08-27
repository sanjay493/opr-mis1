'use client';
import React from 'react';

// Header cell styles
const HDR  = { fontSize: 'var(--report-font-size)', padding: '3px 2px', background: '#1e3a5f', color: '#fff',    textAlign: 'center', border: '0.4px solid #334155', whiteSpace: 'nowrap', fontWeight: '700' };
const QHDR = { ...HDR, background: '#2d4f7f' };
const HHDR = { ...HDR, background: '#68a87e' };
const THDR = { ...HDR, background: '#1a3050' };

// Data cell styles
const CELL  = { fontSize: 'var(--report-font-size)', padding: '2px 3px',  textAlign: 'right',  border: '0.3px solid #e2e8f0' };
// Quarter columns (blue) and the annual Total column (violet) carry
// deliberately different hues so they don't read as one band — keep in
// sync with colors_config.json highlight_qtr_col_bg / highlight_total_col_bg.
const QCELL = { ...CELL, background: '#dce8fa', fontWeight: '600' };
const TCELL = { ...CELL, background: '#eae1f5', fontWeight: '700' };
const HHCELL = { ...CELL, background: '#d1fae5', fontWeight: '700' };
const YCELL = { ...CELL, fontSize: 'var(--report-font-size)', textAlign: 'left', paddingLeft: '3px', whiteSpace: 'nowrap', fontWeight: '400' };

// Colours for aggregate / special rows
const PLAN_BG = '#dbeafe';   // light blue  — plan row
const SAIL_BG = '#dcfce7';   // light green — SAIL / aggregate row
const FP_BG   = '#fef9c3';   // light yellow — 5 Plants aggregate
const HH_BG   = '#d1fae5';   // light teal — Half Yearly aggregate

// Cell highlight for the record flags — keep these in sync with
// colors_config.json's highlight_best_ever_bg and
// highlight_best_month_border_light (the PDF path reads that file; this
// preview can't, so the hex is duplicated here same as PLAN_BG/SAIL_BG/
// FP_BG above). 'best_ever' (all-time record, month/quarter/annual) is
// background fill only — no border, so it doesn't fight for attention with
// the plan/SAIL/5 Plants row backgrounds it can land on top of. 'best_month'
// (this column's own historical record, but not the single all-time best)
// is the weaker signal and gets a light thin border with no fill.
const BEST_EVER_BG  = '#fde68a';
const LIGHT_BORDER  = '#94a3b8';

function bestFlagStyle(flag) {
  if (flag === 'best_ever')  return { background: BEST_EVER_BG, fontWeight: '700' };
  if (flag === 'best_month') return { border: `1px solid ${LIGHT_BORDER}`, fontWeight: '700' };
  return null;
}

const AGGREGATES = new Set(['SAIL', '5 Plants']);

// One fixed background per individual plant's stacked-letter label column,
// same as pages 7-13's colors_config.json plant_color_* entries (kept in
// sync manually — this preview can't read that file, same reason PLAN_BG/
// SAIL_BG/FP_BG above are duplicated hex too). SAIL/'5 Plants' use their own
// aggregate colors in rowColors below instead.
// Distinct, medium-saturation hue per plant so consecutive plant blocks
// down the label column clearly contrast with each other (and with the
// white Year column beside them). Keep in sync with colors_config.json
// plant_color_*.
const PLANT_COLORS = {
  BSP: '#a9c5ec', DSP: '#f1d0a1', RSP: '#cbb5e6', BSL: '#f2b1c7',
  ISP: '#9fd3e0', ASP: '#b9dd9c', SSP: '#e8bb9c', VI: '#afbdd0',
};

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
        <h2 className="page7-13-heading">
          10 Years Month Wise Production : {item_display}
        </h2>
        <span className="page7-13-unit">Unit: {unit}</span>
      </div>

      {/* Table */}
      <table style={{ width: '100%', borderCollapse: 'collapse', tableLayout: 'fixed' }}>
        <colgroup>
          <col style={{ width: '1.8%' }} />
          <col style={{ width: '5.5%' }} />
          <col style={{ width: '4.6%' }} /><col style={{ width: '4.6%' }} /><col style={{ width: '4.6%' }} /><col style={{ width: '5.1%' }} />
          <col style={{ width: '4.6%' }} /><col style={{ width: '4.6%' }} /><col style={{ width: '4.6%' }} /><col style={{ width: '5.1%' }} /><col style={{ width: '5.6%' }} />
          <col style={{ width: '4.6%' }} /><col style={{ width: '4.6%' }} /><col style={{ width: '4.6%' }} /><col style={{ width: '5.1%' }} />
          <col style={{ width: '4.6%' }} /><col style={{ width: '4.6%' }} /><col style={{ width: '4.6%' }} /><col style={{ width: '5.1%' }} /><col style={{ width: '5.6%' }} />
          <col style={{ width: '5.9%' }} />
        </colgroup>

        <thead>
          <tr>
            <th style={HDR}></th>
            <th style={HDR}>Year</th>
            <th style={HDR}>Apr</th><th style={HDR}>May</th><th style={HDR}>Jun</th>
            <th style={QHDR}>Q1</th>
            <th style={HDR}>Jul</th><th style={HDR}>Aug</th><th style={HDR}>Sep</th>
            <th style={QHDR}>Q2</th>
            <th style={HHDR}>H1</th>
            <th style={HDR}>Oct</th><th style={HDR}>Nov</th><th style={HDR}>Dec</th>
            <th style={QHDR}>Q3</th>
            <th style={HDR}>Jan</th><th style={HDR}>Feb</th><th style={HDR}>Mar</th>
            <th style={QHDR}>Q4</th>
            <th style={HHDR}>H2</th>
            <th style={THDR}>Total</th>
          </tr>
        </thead>

        <tbody>
          {rows.map((row, idx) => {
            const v = row.values || [];
            const cf = row.cell_flags || [];
            const cellStyle  = i => ({ ...CELL,  ...bestFlagStyle(cf[i]) });
            const qcellStyle = i => ({ ...QCELL, ...bestFlagStyle(cf[i]) });
            const hcellStyle = i => ({ ...HHCELL, ...bestFlagStyle(cf[i]) }); 
            const tcellStyle = i => ({ ...TCELL, ...bestFlagStyle(cf[i]) });
            const { bg, fw } = rowColors(row);
            const isAggregate = AGGREGATES.has(row.plant);
            const topBorder = row.is_first_in_plant ? '2px solid #64748b' : undefined;

            const plantChars = row.plant.replace(/ /g, '');
            // Font tier is driven by how many stacked letters must fit
            // within this group's own row count, not by the plant name's
            // length alone — this preview never splits across pages, so a
            // long label like "5 Plants" (7 letters) stays full-size as
            // long as its group actually has that many rows (matches
            // trend_section.html's PDF-side logic, where a real page
            // split can leave a segment too short for the label).
            const nRows = row.plant_row_count || 1;
            const tight = plantChars.length > nRows + 2;
            const compact = !tight && plantChars.length > nRows;
            const plantCellStyle = {
              verticalAlign: 'middle',
              fontWeight: '700',
              textAlign: 'center',
              fontSize: tight ? '6pt' : (compact ? '6.5pt' : '8.3pt'),
              background: isAggregate
                ? (row.plant === 'SAIL' ? '#bbf7d0' : '#fef08a')
                : (PLANT_COLORS[row.plant] || '#d1d5db'),
              color: '#1e3a5f',
              border: '0.5px solid #94a3b8',
              padding: '2px 1px',
              lineHeight: tight ? '1.05' : '1.15',
            };

            return (
              <tr key={idx} style={{ background: bg, fontWeight: fw, borderTop: topBorder }}>
                {row.rowspan_start && (
                  <td rowSpan={row.plant_row_count} style={plantCellStyle}>
                    {plantChars.split('').map((ch, i) => (
                      <React.Fragment key={i}>
                        {ch}
                        {i < plantChars.length - 1 && <br />}
                      </React.Fragment>
                    ))}
                  </td>
                )}
                <td style={{
                  ...YCELL,
                  fontWeight: row.is_plan ? '700' : '400',
                  // "P 26-27" runs 2 characters longer than every other
                  // row's "26-27" — column-fit fix, scoped to plan rows
                  // only, matching trend_section.html's tr.plan-row rule.
                  ...(row.is_plan ? { paddingLeft: 0, paddingRight: 0, fontSize: '8pt' } : null),
                }}>{row.year_label}</td>
                <td style={cellStyle(0)}>{v[0]}</td>
                <td style={cellStyle(1)}>{v[1]}</td>
                <td style={cellStyle(2)}>{v[2]}</td>
                <td style={qcellStyle(3)}>{v[3]}</td>
                <td style={cellStyle(4)}>{v[4]}</td>
                <td style={cellStyle(5)}>{v[5]}</td>
                <td style={cellStyle(6)}>{v[6]}</td>
                <td style={qcellStyle(7)}>{v[7]}</td>
                <td style={hcellStyle(8)}>{v[8]}</td>
                <td style={cellStyle(9)}>{v[9]}</td>
                <td style={cellStyle(10)}>{v[10]}</td>
                <td style={cellStyle(11)}>{v[11]}</td>
                <td style={qcellStyle(12)}>{v[12]}</td>
                <td style={cellStyle(13)}>{v[13]}</td>
                <td style={cellStyle(14)}>{v[14]}</td>
                <td style={cellStyle(15)}>{v[15]}</td>
                <td style={qcellStyle(16)}>{v[16]}</td>
                <td style={hcellStyle(17)}>{v[17]}</td>
                <td style={tcellStyle(18)}>{v[18]}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
      <div style={{ fontSize: 11, color: '#475569', marginTop: 4 }}>
        <span style={{ display: 'inline-block', width: 8, height: 8, marginRight: 3, verticalAlign: 'middle', background: BEST_EVER_BG }} />
        Best Ever (month / quarter / Half yearly / annual record)
        &nbsp;&nbsp;
        <span style={{ display: 'inline-block', width: 8, height: 8, marginRight: 3, verticalAlign: 'middle', background: 'transparent', border: `1px solid ${LIGHT_BORDER}` }} />
        Best for that Calendar Month/Quarter/Half Year (e.g. best April, best Q3)
      </div>
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
