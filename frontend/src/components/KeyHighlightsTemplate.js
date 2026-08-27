import React from 'react';
import { chemSub } from '@/lib/chemFormat';

// Mirrors backend/page_templates/key_highlights.html section-for-section —
// see page_key_highlights.py for the data shape. The three narrative
// sections (achievements/shortfalls/focus_areas) are editor-entered, not
// computed — see /data-entry/key-highlights.
const C = {
  textPrimary: '#0f172a',
  textSecondary: '#475569',
  textFaint: '#94a3b8',
  textWhite: '#ffffff',
  textHeadingDark: '#1e293b',
  textVarianceGreen: '#064e3b',
  textVarianceRed: '#9a3412',
  accentBlue: '#0284c7',
  borderLight: '#cbd5e1',
  borderMedium: '#94a3b8',
  borderDivider: '#e2e8f0',
  bannerBg: '#0f2a5c',
  badgeBg: '#0047c8',
  achieveHeaderBg: '#1e7e34',
  achieveBoxBg: '#f0fdf4',
  achieveBoxBorder: '#86efac',
  shortfallHeaderBg: '#b91c1c',
  shortfallBoxBg: '#fef2f2',
  shortfallBoxBorder: '#fca5a5',
  focusHeaderBg: '#0f2a5c',
  focusBoxBg: '#f8fafc',
  vaHeaderBg: '#0369a1',
  vaBoxBg: '#f0f9ff',
  assessGreen: '#16a34a',
  assessAmber: '#d97706',
  assessRed: '#dc2626',
};

function GrowthText({ value, good, suffix = '%' }) {
  if (good === null || good === undefined || !value) return <b>—</b>;
  return <b style={{ color: good ? C.textVarianceGreen : C.textVarianceRed }}>{good ? `+${value}` : value}{suffix}</b>;
}

function KpiStrip({ kpi }) {
  return (
    <div style={{ display: 'flex', gap: 6, marginBottom: 4 }}>
      {kpi.map((row) => (
        <div key={row.item} style={{
          flex: 1, border: `1px solid ${C.borderLight}`, borderLeft: `4px solid ${C.accentBlue}`,
          borderRadius: 4, padding: '4px 9px',
        }}>
          <div style={{ fontSize: '7.2pt', color: C.textSecondary, textTransform: 'uppercase', fontWeight: 700 }}>{chemSub(row.item)}</div>
          <div style={{ fontSize: '14pt', fontWeight: 800, color: C.textPrimary, lineHeight: 1.15 }}>
            {row.value_mt || '—'} <span style={{ fontSize: '7.5pt', fontWeight: 600 }}>MT</span>
          </div>
          <div style={{ fontSize: '7pt', color: C.textSecondary }}>
            {row.pct_app || '—'}% of APP &nbsp;|&nbsp; vs CPLY <GrowthText value={row.growth_cply} good={row.growth_good} />
          </div>
        </div>
      ))}
    </div>
  );
}

function AchievementsBox({ achievements }) {
  return (
    <div style={{ flex: 1, border: `1px solid ${C.achieveBoxBorder}`, background: C.achieveBoxBg, borderRadius: 5, overflow: 'hidden' }}>
      <div style={{ background: C.achieveHeaderBg, color: C.textWhite, fontWeight: 800, fontSize: '7.6pt', padding: '3px 8px', textTransform: 'uppercase' }}>
        Major Achievements
      </div>
      <ul style={{ margin: 0, padding: '5px 10px 5px 16px', listStyle: 'disc' }}>
        {achievements.length === 0 && (
          <li style={{ color: C.textFaint, fontStyle: 'italic', listStyle: 'none', marginLeft: -16 }}>
            No achievements entered for this month yet.
          </li>
        )}
        {achievements.map((a, i) => (
          <li key={i} style={{ marginBottom: 2, fontWeight: 600 }}>
            {a.text}
            {a.subs && a.subs.length > 0 && (
              <ul style={{ margin: '1px 0 2px 12px', listStyle: 'circle', fontWeight: 400 }}>
                {a.subs.map((s, si) => <li key={si} style={{ marginBottom: 1 }}>{s}</li>)}
              </ul>
            )}
          </li>
        ))}
      </ul>
    </div>
  );
}

