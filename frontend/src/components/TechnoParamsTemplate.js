'use client';

// ── style tokens ──────────────────────────────────────────────────────────────
const BLACK  = '1px solid #000';
const NONE   = 0;

// Base cell — vertical dividers only, no horizontal lines inside a parameter block
const CELL = {
  padding: '1.5px 4px', lineHeight: 1.2,
  fontSize: 'var(--report-font-size)',
  borderLeft: BLACK, borderRight: BLACK,
  borderTop: NONE, borderBottom: NONE,
};
const NUM = { ...CELL, textAlign: 'right' };
const LBL = { ...CELL, textAlign: 'left' };

// Header — no background, black border
const TH = {
  color: '#000', padding: '2px 3px',
  textAlign: 'center', verticalAlign: 'middle',
  border: BLACK, fontSize: 'var(--report-font-size)', lineHeight: 1.2, fontWeight: 600,
};
const TH_HIST = { ...TH };
const TH_TGT  = { ...TH };
const TH_CUM  = { ...TH };

// SAIL row — bold + top border to form a box (bottom comes from isLast blockBorder)
const SAIL = { fontWeight: 700, borderTop: BLACK };

export default function TechnoParamsTemplate({ data }) {
  if (!data) return null;
  const {
    title, subtitle = '', sections = [],
    fy3_label = '', fy2_label = '', fy1_label = '', target_label = '',
    month_labels = [], cply_label = '', cum_label = '', cum_cply_label = '',
  } = data;

  const nMonths = month_labels.length;
  const dataCols = 3 + nMonths + 3;
  const dataColWidth = `${72 / dataCols}%`;

  return (
    <div style={{ padding: '6px', fontFamily: "'Arial Narrow', Arial, sans-serif" }}>
      <div style={{ textAlign: 'center', fontWeight: 700, fontSize: '0.88rem' }}>{title}</div>
      {subtitle && (
        <div style={{ textAlign: 'center', fontWeight: 600, fontSize: '0.76rem', marginBottom: 4 }}>
          {subtitle}
        </div>
      )}

      <table style={{ width: '100%', borderCollapse: 'collapse', border: BLACK,
                      tableLayout: 'fixed', fontSize: 'var(--report-font-size)', marginTop: 4 }}>
        <colgroup>
          <col style={{ width: '14%' }} />
          <col style={{ width: '14%' }} />
          {Array.from({ length: dataCols }).map((_, i) => (
            <col key={i} style={{ width: dataColWidth }} />
          ))}
        </colgroup>
        <thead>
          <tr>
            <th rowSpan={2} style={{ ...TH, textAlign: 'left' }}>Parameters</th>
            <th rowSpan={2} style={TH}>Plants</th>
            <th colSpan={3} style={TH_HIST}>Actual</th>
            <th rowSpan={2} style={TH_TGT}>{target_label}</th>
            <th colSpan={nMonths} style={TH}>Actual</th>
            <th rowSpan={2} style={TH}>{cply_label}<br/>Actual</th>
            <th colSpan={2} style={TH_CUM}>Actual</th>
          </tr>
          <tr>
            <th style={TH_HIST}>{fy3_label}</th>
            <th style={TH_HIST}>{fy2_label}</th>
            <th style={TH_HIST}>{fy1_label}</th>
            {month_labels.map((m, i) => <th key={i} style={TH}>{m}</th>)}
            <th style={TH_CUM}>{cum_label}</th>
            <th style={TH_CUM}>{cum_cply_label}</th>
          </tr>
        </thead>
        <tbody>
          {sections.map((sec, si) =>
            sec.rows.map((row, ri) => {
              const sail     = row.label === 'SAIL';
              const isFirst  = ri === 0;
              const isLast   = ri === sec.rows.length - 1;
              // outer black border per parameter block — top on first row, bottom on last
              const topBorder    = isFirst ? { borderTop: BLACK }    : {};
              const bottomBorder = isLast  ? { borderBottom: BLACK } : {};
              const blockBorder  = { ...topBorder, ...bottomBorder };
              const sailStyle    = sail ? SAIL : {};

              return (
                <tr key={`${si}-${ri}`}>
                  {isFirst && (
                    <td rowSpan={sec.rows.length}
                        style={{ ...LBL, fontWeight: 700, verticalAlign: 'top',
                                 borderTop: BLACK, borderBottom: BLACK }}>
                      {sec.label}{sec.rows[0]?.unit ? ` (${sec.rows[0].unit})` : ''}
                    </td>
                  )}
                  <td style={{ ...LBL, ...blockBorder, ...sailStyle }}>{row.label}</td>
                  <td style={{ ...NUM, ...blockBorder, ...sailStyle }}>{row.fy3}</td>
                  <td style={{ ...NUM, ...blockBorder, ...sailStyle }}>{row.fy2}</td>
                  <td style={{ ...NUM, ...blockBorder, ...sailStyle }}>{row.fy1}</td>
                  <td style={{ ...NUM, ...blockBorder, ...sailStyle }}>{row.target}</td>
                  {row.months.map((v, mi) => (
                    <td key={mi} style={{ ...NUM, ...blockBorder, ...sailStyle }}>{v}</td>
                  ))}
                  <td style={{ ...NUM, ...blockBorder, ...sailStyle }}>{row.cply}</td>
                  <td style={{ ...NUM, ...blockBorder, ...sailStyle }}>{row.cum}</td>
                  <td style={{ ...NUM, ...blockBorder, ...sailStyle }}>{row.cum_cply}</td>
                </tr>
              );
            })
          )}
        </tbody>
      </table>
      <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.6rem',
                    color: '#475569', marginTop: 3 }}>
        <span>figures are provisional</span>
        <span>for internal circulation only</span>
      </div>
    </div>
  );
}
