'use client';

import RequireEditor from '@/components/RequireEditor';
import { useState, useEffect, useCallback } from 'react';
import GlobalNavbar from '@/components/GlobalNavbar';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || '';

// The 3 SAIL BFs the "Large BFs" annexure report page (page 3.6,
// page_bf_large_annexure.py) compares — same plant/unit pairs as
// bf_benchmark_registry.py's SAIL_BFS, hardcoded here too rather than
// fetched, since this page only ever needs these 3 (not admin-addable,
// unlike the non-SAIL side of that other feature).
const SAIL_BFS = [
  { plant: 'BSP', unit: 'BF-8', label: 'BSP BF-8' },
  { plant: 'RSP', unit: 'BF-5', label: 'RSP BF-5' },
  { plant: 'ISP', unit: 'BF-5', label: 'ISP BF-5' },
];

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

// The "Large BFs" annexure report page's rows with no extractor behind them
// for any SAIL plant — see bf_benchmark_registry.py's BF_BENCHMARK_PARAMS
// (added there so the existing /reports/bf-benchmark comparison tool and
// its non-SAIL entry grid pick these up too) and page_bf_large_annexure.py's
// module docstring for the full list/reasoning. Saved into techno_data
// under the SAME per-BF unit (BF-8/BF-5) the report page reads from, via
// the existing generic Techno Manual Entry endpoints — so a value entered
// here also shows up in that form's own BF-8/BF-5 tabs, and vice versa,
// both being the same techno_data cell.
const PARAMS = [
  { key: 'top_pressure', label: 'Top Pressure', unit: 'kg/cm²' },
  { key: 'lump_ore_fe', label: 'Lump Ore Fe', unit: '%' },
  { key: 'pellet_fe', label: 'Pellet Fe', unit: '%' },
  // Avg. Burden Fe is NOT here — the report page now computes it live from
  // Sinter/Pellet/Lump in Burden % × their own Fe assay above, per direct
  // instruction (page_bf_large_annexure.py's _avg_burden_fe). It's no
  // longer read from techno_data at all, so a manual-entry field for it
  // here would silently do nothing.
  { key: 'steam_rate_hr', label: 'Steam Rate', unit: 'T/Hr' },
  { key: 'slag_mgo', label: 'Slag MgO', unit: '%' },
  { key: 'slag_al2o3', label: 'Slag Al2O3', unit: '%' },
  { key: 'slag_b2', label: 'Slag B2', unit: 'Ratio' },
  { key: 'eta_co', label: 'Eta CO', unit: '%' },
  { key: 'heat_load_flux', label: 'Heat Load/Flux', unit: 'MJ/hr' },
  { key: 'tapping_duration', label: 'Tapping Duration', unit: 'Hrs' },
  // 'furnace_availability', not the registry's shorter 'availability' —
  // must match techno-manual's own BF template key (and the literal key
  // ISP's own monthly extractor already writes under), or the same
  // divergence bug the Pellet Fe/Lump Ore Fe fix addressed reappears here:
  // a value entered on one form silently invisible on the other.
  // page_bf_large_annexure.py's KEY_ALIASES already resolves either name
  // for the report itself; this only fixes the two ENTRY FORMS agreeing.
  { key: 'furnace_availability', label: 'Fce Availability', unit: '%' },
  { key: 'utilisation', label: 'Fce Utilisation', unit: '%' },
];

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

