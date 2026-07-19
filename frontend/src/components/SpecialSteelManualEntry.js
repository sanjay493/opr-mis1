'use client';

import { useState } from 'react';

const MONTHS = [
  'April','May','June','July','August','September',
  'October','November','December','January','February','March',
];
const MONTH_NUM = {
  January:'01', February:'02', March:'03', April:'04',
  May:'05', June:'06', July:'07', August:'08',
  September:'09', October:'10', November:'11', December:'12',
};
const YEAR_RANGE_START = 2000;
const _now = new Date();
// FY start year: Apr..Dec -> this calendar year; Jan..Mar -> previous calendar year
const CURRENT_FY_END_YEAR = (_now.getMonth() >= 3 ? _now.getFullYear() : _now.getFullYear() - 1) + 1;

// Calendar years: 2000 through the current FY's end year (covers Jan-Mar
// report months that fall in the current FY but the next calendar year).
const YEARS = Array.from(
  { length: CURRENT_FY_END_YEAR - YEAR_RANGE_START + 1 },
  (_, i) => (YEAR_RANGE_START + i).toString()
);

const PLANT_PRODUCTS = {
  BSP: ['Semis', 'Wire Rods', 'Merchant Products', 'BRM Product', 'Rails', 'Plates'],
  DSP: ['CC BILLET', 'CC Bloom', 'CC Round', 'ASP', 'Structurals', 'TMT', 'W & A'],
  RSP: ['PM PLATES', 'New PM PLATES', 'HR PLATES SSL', 'HR COILS (SALE) -HSM-2', 'Pipes, CRNO', 'SPP'],
  BSL: ['HR COIL', 'HR PLATE', 'HR SHEET', 'CR COIL/SHEET/GP GC', 'SLAB'],
  ISP: ['WR COIL', 'TMT COIL', 'TMT BAR', 'STRUCTURALS', '150 BLT', '200 BLM'],
  // Combined ASP+SSP+VISL special steel despatch — single total row per month
  SSPs: ['TOTAL SPECIAL STEEL'],
};

const PLANTS = ['BSP', 'DSP', 'RSP', 'BSL', 'ISP', 'SSPs'];

// Plants whose report has no grade breakdown — grade is always 'TOTAL'
const TOTAL_GRADE_PLANTS = new Set(['ISP', 'SSPs']);

const uid = () => Math.random().toString(36).slice(2);

function blankRow(plant) {
  const products = PLANT_PRODUCTS[plant] || [];
  return {
    _id: uid(),
    product: products[0] || '',
    quality_grade: TOTAL_GRADE_PLANTS.has(plant) ? 'TOTAL' : '',
    section: '',
    order_qty: '',
    actual_despatch: '',
  };
}

function defaultYear() {
  const d = new Date();
  return d.getMonth() >= 3 ? String(d.getFullYear()) : String(d.getFullYear() - 1);
}
function defaultMonth() {
  const d = new Date();
  d.setMonth(d.getMonth() - 1);
  return MONTHS[d.getMonth()];
}

const SEL = {
  padding: '6px 10px', border: '1px solid #cbd5e1',
  borderRadius: 6, fontSize: '0.85rem', backgroundColor: '#fff',
};
const INP = (extra = {}) => ({
  width: '100%', padding: '4px 6px', border: '1px solid #cbd5e1',
  borderRadius: 4, fontSize: '8.5pt', ...extra,
});
const BTN = (bg, disabled) => ({
  padding: '6px 18px', backgroundColor: disabled ? '#94a3b8' : bg,
  color: '#fff', border: 'none', borderRadius: 6, fontWeight: 700,
  fontSize: '0.85rem', cursor: disabled ? 'default' : 'pointer',
});
const TH = { padding: '7px 8px', fontWeight: 600, fontSize: '8pt', color: '#fff', backgroundColor: '#1e3a5f', border: '1px solid #334155' };
const TD = (bg = '#fff') => ({ padding: '3px 5px', borderBottom: '1px solid #e2e8f0', backgroundColor: bg });

