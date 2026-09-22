'use client';

import React from 'react';

// Mirrors backend/page_templates/ready_reckoner_separator.html — a blank
// title page printed right before each Ready Reckoner group's first plant
// page (Annexure-1/5 ISPs, Annexure-2/3 SSPs), per direct instruction,
// 2026-09-21: annexure_label in black, group_label in rust brown on the
// next line, both centered.
export default function ReadyReckonerSeparatorTemplate({ data }) {
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
