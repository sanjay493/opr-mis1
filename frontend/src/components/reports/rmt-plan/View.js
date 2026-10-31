'use client';

import { Fragment, useEffect, useMemo, useState } from 'react';
import Link from 'next/link';
import { ReportPage, FilterBar, Field, Status, Section, Loading, Empty, wb } from '../ReportUI';

const API = process.env.NEXT_PUBLIC_API_URL || '';
const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];

// The RMT plan is discussed before the month starts, so open on next month.
function nextMonth() {
  const d = new Date();
  d.setMonth(d.getMonth() + 1, 1);
  return { month: String(d.getMonth() + 1).padStart(2, '0'), year: String(d.getFullYear()) };
}

// '000 T as the PDF prints it (rmt_plan_pdf.num): whole numbers, one decimal below 100 with a fraction.
function num(v) {
  if (v == null) return '';
  if (Math.abs(v) < 100 && Math.round(v * 10) / 10 !== Math.round(v)) return v.toFixed(1);
  return String(Math.round(v));
}

// Remarks: **bold** (which may span lines) and line breaks, without injecting HTML.
function Rich({ text }) {
  if (!text) return null;
  const lines = (part) => part.split('\n').map((line, i) => (
    <Fragment key={i}>{i > 0 && <br />}{line}</Fragment>
  ));
  return text.split(/\*\*([\s\S]+?)\*\*/g).map((part, j) => (
    j % 2 ? <b key={j}>{lines(part)}</b> : <Fragment key={j}>{lines(part)}</Fragment>
  ));
}

const T = { width: '100%', borderCollapse: 'collapse', fontSize: 12.5, tableLayout: 'fixed' };
const B = '1px solid #475569';
const th = { border: B, padding: '3px 4px', background: '#e2e8f0', fontWeight: 700, textAlign: 'center' };
const td = { border: B, padding: '2px 4px', textAlign: 'center', whiteSpace: 'nowrap' };
const rm = { border: B, padding: '2px 6px', textAlign: 'left', fontSize: 11.5, whiteSpace: 'normal' };
const APP = '#FFF2CC';
const OP = '#DDEBF7';
const ACT = '#C6EFCE';
const vert = { border: B, fontWeight: 700, textAlign: 'center', writingMode: 'vertical-rl', transform: 'rotate(180deg)', padding: '4px 2px' };

function Page1({ data }) {
  const L = data.labels;
  const cols = [['ly_actual', ACT], ['prev_app', APP], ['prev_op', OP], ['prev_mrate', ACT], ['ful_app'], ['ful_op'],
    ['app', APP], ['app_tpd', APP], ['op', OP], ['op_tpd', OP]];
  return (
    <table style={{ ...T, minWidth: 1100 }}>
      <colgroup>
        <col style={{ width: 34 }} /><col style={{ width: 58 }} />
        {cols.map(([k]) => <col key={k} style={{ width: k.startsWith('ful') ? 46 : 58 }} />)}
        <col />
      </colgroup>
      <thead>
        <tr>
          <th style={th} rowSpan={3}>Item</th><th style={th} rowSpan={3}>Plant</th>
          <th style={th}>{L.ly_col}</th><th style={th} colSpan={5}>{L.prev_col}</th><th style={th} colSpan={4}>{L.month_col}</th>
          <th style={th} rowSpan={3}>Remarks regarding S/d plan</th>
        </tr>
        <tr>
          <th style={{ ...th, background: ACT }} rowSpan={2}>Actual</th>
          <th style={{ ...th, background: APP }} rowSpan={2}>APP</th>
          <th style={{ ...th, background: OP }} rowSpan={2}>OP</th>
          <th style={{ ...th, background: ACT }} rowSpan={2} title="The month's actual (provisional until the month closes)">M/rate</th>
          <th style={th} rowSpan={2}>%ful. APP</th><th style={th} rowSpan={2}>%ful. OP</th>
          <th style={{ ...th, background: APP }} colSpan={2}>APP</th><th style={{ ...th, background: OP }} colSpan={2}>OP</th>
        </tr>
        <tr>
          <th style={{ ...th, background: APP }}>Total</th><th style={{ ...th, background: APP }}>TPD</th>
          <th style={{ ...th, background: OP }}>Total</th><th style={{ ...th, background: OP }}>TPD</th>
        </tr>
      </thead>
      {data.page1.map((sec) => (
        <tbody key={sec.key}>
          {sec.rows.map((r, i) => (
            <tr key={r.row} style={{ fontWeight: r.total ? 700 : 400 }}>
              {i === 0 && <td style={vert} rowSpan={sec.rows.length}>{sec.label}</td>}
              <td style={{ ...td, textAlign: 'left', fontWeight: 600 }}>{r.row}</td>
              {cols.map(([k, bg]) => <td key={k} style={{ ...td, background: bg }}>{num(r[k])}</td>)}
              <td style={rm}><Rich text={r.remarks} /></td>
            </tr>
          ))}
        </tbody>
      ))}
    </table>
  );
}

