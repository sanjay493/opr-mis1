'use client';

import React from 'react';
import ParlAnnexure, { C, devTitle, fmt } from '../parl-annexures/ParlAnnexure';

// Annexure-III "Major techno economic parameters" (the workbook's
// "techhistoryfinal" sheet): BF productivity, coke rate and energy
// consumption by plant for the past FYs, the selected period (Apr..month
// cumulative), its CPLY and % improvement.

const NARROW = "'Arial Narrow', Arial, sans-serif";
const TH = { border: C.line, padding: '3px 8px', fontFamily: NARROW, fontSize: '10.5pt', fontWeight: 700, textAlign: 'center', whiteSpace: 'nowrap' };
const TD = { border: C.line, padding: '4px 8px', fontFamily: NARROW, fontSize: '10.5pt', textAlign: 'center', whiteSpace: 'nowrap' };

function Table({ data, devs }) {
  const L = data.labels;
  const fys = data.fys;
  const cols = [...fys, 'cy', 'cply'];
  return (
    <div style={{ maxWidth: 1000 }}>
      <div style={{ textAlign: 'right', fontFamily: NARROW, fontSize: '12pt', fontWeight: 700 }}>{L.annexure}</div>
      <div style={{ fontSize: '14pt', fontWeight: 700, margin: '6px 0 6px' }}>{L.title}</div>
      {data.sections.map((sec) => (
        <div key={sec.key} style={{ marginTop: 14 }}>
          <div style={{ fontFamily: NARROW, fontSize: '11pt', fontWeight: 700 }}>{sec.label}</div>
          <div style={{ fontFamily: NARROW, fontSize: '10.5pt', fontWeight: 700, marginBottom: 3 }}>{sec.unit}</div>
          <table style={{ borderCollapse: 'collapse', width: '100%' }}>
            <thead>
              <tr>
                <th rowSpan={2} style={TH} />
                {fys.map((f) => <th key={f} rowSpan={2} style={TH}>{f}</th>)}
                <th colSpan={2} style={TH}>{L.span}</th>
                <th style={TH}>% imp. Over</th>
              </tr>
              <tr>{[L.fy, L.cply_fy, 'CPLY'].map((h) => <th key={h} style={TH}>{h}</th>)}</tr>
            </thead>
            <tbody>
              {sec.rows.map((r) => (
                <tr key={r.plant} style={{ fontWeight: r.total ? 700 : 400 }}>
                  <td style={{ ...TD, fontWeight: 700, textAlign: 'left' }}>{r.plant}</td>
                  {[...r.fys, r.cy, r.cply].map((v, i) => {
                    const hit = devs.get(`${r.plant}|${sec.key}|${cols[i]}`);
                    return (
                      <td key={i} title={hit ? devTitle(hit) : undefined} style={{ ...TD, ...(hit ? { background: C.dev } : {}) }}>
                        {v == null && i < fys.length ? '-' : fmt(v, sec.decimals)}
                      </td>
                    );
                  })}
                  <td style={TD}>{fmt(r.imp, 0)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ))}
    </div>
  );
}

export default function ParlTechnoHistoryView() {
  return (
    <ParlAnnexure
      slug="techno-history"
      fileBase="Annexure-III_Techno_History"
      defaultYears={6}
      Table={Table}
      title={<>Annexure-III: Major Techno-Economic Parameters</>}
      description={<>BF productivity, coke rate and energy consumption. Past FYs from the hard-coded history (a later FY from the DB&apos;s March cumulative); the period and its CPLY are the DB&apos;s Apr-to-month cumulative (SAIL: stored figure, else HM / Crude Steel weighted). % improvement: higher is better for productivity, lower for coke rate and energy.</>}
    />
  );
}
