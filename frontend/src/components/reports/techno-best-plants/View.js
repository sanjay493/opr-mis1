'use client';

import React, { useState, useEffect } from 'react';
import { ReportPage } from '../ReportUI';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || '';

const MON = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
const RANKS = ['Best', '2nd', '3rd'];
const MODES = [
  { id: 'months', label: 'Best Month', bg: '#1a73e8' },
  { id: 'years', label: 'Best Year (March cumulative)', bg: '#188038' },
];

function fmt(v, unit) {
  if (v == null) return '—';
  const digits = unit === 't/thm' ? 3 : (unit === 't/m³/day' || unit === 'Gcal/tcs') ? 2 : 1;
  return Number(v).toLocaleString('en-IN', { minimumFractionDigits: 0, maximumFractionDigits: digits });
}

// "2025-04" -> "Apr'25"
function monthLabel(p) {
  return `${MON[Number(p.slice(5, 7)) - 1]}'${p.slice(2, 4)}`;
}

const C = {
  headerBg: '#1a73e8', bestBg: '#d1fae5', bestText: '#065f46',
  otherText: '#3c4043', periodText: '#80868b',
  border: '#e8eaed', stickyColBg: '#f8f9fa',
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

export default function TechnoBestPlantsPage() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    fetch(`${API_BASE}/api/techno-best-plants`)
      .then((r) => { if (!r.ok) throw new Error(r.statusText); return r.json(); })
      .then((d) => { setData(d); setLoading(false); })
      .catch((e) => { setError(e.message); setLoading(false); });
  }, []);

  const rows = data?.rows || [];
  // Parameter index of each row, for row banding: a BF parameter's two rows share one band.
  const paramIdx = [];
  rows.forEach((r, i) => paramIdx.push(i === 0 ? 0 : paramIdx[i - 1] + (rows[i - 1].label !== r.label ? 1 : 0)));

  const th = {
    position: 'sticky', top: 0, zIndex: 2, background: C.headerBg, color: '#fff',
    padding: '8px 8px', fontSize: '9.5pt', fontWeight: 700, textAlign: 'center', minWidth: 110,
    borderLeft: '1px solid rgba(255,255,255,0.25)',
  };
  const groupDivider = '2px solid #dadce0';
  const td = { padding: '6px 8px', borderBottom: `1px solid ${C.border}`, borderLeft: `1px solid ${C.border}` };

  return (
    <ReportPage
      maxWidth={1200}
      title={<>Best Techno Plant</>}
      description={<>For every techno-economic parameter, the three best plants (SMS shops for the steel-making parameters), each with its own best figure. Blast-furnace parameters have two rows: the best <strong>furnaces</strong> across SAIL (plant + BF) and the best <strong>BF shops</strong> (plant total; ISP&apos;s single BF-5 counts as its shop). A year&apos;s figure is its <strong>March cumulative</strong> (Apr–Mar). “Best” is the <strong>lowest</strong> figure for consumption rates and the <strong>highest</strong> for CDI, nut coke, burden sinter / pellet, productivity, scrap, hot blast temperature and O₂ enrichment.</>}
    >
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
          <table style={{ borderCollapse: 'collapse', minWidth: 1100, width: '100%' }}>
            <thead>
              <tr>
                <th rowSpan={2} style={{ ...th, left: 0, zIndex: 3, textAlign: 'left', minWidth: 250, padding: '9px 14px' }}>Parameter</th>
                <th rowSpan={2} style={{ ...th, minWidth: 70 }}>Level</th>
                {MODES.map((m) => (
                  <th key={m.id} colSpan={3} style={{ ...th, background: m.bg, borderLeft: groupDivider }}>{m.label}</th>
                ))}
              </tr>
              <tr>
                {MODES.map((m) => RANKS.map((r, i) => (
                  <th key={m.id + r} style={{ ...th, top: 33, background: m.bg, ...(i === 0 ? { borderLeft: groupDivider } : {}) }}>{r}</th>
                )))}
              </tr>
            </thead>
            <tbody>
              {rows.map((row, ri) => {
                // A BF parameter's Furnace row is followed by its BF Shop row: one Parameter cell spans both.
                const first = ri === 0 || rows[ri - 1].label !== row.label;
                const span = first && rows[ri + 1]?.label === row.label ? 2 : 1;
                const even = paramIdx[ri] % 2 === 0;
                return (
                  <tr key={`${row.label}|${row.level}`} style={{ background: even ? '#ffffff' : '#fbfbfa' }}>
                    {first && (
                      <td rowSpan={span} style={{
                        position: 'sticky', left: 0, zIndex: 1, background: even ? C.stickyColBg : '#f1f2f3',
                        padding: '7px 14px', fontSize: '9.5pt', fontWeight: 600, color: '#202124',
                        borderRight: '2px solid #dadce0', borderBottom: `1px solid ${C.border}`, whiteSpace: 'nowrap',
                      }}>
                        {row.label}
                        <span style={{ marginLeft: 6, fontSize: '8pt', fontWeight: 500, color: '#80868b' }}>{row.unit}</span>
                        <Direction better={row.better} />
                      </td>
                    )}
                    <td style={{ ...td, textAlign: 'center', fontSize: '8.5pt', color: '#5f6368', fontWeight: 600 }}>{row.level}</td>
                    {MODES.map(({ id: mode }) => RANKS.map((r, i) => {
                      const it = row[mode][i];
                      const top = i === 0 && it;
                      return (
                        <td key={mode + r} style={{
                          ...td, textAlign: 'center', background: top ? C.bestBg : undefined,
                          ...(i === 0 ? { borderLeft: groupDivider } : {}),
                        }}>
                          {it ? (
                            <>
                              <div style={{ fontSize: '9pt', fontWeight: 700, color: top ? C.bestText : '#202124' }}>{it.name}</div>
                              <div style={{ fontSize: '9.5pt', fontWeight: top ? 800 : 600, color: top ? C.bestText : C.otherText }}>{fmt(it.value, row.unit)}</div>
                              <div style={{ fontSize: '7.5pt', fontStyle: 'italic', color: top ? C.bestText : C.periodText }}>{mode === 'months' ? monthLabel(it.period) : it.period}</div>
                            </>
                          ) : <span style={{ color: '#c3c2b7', fontSize: '9pt' }}>—</span>}
                        </td>
                      );
                    }))}
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </ReportPage>
  );
}
