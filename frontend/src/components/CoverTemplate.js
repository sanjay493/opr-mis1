import React from 'react';

export default function CoverTemplate({ data }) {
  const { title, subtitle, date } = data || {};
  return (
    <div className="page1-container">
      <div className="page1-accent"></div>
      <h1 className="page1-title">{title || "OPERATIONS MONTHLY INFORMATICS"}</h1>
      <p className="page1-subtitle">{subtitle || "O P E R A T I O N S   D I R E C T O R A T E"}</p>
      <div className="page1-meta">
        <div>
          <strong>Prepared By:</strong>
          <div style={{ marginTop: '4px' }}>MIS Group</div>
        </div>
        <div>
          <strong>Report Month:</strong>
          <div style={{ marginTop: '4px' }}>{date || "NOVEMBER 2025"}</div>
        </div>
      </div>
    </div>
  );
}
