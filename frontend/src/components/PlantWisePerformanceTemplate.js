import React from 'react';

export default function PlantWisePerformanceTemplate({ data, onCellChange }) {
  const { headers = [], rows = [] } = data || {};

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
          {rows.map((row, rIdx) => (
            <tr key={rIdx}>
              {/* Plant / Items Column */}
              <td className="label-cell" style={{ minWidth: '150px' }}>
                <input
                  type="text"
                  className="editor-input"
                  style={{ color: 'black', fontWeight: '500', width: '100%', fontFamily: 'inherit' }}
                  value={row.label}
                  onChange={(e) => handleLabelChange(rIdx, e.target.value)}
                />
              </td>
              {/* 11 Value Columns */}
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
          ))}
        </tbody>
      </table>
    </div>
  );
}
