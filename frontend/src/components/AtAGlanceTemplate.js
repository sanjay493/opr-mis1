import React from 'react';

// Mirrors backend/page_templates/at_a_glance.html section-for-section, and
// reuses the same colors_config.json hex values (this codebase's React
// templates don't import that file — every other *Template.js hardcodes its
// own copy of the relevant hex values, e.g. SpecialSteelTemplate.js).
const C = {
  accentBlue: '#0284c7',
  textPrimary: '#0f172a',
  textSecondary: '#475569',
  textWhite: '#ffffff',
  textHeadingDark: '#1e293b',
  textVarianceGreen: '#064e3b',
  textVarianceRed: '#9a3412',
  achievedBg: '#dcfce7',
  shortfallBg: '#fed7aa',
  defaultRowBg: 'transparent',
  borderLight: '#cbd5e1',
  borderDivider: '#e2e8f0',
  khvAssessmentAmber: '#d97706',
};

// Techno-Economic Snapshot tile backgrounds by category — mirrors the
// techno_cat_*_bg entries in backend/colors_config.json.
const TECHNO_CAT_BG = {
  techno_cat_fuel_bg: '#fde2c8',
  techno_cat_energy_bg: '#fff3c4',
  techno_cat_process_bg: '#cfe8ff',
  techno_cat_burden_bg: '#d9f2d0',
  techno_cat_environment_bg: '#cdf0ea',
  techno_cat_blend_bg: '#e5e0f5',
};

function GrowthText({ value, good }) {
  if (good === null || good === undefined || !value) return <b>—</b>;
  return <b style={{ color: good ? C.textVarianceGreen : C.textVarianceRed }}>{good ? `+${value}` : value}%</b>;
}

function ProductionTiles({ production }) {
  return (
    <div style={{ display: 'flex', gap: 7, marginBottom: 10 }}>
      {production.map((row) => (
        <div key={row.item} style={{
          flex: 1, position: 'relative', border: `1px solid ${C.borderLight}`,
          borderRadius: 4, padding: '7px 9px 7px 13px', overflow: 'hidden',
        }}>
          <div style={{
            position: 'absolute', left: 0, top: 0, bottom: 0, width: 4,
            background: `linear-gradient(180deg, ${C.accentBlue} 0 25%, #16a34a 25% 50%, #d97706 50% 75%, #b91c1c 75% 100%)`,
          }} />
          <div style={{ fontSize: '8.5pt', color: C.textBlack, textTransform: 'capitalize', fontWeight: 700, letterSpacing: 0.2 }}>{row.item}</div>
          <div style={{ fontSize: '16pt', fontWeight: 700, color: C.textPrimary, lineHeight: 1.2 }}>{row.month_act || '—'}</div>
          <div style={{ fontSize: '8pt', color: C.textSecondary }}>%Ful: <b style={{ color: C.textPrimary }}>{row.month_pct_ful || '—'}%</b></div>
          <div style={{ fontSize: '8pt', color: C.textSecondary }}>vs CPLY: <GrowthText value={row.pct_growth_cply} good={row.growth_good} /></div>
        </div>
      ))}
    </div>
  );
}

function YtdTrendChart({ ytdTrend }) {
  return (
    <div style={{ border: `1px solid ${C.borderLight}`, borderRadius: 4, padding: '6px 9px', marginBottom: 10 }}
         dangerouslySetInnerHTML={{ __html: (ytdTrend && ytdTrend.svg) || '' }} />
  );
}

// 3D "raised card" look (shadow hugging the left/bottom edges, as if lit
// from the top-right) plus a small folded-paper flap in the top-left
// corner, per direct instruction — mirrors the .techno-tile class added to
// backend/page_templates/main.html. React inline styles can't express
// ::before, so this is the one place in this component that needs a real
// <style> tag rather than a style object.
const TECHNO_TILE_CSS = `
  .techno-tile {
    position: relative;
    overflow: hidden;
    box-shadow: -3px 3px 6px rgba(15, 23, 42, 0.22), 0 1px 0 rgba(15, 23, 42, 0.08);
    border-left: 1px solid rgba(15, 23, 42, 0.14);
    border-bottom: 1px solid rgba(15, 23, 42, 0.14);
  }
  .techno-tile::before {
    content: "";
    position: absolute;
    top: 0;
    left: 0;
    width: 0;
    height: 0;
    border-style: solid;
    border-width: 13px 13px 0 0;
    border-color: rgba(255, 255, 255, 0.8) transparent transparent transparent;
    filter: drop-shadow(1px 1.5px 1.5px rgba(15, 23, 42, 0.35));
  }
`;

