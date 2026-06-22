'use client';

import React, { useState, useCallback, useEffect, useMemo } from 'react';
import Link from 'next/link';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || '';

const MONTHS = [
  'April', 'May', 'June', 'July', 'August', 'September',
  'October', 'November', 'December', 'January', 'February', 'March',
];
const MONTH_NUM = {
  January: '01', February: '02', March: '03', April: '04',
  May: '05', June: '06', July: '07', August: '08',
  September: '09', October: '10', November: '11', December: '12',
};
const YEARS = Array.from({ length: 8 }, (_, i) => (2022 + i).toString());

// group_code → display label
const GROUP_LABELS = {
  IRON_MAKING:  'Iron Making — Cross-plant BF',
  SMS:          'Steel Making — Cross-plant SMS',
  COKE_SINTER:  'Coke & Sinter — Cross-plant',
  MAJOR:        'Major — Cross-plant',
  MILL_BSP:     'Mill — BSP',
  MILL_DSP:     'Mill — DSP',
  MILL_RSP:     'Mill — RSP',
  MILL_BSL:     'Mill — BSL',
  MILL_ISP:     'Mill — ISP',
};

const PRIORITY_LABEL = {
  5: { text: 'extracted', bg: '#dcfce7', color: '#166534' },
  4: { text: 'computed',  bg: '#fef9c3', color: '#854d0e' },
  3: { text: 'fallback',  bg: '#fee2e2', color: '#991b1b' },
};

// Unit type short descriptions shown in info panel
const UNIT_TYPE_INFO = {
  BF:      { label: 'Blast Furnace', color: '#1e3a5f' },
  SMS:     { label: 'Steel Melting Shop', color: '#1e5f3a' },
  MILL:    { label: 'Rolling Mill', color: '#5f3a1e' },
  COKE:    { label: 'Coke Oven', color: '#3a1e5f' },
  SINTER:  { label: 'Sinter Plant', color: '#5f1e3a' },
  GENERAL: { label: 'General / Plant-level', color: '#475569' },
};

function getDefaultPeriod() {
  const d = new Date();
  d.setMonth(d.getMonth() - 1);
  return { month: MONTHS[d.getMonth()], year: d.getFullYear().toString() };
}

function formatMonth(year, month) {
  const num = MONTH_NUM[month];
  return `${year}-${num}`;
}

function PriorityBadge({ priority }) {
  if (!priority) return null;
  const info = PRIORITY_LABEL[priority] || { text: `p${priority}`, bg: '#f1f5f9', color: '#64748b' };
  return (
    <span style={{
      fontSize: 9, padding: '1px 5px', borderRadius: 3,
      background: info.bg, color: info.color, fontWeight: 600, whiteSpace: 'nowrap',
    }}>
      {info.text}
    </span>
  );
}

function NumInput({ value, onChange, highlight }) {
  return (
    <input
      type="number" step="any" value={value}
      onChange={e => onChange(e.target.value)}
      style={{
        width: '100%', padding: '4px 6px', textAlign: 'right',
        border: `1px solid ${highlight ? '#6ee7b7' : '#cbd5e1'}`,
        borderRadius: 4, fontSize: 12,
        background: highlight ? '#f0fdf4' : '#fff',
        color: '#1e293b', outline: 'none',
      }}
    />
  );
}

