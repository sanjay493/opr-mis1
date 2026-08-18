'use client';

import React, { useState } from 'react';
import GlobalNavbar from '@/components/GlobalNavbar';

const API = process.env.NEXT_PUBLIC_API_URL || '';

function previousMonth() {
  const now = new Date();
  const y = now.getFullYear();
  const m = now.getMonth(); // 0-based == "last month" 1-based
  const py = m === 0 ? y - 1 : y;
  const pm = m === 0 ? 12 : m;
  return `${py}-${String(pm).padStart(2, '0')}`;
}

const cardStyle = {
  padding: '20px 24px',
  border: '1px solid #dadce0',
  borderRadius: '8px',
  backgroundColor: '#f8f9fa',
  marginBottom: '24px',
};

const btnStyle = (disabled) => ({
  padding: '9px 24px',
  fontSize: '11pt',
  fontWeight: 700,
  border: 'none',
  borderRadius: '6px',
  cursor: disabled ? 'not-allowed' : 'pointer',
  backgroundColor: disabled ? '#dadce0' : '#1a73e8',
  color: '#ffffff',
});

const selectStyle = {
  padding: '9px 14px',
  fontSize: '11pt',
  border: '1px solid #dadce0',
  borderRadius: '6px',
  backgroundColor: '#ffffff',
  minWidth: '140px',
};

const TABLE_ORDER = [
  ['1a', '1a. Production Overview'],
  ['1b', '1b. Producer wise Production'],
  ['1c', '1c. Steel Prices'],
  ['2', '2. Demand'],
  ['3a', '3a. Finished Steel — Import & Export'],
  ['4a', '4a. Domestic Raw Material Prices'],
  ['5', '5. Key Indices'],
];
const TEXT_ORDER = ['6', '7', '8'];

