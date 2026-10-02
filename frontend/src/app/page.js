'use client';

import React, { useEffect, useMemo, useState } from 'react';
import Link from 'next/link';
import GlobalNavbar from '@/components/GlobalNavbar';
import TechnoPerformanceCharts from '@/components/TechnoPerformanceCharts';
import s from './home.module.css';

const API = process.env.NEXT_PUBLIC_API_URL || '';

const PLANTS = [
  { code: 'BSP', name: 'Bhilai' }, { code: 'DSP', name: 'Durgapur' }, { code: 'RSP', name: 'Rourkela' },
  { code: 'BSL', name: 'Bokaro' }, { code: 'ISP', name: 'Burnpur' },
];
const PLANT_CODES = PLANTS.map(p => p.code);
// KPI tiles — SAIL (5 integrated plants) monthly totals
const TILES = [
  { key: 'Hot Metal',         label: 'Hot metal' },
  { key: 'Total Crude Steel', label: 'Crude steel' },
  { key: 'Saleable Steel',    label: 'Saleable steel' },
  { key: 'Finished Steel',    label: 'Finished steel' },
];
const MONTH_NAMES = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December'];

const monthName = (m) => `${MONTH_NAMES[Number(m.slice(5)) - 1]} ${m.slice(0, 4)}`;
const shortMonth = (m) => `${MONTH_NAMES[Number(m.slice(5)) - 1].slice(0, 3)}'${m.slice(2, 4)}`;
const fyOf = (m) => (Number(m.slice(5)) >= 4 ? Number(m.slice(0, 4)) : Number(m.slice(0, 4)) - 1);
const fyLabel = (y) => `${y}-${String(y + 1).slice(2)}`;
const fmt = (v, d = 2) => (v == null ? '—' : v.toLocaleString('en-IN', { minimumFractionDigits: d, maximumFractionDigits: d }));
const pctClass = (p) => (p == null ? '' : p >= 100 ? s.pillGood : p >= 95 ? s.pillMid : s.pillBad);
const statusOf = (p) => (p == null ? null
  : p >= 100 ? { text: 'Ahead of plan', dot: s.dotG, color: 'var(--ui-success)' }
  : p >= 95 ? { text: 'Near plan', dot: s.dotA, color: '#f9ab00' }
  : { text: 'Behind plan', dot: s.dotR, color: 'var(--ui-danger)' });

// Tiny trend line for a KPI tile
function Sparkline({ values }) {
  const pts = values.filter(v => v != null);
  if (pts.length < 2) return null;
  const W = 110, H = 32, min = Math.min(...pts), max = Math.max(...pts), span = max - min || 1;
  const step = W / (values.length - 1);
  const d = values.map((v, i) => (v == null ? null : `${(i * step).toFixed(1)},${(H - 3 - ((v - min) / span) * (H - 6)).toFixed(1)}`))
    .filter(Boolean).join(' ');
  const up = pts[pts.length - 1] >= pts[pts.length - 2];
  return (
    <svg className={s.spark} width={W} height={H} viewBox={`0 0 ${W} ${H}`} aria-hidden="true">
      <polyline points={d} fill="none" stroke={up ? '#188038' : '#1a73e8'} strokeWidth="2" strokeLinejoin="round" strokeLinecap="round" />
    </svg>
  );
}

