'use client';

import RequireEditor from '@/components/RequireEditor';

import React, { useState, useCallback, useEffect, useMemo } from 'react';
import GlobalNavbar from '@/components/GlobalNavbar';

const API = process.env.NEXT_PUBLIC_API_URL || '';

const PLANTS = [
  { code: 'BSP', label: 'Bhilai Steel Plant' },
  { code: 'DSP', label: 'Durgapur Steel Plant' },
  { code: 'RSP', label: 'Rourkela Steel Plant' },
  { code: 'BSL', label: 'Bokaro Steel Plant' },
  { code: 'ISP', label: 'IISCO Steel Plant' },
];

const UNIT_TYPES = [
  { code: 'BF', label: 'Blast Furnace' },
  { code: 'SMS', label: 'SMS (Converter/Caster)' },
  { code: 'MILL', label: 'Rolling Mill' },
  { code: 'COKE', label: 'Coke Oven' },
  { code: 'SINTER', label: 'Sinter Plant' },
  { code: 'GENERAL', label: 'Plant-Level General' },
];

const S = {
  H:  { padding: '10px 8px', textAlign: 'center', fontWeight: 700, color: '#5f6368',
        borderBottom: '1px solid #dadce0', fontSize: 13, backgroundColor: '#f8f9fa',
        whiteSpace: 'nowrap' },
  TD: { padding: '7px 8px', borderBottom: '1px solid #f0f4f8', fontSize: 14, verticalAlign: 'middle' },
  SEL: { padding: '5px 6px', fontSize: 12.5, border: '1px solid #dadce0', borderRadius: 4, width: '100%' },
  DATE: { padding: '5px 6px', fontSize: 12.5, border: '1px solid #dadce0', borderRadius: 4, width: 122 },
};

function Notice({ type, text }) {
  if (!text) return null;
  const ok = type === 'success';
  return (
    <div style={{
      padding: '10px 16px', borderRadius: 6, marginBottom: 14, fontSize: 14,
      background: ok ? '#f0fdf4' : '#fef2f2',
      color: ok ? '#166534' : '#991b1b',
      border: `1px solid ${ok ? '#86efac' : '#fca5a5'}`,
    }}>
      {text}
    </div>
  );
}

// Client-side suggestion only — schedule_days text ("9 days", "1 month",
// "3+3 (revival)") is never authoritative; the user must confirm/edit the
// numeric value before it feeds the overrun-vs-plan analysis.
function suggestPlannedDays(scheduleDays) {
  const m = /^\s*(\d+)\s*day/i.exec(scheduleDays || '');
  return m ? m[1] : '';
}

