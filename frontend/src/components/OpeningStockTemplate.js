'use client';

// ── style tokens ──────────────────────────────────────────────────────────────
const CELL = { padding: '1px 4px', border: '1px solid #94a3b8', lineHeight: 1.15, fontSize: 'var(--report-font-size)' };
const NUM  = { ...CELL, textAlign: 'right' };
const LBL  = { ...CELL, textAlign: 'left' };
const TH   = {
  backgroundColor: '#1e3a5f', color: '#fff', padding: '2px 3px',
  textAlign: 'center', verticalAlign: 'middle',
  border: '1px solid #334155', fontSize: 'var(--report-font-size)', lineHeight: 1.2, fontWeight: 600,
};
const SECTION_CELL = {
  ...CELL, textAlign: 'center', verticalAlign: 'middle',
  fontWeight: 700, fontSize: 'var(--report-font-size)', backgroundColor: '#e2e8f0',
  // vertical text like the printed report
  writingMode: 'vertical-rl', transform: 'rotate(180deg)',
  width: '22px', whiteSpace: 'nowrap', padding: '2px 1px',
};

export default function OpeningStockTemplate({ data }) {
  if (!data) return null;
  const { title, unit = "'000T", col_labels = [], var_label = '', sections = [] } = data;
  const nCols = col_labels.length;

  return (
    <div style={{ padding: '6px', fontFamily: 'Arial, sans-serif' }}>
      <div style={{ textAlign: 'center', fontWeight: 700, fontSize: '0.88rem', marginBottom: 4 }}>
        {title}
      </div>
      <div style={{ textAlign: 'right', fontSize: '0.65rem', marginBottom: 3 }}>Unit: {unit}</div>

      <table style={{ width: '100%', borderCollapse: 'collapse', border: '2px solid #1e293b',
                      tableLayout: 'fixed', fontSize: 'var(--report-font-size)' }}>
        <colgroup>
          <col style={{ width: '26px' }} />
          <col style={{ width: '20px' }} />
          <col style={{ width: '13%' }} />
          <col style={{ width: '9%' }} />
          {col_labels.map((_, i) => <col key={i} style={{ width: `${58 / nCols}%` }} />)}
          <col style={{ width: '9%' }} />
        </colgroup>
        <thead>
          <tr>
            <th colSpan={3} style={TH}></th>
            <th style={TH}>PLANT</th>
            {col_labels.map((c, i) => <th key={i} style={TH}>{c}</th>)}
            <th style={TH}>{var_label}</th>
          </tr>
        </thead>
        <tbody>
          {sections.map((sec, si) =>
            sec.rows.map((row, ri) => {
              const bg = row.sail
                ? (row.bold ? '#dcfce7' : '#eff6ff')
                : (row.bold ? '#fef9c3' : (ri % 2 ? '#fff' : '#f8fafc'));
              const fw = row.bold ? 700 : 400;
              return (
                <tr key={`${si}-${ri}`} style={{ backgroundColor: bg, fontWeight: fw }}>
                  {ri === 0 && (
                    <td rowSpan={sec.rows.length} style={SECTION_CELL}>{sec.label}</td>
                  )}
                  {ri === 0 && (
                    <td rowSpan={sec.rows.length}
                        style={{ ...SECTION_CELL }}>
                      {sec.code}
                    </td>
                  )}
                  <td style={{ ...LBL }}>{row.sub}</td>
                  <td style={{ ...LBL, fontWeight: row.plant === 'SAIL' ? 700 : fw }}>{row.plant}</td>
                  {row.values.map((v, vi) => <td key={vi} style={NUM}>{v}</td>)}
                  <td style={{ ...NUM, fontWeight: 600 }}>{row.var}</td>
                </tr>
              );
            })
          )}
        </tbody>
      </table>
      <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.6rem',
                    color: '#475569', marginTop: 3 }}>
        <span>Figures are provisional</span>
        <span>For internal use</span>
      </div>
    </div>
  );
}
