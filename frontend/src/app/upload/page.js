'use client';

import React, { useState, useEffect, useCallback } from 'react';
import Link from 'next/link';

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

function PreviewTable({ title, headers, rows }) {
  return (
    <div style={{ marginBottom: 14 }}>
      <div style={{ fontSize: '9pt', fontWeight: 700, color: '#a5b4fc', margin: '8px 0 6px' }}>{title}</div>
      <div style={{ overflowX: 'auto', border: '1px solid #334155', borderRadius: 6, maxHeight: 320, overflowY: 'auto' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '8.5pt' }}>
          <thead>
            <tr style={{ backgroundColor: '#0f172a', position: 'sticky', top: 0 }}>
              {headers.map((h) => (
                <th key={h} style={{ padding: '6px 10px', textAlign: 'left', color: '#94a3b8',
                                     fontWeight: 600, borderBottom: '1px solid #334155', whiteSpace: 'nowrap' }}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((cells, i) => {
              const status = cells[cells.length - 1];
              const ok = status === 'ok';
              return (
                <tr key={i} style={{
                  backgroundColor: ok ? (i % 2 ? '#16242e' : '#0f172a') : 'rgba(248,113,113,0.07)',
                  borderBottom: '1px solid #1e293b', opacity: ok ? 1 : 0.6,
                }}>
                  {cells.map((c, j) => (
                    <td key={j} style={{
                      padding: '4px 10px',
                      color: j === 0 ? '#38bdf8' : (j === cells.length - 1 ? (ok ? '#34d399' : '#f87171') : '#cbd5e1'),
                      fontWeight: j === 0 || j === cells.length - 1 ? 600 : 400,
                      whiteSpace: 'nowrap',
                      fontFamily: String(c).match(/^[A-Z]+\d+/) ? 'monospace' : 'inherit',
                    }}>{c}</td>
                  ))}
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function TechnoCheckTable({ rows }) {
  const okCount      = rows.filter((r) => r.status === 'ok').length;
  const mismatchCount = rows.filter((r) => r.mapping_ok === false).length;
  const title = `Techno-Economic Parameters (${okCount} ok${mismatchCount > 0 ? `, ⚠ ${mismatchCount} mapping issues` : ''}) → techno_table`;

  return (
    <div style={{ marginBottom: 14 }}>
      <div style={{ fontSize: '9pt', fontWeight: 700, color: mismatchCount > 0 ? '#fbbf24' : '#a5b4fc', margin: '8px 0 6px' }}>
        {title}
      </div>
      <div style={{ overflowX: 'auto', border: '1px solid #334155', borderRadius: 6, maxHeight: 320, overflowY: 'auto' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '8.5pt' }}>
          <thead>
            <tr style={{ backgroundColor: '#0f172a', position: 'sticky', top: 0 }}>
              {['Parameter', 'Unit', 'Month', 'YTD', 'Cell', 'File Label', 'Status'].map((h) => (
                <th key={h} style={{ padding: '6px 10px', textAlign: 'left', color: '#94a3b8',
                                     fontWeight: 600, borderBottom: '1px solid #334155', whiteSpace: 'nowrap' }}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((r, i) => {
              const ok     = r.status === 'ok';
              const mapOk  = r.mapping_ok !== false;
              const rowBg  = !mapOk
                ? 'rgba(251,191,36,0.10)'
                : ok ? (i % 2 ? '#16242e' : '#0f172a') : 'rgba(248,113,113,0.07)';
              return (
                <tr key={i} style={{ backgroundColor: rowBg, borderBottom: '1px solid #1e293b' }}>
                  <td style={{ padding: '4px 10px', color: '#38bdf8', fontWeight: 600, whiteSpace: 'nowrap' }}>{r.parameter}</td>
                  <td style={{ padding: '4px 10px', color: '#cbd5e1', whiteSpace: 'nowrap' }}>{r.unit}</td>
                  <td style={{ padding: '4px 10px', color: '#cbd5e1', whiteSpace: 'nowrap' }}>{r.month_actual ?? ''}</td>
                  <td style={{ padding: '4px 10px', color: '#cbd5e1', whiteSpace: 'nowrap' }}>{r.ytd_actual ?? ''}</td>
                  <td style={{ padding: '4px 10px', color: '#94a3b8', whiteSpace: 'nowrap',
                               fontFamily: 'monospace', fontSize: '8pt' }}>{r.cell}</td>
                  <td style={{ padding: '4px 10px', color: mapOk ? '#94a3b8' : '#fbbf24',
                               fontWeight: mapOk ? 400 : 700, whiteSpace: 'nowrap' }}>
                    {r.row_label || '—'}{!mapOk && ' ⚠'}
                  </td>
                  <td style={{ padding: '4px 10px', color: ok ? '#34d399' : '#f87171',
                               fontWeight: 600, whiteSpace: 'nowrap' }}>{r.status}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function EditableSpecialSteelTable({ plant, rows, onToggle, onEditGrade, onEditSection }) {
  const selCount = rows.filter((r) => r.selected).length;
  const cellStyle = { padding: '4px 10px', color: '#cbd5e1', whiteSpace: 'nowrap' };
  return (
    <div style={{ marginBottom: 14 }}>
      <div style={{ fontSize: '9pt', fontWeight: 700, color: '#fbbf24', margin: '8px 0 6px' }}>
        Special Steel Performance ({selCount} selected) → special_steel_orders
      </div>
      <div style={{ overflowX: 'auto', border: '1px solid #334155', borderRadius: 6, maxHeight: 360, overflowY: 'auto' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '8.5pt' }}>
          <thead>
            <tr style={{ backgroundColor: '#0f172a', position: 'sticky', top: 0, zIndex: 1 }}>
              {['Insert', 'Product', 'Quality/Grade (editable)', 'Section (editable)', 'Order Qty', 'ABP Month', 'Desp', 'Unit', 'Cell', 'Status'].map((h) => (
                <th key={h} style={{ padding: '6px 10px', textAlign: 'left', color: '#94a3b8',
                                     fontWeight: 600, borderBottom: '1px solid #334155', whiteSpace: 'nowrap' }}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((r, i) => {
              const isTotal = r.status === 'total';
              const canInsert = !isTotal;
              return (
                <tr key={i} style={{
                  backgroundColor: isTotal
                    ? 'rgba(251,191,36,0.06)'
                    : r.selected ? (i % 2 ? '#16242e' : '#0f172a') : 'rgba(248,113,113,0.07)',
                  borderBottom: '1px solid #1e293b',
                  opacity: isTotal ? 0.7 : r.selected ? 1 : 0.65,
                }}>
                  <td style={{ ...cellStyle, textAlign: 'center' }}>
                    <input type="checkbox" checked={!!r.selected} disabled={!canInsert}
                           title={isTotal ? 'Total rows are for cross-check only' : 'Include in insert'}
                           onChange={(e) => onToggle(i, e.target.checked)}
                           style={{ accentColor: '#10b981', cursor: canInsert ? 'pointer' : 'not-allowed' }} />
                  </td>
                  <td style={{ ...cellStyle, color: '#38bdf8', fontWeight: 600 }}>{r.product || ''}</td>
                  <td style={cellStyle}>
                    {isTotal ? (
                      <span style={{ color: '#fbbf24', fontStyle: 'italic' }}>{r.quality_grade}</span>
                    ) : (
                      <input type="text" value={r.grade_edit ?? r.quality_grade}
                             onChange={(e) => onEditGrade(i, e.target.value)}
                             style={{ width: 180, background: '#020617', color: '#e2e8f0',
                                      border: '1px solid #334155', borderRadius: 4,
                                      padding: '3px 6px', fontSize: '8.5pt' }} />
                    )}
                  </td>
                  <td style={cellStyle}>
                    {isTotal ? '' : (
                      <input type="text" value={r.section_edit ?? r.section ?? ''}
                             onChange={(e) => onEditSection(i, e.target.value)}
                             style={{ width: 100, background: '#020617', color: '#e2e8f0',
                                      border: '1px solid #334155', borderRadius: 4,
                                      padding: '3px 6px', fontSize: '8.5pt' }} />
                    )}
                  </td>
                  <td style={{ ...cellStyle, textAlign: 'right' }}>{r.order_qty ?? ''}</td>
                  <td style={{ ...cellStyle, textAlign: 'right', color: '#64748b' }}>{r.abp_month ?? r.prodn ?? ''}</td>
                  <td style={{ ...cellStyle, textAlign: 'right' }}>{r.actual_despatch ?? ''}</td>
                  <td style={cellStyle}>{r.unit}</td>
                  <td style={{ ...cellStyle, color: '#64748b' }}>{r.cell}</td>
                  <td style={{ ...cellStyle,
                               color: isTotal ? '#fbbf24' : '#34d399', fontWeight: 600 }}>
                    {isTotal ? 'total (skip)' : 'ok'}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function EditableProductionTable({ plant, rows, onToggle, onEditName }) {
  const selCount = rows.filter((r) => r.selected).length;
  const cellStyle = { padding: '4px 10px', color: '#cbd5e1', whiteSpace: 'nowrap' };
  return (
    <div style={{ marginBottom: 14 }}>
      <div style={{ fontSize: '9pt', fontWeight: 700, color: '#a5b4fc', margin: '8px 0 6px' }}>
        Production ({selCount} selected) → production_table
      </div>
      <div style={{ overflowX: 'auto', border: '1px solid #334155', borderRadius: 6, maxHeight: 360, overflowY: 'auto' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '8.5pt' }}>
          <thead>
            <tr style={{ backgroundColor: '#0f172a', position: 'sticky', top: 0, zIndex: 1 }}>
              {['Insert', 'Plant', 'Item (editable)', 'Value', 'Unit', 'Cell', 'PDF Label', 'Status'].map((h) => (
                <th key={h} style={{ padding: '6px 10px', textAlign: 'left', color: '#94a3b8',
                                     fontWeight: 600, borderBottom: '1px solid #334155', whiteSpace: 'nowrap' }}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((r, i) => {
              const wasOk = r.status === 'ok';
              const named = (r.item_edit || '').trim() !== '';
              const edited = named && wasOk && r.item_edit.trim() !== r.item_name;
              const statusText = !named ? 'unmapped'
                : edited ? 'ok (renamed)'
                : wasOk ? 'ok'
                : 'ok (mapped here)';
              const statusOk = named;
              return (
                <tr key={i} style={{
                  backgroundColor: r.selected ? (i % 2 ? '#16242e' : '#0f172a') : 'rgba(248,113,113,0.07)',
                  borderBottom: '1px solid #1e293b', opacity: r.selected ? 1 : 0.65,
                }}>
                  <td style={{ ...cellStyle, textAlign: 'center' }}>
                    <input type="checkbox" checked={r.selected} disabled={!named}
                           title={named ? 'Include this row in the insert' : 'Type an item name first'}
                           onChange={(e) => onToggle(i, e.target.checked)}
                           style={{ accentColor: '#10b981', cursor: named ? 'pointer' : 'not-allowed' }} />
                  </td>
                  <td style={{ ...cellStyle, color: '#38bdf8', fontWeight: 600 }}>{plant}</td>
                  <td style={cellStyle}>
                    <input type="text" value={r.item_edit}
                           placeholder={r.pdf_label || r.item_name}
                           onChange={(e) => onEditName(i, e.target.value)}
                           style={{ width: 180, background: '#020617', color: edited || !wasOk ? '#fbbf24' : '#e2e8f0',
                                    border: '1px solid ' + (edited || (!wasOk && named) ? '#fbbf24' : '#334155'),
                                    borderRadius: 4, padding: '3px 6px', fontSize: '8.5pt' }} />
                  </td>
                  <td style={cellStyle}>{r.value ?? ''}</td>
                  <td style={cellStyle}>{r.unit}</td>
                  <td style={{ ...cellStyle, color: '#64748b' }}>{r.cell}</td>
                  <td style={{ ...cellStyle, color: '#94a3b8', fontStyle: 'italic' }}>{r.pdf_label || ''}</td>
                  <td style={{ ...cellStyle, color: statusOk ? '#34d399' : '#f87171', fontWeight: 600 }}>{statusText}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}

export default function UploadPage() {
  const defaultDate = getDefaultDate();
  const [uploadMode, setUploadMode] = useState('preview'); // 'preview' | 'plan'
  const [showDirectExtract, setShowDirectExtract] = useState(false);
  const [uploadPlantName, setUploadPlantName] = useState('RSP');
  const [uploadMonthName, setUploadMonthName] = useState(defaultDate.month);
  const [uploadYear, setUploadYear] = useState(defaultDate.year);
  const [uploadFile, setUploadFile] = useState(null);

  const [uploadPlanPlantName, setUploadPlanPlantName] = useState('RSP');
  const [uploadPlanFY, setUploadPlanFY] = useState(defaultFY());
  const [uploadPlanFile, setUploadPlanFile] = useState(null);

  const [technoPlant, setTechnoPlant] = useState('RSP');
  const [technoMonthName, setTechnoMonthName] = useState(defaultDate.month);
  const [technoYear, setTechnoYear] = useState(defaultDate.year);
  const [technoFile, setTechnoFile] = useState(null);
  const [technoPreview, setTechnoPreview] = useState(null);
  const [prodRows, setProdRows] = useState([]);   // editable copy of production_rows
  const [ssRows, setSsRows] = useState([]);       // editable copy of special_steel_rows
  const [isTechnoBusy, setIsTechnoBusy] = useState(false);

  // ASP PDF state (single-step auto-detect: REP or FL file)
  const [aspResult, setAspResult] = useState(null);
  const [aspProdRows, setAspProdRows] = useState([]);
  const [aspBusy, setAspBusy] = useState(false);

  // DSP PDF three-step state (independent from the generic technoPreview flow)
  const [dspProdResult, setDspProdResult] = useState(null);
  const [dspProdRows, setDspProdRows] = useState([]);
  const [dspTechnoResult, setDspTechnoResult] = useState(null);
  const [dspSsResult, setDspSsResult] = useState(null);
  const [dspSsRows, setDspSsRows] = useState([]);
  const [dspBusy, setDspBusy] = useState({ production: false, techno: false, special_steel: false });
  
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
    const targetPeriod = `${uploadYear}-${MONTH_NUM[uploadMonthName]}`;
    
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

  const handleTechnoExtract = async (e) => {
    e.preventDefault();
    if (!technoFile) {
      alert('Please select the Excel file to extract.');
      return;
    }
    setIsTechnoBusy(true);
    setTechnoPreview(null);
    const targetPeriod = `${technoYear}-${MONTH_NUM[technoMonthName]}`;
    setLogs([]);
    addLog('info', `Extracting ${technoPlant} report for preview (${targetPeriod})...`);

    const formData = new FormData();
    formData.append('file', technoFile);
    formData.append('plant_name', technoPlant);
    formData.append('month', targetPeriod);

    try {
      const res = await fetch(`${API_BASE_URL}/api/extract-preview`, { method: 'POST', body: formData });
      const rawText = await res.text();
      let result;
      try {
        result = JSON.parse(rawText);
      } catch (_) {
        throw new Error(rawText.substring(0, 300));
      }
      if (!res.ok) throw new Error(result.detail || 'extraction failed');
      const prodOk = (result.production_rows || []).filter((r) => r.status === 'ok').length;
      const teOk = (result.techno_rows || []).filter((r) => r.status === 'ok').length;
      const millOk = (result.techno_param_rows || []).filter((r) => r.status === 'ok').length;
      addLog('success', `File type: ${result.source_type} (month ${result.month})`);
      addLog('info', `Workbook sheets: ${(result.workbook_sheets || []).join(' | ')}`);
      if (!result.production_rows?.length) {
        addLog('info', 'No production data: this file was not recognized as a Final Monthly Report (sheets "page-9" + "page 1-8") or Morning Report. If it should contain production, check the sheet names above.');
      }
      if (result.shops_found?.length) {
        addLog('success', `Mill techno: sheet "${result.mill_sheet}", cols ${result.month_col}/${result.cum_col}` +
          (result.columns_detected ? ' (auto-detected)' : ' (defaults)') + ` — shops: ${result.shops_found.join(', ')}`);
      }
      addLog('success', `Extracted: ${prodOk} production, ${teOk} techno, ${millOk} mill techno values. Review below, then Insert.`);
      setTechnoPreview(result);
      setProdRows((result.production_rows || []).map((r) => ({
        ...r,
        selected: r.status === 'ok',
        item_edit: r.status === 'ok' ? r.item_name : '',
      })));
      setSsRows((result.special_steel_rows || []).map((r) => ({
        ...r,
        selected: r.status === 'ok',
        grade_edit: r.quality_grade ?? '',
        section_edit: r.section ?? '',
      })));
      if (result.special_steel_note) {
        addLog('info', `Special Steel: ${result.special_steel_note}`);
      } else if ((result.special_steel_rows || []).length) {
        const ssOk = (result.special_steel_rows || []).filter((r) => r.status === 'ok').length;
        addLog('success', `Special Steel: ${ssOk} data rows + ${(result.special_steel_rows || []).length - ssOk} total rows extracted.`);
      }
    } catch (err) {
      addLog('error', `Extraction failed: ${err.message}`);
      alert(`Extraction failed: ${err.message}`);
    } finally {
      setIsTechnoBusy(false);
    }
  };

  const handleTechnoInsert = async () => {
    if (!technoPreview) return;
    // Only rows the user kept ticked (and named) are inserted. Raw-tonne values
    // of newly mapped rows are converted to '000T to match DB conventions.
    const chosen = prodRows.filter((r) => r.selected && (r.item_edit || '').trim());
    const production_rows = chosen.map((r) => {
      let value = r.value;
      let unit = r.unit;
      if (r.status !== 'ok' && unit === 'T' && typeof value === 'number') {
        value = Math.round(value) / 1000;
        unit = "'000T";
      }
      return { ...r, item_name: r.item_edit.trim(), value, unit };
    });
    // Renames + newly mapped labels are remembered server-side for future extractions.
    const item_overrides = chosen
      .filter((r) => r.pdf_label && (r.status !== 'ok' || r.item_edit.trim() !== r.item_name))
      .map((r) => ({
        pdf_label: r.pdf_label,
        item_name: r.item_edit.trim(),
        convert_t: r.unit === 'nos/d' ? 0 : 1,
      }));
    const techno_rows = (technoPreview.techno_rows || []).filter((r) => r.status === 'ok');
    const techno_param_rows = (technoPreview.techno_param_rows || []).filter((r) => r.status === 'ok');
    const special_steel_rows = ssRows
      .filter((r) => r.selected && r.status === 'ok')
      .map((r) => ({
        ...r,
        quality_grade: (r.grade_edit ?? r.quality_grade ?? '').trim(),
        section: (r.section_edit ?? r.section ?? '').trim(),
      }));
    if (!production_rows.length && !techno_rows.length && !techno_param_rows.length && !special_steel_rows.length) {
      alert('No extracted values to insert.');
      return;
    }
    setIsTechnoBusy(true);
    try {
      const res = await fetch(`${API_BASE_URL}/api/confirm-extraction`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          month: technoPreview.month,
          plant: technoPreview.plant,
          source_type: technoPreview.source_type,
          sheets: technoPreview.sheets,
          file_name: technoPreview.file_name || '',
          production_rows,
          item_overrides,
          techno_rows,
          techno_param_rows,
          special_steel_rows,
        }),
      });
      const text = await res.text();
      let result;
      try { result = JSON.parse(text); } catch { throw new Error(text.slice(0, 300) || `Server error ${res.status}`); }
      if (!res.ok) throw new Error(result.detail || 'insert failed');
      addLog('success', result.message);
      alert(result.message);
      setTechnoPreview(null);
      setProdRows([]);
      setSsRows([]);
      setTechnoFile(null);
      const fi = document.getElementById('techno-file-input');
      if (fi) fi.value = '';
      fetchExtractionLog();
    } catch (err) {
      addLog('error', `Insert failed: ${err.message}`);
      alert(`Insert failed: ${err.message}`);
    } finally {
      setIsTechnoBusy(false);
    }
  };

  const technoOkCount = technoPreview
    ? prodRows.filter((r) => r.selected && (r.item_edit || '').trim()).length +
      (technoPreview.techno_rows || []).filter((r) => r.status === 'ok').length +
      (technoPreview.techno_param_rows || []).filter((r) => r.status === 'ok').length +
      ssRows.filter((r) => r.selected && r.status === 'ok').length
    : 0;

  const toggleProdRow = (idx, checked) =>
    setProdRows((prev) => prev.map((r, i) => (i === idx ? { ...r, selected: checked } : r)));

  const editProdRowName = (idx, name) =>
    setProdRows((prev) => prev.map((r, i) => {
      if (i !== idx) return r;
      // auto-tick a row the moment the user gives it a name; untick if cleared
      const named = name.trim() !== '';
      return { ...r, item_edit: name, selected: named ? (r.selected || r.status !== 'ok') : false };
    }));

  const toggleSsRow = (idx, checked) =>
    setSsRows((prev) => prev.map((r, i) => (i === idx ? { ...r, selected: checked } : r)));

  const editSsGrade = (idx, val) =>
    setSsRows((prev) => prev.map((r, i) => (i === idx ? { ...r, grade_edit: val } : r)));

  const editSsSection = (idx, val) =>
    setSsRows((prev) => prev.map((r, i) => (i === idx ? { ...r, section_edit: val } : r)));

  // ── ASP PDF handlers ────────────────────────────────────────────────────
  const isAspPdf = technoPlant === 'ASP';

  const handleAspExtract = async (e) => {
    e.preventDefault();
    if (!technoFile) { alert('Please select the ASP PDF file first.'); return; }
    const targetPeriod = `${technoYear}-${MONTH_NUM[technoMonthName]}`;
    setAspBusy(true);
    setAspResult(null);
    setAspProdRows([]);
    setLogs([]);
    const isRep = technoFile.name.toUpperCase().startsWith('REP');
    const isFl  = technoFile.name.toUpperCase().startsWith('FL');
    const hint  = isRep ? 'REP (crude steel)' : isFl ? 'FL (finished steel)' : 'auto-detect';
    addLog('info', `ASP: extracting ${hint} PDF for ${targetPeriod} — ${technoFile.name}...`);
    const formData = new FormData();
    formData.append('file', technoFile);
    formData.append('plant_name', 'ASP');
    formData.append('month', targetPeriod);
    try {
      const res = await fetch(`${API_BASE_URL}/api/extract-preview`, { method: 'POST', body: formData });
      const rawText = await res.text();
      let result;
      try { result = JSON.parse(rawText); } catch (_) { throw new Error(rawText.substring(0, 300)); }
      if (!res.ok) throw new Error(result.detail || 'extraction failed');
      setAspResult(result);
      setAspProdRows((result.production_rows || []).map((r) => ({
        ...r, selected: r.status === 'ok', item_edit: r.status === 'ok' ? r.item_name : '',
      })));
      const ok = (result.production_rows || []).filter((r) => r.status === 'ok').length;
      addLog('success', `ASP ${result.report_type}: ${ok} items extracted (${result.source_type}). Review below, then Insert.`);
    } catch (err) {
      addLog('error', `ASP extraction failed: ${err.message}`);
      alert(`Extraction failed: ${err.message}`);
    } finally {
      setAspBusy(false);
    }
  };

  const handleAspInsert = async () => {
    if (!aspResult) return;
    const chosen = aspProdRows.filter((r) => r.selected && (r.item_edit || '').trim());
    if (!chosen.length) { alert('No rows selected.'); return; }
    const targetPeriod = `${technoYear}-${MONTH_NUM[technoMonthName]}`;
    const production_rows = chosen.map((r) => {
      let value = r.value;
      if (r.status !== 'ok' && r.unit === 'T' && typeof value === 'number') value = Math.round(value) / 1000;
      return { ...r, item_name: r.item_edit.trim(), value };
    });
    const item_overrides = chosen
      .filter((r) => r.pdf_label && (r.status !== 'ok' || r.item_edit.trim() !== r.item_name))
      .map((r) => ({ pdf_label: r.pdf_label, item_name: r.item_edit.trim(), convert_t: 1 }));
    setAspBusy(true);
    try {
      const res = await fetch(`${API_BASE_URL}/api/confirm-extraction`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          month: aspResult.month || targetPeriod,
          plant: 'ASP',
          source_type: aspResult.source_type,
          sheets: aspResult.sheets,
          file_name: technoFile?.name || '',
          production_rows,
          item_overrides,
          techno_rows: [],
          techno_param_rows: [],
          special_steel_rows: [],
        }),
      });
      const text = await res.text();
      let result;
      try { result = JSON.parse(text); } catch { throw new Error(text.slice(0, 300) || `Server error ${res.status}`); }
      if (!res.ok) throw new Error(result.detail || 'insert failed');
      addLog('success', result.message);
      alert(result.message);
      setAspResult(null);
      setAspProdRows([]);
      const fi = document.getElementById('techno-file-input');
      if (fi) fi.value = '';
      fetchExtractionLog();
    } catch (err) {
      addLog('error', `ASP insert failed: ${err.message}`);
      alert(`Insert failed: ${err.message}`);
    } finally {
      setAspBusy(false);
    }
  };

  const toggleAspRow = (idx, checked) =>
    setAspProdRows((prev) => prev.map((r, i) => (i === idx ? { ...r, selected: checked } : r)));
  const editAspRowName = (idx, name) =>
    setAspProdRows((prev) => prev.map((r, i) => {
      if (i !== idx) return r;
      const named = name.trim() !== '';
      return { ...r, item_edit: name, selected: named ? (r.selected || r.status !== 'ok') : false };
    }));

  // ── DSP PDF three-step helpers ──────────────────────────────────────────
  const isDspPdf = technoPlant === 'DSP' && technoFile?.name?.toLowerCase().endsWith('.pdf');

  const handleDspExtract = async (block) => {
    if (!technoFile) { alert('Please select the DSP PDF file first.'); return; }
    const targetPeriod = `${technoYear}-${MONTH_NUM[technoMonthName]}`;
    setDspBusy((b) => ({ ...b, [block]: true }));
    setLogs([]);
    addLog('info', `DSP: extracting ${block} (${targetPeriod}) from ${technoFile.name}...`);
    const formData = new FormData();
    formData.append('file', technoFile);
    formData.append('plant_name', 'DSP');
    formData.append('month', targetPeriod);
    formData.append('extract_block', block);
    try {
      const res = await fetch(`${API_BASE_URL}/api/extract-preview`, { method: 'POST', body: formData });
      const rawText = await res.text();
      let result;
      try { result = JSON.parse(rawText); } catch (_) { throw new Error(rawText.substring(0, 300)); }
      if (!res.ok) throw new Error(result.detail || 'extraction failed');
      if (block === 'production') {
        setDspProdResult(result);
        setDspProdRows((result.production_rows || []).map((r) => ({
          ...r, selected: r.status === 'ok', item_edit: r.status === 'ok' ? r.item_name : '',
        })));
        const ok = (result.production_rows || []).filter((r) => r.status === 'ok').length;
        addLog('success', `Production: ${ok} items extracted. Review below, then Insert Production.`);
      } else if (block === 'techno') {
        setDspTechnoResult(result);
        const ok = (result.techno_param_rows || []).filter((r) => r.status === 'ok').length;
        addLog('success', `Techno: ${ok} parameters extracted. Review below, then Insert Techno.`);
      } else {
        setDspSsResult(result);
        setDspSsRows((result.special_steel_rows || []).map((r) => ({
          ...r, selected: r.status === 'ok', grade_edit: r.quality_grade ?? '', section_edit: r.section ?? '',
        })));
        const ok = (result.special_steel_rows || []).filter((r) => r.status === 'ok').length;
        const note = result.special_steel_note;
        if (note) addLog('info', `Special Steel: ${note}`);
        else addLog('success', `Special Steel: ${ok} rows extracted. Review below, then Insert Special Steel.`);
      }
    } catch (err) {
      addLog('error', `DSP ${block} extraction failed: ${err.message}`);
      alert(`Extraction failed: ${err.message}`);
    } finally {
      setDspBusy((b) => ({ ...b, [block]: false }));
    }
  };

  const handleDspInsert = async (block) => {
    const targetPeriod = `${technoYear}-${MONTH_NUM[technoMonthName]}`;
    const baseResult = dspProdResult || dspTechnoResult || dspSsResult;
    const month = baseResult?.month || targetPeriod;
    let payload = {
      month, plant: 'DSP', source_type: 'DSP OMI PDF Report',
      sheets: '', file_name: technoFile?.name || '',
      production_rows: [], item_overrides: [], techno_rows: [],
      techno_param_rows: [], special_steel_rows: [],
    };
    if (block === 'production' && dspProdResult) {
      const chosen = dspProdRows.filter((r) => r.selected && (r.item_edit || '').trim());
      if (!chosen.length) { alert('No production rows selected.'); return; }
      payload.production_rows = chosen.map((r) => {
        let value = r.value;
        if (r.status !== 'ok' && r.unit === 'T' && typeof value === 'number') value = Math.round(value) / 1000;
        return { ...r, item_name: r.item_edit.trim(), value };
      });
      payload.item_overrides = chosen
        .filter((r) => r.pdf_label && (r.status !== 'ok' || r.item_edit.trim() !== r.item_name))
        .map((r) => ({ pdf_label: r.pdf_label, item_name: r.item_edit.trim(), convert_t: r.unit === 'nos/d' ? 0 : 1 }));
      payload.sheets = dspProdResult.sheets || '';
    } else if (block === 'techno' && dspTechnoResult) {
      payload.techno_param_rows = (dspTechnoResult.techno_param_rows || []).filter((r) => r.status === 'ok');
      if (!payload.techno_param_rows.length) { alert('No techno rows to insert.'); return; }
      payload.sheets = dspTechnoResult.sheets || '';
    } else if (block === 'special_steel' && dspSsResult) {
      payload.special_steel_rows = dspSsRows
        .filter((r) => r.selected && r.status === 'ok')
        .map((r) => ({ ...r, quality_grade: (r.grade_edit ?? r.quality_grade ?? '').trim(), section: (r.section_edit ?? r.section ?? '').trim() }));
      if (!payload.special_steel_rows.length) { alert('No special steel rows selected.'); return; }
      payload.sheets = dspSsResult.sheets || '';
    } else { return; }

    setDspBusy((b) => ({ ...b, [block]: true }));
    try {
      const res = await fetch(`${API_BASE_URL}/api/confirm-extraction`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload),
      });
      const text = await res.text();
      let result;
      try { result = JSON.parse(text); } catch { throw new Error(text.slice(0, 300) || `Server error ${res.status}`); }
      if (!res.ok) throw new Error(result.detail || 'insert failed');
      addLog('success', result.message);
      alert(result.message);
      if (block === 'production') { setDspProdResult(null); setDspProdRows([]); }
      else if (block === 'techno') { setDspTechnoResult(null); }
      else { setDspSsResult(null); setDspSsRows([]); }
      fetchExtractionLog();
    } catch (err) {
      addLog('error', `DSP ${block} insert failed: ${err.message}`);
      alert(`Insert failed: ${err.message}`);
    } finally {
      setDspBusy((b) => ({ ...b, [block]: false }));
    }
  };

  const toggleDspProdRow = (idx, checked) =>
    setDspProdRows((prev) => prev.map((r, i) => (i === idx ? { ...r, selected: checked } : r)));
  const editDspProdName = (idx, name) =>
    setDspProdRows((prev) => prev.map((r, i) => {
      if (i !== idx) return r;
      const named = name.trim() !== '';
      return { ...r, item_edit: name, selected: named ? (r.selected || r.status !== 'ok') : false };
    }));
  const toggleDspSsRow = (idx, checked) =>
    setDspSsRows((prev) => prev.map((r, i) => (i === idx ? { ...r, selected: checked } : r)));
  const editDspSsGrade = (idx, val) =>
    setDspSsRows((prev) => prev.map((r, i) => (i === idx ? { ...r, grade_edit: val } : r)));
  const editDspSsSection = (idx, val) =>
    setDspSsRows((prev) => prev.map((r, i) => (i === idx ? { ...r, section_edit: val } : r)));

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

        {/* Unified Data Upload — single section with mode toggle */}
        <div className="control-section">
          <h2>Data Upload</h2>

          {/* Mode selector — 2 tabs */}
          <div style={{ display: 'flex', gap: 4, marginBottom: 14, paddingBottom: 10, borderBottom: '1px solid #334155' }}>
            {[['preview', 'Preview & Insert'], ['plan', 'ABP Plan']].map(([mode, label]) => (
              <button key={mode} type="button" onClick={() => setUploadMode(mode)}
                style={{ flex: 1, padding: '5px 2px', fontSize: '7.5pt', fontWeight: uploadMode === mode ? 700 : 500,
                         border: `1px solid ${uploadMode === mode ? '#38bdf8' : '#334155'}`,
                         borderRadius: 4, cursor: 'pointer', whiteSpace: 'nowrap',
                         backgroundColor: uploadMode === mode ? 'rgba(56,189,248,0.12)' : 'transparent',
                         color: uploadMode === mode ? '#38bdf8' : '#94a3b8' }}>
                {label}
              </button>
            ))}
          </div>

          {/* ── PREVIEW & INSERT MODE (includes direct extract) ───── */}
          {uploadMode === 'preview' && (
            <>
            <form onSubmit={handleTechnoExtract}>
              <div className="form-group" style={{ marginBottom: '12px' }}>
                <label>Plant Source</label>
                <select className="form-control" value={technoPlant}
                        onChange={(e) => setTechnoPlant(e.target.value)}>
                  <option value="RSP">RSP (Excel)</option>
                  <option value="DSP">DSP (OMI PDF or MCR-I Excel)</option>
                  <option value="ISP">ISP (Morning Report or Final Monthly Excel)</option>
                  <option value="BSP">BSP (Techno / Special Steel .xlsx)</option>
                  <option value="BSP-OISCO">BSP-OISCO (OISCO Techno .xlsx)</option>
                  <option value="BSL">BSL (TECHNO &lt;MON&gt;&lt;YYYY&gt;.xls — Techno params)</option>
                  <option value="ASP">ASP (xlsx or PDF — REP / FL)</option>
                </select>
              </div>
              <div className="form-group" style={{ marginBottom: '12px' }}>
                <label>Report Month</label>
                <div style={{ display: 'flex', gap: '6px' }}>
                  <select className="form-control" style={{ flex: 2 }} value={technoMonthName}
                          onChange={(e) => setTechnoMonthName(e.target.value)}>
                    {months.map((m) => <option key={m} value={m}>{m}</option>)}
                  </select>
                  <select className="form-control" style={{ flex: 1 }} value={technoYear}
                          onChange={(e) => setTechnoYear(e.target.value)}>
                    {years.map((y) => <option key={y} value={y}>{y}</option>)}
                  </select>
                </div>
              </div>
              <div className="form-group" style={{ marginBottom: '15px' }}>
                <label>
                  {technoPlant === 'DSP' ? 'DSP Report (.pdf or MCR-I .xls)'
                    : technoPlant === 'ISP' ? 'ISP Excel File (.xlsx)'
                    : technoPlant === 'BSP' ? 'BSP Excel File (.xlsx) — auto-detected'
                    : technoPlant === 'BSP-OISCO' ? 'BSP OISCO Techno Excel (.xlsx)'
                    : technoPlant === 'BSL' ? 'BSL Techno File (.xls) — TECHNO <MON><YYYY>.XLS'
                    : technoPlant === 'ASP' ? 'ASP file — asp.xlsx  or  REP*.pdf / FL*.pdf'
                    : 'RSP Excel File (.xlsx)'}
                </label>
                <input id="techno-file-input" type="file" className="form-control"
                       accept={technoPlant === 'DSP' ? '.pdf,.xls' : technoPlant === 'BSL' ? '.xls,.xlsx' : technoPlant === 'ASP' ? '.xlsx,.pdf' : '.xlsx'}
                       style={{ padding: '4px', fontSize: '0.8rem' }}
                       onChange={(e) => setTechnoFile(e.target.files[0])} />
                <div style={{ fontSize: '7.5pt', color: '#fbbf24', marginTop: '4px' }}>
                  {technoPlant === 'DSP'
                    ? 'OMI PDF: production + special steel + techno. MCR-I .xls: 21 production items. Month auto-detected.'
                    : technoPlant === 'ISP'
                    ? 'Morning Report (DAILYREPORT1): ~19 items, month from K5. Final Monthly: ~17 items, set month above. Summarized Monthly (B-FCE): ~37 techno params.'
                    : technoPlant === 'BSP'
                    ? 'BSP_Spstl-*.xlsx → Special Steel (sheet CORP). BSP-3-page-Tech.xlsx → 62 techno params. OISCO_*.xlsx → 35 OISCO params.'
                    : technoPlant === 'BSP-OISCO'
                    ? "OISCO_<Mon>'YY.xlsx — 35 techno params. Month auto-detected from title."
                    : technoPlant === 'BSL'
                    ? 'TECHNO <MON><YYYY>.XLS — 14 techno params from Sheet1 (Sp. Heat Cons., Energy, Sinter, BF, CDI, Fuel Rate, Coal to HM, CRM Yield, Refractories, Water) and Sheet2 (Coke Oven: Dry Coal Charge, Avg Coking Time). Set month above — used as report month.'
                    : technoPlant === 'ASP'
                    ? "asp.xlsx → reads cells F10/F11/F13/F21/L26 (Crude Steel, Concast, Ingot, Saleable, Stock). Month auto-detected from E3. REP*.pdf → same items via keyword search. FL*.pdf → BARS+FS PRD+PL MILL → Finished Steel (col3=Actual)."
                    : 'Final Monthly, Morning Report or Techno file — auto-detected. Production + techno both extracted.'}
                  {' '}Shown for review before insertion.
                </div>
              </div>
              {isDspPdf ? (
                <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                  <div style={{ fontSize: '8pt', color: '#94a3b8', marginBottom: 2 }}>
                    DSP PDF — extract each block separately, then insert:
                  </div>
                  {[
                    ['production', '1. Extract Production', '#10b981'],
                    ['techno', '2. Extract Techno', '#8b5cf6'],
                    ['special_steel', '3. Extract Special Steel', '#f59e0b'],
                  ].map(([block, label, color]) => (
                    <button key={block} type="button" onClick={() => handleDspExtract(block)}
                            disabled={dspBusy[block]}
                            style={{ width: '100%', padding: '8px', borderRadius: 6, fontWeight: 700,
                                     backgroundColor: color, border: `1px solid ${color}`, color: '#fff',
                                     cursor: dspBusy[block] ? 'not-allowed' : 'pointer', fontSize: '9pt' }}>
                      {dspBusy[block] ? 'Extracting...' : label}
                    </button>
                  ))}
                </div>
              ) : isAspPdf ? (
                <button type="button" onClick={handleAspExtract} disabled={aspBusy}
                        style={{ width: '100%', padding: '8px', borderRadius: 6, fontWeight: 700,
                                 backgroundColor: '#0ea5e9', border: '1px solid #0ea5e9', color: '#fff',
                                 cursor: aspBusy ? 'not-allowed' : 'pointer', fontSize: '9pt' }}>
                  {aspBusy ? 'Extracting ASP PDF...' : 'Extract ASP PDF (REP / FL)'}
                </button>
              ) : (
                <button type="submit" className="btn btn-primary" disabled={isTechnoBusy}
                        style={{ width: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center',
                                 backgroundColor: '#8b5cf6', borderColor: '#8b5cf6' }}>
                  {isTechnoBusy ? 'Working...' : 'Extract & Preview'}
                </button>
              )}
            </form>

            {/* ── Direct Data Extraction (no preview) ─────────────── */}
            <div style={{ marginTop: 16, borderTop: '1px solid #334155', paddingTop: 12 }}>
              <button type="button" onClick={() => setShowDirectExtract((v) => !v)}
                style={{ width: '100%', display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                         background: 'none', border: 'none', cursor: 'pointer', padding: 0, marginBottom: showDirectExtract ? 10 : 0 }}>
                <span style={{ fontSize: '8pt', fontWeight: 600, color: '#64748b' }}>Direct Data Extraction (no preview)</span>
                <span style={{ fontSize: '9pt', color: '#64748b' }}>{showDirectExtract ? '▲' : '▼'}</span>
              </button>
              {showDirectExtract && (
                <form onSubmit={handleExcelUpload}>
                  <div className="form-group" style={{ marginBottom: '10px' }}>
                    <label>Plant Source</label>
                    <select className="form-control" value={uploadPlantName}
                            onChange={(e) => setUploadPlantName(e.target.value)}>
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
                  <div className="form-group" style={{ marginBottom: '10px' }}>
                    <label>Target Period</label>
                    <div style={{ display: 'flex', gap: '6px' }}>
                      <select className="form-control" style={{ flex: 2 }} value={uploadMonthName}
                              onChange={(e) => setUploadMonthName(e.target.value)}>
                        {months.map((m) => <option key={m} value={m}>{m}</option>)}
                      </select>
                      <select className="form-control" style={{ flex: 1 }} value={uploadYear}
                              onChange={(e) => setUploadYear(e.target.value)}>
                        {years.map((y) => <option key={y} value={y}>{y}</option>)}
                      </select>
                    </div>
                  </div>
                  <div className="form-group" style={{ marginBottom: '12px' }}>
                    <label>Excel File {(uploadPlantName === 'BSP' || uploadPlantName === 'DSP') ? '(.xls)' : '(.xlsx)'}</label>
                    <input id="excel-file-input" type="file" className="form-control"
                           accept={(uploadPlantName === 'BSP' || uploadPlantName === 'DSP') ? '.xls' : '.xlsx'}
                           style={{ padding: '4px', fontSize: '0.8rem' }}
                           onChange={(e) => setUploadFile(e.target.files[0])} />
                    {(uploadPlantName === 'BSP' || uploadPlantName === 'BSL' || uploadPlantName === 'DSP' || uploadPlantName === 'ISP') && (
                      <div style={{ fontSize: '7.5pt', color: '#fbbf24', marginTop: '4px' }}>
                        {uploadPlantName === 'BSP' ? 'Month auto-detected from N1 (sheet S1).'
                          : uploadPlantName === 'BSL' ? 'Month auto-detected from O1 (sheet DPR).'
                          : uploadPlantName === 'DSP' ? 'Month auto-detected from MCR-I header.'
                          : 'Morning Report: month from K5. Final Monthly: set month above.'}
                      </div>
                    )}
                  </div>
                  <button type="submit" className="btn btn-primary" disabled={isUploading}
                          style={{ width: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center',
                                   backgroundColor: '#10b981', borderColor: '#10b981' }}>
                    {isUploading ? 'Extracting...' : (
                      <><svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" style={{ marginRight: '8px' }}>
                        <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="17 8 12 3 7 8"/><line x1="12" y1="3" x2="12" y2="15"/>
                      </svg>Extract Data</>
                    )}
                  </button>
                </form>
              )}
            </div>
            </>
          )}

          {/* ── ABP PLAN MODE ─────────────────────────────────────── */}
          {uploadMode === 'plan' && (
            <form onSubmit={handlePlanUpload}>
              <div className="form-group" style={{ marginBottom: '12px' }}>
                <label>Plant Source</label>
                <select className="form-control" value={uploadPlanPlantName}
                        onChange={(e) => setUploadPlanPlantName(e.target.value)}>
                  <option value="RSP">RSP</option>
                  <option value="ISP">ISP</option>
                  <option value="BSP">BSP</option>
                  <option value="DSP">DSP</option>
                  <option value="BSL">BSL</option>
                  <option value="ASP_SSP_VISL">ASP / SSP / VISL (combined)</option>
                </select>
              </div>
              <div className="form-group" style={{ marginBottom: '12px' }}>
                <label>Financial Year</label>
                <select className="form-control" value={uploadPlanFY}
                        onChange={(e) => setUploadPlanFY(e.target.value)}>
                  {financialYears.map((fy) => <option key={fy} value={fy}>{fy}</option>)}
                </select>
              </div>
              <div style={{ fontSize: '7.5pt', color: '#94a3b8', marginBottom: 8 }}>
                RSP: sheet1 · ISP: SUMM PROD · BSP: Table 1 · DSP: Monthwise · BSL: PLAN SUMMARY · ASP/SSP/VISL: APP 26-27
              </div>
              <div className="form-group" style={{ marginBottom: '15px' }}>
                <label>ABP Excel File (.xlsx)</label>
                <input id="plan-file-input" type="file" className="form-control" accept=".xlsx"
                       style={{ padding: '4px', fontSize: '0.8rem' }}
                       onChange={(e) => setUploadPlanFile(e.target.files[0])} />
              </div>
              <button type="submit" className="btn btn-primary" disabled={isUploading}
                      style={{ width: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center',
                               backgroundColor: '#3b82f6', borderColor: '#3b82f6' }}>
                {isUploading ? 'Extracting Plan...' : (
                  <><svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" style={{ marginRight: '8px' }}>
                    <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="17 8 12 3 7 8"/><line x1="12" y1="3" x2="12" y2="15"/>
                  </svg>Extract Plan Targets</>
                )}
              </button>
            </form>
          )}
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
                <h4 style={{ fontSize: '9.5pt', fontWeight: 'bold', color: '#10b981', margin: '0 0 6px 0' }}>RSP, ISP, BSP, BSL, DSP & ASP Actuals + Special Steel Ingestion</h4>
                <ul style={{ fontSize: '8.5pt', color: '#cbd5e1', lineHeight: '1.6', margin: 0, paddingLeft: '15px' }}>
                  <li><strong>RSP — Final Monthly (.xlsx):</strong> Sheets <strong>page-9</strong> + <strong>page 1-8</strong>. Set month manually.</li>
                  <li><strong>RSP — Morning Report (.xlsx):</strong> Sheet starts with <strong>&quot;RSP Morning Report Data for-&quot;</strong>. Month from <strong>A2</strong>. Auto-detected.</li>
                  <li><strong>ISP — Final Monthly (.xlsx):</strong> Sheet <strong>Maj Production Summ</strong>. Set month manually.</li>
                  <li><strong>ISP — Morning Report (.xlsx):</strong> Sheet <strong>DAILYREPORT1</strong>. Month from <strong>K5</strong>. Auto-detected. 19 items extracted.</li>
                  <li><strong>BSP — PPC MIS (.xls):</strong> Sheet <strong>S1</strong>. Month from <strong>N1</strong>. Auto-detected.</li>
                  <li><strong>BSL — DPR Mail (.xlsx):</strong> Sheet <strong>DPR</strong>. Month from <strong>O1</strong>. Auto-detected.</li>
                  <li><strong>DSP — MCR-I (.xls):</strong> Tab-separated text file (<em>mcr1_*.xls</em>). Month from header row. Auto-detected. 21 items extracted.</li>
                  <li><strong>ASP — asp.xlsx</strong> (Preview &amp; Insert, plant: ASP): Reads cells <strong>F10</strong> (Crude Steel), <strong>F11</strong> (Concast), <strong>F12</strong> (Ingot), <strong>F20</strong> (Saleable Steel), <strong>L25</strong> (Stock). Month <strong>auto-detected from E3</strong> (e.g. 30/04/2026 → Apr&apos;26). Sheet: <em>md cell</em>.</li>
                  <li><strong>ASP — REP*.pdf</strong> (Preview &amp; Insert, plant: ASP): Same items as xlsx via keyword search. Set month manually.</li>
                  <li><strong>ASP — FL*.pdf</strong> (Preview &amp; Insert, plant: ASP): Extracts <strong>BARS Mill, FS PRD, Plate Mill</strong> (Plan col2, Actual col3) + computes <strong>Finished Steel</strong> total. Set month manually.</li>
                  <li>All tonnage values converted Tonnes → &apos;000 T automatically. Every upload is logged below.</li>
                  <li><strong>BSP — Special Steel (.xlsx):</strong> Use <strong>Extraction with Preview → Insert</strong> (plant: BSP). File auto-detected by sheet name <strong>CORP</strong>. Extracts grade-wise Orders (Effective) &amp; Loading from BSP_Spstl-*.xlsx. Data saved to <strong>special_steel_orders</strong> and displayed on report page 19.</li>
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

          {/* RSP extraction preview — verify production + techno before insertion */}
          {technoPreview && (
            <div style={{ padding: '20px', backgroundColor: '#1e293b', border: '1px solid #8b5cf6', borderRadius: '8px' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '10px' }}>
                <h3 style={{ fontSize: '11pt', fontWeight: 700, color: '#f1f5f9', margin: 0 }}>
                  Extracted Data — {technoPreview.plant} {technoPreview.month}
                  <span style={{ fontSize: '8pt', color: '#94a3b8', fontWeight: 400, marginLeft: 10 }}>
                    {technoPreview.source_type}{technoPreview.sheets ? ` · ${technoPreview.sheets}` : ''}
                  </span>
                </h3>
                <div style={{ display: 'flex', gap: 8 }}>
                  <button onClick={() => { setTechnoPreview(null); setProdRows([]); setSsRows([]); }} disabled={isTechnoBusy}
                          style={{ background: 'none', border: '1px solid #64748b', borderRadius: 4,
                                   color: '#94a3b8', fontSize: '8.5pt', padding: '5px 12px', cursor: 'pointer' }}>
                    Discard
                  </button>
                  <button onClick={handleTechnoInsert} disabled={isTechnoBusy}
                          style={{ backgroundColor: '#10b981', border: '1px solid #10b981', borderRadius: 4,
                                   color: '#fff', fontSize: '8.5pt', fontWeight: 700, padding: '5px 14px', cursor: 'pointer' }}>
                    {isTechnoBusy ? 'Inserting...' : `Insert ${technoOkCount} rows into DB`}
                  </button>
                </div>
              </div>

              {/* 1. Production rows → production_table (selectable + item name editable) */}
              {prodRows.length > 0 && (
                <EditableProductionTable
                  plant={technoPreview.plant}
                  rows={prodRows}
                  onToggle={toggleProdRow}
                  onEditName={editProdRowName}
                />
              )}

              {/* 2. Special Steel rows → special_steel_orders */}
              {ssRows.length > 0 && (
                <EditableSpecialSteelTable
                  plant={technoPreview.plant}
                  rows={ssRows}
                  onToggle={toggleSsRow}
                  onEditGrade={editSsGrade}
                  onEditSection={editSsSection}
                />
              )}
              {technoPreview.special_steel_note && (
                <div style={{ fontSize: '8pt', color: '#fbbf24', margin: '4px 0' }}>
                  ⚠ {technoPreview.special_steel_note}
                </div>
              )}

              {/* 4. Old-style techno params → techno_table */}
              {technoPreview.techno_rows?.length > 0 && (
                <TechnoCheckTable rows={technoPreview.techno_rows} />
              )}

              {/* 5. Mill techno params → techno_monthly */}
              {technoPreview.techno_param_rows?.length > 0 && (
                <PreviewTable
                  title={`Mill Techno Parameters (${technoPreview.techno_param_rows.filter(r => r.status === 'ok').length} ok) → techno_monthly`}
                  headers={['Plant', 'Shop', 'Parameter', 'Unit', 'Month', 'Actual', 'Cum', 'Cell', 'Found via', 'Status']}
                  rows={technoPreview.techno_param_rows.map((r) => [
                    r.plant, r.section, r.parameter, r.unit, r.month, r.actual ?? '', r.cum_actual ?? '', r.cell, r.found_via, r.status,
                  ])}
                />
              )}

              <div style={{ fontSize: '8pt', color: '#94a3b8', marginTop: 8 }}>
                Production: only <strong style={{ color: '#34d399' }}>ticked</strong> rows are inserted — untick any
                row to skip it, or type an item name on an <strong style={{ color: '#f87171' }}>unmapped</strong> row
                to map &amp; include it (raw tonne values are stored as &apos;000T). Renamed / newly mapped labels are
                remembered and applied automatically in future {technoPreview.plant} extractions.
                Techno tables: rows with status <strong style={{ color: '#34d399' }}>ok</strong> are inserted;
                "not found" / "no value" rows are skipped.
              </div>
            </div>
          )}

          {/* DSP PDF — three independent block preview panels */}
          {dspProdResult && (
            <div style={{ padding: '20px', backgroundColor: '#1e293b', border: '1px solid #10b981', borderRadius: '8px' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 10 }}>
                <h3 style={{ fontSize: '11pt', fontWeight: 700, color: '#f1f5f9', margin: 0 }}>
                  Step 1 — Production&nbsp;
                  <span style={{ fontSize: '8pt', color: '#94a3b8', fontWeight: 400 }}>
                    DSP {dspProdResult.month} · {dspProdResult.source_type}
                  </span>
                </h3>
                <div style={{ display: 'flex', gap: 8 }}>
                  <button onClick={() => { setDspProdResult(null); setDspProdRows([]); }}
                          disabled={dspBusy.production}
                          style={{ background: 'none', border: '1px solid #64748b', borderRadius: 4,
                                   color: '#94a3b8', fontSize: '8.5pt', padding: '5px 12px', cursor: 'pointer' }}>
                    Discard
                  </button>
                  <button onClick={() => handleDspInsert('production')}
                          disabled={dspBusy.production}
                          style={{ backgroundColor: '#10b981', border: '1px solid #10b981', borderRadius: 4,
                                   color: '#fff', fontSize: '8.5pt', fontWeight: 700, padding: '5px 14px', cursor: 'pointer' }}>
                    {dspBusy.production ? 'Inserting...' : `Insert Production (${dspProdRows.filter(r => r.selected && (r.item_edit||'').trim()).length} rows)`}
                  </button>
                </div>
              </div>
              <EditableProductionTable plant="DSP" rows={dspProdRows}
                onToggle={toggleDspProdRow} onEditName={editDspProdName} />
            </div>
          )}

          {dspTechnoResult && (
            <div style={{ padding: '20px', backgroundColor: '#1e293b', border: '1px solid #8b5cf6', borderRadius: '8px' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 10 }}>
                <h3 style={{ fontSize: '11pt', fontWeight: 700, color: '#f1f5f9', margin: 0 }}>
                  Step 2 — Techno Parameters&nbsp;
                  <span style={{ fontSize: '8pt', color: '#94a3b8', fontWeight: 400 }}>
                    DSP {dspTechnoResult.month}
                  </span>
                </h3>
                <div style={{ display: 'flex', gap: 8 }}>
                  <button onClick={() => setDspTechnoResult(null)}
                          disabled={dspBusy.techno}
                          style={{ background: 'none', border: '1px solid #64748b', borderRadius: 4,
                                   color: '#94a3b8', fontSize: '8.5pt', padding: '5px 12px', cursor: 'pointer' }}>
                    Discard
                  </button>
                  <button onClick={() => handleDspInsert('techno')}
                          disabled={dspBusy.techno}
                          style={{ backgroundColor: '#8b5cf6', border: '1px solid #8b5cf6', borderRadius: 4,
                                   color: '#fff', fontSize: '8.5pt', fontWeight: 700, padding: '5px 14px', cursor: 'pointer' }}>
                    {dspBusy.techno ? 'Inserting...' : `Insert Techno (${(dspTechnoResult.techno_param_rows||[]).filter(r=>r.status==='ok').length} rows)`}
                  </button>
                </div>
              </div>
              <PreviewTable
                title={`Techno Parameters — ${(dspTechnoResult.techno_param_rows||[]).filter(r=>r.status==='ok').length} ok → techno_monthly`}
                headers={['Group', 'Section', 'Parameter', 'Unit', 'Actual', 'Cum', 'Cell', 'Status']}
                rows={(dspTechnoResult.techno_param_rows||[]).map((r) => [
                  r.group_code, r.section, r.parameter, r.unit,
                  r.actual ?? '', r.cum_actual ?? '', r.cell, r.status,
                ])}
              />
            </div>
          )}

          {dspSsResult && (
            <div style={{ padding: '20px', backgroundColor: '#1e293b', border: '1px solid #f59e0b', borderRadius: '8px' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 10 }}>
                <h3 style={{ fontSize: '11pt', fontWeight: 700, color: '#f1f5f9', margin: 0 }}>
                  Step 3 — Special Steel&nbsp;
                  <span style={{ fontSize: '8pt', color: '#94a3b8', fontWeight: 400 }}>
                    DSP {dspSsResult.month}
                  </span>
                </h3>
                <div style={{ display: 'flex', gap: 8 }}>
                  <button onClick={() => { setDspSsResult(null); setDspSsRows([]); }}
                          disabled={dspBusy.special_steel}
                          style={{ background: 'none', border: '1px solid #64748b', borderRadius: 4,
                                   color: '#94a3b8', fontSize: '8.5pt', padding: '5px 12px', cursor: 'pointer' }}>
                    Discard
                  </button>
                  <button onClick={() => handleDspInsert('special_steel')}
                          disabled={dspBusy.special_steel}
                          style={{ backgroundColor: '#f59e0b', border: '1px solid #f59e0b', borderRadius: 4,
                                   color: '#fff', fontSize: '8.5pt', fontWeight: 700, padding: '5px 14px', cursor: 'pointer' }}>
                    {dspBusy.special_steel ? 'Inserting...' : `Insert Special Steel (${dspSsRows.filter(r=>r.selected&&r.status==='ok').length} rows)`}
                  </button>
                </div>
              </div>
              {dspSsResult.special_steel_note && (
                <div style={{ fontSize: '8pt', color: '#fbbf24', margin: '4px 0 8px' }}>
                  {dspSsResult.special_steel_note}
                </div>
              )}
              <EditableSpecialSteelTable plant="DSP" rows={dspSsRows}
                onToggle={toggleDspSsRow} onEditGrade={editDspSsGrade} onEditSection={editDspSsSection} />
            </div>
          )}

          {/* ASP PDF — single-step extract & preview panel */}
          {aspResult && (
            <div style={{ padding: '20px', backgroundColor: '#1e293b', border: '1px solid #0ea5e9', borderRadius: '8px' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 10 }}>
                <h3 style={{ fontSize: '11pt', fontWeight: 700, color: '#f1f5f9', margin: 0 }}>
                  ASP —&nbsp;
                  {aspResult.report_type === 'EXCEL' ? 'Crude Steel (Excel)'
                    : aspResult.report_type === 'REP' ? 'Crude Steel (REP PDF)'
                    : 'Finished Steel (FL PDF)'}
                  &nbsp;<span style={{ fontSize: '8pt', color: '#94a3b8', fontWeight: 400 }}>
                    ASP {aspResult.month} · {aspResult.source_type}
                  </span>
                </h3>
                <div style={{ display: 'flex', gap: 8 }}>
                  <button onClick={() => { setAspResult(null); setAspProdRows([]); }}
                          disabled={aspBusy}
                          style={{ background: 'none', border: '1px solid #64748b', borderRadius: 4,
                                   color: '#94a3b8', fontSize: '8.5pt', padding: '5px 12px', cursor: 'pointer' }}>
                    Discard
                  </button>
                  <button onClick={handleAspInsert}
                          disabled={aspBusy}
                          style={{ backgroundColor: '#0ea5e9', border: '1px solid #0ea5e9', borderRadius: 4,
                                   color: '#fff', fontSize: '8.5pt', fontWeight: 700, padding: '5px 14px', cursor: 'pointer' }}>
                    {aspBusy ? 'Inserting...' : `Insert ${aspProdRows.filter(r => r.selected && (r.item_edit||'').trim()).length} rows into DB`}
                  </button>
                </div>
              </div>

              {/* Report type badge */}
              <div style={{ marginBottom: 10 }}>
                {(() => {
                  const rt = aspResult.report_type;
                  const color = rt === 'EXCEL' ? '#38bdf8' : rt === 'REP' ? '#34d399' : '#fbbf24';
                  const bg    = rt === 'EXCEL' ? 'rgba(56,189,248,0.12)' : rt === 'REP' ? 'rgba(16,185,129,0.15)' : 'rgba(245,158,11,0.15)';
                  const label = rt === 'EXCEL'
                    ? `Excel (${aspResult.sheets}) — cells F10/F11/F12/F20/L25 → Crude Steel, Concast, Ingot, Saleable, Stock`
                    : rt === 'REP'
                    ? 'REP PDF — OMI Production (Crude Steel, Ingot, Concast, Saleable, Stock)'
                    : 'FL PDF — Finished Steel by Mill (BARS + FS PRD + PL MILL)';
                  return (
                    <span style={{ display: 'inline-block', padding: '2px 10px', borderRadius: 4,
                                   fontSize: '8pt', fontWeight: 700, backgroundColor: bg,
                                   color, border: `1px solid ${color}` }}>
                      {label}
                    </span>
                  );
                })()}
              </div>

              <EditableProductionTable plant="ASP" rows={aspProdRows}
                onToggle={toggleAspRow} onEditName={editAspRowName} />

              <div style={{ fontSize: '8pt', color: '#94a3b8', marginTop: 8 }}>
                All values converted from Tonnes → &apos;000T automatically. Tick/untick rows to include or skip.
                Edit item names to override the DB mapping. For multi-month PDFs, verify the &quot;Value&quot; column
                matches the expected month-end figure (extractor picks the largest number on each keyword line).
              </div>
            </div>
          )}

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
