'use client';

import React from 'react';

// Mirrors backend/page_templates/major_unit_records_separator.html — the
// blank "Annexure-III" title page before the Major Units Records plant
// pages; same shape as ReadyReckonerSeparatorTemplate.
export default function MajorUnitRecordsSeparatorTemplate({ data }) {
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
