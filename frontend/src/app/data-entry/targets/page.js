'use client';
import React, { useState, useCallback, useRef, useMemo } from 'react';
import Link from 'next/link';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || '';

const FY_LIST = ['2023-24', '2024-25', '2025-26', '2026-27', '2027-28', '2028-29'];

// BF / plant-level params — columns are plants
const PLANT_COLS = ['BSP', 'DSP', 'RSP', 'BSL', 'ISP', 'SAIL'];

// SMS params rendered in a separate section — columns are shops
const SMS_SECTIONS = ['Hot Metal Consumption', 'Scrap Consumption', 'TMI'];
const SMS_SHOP_ORDER = [
  'BSP SMS-2', 'BSP SMS-3',
  'DSP SMS',
  'RSP SMS-1', 'RSP SMS-2',
  'BSL SMS-1', 'BSL SMS-2',
  'ISP SMS-1',
  'SAIL',
];

// Which sections belong to the SMS div vs BF div
function isSmsSection(section) {
  return SMS_SECTIONS.includes(section);
}

// ── Sub-components ──────────────────────────────────────────────────────────

function SectionHeader({ title }) {
  return (
    <div style={{
      background: '#1e3a5f', color: '#fff', padding: '8px 12px',
      fontWeight: 700, fontSize: 14, borderRadius: '4px 4px 0 0', marginTop: 20,
    }}>
      {title}
    </div>
  );
}

function Cell({ val, readOnly, onChange, title: tip }) {
  return (
    <td style={{ padding: '3px 4px' }}>
      <input
        type="text"
        value={val}
        readOnly={readOnly}
        onChange={readOnly ? undefined : e => onChange(e.target.value)}
        title={tip || ''}
        style={{
          width: '100%', padding: '4px 6px', border: '1px solid #cbd5e1',
          borderRadius: 3, fontSize: 12, textAlign: 'right',
          background: readOnly ? '#f0fdf4' : '#fff',
          fontWeight: readOnly ? 700 : 400,
          color: readOnly ? '#166534' : '#1e293b',
          cursor: readOnly ? 'default' : 'text',
          outline: 'none',
        }}
      />
    </td>
  );
}

const TH = ({ children, style = {} }) => (
  <th style={{
    padding: '7px 6px', background: '#1e3a5f', color: '#fff',
    textAlign: 'center', fontSize: 12, minWidth: 74, ...style,
  }}>
    {children}
  </th>
);

