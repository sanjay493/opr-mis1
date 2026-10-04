'use client';

import RequireEditor from '@/components/RequireEditor';
import { useState, useEffect, useCallback } from 'react';
import { EntryPage, ContextBar, Field, Status, Section, SaveButton, cellClass, entryStyles as es } from '../EntryUI';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || '';

// Same 5 plants as the Key Parameters report page itself (backend
// page_key_parameters.py's PLANTS) — that page has no SAIL column, so
// neither does this form.
const PLANTS = ['BSP', 'DSP', 'RSP', 'BSL', 'ISP'];

const MONTHS = [
  'April', 'May', 'June', 'July', 'August', 'September',
  'October', 'November', 'December', 'January', 'February', 'March',
];
const MONTH_NUM = {
  January: '01', February: '02', March: '03', April: '04',
  May: '05', June: '06', July: '07', August: '08',
  September: '09', October: '10', November: '11', December: '12',
};
const YEAR_RANGE_START = 2000;
const _now = new Date();
const CURRENT_FY_END_YEAR = (_now.getMonth() >= 3 ? _now.getFullYear() : _now.getFullYear() - 1) + 1;
const YEARS = Array.from(
  { length: CURRENT_FY_END_YEAR - YEAR_RANGE_START + 1 },
  (_, i) => String(YEAR_RANGE_START + i)
);

function getDefaultPeriod() {
  const d = new Date(); d.setMonth(d.getMonth() - 1);
  const names = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December'];
  return { monthName: names[d.getMonth()], year: String(d.getFullYear()) };
}

// The Key Parameters report page (page_key_parameters.py) reads these 5
// under techno_data unit="General" — none of them has an extractor behind
// it (no file upload ever fills them), so this is their only data source.
const GENERAL_UNIT = 'General';
// `scale` (optional): this field is STORED (techno_data) in a different
// unit than it's shown/entered here — `scale` is "stored units per shown
// unit" (e.g. Demurrage: 100 Rs Lakh per Rs Cr), divided out on load and
// multiplied back in on save, so the raw techno_data figure (and the
// report page's own /100 — see page_key_parameters.py's "demurrage"
// branch) never has to change, only the unit each side shows.
const GENERAL_PARAMS = [
  { key: 'capex', label: 'CAPEX', unit: 'Rs Cr' },
  { key: 'labour_productivity', label: 'Labour Productivity', unit: 'T/Man-yr' },
  { key: 'avg_rake_detention_time', label: 'Avg Rake Detention Time', unit: 'Hrs' },
  { key: 'demurrage', label: 'Demurrage', unit: 'Rs Cr', scale: 100 },
  { key: 'hm_to_pcm_sandpit_drypit', label: 'HM Sent to PCM/Sand Pit/Dry Pit', unit: "'000 T" },
  // RLTIFR — Reportable Lost Time Injury Frequency Rate. Report page reads
  // the till-month value; monthly is kept too for a future extractor.
  { key: 'rltifr', label: 'RLTIFR', unit: '--' },
];

// Sinter Fe is different: the report page's "Sinter Fe" row reads
// tfe_in_sinter from a plant-specific unit, not "General" — RSP shows its
// three sinter plants slash-joined (_SP_UNIT_MAP/_sinter_fe_val in
// page_key_parameters.py), every other plant reads the single BF-shop
// figure (BF_Shop, or BF-5 for ISP, a single-furnace plant with no
// separate shop-aggregate unit — same fallback page_key_parameters.py's
// _BF_UNITS itself uses). RSP already gets this from its own techno
// extractor each month (rsp_technopara_sections.py); the field's here too
// so a correction/override is possible without digging through the full
// Techno Manual Entry form.
const FE_SINTER_UNITS = {
  BSP: ['BF_Shop'],
  DSP: ['BF_Shop'],
  RSP: ['SP-1', 'SP-2', 'SP-3'],
  BSL: ['BF_Shop'],
  ISP: ['BF-5'],
};
const FE_SINTER_KEY = 'tfe_in_sinter';

// Avg Rake Detention Time: the report page (page_key_parameters.py's
// "rake_detention" row) reads the Rake Detention summary's own figures
// (rake_detention_summary, entered/extracted on /data-entry/rake-detention)
// — CUR_MON_TY for the month, YTD_TY for till-month — and only falls back
// to this form's techno_data value for a month with no summary. So when the
// summary exists the row here shows those figures read-only and is left out
// of Save, rather than storing a second, conflicting copy.
const RAKE_KEY = 'avg_rake_detention_time';

