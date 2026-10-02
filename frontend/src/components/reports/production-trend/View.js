'use client';

import React, { useState, useEffect } from 'react';
import {
  ResponsiveContainer, LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend,
} from 'recharts';
import { ReportPage, FilterBar, Field, Status, Toggle, Empty, entryStyles as es } from '../ReportUI';
import pa from '../pa.module.css';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || '';

const COLORS = { hot_metal: '#1a73e8', crude_steel: '#e8710a', finished_steel: '#188038', saleable_steel: '#a142f4' };
const SHORT = { hot_metal: 'Hot Metal', crude_steel: 'Crude Steel', finished_steel: 'Finished Steel', saleable_steel: 'Saleable Steel' };

function fmt(v) {
  if (v == null) return '—';
  return Number(v).toLocaleString('en-IN', { maximumFractionDigits: 0 });
}
const pct = (cur, prev) => (cur == null || prev == null || prev === 0 ? null : ((cur - prev) / prev) * 100);

// The year containing today is still in progress (year-to-date) — its
// figures aren't comparable with full years, so it gets no YoY and the
// KPI cards use the latest complete year instead.
function currentYearKey(basis) {
  const d = new Date();
  return basis === 'fy' ? (d.getMonth() >= 3 ? d.getFullYear() : d.getFullYear() - 1) : d.getFullYear();
}

function Delta({ value }) {
  if (value == null) return null;
  return <span className={`${pa.delta} ${value >= 0 ? pa.up : pa.down}`}>{value >= 0 ? '▲' : '▼'} {Math.abs(value).toFixed(1)}%</span>;
}

