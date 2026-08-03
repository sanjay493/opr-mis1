'use client';

import React, { useState, useEffect, useCallback } from 'react';
import GlobalNavbar from '@/components/GlobalNavbar';

const API = process.env.NEXT_PUBLIC_API_URL || '';

// Matches page_do_letter.py's own remark-eligible rows exactly — ASP/SSP
// get their own row (and remark) in the Crude Steel table, but are folded
// into a single "Special Steel Plants" row (no individual remark) in the
// Finished Steel table.
const REMARK_PLANTS = {
  'Crude Steel': ['BSP', 'DSP', 'RSP', 'BSL', 'ISP', 'ASP', 'SSP'],
  'Finished Steel': ['BSP', 'DSP', 'RSP', 'BSL', 'ISP'],
};

const MONTH_NAMES = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];

function monthLabel(ym) {
  const [y, m] = ym.split('-');
  return `${MONTH_NAMES[parseInt(m, 10) - 1]}'${y.slice(2)}`;
}

// This letter is due the 1st of the month AFTER the one it reports — so
// "last month" (not the current calendar month) is the sensible default.
function previousMonth() {
  const now = new Date();
  const y = now.getFullYear();
  const m = now.getMonth(); // 0-based == last month's 1-based number
  const py = m === 0 ? y - 1 : y;
  const pm = m === 0 ? 12 : m;
  return `${py}-${String(pm).padStart(2, '0')}`;
}