// Count of param/unit keys whose current value differs from the value
// last loaded/saved — drives both the changed-cell highlight and the
// "Save (N changes)" button label, same convention as techno-manual/
// page.js's countChanges().
function countChanges(generalMonth, generalTill, initGeneralMonth, initGeneralTill,
                       feMonth, feTill, initFeMonth, initFeTill, feUnits, rakeFromSummary) {
  let n = 0;
  for (const { key } of GENERAL_PARAMS) {
    if (key === RAKE_KEY && rakeFromSummary) continue;
    if ((generalMonth[key] ?? '') !== (initGeneralMonth[key] ?? '')) n++;
    if ((generalTill[key] ?? '') !== (initGeneralTill[key] ?? '')) n++;
  }
  for (const unit of feUnits) {
    if ((feMonth[unit] ?? '') !== (initFeMonth[unit] ?? '')) n++;
    if ((feTill[unit] ?? '') !== (initFeTill[unit] ?? '')) n++;
  }
  return n;
}

function ChangedInput({ value, onChange, changed, disabled, label }) {
  return (
    <input
      type="number" step="any" disabled={disabled} aria-label={label}
      className={cellClass({ changed, filled: value !== '' && value != null })}
      style={{ width: 120 }}
      value={value}
      onChange={onChange}
    />
  );
}

