'use client';

import React from 'react';

// Mirrors backend/page_templates/sail8_trend_separator.html — the blank
// "Annexure-4" title page before the SAIL (8 Plants) Production Trend
// content page; same shape as MajorUnitRecordsSeparatorTemplate.
export default function Sail8TrendSeparatorTemplate({ data }) {
  const { annexure_label: annexureLabel, group_label: groupLabel } = data || {};

  return (
    <div style={{ textAlign: 'center', paddingTop: '35%' }}>
      <div style={{ fontWeight: 700, fontSize: '26pt', color: '#000000' }}>
        {annexureLabel}
      </div>
      <div style={{ fontWeight: 700, fontSize: '18pt', color: '#B7410E', marginTop: 10 }}>
        {groupLabel}
      </div>
    </div>
  );
}
