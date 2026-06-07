import React from 'react';

export default function SummaryTemplate({ data, onCellChange, selectedMonth }) {
  const { production_table = [], te_table = [], highlights = [] } = data || {};

  const [monthName, yearStr] = (selectedMonth || 'November 2025').split(' ');
  const shortMonth = monthName ? monthName.substring(0, 3) : 'Nov';
  const prevYear = yearStr ? (Number(yearStr) - 1).toString() : '2024';
  const shortYear = yearStr ? yearStr.substring(2) : '25';
  const shortPrevYear = prevYear ? prevYear.substring(2) : '24';

  const monthIndex = [
    'January', 'February', 'March', 'April', 'May', 'June',
    'July', 'August', 'September', 'October', 'November', 'December'
  ].indexOf(monthName);

  let targetYearStart = yearStr ? Number(yearStr) : 2025;
  if (monthIndex >= 0 && monthIndex < 3) {
    targetYearStart -= 1;
  }
  const targetYearEnd = (targetYearStart + 1) % 100;
  const targetHeader = `Target ${targetYearStart}-${targetYearEnd.toString().padStart(2, '0')}`;

  const handleProdChange = (rowIndex, valIndex, newVal) => {
    const updatedProd = [...production_table];
    updatedProd[rowIndex].values[valIndex] = newVal;
    onCellChange({ ...data, production_table: updatedProd });
  };

  const handleTeChange = (rowIndex, valIndex, newVal) => {
    const updatedTe = [...te_table];
    updatedTe[rowIndex].values[valIndex] = newVal;
    onCellChange({ ...data, te_table: updatedTe });
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%', gap: '15px' }}>

      {/* Production Summary Table */}
      <div>
        <h3 style={{ fontSize: '9pt', fontWeight: 'bold', textTransform: 'uppercase', marginBottom: '6px', color: '#0f172a' }}>
          Production Performance Summary (Unit: '000 T)
        </h3>
        <table className="report-table">
          <thead>
            <tr>
              <th rowSpan="2">Item</th>
              <th colSpan="3">{monthName} {yearStr}</th>
              <th colSpan="2">{shortMonth}’{shortPrevYear}</th>
              <th colSpan="3">April - {monthName} {yearStr} </th>
              <th colSpan="2">April-{shortMonth}’{shortPrevYear}</th>
            </tr>
            <tr>
              <th>APP</th>
              <th>Actual</th>
              <th>% Ful.</th>
              <th>Act.</th>
              <th>% Gr.</th>
              <th>APP</th>
              <th>Actual</th>
              <th>% Ful.</th>
              <th>Act.</th>
              <th>% Gr.</th>
            </tr>
          </thead>
          <tbody>
            {production_table.map((row, rIdx) => (
              <tr key={rIdx}>
                <td className="label-cell">{row.item}</td>
                {row.values.map((val, vIdx) => (
                  <td key={vIdx}>
                    <input
                      type="text"
                      className="editor-input"
                      style={{ color: 'black', textAlign: 'right' }}
                      value={val}
                      onChange={(e) => handleProdChange(rIdx, vIdx, e.target.value)}
                    />
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Highlights Box */}
      {highlights.length > 0 && (
        <div className="highlights-box">
          <h4>Key Production Highlights</h4>
          <ul>
            {highlights.map((highlight, idx) => (
              <li key={idx}>{highlight}</li>
            ))}
          </ul>
        </div>
      )}

      {/* Techno-Economic parameters Table */}
      <div>
        <h3 style={{ fontSize: '9pt', fontWeight: 'bold', textTransform: 'uppercase', marginBottom: '6px', color: '#0f172a' }}>
          Major Techno-Economic Parameters
        </h3>
        <table className="report-table">
          <thead>
            <tr>
              <th>Parameter</th>
              <th>Unit</th>
              <th>{targetHeader}</th>
              <th>{shortMonth}'{shortYear}</th>
              <th>{shortMonth}'{shortPrevYear}</th>
              <th>Apr-{shortMonth}'{shortYear}</th>
              <th>Apr-{shortMonth}'{shortPrevYear}</th>
            </tr>
          </thead>
          <tbody>
            {te_table.map((row, rIdx) => (
              <tr key={rIdx}>
                <td className="label-cell">{row.parameter}</td>
                <td className="label-cell" style={{ fontStyle: 'italic', color: '#475569' }}>{row.unit}</td>
                {row.values.map((val, vIdx) => (
                  <td key={vIdx}>
                    <input
                      type="text"
                      className="editor-input"
                      style={{ color: 'black', textAlign: 'right' }}
                      value={val}
                      onChange={(e) => handleTeChange(rIdx, vIdx, e.target.value)}
                    />
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

    </div>
  );
}
