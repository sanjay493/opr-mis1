'use client';

import React, { useState, useEffect } from 'react';
import GlobalNavbar from '@/components/GlobalNavbar';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || '';

const ITEMS   = ['Hot Metal', 'Total Crude Steel', 'Saleable Steel'];
const ITEM_SHORT = { 'Hot Metal': 'Hot Metal', 'Total Crude Steel': 'Crude Steel', 'Saleable Steel': 'Saleable Steel' };
const ITEM_UNIT  = { 'Hot Metal': "'000 T", 'Total Crude Steel': "'000 T", 'Saleable Steel': "'000 T" };

const CAL_MONTHS = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
const FY_QUARTERS = ['Q1 (Apr-Jun)','Q2 (Jul-Sep)','Q3 (Oct-Dec)','Q4 (Jan-Mar)'];
const FY_HALVES   = ['H1 (Apr-Sep)','H2 (Oct-Mar)'];
const SECTIONS    = ['Calendar Month','FY Quarter','FY Half','Top 5 Years'];

// ── Colours ────────────────────────────────────────────────────────────────
const C = {
  hdr:     '#e8f0fe',
  hdrText: '#f8f9fa',
  gold:    '#b45309',
  goldBg:  '#fffbeb',
  goldBorder:'#fde68a',
  silver:  '#dadce0',
  silverBg:'#202124',
  best:    '#065f46',
  bestBg:  '#d1fae5',
  bestBorder:'#6ee7b7',
  rank1:   '#92400e',
  rank1Bg: '#fef3c7',
  tblBorder:'#dadce0',
  subHdr:  '#dadce0',
  accent:  '#3b82f6',
};

function fmt(v) {
  if (v == null) return '—';
  return Number(v).toLocaleString('en-IN', { minimumFractionDigits: 3, maximumFractionDigits: 3 });
}

// ── Rank badge ─────────────────────────────────────────────────────────────
function RankBadge({ rank }) {
  const s = rank === 1
    ? { background: C.rank1Bg, color: C.rank1, border: `1px solid #fcd34d` }
    : { background: '#f8f9fa', color: '#5f6368', border: '1px solid #dadce0' };
  return (
    <span style={{ ...s, borderRadius: 10, padding: '1px 7px', fontSize: '7.5pt', fontWeight: 700, marginRight: 4 }}>
      #{rank}
    </span>
  );
}