export default function SpecialSteelManualEntry({ apiBase = '', defaultPlant = 'RSP' }) {
  const [plant, setPlant]   = useState(defaultPlant);
  const [month, setMonth]   = useState(defaultMonth());
  const [year, setYear]     = useState(defaultYear());
  const [rows, setRows]     = useState([]);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving]   = useState(false);
  const [status, setStatus]   = useState(null); // { type: 'success'|'error'|'info', text }
  const [loaded, setLoaded]   = useState(false);
  const [dirty, setDirty]     = useState(false);

  const reportMonth = `${year}-${MONTH_NUM[month]}`;
  const products    = PLANT_PRODUCTS[plant] || [];

  /* ── load ─────────────────────────────────────────────────────────────── */
  const handleLoad = async () => {
    if (dirty && !window.confirm('You have unsaved changes. Load and discard them?')) return;
    setLoading(true); setStatus(null);
    try {
      const res = await fetch(
        `${apiBase}/api/special-steel-manual?plant=${encodeURIComponent(plant)}&month=${encodeURIComponent(reportMonth)}`
      );
      if (!res.ok) throw new Error(await res.text());
      const data = await res.json();
      const fetched = data.rows.map(r => ({
        _id: uid(),
        product:          r.product,
        quality_grade:    r.quality_grade,
        section:          r.section,
        order_qty:        r.order_qty != null ? String(r.order_qty) : '',
        actual_despatch:  r.actual_despatch != null ? String(r.actual_despatch) : '',
      }));
      setRows(fetched.length ? fetched : [blankRow(plant)]);
      setLoaded(true); setDirty(false);
      setStatus(fetched.length
        ? { type: 'info', text: `Loaded ${fetched.length} row(s) for ${plant} · ${month} ${year}.` }
        : { type: 'info', text: `No data yet for ${plant} · ${month} ${year}. Add rows below.` });
    } catch (e) {
      setStatus({ type: 'error', text: `Load failed: ${e.message}` });
    } finally {
      setLoading(false);
    }
  };

  /* ── save ─────────────────────────────────────────────────────────────── */
  const handleSave = async () => {
    const valid = rows.filter(r => r.product.trim());
    if (!valid.length) { setStatus({ type: 'error', text: 'No rows with a product name to save.' }); return; }
    setSaving(true); setStatus(null);
    try {
      const payload = {
        plant, month: reportMonth,
        rows: valid.map(r => ({
          product:         r.product.trim(),
          quality_grade:   r.quality_grade.trim() || 'TOTAL',
          section:         r.section.trim(),
          order_qty:       r.order_qty !== '' ? parseFloat(r.order_qty) : null,
          actual_despatch: r.actual_despatch !== '' ? parseFloat(r.actual_despatch) : null,
        })),
      };
      const res = await fetch(`${apiBase}/api/special-steel-manual/save`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
      if (!res.ok) throw new Error(await res.text());
      const data = await res.json();
      setDirty(false);
      setStatus({ type: 'success', text: `Saved ${data.saved} row(s) for ${plant} · ${month} ${year}.` });
    } catch (e) {
      setStatus({ type: 'error', text: `Save failed: ${e.message}` });
    } finally {
      setSaving(false);
    }
  };

  /* ── row ops ──────────────────────────────────────────────────────────── */
  const addRow    = ()        => { setRows(p => [...p, blankRow(plant)]); setDirty(true); };
  const dupRow    = (id)      => { const r = rows.find(x => x._id === id); if (r) { setRows(p => [...p, { ...r, _id: uid() }]); setDirty(true); } };
  const deleteRow = (id)      => { setRows(p => p.filter(r => r._id !== id)); setDirty(true); };
  const updateRow = (id, f, v) => { setRows(p => p.map(r => r._id === id ? { ...r, [f]: v } : r)); setDirty(true); };

  /* ── plant/month reset ────────────────────────────────────────────────── */
  const resetSelector = (setter, val) => { setter(val); setLoaded(false); setRows([]); setDirty(false); setStatus(null); };

  /* ── status colour ───────────────────────────────────────────────────── */
  const stBg   = { success: '#dcfce7', error: '#fee2e2', info: '#eff6ff' }[status?.type] || '#f1f5f9';
  const stText = { success: '#166534', error: '#991b1b', info: '#1e40af' }[status?.type] || '#374151';

  return (
    <div style={{ marginBottom: 24, border: '1px solid #e2e8f0', borderRadius: 8, overflow: 'hidden', fontFamily: 'system-ui, sans-serif' }}>

      {/* ── header ─────────────────────────────────────────────────────── */}
      <div style={{ padding: '12px 20px', backgroundColor: '#0f4c81', color: '#fff', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <div>
          <div style={{ fontWeight: 700, fontSize: '0.92rem' }}>Special Steel — Manual Entry / Update</div>
          <div style={{ fontSize: '0.72rem', color: '#93c5fd', marginTop: 2 }}>
            Enter or revise order qty &amp; actual despatch by product and quality grade
          </div>
        </div>
        {dirty && (
          <span style={{ fontSize: '0.7rem', backgroundColor: '#d97706', color: '#fff', padding: '2px 10px', borderRadius: 99, fontWeight: 700 }}>
            Unsaved changes
          </span>
        )}
      </div>

      <div style={{ padding: 20 }}>

        {/* ── selectors ──────────────────────────────────────────────────── */}
        <div style={{ display: 'flex', gap: 12, alignItems: 'flex-end', flexWrap: 'wrap', marginBottom: 16 }}>
          {[
            { label: 'Plant', comp: (
              <select style={SEL} value={plant} onChange={e => resetSelector(setPlant, e.target.value)}>
                {PLANTS.map(p => <option key={p}>{p}</option>)}
              </select>
            )},
            { label: 'Month', comp: (
              <select style={SEL} value={month} onChange={e => resetSelector(setMonth, e.target.value)}>
                {MONTHS.map(m => <option key={m}>{m}</option>)}
              </select>
            )},
            { label: 'Year', comp: (
              <select style={SEL} value={year} onChange={e => resetSelector(setYear, e.target.value)}>
                {YEARS.map(y => <option key={y}>{y}</option>)}
              </select>
            )},
          ].map(({ label, comp }) => (
            <div key={label}>
              <div style={{ fontSize: '0.72rem', fontWeight: 600, color: '#374151', marginBottom: 4 }}>{label}</div>
              {comp}
            </div>
          ))}
          <button onClick={handleLoad} disabled={loading} style={BTN('#1e40af', loading)}>
            {loading ? 'Loading…' : loaded ? 'Reload' : 'Load Data'}
          </button>
        </div>

        {/* ── status banner ──────────────────────────────────────────────── */}
        {status && (
          <div style={{ padding: '8px 14px', backgroundColor: stBg, color: stText, borderRadius: 6, fontSize: '0.8rem', marginBottom: 14, fontWeight: 500 }}>
            {status.text}
          </div>
        )}

        {/* ── table ──────────────────────────────────────────────────────── */}
        {(loaded || rows.length > 0) ? (
          <>
            <div style={{ overflowX: 'auto' }}>
              <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '8.5pt' }}>
                <colgroup>
                  <col style={{ width: 30 }} />
                  <col style={{ width: '24%' }} />
                  <col style={{ width: '20%' }} />
                  <col style={{ width: '10%' }} />
                  <col style={{ width: '12%' }} />
                  <col style={{ width: '14%' }} />
                  <col style={{ width: 70 }} />
                </colgroup>
                <thead>
                  <tr>
                    {['#','Product','Quality / Grade','Section','Orders (T)','Actual Despatch (T)',''].map((h, i) => (
                      <th key={i} style={{ ...TH, textAlign: i >= 4 && i <= 5 ? 'right' : i === 6 ? 'center' : 'left' }}>{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {rows.map((row, idx) => {
                    const bg = idx % 2 === 0 ? '#fff' : '#f8fafc';
                    return (
                      <tr key={row._id}>
                        <td style={{ ...TD(bg), textAlign: 'center', color: '#94a3b8', fontSize: '7.5pt' }}>{idx + 1}</td>
                        {/* Product */}
                        <td style={TD(bg)}>
                          <select value={row.product} onChange={e => updateRow(row._id, 'product', e.target.value)}
                            style={INP()}>
                            {products.map(p => <option key={p} value={p}>{p}</option>)}
                            {!products.includes(row.product) && row.product &&
                              <option value={row.product}>{row.product}</option>}
                          </select>
                        </td>
                        {/* Quality / Grade */}
                        <td style={TD(bg)}>
                          <input value={row.quality_grade}
                            onChange={e => updateRow(row._id, 'quality_grade', e.target.value)}
                            placeholder={TOTAL_GRADE_PLANTS.has(plant) ? 'TOTAL' : 'e.g. E250, IS:2062'}
                            style={INP()} />
                        </td>
                        {/* Section */}
                        <td style={TD(bg)}>
                          <input value={row.section}
                            onChange={e => updateRow(row._id, 'section', e.target.value)}
                            placeholder="(opt)"
                            style={INP({ color: '#64748b' })} />
                        </td>
                        {/* Orders */}
                        <td style={TD(bg)}>
                          <input type="number" step="any" min="0" value={row.order_qty}
                            onChange={e => updateRow(row._id, 'order_qty', e.target.value)}
                            placeholder="0"
                            style={INP({ textAlign: 'right', backgroundColor: '#eff6ff', color: '#1e40af' })} />
                        </td>
                        {/* Actual */}
                        <td style={TD(bg)}>
                          <input type="number" step="any" min="0" value={row.actual_despatch}
                            onChange={e => updateRow(row._id, 'actual_despatch', e.target.value)}
                            placeholder="0"
                            style={INP({ textAlign: 'right', backgroundColor: '#f0fdf4', color: '#065f46' })} />
                        </td>
                        {/* Actions */}
                        <td style={{ ...TD(bg), textAlign: 'center', whiteSpace: 'nowrap' }}>
                          <button onClick={() => dupRow(row._id)} title="Duplicate row"
                            style={{ background: 'none', border: 'none', color: '#6366f1', cursor: 'pointer', fontSize: '13px', padding: '2px 4px' }}>⧉</button>
                          <button onClick={() => deleteRow(row._id)} title="Delete row"
                            style={{ background: 'none', border: 'none', color: '#ef4444', cursor: 'pointer', fontSize: '15px', padding: '2px 4px' }}>×</button>
                        </td>
                      </tr>
                    );
                  })}
                  {rows.length === 0 && (
                    <tr>
                      <td colSpan={7} style={{ padding: 20, textAlign: 'center', color: '#94a3b8', fontStyle: 'italic' }}>
                        No rows yet — click <strong>+ Add Row</strong> below.
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>

            {/* ── footer ─────────────────────────────────────────────────── */}
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: 10, flexWrap: 'wrap', gap: 10 }}>
              <button onClick={addRow}
                style={{ padding: '6px 16px', backgroundColor: '#e2e8f0', color: '#374151', border: 'none', borderRadius: 6, fontWeight: 600, fontSize: '0.82rem', cursor: 'pointer' }}>
                + Add Row
              </button>
              <div style={{ display: 'flex', alignItems: 'center', gap: 14 }}>
                <span style={{ fontSize: '0.72rem', color: '#64748b' }}>
                  {rows.length} row(s) · Save replaces <em>all</em> existing data for {plant} {month} {year}
                </span>
                <button onClick={handleSave} disabled={saving || !dirty} style={BTN('#10b981', saving || !dirty)}>
                  {saving ? 'Saving…' : 'Save All'}
                </button>
              </div>
            </div>
          </>
        ) : (
          <div style={{ textAlign: 'center', padding: '28px 20px', color: '#94a3b8', fontSize: '0.85rem', border: '1px dashed #e2e8f0', borderRadius: 8 }}>
            Select plant and reporting month, then click <strong>Load Data</strong> to view or edit existing entries.
          </div>
        )}
      </div>
    </div>
  );
}
