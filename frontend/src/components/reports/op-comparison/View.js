'use client';

import { Fragment, useEffect, useMemo, useState } from 'react';
import Link from 'next/link';
import { ReportPage, FilterBar, Field, Status, Section, Loading, Empty, Toggle, entryStyles as e, wb } from '../ReportUI';

const API = process.env.NEXT_PUBLIC_API_URL || '';
const PLANTS = ['SAIL', 'BSP', 'DSP', 'RSP', 'BSL', 'ISP', 'ASP', 'SSP', 'VISL'];
const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
const PERIODS = [{ id: 'month', label: 'Month' }, { id: 'ytd', label: 'Till month (FY)' }];
const ITEM_LABEL = { 'Total Sinter': 'Sinter', 'Total Crude Steel': 'Crude Steel' };

// Last month by default: the latest one that can have an actual.
function lastMonth() {
  const d = new Date();
  d.setMonth(d.getMonth() - 1, 1);
  return { month: String(d.getMonth() + 1).padStart(2, '0'), year: String(d.getFullYear()) };
}

const num = (v) => (v == null ? '—' : v.toLocaleString('en-IN', { maximumFractionDigits: 1 }));

// A percentage cell: green at or above 100 %, red below.
function Pct({ v }) {
  if (v == null) return <td className={e.r}><span className={wb.muted}>—</span></td>;
  return (
    <td className={e.r} style={{ fontWeight: 600, color: v >= 100 ? 'var(--ui-success)' : 'var(--ui-danger)' }}>
      {v.toFixed(1)}%
    </td>
  );
}

function Cells({ r }) {
  const partial = r.op != null && r.op_months < r.months;
  return (
    <>
      <td className={e.r}>{num(r.app)}</td>
      <td className={e.r}>
        {num(r.op)}
        {partial && <span className={wb.muted} style={{ fontSize: 11 }} title="The OP was entered for only these months">{` (${r.op_months}/${r.months} m)`}</span>}
      </td>
      <td className={e.r} style={{ fontWeight: 600 }}>{num(r.actual)}</td>
      <Pct v={r.act_vs_app} />
      <Pct v={r.act_vs_op} />
      <Pct v={r.op_vs_app} />
    </>
  );
}

const HEAD = (first) => (
  <thead>
    <tr>
      <th>{first}</th>
      <th className={e.r}>APP</th>
      <th className={e.r}>OP</th>
      <th className={e.r}>Actual</th>
      <th className={e.r} title="Actual as % of APP">Actual ÷ APP</th>
      <th className={e.r} title="Actual as % of OP, over the months that have an OP">Actual ÷ OP</th>
      <th className={e.r} title="OP as % of APP (only when the OP covers every month)">OP ÷ APP</th>
    </tr>
  </thead>
);

