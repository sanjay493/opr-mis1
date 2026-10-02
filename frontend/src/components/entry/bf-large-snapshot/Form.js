'use client';

// Manual entry for the "SAIL Large BFs — Performance Snapshot" report page
// (backend page_bf_large_annexure.py). Month and Till-Month values for the 3
// flagship furnaces (BSP BF-8, RSP BF-5, ISP BF-5), side by side, in the
// report's own row order.
//
// This is deliberately NOT a separate store: it loads and saves the very
// same techno_data rows (plant + furnace unit + month) that Techno Manual
// Entry edits, through the same /api/techno/manual/{entry,save} endpoints,
// under the same keys (PARAM_TEMPLATES['Blast Furnace']). A value entered on
// either page shows up on the other. A previous dedicated Large-BF form was
// removed because it saved under slightly different key names than Techno
// Manual Entry, so edits on one never appeared on the other — hence:
//   - the row list, labels, units and key aliases come from the backend
//     (/api/bf-benchmark/params), not a copy kept here;
//   - an existing value is read through the report's own key + alias order
//     and written back under the key it was found in, so the report and
//     Techno Manual Entry both keep reading the edited value.

import { useCallback, useEffect, useMemo, useState } from 'react';
import Link from 'next/link';
import GlobalNavbar from '@/components/GlobalNavbar';
import RequireEditor from '@/components/RequireEditor';
import { API_BASE_URL } from '@/providers/AuthProvider';
import { PARAM_TEMPLATES } from '@/lib/technoParamRegistry';
import ui from '@/styles/ui.module.css';
import s from './snapshot.module.css';

const MONTHS = [
  'April', 'May', 'June', 'July', 'August', 'September',
  'October', 'November', 'December', 'January', 'February', 'March',
];
const MONTH_NUM = {
  January: '01', February: '02', March: '03', April: '04', May: '05', June: '06',
  July: '07', August: '08', September: '09', October: '10', November: '11', December: '12',
};
const _now = new Date();
const CURRENT_FY_END_YEAR = (_now.getMonth() >= 3 ? _now.getFullYear() : _now.getFullYear() - 1) + 1;
const YEARS = Array.from({ length: CURRENT_FY_END_YEAR - 2015 + 1 }, (_, i) => String(CURRENT_FY_END_YEAR - i));
const PERIODS = [
  { id: 'month', label: 'Month' },
  { id: 'till_month', label: 'Till Month' },
];

function defaultPeriod() {
  const d = new Date();
  d.setMonth(d.getMonth() - 1);
  const names = ['January', 'February', 'March', 'April', 'May', 'June', 'July',
    'August', 'September', 'October', 'November', 'December'];
  return { monthName: names[d.getMonth()], year: String(d.getFullYear()) };
}

// Report rows that are not typed in on this form — where each one comes from.
const DERIVED = {
  working_volume_m3: { label: 'Working Volume', unit: 'm³', source: 'Static spec — edit in Large BF Benchmarking Entry', showWv: true },
  production: { label: 'Total HM Prod', unit: 'MT', source: "From production data (each furnace's own Hot Metal item)" },
  _avg_daily_rate: { label: 'Avg. Daily Rate', unit: 'TPD', source: 'Calculated: Total HM Prod ÷ days in the period' },
  _total_prepared_burden: { label: 'Total Prepared Burden', unit: '%', source: 'Calculated: Sinter + Pellet in Burden' },
  _coke_ash: { label: 'Coke Ash', unit: '%', source: 'Plant-level — entered under the Coke Ovens unit in Techno Manual Entry' },
  _avg_burden_fe: { label: 'Avg. Burden Fe', unit: '%', source: 'Calculated from the burden mix and Sinter / Pellet / Lump Ore Fe' },
};
// Same per-page label override page_bf_large_annexure.py's _row_spec applies.
const LABEL_OVERRIDES = { bf_productivity: 'BF Prodty-WV' };
const BF_TEMPLATE = new Set(PARAM_TEMPLATES['Blast Furnace']);
const LUMP_KEY = 'lump_in_burden';