function ShortfallsBox({ shortfalls }) {
  return (
    <div style={{ flex: 1, border: `1px solid ${C.shortfallBoxBorder}`, background: C.shortfallBoxBg, borderRadius: 5, overflow: 'hidden' }}>
      <div style={{ background: C.shortfallHeaderBg, color: C.textWhite, fontWeight: 800, fontSize: '7.6pt', padding: '3px 8px', textTransform: 'uppercase' }}>
        Major Shortfalls / Areas of Concern
      </div>
      <ul style={{ margin: 0, padding: '5px 10px 5px 16px', listStyle: 'disc' }}>
        {shortfalls.length === 0 && (
          <li style={{ color: C.textFaint, fontStyle: 'italic', listStyle: 'none', marginLeft: -16 }}>
            No shortfalls entered for this month yet.
          </li>
        )}
        {shortfalls.map((s, i) => <li key={i} style={{ marginBottom: 2 }}>{s}</li>)}
      </ul>
    </div>
  );
}

function YtdBar({ label, valueFmt, pct, color }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 3 }}>
      <div style={{ width: 30, fontSize: '5.6pt', color: C.textSecondary }}>{label}</div>
      <div style={{ flex: 1, background: C.borderDivider, borderRadius: 2, height: 8 }}>
        <div style={{ width: `${pct}%`, background: color, height: '100%', borderRadius: 2 }} />
      </div>
      <div style={{ width: 38, fontSize: '5.8pt', textAlign: 'right', fontWeight: color === C.accentBlue ? 700 : 400 }}>{valueFmt}</div>
    </div>
  );
}

function YtdSection({ ytd }) {
  const { prev_label: prevLabel, cur_label: curLabel, rows = [] } = ytd || {};
  return (
    <div style={{ flex: 1.15, border: `1px solid ${C.borderLight}`, borderRadius: 5, padding: '4px 8px' }}>
      <div style={{ fontWeight: 800, fontSize: '7.6pt', textTransform: 'uppercase', color: C.textHeadingDark, marginBottom: 2 }}>
        Year to Date Performance ({prevLabel} vs {curLabel})
      </div>
      <div style={{ fontSize: '6.2pt', color: C.textSecondary, fontStyle: 'italic', marginBottom: 3 }}>Quantity in &apos;000 T</div>
      {rows.map((it) => (
        <div key={it.item} style={{ marginBottom: 3 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '6.6pt', fontWeight: 700 }}>
            <span>{chemSub(it.item)}</span>
            {it.growth_pct && (
              <span style={{ color: it.growth_good ? C.textVarianceGreen : C.textVarianceRed }}>
                {it.growth_good ? '▲' : '▼'} {it.growth_pct}%
              </span>
            )}
          </div>
          <YtdBar label={prevLabel} valueFmt={it.prev_fmt} pct={it.prev_pct} color={C.textFaint} />
          <YtdBar label={curLabel} valueFmt={it.cur_fmt} pct={it.cur_pct} color={C.accentBlue} />
        </div>
      ))}
    </div>
  );
}

