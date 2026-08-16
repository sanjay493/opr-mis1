'use client';

// Mirrors backend/page_templates/bf_large_annexure.html — SAIL's 3 largest
// BFs only (no non-SAIL comparison columns — see /reports/bf-benchmark for
// that, a separate standalone tool). Each of the 3 periods (Previous FY /
// Month / YTD) is its own parent header group, dynamically labeled for
// report_month (e.g. "25-26" / "Jul-26" / "Apr-Jul'26"); each group's 3
// sub-columns are the 3 SAIL BFs, plant name wrapped over furnace name. See
// page_bf_large_annexure.py for exactly what each row reads from.
// Previous FY and YTD each get their own light, contrasting column-group
// tint (amber / green — same tokens as colors_config.json's
// highlight_target_band_bg / highlight_cumulative_bg) so the 3 periods
// read apart at a glance; Month stays untinted, with the usual row-zebra
// striping instead (matching the Parameter/Unit columns).
const PERIODS = ['prev_fy', 'month', 'ytd'];
const PREV_FY_BG = '#fef9c3';
const YTD_BG = '#d1fae5';
const ZEBRA_BG = '#f8fafc';

const CELL = { padding: '4px 8px', border: '1px solid #94a3b8' };
const NUM = { ...CELL, textAlign: 'right' };
const LBL = { ...CELL, textAlign: 'left', fontWeight: 600 };
const TH = {
  color: '#000', padding: '5px 6px',
  textAlign: 'center', verticalAlign: 'middle',
  border: '1px solid #334155', fontSize: '0.72rem', lineHeight: 1.25, fontWeight: 600,
};

function periodBg(period, alpha) {
  if (period === 'prev_fy') return PREV_FY_BG + alpha;
  if (period === 'ytd') return YTD_BG + alpha;
  return undefined;
}

export default function BfLargeAnnexureTemplate({ data }) {
  if (!data) return null;
  const {
    title, prev_fy_col_label = '', month_col_label = '', ytd_col_label = '',
    sail_cols = [], rows = [],
  } = data;
  const periodLabels = { prev_fy: prev_fy_col_label, month: month_col_label, ytd: ytd_col_label };

  return (
    <div style={{ padding: '8px', fontFamily: 'Arial, sans-serif', fontSize: '0.72rem' }}>
      <div style={{ textAlign: 'center', fontWeight: 700, fontSize: '1rem', marginBottom: 10 }}>
        {title}
      </div>

      <div style={{ overflowX: 'auto' }}>
        <table style={{ borderCollapse: 'collapse', border: '1px solid #1e293b', fontSize: '0.72rem', width: '100%' }}>
          <thead>
            <tr>
              <th rowSpan={2} style={{ ...TH, textAlign: 'left' }}>Parameter</th>
              <th rowSpan={2} style={TH}>Unit</th>
              {PERIODS.map((p) => (
                <th key={p} colSpan={sail_cols.length} style={{ ...TH, backgroundColor: periodBg(p, '') }}>{periodLabels[p]}</th>
              ))}
            </tr>
            <tr>
              {PERIODS.map((p) => sail_cols.map((bf) => (
                <th key={`${p}-${bf.label}`} style={{ ...TH, lineHeight: 1.25, backgroundColor: periodBg(p, '') }}>
                  {bf.plant}<br />{bf.unit}
                </th>
              )))}
            </tr>
          </thead>
          <tbody>
            {rows.map((row, ri) => {
              const zebra = ri % 2 ? ZEBRA_BG : undefined;
              return (
                <tr key={ri}>
                  <td style={{ ...LBL, backgroundColor: zebra }}>{row.parameter}</td>
                  <td style={{ ...CELL, textAlign: 'center', fontStyle: 'italic', color: '#475569', backgroundColor: zebra }}>{row.unit}</td>
                  {PERIODS.map((p) => sail_cols.map((bf) => {
                    const v = row.sail[bf.label]?.[p];
                    return (
                      <td key={`${p}-${bf.label}`} style={{ ...NUM, backgroundColor: periodBg(p, '66') || zebra }}>
                        {v ?? '—'}
                      </td>
                    );
                  }))}
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
