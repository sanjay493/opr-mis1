'use client';

// ── style tokens ──────────────────────────────────────────────────────────────
const CELL = { padding: '2px 5px', border: '1px solid #94a3b8', lineHeight: 1.25, fontSize: 'var(--report-font-size)' };
const NUM  = { ...CELL, textAlign: 'right' };
const CTR  = { ...CELL, textAlign: 'center' };
const LBL  = { ...CELL, textAlign: 'left' };
const TH   = {
  backgroundColor: '#1e3a5f', color: '#fff', padding: '3px 4px',
  textAlign: 'center', verticalAlign: 'middle',
  border: '1px solid #334155', fontSize: 'var(--report-font-size)', lineHeight: 1.2, fontWeight: 600,
};

function Qty({ value, tonnage }) {
  return (
    <>
      {value}
      {tonnage && (
        <div style={{ fontSize: '0.58rem', color: '#475569', lineHeight: 1.1 }}>
          ({tonnage} T)
        </div>
      )}
    </>
  );
}

export default function IptStatusTemplate({ data }) {
  if (!data) return null;
  const { title, month_label = '', cum_label = '', sections = [] } = data;

  return (
    <div style={{ padding: '10px', fontFamily: 'Arial, sans-serif' }}>
      <div style={{ textAlign: 'center', fontWeight: 700, fontSize: '0.95rem', marginBottom: 8 }}>
        {title}
      </div>

      <table style={{ width: '100%', borderCollapse: 'collapse', border: '2px solid #1e293b',
                      tableLayout: 'fixed', fontSize: 'var(--report-font-size)' }}>
        <colgroup>
          <col style={{ width: '24%' }} />
          <col style={{ width: '9%' }} />
          <col style={{ width: '9%' }} />
          <col style={{ width: '8%' }} />
          <col style={{ width: '12.5%' }} /><col style={{ width: '12.5%' }} />
          <col style={{ width: '12.5%' }} /><col style={{ width: '12.5%' }} />
        </colgroup>
        <thead>
          <tr>
            <th rowSpan={2} style={{ ...TH, textAlign: 'left' }}>Item</th>
            <th rowSpan={2} style={TH}>From</th>
            <th rowSpan={2} style={TH}>To</th>
            <th rowSpan={2} style={TH}>Unit</th>
            <th colSpan={2} style={TH}>{month_label}</th>
            <th colSpan={2} style={TH}>{cum_label}</th>
          </tr>
          <tr>
            <th style={TH}>Plan</th>
            <th style={TH}>Actual</th>
            <th style={TH}>Plan</th>
            <th style={TH}>Actual</th>
          </tr>
        </thead>
        <tbody>
          {sections.map((sec, si) =>
            sec.rows.map((row, ri) => (
              <tr key={`${si}-${ri}`}
                  style={{ backgroundColor: si % 2 ? '#f8fafc' : '#fff' }}>
                {ri === 0 && (
                  <td rowSpan={sec.rows.length}
                      style={{ ...LBL, fontWeight: 600, verticalAlign: 'middle' }}>
                    {sec.item}
                  </td>
                )}
                <td style={CTR}>{row.from}</td>
                <td style={CTR}>{row.to}</td>
                <td style={CTR}>{row.unit}</td>
                <td style={NUM}><Qty value={row.plan} tonnage={row.plan_t} /></td>
                <td style={NUM}><Qty value={row.actual} tonnage={row.actual_t} /></td>
                <td style={NUM}><Qty value={row.cum_plan} tonnage={row.cum_plan_t} /></td>
                <td style={NUM}><Qty value={row.cum_actual} tonnage={row.cum_actual_t} /></td>
              </tr>
            ))
          )}
        </tbody>
      </table>
    </div>
  );
}