// ── BF / Plant-level table ───────────────────────────────────────────────────
function BFTable({ sections, edits, onChange }) {
  const bfSections = sections.filter(s => !isSmsSection(s.section));

  const pivotRows = bfSections.map(sec => {
    const byLabel = {};
    for (const r of sec.rows) byLabel[r.row_label] = { param_id: r.param_id, val: edits[r.param_id] ?? '' };
    return { section: sec.section, unit: sec.unit, byLabel };
  });

  return (
    <>
      <SectionHeader title="BF / Iron-making & Energy Parameters" />
      <div style={{ overflowX: 'auto', border: '1px solid #e2e8f0', borderTop: 'none', borderRadius: '0 0 4px 4px' }}>
        <table style={{ borderCollapse: 'collapse', width: '100%', fontSize: 13 }}>
          <thead>
            <tr>
              <TH style={{ textAlign: 'left', minWidth: 200 }}>Parameter</TH>
              <TH style={{ minWidth: 70 }}>Unit</TH>
              {PLANT_COLS.map(p => (
                <TH key={p} style={p === 'SAIL' ? { background: '#166534' } : {}}>{p}</TH>
              ))}
            </tr>
          </thead>
          <tbody>
            {pivotRows.map((row, ri) => (
              <tr key={row.section} style={{ background: ri % 2 === 0 ? '#f8fafc' : '#fff', borderBottom: '1px solid #e2e8f0' }}>
                <td style={{ padding: '5px 10px', fontWeight: 600, whiteSpace: 'nowrap', fontSize: 13 }}>{row.section}</td>
                <td style={{ padding: '5px 6px', textAlign: 'center', color: '#64748b', fontStyle: 'italic', fontSize: 12, whiteSpace: 'nowrap' }}>
                  {row.unit}
                </td>
                {PLANT_COLS.map(p => {
                  const cell = row.byLabel[p];
                  if (!cell) return <td key={p} style={{ padding: '5px 6px', textAlign: 'center', color: '#cbd5e1', fontSize: 12 }}>—</td>;
                  const isSail = p === 'SAIL';
                  return (
                    <td key={p} style={{ padding: '3px 4px' }}>
                      <input
                        type="text"
                        value={cell.val}
                        onChange={e => onChange(cell.param_id, e.target.value)}
                        style={{
                          width: '100%', padding: '4px 6px', border: '1px solid #cbd5e1',
                          borderRadius: 3, fontSize: 12, textAlign: 'right', outline: 'none',
                          background: isSail ? '#f0fdf4' : '#fff',
                          fontWeight: isSail ? 700 : 400,
                          color: isSail ? '#166534' : '#1e293b',
                        }}
                      />
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p style={{ fontSize: 11, color: '#64748b', marginTop: 4 }}>
        SAIL column is editable — use <strong>Recalculate SAIL</strong> to fill from plant values, then override any value manually before saving.
      </p>
    </>
  );
}

// ── SMS / Shop-level table ────────────────────────────────────────────────────
function SMSTable({ sections, edits, computedTmi, onChange }) {
  const smsSections = sections.filter(s => isSmsSection(s.section));
  if (!smsSections.length) return null;

  // pivot: section → shop → {param_id, val}
  const pivotRows = smsSections.map(sec => {
    const isTmi = sec.section === 'TMI';
    const byShop = {};
    for (const r of sec.rows) {
      const val = isTmi && r.row_label !== 'SAIL'
        ? (computedTmi[r.param_id] ?? edits[r.param_id] ?? '')
        : (edits[r.param_id] ?? '');
      byShop[r.row_label] = { param_id: r.param_id, val, computed: isTmi };
    }
    return { section: sec.section, unit: sec.unit, byShop, isTmi };
  });

  // Only show shops that exist in the data
  const presentShops = SMS_SHOP_ORDER.filter(sh =>
    smsSections.some(s => s.rows.some(r => r.row_label === sh))
  );

  return (
    <>
      <SectionHeader title="SMS Parameters (Shop-wise)" />
      <div style={{ overflowX: 'auto', border: '1px solid #e2e8f0', borderTop: 'none', borderRadius: '0 0 4px 4px' }}>
        <table style={{ borderCollapse: 'collapse', width: '100%', fontSize: 13 }}>
          <thead>
            {/* Plant group header */}
            <tr style={{ background: '#334155', color: '#fff' }}>
              <th style={{ padding: '4px 10px', fontSize: 12 }} rowSpan={2}>Parameter</th>
              <th style={{ padding: '4px 6px', fontSize: 12 }} rowSpan={2}>Unit</th>
              <th colSpan={2} style={{ padding: '4px 6px', fontSize: 12, borderLeft: '1px solid #475569', textAlign: 'center' }}>BSP</th>
              <th colSpan={1} style={{ padding: '4px 6px', fontSize: 12, borderLeft: '1px solid #475569', textAlign: 'center' }}>DSP</th>
              <th colSpan={2} style={{ padding: '4px 6px', fontSize: 12, borderLeft: '1px solid #475569', textAlign: 'center' }}>RSP</th>
              <th colSpan={2} style={{ padding: '4px 6px', fontSize: 12, borderLeft: '1px solid #475569', textAlign: 'center' }}>BSL</th>
              <th colSpan={1} style={{ padding: '4px 6px', fontSize: 12, borderLeft: '1px solid #475569', textAlign: 'center' }}>ISP</th>
              <th colSpan={1} style={{ padding: '4px 6px', fontSize: 12, borderLeft: '1px solid #475569', background: '#166534', textAlign: 'center' }}>SAIL</th>
            </tr>
            <tr style={{ background: '#1e3a5f', color: '#fff' }}>
              {presentShops.map(sh => (
                <th key={sh} style={{
                  padding: '5px 6px', fontSize: 11, textAlign: 'center', minWidth: 72,
                  borderLeft: ['DSP SMS','RSP SMS-1','BSL SMS-1','ISP SMS-1','SAIL'].includes(sh) ? '1px solid #475569' : undefined,
                  background: sh === 'SAIL' ? '#166534' : undefined,
                }}>
                  {sh}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {pivotRows.map((row, ri) => (
              <tr key={row.section} style={{ background: ri % 2 === 0 ? '#f8fafc' : '#fff', borderBottom: '1px solid #e2e8f0' }}>
                <td style={{ padding: '5px 10px', fontWeight: 600, whiteSpace: 'nowrap', fontSize: 13 }}>{row.section}</td>
                <td style={{ padding: '5px 6px', textAlign: 'center', color: '#64748b', fontStyle: 'italic', fontSize: 12, whiteSpace: 'nowrap' }}>
                  {row.unit}
                </td>
                {presentShops.map(sh => {
                  const cell = row.byShop[sh];
                  if (!cell) return <td key={sh} style={{ padding: '5px 6px', textAlign: 'center', color: '#cbd5e1', fontSize: 12 }}>—</td>;
                  const isSail = sh === 'SAIL';
                  const isTmiShop = row.isTmi && !isSail;
                  return (
                    <td key={sh} style={{ padding: '3px 4px' }}>
                      <input
                        type="text"
                        value={cell.val}
                        readOnly={isTmiShop}
                        onChange={isTmiShop ? undefined : e => onChange(cell.param_id, e.target.value)}
                        title={isTmiShop ? 'TMI = HM + Scrap (computed live)' : isSail ? 'Editable — use Recalculate SAIL or enter manually' : ''}
                        style={{
                          width: '100%', padding: '4px 6px', border: '1px solid #cbd5e1',
                          borderRadius: 3, fontSize: 12, textAlign: 'right', outline: 'none',
                          background: (isSail || isTmiShop) ? '#f0fdf4' : '#fff',
                          fontWeight: (isSail || isTmiShop) ? 700 : 400,
                          color: (isSail || isTmiShop) ? '#166534' : '#1e293b',
                          cursor: isTmiShop ? 'default' : 'text',
                        }}
                      />
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p style={{ fontSize: 11, color: '#64748b', marginTop: 4 }}>
        TMI shop cells = HM + Scrap (computed live, read-only) · SAIL cells editable — use <strong>Recalculate SAIL</strong> to fill from shops, then override if needed.
      </p>
    </>
  );
}

// ── Main page ────────────────────────────────────────────────────────────────
export default function TechnoTargetsPage() {
  const [fy, setFy] = useState('2026-27');
  const [sections, setSections] = useState([]);
  const [edits, setEdits] = useState({});
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [status, setStatus] = useState(null);
  const [loaded, setLoaded] = useState(false);
  const loadedFy = useRef('');

  const handleLoad = useCallback(async () => {
    setLoading(true);
    setStatus(null);
    setLoaded(false);
    try {
      const res = await fetch(`${API_BASE_URL}/api/techno-targets?fy=${encodeURIComponent(fy)}`);
      if (!res.ok) throw new Error(await res.text());
      const data = await res.json();
      // Only show MAJOR group sections (all returned sections)
      setSections(data.sections || []);
      const init = {};
      for (const sec of (data.sections || [])) {
        for (const r of sec.rows) {
          init[r.param_id] = r.target == null ? '' : String(r.target);
        }
      }
      setEdits(init);
      loadedFy.current = fy;
      setLoaded(true);
    } catch (e) {
      setStatus({ type: 'error', text: String(e) });
    } finally {
      setLoading(false);
    }
  }, [fy]);

  const handleChange = useCallback((param_id, val) => {
    setEdits(prev => ({ ...prev, [param_id]: val }));
  }, []);

  // Compute shop-level TMI = HM + Scrap in real time
  const computedTmi = useMemo(() => {
    const hmSec    = sections.find(s => s.section === 'Hot Metal Consumption');
    const scrapSec = sections.find(s => s.section === 'Scrap Consumption');
    const tmiSec   = sections.find(s => s.section === 'TMI');
    if (!hmSec || !scrapSec || !tmiSec) return {};
    const result = {};
    for (const tmiRow of tmiSec.rows) {
      if (tmiRow.row_label === 'SAIL') continue;
      const hmRow    = hmSec.rows.find(r => r.row_label === tmiRow.row_label);
      const scrapRow = scrapSec.rows.find(r => r.row_label === tmiRow.row_label);
      if (!hmRow || !scrapRow) continue;
      const hm    = parseFloat(edits[hmRow.param_id]);
      const scrap = parseFloat(edits[scrapRow.param_id]);
      if (!isNaN(hm) && !isNaN(scrap)) {
        result[tmiRow.param_id] = String(Math.round((hm + scrap) * 1000) / 1000);
      }
    }
    return result;
  }, [sections, edits]);

  const [recalcLoading, setRecalcLoading] = useState(false);

  // Fetch computed SAIL values from backend and populate edits (does NOT save)
  const handleRecalcSail = async () => {
    setRecalcLoading(true);
    setStatus(null);
    try {
      // First save current plant/shop values so backend can compute from them
      const mergedEdits = { ...edits, ...computedTmi };
      const rows = Object.entries(mergedEdits).map(([param_id, target]) => ({
        param_id: Number(param_id),
        target: target === '' ? null : target,
      }));
      const saveRes = await fetch(`${API_BASE_URL}/api/techno-targets`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ fy: loadedFy.current, rows }),
      });
      if (!saveRes.ok) throw new Error(await saveRes.text());

      // Reload — now SAIL values are the computed ones from backend
      await handleLoad();
      setStatus({ type: 'success', text: 'SAIL values recalculated from plant targets. Review and adjust if needed, then Save All.' });
    } catch (e) {
      setStatus({ type: 'error', text: String(e) });
    } finally {
      setRecalcLoading(false);
    }
  };

  const handleSave = async () => {
    setSaving(true);
    setStatus(null);
    try {
      // Merge computed TMI shop values; SAIL values are saved exactly as shown (user may have overridden them)
      const mergedEdits = { ...edits, ...computedTmi };
      const rows = Object.entries(mergedEdits).map(([param_id, target]) => ({
        param_id: Number(param_id),
        target: target === '' ? null : target,
      }));
      const res = await fetch(`${API_BASE_URL}/api/techno-targets`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ fy: loadedFy.current, rows, skip_sail_compute: true }),
      });
      if (!res.ok) throw new Error(await res.text());
      const data = await res.json();
      setStatus({ type: 'success', text: `Saved ${data.saved} targets for FY ${data.fy}` });
    } catch (e) {
      setStatus({ type: 'error', text: String(e) });
    } finally {
      setSaving(false);
    }
  };

  return (
    <div style={{ fontFamily: 'IBM Plex Sans, Arial, sans-serif', maxWidth: 1200, margin: '0 auto', padding: '24px 16px' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 20 }}>
        <Link href="/data-entry" style={{ color: '#3b82f6', textDecoration: 'none', fontSize: 14 }}>
          ← Data Entry
        </Link>
        <h1 style={{ fontSize: 20, fontWeight: 700, margin: 0 }}>Techno-Economic Annual Targets</h1>
      </div>

      {/* FY Selector */}
      <div style={{ display: 'flex', gap: 10, alignItems: 'center', marginBottom: 16 }}>
        <label style={{ fontWeight: 600, fontSize: 14 }}>Financial Year:</label>
        <select value={fy} onChange={e => { setFy(e.target.value); setLoaded(false); }}
          style={{ padding: '5px 10px', borderRadius: 4, border: '1px solid #cbd5e1', fontSize: 14 }}>
          {FY_LIST.map(y => <option key={y} value={y}>{y}</option>)}
        </select>
        <button onClick={handleLoad} disabled={loading}
          style={{ padding: '6px 18px', background: '#3b82f6', color: '#fff', border: 'none', borderRadius: 4, cursor: 'pointer', fontWeight: 600, fontSize: 14 }}>
          {loading ? 'Loading…' : 'Load'}
        </button>
        {loaded && (
          <>
            <button onClick={handleRecalcSail} disabled={recalcLoading || saving}
              style={{ padding: '6px 16px', background: '#0369a1', color: '#fff', border: 'none', borderRadius: 4, cursor: 'pointer', fontWeight: 600, fontSize: 14 }}
              title="Compute SAIL values from plant targets using formula. Review and adjust before saving.">
              {recalcLoading ? 'Computing…' : '⟳ Recalculate SAIL'}
            </button>
            <button onClick={handleSave} disabled={saving || recalcLoading}
              style={{ padding: '6px 18px', background: '#16a34a', color: '#fff', border: 'none', borderRadius: 4, cursor: 'pointer', fontWeight: 600, fontSize: 14 }}>
              {saving ? 'Saving…' : 'Save All'}
            </button>
          </>
        )}
      </div>

      {/* Status */}
      {status && (
        <div style={{
          padding: '8px 14px', borderRadius: 4, marginBottom: 14, fontSize: 13,
          background: status.type === 'success' ? '#dcfce7' : '#fee2e2',
          color: status.type === 'success' ? '#166534' : '#991b1b',
          border: `1px solid ${status.type === 'success' ? '#86efac' : '#fca5a5'}`,
        }}>
          {status.text}
        </div>
      )}

      {/* Tables */}
      {loaded && (
        <>
          <BFTable sections={sections} edits={edits} onChange={handleChange} />
          <SMSTable sections={sections} edits={edits} computedTmi={computedTmi} onChange={handleChange} />
        </>
      )}

      {!loaded && !loading && (
        <p style={{ color: '#94a3b8', fontSize: 14 }}>Select a financial year and click Load to view / edit targets.</p>
      )}
    </div>
  );
}
