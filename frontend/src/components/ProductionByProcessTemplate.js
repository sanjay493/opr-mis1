import React from 'react';

const MONTH_NAMES = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];

function deriveLabels(selectedMonth) {
  if (!selectedMonth || selectedMonth.length < 7) {
    return { shortM: 'Mar', shortY: '26', shortPrevY: '25' };
  }
  const yr = parseInt(selectedMonth.slice(0, 4));
  const mo = parseInt(selectedMonth.slice(5, 7));
  return {
    shortM:    MONTH_NAMES[mo - 1],
    shortY:    String(yr).slice(2),
    shortPrevY: String(yr - 1).slice(2),
  };
}

const th = {
  padding: '2px 3px',
  fontSize: 'var(--report-font-size)',
  lineHeight: 1.15,
  textAlign: 'center',
  verticalAlign: 'middle',
  border: '1px solid #94a3b8',
};

const td = (extra = {}) => ({
  padding: '2px 3px',
  fontSize: 'var(--report-font-size)',
  lineHeight: 1.15,
  textAlign: 'right',
  border: '1px solid #cbd5e1',
  ...extra,
});

const PLANT_COL = { width: '9%' };
const DATA_COL  = { width: '7%' };
const SMALL_COL = { width: '6%' };

const CC_BG  = '#d1fae5';
const CS_BG  = '#dbeafe';
const SEP    = '2.5px solid #1e293b';

function rowStyle(plant, bold) {
  if (plant === 'SAIL')    return { background: '#dcfce7', fontWeight: 700 };
  if (bold)                return { background: '#fef9c3', fontWeight: 700 };
  return {};
}

function ProcessTable({ curRows, prevRows, periodCur, periodPrev }) {
  return (
    <table style={{
      tableLayout: 'fixed', width: '100%', borderCollapse: 'collapse',
      border: '2px solid #1e293b', marginBottom: '10pt',
    }}>
      <colgroup>
        <col style={PLANT_COL} />
        {/* current period */}
        <col style={DATA_COL} /><col style={SMALL_COL} /><col style={DATA_COL} />
        <col style={DATA_COL} /><col style={DATA_COL} /><col style={DATA_COL} />
        {/* previous period */}
        <col style={DATA_COL} /><col style={SMALL_COL} /><col style={DATA_COL} />
        <col style={DATA_COL} /><col style={DATA_COL} /><col style={DATA_COL} />
      </colgroup>
      <thead>
        <tr style={{ color: 'black' }}>
          <th rowSpan={2} style={th}>PLANT</th>
          <th colSpan={6} style={th}>{periodCur}</th>
          <th colSpan={6} style={{ ...th, borderLeft: SEP }}>{periodPrev}</th>
        </tr>
        <tr style={{ color: 'black' }}>
          <th style={th}>BOF</th>
          <th style={th}>EAF</th>
          <th style={{ ...th, color: '#064e3b' }}>CC</th>
          <th style={{ ...th, color: '#1e40af' }}>CS</th>
          <th style={th}>BOF<br/>%CS</th>
          <th style={th}>CC<br/>%CS</th>
          <th style={{ ...th, borderLeft: SEP }}>BOF</th>
          <th style={th}>EAF</th>
          <th style={{ ...th, color: '#064e3b' }}>CC</th>
          <th style={{ ...th, color: '#1e40af' }}>CS</th>
          <th style={th}>BOF<br/>%CS</th>
          <th style={th}>CC<br/>%CS</th>
        </tr>
      </thead>
      <tbody>
        {curRows.map((row, i) => {
          const pr = prevRows[i] || {};
          const rs = rowStyle(row.plant, row.bold);
          return (
            <tr key={i} style={rs}>
              <td style={td({ textAlign: 'left', fontWeight: 600, background: rs.background || '#f8fafc' })}>
                {row.plant}
              </td>
              <td style={td()}>{row.bof}</td>
              <td style={td()}>{row.eaf}</td>
              <td style={td({ background: CC_BG })}>{row.cc}</td>
              <td style={td({ background: CS_BG })}>{row.cs}</td>
              <td style={td()}>{row.bof_pct}</td>
              <td style={td()}>{row.cc_pct}</td>
              <td style={td({ borderLeft: SEP })}>{pr.bof}</td>
              <td style={td()}>{pr.eaf}</td>
              <td style={td({ background: CC_BG })}>{pr.cc}</td>
              <td style={td({ background: CS_BG })}>{pr.cs}</td>
              <td style={td()}>{pr.bof_pct}</td>
              <td style={td()}>{pr.cc_pct}</td>
            </tr>
          );
        })}
      </tbody>
    </table>
  );
}

export default function ProductionByProcessTemplate({ data, selectedMonth }) {
  const {
    title = 'PRODUCTION BY PROCESS',
    monthly      = [],
    monthly_prev = [],
    ytd          = [],
    ytd_prev     = [],
  } = data || {};

  const { shortM, shortY, shortPrevY } = deriveLabels(selectedMonth);

  return (
    <div style={{ fontFamily: "'Roboto', Arial, Helvetica, sans-serif" }}>
      <div style={{
        display: 'flex', justifyContent: 'space-between', alignItems: 'flex-end',
        borderBottom: '1.5px solid #0f172a', paddingBottom: '3px', marginBottom: '6px',
      }}>
        <h2 style={{ fontSize: '12pt', fontWeight: 700, color: '#060177', margin: 0, textTransform: 'uppercase' }}>
          {title}
        </h2>
        <span style={{ fontSize: '8pt', color: '#475569', fontWeight: 500 }}>Unit: Tonnes</span>
      </div>

      <ProcessTable
        curRows={monthly}
        prevRows={monthly_prev}
        periodCur={`${shortM}'${shortY}`}
        periodPrev={`${shortM}'${shortPrevY}`}
      />

      <ProcessTable
        curRows={ytd}
        prevRows={ytd_prev}
        periodCur={`Apr-${shortM}'${shortY}`}
        periodPrev={`Apr-${shortM}'${shortPrevY}`}
      />
    </div>
  );
}
