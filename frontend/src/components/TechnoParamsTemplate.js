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

  // Widths: fixed text columns take a fixed share; data columns share the rest equally
  const fixedPct = isMill ? 27 : 24;   // mill: Mill(8)+Param(14)+Unit(5); param: Param(17)+Shop(7)
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
        tableLayout: 'fixed', fontSize: 'var(--report-font-size, 6.5pt)', marginTop: 4,
      }}>
        <colgroup>{isMill ? (<><col style={{ width: '8%' }} /><col style={{ width: '14%' }} /><col style={{ width: '5%' }} /></>) : (<><col style={{ width: '17%' }} /><col style={{ width: '7%' }} /></>)}{[0, 1, 2, 3].map(i => <col key={`f${i}`} style={{ width: dataW }} />)}{month_labels.map((_, i) => <col key={`m${i}`} style={{ width: dataW }} />)}{[0, 1, 2].map(i => <col key={`c${i}`} style={{ width: dataW }} />)}</colgroup>

        <thead>
          {/* Row 1 — group headers */}
          <tr>
            {isMill ? (
              <>
                <th rowSpan={2} style={th({ textAlign: 'left' })}>Mill</th>
                <th rowSpan={2} style={th({ textAlign: 'left' })}>Parameters</th>
                <th rowSpan={2} style={th()}>Unit</th>
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

                  {/* ── Mill pages: first col = mill name (rowspan) ── */}
                  {isMill && isFirst && (
                    <td rowSpan={sec.rows.length}
                        style={{ ...LBL, fontWeight: 700, verticalAlign: 'middle',
                                 textAlign: 'center', borderTop: B, borderBottom: B }}>
                      {sec.label}
                    </td>
                  )}

                  {/* Row label: plant/shop for param pages; param name for mill pages */}
                  <td style={{ ...LBL, ...bkSt, ...sailSt, whiteSpace: 'nowrap' }}>{row.label}</td>

                  {/* Unit column only on mill pages (per-row unit) */}
                  {isMill && (
                    <td style={{ ...cell({ textAlign: 'center', color: '#374151' }), ...bkSt }}>
                      {row.unit}
                    </td>
                  )}

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
