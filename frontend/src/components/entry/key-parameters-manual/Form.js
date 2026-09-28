'use client';

import RequireEditor from '@/components/RequireEditor';
import { useState, useEffect, useCallback } from 'react';
import GlobalNavbar from '@/components/GlobalNavbar';

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

// Count of param/unit keys whose current value differs from the value
// last loaded/saved — drives both the changed-cell highlight and the
// "Save (N changes)" button label, same convention as techno-manual/
// page.js's countChanges().
function countChanges(generalMonth, generalTill, initGeneralMonth, initGeneralTill,
                       feMonth, feTill, initFeMonth, initFeTill, feUnits) {
  let n = 0;
  for (const { key } of GENERAL_PARAMS) {
    if ((generalMonth[key] ?? '') !== (initGeneralMonth[key] ?? '')) n++;
    if ((generalTill[key] ?? '') !== (initGeneralTill[key] ?? '')) n++;
  }
  for (const unit of feUnits) {
    if ((feMonth[unit] ?? '') !== (initFeMonth[unit] ?? '')) n++;
    if ((feTill[unit] ?? '') !== (initFeTill[unit] ?? '')) n++;
  }
  return n;
}

function ChangedInput({ value, onChange, changed, disabled }) {
  return (
    <input
      type="number" step="any" disabled={disabled}
      style={{
        width: '110px', padding: '6px 8px', fontSize: '11pt', textAlign: 'right',
        border: `1px solid ${changed ? '#f59e0b' : '#dadce0'}`, borderRadius: '4px',
        background: disabled ? '#f9fafb' : changed ? '#fffbeb' : '#fff',
      }}
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
    } catch (err) {
      setStatus({ type: 'error', text: err.message });
    } finally {
      setLoading(false);
    }
  }, [plant, reportMonth]);

  useEffect(() => { load(); }, [load]);

  const totalChanges = countChanges(
    generalMonth, generalTill, initGeneralMonth, initGeneralTill,
    feMonth, feTill, initFeMonth, initFeTill, feUnits,
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

  const selStyle = {
    padding: '8px 12px', fontSize: '11pt', border: '1px solid #dadce0',
    borderRadius: '6px', backgroundColor: '#ffffff', color: '#202124', cursor: 'pointer',
  };
  const cell = { padding: '8px 12px', fontSize: '10.5pt', borderBottom: '1px solid #e8eaed' };

  const renderRow = (key, label, unit, monthVal, tillVal, onMonth, onTill, i, monthChanged, tillChanged) => (
    <tr key={key} style={{ backgroundColor: i % 2 === 1 ? '#f8f9fa' : '#fff' }}>
      <td style={cell}>{label}</td>
      <td style={{ ...cell, color: '#5f6368' }}>{unit}</td>
      <td style={{ ...cell, textAlign: 'right' }}>
        <ChangedInput value={monthVal ?? ''} disabled={saving} changed={monthChanged} onChange={onMonth} />
      </td>
      <td style={{ ...cell, textAlign: 'right' }}>
        <ChangedInput value={tillVal ?? ''} disabled={saving} changed={tillChanged} onChange={onTill} />
      </td>
    </tr>
  );

  return (
    // height:100vh + flex column, with the content area its own
    // flex:1/overflow:auto scroll region below the sticky GlobalNavbar —
    // same layout techno-manual/page.js uses, rather than an unbounded
    // minHeight:100vh page that just keeps growing.
    <div style={{ height: '100vh', display: 'flex', flexDirection: 'column', backgroundColor: '#ffffff' }}>
      <GlobalNavbar />
      <div style={{ flex: 1, overflow: 'auto', maxWidth: '760px', margin: '0 auto', padding: '32px', width: '100%', boxSizing: 'border-box' }}>
        <h1 style={{ fontSize: '20pt', fontWeight: 900, color: '#202124', margin: 0 }}>
          Key Parameters — Manual Entry
        </h1>
        <p style={{ fontSize: '11pt', color: '#5f6368', marginTop: '6px', marginBottom: '24px' }}>
          Fields on the <a href="/report" style={{ color: '#1a73e8' }}>Key Parameters</a> report page with no
          file-upload source — CAPEX, Labour Productivity, Avg Rake Detention Time, Demurrage, HM Sent to
          PCM/Sand Pit/Dry Pit, RLTIFR, and Sinter Fe (a correction/override for RSP, whose own techno upload
          already fills it each month; the only source for every other plant).
        </p>

        <div style={{
          display: 'flex', alignItems: 'center', gap: '16px', flexWrap: 'wrap',
          padding: '16px 20px', border: '1px solid #dadce0', borderRadius: '8px',
          backgroundColor: '#f8f9fa', marginBottom: '24px',
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <label style={{ fontSize: '11pt', fontWeight: 600 }}>Plant</label>
            <select value={plant} onChange={(e) => setPlant(e.target.value)} style={selStyle}>
              {PLANTS.map((p) => <option key={p}>{p}</option>)}
            </select>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <label style={{ fontSize: '11pt', fontWeight: 600 }}>Month</label>
            <select value={monthName} onChange={(e) => setMonthName(e.target.value)} style={selStyle}>
              {MONTHS.map((m) => <option key={m}>{m}</option>)}
            </select>
            <select value={year} onChange={(e) => setYear(e.target.value)} style={selStyle}>
              {YEARS.map((y) => <option key={y}>{y}</option>)}
            </select>
          </div>
          {loading && <span style={{ fontSize: '10.5pt', color: '#5f6368' }}>Loading…</span>}
        </div>

        {status && (
          <p style={{
            marginBottom: '16px', fontSize: '11pt',
            color: status.type === 'error' ? '#d93025' : '#188038',
          }}>
            {status.text}
          </p>
        )}

        <div style={{ border: '1px solid #dadce0', borderRadius: '8px', overflow: 'hidden', marginBottom: '20px' }}>
          <table style={{ borderCollapse: 'collapse', width: '100%' }}>
            <thead>
              <tr style={{ backgroundColor: '#e8f0fe' }}>
                <th style={{ ...cell, textAlign: 'left', fontWeight: 700, color: '#174ea6' }}>Parameter</th>
                <th style={{ ...cell, textAlign: 'left', fontWeight: 700, color: '#174ea6' }}>Unit</th>
                <th style={{ ...cell, textAlign: 'right', fontWeight: 700, color: '#174ea6' }}>{monthName} (Month)</th>
                <th style={{ ...cell, textAlign: 'right', fontWeight: 700, color: '#174ea6' }}>Till Month</th>
              </tr>
            </thead>
            <tbody>
              {GENERAL_PARAMS.map((p, i) => renderRow(
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
        </div>

        <button
          onClick={handleSave}
          disabled={saving || loading || totalChanges === 0}
          style={{
            padding: '10px 24px', fontSize: '11pt', fontWeight: 700, border: 'none', borderRadius: '6px',
            backgroundColor: saving ? '#9aa0a6' : totalChanges === 0 ? '#9aa0a6' : '#1a73e8', color: '#fff',
            cursor: saving || loading || totalChanges === 0 ? 'not-allowed' : 'pointer',
          }}
        >
          {saving ? 'Saving…' : totalChanges > 0 ? `Save (${totalChanges} change${totalChanges > 1 ? 's' : ''})` : 'Save'}
        </button>
      </div>
    </div>
  );
}

export default function KeyParametersManualPage() {
  return (
    <RequireEditor>
      <KeyParametersManualInner />
    </RequireEditor>
  );
}
