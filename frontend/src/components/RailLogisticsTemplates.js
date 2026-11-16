'use client';

import React from 'react';

// Mirrors backend/page_templates/rail_logistics_{loading,mines,summary,history,wagon}.html
// — see backend/page_rail_logistics.py (pages 40.05-40.3). Colours copied
// from colors_config.json's rail_log_* / perf_app_* / perf_act_* keys.
const C = {
  title: 'rgb(0,0,255)',
  section: '#060177',
  secondary: '#475569',
  dark: '#334155',
  cardBg: '#F1F5F9',
  cardBorder: '#94A3B8',
  cardValue: '#060177',
  ok: '#C6EFCE',
  watch: '#FFEB9C',
  behind: '#FFC7CE',
  totalBg: '#EAE1F5',
  plantRule: '#1E293B',
  pos: '#006100',
  neg: '#9C0006',
  planBg: '#FFF2CC',
  planText: '#7F6000',
  actBg: '#C6EFCE',
  actText: '#006100',
};
const TINT = { ok: C.ok, watch: C.watch, behind: C.behind };

const fmt = (v, nd = 0) => (v === null || v === undefined ? '–' : Number(v).toFixed(nd));
const table = (fontSize) => ({ borderCollapse: 'collapse', width: '100%', tableLayout: 'fixed', fontSize, lineHeight: fontSize === '7.5pt' ? 1.1 : undefined });
const cell = (pad) => ({ border: `1px solid ${C.dark}`, padding: pad, textAlign: 'center', fontVariantNumeric: 'tabular-nums' });
const plan = { background: C.planBg, color: C.planText };
const act = { background: C.actBg, color: C.actText };
const total = { fontWeight: 700, background: C.totalBg };

function Signed({ v, nd = 1, suffix = '%' }) {
  if (v === null || v === undefined) return '–';
  return <span style={{ color: v >= 0 ? C.pos : C.neg }}>{v >= 0 ? '+' : ''}{fmt(v, nd)}{suffix}</span>;
}

function Head({ data }) {
  return (
    <>
      <div style={{ textAlign: 'center', fontWeight: 700, fontSize: '11pt', textDecoration: 'underline', color: C.title, marginBottom: 6 }}>{data.title}</div>
      <div style={{ textAlign: 'right', fontSize: '9pt', fontStyle: 'italic', color: C.secondary, marginBottom: 3 }}>{data.subtitle}</div>
    </>
  );
}

function Sec({ title, sub }) {
  return (
    <div style={{ fontWeight: 700, fontSize: '9.5pt', color: C.section, margin: '6pt 0 3pt' }}>
      {title}{sub && <span style={{ fontWeight: 400, fontStyle: 'italic', fontSize: '7.5pt', color: C.secondary }}> — {sub}</span>}
    </div>
  );
}

function Placeholder({ data }) {
  return <div style={{ textAlign: 'center', fontSize: '11pt', color: C.secondary, marginTop: '60mm' }}>{data.placeholder}</div>;
}

function Card({ title, value, sub }) {
  return (
    <div style={{ flex: 1, border: `1px solid ${C.cardBorder}`, background: C.cardBg, padding: '4pt 6pt' }}>
      <div style={{ fontSize: '7.5pt', color: C.secondary, fontWeight: 600 }}>{title}</div>
      <div style={{ fontSize: '15pt', fontWeight: 700, color: C.cardValue, lineHeight: 1.15 }}>{value}</div>
      <div style={{ fontSize: '7.5pt', color: C.secondary }}>{sub}</div>
    </div>
  );
}

