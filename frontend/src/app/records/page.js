'use client';

import React, { useState, useEffect } from 'react';
import Link from 'next/link';

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
  hdr:     '#1e3a5f',
  hdrText: '#f1f5f9',
  gold:    '#b45309',
  goldBg:  '#fffbeb',
  goldBorder:'#fde68a',
  silver:  '#475569',
  silverBg:'#f8fafc',
  best:    '#065f46',
  bestBg:  '#d1fae5',
  bestBorder:'#6ee7b7',
  rank1:   '#92400e',
  rank1Bg: '#fef3c7',
  tblBorder:'#e2e8f0',
  subHdr:  '#334155',
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
    : { background: '#f1f5f9', color: '#64748b', border: '1px solid #e2e8f0' };
  return (
    <span style={{ ...s, borderRadius: 10, padding: '1px 7px', fontSize: '7.5pt', fontWeight: 700, marginRight: 4 }}>
      #{rank}
    </span>
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
  if (!rows || rows.length === 0) return <td colSpan={2} style={{ padding: '6px 10px', color: '#94a3b8', fontSize: '8.5pt' }}>—</td>;
  return (
    <>
      {[0, 1].map(i => {
        const r = rows[i];
        if (!r) return <td key={i} style={{ padding: '6px 10px', color: '#94a3b8', textAlign: 'center', fontSize: '8.5pt', borderRight: i === 0 ? `1px solid ${C.tblBorder}` : '' }}>—</td>;
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

// ── Calendar Month table ───────────────────────────────────────────────────
function CalMonthTable({ data, item, bestMonth }) {
  const calData = data?.cal_months?.[item] || {};
  const TH = { padding: '8px 10px', background: C.subHdr, color: '#e2e8f0', fontWeight: 700,
               fontSize: '8.5pt', borderRight: `1px solid #475569`, textAlign: 'center' };
  return (
    <div style={{ overflowX: 'auto' }}>
      <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '9pt' }}>
        <thead>
          <tr>
            <th style={{ ...TH, textAlign: 'left', width: 110 }}>Month</th>
            <th style={{ ...TH }}>Best (Rank #1)</th>
            <th style={{ ...TH, borderRight: 'none' }}>2nd Best (Rank #2)</th>
          </tr>
        </thead>
        <tbody>
          {CAL_MONTHS.map((name, i) => {
            const mon_num = i + 1;
            const rows = calData[mon_num] || [];
            const isBestRow = rows.some(r => r.month === bestMonth);
            return (
              <tr key={name} style={{ background: isBestRow ? C.bestBg : i % 2 === 0 ? '#fff' : '#f8fafc',
                                      borderBottom: `1px solid ${C.tblBorder}` }}>
                <td style={{ padding: '7px 12px', fontWeight: 700, color: C.subHdr, fontSize: '9.5pt',
                             borderRight: `1px solid ${C.tblBorder}` }}>
                  {name}
                  {isBestRow && <BestBadge />}
                </td>
                <RecordPair rows={rows} bestMonth={bestMonth} isCal={true} />
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

// ── FY Quarter table ───────────────────────────────────────────────────────
function FYQuarterTable({ data, item, bestQuarterPeriod }) {
  const qData = data?.fy_quarters?.[item] || {};
  const TH = { padding: '8px 10px', background: C.subHdr, color: '#e2e8f0', fontWeight: 700,
               fontSize: '8.5pt', borderRight: `1px solid #475569`, textAlign: 'center' };
  return (
    <div style={{ overflowX: 'auto' }}>
      <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '9pt' }}>
        <thead>
          <tr>
            <th style={{ ...TH, textAlign: 'left', width: 150 }}>Quarter</th>
            <th style={TH}>Best (Rank #1)</th>
            <th style={{ ...TH, borderRight: 'none' }}>2nd Best (Rank #2)</th>
          </tr>
        </thead>
        <tbody>
          {FY_QUARTERS.map((ql, i) => {
            const rows = qData[ql] || [];
            const isBestRow = rows.length > 0 && bestQuarterPeriod &&
              bestQuarterPeriod.includes(rows[0].period) && bestQuarterPeriod.includes(ql);
            return (
              <tr key={ql} style={{ background: isBestRow ? C.bestBg : i % 2 === 0 ? '#fff' : '#f8fafc',
                                    borderBottom: `1px solid ${C.tblBorder}` }}>
                <td style={{ padding: '7px 12px', fontWeight: 700, color: C.subHdr, fontSize: '9.5pt',
                             borderRight: `1px solid ${C.tblBorder}` }}>
                  {ql}
                  {isBestRow && <BestBadge />}
                </td>
                <RecordPair rows={rows} bestPeriod={bestQuarterPeriod} isCal={false} />
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

// ── FY Half table ──────────────────────────────────────────────────────────
function FYHalfTable({ data, item }) {
  const hData = data?.fy_halves?.[item] || {};
  const TH = { padding: '8px 10px', background: C.subHdr, color: '#e2e8f0', fontWeight: 700,
               fontSize: '8.5pt', borderRight: `1px solid #475569`, textAlign: 'center' };
  return (
    <div style={{ overflowX: 'auto' }}>
      <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '9pt' }}>
        <thead>
          <tr>
            <th style={{ ...TH, textAlign: 'left', width: 150 }}>Half Year</th>
            <th style={TH}>Best (Rank #1)</th>
            <th style={{ ...TH, borderRight: 'none' }}>2nd Best (Rank #2)</th>
          </tr>
        </thead>
        <tbody>
          {FY_HALVES.map((hl, i) => {
            const rows = hData[hl] || [];
            return (
              <tr key={hl} style={{ background: i % 2 === 0 ? '#fff' : '#f8fafc',
                                    borderBottom: `1px solid ${C.tblBorder}` }}>
                <td style={{ padding: '7px 12px', fontWeight: 700, color: C.subHdr, fontSize: '9.5pt',
                             borderRight: `1px solid ${C.tblBorder}` }}>{hl}</td>
                <RecordPair rows={rows} isCal={false} />
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

// ── Top 5 table (FY + CY side by side) ────────────────────────────────────
function Top5Table({ data, item }) {
  const fyRows = data?.top5_fy?.[item] || [];
  const cyRows = data?.top5_cy?.[item] || [];
  const TH  = { padding: '8px 10px', background: C.subHdr, color: '#e2e8f0', fontWeight: 700, fontSize: '8.5pt', textAlign: 'center' };
  const TD  = (rank, bg) => ({ padding: '7px 12px', textAlign: 'center', fontSize: '9pt',
    background: bg, fontWeight: rank === 1 ? 700 : rank === 2 ? 600 : 400,
    color: rank === 1 ? C.rank1 : rank === 2 ? C.silver : '#334155',
    borderBottom: `1px solid ${C.tblBorder}` });
  return (
    <div style={{ display: 'flex', gap: 20 }}>
      {[{ label: 'Financial Year (Apr-Mar)', rows: fyRows },
        { label: 'Calendar Year (Jan-Dec)',  rows: cyRows }].map(({ label, rows }) => (
        <div key={label} style={{ flex: 1, border: `1px solid ${C.tblBorder}`, borderRadius: 6, overflow: 'hidden' }}>
          <div style={{ padding: '8px 14px', background: C.subHdr, color: '#e2e8f0', fontWeight: 700, fontSize: '9pt' }}>
            {label}
          </div>
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead>
              <tr>
                <th style={{ ...TH, textAlign: 'left', width: 50 }}>Rank</th>
                <th style={TH}>Period</th>
                <th style={{ ...TH }}>Production ({ITEM_UNIT[item]})</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r, i) => {
                const bg = i === 0 ? C.rank1Bg : i === 1 ? '#f8fafc' : '#fff';
                return (
                  <tr key={i}>
                    <td style={{ ...TD(i + 1, bg), textAlign: 'center' }}><RankBadge rank={i + 1} /></td>
                    <td style={{ ...TD(i + 1, bg), fontWeight: i === 0 ? 700 : 500 }}>{r.period}</td>
                    <td style={{ ...TD(i + 1, bg), fontWeight: 700, fontSize: '10pt' }}>{fmt(r.total)}</td>
                  </tr>
                );
              })}
              {rows.length === 0 && (
                <tr><td colSpan={3} style={{ padding: 16, textAlign: 'center', color: '#94a3b8' }}>No data</td></tr>
              )}
            </tbody>
          </table>
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

  useEffect(() => {
    setLoading(true);
    fetch(`${API_BASE}/api/production-records`)
      .then(r => { if (!r.ok) throw new Error(r.statusText); return r.json(); })
      .then(d => { setData(d); setLoading(false); })
      .catch(e => { setError(e.message); setLoading(false); });
  }, []);

  const grpData = data?.[group];
  const bestMonth   = grpData?.best_month?.[item]?.month;
  const bestQuarter = grpData?.best_quarter?.[item]?.period;

  // ── Tab style helpers ──────────────────────────────────────────────────
  const tabBtn = (active) => ({
    padding: '6px 14px', borderRadius: 4, border: 'none', cursor: 'pointer',
    fontSize: '9pt', fontWeight: active ? 700 : 400,
    background: active ? C.hdr : '#e2e8f0',
    color: active ? '#fff' : '#475569',
    transition: 'all .15s',
  });

  const toggleBtn = (active) => ({
    padding: '5px 18px', borderRadius: 4, border: `1.5px solid ${active ? C.hdr : '#cbd5e1'}`,
    cursor: 'pointer', fontSize: '9pt', fontWeight: active ? 700 : 400,
    background: active ? C.hdr : '#fff', color: active ? '#fff' : '#475569',
  });

  return (
    <main className="app-container">
      {/* ── Sidebar ── */}
      <div className="sidebar no-print">
        <div className="sidebar-header">
          <h1 style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"
                 strokeLinecap="round" strokeLinejoin="round" style={{ color: 'var(--primary)' }}>
              <polyline points="23 6 13.5 15.5 8.5 10.5 1 18"/><polyline points="17 6 23 6 23 12"/>
            </svg>
            SAIL MIS Portal
          </h1>
          <p>Production Records</p>
        </div>

        <div className="control-section">
          <h2>Navigation</h2>
          {[
            { href: '/', label: 'Dashboard' },
            { href: '/upload', label: 'Excel Upload' },
            { href: '/report', label: 'Report Engine' },
            { href: '/data-entry', label: 'Data Entry' },
            { href: '/data-entry/techno', label: 'Techno Data Entry' },
          ].map(({ href, label }) => (
            <Link key={href} href={href} className="btn btn-secondary"
                  style={{ width: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center',
                           gap: 8, marginBottom: 8, textDecoration: 'none' }}>
              {label}
            </Link>
          ))}
        </div>

        <div className="control-section" style={{ marginTop: 16 }}>
          <h2>Plant Group</h2>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
            {[['sail5', 'SAIL-5 (BSP/DSP/RSP/BSL/ISP)'], ['all8', 'ALL-8 (incl. ASP/SSP/VISL)']].map(([k, lbl]) => (
              <button key={k} style={toggleBtn(group === k)} onClick={() => setGroup(k)}>{lbl}</button>
            ))}
          </div>
        </div>

        <div style={{ marginTop: 'auto', fontSize: '0.75rem', color: '#64748b', textAlign: 'center', paddingTop: 15 }}>
          SAIL Informatics Report Portal • v1.0.0
        </div>
      </div>

      {/* ── Main content ── */}
      <div className="preview-area" style={{ padding: '28px 32px', overflowY: 'auto', background: '#f8fafc' }}>
        {/* Page title */}
        <div style={{ marginBottom: 20 }}>
          <h1 style={{ fontSize: '16pt', fontWeight: 800, color: '#0f172a', margin: '0 0 4px 0' }}>
            Production Records Dashboard
          </h1>
          <p style={{ fontSize: '9.5pt', color: '#64748b', margin: 0 }}>
            Best &amp; 2nd-best production by calendar month, FY quarter, FY half · Top-5 FY &amp; calendar years
            · <strong>{group === 'sail5' ? 'SAIL-5 (BSP/DSP/RSP/BSL/ISP)' : 'ALL-8 (incl. ASP/SSP/VISL)'}</strong>
            &nbsp;·&nbsp;Unit: &#39;000 Tonnes
          </p>
        </div>

        {loading && (
          <div style={{ padding: 60, textAlign: 'center', color: '#64748b', fontSize: '10pt' }}>
            Loading records data…
          </div>
        )}

        {error && (
          <div style={{ padding: 20, background: '#fef2f2', border: '1px solid #fca5a5',
                        borderRadius: 8, color: '#991b1b', fontSize: '9.5pt' }}>
            Error loading data: {error}
          </div>
        )}

        {!loading && !error && data && (
          <>
            {/* Item tabs */}
            <div style={{ display: 'flex', gap: 6, marginBottom: 16, flexWrap: 'wrap' }}>
              {ITEMS.map(it => (
                <button key={it} style={tabBtn(item === it)} onClick={() => setItem(it)}>
                  {ITEM_SHORT[it]}
                </button>
              ))}
            </div>

            {/* Best-ever strip */}
            <BestEverStrip data={grpData} item={item} />

            {/* Section tabs */}
            <div style={{ display: 'flex', gap: 6, marginBottom: 16, flexWrap: 'wrap' }}>
              {SECTIONS.map(s => (
                <button key={s} style={tabBtn(section === s)} onClick={() => setSection(s)}>{s}</button>
              ))}
            </div>

            {/* Content card */}
            <div style={{ background: '#fff', border: `1px solid ${C.tblBorder}`, borderRadius: 8, overflow: 'hidden' }}>
              {/* Card header */}
              <div style={{ padding: '12px 18px', background: C.hdr, color: C.hdrText,
                            display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <span style={{ fontWeight: 700, fontSize: '10pt' }}>
                  {section} — {ITEM_SHORT[item]}
                </span>
                <span style={{ fontSize: '8.5pt', color: '#94a3b8' }}>
                  {group === 'sail5' ? 'SAIL-5' : 'ALL-8'} · ★ = Best Ever
                </span>
              </div>

              <div style={{ padding: 16 }}>
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
            </div>

            {/* Legend */}
            <div style={{ marginTop: 12, display: 'flex', gap: 16, fontSize: '8pt', color: '#64748b', flexWrap: 'wrap' }}>
              <span style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
                <span style={{ width: 14, height: 14, borderRadius: 3, background: C.rank1Bg,
                               border: `1px solid #fcd34d`, display: 'inline-block' }}/>
                Rank #1 (Best in period)
              </span>
              <span style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
                <span style={{ width: 14, height: 14, borderRadius: 3, background: C.bestBg,
                               border: `1px solid ${C.bestBorder}`, display: 'inline-block' }}/>
                ★ Best Ever across all years
              </span>
              <span>Only complete periods counted (12 months for FY/CY, 3 months for quarters, 6 for halves)</span>
            </div>
          </>
        )}
      </div>
    </main>
  );
}
