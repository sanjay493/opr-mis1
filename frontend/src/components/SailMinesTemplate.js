'use client';

import React from 'react';

// "SAIL Mines Production & Despatch Performance" — placeholder page (see
// main.py's SAIL_MINES_PAGE_ID / backend/page_sail_mines.py). No mines
// production/despatch data source exists in this app yet — index.txt
// marks this section's content "(empty page contents awaited)" — so this
// is title-only until that data is wired up.
export default function SailMinesTemplate({ data }) {
  const { title = '' } = data || {};
  return (
    <div style={{ fontFamily: 'inherit' }}>
      <div style={{ textAlign: 'center', fontWeight: 700, fontSize: '11pt', textDecoration: 'underline', marginBottom: 6, color: '#333333' }}>
        {title}
      </div>
      <div style={{ padding: '40px 20px', textAlign: 'center', color: '#64748b', fontSize: '9pt' }}>
        Content pending — data source not yet available.
      </div>
    </div>
  );
}
