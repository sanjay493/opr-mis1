'use client';

import React, { useState, useEffect } from 'react';
import { ReportPage } from '../ReportUI';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || '';

// Same plant set and rows as the Best Techno Matrix (techno-records).
const TABS = ['BSP', 'DSP', 'RSP', 'BSL', 'ISP', 'SAIL'];
const MON = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
const RANKS = ['Best', '2nd', '3rd'];

function fmt(v, unit) {
  if (v == null) return '—';
  const digits = unit === 't/thm' ? 3 : (unit === 't/m³/day' || unit === 'Gcal/tcs') ? 2 : 1;
  return Number(v).toLocaleString('en-IN', { minimumFractionDigits: 0, maximumFractionDigits: digits });
}

// "2025-04" -> "Apr'25"; FY labels ("2025-26") pass through.
function periodLabel(p, isMonth) {
  return isMonth ? `${MON[Number(p.slice(5, 7)) - 1]}'${p.slice(2, 4)}` : p;
}

const C = {
  headerBg: '#1a73e8', yearHeaderBg: '#188038',
  bestBg: '#fffbeb', bestText: '#92400e',
  yearBestBg: '#d1fae5', yearBestText: '#065f46',
  otherText: '#3c4043', periodText: '#80868b',
  border: '#e8eaed', stickyColBg: '#f8f9fa',
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

function Cell({ item, unit, isMonth, top, leftBorder }) {
  const bg = top ? (isMonth ? C.bestBg : C.yearBestBg) : undefined;
  const color = top ? (isMonth ? C.bestText : C.yearBestText) : C.otherText;
  return (
    <td style={{
      padding: '6px 6px', textAlign: 'center', borderBottom: `1px solid ${C.border}`,
      borderLeft: leftBorder || `1px solid ${C.border}`, background: bg,
    }}>
      {item ? (
        <>
          <div style={{ fontSize: '9.5pt', fontWeight: top ? 800 : 600, color }}>{fmt(item.value, unit)}</div>
          <div style={{ fontSize: '7.5pt', fontStyle: 'italic', color: top ? color : C.periodText }}>{periodLabel(item.period, isMonth)}</div>
        </>
      ) : <span style={{ color: '#c3c2b7', fontSize: '9pt' }}>—</span>}
    </td>
  );
}

export default function TechnoBestPeriodsPage() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [plant, setPlant] = useState('BSP');

  useEffect(() => {
    fetch(`${API_BASE}/api/techno-best-periods`)
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
  const th = (bg, top) => ({
    position: 'sticky', top, zIndex: 2, background: bg, color: '#fff',
    padding: '7px 8px', fontSize: '9.5pt', fontWeight: 700, textAlign: 'center', minWidth: 90,
    borderLeft: '1px solid rgba(255,255,255,0.25)',
  });
  const stickyItemCell = {
    position: 'sticky', left: 0, zIndex: 1, background: C.stickyColBg,
    padding: '7px 14px', fontSize: '9.5pt', fontWeight: 600, color: '#202124',
    borderRight: '2px solid #dadce0', borderBottom: `1px solid ${C.border}`, whiteSpace: 'nowrap',
  };
  const groupDivider = '2px solid #dadce0';

  return (
    <ReportPage
      maxWidth={1300}
      title={<>Best Techno Month &amp; Year</>}
      description={<>The three best months ever and the three best financial years for every Major 12 techno-economic parameter (as on the Major TEPs page) and the BF-wise Iron Making parameters. A year&apos;s figure is its <strong>March cumulative</strong> (Apr–Mar), so the running financial year is not ranked until March is in. “Best” is the <strong>lowest</strong> figure for consumption rates (coke, fuel, coal to HM, hot metal, TMI, slag, energy) and the <strong>highest</strong> for CDI, nut coke, burden sinter / pellet, productivity, scrap, hot blast temperature and O₂ enrichment. SAIL figures count from Apr&apos;21, when all five plants&apos; techno data begins.</>}
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
        <div style={{ overflow: 'auto', maxHeight: '72vh', border: '1px solid #dadce0', borderRadius: 8 }}>
          <table style={{ borderCollapse: 'collapse', minWidth: 900, width: '100%' }}>
            <thead>
              <tr>
                <th rowSpan={2} style={{ ...th(C.headerBg, 0), left: 0, zIndex: 3, textAlign: 'left', minWidth: 270, padding: '9px 14px', borderRight: '2px solid rgba(255,255,255,0.4)' }}>Parameter</th>
                <th colSpan={3} style={th(C.headerBg, 0)}>Best Months</th>
                <th colSpan={3} style={{ ...th(C.yearHeaderBg, 0), borderLeft: groupDivider }}>Best Years (March cumulative)</th>
              </tr>
              <tr>
                {RANKS.map((r) => <th key={`m${r}`} style={th(C.headerBg, 33)}>{r}</th>)}
                {RANKS.map((r, i) => <th key={`y${r}`} style={{ ...th(C.yearHeaderBg, 33), ...(i === 0 ? { borderLeft: groupDivider } : {}) }}>{r}</th>)}
              </tr>
            </thead>
            <tbody>
              {sections.map((sec) => (
                <React.Fragment key={sec.title}>
                  <tr>
                    <td colSpan={7} style={{
                      position: 'sticky', left: 0, padding: '7px 14px', background: C.sectionBg,
                      color: C.sectionText, fontWeight: 800, fontSize: '9.5pt', letterSpacing: '.03em',
                      borderBottom: `1px solid ${C.border}`,
                    }}>
                      {sec.title}
                    </td>
                  </tr>
                  {sec.rows.length === 0 && (
                    <tr><td colSpan={7} style={{ padding: '18px', textAlign: 'center', color: '#9aa0a6' }}>No data for {plant}.</td></tr>
                  )}
                  {sec.rows.map((row, ri) => (
                    <tr key={row.label} style={{ background: ri % 2 === 0 ? '#ffffff' : '#fbfbfa' }}>
                      <td style={{ ...stickyItemCell, background: ri % 2 === 0 ? C.stickyColBg : '#f1f2f3' }}>
                        {row.label}
                        <span style={{ marginLeft: 6, fontSize: '8pt', fontWeight: 500, color: '#80868b' }}>{row.unit}</span>
                        <Direction better={row.better} />
                      </td>
                      {RANKS.map((r, i) => <Cell key={`m${r}`} item={row.months[i]} unit={row.unit} isMonth top={i === 0} />)}
                      {RANKS.map((r, i) => <Cell key={`y${r}`} item={row.years[i]} unit={row.unit} top={i === 0} leftBorder={i === 0 ? groupDivider : undefined} />)}
                    </tr>
                  ))}
                </React.Fragment>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </ReportPage>
  );
}