export default function ProductionTrendPage() {
  const [basis, setBasis] = useState('fy'); // 'fy' | 'cy'
  const [groups, setGroups] = useState([]);
  const [group, setGroup] = useState('sail5');
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    fetch(`${API_BASE}/api/production-trend/groups`)
      .then((r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        return r.json();
      })
      .then((d) => setGroups(d.groups || []))
      .catch((e) => setError(`Failed to load plant groups: ${e.message}`));
  }, []);

  useEffect(() => {
    setLoading(true);
    setError(null);
    fetch(`${API_BASE}/api/production-trend?basis=${basis}&group=${group}`)
      .then((r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        return r.json();
      })
      .then((d) => setData(d))
      .catch((e) => setError(`Failed to load production trend: ${e.message}`))
      .finally(() => setLoading(false));
  }, [basis, group]);

  const items = data?.items || [];
  const years = data?.years || [];   // newest first
  const curKey = currentYearKey(basis);
  const isPartial = (row) => row.year_key === curKey;

  // YoY for each row vs the next-older row (none for the in-progress year)
  const yoy = years.map((row, i) => {
    const prev = years[i + 1];
    return Object.fromEntries(items.map((it) => [it.key, isPartial(row) || !prev ? null : pct(row[it.key], prev[it.key])]));
  });

  const latestIdx = years.findIndex((r) => !isPartial(r));
  const latest = latestIdx >= 0 ? years[latestIdx] : null;
  const chartData = [...years].reverse().map((r) => ({
    label: isPartial(r) ? `${r.year_label}*` : r.year_label,
    ...Object.fromEntries(items.map((it) => [it.key, r[it.key]])),
  }));
  const basisLabel = basis === 'fy' ? 'financial year' : 'calendar year';

  return (
    <ReportPage
      maxWidth={1200}
      title="Hot Metal / Crude Steel / Finished Steel / Saleable Steel — Trend"
      description={<>Year-wise production for {data?.group_label || '…'}, {basisLabel} basis (&apos;000 T)</>}
    >
      <FilterBar actions={loading ? <span className={es.ctxNote}>Loading…</span> : null}>
        <Field label="Basis">
          <Toggle label="Basis" value={basis} onChange={setBasis}
                  options={[{ id: 'fy', label: 'Financial Year' }, { id: 'cy', label: 'Calendar Year' }]} />
        </Field>
        <Field label="Plant" htmlFor="trend-group">
          <select id="trend-group" className={es.control} style={{ minWidth: 160 }} value={group} onChange={(e) => setGroup(e.target.value)}>
            {groups.map((g) => (
              <option key={g.value} value={g.value}>{g.label}</option>
            ))}
          </select>
        </Field>
      </FilterBar>

      <Status status={error ? { type: 'error', text: error } : null} />

      {!loading && !error && data && years.length === 0 && (
        <Empty>No data available for {data.group_label}.</Empty>
      )}

      {data && years.length > 0 && (
        <>
          {/* KPI cards — latest complete year vs the one before */}
          {latest && (
            <div className={pa.kpis}>
              {items.map((it) => {
                const g = yoy[latestIdx]?.[it.key];
                return (
                  <div key={it.key} className={pa.kpi} style={{ borderTop: `3px solid ${COLORS[it.key] || '#1a73e8'}` }}>
                    <div className={pa.kpiHead}>
                      <span className={pa.kpiLabel}>{SHORT[it.key] || it.item_name}</span>
                      {g != null && <span className={`${pa.pill} ${g >= 0 ? pa.pillUp : pa.pillDown}`}>{g >= 0 ? '+' : ''}{g.toFixed(1)}%</span>}
                    </div>
                    <div className={pa.kpiValue}>{fmt(latest[it.key])}<span className={pa.kpiUnit}>&apos;000 T</span></div>
                    <div className={pa.kpiFoot}>{latest.year_label}{g != null ? ` · vs ${years[latestIdx + 1]?.year_label}` : ''}</div>
                  </div>
                );
              })}
            </div>
          )}

          {/* Trend chart */}
          <section className={pa.card}>
            <div className={pa.cardHead}>
              <div>
                <h3 className={pa.cardTitle}>Production trajectory (&apos;000 T)</h3>
                <p className={pa.cardSub}>{data.group_label}, {basisLabel}-wise, {chartData[0]?.label} to {chartData[chartData.length - 1]?.label}</p>
              </div>
            </div>
            <div className={pa.cardBody}>
              <div className={pa.chart}>
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={chartData} margin={{ top: 8, right: 16, bottom: 4, left: 8 }}>
                    <CartesianGrid stroke="#eef1f4" vertical={false} />
                    <XAxis dataKey="label" tick={{ fontSize: 11, fill: '#5f6368' }} interval="preserveStartEnd" minTickGap={18} />
                    <YAxis tick={{ fontSize: 11, fill: '#5f6368' }} width={56}
                           tickFormatter={(v) => Number(v).toLocaleString('en-IN')} />
                    <Tooltip formatter={(v, name) => [fmt(v), SHORT[name] || name]} labelStyle={{ fontWeight: 700 }} />
                    <Legend formatter={(name) => SHORT[name] || name} wrapperStyle={{ fontSize: 12 }} />
                    {items.map((it) => (
                      <Line key={it.key} type="monotone" dataKey={it.key} stroke={COLORS[it.key] || '#1a73e8'}
                            strokeWidth={2} dot={{ r: 2 }} activeDot={{ r: 4 }} connectNulls={false} />
                    ))}
                  </LineChart>
                </ResponsiveContainer>
              </div>
            </div>
            {years.some(isPartial) && (
              <div className={pa.note}>* {years.find(isPartial).year_label} is year-to-date (in progress), so it is lower than a full year.</div>
            )}
          </section>

          {/* Year-wise table */}
          <section className={pa.card}>
            <div className={pa.cardHead}>
              <div>
                <h3 className={pa.cardTitle}>Year-wise production</h3>
                <p className={pa.cardSub}>Change over the previous year shown under each value</p>
              </div>
            </div>
            <div className={pa.tableScroll}>
              <table className={pa.table}>
                <thead>
                  <tr>
                    <th>{basis === 'fy' ? 'FY' : 'Year'}</th>
                    {items.map((it) => <th key={it.key}>{it.item_name}</th>)}
                  </tr>
                </thead>
                <tbody>
                  {years.map((row, idx) => (
                    <tr key={row.year_key} className={idx === 0 ? pa.rowHi : ''}>
                      <td style={{ fontWeight: 700 }}>
                        {row.year_label}{isPartial(row) && <span className={pa.ytdTag}>YTD</span>}
                      </td>
                      {items.map((it) => (
                        <td key={it.key}>
                          <span className={row[it.key] == null ? pa.empty : ''}>{fmt(row[it.key])}</span>
                          <Delta value={yoy[idx]?.[it.key]} />
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>
        </>
      )}
    </ReportPage>
  );
}
