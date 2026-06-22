'use client';

import React, { useState, useCallback } from 'react';
import Link from 'next/link';

const API = process.env.NEXT_PUBLIC_API_URL || '';

const PLANTS = ['BSP', 'DSP', 'ISP', 'RSP', 'BSL', 'ASP', 'SSP', 'VISL'];
const UNITS  = ['T', 'Rake'];
const IPT_ITEMS = [
  'Screened Coke', 'Sinter', 'Pellet', 'Hot Metal', 'Liquid Steel',
  'CC Slabs', 'Blooms / Billets', 'Finished Steel', 'Wire Rod',
  'Rails', 'Plates / Coils', 'BF Gas', 'CO Gas', 'LD Slag',
];

function defaultMonth() {
  const d = new Date();
  d.setDate(1);
  d.setMonth(d.getMonth() - 1);
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}`;
}

function numOrNull(v) {
  const f = parseFloat(v);
  return isNaN(f) ? null : f;
}

const S = {
  H:  { padding: '7px 8px', textAlign: 'center', fontWeight: 700, color: '#475569',
        borderBottom: '1px solid #e2e8f0', fontSize: '8.5pt', backgroundColor: '#f1f5f9',
        whiteSpace: 'nowrap' },
  TD: { padding: '4px 5px', borderBottom: '1px solid #f0f4f8', fontSize: '9pt', verticalAlign: 'middle' },
};

function Sel({ value, onChange, options, width = 70 }) {
  return (
    <select value={value} onChange={e => onChange(e.target.value)}
      style={{ width, padding: '3px 4px', border: '1px solid #cbd5e1', borderRadius: 3, fontSize: '8.5pt', backgroundColor: '#fff' }}>
      {options.map(o => <option key={o} value={o}>{o}</option>)}
      {!options.includes(value) && <option value={value}>{value}</option>}
    </select>
  );
}

function Num({ value, onChange, width = 68 }) {
  return (
    <input type="number" step="any" value={value ?? ''}
      onChange={e => onChange(e.target.value)}
      style={{ width, padding: '3px 5px', border: '1px solid #cbd5e1', borderRadius: 3,
               textAlign: 'right', fontSize: '8.5pt', backgroundColor: '#fff' }} />
  );
}

function RouteRow({ row, month, onSaved, onDeleted }) {
  const [r, setR]     = useState(row);
  const [saving, setSaving]   = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [msg, setMsg] = useState(null);

  const set = (k, v) => setR(prev => ({ ...prev, [k]: v }));
  const isRake = r.unit === 'Rake';

  const handleSave = async () => {
    setSaving(true);
    setMsg(null);
    try {
      const res = await fetch(`${API}/api/ipt-entry`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          month,
          item: r.item, from_plant: r.from_plant, to_plant: r.to_plant,
          unit: r.unit, sort_order: parseInt(r.sort_order) || 0,
          plan: numOrNull(r.plan), actual: numOrNull(r.actual),
          plan_tonnage: isRake ? numOrNull(r.plan_tonnage) : null,
          actual_tonnage: isRake ? numOrNull(r.actual_tonnage) : null,
        }),
      });
      if (!res.ok) throw new Error(await res.text());
      setMsg('saved');
      onSaved(r);
      setTimeout(() => setMsg(null), 1500);
    } catch (err) {
      setMsg('err:' + err.message);
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async () => {
    if (!confirm(`Delete: ${r.item} ${r.from_plant} → ${r.to_plant}?`)) return;
    setDeleting(true);
    try {
      const res = await fetch(`${API}/api/ipt-delete`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ month, item: row.item, from_plant: row.from_plant, to_plant: row.to_plant }),
      });
      if (!res.ok) throw new Error(await res.text());
      onDeleted();
    } catch (err) {
      setMsg('err:' + err.message);
      setDeleting(false);
    }
  };

  const rowBg = msg === 'saved' ? '#f0fdf4' : msg?.startsWith('err') ? '#fef2f2' : '#fff';

  return (
    <tr style={{ backgroundColor: rowBg }}>
      <td style={S.TD}><Sel value={r.item} onChange={v => set('item', v)} options={IPT_ITEMS} width={140} /></td>
      <td style={{ ...S.TD, textAlign: 'center' }}><Sel value={r.from_plant} onChange={v => set('from_plant', v)} options={PLANTS} width={62} /></td>
      <td style={{ ...S.TD, textAlign: 'center' }}><Sel value={r.to_plant}   onChange={v => set('to_plant',   v)} options={PLANTS} width={62} /></td>
      <td style={{ ...S.TD, textAlign: 'center' }}><Sel value={r.unit} onChange={v => set('unit', v)} options={UNITS} width={56} /></td>
      <td style={{ ...S.TD, textAlign: 'center' }}>
        <input type="number" step="1" value={r.sort_order ?? 0} onChange={e => set('sort_order', e.target.value)}
          style={{ width: 44, padding: '3px 4px', border: '1px solid #cbd5e1', borderRadius: 3, textAlign: 'center', fontSize: '8.5pt' }} />
      </td>
      <td style={{ ...S.TD, textAlign: 'right' }}><Num value={r.plan}            onChange={v => set('plan', v)} /></td>
      <td style={{ ...S.TD, textAlign: 'right' }}><Num value={r.actual}          onChange={v => set('actual', v)} /></td>
      <td style={{ ...S.TD, textAlign: 'right' }}>
        {isRake ? <Num value={r.plan_tonnage}   onChange={v => set('plan_tonnage', v)} /> : <span style={{ color: '#94a3b8' }}>—</span>}
      </td>
      <td style={{ ...S.TD, textAlign: 'right' }}>
        {isRake ? <Num value={r.actual_tonnage} onChange={v => set('actual_tonnage', v)} /> : <span style={{ color: '#94a3b8' }}>—</span>}
      </td>
      <td style={{ ...S.TD, textAlign: 'center' }}>
        {msg === 'saved'
          ? <span style={{ color: '#059669', fontWeight: 700, fontSize: '8pt' }}>✓</span>
          : msg?.startsWith('err')
          ? <span style={{ color: '#dc2626', fontSize: '7.5pt' }} title={msg.slice(4)}>✗</span>
          : (
          <button onClick={handleSave} disabled={saving}
            style={{ padding: '3px 10px', border: 'none', borderRadius: 3,
                     backgroundColor: '#10b981', color: '#fff', fontSize: '8pt',
                     cursor: 'pointer', fontWeight: 600 }}>
            {saving ? '…' : 'Save'}
          </button>
        )}
      </td>
      <td style={{ ...S.TD, textAlign: 'center' }}>
        <button onClick={handleDelete} disabled={deleting}
          style={{ padding: '3px 9px', border: 'none', borderRadius: 3,
                   backgroundColor: '#ef4444', color: '#fff', fontSize: '8pt', cursor: 'pointer' }}>
          {deleting ? '…' : 'Del'}
        </button>
      </td>
    </tr>
  );
}

function NewRouteRow({ month, onAdded }) {
  const [r, setR] = useState({
    item: IPT_ITEMS[0], from_plant: 'BSP', to_plant: 'DSP',
    unit: 'T', sort_order: 0,
    plan: '', actual: '', plan_tonnage: '', actual_tonnage: '',
  });
  const [saving, setSaving] = useState(false);
  const [err, setErr]       = useState(null);

  const set    = (k, v) => setR(prev => ({ ...prev, [k]: v }));
  const isRake = r.unit === 'Rake';

  const handleAdd = async () => {
    if (r.from_plant === r.to_plant) { setErr('From and To must differ.'); return; }
    setSaving(true);
    setErr(null);
    try {
      const res = await fetch(`${API}/api/ipt-entry`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          month,
          item: r.item, from_plant: r.from_plant, to_plant: r.to_plant,
          unit: r.unit, sort_order: parseInt(r.sort_order) || 0,
          plan: numOrNull(r.plan), actual: numOrNull(r.actual),
          plan_tonnage: isRake ? numOrNull(r.plan_tonnage) : null,
          actual_tonnage: isRake ? numOrNull(r.actual_tonnage) : null,
        }),
      });
      if (!res.ok) throw new Error(await res.text());
      onAdded();
    } catch (e) {
      setErr(e.message);
    } finally {
      setSaving(false);
    }
  };

  return (
    <>
      <tr style={{ backgroundColor: '#fffbeb', borderTop: '2px solid #f59e0b' }}>
        <td style={S.TD}><Sel value={r.item} onChange={v => set('item', v)} options={IPT_ITEMS} width={140} /></td>
        <td style={{ ...S.TD, textAlign: 'center' }}><Sel value={r.from_plant} onChange={v => set('from_plant', v)} options={PLANTS} width={62} /></td>
        <td style={{ ...S.TD, textAlign: 'center' }}><Sel value={r.to_plant}   onChange={v => set('to_plant',   v)} options={PLANTS} width={62} /></td>
        <td style={{ ...S.TD, textAlign: 'center' }}><Sel value={r.unit} onChange={v => set('unit', v)} options={UNITS} width={56} /></td>
        <td style={{ ...S.TD, textAlign: 'center' }}>
          <input type="number" step="1" value={r.sort_order} onChange={e => set('sort_order', e.target.value)}
            style={{ width: 44, padding: '3px 4px', border: '1px solid #cbd5e1', borderRadius: 3, textAlign: 'center', fontSize: '8.5pt' }} />
        </td>
        <td style={{ ...S.TD, textAlign: 'right' }}><Num value={r.plan}   onChange={v => set('plan', v)} /></td>
        <td style={{ ...S.TD, textAlign: 'right' }}><Num value={r.actual} onChange={v => set('actual', v)} /></td>
        <td style={{ ...S.TD, textAlign: 'right' }}>
          {isRake ? <Num value={r.plan_tonnage}   onChange={v => set('plan_tonnage', v)} /> : <span style={{ color: '#94a3b8' }}>—</span>}
        </td>
        <td style={{ ...S.TD, textAlign: 'right' }}>
          {isRake ? <Num value={r.actual_tonnage} onChange={v => set('actual_tonnage', v)} /> : <span style={{ color: '#94a3b8' }}>—</span>}
        </td>
        <td colSpan={2} style={{ ...S.TD, textAlign: 'center' }}>
          <button onClick={handleAdd} disabled={saving}
            style={{ padding: '4px 14px', border: 'none', borderRadius: 3,
                     backgroundColor: '#6366f1', color: '#fff', fontSize: '8.5pt',
                     cursor: 'pointer', fontWeight: 600 }}>
            {saving ? '…' : '+ Add Route'}
          </button>
        </td>
      </tr>
      {err && (
        <tr>
          <td colSpan={11} style={{ padding: '4px 10px', color: '#dc2626', fontSize: '8pt', backgroundColor: '#fef2f2' }}>
            {err}
          </td>
        </tr>
      )}
    </>
  );
}

export default function IptDataEntryPage() {
  const [month, setMonth]     = useState(defaultMonth);
  const [rows, setRows]       = useState([]);
  const [loading, setLoading] = useState(false);
  const [status, setStatus]   = useState(null);
  const [loaded, setLoaded]   = useState(false);
  const [showNew, setShowNew] = useState(false);

  const load = useCallback(async (m) => {
    const target = m || month;
    setLoading(true);
    setStatus(null);
    setLoaded(false);
    setShowNew(false);
    try {
      const res = await fetch(`${API}/api/ipt-entries?month=${encodeURIComponent(target)}`);
      if (!res.ok) throw new Error(await res.text());
      const data = await res.json();
      setRows(data.rows.map(r => ({
        ...r,
        plan:            r.plan            ?? '',
        actual:          r.actual          ?? '',
        plan_tonnage:    r.plan_tonnage    ?? '',
        actual_tonnage:  r.actual_tonnage  ?? '',
      })));
      setLoaded(true);
    } catch (err) {
      setStatus({ type: 'error', text: `Load failed: ${err.message}` });
    } finally {
      setLoading(false);
    }
  }, [month]);

  const handleAdded = () => {
    setShowNew(false);
    load(month);
    setStatus({ type: 'success', text: 'Route added.' });
    setTimeout(() => setStatus(null), 2000);
  };

  const handleRowSaved  = (idx, updated) => setRows(prev => prev.map((r, i) => i === idx ? updated : r));
  const handleRowDelete = (idx) => setRows(prev => prev.filter((_, i) => i !== idx));

  const [y, mo] = month.split('-');
  const MON = ['','Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
  const monthDisplay = `${MON[parseInt(mo)]}'${y.slice(2)}`;

  return (
    <main className="app-container">
      {/* Sidebar */}
      <div className="sidebar no-print">
        <div className="sidebar-header">
          <h1 style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" style={{ color: 'var(--primary)' }}>
              <rect x="3" y="3" width="18" height="18" rx="2"/>
              <path d="M3 9h18M9 21V9"/>
            </svg>
            SAIL MIS Portal
          </h1>
          <p>IPT Data Entry</p>
        </div>

        <div className="control-section">
          <h2>Navigation</h2>
          {[
            { href: '/',                  label: 'Dashboard' },
            { href: '/report',            label: 'Report Engine' },
            { href: '/upload',            label: 'Excel Upload' },
            { href: '/data-entry',        label: 'Production Entry' },
            { href: '/data-entry/targets',label: 'TE Annual Targets' },
            { href: '/data-entry/techno', label: 'Techno Data Entry' },
            { href: '/data-entry/ipt',    label: 'IPT Data Entry', active: true },
          ].map(({ href, label, active }) => (
            <Link key={href} href={href} className="btn btn-secondary"
              style={{ width: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center',
                       gap: 8, marginBottom: 8, textDecoration: 'none',
                       ...(active ? { backgroundColor: '#1e3a5f', color: '#fff' } : {}) }}>
              {label}
            </Link>
          ))}
        </div>

        <div className="control-section" style={{ marginTop: 16 }}>
          <h2>Report Month</h2>
          <div className="form-group" style={{ marginBottom: 12 }}>
            <label>Month</label>
            <input type="month" value={month}
              onChange={e => { setMonth(e.target.value); setLoaded(false); setRows([]); }}
              className="form-control" />
          </div>
          <button className="btn btn-primary" style={{ width: '100%', backgroundColor: '#6366f1', borderColor: '#6366f1' }}
            onClick={() => load(month)} disabled={loading}>
            {loading ? 'Loading…' : 'Load Records'}
          </button>
          {loaded && (
            <button className="btn btn-secondary"
              style={{ width: '100%', marginTop: 8 }}
              onClick={() => setShowNew(v => !v)}>
              {showNew ? 'Cancel New Route' : '+ Add New Route'}
            </button>
          )}
        </div>

        {status && (
          <div style={{ margin: '12px 0', padding: '10px 12px', borderRadius: 6, fontSize: '0.8rem',
                        backgroundColor: status.type === 'success' ? '#064e3b' : '#7f1d1d',
                        color: status.type === 'success' ? '#6ee7b7' : '#fca5a5',
                        border: `1px solid ${status.type === 'success' ? '#065f46' : '#991b1b'}` }}>
            {status.text}
          </div>
        )}

        <div style={{ marginTop: 'auto', fontSize: '0.75rem', color: '#64748b', textAlign: 'center', paddingTop: 16 }}>
          SAIL Informatics Report Portal • v1.0.0
        </div>
      </div>

      {/* Main content */}
      <div className="preview-area" style={{ padding: 30, overflowY: 'auto', backgroundColor: '#f8fafc' }}>
        <div style={{ maxWidth: 1100, margin: '0 auto' }}>
          <div style={{ marginBottom: 20 }}>
            <h1 style={{ fontSize: '18pt', fontWeight: 800, color: '#0f172a', margin: '0 0 4px 0' }}>
              IPT Status — Data Entry
            </h1>
            <p style={{ fontSize: '10pt', color: '#64748b', margin: 0 }}>
              Inter-Plant Transfer routes for page 26. Select month and click Load Records.
            </p>
          </div>

          {!loaded && !loading && (
            <div style={{ padding: 48, textAlign: 'center', backgroundColor: '#fff',
                          border: '1px solid #e2e8f0', borderRadius: 8, color: '#94a3b8' }}>
              <p style={{ margin: 0, fontSize: '10pt' }}>
                Select a month and click <strong>Load Records</strong>.
              </p>
            </div>
          )}

          {loading && (
            <div style={{ padding: 48, textAlign: 'center', color: '#64748b', fontSize: '10pt' }}>
              Loading…
            </div>
          )}

          {loaded && (
            <div style={{ backgroundColor: '#fff', border: '1px solid #e2e8f0', borderRadius: 8, overflow: 'hidden' }}>
              {/* Table header */}
              <div style={{ padding: '12px 18px', backgroundColor: '#1e293b', color: '#f1f5f9',
                            display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <span style={{ fontWeight: 700, fontSize: '10pt' }}>
                  IPT Status — {monthDisplay}
                </span>
                <span style={{ fontSize: '9pt', color: '#94a3b8' }}>
                  {rows.length} route{rows.length !== 1 ? 's' : ''}
                </span>
              </div>

              <div style={{ overflowX: 'auto' }}>
                <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '9pt' }}>
                  <thead>
                    <tr>
                      <th style={{ ...S.H, textAlign: 'left', width: 150 }}>Item</th>
                      <th style={S.H}>From</th>
                      <th style={S.H}>To</th>
                      <th style={S.H}>Unit</th>
                      <th style={S.H}>Sort #</th>
                      <th style={S.H}>Plan</th>
                      <th style={S.H}>Actual</th>
                      <th style={S.H}>Plan (T)</th>
                      <th style={S.H}>Actual (T)</th>
                      <th style={S.H} colSpan={2}>Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {rows.length === 0 && !showNew && (
                      <tr>
                        <td colSpan={11} style={{ padding: '24px', textAlign: 'center', color: '#94a3b8', fontSize: '9.5pt' }}>
                          No routes for {monthDisplay}. Click <strong>+ Add New Route</strong> to create one.
                        </td>
                      </tr>
                    )}
                    {rows.map((row, idx) => (
                      <RouteRow
                        key={`${row.item}|${row.from_plant}|${row.to_plant}`}
                        row={row}
                        month={month}
                        onSaved={updated => handleRowSaved(idx, updated)}
                        onDeleted={() => handleRowDelete(idx)}
                      />
                    ))}
                    {showNew && (
                      <NewRouteRow month={month} onAdded={handleAdded} />
                    )}
                  </tbody>
                </table>
              </div>

              <div style={{ padding: '10px 16px', backgroundColor: '#f8fafc', borderTop: '1px solid #e2e8f0',
                            display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <span style={{ fontSize: '8.5pt', color: '#64748b' }}>
                  Save each row individually. Plan (T) and Actual (T) apply only to Rake unit routes.
                </span>
                <button onClick={() => setShowNew(v => !v)}
                  style={{ padding: '5px 14px', border: '1px solid #6366f1', borderRadius: 4,
                           backgroundColor: showNew ? '#f1f5f9' : '#6366f1',
                           color: showNew ? '#6366f1' : '#fff', fontSize: '9pt', cursor: 'pointer' }}>
                  {showNew ? 'Cancel' : '+ Add Route'}
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
    </main>
  );
}
