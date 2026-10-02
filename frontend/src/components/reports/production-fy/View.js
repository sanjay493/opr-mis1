'use client';

import React, { useState, useEffect, useRef } from 'react';
import { ReportPage, FilterBar, Field, Status, Toggle, Empty, entryStyles as es, reportStyles as rs, wb } from '../ReportUI';
import pa from '../pa.module.css';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || '';

const MONTH_NAMES = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];

function monthLabel(ym) {
  // "2026-04" -> "Apr'26"
  const [y, m] = ym.split('-');
  return `${MONTH_NAMES[parseInt(m, 10) - 1]}'${y.slice(2)}`;
}

function fmt(v) {
  if (v == null) return '—';
  return Number(v).toLocaleString('en-IN', { maximumFractionDigits: 3 });
}

// Items expressed as a daily rate — a yearly sum is meaningless, show average instead.
// COB# battery items (e.g. "COB#1-8", "COB#6") are oven-pushing counts in nos/day,
// same unit family as "Oven Pushing (nos/day)", just without the unit in the name.
function isRateItem(name) {
  return /\/day|\/d\)/i.test(name) || /^COB#/i.test(name);
}

function rowTotal(itemName, values, months) {
  const nums = months.map((m) => values[m]).filter((v) => v != null);
  if (nums.length === 0) return null;
  const sum = nums.reduce((a, b) => a + b, 0);
  return isRateItem(itemName) ? sum / nums.length : sum;
}

const cellBase = {
  padding: '7px 10px',
  fontSize: '10pt',
  borderBottom: '1px solid #e8eaed',
  whiteSpace: 'nowrap',
};
const HEAD_CELL = {
  position: 'sticky', top: 0, zIndex: 2, backgroundColor: '#f8f9fa', textAlign: 'right',
  fontSize: '10.5px', fontWeight: 700, letterSpacing: '.05em', textTransform: 'uppercase', color: '#5f6368',
  borderBottom: '1px solid #dadce0',
};

// Actual as a % of the AAP plan, shown under a value when "% of plan" is on
function PctOfPlan({ actual, plan }) {
  if (actual == null || !plan) return null;
  const p = (actual / plan) * 100;
  const color = p >= 100 ? '#188038' : p >= 95 ? '#b06000' : '#d93025';
  return <span style={{ display: 'block', fontSize: '10px', fontWeight: 600, color }}>{p.toFixed(1)}%</span>;
}

