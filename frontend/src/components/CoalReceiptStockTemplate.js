'use client';

// Mirrors backend/page_templates/coal_receipt_stock.html — see
// page_coal_receipts_stock.py for the data shape. Reproduces Report_format/
// Coal_co2/Coal Format.pdf's OIS-2 table (SAIL-level only).
const BORDER = '#334155';
const TITLE_COLOR = '#333333';
const NOTE_COLOR = '#475569';

const cellStyle = { border: `1px solid ${BORDER}`, padding: '2px 5px', textAlign: 'center' };

function fmt0(v) {
  return v === null || v === undefined ? '—' : Math.round(v).toString();
}

function StockHistoryTable({ table, monthNames }) {
  const th = { ...cellStyle, fontWeight: 700, fontSize: '8pt' };
  const td = { ...cellStyle, fontSize: '8pt' };
  return (
    <table style={{ width: '100%', tableLayout: 'fixed', borderCollapse: 'collapse', marginBottom: 4 }}>
      <thead>
        <tr>
          <th style={{ ...th, textAlign: 'left', width: 70 }}>FY</th>
          {monthNames.map((m) => <th key={m} style={th}>{m}</th>)}
        </tr>
      </thead>
      <tbody>
        {table.rows.map((row) => (
          <tr key={row.fy}>
            <td style={{ ...td, textAlign: 'left', fontWeight: 600, width: 70 }}>{row.fy}</td>
            {row.values.map((v, i) => <td key={i} style={td}>{fmt0(v)}</td>)}
          </tr>
        ))}
      </tbody>
    </table>
  );
}

export default function CoalReceiptStockTemplate({ data }) {
  const {
    title = '', receipt_rows: receiptRows = [], consumption_rows: consumptionRows = [],
    stock_history_tables: stockHistoryTables = [], stock_history_month_names: stockHistoryMonthNames = [],
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

      {stockHistoryTables.map((t) => (
        <div key={t.key} style={{ marginTop: 10 }}>
          <div style={{ fontWeight: 700, fontSize: '9.5pt', margin: '6px 0 4px' }}>
            Month-wise Opening Stock — {t.label} (&apos;000 T)
          </div>
          <StockHistoryTable table={t} monthNames={stockHistoryMonthNames} />
        </div>
      ))}

      <div style={{ fontSize: '7.5pt', marginTop: 6, color: NOTE_COLOR }}>
        Note: The above information is based on reports from Plants/CCSO and is provisional
      </div>
    </div>
  );
}
