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

const smallBtnStyle = {
  padding: '4px 10px',
  fontSize: '9pt',
  fontWeight: 600,
  border: '1px solid #dadce0',
  borderRadius: '5px',
  cursor: 'pointer',
  backgroundColor: '#ffffff',
  color: '#3c4043',
};

const selectStyle = {
  padding: '9px 14px',
  fontSize: '11pt',
  border: '1px solid #dadce0',
  borderRadius: '6px',
  backgroundColor: '#ffffff',
  minWidth: '140px',
};

const cellInputStyle = (isHeader) => ({
  width: '100%',
  minWidth: '70px',
  boxSizing: 'border-box',
  padding: '5px 6px',
  fontSize: '9.5pt',
  fontWeight: isHeader ? 700 : 400,
  border: '1px solid #dadce0',
  borderRadius: '4px',
  textAlign: isHeader ? 'left' : 'right',
  backgroundColor: '#ffffff',
});

const TABLE_ORDER = [
  ['1a', '1a. Production Overview'],
  ['1b', '1b. Producer wise Production'],
  ['1c', '1c. Steel Prices'],
  ['2', '2. Demand'],
  ['3a', '3a. Finished Steel — Import & Export'],
  ['4a', '4a. Domestic Raw Material Prices'],
  ['5', '5. Key Indices'],
];
const TEXT_ORDER = [
  ['6', '6. Policy Initiatives/Industry Initiatives'],
  ['7', '7. International Co-operation'],
  ['8', '8. Green Steel Initiatives'],
];

// _clean_num from pdf_extractor_steel_sector_performance.py, mirrored here
// so production_overview_1a_items (the numeric structure page_steel_sector_
// performance.py actually reads for the SAIL-share table) stays in sync
// with whatever the user edits in table 1a's raw cells, rather than saving
// stale numbers alongside a corrected table.
function cleanNum(v) {
  if (v === null || v === undefined) return null;
  const s = String(v).trim().replace(/₹/g, '').replace(/,/g, '').replace(/%/g, '').trim();
  if (!s) return null;
  const n = Number(s);
  return Number.isNaN(n) ? null : n;
}

function rebuildProductionOverview1aItems(table1a) {
  if (!table1a || !table1a.rows) return [];
  const items = [];
  for (const row of table1a.rows) {
    if (!row || !row[0]) continue;
    const label = String(row[0]).trim();
    const cells = row.slice(1, 8);
    while (cells.length < 6) cells.push(null);
    items.push({
      item: label,
      report_month: cleanNum(cells[0]),
      cply_month: cleanNum(cells[1]),
      yoy_pct: cleanNum(cells[2]),
      apr_report_month: cleanNum(cells[3]),
      cply_apr_report_month: cleanNum(cells[4]),
      cply_pct: cleanNum(cells[5]),
    });
  }
  return items;
}

function emptyTable() {
  return { heading: null, headers: ['', ''], rows: [['', '']], row_groups: [], footnotes: [] };
}

