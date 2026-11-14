'use client';

// Rake Despatch (Reports > Rail Logistics): the Rail Movement Cell's monthly
// Despatch Summary Report with management insights on top. Data and every
// computed figure come from GET /api/rake-despatch/report
// (backend/rake_despatch_report.py); this view only lays them out. Upload
// the PDF on Data Entry > Uploads.

import { Fragment, useEffect, useMemo, useState } from 'react';
import Link from 'next/link';
import { ResponsiveContainer, LineChart, Line, BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend } from 'recharts';
import { ReportPage, FilterBar, Field, Status, Section, Loading, Empty, Toggle, entryStyles as es } from '../ReportUI';

const API = process.env.NEXT_PUBLIC_API_URL || '';
const PLANTS = ['BSP', 'DSP', 'RSP', 'BSL', 'ISP', 'SAIL'];
const MON = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
const FY_MON = ['Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec', 'Jan', 'Feb', 'Mar'];

const mlabel = (m) => (m ? `${MON[parseInt(m.slice(5, 7), 10) - 1]}'${m.slice(2, 4)}` : '');
const fmt = (v, d = 0) => (v == null ? '–' : Number(v).toLocaleString('en-IN', { minimumFractionDigits: d, maximumFractionDigits: d }));
const signed = (v, d = 1, unit = '%') => (v == null ? '–' : `${v > 0 ? '+' : ''}${fmt(v, d)}${unit}`);

const STATUS = {
  ok: { bg: '#dcfce7', fg: '#166534', label: 'On plan' },
  watch: { bg: '#fef3c7', fg: '#92400e', label: '95–100%' },
  behind: { bg: '#fee2e2', fg: '#b91c1c', label: 'Below 95%' },
  na: { bg: '#f1f5f9', fg: '#475569', label: 'No plan' },
};
const B = '1px solid #cbd5e1';
const T = { width: '100%', borderCollapse: 'collapse', fontSize: 13 };
const th = { border: B, padding: '5px 8px', background: '#f1f5f9', fontWeight: 600, textAlign: 'center', whiteSpace: 'nowrap' };
const td = { border: B, padding: '4px 8px', textAlign: 'right', whiteSpace: 'nowrap', fontVariantNumeric: 'tabular-nums' };
const tdl = { ...td, textAlign: 'left', fontWeight: 600 };
const sail = { background: '#f8fafc', fontWeight: 700 };
const tone = (v) => ({ color: v == null ? undefined : v < 0 ? '#b91c1c' : '#166534' });
// Seven FYs, newest first: current FY strong, last FY contrasting, older muted.
const FY_COLORS = ['#1d4ed8', '#ea580c', '#64748b', '#94a3b8', '#a8b3c4', '#c0c9d6', '#d5dbe4'];
const TYPE_COLORS = ['#1d4ed8', '#0891b2', '#16a34a', '#ca8a04', '#ea580c', '#dc2626', '#9333ea', '#db2777', '#475569', '#0f766e', '#65a30d', '#a16207'];

function Chip({ status }) {
  const s = STATUS[status] || STATUS.na;
  return <span style={{ background: s.bg, color: s.fg, borderRadius: 999, padding: '1px 8px', fontSize: 12, fontWeight: 600 }}>{s.label}</span>;
}

function Card({ title, value, sub, status, delta }) {
  const s = status ? STATUS[status] : null;
  return (
    <div style={{ border: B, borderRadius: 10, padding: '12px 14px', background: '#fff', borderTop: `4px solid ${s ? s.fg : '#1d4ed8'}`, minWidth: 0 }}>
      <div style={{ fontSize: 12, color: '#475569', fontWeight: 600, textTransform: 'uppercase', letterSpacing: 0.3 }}>{title}</div>
      <div style={{ fontSize: 26, fontWeight: 700, margin: '4px 0 2px', fontVariantNumeric: 'tabular-nums' }}>{value}</div>
      {delta != null && <div style={{ fontSize: 13, fontWeight: 600, ...tone(delta.value) }}>{delta.text}</div>}
      {sub && <div style={{ fontSize: 12.5, color: '#475569', marginTop: 2 }}>{sub}</div>}
    </div>
  );
}

