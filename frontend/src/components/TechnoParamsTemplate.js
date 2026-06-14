'use client';

// ── style tokens ──────────────────────────────────────────────────────────────
const CELL = { padding: '1.5px 4px', border: '1px solid #94a3b8', lineHeight: 1.2, fontSize: 'var(--report-font-size)' };
const NUM  = { ...CELL, textAlign: 'right' };
const LBL  = { ...CELL, textAlign: 'left' };
const TH   = {
  backgroundColor: '#1e3a5f', color: '#fff', padding: '2px 3px',
  textAlign: 'center', verticalAlign: 'middle',
  border: '1px solid #334155', fontSize: 'var(--report-font-size)', lineHeight: 1.2, fontWeight: 600,
};
const TH_HIST = { ...TH, backgroundColor: '#475569' };   // past FY actuals
const TH_TGT  = { ...TH, backgroundColor: '#7c2d12' };   // target
const TH_CUM  = { ...TH, backgroundColor: '#2d5016' };   // cumulative

export default function TechnoParamsTemplate({ data }) {
  if (!data) return null;
  const {
    title, subtitle = '', sections = [],
    fy2_label = '', fy1_label = '', target_label = '',
    month_labels = [], cply_label = '', cum_label = '', cum_cply_label = '',
  } = data;

  const nMonths = month_labels.length;
  const dataCols = 3 + nMonths + 3;
  const dataColWidth = `${64 / dataCols}%`;

  return (
    <div style={{ padding: '6px', fontFamily: 'Arial, sans-serif' }}>
      <div style={{ textAlign: 'center', fontWeight: 700, fontSize: '0.88rem' }}>{title}</div>
      {subtitle && (
        <div style={{ textAlign: 'center', fontWeight: 600, fontSize: '0.76rem', marginBottom: 4 }}>
          {subtitle}
        </div>
      )}

      <table style={{ width: '100%', borderCollapse: 'collapse', border: '2px solid #1e293b',
                      tableLayout: 'fixed', fontSize: 'var(--report-font-size)', marginTop: 4 }}>
        <colgroup>
          <col style={{ width: '14%' }} />
          <col style={{ width: '14%' }} />
          <col style={{ width: '8%' }} />
          {Array.from({ length: dataCols }).map((_, i) => (
            <col key={i} style={{ width: dataColWidth }} />
          ))}
        </colgroup>
        <thead>
          <tr>
            <th rowSpan={2} style={{ ...TH, textAlign: 'left' }}>Shop</th>
            <th rowSpan={2} style={TH}>Parameters</th>
            <th rowSpan={2} style={TH}>Unit</th>
            <th colSpan={2} style={TH_HIST}>Actual</th>
            <th rowSpan={2} style={TH_TGT}>{target_label}</th>
            <th colSpan={nMonths} style={TH}>Actual</th>
            <th rowSpan={2} style={TH}>{cply_label}<br/>Actual</th>
            <th colSpan={2} style={TH_CUM}>Actual</th>
          </tr>
          <tr>
            <th style={TH_HIST}>{fy2_label}</th>
            <th style={TH_HIST}>{fy1_label}</th>
            {month_labels.map((m, i) => <th key={i} style={TH}>{m}</th>)}
            <th style={TH_CUM}>{cum_label}</th>
            <th style={TH_CUM}>{cum_cply_label}</th>
          </tr>
        </thead>
        <tbody>
          {sections.map((sec, si) =>
            sec.rows.map((row, ri) => (
              <tr key={`${si}-${ri}`}
                  style={{ backgroundColor: si % 2 ? '#f8fafc' : '#fff' }}>
                {ri === 0 && (
                  <td rowSpan={sec.rows.length}
                      style={{ ...LBL, fontWeight: 700, verticalAlign: 'top',
                               backgroundColor: '#e2e8f0' }}>
                    {sec.label}
                  </td>
                )}
                <td style={LBL}>{row.label}</td>
                <td style={{ ...CELL, textAlign: 'center' }}>{row.unit}</td>
                <td style={NUM}>{row.fy2}</td>
                <td style={NUM}>{row.fy1}</td>
                <td style={{ ...NUM, backgroundColor: '#fef3ec' }}>{row.target}</td>
                {row.months.map((v, mi) => <td key={mi} style={NUM}>{v}</td>)}
                <td style={NUM}>{row.cply}</td>
                <td style={{ ...NUM, backgroundColor: '#f3faf0' }}>{row.cum}</td>
                <td style={{ ...NUM, backgroundColor: '#f3faf0' }}>{row.cum_cply}</td>
              </tr>
            ))
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
