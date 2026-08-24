'use client';

import React from 'react';

// Mirrors backend/page_templates/sail_mines.html section-for-section — see
// backend/page_sail_mines.py's module docstring for the full section
// registry (6 tables: Iron Ore Production+Despatch (merged), Sales of Iron
// Ore, Coal Mines Production, Washery, Coal Despatch, Flux Production+
// Despatch (merged, at the bottom)) and how each row's APP/Actual/
// %Fulfillment/CPLY/%Growth (or, for despatch/sales tables, just Actual/
// CPLY/%Growth) is computed.
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
  const { title = '', period_label: periodLabel, unit, tables = [], mines_chart_svg: chartSvg } = data || {};
  const byKey = Object.fromEntries(tables.map((t) => [t.key, t]));

  return (
    <div style={{ fontFamily: 'inherit' }}>
      <div style={{ textAlign: 'center', fontWeight: 700, fontSize: '11pt', textDecoration: 'underline', marginBottom: 6, color: C.textDarkGray }}>
        {title}
      </div>
      <div style={{ textAlign: 'right', fontSize: '8pt', fontStyle: 'italic', color: C.textSecondary, marginBottom: 6 }}>
        {periodLabel} &nbsp;|&nbsp; Unit: {unit} (Washery Yield in %)
      </div>

      {/* Iron Ore Production+Despatch — full-width 11-column table, unchanged. */}
      {byKey.iron_ore_prod && <Table table={byKey.iron_ore_prod} />}

      {/* The four plain 6-column tables share one fixed, equal width on the
          left (left-aligned, truncated at the same right edge rather than
          each stretching to fill the full page width) — the freed-up space
          on the right holds a mines-performance chart (illustrative only
          for now — see page_sail_mines.py's _mines_performance_chart_svg). */}
      <div style={{ display: 'flex', alignItems: 'flex-start', gap: 10 }}>
        <div style={{ flex: '0 0 60%', maxWidth: '60%' }}>
          {byKey.iron_ore_sales && <Table table={byKey.iron_ore_sales} />}
          {byKey.coal_prod && <Table table={byKey.coal_prod} />}
          {byKey.washery && <Table table={byKey.washery} />}
          {byKey.coal_despatch && <Table table={byKey.coal_despatch} />}
        </div>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ fontWeight: 700, fontSize: '9.5pt', margin: '6px 0 4px' }}>
            Mines Performance{' '}
            <span style={{ fontWeight: 400, fontStyle: 'italic', fontSize: '7.5pt', color: C.textSecondary }}>
              (illustrative — pending data)
            </span>
          </div>
          {chartSvg && <div dangerouslySetInnerHTML={{ __html: chartSvg }} />}
        </div>
      </div>

      {/* Flux Production+Despatch — merged the same way as Iron Ore, moved
          to the bottom of the page. */}
      {byKey.flux_prod && <Table table={byKey.flux_prod} />}
    </div>
  );
}

const thtd = { border: `1px solid ${C.borderDark}`, padding: '2px 5px', textAlign: 'center' };
