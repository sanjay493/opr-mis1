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

export default function CoalReceiptStockTemplate({ data }) {
  const { title = '', receipt_rows = [], consumption_rows = [], stock_cols = [] } = data || {};

  const abTh = { ...cellStyle, fontWeight: 700, fontSize: '8.5pt' };
  const abTd = { ...cellStyle, fontSize: '8.5pt' };

  return (
    <div style={{ fontFamily: 'inherit' }}>
      <div style={{ textAlign: 'center', fontWeight: 700, fontSize: '11pt', textDecoration: 'underline', marginBottom: 6, color: TITLE_COLOR }}>
        {title}
      </div>

      <div style={{ display: 'flex', gap: 20, marginBottom: 12 }}>
        <div style={{ flex: 1 }}>
          <div style={{ fontWeight: 700, fontSize: '9.5pt', marginBottom: 4 }}>
            (A) Receipt at Plants <span style={{ fontWeight: 400, fontSize: '8pt' }}>(TPD)</span>
          </div>
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead>
              <tr><th style={abTh} /><th style={abTh}>Plan</th><th style={abTh}>Actual</th></tr>
            </thead>
            <tbody>
              {receipt_rows.map((r) => (
                <tr key={r.label} style={r.label === 'Total Coal' ? { fontWeight: 700 } : undefined}>
                  <td style={{ ...abTd, textAlign: 'left', fontWeight: 600 }}>{r.label}</td>
                  <td style={abTd}>{fmt0(r.plan)}</td>
                  <td style={abTd}>{fmt0(r.actual)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <div style={{ flex: 1 }}>
          <div style={{ fontWeight: 700, fontSize: '9.5pt', marginBottom: 4 }}>(B) Consumption at Plants</div>
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead>
              <tr><th style={abTh} /><th style={abTh}>Actual<br />(&apos;000 T)</th><th style={abTh}>Average<br />(TPD)</th></tr>
            </thead>
            <tbody>
              {consumption_rows.map((r) => (
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
      <table style={{ width: '100%', borderCollapse: 'collapse' }}>
        <thead>
          <tr>
            <th style={{ ...cellStyle, fontWeight: 700, fontSize: '8pt', textAlign: 'left' }}>Category</th>
            {stock_cols.map((c, i) => <th key={i} style={{ ...cellStyle, fontWeight: 700, fontSize: '8pt' }}>{c.date_label}</th>)}
          </tr>
        </thead>
        <tbody>
          <tr>
            <td style={{ ...cellStyle, fontSize: '8pt', textAlign: 'left', fontWeight: 600 }}>Indigenous</td>
            {stock_cols.map((c, i) => <td key={i} style={{ ...cellStyle, fontSize: '8pt' }}>{fmt0(c.indigenous)}</td>)}
          </tr>
          <tr>
            <td style={{ ...cellStyle, fontSize: '8pt', textAlign: 'left', fontWeight: 600 }}>Imported</td>
            {stock_cols.map((c, i) => <td key={i} style={{ ...cellStyle, fontSize: '8pt' }}>{fmt0(c.imported)}</td>)}
          </tr>
          <tr style={{ fontWeight: 700 }}>
            <td style={{ ...cellStyle, fontSize: '8pt', textAlign: 'left' }}>Total</td>
            {stock_cols.map((c, i) => <td key={i} style={{ ...cellStyle, fontSize: '8pt' }}>{fmt0(c.total)}</td>)}
          </tr>
        </tbody>
      </table>

      <div style={{ fontSize: '7.5pt', marginTop: 6, color: NOTE_COLOR }}>
        Note: The above information is based on reports from Plants/CCSO and is provisional
      </div>
    </div>
  );
}
