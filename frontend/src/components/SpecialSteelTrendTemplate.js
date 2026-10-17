'use client';

import React from 'react';

// Mirrors backend/page_templates/special_steel_trend.html — the charts are
// server-rendered SVG strings (page_special_steel_trend.py): one per plant
// for the annual trend, then the report-month and till-month charts.
const C = {
  title: 'rgb(0,0,255)',
  muted: '#64748b',
  headingDark: '#1e293b',
  divider: '#e2e8f0',
};
const box = { border: `0.5px solid ${C.divider}`, borderRadius: 3, padding: 4 };

export default function SpecialSteelTrendTemplate({ data }) {
  const { title = '', fy_range_label = '', annual_svgs = [], month_svg, till_month_svg } = data || {};

  return (
    <div style={{ padding: '4px 8px' }}>
      <div style={{ textAlign: 'center', fontWeight: 700, fontSize: '12pt', marginBottom: 2, color: C.title }}>{title}</div>
      <div style={{ textAlign: 'center', fontSize: '8pt', color: C.muted, marginBottom: 8 }}>{fy_range_label}</div>

      <div style={{ fontSize: '9pt', fontWeight: 700, color: C.headingDark, marginBottom: 3 }}>
        Annual Special Steel Despatch — Last 3 Years + Current FY (Likely) (T &amp; % Special Steel in Total Saleable Steel Despatch)
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 6, marginBottom: 10 }}>
        {annual_svgs.map((svg, i) => (
          <div key={i} style={box} dangerouslySetInnerHTML={{ __html: svg }} />
        ))}
      </div>

      {month_svg && <div style={{ ...box, marginBottom: 8 }} dangerouslySetInnerHTML={{ __html: month_svg }} />}
      {till_month_svg && <div style={box} dangerouslySetInnerHTML={{ __html: till_month_svg }} />}
    </div>
  );
}