function SectionTable({ section, rows, edits, onEdit, onClear }) {
  return (
    <div style={{ marginBottom: 18 }}>
      <div style={{
        background: '#1e3a5f', color: '#fff', padding: '7px 14px',
        fontSize: 13, fontWeight: 700, borderRadius: '4px 4px 0 0',
      }}>
        {section}
      </div>
      <div style={{ overflowX: 'auto', border: '1px solid #e2e8f0', borderTop: 'none', borderRadius: '0 0 4px 4px' }}>
        <table style={{ borderCollapse: 'collapse', width: '100%', fontSize: 12 }}>
          <thead>
            <tr style={{ background: '#f8fafc' }}>
              <th style={{ padding: '6px 12px', textAlign: 'left', color: '#475569', fontWeight: 600, minWidth: 150 }}>Row / Label</th>
              <th style={{ padding: '6px 8px', textAlign: 'center', color: '#475569', fontWeight: 600, minWidth: 72 }}>Unit</th>
              <th style={{ padding: '6px 8px', textAlign: 'center', color: '#475569', fontWeight: 600, minWidth: 110 }}>Actual</th>
              <th style={{ padding: '6px 8px', textAlign: 'center', color: '#475569', fontWeight: 600, minWidth: 110 }}>Cum. Actual</th>
              <th style={{ padding: '6px 8px', textAlign: 'center', color: '#475569', fontWeight: 600, minWidth: 80 }}>Status</th>
              <th style={{ padding: '6px 8px', textAlign: 'center', color: '#475569', fontWeight: 600, minWidth: 40 }}>Clr</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row, idx) => {
              const key = row.param_id;
              const edit = edits[key] || {};
              const aChanged = edit.actual !== undefined && edit.actual !== String(row.actual ?? '');
              const cChanged = edit.cum_actual !== undefined && edit.cum_actual !== String(row.cum_actual ?? '');
              const anyChanged = aChanged || cChanged;
              const hasData = row.actual !== null || row.cum_actual !== null;
              return (
                <tr key={key} style={{
                  background: anyChanged ? '#fffbeb' : idx % 2 === 0 ? '#fff' : '#f8fafc',
                  borderBottom: '1px solid #f1f5f9',
                }}>
                  <td style={{ padding: '6px 12px', fontWeight: 500, color: '#1e293b' }}>
                    {row.row_label}
                    {anyChanged && <span style={{ marginLeft: 6, fontSize: 9, color: '#d97706', fontWeight: 700 }}>edited</span>}
                  </td>
                  <td style={{ padding: '6px 8px', textAlign: 'center', color: '#64748b', fontStyle: 'italic' }}>
                    {row.unit || '—'}
                  </td>
                  <td style={{ padding: '4px 6px' }}>
                    <NumInput
                      value={edit.actual !== undefined ? edit.actual : String(row.actual ?? '')}
                      onChange={v => onEdit(key, 'actual', v)}
                      highlight={aChanged}
                    />
                  </td>
                  <td style={{ padding: '4px 6px' }}>
                    <NumInput
                      value={edit.cum_actual !== undefined ? edit.cum_actual : String(row.cum_actual ?? '')}
                      onChange={v => onEdit(key, 'cum_actual', v)}
                      highlight={cChanged}
                    />
                  </td>
                  <td style={{ padding: '6px 8px', textAlign: 'center' }}>
                    {hasData ? <PriorityBadge priority={row.source_priority} /> : <span style={{ color: '#94a3b8', fontSize: 11 }}>—</span>}
                  </td>
                  <td style={{ padding: '4px 8px', textAlign: 'center' }}>
                    {hasData && (
                      <button title="Clear this row" onClick={() => onClear(key)}
                        style={{ border: 'none', background: 'none', cursor: 'pointer', color: '#ef4444', fontSize: 14, padding: '2px 6px', borderRadius: 3 }}>
                        ×
                      </button>
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}

// ── Plant unit catalogue panel ────────────────────────────────────────────────
function UnitCatalogue({ units, paramTypes }) {
  const [openType, setOpenType] = useState(null);

  const byType = useMemo(() => {
    const m = {};
    for (const u of units) {
      if (!m[u.unit_type]) m[u.unit_type] = [];
      m[u.unit_type].push(u);
    }
    return m;
  }, [units]);

  const paramsByType = useMemo(() => {
    const m = {};
    for (const p of paramTypes) {
      if (!m[p.unit_type]) m[p.unit_type] = [];
      m[p.unit_type].push(p);
    }
    return m;
  }, [paramTypes]);

  if (!units.length) return null;

  return (
    <div style={{ marginBottom: 24 }}>
      <h3 style={{ fontSize: 13, color: '#1e293b', margin: '0 0 10px', fontWeight: 700 }}>
        Plant Unit Registry
      </h3>
      {Object.entries(byType).map(([ut, utUnits]) => {
        const info = UNIT_TYPE_INFO[ut] || { label: ut, color: '#475569' };
        const params = paramsByType[ut] || [];
        const isOpen = openType === ut;
        const PLANTS = ['BSP', 'DSP', 'RSP', 'BSL', 'ISP'];
        return (
          <div key={ut} style={{ marginBottom: 8, border: '1px solid #e2e8f0', borderRadius: 6, overflow: 'hidden' }}>
            <button
              onClick={() => setOpenType(isOpen ? null : ut)}
              style={{
                width: '100%', display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                padding: '8px 12px', background: isOpen ? info.color : '#f8fafc',
                color: isOpen ? '#fff' : '#1e293b', border: 'none', cursor: 'pointer',
                fontSize: 12, fontWeight: 600,
              }}
            >
              <span>{info.label}</span>
              <span style={{ fontSize: 10 }}>{isOpen ? '▲' : '▼'}</span>
            </button>
            {isOpen && (
              <div style={{ padding: '10px 12px', background: '#fff', overflowX: 'auto' }}>
                {/* Units grid */}
                <table style={{ fontSize: 11, borderCollapse: 'collapse', width: '100%', marginBottom: 10 }}>
                  <thead>
                    <tr style={{ background: '#f0f4f8' }}>
                      <th style={{ padding: '4px 8px', textAlign: 'left', color: '#475569' }}>Plant</th>
                      <th style={{ padding: '4px 8px', textAlign: 'left', color: '#475569' }}>Units</th>
                    </tr>
                  </thead>
                  <tbody>
                    {PLANTS.map(plant => {
                      const plantUnits = utUnits.filter(u => u.plant_code === plant);
                      if (!plantUnits.length) return null;
                      const fce = plantUnits.filter(u => !u.is_shop).map(u => u.unit_name).join(', ');
                      const shop = plantUnits.find(u => u.is_shop);
                      return (
                        <tr key={plant} style={{ borderBottom: '1px solid #f1f5f9' }}>
                          <td style={{ padding: '4px 8px', fontWeight: 600, color: '#1e293b' }}>{plant}</td>
                          <td style={{ padding: '4px 8px', color: '#475569' }}>
                            {fce}
                            {shop && <span style={{ marginLeft: 6, color: '#10b981', fontSize: 10 }}>+Shop Avg</span>}
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
                {/* Parameter list */}
                <div style={{ fontSize: 11, color: '#475569' }}>
                  <strong>Standard parameters ({params.length}):</strong>
                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: '4px 8px', marginTop: 4 }}>
                    {params.map(p => (
                      <span key={p.param_name} style={{
                        background: '#f0f4f8', padding: '2px 6px', borderRadius: 3,
                        fontSize: 10, color: '#1e293b',
                      }}>
                        {p.param_name} <span style={{ color: '#94a3b8' }}>{p.unit_of_meas}</span>
                      </span>
                    ))}
                  </div>
                </div>
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}

// ── Main page ────────────────────────────────────────────────────────────────
export default function TechnoManualEntry() {
  const def = getDefaultPeriod();
  const [month, setMonth] = useState(def.month);
  const [year, setYear] = useState(def.year);
  const [groupCode, setGroupCode] = useState('IRON_MAKING');
  const [groups, setGroups] = useState([]);
  const [units, setUnits] = useState([]);
  const [paramTypes, setParamTypes] = useState([]);
  const [sections, setSections] = useState([]);
  const [edits, setEdits] = useState({});
  const [pendingClears, setPendingClears] = useState(new Set());
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [status, setStatus] = useState(null);
  const [filter, setFilter] = useState('');
  const [showCatalogue, setShowCatalogue] = useState(false);

  const reportMonth = useMemo(() => formatMonth(year, month), [year, month]);

  // Load catalogue data once on mount
  useEffect(() => {
    fetch(`${API_BASE_URL}/api/techno-groups`)
      .then(r => r.json()).then(j => setGroups(j.groups || [])).catch(() => {});
    fetch(`${API_BASE_URL}/api/plant-units`)
      .then(r => r.json()).then(j => setUnits(j.units || [])).catch(() => {});
    fetch(`${API_BASE_URL}/api/param-types`)
      .then(r => r.json()).then(j => setParamTypes(j.param_types || [])).catch(() => {});
  }, []);

  const handleLoad = useCallback(async () => {
    setLoading(true);
    setEdits({});
    setPendingClears(new Set());
    setStatus(null);
    try {
      const res = await fetch(
        `${API_BASE_URL}/api/techno-monthly-data?group_code=${encodeURIComponent(groupCode)}&month=${reportMonth}`
      );
      if (!res.ok) throw new Error(await res.text());
      const json = await res.json();
      setSections(json.sections || []);
    } catch (err) {
      setStatus({ type: 'error', text: `Load failed: ${err.message}` });
    } finally {
      setLoading(false);
    }
  }, [groupCode, reportMonth]);

  const [firstMount, setFirstMount] = useState(true);
  useEffect(() => {
    if (firstMount) { setFirstMount(false); return; }
    handleLoad();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [groupCode, reportMonth]);

  const handleEdit = useCallback((paramId, field, value) => {
    setEdits(prev => ({ ...prev, [paramId]: { ...(prev[paramId] || {}), [field]: value } }));
  }, []);

  const handleClear = useCallback((paramId) => {
    setPendingClears(prev => new Set([...prev, paramId]));
    setEdits(prev => { const n = { ...prev }; delete n[paramId]; return n; });
    setSections(prev =>
      prev.map(sec => ({
        ...sec,
        rows: sec.rows.map(r =>
          r.param_id === paramId ? { ...r, actual: null, cum_actual: null, source_priority: null } : r
        ),
      }))
    );
  }, []);

  const hasChanges = useMemo(() => {
    if (pendingClears.size > 0) return true;
    for (const [paramId, edit] of Object.entries(edits)) {
      for (const sec of sections) {
        const row = sec.rows.find(r => r.param_id === parseInt(paramId));
        if (!row) continue;
        if (edit.actual !== undefined && edit.actual !== String(row.actual ?? '')) return true;
        if (edit.cum_actual !== undefined && edit.cum_actual !== String(row.cum_actual ?? '')) return true;
      }
    }
    return false;
  }, [edits, sections, pendingClears]);

  const handleSave = async () => {
    setSaving(true);
    setStatus(null);
    try {
      const rows = [];
      for (const [paramIdStr, edit] of Object.entries(edits)) {
        const paramId = parseInt(paramIdStr);
        let origActual = null, origCum = null;
        for (const sec of sections) {
          const row = sec.rows.find(r => r.param_id === paramId);
          if (row) { origActual = row.actual; origCum = row.cum_actual; break; }
        }
        const newActual = edit.actual !== undefined ? edit.actual : String(origActual ?? '');
        const newCum = edit.cum_actual !== undefined ? edit.cum_actual : String(origCum ?? '');
        if (newActual !== String(origActual ?? '') || newCum !== String(origCum ?? '')) {
          rows.push({ param_id: paramId, actual: newActual || null, cum_actual: newCum || null });
        }
      }
      for (const paramId of pendingClears) {
        rows.push({ param_id: paramId, actual: null, cum_actual: null, clear: true });
      }
      if (!rows.length) { setStatus({ type: 'info', text: 'No changes to save.' }); return; }

      const res = await fetch(`${API_BASE_URL}/api/techno-manual-save`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ month: reportMonth, group_code: groupCode, rows }),
      });
      if (!res.ok) throw new Error(await res.text());
      const json = await res.json();
      setStatus({ type: 'success', text: json.message });
      await handleLoad();
    } catch (err) {
      setStatus({ type: 'error', text: `Save failed: ${err.message}` });
    } finally {
      setSaving(false);
    }
  };

  const filteredSections = useMemo(() => {
    if (!filter.trim()) return sections;
    const q = filter.toLowerCase();
    return sections.map(sec => {
      const secMatch = sec.section.toLowerCase().includes(q);
      const filtRows = secMatch ? sec.rows : sec.rows.filter(r => r.row_label.toLowerCase().includes(q));
      return filtRows.length ? { ...sec, rows: filtRows } : null;
    }).filter(Boolean);
  }, [sections, filter]);

  const totalRows = sections.reduce((s, sec) => s + sec.rows.length, 0);
  const filledRows = sections.reduce((s, sec) => s + sec.rows.filter(r => r.actual !== null || r.cum_actual !== null).length, 0);

  return (
    <main className="app-container">
      {/* ── Sidebar ─────────────────────────────────────────────────────────── */}
      <div className="sidebar no-print">
        <div className="sidebar-header">
          <h1 style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
              <path d="M12 20h9"/><path d="M16.5 3.5a2.121 2.121 0 013 3L7 19l-4 1 1-4L16.5 3.5z"/>
            </svg>
            SAIL MIS Portal
          </h1>
          <p>Techno Data Entry</p>
        </div>

        <div className="control-section">
          <h2>Navigation</h2>
          <Link href="/" className="btn btn-secondary"
            style={{ width: '100%', display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6, textDecoration: 'none', justifyContent: 'center' }}>
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <line x1="19" y1="12" x2="5" y2="12"/><polyline points="12 19 5 12 12 5"/>
            </svg>
            Dashboard
          </Link>
          <Link href="/data-entry" className="btn btn-secondary"
            style={{ width: '100%', display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6, textDecoration: 'none', justifyContent: 'center' }}>
            Production Entry
          </Link>
          <Link href="/data-entry/targets" className="btn btn-secondary"
            style={{ width: '100%', display: 'flex', alignItems: 'center', gap: 8, textDecoration: 'none', justifyContent: 'center' }}>
            Techno Targets
          </Link>
        </div>

        <div className="control-section">
          <h2>Report Period</h2>
          <label className="control-label">Month</label>
          <select className="control-select" value={month} onChange={e => setMonth(e.target.value)}>
            {MONTHS.map(m => <option key={m}>{m}</option>)}
          </select>
          <label className="control-label">Year</label>
          <select className="control-select" value={year} onChange={e => setYear(e.target.value)}>
            {YEARS.map(y => <option key={y}>{y}</option>)}
          </select>
          <div style={{ fontSize: 11, color: '#64748b', marginTop: 4 }}>
            Report month: <strong>{reportMonth}</strong>
          </div>
        </div>

        <div className="control-section">
          <h2>Parameter Group</h2>
          <select className="control-select" value={groupCode} onChange={e => setGroupCode(e.target.value)}>
            {groups.length > 0
              ? groups.map(g => (
                  <option key={g.group_code} value={g.group_code}>
                    {GROUP_LABELS[g.group_code] || g.group_code} ({g.param_count})
                  </option>
                ))
              : Object.entries(GROUP_LABELS).map(([code, label]) => (
                  <option key={code} value={code}>{label}</option>
                ))}
          </select>
          <button className="btn btn-primary" style={{ width: '100%', marginTop: 8 }}
            onClick={handleLoad} disabled={loading}>
            {loading ? 'Loading...' : 'Load Parameters'}
          </button>
        </div>

        {sections.length > 0 && (
          <div className="control-section">
            <h2>Coverage</h2>
            <div style={{ fontSize: 12, color: '#475569', lineHeight: 1.9 }}>
              <div>Sections: <strong>{sections.length}</strong></div>
              <div>Parameters: <strong>{totalRows}</strong></div>
              <div style={{ color: '#10b981' }}>Has data: <strong>{filledRows}</strong></div>
              <div style={{ color: filledRows < totalRows ? '#f59e0b' : '#10b981' }}>
                Empty: <strong>{totalRows - filledRows}</strong>
              </div>
            </div>
          </div>
        )}

        {hasChanges && (
          <div className="control-section">
            <button className="btn btn-primary"
              style={{ width: '100%', background: '#10b981', borderColor: '#10b981' }}
              onClick={handleSave} disabled={saving}>
              {saving ? 'Saving...' : 'Save to DB'}
            </button>
            <p style={{ fontSize: 10, color: '#64748b', marginTop: 4 }}>
              Manual entries saved at priority 5 (same as extractors).
            </p>
          </div>
        )}

        <div className="control-section">
          <h2>Legend</h2>
          <div style={{ fontSize: 11, lineHeight: 2.2 }}>
            <span style={{ background: '#dcfce7', color: '#166534', padding: '1px 6px', borderRadius: 3, fontWeight: 600 }}>extracted</span> from source file<br />
            <span style={{ background: '#fef9c3', color: '#854d0e', padding: '1px 6px', borderRadius: 3, fontWeight: 600 }}>computed</span> shop average<br />
            <span style={{ color: '#94a3b8' }}>—</span> no data yet
          </div>
        </div>
      </div>

      {/* ── Main content ────────────────────────────────────────────────────── */}
      <div className="main-content" style={{ padding: '20px 24px', overflowY: 'auto' }}>

        {/* Header row */}
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 16 }}>
          <div>
            <h2 style={{ margin: 0, fontSize: 18, color: '#1e293b', fontWeight: 700 }}>
              {GROUP_LABELS[groupCode] || groupCode}
            </h2>
            <p style={{ margin: '4px 0 0', fontSize: 12, color: '#64748b' }}>
              Manual legacy data entry — {reportMonth}
            </p>
          </div>
          <div style={{ display: 'flex', gap: 8 }}>
            {sections.length > 0 && (
              <input type="text" placeholder="Filter section or label..."
                value={filter} onChange={e => setFilter(e.target.value)}
                style={{ padding: '6px 12px', border: '1px solid #cbd5e1', borderRadius: 6, fontSize: 12, width: 220, outline: 'none' }}
              />
            )}
            <button onClick={() => setShowCatalogue(s => !s)}
              style={{
                padding: '6px 14px', border: '1px solid #cbd5e1', borderRadius: 6,
                background: showCatalogue ? '#1e3a5f' : '#fff',
                color: showCatalogue ? '#fff' : '#475569',
                fontSize: 12, cursor: 'pointer', whiteSpace: 'nowrap',
              }}>
              {showCatalogue ? 'Hide' : 'Unit'} Catalogue
            </button>
          </div>
        </div>

        {status && (
          <div style={{
            padding: '10px 16px', borderRadius: 6, marginBottom: 16, fontSize: 13,
            background: status.type === 'success' ? '#f0fdf4' : status.type === 'error' ? '#fef2f2' : '#f0f9ff',
            color: status.type === 'success' ? '#166534' : status.type === 'error' ? '#991b1b' : '#075985',
            border: `1px solid ${status.type === 'success' ? '#86efac' : status.type === 'error' ? '#fca5a5' : '#bae6fd'}`,
          }}>
            {status.text}
          </div>
        )}

        {/* Unit catalogue panel */}
        {showCatalogue && <UnitCatalogue units={units} paramTypes={paramTypes} />}

        {loading && (
          <div style={{ textAlign: 'center', padding: 40, color: '#64748b', fontSize: 14 }}>
            Loading parameters...
          </div>
        )}

        {!loading && sections.length === 0 && !showCatalogue && (
          <div style={{
            textAlign: 'center', padding: 60, color: '#94a3b8', fontSize: 14,
            border: '2px dashed #e2e8f0', borderRadius: 8,
          }}>
            Select a group and month, then click <strong>Load Parameters</strong>.<br />
            <span style={{ fontSize: 12, marginTop: 8, display: 'block' }}>
              Click <strong>Unit Catalogue</strong> above to see all plant units and standard parameters.
            </span>
          </div>
        )}

        {!loading && filteredSections.map(sec => (
          <SectionTable
            key={sec.section}
            section={sec.section}
            rows={sec.rows}
            edits={edits}
            onEdit={handleEdit}
            onClear={handleClear}
          />
        ))}

        {!loading && sections.length > 0 && filteredSections.length === 0 && (
          <div style={{ textAlign: 'center', padding: 40, color: '#94a3b8', fontSize: 14 }}>
            No parameters match "<strong>{filter}</strong>"
          </div>
        )}

        {hasChanges && (
          <div style={{ position: 'sticky', bottom: 16, display: 'flex', justifyContent: 'flex-end', marginTop: 16 }}>
            <button className="btn btn-primary"
              style={{ background: '#10b981', borderColor: '#10b981', padding: '10px 28px', fontSize: 14 }}
              onClick={handleSave} disabled={saving}>
              {saving ? 'Saving...' : 'Save All Changes'}
            </button>
          </div>
        )}
      </div>
    </main>
  );
}
