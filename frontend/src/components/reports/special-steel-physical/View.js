'use client';

import React, { useState, useEffect } from 'react';
import { ReportPage, Status, Loading } from '../ReportUI';
import pa from '../pa.module.css';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || '';

const cellBase = {
  padding: '5px 8px',
  fontSize: '10pt',
  borderBottom: '1px solid #e8eaed',
  borderRight: '1px solid #f1f3f4',
  whiteSpace: 'nowrap',
  textAlign: 'right',
  fontVariantNumeric: 'tabular-nums',
};
const HEAD = {
  ...cellBase,
  position: 'sticky',
  top: 0,
  zIndex: 2,
  backgroundColor: '#e8f0fe',
  textAlign: 'center',
  fontWeight: 700,
  color: '#174ea6',
};
const sepLeft = { borderLeft: '2px solid #9aa7bd' };
// cur-FY ABP — the single planning-target column: warm tint.
// Apr-<report month> YTD block: cool tint.
const abpBg = { backgroundColor: '#fef3d6' };
const abpHead = { backgroundColor: '#fde3aa' };
const ytdBg = { backgroundColor: '#e7f4ea' };
const ytdHead = { backgroundColor: '#cbe8d2' };

const PLANT_NAMES = { ASP: 'Alloy Steels Plant', SSP: 'Salem Steel Plant', VISP: 'Visvesvaraya Iron & Steel Plant', VISL: 'Visvesvaraya Iron & Steel Plant' };
const toNum = (s) => (s == null || s === '' ? null : Number(String(s).replace(/,/g, '')));
const barColor = (p) => (p == null ? 'var(--ui-border)' : p >= 100 ? 'var(--ui-success)' : p >= 90 ? '#f9ab00' : 'var(--ui-danger)');

