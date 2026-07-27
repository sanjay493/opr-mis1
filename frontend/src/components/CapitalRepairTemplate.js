'use client';

// ── style tokens ──────────────────────────────────────────────────────────────
const CELL = { padding: '4px 7px', border: '1px solid #94a3b8', lineHeight: 1.25, fontSize: '9.5pt' };
const CTR  = { ...CELL, textAlign: 'center' };
const LBL  = { ...CELL, textAlign: 'left' };
const TH   = {
  backgroundColor: '#fff', color: '#000', padding: '4px 7px',
  textAlign: 'center', verticalAlign: 'middle',
  border: '1px solid #334155', fontSize: '9.5pt', lineHeight: 1.2, fontWeight: 600,
};

export default function CapitalRepairTemplate({ data }) {
  if (!data) return null;
  const { title, subtitle, sections = [] } = data;

  return (
    <div style={{ padding: '10px', fontFamily: 'Arial, sans-serif' }}>
      <div style={{ textAlign: 'center', fontWeight: 700, fontSize: '1rem' }}>
        {title}
      </div>
      {subtitle && (
        <div style={{ textAlign: 'center', fontWeight: 700, fontSize: '0.9rem', marginBottom: 8 }}>
          {subtitle}
        </div>
      )}

      <table style={{ width: '100%', borderCollapse: 'collapse', border: '2px solid #1e293b',
                      tableLayout: 'fixed', fontSize: 'var(--report-font-size)' }}>
        <colgroup>
          <col style={{ width: '14%' }} />
          <col style={{ width: '12%' }} />
          <col style={{ width: '34%' }} />
          <col style={{ width: '12%' }} />
          <col style={{ width: '14%' }} />
          <col style={{ width: '14%' }} />
        </colgroup>
        <thead>
          <tr>
            <th style={TH}>Shop</th>
            <th style={TH}>Equipment</th>
            <th style={TH}>Activity</th>
            <th style={TH}>Schedule (days)</th>
            <th style={TH}>Period</th>
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
                    {sec.shop}
                  </td>
                )}
                <td style={CTR}>{row.equipment}</td>
                <td style={LBL}>{row.activity}</td>
                <td style={CTR}>{row.schedule_days}</td>
                <td style={CTR}>{row.period}</td>
                <td style={CTR}>{row.actual}</td>
              </tr>
            ))
          )}
        </tbody>
      </table>
    </div>
  );
}
