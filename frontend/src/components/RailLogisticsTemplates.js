'use client';

import React from 'react';

// Mirrors backend/page_templates/rail_logistics_{summary,history,wagon}.html
// — see backend/page_rail_logistics.py (pages 40.1-40.3). Colours copied
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
        <Card title={`SAIL rakes, ${data.month_label}`} value={fmt(h.month_actual)}
              sub={`Plan ${fmt(h.month_plan)} · ${fmt(h.month_attainment, 1)}% · ${fmt(h.month_avg_day, 2)}/day vs ${fmt(h.month_plan_avg_day, 2)}`} />
        <Card title="vs same month last year" value={<Signed v={h.vs_ly_month_pct} />} sub={`Last year ${fmt(h.ly_month_actual)} rakes`} />
        <Card title="FY to date" value={fmt(h.fytd_actual)}
              sub={<>{h.fytd_plan != null && `Plan ${fmt(h.fytd_plan)} (${fmt(h.fytd_attainment, 1)}%) · `}LY {fmt(h.ly_fytd_actual)} (<Signed v={h.vs_ly_fytd_pct} />)</>} />
        <Card title="FY projection at current pace" value={fmt(h.fy_projection)}
              sub={<>Last FY {fmt(h.ly_fy_total)} (<Signed v={h.projection_vs_ly_pct} />)</>} />
      </div>

      <Sec title="Commodity-wise rakes loaded" sub="slag, coke & sinter (month-end position); slab despatch between plants" />
      <table style={table('8pt')}>
        <colgroup><col style={{ width: '9%' }} />{Array.from({ length: 12 }, (_, i) => <col key={i} />)}</colgroup>
        <thead>
          <tr><th style={c} rowSpan={2}>Plant</th><th style={c} colSpan={4}>Slag</th><th style={c} colSpan={4}>Coke</th><th style={c} colSpan={4}>Sinter</th></tr>
          <tr>{[0, 1, 2].map((i) => (
            <React.Fragment key={i}><th style={c}>On date</th><th style={c}>Cumm.</th><th style={{ ...c, ...act }}>Avg/day</th><th style={{ ...c, ...plan }}>Plan/day</th></React.Fragment>
          ))}</tr>
        </thead>
        <tbody>
          {data.commodity.map((r) => (
            <tr key={r.plant} style={rowStyle(r.plant)}>
              <td style={l}>{r.plant}</td>
              {['slag', 'coke', 'sinter'].map((k) => (
                <React.Fragment key={k}>
                  <td style={c}>{fmt(r[k].on_date)}</td><td style={c}>{fmt(r[k].cumm)}</td>
                  <td style={{ ...c, ...act }}>{fmt(r[k].avg_day, 2)}</td><td style={{ ...c, ...plan }}>{fmt(r[k].plan_avg_day, 2)}</td>
                </React.Fragment>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
      {data.slab?.length > 0 && (
        <table style={{ ...table('8pt'), width: '60%', marginTop: '4pt' }}>
          <thead><tr><th style={c}>Slab despatch from</th><th style={c}>To</th><th style={c}>Rakes</th><th style={c}>Qty (MT)</th></tr></thead>
          <tbody>{data.slab.map((s, i) => (
            <tr key={i}><td style={c}>{s.from_plant_code}</td><td style={c}>{s.to_plant_code}</td><td style={c}>{fmt(s.rakes)}</td><td style={c}>{fmt(s.qty_mt, 1)}</td></tr>
          ))}</tbody>
        </table>
      )}
      {data.slab_note && <div style={{ fontSize: '7.5pt', fontStyle: 'italic', color: C.secondary, marginTop: '2pt' }}>{data.slab_note}</div>}

      <Sec title="Key points" />
      <ul style={{ margin: 0, paddingLeft: '14pt', fontSize: '8.5pt', lineHeight: 1.35 }}>
        {data.key_points.map((p, i) => <li key={i} style={{ marginBottom: '1.5pt' }}>{p}</li>)}
      </ul>

      <Sec title="Plan attainment" sub={`${data.month_label}, plants furthest behind plan first; plan = plan rakes/day × days in the month`} />
      <table style={table('8pt')}>
        <colgroup><col style={{ width: '9%' }} />{Array.from({ length: 9 }, (_, i) => <col key={i} />)}</colgroup>
        <thead><tr>
          <th style={c}>Plant</th><th style={{ ...c, ...act }}>Actual</th><th style={{ ...c, ...plan }}>Plan</th><th style={c}>Attainment</th>
          <th style={{ ...c, ...act }}>Avg/day</th><th style={{ ...c, ...plan }}>Plan/day</th><th style={c}>Gap/day</th>
          <th style={c}>FYTD</th><th style={c}>LY FYTD</th><th style={c}>FYTD vs LY</th>
        </tr></thead>
        <tbody>
          {data.ranking.map((r) => (
            <tr key={r.plant} style={rowStyle(r.plant)}>
              <td style={l}>{r.plant}</td>
              <td style={{ ...c, ...act }}>{fmt(r.actual)}</td><td style={{ ...c, ...plan }}>{fmt(r.plan)}</td>
              <td style={{ ...c, fontWeight: 700, background: TINT[r.tint] }}>{r.attainment == null ? '–' : `${fmt(r.attainment, 1)}%`}</td>
              <td style={{ ...c, ...act }}>{fmt(r.avg_day, 2)}</td><td style={{ ...c, ...plan }}>{fmt(r.plan_avg_day, 2)}</td>
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
  const l = { ...c, textAlign: 'left', fontWeight: 700 };
  const mon = data.month_label.slice(0, 3);
  const span = (plant) => data.trend.filter((r) => r.plant === plant).length;
  const plants = data.export_plants;
  return (
    <div>
      <Head data={data} />
      <Sec title="Records & seasonality" sub={`how ${data.month_label} ranks against every stored ${mon}, and the best month and FY on record`} />
      <table style={table('7.5pt')}>
        <colgroup><col style={{ width: '9%' }} /><col style={{ width: '10%' }} /><col style={{ width: '11%' }} /><col /><col /><col /><col /></colgroup>
        <thead><tr>
          <th style={c}>Plant</th><th style={{ ...c, ...act }}>{data.month_label}</th><th style={c}>Rank among {mon}s</th>
          <th style={c}>Best {mon}</th><th style={c}>Lowest {mon}</th><th style={c}>Best month ever</th><th style={c}>Best FY</th>
        </tr></thead>
        <tbody>
          {data.records.map((r) => (
            <tr key={r.plant} style={r.plant === 'SAIL' ? total : undefined}>
              <td style={l}>{r.plant}</td><td style={{ ...c, ...act }}>{fmt(r.actual)}</td><td style={c}>{r.rank}</td>
              <td style={c}>{r.same_best}</td><td style={c}>{r.same_worst}</td>
              <td style={c}>{r.best_month}{r.is_best_month_ever ? ' ★' : ''}</td><td style={c}>{r.best_fy}</td>
            </tr>
          ))}
        </tbody>
      </table>

      <Sec title="Seven-year monthly trend" sub="rakes per month, current FY first" />
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

      <Sec title="Export" sub="export rakes, programme / actual by destination" />
      {data.export.length === 0 ? (
        <div style={{ fontSize: '8pt', fontStyle: 'italic', color: C.secondary }}>No export programme for {data.month_label}.</div>
      ) : (
        <table style={table('7.5pt')}>
          <colgroup><col style={{ width: '19%' }} />{Array.from({ length: plants.length * 2 + 3 }, (_, i) => <col key={i} />)}</colgroup>
          <thead>
            <tr><th style={c} rowSpan={2}>Destination</th>{plants.map((p) => <th key={p} style={c} colSpan={2}>{p}</th>)}<th style={c} colSpan={3}>SAIL</th></tr>
            <tr>{plants.map((p) => (
              <React.Fragment key={p}><th style={{ ...c, ...plan }}>Prog</th><th style={{ ...c, ...act }}>Act</th></React.Fragment>
            ))}<th style={{ ...c, ...plan }}>Prog</th><th style={{ ...c, ...act }}>Act</th><th style={c}>%</th></tr>
          </thead>
          <tbody>
            {data.export.map((r) => (
              <tr key={r.destination} style={r.is_total ? total : undefined}>
                <td style={l}>{r.destination}</td>
                {plants.map((p) => {
                  const v = r.plants[p];
                  return (
                    <React.Fragment key={p}>
                      <td style={{ ...c, ...plan }}>{v ? fmt(v.prog) : '–'}</td><td style={{ ...c, ...act }}>{v ? fmt(v.actual) : '–'}</td>
                    </React.Fragment>
                  );
                })}
                <td style={{ ...c, ...plan }}>{fmt(r.prog)}</td><td style={{ ...c, ...act }}>{fmt(r.actual)}</td>
                <td style={c}>{r.fulfilment == null ? '–' : <span style={{ color: r.actual >= r.prog ? C.pos : C.neg }}>{fmt(r.fulfilment)}%</span>}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
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
      <Sec title="Wagon-type mix" sub={`share of FY-to-date rakes by wagon type (%); shift: ${mix.label}`} />
      <table style={table('7.5pt')}>
        <colgroup><col style={{ width: '14%' }} />{mix.plants.map((p) => <col key={p} />)}<col /><col /></colgroup>
        <thead><tr><th style={c}>Wagon type</th>{mix.plants.map((p) => <th key={p} style={c}>{p}</th>)}<th style={{ ...c, ...total }}>SAIL</th><th style={c}>SAIL shift (pp)</th></tr></thead>
        <tbody>
          {mix.rows.map((r) => (
            <tr key={r.type}>
              <td style={l}>{r.type}</td>
              {mix.plants.map((p) => <td key={p} style={c}>{fmt(r.shares[p], 1)}</td>)}
              <td style={{ ...c, ...total }}>{fmt(r.sail_share, 1)}</td>
              <td style={c}><Signed v={r.sail_shift} suffix="" /></td>
            </tr>
          ))}
        </tbody>
      </table>

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
