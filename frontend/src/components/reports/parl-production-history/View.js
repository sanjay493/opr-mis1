'use client';

import React from 'react';
import ParlAnnexure, { C, HARD, devTitle, fmt } from '../parl-annexures/ParlAnnexure';

// "Production" history (the workbook's "ProdHIS" sheet): HM / CS / SS /
// Pig Iron actual by plant for the past FYs, the selected period, its CPLY
// and % growth.

const SERIF = "'Book Antiqua', Palatino, serif";
const TH = { border: C.line, padding: '3px 6px', fontFamily: SERIF, fontSize: '10pt', fontWeight: 700, textAlign: 'center', whiteSpace: 'nowrap' };
const TD = {
  borderLeft: C.line, borderRight: C.line, padding: '2px 8px', fontFamily: "'Arial Narrow', Arial, sans-serif",
  fontSize: '10.5pt', textAlign: 'center', whiteSpace: 'nowrap',
};

function Table({ data, devs }) {
  const L = data.labels;
  const fys = data.fys;
  return (
    <div style={{ maxWidth: 1000 }}>
      <div style={{ fontSize: '10pt', fontWeight: 700 }}>{L.org}</div>
      <div style={{ fontSize: '13pt', fontWeight: 700, margin: '4px 0 8px' }}>{L.company}</div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-end', marginBottom: 3 }}>
        <span style={{ fontFamily: SERIF, fontSize: '13pt', fontWeight: 700 }}>{L.title}</span>
        <span style={{ fontSize: '9pt' }}>{L.unit}</span>
      </div>
      <table style={{ borderCollapse: 'collapse', width: '100%', borderBottom: C.line }}>
        <thead>
          <tr>
            <th rowSpan={3} style={{ ...TH, textAlign: 'left' }}>PLANT/ITEMS</th>
            {fys.map((f) => <th key={f} rowSpan={2} style={TH}>{f}</th>)}
            <th colSpan={2} rowSpan={2} style={TH}>{L.span}</th>
            <th style={{ ...TH, borderBottom: 'none' }}>% growth</th>
          </tr>
          <tr><th style={{ ...TH, borderTop: 'none' }}>over</th></tr>
          <tr>
            {fys.map((f) => <th key={f} style={{ ...TH, fontFamily: 'Arial', fontWeight: 400, fontSize: '9pt' }}>ACTUAL</th>)}
            {[L.fy, L.cply_fy, 'CPLY'].map((h) => <th key={h} style={{ ...TH, fontFamily: 'Arial', fontWeight: 400, fontSize: '9pt' }}>{h}</th>)}
          </tr>
        </thead>
        <tbody>
          {data.items.map((it) => (
            <React.Fragment key={it.key}>
              <tr style={{ borderTop: C.line }}>
                <td style={{ ...TD, fontFamily: SERIF, fontWeight: 700, textAlign: 'left' }}>{it.label}</td>
                {Array.from({ length: fys.length + 3 }, (_, i) => <td key={i} style={TD} />)}
              </tr>
              {it.rows.map((r) => {
                const tot = r.total ? { fontWeight: 700, borderTop: C.line, borderBottom: C.line } : {};
                const cols = [...fys, 'cy', 'cply'];
                return (
                  <tr key={r.plant}>
                    <td style={{ ...TD, ...tot, fontFamily: SERIF, textAlign: 'left' }}>{r.plant === 'SAIL-5PL' ? 'SAIL-5 PL' : r.plant}</td>
                    {[...r.fys, r.cy, r.cply].map((v, i) => {
                      const hit = devs.get(`${r.plant}|${it.key}|${cols[i]}`);
                      return (
                        <td key={i} title={hit ? devTitle(hit) : undefined} style={{ ...TD, ...tot, ...(r.hard?.[i] ? HARD : {}), ...(hit ? { background: C.dev } : {}) }}>
                          {fmt(v, 0)}
                        </td>
                      );
                    })}
                    <td style={{ ...TD, ...tot }}>{fmt(r.gr, 0)}</td>
                  </tr>
                );
              })}
            </React.Fragment>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export default function ParlProductionHistoryView() {
  return (
    <ParlAnnexure
      slug="production-history"
      fileBase="Production_History"
      defaultYears={7}
      Table={Table}
      title={<>Production History (HM / CS / SS / Pig Iron)</>}
      description={<>Past FYs up to 2021-22 from the hard-coded history (Report_format/work/HisParlia_Annexures.xlsx), from 2022-23 from the DB where it holds the whole year (else the workbook&apos;s figure); the selected period and its CPLY from the DB, with % growth.</>}
    />
  );
}