function Page2({ data }) {
  return data.page2.map((sec) => (
    <table key={sec.key} style={{ ...T, minWidth: 900, marginBottom: 14 }}>
      <colgroup><col style={{ width: 44 }} /><col style={{ width: 70 }} /><col style={{ width: 90 }} /><col style={{ width: 120 }} /><col style={{ width: 90 }} /><col style={{ width: 120 }} /><col /></colgroup>
      <thead>
        <tr>
          <th style={th} rowSpan={2}>Item</th><th style={th} rowSpan={2}>Plant</th>
          <th style={{ ...th, background: APP }} colSpan={2}>APP</th><th style={{ ...th, background: OP }} colSpan={2}>OP</th>
          <th style={th} rowSpan={2}>Remarks</th>
        </tr>
        <tr>
          <th style={{ ...th, background: APP }}>{sec.rate ? 'Plan' : 'APP'}</th>
          <th style={{ ...th, background: APP }}>{sec.rate ? 'Coal Req. per day (T)' : 'APP (tpd)'}</th>
          <th style={{ ...th, background: OP }}>{sec.rate ? 'Plan' : 'OP'}</th>
          <th style={{ ...th, background: OP }}>{sec.rate ? 'Coal Req. per day (T)' : 'OP (tpd)'}</th>
        </tr>
      </thead>
      <tbody>
        {sec.rows.map((r, i) => (
          <tr key={r.row} style={{ fontWeight: r.total ? 700 : 400 }}>
            {i === 0 && <td style={vert} rowSpan={sec.rows.length}>{sec.label}</td>}
            <td style={{ ...td, textAlign: 'left', fontWeight: 600 }}>{r.row}</td>
            <td style={{ ...td, background: APP }}>{num(r.app)}</td>
            <td style={{ ...td, background: APP }}>{num(r.app_day)}</td>
            <td style={{ ...td, background: OP }}>{num(r.op)}</td>
            <td style={{ ...td, background: OP }}>{num(r.op_day)}</td>
            <td style={rm}><Rich text={r.remarks} /></td>
          </tr>
        ))}
      </tbody>
    </table>
  ));
}

