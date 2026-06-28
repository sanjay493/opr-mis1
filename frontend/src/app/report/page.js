'use client';

import React, { useState, useEffect, useMemo } from 'react';
import GlobalNavbar from '@/components/GlobalNavbar';
import PageRenderer from '../../components/PageRenderer';
import { useReportData, useSaveReportData, useGeneratePDF } from '@/hooks/useReportAPI';

// Edit these labels to change what appears in the Page Selector dropdown
const PAGE_LABELS = {
   1: 'Cover Page',
   2: 'Index / Contents',
   3: 'SAIL Performance Summary',
   4: 'Production Performance vs APP (Month)',
   5: 'Plant-Wise Production Performance',
   6: 'Plant-Wise Production (Month & YTD)',
   7: 'Month-Wise Production Trend – Oven Pushing',
   8: 'Month-Wise Production Trend – Sinter',
   9: 'Month-Wise Production Trend – Hot Metal',
  10: 'Month-Wise Production Trend – Crude Steel',
  11: 'Month-Wise Production Trend – Pig Iron & Finished Steel',
  12: 'Month-Wise Production Trend – Saleable Steel',
  13: 'Concast Production Performance',
  14: 'Production by Process',
  15: 'Category Wise – BSP',
  16: 'Category Wise – DSP & RSP',
  17: 'Category Wise – BSL & ISP',
  18: 'Segment Wise Production',
  19: 'Special Steel – BSP',
  20: 'Special Steel – DSP',
  21: 'Special Steel – RSP',
  22: 'Special Steel – BSL',
  23: 'Special Steel – ISP',
  24: 'Special Steel – SAIL (Consolidated)',
  25: 'Opening Stock at Plants & Stockyards',
  26: 'IPT Status',
  27: 'Major Techno-Economic Parameters',
  28: 'Techno – Coke & Coal Chemicals, Sinter',
  29: 'Techno – Iron Making',
  30: 'Techno – SMS Shop',
  31: 'Mill Wise Techno – BSP',
  32: 'Mill Wise Techno – DSP',
  33: 'Mill Wise Techno – RSP',
  34: 'Mill Wise Techno – BSL',
  35: 'Mill Wise Techno – ISP',
};

const months = [
  'January', 'February', 'March', 'April', 'May', 'June',
  'July', 'August', 'September', 'October', 'November', 'December'
];

const MONTH_NUM = {
  'January': '01', 'February': '02', 'March': '03', 'April': '04',
  'May': '05', 'June': '06', 'July': '07', 'August': '08',
  'September': '09', 'October': '10', 'November': '11', 'December': '12',
};

const years = Array.from({ length: 16 }, (_, i) => (2020 + i).toString());

