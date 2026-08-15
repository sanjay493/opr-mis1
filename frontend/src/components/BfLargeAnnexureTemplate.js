'use client';

// Mirrors backend/page_templates/bf_large_annexure.html — SAIL's 3 largest
// BFs only (no non-SAIL comparison columns — see /reports/bf-benchmark for
// that, a separate standalone tool). Each of the 3 periods (Previous FY /
// Month / YTD) is its own parent header group, dynamically labeled for
// report_month (e.g. "25-26" / "Jul-26" / "Apr-Jul'26"); each group's 3
// sub-columns are the 3 SAIL BFs, plant name wrapped over furnace name. See
// page_bf_large_annexure.py for exactly what each row reads from.
const PERIODS = ['prev_fy', 'month', 'ytd'];

const CELL = { padding: '2px 5px', border: '1px solid #94a3b8', whiteSpace: 'nowrap' };
const NUM  = { ...CELL, textAlign: 'right' };
const LBL  = { ...CELL, textAlign: 'left', fontWeight: 600 };
const TH   = {
  backgroundColor: '#fff', color: '#000', padding: '2px 4px',
  textAlign: 'center', verticalAlign: 'middle',
  border: '1px solid #334155', fontSize: '0.62rem', lineHeight: 1.2, fontWeight: 600,
};

export default function BfLargeAnnexureTemplate({ data }) {
  if (!data) return null;
  const {
    title, prev_fy_col_label = '', month_col_label = '', ytd_col_label = '',
    sail_cols = [], rows = [],
  } = data;
  const periodLabels = { prev_fy: prev_fy_col_label, month: month_col_label, ytd: ytd_col_label };

  return (
    <div style={{ padding: '8px', fontFamily: 'Arial, sans-serif', fontSize: '0.6rem' }}>
      <div style={{ textAlign: 'center', fontWeight: 700, fontSize: '0.95rem', marginBottom: 8 }}>
        {title}
      </div>

      <div style={{ overflowX: 'auto' }}>
        <table style={{ borderCollapse: 'collapse', border: '1px solid #1e293b', fontSize: '0.6rem' }}>
          <thead>
            <tr>
              <th rowSpan={2} style={{ ...TH, textAlign: 'left' }}>Parameter</th>
              <th rowSpan={2} style={TH}>Unit</th>
              {PERIODS.map((p) => (
                <th key={p} colSpan={sail_cols.length} style={TH}>{periodLabels[p]}</th>
              ))}
            </tr>
            <tr>
              {PERIODS.map((p) => sail_cols.map((bf) => (
                <th key={`${p}-${bf.label}`} style={{ ...TH, lineHeight: 1.2 }}>
                  {bf.plant}<br />{bf.unit}
                </th>
              )))}
            </tr>
          </thead>
          <tbody>
            {rows.map((row, ri) => (
              <tr key={ri} style={{ backgroundColor: ri % 2 ? '#f8fafc' : '#fff' }}>
                <td style={LBL}>{row.parameter}</td>
                <td style={{ ...CELL, textAlign: 'center', fontStyle: 'italic', color: '#475569' }}>{row.unit}</td>
                {PERIODS.map((p) => sail_cols.map((bf) => {
                  const v = row.sail[bf.label]?.[p];
                  return <td key={`${p}-${bf.label}`} style={NUM}>{v ?? '—'}</td>;
                }))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div style={{ fontSize: '0.55rem', color: '#475569', marginTop: 4 }}>
        Blank cells (&ldquo;—&rdquo;) have no data uploaded/entered yet for that furnace/period — see{' '}
        <a href="/data-entry/bf-large-manual" style={{ color: '#1a73e8' }}>BF Large Manual Entry</a>.
      </div>
    </div>
  );
}
