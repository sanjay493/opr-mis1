import React from 'react';

export default function TrendTemplate({ data, onCellChange }) {
  const { headers = [], rows = [] } = data || {};

  const handleValueChange = (rowIndex, valIndex, newVal) => {
    const updatedRows = [...rows];
    updatedRows[rowIndex].values[valIndex] = newVal;
    onCellChange({ ...data, rows: updatedRows });
  };

  const handleLabelChange = (rowIndex, newLabel) => {
    const updatedRows = [...rows];
    updatedRows[rowIndex].label = newLabel;
    onCellChange({ ...data, rows: updatedRows });
  };

  return (
    <div className="report-table-wrapper trend-table-container">
      <table className="report-table trend-table">
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
              <td className="label-cell" style={{ fontWeight: '600' }}>
                <input
                  type="text"
                  className="editor-input"
                  style={{ color: 'black', fontWeight: '600', width: '100%', fontFamily: 'inherit' }}
                  value={row.label}
                  onChange={(e) => handleLabelChange(rIdx, e.target.value)}
                />
              </td>
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
