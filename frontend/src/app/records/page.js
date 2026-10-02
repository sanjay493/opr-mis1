'use client';

import React, { useState, useEffect, useRef } from 'react';
import GlobalNavbar from '@/components/GlobalNavbar';
import s from './records.module.css';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || '';

const ITEMS   = ['Hot Metal', 'Total Crude Steel', 'Saleable Steel'];
const ITEM_SHORT = { 'Hot Metal': 'Hot Metal', 'Total Crude Steel': 'Crude Steel', 'Saleable Steel': 'Saleable Steel' };
const GROUPS = [['sail5', '5 Plants'], ['all8', 'All 8']];
const GROUP_LABEL = { sail5: 'SAIL-5 integrated plants', all8: 'All 8 plants' };

// Keys of /api/production-records' fy_quarters / fy_halves (page_records.py
// _Q_LABELS / _H_LABELS) — must match them exactly.
const FY_QUARTERS = ['Q1','Q2','Q3','Q4'];
const FY_HALVES   = ['H1','H2'];
const SECTIONS    = ['Calendar Month','FY Quarter','FY Half','Top 5 Years'];
const ROTATE_MS   = 5 * 60 * 1000;

// FY month order, split into the two half-year "cycles" the month chart pages through
const FY_MONTHS = [
  { num: 4, name: 'April' }, { num: 5, name: 'May' }, { num: 6, name: 'June' },
  { num: 7, name: 'July' }, { num: 8, name: 'August' }, { num: 9, name: 'September' },
  { num: 10, name: 'October' }, { num: 11, name: 'November' }, { num: 12, name: 'December' },
  { num: 1, name: 'January' }, { num: 2, name: 'February' }, { num: 3, name: 'March' },
];
const CYCLES = [{ label: 'Apr–Sep', from: 0 }, { label: 'Oct–Mar', from: 6 }];

// Bar colours: the all-time top 3 of the bests in rank colours, other bests
// in deep blue, and the 2nd best of the same period in light blue beside it.
const RANK_COLOR = { 1: '#d97706', 2: '#9aa0a6', 3: '#a85a36' };
const BEST_COLOR = '#1967d2';
const SECOND_COLOR = '#a8c7fa';

function fmt(v) {
  if (v == null) return '—';
  return Number(v).toLocaleString('en-IN', { minimumFractionDigits: 3, maximumFractionDigits: 3 });
}
function fmt1(v) {
  if (v == null) return '—';
  return Number(v).toLocaleString('en-IN', { minimumFractionDigits: 1, maximumFractionDigits: 1 });
}
function fmtDelta(best, second) {
  const d = best - second;
  const pct = second ? (d / second) * 100 : null;
  const sign = d >= 0 ? '+' : '−';
  return `${sign}${fmt1(Math.abs(d))}${pct != null ? ` (${sign}${Math.abs(pct).toFixed(1)}%)` : ''}`;
}
// Year chips inside the bars: month "2026-03" -> "'26", FY "2023-24" -> "23-24"
const monthYear = (month) => (month ? `'${month.slice(2, 4)}` : '');
const fyShort = (fy) => (fy ? fy.slice(2) : '');

// Best and runner-up across a set of {period,total} rows
function bestTwo(rows) {
  const sorted = [...rows].filter(r => r && r.total != null).sort((a, b) => b.total - a.total);
  return [sorted[0], sorted[1]];
}

// ── Segmented control ──────────────────────────────────────────────────────
function Segmented({ options, value, onChange, label }) {
  return (
    <div className={s.segmented} role="group" aria-label={label}>
      {options.map(([key, text]) => (
        <button key={key} type="button" onClick={() => onChange(key)}
                className={`${s.segBtn} ${value === key ? s.segBtnActive : ''}`}
                aria-pressed={value === key}>
          {text}
        </button>
      ))}
    </div>
  );
}

// ── KPI tile ───────────────────────────────────────────────────────────────
function Kpi({ label, best, second, gold }) {
  return (
    <div className={`${s.kpi} ${gold ? s.kpiGold : ''}`}>
      <div className={s.kpiLabel}>{label}</div>
      <div className={s.kpiValue}>{fmt(best?.total)}<span className={s.kpiUnit}>&apos;000 T</span></div>
      <div className={s.kpiFoot}>
        <span className={s.kpiPeriod}>{best?.period ?? '—'}</span>
        {best && second
          ? <span className={s.kpiDelta} title={`2nd best: ${second.period} — ${fmt(second.total)}`}>
              ▲ {fmtDelta(best.total, second.total)} vs {second.period}
            </span>
          : <span className={s.kpiDeltaMuted}>no runner-up yet</span>}
      </div>
    </div>
  );
}

