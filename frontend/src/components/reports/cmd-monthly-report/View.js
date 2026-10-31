'use client';

import React, { useState, useEffect } from 'react';
import { ReportPage } from '../ReportUI';

const API = process.env.NEXT_PUBLIC_API_URL || '';

// CMD Office "SAIL: Monthly Activity Report" — production paragraphs come
// from the DB (page_cmd_monthly_report.py); the best-ever list is pre-filled
// with what the DB can prove and is editable, as are the other events and
// areas of concern. Nothing here is saved — it goes straight into the .docx.

// The report goes out early in the month AFTER the one it covers, so
// default to last month.
function previousMonth() {
  const now = new Date();
  const m = now.getMonth();
  const y = m === 0 ? now.getFullYear() - 1 : now.getFullYear();
  return `${y}-${String(m === 0 ? 12 : m).padStart(2, '0')}`;
}

const lines = (s) => s.split('\n').map(x => x.trim()).filter(Boolean);

const TA = {
  width: '100%', padding: '8px 10px', fontSize: 14, border: '1px solid #d1d5db',
  borderRadius: 6, fontFamily: 'inherit', resize: 'vertical', boxSizing: 'border-box',
};
const LBL = { display: 'block', fontSize: 13, fontWeight: 600, color: '#374151', margin: '14px 0 6px' };

export default function CmdMonthlyReportPage() {
  const [month, setMonth] = useState(previousMonth());
  const [data, setData] = useState(null);
  const [bestEver, setBestEver] = useState('');
  const [events, setEvents] = useState('');
  const [concerns, setConcerns] = useState('None');
  const [loading, setLoading] = useState(false);
  const [downloading, setDownloading] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      setLoading(true);
      setError(null);
      try {
        const res = await fetch(`${API}/api/cmd-monthly-report/data?month=${encodeURIComponent(month)}`);
        if (!res.ok) throw new Error(await res.text());
        const d = await res.json();
        if (cancelled) return;
        setData(d);
        setBestEver((d.best_ever || []).join('\n'));
      } catch (e) {
        if (!cancelled) setError(`Failed to load: ${e.message}`);
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, [month]);

  const handleDownload = async () => {
    setDownloading(true);
    setError(null);
    try {
      const res = await fetch(`${API}/api/cmd-monthly-report/docx`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ month, best_ever: lines(bestEver), events: lines(events), concerns }),
      });
      if (!res.ok) throw new Error(await res.text());
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `SAIL_Monthly_Activity_Report_${month}.docx`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    } catch (e) {
      setError(`Download failed: ${e.message}`);
    } finally {
      setDownloading(false);
    }
  };

  const monthName = data?.month_label?.split(' ')[0] || '';
  const busy = loading || downloading;

  return (
    <ReportPage
      maxWidth={980}
      title={<>CMD Monthly Activity Report</>}
      description={<>SAIL: Monthly Activity Report{data ? ` for ${data.month_label}` : ''} · Word (.docx)</>}
    >
      <div style={{
        display: 'flex', gap: 10, alignItems: 'center', flexWrap: 'wrap',
        marginBottom: 18, border: '1px solid #dadce0', borderRadius: 8, padding: '14px 18px',
      }}>
        <label style={{ fontSize: 13, fontWeight: 600, color: '#374151' }}>Report month</label>
        <input type="month" value={month} onChange={e => e.target.value && setMonth(e.target.value)}
          style={{ padding: '6px 10px', fontSize: 14, border: '1px solid #d1d5db', borderRadius: 4 }} />
        <button onClick={handleDownload} disabled={busy || !data} style={{
          marginLeft: 12, padding: '7px 16px', fontSize: 13, fontWeight: 600, borderRadius: 6,
          border: '1px solid #1a56db', cursor: busy || !data ? 'not-allowed' : 'pointer',
          background: '#e8f0fe', color: '#1a56db', opacity: busy || !data ? 0.5 : 1,
        }}>{downloading ? 'Generating…' : '⬇ Download Report (.docx)'}</button>
        <span style={{ marginLeft: 'auto', fontSize: 13, color: '#5f6368' }}>{loading && '⟳ loading…'}</span>
      </div>

      {error && (
        <div style={{ padding: '10px 16px', borderRadius: 6, marginBottom: 14, fontSize: 14, background: '#fef2f2', color: '#991b1b', border: '1px solid #fca5a5' }}>
          {error}
        </div>
      )}

      {data && (
        <div style={{ border: '1px solid #dadce0', borderRadius: 8, padding: '18px 22px', fontSize: 14, color: '#202124', lineHeight: 1.55 }}>
          <div style={{ textAlign: 'center', fontWeight: 700, textDecoration: 'underline', marginBottom: 14 }}>
            SAIL: Monthly Activity Report for {data.month_label.replace(' ', '’')}
          </div>
          <div style={{ fontWeight: 700, marginBottom: 8 }}>
            1. Performance of SAIL – {monthName.slice(0, 3)} {month.slice(0, 4)} (Provisional):
          </div>
          {data.items.map((it, i) => (
            <div key={it.label} style={{ marginBottom: 10 }}>
              <div>({['i', 'ii', 'iii', 'iv'][i]}) <b>{it.label}:</b></div>
              <div style={{ textAlign: 'justify' }}>{it.sentence}</div>
            </div>
          ))}

          <div style={{ fontWeight: 700, marginTop: 16 }}>
            3. Significant Events / Achievements during {monthName}’{month.slice(2, 4)}:
          </div>

          <label style={LBL}>
            SAIL recorded its best-ever {monthName} performance for following — one per line
            <span style={{ fontWeight: 400, color: '#6b7280' }}> (pre-filled from DB records; add sales, fuel rate etc. by hand)</span>
          </label>
          <textarea rows={5} value={bestEver} onChange={e => setBestEver(e.target.value)} style={TA}
            placeholder="e.g. Saleable Steel Sales" />

          <label style={LBL}>
            Other significant events — one per line <span style={{ fontWeight: 400, color: '#6b7280' }}>(optional)</span>
          </label>
          <textarea rows={3} value={events} onChange={e => setEvents(e.target.value)} style={TA} />

          <label style={LBL}>Areas of Concern</label>
          <input value={concerns} onChange={e => setConcerns(e.target.value)} style={TA} />
        </div>
      )}

      <div style={{ marginTop: 14, fontSize: 12, color: '#9ca3af' }}>
        SAIL = sum of the eight producing units (BSP, DSP, RSP, BSL, ISP, ASP, SSP, VISL); Finished Steel includes
        the SAIL-level Conversion figure. Best-ever suggestions: the production lines exactly as the PDF report&apos;s
        Page 3 highlights, plus Iron Ore Production when it beats every earlier year&apos;s same month (at least 5
        years of history). Edits on this page are not saved — they go only into the downloaded file.
      </div>
    </ReportPage>
  );
}
