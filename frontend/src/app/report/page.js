'use client';

import React, { useState, useEffect, useMemo, useRef } from 'react';
import GlobalNavbar from '@/components/GlobalNavbar';
import PageRenderer from '../../components/PageRenderer';
import { useReportData, useReportPage, useGeneratePDF } from '@/hooks/useReportAPI';

// Edit these labels to change what appears in the Page Selector dropdown
const PAGE_LABELS = {
   1: 'Cover Page',
   2: 'Index / Contents',
   2.1: 'Indian Steel Sector Performance — Production & Prices',
   2.2: 'Indian Steel Sector Performance — Demand, Trade, Raw Materials & Key Indices',
   2.3: 'Indian Steel Sector Performance — Policy & Green Steel Initiatives',
   2.5: 'SAIL Performance - At a Glance',
   3: 'SAIL Performance - 1 Page Summary',
   3.2: 'Production Highlights - Best-Ever Records',
   3.3: 'Production Highlights - Best Calendar Month',
   3.5: 'Inter Plant Performance Comparison',
   3.6: 'SAIL Large BFs - Performance Snapshot',
   3.61: 'Cost Trend – Hot Metal',
   3.62: 'Cost Trend – Crude Steel',
   3.63: 'Cost Trend – Saleable Steel',
   4: 'Plant Wise Performance of Main Items (w.r.t. ABP)',
   4.5: 'SAIL Mines Production & Despatch Performance',
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
  23: 'Special Steel – ISP + SAIL (Consolidated)',
  24: 'Special Steel – Saleable/Value-Added Share (Donut)',
  1025: 'Special Steel Plants Physical Performance',
  25: 'Opening Stock at Plants & Stockyards',
  26: 'IPT Status',
  27: 'Major Techno-Economic Parameters',
  28: 'Techno – Coke & Coal Chemicals, Sinter',
  29: 'Techno – Iron Making',
  29.5: 'Techno – Iron Making (contd.)',
  30: 'Techno – SMS Shop',
  31: 'Mill Wise Techno – BSP',
  32: 'Mill Wise Techno – DSP',
  33: 'Mill Wise Techno – RSP',
  34: 'Mill Wise Techno – BSL',
  35: 'Mill Wise Techno – ISP',
  35.4: 'Major Environmental Performance Indicators (EPIs)',
  35.5: 'Consumption of Coking Coal and CDI Coal',
  35.6: 'Receipt, Consumption & Stocks of Coking Coal',
  35.7: 'Monthly Summary of Power Data',
  36: 'Capital Repair – BSP',
  37: 'Capital Repair – DSP',
  38: 'Capital Repair – RSP',
  39: 'Capital Repair – BSL',
  40: 'Capital Repair – ISP',
};

// Page list/count is fixed regardless of report month, so the page selector
// and PDF checklist can render from this immediately — they don't need to
// wait on any report data to load.
//
// Sort key ≠ id for the big-int sentinels: SS Physical Performance keeps its
// backend id 1025 (that's what /api/data?page_number= expects and what the
// page object comes back tagged with), but physically sits right after
// page 24, so it's sorted there — not after page 40. Same slot the Special
// Steel trend sentinel (1024) would take if it were ever surfaced here.
const _PAGE_SORT_POS = { 1024: 24.5, 1025: 24.6 };
const _pageSortPos = (n) => _PAGE_SORT_POS[n] ?? n;
const ALL_PAGE_NUMBERS = Object.keys(PAGE_LABELS).map(Number).sort((a, b) => _pageSortPos(a) - _pageSortPos(b));

// Internal page ids include sentinel decimals (e.g. 2.5 for "MIS at a
// Glance", 3.5 for "Key Parameters") so they can be inserted between real
// pages without renumbering the rest of the report — but showing "2.5. MIS
// at a Glance" in the UI is confusing since the actual printed PDF numbers
// these pages 1, 2, 3, 4... in plain sequence (Chromium's own page counter,
// driven by physical page order, not by this id). This map gives every
// page id its plain sequential display position so the selector/checklist
// show the same continuous numbering the PDF does, while `value=`/routing
// everywhere else keeps using the real internal id.
const PAGE_DISPLAY_NUMBER = Object.fromEntries(ALL_PAGE_NUMBERS.map((n, i) => [n, i + 1]));

const months = [
  'January', 'February', 'March', 'April', 'May', 'June',
  'July', 'August', 'September', 'October', 'November', 'December'
];

const MONTH_NUM = {
  'January': '01', 'February': '02', 'March': '03', 'April': '04',
  'May': '05', 'June': '06', 'July': '07', 'August': '08',
  'September': '09', 'October': '10', 'November': '11', 'December': '12',
};