// ── Paired best / 2nd-best column chart ────────────────────────────────────
// entries: [{ label, best: {total, chip, period}, second: {total, chip, period} | null }]
function RecordChart({ entries }) {
  if (!entries.length) return <div className={s.empty}>No data available</div>;
  const max = Math.max(...entries.flatMap(e => [e.best.total, e.second?.total || 0]), 1);
  const ranked = [...entries].sort((a, b) => b.best.total - a.best.total);
  return <RecordChartView entries={entries} rankOf={e => ranked.indexOf(e) + 1} max={max} />;
}

function RecordChartView({ entries, rankOf, max }) {
  return (
    <div className={s.chart}>
      {entries.map((e) => {
        const rank = rankOf(e);
        const bestColor = RANK_COLOR[rank] || BEST_COLOR;
        const bars = [
          { ...e.best, color: bestColor, main: true },
          ...(e.second ? [{ ...e.second, color: SECOND_COLOR, main: false }] : []),
        ];
        return (
          <div key={e.label} className={`${s.group} ${rank === 1 ? s.groupRecord : ''}`}>
            <div className={s.bars}>
              {bars.map((b, i) => (
                <div key={i} className={s.barCol} title={`${b.period}: ${fmt(b.total)} '000 T`}>
                  <span className={`${s.barValue} ${b.main ? '' : s.barValueSecond}`}
                        style={b.main ? { color: bestColor } : undefined}>
                    {b.main && rank <= 3 ? (rank === 1 ? '🏆 ' : `#${rank} `) : ''}{fmt1(b.total)}
                  </span>
                  <div className={s.bar}
                       style={{ height: `${Math.max((b.total / max) * 100, 8)}%`, background: b.color }}>
                    {b.chip ? <span className={`${s.yearChip} ${b.main ? '' : s.yearChipDark}`}>{b.chip}</span> : <span />}
                    {b.main && rank === 1 && <span className={s.barTag}>Record</span>}
                  </div>
                </div>
              ))}
            </div>
            <div className={s.groupLabel} style={rank === 1 ? { color: RANK_COLOR[1] } : undefined}>{e.label}</div>
            {e.ranked ? null : e.second
              ? <div className={s.groupDelta} title="Best minus 2nd best of the same period">{fmtDelta(e.best.total, e.second.total)}</div>
              : <div className={s.groupDeltaNone}>no 2nd best yet</div>}
          </div>
        );
      })}
    </div>
  );
}

// ── Data shaping per section ───────────────────────────────────────────────
function monthEntries(grp, item) {
  const cal = grp?.cal_months?.[item] || {};
  return FY_MONTHS.map(({ num, name }) => {
    const rows = cal[num] || [];
    if (!rows.length) return null;
    return {
      label: name,
      best:   { total: rows[0].total, period: rows[0].period, chip: monthYear(rows[0].month) },
      second: rows[1] ? { total: rows[1].total, period: rows[1].period, chip: monthYear(rows[1].month) } : null,
    };
  });
}
function periodEntries(grp, key, labels, item) {
  const data = grp?.[key]?.[item] || {};
  return labels.map(l => {
    const rows = data[l] || [];
    if (!rows.length) return null;
    return {
      label: l,
      best:   { total: rows[0].total, period: `${rows[0].period} ${l}`, chip: fyShort(rows[0].period) },
      second: rows[1] ? { total: rows[1].total, period: `${rows[1].period} ${l}`, chip: fyShort(rows[1].period) } : null,
    };
  }).filter(Boolean);
}
// Top-5 year lists are a plain ranking — no "2nd best of the same period"
const yearEntries = (rows) => (rows || []).map(r => ({
  label: r.period, best: { total: r.total, period: r.period, chip: null }, second: null, ranked: true,
}));

// ── Ranked list (podium / top years) ───────────────────────────────────────
function RankedList({ rows, metaOf }) {
  if (!rows?.length) return <div className={s.empty}>No data available</div>;
  const medal = ['🥇', '🥈', '🥉'];
  const tag = ['Rank #1', 'Rank #2', 'Rank #3'];
  return (
    <div className={s.rankList}>
      {rows.map((r, i) => (
        <div key={r.period} className={`${s.rankRow} ${[s.rank1, s.rank2, s.rank3][i] || ''}`}>
          <span className={s.rankNum}>{medal[i] || i + 1}</span>
          <div>
            <div className={s.rankValue}>{fmt(r.total)}</div>
            <div className={s.rankMeta}>{metaOf(r)}</div>
          </div>
          <span className={s.rankTag}>{tag[i] || `#${i + 1}`}</span>
        </div>
      ))}
    </div>
  );
}

