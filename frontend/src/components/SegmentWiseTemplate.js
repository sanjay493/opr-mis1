'use client';

const CELL = { padding: '1.5px 4px', border: '1px solid #cbd5e1', lineHeight: 1.2 };
const NUM  = { ...CELL, textAlign: 'right' };
const LBL  = { ...CELL, textAlign: 'left' };
const CTR  = { ...CELL, textAlign: 'center' };

const ROW_STYLES = {
  data:          { backgroundColor: '#f8fafc' },
  'seg-total':   { backgroundColor: '#fef9c3', fontWeight: 700 },
  'seg-pct':     { backgroundColor: '#f1f5f9', fontWeight: 700, fontStyle: 'italic' },
  'grand-total': { backgroundColor: '#dcfce7', fontWeight: 700 },
};

function SWRow({ row }) {
  if (row.type === 'separator') return null;

  const style     = ROW_STYLES[row.type] || {};
  const isSpanning = ['seg-total', 'seg-pct', 'grand-total'].includes(row.type);

  const nums = [
    row.ann_plan,
    row.m_plan, row.m_act, row.m_pct,
    row.cply_act, row.m_growth,
    row.cum_plan, row.cum_act, row.cum_pct,
    row.cum_cply, row.cum_growth,
  ].map((v, i) => <td key={i} style={{ ...NUM, ...style }}>{v}</td>);

  if (isSpanning) {
    return (
      <tr style={style}>
        <td colSpan={3} style={{ ...LBL, ...style }}>{row.label}</td>
        {nums}
      </tr>
    );
  }

  return (
    <tr style={style}>
      {row.show_group && (
        <td rowSpan={row.group_span} style={{
          ...CTR, backgroundColor: '#1e3a5f', color: '#fff',
          fontWeight: 700, verticalAlign: 'middle', border: '1px solid #334155',
        }}>
          {row.group}
        </td>
      )}
      {row.show_plant && (
        <td rowSpan={row.plant_span} style={{
          ...CTR, backgroundColor: '#dbeafe', fontWeight: 700, verticalAlign: 'middle',
        }}>
          {row.plant}
        </td>
      )}
      <td style={LBL}>{row.label}</td>
      {nums}
    </tr>
  );
}

export default function SegmentWiseTemplate({ data }) {
  const monthLabel   = data?.month_label || '';
  const cplyLabel    = data?.cply_label  || '';
  const rows         = data?.rows        || [];
  const cumLabel     = monthLabel ? `Apr-${monthLabel}` : 'Apr-YTD';
  const cumCplyLabel = cplyLabel  ? `Apr-${cplyLabel}`  : 'Apr-CPLY';

  const TH = ({ children, rowSpan, colSpan, left }) => (
    <th rowSpan={rowSpan} colSpan={colSpan}
      style={{
        backgroundColor: '#1e3a5f', color: '#fff', padding: '2px 3px',
        textAlign: left ? 'left' : 'center', verticalAlign: 'middle',
        border: '1px solid #334155',
        fontSize: 'var(--report-font-size)', lineHeight: 1.2, fontWeight: 600,
      }}>
      {children}
    </th>
  );

  return (
    <div style={{ padding: '6px', fontFamily: 'Arial, sans-serif', fontSize: 'var(--report-font-size)' }}>
      <table style={{
        width: '100%', borderCollapse: 'collapse',
        border: '2px solid #1e293b', tableLayout: 'fixed',
      }}>
        <colgroup>
          <col style={{ width: '5%' }} />
          <col style={{ width: '5%' }} />
          <col style={{ width: '14%' }} />
          <col style={{ width: '7%' }} />
          <col style={{ width: '6%' }} />
          <col style={{ width: '6%' }} />
          <col style={{ width: '5%' }} />
          <col style={{ width: '6%' }} />
          <col style={{ width: '5%' }} />
          <col style={{ width: '6%' }} />
          <col style={{ width: '6%' }} />
          <col style={{ width: '5%' }} />
          <col style={{ width: '6%' }} />
          <col style={{ width: '5%' }} />
        </colgroup>
        <thead>
          <tr>
            <TH rowSpan={2}>Group</TH>
            <TH rowSpan={2}>Plant</TH>
            <TH rowSpan={2} left>Item</TH>
            <TH rowSpan={2}>Plan<br />26-27</TH>
            <TH colSpan={3}>{monthLabel}</TH>
            <TH rowSpan={2}>{cplyLabel}<br />Actual</TH>
            <TH rowSpan={2}>% Gr.<br />over<br />{cplyLabel}</TH>
            <TH colSpan={3}>{cumLabel}</TH>
            <TH rowSpan={2}>{cumCplyLabel}<br />Actual</TH>
            <TH rowSpan={2}>% Gr<br />Over<br />{cumCplyLabel}</TH>
          </tr>
          <tr>
            <TH>Plan</TH><TH>Actual</TH><TH>%Ful.</TH>
            <TH>Plan</TH><TH>Actual</TH><TH>%Ful.</TH>
          </tr>
        </thead>
        <tbody>
          {rows.map((row, i) => <SWRow key={i} row={row} />)}
        </tbody>
      </table>
    </div>
  );
}