function EditableTable({ table, onChange }) {
  const t = table || emptyTable();
  const missing = !table;

  const setHeader = (ci, val) => {
    const headers = [...t.headers];
    headers[ci] = val;
    onChange({ ...t, headers });
  };
  const setCell = (ri, ci, val) => {
    const rows = t.rows.map((r) => [...r]);
    rows[ri][ci] = val;
    onChange({ ...t, rows });
  };
  const addRow = () => {
    const rows = [...t.rows, t.headers.map(() => '')];
    onChange({ ...t, rows });
  };
  const removeRow = (ri) => {
    const rows = t.rows.filter((_, i) => i !== ri);
    onChange({ ...t, rows });
  };
  const addCol = () => {
    const headers = [...t.headers, ''];
    const rows = t.rows.map((r) => [...r, '']);
    onChange({ ...t, headers, rows });
  };
  const removeCol = (ci) => {
    if (t.headers.length <= 1) return;
    const headers = t.headers.filter((_, i) => i !== ci);
    const rows = t.rows.map((r) => r.filter((_, i) => i !== ci));
    onChange({ ...t, headers, rows });
  };

  return (
    <div style={{ marginBottom: '16px' }}>
      {missing && (
        <p style={{ fontSize: '9pt', color: '#c5221f', marginBottom: '6px' }}>
          Not found in the uploaded PDF — enter it by hand below (type the column headers first).
        </p>
      )}
      <div style={{ overflowX: 'auto' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '9.5pt' }}>
          <thead>
            <tr style={{ backgroundColor: '#e8f0fe' }}>
              {t.headers.map((h, ci) => (
                <th key={ci} style={{ padding: '4px 4px' }}>
                  <div style={{ display: 'flex', gap: '3px', alignItems: 'center' }}>
                    <input
                      value={h ?? ''}
                      onChange={(e) => setHeader(ci, e.target.value)}
                      style={cellInputStyle(true)}
                    />
                    <button
                      onClick={() => removeCol(ci)}
                      title="Remove column"
                      style={{ ...smallBtnStyle, padding: '2px 6px', color: '#c5221f' }}
                    >
                      ×
                    </button>
                  </div>
                </th>
              ))}
              <th style={{ width: '1%' }}>
                <button onClick={addCol} style={smallBtnStyle} title="Add column">+col</button>
              </th>
            </tr>
          </thead>
          <tbody>
            {t.rows.map((row, ri) => (
              <tr key={ri} style={{ borderBottom: '1px solid #e8eaed' }}>
                {t.headers.map((_, ci) => (
                  <td key={ci} style={{ padding: '3px 4px' }}>
                    <input
                      value={row[ci] ?? ''}
                      onChange={(e) => setCell(ri, ci, e.target.value)}
                      style={cellInputStyle(ci === 0)}
                    />
                  </td>
                ))}
                <td style={{ padding: '3px 4px' }}>
                  <button onClick={() => removeRow(ri)} style={{ ...smallBtnStyle, color: '#c5221f' }} title="Remove row">×</button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <button onClick={addRow} style={{ ...smallBtnStyle, marginTop: '6px' }}>+ Add Row</button>
    </div>
  );
}

function EditableTextSection({ section, heading, onChange }) {
  const s = section || { heading, paragraphs: [''] };

  const setHeading = (val) => onChange({ ...s, heading: val });
  const setPara = (i, val) => {
    const paragraphs = [...s.paragraphs];
    paragraphs[i] = val;
    onChange({ ...s, paragraphs });
  };
  const addPara = () => onChange({ ...s, paragraphs: [...s.paragraphs, ''] });
  const removePara = (i) => onChange({ ...s, paragraphs: s.paragraphs.filter((_, idx) => idx !== i) });

  return (
    <div style={{ marginBottom: '16px' }}>
      <input
        value={s.heading ?? ''}
        onChange={(e) => setHeading(e.target.value)}
        style={{ ...cellInputStyle(true), fontSize: '10.5pt', marginBottom: '6px', maxWidth: '500px' }}
      />
      {s.paragraphs.map((p, i) => (
        <div key={i} style={{ display: 'flex', gap: '6px', marginBottom: '4px', alignItems: 'flex-start' }}>
          <textarea
            value={p ?? ''}
            onChange={(e) => setPara(i, e.target.value)}
            rows={2}
            style={{ flex: 1, fontSize: '9.5pt', lineHeight: 1.4, padding: '6px 8px', border: '1px solid #dadce0', borderRadius: '4px' }}
          />
          <button onClick={() => removePara(i)} style={{ ...smallBtnStyle, color: '#c5221f' }} title="Remove paragraph">×</button>
        </div>
      ))}
      <button onClick={addPara} style={smallBtnStyle}>+ Add Paragraph</button>
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

  // Starts a fully blank preview (no PDF needed) so this month can be
  // entered by hand end-to-end when there's no source file at all, or the
  // extractor can't read it. Same shape /confirm already expects.
  const handleStartManual = () => {
    setError(null);
    setSaveResult(null);
    setPreview({
      report_month: srcMonth,
      source_type: 'Indian Steel Sector Performance (PIB, Ministry of Steel)',
      title: '',
      posted_on: '',
      tables: {},
      production_overview_1a_items: [],
      text_sections: {},
      footer_note: '',
      source_file: 'manual entry',
    });
  };

  const updateTable = (key, newTable) => {
    setPreview((prev) => ({ ...prev, tables: { ...prev.tables, [key]: newTable } }));
  };
  const updateTextSection = (key, newSection) => {
    setPreview((prev) => ({ ...prev, text_sections: { ...prev.text_sections, [key]: newSection } }));
  };

  const handleSave = async () => {
    if (!preview) return;
    setSaving(true);
    setError(null);
    try {
      // Keep the derived SAIL-share item list (what the report itself
      // reads) in sync with whatever table 1a's cells now say, whether
      // that came from the extractor or was hand-typed just now.
      const toSave = {
        ...preview,
        production_overview_1a_items: rebuildProductionOverview1aItems(preview.tables?.['1a']),
      };
      const res = await fetch(`${API}/api/steel-sector-performance/confirm`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(toSave),
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
    <div style={{ height: '100vh', display: 'flex', flexDirection: 'column', backgroundColor: '#ffffff' }}>
      <GlobalNavbar />
      <main style={{ flex: 1, overflow: 'auto', maxWidth: '1100px', margin: '0 auto', padding: '32px', width: '100%', boxSizing: 'border-box' }}>
        <div style={{ marginBottom: '24px' }}>
          <h1 style={{ fontSize: '20pt', fontWeight: 900, color: '#202124', margin: 0 }}>
            Indian Steel Sector Performance
          </h1>
          <p style={{ fontSize: '11pt', color: '#5f6368', marginTop: '6px' }}>
            Upload the monthly PIB (Ministry of Steel) &quot;Indian Steel Sector Performance&quot; PDF
            (Report_format/&quot;Indian Steel Sector Performance in &lt;Mon&gt;&apos;&lt;YY&gt;.pdf&quot;).
            Every table and narrative section is extracted for review below — every cell, heading and
            paragraph is editable before saving, so a table the extractor gets wrong (or misses
            entirely) can be corrected or typed in by hand. Table 1a&apos;s SAIL rows and % share of
            India are computed automatically when the report is generated, not here.
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
            <span style={{ fontSize: '9.5pt', color: '#5f6368' }}>or</span>
            <button onClick={handleStartManual} style={{ ...btnStyle(false), backgroundColor: '#ffffff', color: '#1a73e8', border: '1px solid #1a73e8' }}>
              Start blank (no PDF)
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
                Preview — edit anything below, then save
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

            <div style={{ marginBottom: '16px' }}>
              <div style={{ fontSize: '8.5pt', color: '#5f6368', marginBottom: '2px' }}>Title</div>
              <input
                value={preview.title ?? ''}
                onChange={(e) => setPreview((p) => ({ ...p, title: e.target.value }))}
                style={{ ...cellInputStyle(true), fontSize: '10pt', width: '100%', maxWidth: '700px' }}
              />
              <div style={{ fontSize: '8.5pt', color: '#5f6368', margin: '8px 0 2px' }}>Posted on</div>
              <input
                value={preview.posted_on ?? ''}
                onChange={(e) => setPreview((p) => ({ ...p, posted_on: e.target.value }))}
                style={{ ...cellInputStyle(false), fontSize: '9pt', width: '100%', maxWidth: '400px' }}
              />
            </div>

            {TABLE_ORDER.map(([key, label]) => (
              <div key={key}>
                <div style={{ fontSize: '10.5pt', fontWeight: 700, marginBottom: '4px' }}>{label}</div>
                <EditableTable table={preview.tables?.[key]} onChange={(t) => updateTable(key, t)} />
              </div>
            ))}

            {TEXT_ORDER.map(([key, defaultHeading]) => (
              <div key={key}>
                <EditableTextSection
                  section={preview.text_sections?.[key]}
                  heading={defaultHeading}
                  onChange={(s) => updateTextSection(key, s)}
                />
              </div>
            ))}

            <div style={{ marginTop: '8px' }}>
              <div style={{ fontSize: '8.5pt', color: '#5f6368', marginBottom: '2px' }}>Footer note</div>
              <input
                value={preview.footer_note ?? ''}
                onChange={(e) => setPreview((p) => ({ ...p, footer_note: e.target.value }))}
                style={{ ...cellInputStyle(false), fontSize: '9pt', fontStyle: 'italic', width: '100%' }}
              />
            </div>
          </div>
        )}
      </main>
    </div>
  );
}
