import React from 'react';

export default function MonthWiseProductionTemplate({ data, onCellChange, selectedMonth }) {
  const { headers = [], rows = [] } = data || {};

  const [mName, yStr] = selectedMonth ? selectedMonth.split(" ") : ["November", "2025"];
  const shortM = mName ? mName.substring(0, 3) : "Nov";
  const shortY = yStr ? yStr.substring(2) : "25";
  const prevY = yStr ? (Number(yStr) - 1).toString().substring(2) : "24";

  const monthsOrder = [
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December"
  ];
  const mIdx = monthsOrder.indexOf(mName);
  const fyStart = (mIdx >= 0 && mIdx < 3) ? Number(yStr) - 1 : Number(yStr);
  const fyEnd = (fyStart + 1) % 100;
  const fyStr = `${fyStart}-${fyEnd.toString().padStart(2, '0')}`;

  const splitLabel = (label) => {
    if (!label) return { item: '', plant: '' };

    const plants = ['BSP', 'DSP', 'RSP', 'BSL', 'ISP', 'SAIL', 'ASP', 'SSP', 'VISL'];
    const parts = label.trim().split(/\s+/);

    if (parts.length > 1) {
      const lastPart = parts[parts.length - 1];
      if (plants.includes(lastPart)) {
        const item = parts.slice(0, parts.length - 1).join(' ');
        return { item, plant: lastPart };
      }
    }

    if (plants.includes(label)) {
      return { item: '', plant: label };
    }

    return { item: label, plant: '' };
  };

  const handleValueChange = (rowIndex, valIndex, newVal) => {
    const updatedRows = [...rows];
    updatedRows[rowIndex] = {
      ...updatedRows[rowIndex],
      values: [...updatedRows[rowIndex].values]
    };
    updatedRows[rowIndex].values[valIndex] = newVal;
    onCellChange({ ...data, rows: updatedRows });
  };

  const handleLabelChange = (rowIndex, newLabel) => {
    const updatedRows = [...rows];
    updatedRows[rowIndex] = {
      ...updatedRows[rowIndex],
      label: newLabel
    };
    onCellChange({ ...data, rows: updatedRows });
  };

  const handleItemChange = (rowIndex, newItem) => {
    const oldLabel = rows[rowIndex].label;
    const { item: oldItem } = splitLabel(oldLabel);
    
    const updatedRows = rows.map((row) => {
      const { item, plant } = splitLabel(row.label);
      if (item === oldItem && oldItem !== '') {
        return {
          ...row,
          label: newItem ? `${newItem} ${plant}`.trim() : plant
        };
      }
      return row;
    });
    onCellChange({ ...data, rows: updatedRows });
  };

  const handlePlantChange = (rowIndex, newPlant) => {
    const { item } = splitLabel(rows[rowIndex].label);
    const combined = item ? `${item} ${newPlant}`.trim() : newPlant;
    handleLabelChange(rowIndex, combined);
  };

  // Group rows by item prefix
  const groupedRows = [];
  let i = 0;
  while (i < rows.length) {
    const { item, plant } = splitLabel(rows[i].label);
    
    // Find how many consecutive rows have the exact same item prefix
    let groupSize = 1;
    while (i + groupSize < rows.length) {
      const nextLabel = splitLabel(rows[i + groupSize].label);
      if (nextLabel.item === item && item !== '') {
        groupSize++;
      } else {
        break;
      }
    }
    
    for (let g = 0; g < groupSize; g++) {
      groupedRows.push({
        row: rows[i + g],
        rIdx: i + g,
        isFirstInGroup: g === 0,
        groupSize,
        item,
        plant: splitLabel(rows[i + g].label).plant
      });
    }
    i += groupSize;
  }

  return (
    <div className="report-table-wrapper">
      {/* Title block with split alignment */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-end', }}>
        <h2 style={{ fontSize: '12pt', fontWeight: '850', color: '#060177ff', margin: 0, textTransform: 'uppercase', fontFamily: 'inherit' }}>
          SAIL: Production Performance during {mName}'{shortY} and Apr-{shortM}'{shortY}
        </h2>
        <h2 style={{ fontSize: '11.5pt', fontWeight: '850', color: '#0f172a', margin: 0, textTransform: 'uppercase', fontFamily: 'inherit' }}>
          w.r.t APP
        </h2>
      </div>
      <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '9pt', fontWeight: '600', color: '#475569', marginBottom: '8px' }}>
        <span>Tentative</span>
        <span>Unit: '000 T</span>
      </div>

      <table className="report-table">
        <thead>
          <tr>
            <th rowSpan="2" style={{ padding: '4px 6px', verticalAlign: 'middle' }}>Items</th>
            <th rowSpan="2" style={{ padding: '4px 6px', verticalAlign: 'middle' }}>Plant</th>
            <th rowSpan="2" style={{ padding: '4px 6px', verticalAlign: 'middle' }}>APP {fyStr}</th>
            <th colSpan="4" style={{ padding: '4px 6px', textAlign: 'center' }}>{shortM}'{shortY}</th>
            <th rowSpan="2" style={{ padding: '4px 6px', verticalAlign: 'middle' }}>{shortM}'{prevY}<br />Actual</th>
            <th rowSpan="2" style={{ padding: '4px 6px', verticalAlign: 'middle' }}>% Gr. over<br />{shortM}'{prevY}</th>
            <th colSpan="4" style={{ padding: '4px 6px', textAlign: 'center' }}>Apr-{shortM}'{shortY}</th>
            <th rowSpan="2" style={{ padding: '4px 6px', verticalAlign: 'middle' }}>Apr-{shortM}'{prevY}<br />Actual</th>
            <th rowSpan="2" style={{ padding: '4px 6px', verticalAlign: 'middle' }}>% Gr. over<br />Apr-{shortM}'{prevY}</th>
          </tr>
          <tr>
            <th style={{ padding: '4px 6px' }}>APP</th>
            <th style={{ padding: '4px 6px' }}>Actual</th>
            <th style={{ padding: '4px 6px' }}>Var</th>
            <th style={{ padding: '4px 6px' }}>% Ful.</th>
            <th style={{ padding: '4px 6px' }}>APP</th>
            <th style={{ padding: '4px 6px' }}>Actual</th>
            <th style={{ padding: '4px 6px' }}>Var</th>
            <th style={{ padding: '4px 6px' }}>% Ful.</th>
          </tr>
        </thead>
        <tbody>
          {groupedRows.map(({ row, rIdx, isFirstInGroup, groupSize, item, plant }) => {
            return (
              <tr key={rIdx}>
                {/* Item Column */}
                {isFirstInGroup && (
                  <td className="label-cell" rowSpan={groupSize} style={{ minWidth: '120px', fontWeight: 'bold', verticalAlign: 'middle', backgroundColor: '#f8fafc', borderRight: '1px solid #cbd5e1' }}>
                    <textarea
                      className="editor-input"
                      style={{ color: 'black', fontWeight: 'bold', width: '100%', fontFamily: 'inherit', border: 'none', background: 'transparent', resize: 'none' }}
                      value={item}
                      onChange={(e) => handleItemChange(rIdx, e.target.value)}
                      rows={Math.max(1, Math.ceil(item.length / 15))}
                    />
                  </td>
                )}
                {/* Plant Column */}
                <td className="label-cell" style={{ minWidth: '60px', fontWeight: '600', textAlign: 'center', backgroundColor: '#f8fafc' }}>
                  <input
                    type="text"
                    className="editor-input"
                    style={{ color: 'black', fontWeight: '600', width: '100%', fontFamily: 'inherit', textAlign: 'center' }}
                    value={plant}
                    onChange={(e) => handlePlantChange(rIdx, e.target.value)}
                  />
                </td>
                {/* 13 Value Columns */}
                {row.values.map((val, vIdx) => (
                  <td key={vIdx}>
                    <input
                      type="text"
                      className="editor-input"
                      style={{ color: 'black', textAlign: 'right' }}
                      value={val}
                      onChange={(e) => handleValueChange(rIdx, vIdx, e.target.value)}
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
