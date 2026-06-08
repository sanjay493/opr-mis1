'use client';
import React from 'react';

// Column widths as % — 15 cols, must sum to 100
const COL_W = {
  items:      '13%',
  plant:       '5%',
  annualApp:   '7%',
  mApp:        '6%',
  mActual:     '6%',
  mVar:       '5.5%',
  mPct:       '5.5%',
  cplyAct:     '6%',
  pctGr:      '5.5%',
  ytdApp:      '6%',
  ytdActual:   '6%',
  ytdVar:     '5.5%',
  ytdPct:     '5.5%',
  ytdCply:     '6%',
  ytdGr:      '5.5%',
};

const TH_STYLE = { padding: '2px 2px', fontSize: '6pt',  verticalAlign: 'middle', lineHeight: '1.15' };
const TD_STYLE = { padding: '1px 2px', fontSize: '6.5pt', lineHeight: '1.15' };
const INPUT_STYLE = {
  width: '100%', minWidth: 0, padding: '0 1px',
  background: 'transparent', border: 'none',
  color: 'black', fontFamily: 'var(--font-mono)',
  fontSize: 'inherit', textAlign: 'right',
};
const LABEL_INPUT_STYLE = {
  ...INPUT_STYLE,
  textAlign: 'left',
  fontFamily: 'var(--font-sans)',
};

