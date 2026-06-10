import React from 'react';

export default function SummaryTemplate({ data, onCellChange, selectedMonth }) {
  const { production_table = [], te_table = [], highlights = [] } = data || {};

  const monthsOrder = [
    'January', 'February', 'March', 'April', 'May', 'June',
    'July', 'August', 'September', 'October', 'November', 'December',
  ];

  const _def = new Date(Date.now() - 45 * 24 * 60 * 60 * 1000);
  let monthName = monthsOrder[_def.getMonth()];
  let yearStr   = _def.getFullYear().toString();
  if (selectedMonth && /^\d{4}-\d{2}$/.test(selectedMonth)) {
    yearStr   = selectedMonth.substring(0, 4);
    monthName = monthsOrder[parseInt(selectedMonth.substring(5, 7), 10) - 1] || monthName;
  }

  const shortMonth     = monthName.substring(0, 3);
  const prevYear       = (Number(yearStr) - 1).toString();
  const shortYear      = yearStr.substring(2);
  const shortPrevYear  = prevYear.substring(2);

  const monthIndex = monthsOrder.indexOf(monthName);

  let targetYearStart = Number(yearStr);
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
        <h3 className="page3-section-heading">
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
        <h3 className="page3-section-heading">
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
