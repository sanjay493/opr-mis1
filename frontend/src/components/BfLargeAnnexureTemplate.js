'use client';

import React from 'react';

// Mirrors backend/page_templates/bf_large_annexure.html — SAIL's 3 largest
// BFs (Previous FY / Month / YTD columns) vs non-SAIL BFs (Previous FY
// only — no monthly data exists for them). See page_bf_large_annexure.py
// for exactly what each row reads from and why the columns don't match the
// source Excel's own hand-built month-by-month layout.
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
  const { title, prev_fy_label = '', month_label = '', sail_cols = [], non_sail_cols = [], rows = [] } = data;

  return (
    <div style={{ padding: '8px', fontFamily: 'Arial, sans-serif', fontSize: '0.6rem' }}>
      <div style={{ textAlign: 'center', fontWeight: 700, fontSize: '0.95rem', marginBottom: 2 }}>
        {title}
      </div>
      <div style={{ textAlign: 'center', fontSize: '0.7rem', color: '#64748b', marginBottom: 8 }}>
        Previous FY: {prev_fy_label} &middot; Month: {month_label} &middot; YTD: Apr-{month_label}
      </div>

      <div style={{ overflowX: 'auto' }}>
        <table style={{ borderCollapse: 'collapse', border: '1px solid #1e293b', fontSize: '0.6rem' }}>
          <thead>
            <tr>
              <th rowSpan={2} style={{ ...TH, textAlign: 'left' }}>Parameter</th>
              <th rowSpan={2} style={TH}>Unit</th>
              {sail_cols.map((bf) => <th key={bf} colSpan={3} style={TH}>{bf}</th>)}
              {non_sail_cols.map((bf) => (
                <th key={bf} rowSpan={2} style={{ ...TH, writingMode: 'vertical-rl' }}>{bf}</th>
              ))}
            </tr>
            <tr>
              {sail_cols.map((bf) => (
<React.Fragment key={bf}>
                  <th style={TH}>Prev FY</th>
                  <th style={TH}>Month</th>
                  <th style={TH}>YTD</th>
                </React.Fragment>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((row, ri) => (
              <tr key={ri} style={{ backgroundColor: ri % 2 ? '#f8fafc' : '#fff' }}>
                <td style={LBL}>{row.parameter}</td>
                <td style={{ ...CELL, textAlign: 'center', fontStyle: 'italic', color: '#475569' }}>{row.unit}</td>
                {sail_cols.map((bf) => {
                  const v = row.sail[bf] || {};
                  return (
                    <React.Fragment key={bf}>
                      <td style={NUM}>{v.prev_fy ?? '—'}</td>
                      <td style={NUM}>{v.month ?? '—'}</td>
                      <td style={NUM}>{v.ytd ?? '—'}</td>
                    </React.Fragment>
                  );
                })}
                {non_sail_cols.map((bf) => (
                  <td key={bf} style={NUM}>{row.non_sail[bf] ?? '—'}</td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div style={{ fontSize: '0.55rem', color: '#475569', marginTop: 4 }}>
        Non-SAIL BFs show Previous FY only (no monthly figures are tracked for them). Blank cells (&ldquo;—&rdquo;)
        have no data uploaded/entered yet for that plant/period — see <a href="/data-entry/bf-large-manual" style={{ color: '#1a73e8' }}>BF Large Manual Entry</a>.
      </div>
    </div>
  );
}
