import React from 'react';

// Mirrors backend/page_templates/best_ever_highlights.html section-for-section
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
  bestEverBg: '#fde68a',
  khvAssessmentAmber: '#d97706',
};

const PERIOD_COLS = [
  { key: 'month', label: 'Best Month' },
  { key: 'quarter', label: 'Best Quarter' },
  { key: 'half', label: 'Best Half' },
  { key: 'fy', label: 'Best Financial Year' },
  { key: 'cy', label: 'Best Calendar Year' },
];

function fmt(v) {
  return v == null ? '—' : v.toFixed(3);
}

function RecordCell({ rec }) {
  const best = rec?.best ?? null;
  const second = rec?.second ?? null;
  const fresh = best?.fresh;
  return (
    <td style={{
      textAlign: 'center', verticalAlign: 'top', padding: '6px 7px',
      borderTop: `1px solid ${C.borderDivider}`, borderLeft: `1px solid ${C.borderDivider}`,
      ...(fresh && { background: C.bestEverBg }),
    }}>
      {best == null ? (
        <span style={{ color: C.textFaint }}>—</span>
      ) : (
        <>
          {fresh && (
            <div style={{
              display: 'inline-block', marginBottom: 1, padding: '0 4px', borderRadius: 6,
              background: C.khvAssessmentAmber, color: C.textWhite, fontSize: '5.6pt', fontWeight: 800,
            }}>★ NEW</div>
          )}
          <div style={{ fontSize: '10.5pt', fontWeight: 700, color: C.textPrimary }}>{fmt(best.total)}</div>
          <div style={{ fontSize: '6.4pt', color: C.textSecondary }}>{best.period}</div>
          {second != null && (
            <div style={{
              marginTop: 2, paddingTop: 2, borderTop: `1px dashed ${C.borderDivider}`,
              fontSize: '6.4pt', color: C.textSecondary,
            }}>
              <span style={{ fontWeight: 700 }}>2nd · {fmt(second.total)}</span><br />
              <span style={{ fontSize: '6pt' }}>{second.period}</span>
            </div>
          )}
        </>
      )}
    </td>
  );
}

function GroupTable({ group, first }) {
  return (
    <>
      <div style={{
        fontSize: '9.5pt', fontWeight: 700, color: C.textHeadingDark, textTransform: 'uppercase',
        marginBottom: 2, marginTop: first ? 0 : 8,
      }}>{group.label}</div>
      <table style={{
        width: '100%', borderCollapse: 'collapse', tableLayout: 'fixed',
        border: `1px solid ${C.borderLight}`, borderRadius: 4, overflow: 'hidden',
      }}>
        <thead>
          <tr>
            <th style={{ width: '15%', textAlign: 'left', background: C.accentBlue, color: C.textWhite, fontSize: '7.5pt', fontWeight: 700, padding: '6px 10px' }}>Item</th>
            {PERIOD_COLS.map(({ key, label }) => (
              <th key={key} style={{ width: '17%', textAlign: 'center', background: C.accentBlue, color: C.textWhite, fontSize: '7.5pt', fontWeight: 700, padding: '6px 8px' }}>{label}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {group.rows.map((row, i) => (
            <tr key={row.key} style={{ background: i % 2 === 0 ? C.textWhite : C.highlightsBoxBg }}>
              <td style={{ textAlign: 'left', fontWeight: 700, color: C.textHeadingDark, padding: '6px 10px', borderTop: `1px solid ${C.borderDivider}`, fontSize: '7.3pt' }}>{row.label}</td>
              {PERIOD_COLS.map(({ key }) => <RecordCell key={key} rec={row.periods[key]} />)}
            </tr>
          ))}
        </tbody>
      </table>
    </>
  );
}

export default function BestEverHighlightsTemplate({ data }) {
  if (!data) return null;
  const { title, month_label: monthLabel, groups = [], latest_month: latestMonth } = data;

  return (
    <div style={{ padding: '2px 4px', fontFamily: "'Arial Narrow', Arial, sans-serif", fontSize: '7.5pt', color: C.textPrimary }}>
      <div style={{ background: `linear-gradient(to right, ${C.textWhite}, ${C.accentBlue})`, padding: 2, borderRadius: 6, marginBottom: 5 }}>
        <div style={{ background: `linear-gradient(to right, ${C.accentBlue}, ${C.textWhite})`, color: C.textWhite, padding: '4px 14px', borderRadius: 5, display: 'flex', alignItems: 'baseline', justifyContent: 'space-between', gap: 10 }}>
          <div style={{ fontSize: '15pt', fontWeight: 700 }}>{title}</div>
          <div style={{ fontSize: '9.5pt', fontWeight: 700, color: C.khvAssessmentAmber, whiteSpace: 'nowrap' }}>{monthLabel}</div>
        </div>
      </div>

      {groups.map((g, i) => <GroupTable key={g.key} group={g} first={i === 0} />)}

      <div style={{ marginTop: 6, fontSize: '6pt', color: C.textSecondary, lineHeight: 1.5 }}>
        All-time records from production_table (since Apr 2000), in &apos;000 tonnes. Quarters/halves/years count only complete periods (3, 6 or 12 months of data).
        Each cell shows the all-time best and, where one exists, the 2nd-best of that period type.{' '}
        <span style={{ display: 'inline-block', padding: '0 4px', borderRadius: 6, background: C.khvAssessmentAmber, color: C.textWhite, fontSize: '5.6pt', fontWeight: 800 }}>★ NEW</span>
        {' '}marks a record set within the last 3 months of available data ({latestMonth}). SAIL (5 Plants) = BSP, DSP, RSP, BSL, ISP; SAIL (8 Plants) adds ASP, SSP, VISL.
      </div>
    </div>
  );
}