function Headline({ d }) {
  const h = d.headline;
  return (
    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(210px, 1fr))', gap: 12, marginBottom: 16 }}>
      <Card title={`SAIL rakes, ${mlabel(d.report_month)}`} value={fmt(h.month_actual)} status={h.month_status}
            delta={h.month_attainment != null ? { value: h.month_attainment - 100, text: `${fmt(h.month_attainment, 1)}% of plan (${fmt(h.month_plan, 0)})` } : null}
            sub={`${fmt(h.month_avg_day, 2)}/day vs plan ${fmt(h.month_plan_avg_day, 2)}/day`} />
      <Card title={`vs ${mlabel(`${Number(d.report_month.slice(0, 4)) - 1}${d.report_month.slice(4)}`)}`} value={signed(h.vs_ly_month_pct)}
            delta={null} sub={`${fmt(h.ly_month_actual)} rakes in the same month last year`} />
      <Card title={`FY ${d.fy} to date`} value={fmt(h.fytd_actual)}
            delta={h.vs_ly_fytd_pct != null ? { value: h.vs_ly_fytd_pct, text: `${signed(h.vs_ly_fytd_pct)} vs last year (${fmt(h.ly_fytd_actual)})` } : null}
            sub={h.fytd_plan != null ? `${fmt(h.fytd_attainment, 1)}% of FYTD plan (${fmt(h.fytd_plan)})` : 'FYTD plan needs every month of the FY uploaded'} />
      <Card title="FY projection at current pace" value={fmt(h.fy_projection)}
            delta={h.projection_vs_ly_pct != null ? { value: h.projection_vs_ly_pct, text: `${signed(h.projection_vs_ly_pct)} vs last FY (${fmt(h.ly_fy_total)})` } : null} />
    </div>
  );
}

function KeyPoints({ points }) {
  if (!points?.length) return null;
  return (
    <Section title="Key points" sub="Written from the figures below; ready to paste into a note." flush={false}>
      <ul style={{ margin: 0, paddingLeft: 20, lineHeight: 1.6, fontSize: 14 }}>
        {points.map((p, i) => <li key={i}>{p}</li>)}
      </ul>
    </Section>
  );
}

function Ranking({ rows, month }) {
  return (
    <Section title="Plan attainment" sub={`${mlabel(month)}: plants furthest behind plan first. Plan = page-1 plan rakes/day × days in the month.`}>
      <table style={T}>
        <thead><tr>
          <th style={th}>Plant</th><th style={th}>Actual</th><th style={th}>Plan</th><th style={th}>% of plan</th><th style={th}>Status</th>
          <th style={th}>Avg/day</th><th style={th}>Plan/day</th><th style={th}>Gap/day</th>
          <th style={th}>FYTD</th><th style={th}>FYTD last year</th><th style={th}>FYTD vs LY</th>
        </tr></thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.plant} style={r.plant === 'SAIL' ? sail : undefined}>
              <td style={tdl}>{r.plant}</td><td style={td}>{fmt(r.actual)}</td><td style={td}>{fmt(r.plan, 0)}</td>
              <td style={{ ...td, fontWeight: 700 }}>{fmt(r.attainment, 1)}</td><td style={{ ...td, textAlign: 'center' }}><Chip status={r.status} /></td>
              <td style={td}>{fmt(r.avg_day, 2)}</td><td style={td}>{fmt(r.plan_avg_day, 2)}</td>
              <td style={{ ...td, ...tone(r.gap_per_day) }}>{r.gap_per_day == null ? '–' : signed(r.gap_per_day, 2, '')}</td>
              <td style={td}>{fmt(r.fytd_actual)}</td><td style={td}>{fmt(r.ly_fytd_actual)}</td>
              <td style={{ ...td, ...tone(r.fytd_vs_ly_pct) }}>{signed(r.fytd_vs_ly_pct)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </Section>
  );
}

