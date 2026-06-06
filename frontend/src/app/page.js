'use client';

import React, { useState, useEffect } from 'react';
import PageRenderer from '../components/PageRenderer';
import initialPagesData from '../data/mis_data.json';

const months = [
  'January', 'February', 'March', 'April', 'May', 'June',
  'July', 'August', 'September', 'October', 'November', 'December'
];

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
  
  // 1. Shift financial year patterns (e.g. 2025-26 -> 2026-27)
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
  
  // 2. Replace years
  result = result.replace(new RegExp(oldYear, 'g'), newYear);
  result = result.replace(new RegExp(oldPrevYearNum.toString(), 'g'), newPrevYearNum.toString());
  
  // 3. Replace Month names (case variations)
  result = result.replace(new RegExp(oldMonth, 'g'), newMonth);
  result = result.replace(new RegExp(oldMonth.toLowerCase(), 'g'), newMonth.toLowerCase());
  result = result.replace(new RegExp(oldMonth.toUpperCase(), 'g'), newMonth.toUpperCase());
  
  result = result.replace(new RegExp(oldShortMonth, 'g'), newShortMonth);
  result = result.replace(new RegExp(oldShortMonth.toLowerCase(), 'g'), newShortMonth.toLowerCase());
  result = result.replace(new RegExp(oldShortMonth.toUpperCase(), 'g'), newShortMonth.toUpperCase());
  
  // 4. Short year references
  result = result.replace(new RegExp(`'${oldShortYear}`, 'g'), `'${newShortYear}`);
  result = result.replace(new RegExp(`'${oldShortPrevYear}`, 'g'), `'${newShortPrevYear}`);
  
  return result;
}

function getFormattedPagesData(pages, newMonth, newYear, oldMonth, oldYear) {
  return pages.map((page) => {
    // 1. Cover page
    if (page.page === 1) {
      return {
        ...page,
        date: `${newMonth.toUpperCase()} ${newYear}`
      };
    }
    
    // 2. Summary page
    if (page.page === 3 || page.type === 'summary') {
      const shortYear = newYear.substring(2);
      return {
        ...page,
        subtitle: `${newMonth}’${shortYear}`
      };
    }
    
    // 3. Any table/trend/other page with titles/subtitles/headers that might need updating
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

export default function Home() {
  const [pagesData, setPagesData] = useState(() =>
    initialPagesData.map((p) => {
      if (p.page === 4) return { ...p, type: 'page4_table' };
      if (p.page === 5 || p.page === 6) return { ...p, type: 'performance_summary_table' };
      return p;
    })
  );
  const [activePageNum, setActivePageNum] = useState(1);
  const [selectedMonthName, setSelectedMonthName] = useState('November');
  const [selectedYear, setSelectedYear] = useState('2025');
  const [pagesDataMonth, setPagesDataMonth] = useState({ name: 'November', year: '2025' });
  const [isBackendGenerating, setIsBackendGenerating] = useState(false);

  const selectedMonth = `${selectedMonthName} ${selectedYear}`;
  const activePage = pagesData.find((p) => p.page === activePageNum) || pagesData[0];

  useEffect(() => {
    const prevMonth = pagesDataMonth.name;
    const prevYear = pagesDataMonth.year;
    const newMonth = selectedMonthName;
    const newYear = selectedYear;
    
    if (prevMonth === newMonth && prevYear === newYear) return;
    
    setPagesData((prev) => getFormattedPagesData(prev, newMonth, newYear, prevMonth, prevYear));
    setPagesDataMonth({ name: newMonth, year: newYear });
  }, [selectedMonthName, selectedYear, pagesDataMonth]);

  const handleCellChange = (updatedPageData) => {
    setPagesData((prev) =>
      prev.map((p) => (p.page === updatedPageData.page ? updatedPageData : p))
    );
  };

  const handleBackendExport = async () => {
    setIsBackendGenerating(true);
    try {
      const response = await fetch('http://127.0.0.1:8082/api/generate-pdf', {
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
        throw new Error('Failed to generate PDF from Python backend');
      }

      // Download the PDF stream
      const blob = await response.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `SAIL_MIS_Report_${selectedMonth.replace(' ', '_')}.pdf`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      window.URL.revokeObjectURL(url);
    } catch (error) {
      console.error(error);
      alert('Error generating PDF on Python backend. Make sure the FastAPI server is running.');
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
          <p>Monthly Informatics Report Engine</p>
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
                  Page {page.page}: {page.title ? page.title.substring(0, 32) : 'Cover/Index'}
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
              value={activePage.orientation || 'portrait'}
              onChange={(e) => {
                const newOrientation = e.target.value;
                handleCellChange({
                  ...activePage,
                  orientation: newOrientation
                });
              }}
            >
              <option value="portrait">Portrait</option>
              <option value="landscape">Landscape</option>
            </select>
          </div>
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
        <PageRenderer
          pageData={activePage}
          onCellChange={handleCellChange}
          selectedMonth={selectedMonth}
          totalPages={pagesData.length}
        />
      </div>
    </main>
  );
}
