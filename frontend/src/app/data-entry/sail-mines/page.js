'use client';

import RequireEditor from '@/components/RequireEditor';
import React, { useState, useEffect, useCallback } from 'react';
import GlobalNavbar from '@/components/GlobalNavbar';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || '';

// Must match backend/page_sail_mines.py's SAIL_MINES_SECTIONS (items only —
// Total/Yield rows there are computed, never entered). kind='production'
// sections get an Actual + Plan (APP) input per item; kind='flow' sections
// would get Actual only, but every despatch/sales section now carries its
// own Plan too (per direct instruction), so every section here is
// currently 'production'. iron_ore_despatch is `hidden` here (not its own
// table block) because the report merges it into Iron Ore Mines
// Performance as an extra DESPATCH column group (see iron_ore_prod's
// `despatchSection`) — it's still a normal SECTIONS entry so load/save
// pick its data up like any other section, just rendered inline (Actual +
// Plan, since it's 'production'-kind) instead of as its own table.
const SECTIONS = [
  { key: 'iron_ore_prod', title: 'Iron Ore Mines Performance', kind: 'production', items: ['CGoM', 'OGoM', 'JGoM', 'SAIL'], despatchSection: 'iron_ore_despatch' },
  { key: 'iron_ore_despatch', kind: 'production', items: ['CGoM', 'OGoM', 'JGoM', 'SAIL'], hidden: true },
  { key: 'iron_ore_sales', title: 'Sales of Iron Ore', kind: 'production', items: ['Auction', 'Despatch'] },
  { key: 'coal_prod', title: 'Coal Mines Production', kind: 'production', items: ['Raw Coking Coal', 'Thermal Coal'] },
  { key: 'washery', title: 'Washery Performance', kind: 'production', items: ['Input Raw Coal', 'Clean Coal'] },
  { key: 'coal_despatch', title: 'Despatch of Clean Coal, Thermal & Middlings', kind: 'production', items: ['Clean Coal', 'Thermal', 'Middlings'] },
  { key: 'flux_prod', title: 'Flux Production (Limestone & Dolomite)', kind: 'production', items: ['Limestone', 'Dolomite'] },
  { key: 'flux_despatch', title: 'Flux Despatch (Limestone & Dolomite)', kind: 'production', items: ['Limestone', 'Dolomite'] },
];

const keyOf = (section, item) => `${section}|${item}`;
const thisMonth = () => new Date().toISOString().slice(0, 7);

