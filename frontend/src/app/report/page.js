'use client';

import React, { useState, useEffect } from 'react';
import Link from 'next/link';
import PageRenderer from '../../components/PageRenderer';

// Edit these labels to change what appears in the Page Selector dropdown
const PAGE_LABELS = {
   1: 'Cover Page',
   2: 'Index / Contents',
   3: 'SAIL Performance Summary',
   4: 'Production Performance vs APP (Month)',
   5: 'Plant-Wise Production Performance',
   6: 'Plant-Wise Production (Month & YTD)',
   7: 'Month-Wise Trend – Oven Pushing',
   8: 'Month-Wise Trend – Sinter',
   9: 'Month-Wise Trend – Hot Metal',
  10: 'Month-Wise Trend – Pig Iron',
  11: 'Month-Wise Trend – Crude Steel',
  12: 'Month-Wise Trend – Saleable Steel',
  13: 'Month-Wise Trend – Finished Steel',
  14: 'Plant-Wise Production Performance (Detailed)',
  15: 'Production by Process (BOF / EAF / CC)',
  16: 'Category-Wise Production – BSP (Bhilai)',
  17: 'Category-Wise Production – DSP (Durgapur)',
  18: 'Category-Wise Production – BSL (Bokaro)',
  19: 'Category-Wise Production – RSP (Rourkela)',
  20: 'Despatches & Orders – Rails',
  21: 'Despatches & Orders – Structural / TLT',
  22: 'Despatches & Orders – Export',
  23: 'Despatches & Orders – Plates',
  24: 'Despatches & Orders – By Item',
  25: 'Despatches & Orders – By Plant',
  26: 'Opening Stock at SAIL Plants & Stockyards',
  27: 'Raw Material Movement',
  28: 'Major Techno-Economic Parameters',
  29: 'Month-Wise TE Parameters – Coke & Sinter',
  30: 'Month-Wise TE Parameters – Blast Furnace',
  31: 'Month-Wise TE Parameters – BOF Shop',
  32: 'Mill-Wise TE Parameters – BSP (Bhilai)',
  33: 'Mill-Wise TE Parameters – DSP (Durgapur)',
  34: 'Mill-Wise TE Parameters – RSP (Rourkela)',
  35: 'Mill-Wise TE Parameters – BSL (Bokaro)',
  36: 'Mill-Wise TE Parameters – ISP (IISCO)',
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

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || '';
console.log('API_BASE_URL:', API_BASE_URL);

// In browser environments, failing to fetch is often due to CORS/origin/host reachability.
// Add a lightweight timeout so the user sees faster feedback in DevTools.
const fetchWithTimeout = (url, options = {}, timeoutMs = 8000) => {
  return new Promise((resolve, reject) => {
    const ctrl = new AbortController();
    const t = setTimeout(() => {
      ctrl.abort();
      reject(new Error(`Request timed out after ${timeoutMs}ms: ${url}`));
    }, timeoutMs);
    fetch(url, { ...options, signal: ctrl.signal })
      .then((res) => {
        clearTimeout(t);
        resolve(res);
      })
      .catch((err) => {
        clearTimeout(t);
        reject(err);
      });
  });
};

const getDefaultDate = () => {
  const d = new Date();
  d.setMonth(d.getMonth() - 2);
  return {
    month: months[d.getMonth()],
    year: d.getFullYear().toString()
  };
};

export default function ReportPage() {
  const defaultDate = getDefaultDate();
  const [pagesData, setPagesData] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [activePageNum, setActivePageNum] = useState(1);
  const [selectedMonthName, setSelectedMonthName] = useState(defaultDate.month);
  const [selectedYear, setSelectedYear] = useState(defaultDate.year);
  const [pagesDataMonth, setPagesDataMonth] = useState({ name: defaultDate.month, year: defaultDate.year });
  const [isBackendGenerating, setIsBackendGenerating] = useState(false);

  const selectedMonth = `${selectedYear}-${MONTH_NUM[selectedMonthName]}`;
  const activePage = pagesData.find((p) => p.page === activePageNum) || pagesData[0];

  // Fetch report data dynamically from DB when month/year changes
  useEffect(() => {
    let active = true;
    const loadReportData = async () => {
      setIsLoading(true);
      try {
        const response = await fetchWithTimeout(
          `${API_BASE_URL}/api/data?month=${encodeURIComponent(selectedMonth)}`
        );
        if (response.ok) {
          const data = await response.json();
          if (active) {
            const normalized = data.map((p) => {
              if (p.page === 4) return { ...p, type: 'page4_table' };
              if (p.page === 5 || p.page === 6) return { ...p, type: 'performance_summary_table' };
              return p;
            });
            const formatted = getFormattedPagesData(normalized, selectedMonthName, selectedYear, 'November', '2025');
            setPagesData(formatted.filter((p) => p.page <= 36));
            setPagesDataMonth({ name: selectedMonthName, year: selectedYear });
          }
        }
      } catch (err) {
        console.error("Failed to load data from SQLite database:", err);
      } finally {
        if (active) setIsLoading(false);
      }
    };
    loadReportData();
    return () => { active = false; };
  }, [selectedMonthName, selectedYear]);

  const handleSaveToDatabase = async () => {
    try {
      const response = await fetch(`${API_BASE_URL}/api/data`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          month: selectedMonth,
          pages: pagesData,
        }),
      });

      if (!response.ok) {
        throw new Error('Failed to save report data');
      }
      alert('Changes saved successfully to SQLite database!');
    } catch (error) {
      console.error(error);
      alert('Error saving data to SQLite database. Ensure backend is running.');
    }
  };

  const handleCellChange = (updatedPageData) => {
    setPagesData((prev) =>
      prev.map((p) => (p.page === updatedPageData.page ? updatedPageData : p))
    );
  };

  const handleBackendExport = async () => {
    setIsBackendGenerating(true);
    try {
      const response = await fetch(`${API_BASE_URL}/api/generate-pdf`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          month: selectedMonth,
          pages: pagesData,
        }),
      });

      if (!response.ok) {
        const errBody = await response.json().catch(() => ({}));
        throw new Error(errBody.error || `HTTP ${response.status}`);
      }

      const blob = await response.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `SAIL_MIS_Report_${selectedMonthName}_${selectedYear}.pdf`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      window.URL.revokeObjectURL(url);
    } catch (error) {
      console.error(error);
      alert(`PDF generation failed: ${error.message}`);
    } finally {
      setIsBackendGenerating(false);
    }
  };

  return (
    <main className="app-container">
      {/* Sidebar Control Panel */}
      <div className="sidebar no-print">
        <div className="sidebar-header">
          <h1>
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" style={{ color: 'var(--primary)' }}>
              <path d="M14.5 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7.5L14.5 2z" />
              <polyline points="14 2 14 8 20 8" />
            </svg>
            SAIL MIS Portal
          </h1>
          <p>Report Viewer & Editor</p>
        </div>

        {/* Navigation Section */}
        <div className="control-section">
          <h2>Navigation</h2>
          <Link href="/" className="btn btn-secondary" style={{ width: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '8px', marginBottom: '8px', textDecoration: 'none' }}>
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <line x1="19" y1="12" x2="5" y2="12" />
              <polyline points="12 19 5 12 12 5" />
            </svg>
            Back to Dashboard
          </Link>
          <Link href="/upload" className="btn btn-secondary" style={{ width: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '8px', textDecoration: 'none', borderColor: 'var(--primary)' }}>
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
              <polyline points="17 8 12 3 7 8" />
              <line x1="12" y1="3" x2="12" y2="15" />
            </svg>
            Excel Ingestion
          </Link>
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
              onClick={() => setActivePageNum((prev) => Math.min(36, pagesData.length, prev + 1))}
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

        {/* Database Actions */}
        <div className="control-section">
          <h2>Database Actions</h2>
          <button
            className="btn btn-primary"
            onClick={handleSaveToDatabase}
            style={{ width: '100%' }}
          >
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" style={{ marginRight: '8px', verticalAlign: 'middle' }}>
              <path d="M19 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11l5 5v11a2 2 0 0 1-2 2z" />
              <polyline points="17 21 17 13 7 13 7 21" />
              <polyline points="7 3 7 8 15 8" />
            </svg>
            Save Changes to DB
          </button>
        </div>

        {/* Export triggers */}
        <div className="control-section">
          <h2>Export Actions</h2>
          <button
            className="btn btn-secondary"
            onClick={handleBackendExport}
            disabled={isBackendGenerating}
            style={{ borderColor: 'var(--primary)', color: '#38bdf8' }}
          >
            {isBackendGenerating ? (
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
  );
}
