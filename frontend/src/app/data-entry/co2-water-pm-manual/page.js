'use client';

import RequireEditor from '@/components/RequireEditor';
import { useState, useEffect, useCallback } from 'react';
import GlobalNavbar from '@/components/GlobalNavbar';

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

// Manual counterpart to CoalCo2ExtractRow (data-entry/techno/page.js) — that
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

function Co2WaterPmManualInner() {
  const def = getDefaultPeriod();
  const [plant, setPlant] = useState('BSP');
  const [monthName, setMonthName] = useState(def.monthName);
  const [year, setYear] = useState(def.year);
  const [monthVals, setMonthVals] = useState({});
  const [tillVals, setTillVals] = useState({});
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
    } catch (err) {
      setStatus({ type: 'error', text: err.message });
    } finally {
      setLoading(false);
    }
  }, [plant, reportMonth]);

  useEffect(() => { load(); }, [load]);

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
  const inputStyle = {
    width: '110px', padding: '6px 8px', fontSize: '11pt', textAlign: 'right',
    border: '1px solid #dadce0', borderRadius: '4px',
  };
  const cell = { padding: '8px 12px', fontSize: '10.5pt', borderBottom: '1px solid #e8eaed' };

  return (
    <div style={{ minHeight: '100vh', backgroundColor: '#ffffff' }}>
      <GlobalNavbar />
      <div style={{ maxWidth: '760px', margin: '0 auto', padding: '32px' }}>
        <h1 style={{ fontSize: '20pt', fontWeight: 900, color: '#202124', margin: 0 }}>
          CO2 / Water / PM — Manual Entry
        </h1>
        <p style={{ fontSize: '11pt', color: '#5f6368', marginTop: '6px', marginBottom: '24px' }}>
          Enter these directly when no EPI report is available yet, or to correct a value — same fields the
          Coal OMI/EPI report uploads on <a href="/data-entry/techno" style={{ color: '#1a73e8' }}>Techno Upload</a> write to.
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
              {PARAMS.map((p, i) => (
                <tr key={p.key} style={{ backgroundColor: i % 2 === 1 ? '#f8f9fa' : '#fff' }}>
                  <td style={cell}>{p.label}</td>
                  <td style={{ ...cell, color: '#5f6368' }}>{p.unit}</td>
                  <td style={{ ...cell, textAlign: 'right' }}>
                    <input
                      type="number" step="any" style={inputStyle}
                      value={monthVals[p.key] ?? ''}
                      onChange={(e) => setMonthVals((v) => ({ ...v, [p.key]: e.target.value }))}
                    />
                  </td>
                  <td style={{ ...cell, textAlign: 'right' }}>
                    <input
                      type="number" step="any" style={inputStyle}
                      value={tillVals[p.key] ?? ''}
                      onChange={(e) => setTillVals((v) => ({ ...v, [p.key]: e.target.value }))}
                    />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <button
          onClick={handleSave}
          disabled={saving || loading}
          style={{
            padding: '10px 24px', fontSize: '11pt', fontWeight: 700, border: 'none', borderRadius: '6px',
            backgroundColor: saving ? '#9aa0a6' : '#1a73e8', color: '#fff',
            cursor: saving || loading ? 'not-allowed' : 'pointer',
          }}
        >
          {saving ? 'Saving…' : 'Save'}
        </button>
      </div>
    </div>
  );
}

export default function Co2WaterPmManualPage() {
  return (
    <RequireEditor>
      <Co2WaterPmManualInner />
    </RequireEditor>
  );
}