function Page3({ data }) {
  const groups = [];
  data.ipt.forEach((r) => {
    const last = groups[groups.length - 1];
    if (last && last.item === r.item) last.rows.push(r); else groups.push({ item: r.item, rows: [r] });
  });
  const asOn = data.stock_as_on ? `${data.stock_as_on.slice(8, 10)}.${data.stock_as_on.slice(5, 7)}.${data.stock_as_on.slice(2, 4)}` : '';
  return (
    <>
      {groups.length === 0 ? <Empty>No IPT requirement / availability entered for this month.</Empty> : (
        <table style={{ ...T, minWidth: 900 }}>
          <colgroup><col style={{ width: 110 }} /><col style={{ width: 60 }} /><col style={{ width: 60 }} /><col style={{ width: 100 }} /><col style={{ width: 100 }} /><col /></colgroup>
          <thead><tr>{['Item', 'From', 'To', 'Availability', 'Requirement', 'Remarks'].map((h) => <th key={h} style={th}>{h}</th>)}</tr></thead>
          {groups.map((g, gi) => (
            <tbody key={gi} style={{ borderTop: '2px solid #0f172a' }}>
              {g.rows.map((r, i) => (
                <tr key={i}>
                  {i === 0 && <td style={{ ...td, fontWeight: 700 }} rowSpan={g.rows.length}>{g.item}</td>}
                  <td style={td}>{r.from_plant}</td><td style={td}>{r.to_plant}</td>
                  <td style={td}>{r.availability}</td><td style={td}>{r.requirement}</td>
                  <td style={rm}><Rich text={r.remarks} /></td>
                </tr>
              ))}
            </tbody>
          ))}
        </table>
      )}
      {data.stock.length > 0 && (
        <>
          <p style={{ textAlign: 'center', margin: '14px 0 6px', fontWeight: 600 }}>Stock{asOn ? ` as on ${asOn}` : ''}</p>
          <table style={{ ...T, maxWidth: 760, margin: '0 auto' }}>
            <thead><tr>{['', 'BF Coke', 'Slab', 'Bloom'].map((h, i) => <th key={i} style={th}>{h}</th>)}</tr></thead>
            <tbody>
              {data.stock.map((r, i) => (
                <tr key={i}>
                  <td style={{ ...td, fontWeight: 700, textAlign: 'left' }}>{r.plant}</td>
                  <td style={td}>{r.bf_coke}</td><td style={td}>{r.slab}</td><td style={td}>{r.bloom}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </>
      )}
    </>
  );
}

export default function RmtPlanView() {
  const start = nextMonth();
  const [month, setMonth] = useState(start.month);
  const [year, setYear] = useState(start.year);
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);

  const reportMonth = `${year}-${month}`;
  const years = useMemo(() => {
    const y = new Date().getFullYear();
    return Array.from({ length: 8 }, (_, i) => String(y - 6 + i));
  }, []);

  useEffect(() => {
    let live = true;
    fetch(`${API}/api/rmt-plan?month=${encodeURIComponent(reportMonth)}`)
      .then(async (res) => {
        const body = await res.json().catch(() => ({}));
        if (!res.ok) throw new Error(typeof body.detail === 'string' ? body.detail : `Load failed (${res.status})`);
        return body;
      })
      .then((body) => { if (live) { setData(body); setError(null); } })
      .catch((err) => { if (live) setError({ key: reportMonth, text: err.message }); });
    return () => { live = false; };
  }, [reportMonth]);

  const body = data?.month === reportMonth ? data : null;
  const err = error?.key === reportMonth ? error.text : null;
  const qs = new URLSearchParams({ month: reportMonth });
  const label = body?.labels.month ?? `${MONTHS[Number(month) - 1]} ${year}`;

  return (
    <ReportPage
      title="RMT: Production Plan"
      description="The RMT meeting's production plan for the month: Hot Metal, Crude and Saleable Steel against last year, last month's APP / OP / actual and this month's APP and OP; Oven Pushing, Sinter and Pig Iron; IPT requirement / availability and stock."
      actions={(
        <>
          <a href={`${API}/api/rmt-plan/pdf?${qs}`} className={`${wb.btn} ${wb.btnSm} ${wb.btnPrimary}`} download title="A4 landscape, three pages">⬇ Download PDF</a>
          <a href={`${API}/api/rmt-plan/xlsx?${qs}`} className={`${wb.btn} ${wb.btnSm}`} download title="Three sheets, as the PDF">⬇ Download Excel</a>
          <Link href="/data-entry/production-techno?tab=rmt-plan" className={`${wb.btn} ${wb.btnSm}`}>Enter remarks / IPT</Link>
          <Link href="/data-entry/production-techno?tab=op-plan" className={`${wb.btn} ${wb.btnSm}`}>Enter OP</Link>
        </>
      )}
    >
      <FilterBar>
        <Field label="Report month" htmlFor="rmt-month">
          <select id="rmt-month" className={wb.select} value={month} onChange={(ev) => setMonth(ev.target.value)}>
            {MONTHS.map((m, i) => <option key={m} value={String(i + 1).padStart(2, '0')}>{m}</option>)}
          </select>
          <select className={wb.select} value={year} aria-label="Year" onChange={(ev) => setYear(ev.target.value)}>
            {years.map((y) => <option key={y} value={y}>{y}</option>)}
          </select>
        </Field>
      </FilterBar>

      {err && <Status status={{ type: 'error', text: err }} />}
      {!body && !err ? <Loading /> : body && (
        <>
          <Section title={`Production Plan for ${label}`} sub="Unit: '000T; TPD in tonnes per day. A total OP is blank while a plant with an APP has no OP.">
            <div style={{ overflowX: 'auto', padding: 8 }}><Page1 data={body} /></div>
            {body.note && <p style={{ fontWeight: 700, fontSize: 12.5, margin: '0 8px 8px' }}>{body.note}</p>}
          </Section>
          <Section title={`Production Plan for ${label} — Oven Pushing, Sinter, Pig Iron`} sub="Oven Pushing in nos./day with the coal requirement per day (T); Sinter and Pig Iron in '000T with TPD.">
            <div style={{ overflowX: 'auto', padding: 8 }}><Page2 data={body} /></div>
          </Section>
          <Section title={`IPT Requirement / Availability Plant wise for ${label}`} sub="Unit: T.">
            <div style={{ overflowX: 'auto', padding: 8 }}><Page3 data={body} /></div>
          </Section>
        </>
      )}
    </ReportPage>
  );
}
