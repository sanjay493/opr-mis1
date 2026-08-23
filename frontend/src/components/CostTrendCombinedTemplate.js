'use client';

import React from 'react';
import { CostTrendProduct } from './CostTrendTemplate';

// Mirrors backend/page_templates/cost_trend_combined.html — Crude Steel +
// Saleable Steel Cost Trend sharing one physical page (Hot Metal stays on
// its own page, see CostTrendTemplate). Reuses CostTrendProduct with
// compact=true for both.
const BORDER_LIGHT = '#cbd5e1';
const TEXT_SECONDARY = '#475569';

export default function CostTrendCombinedTemplate({ data }) {
  const pages = data?.pages || [];
  return (
    <div style={{ padding: 4, fontFamily: 'Arial, sans-serif', fontSize: '8pt' }}>
      {pages.map((p, i) => (
        <React.Fragment key={i}>
          <CostTrendProduct page={p} compact={true} />
          {i < pages.length - 1 && (
            <div style={{ borderTop: `1px solid ${BORDER_LIGHT}`, margin: '5px 0 9px 0' }} />
          )}
        </React.Fragment>
      ))}
      <div style={{ fontSize: '7.5pt', fontStyle: 'italic', color: TEXT_SECONDARY, marginTop: 4 }}>
        (-) indicates decrease in cost
      </div>
    </div>
  );
}
