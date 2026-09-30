'use client';

import React, { useState, useEffect } from 'react';
import GlobalNavbar from '@/components/GlobalNavbar';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || '';

// Real plants in process/production order (matches ALL8 in page_records.py);
// sail5/all8 are the two group roll-ups the same endpoint also returns.
const PLANTS = ['BSP', 'DSP', 'RSP', 'BSL', 'ISP', 'ASP', 'SSP', 'VISL'];
const TABS = [...PLANTS, 'sail5', 'all8'];
const TAB_LABEL = { sail5: 'SAIL (5 Plants)', all8: 'All 8 Plants' };

const CAL_MONTHS = [
  { num: 1, name: 'Jan' }, { num: 2, name: 'Feb' }, { num: 3, name: 'Mar' },
  { num: 4, name: 'Apr' }, { num: 5, name: 'May' }, { num: 6, name: 'Jun' },
  { num: 7, name: 'Jul' }, { num: 8, name: 'Aug' }, { num: 9, name: 'Sep' },
  { num: 10, name: 'Oct' }, { num: 11, name: 'Nov' }, { num: 12, name: 'Dec' },
];

function fmt(v) {
  if (v == null) return '—';
  return Number(v).toLocaleString('en-IN', { maximumFractionDigits: 3 });
}

const MON_ABBR = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];

// 'YYYY-MM' of calendar month `num` inside the FY containing `reportMonth`,
// or null when that month is still after the report month.
function fyMonthOf(num, reportMonth) {
  if (!reportMonth) return null;
  const ry = Number(reportMonth.slice(0, 4));
  const rm = Number(reportMonth.slice(5, 7));
  const fyStart = rm >= 4 ? ry : ry - 1;
  const ym = `${num >= 4 ? fyStart : fyStart + 1}-${String(num).padStart(2, '0')}`;
  return ym <= reportMonth ? ym : null;
}

function yearOf(month) {
  return month ? `[${month.slice(0, 4)}]` : '';
}

const C = {
  headerBg: '#1a73e8',
  bestBg: '#fffbeb', bestBorder: '#fde68a', bestText: '#92400e',
  topBg: '#d1fae5', topBorder: '#6ee7b7', topText: '#065f46',
  secondText: '#9aa0a6',
  fyHeaderBg: '#0b4fb3', fyRing: '#1a73e8', fyBadgeBg: '#1a73e8',
  border: '#e8eaed',
  stickyColBg: '#f8f9fa',
};