function TechnoTiles({ techno }) {
  return (
    <div style={{ display: 'flex', gap: 9, marginBottom: 12 }}>
      <style>{TECHNO_TILE_CSS}</style>
      {techno.map((t) => {
        const bg = (t.bg_key && TECHNO_CAT_BG[t.bg_key]) || C.defaultRowBg;
        return (
          <div key={t.parameter} className="techno-tile" style={{ flex: 1, background: bg, borderRadius: 4, padding: '10px 13px' }}>
            <div style={{ fontSize: '8pt', fontWeight: 700, lineHeight: 1.15, color: C.textHeadingDark }}>
              {t.parameter} <span style={{ fontWeight: 400, fontStyle: 'italic', color: C.textSecondary }}>({t.unit})</span>
            </div>
            <div style={{ display: 'flex', alignItems: 'baseline', justifyContent: 'space-between', marginTop: 4 }}>
              <span style={{ fontSize: '12.5pt', fontWeight: 700, lineHeight: 1.2, color: C.textPrimary }}>{t.month_actual || '—'}</span>
              <span style={{ fontSize: '11.5pt', fontWeight: 400, lineHeight: 1.2, color: C.textSecondary }}>Target: {t.target || '—'}</span>
            </div>
            {t.delta_pct !== null && t.delta_pct !== undefined && (
              <div style={{ fontSize: '7.8pt', lineHeight: 1.15, fontWeight: 700, marginTop: 2, color: t.good ? C.textVarianceGreen : C.textVarianceRed }}>
                {t.delta_pct > 0 ? '+' : ''}{t.delta_pct.toFixed(1)}% vs target
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}

function ValueAddedSteelPanel({ specialSteel }) {
  return (
    <div style={{ border: `1px solid ${C.borderLight}`, borderRadius: 4, padding: '5px 8px' }}>
      <div style={{ fontSize: '11pt', fontWeight: 700, color: C.textHeadingDark, textTransform: 'capitalize', marginBottom: 4 }}>
        Value Added Steel Performance (SAIL)
      </div>
      <div style={{ display: 'flex', gap: 9, alignItems: 'center' }}>
        <div style={{ flex: 1.5 }} dangerouslySetInnerHTML={{ __html: specialSteel.five_year_svg || '' }} />
        <div style={{ flex: 0.85, borderLeft: `1px solid ${C.borderDivider}`, paddingLeft: 9 }} dangerouslySetInnerHTML={{ __html: specialSteel.quarter_svg || '' }} />
        <div style={{ flex: 0.55, fontSize: '9.5pt', lineHeight: 1.6, paddingLeft: 9, borderLeft: `1px solid ${C.borderDivider}` }}>
          <div style={{ fontSize: '10pt', fontWeight: 700, color: C.textHeadingDark, marginBottom: 2 }}>{specialSteel.month_title}</div>
          <div>Qty (Value Added Steel): <b>{specialSteel.month_qty || '—'} T</b></div>
          <div>%Fulfilment of Orderbook: <b>{specialSteel.pct_ful || '—'}%</b></div>
          <div>vs CPLY: <GrowthText value={specialSteel.pct_growth} good={specialSteel.growth_good} /></div>
          <div>% of Saleable Steel: <b>{specialSteel.special_pct || '—'}%</b></div>
        </div>
      </div>
    </div>
  );
}

export default function AtAGlanceTemplate({ data }) {
  if (!data) return null;
  const {
    title, month_label: monthLabel,
    production = [], ytd_trend: ytdTrend = {}, techno = [], special_steel: specialSteel = {},
    trend = {},
  } = data;

  return (
    <div style={{ padding: '2px 4px', fontFamily: "'Arial Narrow', Arial, sans-serif", fontSize: '7.8pt', color: C.textPrimary }}>
      <div style={{ display: 'flex', alignItems: 'baseline', justifyContent: 'space-between', gap: 10, marginBottom: 6 }}>
        <div style={{ fontSize: '17pt', fontWeight: 700, color: C.textHeadingDark }}>{title}</div>
        <div style={{ fontSize: '11pt', fontWeight: 700, color: C.khvAssessmentAmber, whiteSpace: 'nowrap' }}>{monthLabel}</div>
      </div>

      <div style={{ fontSize: '10pt', fontWeight: 700, color: C.textHeadingDark, textTransform: 'capitalize', marginBottom: 4 }}>
        Production Performance — Month (&apos;000 T)
      </div>
      <ProductionTiles production={production} />

      <div style={{ fontSize: '10pt', fontWeight: 700, color: C.textHeadingDark, textTransform: 'capitalize', marginBottom: 4 }}>
        Production Trend — Last 4 Years ({ytdTrend.period_label || ''} , &apos;000 T)
      </div>
      <YtdTrendChart ytdTrend={ytdTrend} />

      <div style={{ fontSize: '10pt', fontWeight: 700, color: C.textHeadingDark, textTransform: 'capitalize', marginBottom: 4 }}>
        Techno-Economic Snapshot — SAIL
      </div>
      <TechnoTiles techno={techno} />

      <div style={{ marginBottom: 6 }}>
        <ValueAddedSteelPanel specialSteel={specialSteel} />
      </div>

      <div style={{ fontSize: '10pt', fontWeight: 700, color: C.textHeadingDark, textTransform: 'capitalize', marginBottom: 4 }}>
        Saleable Steel &amp; Finished Steel Production Trend — Last 6 Months (&apos;000 T)
      </div>
      <div style={{ border: `1px solid ${C.borderLight}`, borderRadius: 4, padding: '5px 9px' }}
           dangerouslySetInnerHTML={{ __html: trend.svg || '' }} />
    </div>
  );
}
