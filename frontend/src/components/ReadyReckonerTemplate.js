'use client';

import React, { useRef, useState } from 'react';
import { useAuth, API_BASE_URL } from '@/providers/AuthProvider';

// Mirrors backend/page_templates/ready_reckoner_plant.html. 2 pages per
// plant (process flow / unit-wise capacity + product mix consolidated onto
// one page, per direct instruction 2026-09-21 — was 3 separate pages until
// then), distinguished by `data.subtype`. Unlike every other page in this
// report, this content is static reference material (not month-scoped).
//
// Capacity/Product Mix are read-only here (per direct instruction,
// 2026-09-21 — no HTML/formatting entry in table rows/columns): editing
// happens exclusively in the structured /data-entry/ready-reckoner form,
// which sends plain data (no markup) to the same backend row this preview
// reads. Rendering is plain JS/JSX building a real <table> from that data
// at display time, coloring the Item/Details columns and bolding
// is_total rows in code — nothing rendered here ever came from
// dangerouslySetInnerHTML. The process-flow diagram upload is still
// editable here (it's a file, not a text/table field).
function CapacityTable({ rows }) {
  if (!rows || rows.length === 0) {
    return <div style={{ textAlign: 'center', fontStyle: 'italic', padding: '40px 0', color: '#5f6368' }}>No capacity data yet.</div>;
  }
  const th = { border: '0.5pt solid #5f6368', padding: '3px 5px', fontWeight: 700 };
  const td = { border: '0.5pt solid #5f6368', padding: '3px 5px', whiteSpace: 'pre-line' };
  return (
    <table style={{ borderCollapse: 'collapse', width: '100%', fontSize: '12pt' }}>
      <thead>
        <tr><th style={th}>Facility</th><th style={th}>Details</th><th style={th}>Capacity</th></tr>
      </thead>
      <tbody>
        {rows.map((row, i) => (
          <tr key={i} style={row.is_total ? { fontWeight: 700 } : undefined}>
            <td style={{ ...td, color: '#8b4513' }}>{row.item}</td>
            <td style={{ ...td, color: '#1a56db' }}>{row.details}</td>
            <td style={td}>{row.capacity}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function ProductMixTable({ headers, rows, caption }) {
  if (!headers || headers.length === 0) {
    return <div style={{ textAlign: 'center', fontStyle: 'italic', padding: '40px 0', color: '#5f6368' }}>No product mix data yet.</div>;
  }
  const th = { border: '0.5pt solid #5f6368', padding: '3px 5px', fontWeight: 700 };
  const td = { border: '0.5pt solid #5f6368', padding: '3px 5px', whiteSpace: 'pre-line' };
  return (
    <>
      {caption && <div style={{ fontWeight: 700, marginBottom: 4, fontSize: '12pt' }}>{caption}</div>}
      <table style={{ borderCollapse: 'collapse', width: '100%', fontSize: '12pt' }}>
        <thead>
          <tr>{headers.map((h, i) => <th key={i} style={th}>{h}</th>)}</tr>
        </thead>
        <tbody>
          {rows.map((row, i) => (
            <tr key={i} style={row.is_total ? { fontWeight: 700 } : undefined}>
              {row.cells.map((cell, j) => <td key={j} style={td}>{cell}</td>)}
            </tr>
          ))}
        </tbody>
      </table>
    </>
  );
}

export default function ReadyReckonerTemplate({ data }) {
  const { user } = useAuth();
  const isEditor = !!user && (user.role === 'editor' || user.role === 'admin');

  const {
    plant_code: plantCode,
    plant_name: plantName,
    subtype,
    subtype_label: subtypeLabel,
    image_data_uri: imageDataUri,
    capacity_rows: capacityRows,
    product_mix_headers: productMixHeaders,
    product_mix_rows: productMixRows,
    product_mix_caption: productMixCaption,
  } = data || {};

  const fileInputRef = useRef(null);
  const [imgSrc, setImgSrc] = useState(imageDataUri || '');
  const [saving, setSaving] = useState(false);
  const [savedAt, setSavedAt] = useState(null);

  const handleImageUpload = async (e) => {
    const file = e.target.files && e.target.files[0];
    if (!file) return;
    const form = new FormData();
    form.append('file', file);
    setSaving(true);
    try {
      const res = await fetch(`${API_BASE_URL}/api/ready-reckoner/${plantCode}/image`, {
        method: 'POST',
        credentials: 'include',
        body: form,
      });
      if (!res.ok) throw new Error(await res.text());
      setImgSrc(URL.createObjectURL(file));
      setSavedAt(new Date());
    } catch (err) {
      alert('Image upload failed: ' + err.message);
    } finally {
      setSaving(false);
      if (fileInputRef.current) fileInputRef.current.value = '';
    }
  };

  return (
    <div style={{ fontFamily: 'inherit' }}>
      <div style={{ textAlign: 'center', fontWeight: 700, fontSize: '15pt', color: '#1e3a8a', textDecoration: 'underline', marginBottom: 2 }}>
        {plantName}
      </div>
      <div style={{ textAlign: 'center', fontWeight: 600, fontSize: '11pt', color: '#5f6368', marginBottom: 10 }}>
        {subtypeLabel}
      </div>

      {subtype === 'process_flow' && (
        <>
          {isEditor && (
            <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', gap: 8, marginBottom: 8 }}>
              <button type="button" className="btn btn-sm" onClick={() => fileInputRef.current && fileInputRef.current.click()} disabled={saving}>
                Replace diagram
              </button>
              <input ref={fileInputRef} type="file" accept="image/*" onChange={handleImageUpload} style={{ display: 'none' }} />
              {savedAt && (
                <span style={{ fontSize: '8pt', color: '#5f6368' }}>Saved {savedAt.toLocaleTimeString()}</span>
              )}
            </div>
          )}
          {imgSrc ? (
            <div style={{ textAlign: 'center' }}>
              <img src={imgSrc} alt={`${plantName || ''} Process Flow`} style={{ maxWidth: '100%', maxHeight: 700 }} />
            </div>
          ) : (
            <div style={{ textAlign: 'center', fontStyle: 'italic', padding: '60px 0', color: '#5f6368' }}>
              No process-flow diagram uploaded yet.
            </div>
          )}
        </>
      )}

      {subtype === 'details' && (
        <>
          <div style={{ fontWeight: 700, marginBottom: 4, fontSize: '12pt' }}>Unit-wise Capacity</div>
          <CapacityTable rows={capacityRows} />
          <div style={{ fontWeight: 700, margin: '10px 0 4px', fontSize: '12pt' }}>
            Product Mix{productMixCaption ? ` — ${productMixCaption}` : ''}
          </div>
          <ProductMixTable headers={productMixHeaders} rows={productMixRows} />
          {isEditor && (
            <div style={{ textAlign: 'center', marginTop: 8, fontSize: '8pt', color: '#5f6368' }}>
              Read-only here — edit at <a href="/data-entry/ready-reckoner">Data Entry &rarr; Ready Reckoner</a>.
            </div>
          )}
        </>
      )}
    </div>
  );
}
