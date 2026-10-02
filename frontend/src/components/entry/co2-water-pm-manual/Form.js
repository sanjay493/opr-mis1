'use client';

import RequireEditor from '@/components/RequireEditor';
import { useState, useEffect, useCallback } from 'react';
import { EntryPage, ContextBar, Field, Status, Section, SaveButton, cellClass, entryStyles as es } from '../EntryUI';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || '';
// SAIL included — techno_data plant="SAIL" unit="General" already exists
// (written by the Coal OMI extractor for the 4 coal-consumption keys); a
// manually-entered SAIL value here takes precedence over the report pages'
// own computed crude-steel-weighted average of the 5 plants (page_techno.py
// BF_SAIL_SPECS/_bf_sail_v — that computation is a fallback used only when
// no stored SAIL value exists, same treatment as Specific Energy
// Consumption). /api/techno/manual/entry+save are already plant-agnostic,
// so no backend change was needed for this.
const PLANTS = ['BSP', 'DSP', 'RSP', 'BSL', 'ISP', 'SAIL'];

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

// Manual counterpart to CoalCo2ExtractRow (data-entry/uploads/page.js) — that
// component only ever fills these 3 keys via an uploaded EPI report; this
// page lets someone type the figures straight in when no report is
// available yet (or to correct one), using the same techno_data keys/unit
// so both paths stay interchangeable. Reuses the existing generic Techno
// Manual Entry endpoints verbatim (GET .../entry, POST .../save) — no new
// backend code.
const PARAMS = [
  { key: 'sp_co2_emission', label: 'Sp. CO2 Emission', unit: 'T/tcs' },
  { key: 'sp_water_consumption', label: 'Sp. Water Consumption', unit: 'm³/tcs' },
  { key: 'sp_pm_emission', label: 'Sp. PM Emission', unit: 'kg/tcs' },
];
const GENERAL_UNIT = 'General';

