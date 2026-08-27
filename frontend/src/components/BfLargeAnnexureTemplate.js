'use client';

// Mirrors backend/page_templates/bf_large_annexure.html — SAIL's 3 largest
// BFs only (no non-SAIL comparison columns — see /reports/bf-benchmark for
// that, a separate standalone tool). Columns come entirely from data.periods
// (backend/page_bf_large_annexure.py's period_defs): Previous FY, ABP
// Target, one column per YTD month so far, then YTD cumulative — dynamic in
// count (a March report_month has 4 more month columns than an April one),
// so this reads that list directly rather than assuming a fixed shape.
// Each period's own dept-badge-style tint (prev_fy amber / abp light green /
// ytd darker green — same colors_config.json tokens the PDF template uses)
// makes the 3 "kinds" read apart at a glance; plain month columns stay
// untinted. See page_bf_large_annexure.py for exactly what each row reads
// from.
const KIND_BG = {
  prev_fy: '#fef9c3',
  abp: '#dcfce7',
  ytd: '#d1fae5',
};

const CELL = { padding: '1.5px 4px', border: '1px solid #94a3b8', lineHeight: 1.1 };
const NUM = { ...CELL, textAlign: 'right' };
const LBL = { ...CELL, textAlign: 'left', fontWeight: 600 };
const TH = {
  color: '#000', padding: '2px 5px',
  textAlign: 'center', verticalAlign: 'middle',
  border: '1px solid #334155', fontSize: '0.72rem', lineHeight: 1.2, fontWeight: 600,
};

export default function BfLargeAnnexureTemplate({ data }) {
  if (!data) return null;
  const { title, sail_cols = [], periods = [], rows = [] } = data;

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
              {periods.map((p) => (
                <th
                  key={p.key}
                  colSpan={sail_cols.length}
                  style={{ ...TH, backgroundColor: KIND_BG[p.kind] }}
                  dangerouslySetInnerHTML={{ __html: p.label }}
                />
              ))}
            </tr>
            <tr>
              {periods.map((p) => sail_cols.map((bf) => (
                <th key={`${p.key}-${bf.label}`} style={{ ...TH, lineHeight: 1.15, backgroundColor: KIND_BG[p.kind] }}>
                  {bf.plant}<br />{bf.unit}
                </th>
              )))}
            </tr>
          </thead>
          <tbody>
            {rows.map((row, ri) => {
              const zebra = ri % 2 ? undefined : undefined; // highlight_alt_section_bg is transparent — no zebra fill
              return (
                <tr key={ri}>
                  <td style={{ ...LBL, backgroundColor: zebra }}>{row.parameter}</td>
                  <td style={{ ...CELL, textAlign: 'center', fontStyle: 'italic', color: '#475569', backgroundColor: zebra }}>{row.unit}</td>
                  {periods.map((p) => sail_cols.map((bf) => {
                    const v = row.sail?.[bf.label]?.[p.key];
                    const tint = KIND_BG[p.kind];
                    return (
                      <td key={`${p.key}-${bf.label}`} style={{ ...NUM, backgroundColor: tint ? `${tint}66` : zebra }}>
                        {v !== null && v !== undefined ? v : '—'}
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
