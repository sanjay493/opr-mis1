'use client';

import React from 'react';

// Mirrors backend/page_templates/rake_detention_{detail,summary,trend}.html
// — see backend/page_rake_detention.py. Heatmap cell colours (vals[].bg)
// are computed server-side.
const C = {
  title: 'rgb(0,0,255)',
  navy: '#060177',
  secondary: '#475569',
  dark: '#334155',
  headerBg: '#ccdcf2',
  freetimeBg: '#fdf0d5',
  detailTotalBg: '#c7d6ec',
  pctBg: '#fed7aa',
  annualBg: '#eae1f5',
  currentFyBg: '#dcfce7',
  plantBg: '#f8fafc',
};

const cell = { border: `0.5pt solid ${C.dark}`, textAlign: 'center', overflow: 'hidden' };
const num = { ...cell, fontVariantNumeric: 'tabular-nums' };

function Title({ title, subtitle, subtitleStyle }) {
  return (
    <>
      <div style={{ textAlign: 'center', fontWeight: 700, fontSize: '11pt', textDecoration: 'underline', color: C.title, marginBottom: 4 }}>{title}</div>
      {subtitle && <div style={subtitleStyle}>{subtitle}</div>}
    </>
  );
}

function Footnote({ size = '8pt', marginTop = '4pt' }) {
  return (
    <div style={{ textAlign: 'right', fontSize: size, fontStyle: 'italic', color: C.secondary, marginTop }}>
      RAIL MOVEMENT CELL, L &amp; I DEPARTMENT,
    </div>
  );
}

