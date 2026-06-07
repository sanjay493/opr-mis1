'use client';

import React, { useState } from 'react';
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

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://127.0.0.1:8082';

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
        addLog('success', `Database tables production_table and techno_table successfully updated.`);
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
                <option value="RSP">RSP (Steel Plant)</option>
                <option value="BSP">BSP</option>
                <option value="DSP">DSP</option>
                <option value="BSL">BSL</option>
                <option value="ISP">ISP</option>
                <option value="ASP">ASP</option>
                <option value="SSP">SSP</option>
                <option value="VISL">VISL</option>
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
              <label>Excel File (.xlsx)</label>
              <input
                id="excel-file-input"
                type="file"
                className="form-control"
                accept=".xlsx"
                style={{ padding: '4px', fontSize: '0.8rem' }}
                onChange={(e) => setUploadFile(e.target.files[0])}
              />
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
                <h4 style={{ fontSize: '9.5pt', fontWeight: 'bold', color: '#10b981', margin: '0 0 6px 0' }}>RSP & ISP Actuals Ingestion (Monthly)</h4>
                <ul style={{ fontSize: '8.5pt', color: '#cbd5e1', lineHeight: '1.6', margin: 0, paddingLeft: '15px' }}>
                  <li>Spreadsheet files must be in <strong>.xlsx</strong> format.</li>
                  <li>RSP requires sheets <strong>page-9</strong> and <strong>page 1-8</strong>.</li>
                  <li>ISP requires sheet <strong>Maj Production Summ</strong>.</li>
                  <li>Converts Tonnes to '000 T where required.</li>
                </ul>
              </div>
              <div>
                <h4 style={{ fontSize: '9.5pt', fontWeight: 'bold', color: '#3b82f6', margin: '0 0 6px 0' }}>RSP, ISP, BSP & DSP ABP Targets Ingestion (Annual)</h4>
                <ul style={{ fontSize: '8.5pt', color: '#cbd5e1', lineHeight: '1.6', margin: 0, paddingLeft: '15px' }}>
                  <li>Spreadsheet files must be in <strong>.xlsx</strong> format.</li>
                  <li>RSP requires sheet <strong>sheet1</strong>; ISP requires <strong>SUMM PROD</strong>; BSP requires <strong>Table 1</strong>; DSP requires <strong>Monthwise</strong>.</li>
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
        </div>
      </div>
    </main>
  );
}
