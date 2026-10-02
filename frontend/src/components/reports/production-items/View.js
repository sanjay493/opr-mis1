'use client';

import React, { useState, useEffect } from 'react';
import { ResponsiveContainer, BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend } from 'recharts';
import { ReportPage, FilterBar, Field, Status, Empty, entryStyles as es, wb } from '../ReportUI';
import pa from '../pa.module.css';

const API = process.env.NEXT_PUBLIC_API_URL || '';

const MONTH_NAMES = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];

// Selectable production items (must match page_finished_steel_report.ITEMS keys).
const ITEMS = ['Oven Pushing', 'Sinter', 'Hot Metal', 'Crude Steel', 'Pig Iron', 'Finished Steel', 'Saleable Steel'];
const RATE_ITEMS = new Set(['Oven Pushing']);

function monthLabel(ym) {
  // "2026-04" -> "Apr'26"
  const [y, m] = ym.split('-');
  return `${MONTH_NAMES[parseInt(m, 10) - 1]}'${y.slice(2)}`;
}

function fmt(v) {
  if (v == null) return '—';
  return Number(v).toLocaleString('en-IN', { maximumFractionDigits: 3 });
}

const PLANT_COLORS = ['#1a73e8', '#8ab4f8', '#188038', '#81c995', '#e8710a', '#a142f4', '#f9ab00', '#9aa0a6'];

async function downloadCsv(url, fallbackName) {
  const res = await fetch(url);
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail || `HTTP ${res.status}`);
  }
  const disposition = res.headers.get('Content-Disposition') || '';
  const match = disposition.match(/filename="([^"]+)"/);
  const filename = match ? match[1] : fallbackName;
  const blob = await res.blob();
  const objUrl = window.URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = objUrl;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  window.URL.revokeObjectURL(objUrl);
}

