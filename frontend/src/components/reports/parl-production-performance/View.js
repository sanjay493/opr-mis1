'use client';

import React from 'react';
import ParlAnnexure, { C, devTitle, fmt } from '../parl-annexures/ParlAnnexure';

// Annexure-II "Production performance of SAIL plants" (the workbook's
// "hisparlia" sheet): per plant, the past FYs, the FY's annual APP / MoU
// row and the selected period, for Hot Metal, Crude Steel, Saleable Steel.

const FIELDS = ['cap', 'app', 'mou', 'actual', 'ful_app', 'ful_mou', 'gr', 'cu'];

// Same rule as parl_annexures_export.pp_cells: an item with no data stays
// blank; otherwise a missing MoU (and %Ful. against it) shows '-'.
function cells(kind, v) {
  const out = FIELDS.map((f) => v[f]);
  if (out.every((x) => x == null)) return out;
  if (v.mou == null) {
    out[2] = '-';
    if (kind !== 'plan') out[5] = '-';
  }
  return out;
}

const TH = {
  border: C.line, padding: '3px 4px', fontFamily: "'Arial Narrow', Arial, sans-serif", fontSize: '9pt',
  fontWeight: 700, textAlign: 'center', whiteSpace: 'nowrap',
};
const TD = { border: C.line, padding: '2px 5px', fontSize: '9pt', textAlign: 'center', whiteSpace: 'nowrap' };

function Table({ data, devs }) {
  const L = data.labels;
  const items = data.items;
  return (
    <div style={{ fontFamily: 'Arial, sans-serif', minWidth: 1250 }}>
      <div style={{ fontSize: '9pt', fontWeight: 700 }}>{L.org}</div>
      <div style={{ display: 'flex', alignItems: 'flex-start' }}>
        <div style={{ flex: 1, textAlign: 'center' }}>
          <div style={{ fontSize: '13pt', fontWeight: 700 }}>{L.title}</div>
          <div style={{ fontSize: '12pt', fontWeight: 700, margin: '2px 0 4px' }}>{L.subtitle}</div>
        </div>
        <div style={{ textAlign: 'right', fontWeight: 700 }}>{L.annexure}<br /><span style={{ fontSize: '8.5pt', fontWeight: 400 }}>{L.unit}</span></div>
      </div>
      <table style={{ borderCollapse: 'collapse', width: '100%' }}>
        <thead>
          <tr>
            <th rowSpan={3} style={TH}>PLANT</th>
            <th rowSpan={3} style={TH}>YEAR</th>
            {items.map((it) => (
              <th key={it.key} colSpan={8} style={{ ...TH, fontFamily: 'Arial, sans-serif', fontSize: '10pt', background: C.item, borderLeft: C.thick }}>{it.label}</th>
            ))}
          </tr>
          <tr>
            {items.map((it) => (
              <React.Fragment key={it.key}>
                <th rowSpan={2} style={{ ...TH, background: C.cap, borderLeft: C.thick }}>CAP.*</th>
                <th colSpan={2} style={TH}>TARGET</th>
                <th rowSpan={2} style={{ ...TH, background: C.act }}>ACTUAL</th>
                <th colSpan={2} style={TH}>% FUL.</th>
                <th rowSpan={2} style={TH}>% GR.</th>
                <th rowSpan={2} style={TH}>% C.U</th>
              </React.Fragment>
            ))}
          </tr>
          <tr>
            {items.map((it) => ['APP', 'MoU', 'APP', 'MoU'].map((h, i) => <th key={`${it.key}${i}`} style={TH}>{h}</th>))}
          </tr>
        </thead>
        {data.plants.map((blk) => {
          const sail = blk.plant === 'SAIL';
          return (
            <tbody key={blk.plant} style={{ borderTop: C.thick }}>
              {blk.rows.map((row, k) => {
                const col = row.kind === 'fy' ? row.label : row.kind;
                return (
                  <tr key={row.label} style={{ fontWeight: sail ? 700 : 400 }}>
                    {k === 0 && <td rowSpan={blk.rows.length} style={{ ...TD, fontWeight: 700, fontSize: '10.5pt', borderTop: C.thick }}>{blk.plant}</td>}
                    <td style={{ ...TD, fontWeight: 700, ...(k === 0 ? { borderTop: C.thick } : {}) }}
                        title={row.kind !== 'fy' ? 'From the DB' : row.source === 'history' ? 'From the hard-coded history (workbook)' : 'Actual from the DB; Cap. / APP / MoU from the workbook where the DB has none'}>
                      {row.label}{row.kind === 'fy' && row.source !== 'history' ? ' †' : ''}
                    </td>
                    {items.map((it) => {
                      const dev = devs.get(`${blk.plant}|${it.key}|${col}`);
                      return cells(row.kind, row.values[it.key]).map((v, i) => {
                        const measure = { 1: 'APP', 2: 'MoU', 3: 'Actual' }[i];
                        const hit = dev && dev.filter((d) => d.measure === measure);
                        const bg = hit && hit.length ? C.dev : i === 0 ? C.cap : i === 3 ? C.act : undefined;
                        return (
                          <td key={`${it.key}${i}`} title={hit && hit.length ? devTitle(hit) : undefined}
                              style={{ ...TD, background: bg, ...(i === 0 ? { borderLeft: C.thick } : {}), ...(k === 0 ? { borderTop: C.thick } : {}) }}>
                            {fmt(v, 0)}
                          </td>
                        );
                      });
                    })}
                  </tr>
                );
              })}
            </tbody>
          );
        })}
      </table>
      {data.note && <p style={{ fontSize: '8pt', whiteSpace: 'pre-line', margin: '4px 0 0' }}>{data.note}</p>}
      <p style={{ fontSize: '8pt', color: '#5f6368', margin: '2px 0 0' }}>† from the DB (actuals); Cap., APP and MoU from the workbook where the DB has none (before 2026-27).</p>
    </div>
  );
}

export default function ParlProductionPerformanceView() {
  return (
    <ParlAnnexure
      slug="production-performance"
      fileBase="Annexure-II_Production_Performance"
      defaultYears={5}
      Table={Table}
      title={<>Annexure-II: Production Performance of SAIL Plants</>}
      description={<>Past FYs up to 2021-22 from the hard-coded history (Report_format/work/HisParlia_Annexures.xlsx), from 2022-23 from the DB (a year the DB holds only in part stays the workbook&apos;s); the FY&apos;s annual APP / MoU row and the selected period from the DB (MoU &quot;-&quot; when not loaded). The period&apos;s Cap., APP and MoU = annual figure × days in the period ÷ days in the FY.</>}
    />
  );
}
