'use client';

import React, { useState, useCallback, useEffect, useMemo } from 'react';
import GlobalNavbar from '@/components/GlobalNavbar';

const MONTH_SHORT = { '01':'Jan','02':'Feb','03':'Mar','04':'Apr','05':'May','06':'Jun','07':'Jul','08':'Aug','09':'Sep','10':'Oct','11':'Nov','12':'Dec' };
const FY_YEARS = Array.from({ length: 6 }, (_, i) => (2022 + i).toString());

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://127.0.0.1:8082';

function ConversionCard({ apiBase }) {
  const getDefaultFy = () => {
    const d = new Date();
    return (d.getMonth() + 1 >= 4 ? d.getFullYear() : d.getFullYear() - 1).toString();
  };
  const [fyStart, setFyStart] = useState(getDefaultFy);
  const [convData, setConvData] = useState({});
  const [edits, setEdits] = useState({});
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [status, setStatus] = useState(null);

  const fyMonths = useMemo(() => {
    const y = parseInt(fyStart);
    return [`${y}-04`,`${y}-05`,`${y}-06`,`${y}-07`,`${y}-08`,`${y}-09`,`${y}-10`,`${y}-11`,`${y}-12`,`${y+1}-01`,`${y+1}-02`,`${y+1}-03`];
  }, [fyStart]);

  const loadData = useCallback(async () => {
    setLoading(true);
    setEdits({});
    try {
      const res = await fetch(`${apiBase}/api/conversion-data?fy_start=${fyStart}`);
      if (!res.ok) throw new Error(await res.text());
      const json = await res.json();
      setConvData(json.data);
    } catch (err) {
      setStatus({ type: 'error', text: `Load failed: ${err.message}` });
    } finally {
      setLoading(false);
    }
  }, [fyStart, apiBase]);

  useEffect(() => { loadData(); }, [loadData]);

  const currentVal = m => edits[m] !== undefined ? edits[m] : String(convData[m] ?? '');
  const hasEdits = fyMonths.some(m => edits[m] !== undefined && edits[m] !== String(convData[m] ?? ''));

  const handleSave = async () => {
    setSaving(true);
    setStatus(null);
    const entries = fyMonths
      .filter(m => edits[m] !== undefined && edits[m] !== '')
      .map(m => ({ month: m, value: parseFloat(edits[m]) }))
      .filter(e => !isNaN(e.value));
    try {
      const res = await fetch(`${apiBase}/api/conversion-entry`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ entries }),
      });
      if (!res.ok) throw new Error(await res.text());
      setStatus({ type: 'success', text: `Saved ${entries.length} conversion value(s).` });
      await loadData();
    } catch (err) {
      setStatus({ type: 'error', text: `Save failed: ${err.message}` });
    } finally {
      setSaving(false);
    }
  };

  return (
    <>
      <GlobalNavbar />
      <main style={{ padding: '40px 32px', maxWidth: '1200px', margin: '0 auto' }}>
        <h1 style={{ fontSize: '24px', fontWeight: '900', color: '#0f172a', marginBottom: '24px' }}>⚡ Conversion Data</h1>

        <div style={{ backgroundColor: '#fff', border: '1px solid #e2e8f0', borderRadius: '8px', overflow: 'hidden' }}>
          <div style={{ padding: '14px 20px', backgroundColor: '#1e3a5f', color: '#f1f5f9', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <span style={{ fontWeight: '700', fontSize: '10pt' }}>Conversion (SAIL) — Monthly Actuals</span>
            <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
              <span style={{ fontSize: '9pt', color: '#94a3b8' }}>FY:</span>
              <select value={fyStart} onChange={e => setFyStart(e.target.value)}
                style={{ fontSize: '9pt', padding: '2px 6px', borderRadius: '4px', border: '1px solid #475569', backgroundColor: '#334155', color: '#f1f5f9' }}>
                {FY_YEARS.map(y => <option key={y} value={y}>{y}-{String(parseInt(y)+1).slice(2)}</option>)}
              </select>
            </div>
          </div>

          {loading ? (
            <div style={{ padding: '24px', textAlign: 'center', color: '#64748b', fontSize: '10pt' }}>Loading...</div>
          ) : (
            <div style={{ overflowX: 'auto' }}>
              <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '9.5pt' }}>
                <thead>
                  <tr style={{ backgroundColor: '#f1f5f9' }}>
                    <th style={{ padding: '8px 16px', textAlign: 'left', fontWeight: '700', color: '#475569', borderBottom: '1px solid #e2e8f0', width: '50%' }}>Month</th>
                    <th style={{ padding: '8px 12px', textAlign: 'center', fontWeight: '700', color: '#10b981', borderBottom: '1px solid #e2e8f0' }}>Actual ('000 T)</th>
                  </tr>
                </thead>
                <tbody>
                  {fyMonths.map((m, idx) => {
                    const [y, mo] = m.split('-');
                    const label = `${MONTH_SHORT[mo]}'${y.slice(2)}`;
                    const val = currentVal(m);
                    const isEdited = edits[m] !== undefined && edits[m] !== String(convData[m] ?? '');
                    return (
                      <tr key={m} style={{ backgroundColor: isEdited ? '#fffbeb' : idx % 2 === 0 ? '#fff' : '#f8fafc', borderBottom: '1px solid #f1f5f9' }}>
                        <td style={{ padding: '6px 16px', color: '#1e293b', fontWeight: '500' }}>
                          {label}
                          {isEdited && <span style={{ marginLeft: '6px', fontSize: '8pt', color: '#d97706', fontWeight: '600' }}>edited</span>}
                        </td>
                        <td style={{ padding: '6px 12px', textAlign: 'center' }}>
                          <input type="number" step="0.001" value={val}
                            onChange={e => setEdits(prev => ({ ...prev, [m]: e.target.value }))}
                            placeholder="Enter actual"
                            style={{ width: '120px', padding: '4px 6px', border: `1px solid ${val ? '#6ee7b7' : '#cbd5e1'}`, borderRadius: '4px', textAlign: 'right', fontSize: '9pt', color: '#065f46', backgroundColor: val ? '#f0fdf4' : '#fff' }} />
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}

          {status && (
            <div style={{ margin: '0 16px 12px', padding: '8px 12px', borderRadius: '6px', fontSize: '0.8rem', backgroundColor: status.type === 'success' ? '#064e3b' : '#7f1d1d', color: status.type === 'success' ? '#6ee7b7' : '#fca5a5' }}>
              {status.text}
            </div>
          )}

          <div style={{ padding: '12px 20px', backgroundColor: '#f8fafc', borderTop: '1px solid #e2e8f0', display: 'flex', justifyContent: 'flex-end' }}>
            <button onClick={handleSave} disabled={saving || !hasEdits}
              style={{ padding: '6px 16px', fontSize: '9pt', backgroundColor: hasEdits ? '#10b981' : '#94a3b8', color: '#fff', border: 'none', borderRadius: '4px', cursor: hasEdits ? 'pointer' : 'default', fontWeight: '600' }}>
              {saving ? 'Saving...' : 'Save Conversion Data'}
            </button>
          </div>
        </div>
      </main>
    </>
  );
}

export default function ConversionPage() {
  return <ConversionCard apiBase={API_BASE_URL} />;
}