export function RailLogisticsSummaryTemplate({ data }) {
  if (!data?.available) return <div><Head data={data || {}} /><Placeholder data={data || {}} /></div>;
  const h = data.headline;
  const c = cell('1.8pt 2pt');
  const l = { ...c, textAlign: 'left', fontWeight: 700 };
  const rowStyle = (p) => (p === 'SAIL' ? total : undefined);
  const rr = data.run_rate || [];
  return (
    <div>
      <Head data={data} />
      <div style={{ display: 'flex', gap: '5pt' }}>
        <Card title={`Steel rakes despatched, ${data.month_label}`} value={fmt(h.month_actual)}
              sub={`Plan ${fmt(h.month_plan)} · ${fmt(h.month_attainment, 1)}% · ${fmt(h.month_avg_day, 2)}/day vs ${fmt(h.month_plan_avg_day, 2)}`} />
        <Card title="vs same month last year" value={<Signed v={h.vs_ly_month_pct} />} sub={`Last year ${fmt(h.ly_month_actual)} rakes`} />
        <Card title="FY to date" value={fmt(h.fytd_actual)}
              sub={<>{h.fytd_plan != null && `Plan ${fmt(h.fytd_plan)} (${fmt(h.fytd_attainment, 1)}%) · `}LY {fmt(h.ly_fytd_actual)} (<Signed v={h.vs_ly_fytd_pct} />)</>} />
        <Card title="FY projection at current pace" value={fmt(h.fy_projection)}
              sub={<>Last FY {fmt(h.ly_fy_total)} (<Signed v={h.projection_vs_ly_pct} />)</>} />
      </div>

      <Sec title="Key points" sub="plant outward loading (steel rakes despatched from the plants)" />
      <ul style={{ margin: 0, paddingLeft: '14pt', fontSize: '8.5pt', lineHeight: 1.35 }}>
        {data.key_points.map((p, i) => <li key={i} style={{ marginBottom: '1.5pt' }}>{p}</li>)}
      </ul>

      <Sec title="Plan attainment" sub={`${data.month_label}, plants furthest behind plan first; plan = plan rakes/day × days in the month`} />
      <table style={table('8pt')}>
        <colgroup><col style={{ width: '9%' }} />{Array.from({ length: 9 }, (_, i) => <col key={i} />)}</colgroup>
        <thead><tr>
          <th style={c}>Plant</th><th style={{ ...c, ...plan }}>Plan</th><th style={{ ...c, ...act }}>Actual</th><th style={c}>Attainment</th>
          <th style={{ ...c, ...plan }}>Plan/day</th><th style={{ ...c, ...act }}>Actual/day</th><th style={c}>Gap/day</th>
          <th style={c}>FYTD</th><th style={c}>LY FYTD</th><th style={c}>FYTD vs LY</th>
        </tr></thead>
        <tbody>
          {data.ranking.map((r) => (
            <tr key={r.plant} style={rowStyle(r.plant)}>
              <td style={l}>{r.plant}</td>
              <td style={{ ...c, ...plan }}>{fmt(r.plan)}</td><td style={{ ...c, ...act }}>{fmt(r.actual)}</td>
              <td style={{ ...c, fontWeight: 700, background: TINT[r.tint] }}>{r.attainment == null ? '–' : `${fmt(r.attainment, 1)}%`}</td>
              <td style={{ ...c, ...plan }}>{fmt(r.plan_avg_day, 2)}</td><td style={{ ...c, ...act }}>{fmt(r.avg_day, 2)}</td>
              <td style={c}><Signed v={r.gap_per_day} nd={2} suffix="" /></td>
              <td style={c}>{fmt(r.fytd_actual)}</td><td style={c}>{fmt(r.ly_fytd_actual)}</td><td style={c}><Signed v={r.fytd_vs_ly_pct} /></td>
            </tr>
          ))}
        </tbody>
      </table>

      <Sec title="Run-rate to FY end"
           sub={`rakes/day needed for the rest of the FY to equal last FY's total, and where the FY ends at this month's plan rate or at the pace so far${rr.length ? `; ${rr[0].remaining_days} days left` : ''}`} />
      <table style={table('8pt')}>
        <colgroup><col style={{ width: '9%' }} />{Array.from({ length: 9 }, (_, i) => <col key={i} />)}</colgroup>
        <thead><tr>
          <th style={c}>Plant</th><th style={c}>FYTD</th><th style={{ ...c, ...act }}>FYTD avg/day</th><th style={{ ...c, ...act }}>Month avg/day</th>
          <th style={{ ...c, ...plan }}>Plan/day</th><th style={c}>Last FY total</th><th style={c}>Needed/day to match LY</th><th style={c}>Lift needed</th>
          <th style={c}>FY at plan rate</th><th style={c}>FY at current pace</th>
        </tr></thead>
        <tbody>
          {rr.map((r) => (
            <tr key={r.plant} style={rowStyle(r.plant)}>
              <td style={l}>{r.plant}</td><td style={c}>{fmt(r.fytd_actual)}</td>
              <td style={{ ...c, ...act }}>{fmt(r.fytd_avg_day, 2)}</td><td style={{ ...c, ...act }}>{fmt(r.month_avg_day, 2)}</td>
              <td style={{ ...c, ...plan }}>{fmt(r.plan_avg_day, 2)}</td><td style={c}>{fmt(r.ly_total)}</td>
              <td style={{ ...c, fontWeight: 700 }}>{fmt(r.required_avg_day_ly, 2)}</td>
              <td style={c}>{r.lift_needed_pct == null ? '–' : r.lift_needed_pct > 0
                ? <span style={{ color: C.neg }}>+{fmt(r.lift_needed_pct, 1)}%</span> : <span style={{ color: C.pos }}>On course</span>}</td>
              <td style={c}>{fmt(r.fy_at_plan_rate)}</td><td style={c}>{fmt(r.fy_at_current_pace)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function RailLogisticsHistoryTemplate({ data }) {
  if (!data?.available) return <div><Head data={data || {}} /><Placeholder data={data || {}} /></div>;
  const c = cell('0.6pt 2pt');
  const span = (plant) => data.trend.filter((r) => r.plant === plant).length;
  return (
    <div>
      <Head data={data} />
      <Sec title="Seven-year monthly trend" sub="steel rakes despatched per month, current FY first" />
      <table style={table('7.5pt')}>
        <colgroup><col style={{ width: '7%' }} /><col style={{ width: '9%' }} />{data.month_labels.map((m) => <col key={m} />)}<col style={{ width: '8%' }} /></colgroup>
        <thead><tr><th style={c}>Plant</th><th style={c}>FY</th>{data.month_labels.map((m) => <th key={m} style={c}>{m}</th>)}<th style={c}>Total</th></tr></thead>
        <tbody>
          {data.trend.map((r) => {
            const td = r.first_of_plant ? { ...c, borderTop: `1px solid ${C.plantRule}`, fontWeight: 700 } : c;
            return (
              <tr key={`${r.plant}-${r.fy}`}>
                {r.first_of_plant && <td style={{ ...td, verticalAlign: 'middle' }} rowSpan={span(r.plant)}>{r.plant}</td>}
                <td style={td}>{r.fy}</td>
                {r.months.map((v, i) => <td key={i} style={td}>{fmt(v)}</td>)}
                <td style={{ ...td, ...act }}>{fmt(r.total)}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

export function RailLogisticsWagonTemplate({ data }) {
  if (!data?.available) return <div><Head data={data || {}} /><Placeholder data={data || {}} /></div>;
  const c = cell('0.6pt 2pt');
  const l = { ...c, textAlign: 'left', fontWeight: 700 };
  const { mix, blocks, month_labels: months } = data;
  return (
    <div>
      <Head data={data} />
      <Sec title="Wagon-type mix"
           sub={`each wagon type's share of the plant's FY-to-date rakes; in brackets, how many percentage points that share moved (${mix.label}), the plant's biggest move in bold`} />
      {mix.rows.length === 0 ? (
        <div style={{ fontSize: '8pt', fontStyle: 'italic', color: C.secondary }}>No wagon-type data for this FY.</div>
      ) : (
        <table style={{ ...table('8pt'), lineHeight: 1.3 }}>
          <colgroup><col style={{ width: '8%' }} /><col style={{ width: '10%' }} /><col /></colgroup>
          <thead><tr><th style={c}>Plant</th><th style={{ ...c, ...act }}>FYTD rakes</th><th style={c}>Mix (share, shift in points)</th></tr></thead>
          <tbody>
            {mix.rows.map((r) => (
              <tr key={r.plant} style={r.plant === 'SAIL' ? total : undefined}>
                <td style={l}>{r.plant}</td>
                <td style={{ ...c, ...act }}>{fmt(r.fytd_total)}</td>
                <td style={{ ...c, textAlign: 'left', padding: '1.5pt 4pt' }}>
                  {r.types.map((t) => (
                    <span key={t.type} style={{ display: 'inline-block', whiteSpace: 'nowrap', marginRight: '9pt' }}>
                      <b>{t.type}</b> {fmt(t.share, 1)}%
                      {t.shift != null && (
                        <span style={{ color: t.shift >= 0 ? C.pos : C.neg, fontWeight: t.biggest ? 700 : 400 }}> ({t.shift >= 0 ? '+' : ''}{fmt(t.shift, 1)})</span>
                      )}
                    </span>
                  ))}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      <Sec title={`Rakes by wagon type, FY ${data.fy}`} sub="plant-wise, month by month" />
      {blocks.length === 0 ? (
        <div style={{ fontSize: '8pt', fontStyle: 'italic', color: C.secondary }}>No wagon-type data for this FY.</div>
      ) : (
        <table style={table('7.5pt')}>
          <colgroup><col style={{ width: '7%' }} /><col style={{ width: '10%' }} />{months.map((m) => <col key={m} />)}<col style={{ width: '8%' }} /></colgroup>
          <thead><tr><th style={c}>Plant</th><th style={c}>Wagon type</th>{months.map((m) => <th key={m} style={c}>{m}</th>)}<th style={{ ...c, ...act }}>FYTD</th></tr></thead>
          <tbody>
            {blocks.map((b) => (
              <React.Fragment key={b.plant}>
                {b.rows.map((r, i) => {
                  const td = i === 0 ? { ...c, borderTop: `1px solid ${C.plantRule}` } : c;
                  return (
                    <tr key={r.type}>
                      {i === 0 && <td style={{ ...td, fontWeight: 700, verticalAlign: 'middle' }} rowSpan={b.rows.length + 1}>{b.plant}</td>}
                      <td style={{ ...td, textAlign: 'left', fontWeight: 700 }}>{r.type}</td>
                      {r.months.map((v, k) => <td key={k} style={td}>{fmt(v)}</td>)}
                      <td style={{ ...td, ...act }}>{fmt(r.fytd)}</td>
                    </tr>
                  );
                })}
                <tr style={total}>
                  <td style={l}>Total</td>
                  {b.total.months.map((v, k) => <td key={k} style={c}>{fmt(v)}</td>)}
                  <td style={c}>{fmt(b.total.fytd)}</td>
                </tr>
              </React.Fragment>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}

// Rake count as backend/rail_loading.py's fmt_rakes: one decimal only where
// the figure has one (coking coal is reported as 46.3).
const fmtRakes = (v) => (v === null || v === undefined ? '–' : String(Math.round(Number(v) * 10) / 10));

// Page 40.05 — backend/page_templates/rail_logistics_loading.html (rail_loading.py).
export function RailLogisticsLoadingTemplate({ data }) {
  if (!data?.available) return <div><Head data={data || {}} /><Placeholder data={data || {}} /></div>;
  const c = cell('2.4pt 1pt');
  const { rows, month_labels: months } = data;
  const grand = { fontWeight: 700, ...plan };
  const INDENT = { item: '9pt', subitem: '18pt' };
  const label = (kind) => ({ ...c, textAlign: 'left', whiteSpace: 'nowrap', paddingLeft: INDENT[kind] || '3pt' });
  return (
    <div>
      <Head data={data} />
      <table style={{ ...table('8pt'), lineHeight: 1.15 }}>
        <colgroup>
          <col style={{ width: '26%' }} />{months.map((m) => <col key={m} style={{ width: '4.9%' }} />)}
          <col style={{ width: '7.6%' }} /><col style={{ width: '7.6%' }} />
        </colgroup>
        <thead>
          <tr>
            <th style={c}>Rakes loaded</th>{months.map((m) => <th key={m} style={c}>{m}</th>)}
            <th style={{ ...c, ...act }}>FYTD</th><th style={c}>FYTD rakes / day</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => {
            if (r.kind === 'group') {
              return (
                <tr key={r.code}>
                  <td colSpan={months.length + 3} style={{ ...c, textAlign: 'left', paddingLeft: '3pt', fontWeight: 700, color: C.section, background: C.cardBg }}>{r.label}</td>
                </tr>
              );
            }
            if (r.kind === 'sub') {
              return (
                <tr key={r.code}>
                  <td colSpan={months.length + 3} style={{ ...c, textAlign: 'left', paddingLeft: '9pt', fontWeight: 700 }}>{r.label}</td>
                </tr>
              );
            }
            const perDay = r.kind === 'per_day';
            const plain = r.kind === 'item' || r.kind === 'subitem';
            const row = r.kind === 'total' ? total : (r.kind === 'grand' || perDay) ? grand : undefined;
            return (
              <tr key={r.code} style={row}>
                <td style={label(r.kind)}>{r.label}</td>
                {r.months.map((v, k) => <td key={k} style={perDay ? { ...c, fontSize: '7.5pt' } : c}>{perDay ? fmt(v, 2) : fmtRakes(v)}</td>)}
                <td style={plain ? { ...c, ...act } : c}>{perDay ? '' : fmtRakes(r.fytd)}</td>
                <td style={c}>{fmt(r.fytd_per_day, 2)}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

// Page 40.07 — backend/page_templates/rail_logistics_mines.html (iron_ore_rakes.py).
export function RailLogisticsMinesTemplate({ data }) {
  if (!data?.available) return <div><Head data={data || {}} /><Placeholder data={data || {}} /></div>;
  const c = cell('1pt 2pt');
  const l = { ...c, textAlign: 'left', fontWeight: 700, whiteSpace: 'nowrap' };
  const { mix, blocks, trend, month_labels: months } = data;
  const span = (group) => trend.filter((r) => r.plant === group).length;
  return (
    <div>
      <Head data={data} />
      {data.key_points.length > 0 && (
        <>
          <Sec title="Key points" sub="iron ore rakes loaded at the mines, all destinations" />
          <ul style={{ margin: 0, paddingLeft: '14pt', fontSize: '8.5pt', lineHeight: 1.35 }}>
            {data.key_points.map((p, i) => <li key={i} style={{ marginBottom: '1.5pt' }}>{p}</li>)}
          </ul>
        </>
      )}

      <Sec title="Seven-year monthly trend" sub="iron ore rakes loaded per month, current FY first" />
      <table style={table('7.5pt')}>
        <colgroup><col style={{ width: '7%' }} /><col style={{ width: '9%' }} />{months.map((m) => <col key={m} />)}<col style={{ width: '8%' }} /></colgroup>
        <thead><tr><th style={c}>Mines</th><th style={c}>FY</th>{months.map((m) => <th key={m} style={c}>{m}</th>)}<th style={c}>Total</th></tr></thead>
        <tbody>
          {trend.map((r) => {
            const td = r.first_of_plant ? { ...c, borderTop: `1px solid ${C.plantRule}`, fontWeight: 700 } : c;
            return (
              <tr key={`${r.plant}-${r.fy}`}>
                {r.first_of_plant && <td style={{ ...td, verticalAlign: 'middle' }} rowSpan={span(r.plant)}>{r.plant}</td>}
                <td style={td}>{r.fy}</td>
                {r.months.map((v, i) => <td key={i} style={td}>{fmt(v)}</td>)}
                <td style={{ ...td, ...act }}>{fmt(r.total)}</td>
              </tr>
            );
          })}
        </tbody>
      </table>

      <Sec title="Wagon-type mix"
           sub={`each wagon type's share of the group's FY-to-date rakes; in brackets, how many percentage points that share moved (${mix.label}), the group's biggest move in bold`} />
      <table style={{ ...table('8pt'), lineHeight: 1.3 }}>
        <colgroup><col style={{ width: '8%' }} /><col style={{ width: '10%' }} /><col /></colgroup>
        <thead><tr><th style={c}>Mines</th><th style={{ ...c, ...act }}>FYTD rakes</th><th style={c}>Mix (share, shift in points)</th></tr></thead>
        <tbody>
          {mix.rows.map((r) => (
            <tr key={r.plant} style={r.plant === 'Total' ? total : undefined}>
              <td style={l}>{r.plant}</td>
              <td style={{ ...c, ...act }}>{fmt(r.fytd_total)}</td>
              <td style={{ ...c, textAlign: 'left', padding: '1.5pt 4pt' }}>
                {r.types.map((t) => (
                  <span key={t.type} style={{ display: 'inline-block', whiteSpace: 'nowrap', marginRight: '9pt' }}>
                    <b>{t.type}</b> {fmt(t.share, 1)}%
                    {t.shift != null && (
                      <span style={{ color: t.shift >= 0 ? C.pos : C.neg, fontWeight: t.biggest ? 700 : 400 }}> ({t.shift >= 0 ? '+' : ''}{fmt(t.shift, 1)})</span>
                    )}
                  </span>
                ))}
              </td>
            </tr>
          ))}
        </tbody>
      </table>

      <Sec title={`Rakes by wagon type, FY ${data.fy}`} sub="mines group-wise, month by month" />
      <table style={table('7.5pt')}>
        <colgroup><col style={{ width: '7%' }} /><col style={{ width: '17%' }} />{months.map((m) => <col key={m} />)}<col style={{ width: '8%' }} /></colgroup>
        <thead><tr><th style={c}>Mines</th><th style={c}>Wagon type</th>{months.map((m) => <th key={m} style={c}>{m}</th>)}<th style={{ ...c, ...act }}>FYTD</th></tr></thead>
        <tbody>
          {blocks.map((b) => (
            <React.Fragment key={b.plant}>
              {b.rows.map((r, i) => {
                const td = i === 0 ? { ...c, borderTop: `1px solid ${C.plantRule}` } : c;
                return (
                  <tr key={r.type}>
                    {i === 0 && <td style={{ ...td, fontWeight: 700, verticalAlign: 'middle' }} rowSpan={b.rows.length + 1}>{b.plant}</td>}
                    <td style={{ ...td, textAlign: 'left', fontWeight: 700, whiteSpace: 'nowrap' }}>{r.type}</td>
                    {r.months.map((v, k) => <td key={k} style={td}>{fmt(v)}</td>)}
                    <td style={{ ...td, ...act }}>{fmt(r.fytd)}</td>
                  </tr>
                );
              })}
              <tr style={total}>
                <td style={l}>Total</td>
                {b.total.months.map((v, k) => <td key={k} style={c}>{fmt(v)}</td>)}
                <td style={c}>{fmt(b.total.fytd)}</td>
              </tr>
            </React.Fragment>
          ))}
        </tbody>
      </table>
    </div>
  );
}
