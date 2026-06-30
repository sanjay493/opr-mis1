'use client';

import React, { useState } from 'react';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://127.0.0.1:8082';

export default function BSLBFTechnoExtractor({ reportMonth, apiBase = API_BASE_URL, onSuccess }) {
  const [file, setFile] = useState(null);
  const [loading, setLoading] = useState(false);
  const [status, setStatus] = useState(null);
  const [data, setData] = useState(null);
  const [saving, setSaving] = useState(false);
  const inputRef = React.useRef();

  const parameters = [
    { key: 'production', label: 'Production (T)', type: 'number' },
    { key: 'bf_productivity', label: 'BF Productivity (t/m³/day)', type: 'number', step: '0.01' },
    { key: 'coke_rate', label: 'Coke Rate (kg/THM)', type: 'number', step: '0.01' },
    { key: 'cdi', label: 'CDI Rate (kg/THM)', type: 'number', step: '0.01' },
    { key: 'fuel_rate', label: 'Fuel Rate (kg/THM)', type: 'number', step: '0.01' },
    { key: 'hot_blast_temp', label: 'Hot Blast Temp (°C)', type: 'number' },
    { key: 'o2_enrichment', label: 'O2 Enrichment (%)', type: 'number', step: '0.01' },
    { key: 'slag_rate', label: 'Slag Rate (kg/THM)', type: 'number', step: '0.01' },
  ];

  // Handle file selection
  const handleFileSelect = (e) => {
    setFile(e.target.files[0]);
    setStatus(null);
    setData(null);
  };

  // Handle PDF extraction - directly load into editable table
  const handleExtract = async (debug = false) => {
    if (!file) return;

    setLoading(true);
    setStatus(null);
    const form = new FormData();
    form.append('file', file);
    form.append('month', reportMonth);

    try {
      const endpoint = debug ? '/api/bsl-bf-techno/debug' : '/api/bsl-bf-techno/preview';
      const res = await fetch(`${apiBase}${endpoint}`, {
        method: 'POST',
        body: form,
      });

      const json = await res.json();

      if (!res.ok) {
        throw new Error(json.detail || 'Extraction failed');
      }

      if (debug) {
        // Show debug info
        setStatus({
          type: 'info',
          text: `PDF loaded: ${json.pdf_text_length} chars. Prod section: ${json.has_production_section ? 'Yes' : 'No'}, Quality: ${json.has_quality_section ? 'Yes' : 'No'}`,
        });
        console.log('DEBUG INFO:', json);
      } else {
        // Set data directly - no separate extracted state
        setData(json.data.map(row => ({ ...row })));
        const msg = json.data.length > 0
          ? `Extracted ${json.total_records} furnaces for ${reportMonth}. Edit values directly in the table.`
          : `Found ${json.total_records} furnaces but no data values. Check PDF format or click Debug for details.`;
        setStatus({ type: 'success', text: msg });
      }
    } catch (err) {
      setStatus({ type: 'error', text: err.message });
      setData(null);
    } finally {
      setLoading(false);
    }
  };

  // Handle cell edit - single data state
  const handleCellChange = (rowIndex, key, value) => {
    const updated = [...data];
    updated[rowIndex][key] = value === '' ? null : (isNaN(parseFloat(value)) ? value : parseFloat(value));
    setData(updated);
  };

  // Add new row
  const handleAddRow = () => {
    const newRow = {
      id: `new_${Date.now()}`,
      unit: '',
      ...Object.fromEntries(parameters.map(p => [p.key, null])),
    };
    setData([...data, newRow]);
  };

  // Remove row
  const handleRemoveRow = (rowIndex) => {
    const updated = data.filter((_, i) => i !== rowIndex);
    setData(updated);
  };

  // Handle save
  const handleSave = async () => {
    if (!data || data.length === 0) {
      setStatus({ type: 'error', text: 'No data to save' });
      return;
    }

    setSaving(true);
    try {
      const res = await fetch(`${apiBase}/api/bsl-bf-techno/save`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          month: reportMonth,
          data: data,
        }),
      });

      const json = await res.json();

      if (!res.ok) {
        throw new Error(json.detail || 'Save failed');
      }

      setStatus({ type: 'success', text: `✓ Saved ${json.records_saved} records successfully` });
      setData(null);
      setFile(null);
      if (inputRef.current) inputRef.current.value = '';
      if (onSuccess) onSuccess();
    } catch (err) {
      setStatus({ type: 'error', text: err.message });
    } finally {
      setSaving(false);
    }
  };

  // Styles - IMPROVED DESIGN
  const styles = {
    container: {
      padding: '20px',
      background: '#f0fdf4',
      border: '2px solid #86efac',
      borderRadius: '10px',
      marginBottom: '20px',
      display: 'flex',
      flexDirection: 'column',
    },
    title: {
      fontSize: '18px',
      fontWeight: '700',
      color: '#166534',
      marginBottom: '16px',
    },
    uploadSection: {
      display: 'flex',
      alignItems: 'center',
      gap: '12px',
      flexWrap: 'wrap',
      padding: '14px 16px',
      background: '#fff',
      border: '2px solid #dcfce7',
      borderRadius: '8px',
      marginBottom: '16px',
    },
    fileInput: {
      fontSize: '13px',
      flex: 1,
      minWidth: '200px',
    },
    button: {
      padding: '8px 18px',
      background: '#166534',
      color: '#fff',
      border: 'none',
      borderRadius: '7px',
      fontSize: '13px',
      cursor: 'pointer',
      fontWeight: '600',
      whiteSpace: 'nowrap',
      transition: 'all 0.2s',
    },
    buttonDisabled: {
      background: '#94a3b8',
      cursor: 'not-allowed',
      opacity: 0.6,
    },
    buttonSecondary: {
      background: '#059669',
    },
    statusMsg: (type) => ({
      padding: '12px 16px',
      borderRadius: '7px',
      marginBottom: '16px',
      fontSize: '14px',
      fontWeight: '500',
      background: type === 'success' ? '#f0fdf4' : '#fef2f2',
      color: type === 'success' ? '#166534' : '#991b1b',
      border: `2px solid ${type === 'success' ? '#86efac' : '#fca5a5'}`,
    }),
    infoLabel: {
      fontSize: '14px',
      fontWeight: '600',
      color: '#475569',
      marginBottom: '12px',
      marginTop: '4px',
    },
    helperText: {
      fontSize: '13px',
      color: '#64748b',
      lineHeight: '1.5',
      marginTop: '4px',
    },
    warningText: {
      display: 'block',
      marginTop: '8px',
      color: '#d97706',
      fontSize: '13px',
      fontWeight: '500',
    },
    tableWrapper: {
      overflowX: 'auto',
      marginBottom: '16px',
      borderRadius: '8px',
      border: '1px solid #e2e8f0',
    },
    table: {
      width: '100%',
      borderCollapse: 'collapse',
      fontSize: '13px',
      background: '#fff',
      minWidth: '1000px',
    },
    th: {
      padding: '12px 14px',
      textAlign: 'left',
      background: '#f1f5f9',
      borderBottom: '2px solid #cbd5e1',
      fontWeight: '600',
      color: '#334155',
      fontSize: '13px',
      whiteSpace: 'nowrap',
    },
    td: {
      padding: '10px 14px',
      borderBottom: '1px solid #e2e8f0',
    },
    input: {
      width: '100%',
      padding: '6px 8px',
      border: '1.5px solid #cbd5e1',
      borderRadius: '5px',
      fontSize: '13px',
      fontFamily: 'inherit',
      boxSizing: 'border-box',
    },
    inputText: {
      fontWeight: '600',
      color: '#1e293b',
    },
    actionButton: {
      padding: '5px 10px',
      fontSize: '12px',
      background: '#e11d48',
      color: '#fff',
      border: 'none',
      borderRadius: '5px',
      cursor: 'pointer',
      fontWeight: '600',
      transition: 'all 0.2s',
    },
    actionButtonHover: {
      background: '#be185d',
    },
    saveButtonContainer: {
      marginTop: '16px',
      display: 'flex',
      gap: '10px',
      flexWrap: 'wrap',
    },
  };

  return (
    <div style={styles.container}>
      <div style={styles.title}>BSL BF Performance PDF Extraction</div>

      {/* File Upload Section */}
      <div style={styles.uploadSection}>
        <input
          ref={inputRef}
          type="file"
          accept=".pdf"
          onChange={handleFileSelect}
          style={styles.fileInput}
        />
        <button
          onClick={() => handleExtract(false)}
          disabled={!file || loading}
          style={{
            ...styles.button,
            ...((!file || loading) && styles.buttonDisabled),
          }}
        >
          {loading ? 'Extracting…' : 'Extract & Preview'}
        </button>
        <button
          onClick={() => handleExtract(true)}
          disabled={!file || loading}
          style={{
            ...styles.button,
            background: '#64748b',
            fontSize: '11px',
            padding: '5px 12px',
          }}
          title="Debug: Show PDF content details"
        >
          Debug
        </button>
      </div>

      {/* Status Message */}
      {status && (
        <div style={styles.statusMsg(status.type)}>
          {status.text}
        </div>
      )}

      {/* Extracted & Editable Data Table - Single View */}
      {data && data.length > 0 && (
        <div style={{ display: 'flex', flexDirection: 'column' }}>
          {/* Header Section */}
          <div style={{ marginBottom: '16px' }}>
            <div style={styles.infoLabel}>
              📊 Cumulative (Till-Month) Values - Editable Data Table
            </div>
            <div style={styles.helperText}>
              ✏️ Click any cell to edit values  |  ➕ Add rows for missing furnaces  |  ❌ Remove rows as needed
              {data.filter(r => !r.coke_rate && !r.cdi).length > 0 && (
                <span style={styles.warningText}>
                  ⚠️ Some parameters missing - manually enter or edit as needed
                </span>
              )}
            </div>
          </div>

          {/* Table Container with Scrolling */}
          <div style={styles.tableWrapper}>
            <table style={styles.table}>
              <thead>
                <tr>
                  <th style={styles.th}>Furnace</th>
                  {parameters.map(param => (
                    <th key={param.key} style={styles.th}>{param.label}</th>
                  ))}
                  <th style={{ ...styles.th, width: '80px' }}>Action</th>
                </tr>
              </thead>
              <tbody>
                {data.map((row, idx) => (
                  <tr key={row.id} style={{ background: idx % 2 === 0 ? '#fff' : '#f9fdf7' }}>
                    <td style={{ ...styles.td, ...styles.inputText, minWidth: '90px' }}>
                      <input
                        type="text"
                        value={row.unit || ''}
                        onChange={(e) => handleCellChange(idx, 'unit', e.target.value)}
                        style={{ ...styles.input, ...styles.inputText }}
                        placeholder="e.g., BF-1"
                      />
                    </td>
                    {parameters.map(param => (
                      <td key={param.key} style={{ ...styles.td, minWidth: '120px' }}>
                        <input
                          type={param.type}
                          step={param.step}
                          value={row[param.key] ?? ''}
                          onChange={(e) => handleCellChange(idx, param.key, e.target.value)}
                          style={styles.input}
                          placeholder="-"
                        />
                      </td>
                    ))}
                    <td style={{ ...styles.td, minWidth: '80px' }}>
                      <button
                        onClick={() => handleRemoveRow(idx)}
                        style={styles.actionButton}
                        title="Remove this row"
                        onMouseOver={(e) => e.target.style.background = '#be185d'}
                        onMouseOut={(e) => e.target.style.background = '#e11d48'}
                      >
                        Remove
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* Action Buttons */}
          <div style={styles.saveButtonContainer}>
            <button
              onClick={handleAddRow}
              style={{
                ...styles.button,
                ...styles.buttonSecondary,
                padding: '10px 20px',
                fontSize: '14px',
              }}
            >
              ➕ Add Row
            </button>
            <button
              onClick={handleSave}
              disabled={saving}
              style={{
                ...styles.button,
                padding: '10px 20px',
                fontSize: '14px',
                ...(saving && styles.buttonDisabled),
              }}
            >
              {saving ? '⏳ Saving…' : '💾 Save All Data'}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
