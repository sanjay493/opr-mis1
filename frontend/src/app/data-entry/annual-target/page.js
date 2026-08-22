'use client';

import RequireEditor from '@/components/RequireEditor';
import React, { useState, useEffect, useCallback } from 'react';
import GlobalNavbar from '@/components/GlobalNavbar';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || '';

const FY_LIST = ['2023-24', '2024-25', '2025-26', '2026-27', '2027-28', '2028-29'];
// Labels use the printed PDF page numbers (as seen in the report/footer),
// which run +3 ahead of the internal `page` id used by the API from this
// point on (two front-matter sentinel pages, 2.5 and 3.5, plus the 29.5
// Iron Making contd. page, push everything from page 30 onward up by 3).
const PAGES = [
  { page: 28, label: 'Page 30 — Coke Ovens & Sinter' },
  { page: 29, label: 'Page 31 — Iron Making' },
  { page: 29.5, label: 'Page 32 (contd.) — Iron Making' },
  { page: 30, label: 'Page 33 — SMS Shop' },
  { page: 31, label: 'Page 34 — Mill Wise (BSP)' },
  { page: 32, label: 'Page 35 — Mill Wise (DSP)' },
  { page: 33, label: 'Page 36 — Mill Wise (RSP)' },
  { page: 34, label: 'Page 37 — Mill Wise (BSL)' },
  { page: 35, label: 'Page 38 — Mill Wise (ISP)' },
  // Not a real report page id (unlike every entry above, which is the
  // exact same integer/float main.py uses for that actual page) — Imported
  // Coal/Imported Soft Coal in Blend targets live on the Key Parameters
  // page instead, a per-plant table with no target column of its own for
  // any OTHER row, so they get their own small fixed 2-param schema here
  // rather than being folded into either this page's discovered-from-data
  // mechanism or page 27's targets page (neither fits: this one has no
  // SAIL column by design, and page 27's schema is keyed off param labels
  // that already mean something specific there).
  { page: 'coal-blend', label: 'Coal Blend %' },
];

const COAL_BLEND_SECTIONS = [
  { kind: 'total', label: 'Imported Coking Coal in Blend' },
  { kind: 'soft',  label: 'Imported Soft Coking Coal in Blend' },
];
const COAL_BLEND_PLANTS = ['BSP', 'DSP', 'RSP', 'BSL', 'ISP', 'SAIL'];

const keyOf = (col) => `${col.plant}|${col.unit}|${col.param_key}`;