function SailMinesPageInner() {
  const [reportMonth, setReportMonth] = useState(thisMonth());
  const [saved, setSaved] = useState({});
  const [edits, setEdits] = useState({});
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [status, setStatus] = useState(null);

  const handleLoad = useCallback(async () => {
    setLoading(true);
    setStatus(null);
    try {
      const res = await fetch(`${API_BASE_URL}/api/sail-mines/monthly?report_month=${reportMonth}`);
      if (!res.ok) throw new Error((await res.json()).detail || 'Load failed');
      const json = await res.json();
      const entries = json.entries || {};
      const nextSaved = {};
      const nextEdits = {};
      SECTIONS.forEach(({ key: section, items }) => {
        items.forEach((item) => {
          const cell = entries[section]?.[item];
          const k = keyOf(section, item);
          const actual = cell?.actual ?? null;
          const plan = cell?.plan ?? null;
          nextSaved[k] = { actual, plan };
          nextEdits[k] = {
            actual: actual != null ? String(actual) : '',
            plan: plan != null ? String(plan) : '',
          };
        });
      });
      setSaved(nextSaved);
      setEdits(nextEdits);
    } catch (err) {
      setStatus({ type: 'error', text: err.message });
      setSaved({});
      setEdits({});
    } finally {
      setLoading(false);
    }
  }, [reportMonth]);

  useEffect(() => { handleLoad(); }, [handleLoad]);

  const handleChange = (section, item, field, value) => {
    const k = keyOf(section, item);
    setEdits((prev) => ({ ...prev, [k]: { ...prev[k], [field]: value } }));
  };

  const isChanged = (section, item) => {
    const k = keyOf(section, item);
    const e = edits[k] || {};
    const s = saved[k] || {};
    const sActual = s.actual != null ? String(s.actual) : '';
    const sPlan = s.plan != null ? String(s.plan) : '';
    return (e.actual ?? '') !== sActual || (e.plan ?? '') !== sPlan;
  };

  const hasChanges = () => SECTIONS.some(({ key: section, items }) => items.some((item) => isChanged(section, item)));

  const handleSave = async () => {
    setSaving(true);
    setStatus(null);
    const entries = [];
    SECTIONS.forEach(({ key: section, items }) => {
      items.forEach((item) => {
        if (!isChanged(section, item)) return;
        const e = edits[keyOf(section, item)] || {};
        const actual = e.actual === '' ? null : parseFloat(e.actual);
        const plan = e.plan === '' ? null : parseFloat(e.plan);
        if ((e.actual !== '' && Number.isNaN(actual)) || (e.plan !== '' && Number.isNaN(plan))) return;
        entries.push({ section, item, actual, plan });
      });
    });
    if (!entries.length) {
      setStatus({ type: 'error', text: 'No changes to save.' });
      setSaving(false);
      return;
    }
    try {
      const res = await fetch(`${API_BASE_URL}/api/sail-mines/monthly`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ report_month: reportMonth, entries }),
      });
      if (!res.ok) throw new Error((await res.json()).detail || 'Save failed');
      const result = await res.json();
      setStatus({ type: 'success', text: `Saved ${result.saved} value(s).` });
      await handleLoad();
    } catch (err) {
      setStatus({ type: 'error', text: `Save failed: ${err.message}` });
    } finally {
      setSaving(false);
    }
  };

  const inputStyle = (changed, hasValue) => ({
    width: 90, padding: '5px 6px', fontSize: 13, textAlign: 'right', borderRadius: 4,
    border: `1px solid ${changed ? '#fbbf24' : '#d1d5db'}`,
    background: changed ? '#fffbeb' : hasValue ? '#f0fdf4' : '#fff',
    color: changed ? '#92400e' : '#202124',
  });

  return (
    <div style={{ height: '100vh', display: 'flex', flexDirection: 'column', background: '#ffffff', fontFamily: "-apple-system,BlinkMacSystemFont,'Segoe UI',Arial,sans-serif" }}>
      <GlobalNavbar />

      <div style={{ flex: 1, overflowY: 'auto', maxWidth: 1200, width: '100%', margin: '0 auto', padding: '22px 20px' }}>
        <div style={{ display: 'flex', alignItems: 'baseline', gap: 14, marginBottom: 6, flexWrap: 'wrap' }}>
          <h2 style={{ fontSize: '1.6rem', fontWeight: 700, color: '#202124', margin: 0 }}>
            SAIL Mines Entry — Page 4.5
          </h2>
          <span style={{ fontSize: 13, color: '#5f6368' }}>
            Monthly Actual (and Plan, where the report shows an APP/%Fulfillment column) per item — Iron Ore Production/Sales,
            Coal Mines Production, Washery, Coal Despatch, Flux Production/Despatch. The report cumulates April-&lt;report month&gt;
            from these monthly entries; Total and Yield rows are computed automatically.
          </span>
        </div>

        <div style={{
          display: 'flex', gap: 14, alignItems: 'center', flexWrap: 'wrap',
          marginBottom: 18, border: '1px solid #dadce0', borderRadius: 8, padding: '14px 18px',
        }}>
          <label style={{ fontSize: 13, fontWeight: 600, color: '#374151' }}>Report Month</label>
          <input type="month" value={reportMonth} onChange={(e) => setReportMonth(e.target.value)}
                 style={{ padding: '6px 10px', fontSize: 14, border: '1px solid #d1d5db', borderRadius: 4 }} />

          <button onClick={handleSave} disabled={saving || !hasChanges()} style={{
            marginLeft: 'auto', padding: '8px 20px', fontSize: 13, fontWeight: 700, borderRadius: 6,
            border: 'none', cursor: hasChanges() ? 'pointer' : 'default',
            background: hasChanges() ? '#10b981' : '#9ca3af', color: '#fff',
          }}>
            {saving ? 'Saving...' : 'Save All'}
          </button>
        </div>

        {status && (
          <div style={{
            padding: '10px 16px', borderRadius: 6, marginBottom: 14, fontSize: 14,
            background: status.type === 'success' ? '#e6f4ea' : '#fef2f2',
            color: status.type === 'success' ? '#188038' : '#991b1b',
            border: `1px solid ${status.type === 'success' ? '#a8dab5' : '#fca5a5'}`,
          }}>
            {status.text}
          </div>
        )}

        {loading && <div style={{ color: '#5f6368', fontSize: 14, padding: '30px 0', textAlign: 'center' }}>Loading…</div>}

        {!loading && SECTIONS.filter((s) => !s.hidden).map(({ key: section, title, kind, items, despatchSection }) => {
          const despatchDef = despatchSection ? SECTIONS.find((s) => s.key === despatchSection) : null;
          const despatchIsProduction = despatchDef?.kind === 'production';
          return (
          <div key={section} style={{ marginBottom: 22 }}>
            <div style={{ fontSize: 14, fontWeight: 700, color: '#1e293b', marginBottom: 6 }}>{title}</div>
            <div style={{ border: '1px solid #dadce0', borderRadius: 8, overflow: 'hidden' }}>
              <table style={{ borderCollapse: 'collapse', width: '100%' }}>
                <thead>
                  <tr>
                    <th style={{
                      padding: '7px 12px', fontSize: 12, fontWeight: 600, color: '#374151',
                      background: '#f8fafc', borderBottom: '1px solid #dadce0', borderRight: '1px solid #eef1f4',
                      textAlign: 'left', whiteSpace: 'nowrap',
                    }}>Item</th>
                    <th style={{ padding: '7px 12px', fontSize: 12, fontWeight: 600, color: '#374151', background: '#f8fafc', borderBottom: '1px solid #dadce0', borderRight: (kind === 'production' || despatchSection) ? '1px solid #eef1f4' : 'none', textAlign: 'center' }}>Actual ({reportMonth})</th>
                    {kind === 'production' && (
                      <th style={{ padding: '7px 12px', fontSize: 12, fontWeight: 600, color: '#374151', background: '#f8fafc', borderBottom: '1px solid #dadce0', borderRight: despatchSection ? '1px solid #eef1f4' : 'none', textAlign: 'center' }}>Plan / APP ({reportMonth})</th>
                    )}
                    {despatchSection && (
                      <th style={{ padding: '7px 12px', fontSize: 12, fontWeight: 600, color: '#374151', background: '#f8fafc', borderBottom: '1px solid #dadce0', borderRight: despatchIsProduction ? '1px solid #eef1f4' : 'none', textAlign: 'center' }}>Despatch Actual ({reportMonth})</th>
                    )}
                    {despatchSection && despatchIsProduction && (
                      <th style={{ padding: '7px 12px', fontSize: 12, fontWeight: 600, color: '#374151', background: '#f8fafc', borderBottom: '1px solid #dadce0', textAlign: 'center' }}>Despatch Plan / APP ({reportMonth})</th>
                    )}
                  </tr>
                </thead>
                <tbody>
                  {items.map((item) => {
                    const changed = isChanged(section, item);
                    const e = edits[keyOf(section, item)] || {};
                    const dChanged = despatchSection && isChanged(despatchSection, item);
                    const dEdit = despatchSection ? (edits[keyOf(despatchSection, item)] || {}) : null;
                    return (
                      <tr key={item}>
                        <td style={{
                          padding: '8px 12px', fontSize: 13, fontWeight: 600, color: '#374151',
                          borderRight: '1px solid #eef1f4', borderBottom: '1px solid #f1f3f4', whiteSpace: 'nowrap',
                        }}>{item}</td>
                        <td style={{ padding: '6px 8px', borderRight: (kind === 'production' || despatchSection) ? '1px solid #eef1f4' : 'none', borderBottom: '1px solid #f1f3f4', textAlign: 'center' }}>
                          <input type="number" step="any" value={e.actual ?? ''} placeholder="–"
                                 onChange={(ev) => handleChange(section, item, 'actual', ev.target.value)}
                                 style={inputStyle(changed, e.actual)} />
                        </td>
                        {kind === 'production' && (
                          <td style={{ padding: '6px 8px', borderRight: despatchSection ? '1px solid #eef1f4' : 'none', borderBottom: '1px solid #f1f3f4', textAlign: 'center' }}>
                            <input type="number" step="any" value={e.plan ?? ''} placeholder="–"
                                   onChange={(ev) => handleChange(section, item, 'plan', ev.target.value)}
                                   style={inputStyle(changed, e.plan)} />
                          </td>
                        )}
                        {despatchSection && (
                          <td style={{ padding: '6px 8px', borderRight: despatchIsProduction ? '1px solid #eef1f4' : 'none', borderBottom: '1px solid #f1f3f4', textAlign: 'center' }}>
                            <input type="number" step="any" value={dEdit.actual ?? ''} placeholder="–"
                                   onChange={(ev) => handleChange(despatchSection, item, 'actual', ev.target.value)}
                                   style={inputStyle(dChanged, dEdit.actual)} />
                          </td>
                        )}
                        {despatchSection && despatchIsProduction && (
                          <td style={{ padding: '6px 8px', borderBottom: '1px solid #f1f3f4', textAlign: 'center' }}>
                            <input type="number" step="any" value={dEdit.plan ?? ''} placeholder="–"
                                   onChange={(ev) => handleChange(despatchSection, item, 'plan', ev.target.value)}
                                   style={inputStyle(dChanged, dEdit.plan)} />
                          </td>
                        )}
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </div>
          );
        })}
      </div>
    </div>
  );
}

export default function SailMinesPage() {
  return (
    <RequireEditor>
      <SailMinesPageInner />
    </RequireEditor>
  );
}