function ValueAddedBand({ va }) {
  if (!va) return null;
  return (
    <div style={{ border: `1px solid ${C.borderLight}`, background: C.vaBoxBg, borderRadius: 5, overflow: 'hidden', marginBottom: 4 }}>
      <div style={{ background: C.vaHeaderBg, color: C.textWhite, fontWeight: 800, fontSize: '7.6pt', padding: '3px 8px', textTransform: 'uppercase' }}>
        Value Added Steel Performance (SAIL)
      </div>
      <div style={{ display: 'flex', padding: '4px 8px' }}>
        <div style={{ flex: 1, paddingRight: 10 }}>
          <div style={{ fontSize: '7pt', fontWeight: 700, color: C.textSecondary, textTransform: 'uppercase' }}>Value Added Steel (YTD)</div>
          <div style={{ fontSize: '13pt', fontWeight: 800 }}>{va.ytd_pct ?? '—'}%</div>
          <div style={{ fontSize: '6.6pt', color: C.textSecondary }}>
            of Saleable Steel
            {va.ytd_pp !== null && va.ytd_pp !== undefined && (
              <>
                {' '}
                <b style={{ color: va.ytd_pp >= 0 ? C.textVarianceGreen : C.textVarianceRed }}>
                  {va.ytd_pp >= 0 ? '▲' : '▼'} {va.ytd_pp_abs} pp
                </b> vs CPLY
              </>
            )}
          </div>
        </div>
        <div style={{ flex: 1, borderLeft: `1px solid ${C.borderDivider}`, padding: '0 10px' }}>
          <div style={{ fontSize: '7pt', fontWeight: 700, color: C.textSecondary, textTransform: 'uppercase' }}>Quarter Just Ended ({va.quarter_label})</div>
          <div style={{ fontSize: '11pt', fontWeight: 800 }}>
            {va.quarter_cply_pct ?? '—'}% &rarr; {va.quarter_cur_pct ?? '—'}%
          </div>
          <div style={{ fontSize: '6.6pt', color: C.textSecondary }}>
            {va.quarter_pp !== null && va.quarter_pp !== undefined ? (
              <b style={{ color: va.quarter_pp >= 0 ? C.textVarianceGreen : C.textVarianceRed }}>
                {va.quarter_pp >= 0 ? '▲' : '▼'} {va.quarter_pp_abs} pp
              </b>
            ) : '—'}
          </div>
        </div>
        <div style={{ flex: 1, borderLeft: `1px solid ${C.borderDivider}`, paddingLeft: 10 }}>
          <div style={{ fontSize: '7pt', fontWeight: 700, color: C.textSecondary, textTransform: 'uppercase' }}>For the Month ({va.month_label})</div>
          <div>Qty (Value Added Steel): <b>{va.month_qty || '—'} T</b></div>
          <div>
            %Fulfilment: <b>{va.month_pct_ful || '—'}%</b> &nbsp;|&nbsp; vs CPLY:{' '}
            <GrowthText value={va.month_growth_cply} good={va.month_growth_good} />
          </div>
        </div>
      </div>
    </div>
  );
}

const DOT_COLOR = { green: C.assessGreen, amber: C.assessAmber, red: C.assessRed };

