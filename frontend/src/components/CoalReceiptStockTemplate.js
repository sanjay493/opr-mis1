'use client';

// Mirrors backend/page_templates/coal_receipt_stock.html — see
// page_coal_receipts_stock.py for the data shape. Reproduces Report_format/
// Coal_co2/Coal Format.pdf's OIS-2 table (SAIL-level only).
const BORDER = '#334155';
const TITLE_COLOR = '#333333';
const NOTE_COLOR = '#475569';

const cellStyle = { border: `1px solid ${BORDER}`, padding: '2px 5px', textAlign: 'center' };
const gapCellStyle = { border: 'none', padding: 0, background: 'transparent', width: 14 };

// Fixed (not 100%-stretched) column widths — however many months happen to
// have data yet, each column stays the same width as every other row's,
// instead of the table's columns stretching to fill the full available
// width whenever few months are populated (e.g. early in an FY, before
// most months have stock data: a lone 2-3-column table would otherwise
// balloon each column to several times a fully-populated row's width).
const LABEL_COL_WIDTH = 95;
const DATA_COL_WIDTH = 68;

function fmt0(v) {
  return v === null || v === undefined ? '—' : Math.round(v).toString();
}

function StockTable({ cols, gapAfter }) {
  const th = { ...cellStyle, fontWeight: 700, fontSize: '8pt', width: DATA_COL_WIDTH };
  const td = { ...cellStyle, fontSize: '8pt', width: DATA_COL_WIDTH };
  const before = gapAfter ? cols.slice(0, gapAfter) : cols;
  const after = gapAfter ? cols.slice(gapAfter) : [];

  const rowCells = (renderCell) => (
    <>
      {before.map((c, i) => renderCell(c, i))}
      {gapAfter && <td style={gapCellStyle} />}
      {after.map((c, i) => renderCell(c, gapAfter + i))}
    </>
  );

  return (
    <table style={{ width: 'auto', tableLayout: 'fixed', borderCollapse: 'collapse' }}>
      <thead>
        <tr>
          <th style={{ ...th, textAlign: 'left', width: LABEL_COL_WIDTH }}>Category</th>
          {before.map((c, i) => <th key={i} style={th}>{c.date_label}</th>)}
          {gapAfter && <th style={gapCellStyle} />}
          {after.map((c, i) => <th key={gapAfter + i} style={th}>{c.date_label}</th>)}
        </tr>
      </thead>
      <tbody>
        <tr>
          <td style={{ ...td, textAlign: 'left', fontWeight: 600, width: LABEL_COL_WIDTH }}>Indigenous</td>
          {rowCells((c, i) => <td key={i} style={td}>{fmt0(c.indigenous)}</td>)}
        </tr>
        <tr>
          <td style={{ ...td, textAlign: 'left', fontWeight: 600, width: LABEL_COL_WIDTH }}>Imported</td>
          {rowCells((c, i) => <td key={i} style={td}>{fmt0(c.imported)}</td>)}
        </tr>
        <tr style={{ fontWeight: 700 }}>
          <td style={{ ...td, textAlign: 'left', width: LABEL_COL_WIDTH }}>Total</td>
          {rowCells((c, i) => <td key={i} style={td}>{fmt0(c.total)}</td>)}
        </tr>
      </tbody>
    </table>
  );
}

export default function CoalReceiptStockTemplate({ data }) {
  const {
    title = '', receipt_rows: receiptRows = [], consumption_rows: consumptionRows = [],
    stock_cols_1: stockCols1 = [], stock_cols_2: stockCols2 = [], stock_gap_after: stockGapAfter,
  } = data || {};

  const abTh = { ...cellStyle, fontWeight: 700, fontSize: '8.5pt' };
  const abTd = { ...cellStyle, fontSize: '8.5pt' };

  return (
    <div style={{ fontFamily: 'inherit' }}>
      <div style={{ textAlign: 'center', fontWeight: 700, fontSize: '11pt', textDecoration: 'underline', marginBottom: 6, color: TITLE_COLOR }}>
        {title}
      </div>

      {/* Sized to content (label col + 2-3 narrow data cols), not
          stretched to fill half the landscape page each — matching the
          reference PDF's compact boxes. (B) is pushed to the right edge
          (space-between) rather than sitting gap-adjacent to (A), per
          direct instruction. */}
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 12 }}>
        <div style={{ flex: '0 0 auto', width: 300 }}>
          <div style={{ fontWeight: 700, fontSize: '9.5pt', marginBottom: 4 }}>
            (A) Receipt at Plants <span style={{ fontWeight: 400, fontSize: '8pt' }}>(TPD)</span>
          </div>
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead>
              <tr><th style={abTh} /><th style={abTh}>Plan</th><th style={abTh}>Actual</th></tr>
            </thead>
            <tbody>
              {receiptRows.map((r) => (
                <tr key={r.label} style={r.label === 'Total Coal' ? { fontWeight: 700 } : undefined}>
                  <td style={{ ...abTd, textAlign: 'left', fontWeight: 600 }}>{r.label}</td>
                  <td style={abTd}>{fmt0(r.plan)}</td>
                  <td style={abTd}>{fmt0(r.actual)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <div style={{ flex: '0 0 auto', width: 300 }}>
          <div style={{ fontWeight: 700, fontSize: '9.5pt', marginBottom: 4 }}>(B) Consumption at Plants</div>
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead>
              <tr><th style={abTh} /><th style={abTh}>Actual<br />(&apos;000 T)</th><th style={abTh}>Average<br />(TPD)</th></tr>
            </thead>
            <tbody>
              {consumptionRows.map((r) => (
                <tr key={r.label} style={r.label === 'Total Coal' ? { fontWeight: 700 } : undefined}>
                  <td style={{ ...abTd, textAlign: 'left', fontWeight: 600 }}>{r.label}</td>
                  <td style={abTd}>{fmt0(r.actual)}</td>
                  <td style={abTd}>{fmt0(r.avg)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      <div style={{ fontWeight: 700, fontSize: '9.5pt', margin: '6px 0 4px' }}>
        (C) Month-wise stocks at plants (&apos;000 T)
      </div>
      {/* Two stacked mini-tables (first 6 FY months, then the remaining 7),
          matching the reference PDF's own two-row layout rather than one
          row growing wider as the FY progresses. Each column only renders
          if that month actually has data (see stock_gap_after's docstring
          in page_coal_receipts_stock.py) — either table skips rendering
          entirely once nothing in it has data yet (e.g. early in an FY,
          before any Apr-Sep month has been reported, table 1 alone would
          otherwise render as an empty label-only box). */}
      {stockCols1.length > 0 && <StockTable cols={stockCols1} gapAfter={stockGapAfter} />}
      {stockCols2.length > 0 && (
        <div style={{ marginTop: 6 }}>
          <StockTable cols={stockCols2} />
        </div>
      )}

      <div style={{ fontSize: '7.5pt', marginTop: 6, color: NOTE_COLOR }}>
        Note: The above information is based on reports from Plants/CCSO and is provisional
      </div>
    </div>
  );
}
