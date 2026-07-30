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
  borderMedium: '#94a3b8',
  borderDivider: '#e2e8f0',
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
          flex: 1, border: `1px solid ${C.borderLight}`, borderLeft: `4px solid ${C.accentBlue}`,
          borderRadius: 4, padding: '7px 9px',
        }}>
          <div style={{ fontSize: '7.6pt', color: C.textSecondary, textTransform: 'uppercase', fontWeight: 600 }}>{row.item}</div>
          <div style={{ fontSize: '15pt', fontWeight: 700, color: C.textPrimary, lineHeight: 1.3 }}>{row.month_act || '—'}</div>
          <div style={{ fontSize: '7.4pt', color: C.textSecondary }}>%Ful: <b style={{ color: C.textPrimary }}>{row.month_pct_ful || '—'}%</b></div>
          <div style={{ fontSize: '7.4pt', color: C.textSecondary }}>vs CPLY: <GrowthText value={row.pct_growth_cply} good={row.growth_good} /></div>
        </div>
      ))}
    </div>
  );
}

function YtdTable({ production }) {
  const th = { padding: '5px 4px', border: `1px solid ${C.borderMedium}`, textAlign: 'center', fontWeight: 700, fontSize: '7.5pt' };
  const td = { padding: '4px 4px', border: `1px solid ${C.borderLight}`, textAlign: 'right', fontSize: '7.5pt' };
  return (
    <table style={{ width: '100%', borderCollapse: 'collapse', marginBottom: 10 }}>
      <thead>
        <tr>
          <th style={{ ...th, textAlign: 'left' }}>Item — YTD (&apos;000 T)</th>
          <th style={th}>CPLY YTD Actual</th>
          <th style={th}>This FY YTD Actual</th>
          <th style={th}>%Growth (YoY)</th>
        </tr>
      </thead>
      <tbody>
        {production.map((row) => (
          <tr key={row.item}>
            <td style={{ ...td, textAlign: 'left', fontWeight: 500 }}>{row.item}</td>
            <td style={td}>{row.ytd_cply_act || '—'}</td>
            <td style={{ ...td, fontWeight: 700 }}>{row.ytd_act || '—'}</td>
            <td style={{ ...td, fontWeight: 600 }}><GrowthText value={row.ytd_pct_growth} good={row.ytd_growth_good} /></td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function TechnoTiles({ techno }) {
  return (
    <div style={{ display: 'flex', gap: 7, marginBottom: 10 }}>
      {techno.map((t) => {
        const bg = t.good === true ? C.achievedBg : t.good === false ? C.shortfallBg : C.defaultRowBg;
        return (
          <div key={t.parameter} style={{ flex: 1, background: bg, borderRadius: 4, padding: '6px 8px' }}>
            <div style={{ fontSize: '7.6pt', fontWeight: 700, color: C.textHeadingDark }}>{t.parameter}</div>
            <div style={{ fontSize: '6.8pt', color: C.textSecondary, fontStyle: 'italic' }}>{t.unit}</div>
            <div style={{ fontSize: '11pt', fontWeight: 700, color: C.textPrimary }}>{t.month_actual || '—'}</div>
            <div style={{ fontSize: '7pt', color: C.textSecondary }}>Target: {t.target || '—'}</div>
            {t.delta_pct !== null && t.delta_pct !== undefined && (
              <div style={{ fontSize: '7.4pt', fontWeight: 700, color: t.good ? C.textVarianceGreen : C.textVarianceRed }}>
                {t.delta_pct > 0 ? '+' : ''}{t.delta_pct.toFixed(1)}% vs target
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}

function SpecialSteelPanel({ specialSteel }) {
  return (
    <div style={{ flex: 1.05, border: `1px solid ${C.borderLight}`, borderRadius: 4, padding: '7px 9px' }}>
      <div style={{ fontSize: '9pt', fontWeight: 700, color: C.textHeadingDark, textTransform: 'uppercase', marginBottom: 5 }}>
        Special Steel Performance (SAIL)
      </div>
      <div style={{ display: 'flex', gap: 9, alignItems: 'center' }}>
        <div style={{ flex: 1 }} dangerouslySetInnerHTML={{ __html: specialSteel.bar_svg || '' }} />
        <div style={{ flex: 1, fontSize: '7.5pt', lineHeight: 1.85 }}>
          <div>%Fulfilment: <b>{specialSteel.pct_ful || '—'}%</b></div>
          <div>vs CPLY: <GrowthText value={specialSteel.pct_growth} good={specialSteel.growth_good} /></div>
          <div>ABP FY: <b>{specialSteel.abp_fy || '—'}</b></div>
          <div>% of Saleable Steel: <b>{specialSteel.special_pct || '—'}%</b></div>
        </div>
      </div>
    </div>
  );
}

function CapitalRepairPanel({ capitalRepair }) {
  return (
    <div style={{ flex: 1, border: `1px solid ${C.borderLight}`, borderRadius: 4, padding: '7px 9px' }}>
      <div style={{ fontSize: '9pt', fontWeight: 700, color: C.textHeadingDark, textTransform: 'uppercase', marginBottom: 5 }}>
        Capital Repair Status — Current FY
      </div>
      {capitalRepair.map((pl) => (
        <div key={pl.plant} style={{ marginBottom: 5 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '7.4pt', marginBottom: 1 }}>
            <span style={{ fontWeight: 700 }}>{pl.plant}</span>
            <span style={{ color: C.textSecondary }}>{pl.completed}/{pl.total}{pl.pct !== null && pl.pct !== undefined ? ` (${pl.pct}%)` : ''}</span>
          </div>
          <div style={{ background: C.borderDivider, borderRadius: 3, height: 6, overflow: 'hidden' }}>
            <div style={{ width: `${pl.pct || 0}%`, height: '100%', background: C.accentBlue }} />
          </div>
        </div>
      ))}
    </div>
  );
}

export default function AtAGlanceTemplate({ data }) {
  if (!data) return null;
  const {
    title, month_label: monthLabel,
    production = [], techno = [], special_steel: specialSteel = {},
    capital_repair: capitalRepair = [], trend = {},
  } = data;

  return (
    <div style={{ padding: '2px 4px', fontFamily: "'Arial Narrow', Arial, sans-serif", fontSize: '7.8pt', color: C.textPrimary }}>
      <div style={{ background: C.accentBlue, color: C.textWhite, padding: '12px 16px', borderRadius: 5, marginBottom: 10 }}>
        <div style={{ fontSize: '17pt', fontWeight: 700 }}>{title}</div>
        <div style={{ fontSize: '10.5pt', fontWeight: 500, opacity: 0.92 }}>{monthLabel}</div>
      </div>

      <div style={{ fontSize: '10pt', fontWeight: 700, color: C.textHeadingDark, textTransform: 'uppercase', marginBottom: 5 }}>
        Production Performance — Month (&apos;000 T)
      </div>
      <ProductionTiles production={production} />

      <YtdTable production={production} />

      <div style={{ fontSize: '10pt', fontWeight: 700, color: C.textHeadingDark, textTransform: 'uppercase', marginBottom: 5 }}>
        Techno-Economic Snapshot — SAIL
      </div>
      <TechnoTiles techno={techno} />

      <div style={{ display: 'flex', gap: 10, marginBottom: 10 }}>
        <SpecialSteelPanel specialSteel={specialSteel} />
        <CapitalRepairPanel capitalRepair={capitalRepair} />
      </div>

      <div style={{ fontSize: '10pt', fontWeight: 700, color: C.textHeadingDark, textTransform: 'uppercase', marginBottom: 5 }}>
        Saleable Steel Production Trend — Last 6 Months (&apos;000 T)
      </div>
      <div style={{ border: `1px solid ${C.borderLight}`, borderRadius: 4, padding: '5px 9px' }}
           dangerouslySetInnerHTML={{ __html: trend.svg || '' }} />
    </div>
  );
}
