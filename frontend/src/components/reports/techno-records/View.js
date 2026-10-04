'use client';

import React, { useState, useEffect } from 'react';
import { ReportPage } from '../ReportUI';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || '';

// The 5 integrated plants + SAIL (page 27's plant set); BF-wise rows exist
// for plants only.
const TABS = ['BSP', 'DSP', 'RSP', 'BSL', 'ISP', 'SAIL'];

const CAL_MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
  .map((name, i) => ({ num: i + 1, name }));

// Ratios/productivities need their decimals; kg/thm, °C, kg/tcs don't.
function fmt(v, unit) {
  if (v == null) return '—';
  const digits = unit === 't/thm' ? 3 : (unit === 't/m³/day' || unit === 'Gcal/tcs') ? 2 : 1;
  return Number(v).toLocaleString('en-IN', { minimumFractionDigits: 0, maximumFractionDigits: digits });
}

function yearOf(month) {
  return month ? `[${month.slice(0, 4)}]` : '';
}

const C = {
  headerBg: '#1a73e8',
  bestBg: '#fffbeb', bestBorder: '#fde68a', bestText: '#92400e',
  topBg: '#d1fae5', topBorder: '#6ee7b7', topText: '#065f46',
  secondText: '#9aa0a6',
  border: '#e8eaed',
  stickyColBg: '#f8f9fa',
  sectionBg: '#e8f0fe', sectionText: '#174ea6',
};

function Direction({ better }) {
  const low = better === 'low';
  return (
    <span title={low ? 'Lower is better' : 'Higher is better'} style={{
      marginLeft: 6, fontSize: '7.5pt', fontWeight: 700, padding: '0 5px', borderRadius: 8,
      background: low ? '#e6f4ea' : '#e8f0fe', color: low ? '#188038' : '#1967d2',
    }}>
      {low ? '↓ low' : '↑ high'}
    </span>
  );
}