function BfLargeManualInner() {
  const def = getDefaultPeriod();
  const [bfKey, setBfKey] = useState('BSP');
  const [monthName, setMonthName] = useState(def.monthName);
  const [year, setYear] = useState(def.year);
  const [monthVals, setMonthVals] = useState({});
  const [tillVals, setTillVals] = useState({});
  const [initMonthVals, setInitMonthVals] = useState({});
  const [initTillVals, setInitTillVals] = useState({});
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [status, setStatus] = useState(null);

  const bf = SAIL_BFS.find((b) => b.plant === bfKey) || SAIL_BFS[0];
  const reportMonth = `${year}-${MONTH_NUM[monthName]}`;

  const load = useCallback(async () => {
    setLoading(true);
    setStatus(null);
    try {
      const res = await fetch(`${API_BASE_URL}/api/techno/manual/entry?plant=${bf.plant}&report_month=${reportMonth}`);
      const json = await res.json();
      if (!res.ok) throw new Error(json.detail || 'Load failed');
      const unitData = json.units?.[bf.unit] || {};
      setMonthVals({ ...unitData.month });
      setTillVals({ ...unitData.till_month });
      setInitMonthVals({ ...unitData.month });
      setInitTillVals({ ...unitData.till_month });
    } catch (err) {
      setStatus({ type: 'error', text: err.message });
    } finally {
      setLoading(false);
    }
  }, [bf.plant, bf.unit, reportMonth]);

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
        body: JSON.stringify({ plant: bf.plant, report_month: reportMonth, unit: bf.unit, month_data, till_month_data }),
      });
      const json = await res.json();
      if (!res.ok) throw new Error(json.detail || 'Save failed');
      // Resets the changed-highlight/count baseline to what was just saved,
      // same as techno-manual/page.js's saveAll().
      setInitMonthVals({ ...monthVals });
      setInitTillVals({ ...tillVals });
      setStatus({ type: 'success', text: `✓ Saved for ${bf.label} — ${reportMonth}` });
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

  return (
    // height:100vh + flex column, with the content area its own
    // flex:1/overflow:auto scroll region below the sticky GlobalNavbar —
    // same layout techno-manual/page.js uses, rather than an unbounded
    // minHeight:100vh page that just keeps growing.
    <div style={{ height: '100vh', display: 'flex', flexDirection: 'column', backgroundColor: '#ffffff' }}>
      <GlobalNavbar />
      <div style={{ flex: 1, overflow: 'auto', maxWidth: '760px', margin: '0 auto', padding: '32px', width: '100%', boxSizing: 'border-box' }}>
        <h1 style={{ fontSize: '20pt', fontWeight: 900, color: '#202124', margin: 0 }}>
          Large BFs — Manual Entry
        </h1>
        <p style={{ fontSize: '11pt', color: '#5f6368', marginTop: '6px', marginBottom: '24px' }}>
          Fields on the <a href="/report" style={{ color: '#1a73e8' }}>Large BFs</a> benchmark report page with no
          extractor for any SAIL plant yet. Saves into the same techno_data cell the general{' '}
          <a href="/data-entry/techno-manual" style={{ color: '#1a73e8' }}>Techno Manual Entry</a> form's BF tabs
          use, so either form shows the same value.
        </p>

        <div style={{
          display: 'flex', alignItems: 'center', gap: '16px', flexWrap: 'wrap',
          padding: '16px 20px', border: '1px solid #dadce0', borderRadius: '8px',
          backgroundColor: '#f8f9fa', marginBottom: '24px',
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <label style={{ fontSize: '11pt', fontWeight: 600 }}>BF</label>
            <select value={bfKey} onChange={(e) => setBfKey(e.target.value)} style={selStyle}>
              {SAIL_BFS.map((b) => <option key={b.plant} value={b.plant}>{b.label}</option>)}
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
                    <ChangedInput
                      value={monthVals[p.key] ?? ''}
                      disabled={saving}
                      changed={(monthVals[p.key] ?? '') !== (initMonthVals[p.key] ?? '')}
                      onChange={(e) => setMonthVals((v) => ({ ...v, [p.key]: e.target.value }))}
                    />
                  </td>
                  <td style={{ ...cell, textAlign: 'right' }}>
                    <ChangedInput
                      value={tillVals[p.key] ?? ''}
                      disabled={saving}
                      changed={(tillVals[p.key] ?? '') !== (initTillVals[p.key] ?? '')}
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

export default function BfLargeManualPage() {
  return (
    <RequireEditor>
      <BfLargeManualInner />
    </RequireEditor>
  );
}