export default function RecordsMatrixPage() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [plant, setPlant] = useState('BSP');

  useEffect(() => {
    fetch(`${API_BASE}/api/production-records`)
      .then((r) => { if (!r.ok) throw new Error(r.statusText); return r.json(); })
      .then((d) => { setData(d); setLoading(false); })
      .catch((e) => { setError(e.message); setLoading(false); });
  }, []);

  const grp = data?.[plant];
  const items = grp?.items || [];
  const reportMonth = data?.latest_month || null;
  const reportFy = reportMonth
    ? (Number(reportMonth.slice(5, 7)) >= 4 ? Number(reportMonth.slice(0, 4)) : Number(reportMonth.slice(0, 4)) - 1)
    : null;
  const fyLabel = reportFy != null ? `${reportFy}-${String((reportFy + 1) % 100).padStart(2, '0')}` : '';
  const reportLabel = reportMonth ? `${MON_ABBR[Number(reportMonth.slice(5, 7)) - 1]}'${reportMonth.slice(2, 4)}` : '';

  const tabBtn = (active) => ({
    padding: '7px 16px',
    borderRadius: 6,
    border: `1.5px solid ${active ? C.headerBg : '#dadce0'}`,
    background: active ? C.headerBg : '#fff',
    color: active ? '#fff' : '#5f6368',
    fontSize: '10.5pt',
    fontWeight: active ? 700 : 600,
    cursor: 'pointer',
  });

  const stickyHeaderCell = {
    position: 'sticky', top: 0, zIndex: 2,
    background: C.headerBg, color: '#fff',
    padding: '9px 8px', fontSize: '9.5pt', fontWeight: 700,
    textAlign: 'center', minWidth: 96,
    borderLeft: '1px solid rgba(255,255,255,0.25)',
  };

  const stickyItemHeaderCell = {
    position: 'sticky', top: 0, left: 0, zIndex: 3,
    background: C.headerBg, color: '#fff',
    padding: '9px 14px', fontSize: '9.5pt', fontWeight: 700,
    textAlign: 'left', minWidth: 230,
    borderRight: '2px solid rgba(255,255,255,0.4)',
  };

  const stickyItemCell = {
    position: 'sticky', left: 0, zIndex: 1,
    background: C.stickyColBg,
    padding: '7px 14px', fontSize: '9.5pt', fontWeight: 600, color: '#202124',
    borderRight: `2px solid #dadce0`, borderBottom: `1px solid ${C.border}`,
    whiteSpace: 'nowrap',
  };

  return (
    <>
      <GlobalNavbar />
      <main style={{ backgroundColor: '#ffffff', padding: '36px 32px', minHeight: 'calc(100vh - 70px)' }}>
        <div style={{ maxWidth: 1600, margin: '0 auto' }}>
          <h1 style={{ fontSize: '26px', fontWeight: 900, color: '#202124', margin: '0 0 8px' }}>
            Monthly Records Matrix
          </h1>
          <p style={{ fontSize: '12.5px', color: '#5f6368', margin: '0 0 24px', lineHeight: 1.6, maxWidth: 780 }}>
            Best and 2nd-best ever figure for every calendar month, item-wise — grouped plant-wise,
            items listed in process order. The best-ever figure for each calendar month is
            highlighted; the single all-time-best month for an item (across all 12 months) is
            marked <strong>★</strong>. Months of the report FY{fyLabel ? ` ${fyLabel}` : ''} are shaded in the header, and
            records set during that FY are outlined in blue.
          </p>

          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginBottom: 20 }}>
            {TABS.map((p) => (
              <button key={p} onClick={() => setPlant(p)} style={tabBtn(plant === p)}>
                {TAB_LABEL[p] || p}
              </button>
            ))}
          </div>

          {loading && <div style={{ padding: '60px 0', textAlign: 'center', color: '#5f6368', fontSize: 14 }}>Loading records…</div>}
          {error && (
            <div style={{ padding: '16px 20px', background: '#fef2f2', border: '1px solid #fca5a5', borderRadius: 8, color: '#991b1b', fontSize: 13 }}>
              Error loading data: {error}
            </div>
          )}

          {!loading && !error && grp && (
            <>
              <div style={{
                display: 'flex', gap: 18, flexWrap: 'wrap', alignItems: 'center',
                marginBottom: 14, fontSize: '10.5px', color: '#5f6368',
              }}>
                <span><span style={{ display: 'inline-block', width: 13, height: 13, borderRadius: 3, background: C.bestBg, border: `1.5px solid ${C.bestBorder}`, marginRight: 5, verticalAlign: 'middle' }} />Best of that calendar month</span>
                <span><span style={{ display: 'inline-block', width: 13, height: 13, borderRadius: 3, background: C.topBg, border: `1.5px solid ${C.topBorder}`, marginRight: 5, verticalAlign: 'middle' }} />★ All-time best month for the item</span>
                {reportMonth && (
                  <span><span style={{ display: 'inline-block', width: 13, height: 13, borderRadius: 3, background: '#fff', boxShadow: `inset 0 0 0 2px ${C.fyRing}`, marginRight: 5, verticalAlign: 'middle' }} />Record set in report FY {fyLabel} (Apr – {reportLabel})</span>
                )}
                <span style={{ color: C.secondText }}>Small figure below = 2nd-best of that month</span>
              </div>

              <div style={{ overflow: 'auto', maxHeight: '72vh', border: '1px solid #dadce0', borderRadius: 8 }}>
                <table style={{ borderCollapse: 'collapse', minWidth: 1350, width: '100%' }}>
                  <thead>
                    <tr>
                      <th style={stickyItemHeaderCell}>Item</th>
                      {CAL_MONTHS.map((m) => {
                        const fyYm = fyMonthOf(m.num, reportMonth);
                        return (
                          <th
                            key={m.num}
                            style={fyYm ? { ...stickyHeaderCell, background: C.fyHeaderBg, boxShadow: 'inset 0 -3px 0 #fbbc04' } : stickyHeaderCell}
                            title={fyYm ? `${m.name}'${fyYm.slice(2, 4)} — in report FY ${fyLabel}` : undefined}
                          >
                            {m.name}
                            {fyYm && <div style={{ fontSize: '7.5pt', fontWeight: 600, opacity: 0.85 }}>FY {fyLabel}</div>}
                          </th>
                        );
                      })}
                    </tr>
                  </thead>
                  <tbody>
                    {items.length === 0 && (
                      <tr><td colSpan={13} style={{ padding: '24px', textAlign: 'center', color: '#9aa0a6' }}>No items found for this plant.</td></tr>
                    )}
                    {items.map((item, ri) => {
                      const cal = grp.cal_months?.[item] || {};
                      const bestMonth = grp.best_month?.[item]?.month;
                      const rowBg = ri % 2 === 0 ? '#ffffff' : '#fbfbfa';
                      return (
                        <tr key={item}>
                          <td style={{ ...stickyItemCell, background: ri % 2 === 0 ? C.stickyColBg : '#f1f2f3' }}>{item}</td>
                          {CAL_MONTHS.map((m) => {
                            const rows = cal[m.num] || [];
                            const best = rows[0];
                            const second = rows[1];
                            const isAllTimeBest = best && bestMonth && best.month === bestMonth;
                            const fyYm = fyMonthOf(m.num, reportMonth);
                            const bestInFy = !!(fyYm && best && best.month === fyYm);
                            const secondInFy = !!(fyYm && second && second.month === fyYm);
                            return (
                              <td
                                key={m.num}
                                style={{
                                  padding: '6px 6px', textAlign: 'center', verticalAlign: 'top',
                                  borderBottom: `1px solid ${C.border}`, borderLeft: `1px solid ${C.border}`,
                                  background: !best ? rowBg : isAllTimeBest ? C.topBg : C.bestBg,
                                  boxShadow: bestInFy ? `inset 0 0 0 2px ${C.fyRing}` : undefined,
                                }}
                                title={bestInFy ? `Best-ever ${m.name} set in report FY ${fyLabel}` : secondInFy ? `2nd-best ${m.name} set in report FY ${fyLabel}` : undefined}
                              >
                                {best ? (
                                  <>
                                    <div style={{
                                      fontSize: '9.5pt', fontWeight: 800,
                                      color: isAllTimeBest ? C.topText : C.bestText,
                                    }}>
                                      {fmt(best.total)}{isAllTimeBest ? ' ★' : ''}
                                    </div>
                                    {bestInFy && (
                                      <div style={{ display: 'inline-block', margin: '2px 0 1px', padding: '0 5px', borderRadius: 8, background: C.fyBadgeBg, color: '#fff', fontSize: '6.5pt', fontWeight: 700 }}>
                                        FY {fyLabel} BEST
                                      </div>
                                    )}
                                    <div style={{ fontSize: '7.5pt', fontStyle: 'italic', color: isAllTimeBest ? C.topText : C.bestText, opacity: 0.75 }}>
                                      {yearOf(best.month)}
                                    </div>
                                    {second && (
                                      <div style={{ marginTop: 3, fontSize: '8pt', color: secondInFy ? C.fyRing : C.secondText, fontWeight: secondInFy ? 700 : 400 }}>
                                        {fmt(second.total)} <span style={{ fontSize: '7pt', fontStyle: 'italic' }}>{yearOf(second.month)}</span>
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
                  </tbody>
                </table>
              </div>
            </>
          )}
        </div>
      </main>

      <style>{`html, body { overflow-y: auto; overflow-x: hidden; }`}</style>
    </>
  );
}
