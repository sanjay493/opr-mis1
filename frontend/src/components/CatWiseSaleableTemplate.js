'use client';

const ROW_STYLES = {
  data:           { backgroundColor: '#f8fafc' },
  'section-data': { backgroundColor: '#eff6ff', fontWeight: 600 },
  'section-hdr':  { backgroundColor: '#e2e8f0', fontWeight: 700 },
  subtotal:       { backgroundColor: '#fef9c3', fontWeight: 700 },
  pct:            { backgroundColor: '#f1f5f9', fontStyle: 'italic', fontSize: 'var(--report-font-size)' },
  total:          { backgroundColor: '#dcfce7', fontWeight: 700 },
};

const CELL = { padding: '1.5px 4px', border: '1px solid #cbd5e1', lineHeight: 1.2 };
const NUM  = { ...CELL, textAlign: 'right' };
const LBL  = { ...CELL, textAlign: 'left' };

function Row({ row }) {
  if (row.type === 'separator') {
    return <tr style={{ height: 3 }}><td colSpan={8} style={{ border: 'none', padding: 0 }} /></tr>;
  }
  if (row.type === 'section-hdr') {
    return (
      <tr style={ROW_STYLES['section-hdr']}>
        <td colSpan={8} style={{ ...LBL, backgroundColor: '#e2e8f0', fontWeight: 700 }}>{row.label}</td>
      </tr>
    );
  }

  const style = ROW_STYLES[row.type] || {};

  let catCell = null;
  if (row.cat_first) {
    catCell = (
      <td rowSpan={row.cat_rowspan}
          style={{ ...CELL, backgroundColor: '#fff', color: '#000',
                   fontWeight: 700, textAlign: 'center', verticalAlign: 'middle',
                   fontSize: 'var(--report-font-size)' }}>
        <div style={{ writingMode: 'vertical-rl', transform: 'rotate(180deg)' }}>
          {row.category}
        </div>
      </td>
    );
  } else if (!row.category) {
    catCell = <td style={{ ...CELL, backgroundColor: '#fff' }} />;
  }
  // rows mid-group (cat set, cat_first false): covered by rowspan — no td

  return (
    <tr style={style}>
      {catCell}
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
      style={{ backgroundColor: '#fff', color: '#000', padding: '2px 3px',
               textAlign: left ? 'left' : 'center', verticalAlign: 'middle',
               border: '1px solid #334155', fontSize: 'var(--report-font-size)', lineHeight: 1.2, fontWeight: 600 }}>
      {children}
    </th>
  );
  return (
    <div style={{ marginBottom: 8 }}>
      <div style={{ fontWeight: 700, fontSize: '0.9rem', textDecoration: 'underline', marginBottom: 3 }}>
        {section.label}
      </div>
      <table style={{ width: '100%', borderCollapse: 'collapse', border: '2px solid #1e293b',
                      tableLayout: 'fixed', fontSize: 'var(--report-font-size)' }}>
        <colgroup>
          <col style={{ width: '5%' }} />
          <col style={{ width: '28%' }} />
          {[...Array(6)].map((_, i) => <col key={i} style={{ width: '11.2%' }} />)}
        </colgroup>
        <thead>
          <tr>
            <TH rowSpan={2}>Cat.</TH>
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
  const title      = data?.title       || '';
  const subtitle   = data?.subtitle    || '';
  const monthLabel = data?.month_label || '';
  const cplyLabel  = data?.cply_label  || '';
  const sections   = data?.sections    || [];

  return (
    <div style={{ padding: '8px 8px 0', fontFamily: 'Arial, sans-serif' }}>
      {title && (
        <div style={{ textAlign: 'center', fontWeight: 700, fontSize: '0.9rem',
                      textDecoration: 'underline', marginBottom: 2 }}>
          {title}
        </div>
      )}
      {subtitle && (
        <div style={{ textAlign: 'center', fontWeight: 600, fontSize: '0.85rem', marginBottom: 5 }}>
          {subtitle}
        </div>
      )}
      {sections.map((section, i) => (
        <PlantTable key={i} section={section} monthLabel={monthLabel} cplyLabel={cplyLabel} />
      ))}
    </div>
  );
}
