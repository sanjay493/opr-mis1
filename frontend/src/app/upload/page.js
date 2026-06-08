'use client';

import React, { useState, useEffect, useCallback } from 'react';
import Link from 'next/link';

const months = [
  'January', 'February', 'March', 'April', 'May', 'June',
  'July', 'August', 'September', 'October', 'November', 'December'
];

const years = Array.from({ length: 16 }, (_, i) => (2020 + i).toString());

const financialYears = Array.from({ length: 16 }, (_, i) => {
  const start = 2020 + i;
  const end = (start + 1) % 100;
  return `${start}-${end.toString().padStart(2, '0')}`;
});

const defaultFY = () => {
  const d = new Date();
  d.setMonth(d.getMonth() - 2);
  const year = d.getFullYear();
  const monthIdx = d.getMonth();
  const startYear = (monthIdx < 3) ? year - 1 : year;
  const endYear = (startYear + 1) % 100;
  return `${startYear}-${endYear.toString().padStart(2, '0')}`;
};

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || '';

const getDefaultDate = () => {
  const d = new Date();
  d.setMonth(d.getMonth() - 2);
  return {
    month: months[d.getMonth()],
    year: d.getFullYear().toString()
  };
};

export default function UploadPage() {
  const defaultDate = getDefaultDate();
  const [uploadPlantName, setUploadPlantName] = useState('RSP');
  const [uploadMonthName, setUploadMonthName] = useState(defaultDate.month);
  const [uploadYear, setUploadYear] = useState(defaultDate.year);
  const [uploadFile, setUploadFile] = useState(null);
  
  const [uploadPlanPlantName, setUploadPlanPlantName] = useState('RSP');
  const [uploadPlanFY, setUploadPlanFY] = useState(defaultFY());
  const [uploadPlanFile, setUploadPlanFile] = useState(null);
  
  const [isUploading, setIsUploading] = useState(false);
  const [logs, setLogs] = useState([
    { type: 'info', text: 'System ready. Select a spreadsheet and click "Extract Data".' }
  ]);
  const [extractionLog, setExtractionLog] = useState([]);

  const fetchExtractionLog = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE_URL}/api/extraction-log?limit=30`);
      if (res.ok) {
        const data = await res.json();
        setExtractionLog(data.logs || []);
      }
    } catch (_) {}
  }, []);

  useEffect(() => { fetchExtractionLog(); }, [fetchExtractionLog]);

  const addLog = (type, text) => {
    setLogs((prev) => [...prev, { type, text, time: new Date().toLocaleTimeString() }]);
  };

  const handleExcelUpload = async (e) => {
    e.preventDefault();
    if (!uploadFile) {
      alert("Please select an Excel file to upload.");
      return;
    }

    setIsUploading(true);
    const targetPeriod = `${uploadMonthName} ${uploadYear}`;
    
    setLogs([]);
    addLog('info', `Starting extraction job for ${uploadPlantName} (${targetPeriod})...`);
    addLog('info', `Validating spreadsheet: ${uploadFile.name} (${(uploadFile.size / 1024).toFixed(1)} KB)`);

    const formData = new FormData();
    formData.append("file", uploadFile);
    formData.append("plant_name", uploadPlantName);
    formData.append("month", targetPeriod);

    try {
      addLog('info', 'Uploading spreadsheet file to FastAPI backend...');
      const response = await fetch(`${API_BASE_URL}/api/upload-excel`, {
        method: "POST",
        body: formData,
      });

      const result = await response.json();
      if (response.ok) {
        addLog('success', `Excel file uploaded successfully!`);
        addLog('success', `Extractor Status: ${result.message}`);
        addLog('success', `Database table production_table updated. Extraction logged.`);
        fetchExtractionLog();
        alert(result.message || "Excel sheet parsed and extracted successfully!");
      } else {
        const errMsg = result.detail || "Database write failure.";
        addLog('error', `Data Extraction Failed: ${errMsg}`);
        alert(`Extraction failed: ${errMsg}`);
      }
    } catch (err) {
      console.error(err);
      addLog('error', `Connection Error: Backend server is not running at ${API_BASE_URL}.`);
      alert("An error occurred during upload. Ensure the backend server is running.");
    } finally {
      setIsUploading(false);
      setUploadFile(null);
      const fileInput = document.getElementById("excel-file-input");
      if (fileInput) fileInput.value = "";
    }
  };

  const handlePlanUpload = async (e) => {
    e.preventDefault();
    if (!uploadPlanFile) {
      alert("Please select a Plan Excel file to upload.");
      return;
    }

    setIsUploading(true);
    
    setLogs([]);
    addLog('info', `Starting ABP Plan extraction job for ${uploadPlanPlantName} (${uploadPlanFY})...`);
    addLog('info', `Validating plan spreadsheet: ${uploadPlanFile.name} (${(uploadPlanFile.size / 1024).toFixed(1)} KB)`);

    const formData = new FormData();
    formData.append("file", uploadPlanFile);
    formData.append("plant_name", uploadPlanPlantName);
    formData.append("financial_year", uploadPlanFY);

    try {
      addLog('info', 'Uploading plan spreadsheet file to FastAPI backend...');
      const response = await fetch(`${API_BASE_URL}/api/upload-excel-plan`, {
        method: "POST",
        body: formData,
      });

      const result = await response.json();
      if (response.ok) {
        addLog('success', `Plan Excel file uploaded and parsed successfully!`);
        addLog('success', `Extractor Status: ${result.message}`);
        addLog('success', `Database table production_plan_table successfully updated for all 12 months.`);
        alert(result.message || "Excel ABP targets parsed and extracted successfully!");
      } else {
        const errMsg = result.detail || "Database write failure.";
        addLog('error', `Plan Data Extraction Failed: ${errMsg}`);
        alert(`Plan extraction failed: ${errMsg}`);
      }
    } catch (err) {
      console.error(err);
      addLog('error', `Connection Error: Backend server is not running at ${API_BASE_URL}.`);
      alert("An error occurred during plan upload. Ensure the backend server is running.");
    } finally {
      setIsUploading(false);
      setUploadPlanFile(null);
      const fileInput = document.getElementById("plan-file-input");
      if (fileInput) fileInput.value = "";
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
          <p>Excel Ingestion Engine</p>
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
          <Link href="/report" className="btn btn-secondary" style={{ width: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '8px', textDecoration: 'none', borderColor: 'var(--primary)' }}>
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7.5L14.5 2z" />
              <polyline points="14 2 14 8 20 8" />
            </svg>
            Report Engine
          </Link>
        </div>

        {/* Excel Import Config form */}
        <div className="control-section">
          <h2>Extraction Settings</h2>
          <form onSubmit={handleExcelUpload}>
            <div className="form-group" style={{ marginBottom: '12px' }}>
              <label>Plant Source</label>
              <select
                className="form-control"
                value={uploadPlantName}
                onChange={(e) => setUploadPlantName(e.target.value)}
              >
                <option value="RSP">RSP</option>
                <option value="BSP">BSP</option>
                <option value="ISP">ISP</option>
                <option value="BSL">BSL</option>
                <option value="DSP">DSP</option>
                <option value="ASP">ASP (not yet supported)</option>
                <option value="SSP">SSP (not yet supported)</option>
                <option value="VISL">VISL (not yet supported)</option>
              </select>
            </div>

            <div className="form-group" style={{ marginBottom: '12px' }}>
              <label>Target Period</label>
              <div style={{ display: 'flex', gap: '6px' }}>
                <select
                  className="form-control"
                  style={{ flex: 2 }}
                  value={uploadMonthName}
                  onChange={(e) => setUploadMonthName(e.target.value)}
                >
                  {months.map((m) => (
                    <option key={m} value={m}>{m}</option>
                  ))}
                </select>
                <select
                  className="form-control"
                  style={{ flex: 1 }}
                  value={uploadYear}
                  onChange={(e) => setUploadYear(e.target.value)}
                >
                  {years.map((y) => (
                    <option key={y} value={y}>{y}</option>
                  ))}
                </select>
              </div>
            </div>

            <div className="form-group" style={{ marginBottom: '15px' }}>
              <label>
                Excel File&nbsp;
                {(uploadPlantName === 'BSP' || uploadPlantName === 'DSP') ? '(.xls — tab-separated)' : '(.xlsx)'}
              </label>
              <input
                id="excel-file-input"
                type="file"
                className="form-control"
                accept={(uploadPlantName === 'BSP' || uploadPlantName === 'DSP') ? '.xls' : '.xlsx'}
                style={{ padding: '4px', fontSize: '0.8rem' }}
                onChange={(e) => setUploadFile(e.target.files[0])}
              />
              {(uploadPlantName === 'BSP' || uploadPlantName === 'BSL' || uploadPlantName === 'DSP' || uploadPlantName === 'ISP') && (
                <div style={{ fontSize: '7.5pt', color: '#fbbf24', marginTop: '4px' }}>
                  {uploadPlantName === 'BSP'
                    ? 'Month auto-detected from cell N1 (sheet S1). Month selector ignored.'
                    : uploadPlantName === 'BSL'
                    ? 'Month auto-detected from cell O1 (sheet DPR). Month selector ignored.'
                    : uploadPlantName === 'DSP'
                    ? 'Month auto-detected from date in MCR-I header row. Month selector ignored.'
                    : 'Morning Report (DAILYREPORT1): month auto-detected from K5. Final Monthly (Maj Production Summ): set month above.'}
                </div>
              )}
            </div>

            <button
              type="submit"
              className="btn btn-primary"
              style={{ width: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center', backgroundColor: '#10b981', borderColor: '#10b981' }}
              disabled={isUploading}
            >
              {isUploading ? (
                "Extracting Data..."
              ) : (
                <>
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" style={{ marginRight: '8px' }}>
                    <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
                    <polyline points="17 8 12 3 7 8" />
                    <line x1="12" y1="3" x2="12" y2="15" />
                  </svg>
                  Extract Data
                </>
              )}
            </button>
          </form>
        </div>

        {/* ABP Plan Target Ingestion Form */}
        <div className="control-section" style={{ marginTop: '15px' }}>
          <h2>ABP Plan Target Ingestion</h2>
          <form onSubmit={handlePlanUpload}>
            <div className="form-group" style={{ marginBottom: '12px' }}>
              <label>Plant Source</label>
              <select
                className="form-control"
                value={uploadPlanPlantName}
                onChange={(e) => setUploadPlanPlantName(e.target.value)}
              >
                <option value="RSP">RSP (Steel Plant)</option>
                <option value="ISP">ISP (Steel Plant)</option>
                <option value="BSP">BSP (Steel Plant)</option>
                <option value="DSP">DSP (Steel Plant)</option>
                <option value="BSL">BSL (Steel Plant)</option>
                <option value="ASP_SSP_VISL">ASP / SSP / VISL (combined file)</option>
              </select>
            </div>

            <div className="form-group" style={{ marginBottom: '12px' }}>
              <label>Financial Year</label>
              <select
                className="form-control"
                value={uploadPlanFY}
                onChange={(e) => setUploadPlanFY(e.target.value)}
              >
                {financialYears.map((fy) => (
                  <option key={fy} value={fy}>{fy}</option>
                ))}
              </select>
            </div>

            <div className="form-group" style={{ marginBottom: '15px' }}>
              <label>ABP Excel File (.xlsx)</label>
              <input
                id="plan-file-input"
                type="file"
                className="form-control"
                accept=".xlsx"
                style={{ padding: '4px', fontSize: '0.8rem' }}
                onChange={(e) => setUploadPlanFile(e.target.files[0])}
              />
            </div>

            <button
              type="submit"
              className="btn btn-primary"
              style={{ width: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center', backgroundColor: '#3b82f6', borderColor: '#3b82f6' }}
              disabled={isUploading}
            >
              {isUploading ? (
                "Extracting Plan..."
              ) : (
                <>
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" style={{ marginRight: '8px' }}>
                    <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
                    <polyline points="17 8 12 3 7 8" />
                    <line x1="12" y1="3" x2="12" y2="15" />
                  </svg>
                  Extract Plan Targets
                </>
              )}
            </button>
          </form>
        </div>

        <div style={{ marginTop: 'auto', fontSize: '0.75rem', color: '#64748b', textAlign: 'center', paddingTop: '15px' }}>
          SAIL Informatics Report Portal • v1.0.0
        </div>
      </div>

      {/* Ingestion Console Screen */}
      <div className="preview-area" style={{ padding: '30px', backgroundColor: '#0f172a', overflowY: 'auto' }}>
        <div style={{ maxWidth: '800px', margin: '0 auto', display: 'flex', flexDirection: 'column', gap: '20px' }}>
          
          {/* Headline */}
          <div>
            <h1 style={{ fontSize: '20pt', fontWeight: '800', color: '#f8fafc', margin: 0 }}>
              Excel Data Extraction Control Room
            </h1>
            <p style={{ fontSize: '10pt', color: '#94a3b8', marginTop: '4px', margin: 0 }}>
              Ingest plant spreadsheets, populate SQLite production tables, and seed techno-economic metrics dynamically.
            </p>
          </div>

          {/* Guidelines info card */}
          <div style={{ padding: '20px', backgroundColor: '#1e293b', border: '1px solid #334155', borderRadius: '8px' }}>
            <h3 style={{ fontSize: '11pt', fontWeight: '700', color: '#f1f5f9', margin: '0 0 12px 0', borderBottom: '1px solid #334155', paddingBottom: '6px' }}>
              Guidelines for Ingestion
            </h3>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '25px' }}>
              <div>
                <h4 style={{ fontSize: '9.5pt', fontWeight: 'bold', color: '#10b981', margin: '0 0 6px 0' }}>RSP, ISP, BSP, BSL & DSP Actuals Ingestion</h4>
                <ul style={{ fontSize: '8.5pt', color: '#cbd5e1', lineHeight: '1.6', margin: 0, paddingLeft: '15px' }}>
                  <li><strong>RSP — Final Monthly (.xlsx):</strong> Sheets <strong>page-9</strong> + <strong>page 1-8</strong>. Set month manually.</li>
                  <li><strong>RSP — Morning Report (.xlsx):</strong> Sheet starts with <strong>"RSP Morning Report Data for-"</strong>. Month from <strong>A2</strong>. Auto-detected.</li>
                  <li><strong>ISP — Final Monthly (.xlsx):</strong> Sheet <strong>Maj Production Summ</strong>. Set month manually.</li>
                  <li><strong>ISP — Morning Report (.xlsx):</strong> Sheet <strong>DAILYREPORT1</strong>. Month from <strong>K5</strong>. Auto-detected. 19 items extracted.</li>
                  <li><strong>BSP — PPC MIS (.xls):</strong> Sheet <strong>S1</strong>. Month from <strong>N1</strong>. Auto-detected.</li>
                  <li><strong>BSL — DPR Mail (.xlsx):</strong> Sheet <strong>DPR</strong>. Month from <strong>O1</strong>. Auto-detected.</li>
                  <li><strong>DSP — MCR-I (.xls):</strong> Tab-separated text file (<em>mcr1_*.xls</em>). Month from header row. Auto-detected. 21 items extracted.</li>
                  <li>All tonnage values converted Tonnes → '000 T automatically. Every upload is logged below.</li>
                </ul>
              </div>
              <div>
                <h4 style={{ fontSize: '9.5pt', fontWeight: 'bold', color: '#3b82f6', margin: '0 0 6px 0' }}>RSP, ISP, BSP, DSP & BSL ABP Targets Ingestion (Annual)</h4>
                <ul style={{ fontSize: '8.5pt', color: '#cbd5e1', lineHeight: '1.6', margin: 0, paddingLeft: '15px' }}>
                  <li>Spreadsheet files must be in <strong>.xlsx</strong> format.</li>
                  <li><strong>RSP</strong> — sheet <strong>sheet1</strong>; <strong>ISP</strong> — sheet <strong>SUMM PROD</strong>; <strong>BSP</strong> — sheet <strong>Table 1</strong>; <strong>DSP</strong> — sheet <strong>Monthwise</strong>.</li>
                  <li><strong>BSL</strong> — sheet <strong>PLAN SUMMARY</strong>. Months in rows (Apr row 10 → Mar row 24), items in columns B–R. Quarter rows auto-skipped.</li>
                  <li><strong>ASP / SSP / VISL</strong> — single combined <code>.xlsx</code> file (sheet <strong>APP 26-27</strong>). Row 1 has month dates (col C onward); col A = plant name, col B = item. All three plants extracted in one upload.</li>
                  <li>Extracts and populates targets for all 12 months in a single upload.</li>
                  <li>Preserves the plan sheet scale.</li>
                </ul>
              </div>
            </div>
          </div>

          {/* Terminal log window */}
          <div style={{
            fontFamily: '"JetBrains Mono", monospace',
            fontSize: '9.5pt',
            backgroundColor: '#020617',
            border: '1px solid #1e293b',
            borderRadius: '6px',
            padding: '20px',
            minHeight: '280px',
            display: 'flex',
            flexDirection: 'column',
            gap: '8px',
            color: '#f8fafc',
            boxShadow: 'inset 0 2px 4px rgba(0,0,0,0.6)'
          }}>
            <div style={{ color: '#64748b', borderBottom: '1px solid #1e293b', paddingBottom: '6px', marginBottom: '4px', fontSize: '8pt', display: 'flex', justifyContent: 'space-between' }}>
              <span>EXTRACTION JOB OUTPUT LOGS</span>
              <span>v1.0.0</span>
            </div>
            
            {logs.map((log, index) => {
              let color = '#38bdf8';
              let prefix = '[INFO]';
              if (log.type === 'success') {
                color = '#34d399';
                prefix = '[SUCCESS]';
              } else if (log.type === 'error') {
                color = '#f87171';
                prefix = '[ERROR]';
              }
              return (
                <div key={index} style={{ display: 'flex', gap: '8px', lineHeight: '1.4' }}>
                  <span style={{ color: '#64748b' }}>{log.time || '--:--:--'}</span>
                  <span style={{ color }}>{prefix}</span>
                  <span style={{ color: log.type === 'error' ? '#f87171' : '#cbd5e1' }}>{log.text}</span>
                </div>
              );
            })}
            
            {isUploading && (
              <div style={{ color: '#fbbf24', display: 'flex', gap: '8px', animation: 'pulse 1.5s infinite' }}>
                <span>{new Date().toLocaleTimeString()}</span>
                <span>[PROCESS]</span>
                <span>Data extraction script is executing... Please wait...</span>
              </div>
            )}
          </div>

          {/* Extraction Audit Log */}
          <div>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '10px' }}>
              <h2 style={{ fontSize: '12pt', fontWeight: '700', color: '#f1f5f9', margin: 0 }}>
                Extraction Audit Log
              </h2>
              <button
                onClick={fetchExtractionLog}
                style={{ background: 'none', border: '1px solid #334155', borderRadius: '4px', color: '#94a3b8', fontSize: '8pt', padding: '4px 10px', cursor: 'pointer' }}
              >
                Refresh
              </button>
            </div>

            {extractionLog.length === 0 ? (
              <div style={{ padding: '20px', textAlign: 'center', color: '#475569', fontSize: '9pt', backgroundColor: '#1e293b', border: '1px solid #334155', borderRadius: '6px' }}>
                No extractions recorded yet.
              </div>
            ) : (
              <div style={{ overflowX: 'auto', border: '1px solid #334155', borderRadius: '6px', overflow: 'hidden' }}>
                <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '8.5pt' }}>
                  <thead>
                    <tr style={{ backgroundColor: '#1e293b' }}>
                      {['Timestamp', 'Plant', 'Month', 'Source Type', 'File Name', 'Sheet', 'Items'].map(h => (
                        <th key={h} style={{ padding: '8px 12px', textAlign: 'left', color: '#94a3b8', fontWeight: '600', borderBottom: '1px solid #334155', whiteSpace: 'nowrap' }}>{h}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {extractionLog.map((entry, idx) => (
                      <tr key={entry.id} style={{ backgroundColor: idx % 2 === 0 ? '#0f172a' : '#1e293b', borderBottom: '1px solid #1e293b' }}>
                        <td style={{ padding: '7px 12px', color: '#64748b', whiteSpace: 'nowrap' }}>{entry.logged_at}</td>
                        <td style={{ padding: '7px 12px', color: '#38bdf8', fontWeight: '600' }}>{entry.plant_name}</td>
                        <td style={{ padding: '7px 12px', color: '#f1f5f9', whiteSpace: 'nowrap' }}>{entry.report_month}</td>
                        <td style={{ padding: '7px 12px' }}>
                          <span style={{
                            padding: '2px 7px', borderRadius: '4px', fontSize: '7.5pt', fontWeight: '600',
                            backgroundColor: entry.source_type?.includes('Monthly') ? 'rgba(16,185,129,0.15)' : entry.source_type?.includes('Morning') ? 'rgba(245,158,11,0.15)' : 'rgba(99,102,241,0.15)',
                            color: entry.source_type?.includes('Monthly') ? '#34d399' : entry.source_type?.includes('Morning') ? '#fbbf24' : '#a5b4fc',
                          }}>
                            {entry.source_type}
                          </span>
                        </td>
                        <td style={{ padding: '7px 12px', color: '#94a3b8', maxWidth: '180px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }} title={entry.file_name}>{entry.file_name}</td>
                        <td style={{ padding: '7px 12px', color: '#64748b', fontFamily: 'monospace' }}>{entry.sheet_name}</td>
                        <td style={{ padding: '7px 12px', color: '#34d399', textAlign: 'right', fontWeight: '700' }}>{entry.items_extracted}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>

        </div>
      </div>
    </main>
  );
}
