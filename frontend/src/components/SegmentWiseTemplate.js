'use client';

const CELL = { padding: '1.5px 4px', border: '1px solid #cbd5e1', lineHeight: 1.2 };
const NUM = { ...CELL, textAlign: 'right' };
const LBL = { ...CELL, textAlign: 'left' };

const ROW_STYLES = {
  data:         { backgroundColor: '#f8fafc' },
  'seg-total':  { backgroundColor: '#fef9c3', fontWeight: 700 },
  'seg-pct':    { backgroundColor: '#f1f5f9', fontWeight: 700, fontStyle: 'italic' },
  'grand-total':{ backgroundColor: '#dcfce7', fontWeight: 700 },
};

function SWRow({ row }) {
  if (row.type === 'separator') {
    return <tr style={{ height: 3 }}><td colSpan={7} style={{ border: 'none', padding: 0 }} /></tr>;
  }
  if (row.type === 'seg-hdr') {
    return (
      <tr>
        <td colSpan={7} style={{ ...LBL, backgroundColor: '#1e3a5f', color: '#fff',
                                  fontWeight: 700, padding: '3px 5px',
                                  border: '1px solid #334155' }}>
          {row.label}
        </td>
      </tr>
    );
  }
  if (row.type === 'plant-lbl') {
    return (
      <tr>
        <td colSpan={7} style={{ ...LBL, backgroundColor: '#dbeafe', fontWeight: 700 }}>
          {row.label}
        </td>
      </tr>
    );
  }
  const style = ROW_STYLES[row.type] || {};
  const isPct = row.type === 'seg-pct';
  return (
    <tr style={style}>
      <td style={{ ...LBL, ...style }}>{row.label}</td>
      <td style={{ ...NUM, ...style }}>{row.ann_plan}</td>
      <td style={{ ...NUM, ...style }}>{row.m_plan}</td>
      <td style={{ ...NUM, ...style }}>{row.m_act}</td>
      <td style={{ ...NUM, ...style }}>{isPct ? '' : row.m_pct}</td>
      <td style={{ ...NUM, ...style }}>{row.cply_act}</td>
      <td style={{ ...NUM, ...style }}>{isPct ? '' : row.m_growth}</td>
    </tr>
  );
}

export default function SegmentWiseTemplate({ data }) {
  const monthLabel = data?.month_label || '';
  const cplyLabel  = data?.cply_label  || '';
  const rows       = data?.rows        || [];

  const TH = ({ children, rowSpan, colSpan, left }) => (
    <th rowSpan={rowSpan} colSpan={colSpan}
      style={{ backgroundColor: '#1e3a5f', color: '#fff', padding: '2px 3px',
               textAlign: left ? 'left' : 'center', verticalAlign: 'middle',
               border: '1px solid #334155', fontSize: 'var(--report-font-size)', lineHeight: 1.2, fontWeight: 600 }}>
      {children}
    </th>
  );

  return (
    <div style={{ padding: '8px', fontFamily: 'Arial, sans-serif', fontSize: 'var(--report-font-size)' }}>
      <table style={{ width: '100%', borderCollapse: 'collapse', border: '2px solid #1e293b',
                      tableLayout: 'fixed' }}>
        <colgroup>
          <col style={{ width: '27%' }} />
          {[...Array(6)].map((_, i) => <col key={i} style={{ width: '12.2%' }} />)}
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
          {rows.map((row, i) => <SWRow key={i} row={row} />)}
        </tbody>
      </table>
    </div>
  );
}