function replaceTimeStrings(text, newMonth, newYear, oldMonth, oldYear) {
  if (typeof text !== 'string') return text;
  
  const oldShortMonth = oldMonth.substring(0, 3);
  const oldYearNum = Number(oldYear);
  const oldPrevYearNum = oldYearNum - 1;
  const oldShortYear = oldYear.substring(2);
  const oldShortPrevYear = oldPrevYearNum.toString().substring(2);

  const newShortMonth = newMonth.substring(0, 3);
  const newYearNum = Number(newYear);
  const newPrevYearNum = newYearNum - 1;
  const newShortYear = newYear.substring(2);
  const newShortPrevYear = newPrevYearNum.toString().substring(2);
  
  let result = text;
  
  // 1. Shift 4-digit financial year patterns (e.g. 2025-26 -> 2026-27)
  const delta = newYearNum - oldYearNum;
  const yearRegex = /(\d{4})-(\d{2})/g;
  result = result.replace(yearRegex, (match, p1, p2) => {
    const y1 = Number(p1);
    const y2 = Number(p2);
    if (Math.abs(y1 - oldYearNum) <= 10) {
      const newY1 = y1 + delta;
      const newY2 = (y2 + delta) % 100;
      return `${newY1}-${newY2.toString().padStart(2, '0')}`;
    }
    return match;
  });
  
  // 2. Shift 2-digit financial year patterns (e.g. 25-26 -> 26-27)
  const shortYearRegex = /\b(\d{2})-(\d{2})\b/g;
  result = result.replace(shortYearRegex, (match, p1, p2) => {
    const y1 = Number(p1);
    const y2 = Number(p2);
    if (Math.abs(y1 - Number(oldShortYear)) <= 10) {
      const newY1 = y1 + delta;
      const newY2 = (y2 + delta) % 100;
      return `${newY1.toString().padStart(2, '0')}-${newY2.toString().padStart(2, '0')}`;
    }
    return match;
  });
  
  // 3. Replace full 4-digit years
  result = result.replace(new RegExp(oldYear, 'g'), newYear);
  result = result.replace(new RegExp(oldPrevYearNum.toString(), 'g'), newPrevYearNum.toString());
  
  // 4. Replace Month names
  result = result.replace(new RegExp(oldMonth, 'g'), newMonth);
  result = result.replace(new RegExp(oldMonth.toLowerCase(), 'g'), newMonth.toLowerCase());
  result = result.replace(new RegExp(oldMonth.toUpperCase(), 'g'), newMonth.toUpperCase());
  
  result = result.replace(new RegExp(oldShortMonth, 'g'), newShortMonth);
  result = result.replace(new RegExp(oldShortMonth.toLowerCase(), 'g'), newShortMonth.toLowerCase());
  result = result.replace(new RegExp(oldShortMonth.toUpperCase(), 'g'), newShortMonth.toUpperCase());
  
  // 5. Short year references (with or without single quote prefix)
  result = result.replace(new RegExp(`'${oldShortYear}`, 'g'), `'${newShortYear}`);
  result = result.replace(new RegExp(`'${oldShortPrevYear}`, 'g'), `'${newShortPrevYear}`);
  result = result.replace(new RegExp(`\\b${oldShortPrevYear}\\b`, 'g'), newShortPrevYear);
  result = result.replace(new RegExp(`\\b${oldShortYear}\\b`, 'g'), newShortYear);
  
  return result;
}

function getFormattedPagesData(pages, newMonth, newYear, oldMonth, oldYear) {
  return pages.map((page) => {
    if (page.page === 1) {
      return {
        ...page,
        date: `${newMonth.toUpperCase()} ${newYear}`
      };
    }
    
    if (page.page === 3 || page.type === 'summary') {
      const shortYear = newYear.substring(2);
      return {
        ...page,
        subtitle: `${newMonth}’${shortYear}`
      };
    }
    
    const formattedHeaders = page.headers
      ? page.headers.map((h) => replaceTimeStrings(h, newMonth, newYear, oldMonth, oldYear))
      : page.headers;
      
    const formattedRows = page.rows
      ? page.rows.map((row) => ({
          ...row,
          label: replaceTimeStrings(row.label, newMonth, newYear, oldMonth, oldYear)
        }))
      : page.rows;
      
    return {
      ...page,
      title: replaceTimeStrings(page.title, newMonth, newYear, oldMonth, oldYear),
      subtitle: replaceTimeStrings(page.subtitle, newMonth, newYear, oldMonth, oldYear),
      headers: formattedHeaders,
      rows: formattedRows
    };
  });
}

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://127.0.0.1:8082';
console.log('API_BASE_URL:', API_BASE_URL);

const getDefaultDate = () => {
  const d = new Date(Date.now() - 45 * 24 * 60 * 60 * 1000);
  return {
    month: months[d.getMonth()],
    year: d.getFullYear().toString()
  };
};