// ── Main page ──────────────────────────────────────────────────────────────
export default function RecordsPage() {
  const [data,    setData]    = useState(null);
  const [loading, setLoading] = useState(true);
  const [error,   setError]   = useState(null);
  const [group,   setGroup]   = useState('sail5');   // sail5 | all8
  const [item,    setItem]    = useState(ITEMS[0]);
  const [section, setSection] = useState(SECTIONS[0]);
  const [cycle,   setCycle]   = useState(0);         // month chart: 0 = Apr–Sep, 1 = Oct–Mar
  const [autoRotate, setAutoRotate] = useState(true);
  const [nextAt,  setNextAt]  = useState(() => Date.now() + ROTATE_MS);
  const [now,     setNow]     = useState(() => Date.now());
  const mainRef = useRef(null);

  useEffect(() => {
    fetch(`${API_BASE}/api/production-records`)
      .then(r => { if (!r.ok) throw new Error(r.statusText); return r.json(); })
      .then(d => { setData(d); setLoading(false); })
      .catch(e => { setError(e.message); setLoading(false); });
  }, []);

  // Auto-rotate the period view every 5 minutes; a 1s tick drives the countdown
  useEffect(() => {
    if (!autoRotate) return;
    const id = setInterval(() => {
      const t = Date.now();
      setNow(t);
      if (t >= nextAt) {
        setSection(prev => SECTIONS[(SECTIONS.indexOf(prev) + 1) % SECTIONS.length]);
        setNextAt(t + ROTATE_MS);
      }
    }, 1000);
    return () => clearInterval(id);
  }, [autoRotate, nextAt]);

  const pickSection = (sec) => { setSection(sec); setAutoRotate(false); };
  const resumeAuto = () => { setNextAt(Date.now() + ROTATE_MS); setNow(Date.now()); setAutoRotate(true); };
  const toggleFullscreen = () => {
    if (document.fullscreenElement) document.exitFullscreen();
    else mainRef.current?.requestFullscreen?.();
  };

  const grp = data?.[group];
  const months = monthEntries(grp, item);
  const allMonths = months.filter(Boolean);
  const quarters = periodEntries(grp, 'fy_quarters', FY_QUARTERS, item);
  const halves   = periodEntries(grp, 'fy_halves', FY_HALVES, item);

  // KPI tiles: best and runner-up across every period of that kind
  const top5m = grp?.top5_months?.[item] || [];
  const [bQ, sQ] = bestTwo(quarters.flatMap(q => [q.best, q.second]));
  const [bH, sH] = bestTwo(halves.flatMap(h => [h.best, h.second]));
  const topFy = grp?.top5_fy?.[item] || [];

  const nextSection = SECTIONS[(SECTIONS.indexOf(section) + 1) % SECTIONS.length];
  const secsLeft = Math.max(0, Math.round((nextAt - now) / 1000));
  const countdown = `${Math.floor(secsLeft / 60)}:${String(secsLeft % 60).padStart(2, '0')}`;

  // Month chart pages through the two half-year cycles; the rank colours
  // still compare against all 12 months, so pass ranks via the full list.
  const cycleMonths = months.slice(CYCLES[cycle].from, CYCLES[cycle].from + 6).filter(Boolean);

  return (
    <>
      <GlobalNavbar />
      <main ref={mainRef} className={s.main}>
        <div className={s.inner}>
          <header className={s.header}>
            <div>
              <div className={s.badges}>
                <span className={s.badgeBlue}>All-time records</span>
                {autoRotate
                  ? <span className={s.badgeLive}>● Auto-rotation · next view: {nextSection} in {countdown}</span>
                  : <span className={s.badgePaused}>⏸ Auto-rotation paused</span>}
              </div>
              <h1 className={s.title}>Production Records Dashboard</h1>
              <p className={s.lead}>Best-ever production by period · {GROUP_LABEL[group]} · unit &apos;000 tonnes</p>
            </div>
            <div className={s.controls}>
              <Segmented label="Plant group" options={GROUPS} value={group} onChange={setGroup} />
              <Segmented label="Item" options={ITEMS.map(i => [i, ITEM_SHORT[i]])} value={item} onChange={setItem} />
              <Segmented label="Period" options={SECTIONS.map(x => [x, x])} value={section} onChange={pickSection} />
              {autoRotate
                ? <button type="button" className={s.ghostBtn} onClick={() => setAutoRotate(false)}>⏸ Pause</button>
                : <button type="button" className={s.ghostBtn} onClick={resumeAuto}>▶ Auto-rotate</button>}
              <button type="button" className={s.ghostBtn} onClick={toggleFullscreen}>⛶ Fullscreen</button>
            </div>
          </header>

          {loading && <div className={s.state}>Loading records data…</div>}
          {error && <div className={s.error}>Error loading data: {error}</div>}

          {!loading && !error && grp && (
            <>
              <section className={s.kpis}>
                <Kpi gold label="🏆 All-time record month" best={top5m[0]} second={top5m[1]} />
                <Kpi label="Best-ever quarter" best={bQ} second={sQ} />
                <Kpi label="Best-ever half year" best={bH} second={sH} />
                <Kpi label="Best-ever financial year" best={topFy[0]} second={topFy[1]} />
              </section>

              <div className={s.grid}>
                <section className={s.card}>
                  <div className={s.cardHead}>
                    <div>
                      <h2 className={s.cardTitle}>
                        {section === 'Calendar Month' ? 'Calendar monthly benchmarks'
                          : section === 'Top 5 Years' ? 'Top 5 years' : `${section} benchmarks`} — {ITEM_SHORT[item]}
                      </h2>
                      <p className={s.cardSub}>
                        {section === 'Top 5 Years'
                          ? 'Highest annual totals, financial and calendar year'
                          : 'All-time best of each period beside the 2nd best · figure below = margin over 2nd best'}
                      </p>
                    </div>
                    <div className={s.legend}>
                      <span className={s.legendItem}><i className={s.swatch} style={{ background: BEST_COLOR }} />All-time best</span>
                      {section !== 'Top 5 Years' && <span className={s.legendItem}><i className={s.swatch} style={{ background: SECOND_COLOR }} />2nd best</span>}
                      <span className={s.legendItem}><i className={s.swatch} style={{ background: RANK_COLOR[1] }} />Top 3 of these bests</span>
                    </div>
                  </div>

                  {section === 'Calendar Month' && (
                    <>
                      <RecordChartRanked entries={cycleMonths} allEntries={allMonths} />
                      <div className={s.chartFoot}>
                        <span>Showing {CYCLES[cycle].label} ({cycle + 1} of 2)</span>
                        <button type="button" className={s.linkBtn} onClick={() => setCycle(1 - cycle)}>
                          Switch to {CYCLES[1 - cycle].label} →
                        </button>
                        <span>Record month: <span className={s.footStrong}>{top5m[0] ? `${top5m[0].period} · ${fmt(top5m[0].total)}` : '—'}</span></span>
                      </div>
                    </>
                  )}
                  {section === 'FY Quarter' && <RecordChart entries={quarters} />}
                  {section === 'FY Half' && <RecordChart entries={halves} />}
                  {section === 'Top 5 Years' && (
                    <div className={s.twoCharts}>
                      <div><h3 className={s.subHeading}>Financial years</h3><RecordChart entries={yearEntries(grp.top5_fy?.[item])} /></div>
                      <div><h3 className={s.subHeading}>Calendar years</h3><RecordChart entries={yearEntries(grp.top5_cy?.[item])} /></div>
                    </div>
                  )}
                </section>

                <aside className={s.sideCol}>
                  <section className={s.card}>
                    <div className={s.cardHead} style={{ marginBottom: 0 }}>
                      <h2 className={s.sideTitle}>🏆 All-time top 5 months</h2>
                      <span className={s.sideHint}>{group === 'sail5' ? 'SAIL-5' : 'All 8'}</span>
                    </div>
                    <RankedList rows={top5m} metaOf={r => r.period} />
                  </section>
                  <section className={s.card}>
                    <div className={s.cardHead} style={{ marginBottom: 0 }}>
                      <h2 className={s.sideTitle}>📅 Top 5 financial years</h2>
                      <span className={s.sideHint}>Full-year totals</span>
                    </div>
                    <RankedList rows={topFy} metaOf={r => `FY ${r.period}`} />
                  </section>
                </aside>
              </div>
            </>
          )}
        </div>
      </main>
    </>
  );
}

// Month chart shows one 6-month cycle at a time, but its rank colours must
// compare against all 12 months — rank on the full list, render the page.
function RecordChartRanked({ entries, allEntries }) {
  if (!entries.length) return <div className={s.empty}>No data available</div>;
  const ranked = [...allEntries].sort((a, b) => b.best.total - a.best.total);
  const max = Math.max(...allEntries.flatMap(e => [e.best.total, e.second?.total || 0]), 1);
  return <RecordChartView entries={entries} rankOf={e => ranked.indexOf(e) + 1} max={max} />;
}
