'use client';

import React from 'react';

// Mirrors backend/page_templates/sail_mines.html section-for-section — see
// backend/page_sail_mines.py's module docstring for the full section
// registry (7 tables: Iron Ore Production/Sales, Coal Mines Production,
// Washery, Coal Despatch, Flux Production/Despatch) and how each row's
// APP/Actual/%Fulfillment/CPLY/%Growth (or, for despatch/sales tables,
// just Actual/CPLY/%Growth) is computed.
const C = {
  textDarkGray: '#333333',
  textSecondary: '#475569',
  borderDark: '#334155',
};

function Table({ table }) {
  const isProdDespatch = table.kind === 'production_despatch';
  return (
    <>
      <div style={{ fontWeight: 700, fontSize: '9.5pt', margin: '6px 0 4px' }}>{table.title}</div>
      <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '8pt', marginBottom: 8 }}>
        <thead>
          {isProdDespatch ? (
            <>
              <tr>
                <th rowSpan={2} style={{ ...thtd, textAlign: 'left', fontWeight: 700 }}>Item</th>
                {table.column_groups.map((grp, i) => (
                  <th key={grp.label} colSpan={grp.columns.length}
                      style={{ ...thtd, fontWeight: 700, ...(i > 0 ? { borderLeft: `1.5px solid ${C.borderDark}` } : {}) }}>
                    {grp.label}
                  </th>
                ))}
              </tr>
              <tr>
                {table.column_groups.map((grp, gi) => grp.columns.map((c, ci) => (
                  <th key={`${grp.label}-${c}`}
                      style={{ ...thtd, fontWeight: 700, ...(gi > 0 && ci === 0 ? { borderLeft: `1.5px solid ${C.borderDark}` } : {}) }}>
                    {c}
                  </th>
                )))}
              </tr>
            </>
          ) : (
            <tr>
              <th style={{ ...thtd, textAlign: 'left', fontWeight: 700 }}>Item</th>
              {table.columns.map((c) => <th key={c} style={{ ...thtd, fontWeight: 700 }}>{c}</th>)}
            </tr>
          )}
        </thead>
        <tbody>
          {table.rows.map((r) => (
            <tr key={r.label} style={r.bold ? { fontWeight: 700 } : undefined}>
              <td style={{ ...thtd, textAlign: 'left', fontWeight: 600 }}>{r.label}</td>
              {isProdDespatch ? (
                <>
                  <td style={thtd}>{r.app ?? '—'}</td>
                  <td style={thtd}>{r.actual ?? '—'}</td>
                  <td style={thtd}>{r.pct_ful != null ? `${r.pct_ful}%` : '—'}</td>
                  <td style={thtd}>{r.cply ?? '—'}</td>
                  <td style={thtd}>{r.pct_growth != null ? `${r.pct_growth}%` : '—'}</td>
                  <td style={{ ...thtd, borderLeft: `1.5px solid ${C.borderDark}` }}>{r.d_app ?? '—'}</td>
                  <td style={thtd}>{r.d_actual ?? '—'}</td>
                  <td style={thtd}>{r.d_pct_ful != null ? `${r.d_pct_ful}%` : '—'}</td>
                  <td style={thtd}>{r.d_cply ?? '—'}</td>
                  <td style={thtd}>{r.d_pct_growth != null ? `${r.d_pct_growth}%` : '—'}</td>
                </>
              ) : table.kind === 'production' ? (
                <>
                  <td style={thtd}>{r.app ?? '—'}</td>
                  <td style={thtd}>{r.actual ?? '—'}</td>
                  <td style={thtd}>{r.pct_ful != null ? `${r.pct_ful}%` : '—'}</td>
                  <td style={thtd}>{r.cply ?? '—'}</td>
                  <td style={thtd}>{r.pct_growth != null ? `${r.pct_growth}%` : '—'}</td>
                </>
              ) : (
                <>
                  <td style={thtd}>{r.actual ?? '—'}</td>
                  <td style={thtd}>{r.cply ?? '—'}</td>
                  <td style={thtd}>{r.pct_growth != null ? `${r.pct_growth}%` : '—'}</td>
                </>
              )}
            </tr>
          ))}
        </tbody>
      </table>
    </>
  );
}

export default function SailMinesTemplate({ data }) {
  const { title = '', period_label: periodLabel, unit, tables = [] } = data || {};
  return (
    <div style={{ fontFamily: 'inherit' }}>
      <div style={{ textAlign: 'center', fontWeight: 700, fontSize: '11pt', textDecoration: 'underline', marginBottom: 6, color: C.textDarkGray }}>
        {title}
      </div>
      <div style={{ textAlign: 'right', fontSize: '8pt', fontStyle: 'italic', color: C.textSecondary, marginBottom: 6 }}>
        {periodLabel} &nbsp;|&nbsp; Unit: {unit} (Washery Yield in %)
      </div>

      {tables.map((t) => <Table key={t.key} table={t} />)}

      <div style={{ fontSize: '7.5pt', marginTop: 6, color: C.textSecondary }}>
        Cumulative figures for {periodLabel}. APP = Annual Plan (year-to-date); CPLY = Corresponding Period Last Year.
        Iron Ore Production&apos;s SAIL row is its own reported figure, not a sum of CGoM/OGoM/JGoM. Coal Mines Production&apos;s
        Total and Washery&apos;s Yield (Clean Coal/Raw Coal) rows are computed from the rows above them.
      </div>
    </div>
  );
}

const thtd = { border: `1px solid ${C.borderDark}`, padding: '2px 5px', textAlign: 'center' };
