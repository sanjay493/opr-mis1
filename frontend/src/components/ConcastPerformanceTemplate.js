import React from 'react';

const BOLD_PLANTS = new Set(['5 Plants', 'SAIL']);

function PlantRow({ row, valueKeys }) {
  const isBold = BOLD_PLANTS.has(row.plant);
  const bg =
    row.plant === 'SAIL'      ? '#dcfce7' :
    row.plant === '5 Plants'  ? '#fef9c3' : 'white';

  return (
    <tr style={{ background: bg, fontWeight: isBold ? 700 : 400 }}>
      <td style={{ padding: '2px 4px', border: '1px solid #cbd5e1', fontWeight: isBold ? 700 : 500, fontSize: 'var(--report-font-size)' }}>
        {row.plant}
      </td>
      <td style={{ padding: '2px 4px', border: '1px solid #cbd5e1', textAlign: 'right', fontSize: 'var(--report-font-size)', background: '#dbeafe' }}>
        {row.ann_plan}
      </td>
      {valueKeys.map((k, i) => (
        <td
          key={k}
          style={{
            padding: '2px 4px',
            border: '1px solid #cbd5e1',
            textAlign: 'right',
            fontSize: 'var(--report-font-size)',
            background: i === 1 ? '#d1fae5' : 'inherit',
          }}
        >
          {row[k]}
        </td>
      ))}
    </tr>
  );
}

function ConcastTable({ rows, colHeaders, valueKeys, periodLabel, prevLabel, fy }) {
  return (
    <table style={{ width: '100%', borderCollapse: 'collapse', tableLayout: 'fixed', marginBottom: '14pt' }}>
      <colgroup>
        <col style={{ width: '12%' }} />
        <col style={{ width: '12%' }} />
        <col style={{ width: '11%' }} />
        <col style={{ width: '11%' }} />
        <col style={{ width: '7%' }} />
        <col style={{ width: '11%' }} />
        <col style={{ width: '11%' }} />
      </colgroup>
      <thead>
        <tr style={{ background: '#fff', color: '#000' }}>
          <th rowSpan={2} style={thStyle}>PLANT</th>
          <th rowSpan={2} style={thStyle}>{fy}<br />Plan</th>
          <th colSpan={3} style={thStyle}>{periodLabel}</th>
          <th rowSpan={2} style={thStyle}>{prevLabel}<br />Actual</th>
          <th rowSpan={2} style={thStyle}>% Growth over<br />{prevLabel}</th>
        </tr>
        <tr style={{ background: '#fff', color: '#000' }}>
          {colHeaders.map((h) => (
            <th key={h} style={{ ...thStyle, background: '#fff' }}>{h}</th>
          ))}
        </tr>
      </thead>
      <tbody>
        {rows.map((row, i) => (
          <PlantRow key={i} row={row} valueKeys={valueKeys} />
        ))}
      </tbody>
    </table>
  );
}

const thStyle = {
  padding: '3px 4px',
  fontSize: 'var(--report-font-size)',
  border: '1px solid #94a3b8',
  verticalAlign: 'middle',
  textAlign: 'center',
};

export default function ConcastPerformanceTemplate({ data, selectedMonth }) {
  const { monthly = [], ytd = [], title = 'CONCAST PRODUCTION PERFORMANCE' } = data || {};

  // Derive labels from selectedMonth (e.g. "2026-03")
  const monthNames = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
  let shortM = 'Mar', shortY = '26', shortPrevY = '25', fyStr = '2025-26';
  if (selectedMonth && selectedMonth.length >= 7) {
    const yr = parseInt(selectedMonth.slice(0, 4));
    const mo = parseInt(selectedMonth.slice(5, 7));
    shortM    = monthNames[mo - 1];
    shortY    = String(yr).slice(2);
    shortPrevY = String(yr - 1).slice(2);
    const fyStart = mo >= 4 ? yr : yr - 1;
    fyStr = `${fyStart}-${String(fyStart + 1).slice(2)}`;
  }

  const monthLabel   = `${shortM}'${shortY}`;
  const prevMLabel   = `${shortM}'${shortPrevY}`;
  const ytdLabel     = `Apr-${shortM}'${shortY}`;
  const prevYtdLabel = `Apr-${shortM}'${shortPrevY}`;

  return (
    <div style={{ fontFamily: "'Roboto', Arial, Helvetica, sans-serif" }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-end', marginBottom: '6px' }}>
        <h2 style={{ fontSize: '13pt', fontWeight: 700, color: '#060177', margin: 0, textTransform: 'uppercase' }}>
          {title} – {monthLabel}
        </h2>
        <span style={{ fontSize: '8.5pt', color: '#475569', fontWeight: 500 }}>Unit: Tonnes</span>
      </div>

      <ConcastTable
        rows={monthly}
        colHeaders={['Plan', 'Actual', '% Ful.']}
        valueKeys={['m_plan', 'm_act', 'm_pct', 'cply_act', 'm_growth']}
        periodLabel={monthLabel}
        prevLabel={prevMLabel}
        fy={fyStr}
      />

      <ConcastTable
        rows={ytd}
        colHeaders={['Plan', 'Actual', '% Ful.']}
        valueKeys={['ytd_plan', 'ytd_act', 'ytd_pct', 'ytd_cply', 'ytd_growth']}
        periodLabel={ytdLabel}
        prevLabel={prevYtdLabel}
        fy={fyStr}
      />
    </div>
  );
}
