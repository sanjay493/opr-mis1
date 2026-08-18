'use client';

import React from 'react';

// Reproduces the monthly PIB (Ministry of Steel) "Indian Steel Sector
// Performance" release across 4 pages (see main.py's STEEL_SECTOR_PAGES /
// page_steel_sector_performance.py). `data.section` selects which slice of
// the archived content this physical page shows; `data.tables`/
// `data.text_sections` are reproduced verbatim (as extracted), except
// `data.production_overview_1a` — Table 1a's rows augmented with SAIL's own
// Crude Steel/Hot Metal/Finished Steel actuals + % share of India, computed
// server-side (see page_steel_sector_performance.py).
const BORDER = '#334155';
const TITLE_COLOR = '#1e3a5f';

const wrap = { fontFamily: 'inherit' };
const pageTitle = {
  textAlign: 'center', fontWeight: 700, fontSize: '14pt', color: TITLE_COLOR, marginBottom: 2,
};
const pageSubtitle = {
  textAlign: 'center', fontSize: '10pt', color: '#64748b', marginBottom: 10,
};
const sectionHeading = {
  fontWeight: 700, fontSize: '12pt', color: TITLE_COLOR, margin: '10px 0 4px',
  borderBottom: `1px solid ${BORDER}`, paddingBottom: 2,
};
const table = { width: '100%', borderCollapse: 'collapse', marginBottom: 6, fontSize: '11pt' };
const th = { border: `1px solid ${BORDER}`, padding: '3px 5px', background: '#e2e8f0', fontWeight: 700, textAlign: 'center' };
const td = { border: `1px solid ${BORDER}`, padding: '3px 5px', textAlign: 'right' };
const tdLabel = { ...td, textAlign: 'left' };
const note = { fontSize: '10.5pt', fontStyle: 'italic', color: '#475569', marginTop: 2 };

function fmtCell(v) {
  return v === null || v === undefined || v === '' ? '—' : v;
}

