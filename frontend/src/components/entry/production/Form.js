'use client';

import RequireEditor from '@/components/RequireEditor';

import React, { useState, useCallback, useMemo } from 'react';
import GlobalNavbar from '@/components/GlobalNavbar';
import s from './Form.module.css';

const PLANTS = ['BSP', 'DSP', 'ISP', 'RSP', 'BSL', 'ASP', 'SSP', 'VISL'];
const PLANT_NAMES = {
  BSP: 'Bhilai Steel Plant', DSP: 'Durgapur Steel Plant', ISP: 'IISCO Steel Plant', RSP: 'Rourkela Steel Plant',
  BSL: 'Bokaro Steel Plant', ASP: 'Alloy Steels Plant', SSP: 'Salem Steel Plant', VISL: 'Visvesvaraya Iron & Steel Plant',
};
const MONTHS = [
  'April', 'May', 'June', 'July', 'August', 'September',
  'October', 'November', 'December', 'January', 'February', 'March'
];

const MONTH_NUM = {
  'January': '01', 'February': '02', 'March': '03', 'April': '04',
  'May': '05', 'June': '06', 'July': '07', 'August': '08',
  'September': '09', 'October': '10', 'November': '11', 'December': '12',
};
const YEAR_RANGE_START = 2000;
const _now = new Date();
// FY start year: Apr..Dec -> this calendar year; Jan..Mar -> previous calendar year
const CURRENT_FY_END_YEAR = (_now.getMonth() >= 3 ? _now.getFullYear() : _now.getFullYear() - 1) + 1;

// Calendar years: 2000 through the current FY's end year (covers Jan-Mar
// report months that fall in the current FY but the next calendar year).
const YEARS = Array.from(
  { length: CURRENT_FY_END_YEAR - YEAR_RANGE_START + 1 },
  (_, i) => (YEAR_RANGE_START + i).toString()
);

// Summary cards under the table — shown for the items the plant reports
const KPI_ITEMS = [
  { key: 'Hot Metal', label: 'Hot metal' },
  { key: 'Total Crude Steel', label: 'Crude steel' },
  { key: 'Saleable Steel', label: 'Saleable steel' },
];

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || '';

function getDefaultPeriod() {
  const d = new Date();
  d.setMonth(d.getMonth() - 1);
  // MONTHS is FY-ordered (April-first) — can't index it with JS's
  // Jan-ordered getMonth(), so look the name up in a Jan-ordered array.
  const names = ['January','February','March','April','May','June','July','August','September','October','November','December'];
  return { month: names[d.getMonth()], year: d.getFullYear().toString() };
}