function EntryRow({ row, plant, units, onSaved }) {
  const [unitType, setUnitType]   = useState(row.unit_type || '');
  const [unitName, setUnitName]   = useState(row.unit_name || '');
  const [smsSubtag, setSmsSubtag] = useState(row.sms_subtag || '');
  const [actualStart, setActualStart] = useState(row.actual_start || '');
  const [actualEnd, setActualEnd]     = useState(row.actual_end || '');
  const [ongoing, setOngoing]         = useState(!!row.actual_ongoing);
  const [plannedDays, setPlannedDays] = useState(
    row.planned_days != null ? String(row.planned_days) : suggestPlannedDays(row.schedule_days)
  );
  const [actualPreview, setActualPreview] = useState(row.actual || '');
  const [saving, setSaving] = useState(false);
  const [msg, setMsg]       = useState(null);

  const unitOptions = useMemo(
    () => units.filter(u => u.unit_type === unitType && !u.is_shop),
    [units, unitType]
  );

  const handleUnitTypeChange = (val) => {
    setUnitType(val);
    setUnitName('');
    if (val !== 'SMS') setSmsSubtag('');
  };

  const handleSave = async () => {
    if (unitType === 'SMS' && !smsSubtag) {
      setMsg('err:Converter or Caster must be chosen for an SMS unit');
      return;
    }
    if (!ongoing && actualStart && actualEnd && actualEnd < actualStart) {
      setMsg('err:End date cannot be before start date');
      return;
    }
    setSaving(true);
    setMsg(null);
    try {
      const res = await fetch(`${API}/api/capital-repair-entry`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          id: row.id,
          unit_type: unitType || null,
          unit_name: unitName || null,
          sms_subtag: unitType === 'SMS' ? (smsSubtag || null) : null,
          actual_start: actualStart || null,
          actual_end: ongoing ? null : (actualEnd || null),
          actual_ongoing: ongoing,
          planned_days: plannedDays === '' ? null : plannedDays,
        }),
      });
      if (!res.ok) throw new Error(await res.text());
      const data = await res.json();
      setActualPreview(data.actual || '');
      setMsg('saved');
      onSaved({
        ...row, unit_type: unitType, unit_name: unitName, sms_subtag: unitType === 'SMS' ? smsSubtag : null,
        actual_start: actualStart, actual_end: ongoing ? null : actualEnd, actual_ongoing: ongoing,
        planned_days: plannedDays === '' ? null : Number(plannedDays), actual: data.actual,
      });
      setTimeout(() => setMsg(null), 1500);
    } catch (err) {
      setMsg('err:' + err.message);
    } finally {
      setSaving(false);
    }
  };

  const rowBg = msg === 'saved' ? '#f0fdf4' : msg?.startsWith('err') ? '#fef2f2' : '#fff';

  return (
    <tr style={{ backgroundColor: rowBg }}>
      <td style={{ ...S.TD, fontWeight: 600 }}>{row.shop}</td>
      <td style={{ ...S.TD, textAlign: 'center' }}>{row.equipment}</td>
      <td style={S.TD}>{row.activity}</td>
      <td style={{ ...S.TD, textAlign: 'center' }}>{row.schedule_days}</td>
      <td style={{ ...S.TD, textAlign: 'center' }}>{row.period}</td>

      <td style={{ ...S.TD, minWidth: 190 }}>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
          <select style={S.SEL} value={unitType} onChange={e => handleUnitTypeChange(e.target.value)}>
            <option value="">— unit type —</option>
            {UNIT_TYPES.map(t => <option key={t.code} value={t.code}>{t.label}</option>)}
          </select>
          {unitType && (
            <select style={S.SEL} value={unitName} onChange={e => setUnitName(e.target.value)}>
              <option value="">— unit —</option>
              {unitOptions.map(u => <option key={u.unit_name} value={u.unit_name}>{u.unit_name}</option>)}
            </select>
          )}
          {unitType === 'SMS' && (
            <select style={S.SEL} value={smsSubtag} onChange={e => setSmsSubtag(e.target.value)}>
              <option value="">— converter/caster —</option>
              <option value="CONVERTER">Converter</option>
              <option value="CASTER">Caster</option>
            </select>
          )}
        </div>
      </td>

      <td style={{ ...S.TD, textAlign: 'center', width: 70 }}>
        <input type="number" min="0" style={{ ...S.DATE, width: 60, textAlign: 'center' }}
          value={plannedDays} onChange={e => setPlannedDays(e.target.value)} placeholder="days" />
      </td>

      <td style={{ ...S.TD, minWidth: 280 }}>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
          <div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
            <input type="date" style={S.DATE} value={actualStart}
              onChange={e => setActualStart(e.target.value)} />
            <span style={{ color: '#9aa0a6' }}>–</span>
            <input type="date" style={S.DATE} value={actualEnd} disabled={ongoing}
              onChange={e => setActualEnd(e.target.value)} />
          </div>
          <label style={{ fontSize: 12, color: '#5f6368', display: 'flex', alignItems: 'center', gap: 4 }}>
            <input type="checkbox" checked={ongoing}
              onChange={e => { setOngoing(e.target.checked); if (e.target.checked) setActualEnd(''); }} />
            Ongoing (not yet completed)
          </label>
          {actualPreview && (
            <span style={{ fontSize: 11.5, color: '#5f6368' }}>will print as: <strong>{actualPreview}</strong></span>
          )}
        </div>
      </td>

      <td style={{ ...S.TD, textAlign: 'center' }}>
        {msg === 'saved'
          ? <span style={{ color: '#059669', fontWeight: 700, fontSize: 14 }}>✓</span>
          : msg?.startsWith('err')
          ? <span style={{ color: '#dc2626', fontSize: 12 }} title={msg.slice(4)}>✗ {msg.slice(4)}</span>
          : (
          <button onClick={handleSave} disabled={saving}
            style={{ padding: '5px 14px', border: 'none', borderRadius: 4,
                     backgroundColor: '#10b981', color: '#fff', fontSize: 13,
                     cursor: 'pointer', fontWeight: 600 }}>
            {saving ? '…' : 'Save'}
          </button>
        )}
      </td>
    </tr>
  );
}