export function RakeDetentionDetailTemplate({ data }) {
  const { title = '', subtitle = '', plants = [], month_labels = [] } = data || {};
  const c = { ...cell, padding: '2.6px 2.5px' };
  const th = { ...c, background: C.headerBg, fontWeight: 700 };
  const n = { ...num, padding: '2.6px 2.5px', textAlign: 'right' };
  const commodityCell = { ...c, textAlign: 'left', fontWeight: 600, verticalAlign: 'middle', wordBreak: 'break-word' };
  const wagonCell = { ...c, textAlign: 'left', wordBreak: 'break-word' };
  const table = { borderCollapse: 'collapse', width: '100%', tableLayout: 'fixed', fontSize: '7.8pt', marginBottom: '6pt' };
  const vals = (row) => row.vals.map((v, i) => (
    <td key={i} style={{ ...n, background: v.bg || undefined }}>{v.text}</td>
  ));

  return (
    <div>
      <Title title={title} subtitle={subtitle} subtitleStyle={{ textAlign: 'center', fontSize: '9pt', fontWeight: 600, marginBottom: 3 }} />
      {plants.map((plant) => (
        <div key={plant.plant}>
          <div style={{ fontWeight: 700, fontSize: '13pt', color: C.navy, textAlign: 'center', margin: '2pt 0 6pt' }}>{plant.plant}</div>
          {plant.sections.map((sec) => (
            <div key={sec.section}>
              <div style={{ fontWeight: 700, fontSize: '9.5pt', margin: '5pt 0 2pt' }}>
                {sec.heading}
                {sec.direction && (
                  <span style={{ display: 'inline-block', fontSize: '8pt', fontWeight: 600, color: C.secondary, marginLeft: '8pt' }}>({sec.direction})</span>
                )}
              </div>
              {sec.section === 'OVERALL' ? (
                <table style={table}>
                  <colgroup>
                    <col style={{ width: '15%' }} />
                    {month_labels.map((m) => <col key={m} style={{ width: '7.0833%' }} />)}
                  </colgroup>
                  <thead>
                    <tr><th style={th}>Wagon Type</th>{month_labels.map((m) => <th key={m} style={th}>{m}</th>)}</tr>
                  </thead>
                  <tbody>
                    {sec.rows.map((row, ri) => (
                      <tr key={ri} style={row.is_total ? { fontWeight: 700, background: C.detailTotalBg } : undefined}>
                        <td style={wagonCell}>{row.row_label}</td>
                        {vals(row)}
                      </tr>
                    ))}
                  </tbody>
                </table>
              ) : (
                <table style={table}>
                  <colgroup>
                    <col style={{ width: '14%' }} /><col style={{ width: '11%' }} /><col style={{ width: '6%' }} />
                    {month_labels.map((m) => <col key={m} style={{ width: '5.75%' }} />)}
                  </colgroup>
                  <thead>
                    <tr>
                      <th style={th}>Commodity</th><th style={th}>Wagon Type</th><th style={th}>Freetime</th>
                      {month_labels.map((m) => <th key={m} style={th}>{m}</th>)}
                    </tr>
                  </thead>
                  <tbody>
                    {sec.rows.map((row, ri) => (
                      <tr key={ri} style={row.is_total ? { fontWeight: 700, background: C.detailTotalBg } : undefined}>
                        {row.is_total ? (
                          <td style={commodityCell} colSpan={3}>{row.row_label}</td>
                        ) : (
                          <>
                            {row.commodity_rowspan > 0 && (
                              <td style={commodityCell} rowSpan={row.commodity_rowspan}>{row.commodity || ''}</td>
                            )}
                            <td style={wagonCell}>{row.row_label}</td>
                            <td style={{ ...n, background: C.freetimeBg }}>{row.freetime_hours}</td>
                          </>
                        )}
                        {vals(row)}
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>
          ))}
        </div>
      ))}
      <Footnote size="7.5pt" marginTop="3pt" />
    </div>
  );
}

export function RakeDetentionSummaryTemplate({ data }) {
  const { title = '', subtitle = '', plants = [], rows = [] } = data || {};
  const c = { ...cell, padding: '5pt 4pt' };
  const th = { ...c, fontWeight: 700 };

  return (
    <div>
      <Title title={title} subtitle={subtitle} subtitleStyle={{ textAlign: 'right', fontSize: '9pt', fontStyle: 'italic', color: C.secondary, marginBottom: 6 }} />
      <table style={{ borderCollapse: 'collapse', width: '100%', tableLayout: 'fixed', fontSize: '10pt' }}>
        <colgroup>
          <col style={{ width: '21%' }} />
          {plants.map((p) => <col key={p} />)}
        </colgroup>
        <thead>
          <tr><th style={th}>Period</th>{plants.map((p) => <th key={p} style={th}>{p}</th>)}</tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.code} style={row.is_pct ? { fontStyle: 'italic', background: C.pctBg } : undefined}>
              <td style={{ ...c, textAlign: 'left', fontWeight: 700, color: C.navy, whiteSpace: 'nowrap' }}>{row.label}</td>
              {row.vals.map((v, i) => <td key={i} style={{ ...num, padding: '5pt 4pt' }}>{v}</td>)}
            </tr>
          ))}
        </tbody>
      </table>
      <Footnote marginTop="8pt" />
    </div>
  );
}

export function RakeDetentionTrendTemplate({ data }) {
  const { title = '', subtitle = '', plants = [], month_labels = [] } = data || {};
  const c = { ...cell, padding: '2pt 3pt' };
  const th = { ...c, fontWeight: 700 };
  const span = month_labels.length + 2;

  return (
    <div>
      <Title title={title} subtitle={subtitle} subtitleStyle={{ fontWeight: 600, fontStyle: 'italic', fontSize: '9pt', textAlign: 'right', color: C.secondary, padding: '0 2pt 4pt' }} />
      <table style={{ borderCollapse: 'collapse', width: '100%', tableLayout: 'fixed', fontSize: '8pt', marginBottom: '2pt' }}>
        <colgroup>
          <col style={{ width: '9%' }} />
          {month_labels.map((m) => <col key={m} />)}
          <col style={{ width: '9%' }} />
        </colgroup>
        <thead>
          <tr><th style={th}>Year</th>{month_labels.map((m) => <th key={m} style={th}>{m}</th>)}<th style={th}>Apr-Mar</th></tr>
        </thead>
        <tbody>
          {plants.map((plant) => (
            <React.Fragment key={plant.plant}>
              <tr>
                <td colSpan={span} style={{ ...c, textAlign: 'left', fontWeight: 700, fontSize: '9pt', color: C.navy, background: C.plantBg, padding: '3pt 4pt' }}>
                  {plant.plant}
                </td>
              </tr>
              {plant.fy_rows.map((fy, i) => (
                <tr key={fy.fy} style={i === 0 ? { fontWeight: 700, background: C.currentFyBg } : undefined}>
                  <td style={c}>{fy.fy}</td>
                  {fy.vals.map((v, vi) => <td key={vi} style={{ ...num, padding: '2pt 3pt' }}>{v}</td>)}
                  <td style={{ ...num, padding: '2pt 3pt', background: C.annualBg, fontWeight: 700 }}>{fy.annual}</td>
                </tr>
              ))}
            </React.Fragment>
          ))}
        </tbody>
      </table>
      <Footnote />
    </div>
  );
}