// Count of param keys whose current value differs from the value last
// loaded/saved — drives both the changed-cell highlight and the "Save (N
// changes)" button label, same convention as techno-manual/page.js's
// countChanges().
function countChanges(monthVals, tillVals, initMonthVals, initTillVals) {
  let n = 0;
  for (const { key } of PARAMS) {
    if ((monthVals[key] ?? '') !== (initMonthVals[key] ?? '')) n++;
    if ((tillVals[key] ?? '') !== (initTillVals[key] ?? '')) n++;
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

function Co2WaterPmManualInner() {
  const def = getDefaultPeriod();
  const [plant, setPlant] = useState('BSP');
  const [monthName, setMonthName] = useState(def.monthName);
  const [year, setYear] = useState(def.year);
  const [monthVals, setMonthVals] = useState({});
  const [tillVals, setTillVals] = useState({});
  const [initMonthVals, setInitMonthVals] = useState({});
  const [initTillVals, setInitTillVals] = useState({});
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [status, setStatus] = useState(null);

  const reportMonth = `${year}-${MONTH_NUM[monthName]}`;

  const load = useCallback(async () => {
    setLoading(true);
    setStatus(null);
    try {
      const res = await fetch(`${API_BASE_URL}/api/techno/manual/entry?plant=${plant}&report_month=${reportMonth}`);
      const json = await res.json();
      if (!res.ok) throw new Error(json.detail || 'Load failed');
      const general = json.units?.[GENERAL_UNIT] || {};
      setMonthVals({ ...general.month });
      setTillVals({ ...general.till_month });
      setInitMonthVals({ ...general.month });
      setInitTillVals({ ...general.till_month });
    } catch (err) {
      setStatus({ type: 'error', text: err.message });
    } finally {
      setLoading(false);
    }
  }, [plant, reportMonth]);

  useEffect(() => { load(); }, [load]);

  const totalChanges = countChanges(monthVals, tillVals, initMonthVals, initTillVals);

  const handleSave = async () => {
    setSaving(true);
    setStatus(null);
    try {
      const month_data = {};
      const till_month_data = {};
      for (const { key } of PARAMS) {
        month_data[key] = monthVals[key] === '' || monthVals[key] === undefined ? null : Number(monthVals[key]);
        till_month_data[key] = tillVals[key] === '' || tillVals[key] === undefined ? null : Number(tillVals[key]);
      }
      const res = await fetch(`${API_BASE_URL}/api/techno/manual/save`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ plant, report_month: reportMonth, unit: GENERAL_UNIT, month_data, till_month_data }),
      });
      const json = await res.json();
      if (!res.ok) throw new Error(json.detail || 'Save failed');
      // Resets the changed-highlight/count baseline to what was just saved,
      // same as techno-manual/page.js's saveAll().
      setInitMonthVals({ ...monthVals });
      setInitTillVals({ ...tillVals });
      setStatus({ type: 'success', text: `✓ Saved for ${plant} ${reportMonth}` });
    } catch (err) {
      setStatus({ type: 'error', text: err.message });
    } finally {
      setSaving(false);
    }
  };

  const saveLabel = totalChanges > 0 ? `Save (${totalChanges} change${totalChanges > 1 ? 's' : ''})` : 'Save';

  return (
    <EntryPage
      maxWidth={860}
      title="CO2 / Water / PM — Manual Entry"
      description={<>
        Enter these directly when no EPI report is available yet, or to correct a value — same fields the
        Coal OMI/EPI report uploads on <a href="/data-entry/techno">Techno Upload</a> write to.
      </>}
    >
      <ContextBar actions={<>
        {loading && <span className={es.ctxNote}>Loading…</span>}
        <SaveButton dirty={!loading && totalChanges > 0} saving={saving} onClick={handleSave}>{saveLabel}</SaveButton>
      </>}>
        <Field label="Plant" htmlFor="co2-plant">
          <select id="co2-plant" className={es.control} value={plant} onChange={(e) => setPlant(e.target.value)}>
            {PLANTS.map((p) => <option key={p}>{p}</option>)}
          </select>
        </Field>
        <Field label="Month" htmlFor="co2-month">
          <select id="co2-month" className={es.control} value={monthName} onChange={(e) => setMonthName(e.target.value)}>
            {MONTHS.map((m) => <option key={m}>{m}</option>)}
          </select>
          <select className={es.control} value={year} onChange={(e) => setYear(e.target.value)} aria-label="Year">
            {YEARS.map((y) => <option key={y}>{y}</option>)}
          </select>
        </Field>
      </ContextBar>

      <Status status={status} />

      <Section title={`CO2 / Water / PM — ${plant}, ${monthName} ${year}`} sub="Edited values are highlighted until saved.">
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
            {PARAMS.map((p) => (
              <tr key={p.key}>
                <td className={es.itemCell}>{p.label}</td>
                <td style={{ color: 'var(--ui-text-secondary)' }}>{p.unit}</td>
                <td className={es.r}>
                  <ChangedInput
                    value={monthVals[p.key] ?? ''}
                    disabled={saving}
                    label={`${p.label} month`}
                    changed={(monthVals[p.key] ?? '') !== (initMonthVals[p.key] ?? '')}
                    onChange={(e) => setMonthVals((v) => ({ ...v, [p.key]: e.target.value }))}
                  />
                </td>
                <td className={es.r}>
                  <ChangedInput
                    value={tillVals[p.key] ?? ''}
                    disabled={saving}
                    label={`${p.label} till month`}
                    changed={(tillVals[p.key] ?? '') !== (initTillVals[p.key] ?? '')}
                    onChange={(e) => setTillVals((v) => ({ ...v, [p.key]: e.target.value }))}
                  />
                </td>
              </tr>
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

export default function Co2WaterPmManualPage() {
  return (
    <RequireEditor>
      <Co2WaterPmManualInner />
    </RequireEditor>
  );
}