const YEAR_RANGE_START = 2000;
const _now = new Date();
// FY start year: Apr..Dec -> this calendar year; Jan..Mar -> previous calendar year
const CURRENT_FY_END_YEAR = (_now.getMonth() >= 3 ? _now.getFullYear() : _now.getFullYear() - 1) + 1;

// Calendar years: 2000 through the current FY's end year (covers Jan-Mar
// report months that fall in the current FY but the next calendar year).
const years = Array.from(
  { length: CURRENT_FY_END_YEAR - YEAR_RANGE_START + 1 },
  (_, i) => (YEAR_RANGE_START + i).toString()
);

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

    // Capital Repair pages (36-40) and "Monthly Summary of Power Data"
    // (35.7) already carry the correct FY computed server-side from the
    // report month — running them through the generic date-shift regex on
    // top of that double-applies the shift and corrupts the year (and can
    // mangle schedule/period text like "7-15").
    if ((page.page >= 36 && page.page <= 40) || page.type === 'power_data') {
      return page;
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

const getDefaultDate = () => {
  const d = new Date(Date.now() - 45 * 24 * 60 * 60 * 1000);
  return {
    month: months[d.getMonth()],
    year: d.getFullYear().toString()
  };
};

// Applies the page===4/5/6 type overrides the raw API response needs before
// display. Shared by the per-page fast path and the full-fetch export path.
function normalizePageTypes(pages) {
  return pages.map((p) => {
    if (p.page === 4) return { ...p, type: 'page4_table' };
    if (p.page === 5 || p.page === 6) return { ...p, type: 'performance_summary_table' };
    return p;
  });
}

export default function ReportPage() {
  const defaultDate = getDefaultDate();
  // Pages load lazily, one at a time, as the user views/edits/exports them —
  // this accumulates whatever has been fetched so far for the CURRENT
  // selectedMonth (wiped and rebuilt whenever the month changes).
  const [pagesData, setPagesData] = useState([]);
  const [activePageNum, setActivePageNum] = useState(1);
  const [selectedMonthName, setSelectedMonthName] = useState(defaultDate.month);
  const [selectedYear, setSelectedYear] = useState(defaultDate.year);
  const [selectedPages, setSelectedPages] = useState(new Set(ALL_PAGE_NUMBERS));
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [isPreparingExport, setIsPreparingExport] = useState(false);

  const selectedMonth = `${selectedYear}-${MONTH_NUM[selectedMonthName]}`;
  // Guards the async export flow below against a month change landing mid-
  // flight (the full-fetch it awaits can take 20-40s) — without this, a
  // slow fetch for month A resolving after the user has already switched to
  // month B would inject month A's pages into month B's pagesData.
  const selectedMonthRef = useRef(selectedMonth);
  useEffect(() => { selectedMonthRef.current = selectedMonth; }, [selectedMonth]);

  // Ctrl+B (Cmd+B on Mac) toggles the sidebar, same convention as most IDEs.
  useEffect(() => {
    const handleKeyDown = (e) => {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'b') {
        e.preventDefault();
        setSidebarCollapsed((prev) => !prev);
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, []);

  // Switching months invalidates every previously-loaded page.
  useEffect(() => {
    setPagesData([]);
  }, [selectedMonth]);

  // Default the PDF export selection to "all pages" whenever the month changes.
  useEffect(() => {
    setSelectedPages(new Set(ALL_PAGE_NUMBERS));
  }, [selectedMonth]);

  const isActivePageLoaded = pagesData.some((p) => p.page === activePageNum);

  // Fast path: only the page currently on screen. Each page's data only
  // depends on its own DB calls server-side (~1s typical), so this is what
  // makes switching months/pages responsive instead of waiting 20-40s for
  // every page. Disabled once the page is already in pagesData so revisiting
  // an already-loaded (and possibly locally-edited) page never refetches
  // over it.
  const { data: activePageRaw, error: activePageError } =
    useReportPage(selectedMonth, activePageNum, { enabled: !isActivePageLoaded });

  // Slow path: every page at once. Not fetched automatically — only pulled
  // on demand when exporting a page that hasn't been viewed yet (see
  // handleBackendExport below).
  const { refetch: refetchFullData } = useReportData(selectedMonth, { enabled: false });

  const { mutate: generatePDF, isPending: isGeneratingPDF } = useGeneratePDF();

  // Full reports now take 20+ minutes to render (see useGeneratePDF — the
  // job runs on the backend, decoupled from any request timeout), so the
  // button needs to show it's still alive rather than just sitting on
  // static "Compiling..." text with no feedback for that whole time.
  const [pdfElapsedSec, setPdfElapsedSec] = useState(0);
  useEffect(() => {
    if (!isGeneratingPDF) {
      setPdfElapsedSec(0);
      return;
    }
    const startedAt = Date.now();
    const interval = setInterval(() => {
      setPdfElapsedSec(Math.floor((Date.now() - startedAt) / 1000));
    }, 1000);
    return () => clearInterval(interval);
  }, [isGeneratingPDF]);

  // Merge the active page into pagesData once it arrives. Skipped if already
  // present (see the `enabled` guard above for why that matters).
  useEffect(() => {
    if (!activePageRaw) return;
    setPagesData((prev) => {
      if (prev.some((p) => p.page === activePageRaw.page)) return prev;
      const [formatted] = getFormattedPagesData(
        normalizePageTypes([activePageRaw]), selectedMonthName, selectedYear, 'November', '2025'
      );
      return [...prev, formatted];
    });
  }, [activePageRaw, selectedMonthName, selectedYear]);

  const activePage = useMemo(
    () => pagesData.find((p) => p.page === activePageNum),
    [pagesData, activePageNum]
  );

  const togglePageSelection = (pageNum) => {
    setSelectedPages((prev) => {
      const next = new Set(prev);
      if (next.has(pageNum)) next.delete(pageNum);
      else next.add(pageNum);
      return next;
    });
  };

  const selectAllPages = () => setSelectedPages(new Set(ALL_PAGE_NUMBERS));
  const selectNoPages = () => setSelectedPages(new Set());

  const handleCellChange = (updatedPageData) => {
    setPagesData((prev) =>
      prev.map((p) => (p.page === updatedPageData.page ? updatedPageData : p))
    );
  };

  const handleBackendExport = async () => {
    const exportMonth = selectedMonth;
    let dataForExport;

    setIsPreparingExport(true);
    try {
      // Always re-fetch the full page list rather than trusting pagesData's
      // own array order for sequencing. pagesData accumulates pages in
      // whichever order the user happened to view them in (or in whatever
      // order a previous export left it in) — not document order — so
      // spreading it first (or using it directly when nothing was
      // "missing") put whatever was already loaded at the front of the
      // exported PDF regardless of its real page number (e.g. pages 24/25
      // landing right after the Index because they'd been individually
      // viewed earlier). The full fetch is always correctly ordered
      // server-side, so it's the only reliable source of export order;
      // pagesData is still consulted below, but only to carry forward
      // local edits not yet saved, never for sequencing.
      const { data: fullRawData } = await refetchFullData();
      if (!fullRawData) {
        alert('Failed to load report data for export.');
        return;
      }
      // The month may have changed while this (slow, 20-40s) fetch was in
      // flight — its result belongs to exportMonth, not necessarily
      // whatever's on screen now, so only fold it into live pagesData
      // state if the two still match. Either way, the export itself below
      // still uses the correct exportMonth data via dataForExport.
      const formatted = getFormattedPagesData(
        normalizePageTypes(fullRawData), selectedMonthName, selectedYear, 'November', '2025'
      );
      const localByPage = new Map(pagesData.map((p) => [p.page, p]));
      dataForExport = formatted.map((p) => localByPage.get(p.page) || p);
      if (selectedMonthRef.current === exportMonth) {
        setPagesData(dataForExport);
      }
    } finally {
      setIsPreparingExport(false);
    }

    const pagesToExport = dataForExport.filter((p) => selectedPages.has(p.page));
    if (pagesToExport.length === 0) {
      alert('Select at least one page to export.');
      return;
    }
    generatePDF(
      { month: selectedMonth, pages: pagesToExport },
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
      <div className={`sidebar no-print${sidebarCollapsed ? ' collapsed' : ''}`}>
        <div className="sidebar-header">
          {!sidebarCollapsed && (
            <div>
              <h1>
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" style={{ color: 'var(--primary)' }}>
                  <path d="M14.5 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7.5L14.5 2z" />
                  <polyline points="14 2 14 8 20 8" />
                </svg>
                Report Engine
              </h1>
              <p>Viewer &amp; Editor</p>
            </div>
          )}
          <button
            type="button"
            className="sidebar-toggle-btn"
            onClick={() => setSidebarCollapsed((prev) => !prev)}
            title={`${sidebarCollapsed ? 'Expand' : 'Collapse'} sidebar (Ctrl+B)`}
            aria-label={sidebarCollapsed ? 'Expand sidebar' : 'Collapse sidebar'}
          >
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"
                 style={{ transform: sidebarCollapsed ? 'rotate(180deg)' : 'none', transition: 'transform 0.15s ease' }}>
              <polyline points="15 18 9 12 15 6" />
            </svg>
          </button>
        </div>

        {!sidebarCollapsed && (
        <>
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
            <label>Navigate Report Pages ({ALL_PAGE_NUMBERS.length} total)</label>
            <select
              className="form-control"
              value={activePageNum}
              onChange={(e) => setActivePageNum(Number(e.target.value))}
            >
              {ALL_PAGE_NUMBERS.map((pageNum) => (
                <option key={pageNum} value={pageNum}>
                  {PAGE_DISPLAY_NUMBER[pageNum]}. {PAGE_LABELS[pageNum] || 'Page ' + pageNum}
                </option>
              ))}
            </select>
          </div>

          <div style={{ display: 'flex', gap: '8px', marginTop: '10px' }}>
            <button
              className="btn btn-secondary"
              style={{ flex: 1, margin: 0 }}
              onClick={() => setActivePageNum((prev) => {
                const idx = ALL_PAGE_NUMBERS.indexOf(prev);
                return ALL_PAGE_NUMBERS[Math.max(0, idx - 1)];
              })}
              disabled={ALL_PAGE_NUMBERS.indexOf(activePageNum) <= 0}
            >
              Previous
            </button>
            <button
              className="btn btn-secondary"
              style={{ flex: 1, margin: 0 }}
              onClick={() => setActivePageNum((prev) => {
                const idx = ALL_PAGE_NUMBERS.indexOf(prev);
                return ALL_PAGE_NUMBERS[Math.min(ALL_PAGE_NUMBERS.length - 1, idx + 1)];
              })}
              disabled={ALL_PAGE_NUMBERS.indexOf(activePageNum) === ALL_PAGE_NUMBERS.length - 1}
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

        {/* PDF Export — Page Selection */}
        <div className="control-section">
          <h2>PDF Export — Page Selection</h2>
          <div style={{ display: 'flex', gap: '8px', marginBottom: '10px' }}>
            <button
              type="button"
              className="btn btn-secondary"
              style={{ flex: 1, margin: 0 }}
              onClick={selectAllPages}
            >
              Select All
            </button>
            <button
              type="button"
              className="btn btn-secondary"
              style={{ flex: 1, margin: 0 }}
              onClick={selectNoPages}
            >
              Select None
            </button>
          </div>
          <div
            style={{
              maxHeight: '260px',
              overflowY: 'auto',
              border: '1px solid #dadce0',
              borderRadius: '6px',
              padding: '4px 8px',
            }}
          >
            {ALL_PAGE_NUMBERS.map((pageNum) => (
              <label
                key={pageNum}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '8px',
                  fontSize: '0.8rem',
                  padding: '4px 0',
                  cursor: 'pointer',
                }}
              >
                <input
                  type="checkbox"
                  checked={selectedPages.has(pageNum)}
                  onChange={() => togglePageSelection(pageNum)}
                />
                {PAGE_DISPLAY_NUMBER[pageNum]}. {PAGE_LABELS[pageNum] || 'Page ' + pageNum}
              </label>
            ))}
          </div>
          <div style={{ fontSize: '0.75rem', color: '#5f6368', marginTop: '6px' }}>
            {selectedPages.size} of {ALL_PAGE_NUMBERS.length} pages selected
          </div>
        </div>

        {/* Export triggers */}
        <div className="control-section">
          <h2>Export Actions</h2>
          <button
            className="btn btn-secondary"
            onClick={handleBackendExport}
            disabled={isGeneratingPDF || isPreparingExport}
            style={{ borderColor: 'var(--primary)', color: '#1a73e8' }}
          >
            {isGeneratingPDF ? (
              `Compiling PDF Backend... (${String(Math.floor(pdfElapsedSec / 60)).padStart(1, '0')}:${String(pdfElapsedSec % 60).padStart(2, '0')})`
            ) : isPreparingExport ? (
              'Preparing export…'
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

        <div style={{ marginTop: 'auto', fontSize: '0.75rem', color: '#5f6368', textAlign: 'center' }}>
          SAIL Informatics Report Portal • v1.0.0
        </div>
        </>
        )}
      </div>

      {/* Main Preview Area */}
      <div className="preview-area">
        {!activePage ? (
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%', color: '#5f6368', fontSize: '1.2rem', fontWeight: '500' }}>
            <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '12px' }}>
              <style>{`
                @keyframes spin {
                  to { transform: rotate(360deg); }
                }
              `}</style>
              <div className="spinner" style={{ width: '40px', height: '40px', border: '4px solid #dadce0', borderTopColor: 'var(--primary)', borderRadius: '50%', animation: 'spin 1s linear infinite' }} />
              {activePageError ? `Failed to load page ${PAGE_DISPLAY_NUMBER[activePageNum]}` : `Loading page ${PAGE_DISPLAY_NUMBER[activePageNum]}...`}
            </div>
          </div>
        ) : (
          <PageRenderer
            pageData={activePage}
            onCellChange={handleCellChange}
            selectedMonth={selectedMonth}
            totalPages={ALL_PAGE_NUMBERS.length}
            displayPageNumber={PAGE_DISPLAY_NUMBER[activePageNum] - 2}
          />
        )}
      </div>
    </main>
    </>
  );
}