export default function SpecialSteelPhysicalPage() {
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    fetch(`${API_BASE}/api/special-steel-physical`)
      .then((r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        return r.json();
      })
      .then(setData)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  const historyFys = data?.history_fys || [];
  const sections = data?.sections || [];

  return (
    <ReportPage
      maxWidth={1800}
      title={<>{data?.title || 'Special Steel Plants Physical Performance'}</>}
      description={<>Unit: {data?.unit || 'Tonnes'}</>}
    >

        {loading && <Loading />}
        <Status status={error ? { type: 'error', text: `Failed to load: ${error}` } : null} />

        {data && !loading && (
          <>
            {/* Per-plant Apr-to-date achievement vs APP (figures from the table below) */}
            <div className={pa.kpis}>
              {sections.map((sec) => (
                <div key={sec.plant} className={pa.kpi}>
                  <div className={pa.kpiHead}>
                    <span className={pa.kpiLabel}>{sec.plant} · {PLANT_NAMES[sec.plant] || ''}</span>
                  </div>
                  {sec.rows.map((r) => {
                    const ff = toNum(r.ytd_pct_ful);
                    return (
                      <div key={r.series_label} style={{ marginTop: 10 }}>
                        <div style={{ display: 'flex', justifyContent: 'space-between', gap: 8, fontSize: 12.5 }}>
                          <span style={{ fontWeight: 600 }}>{r.series_label}</span>
                          <span className={`${pa.pill} ${ff == null ? pa.pillFlat : ff >= 100 ? pa.pillUp : ff >= 90 ? pa.pillFlat : pa.pillDown}`}>
                            {ff == null ? '—' : `${ff}% of APP`}
                          </span>
                        </div>
                        <div className={pa.kpiFoot}>
                          {data.ytd_label}: <b>{r.ytd_actual || '—'}</b> / APP {r.ytd_app || '—'} T · ABP {data.cur_fy} {r.cur_abp || '—'}
                        </div>
                        <div className={pa.kpiBar}>
                          <span style={{ width: `${Math.min(ff ?? 0, 100)}%`, background: barColor(ff) }} />
                        </div>
                      </div>
                    );
                  })}
                </div>
              ))}
            </div>

            <section className={pa.card}>
              <div className={pa.cardHead}>
                <div>
                  <h3 className={pa.cardTitle}>Multi-year physical performance</h3>
                  <p className={pa.cardSub}>Capacity, best achieved, year-wise actuals, {data.prev_fy} actual, {data.cur_fy} ABP and {data.ytd_label} (Tonnes)</p>
                </div>
              </div>
            <div style={{ overflow: 'auto' }}>
              <table style={{ borderCollapse: 'separate', borderSpacing: 0, width: '100%' }}>
                <thead>
                  <tr>
                    <th rowSpan={2} style={{ ...HEAD, left: 0, zIndex: 3, textAlign: 'left', minWidth: 60 }}>Plant</th>
                    <th rowSpan={2} style={{ ...HEAD, left: 60, zIndex: 3, textAlign: 'left', minWidth: 120 }}>Item</th>
                    <th rowSpan={2} style={HEAD}>Capacity</th>
                    <th colSpan={2} style={HEAD}>Best Achieved</th>
                    {historyFys.map((fy) => <th key={fy} rowSpan={2} style={HEAD}>{fy}</th>)}
                    <th rowSpan={2} style={{ ...HEAD, ...sepLeft }}>{data.prev_fy}</th>
                    <th rowSpan={2} style={{ ...HEAD, ...sepLeft, ...abpHead }}>{data.cur_fy} ABP</th>
                    <th colSpan={5} style={{ ...HEAD, ...sepLeft, ...ytdHead }}>{data.ytd_label}</th>
                  </tr>
                  <tr>
                    <th style={{ ...HEAD, top: 31 }}>Actual</th>
                    <th style={{ ...HEAD, top: 31 }}>Year</th>
                    <th style={{ ...HEAD, top: 31, ...sepLeft, ...ytdHead }}>APP</th>
                    <th style={{ ...HEAD, top: 31, ...ytdHead }}>Actual</th>
                    <th style={{ ...HEAD, top: 31, ...ytdHead }}>%FF</th>
                    <th style={{ ...HEAD, top: 31, ...ytdHead }}>CPLY</th>
                    <th style={{ ...HEAD, top: 31, ...ytdHead }}>%Gr</th>
                  </tr>
                </thead>
                <tbody>
                  {sections.map((sec) => sec.rows.map((r, i) => (
                    <tr key={`${sec.plant}-${r.series_label}`}>
                      {i === 0 && (
                        <td rowSpan={sec.rows.length} style={{ ...cellBase, position: 'sticky', left: 0, textAlign: 'left', fontWeight: 700, background: '#f8f9fa' }}>
                          {sec.plant}
                        </td>
                      )}
                      <td style={{ ...cellBase, position: 'sticky', left: 60, textAlign: 'left', fontWeight: 600, background: '#fff' }}>{r.series_label}</td>
                      <td style={cellBase}>{r.capacity}</td>
                      <td style={cellBase}>{r.best_actual}</td>
                      <td style={{ ...cellBase, textAlign: 'center' }}>{r.best_year}</td>
                      {historyFys.map((fy) => <td key={fy} style={cellBase}>{r.history[fy]}</td>)}
                      <td style={{ ...cellBase, ...sepLeft }}>{r.prev_actual}</td>
                      <td style={{ ...cellBase, ...sepLeft, ...abpBg }}>{r.cur_abp}</td>
                      <td style={{ ...cellBase, ...sepLeft, ...ytdBg }}>{r.ytd_app}</td>
                      <td style={{ ...cellBase, ...ytdBg }}>{r.ytd_actual}</td>
                      <td style={{ ...cellBase, ...ytdBg }}>{r.ytd_pct_ful}</td>
                      <td style={{ ...cellBase, ...ytdBg }}>{r.ytd_cply}</td>
                      <td style={{ ...cellBase, ...ytdBg }}>{r.ytd_growth}</td>
                    </tr>
                  )))}
                </tbody>
              </table>
            </div>
            {(data.notes || []).length > 0 && (
              <ul style={{ margin: 0, padding: '10px 16px 12px 32px', fontSize: 12, color: 'var(--ui-text-secondary)', borderTop: '1px solid var(--ui-border-subtle)' }}>
                {data.notes.map((n, i) => <li key={i} style={{ marginBottom: 3 }}>{n}</li>)}
              </ul>
            )}
            </section>

            {(data.ipt_rows || []).length > 0 && (
              <section className={pa.card} style={{ maxWidth: 640 }}>
                <div className={pa.cardHead}>
                  <h3 className={pa.cardTitle}>{data.ipt_title}</h3>
                </div>
                <table style={{ borderCollapse: 'collapse', fontSize: 12.5, width: '100%' }}>
                  <thead>
                    <tr>
                      {['Item (‘000 T)', 'From', 'To', 'Plan'].map((h) => (
                        <th key={h} style={{ ...HEAD, position: 'static', padding: '6px 14px' }}>{h}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {data.ipt_rows.map((r, i) => (
                      <tr key={i}>
                        {r.item_rowspan > 0 && (
                          <td rowSpan={r.item_rowspan} style={{ padding: '6px 14px', borderBottom: '1px solid var(--ui-border-subtle)', fontWeight: 600 }}>{r.item}</td>
                        )}
                        <td style={{ padding: '6px 14px', borderBottom: '1px solid var(--ui-border-subtle)', textAlign: 'center' }}>{r.from}</td>
                        <td style={{ padding: '6px 14px', borderBottom: '1px solid var(--ui-border-subtle)', textAlign: 'center' }}>{r.to}</td>
                        <td style={{ padding: '6px 14px', borderBottom: '1px solid var(--ui-border-subtle)', textAlign: 'right', fontVariantNumeric: 'tabular-nums' }}>{r.plan}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </section>
            )}
          </>
        )}
    </ReportPage>
  );
}
