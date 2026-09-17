'use client';

import React from 'react';

// Mirrors backend/page_templates/market_prices.html — see
// backend/page_market_prices.py for the series registry. Genuine
// A4-landscape page (spliced in by pdf.py's _LANDSCAPE_TYPES handling).
// The two chart SVGs are already fully built server-side (same string
// embedded verbatim in the PDF template) — this component just lays them
// out in a card, same as SailMinesTemplate.js does for its own SVG charts.

export default function MarketPricesTemplate({ data }) {
  const {
    title = '', unit = '', source = '', period_label: periodLabel = '',
    raw_materials_svg: rawSvg = '', finished_steel_svg: finishedSvg = '',
  } = data || {};

  return (
    <div style={{ fontFamily: 'inherit', color: '#333333' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', marginBottom: 6 }}>
        <div style={{ textAlign: 'center', fontWeight: 700, fontSize: '11pt', textDecoration: 'underline', color: 'rgb(0,0,255)' }}>
          {title}
        </div>
        <div style={{ fontSize: '9pt', fontStyle: 'italic', color: '#5f6368' }}>( {unit} )</div>
      </div>

      <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
        <div style={{ width: '100%', boxSizing: 'border-box', border: '1.25pt solid #fed7aa', borderRadius: 4, padding: '8pt 10pt 6pt' }}
             dangerouslySetInnerHTML={{ __html: rawSvg }} />
        <div style={{ width: '100%', boxSizing: 'border-box', border: '1.25pt solid #fed7aa', borderRadius: 4, padding: '8pt 10pt 6pt' }}
             dangerouslySetInnerHTML={{ __html: finishedSvg }} />
      </div>

      <div style={{ textAlign: 'right', fontSize: '7.6pt', fontStyle: 'italic', color: '#5f6368', marginTop: 4 }}>
        {source} &nbsp;·&nbsp; {periodLabel}
      </div>
    </div>
  );
}