function CapitalRepairDataEntryPageInner() {
  const [plant, setPlant]     = useState('BSP');
  const [fy, setFy]           = useState('2026-27');
  const [rows, setRows]       = useState([]);
  const [units, setUnits]     = useState([]);
  const [loading, setLoading] = useState(false);
  const [status, setStatus]   = useState(null);
  const [loaded, setLoaded]   = useState(false);

  useEffect(() => {
    fetch(`${API}/api/plant-units?plant_code=${encodeURIComponent(plant)}`)
      .then(res => res.json())
      .then(data => setUnits(data.units || []))
      .catch(() => setUnits([]));
  }, [plant]);

  const load = useCallback(async () => {
    setLoading(true);
    setStatus(null);
    setLoaded(false);
    try {
      const res = await fetch(`${API}/api/capital-repair?plant=${encodeURIComponent(plant)}&fy=${encodeURIComponent(fy)}`);
      if (!res.ok) throw new Error(await res.text());
      const data = await res.json();
      setRows(data.rows);
      setLoaded(true);
    } catch (err) {
      setStatus({ type: 'error', text: `Load failed: ${err.message}` });
    } finally {
      setLoading(false);
    }
  }, [plant, fy]);

  const handleRowSaved = (idx, updated) => setRows(prev => prev.map((r, i) => i === idx ? updated : r));

  const plantLabel = PLANTS.find(p => p.code === plant)?.label || plant;

  return (
    <div style={{ height: '100vh', display: 'flex', flexDirection: 'column', background: '#ffffff' }}>
      <GlobalNavbar />

      <div style={{ flex: 1, overflow: 'auto', maxWidth: 1600, margin: '0 auto', padding: '22px 20px', width: '100%', boxSizing: 'border-box' }}>

        <div style={{ marginBottom: 18 }}>
          <h2 style={{ fontSize: '1.6rem', fontWeight: 700, color: '#202124', margin: '0 0 4px' }}>
            Capital Repair — Data Entry
          </h2>
          <span style={{ fontSize: 13, color: '#5f6368' }}>
            Update Unit, Planned Days and Actual dates as Capital Repair jobs execute — these feed the
            Production Loss Analysis report. Shop, Equipment, Activity, Schedule and Period are the fixed
            yearly plan and are not editable here.
          </span>
        </div>

        <div style={{
          display: 'flex', gap: 10, alignItems: 'center', flexWrap: 'wrap',
          marginBottom: 18, background: '#fff', border: '1px solid #dadce0',
          borderRadius: 8, padding: '14px 18px',
        }}>
          <label style={{ fontSize: 13, fontWeight: 600, color: '#374151' }}>Plant</label>
          <select value={plant} onChange={e => { setPlant(e.target.value); setLoaded(false); setRows([]); }}
            style={{ padding: '7px 10px', fontSize: 14, border: '1px solid #d1d5db', borderRadius: 4 }}>
            {PLANTS.map(p => <option key={p.code} value={p.code}>{p.code} — {p.label}</option>)}
          </select>

          <label style={{ fontSize: 13, fontWeight: 600, color: '#374151' }}>FY</label>
          <input type="text" value={fy} onChange={e => { setFy(e.target.value); setLoaded(false); setRows([]); }}
            placeholder="2026-27"
            style={{ width: 90, padding: '7px 10px', fontSize: 14, border: '1px solid #d1d5db', borderRadius: 4 }} />

          <button onClick={load} disabled={loading} style={{
            padding: '7px 20px', fontSize: 14, fontWeight: 600,
            background: '#1a73e8', color: '#fff', border: 'none', borderRadius: 4,
            cursor: loading ? 'not-allowed' : 'pointer',
          }}>
            {loading ? 'Loading…' : 'Load Records'}
          </button>

          <span style={{ marginLeft: 'auto', fontSize: 13, color: '#5f6368' }}>
            {plantLabel}{loading && ' ⟳'}
          </span>
        </div>

        <Notice type={status?.type} text={status?.text} />

        {!loaded && !loading && (
          <div style={{
            padding: 48, textAlign: 'center', backgroundColor: '#fff',
            border: '2px dashed #dadce0', borderRadius: 8, color: '#5f6368',
          }}>
            <p style={{ margin: 0, fontSize: 14 }}>
              Select a plant and FY, then click <strong>Load Records</strong>.
            </p>
          </div>
        )}

        {loading && (
          <div style={{ padding: 48, textAlign: 'center', color: '#5f6368', fontSize: 14 }}>
            Loading…
          </div>
        )}

        {loaded && (
          <div style={{ backgroundColor: '#fff', border: '1px solid #dadce0', borderRadius: 8, overflow: 'hidden' }}>
            <div style={{
              padding: '14px 18px', backgroundColor: '#f8f9fa', color: '#202124',
              display: 'flex', justifyContent: 'space-between', alignItems: 'center',
            }}>
              <span style={{ fontWeight: 700, fontSize: 14 }}>
                Capital Repair — {plantLabel} (FY {fy})
              </span>
              <span style={{ fontSize: 13, color: '#5f6368' }}>
                {rows.length} row{rows.length !== 1 ? 's' : ''}
              </span>
            </div>

            <div style={{ overflowX: 'auto', maxHeight: 'calc(100vh - 420px)', overflowY: 'auto' }}>
              <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 14 }}>
                <thead>
                  <tr style={{ position: 'sticky', top: 0, zIndex: 1 }}>
                    <th style={{ ...S.H, textAlign: 'left', width: 130 }}>Shop</th>
                    <th style={S.H}>Equipment</th>
                    <th style={{ ...S.H, textAlign: 'left' }}>Activity</th>
                    <th style={S.H}>Schedule (days)</th>
                    <th style={S.H}>Period</th>
                    <th style={S.H}>Unit (for analysis)</th>
                    <th style={S.H}>Planned Days</th>
                    <th style={S.H}>Actual (Start – End)</th>
                    <th style={S.H}>Save</th>
                  </tr>
                </thead>
                <tbody>
                  {rows.length === 0 && (
                    <tr>
                      <td colSpan={9} style={{ padding: 24, textAlign: 'center', color: '#5f6368', fontSize: 14 }}>
                        No Capital Repair rows for {plantLabel}, FY {fy}.
                      </td>
                    </tr>
                  )}
                  {rows.map((row, idx) => (
                    <EntryRow
                      key={row.id}
                      row={row}
                      plant={plant}
                      units={units}
                      onSaved={updated => handleRowSaved(idx, updated)}
                    />
                  ))}
                </tbody>
              </table>
            </div>

            <div style={{
              padding: '12px 18px', backgroundColor: '#f8f9fa', borderTop: '1px solid #dadce0',
            }}>
              <span style={{ fontSize: 13, color: '#5f6368' }}>
                Save each row individually. Unit/Planned Days only need to be set once per row (they persist);
                update the Actual dates and Ongoing checkbox as the repair progresses.
              </span>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

export default function CapitalRepairDataEntryPage() {
  return (
    <RequireEditor>
      <CapitalRepairDataEntryPageInner />
    </RequireEditor>
  );
}
