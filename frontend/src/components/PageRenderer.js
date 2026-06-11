import React from 'react';
import CoverTemplate from './CoverTemplate';
import SummaryTemplate from './SummaryTemplate';
import TableTemplate from './TableTemplate';
import TrendTemplate from './TrendTemplate';
import TrendYearlyTemplate from './TrendYearlyTemplate';
import MonthWiseProductionTemplate from './MonthWiseProductionTemplate';
import PlantWisePerformanceTemplate from './PlantWisePerformanceTemplate';
import ConcastPerformanceTemplate from './ConcastPerformanceTemplate';
import ProductionByProcessTemplate from './ProductionByProcessTemplate';
import CatWiseSaleableTemplate from './CatWiseSaleableTemplate';
import SegmentWiseTemplate from './SegmentWiseTemplate';

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
    <div className="report-table-wrapper" style={{ marginTop: '8px' }}>
      <h2 className="page2-heading">Index</h2>
      <table className="report-table page2-table" style={{ width: '100%', tableLayout: 'fixed' }}>
        <thead>
          <tr>
            <th style={{ width: '8%', textAlign: 'center' }}>S.No.</th>
            <th style={{ width: '77%', textAlign: 'left' }}>Contents</th>
            <th style={{ width: '15%', textAlign: 'center' }}>Page</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row, idx) => (
            <tr key={idx}>
              <td className="sno" style={{ verticalAlign: 'top' }}>
                <input
                  type="text"
                  className="editor-input"
                  style={{ color: 'black', textAlign: 'center', width: '100%', fontWeight: 'bold' }}
                  value={row.sno}
                  onChange={(e) => handleRowChange(idx, 'sno', e.target.value)}
                />
              </td>
              <td style={{ textAlign: 'left', wordWrap: 'break-word', whiteSpace: 'normal', verticalAlign: 'top' }}>
                <textarea
                  className="editor-input"
                  style={{
                    color: 'black',
                    textAlign: 'left',
                    width: '100%',
                    resize: 'none',
                    background: 'transparent',
                    border: 'none',
                    fontFamily: 'inherit',
                    lineHeight: '1.4',
                    verticalAlign: 'top'
                  }}
                  rows={1}
                  value={row.title}
                  onChange={(e) => handleRowChange(idx, 'title', e.target.value)}
                />
              </td>
              <td className="center" style={{ textAlign: 'center', verticalAlign: 'top' }}>
                <input
                  type="text"
                  className="editor-input"
                  style={{ color: 'black', textAlign: 'center', width: '100%' }}
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
      case 'trend_yearly':
      case 'trend_combined':
        return <TrendYearlyTemplate data={pageData} />;
      case 'concast_performance':
        return <ConcastPerformanceTemplate data={pageData} selectedMonth={selectedMonth} />;
      case 'prod_by_process':
        return <ProductionByProcessTemplate data={pageData} selectedMonth={selectedMonth} />;
      case 'catwise_saleable':
        return <CatWiseSaleableTemplate data={pageData} />;
      case 'segment_wise':
        return <SegmentWiseTemplate data={pageData} />;
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
        {pageData.type !== 'cover' && pageData.type !== 'index' && pageData.type !== 'page4_table' && pageData.type !== 'performance_summary_table' && pageData.type !== 'trend_yearly' && pageData.type !== 'trend_combined' && pageData.type !== 'concast_performance' && pageData.type !== 'prod_by_process' && pageData.type !== 'catwise_saleable' && pageData.type !== 'segment_wise' && (
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
          <div>Page {pageData.page} of {totalPages || 48}</div>
        </div>
      )}
    </div>
  );
}
