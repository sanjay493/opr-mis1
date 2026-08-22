import React from 'react';

// Mirrors backend/page_templates/best_calendar_month.html section-for-section
// (this codebase's React templates don't import colors_config.json — every
// other *Template.js hardcodes its own copy of the relevant hex values).
const C = {
  accentBlue: '#0284c7',
  textPrimary: '#0f172a',
  textSecondary: '#475569',
  textWhite: '#ffffff',
  textHeadingDark: '#1e293b',
  textFaint: '#94a3b8',
  borderLight: '#cbd5e1',
  borderDivider: '#e2e8f0',
  highlightsBoxBg: '#f8fafc',
  khvAssessmentAmber: '#d97706',
  khvAssessmentRed: '#dc2626',
  steelBlue: '#4682b4',
};

function fmt0(v) {
  return v == null ? '—' : Math.round(v).toString();
}

function MonthCell({ cell }) {
  if (!cell) return <td style={{ textAlign: 'center', padding: '3px 2px', borderTop: `1px solid ${C.borderDivider}`, borderLeft: `1px solid ${C.borderDivider}` }}><span style={{ color: C.textFaint, fontSize: '10pt' }}>—</span></td>;
  const { best, second } = cell;
  return (
    <td style={{
      textAlign: 'center', verticalAlign: 'top', padding: '3px 2px',
      borderTop: `1px solid ${C.borderDivider}`, borderLeft: `1px solid ${C.borderDivider}`,
    }}>
      <span style={{ fontSize: '10pt', fontWeight: 800, color: best.is_all_time_best ? C.khvAssessmentRed : C.steelBlue }}>
        {fmt0(best.total)}{best.is_all_time_best ? ' ★' : ''}
      </span>
      <div style={{ fontSize: '10pt', fontStyle: 'italic', fontWeight: 700, color: C.textSecondary, opacity: 0.85 }}>[{best.year}]</div>
      {second != null && (
        <>
          <div style={{ marginTop: 2, paddingTop: 2, borderTop: `1px dashed ${C.borderDivider}`, fontSize: '10pt', color: C.textSecondary }}>
            {fmt0(second.total)}
          </div>
          <div style={{ fontSize: '10pt', fontStyle: 'italic', color: C.textSecondary }}>[{second.year}]</div>
        </>
      )}
    </td>
  );
}

function GroupTable({ group, monthNames, first }) {
  return (
    <>
      <div style={{
        fontSize: '10pt', fontWeight: 700, color: C.textHeadingDark, textTransform: 'uppercase',
        marginBottom: 2, marginTop: first ? 0 : 8,
      }}>{group.label}</div>
      <table style={{
        width: '100%', borderCollapse: 'collapse', tableLayout: 'fixed',
        border: `1px solid ${C.borderLight}`, borderRadius: 4, overflow: 'hidden',
      }}>
        <thead>
          <tr>
            <th style={{ width: '11%', textAlign: 'left', background: C.accentBlue, color: C.textWhite, fontSize: '10pt', fontWeight: 700, padding: '4px 6px' }}>Item</th>
            {monthNames.map((m) => (
              <th key={m} style={{ textAlign: 'center', background: C.accentBlue, color: C.textWhite, fontSize: '10pt', fontWeight: 700, padding: '4px 3px' }}>{m}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {group.rows.map((row, i) => (
            <tr key={row.key} style={{ background: i % 2 === 0 ? C.textWhite : C.highlightsBoxBg }}>
              <td style={{ textAlign: 'left', fontWeight: 700, color: C.textHeadingDark, padding: '4px 6px', borderTop: `1px solid ${C.borderDivider}`, fontSize: '10pt' }}>{row.label}</td>
              {Array.from({ length: 12 }, (_, idx) => idx + 1).map((mnum) => (
                <MonthCell key={mnum} cell={row.months[mnum]} />
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </>
  );
}

export default function BestCalendarMonthTemplate({ data }) {
  if (!data) return null;
  const { title, month_label: monthLabel, unit, month_names: monthNames = [], groups = [] } = data;

  return (
    <div style={{ padding: '2px 4px', fontFamily: "'Arial Narrow', Arial, sans-serif", fontSize: '10pt', color: C.textPrimary }}>
      <div style={{ background: `linear-gradient(to right, ${C.textWhite}, ${C.accentBlue})`, padding: 2, borderRadius: 6, marginBottom: 5 }}>
        <div style={{ background: `linear-gradient(to right, ${C.accentBlue}, ${C.textWhite})`, color: C.textWhite, padding: '4px 14px', borderRadius: 5, display: 'flex', alignItems: 'baseline', justifyContent: 'space-between', gap: 10 }}>
          <div style={{ fontSize: '15pt', fontWeight: 700 }}>{title}</div>
          <div style={{ fontSize: '10pt', fontWeight: 700, color: C.khvAssessmentAmber, whiteSpace: 'nowrap' }}>{monthLabel}</div>
        </div>
      </div>

      <div style={{ textAlign: 'right', fontSize: '10pt', fontWeight: 700, fontStyle: 'italic', color: C.textSecondary, marginBottom: 4 }}>Unit: {unit}</div>

      {groups.map((g, i) => <GroupTable key={g.key} group={g} monthNames={monthNames} first={i === 0} />)}

      <div style={{ marginTop: 6, fontSize: '6pt', color: C.textSecondary, lineHeight: 1.5 }}>
        Best and 2nd-best ever figure for every calendar month.{' '}
        <span style={{ color: C.khvAssessmentAmber, fontWeight: 800 }}>★</span> marks the single all-time-best month for that item (across all 12 calendar months).
        SAIL (5 Plants) = BSP, DSP, RSP, BSL, ISP; SAIL (8 Plants) adds ASP, SSP, VISL and is shown for Crude Steel, Finished Steel and Saleable Steel only.
      </div>
    </div>
  );
}