export default function DoLetterPage() {
  const [month, setMonth] = useState(previousMonth());
  const [remarks, setRemarks] = useState({ 'Crude Steel': {}, 'Finished Steel': {} });
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [downloading, setDownloading] = useState(null); // 'docx' | 'xlsx' | null
  const [error, setError] = useState(null);
  const [saveMsg, setSaveMsg] = useState(null);

  const loadRemarks = useCallback(async (ym) => {
    setLoading(true);
    setError(null);
    setSaveMsg(null);
    try {
      const res = await fetch(`${API}/api/do-letter/remarks?month=${encodeURIComponent(ym)}`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      setRemarks({
        'Crude Steel': data['Crude Steel'] || {},
        'Finished Steel': data['Finished Steel'] || {},
      });
    } catch (e) {
      setError(`Failed to load remarks: ${e.message}`);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { loadRemarks(month); }, [month, loadRemarks]);

  const setRemark = (item, plant, text) => {
    setRemarks((prev) => ({ ...prev, [item]: { ...prev[item], [plant]: text } }));
  };

  const handleSave = async () => {
    setSaving(true);
    setError(null);
    setSaveMsg(null);
    try {
      const entries = [];
      for (const item of Object.keys(REMARK_PLANTS)) {
        for (const plant of REMARK_PLANTS[item]) {
          entries.push({ item_name: item, plant_name: plant, remark: (remarks[item]?.[plant] || '').trim() });
        }
      }
      const res = await fetch(`${API}/api/do-letter/remarks`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ report_month: month, remarks: entries }),
      });
      const body = await res.json();
      if (!res.ok) throw new Error(body.detail || `HTTP ${res.status}`);
      setSaveMsg(`Saved. These remarks will be used when the letter is generated for ${monthLabel(month)}.`);
    } catch (e) {
      setError(`Save failed: ${e.message}`);
    } finally {
      setSaving(false);
    }
  };

  const handleDownload = async (kind) => {
    setDownloading(kind);
    setError(null);
    try {
      const url = kind === 'docx'
        ? `${API}/api/do-letter/docx?month=${encodeURIComponent(month)}`
        : `${API}/api/do-letter/annexure-xlsx?month=${encodeURIComponent(month)}`;
      const res = await fetch(url);
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        throw new Error(body.detail || `HTTP ${res.status}`);
      }
      const blob = await res.blob();
      const blobUrl = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = blobUrl;
      a.download = kind === 'docx'
        ? `DO_${month}_Monthly_Performance.docx`
        : `Monthly_DO_Annexure_${month}.xlsx`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      window.URL.revokeObjectURL(blobUrl);
    } catch (e) {
      setError(`Download failed: ${e.message}`);
    } finally {
      setDownloading(null);
    }
  };

  const selectStyle = {
    padding: '9px 14px', fontSize: '11pt', border: '1px solid #dadce0',
    borderRadius: '6px', backgroundColor: '#ffffff', color: '#202124',
    cursor: 'pointer', minWidth: '140px',
  };

  const btnStyle = (disabled, color = '#1a73e8') => ({
    padding: '10px 24px', fontSize: '11pt', fontWeight: 700, border: 'none',
    borderRadius: '6px', cursor: disabled ? 'not-allowed' : 'pointer',
    backgroundColor: disabled ? '#dadce0' : color, color: '#ffffff',
  });

  return (
    <div style={{ minHeight: '100vh', backgroundColor: '#ffffff' }}>
      <GlobalNavbar />
      <main style={{ maxWidth: '900px', margin: '0 auto', padding: '32px' }}>
        <div style={{ marginBottom: '24px' }}>
          <h1 style={{ fontSize: '20pt', fontWeight: 900, color: '#202124', margin: 0 }}>
            Monthly D.O. Letter
          </h1>
          <p style={{ fontSize: '11pt', color: '#5f6368', marginTop: '6px' }}>
            &quot;Monthly performance of SAIL&quot; letter + Annexure A/B (Crude Steel &amp; Finished
            Steel, plant-wise) and the companion Ministry &quot;Monthly DO Annexure&quot; workbook —
            generated from data already in this app, in the exact format of the reference letter.
            Pick the month being <strong>reported on</strong> (the letter itself goes out on the
            1st of the following month).
          </p>
        </div>

        <div style={{
          padding: '20px 24px', border: '1px solid #dadce0', borderRadius: '8px',
          backgroundColor: '#f8f9fa', marginBottom: '24px',
          display: 'flex', alignItems: 'center', gap: '16px', flexWrap: 'wrap',
        }}>
          <label style={{ fontSize: '11pt', fontWeight: 600 }}>Report month</label>
          <input type="month" value={month} onChange={(e) => setMonth(e.target.value)} style={selectStyle} />
          <button onClick={() => handleDownload('docx')} disabled={downloading !== null} style={btnStyle(downloading !== null)}>
            {downloading === 'docx' ? 'Generating…' : '⬇ Download Letter (.docx)'}
          </button>
          <button onClick={() => handleDownload('xlsx')} disabled={downloading !== null} style={btnStyle(downloading !== null, '#0f9d58')}>
            {downloading === 'xlsx' ? 'Generating…' : '⬇ Download Annexure (.xlsx)'}
          </button>
        </div>

        {error && (
          <div style={{ padding: '14px 18px', border: '1px solid #f28b82', borderRadius: '8px', backgroundColor: '#fce8e6', color: '#c5221f', fontSize: '11pt', marginBottom: '24px' }}>
            {error}
          </div>
        )}

        <div style={{ padding: '20px 24px', border: '1px solid #dadce0', borderRadius: '8px', marginBottom: '24px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '14px' }}>
            <div style={{ fontSize: '12pt', fontWeight: 700, color: '#202124' }}>
              Annexure remarks — {monthLabel(month)}
            </div>
            <button onClick={handleSave} disabled={saving || loading} style={btnStyle(saving || loading, '#0f9d58')}>
              {saving ? 'Saving…' : 'Save remarks'}
            </button>
          </div>
          <p style={{ fontSize: '9.5pt', color: '#9aa0a6', marginTop: 0, marginBottom: '16px' }}>
            Enter these any time during (or after) the month — they&#39;ll already be in place when
            the letter is generated on the 1st. A blank box means no remark for that plant.
          </p>

          {loading ? (
            <div style={{ fontSize: '10.5pt', color: '#5f6368' }}>Loading…</div>
          ) : (
            Object.entries(REMARK_PLANTS).map(([item, plants]) => (
              <div key={item} style={{ marginBottom: '20px' }}>
                <div style={{ fontSize: '10.5pt', fontWeight: 700, color: '#1a73e8', marginBottom: '8px' }}>
                  {item}
                </div>
                <div style={{ display: 'grid', gridTemplateColumns: '90px 1fr', gap: '8px 12px' }}>
                  {plants.map((plant) => (
                    <React.Fragment key={plant}>
                      <div style={{ fontSize: '10.5pt', fontWeight: 600, color: '#202124', paddingTop: '8px' }}>
                        {plant}
                      </div>
                      <textarea
                        value={remarks[item]?.[plant] || ''}
                        onChange={(e) => setRemark(item, plant, e.target.value)}
                        rows={2}
                        placeholder="No remark"
                        style={{
                          width: '100%', padding: '8px 10px', fontSize: '10pt',
                          border: '1px solid #dadce0', borderRadius: '6px',
                          fontFamily: 'inherit', resize: 'vertical',
                        }}
                      />
                    </React.Fragment>
                  ))}
                </div>
              </div>
            ))
          )}

          {saveMsg && (
            <div style={{ padding: '10px 14px', backgroundColor: '#e6f4ea', color: '#137333', borderRadius: '6px', fontSize: '10.5pt' }}>
              {saveMsg}
            </div>
          )}
        </div>
      </main>
    </div>
  );
}