export default function HomePage() {
  const [fyData, setFyData] = useState({});   // fy_start -> /api/production-fy response
  const [error, setError] = useState(null);
  const [month, setMonth] = useState(null);   // selected YYYY-MM (default: latest complete month)

  // Current and previous FY (previous one gives MoM for April and a 12-month trend)
  useEffect(() => {
    (async () => {
      try {
        const fys = (await (await fetch(`${API}/api/production-fys`)).json()).fys || [];
        if (!fys.length) throw new Error('no financial years with data');
        const latest = fys[0].fy_start;
        const loaded = await Promise.all([latest, latest - 1].map(async fy => {
          const r = await fetch(`${API}/api/production-fy?fy_start=${fy}`);
          return [fy, r.ok ? await r.json() : null];
        }));
        setFyData(Object.fromEntries(loaded));
      } catch (e) {
        setError(`Could not load production data: ${e.message}`);
      }
    })();
  }, []);

  // value(plant, item, kind, month) from the loaded FY datasets
  const value = useMemo(() => (plant, item, kind, m) => {
    const d = fyData[fyOf(m)];
    return d?.plants?.find(p => p.plant === plant)?.items?.find(i => i.item_name === item)?.[kind]?.[m] ?? null;
  }, [fyData]);

  // SAIL-5 total; null unless every plant reported (a partial sum would mislead)
  const sail5 = useMemo(() => (item, kind, m) => {
    const vals = PLANT_CODES.map(p => value(p, item, kind, m));
    return vals.some(v => v == null) ? null : vals.reduce((a, v) => a + v, 0);
  }, [value]);

  // Months (both FYs, oldest first) where all 5 plants reported hot metal
  const months = useMemo(() => Object.keys(fyData).map(Number).sort()
    .flatMap(fy => fyData[fy]?.months || [])
    .filter(m => sail5('Hot Metal', 'actual', m) != null), [fyData, sail5]);

  const sel = month && months.includes(month) ? month : months[months.length - 1];
  const selIdx = months.indexOf(sel);
  const prev = selIdx > 0 ? months[selIdx - 1] : null;
  const trend = months.slice(Math.max(0, selIdx - 11), selIdx + 1);

  const tiles = sel ? TILES.map(t => {
    const actual = sail5(t.key, 'actual', sel);
    const plan = sail5(t.key, 'plan', sel);
    const last = prev ? sail5(t.key, 'actual', prev) : null;
    return {
      ...t, actual,
      ach: actual != null && plan ? (actual / plan) * 100 : null,
      mom: actual != null && last ? ((actual - last) / last) * 100 : null,
      trend: trend.map(m => sail5(t.key, 'actual', m)),
    };
  }) : [];

  const plants = sel ? PLANTS.map(p => {
    const hm = value(p.code, 'Hot Metal', 'actual', sel);
    const hmPlan = value(p.code, 'Hot Metal', 'plan', sel);
    const cs = value(p.code, 'Total Crude Steel', 'actual', sel);
    const csPlan = value(p.code, 'Total Crude Steel', 'plan', sel);
    return {
      ...p, hm, hmPlan, cs,
      hmAch: hm != null && hmPlan ? (hm / hmPlan) * 100 : null,
      csAch: cs != null && csPlan ? (cs / csPlan) * 100 : null,
    };
  }) : [];
  const ranked = plants.filter(p => p.hmAch != null);
  const leader = [...ranked].sort((a, b) => b.hmAch - a.hmAch)[0];
  const laggard = [...ranked].sort((a, b) => a.hmAch - b.hmAch)[0];
  const topVolume = [...plants].filter(p => p.hm != null).sort((a, b) => b.hm - a.hm)[0];
  // null (shown as "—") when no plant has the value, e.g. a month without AAP plan
  const tot = (k) => plants.reduce((a, p) => (p[k] == null ? a : (a ?? 0) + p[k]), null);
  const totHm = tot('hm'), totHmPlan = tot('hmPlan'), totCs = tot('cs');
  const totAch = totHmPlan ? (totHm / totHmPlan) * 100 : null;

  const loading = !error && !Object.keys(fyData).length;

  return (
    <main className={s.main}>
      <GlobalNavbar />
      <div className={s.inner}>

        <header className={s.header}>
          <div>
            <span className={s.eyebrow}>Operations Directorate · MIS</span>
            <h1 className={s.title}>SAIL Operations Monthly Informatics</h1>
            <p className={s.lead}>
              Production, plan achievement and techno-economic performance of SAIL&apos;s five integrated
              steel plants, with data entry and publication of the monthly OMI report.
            </p>
          </div>
          <nav className={s.ctas} aria-label="Quick actions">
            <Link href="/records" className={`${s.cta} ${s.ctaPrimary}`}>🏆 Records dashboard</Link>
            <Link href="/data-entry" className={s.cta}>📋 Enter production data</Link>
            <Link href="/report" className={s.cta}>📄 {sel ? `${shortMonth(sel)} ` : ''}PDF report</Link>
            <Link href="/reports/production-analysis" className={s.cta}>📊 Month-wise production</Link>
          </nav>
        </header>

        <div className={s.status}>
          <span><i className={s.statusDot} />Showing <span className={s.statusStrong}>{sel ? monthName(sel) : '—'}</span>{sel && ` · FY ${fyLabel(fyOf(sel))}`}</span>
          <span className={s.statusSep} />
          <span>Scope: 5 integrated steel plants (BSP, DSP, RSP, BSL, ISP)</span>
          {months.length > 0 && (
            <>
              <span className={s.statusSep} />
              <label>Month{' '}
                <select className={s.select} value={sel} onChange={e => setMonth(e.target.value)}>
                  {[...months].reverse().map(m => <option key={m} value={m}>{monthName(m)}</option>)}
                </select>
              </label>
            </>
          )}
        </div>

        {error && <div className={s.error}>{error}</div>}
        {loading && <div className={s.state}>Loading production data…</div>}

        {sel && (
          <>
            <section className={s.kpis}>
              {tiles.map(t => (
                <div key={t.key} className={s.kpi}>
                  <div className={s.kpiHead}>
                    <span className={s.kpiLabel}>{t.label} · SAIL-5</span>
                    {t.ach != null && <span className={`${s.pill} ${pctClass(t.ach)}`}>{t.ach.toFixed(1)}% AAP</span>}
                  </div>
                  <div className={s.kpiValue}>{fmt(t.actual)}</div>
                  <div className={s.kpiUnit}>thousand tonnes (&apos;000 T)</div>
                  <div className={s.kpiFoot}>
                    {t.mom == null
                      ? <span className={`${s.delta} ${s.muted}`}>no previous month</span>
                      : <span className={`${s.delta} ${t.mom >= 0 ? s.up : s.down}`}>{t.mom >= 0 ? '↗ +' : '↘ '}{t.mom.toFixed(1)}% MoM</span>}
                    <Sparkline values={t.trend} />
                  </div>
                </div>
              ))}
            </section>

            <div className={s.grid}>
              <section className={s.card}>
                <div className={s.cardHead}>
                  <div>
                    <h2 className={s.cardTitle}>Integrated steel plants — monthly performance</h2>
                    <p className={s.cardSub}>Actual against Annual Action Plan (AAP) for {monthName(sel)}</p>
                  </div>
                  <Link href="/reports/highlights-records" className={s.cardLink}>Highlights →</Link>
                </div>

                {ranked.length > 0 && (
                  <div className={s.highlights}>
                    <div>
                      <div className={s.hlLabel}>Best hot metal plan achievement</div>
                      <div className={s.hlValue}>{leader.code} {leader.name}</div>
                      <div className={s.hlMeta} style={{ color: statusOf(leader.hmAch).color }}>{leader.hmAch.toFixed(1)}% of plan</div>
                    </div>
                    <div>
                      <div className={s.hlLabel}>Top hot metal volume</div>
                      <div className={s.hlValue}>{fmt(topVolume.hm)} kt</div>
                      <div className={s.hlMeta}>{topVolume.code} {topVolume.name}</div>
                    </div>
                    <div>
                      <div className={s.hlLabel}>Furthest from plan</div>
                      <div className={s.hlValue}>{laggard.code} {laggard.name}</div>
                      <div className={s.hlMeta} style={{ color: statusOf(laggard.hmAch).color }}>{laggard.hmAch.toFixed(1)}% of plan</div>
                    </div>
                  </div>
                )}

                <div className={s.tableWrap}>
                <table className={s.table}>
                  <thead>
                    <tr>
                      <th className={s.left}>Plant</th>
                      <th>Hot metal</th>
                      <th>AAP plan</th>
                      <th className={s.left}>HM % plan</th>
                      <th>Crude steel</th>
                      <th>CS % plan</th>
                      <th className={s.left}>Status</th>
                    </tr>
                  </thead>
                  <tbody>
                    {plants.map(p => {
                      const st = statusOf(p.hmAch);
                      return (
                        <tr key={p.code}>
                          <td className={`${s.left} ${s.plantCell}`}><i className={st?.dot || s.dotA} />{p.code} <span className={s.plantName}>{p.name}</span></td>
                          <td>{fmt(p.hm)}</td>
                          <td className={s.muted}>{fmt(p.hmPlan)}</td>
                          <td className={s.left}>
                            {p.hmAch == null ? '—' : (
                              <span className={s.barWrap}>
                                <span className={s.bar}><span className={s.barFill} style={{ width: `${Math.min(p.hmAch, 100)}%`, background: st.color }} /></span>
                                <b style={{ color: st.color }}>{p.hmAch.toFixed(1)}%</b>
                              </span>
                            )}
                          </td>
                          <td>{fmt(p.cs)}</td>
                          <td>{p.csAch == null ? '—' : <span className={`${s.pill} ${pctClass(p.csAch)}`}>{p.csAch.toFixed(1)}%</span>}</td>
                          <td className={s.left}>{st ? <span className={`${s.pill} ${pctClass(p.hmAch)}`}>{st.text}</span> : '—'}</td>
                        </tr>
                      );
                    })}
                    <tr className={s.totalRow}>
                      <td className={s.left}>SAIL — 5 plants</td>
                      <td>{fmt(totHm)}</td>
                      <td>{fmt(totHmPlan)}</td>
                      <td className={s.left}>{totAch == null ? '—' : `${totAch.toFixed(1)}%`}</td>
                      <td>{fmt(totCs)}</td>
                      <td />
                      <td />
                    </tr>
                  </tbody>
                </table>
                </div>
                <div className={s.tableNote}>
                  <span>Figures in &apos;000 T · status by hot metal plan achievement: ≥100% ahead · 95–99.9% near plan · &lt;95% behind</span>
                  <Link href="/reports/production-analysis" className={s.cardLink}>Full month-wise production →</Link>
                </div>
              </section>

              <section className={s.card}>
                <div className={s.cardHead}>
                  <div>
                    <h2 className={s.cardTitle}>Techno-economic efficiency</h2>
                    <p className={s.cardSub}>FY-to-date coal to hot metal, fuel rate, specific energy and CO₂ — 5 plants</p>
                  </div>
                  <Link href="/reports/techno" className={s.cardLink}>Techno reports →</Link>
                </div>
                <TechnoPerformanceCharts />
              </section>
            </div>
          </>
        )}

        <section className={s.card}>
          <div className={s.cardHead}>
            <h2 className={s.cardTitle}>Workflows</h2>
          </div>
          <div className={s.pads}>
            {[
              { href: '/data-entry', icon: '📋', kind: 'Input hub', color: 'var(--ui-primary)', title: 'Data entry hub', desc: 'Production, techno, mines, special steel and commentary forms' },
              { href: '/upload', icon: '🧮', kind: 'Ingestion', color: 'var(--ui-success)', title: 'Excel & PDF uploads', desc: 'Extract plant files, review, then insert into the database' },
              { href: '/report', icon: '📄', kind: 'Publication', color: '#7b1fa2', title: 'Monthly OMI report', desc: 'Preview, edit and export the monthly report PDF' },
              { href: '/records', icon: '🏆', kind: 'Records', color: '#b06000', title: 'All-time records', desc: 'Best-ever months, quarters, halves and years' },
            ].map(p => (
              <Link key={p.href} href={p.href} className={s.pad}>
                <div className={s.padTop}><span>{p.icon}</span><span className={s.padArrow}>→</span></div>
                <div className={s.padKind} style={{ color: p.color }}>{p.kind}</div>
                <div className={s.padTitle}>{p.title}</div>
                <div className={s.padDesc}>{p.desc}</div>
              </Link>
            ))}
          </div>
        </section>

        <footer className={s.footer}>
          <span>Steel Authority of India Limited · Operations Directorate · MIS Group</span>
          <span>Figures in &apos;000 tonnes · AAP = Annual Action Plan · MoM = change over the previous month</span>
        </footer>
      </div>
    </main>
  );
}