export default function TechnoRecordsPage() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [plant, setPlant] = useState('BSP');

  useEffect(() => {
    fetch(`${API_BASE}/api/techno-records`)
      .then((r) => { if (!r.ok) throw new Error(r.statusText); return r.json(); })
      .then((d) => { setData(d); setLoading(false); })
      .catch((e) => { setError(e.message); setLoading(false); });
  }, []);

  const sections = data?.[plant]?.sections || [];

  const tabBtn = (active) => ({
    padding: '7px 16px', borderRadius: 6,
    border: `1.5px solid ${active ? C.headerBg : '#dadce0'}`,
    background: active ? C.headerBg : '#fff', color: active ? '#fff' : '#5f6368',
    fontSize: '10.5pt', fontWeight: active ? 700 : 600, cursor: 'pointer',
  });

  const stickyHeaderCell = {
    position: 'sticky', top: 0, zIndex: 2, background: C.headerBg, color: '#fff',
    padding: '9px 8px', fontSize: '9.5pt', fontWeight: 700, textAlign: 'center', minWidth: 86,
    borderLeft: '1px solid rgba(255,255,255,0.25)',
  };
  const stickyItemHeaderCell = {
    position: 'sticky', top: 0, left: 0, zIndex: 3, background: C.headerBg, color: '#fff',
    padding: '9px 14px', fontSize: '9.5pt', fontWeight: 700, textAlign: 'left', minWidth: 270,
    borderRight: '2px solid rgba(255,255,255,0.4)',
  };
  const stickyItemCell = {
    position: 'sticky', left: 0, zIndex: 1, background: C.stickyColBg,
    padding: '7px 14px', fontSize: '9.5pt', fontWeight: 600, color: '#202124',
    borderRight: '2px solid #dadce0', borderBottom: `1px solid ${C.border}`, whiteSpace: 'nowrap',
  };

  return (
    <ReportPage
      maxWidth={1600}
      title={<>Best Techno Matrix</>}
      description={<>Best and 2nd-best ever figure for every calendar month — the Major 12 techno-economic parameters (as on the Major TEPs page) and the BF-wise Iron Making parameters. “Best” is the <strong>lowest</strong> figure for consumption rates (coke, fuel, coal to HM, hot metal, TMI, slag, energy) and the <strong>highest</strong> for CDI, nut coke, burden sinter / pellet, productivity, scrap, hot blast temperature and O₂ enrichment. The single all-time best month of a row is marked <strong>★</strong>. SAIL figures count from Apr&apos;21, when all five plants&apos; techno data begins.</>}
    >

<div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginBottom: 20 }}>
            {TABS.map((p) => (
              <button key={p} onClick={() => setPlant(p)} style={tabBtn(plant === p)}>{p}</button>
            ))}
          </div>

          {loading && (
            <div style={{ padding: '60px 0', textAlign: 'center', color: '#5f6368', fontSize: 14 }}>
              Loading records… (the first load after new data can take a few seconds)
            </div>
          )}
          {error && (
            <div style={{ padding: '16px 20px', background: '#fef2f2', border: '1px solid #fca5a5', borderRadius: 8, color: '#991b1b', fontSize: 13 }}>
              Error loading data: {error}
            </div>
          )}

          {!loading && !error && data && (
            <>
              <div style={{ display: 'flex', gap: 18, flexWrap: 'wrap', alignItems: 'center', marginBottom: 14, fontSize: '10.5px', color: '#5f6368' }}>
                <span><span style={{ display: 'inline-block', width: 13, height: 13, borderRadius: 3, background: C.bestBg, border: `1.5px solid ${C.bestBorder}`, marginRight: 5, verticalAlign: 'middle' }} />Best of that calendar month</span>
                <span><span style={{ display: 'inline-block', width: 13, height: 13, borderRadius: 3, background: C.topBg, border: `1.5px solid ${C.topBorder}`, marginRight: 5, verticalAlign: 'middle' }} />★ All-time best month of the row</span>
                <span style={{ color: C.secondText }}>Small figure below = 2nd-best of that month</span>
              </div>

              <div style={{ overflow: 'auto', maxHeight: '72vh', border: '1px solid #dadce0', borderRadius: 8 }}>
                <table style={{ borderCollapse: 'collapse', minWidth: 1350, width: '100%' }}>
                  <thead>
                    <tr>
                      <th style={stickyItemHeaderCell}>Parameter</th>
                      {CAL_MONTHS.map((m) => <th key={m.num} style={stickyHeaderCell}>{m.name}</th>)}
                    </tr>
                  </thead>
                  <tbody>
                    {sections.map((sec) => (
                      <React.Fragment key={sec.title}>
                        <tr>
                          <td colSpan={13} style={{
                            position: 'sticky', left: 0, padding: '7px 14px', background: C.sectionBg,
                            color: C.sectionText, fontWeight: 800, fontSize: '9.5pt', letterSpacing: '.03em',
                            borderBottom: `1px solid ${C.border}`,
                          }}>
                            {sec.title}
                          </td>
                        </tr>
                        {sec.rows.length === 0 && (
                          <tr><td colSpan={13} style={{ padding: '18px', textAlign: 'center', color: '#9aa0a6' }}>No data for {plant}.</td></tr>
                        )}
                        {sec.rows.map((row, ri) => {
                          const rowBg = ri % 2 === 0 ? '#ffffff' : '#fbfbfa';
                          return (
                            <tr key={row.label}>
                              <td style={{ ...stickyItemCell, background: ri % 2 === 0 ? C.stickyColBg : '#f1f2f3' }}>
                                {row.label}
                                <span style={{ marginLeft: 6, fontSize: '8pt', fontWeight: 500, color: '#80868b' }}>{row.unit}</span>
                                <Direction better={row.better} />
                              </td>
                              {CAL_MONTHS.map((m) => {
                                const rows = row.cal_months?.[m.num] || [];
                                const best = rows[0];
                                const second = rows[1];
                                const isAllTimeBest = best && row.best && best.month === row.best.month;
                                return (
                                  <td key={m.num} style={{
                                    padding: '6px 6px', textAlign: 'center', verticalAlign: 'top',
                                    borderBottom: `1px solid ${C.border}`, borderLeft: `1px solid ${C.border}`,
                                    background: !best ? rowBg : isAllTimeBest ? C.topBg : C.bestBg,
                                  }}>
                                    {best ? (
                                      <>
                                        <div style={{ fontSize: '9.5pt', fontWeight: 800, color: isAllTimeBest ? C.topText : C.bestText }}>
                                          {fmt(best.value, row.unit)}{isAllTimeBest ? ' ★' : ''}
                                        </div>
                                        <div style={{ fontSize: '7.5pt', fontStyle: 'italic', color: isAllTimeBest ? C.topText : C.bestText, opacity: 0.75 }}>
                                          {yearOf(best.month)}
                                        </div>
                                        {second && (
                                          <div style={{ marginTop: 3, fontSize: '8pt', color: C.secondText }}>
                                            {fmt(second.value, row.unit)} <span style={{ fontSize: '7pt', fontStyle: 'italic' }}>{yearOf(second.month)}</span>
                                          </div>
                                        )}
                                      </>
                                    ) : (
                                      <span style={{ color: '#c3c2b7', fontSize: '9pt' }}>—</span>
                                    )}
                                  </td>
                                );
                              })}
                            </tr>
                          );
                        })}
                      </React.Fragment>
                    ))}
                  </tbody>
                </table>
              </div>
            </>
          )}
    </ReportPage>
  );
}
