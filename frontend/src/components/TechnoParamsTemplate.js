'use client';

const B = '1px solid #000';

const cell = (extra = {}) => ({
  padding: '1.5px 3px', lineHeight: 1.15,
  fontSize: 'var(--report-font-size, 6.5pt)',
  borderLeft: B, borderRight: B, borderTop: 0, borderBottom: 0,
  ...extra,
});
const NUM = cell({ textAlign: 'right', whiteSpace: 'nowrap' });
const LBL = cell({ textAlign: 'left' });
const th = (extra = {}) => ({
  color: '#000', padding: '2px 3px', textAlign: 'center',
  verticalAlign: 'middle', border: B,
  fontSize: 'var(--report-font-size, 6.5pt)', lineHeight: 1.15, fontWeight: 700,
  ...extra,
});

export default function TechnoParamsTemplate({ data }) {
  if (!data) return null;
  const {
    title, subtitle = '', sections = [], group = '',
    fy3_label = '', fy2_label = '', fy1_label = '', target_label = '',
    month_labels = [], cply_label = '', cum_label = '', cum_cply_label = '',
    sail_is_user_supplied = false,
  } = data;

  // Mill pages (31-35): sections = mills, rows = params with individual units
  // Param pages (27-30): sections = params (with shared unit), rows = plants/shops
  const isMill = (group || '').startsWith('MILL_');
  const nMonths = month_labels.length;
  // data cols: FY-3, FY-2, FY-1, Target, Apr…Month, CPLY-month, YTD, YTD-CPLY
  const nData = 3 + 1 + nMonths + 1 + 1 + 1;

  // Param pages (27-30): fixed text columns take a fixed share, data columns share the rest.
  // Mill pages (31-35): table-layout:auto instead, so every column (including
  // data columns) sizes to its own content rather than a guessed percentage.
  const fixedPct = 17;   // Param(10)+Shop(7)
  const dataW    = `${(100 - fixedPct) / nData}%`;

  const bk = (first, last) => ({
    ...(first ? { borderTop: B }    : {}),
    ...(last  ? { borderBottom: B } : {}),
  });

  const renderDataCells = (row, bkSt, sailSt) => (
    <>
      <td style={{ ...NUM, ...bkSt, ...sailSt }}>{row.fy3}</td>
      <td style={{ ...NUM, ...bkSt, ...sailSt }}>{row.fy2}</td>
      <td style={{ ...NUM, ...bkSt, ...sailSt }}>{row.fy1}</td>
      <td style={{ ...NUM, ...bkSt, ...sailSt }}>{row.target}</td>
      {(row.months || []).map((v, mi) => (
        <td key={mi} style={{ ...NUM, ...bkSt, ...sailSt }}>{v}</td>
      ))}
      <td style={{ ...NUM, ...bkSt, ...sailSt }}>{row.cply}</td>
      <td style={{ ...NUM, ...bkSt, ...sailSt }}>{row.cum}</td>
      <td style={{ ...NUM, ...bkSt, ...sailSt }}>{row.cum_cply}</td>
    </>
  );

  return (
    <div style={{ padding: '6px', fontFamily: "'Arial Narrow', Arial, sans-serif" }}>
      {/* Page title */}
      <div style={{ textAlign: 'center', fontWeight: 700, fontSize: '0.88rem', marginBottom: 1 }}>
        {title}
        {sail_is_user_supplied && group === 'MAJOR' && (
          <span style={{ marginLeft: '8px', fontSize: '0.75rem', color: '#059669', fontWeight: '600' }}>
            ✏️ (SAIL: User-supplied)
          </span>
        )}
      </div>
      {subtitle && (
        <div style={{ textAlign: 'center', fontWeight: 600, fontSize: '0.76rem', marginBottom: 4 }}>
          {subtitle}
        </div>
      )}

      <table style={{
        width: '100%', borderCollapse: 'collapse', border: B,
        tableLayout: isMill ? 'auto' : 'fixed', fontSize: 'var(--report-font-size, 6.5pt)', marginTop: 4,
      }}>
        <colgroup>{isMill ? (<><col /><col /></>) : (<><col style={{ width: '10%' }} /><col style={{ width: '7%' }} /></>)}{[0, 1, 2, 3].map(i => <col key={`f${i}`} style={isMill ? undefined : { width: dataW }} />)}{month_labels.map((_, i) => <col key={`m${i}`} style={isMill ? undefined : { width: dataW }} />)}{[0, 1, 2].map(i => <col key={`c${i}`} style={isMill ? undefined : { width: dataW }} />)}</colgroup>

        <thead>
          {/* Row 1 — group headers */}
          <tr>
            {isMill ? (
              <>
                <th rowSpan={2} style={th()}>Mill</th>
                <th rowSpan={2} style={th({ textAlign: 'left' })}>Parameters</th>
              </>
            ) : (
              <>
                <th rowSpan={2} style={th({ textAlign: 'left' })}>Parameters</th>
                <th rowSpan={2} style={th()}>Shop /<br />Plant</th>
              </>
            )}
            <th colSpan={3} style={th()}>Actual</th>
            <th rowSpan={2} style={th()}>{target_label || 'Target'}</th>
            {nMonths > 0 && <th colSpan={nMonths} style={th()}>Actual (Month-wise)</th>}
            <th rowSpan={2} style={th()}>{cply_label || 'CPLY'}<br />Actual</th>
            <th colSpan={2} style={th()}>Cumulative</th>
          </tr>
          {/* Row 2 — individual column labels */}
          <tr>
            <th style={th()}>{fy3_label}</th>
            <th style={th()}>{fy2_label}</th>
            <th style={th()}>{fy1_label}</th>
            {month_labels.map((m, i) => <th key={i} style={th()}>{m}</th>)}
            <th style={th()}>{cum_label}</th>
            <th style={th()}>{cum_cply_label}</th>
          </tr>
        </thead>

        <tbody>
          {sections.map((sec, si) =>
            sec.rows.map((row, ri) => {
              const isFirst = ri === 0;
              const isLast  = ri === sec.rows.length - 1;
              const bkSt    = bk(isFirst, isLast);
              const sailSt  = (row.label === 'SAIL' || row.bold) ? { fontWeight: 700, borderTop: B } : {};

              return (
                <tr key={`${si}-${ri}`}>
                  {/* ── Param pages: first col = param name + unit on separate line ── */}
                  {!isMill && isFirst && (
                    <td rowSpan={sec.rows.length}
                        style={{ ...LBL, fontWeight: 700, verticalAlign: 'top',
                                 borderTop: B, borderBottom: B }}>
                      {sec.label}
                      {sec.rows[0]?.unit && (
                        <div style={{ fontWeight: 400, color: '#374151', marginTop: '1px' }}>
                          ({sec.rows[0].unit})
                        </div>
                      )}
                    </td>
                  )}

                  {/* ── Mill pages: first col = mill name (rowspan), rotated bottom-to-top ── */}
                  {isMill && isFirst && (
                    <td rowSpan={sec.rows.length}
                        style={{ ...LBL, fontWeight: 700, verticalAlign: 'middle',
                                 textAlign: 'center', borderTop: B, borderBottom: B,
                                 whiteSpace: 'nowrap', writingMode: 'vertical-rl', transform: 'rotate(180deg)' }}>
                      {sec.label}
                    </td>
                  )}

                  {/* Row label: plant/shop for param pages; param name + unit for mill pages */}
                  <td style={{ ...LBL, ...bkSt, ...sailSt, whiteSpace: 'nowrap' }}>
                    {isMill && row.unit ? `${row.label} (${row.unit})` : row.label}
                  </td>

                  {renderDataCells(row, bkSt, sailSt)}
                </tr>
              );
            })
          )}
        </tbody>
      </table>

      <div style={{
        display: 'flex', justifyContent: 'space-between',
        fontSize: '0.6rem', color: '#475569', marginTop: 3,
      }}>
        <span>figures are provisional</span>
        <span>for internal circulation only</span>
      </div>
    </div>
  );
}