// 'YYYY-MM' shifted by n months
const shiftMonth = (ym, n) => {
  const d = new Date(Number(ym.slice(0, 4)), Number(ym.slice(5, 7)) - 1 + n, 1);
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}`;
};
const toNum = (v) => (v === '' || v == null || Number.isNaN(parseFloat(v)) ? null : parseFloat(v));
const fmt = (v) => (v == null ? '—' : v.toLocaleString('en-IN', { maximumFractionDigits: 3 }));
const pctChange = (cur, base) => (cur == null || base == null || base === 0 ? null : ((cur - base) / base) * 100);

async function fetchItems(plant, month) {
  const res = await fetch(`${API_BASE_URL}/api/production-items?plant=${encodeURIComponent(plant)}&month=${encodeURIComponent(month)}`);
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}
// item_name -> actual, for the comparison columns; a failed lookup just leaves them blank
async function fetchActuals(plant, month) {
  try {
    const data = await fetchItems(plant, month);
    return Object.fromEntries(data.items.map(it => [it.item_name, it.actual_value]));
  } catch {
    return {};
  }
}

const VarPill = ({ value }) => {
  if (value == null) return <span className={s.muted}>—</span>;
  const cls = value > 0 ? s.varUp : value < 0 ? s.varDown : s.varFlat;
  return <span className={`${s.var} ${cls}`}>{value > 0 ? '+' : ''}{value.toFixed(1)}%</span>;
};
const Delta = ({ value }) => (value == null ? null : (
  <span className={`${s.delta} ${value >= 0 ? s.up : s.down}`}>{value >= 0 ? '▲' : '▼'} {Math.abs(value).toFixed(1)}%</span>
));

function ProductionDataEntryPageInner() {
  const defaultPeriod = getDefaultPeriod();
  const [plant, setPlant] = useState('BSP');
  const [month, setMonth] = useState(defaultPeriod.month);
  const [year, setYear] = useState(defaultPeriod.year);
  const [items, setItems] = useState([]);
  const [knownItems, setKnownItems] = useState([]);
  const [prevActuals, setPrevActuals] = useState({});
  const [cplyActuals, setCplyActuals] = useState({});
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [status, setStatus] = useState(null);
  const [loaded, setLoaded] = useState(false);
  const newRowSeq = React.useRef(0);

  const reportMonth = `${year}-${MONTH_NUM[month]}`;
  const reportMonthDisplay = `${month} ${year}`;
  const prevMonth = shiftMonth(reportMonth, -1);
  const cplyMonth = shiftMonth(reportMonth, -12);
  const fyStart = Number(MONTH_NUM[month]) >= 4 ? Number(year) : Number(year) - 1;
  const shortMonth = (ym) => `${['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'][Number(ym.slice(5)) - 1]}'${ym.slice(2, 4)}`;

  const handleLoad = useCallback(async () => {
    setLoading(true);
    setStatus(null);
    setLoaded(false);
    try {
      const [data, suggestRes, prev, cply] = await Promise.all([
        fetchItems(plant, reportMonth),
        fetch(`${API_BASE_URL}/api/item-mapping-suggestions?plant=${encodeURIComponent(plant)}`),
        fetchActuals(plant, shiftMonth(reportMonth, -1)),
        fetchActuals(plant, shiftMonth(reportMonth, -12)),
      ]);
      setKnownItems(suggestRes.ok ? (await suggestRes.json()).items ?? [] : []);
      setPrevActuals(prev);
      setCplyActuals(cply);
      if (data.items.length === 0) {
        setStatus({ type: 'error', text: `No plan items found for ${plant} in ${reportMonthDisplay}. Upload ABP plan first.` });
        setItems([]);
      } else {
        setItems(data.items.map(it => ({
          item_name: it.item_name,
          plan_value: it.plan_value ?? '',
          actual_value: it.actual_value ?? '',
          plan_edit: String(it.plan_value ?? ''),
          actual_edit: String(it.actual_value ?? ''),
        })));
        setLoaded(true);
      }
    } catch (err) {
      setStatus({ type: 'error', text: `Load failed: ${err.message}` });
    } finally {
      setLoading(false);
    }
  }, [plant, reportMonth, reportMonthDisplay]);

  const handleAddRow = () => {
    newRowSeq.current += 1;
    setItems(prev => [...prev, {
      key: `new-${newRowSeq.current}`,
      isNew: true,
      item_name: '',
      plan_value: '',
      actual_value: '',
      plan_edit: '',
      actual_edit: '',
    }]);
  };

  const handleRemoveRow = (idx) => {
    setItems(prev => prev.filter((_, i) => i !== idx));
  };

  const handleItemNameChange = (idx, val) => {
    setItems(prev => prev.map((it, i) => i === idx ? { ...it, item_name: val } : it));
  };

  const handleActualChange = (idx, val) => {
    setItems(prev => prev.map((it, i) => i === idx ? { ...it, actual_edit: val } : it));
  };

  const handlePlanChange = (idx, val) => {
    setItems(prev => prev.map((it, i) => i === idx ? { ...it, plan_edit: val } : it));
  };

  const handleReset = () => {
    setItems(prev => prev
      .filter(it => !it.isNew)
      .map(it => ({ ...it, plan_edit: String(it.plan_value ?? ''), actual_edit: String(it.actual_value ?? '') })));
    setStatus(null);
  };

  const handleSave = async () => {
    setSaving(true);
    setStatus(null);
    const entries = items.map(it => ({
      item_name: it.item_name.trim(),
      actual_value: it.actual_edit !== '' && it.actual_edit !== null ? parseFloat(it.actual_edit) : null,
      plan_value: it.plan_edit !== '' && it.plan_edit !== null ? parseFloat(it.plan_edit) : null,
    })).filter(e => e.item_name !== '' && (e.actual_value !== null || e.plan_value !== null));

    try {
      const res = await fetch(`${API_BASE_URL}/api/production-entry`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ plant, month: reportMonth, entries }),
      });
      if (!res.ok) throw new Error(await res.text());
      const result = await res.json();
      setStatus({ type: 'success', text: `Saved ${result.count} value(s) for ${plant} — ${reportMonthDisplay}.` });
      await handleLoad();
    } catch (err) {
      setStatus({ type: 'error', text: `Save failed: ${err.message}` });
    } finally {
      setSaving(false);
    }
  };

  const isDirty = (it) =>
    it.isNew ||
    it.actual_edit !== String(it.actual_value ?? '') ||
    it.plan_edit !== String(it.plan_value ?? '');
  const dirtyCount = items.filter(isDirty).length;
  const hasChanges = dirtyCount > 0;

  const usedItemNames = useMemo(
    () => new Set(items.map(it => it.item_name.trim().toLowerCase()).filter(Boolean)),
    [items]
  );
  const itemSuggestions = useMemo(
    () => knownItems.filter(n => !usedItemNames.has(n.trim().toLowerCase())),
    [knownItems, usedItemNames]
  );

  // Entry status for the side panel
  const summary = useMemo(() => {
    let filled = 0, above = 0, below = 0, worst = null;
    items.forEach(it => {
      const plan = toNum(it.plan_edit), actual = toNum(it.actual_edit);
      if (actual != null) filled += 1;
      const v = pctChange(actual, plan);
      if (v == null) return;
      if (v >= 0) above += 1; else below += 1;
      if (v < 0 && (worst == null || v < worst.v)) worst = { name: it.item_name, v };
    });
    return { filled, above, below, worst, total: items.length };
  }, [items]);
  const pctFilled = summary.total ? Math.round((summary.filled / summary.total) * 100) : 0;

  const kpis = KPI_ITEMS
    .map(k => {
      const it = items.find(x => x.item_name === k.key);
      if (!it) return null;
      const plan = toNum(it.plan_edit), actual = toNum(it.actual_edit);
      return { ...k, plan, actual, ach: plan ? (actual / plan) * 100 : null, cply: pctChange(actual, cplyActuals[k.key]) };
    })
    .filter(Boolean);

  const clearLoaded = () => { setLoaded(false); setItems([]); };

  return (
    <div className={s.standalone}>
      <GlobalNavbar />
      <div className={s.page}>
        <div className={s.inner}>
          {/* ── Context bar ── */}
          <div className={s.ctxBar}>
            <div className={s.ctxField}>
              <span className={s.ctxLabel}>Steel plant</span>
              <select className={s.select} value={plant} aria-label="Plant"
                      onChange={e => { setPlant(e.target.value); clearLoaded(); }}>
                {PLANTS.map(p => <option key={p} value={p}>{p} — {PLANT_NAMES[p]}</option>)}
              </select>
            </div>
            <div className={s.ctxField}>
              <span className={s.ctxLabel}>Reporting month</span>
              <div className={s.ctxRow}>
                <select className={s.select} value={month} aria-label="Month"
                        onChange={e => { setMonth(e.target.value); clearLoaded(); }}>
                  {MONTHS.map(m => <option key={m} value={m}>{m}</option>)}
                </select>
                <select className={s.select} value={year} aria-label="Year"
                        onChange={e => { setYear(e.target.value); clearLoaded(); }}>
                  {YEARS.map(y => <option key={y} value={y}>{y}</option>)}
                </select>
              </div>
            </div>
            <div className={s.ctxField}>
              <span className={s.ctxLabel}>Fiscal year</span>
              <span className={s.fyChip}>FY {fyStart}-{String(fyStart + 1).slice(2)}</span>
            </div>
            <div className={s.ctxEnd}>
              <button type="button" className={`${s.btn} ${s.btnPrimary}`} onClick={handleLoad} disabled={loading}>
                {loading ? 'Loading…' : loaded ? '⟳ Reload Items' : 'Load Plant Items'}
              </button>
            </div>
          </div>

          {status && (
            <div role={status.type === 'error' ? 'alert' : 'status'}
                 className={`${s.alert} ${status.type === 'success' ? s.alertSuccess : s.alertError}`}>
              {status.text}
            </div>
          )}

          {!loaded && !loading && (
            <div className={s.empty}>
              Select plant, month and year, then click <strong>Load Plant Items</strong> to enter production data.
            </div>
          )}

          {loaded && items.length > 0 && (
            <>
              <div className={s.workbench}>
                {/* ── Entry table ── */}
                <div className={s.panel}>
                  <div className={s.panelHead}>
                    <div>
                      <h2 className={s.panelTitle}>Monthly production — {plant}, {reportMonthDisplay}</h2>
                      <p className={s.panelSub}>
                        Actuals against the ABP plan, in &apos;000 tonnes unless the item names its unit. Plan values come from the uploaded ABP and can be edited.
                      </p>
                    </div>
                    <span className={`${s.badge} ${hasChanges ? s.badgeAmber : s.badgeGreen}`}>
                      {hasChanges ? `${dirtyCount} unsaved` : 'Saved'}
                    </span>
                  </div>

                  <div className={s.tableWrap}>
                    <table className={s.table}>
                      <thead>
                        <tr>
                          <th className={s.left}>#</th>
                          <th className={s.left}>Item</th>
                          <th>Plan<span className={s.thSub}>(&apos;000 T)</span></th>
                          <th className={s.thActual}>Actual<span className={s.thSub}>{shortMonth(reportMonth)}</span></th>
                          <th>Var vs plan</th>
                          <th>Prev month<span className={s.thSub}>{shortMonth(prevMonth)} · MoM</span></th>
                          <th>CPLY<span className={s.thSub}>{shortMonth(cplyMonth)} · growth</span></th>
                        </tr>
                      </thead>
                      <tbody>
                        {items.map((item, idx) => {
                          const plan = toNum(item.plan_edit), actual = toNum(item.actual_edit);
                          const prev = prevActuals[item.item_name] ?? null;
                          const cply = cplyActuals[item.item_name] ?? null;
                          return (
                            <tr key={item.key ?? item.item_name} className={isDirty(item) ? s.rowDirty : ''}>
                              <td className={`${s.left} ${s.idx}`}>{idx + 1}</td>
                              <td className={`${s.left} ${s.item}`}>
                                {item.isNew ? (
                                  <div className={s.newItem}>
                                    <input
                                      type="text" list="known-item-names"
                                      className={`${s.cellInput} ${s.nameInput}`}
                                      value={item.item_name}
                                      onChange={e => handleItemNameChange(idx, e.target.value)}
                                      placeholder="Select or type item name"
                                    />
                                    <button type="button" className={s.removeBtn} title="Remove row"
                                            onClick={() => handleRemoveRow(idx)}>×</button>
                                  </div>
                                ) : item.item_name}
                              </td>
                              <td>
                                <input type="number" step="0.001" aria-label={`${item.item_name} plan`}
                                       className={`${s.cellInput} ${s.cellInputPlan}`}
                                       value={item.plan_edit} onChange={e => handlePlanChange(idx, e.target.value)} />
                              </td>
                              <td>
                                <input type="number" step="0.001" aria-label={`${item.item_name} actual`}
                                       className={`${s.cellInput} ${s.cellInputActual}`}
                                       value={item.actual_edit} onChange={e => handleActualChange(idx, e.target.value)} />
                              </td>
                              <td><VarPill value={pctChange(actual, plan)} /></td>
                              <td className={s.num}>
                                {prev == null ? <span className={s.muted}>—</span> : fmt(prev)}
                                <Delta value={pctChange(actual, prev)} />
                              </td>
                              <td className={s.num}>
                                {cply == null ? <span className={s.muted}>—</span> : fmt(cply)}
                                <Delta value={pctChange(actual, cply)} />
                              </td>
                            </tr>
                          );
                        })}
                      </tbody>
                    </table>
                    <datalist id="known-item-names">
                      {itemSuggestions.map(n => <option key={n} value={n} />)}
                    </datalist>
                  </div>

                  <div className={s.tableFoot}>
                    <span>{summary.total} items · variance = (actual − plan) ÷ plan · MoM and growth compare this month&apos;s actual</span>
                    <button type="button" className={`${s.btn} ${s.btnDashed}`} onClick={handleAddRow}>+ Add Item</button>
                  </div>
                </div>

                {/* ── Side panel ── */}
                <aside className={s.side}>
                  <div className={s.panel}>
                    <div className={s.panelHead}>
                      <div>
                        <h2 className={s.panelTitle}>Entry status</h2>
                        <p className={s.panelSub}>{plant} · {reportMonthDisplay}</p>
                      </div>
                      <span className={`${s.badge} ${pctFilled === 100 ? s.badgeGreen : s.badgeBlue}`}>
                        {pctFilled === 100 ? 'Complete' : 'In progress'}
                      </span>
                    </div>
                    <div className={s.sideBody}>
                      <div>
                        <div className={s.progressTop}><span>Actuals entered</span><span>{pctFilled}%</span></div>
                        <div className={s.progressBar}><span style={{ width: `${pctFilled}%` }} /></div>
                        <div className={s.progressNote}>{summary.filled} of {summary.total} items have an actual value</div>
                      </div>
                      <div className={s.stats}>
                        <div className={s.stat}>
                          <div className={s.statLabel}>At / above plan</div>
                          <div className={`${s.statValue} ${s.up}`}>{summary.above}</div>
                        </div>
                        <div className={s.stat}>
                          <div className={s.statLabel}>Below plan</div>
                          <div className={`${s.statValue} ${s.down}`}>{summary.below}</div>
                        </div>
                      </div>
                      {summary.worst && (
                        <div className={s.callout}>
                          <b>Largest shortfall:</b> {summary.worst.name} at {summary.worst.v.toFixed(1)}% vs plan.
                        </div>
                      )}
                      <div className={s.sideActions}>
                        <button type="button" className={`${s.btn} ${s.btnSuccess} ${s.btnBlock}`}
                                onClick={handleSave} disabled={saving || !hasChanges}>
                          {saving ? 'Saving…' : hasChanges ? `Save ${dirtyCount} change${dirtyCount === 1 ? '' : 's'} to DB` : 'Save to DB'}
                        </button>
                        <div className={s.sideRow}>
                          <button type="button" className={s.btn} onClick={handleReset} disabled={!hasChanges}>Reset</button>
                          <button type="button" className={s.btn} onClick={handleAddRow}>+ Add Item</button>
                        </div>
                      </div>
                    </div>
                  </div>
                </aside>
              </div>

              {/* ── KPI cards ── */}
              {kpis.length > 0 && (
                <div className={s.kpis}>
                  {kpis.map(k => (
                    <div key={k.key} className={s.kpi}>
                      <div className={s.kpiHead}>
                        <span className={s.kpiLabel}>{k.label}</span>
                        <VarPill value={k.cply} />
                      </div>
                      <div className={s.kpiValue}>{fmt(k.actual)}<span className={s.kpiUnit}>&apos;000 T</span></div>
                      <div className={s.kpiFoot}>
                        Plan {fmt(k.plan)} · {k.ach == null ? 'no plan' : `${k.ach.toFixed(1)}% achieved`} · badge = growth vs CPLY
                      </div>
                      <div className={s.kpiBar}>
                        <span style={{
                          width: `${Math.min(k.ach ?? 0, 100)}%`,
                          background: k.ach == null ? 'var(--ui-border)' : k.ach >= 100 ? 'var(--ui-success)' : k.ach >= 95 ? '#f9ab00' : 'var(--ui-danger)',
                        }} />
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  );
}

export default function ProductionDataEntryPage() {
  return (
    <RequireEditor>
      <ProductionDataEntryPageInner />
    </RequireEditor>
  );
}