export default function ProductionItemsReportPage() {
  const [item, setItem] = useState('Finished Steel');
  const [fys, setFys] = useState([]);
  const [fyStart, setFyStart] = useState(null);
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [downloadingAll, setDownloadingAll] = useState(false);
  const [downloadingFy, setDownloadingFy] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    fetch(`${API}/api/finished-steel-fys?item=${encodeURIComponent(item)}`)
      .then((r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        return r.json();
      })
      .then((d) => {
        const list = d.fys || [];
        setFys(list);
        setFyStart((prev) => {
          if (prev != null && list.some((fy) => fy.fy_start === prev)) return prev;
          return list.length > 0 ? list[0].fy_start : null;
        });
      })
      .catch((e) => setError(`Failed to load financial years: ${e.message}`));
  }, [item]);

  useEffect(() => {
    if (fyStart == null) return;
    setLoading(true);
    setError(null);
    fetch(`${API}/api/finished-steel-report/fy?fy_start=${fyStart}&item=${encodeURIComponent(item)}`)
      .then((r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        return r.json();
      })
      .then((d) => setData(d))
      .catch((e) => setError(`Failed to load ${item} data: ${e.message}`))
      .finally(() => setLoading(false));
  }, [fyStart, item]);

  const handleDownloadAll = async () => {
    setDownloadingAll(true);
    setError(null);
    try {
      const slug = item.toLowerCase().replace(/ /g, '_');
      await downloadCsv(`${API}/api/finished-steel-report?item=${encodeURIComponent(item)}`, `${slug}_month_plant_wise.csv`);
    } catch (e) {
      setError(`Download failed: ${e.message}`);
    } finally {
      setDownloadingAll(false);
    }
  };

  const handleDownloadFy = async () => {
    if (fyStart == null) return;
    setDownloadingFy(true);
    setError(null);
    try {
      const slug = item.toLowerCase().replace(/ /g, '_');
      await downloadCsv(`${API}/api/finished-steel-report?fy_start=${fyStart}&item=${encodeURIComponent(item)}`, `${slug}_FY${fyStart}.csv`);
    } catch (e) {
      setError(`Download failed: ${e.message}`);
    } finally {
      setDownloadingFy(false);
    }
  };

  const months = data?.months || [];
  const plants = data?.plants || [];
  const rows = data?.rows || {};

  const unit = RATE_ITEMS.has(item) ? 'nos./day' : "'000 T";
  const isRate = RATE_ITEMS.has(item);
  const plantCols = plants.filter((p) => p !== 'SAIL');
  const reported = months.filter((m) => Object.values(rows[m] || {}).some((v) => v != null));
  // FY-to-date per column: sum, or mean for a rate item (nos/day)
  const ytd = Object.fromEntries(plants.map((p) => {
    const vals = reported.map((m) => rows[m]?.[p]).filter((v) => v != null);
    if (!vals.length) return [p, null];
    const sum = vals.reduce((a, v) => a + v, 0);
    return [p, isRate ? sum / vals.length : sum];
  }));
  const topPlant = plantCols.filter((p) => ytd[p] != null).sort((a, b) => ytd[b] - ytd[a])[0];
  const sailVals = reported.map((m) => ({ m, v: rows[m]?.SAIL })).filter((x) => x.v != null);
  const peak = sailVals.length ? sailVals.reduce((a, x) => (x.v > a.v ? x : a)) : null;
  const avg = sailVals.length ? sailVals.reduce((a, x) => a + x.v, 0) / sailVals.length : null;
  const chartData = months.map((m) => ({ label: monthLabel(m), ...Object.fromEntries(plantCols.map((p) => [p, rows[m]?.[p] ?? null])) }));
  const fyLabel = fys.find((f) => f.fy_start === fyStart)?.label || data?.fy_label || '';
  const ytdLabel = reported.length ? `Apr–${monthLabel(reported[reported.length - 1]).slice(0, 3)}` : '';

  return (
    <ReportPage
      maxWidth={1400}
      title={<>{item} — Month-wise, Plant-wise</>}
      description={<>One row per month, one column per plant (plus the SAIL total), from production_table. Unit: {unit}. Blank cells mean no figure recorded for that plant that month.</>}
    >
      <FilterBar actions={<>
        {loading && <span className={es.ctxNote}>Loading…</span>}
        <button type="button" className={wb.btn} onClick={handleDownloadAll} disabled={downloadingAll}>
          {downloadingAll ? 'Generating…' : '⬇ Download All (full history)'}
        </button>
        <button type="button" className={`${wb.btn} ${wb.btnPrimary}`} onClick={handleDownloadFy} disabled={downloadingFy || fyStart == null}>
          {downloadingFy ? 'Generating…' : `⬇ Download FY ${fyLabel}`}
        </button>
      </>}>
        <Field label="Item" htmlFor="pi-item">
          <select id="pi-item" className={es.control} style={{ minWidth: 150 }} value={item} onChange={(e) => setItem(e.target.value)}>
            {ITEMS.map((it) => <option key={it} value={it}>{it}</option>)}
          </select>
        </Field>
        <Field label="Financial year" htmlFor="pi-fy">
          <select id="pi-fy" className={es.control} style={{ minWidth: 120 }} value={fyStart ?? ''} onChange={(e) => setFyStart(parseInt(e.target.value, 10))}>
            {fys.map((fy) => <option key={fy.fy_start} value={fy.fy_start}>{fy.label}</option>)}
          </select>
        </Field>
      </FilterBar>

      <Status status={error ? { type: 'error', text: error } : null} />

      {!loading && !error && data && reported.length === 0 && (
        <Empty>No {item} data available for FY {data.fy_label}.</Empty>
      )}

      {data && reported.length > 0 && (
        <>
          <div className={pa.kpis}>
            <div className={pa.kpi}>
              <div className={pa.kpiLabel}>Top producing plant · {ytdLabel}</div>
              <div className={pa.kpiValue}>{topPlant || '—'}</div>
              <div className={pa.kpiFoot}>{topPlant ? `${fmt(ytd[topPlant])} ${unit}${isRate ? ' (avg)' : ''}` : ''}</div>
            </div>
            <div className={pa.kpi}>
              <div className={pa.kpiLabel}>Peak month · SAIL</div>
              <div className={pa.kpiValue}>{peak ? monthLabel(peak.m) : '—'}</div>
              <div className={pa.kpiFoot}>{peak ? `${fmt(peak.v)} ${unit}` : ''}</div>
            </div>
            <div className={pa.kpi}>
              <div className={pa.kpiLabel}>Monthly average · SAIL</div>
              <div className={pa.kpiValue}>{fmt(avg)}<span className={pa.kpiUnit}>{unit}</span></div>
              <div className={pa.kpiFoot}>over {sailVals.length} reported month{sailVals.length === 1 ? '' : 's'}</div>
            </div>
            <div className={pa.kpi}>
              <div className={pa.kpiLabel}>SAIL · {ytdLabel} {isRate ? 'average' : 'total'}</div>
              <div className={pa.kpiValue}>{fmt(ytd.SAIL)}<span className={pa.kpiUnit}>{unit}</span></div>
              <div className={pa.kpiFoot}>FY {fyLabel}</div>
            </div>
          </div>

          <section className={pa.card}>
            <div className={pa.cardHead}>
              <div>
                <h3 className={pa.cardTitle}>Monthly volume by plant</h3>
                <p className={pa.cardSub}>{item}, FY {fyLabel} — each column is the month&apos;s plants stacked ({unit})</p>
              </div>
            </div>
            <div className={pa.cardBody}>
              <div className={pa.chart}>
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={chartData} margin={{ top: 8, right: 12, bottom: 4, left: 8 }}>
                    <CartesianGrid stroke="#eef1f4" vertical={false} />
                    <XAxis dataKey="label" tick={{ fontSize: 11, fill: '#5f6368' }} />
                    <YAxis tick={{ fontSize: 11, fill: '#5f6368' }} width={56} tickFormatter={(v) => Number(v).toLocaleString('en-IN')} />
                    <Tooltip formatter={(v, name) => [fmt(v), name]} labelStyle={{ fontWeight: 700 }} />
                    <Legend wrapperStyle={{ fontSize: 12 }} />
                    {plantCols.map((p, i) => (
                      <Bar key={p} dataKey={p} stackId="plants" fill={PLANT_COLORS[i % PLANT_COLORS.length]}
                           radius={i === plantCols.length - 1 ? [3, 3, 0, 0] : 0} />
                    ))}
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </div>
          </section>

          <section className={pa.card}>
            <div className={pa.cardHead}>
              <div>
                <h3 className={pa.cardTitle}>Month-by-plant table</h3>
                <p className={pa.cardSub}>{ytdLabel} row = {isRate ? 'average' : 'total'} of the reported months</p>
              </div>
            </div>
            <div className={pa.tableScroll}>
              <table className={pa.table}>
                <thead>
                  <tr>
                    <th>Month</th>
                    {plants.map((p) => <th key={p} className={p === 'SAIL' ? pa.colTotal : ''}>{p}</th>)}
                  </tr>
                </thead>
                <tbody>
                  {months.map((m) => {
                    const byPlant = rows[m] || {};
                    return (
                      <tr key={m}>
                        <td style={{ fontWeight: 600 }}>{monthLabel(m)}</td>
                        {plants.map((p) => (
                          <td key={p} className={p === 'SAIL' ? pa.colTotal : ''}>
                            <span className={byPlant[p] == null ? pa.empty : ''}>{fmt(byPlant[p])}</span>
                          </td>
                        ))}
                      </tr>
                    );
                  })}
                  <tr className={pa.rowHi}>
                    <td style={{ fontWeight: 800 }}>{ytdLabel} {isRate ? 'avg' : 'total'}</td>
                    {plants.map((p) => <td key={p} style={{ fontWeight: 800 }}>{fmt(ytd[p])}</td>)}
                  </tr>
                </tbody>
              </table>
            </div>
          </section>
        </>
      )}
    </ReportPage>
  );
}