function TechnoPageTargetsPageInner() {
  const [fy, setFy] = useState('2026-27');
  const [page, setPage] = useState(28);
  const [data, setData] = useState(null);
  const [edits, setEdits] = useState({});
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [status, setStatus] = useState(null);

  const handleLoad = useCallback(async () => {
    setLoading(true);
    setStatus(null);
    try {
      let json;
      if (page === 'coal-blend') {
        const res = await fetch(`${API_BASE_URL}/api/coal-blend-targets?fy=${encodeURIComponent(fy)}`);
        if (!res.ok) throw new Error((await res.json()).detail || 'Load failed');
        const raw = await res.json();
        json = {
          sections: COAL_BLEND_SECTIONS.map(({ kind, label }) => ({
            label,
            unit: '%',
            columns: COAL_BLEND_PLANTS.map((plant) => ({
              plant, unit: 'Coal_Consumption', param_key: kind, label: plant,
              target: raw.targets?.[plant]?.[kind] ?? null,
            })),
          })),
        };
      } else {
        const res = await fetch(`${API_BASE_URL}/api/techno-page-targets?page=${page}&fy=${encodeURIComponent(fy)}`);
        if (!res.ok) throw new Error((await res.json()).detail || 'Load failed');
        json = await res.json();
      }
      setData(json);
      const initial = {};
      (json.sections || []).forEach((sec) => {
        sec.columns.forEach((col) => {
          initial[keyOf(col)] = col.target != null ? String(col.target) : '';
        });
      });
      setEdits(initial);
    } catch (err) {
      setStatus({ type: 'error', text: err.message });
      setData(null);
    } finally {
      setLoading(false);
    }
  }, [page, fy]);

  useEffect(() => { handleLoad(); }, [handleLoad]);

  const handleChange = (col, value) => {
    setEdits((prev) => ({ ...prev, [keyOf(col)]: value }));
  };

  const isChanged = (col) => {
    const cur = edits[keyOf(col)] ?? '';
    const saved = col.target != null ? String(col.target) : '';
    return cur !== saved;
  };

  const hasChanges = () => (data?.sections || []).some((sec) => sec.columns.some((c) => isChanged(c)));

  const handleSave = async () => {
    setSaving(true);
    setStatus(null);
    const isCoalBlend = page === 'coal-blend';
    const entries = [];
    (data?.sections || []).forEach((sec) => {
      sec.columns.forEach((col) => {
        const val = edits[keyOf(col)];
        if (val === '' || val === undefined) {
          // A field cleared back to blank from a previously-saved value is
          // a delete request, not a no-op — send value: null explicitly so
          // the backend removes the stored key. A field that was already
          // blank and stays blank has nothing to say, so it's left out of
          // the payload entirely (same as before).
          if (col.target != null) {
            entries.push(isCoalBlend
              ? { plant: col.plant, kind: col.param_key, value: null }
              : { plant: col.plant, unit: col.unit, param_key: col.param_key, unit_str: sec.unit, value: null });
          }
          return;
        }
        const num = parseFloat(val);
        if (Number.isNaN(num)) return;
        entries.push(isCoalBlend
          ? { plant: col.plant, kind: col.param_key, value: num }
          : { plant: col.plant, unit: col.unit, param_key: col.param_key, unit_str: sec.unit, value: num });
      });
    });
    if (!entries.length) {
      setStatus({ type: 'error', text: 'No values entered to save.' });
      setSaving(false);
      return;
    }
    try {
      const res = await fetch(`${API_BASE_URL}/api/${isCoalBlend ? 'coal-blend-targets' : 'techno-page-targets'}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ fy, entries }),
      });
      if (!res.ok) throw new Error((await res.json()).detail || 'Save failed');
      const result = await res.json();
      setStatus({ type: 'success', text: `Saved ${result.saved} target value(s) for FY ${fy}.` });
      await handleLoad();
    } catch (err) {
      setStatus({ type: 'error', text: `Save failed: ${err.message}` });
    } finally {
      setSaving(false);
    }
  };

  return (
    <div style={{ height: '100vh', display: 'flex', flexDirection: 'column', background: '#ffffff', fontFamily: "-apple-system,BlinkMacSystemFont,'Segoe UI',Arial,sans-serif" }}>
      <GlobalNavbar />

      <main style={{ flex: 1, overflow: 'auto', maxWidth: 1400, margin: '0 auto', padding: '22px 20px', width: '100%' }}>
        <div style={{ display: 'flex', alignItems: 'baseline', gap: 14, marginBottom: 6, flexWrap: 'wrap' }}>
          <h2 style={{ fontSize: '1.6rem', fontWeight: 700, color: '#202124', margin: 0 }}>
            Techno Targets — Pages 30-38
          </h2>
          <span style={{ fontSize: 13, color: '#5f6368' }}>
            Entered once a year per FY; shown as the "Target"/"Norm" column on the month-wise techno pages
          </span>
        </div>
        <p style={{ fontSize: 12.5, color: '#9ca3af', marginTop: 0, marginBottom: 18 }}>
          {page === 'coal-blend' ? (
            <>Shown as the "Target %" row on the <a href="/report" style={{ color: '#1a73e8' }}>Key Parameters</a> page, directly under each plant's actual — the only tab here with a SAIL column.</>
          ) : (
            <>No SAIL column here — SAIL's target on page 29 (printed) is entered separately at{' '}
              <a href="/data-entry/targets" style={{ color: '#1a73e8' }}>TE Targets</a>.
              {' '}Pages 34-38 (Mill Wise) are grouped by parameter, one column per mill unit, for the one plant that page covers.</>
          )}
        </p>

        {/* Controls */}
        <div style={{
          display: 'flex', gap: 10, alignItems: 'center', flexWrap: 'wrap',
          marginBottom: 18, border: '1px solid #dadce0', borderRadius: 8, padding: '14px 18px',
        }}>
          <label style={{ fontSize: 13, fontWeight: 600, color: '#374151' }}>Financial Year</label>
          <select value={fy} onChange={(e) => setFy(e.target.value)}
                  style={{ padding: '7px 10px', fontSize: 14, border: '1px solid #d1d5db', borderRadius: 4 }}>
            {FY_LIST.map((f) => <option key={f} value={f}>{f}</option>)}
          </select>

          <div style={{ marginLeft: 18, display: 'flex', border: '1px solid #d1d5db', borderRadius: 6, overflow: 'hidden' }}>
            {PAGES.map(({ page: p, label }) => (
              <button key={p} onClick={() => setPage(p)} style={{
                padding: '7px 16px', fontSize: 13, fontWeight: 600, border: 'none', cursor: 'pointer',
                background: page === p ? '#1a73e8' : '#fff',
                color: page === p ? '#fff' : '#374151',
              }}>{label}</button>
            ))}
          </div>

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

        {!loading && data && (data.sections || []).length === 0 && (
          <div style={{ color: '#9ca3af', fontSize: 14, padding: '50px 0', textAlign: 'center', border: '2px dashed #dadce0', borderRadius: 8 }}>
            No plant/unit data found yet for page {page} — targets can be entered once at least one month has been uploaded for this page.
          </div>
        )}

        {!loading && data && (data.sections || []).map((sec) => (
          <div key={sec.label} style={{ marginBottom: 22, border: '1px solid #dadce0', borderRadius: 8, overflow: 'hidden' }}>
            <div style={{ padding: '9px 16px', background: '#1e3a5f', color: '#fff', fontSize: 13.5, fontWeight: 700, display: 'flex', justifyContent: 'space-between' }}>
              <span>{sec.label}</span>
              <span style={{ fontWeight: 500, color: '#bcd0e8' }}>{sec.unit}</span>
            </div>
            <div style={{ overflowX: 'auto' }}>
              <table style={{ borderCollapse: 'collapse', width: '100%' }}>
                <thead>
                  <tr>
                    {sec.columns.map((col) => (
                      <th key={keyOf(col)} style={{
                        padding: '7px 12px', fontSize: 12, fontWeight: 600, color: '#374151',
                        background: '#f8fafc', borderBottom: '1px solid #dadce0', borderRight: '1px solid #eef1f4',
                        whiteSpace: 'nowrap', textAlign: 'center',
                      }}>{col.label}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  <tr>
                    {sec.columns.map((col) => {
                      const changed = isChanged(col);
                      return (
                        <td key={keyOf(col)} style={{ padding: '8px 10px', borderRight: '1px solid #eef1f4', textAlign: 'center' }}>
                          <input
                            type="number" step="any"
                            value={edits[keyOf(col)] ?? ''}
                            onChange={(e) => handleChange(col, e.target.value)}
                            placeholder="–"
                            style={{
                              width: 90, padding: '5px 6px', fontSize: 13, textAlign: 'right', borderRadius: 4,
                              border: `1px solid ${changed ? '#fbbf24' : '#d1d5db'}`,
                              background: changed ? '#fffbeb' : col.target != null ? '#f0fdf4' : '#fff',
                              color: changed ? '#92400e' : '#202124',
                            }}
                          />
                        </td>
                      );
                    })}
                  </tr>
                </tbody>
              </table>
            </div>
          </div>
        ))}
      </main>
    </div>
  );
}

export default function TechnoPageTargetsPage() {
  return (
    <RequireEditor>
      <TechnoPageTargetsPageInner />
    </RequireEditor>
  );
}