export default function ReportPage() {
  const defaultDate = getDefaultDate();
  const [pagesData, setPagesData] = useState([]);
  const [activePageNum, setActivePageNum] = useState(1);
  const [selectedMonthName, setSelectedMonthName] = useState(defaultDate.month);
  const [selectedYear, setSelectedYear] = useState(defaultDate.year);

  const selectedMonth = `${selectedYear}-${MONTH_NUM[selectedMonthName]}`;

  // Use React Query to fetch report data - automatically cached for 10 minutes
  const { data: rawData, isLoading, error } = useReportData(selectedMonth);
  const { mutate: saveData, isPending: isSaving } = useSaveReportData();
  const { mutate: generatePDF, isPending: isGeneratingPDF } = useGeneratePDF();

  // Format data when it loads
  useEffect(() => {
    if (rawData) {
      const normalized = rawData.map((p) => {
        if (p.page === 4) return { ...p, type: 'page4_table' };
        if (p.page === 5 || p.page === 6) return { ...p, type: 'performance_summary_table' };
        return p;
      });
      const formatted = getFormattedPagesData(normalized, selectedMonthName, selectedYear, 'November', '2025');
      setPagesData(formatted);
    }
  }, [rawData, selectedMonthName, selectedYear]);

  const activePage = useMemo(
    () => pagesData.find((p) => p.page === activePageNum) || pagesData[0],
    [pagesData, activePageNum]
  );

  const handleSaveToDatabase = () => {
    saveData(
      { month: selectedMonth, pages: pagesData },
      {
        onSuccess: () => {
          alert('Changes saved successfully to SQLite database!');
        },
        onError: (error) => {
          console.error(error);
          alert('Error saving data to SQLite database. Ensure backend is running.');
        },
      }
    );
  };

  const handleCellChange = (updatedPageData) => {
    setPagesData((prev) =>
      prev.map((p) => (p.page === updatedPageData.page ? updatedPageData : p))
    );
  };

  const handleBackendExport = () => {
    generatePDF(
      { month: selectedMonth },
      {
        onSuccess: (blob) => {
          const url = window.URL.createObjectURL(blob);
          const a = document.createElement('a');
          a.href = url;
          a.download = `SAIL_MIS_Report_${selectedMonthName}_${selectedYear}.pdf`;
          document.body.appendChild(a);
          a.click();
          a.remove();
          window.URL.revokeObjectURL(url);
        },
        onError: (error) => {
          console.error(error);
          alert(`PDF generation failed: ${error.message}`);
        },
      }
    );
  };

  return (
    <>
      {/* Global Navbar */}
      <GlobalNavbar />

      <main className="app-container">
      {/* Sidebar Control Panel - Customized for Report Only */}
      <div className="sidebar no-print">
        <div className="sidebar-header">
          <h1>
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" style={{ color: 'var(--primary)' }}>
              <path d="M14.5 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7.5L14.5 2z" />
              <polyline points="14 2 14 8 20 8" />
            </svg>
            Report Engine
          </h1>
          <p>Viewer & Editor</p>
        </div>

        {/* Report Selector */}
        <div className="control-section">
          <h2>Report Configuration</h2>
          <div className="form-group">
            <label>Reporting Month & Year</label>
            <div style={{ display: 'flex', gap: '8px' }}>
              <select
                className="form-control"
                style={{ flex: 2 }}
                value={selectedMonthName}
                onChange={(e) => setSelectedMonthName(e.target.value)}
              >
                {months.map((m) => (
                  <option key={m} value={m}>{m}</option>
                ))}
              </select>
              <select
                className="form-control"
                style={{ flex: 1 }}
                value={selectedYear}
                onChange={(e) => setSelectedYear(e.target.value)}
              >
                {years.map((y) => (
                  <option key={y} value={y}>{y}</option>
                ))}
              </select>
            </div>
          </div>
        </div>

        {/* Page Navigation */}
        <div className="control-section">
          <h2>Page Selector</h2>
          <div className="form-group">
            <label>Navigate Report Pages ({pagesData.length} total)</label>
            <select
              className="form-control"
              value={activePageNum}
              onChange={(e) => setActivePageNum(Number(e.target.value))}
            >
              {pagesData.map((page) => (
                <option key={page.page} value={page.page}>
                  {page.page}. {PAGE_LABELS[page.page] || page.title || 'Page ' + page.page}
                </option>
              ))}
            </select>
          </div>
          
          <div style={{ display: 'flex', gap: '8px', marginTop: '10px' }}>
            <button
              className="btn btn-secondary"
              style={{ flex: 1, margin: 0 }}
              onClick={() => setActivePageNum((prev) => Math.max(1, prev - 1))}
              disabled={activePageNum === 1}
            >
              Previous
            </button>
            <button
              className="btn btn-secondary"
              style={{ flex: 1, margin: 0 }}
              onClick={() => setActivePageNum((prev) => Math.min(pagesData.length, prev + 1))}
              disabled={activePageNum === pagesData.length}
            >
              Next
            </button>
          </div>

          <div className="form-group" style={{ marginTop: '12px' }}>
            <label>Page Orientation</label>
            <select
              className="form-control"
              value={activePage?.orientation || 'portrait'}
              onChange={(e) => {
                if (!activePage) return;
                const newOrientation = e.target.value;
                handleCellChange({
                  ...activePage,
                  orientation: newOrientation
                });
              }}
              disabled={!activePage}
            >
              <option value="portrait">Portrait</option>
              <option value="landscape">Landscape</option>
            </select>
          </div>
        </div>

        {/* Typography and Layout Settings — now configured via backend layout_config.json only */}
        <div className="control-section">
          <h2>Layout & Typography</h2>
          <p style={{ fontSize: '0.8rem', color: '#94a3b8', lineHeight: '1.4' }}>
            Font sizes, margins, and layout settings are now configured in the backend <code style={{ backgroundColor: '#1e293b', padding: '2px 6px', borderRadius: '3px', fontFamily: 'monospace', fontSize: '0.75rem' }}>layout_config.json</code> file.
          </p>
          <p style={{ fontSize: '0.8rem', color: '#94a3b8', lineHeight: '1.4', marginTop: '8px' }}>
            Edit that file to customize per-page layouts and global typography, then regenerate the PDF.
          </p>
        </div>

        {/* Database Actions */}
        <div className="control-section">
          <h2>Database Actions</h2>
          <button
            className="btn btn-primary"
            onClick={handleSaveToDatabase}
            disabled={isSaving}
            style={{ width: '100%' }}
          >
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" style={{ marginRight: '8px', verticalAlign: 'middle' }}>
              <path d="M19 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11l5 5v11a2 2 0 0 1-2 2z" />
              <polyline points="17 21 17 13 7 13 7 21" />
              <polyline points="7 3 7 8 15 8" />
            </svg>
            {isSaving ? 'Saving...' : 'Save Changes to DB'}
          </button>
        </div>

        {/* Export triggers */}
        <div className="control-section">
          <h2>Export Actions</h2>
          <button
            className="btn btn-secondary"
            onClick={handleBackendExport}
            disabled={isGeneratingPDF}
            style={{ borderColor: 'var(--primary)', color: '#38bdf8' }}
          >
            {isGeneratingPDF ? (
              'Compiling PDF Backend...'
            ) : (
              <>
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
                  <polyline points="7 10 12 15 17 10" />
                  <line x1="12" y1="15" x2="12" y2="3" />
                </svg>
                Export PDF (Python API)
              </>
            )}
          </button>
        </div>

        <div style={{ marginTop: 'auto', fontSize: '0.75rem', color: '#64748b', textAlign: 'center' }}>
          SAIL Informatics Report Portal • v1.0.0
        </div>
      </div>

      {/* Main Preview Area */}
      <div className="preview-area">
        {isLoading ? (
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%', color: '#64748b', fontSize: '1.2rem', fontWeight: '500' }}>
            <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '12px' }}>
              <style>{`
                @keyframes spin {
                  to { transform: rotate(360deg); }
                }
              `}</style>
              <div className="spinner" style={{ width: '40px', height: '40px', border: '4px solid #cbd5e1', borderTopColor: 'var(--primary)', borderRadius: '50%', animation: 'spin 1s linear infinite' }} />
              Loading database report data...
            </div>
          </div>
        ) : (
          <PageRenderer
            pageData={activePage}
            onCellChange={handleCellChange}
            selectedMonth={selectedMonth}
            totalPages={pagesData.length}
          />
        )}
      </div>
    </main>
    </>
  );
}