function TechnoTable({ techno, monthLabel }) {
  const th = { border: `1px solid ${C.borderMedium}`, padding: '2px 5px' };
  const td = { border: `1px solid ${C.borderLight}`, padding: '2px 5px' };
  return (
    <div style={{ flex: 1.25 }}>
      <div style={{ fontWeight: 800, fontSize: '7.6pt', textTransform: 'uppercase', color: C.textHeadingDark, marginBottom: 2 }}>
        Techno-Economic Snapshot — {monthLabel} Against Target
      </div>
      <table style={{ borderCollapse: 'collapse', width: '100%', fontSize: '6.4pt' }}>
        <thead>
          <tr>
            <th style={{ ...th, textAlign: 'left' }}>Parameter</th>
            <th style={th}>Unit</th>
            <th style={th}>Better Direction</th>
            <th style={th}>Actual</th>
            <th style={th}>Target FY</th>
            <th style={th}>Variance</th>
            <th style={th}>Assessment</th>
          </tr>
        </thead>
        <tbody>
          {techno.map((t) => (
            <tr key={t.parameter}>
              <td style={{ ...td, fontWeight: 600 }}>{chemSub(t.parameter)}</td>
              <td style={{ ...td, textAlign: 'center', fontStyle: 'italic', color: C.textSecondary }}>{chemSub(t.unit)}</td>
              <td style={{ ...td, textAlign: 'center', color: C.textSecondary }}>{t.better_direction}</td>
              <td style={{ ...td, textAlign: 'right' }}>{t.actual}</td>
              <td style={{ ...td, textAlign: 'right' }}>{t.target}</td>
              <td style={{ ...td, textAlign: 'right' }}>
                {t.variance !== null && t.variance !== undefined
                  ? `${t.variance > 0 ? '+' : ''}${t.variance.toFixed(2)} (${t.variance_pct}%)` : '—'}
              </td>
              <td style={td}>
                {t.dot_color ? (
                  <>
                    <span style={{ display: 'inline-block', width: 6, height: 6, borderRadius: '50%', background: DOT_COLOR[t.dot_color], marginRight: 3 }} />
                    {t.assessment}
                  </>
                ) : '—'}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      <div style={{ fontSize: '5.6pt', color: C.textSecondary, marginTop: 2 }}>
        <span style={{ display: 'inline-block', width: 6, height: 6, borderRadius: '50%', background: C.assessGreen, marginRight: 2 }} />Better than / within target &nbsp;
        <span style={{ display: 'inline-block', width: 6, height: 6, borderRadius: '50%', background: C.assessAmber, marginRight: 2 }} />Slightly below/above target &nbsp;
        <span style={{ display: 'inline-block', width: 6, height: 6, borderRadius: '50%', background: C.assessRed, marginRight: 2 }} />Below/above target
      </div>
    </div>
  );
}

function FocusAreas({ focusAreas }) {
  return (
    <div style={{ flex: 1, border: `1px solid ${C.borderLight}`, background: C.focusBoxBg, borderRadius: 5, overflow: 'hidden', alignSelf: 'flex-start' }}>
      <div style={{ background: C.focusHeaderBg, color: C.textWhite, fontWeight: 800, fontSize: '7.6pt', padding: '3px 8px', textTransform: 'uppercase' }}>
        Focus Areas Going Forward
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', padding: '4px 8px' }}>
        {focusAreas.length === 0 && (
          <div style={{ gridColumn: '1 / -1', color: C.textFaint, fontStyle: 'italic' }}>No focus areas entered for this month yet.</div>
        )}
        {focusAreas.map((f, i) => (
          <div key={i} style={{ padding: '2px 4px' }}>
            <div style={{ fontSize: '6.8pt', fontWeight: 800, color: C.focusHeaderBg }}>{f.title}</div>
            <div style={{ fontSize: '6.2pt', color: C.textSecondary }}>{f.description}</div>
          </div>
        ))}
      </div>
    </div>
  );
}

export default function KeyHighlightsTemplate({ data }) {
  if (!data) return null;
  const {
    title = '', subtitle = '', month_label: monthLabel = '',
    kpi = [], ytd, value_added: valueAdded, techno = [],
    achievements = [], shortfalls = [], focus_areas: focusAreas = [],
  } = data;

  return (
    <div style={{ padding: '2px 4px', fontFamily: "'Arial Narrow', Arial, sans-serif", fontSize: '7.4pt', color: C.textPrimary }}>
      <div style={{
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        background: C.bannerBg, color: C.textWhite, padding: '5px 14px', borderRadius: 5, marginBottom: 4,
      }}>
        <div>
          <div style={{ fontSize: '16pt', fontWeight: 900, letterSpacing: 0.3 }}>{title}</div>
          <div style={{ fontSize: '8.5pt', fontWeight: 500, opacity: 0.9 }}>{subtitle}</div>
        </div>
        <div style={{ background: C.badgeBg, borderRadius: 5, padding: '4px 12px', textAlign: 'center' }}>
          <div style={{ fontSize: '6.4pt', textTransform: 'uppercase', opacity: 0.85 }}>Report Month</div>
          <div style={{ fontSize: '11pt', fontWeight: 800 }}>{monthLabel}</div>
        </div>
      </div>

      <KpiStrip kpi={kpi} />

      <div style={{ display: 'flex', gap: 6, marginBottom: 4, alignItems: 'stretch' }}>
        <AchievementsBox achievements={achievements} />
        <YtdSection ytd={ytd} />
        <ShortfallsBox shortfalls={shortfalls} />
      </div>

      <ValueAddedBand va={valueAdded} />

      <div style={{ display: 'flex', gap: 6 }}>
        <TechnoTable techno={techno} monthLabel={monthLabel} />
        <FocusAreas focusAreas={focusAreas} />
      </div>
    </div>
  );
}