export default function MonthWiseProductionTemplate({ data, onCellChange, selectedMonth }) {
  const { rows = [] } = data || {};

  const [mName, yStr] = selectedMonth ? selectedMonth.split(' ') : ['November', '2025'];
  const shortM = mName ? mName.substring(0, 3) : 'Nov';
  const shortY = yStr ? yStr.substring(2) : '25';
  const prevY  = yStr ? (Number(yStr) - 1).toString().substring(2) : '24';

  const monthsOrder = [
    'January','February','March','April','May','June',
    'July','August','September','October','November','December',
  ];
  const mIdx   = monthsOrder.indexOf(mName);
  const fyStart = (mIdx >= 0 && mIdx < 3) ? Number(yStr) - 1 : Number(yStr);
  const fyEnd   = (fyStart + 1) % 100;
  const fyStr   = `${fyStart}-${fyEnd.toString().padStart(2, '0')}`;

  const PLANTS = ['BSP','DSP','RSP','BSL','ISP','SAIL','ASP','SSP','VISL','5 Plants'];

  const splitLabel = (label) => {
    if (!label) return { item: '', plant: '' };
    const parts = label.trim().split(/\s+/);
    if (parts.length > 1 && PLANTS.includes(parts[parts.length - 1]))
      return { item: parts.slice(0, -1).join(' '), plant: parts[parts.length - 1] };
    if (parts.length > 2 && PLANTS.includes(parts.slice(-2).join(' ')))
      return { item: parts.slice(0, -2).join(' '), plant: parts.slice(-2).join(' ') };
    if (PLANTS.includes(label)) return { item: '', plant: label };
    return { item: label, plant: '' };
  };

  const handleValueChange = (rowIndex, valIndex, newVal) => {
    const updatedRows = rows.map((r, i) =>
      i === rowIndex ? { ...r, values: r.values.map((v, vi) => (vi === valIndex ? newVal : v)) } : r
    );
    onCellChange({ ...data, rows: updatedRows });
  };

  const handleItemChange = (rowIndex, newItem) => {
    const { item: oldItem } = splitLabel(rows[rowIndex].label);
    const updatedRows = rows.map((r) => {
      const { item, plant } = splitLabel(r.label);
      if (item === oldItem && oldItem !== '')
        return { ...r, label: newItem ? `${newItem} ${plant}`.trim() : plant };
      return r;
    });
    onCellChange({ ...data, rows: updatedRows });
  };

  const handlePlantChange = (rowIndex, newPlant) => {
    const { item } = splitLabel(rows[rowIndex].label);
    const combined = item ? `${item} ${newPlant}`.trim() : newPlant;
    const updatedRows = rows.map((r, i) =>
      i === rowIndex ? { ...r, label: combined } : r
    );
    onCellChange({ ...data, rows: updatedRows });
  };

  // Group consecutive rows with the same item prefix
  const groupedRows = [];
  let i = 0;
  while (i < rows.length) {
    const { item } = splitLabel(rows[i].label);
    let groupSize = 1;
    while (i + groupSize < rows.length) {
      const { item: nextItem } = splitLabel(rows[i + groupSize].label);
      if (nextItem === item && item !== '') groupSize++;
      else break;
    }
    for (let g = 0; g < groupSize; g++) {
      groupedRows.push({
        row: rows[i + g],
        rIdx: i + g,
        isFirstInGroup: g === 0,
        groupSize,
        item,
        plant: splitLabel(rows[i + g].label).plant,
      });
    }
    i += groupSize;
  }

  return (
    <div className="report-table-wrapper" style={{ marginTop: '4px' }}>
      {/* Title */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-end', marginBottom: '2px' }}>
        <h2 style={{ fontSize: '10pt', fontWeight: '850', color: '#060177', margin: 0, textTransform: 'uppercase' }}>
          SAIL: Production Performance during {mName}'{shortY} and Apr-{shortM}'{shortY}
        </h2>
        <h2 style={{ fontSize: '10pt', fontWeight: '850', color: '#0f172a', margin: 0, textTransform: 'uppercase' }}>
          w.r.t APP
        </h2>
      </div>
      <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '7pt', fontWeight: '600', color: '#475569', marginBottom: '4px' }}>
        <span>Tentative</span>
        <span>Unit: '000 T</span>
      </div>

      <table
        className="report-table"
        style={{ tableLayout: 'fixed', width: '100%', fontSize: '6.5pt' }}
      >
        <colgroup>
          <col style={{ width: COL_W.items }} />
          <col style={{ width: COL_W.plant }} />
          <col style={{ width: COL_W.annualApp }} />
          <col style={{ width: COL_W.mApp }} />
          <col style={{ width: COL_W.mActual }} />
          <col style={{ width: COL_W.mVar }} />
          <col style={{ width: COL_W.mPct }} />
          <col style={{ width: COL_W.cplyAct }} />
          <col style={{ width: COL_W.pctGr }} />
          <col style={{ width: COL_W.ytdApp }} />
          <col style={{ width: COL_W.ytdActual }} />
          <col style={{ width: COL_W.ytdVar }} />
          <col style={{ width: COL_W.ytdPct }} />
          <col style={{ width: COL_W.ytdCply }} />
          <col style={{ width: COL_W.ytdGr }} />
        </colgroup>

        <thead>
          <tr>
            <th rowSpan="2" style={{ ...TH_STYLE, textAlign: 'left', paddingLeft: '4px' }}>Items</th>
            <th rowSpan="2" style={TH_STYLE}>Plant</th>
            <th rowSpan="2" style={TH_STYLE}>APP<br />{fyStr}</th>
            <th colSpan="4" style={TH_STYLE}>{shortM}'{shortY}</th>
            <th rowSpan="2" style={TH_STYLE}>{shortM}'{prevY}<br />Actual</th>
            <th rowSpan="2" style={TH_STYLE}>%Gr.<br />{shortM}'{prevY}</th>
            <th colSpan="4" style={TH_STYLE}>Apr-{shortM}'{shortY}</th>
            <th rowSpan="2" style={TH_STYLE}>Apr-{shortM}'{prevY}<br />Actual</th>
            <th rowSpan="2" style={TH_STYLE}>%Gr.<br />Apr-{shortM}'{prevY}</th>
          </tr>
          <tr>
            {['APP','Actual','Var','%Ful.','APP','Actual','Var','%Ful.'].map((h, i) => (
              <th key={i} style={TH_STYLE}>{h}</th>
            ))}
          </tr>
        </thead>

        <tbody>
          {groupedRows.map(({ row, rIdx, isFirstInGroup, groupSize, item, plant }) => (
            <tr key={rIdx}>
              {isFirstInGroup && (
                <td
                  className="label-cell"
                  rowSpan={groupSize}
                  style={{
                    ...TD_STYLE,
                    fontWeight: 'bold',
                    verticalAlign: 'middle',
                    backgroundColor: '#f8fafc',
                    borderRight: '1px solid #cbd5e1',
                    overflow: 'hidden',
                    textAlign: 'left',
                    paddingLeft: '3px',
                  }}
                >
                  <input
                    type="text"
                    className="editor-input"
                    style={{ ...LABEL_INPUT_STYLE, fontWeight: 'bold', fontSize: '6pt' }}
                    value={item}
                    onChange={(e) => handleItemChange(rIdx, e.target.value)}
                  />
                </td>
              )}
              <td
                className="label-cell"
                style={{
                  ...TD_STYLE,
                  fontWeight: '600',
                  textAlign: 'center',
                  backgroundColor: '#f8fafc',
                  overflow: 'hidden',
                }}
              >
                <input
                  type="text"
                  className="editor-input"
                  style={{ ...LABEL_INPUT_STYLE, textAlign: 'center', fontWeight: '600', fontSize: '6pt' }}
                  value={plant}
                  onChange={(e) => handlePlantChange(rIdx, e.target.value)}
                />
              </td>
              {row.values.map((val, vIdx) => (
                <td key={vIdx} style={{ ...TD_STYLE, overflow: 'hidden' }}>
                  <input
                    type="text"
                    className="editor-input"
                    style={{ ...INPUT_STYLE, fontSize: '6.5pt' }}
                    value={val}
                    onChange={(e) => handleValueChange(rIdx, vIdx, e.target.value)}
                  />
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