function GenericTable({ tableData }) {
  if (!tableData) return null;
  const { heading, headers = [], rows = [] } = tableData;
  return (
    <div>
      {heading && <div style={{ fontWeight: 700, fontSize: '11pt', margin: '6px 0 3px' }}>{heading}</div>}
      <table style={table}>
        <thead>
          <tr>{headers.map((h, i) => <th key={i} style={th}>{h}</th>)}</tr>
        </thead>
        <tbody>
          {rows.map((row, ri) => (
            <tr key={ri}>
              {row.map((cell, ci) => (
                <td key={ci} style={ci === 0 ? tdLabel : td}>{fmtCell(cell)}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

const shareBracket = { display: 'block', fontSize: '10.5pt', color: '#1d4ed8', fontWeight: 400 };
const sailRowStyle = { fontStyle: 'italic', background: '#f8fafc' };

function ValueCell({ value, share }) {
  return (
    <td style={td}>
      {fmtCell(value)}
      {share !== null && share !== undefined && <span style={shareBracket}>({share}%)</span>}
    </td>
  );
}

function ProductionOverviewTable({ headers, groups }) {
  if (!groups || !groups.length) return null;
  // headers come verbatim from the source PDF (e.g. "Jul 2026", "Apr-Jul
  // 2026") — real month labels are friendlier here than the generic
  // report_month/cply_month/... key names used internally.
  const colHeaders = headers && headers.length === 7
    ? headers
    : ['Production', 'Report Month', 'CPLY Month', 'YoY %', 'Apr-Report Month', 'CPLY Apr-Report Month', 'CPLY %'];
  return (
    <table style={table}>
      <thead>
        <tr>
          <th style={th}>{colHeaders[0]}</th>
          <th style={th} />
          {colHeaders.slice(1).map((h, i) => <th key={i} style={th}>{h}</th>)}
        </tr>
      </thead>
      <tbody>
        {groups.map((g, gi) => (
          <React.Fragment key={gi}>
            <tr>
              <td style={{ ...tdLabel, fontWeight: 700 }} rowSpan={g.sail ? 2 : 1}>{g.item}</td>
              <td style={{ ...tdLabel, fontWeight: 600 }}>India</td>
              <td style={td}>{fmtCell(g.india.report_month)}</td>
              <td style={td}>{fmtCell(g.india.cply_month)}</td>
              <td style={td}>{fmtCell(g.india.yoy_pct)}</td>
              <td style={td}>{fmtCell(g.india.apr_report_month)}</td>
              <td style={td}>{fmtCell(g.india.cply_apr_report_month)}</td>
              <td style={td}>{fmtCell(g.india.cply_pct)}</td>
            </tr>
            {g.sail && (
              <tr style={sailRowStyle}>
                <td style={{ ...tdLabel, fontStyle: 'italic' }}>SAIL</td>
                <ValueCell value={g.sail.report_month} share={g.share?.report_month} />
                <ValueCell value={g.sail.cply_month} share={g.share?.cply_month} />
                <td style={td}>{fmtCell(g.sail.yoy_pct)}</td>
                <ValueCell value={g.sail.apr_report_month} share={g.share?.apr_report_month} />
                <ValueCell value={g.sail.cply_apr_report_month} share={g.share?.cply_apr_report_month} />
                <td style={td}>{fmtCell(g.sail.cply_pct)}</td>
              </tr>
            )}
          </React.Fragment>
        ))}
      </tbody>
    </table>
  );
}

function TextSection({ section }) {
  if (!section) return null;
  const { heading, paragraphs = [] } = section;
  return (
    <div>
      {heading && <div style={sectionHeading}>{heading}</div>}
      {paragraphs.map((p, i) => (
        <p key={i} style={{ fontSize: '11pt', lineHeight: 1.4, margin: '0 0 6px', textAlign: 'justify' }}>{p}</p>
      ))}
    </div>
  );
}

function Header({ data }) {
  return (
    <>
      <div style={pageTitle}>{data.title}</div>
      <div style={pageSubtitle}>
        {data.posted_on ? `Posted On: ${data.posted_on}` : ''}
        {data.data_month && data.data_month !== data.report_month
          ? ` (latest available release: ${data.data_month})` : ''}
      </div>
    </>
  );
}

export default function SteelSectorPerformanceTemplate({ data }) {
  if (!data || !data.available) {
    return (
      <div style={wrap}>
        <Header data={data || {}} />
        <div style={{ padding: 20, textAlign: 'center', color: '#64748b', fontSize: '9pt' }}>
          No "Indian Steel Sector Performance" release has been uploaded yet for this month.
        </div>
      </div>
    );
  }

  const { section, tables = {}, text_sections = {}, production_overview_1a = [], footer_note } = data;

  if (section === 'demand_trade') {
    return (
      <div style={wrap}>
        <Header data={data} />
        <GenericTable tableData={tables['2']} />
        <div style={sectionHeading}>3. Trade Dynamics</div>
        <GenericTable tableData={tables['3a']} />
      </div>
    );
  }

  if (section === 'raw_materials_indices') {
    return (
      <div style={wrap}>
        <Header data={data} />
        <div style={sectionHeading}>4. Raw Materials</div>
        <GenericTable tableData={tables['4a']} />
        <GenericTable tableData={tables['5']} />
      </div>
    );
  }

  if (section === 'policy_green') {
    return (
      <div style={wrap}>
        <Header data={data} />
        <TextSection section={text_sections['6']} />
        <TextSection section={text_sections['7']} />
        <TextSection section={text_sections['8']} />
        {footer_note && <div style={note}>{footer_note}</div>}
      </div>
    );
  }

  // default / 'prod_prices': Table 1a (with SAIL rows + share %), 1b, 1c
  return (
    <div style={wrap}>
      <Header data={data} />
      <div style={sectionHeading}>1. Steel Production &amp; Prices</div>
      <div style={{ fontWeight: 700, fontSize: '11pt', margin: '6px 0 3px' }}>
        1a. Production Overview (in Mt) — with SAIL &amp; Share of India
      </div>
      <ProductionOverviewTable headers={tables['1a']?.headers} groups={production_overview_1a} />
      <div style={note}>Bracketed value under each SAIL figure: SAIL's % share of India.</div>
      <GenericTable tableData={tables['1b']} />
      <GenericTable tableData={tables['1c']} />
    </div>
  );
}