// ── Vertical Bar Chart Component ───────────────────────────────────────────
function VerticalBarChart({ data, item, title, isMonthChart = false }) {
  if (!data || data.length === 0) {
    return <div style={{ padding: '20px', color: '#5f6368', textAlign: 'center' }}>No data available</div>;
  }

  // For month chart, maintain April-to-March order; otherwise sort by value descending
  let chartData = isMonthChart ? data : [...data].sort((a, b) => (b.total || 0) - (a.total || 0));

  const maxValue = Math.max(...chartData.map(d => d.total || 0), 1);

  // Get rank (1-based) for each data point when sorted by value
  const sortedByValue = [...data].sort((a, b) => (b.total || 0) - (a.total || 0));
  const getRankForValue = (val) => {
    return sortedByValue.findIndex(d => d.total === val) + 1;
  };

  // Color mapping: Rank 1=Gold, Rank 2=Silver, Rank 3=Bronze, Rest=Light Pellet Green
  const getRankColor = (value) => {
    const rank = getRankForValue(value);
    if (rank === 1) return { bar: '#d97706', label: 'gold' };              // Golden
    if (rank === 2) return { bar: '#a8adb5', label: 'silver' };            // Silver
    if (rank === 3) return { bar: '#a85a36', label: 'bronze' };            // Bronze
    return { bar: '#16a34a', label: 'green' };                              // Light Pellet Green
  };

  return (
    <div style={{
      display: 'grid',
      gridTemplateColumns: 'repeat(12, 1fr)',
      gap: '8px',
      alignItems: 'flex-end',
      padding: '20px',
      backgroundColor: '#fff',
      borderRadius: '8px',
      minHeight: '320px',
      overflowX: 'auto'
    }}>
      {chartData.map((entry, idx) => {
        const colors = getRankColor(entry.total);
        const barHeight = (entry.total / maxValue) * 100;
        const rank = getRankForValue(entry.total);

        return (
          <div
            key={idx}
            style={{
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              gap: '6px',
              justifyContent: 'flex-end'
            }}
          >
            {/* Quantity Label (Top) */}
            <div style={{
              fontSize: '14px',
              fontWeight: '900',
              color: colors.bar,
              textAlign: 'center',
              maxWidth: '100%',
              minHeight: '18px',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              marginBottom: '20px',
              transform: 'rotate(-70deg)',
              transformOrigin: 'center',
              whiteSpace: 'nowrap',
              letterSpacing: '0.5px'
            }}>
              {fmt(entry.total)}
            </div>

            {/* Bar Container */}
            <div style={{
              width: '100%',
              height: '180px',
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              justifyContent: 'flex-end',
              position: 'relative'
            }}>
              {/* Bar - Scaled to show difference */}
              <div
                style={{
                  width: '85%',
                  height: `${Math.max(barHeight, 3)}%`,
                  backgroundColor: colors.bar,
                  borderRadius: '4px 4px 0 0',
                  transition: 'all 0.3s ease',
                  boxShadow: `0 2px 6px ${colors.bar}50`,
                  position: 'relative',
                  cursor: 'pointer',
                  display: 'flex',
                  flexDirection: 'column',
                  alignItems: 'center',
                  justifyContent: 'flex-start',
                  paddingTop: '2px'
                }}
              >
                {/* Rank Badge (Inside Bar if space) */}
                {barHeight > 25 && rank <= 3 && (
                  <div style={{
                    width: '16px',
                    height: '16px',
                    borderRadius: '50%',
                    backgroundColor: 'rgba(255, 255, 255, 0.95)',
                    color: colors.bar,
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    fontSize: '9px',
                    fontWeight: '900',
                    border: `1px solid ${colors.bar}`,
                    flexShrink: 0,
                    marginTop: '2px'
                  }}>
                    {rank}
                  </div>
                )}
              </div>
            </div>

            {/* Period Label (Bottom) */}
            <div style={{
              fontSize: '14px',
              fontWeight: '900',
              color: colors.bar,
              textAlign: 'center',
              maxWidth: '100%',
              minHeight: '18px',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              marginTop: '2px',
              lineHeight: '1.2'
            }}>
              {entry.period}
            </div>

            {/* Rank Badge (Outside Bar if needed) */}
            {barHeight <= 25 && rank <= 3 && (
              <div style={{
                width: '16px',
                height: '16px',
                borderRadius: '50%',
                backgroundColor: colors.bar,
                color: '#fff',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                fontSize: '8px',
                fontWeight: '900',
                border: '1px solid white'
              }}>
                {rank}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}

// ── Horizontal Bar Chart Component (for Quarter/Half/Top5) ─────────────────
function BarChart({ data, item, title }) {
  if (!data || data.length === 0) {
    return <div style={{ padding: '20px', color: '#5f6368', textAlign: 'center' }}>No data available</div>;
  }

  // Sort by value descending
  const sortedData = [...data].sort((a, b) => (b.total || 0) - (a.total || 0));
  const maxValue = Math.max(...sortedData.map(d => d.total || 0), 1);

  // Get rank for each entry
  const getRankForValue = (val) => {
    return sortedData.findIndex(d => d.total === val) + 1;
  };

  // Color mapping: Rank 1=Gold, Rank 2=Silver, Rank 3=Bronze, Rest=Light Pellet Green
  const getRankColor = (index) => {
    if (index === 0) return { bar: '#d97706', bg: '#fef3c7' };               // Golden
    if (index === 1) return { bar: '#a8adb5', bg: '#f3f4f6' };               // Silver
    if (index === 2) return { bar: '#a85a36', bg: '#faf5f0' };               // Bronze
    return { bar: '#86efac', bg: '#f0fdf4' };                                 // Light Pellet Green
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
      {sortedData.slice(0, 10).map((entry, idx) => {
        const colors = getRankColor(idx);
        const barWidth = (entry.total / maxValue) * 100;
        const rank = idx + 1;

        return (
          <div
            key={idx}
            style={{
              display: 'grid',
              gridTemplateColumns: '120px 1fr 80px',
              gap: '12px',
              alignItems: 'center',
              padding: '12px',
              backgroundColor: colors.bg,
              borderRadius: '8px',
              border: `2px solid ${colors.bar}`
            }}
          >
            {/* Label */}
            <div style={{
              fontSize: '12px',
              fontWeight: '700',
              color: '#202124',
              overflow: 'hidden',
              textOverflow: 'ellipsis',
              whiteSpace: 'nowrap'
            }}>
              {rank <= 3 && (
                <span style={{
                  display: 'inline-block',
                  width: '20px',
                  height: '20px',
                  borderRadius: '50%',
                  background: colors.bar,
                  color: '#fff',
                  fontSize: '10px',
                  fontWeight: '900',
                  textAlign: 'center',
                  lineHeight: '20px',
                  marginRight: '6px'
                }}>
                  {rank}
                </span>
              )}
              {entry.period}
            </div>

            {/* Bar */}
            <div style={{
              height: '32px',
              backgroundColor: '#e5e7eb',
              borderRadius: '6px',
              overflow: 'hidden',
              position: 'relative'
            }}>
              <div
                style={{
                  height: '100%',
                  width: `${barWidth}%`,
                  backgroundColor: colors.bar,
                  borderRadius: '6px',
                  transition: 'width 0.3s ease',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'flex-end',
                  paddingRight: '8px'
                }}
              >
                {barWidth > 15 && (
                  <span style={{
                    color: '#fff',
                    fontSize: '11px',
                    fontWeight: '700'
                  }}>
                    {fmt(entry.total)}
                  </span>
                )}
              </div>
              {barWidth <= 15 && (
                <span style={{
                  position: 'absolute',
                  right: '8px',
                  top: '50%',
                  transform: 'translateY(-50%)',
                  fontSize: '11px',
                  fontWeight: '700',
                  color: colors.bar
                }}>
                  {fmt(entry.total)}
                </span>
              )}
            </div>

            {/* Rank Badge */}
            <div style={{
              textAlign: 'right',
              fontSize: '11px',
              fontWeight: '700',
              color: colors.bar
            }}>
              {rank <= 3 && `#${rank}`}
            </div>
          </div>
        );
      })}
    </div>
  );
}

// ── Best-ever badge ────────────────────────────────────────────────────────
function BestBadge() {
  return (
    <span style={{ background: C.bestBg, color: C.best, border: `1px solid ${C.bestBorder}`,
                   borderRadius: 10, padding: '1px 7px', fontSize: '7pt', fontWeight: 700, marginLeft: 6 }}>
      ★ Best Ever
    </span>
  );
}

// ── Two-row record cell ────────────────────────────────────────────────────
function RecordPair({ rows, bestPeriod, bestMonth, isCal }) {
  if (!rows || rows.length === 0) return <td colSpan={2} style={{ padding: '6px 10px', color: '#5f6368', fontSize: '8.5pt' }}>—</td>;
  return (
    <>
      {[0, 1].map(i => {
        const r = rows[i];
        if (!r) return <td key={i} style={{ padding: '6px 10px', color: '#5f6368', textAlign: 'center', fontSize: '8.5pt', borderRight: i === 0 ? `1px solid ${C.tblBorder}` : '' }}>—</td>;
        const isBest = isCal ? r.month === bestMonth : r.period === bestPeriod;
        return (
          <td key={i} style={{
            padding: '6px 10px', textAlign: 'center', fontSize: '9pt',
            background: isBest ? C.bestBg : i === 0 ? C.rank1Bg : '#fff',
            borderRight: i === 0 ? `1px solid ${C.tblBorder}` : '',
            fontWeight: isBest ? 700 : i === 0 ? 600 : 400,
            color: isBest ? C.best : i === 0 ? C.rank1 : C.silver,
          }}>
            <RankBadge rank={i + 1} />
            <span>{r.period}</span>
            {isBest && <BestBadge />}
            <br />
            <span style={{ fontSize: '10pt', fontWeight: 700 }}>{fmt(r.total)}</span>
          </td>
        );
      })}
    </>
  );
}

// ── Calendar Month Bar Chart (Vertical - April to March) ──────────────────
function CalMonthTable({ data, item, bestMonth }) {
  const calData = data?.cal_months?.[item] || {};

  // FY month order: April (4) to March (3)
  const FY_MONTHS = [
    { num: 4, name: 'Apr' }, { num: 5, name: 'May' }, { num: 6, name: 'Jun' },
    { num: 7, name: 'Jul' }, { num: 8, name: 'Aug' }, { num: 9, name: 'Sep' },
    { num: 10, name: 'Oct' }, { num: 11, name: 'Nov' }, { num: 12, name: 'Dec' },
    { num: 1, name: 'Jan' }, { num: 2, name: 'Feb' }, { num: 3, name: 'Mar' }
  ];

  // Convert to flat array maintaining FY month order
  const chartData = FY_MONTHS
    .map(({ num, name }) => {
      const rows = calData[num] || [];
      if (rows.length === 0) return null;
      // Extract year from month data if available, otherwise use current year
      const monthData = rows[0]?.month || '';
      const yearMatch = monthData.match(/\d{4}/);
      const year = yearMatch ? yearMatch[0] : new Date().getFullYear();

      return {
        period: `${name} ${year}`,  // e.g., "Apr 2024"
        total: rows[0]?.total,
        month: rows[0]?.month,
        isBest: rows.some(r => r.month === bestMonth)
      };
    })
    .filter(Boolean);

  return <VerticalBarChart data={chartData} item={item} title="FY Month Production (Apr-Mar)" isMonthChart={true} />;
}

// ── FY Quarter Bar Chart (Vertical) ───────────────────────────────────────
function FYQuarterTable({ data, item, bestQuarterPeriod }) {
  const qData = data?.fy_quarters?.[item] || {};

  // Convert to flat array - maintain Q1-Q4 order
  const chartData = FY_QUARTERS
    .map((ql, i) => {
      const rows = qData[ql] || [];
      if (rows.length === 0) return null;
      const qMatch = ql.match(/Q\d/)[0];  // Extract "Q1", "Q2", etc.
      const periodData = rows[0]?.period || '';
      // Extract FY year from period data if available
      const fyMatch = periodData.match(/FY[\d]{2,4}/);
      const fy = fyMatch ? fyMatch[0] : `FY${new Date().getFullYear().toString().slice(-2)}`;

      return {
        period: `${qMatch} ${fy}`,  // e.g., "Q1 FY25"
        total: rows[0]?.total,
        isBest: rows.length > 0 && bestQuarterPeriod && rows[0].period === bestQuarterPeriod
      };
    })
    .filter(Boolean);

  return <VerticalBarChart data={chartData} item={item} title="FY Quarter Production" isMonthChart={false} />;
}

// ── FY Half Bar Chart (Vertical) ──────────────────────────────────────────
function FYHalfTable({ data, item }) {
  const hData = data?.fy_halves?.[item] || {};

  // Convert to flat array - maintain H1-H2 order
  const chartData = FY_HALVES
    .map((hl, i) => {
      const rows = hData[hl] || [];
      if (rows.length === 0) return null;
      const hMatch = hl.match(/H\d/)[0];  // Extract "H1", "H2"
      const periodData = rows[0] || {};
      // Extract FY year or use current
      const fy = `FY${new Date().getFullYear().toString().slice(-2)}`;

      return {
        period: `${hMatch} ${fy}`,  // e.g., "H1 FY25"
        total: rows[0]?.total
      };
    })
    .filter(Boolean);

  return <VerticalBarChart data={chartData} item={item} title="FY Half Year Production" isMonthChart={false} />;
}

// ── Top 5 table (FY + CY side by side) ────────────────────────────────────
function Top5Table({ data, item }) {
  const fyRows = (data?.top5_fy?.[item] || []).map((row, idx) => ({
    ...row,
    period: `${row.period} FY${new Date().getFullYear().toString().slice(-2)}`
  }));
  const cyRows = (data?.top5_cy?.[item] || []).map((row, idx) => ({
    ...row,
    period: `${row.period} CY${new Date().getFullYear()}`
  }));

  return (
    <div style={{
      display: 'grid',
      gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))',
      gap: '20px'
    }}>
      {[
        { label: 'Top 5 Financial Years', rows: fyRows },
        { label: 'Top 5 Calendar Years', rows: cyRows }
      ].map(({ label, rows }) => (
        <div key={label}>
          <h3 style={{
            fontSize: '12px',
            fontWeight: '800',
            color: '#202124',
            marginBottom: '10px',
            textTransform: 'uppercase',
            letterSpacing: '0.05em'
          }}>
            {label}
          </h3>
          <VerticalBarChart data={rows} item={item} title={label} isMonthChart={false} />
        </div>
      ))}
    </div>
  );
}

// ── Best-ever summary strip ────────────────────────────────────────────────
function BestEverStrip({ data, item }) {
  const bm = data?.best_month?.[item];
  const bq = data?.best_quarter?.[item];
  const card = (label, period, total) => (
    <div style={{ flex: 1, background: C.bestBg, border: `1.5px solid ${C.bestBorder}`,
                  borderRadius: 8, padding: '10px 16px' }}>
      <div style={{ fontSize: '8pt', color: '#047857', fontWeight: 600, marginBottom: 2 }}>{label}</div>
      <div style={{ fontSize: '13pt', fontWeight: 800, color: C.best }}>{period ?? '—'}</div>
      <div style={{ fontSize: '10pt', fontWeight: 700, color: '#065f46', marginTop: 2 }}>
        {total != null ? fmt(total) : '—'} <span style={{ fontSize: '8pt', fontWeight: 400 }}>{ITEM_UNIT[item]}</span>
      </div>
    </div>
  );
  return (
    <div style={{ display: 'flex', gap: 12, marginBottom: 18 }}>
      {card('★ Best Ever Month', bm?.period, bm?.total)}
      {card('★ Best Ever Quarter', bq?.period, bq?.total)}
    </div>
  );
}

// ── Main page ──────────────────────────────────────────────────────────────
export default function RecordsPage() {
  const [data,    setData]    = useState(null);
  const [loading, setLoading] = useState(true);
  const [error,   setError]   = useState(null);
  const [group,   setGroup]   = useState('sail5');   // sail5 | all8
  const [item,    setItem]    = useState(ITEMS[0]);
  const [section, setSection] = useState(SECTIONS[0]);
  const [autoRotate, setAutoRotate] = useState(true);

  // Fetch data on mount
  useEffect(() => {
    setLoading(true);
    fetch(`${API_BASE}/api/production-records`)
      .then(r => { if (!r.ok) throw new Error(r.statusText); return r.json(); })
      .then(d => { setData(d); setLoading(false); })
      .catch(e => { setError(e.message); setLoading(false); });
  }, []);

  // Auto-rotate sections every 5 minutes
  useEffect(() => {
    if (!autoRotate) return;

    const interval = setInterval(() => {
      setSection(prev => {
        const currentIdx = SECTIONS.indexOf(prev);
        const nextIdx = (currentIdx + 1) % SECTIONS.length;
        return SECTIONS[nextIdx];
      });
    }, 5 * 60 * 1000); // 5 minutes in milliseconds

    return () => clearInterval(interval);
  }, [autoRotate]);

  const grpData = data?.[group];
  const bestMonth   = grpData?.best_month?.[item]?.month;
  const bestQuarter = grpData?.best_quarter?.[item]?.period;

  // ── Tab style helpers ──────────────────────────────────────────────────
  const tabBtn = (active) => ({
    padding: '6px 14px', borderRadius: 4, border: 'none', cursor: 'pointer',
    fontSize: '9pt', fontWeight: active ? 700 : 400,
    background: active ? C.hdr : '#dadce0',
    color: active ? '#fff' : '#dadce0',
    transition: 'all .15s',
  });

  const toggleBtn = (active) => ({
    padding: '5px 18px', borderRadius: 4, border: `1.5px solid ${active ? C.hdr : '#202124'}`,
    cursor: 'pointer', fontSize: '9pt', fontWeight: active ? 700 : 400,
    background: active ? C.hdr : '#fff', color: active ? '#fff' : '#dadce0',
  });

  return (
    <>
      {/* Global Navbar */}
      <GlobalNavbar />

      <main style={{
        backgroundColor: '#ffffff',
        padding: '40px 32px',
        width: '100%',
        minHeight: 'calc(100vh - 70px)'
      }}>
        {/* Header */}
        <div style={{ marginBottom: '32px' }}>
          <h1 style={{
            fontSize: '32px',
            fontWeight: '900',
            color: '#202124',
            margin: '0 0 8px 0',
            letterSpacing: '-0.02em'
          }}>
            Production Records Dashboard
          </h1>
          <p style={{
            fontSize: '13px',
            color: '#5f6368',
            margin: '0',
            lineHeight: '1.6'
          }}>
            Real-time production metrics with auto-rotating views every 5 minutes
          </p>
        </div>

        {/* Two-Column Layout: Left Controls (1/3) + Right Chart (2/3) */}
        <div style={{
          display: 'grid',
          gridTemplateColumns: '1fr 2fr',
          gap: '24px',
          maxWidth: '1600px',
          margin: '0 auto',
          alignItems: 'start'
        }}>
          {/* ═══ LEFT PANEL: CONTROLS ═══ */}
          <div style={{
            display: 'flex',
            flexDirection: 'column',
            gap: '20px'
          }}>

        {loading && (
          <div style={{
            padding: '80px 40px',
            textAlign: 'center',
            color: '#5f6368',
            fontSize: '14px'
          }}>
            <div style={{ marginBottom: '16px' }}>
              <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5"
                   style={{ margin: '0 auto', color: '#202124', animation: 'spin 2s linear infinite' }}>
                <circle cx="12" cy="12" r="10" />
                <path d="M12 6v6l4 2" />
              </svg>
            </div>
            Loading records data…
          </div>
        )}

        {error && (
          <div style={{
            padding: '20px 24px',
            background: '#fef2f2',
            border: '1px solid #fca5a5',
            borderRadius: '8px',
            color: '#991b1b',
            fontSize: '13px'
          }}>
            Error loading data: {error}
          </div>
        )}

          {/* Best Records Display - Top Inline */}
          {!loading && !error && data && (
            <>
              {(() => {
                const bm = grpData?.best_month?.[item];
                const bq = grpData?.best_quarter?.[item];
                return (
                  <div style={{
                    display: 'grid',
                    gridTemplateColumns: '1fr 1fr',
                    gap: '12px',
                    marginBottom: '16px'
                  }}>
                    <div style={{
                      backgroundColor: '#fef3c7',
                      borderRadius: '10px',
                      padding: '14px',
                      border: '2px solid #fcd34d',
                      boxShadow: '0 1px 3px rgba(0,0,0,0.08)'
                    }}>
                      <div style={{ fontSize: '9px', fontWeight: '700', color: '#92400e', marginBottom: '4px', textTransform: 'uppercase' }}>🥇 Best Month</div>
                      <div style={{ fontSize: '16px', fontWeight: '900', color: '#92400e' }}>{fmt(bm?.total)}</div>
                      <div style={{ fontSize: '8px', color: '#b45309', marginTop: '3px' }}>{bm?.period || '—'}</div>
                    </div>
                    <div style={{
                      backgroundColor: '#d1fae5',
                      borderRadius: '10px',
                      padding: '14px',
                      border: '2px solid #6ee7b7',
                      boxShadow: '0 1px 3px rgba(0,0,0,0.08)'
                    }}>
                      <div style={{ fontSize: '9px', fontWeight: '700', color: '#065f46', marginBottom: '4px', textTransform: 'uppercase' }}>🥇 Best Quarter</div>
                      <div style={{ fontSize: '16px', fontWeight: '900', color: '#065f46' }}>{fmt(bq?.total)}</div>
                      <div style={{ fontSize: '8px', color: '#047857', marginTop: '3px' }}>{bq?.period || '—'}</div>
                    </div>
                  </div>
                );
              })()}

              {/* Bottom Section: Two-Column Layout */}
              <div style={{
                display: 'grid',
                gridTemplateColumns: '1fr 1fr',
                gap: '12px',
                flex: 1,
                minHeight: '350px',
                alignItems: 'center'
              }}>
                {/* Left Column: Plant Group + Item */}
                <div style={{
                  display: 'flex',
                  flexDirection: 'column',
                  gap: '12px'
                }}>
                  {/* Plant Group Selector */}
                  <div style={{
                    backgroundColor: '#fff',
                    borderRadius: '10px',
                    padding: '14px',
                    boxShadow: '0 1px 3px rgba(0,0,0,0.08)',
                    border: '1px solid #dadce0'
                  }}>
                    <label style={{
                      display: 'block',
                      fontSize: '10px',
                      fontWeight: '800',
                      color: '#202124',
                      marginBottom: '8px',
                      textTransform: 'uppercase',
                      letterSpacing: '0.05em'
                    }}>
                      🏭 Plant
                    </label>
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                      {[
                        ['sail5', '5 Plants'],
                        ['all8', 'All 8']
                      ].map(([key, label]) => (
                        <button
                          key={key}
                          onClick={() => setGroup(key)}
                          style={{
                            padding: '8px 10px',
                            borderRadius: '6px',
                            border: `2px solid ${group === key ? '#1a73e8' : '#dadce0'}`,
                            background: group === key ? '#f0f9ff' : '#fff',
                            color: group === key ? '#1a73e8' : '#dadce0',
                            fontSize: '11px',
                            fontWeight: group === key ? '700' : '600',
                            cursor: 'pointer',
                            transition: 'all 0.2s'
                          }}
                        >
                          {label}
                        </button>
                      ))}
                    </div>
                  </div>

                  {/* Production Item Selector */}
                  <div style={{
                    backgroundColor: '#fff',
                    borderRadius: '10px',
                    padding: '14px',
                    boxShadow: '0 1px 3px rgba(0,0,0,0.08)',
                    border: '1px solid #dadce0',
                    flex: 1
                  }}>
                    <label style={{
                      display: 'block',
                      fontSize: '10px',
                      fontWeight: '800',
                      color: '#202124',
                      marginBottom: '8px',
                      textTransform: 'uppercase',
                      letterSpacing: '0.05em'
                    }}>
                      📊 Item
                    </label>
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                      {ITEMS.map(it => (
                        <button
                          key={it}
                          onClick={() => setItem(it)}
                          style={{
                            padding: '7px 10px',
                            borderRadius: '6px',
                            border: `2px solid ${item === it ? '#1a73e8' : '#dadce0'}`,
                            background: item === it ? '#f0f9ff' : '#fff',
                            color: item === it ? '#1a73e8' : '#dadce0',
                            fontSize: '10px',
                            fontWeight: item === it ? '700' : '600',
                            cursor: 'pointer',
                            transition: 'all 0.2s',
                            textAlign: 'left'
                          }}
                        >
                          {ITEM_SHORT[it]}
                        </button>
                      ))}
                    </div>
                  </div>
                </div>

                {/* Right Column: Time Period (Full Height) */}
                <div style={{
                  backgroundColor: '#fff',
                  borderRadius: '10px',
                  padding: '14px',
                  boxShadow: '0 1px 3px rgba(0,0,0,0.08)',
                  border: '1px solid #dadce0',
                  display: 'flex',
                  flexDirection: 'column'
                }}>
                  <label style={{
                    display: 'block',
                    fontSize: '10px',
                    fontWeight: '800',
                    color: '#202124',
                    marginBottom: '8px',
                    textTransform: 'uppercase',
                    letterSpacing: '0.05em'
                  }}>
                    ⏱️ Period
                  </label>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '5px', flex: 1 }}>
                    {SECTIONS.map(s => (
                      <button
                        key={s}
                        onClick={() => {
                          setSection(s);
                          setAutoRotate(false);
                        }}
                        style={{
                          padding: '7px 10px',
                          borderRadius: '6px',
                          border: `2px solid ${section === s ? '#10b981' : '#dadce0'}`,
                          background: section === s ? '#f0fdf4' : '#fff',
                          color: section === s ? '#10b981' : '#dadce0',
                          fontSize: '10px',
                          fontWeight: section === s ? '700' : '600',
                          cursor: 'pointer',
                          transition: 'all 0.2s',
                          textAlign: 'left'
                        }}
                      >
                        {s}
                      </button>
                    ))}
                  </div>
                  <div style={{
                    marginTop: 'auto',
                    paddingTop: '8px',
                    borderTop: '1px solid #dadce0',
                    fontSize: '9px',
                    color: '#5f6368',
                    textAlign: 'center'
                  }}>
                    {autoRotate ? '🔄 Auto' : '⏸️ Manual'}
                  </div>
                </div>
              </div>
            </>
          )}
          </div>

          {/* ═══ RIGHT PANEL: CHART DISPLAY ═══ */}
          {!loading && !error && data && (
          <div style={{
            backgroundColor: '#fff',
            borderRadius: '12px',
            padding: '24px',
            boxShadow: '0 4px 6px rgba(0,0,0,0.07)',
            border: '1px solid #dadce0',
            minHeight: '350px',
            display: 'flex',
            flexDirection: 'column'
          }}>
            {/* Chart Header */}
            <div style={{
              marginBottom: '20px',
              paddingBottom: '16px',
              borderBottom: '2px solid #dadce0'
            }}>
              <h2 style={{
                fontSize: '18px',
                fontWeight: '800',
                color: '#202124',
                margin: '0 0 4px 0'
              }}>
                {section} — {ITEM_SHORT[item]}
              </h2>
              <p style={{
                fontSize: '11px',
                color: '#5f6368',
                margin: '0',
                textTransform: 'uppercase',
                letterSpacing: '0.05em'
              }}>
                {group === 'sail5' ? '5 Plants (SAIL-5)' : 'All 8 Plants'} • Unit: '000 Tonnes
              </p>
            </div>

            {/* Chart Display */}
            <div style={{
              flexGrow: 1,
              display: 'flex',
              flexDirection: 'column'
            }}>
              {section === 'Calendar Month' && (
                <CalMonthTable data={grpData} item={item} bestMonth={bestMonth} />
              )}
              {section === 'FY Quarter' && (
                <FYQuarterTable data={grpData} item={item} bestQuarterPeriod={bestQuarter} />
              )}
              {section === 'FY Half' && (
                <FYHalfTable data={grpData} item={item} />
              )}
              {section === 'Top 5 Years' && (
                <Top5Table data={grpData} item={item} />
              )}
            </div>

            {/* Legend */}
            <div style={{
              marginTop: '20px',
              paddingTop: '16px',
              borderTop: '1px solid #dadce0',
              fontSize: '11px',
              color: '#5f6368'
            }}>
              <div style={{ fontWeight: '700', marginBottom: '8px', textTransform: 'uppercase' }}>Color Legend:</div>
              <div style={{
                display: 'flex',
                gap: '16px',
                flexWrap: 'wrap'
              }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                  <span style={{ width: '14px', height: '14px', borderRadius: '2px', background: '#d97706' }}/>
                  <span>🥇 Rank 1</span>
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                  <span style={{ width: '14px', height: '14px', borderRadius: '2px', background: '#a8adb5' }}/>
                  <span>🥈 Rank 2</span>
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                  <span style={{ width: '14px', height: '14px', borderRadius: '2px', background: '#a85a36' }}/>
                  <span>🥉 Rank 3</span>
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                  <span style={{ width: '14px', height: '14px', borderRadius: '2px', background: '#16a34a' }}/>
                  <span>🌿 Others</span>
                </div>
              </div>
            </div>
          </div>
          )}
        </div>
      </main>

      {/* ── Global Styles ── */}
      <style>{`
        html, body {
          overflow-y: auto;
          overflow-x: hidden;
        }
        @keyframes spin {
          from { transform: rotate(0deg); }
          to { transform: rotate(360deg); }
        }
      `}</style>
    </>
  );
}