function KeyParametersManualInner() {
  const def = getDefaultPeriod();
  const [plant, setPlant] = useState('BSP');
  const [monthName, setMonthName] = useState(def.monthName);
  const [year, setYear] = useState(def.year);
  const [generalMonth, setGeneralMonth] = useState({});
  const [generalTill, setGeneralTill] = useState({});
  const [feMonth, setFeMonth] = useState({});   // { unit: value }
  const [feTill, setFeTill] = useState({});     // { unit: value }
  const [initGeneralMonth, setInitGeneralMonth] = useState({});
  const [initGeneralTill, setInitGeneralTill] = useState({});
  const [initFeMonth, setInitFeMonth] = useState({});
  const [initFeTill, setInitFeTill] = useState({});
  // { month, till } from the Rake Detention summary, or null when this
  // plant/month has no summary figures (row stays a manual fallback).
  const [rakeSummary, setRakeSummary] = useState(null);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [status, setStatus] = useState(null);

  const reportMonth = `${year}-${MONTH_NUM[monthName]}`;
  const feUnits = FE_SINTER_UNITS[plant] || [];

  const load = useCallback(async () => {
    setLoading(true);
    setStatus(null);
    try {
      const res = await fetch(`${API_BASE_URL}/api/techno/manual/entry?plant=${plant}&report_month=${reportMonth}`);
      const json = await res.json();
      if (!res.ok) throw new Error(json.detail || 'Load failed');
      const general = json.units?.[GENERAL_UNIT] || {};
      const gm = { ...general.month };
      const gt = { ...general.till_month };
      for (const { key, scale } of GENERAL_PARAMS) {
        if (!scale) continue;
        if (gm[key] != null) gm[key] = gm[key] / scale;
        if (gt[key] != null) gt[key] = gt[key] / scale;
      }
      setGeneralMonth(gm);
      setGeneralTill(gt);
      setInitGeneralMonth(gm);
      setInitGeneralTill(gt);

      const fm = {}, ft = {};
      for (const unit of FE_SINTER_UNITS[plant] || []) {
        const u = json.units?.[unit] || {};
        fm[unit] = u.month?.[FE_SINTER_KEY] ?? '';
        ft[unit] = u.till_month?.[FE_SINTER_KEY] ?? '';
      }
      setFeMonth(fm);
      setFeTill(ft);
      setInitFeMonth(fm);
      setInitFeTill(ft);

      // Rake Detention summary — a failure here just leaves the row as the
      // manual fallback rather than blocking the rest of the form.
      let rake = null;
      try {
        const rr = await fetch(`${API_BASE_URL}/api/rake-detention/grid?report_month=${reportMonth}`);
        if (rr.ok) {
          const rj = await rr.json();
          const pick = (code) => (rj.summary || []).find((s) => s.period_row === code && s.plant === plant)?.value ?? null;
          const month = pick('CUR_MON_TY');
          const till = pick('YTD_TY');
          if (month != null || till != null) rake = { month, till };
        }
      } catch { /* fallback to manual entry */ }
      setRakeSummary(rake);
    } catch (err) {
      setStatus({ type: 'error', text: err.message });
    } finally {
      setLoading(false);
    }
  }, [plant, reportMonth]);

  useEffect(() => { load(); }, [load]);

  const totalChanges = countChanges(
    generalMonth, generalTill, initGeneralMonth, initGeneralTill,
    feMonth, feTill, initFeMonth, initFeTill, feUnits, rakeSummary != null,
  );

  const saveUnit = async (unit, month_data, till_month_data) => {
    const res = await fetch(`${API_BASE_URL}/api/techno/manual/save`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ plant, report_month: reportMonth, unit, month_data, till_month_data }),
    });
    const json = await res.json();
    if (!res.ok) throw new Error(json.detail || `Save failed (${unit})`);
  };

  const handleSave = async () => {
    setSaving(true);
    setStatus(null);
    try {
      const month_data = {};
      const till_month_data = {};
      for (const { key, scale } of GENERAL_PARAMS) {
        // Not sent at all (not even as null) while the summary supplies it,
        // so a stored fallback value is left untouched.
        if (key === RAKE_KEY && rakeSummary) continue;
        const mv = generalMonth[key] === '' || generalMonth[key] === undefined ? null : Number(generalMonth[key]);
        const tv = generalTill[key] === '' || generalTill[key] === undefined ? null : Number(generalTill[key]);
        month_data[key] = mv !== null && scale ? mv * scale : mv;
        till_month_data[key] = tv !== null && scale ? tv * scale : tv;
      }
      // Same "nothing to send" guard as the FE-Sinter loop below — only
      // call saveUnit when at least one General param actually has a
      // value; otherwise the backend's own "No values provided" rejection
      // would surface here even when the real edit was only a Sinter Fe
      // change below.
      const hasGeneralValue = Object.values(month_data).some((v) => v !== null)
        || Object.values(till_month_data).some((v) => v !== null);
      if (hasGeneralValue) {
        await saveUnit(GENERAL_UNIT, month_data, till_month_data);
      }

      for (const unit of feUnits) {
        const mv = feMonth[unit];
        const tv = feTill[unit];
        const mBlank = mv === '' || mv === undefined || mv === null;
        const tBlank = tv === '' || tv === undefined || tv === null;
        // Skip units with nothing entered on either side — saveUnit would
        // send {tfe_in_sinter: null} for both periods, which the backend
        // rejects as "No values provided — nothing to save." (a save with
        // nothing to send there, not a real failure), surfacing as a
        // misleading error even when the General params above just saved
        // fine (e.g. only a Demurrage till-month value was changed and
        // this plant has never had a Sinter Fe figure entered at all).
        if (mBlank && tBlank) continue;
        await saveUnit(
          unit,
          { [FE_SINTER_KEY]: mBlank ? null : Number(mv) },
          { [FE_SINTER_KEY]: tBlank ? null : Number(tv) },
        );
      }
      // Resets the changed-highlight/count baseline to what was just
      // saved, same as techno-manual/page.js's saveAll().
      setInitGeneralMonth({ ...generalMonth });
      setInitGeneralTill({ ...generalTill });
      setInitFeMonth({ ...feMonth });
      setInitFeTill({ ...feTill });
      setStatus({ type: 'success', text: `✓ Saved for ${plant} ${reportMonth}` });
    } catch (err) {
      setStatus({ type: 'error', text: err.message });
    } finally {
      setSaving(false);
    }
  };

  const renderRow = (key, label, unit, monthVal, tillVal, onMonth, onTill, i, monthChanged, tillChanged) => (
    <tr key={key}>
      <td className={es.itemCell}>{label}</td>
      <td style={{ color: 'var(--ui-text-secondary)' }}>{unit}</td>
      <td className={es.r}>
        <ChangedInput value={monthVal ?? ''} disabled={saving} changed={monthChanged} onChange={onMonth} label={`${label} month`} />
      </td>
      <td className={es.r}>
        <ChangedInput value={tillVal ?? ''} disabled={saving} changed={tillChanged} onChange={onTill} label={`${label} till month`} />
      </td>
    </tr>
  );

  const rakeSummaryRow = (label, unit) => (
    <tr key={RAKE_KEY}>
      <td className={es.itemCell}>
        {label}
        <div style={{ fontSize: '8.5pt', color: 'var(--ui-text-secondary)' }}>
          from <a href="/data-entry/rake-detention">Rake Detention</a> summary (read-only)
        </div>
      </td>
      <td style={{ color: 'var(--ui-text-secondary)' }}>{unit}</td>
      <td className={es.r}>{rakeSummary.month ?? '—'}</td>
      <td className={es.r}>{rakeSummary.till ?? '—'}</td>
    </tr>
  );

  const saveLabel = totalChanges > 0 ? `Save (${totalChanges} change${totalChanges > 1 ? 's' : ''})` : 'Save';

  return (
    <EntryPage
      maxWidth={860}
      title="Key Parameters — Manual Entry"
      description={<>
        Fields on the <a href="/report">Key Parameters</a> report page with no
        file-upload source — CAPEX, Labour Productivity, Demurrage, HM Sent to PCM/Sand Pit/Dry Pit,
        RLTIFR, and Sinter Fe (a correction/override for RSP, whose own techno upload already fills it each
        month; the only source for every other plant). Avg Rake Detention Time comes from the{' '}
        <a href="/data-entry/rake-detention">Rake Detention</a> summary and is shown read-only; it can be
        entered here only for a month that has no rake detention summary.
      </>}
    >
      <ContextBar actions={<>
        {loading && <span className={es.ctxNote}>Loading…</span>}
        <SaveButton dirty={!loading && totalChanges > 0} saving={saving} onClick={handleSave}>{saveLabel}</SaveButton>
      </>}>
        <Field label="Plant" htmlFor="kp-plant">
          <select id="kp-plant" className={es.control} value={plant} onChange={(e) => setPlant(e.target.value)}>
            {PLANTS.map((p) => <option key={p}>{p}</option>)}
          </select>
        </Field>
        <Field label="Month" htmlFor="kp-month">
          <select id="kp-month" className={es.control} value={monthName} onChange={(e) => setMonthName(e.target.value)}>
            {MONTHS.map((m) => <option key={m}>{m}</option>)}
          </select>
          <select className={es.control} value={year} onChange={(e) => setYear(e.target.value)} aria-label="Year">
            {YEARS.map((y) => <option key={y}>{y}</option>)}
          </select>
        </Field>
      </ContextBar>

      <Status status={status} />

      <Section title={`Key parameters — ${plant}, ${monthName} ${year}`} sub="Edited values are highlighted until saved.">
        <table className={es.table}>
          <thead>
            <tr>
              <th>Parameter</th>
              <th>Unit</th>
              <th className={es.r}>{monthName} (Month)</th>
              <th className={es.r}>Till Month</th>
            </tr>
          </thead>
          <tbody>
            {GENERAL_PARAMS.map((p, i) => (p.key === RAKE_KEY && rakeSummary) ? rakeSummaryRow(p.label, p.unit) : renderRow(
              p.key, p.label, p.unit,
              generalMonth[p.key], generalTill[p.key],
              (e) => setGeneralMonth((v) => ({ ...v, [p.key]: e.target.value })),
              (e) => setGeneralTill((v) => ({ ...v, [p.key]: e.target.value })),
              i,
              (generalMonth[p.key] ?? '') !== (initGeneralMonth[p.key] ?? ''),
              (generalTill[p.key] ?? '') !== (initGeneralTill[p.key] ?? ''),
            ))}
            {feUnits.map((unit, j) => renderRow(
              `fe-${unit}`,
              feUnits.length > 1 ? `Fe in Sinter (${unit})` : 'Fe in Sinter',
              '%',
              feMonth[unit], feTill[unit],
              (e) => setFeMonth((v) => ({ ...v, [unit]: e.target.value })),
              (e) => setFeTill((v) => ({ ...v, [unit]: e.target.value })),
              GENERAL_PARAMS.length + j,
              (feMonth[unit] ?? '') !== (initFeMonth[unit] ?? ''),
              (feTill[unit] ?? '') !== (initFeTill[unit] ?? ''),
            ))}
          </tbody>
        </table>
      </Section>

      <div className={es.foot}>
        <SaveButton dirty={!loading && totalChanges > 0} saving={saving} onClick={handleSave}>{saveLabel}</SaveButton>
      </div>
    </EntryPage>
  );
}

export default function KeyParametersManualPage() {
  return (
    <RequireEditor>
      <KeyParametersManualInner />
    </RequireEditor>
  );
}
