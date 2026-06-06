import React from 'react';
import CoverTemplate from './CoverTemplate';
import SummaryTemplate from './SummaryTemplate';
import TableTemplate from './TableTemplate';
import TrendTemplate from './TrendTemplate';
import MonthWiseProductionTemplate from './MonthWiseProductionTemplate';
import PlantWisePerformanceTemplate from './PlantWisePerformanceTemplate';

function IndexTemplate({ data, onCellChange }) {
  const { rows = [] } = data || {};

  const handleRowChange = (rowIndex, key, newVal) => {
    const updatedRows = [...rows];
    updatedRows[rowIndex] = {
      ...updatedRows[rowIndex],
      [key]: newVal
    };
    onCellChange({ ...data, rows: updatedRows });
  };

  return (
    <div className="report-table-wrapper" style={{ marginTop: '15px' }}>
      <h3 style={{ fontSize: '12pt', fontWeight: '700', textTransform: 'uppercase', marginBottom: '12px', color: '#0f172a', textAlign: 'center' }}>
        Table of Contents
      </h3>
      <table className="report-table" style={{ fontSize: '12pt', width: '100%', lineHeight: '13pt' }}>
        <thead>
          <tr>
            <th style={{ width: '10%', textAlign: 'center', padding: '6px 10px' }}>S.No.</th>
            <th style={{ width: '75%', textAlign: 'left', paddingLeft: '15px', padding: '6px 10px' }}>Contents</th>
            <th style={{ width: '15%', textAlign: 'center', padding: '6px 10px' }}>Page</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row, idx) => (
            <tr key={idx}>
              <td style={{ textAlign: 'center', fontFamily: 'inherit', padding: '5px 8px' }}>
                <input
                  type="text"
                  className="editor-input"
                  style={{ color: 'black', textAlign: 'center', width: '100%', fontSize: '12pt' }}
                  value={row.sno}
                  onChange={(e) => handleRowChange(idx, 'sno', e.target.value)}
                />
              </td>
              <td style={{ textAlign: 'left', fontFamily: 'inherit', padding: '5px 8px', paddingLeft: '15px', fontWeight: row.sno ? '600' : '400', wordWrap: 'break-word', whiteSpace: 'normal' }}>
                <textarea
                  className="editor-input"
                  style={{
                    color: 'black',
                    textAlign: 'left',
                    width: '100%',
                    fontWeight: row.sno ? '600' : '400',
                    fontSize: '12pt',
                    resize: 'none',
                    background: 'transparent',
                    border: 'none',
                    fontFamily: 'inherit',
                    lineHeight: '1.3',
                    verticalAlign: 'middle'
                  }}
                  rows={Math.max(1, Math.ceil((row.title || '').length / 50))}
                  value={row.title}
                  onChange={(e) => handleRowChange(idx, 'title', e.target.value)}
                />
              </td>
              <td style={{ textAlign: 'center', fontFamily: 'inherit', padding: '5px 8px' }}>
                <input
                  type="text"
                  className="editor-input"
                  style={{ color: 'black', textAlign: 'center', width: '100%', fontSize: '12pt' }}
                  value={row.page_range}
                  onChange={(e) => handleRowChange(idx, 'page_range', e.target.value)}
                />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export default function PageRenderer({ pageData, onCellChange, selectedMonth, totalPages }) {
  if (!pageData) {
    return (
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%', color: '#64748b' }}>
        No page selected
      </div>
    );
  }

  const renderContent = () => {
    switch (pageData.type) {
      case 'cover':
        return <CoverTemplate data={pageData} />;
      case 'index':
        return <IndexTemplate data={pageData} onCellChange={onCellChange} />;
      case 'summary':
        return <SummaryTemplate data={pageData} onCellChange={onCellChange} selectedMonth={selectedMonth} />;
      case 'page4_table':
        return <MonthWiseProductionTemplate data={pageData} onCellChange={onCellChange} selectedMonth={selectedMonth} />;
      case 'performance_summary_table':
        return <PlantWisePerformanceTemplate data={pageData} onCellChange={onCellChange} selectedMonth={selectedMonth} />;
      case 'table':
        return <TableTemplate data={pageData} onCellChange={onCellChange} />;
      case 'trend':
        return <TrendTemplate data={pageData} onCellChange={onCellChange} />;
      default:
        return (
          <div style={{ padding: '20px', fontSize: '10pt', color: '#64748b' }}>
            Unsupported page type: {pageData.type}
          </div>
        );
    }
  };

  const isLandscape = pageData.orientation === 'landscape';

  return (
    <div className={`a4-page ${isLandscape ? 'landscape' : ''}`}>
      {/* Header (hidden on Cover page for cleaner design) */}
      {pageData.type !== 'cover' && (
        <div className="report-header">
          Steel Authority of India Limited - Operations Monthly Informatics
        </div>
      )}

      {/* Main Body */}
      <div className="report-body">
        {pageData.type !== 'cover' && pageData.type !== 'index' && (
          <div className="report-title-section">
            <h2>{pageData.title}</h2>
            {pageData.subtitle && <h3>{pageData.subtitle}</h3>}
          </div>
        )}
        {renderContent()}
      </div>

      {/* Footer (hidden on Cover page) */}
      {pageData.type !== 'cover' && (
        <div className="report-footer">
          <div>Prepared by: MIS Group</div>
          <div>Page {pageData.page} of {totalPages || 49}</div>
        </div>
      )}
    </div>
  );
}
