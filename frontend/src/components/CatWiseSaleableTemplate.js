'use client';

const ROW_STYLES = {
  data:         { backgroundColor: '#f8fafc' },
  'section-data': { backgroundColor: '#eff6ff', fontWeight: 600 },
  'section-hdr':  { backgroundColor: '#e2e8f0', fontWeight: 700 },
  subtotal:     { backgroundColor: '#fef9c3', fontWeight: 700 },
  pct:          { backgroundColor: '#f1f5f9', fontStyle: 'italic', fontSize: '0.72rem' },
  total:        { backgroundColor: '#dcfce7', fontWeight: 700 },
};

const CELL = { padding: '1.5px 4px', border: '1px solid #cbd5e1', lineHeight: 1.2 };
const NUM = { ...CELL, textAlign: 'right' };
const LBL = { ...CELL, textAlign: 'left' };

function Row({ row }) {
  if (row.type === 'separator') {
    return <tr style={{ height: 3 }}><td colSpan={7} style={{ border: 'none', padding: 0 }} /></tr>;
  }
  if (row.type === 'section-hdr') {
    return (
      <tr style={ROW_STYLES['section-hdr']}>
        <td colSpan={7} style={{ ...LBL, backgroundColor: '#e2e8f0', fontWeight: 700 }}>{row.label}</td>
      </tr>
    );
  }
  const style = ROW_STYLES[row.type] || {};
  return (
    <tr style={style}>
      <td style={{ ...LBL, ...style }}>{row.label}</td>
      {[row.ann_plan, row.m_plan, row.m_act, row.m_pct, row.cply_act, row.m_growth].map((v, i) => (
        <td key={i} style={{ ...NUM, ...style }}>{v}</td>
      ))}
    </tr>
  );
}

function PlantTable({ section, monthLabel, cplyLabel }) {
  const TH = ({ children, rowSpan, colSpan, left }) => (
    <th rowSpan={rowSpan} colSpan={colSpan}
      style={{ backgroundColor: '#1e3a5f', color: '#fff', padding: '2px 3px',
               textAlign: left ? 'left' : 'center', verticalAlign: 'middle',
               border: '1px solid #334155', fontSize: '0.72rem', lineHeight: 1.2, fontWeight: 600 }}>
      {children}
    </th>
  );
  return (
    <div style={{ marginBottom: 8 }}>
      <div style={{ fontWeight: 700, fontSize: '0.9rem', textDecoration: 'underline', marginBottom: 3 }}>
        {section.label}
      </div>
      <table style={{ width: '100%', borderCollapse: 'collapse', border: '2px solid #1e293b',
                      tableLayout: 'fixed', fontSize: '0.76rem' }}>
        <colgroup>
          <col style={{ width: '33%' }} />
          {[...Array(6)].map((_, i) => <col key={i} style={{ width: '11.2%' }} />)}
        </colgroup>
        <thead>
          <tr>
            <TH rowSpan={2} left>CATEGORY</TH>
            <TH rowSpan={2}>2026-27<br/>Plan</TH>
            <TH colSpan={3}>{monthLabel}</TH>
            <TH rowSpan={2}>{cplyLabel}<br/>Actual</TH>
            <TH rowSpan={2}>% Gr.<br/>over<br/>{cplyLabel}</TH>
          </tr>
          <tr>
            <TH>Plan</TH><TH>Actual</TH><TH>% Ful</TH>
          </tr>
        </thead>
        <tbody>
          {section.rows.map((row, i) => <Row key={i} row={row} />)}
        </tbody>
      </table>
    </div>
  );
}

export default function CatWiseSaleableTemplate({ data }) {
  const monthLabel = data?.month_label || '';
  const cplyLabel  = data?.cply_label  || '';
  const sections   = data?.sections    || [];

  return (
    <div style={{ padding: '8px 8px 0', fontFamily: 'Arial, sans-serif' }}>
      {sections.map((section, i) => (
        <PlantTable key={i} section={section} monthLabel={monthLabel} cplyLabel={cplyLabel} />
      ))}
    </div>
  );
}
