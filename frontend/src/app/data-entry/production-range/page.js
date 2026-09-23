'use client';

import RequireEditor from '@/components/RequireEditor';
import React, { useState, useCallback, useMemo, useEffect } from 'react';
import GlobalNavbar from '@/components/GlobalNavbar';

const PLANTS = ['BSP', 'DSP', 'ISP', 'RSP', 'BSL', 'ASP', 'SSP', 'VISL'];
const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || '';

const MON_LABEL = ['', 'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];

function monthLabel(reportMonth) {
  const [y, m] = reportMonth.split('-');
  return `${MON_LABEL[parseInt(m, 10)]}'${y.slice(2)}`;
}

/** Every 'YYYY-MM' from `from` to `to` inclusive, chronological order. */
function monthsBetween(from, to) {
  const [fy, fm] = from.split('-').map(Number);
  const [ty, tm] = to.split('-').map(Number);
  const out = [];
  let y = fy, m = fm;
  while (y < ty || (y === ty && m <= tm)) {
    out.push(`${y}-${String(m).padStart(2, '0')}`);
    m += 1;
    if (m > 12) { m = 1; y += 1; }
  }
  return out;
}

function getDefaultRange() {
  const now = new Date();
  const to = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}`;
  const fromDate = new Date(now.getFullYear(), now.getMonth() - 11, 1);
  const from = `${fromDate.getFullYear()}-${String(fromDate.getMonth() + 1).padStart(2, '0')}`;
  return { from, to };
}

function Notice({ type, text }) {
  if (!text) return null;
  const ok = type === 'success';
  return (
    <div style={{
      padding: '12px 16px', borderRadius: 6, margin: '16px 0', fontSize: 13,
      background: ok ? '#dcfce7' : '#fee2e2', color: ok ? '#166534' : '#991b1b',
      border: `1px solid ${ok ? '#bbf7d0' : '#fecaca'}`,
    }}>{text}</div>
  );
}

function ProductionRangeEntryInner() {
  const defaultRange = getDefaultRange();
  const [plant, setPlant] = useState('BSP');
  const [item, setItem] = useState('');
  const [knownItems, setKnownItems] = useState([]);
  const [from, setFrom] = useState(defaultRange.from);
  const [to, setTo] = useState(defaultRange.to);
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [loaded, setLoaded] = useState(false);
  const [status, setStatus] = useState(null);

  useEffect(() => {
    let cancelled = false;
    fetch(`${API_BASE_URL}/api/item-mapping-suggestions?plant=${encodeURIComponent(plant)}`)
      .then((r) => (r.ok ? r.json() : { items: [] }))
      .then((d) => {
        if (cancelled) return;
        const items = d.items ?? [];
        setKnownItems(items);
        setItem((cur) => (items.includes(cur) ? cur : (items[0] ?? '')));
      })
      .catch(() => { if (!cancelled) { setKnownItems([]); setItem(''); } });
    return () => { cancelled = true; };
  }, [plant]);

  const monthsWanted = useMemo(() => {
    if (!from || !to || from > to) return [];
    return monthsBetween(from, to);
  }, [from, to]);

  const handleLoad = useCallback(async () => {
    const trimmedItem = item.trim();
    if (!trimmedItem) {
      setStatus({ type: 'error', text: 'Select a unit first.' });
      return;
    }
    if (monthsWanted.length === 0) {
      setStatus({ type: 'error', text: '"From" must be on or before "To".' });
      return;
    }
    setLoading(true);
    setStatus(null);
    setLoaded(false);
    try {
      const res = await fetch(
        `${API_BASE_URL}/api/production-item-range?plant=${encodeURIComponent(plant)}` +
        `&item=${encodeURIComponent(trimmedItem)}&months=${monthsWanted.join(',')}`
      );
      if (!res.ok) throw new Error(await res.text());
      const data = await res.json();
      setRows(data.rows.map((r) => ({
        report_month: r.report_month,
        value: r.value,
        edit: r.value === null || r.value === undefined ? '' : String(r.value),
      })));
      setLoaded(true);
    } catch (err) {
      setStatus({ type: 'error', text: `Load failed: ${err.message}` });
    } finally {
      setLoading(false);
    }
  }, [plant, item, monthsWanted]);

  const setEdit = (idx, val) => setRows((prev) => prev.map((r, i) => (i === idx ? { ...r, edit: val } : r)));

  const hasChanges = rows.some((r) => r.edit !== (r.value === null || r.value === undefined ? '' : String(r.value)));

  const handleSave = async () => {
    setSaving(true);
    setStatus(null);
    const entries = rows
      .filter((r) => r.edit !== (r.value === null || r.value === undefined ? '' : String(r.value)))
      .map((r) => ({
        report_month: r.report_month,
        value: r.edit.trim() === '' ? null : parseFloat(r.edit),
      }));
    if (entries.length === 0) {
      setSaving(false);
      setStatus({ type: 'error', text: 'Nothing changed.' });
      return;
    }
    try {
      const res = await fetch(`${API_BASE_URL}/api/production-item-range`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ plant, item: item.trim(), entries }),
      });
      if (!res.ok) throw new Error(await res.text());
      const result = await res.json();
      setStatus({ type: 'success', text: `Saved ${result.count} month(s) for ${plant} — ${item.trim()}.` });
      await handleLoad();
    } catch (err) {
      setStatus({ type: 'error', text: `Save failed: ${err.message}` });
    } finally {
      setSaving(false);
    }
  };

  const label = { fontSize: 13, fontWeight: 600, color: '#5f6368', display: 'block', marginBottom: 6 };
  const input = { padding: '9px 12px', fontSize: 13.5, width: '100%', borderRadius: 4, border: '1px solid #dadce0', boxSizing: 'border-box' };

  return (
    <div style={{ minHeight: '100vh', display: 'flex', flexDirection: 'column', background: '#fff' }}>
      <GlobalNavbar />
      <div style={{ flex: 1, maxWidth: 900, margin: '0 auto', padding: '32px 24px', width: '100%', boxSizing: 'border-box' }}>
        <h1 style={{ fontSize: '1.7rem', fontWeight: 800, color: '#202124', margin: '0 0 4px' }}>
          📈 Production Data Entry — Month Range
        </h1>
        <p style={{ fontSize: 13.5, color: '#5f6368', margin: '0 0 20px' }}>
          Enter or correct one plant/unit&apos;s actual production across several months at once — writes straight
          to <code>production_table</code>, the same table every report page reads. For entering a whole month&apos;s
          items at once, use <a href="/data-entry/production">Production Data Entry</a> instead.
        </p>

        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: 16, border: '1px solid #dadce0', borderRadius: 8, padding: 18 }}>
          <div>
            <label style={label}>Plant</label>
            <select value={plant} onChange={(e) => { setPlant(e.target.value); setLoaded(false); setRows([]); }} style={input}>
              {PLANTS.map((p) => <option key={p} value={p}>{p}</option>)}
            </select>
          </div>
          <div>
            <label style={label}>Unit / Item</label>
            {/* Units are this plant's own item names in production_table
                (via /api/item-mapping-suggestions), in process order. */}
            <select
              value={item}
              onChange={(e) => { setItem(e.target.value); setLoaded(false); setRows([]); }}
              disabled={knownItems.length === 0} style={input}
            >
              {knownItems.length === 0 && <option value="">No units in production_table</option>}
              {knownItems.map((n) => <option key={n} value={n}>{n}</option>)}
            </select>
          </div>
          <div>
            <label style={label}>From</label>
            <input type="month" value={from} onChange={(e) => { setFrom(e.target.value); setLoaded(false); setRows([]); }} style={input} />
          </div>
          <div>
            <label style={label}>To</label>
            <input type="month" value={to} onChange={(e) => { setTo(e.target.value); setLoaded(false); setRows([]); }} style={input} />
          </div>
          <div style={{ display: 'flex', alignItems: 'flex-end' }}>
            <button
              onClick={handleLoad} disabled={loading}
              style={{ width: '100%', padding: '9px 14px', fontSize: 13.5, fontWeight: 700, background: '#6366f1', color: '#fff', border: 'none', borderRadius: 4, cursor: 'pointer' }}
            >
              {loading ? 'Loading…' : `Load ${monthsWanted.length || ''} month(s)`}
            </button>
          </div>
        </div>

        <Notice type={status?.type} text={status?.text} />

        {loaded && rows.length > 0 && (
          <>
            <div style={{ border: '1px solid #dadce0', borderRadius: 8, overflow: 'hidden', marginTop: 20 }}>
              <table style={{ borderCollapse: 'collapse', width: '100%' }}>
                <thead>
                  <tr style={{ background: '#f8f9fa' }}>
                    <th style={{ padding: '10px 14px', textAlign: 'left', fontSize: 12, fontWeight: 700, color: '#5f6368', borderBottom: '1px solid #dadce0' }}>Month</th>
                    <th style={{ padding: '10px 14px', textAlign: 'right', fontSize: 12, fontWeight: 700, color: '#5f6368', borderBottom: '1px solid #dadce0' }}>Actual Value</th>
                  </tr>
                </thead>
                <tbody>
                  {rows.map((r, idx) => {
                    const changed = r.edit !== (r.value === null || r.value === undefined ? '' : String(r.value));
                    return (
                      <tr key={r.report_month} style={{ borderBottom: '1px solid #f1f3f4', background: changed ? '#fffbea' : 'transparent' }}>
                        <td style={{ padding: '8px 14px', fontSize: 13.5, color: '#202124', fontWeight: 500 }}>
                          {monthLabel(r.report_month)} <span style={{ color: '#9aa0a6', fontSize: 11.5 }}>({r.report_month})</span>
                        </td>
                        <td style={{ padding: '6px 14px', textAlign: 'right' }}>
                          <input
                            type="number" step="0.001" value={r.edit}
                            onChange={(e) => setEdit(idx, e.target.value)}
                            style={{ width: 140, padding: '7px 10px', border: '1px solid #dadce0', borderRadius: 4, textAlign: 'right', fontSize: 13 }}
                          />
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>

            <div style={{ display: 'flex', gap: 12, justifyContent: 'flex-end', marginTop: 16 }}>
              <button
                onClick={() => setRows((prev) => prev.map((r) => ({ ...r, edit: r.value === null || r.value === undefined ? '' : String(r.value) })))}
                disabled={!hasChanges}
                style={{ padding: '10px 20px', borderRadius: 4, border: '1px solid #dadce0', background: '#fff', color: '#5f6368', fontSize: 13, fontWeight: 600, cursor: hasChanges ? 'pointer' : 'default' }}
              >
                Reset
              </button>
              <button
                onClick={handleSave} disabled={saving || !hasChanges}
                style={{ padding: '10px 20px', borderRadius: 4, border: 'none', background: hasChanges ? '#10b981' : '#9ca3af', color: '#fff', fontSize: 13, fontWeight: 700, cursor: hasChanges ? 'pointer' : 'default' }}
              >
                {saving ? 'Saving…' : 'Save All'}
              </button>
            </div>
          </>
        )}

        {!loaded && !loading && (
          <div style={{ padding: 50, textAlign: 'center', color: '#5f6368', fontSize: 13.5, marginTop: 20, border: '1px solid #dadce0', borderRadius: 8 }}>
            Select a plant, a unit/item, and a month range, then click <strong>Load</strong>.
          </div>
        )}
      </div>
    </div>
  );
}

export default function ProductionRangeEntryPage() {
  return (
    <RequireEditor>
      <ProductionRangeEntryInner />
    </RequireEditor>
  );
}
