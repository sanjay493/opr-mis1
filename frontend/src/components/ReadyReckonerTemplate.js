'use client';

import React, { useRef, useState } from 'react';
import { useAuth, API_BASE_URL } from '@/providers/AuthProvider';

// Mirrors backend/page_templates/ready_reckoner_plant.html. 3 pages per
// plant (process flow / unit-wise capacity / product mix — split from one
// combined page per plant, 2026-09-20), distinguished by `data.subtype`.
// Unlike every other page in this report, this content is static reference
// material (not month-scoped) — an editor/admin can edit it in place,
// straight from the live preview, via its own dedicated save endpoints
// (/api/ready-reckoner/{plant_code} and .../image), bypassing the generic
// per-report-month onCellChange -> /api/data flow entirely (see
// backend/page_ready_reckoner.py and db.py's ready_reckoner_pages table).
// Each page's Save action only ever sends the ONE field it owns — the
// backend leaves any field absent from the payload untouched, so the
// capacity page's Save can never blank out product_mix_html and vice
// versa (see db.save_ready_reckoner_content).
//
// The content block is an uncontrolled contentEditable div: its innerHTML
// is set once from `data` via dangerouslySetInnerHTML and read back
// through a ref at save time, so typing doesn't fight React's render cycle
// (a controlled contentEditable re-renders on every keystroke and loses
// the caret position).
export default function ReadyReckonerTemplate({ data }) {
  const { user } = useAuth();
  const isEditor = !!user && (user.role === 'editor' || user.role === 'admin');

  const {
    plant_code: plantCode,
    plant_name: plantName,
    subtype,
    subtype_label: subtypeLabel,
    image_data_uri: imageDataUri,
    capacity_html: capacityHtml,
    product_mix_html: productMixHtml,
  } = data || {};

  const contentRef = useRef(null);
  const fileInputRef = useRef(null);
  const [imgSrc, setImgSrc] = useState(imageDataUri || '');
  const [saving, setSaving] = useState(false);
  const [savedAt, setSavedAt] = useState(null);

  const fieldKey = subtype === 'capacity' ? 'capacity_html' : subtype === 'product_mix' ? 'product_mix_html' : null;
  const initialHtml = subtype === 'capacity' ? capacityHtml : subtype === 'product_mix' ? productMixHtml : '';

  const handleSaveContent = async () => {
    if (!fieldKey) return;
    setSaving(true);
    try {
      const res = await fetch(`${API_BASE_URL}/api/ready-reckoner/${plantCode}`, {
        method: 'POST',
        credentials: 'include',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ [fieldKey]: contentRef.current ? contentRef.current.innerHTML : initialHtml }),
      });
      if (!res.ok) throw new Error(await res.text());
      setSavedAt(new Date());
    } catch (err) {
      alert('Save failed: ' + err.message);
    } finally {
      setSaving(false);
    }
  };

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

      {(subtype === 'capacity' || subtype === 'product_mix') && (
        <>
          {isEditor && (
            <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', gap: 8, marginBottom: 8 }}>
              <button type="button" className="btn btn-sm btn-primary" onClick={handleSaveContent} disabled={saving}>
                {saving ? 'Saving…' : 'Save content'}
              </button>
              {savedAt && (
                <span style={{ fontSize: '8pt', color: '#5f6368' }}>Saved {savedAt.toLocaleTimeString()}</span>
              )}
            </div>
          )}
          <div
            ref={contentRef}
            contentEditable={isEditor}
            suppressContentEditableWarning
            style={{
              fontSize: '9pt',
              outline: isEditor ? '1px dashed #94a3b8' : 'none',
              padding: isEditor ? 4 : 0,
            }}
            dangerouslySetInnerHTML={{ __html: initialHtml || '' }}
          />
        </>
      )}
    </div>
  );
}