export default function ProductionFYPage() {
  const [fys, setFys] = useState([]);
  const [fyStart, setFyStart] = useState(null);
  const [mode, setMode] = useState('actual'); // 'actual' | 'plan'
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [downloading, setDownloading] = useState(null); // 'excel' | 'pdf' | null
  const [showPct, setShowPct] = useState(false);         // "% of plan" under actuals
  const [collapsed, setCollapsed] = useState(() => new Set()); // collapsed plant sections
  const scrollRef = useRef(null);

  const toggle = (plant) => setCollapsed((prev) => {
    const next = new Set(prev);
    if (next.has(plant)) next.delete(plant); else next.add(plant);
    return next;
  });
  // Scroll the table so a plant's section header sits just below the sticky column header
  const jumpTo = (plant) => {
    setCollapsed((prev) => { const next = new Set(prev); next.delete(plant); return next; });
    setTimeout(() => {   // after the expand re-render
      const box = scrollRef.current;
      const row = document.getElementById(`pfy-${plant}`);
      const head = box?.querySelector('thead');
      if (box && row) box.scrollTo({ top: row.offsetTop - (head?.offsetHeight || 0) });
    }, 0);
  };

  useEffect(() => {
    fetch(`${API_BASE}/api/production-fys`)
      .then((r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        return r.json();
      })
      .then((d) => {
        setFys(d.fys || []);
        if (d.fys && d.fys.length > 0) setFyStart(d.fys[0].fy_start);
      })
      .catch((e) => setError(`Failed to load financial years: ${e.message}`));
  }, []);

  useEffect(() => {
    if (fyStart == null) return;
    setLoading(true);
    setError(null);
    fetch(`${API_BASE}/api/production-fy?fy_start=${fyStart}`)
      .then((r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        return r.json();
      })
      .then((d) => setData(d))
      .catch((e) => setError(`Failed to load production data: ${e.message}`))
      .finally(() => setLoading(false));
  }, [fyStart]);

  const handleDownload = async (kind) => {
    if (!fyStart) return;
    setDownloading(kind);
    setError(null);
    try {
      const res = await fetch(`${API_BASE}/api/production-fy/${kind}?fy_start=${fyStart}&mode=${mode}`);
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        throw new Error(body.detail || `HTTP ${res.status}`);
      }
      const blob = await res.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      const fyLabel = fys.find((fy) => fy.fy_start === fyStart)?.label || String(fyStart);
      a.download = `Production_${fyLabel}_${mode}.${kind === 'excel' ? 'xlsx' : 'pdf'}`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      window.URL.revokeObjectURL(url);
    } catch (e) {
      setError(`Download failed: ${e.message}`);
    } finally {
      setDownloading(null);
    }
  };

  const months = data?.months || [];

  // In Plan view, hide plants that have no plan rows at all for this FY
  const visiblePlants = (data?.plants || [])
    .map((p) => ({
      ...p,
      items: p.items.filter((it) =>
        months.some((m) => it[mode][m] != null)
      ),
    }))
    .filter((p) => p.items.length > 0);

  return (
    <ReportPage
      fill
      maxWidth={1600}
      title={`Month-wise Production ${mode === 'actual' ? '(Actual)' : '(Plan)'}`}
      description={`All plants, all items — monthly ${mode} figures for the selected financial year ('000 T unless stated)`}
    >
        <FilterBar actions={<>
          {loading && <span className={es.ctxNote}>Loading…</span>}
          <button type="button" className={wb.btn} onClick={() => handleDownload('excel')} disabled={!fyStart || downloading !== null}>
            {downloading === 'excel' ? 'Generating…' : '⬇ Excel'}
          </button>
          <button type="button" className={wb.btn} onClick={() => handleDownload('pdf')} disabled={!fyStart || downloading !== null}>
            {downloading === 'pdf' ? 'Generating…' : '⬇ PDF'}
          </button>
        </>}>
          <Field label="Financial year" htmlFor="pfy-fy">
            <select id="pfy-fy" className={es.control} style={{ minWidth: 130 }} value={fyStart ?? ''} onChange={(e) => setFyStart(parseInt(e.target.value, 10))}>
              {fys.map((fy) => (
                <option key={fy.fy_start} value={fy.fy_start}>{fy.label}</option>
              ))}
            </select>
          </Field>
          <Field label="Figures">
            <Toggle label="Figures" value={mode} onChange={setMode}
                    options={[{ id: 'actual', label: 'Actual' }, { id: 'plan', label: 'Plan' }]} />
          </Field>
          {mode === 'actual' && (
            <label style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 13, fontWeight: 600, color: 'var(--ui-text-secondary)', paddingBottom: 6, cursor: 'pointer' }}>
              <input type="checkbox" checked={showPct} onChange={(e) => setShowPct(e.target.checked)} style={{ accentColor: 'var(--ui-primary)' }} />
              Show % of plan
            </label>
          )}
        </FilterBar>

        <Status status={error ? { type: 'error', text: error } : null} />

        {!loading && !error && data && visiblePlants.length === 0 && (
          <Empty>No {mode} data available for FY {data.fy_label}.</Empty>
        )}

        {/* Table */}
        {data && visiblePlants.length > 0 && (
          <>
            <div className={pa.chips}>
              <span className={pa.chipsLabel}>Jump to</span>
              {visiblePlants.map((p) => (
                <button key={p.plant} type="button" className={pa.chip} onClick={() => jumpTo(p.plant)}>{p.plant}</button>
              ))}
              <button type="button" className={pa.chip} style={{ marginLeft: 'auto' }}
                      onClick={() => setCollapsed(collapsed.size ? new Set() : new Set(visiblePlants.map((p) => p.plant)))}>
                {collapsed.size ? 'Expand all' : 'Collapse all'}
              </button>
            </div>
            <div className={rs.grow} ref={scrollRef}>
              <table style={{ borderCollapse: 'separate', borderSpacing: 0, width: '100%' }}>
                <thead>
                  <tr>
                    <th style={{ ...cellBase, ...HEAD_CELL, left: 0, zIndex: 3, textAlign: 'left', minWidth: '200px', borderRight: '1px solid #dadce0' }}>
                      Item
                    </th>
                    {months.map((m) => (
                      <th key={m} style={{ ...cellBase, ...HEAD_CELL, minWidth: '76px' }}>{monthLabel(m)}</th>
                    ))}
                    <th style={{ ...cellBase, ...HEAD_CELL, minWidth: '90px', borderLeft: '1px solid #dadce0', color: '#174ea6' }}>Total</th>
                  </tr>
                </thead>
                <tbody>
                  {visiblePlants.map((plant) => {
                    const isCollapsed = collapsed.has(plant.plant);
                    return (
                      <React.Fragment key={plant.plant}>
                        {/* Plant section header — click to collapse / expand */}
                        <tr id={`pfy-${plant.plant}`}>
                          <td colSpan={months.length + 2} style={{ ...cellBase, padding: 0, position: 'sticky', left: 0, backgroundColor: '#1a73e8' }}>
                            <button type="button" onClick={() => toggle(plant.plant)} aria-expanded={!isCollapsed}
                                    style={{
                                      display: 'flex', alignItems: 'center', gap: 8, width: '100%', padding: '7px 12px',
                                      border: 0, background: 'none', cursor: 'pointer', color: '#fff', textAlign: 'left',
                                      font: '800 13px var(--ui-font)', letterSpacing: '0.03em',
                                    }}>
                              <span style={{ display: 'inline-block', width: 12, transform: isCollapsed ? 'none' : 'rotate(90deg)', transition: 'transform .15s' }}>▸</span>
                              {plant.plant}
                              <span style={{ fontWeight: 500, fontSize: 11.5, opacity: 0.85, letterSpacing: 0 }}>
                                {plant.items.length} item{plant.items.length === 1 ? '' : 's'}{isCollapsed ? ' · collapsed' : ''}
                              </span>
                            </button>
                          </td>
                        </tr>
                        {!isCollapsed && plant.items.map((item, idx) => {
                          const values = item[mode];
                          const total = rowTotal(item.item_name, values, months);
                          const planTotal = rowTotal(item.item_name, item.plan, months.filter((m) => values[m] != null));
                          const zebra = idx % 2 === 1 ? '#f8f9fa' : '#ffffff';
                          const showPctRow = mode === 'actual' && showPct;
                          return (
                            <tr key={item.item_name}>
                              <td style={{ ...cellBase, position: 'sticky', left: 0, zIndex: 1, backgroundColor: zebra, fontWeight: 600, color: '#202124', borderRight: '1px solid #dadce0' }}>
                                {item.item_name}
                              </td>
                              {months.map((m) => (
                                <td key={m} style={{ ...cellBase, textAlign: 'right', backgroundColor: zebra, color: values[m] == null ? '#bdc1c6' : '#202124', fontVariantNumeric: 'tabular-nums' }}>
                                  {fmt(values[m])}
                                  {showPctRow && <PctOfPlan actual={values[m]} plan={item.plan?.[m]} />}
                                </td>
                              ))}
                              <td style={{ ...cellBase, textAlign: 'right', backgroundColor: zebra, fontWeight: 700, color: total == null ? '#bdc1c6' : '#174ea6', fontVariantNumeric: 'tabular-nums', borderLeft: '1px solid #dadce0' }}>
                                {fmt(total)}{total != null && isRateItem(item.item_name) ? ' (avg)' : ''}
                                {showPctRow && <PctOfPlan actual={total} plan={planTotal} />}
                              </td>
                            </tr>
                          );
                        })}
                      </React.Fragment>
                    );
                  })}
                </tbody>
              </table>
            </div>
            {mode === 'actual' && showPct && (
              <div style={{ marginTop: 6, fontSize: 11.5, color: 'var(--ui-text-tertiary)' }}>
                % of plan = actual ÷ AAP plan for that month (Total: over the months with an actual). Green ≥ 100%, amber 95–99%, red &lt; 95%.
              </div>
            )}
          </>
        )}
    </ReportPage>
  );
}
