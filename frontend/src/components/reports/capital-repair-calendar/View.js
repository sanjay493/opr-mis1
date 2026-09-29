'use client';

import React, { useEffect, useState } from 'react';
import GlobalNavbar from '@/components/GlobalNavbar';
import {
  API_BASE, CURRENT_FY_END_YEAR, selStyle, ErrorBox, TabIntro, ExportButtons, downloadFile,
} from '@/components/techno/shared';

const PLANTS = [
  { code: 'BSP', label: 'Bhilai Steel Plant' },
  { code: 'DSP', label: 'Durgapur Steel Plant' },
  { code: 'RSP', label: 'Rourkela Steel Plant' },
  { code: 'BSL', label: 'Bokaro Steel Plant' },
  { code: 'ISP', label: 'IISCO Steel Plant' },
];

function defaultFy() {
  const endYear = CURRENT_FY_END_YEAR;
  return `${endYear - 1}-${String(endYear % 100).padStart(2, '0')}`;
}

// Recent FYs, current first.
function fyOptions() {
  const endYear = CURRENT_FY_END_YEAR;
  return Array.from({ length: 6 }, (_, i) => {
    const start = endYear - 1 - i;
    return `${start}-${String((start + 1) % 100).padStart(2, '0')}`;
  });
}

export default function CapitalRepairCalendarView() {
  const [plant, setPlant] = useState('BSP');
  const [fy, setFy] = useState(defaultFy());
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [downloading, setDownloading] = useState(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    fetch(`${API_BASE}/api/capital-repair-calendar?plant=${plant}&fy=${fy}`)
      .then((r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        return r.json();
      })
      .then((d) => { if (!cancelled) setData(d); })
      .catch((e) => { if (!cancelled) setError(`Failed to load: ${e.message}`); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [plant, fy]);

  const handleDownload = async (kind) => {
    setDownloading(kind);
    try {
      await downloadFile(
        `${API_BASE}/api/capital-repair-calendar/${kind}?plant=${plant}&fy=${fy}`,
        undefined,
        `Capital_Repair_Calendar_${plant}_${fy}.${kind === 'excel' ? 'xlsx' : 'pdf'}`,
      );
    } catch (e) {
      setError(`Download failed: ${e.message}`);
    } finally {
      setDownloading(null);
    }
  };

  const months = data?.month_labels || [];

  return (
    <div style={{ minHeight: '100vh', backgroundColor: '#ffffff' }}>
      <GlobalNavbar />

      <div style={{ maxWidth: '1600px', margin: '0 auto', padding: '24px 32px 40px' }}>
        <h1 style={{ fontSize: '20pt', fontWeight: 900, color: '#202124', margin: '0 0 8px' }}>
          Capital Repair — Plan vs Actual
        </h1>
        <TabIntro>
          One row per unit — which months it was scheduled (Plan) vs actually under repair (Actual),
          Apr–Mar for the selected plant and financial year.
        </TabIntro>

        <div style={{ display: 'flex', gap: '14px', alignItems: 'center', flexWrap: 'wrap', marginBottom: '18px' }}>
          <select value={plant} onChange={(e) => setPlant(e.target.value)} style={selStyle}>
            {PLANTS.map((p) => <option key={p.code} value={p.code}>{p.label}</option>)}
          </select>
          <select value={fy} onChange={(e) => setFy(e.target.value)} style={selStyle}>
            {fyOptions().map((f) => <option key={f} value={f}>FY {f}</option>)}
          </select>

          <div style={{ display: 'flex', alignItems: 'center', gap: '16px', marginLeft: '4px', fontSize: '10.5pt', color: '#5f6368' }}>
            <span style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
              <span style={{ width: 14, height: 14, background: '#fce8b2', border: '1px solid #dadce0', display: 'inline-block' }} />
              Plan
            </span>
            <span style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
              <span style={{ width: 14, height: 14, background: '#cfe2ff', border: '1px solid #dadce0', display: 'inline-block' }} />
              Actual
            </span>
          </div>

          <div style={{ marginLeft: 'auto' }}>
            <ExportButtons onDownload={handleDownload} downloading={downloading} disabled={!data || loading} />
          </div>
        </div>

        <ErrorBox>{error}</ErrorBox>

        {loading && <p style={{ color: '#5f6368', fontSize: '11pt' }}>Loading…</p>}

        {!loading && data && (
          <div style={{ overflowX: 'auto', border: '1px solid #dadce0', borderRadius: '8px' }}>
            <table style={{ borderCollapse: 'collapse', width: '100%', minWidth: '900px' }}>
              <thead>
                <tr>
                  <th style={thStyle('left', 160)}>Unit</th>
                  <th style={thStyle('left', 200)}>Activity</th>
                  {months.map((m) => <th key={m} style={thStyle('center', 64)}>{m}</th>)}
                </tr>
              </thead>
              <tbody>
                {data.sections.map((sec) => (
                  <React.Fragment key={sec.shop}>
                    <tr>
                      <td colSpan={2 + months.length} style={{
                        padding: '6px 12px', background: '#1a73e8', color: '#ffffff',
                        fontWeight: 700, fontSize: '10.5pt',
                      }}>
                        {sec.shop}
                      </td>
                    </tr>
                    {sec.rows.map((r, idx) => (
                      <tr key={`${sec.shop}-${r.unit}-${idx}`} style={{ backgroundColor: idx % 2 === 1 ? '#f8f9fa' : '#ffffff' }}>
                        <td style={tdStyle('left')}>{r.unit}</td>
                        <td style={{ ...tdStyle('left'), color: '#5f6368' }}>{r.activity}</td>
                        {r.months.map((m, mi) => (
                          <td key={mi} style={{ padding: 0, border: '1px solid #e8eaed' }}>
                            <div style={{ height: 10, background: m.plan ? '#fce8b2' : 'transparent' }} />
                            <div style={{ height: 10, background: m.actual ? '#cfe2ff' : 'transparent' }} />
                          </td>
                        ))}
                      </tr>
                    ))}
                  </React.Fragment>
                ))}
                {data.sections.length === 0 && (
                  <tr>
                    <td colSpan={2 + months.length} style={{ padding: '40px', textAlign: 'center', color: '#5f6368' }}>
                      No Capital Repair rows for {data.plant_title}, FY {fy}.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}

function thStyle(align, minWidth) {
  return {
    padding: '8px 12px', fontSize: '10pt', fontWeight: 700, color: '#174ea6',
    backgroundColor: '#e8f0fe', textAlign: align, borderBottom: '1px solid #dadce0',
    minWidth, whiteSpace: 'nowrap',
  };
}

function tdStyle(align) {
  return {
    padding: '6px 12px', fontSize: '10.5pt', textAlign: align,
    borderBottom: '1px solid #e8eaed', whiteSpace: 'nowrap',
  };
}