function RunRate({ rows }) {
  const [basis, setBasis] = useState('ly');
  return (
    <Section title="Run-rate to FY end"
             sub={basis === 'ly' ? "Rakes/day needed for the rest of the FY to equal last FY's total, against the pace so far."
               : "Where the FY ends if each plant loads at this month's plan rate for the rest of the year."}
             actions={<Toggle label="Target" value={basis} onChange={setBasis}
                              options={[{ id: 'ly', label: 'Match last FY' }, { id: 'plan', label: 'Plan rate' }]} />}>
      <table style={T}>
        <thead><tr>
          <th style={th}>Plant</th><th style={th}>FYTD</th><th style={th}>FYTD avg/day</th><th style={th}>This month avg/day</th>
          {basis === 'ly'
            ? <><th style={th}>Last FY total</th><th style={th}>Needed/day</th><th style={th}>Lift needed</th></>
            : <><th style={th}>Plan/day</th><th style={th}>FY at plan rate</th><th style={th}>FY at current pace</th></>}
        </tr></thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.plant} style={r.plant === 'SAIL' ? sail : undefined}>
              <td style={tdl}>{r.plant}</td><td style={td}>{fmt(r.fytd_actual)}</td><td style={td}>{fmt(r.fytd_avg_day, 2)}</td>
              <td style={td}>{fmt(r.month_avg_day, 2)}</td>
              {basis === 'ly'
                ? <><td style={td}>{fmt(r.ly_total)}</td><td style={{ ...td, fontWeight: 700 }}>{fmt(r.required_avg_day_ly, 2)}</td>
                  <td style={{ ...td, color: r.lift_needed_pct > 0 ? '#b91c1c' : '#166534', fontWeight: 600 }}>
                    {r.lift_needed_pct == null ? '–' : r.lift_needed_pct > 0 ? `+${fmt(r.lift_needed_pct, 1)}%` : 'On course'}</td></>
                : <><td style={td}>{fmt(r.plan_avg_day, 2)}</td><td style={{ ...td, fontWeight: 700 }}>{fmt(r.fy_at_plan_rate)}</td>
                  <td style={td}>{fmt(r.fy_at_current_pace)}</td></>}
            </tr>
          ))}
        </tbody>
      </table>
      <p style={{ fontSize: 12, color: '#64748b', margin: '6px 2px 0' }}>{rows[0]?.remaining_days} days left in the FY.</p>
    </Section>
  );
}

function Records({ rows, month }) {
  const monName = new Date(2000, parseInt(month.slice(5, 7), 10) - 1, 1).toLocaleString('en-IN', { month: 'long' });
  return (
    <Section title="Records & seasonality" sub={`How ${mlabel(month)} ranks against every stored ${monName}, and the best month and FY on record.`}>
      <table style={T}>
        <thead><tr>
          <th style={th}>Plant</th><th style={th}>{mlabel(month)}</th><th style={th}>Rank among {monName}s</th>
          <th style={th}>Best {monName}</th><th style={th}>Worst {monName}</th><th style={th}>Best month ever</th><th style={th}>Best FY</th>
        </tr></thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.plant} style={r.plant === 'SAIL' ? sail : undefined}>
              <td style={tdl}>{r.plant}</td><td style={td}>{fmt(r.actual)}</td>
              <td style={{ ...td, textAlign: 'center', fontWeight: 700, color: r.same_month_rank === 1 ? '#166534' : undefined }}>
                {r.same_month_rank ? `${r.same_month_rank} of ${r.same_month_count}` : '–'}{r.same_month_rank === 1 && r.same_month_count > 1 ? ' ★' : ''}</td>
              <td style={td}>{fmt(r.same_month_best[1])} <span style={{ color: '#64748b' }}>({mlabel(r.same_month_best[0])})</span></td>
              <td style={td}>{fmt(r.same_month_worst[1])} <span style={{ color: '#64748b' }}>({mlabel(r.same_month_worst[0])})</span></td>
              <td style={{ ...td, background: r.is_best_month_ever ? '#dcfce7' : undefined }}>
                {fmt(r.best_month.rakes)} <span style={{ color: '#64748b' }}>({mlabel(r.best_month.month)})</span>{r.is_best_month_ever ? ' ★ this month' : ''}</td>
              <td style={td}>{fmt(r.best_fy.rakes)} <span style={{ color: '#64748b' }}>({r.best_fy.fy || '–'})</span></td>
            </tr>
          ))}
        </tbody>
      </table>
    </Section>
  );
}

