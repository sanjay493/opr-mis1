import React from 'react';

export default function MonthWiseProductionTemplate({ data, onCellChange }) {
  const { headers = [], rows = [] } = data || {};

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
    const { plant } = splitLabel(rows[rowIndex].label);
    const combined = newItem ? `${newItem} ${plant}`.trim() : plant;
    handleLabelChange(rowIndex, combined);
  };

  const handlePlantChange = (rowIndex, newPlant) => {
    const { item } = splitLabel(rows[rowIndex].label);
    const combined = item ? `${item} ${newPlant}`.trim() : newPlant;
    handleLabelChange(rowIndex, combined);
  };

  return (
    <div className="report-table-wrapper">
      <table className="report-table">
        <thead>
          <tr>
            {headers.map((h, idx) => (
              <th key={idx}>{h}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, rIdx) => {
            const { item, plant } = splitLabel(row.label);
            return (
              <tr key={rIdx}>
                {/* Item Column */}
                <td className="label-cell" style={{ minWidth: '100px' }}>
                  <input
                    type="text"
                    className="editor-input"
                    style={{ color: 'black', fontWeight: '500', width: '100%', fontFamily: 'inherit' }}
                    value={item}
                    onChange={(e) => handleItemChange(rIdx, e.target.value)}
                  />
                </td>
                {/* Plant Column */}
                <td className="label-cell" style={{ minWidth: '60px' }}>
                  <input
                    type="text"
                    className="editor-input"
                    style={{ color: 'black', fontWeight: '500', width: '100%', fontFamily: 'inherit' }}
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