function GenericTablePreview({ table }) {
  if (!table) return <p style={{ fontSize: '9.5pt', color: '#c5221f' }}>Not found in the uploaded PDF.</p>;
  return (
    <div style={{ overflowX: 'auto', marginBottom: '16px' }}>
      <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '9.5pt' }}>
        <thead>
          <tr style={{ backgroundColor: '#e8f0fe' }}>
            {table.headers.map((h, i) => (
              <th key={i} style={{ textAlign: i === 0 ? 'left' : 'right', padding: '6px 8px' }}>{h}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {table.rows.map((row, ri) => (
            <tr key={ri} style={{ borderBottom: '1px solid #e8eaed' }}>
              {row.map((cell, ci) => (
                <td key={ci} style={{ padding: '5px 8px', textAlign: ci === 0 ? 'left' : 'right' }}>
                  {cell === null || cell === undefined || cell === '' ? '—' : cell}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export default function SteelSectorPerformancePage() {
  const [srcMonth, setSrcMonth] = useState(previousMonth());
  const [file, setFile] = useState(null);
  const [preview, setPreview] = useState(null);
  const [extracting, setExtracting] = useState(false);
  const [saving, setSaving] = useState(false);
  const [saveResult, setSaveResult] = useState(null);
  const [error, setError] = useState(null);

  const handleExtract = async () => {
    if (!file) return;
    setExtracting(true);
    setError(null);
    setPreview(null);
    setSaveResult(null);
    try {
      const fd = new FormData();
      fd.append('file', file);
      fd.append('month', srcMonth);
      const res = await fetch(`${API}/api/steel-sector-performance/preview`, { method: 'POST', body: fd });
      const body = await res.json();
      if (!res.ok) throw new Error(body.detail || `HTTP ${res.status}`);
      setPreview(body);
    } catch (e) {
      setError(`Extraction failed: ${e.message}`);
    } finally {
      setExtracting(false);
    }
  };

  const handleSave = async () => {
    if (!preview) return;
    setSaving(true);
    setError(null);
    try {
      const res = await fetch(`${API}/api/steel-sector-performance/confirm`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(preview),
      });
      const body = await res.json();
      if (!res.ok) throw new Error(body.detail || `HTTP ${res.status}`);
      setSaveResult(body);
    } catch (e) {
      setError(`Save failed: ${e.message}`);
    } finally {
      setSaving(false);
    }
  };

  return (
    <div style={{ minHeight: '100vh', backgroundColor: '#ffffff' }}>
      <GlobalNavbar />
      <main style={{ maxWidth: '1100px', margin: '0 auto', padding: '32px' }}>
        <div style={{ marginBottom: '24px' }}>
          <h1 style={{ fontSize: '20pt', fontWeight: 900, color: '#202124', margin: 0 }}>
            Indian Steel Sector Performance
          </h1>
          <p style={{ fontSize: '11pt', color: '#5f6368', marginTop: '6px' }}>
            Upload the monthly PIB (Ministry of Steel) &quot;Indian Steel Sector Performance&quot; PDF
            (Report_format/&quot;Indian Steel Sector Performance in &lt;Mon&gt;&apos;&lt;YY&gt;.pdf&quot;).
            Every table and narrative section is extracted for review below; Table 1a&apos;s SAIL rows
            and % share of India are computed automatically when the report is generated, not here.
          </p>
        </div>

        <div style={cardStyle}>
          <div style={{ fontSize: '11pt', fontWeight: 700, color: '#202124', marginBottom: '12px' }}>
            Extract from source PDF
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '16px', flexWrap: 'wrap' }}>
            <label style={{ fontSize: '11pt', fontWeight: 600 }}>Report month</label>
            <input
              type="month"
              value={srcMonth}
              onChange={(e) => setSrcMonth(e.target.value)}
              style={selectStyle}
            />
            <input
              type="file"
              accept=".pdf"
              onChange={(e) => setFile(e.target.files?.[0] || null)}
              style={{ fontSize: '10.5pt' }}
            />
            <button onClick={handleExtract} disabled={!file || extracting} style={btnStyle(!file || extracting)}>
              {extracting ? 'Extracting…' : 'Extract'}
            </button>
          </div>
        </div>

        {error && (
          <div style={{ padding: '14px 18px', border: '1px solid #f28b82', borderRadius: '8px', backgroundColor: '#fce8e6', color: '#c5221f', fontSize: '11pt', marginBottom: '24px' }}>
            {error}
          </div>
        )}

        {preview && (
          <div style={cardStyle}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '14px' }}>
              <div style={{ fontSize: '11pt', fontWeight: 700, color: '#202124' }}>
                Preview — review before saving
              </div>
              <button onClick={handleSave} disabled={saving} style={btnStyle(saving)}>
                {saving ? 'Saving…' : 'Save to database'}
              </button>
            </div>

            {saveResult && (
              <div style={{ padding: '10px 14px', backgroundColor: '#e6f4ea', color: '#137333', borderRadius: '6px', fontSize: '10.5pt', marginBottom: '14px' }}>
                Saved for {saveResult.report_month}.
              </div>
            )}

            <p style={{ fontSize: '10pt', fontWeight: 600, marginBottom: '2px' }}>{preview.title}</p>
            <p style={{ fontSize: '9pt', color: '#9aa0a6', marginTop: 0, marginBottom: '16px' }}>{preview.posted_on}</p>

            {TABLE_ORDER.map(([key, label]) => (
              <div key={key}>
                <div style={{ fontSize: '10.5pt', fontWeight: 700, marginBottom: '4px' }}>{label}</div>
                <GenericTablePreview table={preview.tables?.[key]} />
              </div>
            ))}

            {TEXT_ORDER.map((key) => {
              const section = preview.text_sections?.[key];
              if (!section) return null;
              return (
                <div key={key} style={{ marginBottom: '16px' }}>
                  <div style={{ fontSize: '10.5pt', fontWeight: 700, marginBottom: '4px' }}>{section.heading}</div>
                  {section.paragraphs.map((p, i) => (
                    <p key={i} style={{ fontSize: '9.5pt', lineHeight: 1.4, margin: '0 0 6px' }}>{p}</p>
                  ))}
                </div>
              );
            })}

            {preview.footer_note && (
              <p style={{ fontSize: '9pt', fontStyle: 'italic', color: '#5f6368' }}>{preview.footer_note}</p>
            )}
          </div>
        )}
      </main>
    </div>
  );
}
