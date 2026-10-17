'use client';

import React from 'react';

// Mirrors backend/page_templates/steel_sales_performance.html — report-month
// and YTD bullet lists in full page width. The first bullet of each section
// is an emphasis banner; bullets may carry embedded newlines (extra lines in
// the same row).
const C = {
  title: 'rgb(0,0,255)',
  navy: '#060177',
  white: '#ffffff',
  headingDark: '#1e293b',
  secondary: '#475569',
};

export default function SteelSalesPerformanceTemplate({ data }) {
  const { title = '', month_heading = '', ytd_heading = '', month_items = [], ytd_items = [] } = data || {};
  const sections = [
    { heading: month_heading, bullets: month_items },
    { heading: ytd_heading, bullets: ytd_items },
  ];

  return (
    <div style={{ padding: '2px 6px' }}>
      <div style={{ textAlign: 'center', fontWeight: 700, fontSize: '15pt', textDecoration: 'underline', color: C.title, marginBottom: 6 }}>
        {title}
      </div>
      {sections.map((sec, si) => (
        <div key={si} style={{ marginBottom: 4 }}>
          <div style={{ fontWeight: 700, fontSize: '11pt', textDecoration: 'underline', color: C.title, marginBottom: 3 }}>
            {sec.heading}
          </div>
          {sec.bullets && sec.bullets.length ? (
            <table style={{ width: '100%', borderCollapse: 'collapse', tableLayout: 'fixed' }}>
              <tbody>
                {sec.bullets.map((item, i) => (
                  <tr key={i}>
                    <td style={{
                      padding: '4px 8px', textAlign: 'left', fontWeight: 700, fontSize: '9.5pt', lineHeight: 1.2,
                      wordWrap: 'break-word',
                      background: i === 0 ? C.navy : undefined,
                      color: i === 0 ? C.white : C.headingDark,
                    }}>
                      {String(item).split('\n').map((line, li) => (
                        <div key={li} style={li ? { marginTop: 1 } : undefined}>{line}</div>
                      ))}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : (
            <div style={{ fontStyle: 'italic', fontSize: '9pt', color: C.secondary, padding: 6 }}>
              No highlights entered for this period yet.
            </div>
          )}
        </div>
      ))}
    </div>
  );
}