function errText(detail, fallback) {
  if (!detail) return fallback;
  if (typeof detail === 'string') return detail;
  if (Array.isArray(detail)) return detail.map((e) => e?.msg || String(e)).join('; ') || fallback;
  return fallback;
}

function buildRows(meta) {
  const byKey = Object.fromEntries(meta.params.map((p) => [p.key, p]));
  return meta.large_bf_row_keys.map((key) => {
    if (key === '_sinter_fe') {
      // The report prefers Sinter Fe entered under the furnace's own unit.
      return { kind: 'entry', key, label: 'Sinter Fe', unit: '%', candidates: ['tfe_in_sinter'], storeKey: 'tfe_in_sinter' };
    }
    if (DERIVED[key]) return { kind: 'derived', key, ...DERIVED[key] };
    const p = byKey[key] || { label: key, unit: '' };
    // Report read order: canonical key first, then its aliases.
    const candidates = [key, ...(meta.key_aliases?.[key] || [])];
    // New values go under the key Techno Manual Entry uses for this concept.
    const storeKey = candidates.find((k) => BF_TEMPLATE.has(k)) || key;
    return {
      kind: key === 'fuel_rate' ? 'computed' : 'entry',
      key, label: LABEL_OVERRIDES[key] || p.label, unit: p.unit, candidates, storeKey,
    };
  });
}

const bfId = (bf) => `${bf.plant}:${bf.unit}`;
const num = (v) => (typeof v === 'number' && Number.isFinite(v) ? v : null);
// Display only: at most 2 decimals (trailing zeros dropped), or the row's own
// DISPLAY_DP. The stored value keeps its full precision and is only re-saved
// if the user edits the cell.
const DISPLAY_DP = { sulphur_in_hm: 3 };
const fmt2 = (v, dp = 2) => (num(v) === null ? '' : String(Math.round(v * 10 ** dp) / 10 ** dp));

