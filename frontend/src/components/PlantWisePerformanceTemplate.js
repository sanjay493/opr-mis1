'use client';
import React from 'react';

const COL_W = {
  plant:   '4%',
  item:    '20%',
  annual:  '8%',
  mPlan:   '5.5%',
  mAct:    '5.5%',
  mPct:    '5%',
  cplyAct: '6%',
  mGr:     '6%',
  ytdPlan: '6%',
  ytdAct:  '6%',
  ytdPct:  '5%',
  ytdCply: '6%',
  ytdGr:   '6%',
};

const TH = { padding: '2px 3px', fontSize: '11pt', verticalAlign: 'middle', lineHeight: '1.2' };
const TD = { padding: '1px 3px', fontSize: '11pt', lineHeight: '1.2', overflow: 'hidden' };
const INPUT = {
  width: '100%', minWidth: 0, padding: '0 1px',
  background: 'transparent', border: 'none',
  color: 'black', fontSize: 'inherit', textAlign: 'right',
};

const PLANT_BG = {
  SAIL: '#dbeafe', BSP: '#fef9c3', DSP: '#dcfce7',
  RSP: '#fce7f3', BSL: '#ede9fe', ISP: '#ffedd5',
  ASP: '#f1f5f9', SSP: '#f1f5f9', VISP: '#f1f5f9',
};

const BOLD_PLANTS = new Set(['SAIL', 'BSP', 'DSP', 'RSP', 'BSL', 'ISP']);

export default function PlantWisePerformanceTemplate({ data, onCellChange, selectedMonth }) {
  const { rows = [] } = data || {};

  const [mName, yStr] = selectedMonth ? selectedMonth.split(' ') : ['November', '2025'];
  const shortM = mName ? mName.substring(0, 3) : 'Nov';
  const shortY = yStr  ? yStr.substring(2)      : '25';
  const prevY  = yStr  ? (Number(yStr) - 1).toString().substring(2) : '24';

  const monthsOrder = [
    'January','February','March','April','May','June',
    'July','August','September','October','November','December',
  ];
  const mIdx    = monthsOrder.indexOf(mName);
  const fyStart = (mIdx >= 0 && mIdx < 3) ? Number(yStr) - 1 : Number(yStr);
  const fyEnd   = (fyStart + 1) % 100;
  const fyStr   = `${fyStart}-${fyEnd.toString().padStart(2, '0')}`;

  const handleValChange = (rowIdx, valIdx, val) => {
    const updated = rows.map((r, i) =>
      i === rowIdx ? { ...r, values: r.values.map((v, vi) => (vi === valIdx ? val : v)) } : r
    );
    onCellChange({ ...data, rows: updated });
  };

  const handleLabelChange = (rowIdx, val) => {
    const updated = rows.map((r, i) => (i === rowIdx ? { ...r, label: val } : r));
    onCellChange({ ...data, rows: updated });
  };

  // Group consecutive rows by plant for rowspan
  const grouped = [];
  let i = 0;
  while (i < rows.length) {
    const plant = rows[i].plant;
    let size = 1;
    while (i + size < rows.length && rows[i + size].plant === plant) size++;
    for (let g = 0; g < size; g++) {
      grouped.push({ row: rows[i + g], rIdx: i + g, isFirst: g === 0, size });
    }
    i += size;
  }

  return (
    <div className="report-table-wrapper" style={{ marginTop: '4px' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-end', marginBottom: '2px' }}>
        <h2 style={{ fontSize: '11pt', fontWeight: '850', color: '#060177', margin: 0, textTransform: 'uppercase' }}>
          PLANT-WISE PRODUCTION PERFORMANCE :{shortM}'{shortY} and Apr-{shortM}'{shortY}
        </h2>
        <span style={{ fontSize: '1pt', fontWeight: '600', color: '#475569' }}>Unit:000 T</span>
      </div>

      <table className="report-table" style={{ tableLayout: 'fixed', width: '100%', fontSize: '11.5pt' }}>
        <colgroup>
          <col style={{ width: COL_W.plant }} />
          <col style={{ width: COL_W.item }} />
          <col style={{ width: COL_W.annual }} />
          <col style={{ width: COL_W.mPlan }} />
          <col style={{ width: COL_W.mAct }} />
          <col style={{ width: COL_W.mPct }} />
          <col style={{ width: COL_W.cplyAct }} />
          <col style={{ width: COL_W.mGr }} />
          <col style={{ width: COL_W.ytdPlan }} />
          <col style={{ width: COL_W.ytdAct }} />
          <col style={{ width: COL_W.ytdPct }} />
          <col style={{ width: COL_W.ytdCply }} />
          <col style={{ width: COL_W.ytdGr }} />
        </colgroup>

        <thead>
          <tr>
            <th rowSpan="2" style={TH}></th>
            <th rowSpan="2" style={{ ...TH, textAlign: 'left', paddingLeft: '4px' }}></th>
            <th rowSpan="2" style={TH}>{fyStr}<br />Plan</th>
            <th colSpan="3" style={TH}>{shortM}'{shortY}</th>
            <th rowSpan="2" style={TH}>{shortM}'{prevY}<br />Act</th>
            <th rowSpan="2" style={TH}>%Gr.<br />{shortM}'{prevY}</th>
            <th colSpan="3" style={TH}>Apr-{shortM}'{shortY}</th>
            <th rowSpan="2" style={TH}>Apr-{shortM}'{prevY}<br />Act</th>
            <th rowSpan="2" style={TH}>%Gr.<br />Apr-{shortM}'{prevY}</th>
          </tr>
          <tr>
            {['Plan', 'Actual', '%Ful', 'Plan', 'Actual', '%Ful'].map((h, idx) => (
              <th key={idx} style={TH}>{h}</th>
            ))}
          </tr>
        </thead>

        <tbody>
          {grouped.map(({ row, rIdx, isFirst, size }) => {
            const plantBg = PLANT_BG[row.plant] || '#f8fafc';
            const isHighlight = BOLD_PLANTS.has(row.plant);
            return (
              <tr
                key={rIdx}
                style={{
                  fontWeight: isHighlight || row.bold ? '700' : '400',
                  backgroundColor: isHighlight ? plantBg : (row.bold ? '#f0f4f8' : 'transparent'),
                }}
              >
                {isFirst && (
                  <td
                    rowSpan={size}
                    style={{
                      ...TD,
                      fontWeight: '800',
                      fontSize: '11pt',
                      textAlign: 'center',
                      verticalAlign: 'middle',
                      backgroundColor: plantBg,
                      borderRight: '1px solid #94a3b8',
                    }}
                  >
                    {row.plant}
                  </td>
                )}
                <td style={{ ...TD, textAlign: 'left', paddingLeft: '4px', fontWeight: 'inherit' }}>
                  <input
                    type="text"
                    className="editor-input"
                    style={{ ...INPUT, textAlign: 'left', fontWeight: 'inherit' }}
                    value={row.label || ''}
                    onChange={(e) => handleLabelChange(rIdx, e.target.value)}
                  />
                </td>
                {(row.values || []).map((val, vIdx) => (
                  <td key={vIdx} style={{ ...TD, textAlign: 'right' }}>
                    <input
                      type="text"
                      className="editor-input"
                      style={INPUT}
                      value={val}
                      onChange={(e) => handleValChange(rIdx, vIdx, e.target.value)}
                    />
                  </td>
                ))}
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