function Trend({ trend }) {
  const [plant, setPlant] = useState('SAIL');
  const series = trend[plant] || [];
  const data = FY_MON.map((m, i) => {
    const row = { month: m };
    series.forEach((s) => { row[s.fy] = s.months[i]; });
    return row;
  });
  return (
    <Section title="Seven-year monthly trend" sub="Rakes per month, current FY against the six before it."
             actions={<Toggle label="Plant" value={plant} onChange={setPlant} options={PLANTS.map((p) => ({ id: p, label: p }))} />} flush={false}>
      <div style={{ width: '100%', height: 340 }}>
        <ResponsiveContainer>
          <LineChart data={data} margin={{ top: 8, right: 16, left: 0, bottom: 0 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
            <XAxis dataKey="month" tick={{ fontSize: 12 }} />
            <YAxis tick={{ fontSize: 12 }} domain={['auto', 'auto']} />
            <Tooltip />
            <Legend wrapperStyle={{ fontSize: 12 }} />
            {[...series].reverse().map((s) => {
              const i = series.indexOf(s);
              return <Line key={s.fy} type="monotone" dataKey={s.fy} stroke={FY_COLORS[i]} strokeWidth={i === 0 ? 3 : i === 1 ? 2 : 1.25}
                           dot={i === 0 ? { r: 3 } : false} connectNulls={false} isAnimationActive={false} />;
            })}
          </LineChart>
        </ResponsiveContainer>
      </div>
      <table style={{ ...T, marginTop: 10, fontSize: 12.5 }}>
        <thead><tr><th style={th}>FY</th>{FY_MON.map((m) => <th key={m} style={th}>{m}</th>)}<th style={th}>Total</th></tr></thead>
        <tbody>
          {series.map((s, i) => (
            <tr key={s.fy} style={i === 0 ? { fontWeight: 700, background: '#eff6ff' } : undefined}>
              <td style={tdl}>{s.fy}</td>{s.months.map((v, j) => <td key={j} style={td}>{v == null ? '' : fmt(v)}</td>)}
              <td style={{ ...td, fontWeight: 700 }}>{fmt(s.total)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </Section>
  );
}

function WagonMix({ mix }) {
  const types = useMemo(() => {
    const seen = [];
    mix.plants.forEach((p) => p.types.forEach((t) => { if (!seen.includes(t.type)) seen.push(t.type); }));
    return seen;
  }, [mix]);
  const data = mix.plants.map((p) => {
    const row = { plant: p.plant };
    p.types.forEach((t) => { row[t.type] = t.fytd_share; });
    return row;
  });
  return (
    <Section title="Wagon-type mix" sub={`Share of FY-to-date rakes by wagon type. Shift: ${mix.label}.`} flush={false}>
      <div style={{ width: '100%', height: 46 * data.length + 50 }}>
        <ResponsiveContainer>
          <BarChart data={data} layout="vertical" margin={{ top: 4, right: 16, left: 8, bottom: 0 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
            <XAxis type="number" domain={[0, 100]} unit="%" tick={{ fontSize: 12 }} />
            <YAxis type="category" dataKey="plant" width={44} tick={{ fontSize: 12, fontWeight: 600 }} />
            <Tooltip formatter={(v) => `${fmt(v, 1)}%`} />
            <Legend wrapperStyle={{ fontSize: 12 }} />
            {types.map((t, i) => <Bar key={t} dataKey={t} stackId="a" fill={TYPE_COLORS[i % TYPE_COLORS.length]} isAnimationActive={false} />)}
          </BarChart>
        </ResponsiveContainer>
      </div>
      <table style={{ ...T, marginTop: 10, fontSize: 12.5 }}>
        <thead><tr><th style={th}>Plant</th><th style={th}>FYTD rakes</th><th style={th}>Mix (share, shift in points)</th></tr></thead>
        <tbody>
          {mix.plants.map((p) => (
            <tr key={p.plant} style={p.plant === 'SAIL' ? sail : undefined}>
              <td style={tdl}>{p.plant}</td><td style={td}>{fmt(p.fytd_total)}</td>
              <td style={{ ...td, textAlign: 'left', whiteSpace: 'normal' }}>
                {p.types.filter((t) => t.fytd_rakes > 0).map((t) => (
                  <span key={t.type} style={{ marginRight: 14, display: 'inline-block' }}>
                    <b>{t.type}</b> {fmt(t.fytd_share, 1)}%
                    {t.shift_pp != null && Math.abs(t.shift_pp) >= 0.1 && (
                      <span style={{ ...tone(t.shift_pp), fontWeight: p.biggest_shift?.type === t.type ? 700 : 400 }}> ({signed(t.shift_pp, 1, '')})</span>)}
                  </span>
                ))}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </Section>
  );
}

function ExportWatch({ rows }) {
  const flag = { excess: { c: '#166534', t: 'Excess' }, shortfall: { c: '#b91c1c', t: 'Shortfall' }, on: { c: '#475569', t: 'On programme' } };
  return (
    <Section title="Export watch" sub="Export rakes against programme by destination (programme / actual).">
      <table style={T}>
        <thead><tr>
          <th style={th}>Destination</th>
          {PLANTS.slice(0, 5).map((p) => <th key={p} style={th}>{p}</th>)}
          <th style={th}>SAIL prog</th><th style={th}>SAIL actual</th><th style={th}>% fulfilment</th><th style={th}>Gap</th><th style={th}></th>
        </tr></thead>
        <tbody>
          {rows.map((r) => {
            const quiet = !r.prog && !r.actual && !r.is_total;
            return (
              <tr key={r.destination} style={r.is_total ? sail : quiet ? { color: '#94a3b8' } : undefined}>
                <td style={{ ...tdl, fontWeight: r.is_total ? 700 : 500 }}>{r.destination}</td>
                {PLANTS.slice(0, 5).map((p) => {
                  const c = r.plants[p] || {};
                  return <td key={p} style={td}>{c.prog || c.actual ? `${fmt(c.prog)} / ${fmt(c.actual)}` : ''}</td>;
                })}
                <td style={td}>{fmt(r.prog)}</td><td style={{ ...td, fontWeight: 700 }}>{fmt(r.actual)}</td>
                <td style={td}>{r.fulfilment == null ? '–' : `${fmt(r.fulfilment, 0)}%`}</td>
                <td style={{ ...td, ...tone(r.gap) }}>{r.prog || r.actual ? signed(r.gap, 0, '') : ''}</td>
                <td style={{ ...td, textAlign: 'center', color: flag[r.flag]?.c, fontWeight: 600 }}>{r.prog || r.actual ? flag[r.flag]?.t : ''}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </Section>
  );
}

// ── source data (the PDF's own tables) ───────────────────────────────────────

const POS_COLS = [
  ['plan_avg_day', 'Plan avg/day', 2], ['empties_received', 'Empties recd (last day)', 0], ['made_over', 'Made over (last day)', 0],
  ['cumm', 'Cumm.', 0], ['avg_day', 'Avg/day', 2], ['diff_plan', 'Diff. with plan', 2],
  ['made_over_after_00', 'Made over after 00:00', 0], ['under_loading', 'Under loading', 0], ['empty_forecast', 'Empty forecast', 0],
];
const BY_COLS = ['slag', 'coke', 'sinter'];

function SourcePosition({ src }) {
  const pos = src.position;
  const dmt = pos.BSP && Object.keys(pos.BSP).some((k) => k.endsWith('_dmt'));
  return (
    <>
      <h4 style={{ margin: '4px 0 6px' }}>Iron & steel — month-end position (page 1)</h4>
      <table style={T}>
        <thead><tr><th style={th}>Plant</th>{POS_COLS.map(([k, l]) => <th key={k} style={th}>{l}</th>)}</tr></thead>
        <tbody>
          {PLANTS.map((p) => (
            <tr key={p} style={p === 'SAIL' ? sail : undefined}>
              <td style={tdl}>{p}</td>
              {POS_COLS.map(([k, , d]) => {
                const v = pos[p]?.[k];
                const sub = pos[p]?.[`${k}_dmt`];
                return <td key={k} style={{ ...td, ...(k === 'diff_plan' ? tone(v) : {}) }}>{fmt(v, d)}{sub != null && <div style={{ fontSize: 11, color: '#64748b' }}>{fmt(sub)} DMT</div>}</td>;
              })}
            </tr>
          ))}
        </tbody>
      </table>
      {dmt && <p style={{ fontSize: 12, color: '#64748b', margin: '4px 2px 0' }}>DMT: BSP&apos;s DMT rakes, included in its figures.</p>}

      <h4 style={{ margin: '16px 0 6px' }}>Slag, coke & sinter (page 1)</h4>
      <table style={T}>
        <thead>
          <tr><th style={th} rowSpan={2}>Plant</th>{BY_COLS.map((b) => <th key={b} style={th} colSpan={4}>{b.toUpperCase()}</th>)}</tr>
          <tr>{BY_COLS.map((b) => <Fragment key={b}><th style={th}>Plan/day</th><th style={th}>On date</th><th style={th}>Cumm.</th><th style={th}>Avg/day</th></Fragment>)}</tr>
        </thead>
        <tbody>
          {PLANTS.map((p) => (
            <tr key={p} style={p === 'SAIL' ? sail : undefined}>
              <td style={tdl}>{p}</td>
              {BY_COLS.map((b) => ['plan_avg_day', 'on_date', 'cumm', 'avg_day'].map((k) => {
                const v = pos[p]?.[`${b}_${k}`];
                return <td key={`${b}${k}`} style={td}>{v == null ? '' : fmt(v, k.includes('day') ? 2 : 0)}</td>;
              }))}
            </tr>
          ))}
        </tbody>
      </table>

      <h4 style={{ margin: '16px 0 6px' }}>Slab despatch (page 1)</h4>
      <table style={{ ...T, width: 'auto' }}>
        <thead><tr><th style={th}>From</th><th style={th}>To</th><th style={th}>Rakes</th><th style={th}>Qty (MT)</th></tr></thead>
        <tbody>
          {src.slab.map((s) => (
            <tr key={`${s.from_plant_code}${s.to_plant_code}`}>
              <td style={tdl}>{s.from_plant_code}</td><td style={tdl}>{s.to_plant_code}</td><td style={td}>{fmt(s.rakes)}</td><td style={td}>{fmt(s.qty_mt, 1)}</td>
            </tr>
          ))}
          <tr style={sail}><td style={tdl} colSpan={2}>Total</td>
            <td style={td}>{fmt(src.slab.reduce((a, s) => a + s.rakes, 0))}</td>
            <td style={td}>{fmt(src.slab.reduce((a, s) => a + (s.qty_mt || 0), 0), 1)}</td></tr>
        </tbody>
      </table>
      {src.slab_note && <p style={{ fontSize: 13, margin: '6px 2px 0' }}><b>Today&apos;s slab rake position:</b> {src.slab_note}</p>}
    </>
  );
}

function SourceTypes({ d }) {
  const months = d.fy_months;
  const src = d.source.types;
  const sailTypes = {};
  Object.values(src).forEach((byType) => Object.entries(byType).forEach(([t, byM]) => {
    sailTypes[t] = sailTypes[t] || {};
    Object.entries(byM).forEach(([m, v]) => { sailTypes[t][m] = (sailTypes[t][m] || 0) + v; });
  }));
  const blocks = [...PLANTS.slice(0, 5).map((p) => [p, src[p] || {}]), ['SAIL', sailTypes]];
  return (
    <table style={{ ...T, fontSize: 12.5 }}>
      <thead><tr><th style={th}>Plant</th><th style={th}>Type</th>{months.map((m) => <th key={m} style={th}>{mlabel(m)}</th>)}<th style={th}>FYTD</th></tr></thead>
      {blocks.map(([p, byType]) => {
        const typeNames = Object.keys(byType);
        const total = (m) => typeNames.reduce((a, t) => a + (byType[t][m] || 0), 0);
        const has = (m) => typeNames.some((t) => byType[t][m] != null);
        return (
          <tbody key={p}>
            {typeNames.map((t, i) => (
              <tr key={t}>
                {i === 0 && <td style={{ ...tdl, verticalAlign: 'middle' }} rowSpan={typeNames.length + 1}>{p}</td>}
                <td style={{ ...td, textAlign: 'left' }}>{t}</td>
                {months.map((m) => <td key={m} style={td}>{byType[t][m] == null ? '' : fmt(byType[t][m])}</td>)}
                <td style={{ ...td, fontWeight: 600 }}>{fmt(Object.values(byType[t]).reduce((a, v) => a + v, 0))}</td>
              </tr>
            ))}
            <tr style={sail}>
              <td style={{ ...td, textAlign: 'left' }}>TOTAL</td>
              {months.map((m) => <td key={m} style={td}>{has(m) ? fmt(total(m)) : ''}</td>)}
              <td style={td}>{fmt(months.reduce((a, m) => a + total(m), 0))}</td>
            </tr>
          </tbody>
        );
      })}
    </table>
  );
}

function SourceHistory({ trend }) {
  return (
    <table style={{ ...T, fontSize: 12.5 }}>
      <thead><tr><th style={th}>Plant</th><th style={th}>FY</th>{FY_MON.map((m) => <th key={m} style={th}>{m}</th>)}<th style={th}>Cumm.</th><th style={th}>Avg/month</th></tr></thead>
      {PLANTS.map((p) => (
        <tbody key={p}>
          {(trend[p] || []).map((s, i) => {
            const n = s.months.filter((v) => v != null).length;
            return (
              <tr key={s.fy} style={p === 'SAIL' ? sail : undefined}>
                {i === 0 && <td style={{ ...tdl, verticalAlign: 'middle' }} rowSpan={trend[p].length}>{p}</td>}
                <td style={{ ...td, textAlign: 'left', fontWeight: i === 0 ? 700 : 400 }}>{s.fy}</td>
                {s.months.map((v, j) => <td key={j} style={td}>{v == null ? '' : fmt(v)}</td>)}
                <td style={{ ...td, fontWeight: 600 }}>{fmt(s.total)}</td>
                <td style={td}>{n ? fmt(s.total / n, 1) : '–'}</td>
              </tr>
            );
          })}
        </tbody>
      ))}
    </table>
  );
}

function Collapsible({ title, sub, children }) {
  return (
    <details style={{ border: B, borderRadius: 8, background: '#fff', marginBottom: 12 }}>
      <summary style={{ cursor: 'pointer', padding: '10px 14px', fontWeight: 600 }}>
        {title} {sub && <span style={{ fontWeight: 400, color: '#64748b', fontSize: 13 }}>— {sub}</span>}
      </summary>
      <div style={{ padding: '4px 14px 14px', overflowX: 'auto' }}>{children}</div>
    </details>
  );
}

export default function RakeDespatchView() {
  const [months, setMonths] = useState(null);
  const [month, setMonth] = useState('');
  const [data, setData] = useState(null);
  const [status, setStatus] = useState(null);
  const [loading, setLoading] = useState(false);

  const load = (m) => {
    setMonth(m);
    setLoading(true);
    setStatus(null);
    fetch(`${API}/api/rake-despatch/report?month=${m}`)
      .then(async (r) => {
        const body = await r.json().catch(() => ({}));
        if (!r.ok) throw new Error(body.detail || `HTTP ${r.status}`);
        setData(body);
      })
      .catch((e) => setStatus({ type: 'error', text: e.message }))
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    fetch(`${API}/api/rake-despatch/months`).then((r) => r.json()).then((rows) => {
      setMonths(rows);
      if (rows.length) load(rows[0].report_month);
    }).catch((e) => setStatus({ type: 'error', text: `Could not load months: ${e.message}` }));
  }, []);

  return (
    <ReportPage title="Rake Despatch"
                description="Iron & steel rake loading from the Rail Movement Cell's monthly Despatch Summary Report, with plan attainment, history and run-rate insights."
                maxWidth={1400}>
      <FilterBar actions={<>
        {loading && <span className={es.ctxNote}>Loading…</span>}
        {data?.available && <span className={es.ctxNote}>Report as on {data.as_on} · {data.source_file}</span>}
      </>}>
        <Field label="Month" htmlFor="rd-month">
          <select id="rd-month" className={es.control} style={{ minWidth: 130 }} value={month} onChange={(e) => load(e.target.value)}>
            {(months || []).map((m) => <option key={m.report_month} value={m.report_month}>{mlabel(m.report_month)}</option>)}
          </select>
        </Field>
      </FilterBar>
      <Status status={status} />
      {months === null && !status && <Loading />}
      {months?.length === 0 && (
        <Empty>No Despatch Summary Report uploaded yet. Upload the month-end PDF on{' '}
          <Link href="/data-entry/uploads">Data Entry › Uploads</Link>.</Empty>
      )}
      {data && !data.available && <Empty>No report uploaded for {mlabel(data.report_month)}.</Empty>}
      {data?.available && (
        <>
          <Headline d={data} />
          <KeyPoints points={data.key_points} />
          <Ranking rows={data.ranking} month={data.report_month} />
          <RunRate rows={data.run_rate} />
          <Records rows={data.records} month={data.report_month} />
          <Trend trend={data.trend} />
          <WagonMix mix={data.wagon_mix} />
          <ExportWatch rows={data.export} />
          <h3 style={{ margin: '20px 0 8px', fontSize: 16 }}>Source data</h3>
          <Collapsible title="Month-end position, slag/coke/sinter & slab" sub="report page 1"><SourcePosition src={data.source} /></Collapsible>
          <Collapsible title={`Rakes by wagon type, FY ${data.fy}`} sub="report page 2"><SourceTypes d={data} /></Collapsible>
          <Collapsible title="Month-wise rakes, seven FYs" sub="report page 5 (current FY from page 2)"><SourceHistory trend={data.trend} /></Collapsible>
        </>
      )}
    </ReportPage>
  );
}