export default function OpComparisonView() {
  const start = lastMonth();
  const [month, setMonth] = useState(start.month);
  const [year, setYear] = useState(start.year);
  const [plant, setPlant] = useState('SAIL');
  const [period, setPeriod] = useState('month');
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);

  const reportMonth = `${year}-${month}`;
  const key = `${plant}|${reportMonth}|${period}`;
  const years = useMemo(() => {
    const y = new Date().getFullYear();
    return Array.from({ length: 8 }, (_, i) => String(y - 6 + i));
  }, []);

  useEffect(() => {
    let live = true;
    const qs = new URLSearchParams({ month: reportMonth, plant, period });
    fetch(`${API}/api/op-comparison?${qs}`)
      .then(async (res) => {
        const body = await res.json().catch(() => ({}));
        if (!res.ok) throw new Error(typeof body.detail === 'string' ? body.detail : `Load failed (${res.status})`);
        return body;
      })
      .then((body) => { if (live) { setData({ key, body }); setError(null); } })
      .catch((err) => { if (live) setError({ key, text: err.message }); });
    return () => { live = false; };
  }, [key, reportMonth, plant, period]);

  const body = data?.key === key ? data.body : null;
  const err = error?.key === key ? error.text : null;
  const months = body?.months ?? [];
  const periodLabel = period === 'ytd' && months.length
    ? `${MONTHS[Number(months[0].slice(5)) - 1]}–${MONTHS[Number(month) - 1]} ${year}`
    : `${MONTHS[Number(month) - 1]} ${year}`;
  const anyOp = body && (body.rows ?? body.groups.flatMap((g) => g.rows)).some((r) => r.op != null);

  return (
    <ReportPage
      title="OP vs APP vs Actual"
      description="Production against the month's Operating Plan (OP) and the Annual Plan (APP). Till month sums April to the selected month; Actual ÷ OP then uses only the months that have an OP."
      actions={(
        <>
          <a href={`${API}/api/op-comparison/xlsx?${new URLSearchParams({ month: reportMonth, period })}`}
             className={`${wb.btn} ${wb.btnSm} ${wb.btnPrimary}`} download
             title="SAIL sheet plus one sheet per plant, for the selected month and period">
            ⬇ Download Excel
          </a>
          <Link href="/data-entry/production-techno?tab=op-plan" className={`${wb.btn} ${wb.btnSm}`}>Enter OP</Link>
        </>
      )}
    >
      <FilterBar>
        <Field label="Month" htmlFor="opc-month">
          <select id="opc-month" className={wb.select} value={month} onChange={(ev) => setMonth(ev.target.value)}>
            {MONTHS.map((m, i) => <option key={m} value={String(i + 1).padStart(2, '0')}>{m}</option>)}
          </select>
          <select className={wb.select} value={year} aria-label="Year" onChange={(ev) => setYear(ev.target.value)}>
            {years.map((y) => <option key={y} value={y}>{y}</option>)}
          </select>
        </Field>
        <Field label="Period">
          <Toggle options={PERIODS} value={period} onChange={setPeriod} label="Period" />
        </Field>
        <Field label="Plant">
          <div className={wb.chips} role="group" aria-label="Plant">
            {PLANTS.map((p) => (
              <button key={p} type="button" aria-pressed={p === plant}
                      className={`${wb.chip} ${p === plant ? wb.chipActive : ''}`} onClick={() => setPlant(p)}>
                {p}
              </button>
            ))}
          </div>
        </Field>
      </FilterBar>

      {err && <Status status={{ type: 'error', text: err }} />}
      {body && !anyOp && (
        <Status status={{ type: 'info', text: `No OP has been entered for ${plant === 'SAIL' ? 'any plant' : plant} in ${periodLabel}; the OP columns are empty.` }} />
      )}

      {!body && !err ? <Loading /> : body && plant === 'SAIL' ? (
        <Section title={`SAIL — key items · ${periodLabel}`} sub="Each item by plant, with the SAIL total. Values in '000 T.">
          {body.groups.length === 0 ? <Empty>No production data for {periodLabel}.</Empty> : (
            <table className={e.table}>
              {HEAD('Item / plant')}
              <tbody>
                {body.groups.map((g) => (
                  <Fragment key={g.item}>
                    <tr className={e.subRow}><td colSpan={7}>{ITEM_LABEL[g.item] || g.item}</td></tr>
                    {g.rows.map((r) => (
                      <tr key={r.plant}>
                        <td style={{ paddingLeft: 24 }}>{r.plant}</td>
                        <Cells r={r} />
                      </tr>
                    ))}
                    <tr style={{ fontWeight: 700 }}>
                      <td className={e.itemCell} style={{ paddingLeft: 24 }}>
                        SAIL
                        {!g.total.op_complete && g.total.op != null && (
                          <span className={wb.muted} style={{ fontWeight: 400, fontSize: 11 }} title="Some plants or months have no OP, so the SAIL OP is incomplete"> · OP incomplete</span>
                        )}
                      </td>
                      <Cells r={g.total} />
                    </tr>
                  </Fragment>
                ))}
              </tbody>
            </table>
          )}
        </Section>
      ) : body && (
        <Section title={`${plant} · ${periodLabel}`} sub="Every production unit with an APP, OP or actual. Values in the APP's units ('000 T; Oven Pushing in nos/day, averaged over the days for Till month).">
          {body.rows.length === 0 ? <Empty>No production data for {plant} in {periodLabel}.</Empty> : (
            <table className={e.table}>
              {HEAD('Production unit / item')}
              <tbody>
                {body.rows.map((r) => (
                  <tr key={r.item}>
                    <td className={e.itemCell}>{r.item}</td>
                    <Cells r={r} />
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </Section>
      )}
    </ReportPage>
  );
}