function BfLargeSnapshotInner() {
  const def = defaultPeriod();
  const [monthName, setMonthName] = useState(def.monthName);
  const [year, setYear] = useState(def.year);
  const reportMonth = `${year}-${MONTH_NUM[monthName]}`;

  const [meta, setMeta] = useState(null);
  const [values, setValues] = useState({});     // {bfId: {month: {rowKey: v}, till_month: {...}}}
  const [initial, setInitial] = useState({});   // snapshot from the last load
  const [srcKeys, setSrcKeys] = useState({});   // {bfId: {period: {rowKey: storedUnderKey}}}
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [ytdBusy, setYtdBusy] = useState('');
  const [notice, setNotice] = useState(null);
  // Text of the cell being typed in ({"id|period|key": "12.3"}), so typing
  // isn't reformatted mid-keystroke; cleared on blur to show fmt2 again.
  const [drafts, setDrafts] = useState({});

  const rows = useMemo(() => (meta ? buildRows(meta) : []), [meta]);
  const bfs = meta?.sail_bfs || [];
  const wvById = useMemo(() => Object.fromEntries(
    (meta?.sail_bfs_all || []).map((b) => [`${b.plant}:${b.unit}`, b.working_volume_m3]),
  ), [meta]);

  useEffect(() => {
    fetch(`${API_BASE_URL}/api/bf-benchmark/params`)
      .then((r) => r.json())
      .then((d) => {
        if (!d.large_bf_row_keys) {
          throw new Error('The backend is older than this page — restart the backend to load it.');
        }
        setMeta(d);
      })
      .catch((e) => { setNotice({ type: 'error', text: `Could not load the parameter list: ${e.message}` }); setLoading(false); });
  }, []);

  const load = useCallback(async () => {
    if (!meta) return;
    setLoading(true);
    setNotice(null);
    try {
      const plants = [...new Set(meta.sail_bfs.map((b) => b.plant))];
      const results = await Promise.all(plants.map(async (plant) => {
        const r = await fetch(`${API_BASE_URL}/api/techno/manual/entry?plant=${plant}&report_month=${reportMonth}`);
        const d = await r.json();
        if (!r.ok) throw new Error(`${plant}: ${errText(d.detail, 'load failed')}`);
        return [plant, d.units || {}];
      }));
      const unitsByPlant = Object.fromEntries(results);
      const vals = {};
      const srcs = {};
      let found = 0;
      for (const bf of meta.sail_bfs) {
        const id = bfId(bf);
        const stored = unitsByPlant[bf.plant]?.[bf.unit] || {};
        vals[id] = { month: {}, till_month: {} };
        srcs[id] = { month: {}, till_month: {} };
        for (const { id: period } of PERIODS) {
          const data = stored[period] || {};
          for (const row of buildRows(meta)) {
            if (row.kind === 'derived') continue;
            const hit = row.candidates.find((k) => num(data[k]) !== null);
            vals[id][period][row.key] = hit ? data[hit] : null;
            if (hit) { srcs[id][period][row.key] = hit; found++; }
          }
        }
      }
      setValues(vals);
      setDrafts({});
      setInitial(JSON.parse(JSON.stringify(vals)));
      setSrcKeys(srcs);
      if (!found) setNotice({ type: 'info', text: `Nothing entered yet for ${monthName} ${year} — values you save here also appear in Techno Manual Entry.` });
    } catch (e) {
      setNotice({ type: 'error', text: `Load failed: ${e.message}` });
    } finally {
      setLoading(false);
    }
  }, [meta, reportMonth, monthName, year]);

  // Deferred a tick so the load's own state updates don't run synchronously
  // inside the effect (react-hooks/set-state-in-effect).
  useEffect(() => {
    let cancelled = false;
    Promise.resolve().then(() => { if (!cancelled) load(); });
    return () => { cancelled = true; };
  }, [load]);

  // Lump in Burden defaults to 100 − Total Prepared Burden (Sinter + Pellet
  // in Burden) while its own cell is empty. It stays a directly-entered key
  // (a furnace charging scrap has lump below that), so a typed value always
  // wins; clearing the cell brings the default back. The default is saved
  // like a typed value, so the report shows it too.
  const lumpDefault = useCallback((id, period) => {
    const d = values[id]?.[period] || {};
    const sinter = num(d.sinter_in_burden), pellet = num(d.pellet_in_burden);
    return sinter !== null && pellet !== null ? Math.round((100 - sinter - pellet) * 100) / 100 : null;
  }, [values]);
  const isLumpDefault = (id, period, key) =>
    key === LUMP_KEY && num(values[id]?.[period]?.[key]) === null && lumpDefault(id, period) !== null;
  // The value that will be saved: what's typed, else the Lump default.
  const effective = useCallback((id, period, key) => {
    const v = values[id]?.[period]?.[key] ?? null;
    return v === null && key === LUMP_KEY ? lumpDefault(id, period) : v;
  }, [values, lumpDefault]);

  const changes = useMemo(() => {
    const out = [];
    for (const [id, periods] of Object.entries(values)) {
      for (const { id: period } of PERIODS) {
        const keys = new Set([...Object.keys(periods[period] || {}), LUMP_KEY]);
        for (const key of keys) {
          if (effective(id, period, key) !== (initial[id]?.[period]?.[key] ?? null)) out.push({ id, period, key });
        }
      }
    }
    return out;
  }, [values, initial, effective]);
  const dirty = changes.length > 0;

  useEffect(() => {
    if (!dirty) return;
    const handler = (e) => { e.preventDefault(); e.returnValue = ''; };
    window.addEventListener('beforeunload', handler);
    return () => window.removeEventListener('beforeunload', handler);
  }, [dirty]);

  const changePeriod = (setter) => (e) => {
    if (dirty && !window.confirm('You have unsaved changes for this month. Discard them?')) return;
    setter(e.target.value);
  };

  const setCell = (id, period, key, raw) => {
    setDrafts((prev) => ({ ...prev, [`${id}|${period}|${key}`]: raw }));
    const v = raw === '' ? null : Number(raw);
    setValues((prev) => ({
      ...prev,
      [id]: { ...prev[id], [period]: { ...prev[id]?.[period], [key]: Number.isFinite(v) ? v : null } },
    }));
  };

  const isChanged = (id, period, key) =>
    effective(id, period, key) !== (initial[id]?.[period]?.[key] ?? null);

  // Fuel Rate = Coke + Nut Coke + CDI — the backend recalculates and stores
  // it on every save (db._maybe_recompute_derived_params); shown live here.
  const fuelRate = (id, period) => {
    const d = values[id]?.[period] || {};
    const coke = num(d.coke_rate), cdi = num(d.cdi);
    if (coke !== null && cdi !== null) return Math.round((coke + (num(d.nut_coke_rate) ?? 0) + cdi) * 100) / 100;
    return num(d.fuel_rate);
  };

  const targetKey = (id, period, row) => srcKeys[id]?.[period]?.[row.key] || row.storeKey;

  const save = async () => {
    setSaving(true);
    setNotice(null);
    const errors = [];
    let savedBfs = 0;
    for (const bf of bfs) {
      const id = bfId(bf);
      const body = {
        plant: bf.plant, report_month: reportMonth, unit: bf.unit,
        month_data: {}, till_month_data: {}, clear_month_keys: [], clear_till_keys: [],
      };
      let n = 0;
      for (const row of rows) {
        if (row.kind !== 'entry') continue;
        for (const { id: period } of PERIODS) {
          if (!isChanged(id, period, row.key)) continue;
          const v = effective(id, period, row.key);
          const k = targetKey(id, period, row);
          if (v === null) (period === 'month' ? body.clear_month_keys : body.clear_till_keys).push(k);
          else (period === 'month' ? body.month_data : body.till_month_data)[k] = v;
          n++;
        }
      }
      if (!n) continue;
      try {
        const r = await fetch(`${API_BASE_URL}/api/techno/manual/save`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          credentials: 'include',
          body: JSON.stringify(body),
        });
        const d = await r.json().catch(() => ({}));
        if (!r.ok) throw new Error(errText(d.detail, 'save failed'));
        savedBfs++;
      } catch (e) {
        errors.push(`${bf.label}: ${e.message}`);
      }
    }
    setSaving(false);
    await load();  // pick up the backend's recalculated Fuel Rate
    setNotice(errors.length
      ? { type: 'error', text: `Saved ${savedBfs} furnace(s). Failed — ${errors.join('; ')}` }
      : { type: 'success', text: `Saved ${savedBfs} furnace(s) for ${monthName} ${year}. The same values now show in Techno Manual Entry and the report.` });
  };

  // Fill a furnace's Till Month column from Apr→this month's monthly values,
  // with the same cumulative rules Techno Manual Entry's "Calculate
  // Cumulative" uses. Results are only placed in the form — review, then Save.
  const calcYtd = async (bf) => {
    const id = bfId(bf);
    const todo = rows.filter((r) => r.kind === 'entry' && num(values[id]?.month?.[r.key]) !== null);
    if (!todo.length) {
      setNotice({ type: 'info', text: `Enter ${bf.label}'s Month values first — Till Month is calculated from them.` });
      return;
    }
    setYtdBusy(id);
    setNotice(null);
    const results = await Promise.all(todo.map(async (row) => {
      const qs = new URLSearchParams({
        plant: bf.plant, unit: bf.unit, param_key: targetKey(id, 'month', row),
        report_month: reportMonth, current_value: values[id].month[row.key],
      });
      try {
        const r = await fetch(`${API_BASE_URL}/api/techno/manual/cumulative-preview?${qs}`);
        const d = await r.json();
        return r.ok ? { row, result: num(d.result), warnings: d.warnings || [] } : { row, result: null, warnings: [errText(d.detail, 'failed')] };
      } catch (e) {
        return { row, result: null, warnings: [e.message] };
      }
    }));
    setValues((prev) => {
      const till = { ...prev[id].till_month };
      for (const { row, result } of results) if (result !== null) till[row.key] = result;
      return { ...prev, [id]: { ...prev[id], till_month: till } };
    });
    setYtdBusy('');
    const filled = results.filter((r) => r.result !== null).length;
    const warned = results.filter((r) => r.result === null || r.warnings.length).map((r) => r.row.label);
    setNotice({
      type: warned.length ? 'warning' : 'success',
      text: `${bf.label}: calculated Till Month for ${filled} of ${todo.length} parameters — review, then Save.`
        + (warned.length ? ` Check: ${warned.join(', ')} (missing months or weights).` : ''),
    });
  };

  const alertClass = { success: ui.alertSuccess, error: ui.alertError, warning: ui.alertWarning, info: ui.alertWarning };

  return (
    <>
      <GlobalNavbar />
      <main className={`${ui.page} ${ui.pageWide}`} style={{ maxWidth: 1320 }}>
        <div className={ui.pageHeader}>
          <h1 className={ui.pageTitle}>SAIL Large BFs — Performance Snapshot</h1>
          <p className={ui.pageLead}>
            Month and Till Month figures for BSP BF-8, RSP BF-5 and ISP BF-5, in report order. Saves into the
            same techno data as <Link href="/data-entry/techno-manual">Techno Manual Entry</Link>, so a value
            entered on either page appears on both, and in the report.
          </p>
        </div>

        <div className={s.toolbar}>
          <div className={ui.field} style={{ marginBottom: 0 }}>
            <label htmlFor="snap-month" className={ui.label}>Month</label>
            <select id="snap-month" className="form-control" value={monthName} onChange={changePeriod(setMonthName)}>
              {MONTHS.map((m) => <option key={m} value={m}>{m}</option>)}
            </select>
          </div>
          <div className={ui.field} style={{ marginBottom: 0 }}>
            <label htmlFor="snap-year" className={ui.label}>Year</label>
            <select id="snap-year" className="form-control" value={year} onChange={changePeriod(setYear)}>
              {YEARS.map((y) => <option key={y} value={y}>{y}</option>)}
            </select>
          </div>
          <button type="button" className={`${ui.btn} ${ui.btnSecondary}`} disabled={loading || saving}
                  onClick={() => { if (!dirty || window.confirm('Discard your unsaved changes and reload?')) load(); }}>
            Reload
          </button>
          <span className={s.spacer} />
          <span className={ui.meta} style={{ margin: 0 }} aria-live="polite">
            {loading ? 'Loading…' : dirty ? `${changes.length} unsaved change${changes.length === 1 ? '' : 's'}` : 'All changes saved'}
          </span>
          <button type="button" className={`${ui.btn} ${ui.btnPrimary}`} onClick={save}
                  disabled={!dirty || saving || loading} aria-busy={saving}>
            {saving ? 'Saving…' : 'Save'}
          </button>
        </div>

        {notice && (
          <p role={notice.type === 'error' ? 'alert' : 'status'} className={`${ui.alert} ${alertClass[notice.type]}`}>
            {notice.text}
          </p>
        )}

        {meta && (
          <div className={s.gridWrap}>
            <table className={s.grid}>
              <thead>
                <tr>
                  <th scope="col" rowSpan={2} className={s.paramCol}>Parameter</th>
                  <th scope="col" rowSpan={2} className={s.unitCol}>Unit</th>
                  {bfs.map((bf) => (
                    <th key={bfId(bf)} scope="colgroup" colSpan={2} className={s.bfHead}>
                      <div className={s.bfHeadInner}>
                        <span>{bf.label}</span>
                        <button type="button" className={`${ui.btn} ${ui.btnSecondary} ${ui.btnSm}`}
                                onClick={() => calcYtd(bf)} disabled={loading || !!ytdBusy}
                                aria-busy={ytdBusy === bfId(bf)}
                                title="Calculate Till Month from April → this month's monthly values">
                          {ytdBusy === bfId(bf) ? 'Calculating…' : 'Calc. Till Month'}
                        </button>
                      </div>
                    </th>
                  ))}
                </tr>
                <tr>
                  {bfs.flatMap((bf) => PERIODS.map((p) => (
                    <th key={`${bfId(bf)}-${p.id}`} scope="col">{p.label}</th>
                  )))}
                </tr>
              </thead>
              <tbody>
                {rows.map((row) => {
                  if (row.kind === 'derived') {
                    return (
                      <tr key={row.key} className={s.derivedRow}>
                        <th scope="row" className={s.paramCol}>{row.label}</th>
                        <td className={s.unitCol}>{row.unit}</td>
                        {row.showWv
                          ? bfs.map((bf) => (
                            <td key={bfId(bf)} colSpan={2} className={s.computed}>
                              {fmt2(wvById[bfId(bf)]) || '—'}
                            </td>
                          ))
                          : <td colSpan={bfs.length * 2}>{row.source}</td>}
                      </tr>
                    );
                  }
                  return (
                    <tr key={row.key}>
                      <th scope="row" className={s.paramCol}>
                        {row.label}
                        {row.kind === 'computed' && <span className={s.aliasNote}>Auto: Coke + Nut Coke + CDI</span>}
                        {row.key === LUMP_KEY && <span className={s.aliasNote}>Default: 100 − Total Prepared Burden</span>}
                      </th>
                      <td className={s.unitCol}>{row.unit}</td>
                      {bfs.flatMap((bf) => PERIODS.map((p) => {
                        const id = bfId(bf);
                        if (row.kind === 'computed') {
                          const v = fuelRate(id, p.id);
                          return <td key={`${id}-${p.id}`} className={s.computed}>{fmt2(v) || '—'}</td>;
                        }
                        const src = srcKeys[id]?.[p.id]?.[row.key];
                        const changed = isChanged(id, p.id, row.key);
                        const isDefault = isLumpDefault(id, p.id, row.key);
                        return (
                          <td key={`${id}-${p.id}`}>
                            <input
                              type="number" step="any" inputMode="decimal"
                              className={`${s.cell} ${changed ? s.cellChanged : ''} ${isDefault ? s.cellDefault : ''}`}
                              value={drafts[`${id}|${p.id}|${row.key}`] ?? fmt2(effective(id, p.id, row.key), DISPLAY_DP[row.key])}
                              onChange={(e) => setCell(id, p.id, row.key, e.target.value)}
                              onBlur={() => setDrafts((prev) => {
                                const next = { ...prev };
                                delete next[`${id}|${p.id}|${row.key}`];
                                return next;
                              })}
                              disabled={loading || saving}
                              aria-label={`${row.label}, ${bf.label}, ${p.label}`}
                              title={isDefault ? 'Default: 100 − Total Prepared Burden. Type a value to override.'
                                : src && src !== row.storeKey ? `Stored as "${src}"` : undefined}
                            />
                          </td>
                        );
                      }))}
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}

        <div className={s.legend}>
          <span><span className={s.swatch} />Changed, not yet saved</span>
          <span><span className={`${s.swatch} ${s.swatchDerived}`} />Not entered here — filled automatically from the source shown</span>
          <span>Clearing a box and saving removes that value.</span>
        </div>
      </main>
    </>
  );
}

export default function BfLargeSnapshotPage() {
  return (
    <RequireEditor>
      <BfLargeSnapshotInner />
    </RequireEditor>
  );
}
