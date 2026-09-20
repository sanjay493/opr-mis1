'use client';

import RequireEditor from '@/components/RequireEditor';
import React, { useState, useEffect, useCallback } from 'react';
import GlobalNavbar from '@/components/GlobalNavbar';

const API = process.env.NEXT_PUBLIC_API_URL || '';
const SECTIONS = ['INWARD', 'OUTWARD', 'OVERALL'];
const PLANTS = ['BSP', 'DSP', 'RSP', 'BSL', 'ISP', 'SAIL'];

function numOrNull(v) {
  const f = parseFloat(v);
  return Number.isNaN(f) ? null : f;
}
const s = (v) => (v === null || v === undefined ? '' : String(v));

function Notice({ type, text }) {
  if (!text) return null;
  const ok = type === 'success';
  return (
    <div style={{
      padding: '10px 16px', borderRadius: 6, margin: '14px 0', fontSize: 14,
      background: ok ? '#f0fdf4' : '#fef2f2', color: ok ? '#166534' : '#991b1b',
      border: `1px solid ${ok ? '#86efac' : '#fca5a5'}`,
    }}>{text}</div>
  );
}

const cellInput = {
  width: 72, padding: '4px 6px', border: '1px solid #dadce0', borderRadius: 4,
  textAlign: 'right', fontSize: 12.5,
};
const TH = { padding: '6px 6px', fontSize: 11, fontWeight: 700, color: '#5f6368', background: '#f8f9fa', borderBottom: '1px solid #dadce0', borderRight: '1px solid #eef1f4', textAlign: 'center', whiteSpace: 'nowrap' };
const TD = { padding: '3px 4px', borderRight: '1px solid #eef1f4', borderBottom: '1px solid #f1f3f4', textAlign: 'center' };

function blankMasterRow() {
  return {
    id: null, plant: 'BSP', section: 'INWARD', commodity: '', wagon_type: '',
    row_label: '', is_total: false, direction: '', freetime_hours: '',
    freetime_effective_from: '', sort_order: 0, is_active: true,
  };
}

function RakeDetentionEntryInner() {
  const [month, setMonth] = useState('2026-08');
  const [master, setMaster] = useState([]);       // full registry, as returned
  const [newRow, setNewRow] = useState(blankMasterRow());
  const [gridRows, setGridRows] = useState([]);    // master rows + value_hours for `month`
  const [summaryLabels, setSummaryLabels] = useState([]);
  const [summaryPlants, setSummaryPlants] = useState(PLANTS);
  const [summary, setSummary] = useState({});      // {period_row: {plant: value}}
  const [loading, setLoading] = useState(false);
  const [savingMaster, setSavingMaster] = useState(false);
  const [savingGrid, setSavingGrid] = useState(false);
  const [status, setStatus] = useState(null);
  const [extractFile, setExtractFile] = useState(null);
  const [extracting, setExtracting] = useState(false);
  const [extractWarnings, setExtractWarnings] = useState([]);

  const loadMaster = useCallback(async () => {
    const res = await fetch(`${API}/api/rake-detention/master`);
    if (!res.ok) throw new Error(await res.text());
    const d = await res.json();
    setMaster(d.rows);
  }, []);

  const loadGrid = useCallback(async (targetMonth) => {
    setLoading(true);
    setStatus(null);
    try {
      const res = await fetch(`${API}/api/rake-detention/grid?report_month=${encodeURIComponent(targetMonth)}`);
      if (!res.ok) throw new Error(await res.text());
      const d = await res.json();
      setGridRows(d.rows.map((r) => ({ ...r, value_hours: s(r.value_hours) })));
      setSummaryLabels(d.summary_period_rows);
      setSummaryPlants(d.summary_plants);
      const byPeriod = {};
      d.summary.forEach((r) => {
        byPeriod[r.period_row] = byPeriod[r.period_row] || {};
        byPeriod[r.period_row][r.plant] = s(r.value);
      });
      setSummary(byPeriod);
    } catch (err) {
      setStatus({ type: 'error', text: `Load failed: ${err.message}` });
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { loadMaster(); }, [loadMaster]);
  useEffect(() => { loadGrid(month); }, [month, loadGrid]);

  const setGridValue = (id, value) => setGridRows((prev) => prev.map((r) => (r.id === id ? { ...r, value_hours: value } : r)));
  const setSummaryValue = (period, plant, value) => setSummary((prev) => ({ ...prev, [period]: { ...prev[period], [plant]: value } }));

  // Alternate, faster way to fill the grid/summary below: upload the same
  // monthly PDF the Rail Movement Cell already emails out. Only fills this
  // session's in-memory state for review — nothing is saved until the
  // existing "Save Month Values" button below is clicked, same as editing
  // any cell by hand. See backend/page_rake_detention_pdf_extractor.py for
  // why a PDF row can't always be matched 1:1 by name (status !== 'ok' rows
  // are surfaced as warnings instead of silently applied).
  const extractFromPdf = async () => {
    if (!extractFile) {
      setStatus({ type: 'error', text: 'Choose a PDF file first.' });
      return;
    }
    setExtracting(true);
    setStatus(null);
    setExtractWarnings([]);
    try {
      const form = new FormData();
      form.append('file', extractFile);
      form.append('report_month', month);
      const res = await fetch(`${API}/api/rake-detention/extract-pdf`, { method: 'POST', body: form });
      if (!res.ok) throw new Error(await res.text());
      const preview = await res.json();

      const valueByMasterId = {};
      let applied = 0;
      Object.values(preview.plants || {}).forEach((sections) => {
        Object.values(sections).forEach((sec) => {
          [...sec.rows, sec.total].forEach((r) => {
            if (r && r.status === 'ok' && r.matched_master_id != null && r.monthly?.[month] !== undefined) {
              valueByMasterId[r.matched_master_id] = r.monthly[month];
              applied += 1;
            }
          });
        });
      });
      setGridRows((prev) => prev.map((r) => (
        r.id in valueByMasterId ? { ...r, value_hours: s(valueByMasterId[r.id]) } : r
      )));
      if (preview.summary) {
        setSummary((prev) => {
          const next = { ...prev };
          Object.entries(preview.summary).forEach(([code, byPlant]) => {
            next[code] = { ...next[code], ...Object.fromEntries(
              Object.entries(byPlant).map(([p, v]) => [p, s(v)])
            ) };
          });
          return next;
        });
      }
      setExtractWarnings(preview.warnings || []);
      setStatus({
        type: 'success',
        text: `Extracted ${applied} value(s) for ${month} from the PDF — review below, `
          + `then click "Save Month Values" to persist.`
          + (preview.warnings?.length ? ` ${preview.warnings.length} row(s) need attention (see below).` : ''),
      });
    } catch (err) {
      setStatus({ type: 'error', text: `Extraction failed: ${err.message}` });
    } finally {
      setExtracting(false);
    }
  };

  const saveGrid = async () => {
    setSavingGrid(true);
    setStatus(null);
    try {
      const monthly = gridRows.map((r) => ({ master_id: r.id, value_hours: numOrNull(r.value_hours) }));
      const summaryOut = [];
      summaryLabels.forEach(({ code }) => {
        summaryPlants.forEach((p) => {
          summaryOut.push({ period_row: code, plant: p, value: numOrNull(summary[code]?.[p]) });
        });
      });
      const res = await fetch(`${API}/api/rake-detention/grid`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ report_month: month, monthly, summary: summaryOut }),
      });
      if (!res.ok) throw new Error(await res.text());
      setStatus({ type: 'success', text: 'Saved.' });
      await loadGrid(month);
    } catch (err) {
      setStatus({ type: 'error', text: `Save failed: ${err.message}` });
    } finally {
      setSavingGrid(false);
    }
  };

  const saveOneMasterRow = async (row) => {
    setSavingMaster(true);
    setStatus(null);
    try {
      const res = await fetch(`${API}/api/rake-detention/master`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          ...row,
          freetime_hours: numOrNull(row.freetime_hours),
          sort_order: parseInt(row.sort_order, 10) || 0,
        }),
      });
      if (!res.ok) throw new Error(await res.text());
      setStatus({ type: 'success', text: 'Wagon type saved.' });
      await loadMaster();
      await loadGrid(month);
    } catch (err) {
      setStatus({ type: 'error', text: `Save failed: ${err.message}` });
    } finally {
      setSavingMaster(false);
    }
  };

  const addNewRow = async () => {
    if (!newRow.row_label.trim()) {
      setStatus({ type: 'error', text: 'Row label (wagon type, or total-row name) is required.' });
      return;
    }
    await saveOneMasterRow(newRow);
    setNewRow(blankMasterRow());
  };

  const deactivateRow = async (id) => {
    setSavingMaster(true);
    try {
      const res = await fetch(`${API}/api/rake-detention/master/deactivate`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ id }),
      });
      if (!res.ok) throw new Error(await res.text());
      await loadMaster();
      await loadGrid(month);
    } catch (err) {
      setStatus({ type: 'error', text: `Deactivate failed: ${err.message}` });
    } finally {
      setSavingMaster(false);
    }
  };

  const rowsByPlantSection = {};
  gridRows.forEach((r) => {
    const key = `${r.plant}|${r.section}`;
    rowsByPlantSection[key] = rowsByPlantSection[key] || [];
    rowsByPlantSection[key].push(r);
  });
  const plantsInGrid = [...new Set(gridRows.map((r) => r.plant))];

  // Existing commodities for whichever plant/section the "+ Add" row is
  // currently set to — offered as a datalist so adding a new rake/wagon
  // type under an ALREADY-existing commodity (the common case) doesn't
  // risk a typo silently creating a second, near-duplicate commodity
  // group instead of joining the real one. Free text (a genuinely new
  // commodity) still works — it's a suggestion list, not a hard choice.
  const commoditiesForNewRow = [...new Set(
    master
      .filter((r) => r.plant === newRow.plant && r.section === newRow.section && r.commodity)
      .map((r) => r.commodity)
  )];

  return (
    <div style={{ height: '100vh', overflowY: 'auto', display: 'flex', flexDirection: 'column', background: '#fff' }}>
      <GlobalNavbar />
      <div style={{ flex: 1, maxWidth: 1700, margin: '0 auto', padding: '22px 20px', width: '100%', boxSizing: 'border-box' }}>
        <h2 style={{ fontSize: '1.6rem', fontWeight: 700, color: '#202124', margin: '0 0 4px' }}>
          Details of Rakes Detention Plant Wise — Data Entry
        </h2>
        <span style={{ fontSize: 13, color: '#5f6368' }}>
          SAIL Rail Movement Cell&apos;s &quot;Average Plant Detention Report&quot;. Every figure here — including
          each section&apos;s own Total/Overall row and the Improvement summary — is entered directly, never
          computed from the others.
        </span>

        <Notice type={status?.type} text={status?.text} />

        {/* ── Wagon type registry ─────────────────────────────────────── */}
        <div style={{ marginTop: 20, border: '1px solid #dadce0', borderRadius: 8, padding: '14px 18px' }}>
          <div style={{ fontSize: 15, fontWeight: 700, color: '#1e293b', marginBottom: 8 }}>
            Wagon Types (add one for a plant here — no code change needed)
          </div>
          <div style={{ overflowX: 'auto' }}>
            <table style={{ borderCollapse: 'collapse', width: '100%' }}>
              <thead>
                <tr>
                  <th style={TH}>Plant</th><th style={TH}>Section</th>
                  <th style={{ ...TH, textAlign: 'left' }}>Commodity</th>
                  <th style={{ ...TH, textAlign: 'left' }}>Row Label</th>
                  <th style={TH}>Direction</th><th style={TH}>Freetime (hrs)</th>
                  <th style={TH}>Total row?</th><th style={TH}>Sort</th>
                  <th style={TH}>Active</th><th style={TH}></th>
                </tr>
              </thead>
              <tbody>
                {master.map((r, idx) => (
                  <tr key={r.id}>
                    <td style={TD}>
                      <select value={r.plant} onChange={(e) => setMaster((p) => p.map((x, i) => (i === idx ? { ...x, plant: e.target.value } : x)))} style={{ ...cellInput, width: 60, textAlign: 'center' }}>
                        {PLANTS.map((p) => <option key={p} value={p}>{p}</option>)}
                      </select>
                    </td>
                    <td style={TD}>
                      <select value={r.section} onChange={(e) => setMaster((p) => p.map((x, i) => (i === idx ? { ...x, section: e.target.value } : x)))} style={{ ...cellInput, width: 80, textAlign: 'center' }}>
                        {SECTIONS.map((sec) => <option key={sec} value={sec}>{sec}</option>)}
                      </select>
                    </td>
                    <td style={TD}><input value={s(r.commodity)} onChange={(e) => setMaster((p) => p.map((x, i) => (i === idx ? { ...x, commodity: e.target.value } : x)))} style={{ ...cellInput, width: 140, textAlign: 'left' }} /></td>
                    <td style={TD}><input value={s(r.row_label)} onChange={(e) => setMaster((p) => p.map((x, i) => (i === idx ? { ...x, row_label: e.target.value } : x)))} style={{ ...cellInput, width: 120, textAlign: 'left' }} /></td>
                    <td style={TD}><input value={s(r.direction)} onChange={(e) => setMaster((p) => p.map((x, i) => (i === idx ? { ...x, direction: e.target.value } : x)))} style={{ ...cellInput, width: 50, textAlign: 'center' }} /></td>
                    <td style={TD}><input value={s(r.freetime_hours)} onChange={(e) => setMaster((p) => p.map((x, i) => (i === idx ? { ...x, freetime_hours: e.target.value } : x)))} style={cellInput} /></td>
                    <td style={TD}><input type="checkbox" checked={!!r.is_total} onChange={(e) => setMaster((p) => p.map((x, i) => (i === idx ? { ...x, is_total: e.target.checked } : x)))} /></td>
                    <td style={TD}><input value={s(r.sort_order)} onChange={(e) => setMaster((p) => p.map((x, i) => (i === idx ? { ...x, sort_order: e.target.value } : x)))} style={{ ...cellInput, width: 44 }} /></td>
                    <td style={TD}>{r.is_active ? 'Yes' : 'No'}</td>
                    <td style={TD}>
                      <button onClick={() => saveOneMasterRow(r)} disabled={savingMaster} style={{ padding: '4px 10px', fontSize: 12, fontWeight: 600, background: '#10b981', color: '#fff', border: 'none', borderRadius: 4, cursor: 'pointer', marginRight: 4 }}>Save</button>
                      {r.is_active ? (
                        <button onClick={() => deactivateRow(r.id)} disabled={savingMaster} style={{ padding: '4px 10px', fontSize: 12, fontWeight: 600, background: '#ef4444', color: '#fff', border: 'none', borderRadius: 4, cursor: 'pointer' }}>Retire</button>
                      ) : null}
                    </td>
                  </tr>
                ))}
                <tr>
                  <td style={TD}>
                    <select value={newRow.plant} onChange={(e) => setNewRow((r) => ({ ...r, plant: e.target.value }))} style={{ ...cellInput, width: 60, textAlign: 'center' }}>
                      {PLANTS.map((p) => <option key={p} value={p}>{p}</option>)}
                    </select>
                  </td>
                  <td style={TD}>
                    <select value={newRow.section} onChange={(e) => setNewRow((r) => ({ ...r, section: e.target.value }))} style={{ ...cellInput, width: 80, textAlign: 'center' }}>
                      {SECTIONS.map((sec) => <option key={sec} value={sec}>{sec}</option>)}
                    </select>
                  </td>
                  <td style={TD}>
                    <input placeholder="commodity" value={newRow.commodity} list="rd-commodity-options"
                      onChange={(e) => {
                        const commodity = e.target.value;
                        setNewRow((r) => {
                          // Picking an EXISTING commodity (exact match) auto-suggests a
                          // sort_order right after that commodity's own last row, so the
                          // new wagon type lands inside its group instead of defaulting
                          // to 0 (sorts to the very top of the section — see db.py's
                          // "ORDER BY plant, section, sort_order, id"). Still editable —
                          // this is a starting guess, not a lock.
                          const siblings = master.filter((m) => m.plant === r.plant && m.section === r.section && m.commodity === commodity);
                          const suggestedSort = siblings.length
                            ? Math.max(...siblings.map((m) => Number(m.sort_order) || 0)) + 1
                            : r.sort_order;
                          return { ...r, commodity, sort_order: suggestedSort };
                        });
                      }}
                      style={{ ...cellInput, width: 140, textAlign: 'left' }} />
                    <datalist id="rd-commodity-options">
                      {commoditiesForNewRow.map((c) => <option key={c} value={c} />)}
                    </datalist>
                  </td>
                  <td style={TD}><input placeholder="wagon type" value={newRow.row_label} onChange={(e) => setNewRow((r) => ({ ...r, row_label: e.target.value, wagon_type: e.target.value }))} style={{ ...cellInput, width: 120, textAlign: 'left' }} /></td>
                  <td style={TD}><input placeholder="L-E" value={newRow.direction} onChange={(e) => setNewRow((r) => ({ ...r, direction: e.target.value }))} style={{ ...cellInput, width: 50, textAlign: 'center' }} /></td>
                  <td style={TD}><input value={newRow.freetime_hours} onChange={(e) => setNewRow((r) => ({ ...r, freetime_hours: e.target.value }))} style={cellInput} /></td>
                  <td style={TD}><input type="checkbox" checked={newRow.is_total} onChange={(e) => setNewRow((r) => ({ ...r, is_total: e.target.checked }))} /></td>
                  <td style={TD}><input value={newRow.sort_order} onChange={(e) => setNewRow((r) => ({ ...r, sort_order: e.target.value }))} style={{ ...cellInput, width: 44 }} /></td>
                  <td style={TD}>—</td>
                  <td style={TD}>
                    <button onClick={addNewRow} disabled={savingMaster} style={{ padding: '4px 10px', fontSize: 12, fontWeight: 700, background: '#6366f1', color: '#fff', border: 'none', borderRadius: 4, cursor: 'pointer' }}>+ Add</button>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>

        {/* ── Month picker ────────────────────────────────────────────── */}
        <div style={{ display: 'flex', gap: 12, alignItems: 'center', flexWrap: 'wrap', margin: '18px 0', border: '1px solid #dadce0', borderRadius: 8, padding: '14px 18px' }}>
          <label style={{ fontSize: 13, fontWeight: 600, color: '#374151' }}>Report Month</label>
          <input type="month" value={month} onChange={(e) => setMonth(e.target.value)}
            style={{ padding: '7px 10px', fontSize: 14, border: '1px solid #d1d5db', borderRadius: 4 }} />
          <button onClick={saveGrid} disabled={savingGrid || loading}
            style={{ marginLeft: 'auto', padding: '8px 22px', fontSize: 14, fontWeight: 700, background: '#10b981', color: '#fff', border: 'none', borderRadius: 6, cursor: 'pointer' }}>
            {savingGrid ? 'Saving…' : 'Save Month Values'}
          </button>
        </div>

        {/* ── PDF extraction source (alternate to typing values by hand) ── */}
        <div style={{ display: 'flex', gap: 12, alignItems: 'center', flexWrap: 'wrap', margin: '0 0 18px', border: '1px dashed #a5b4fc', borderRadius: 8, padding: '14px 18px', background: '#f5f7ff' }}>
          <label style={{ fontSize: 13, fontWeight: 600, color: '#374151' }}>
            Extract from PDF <span style={{ fontWeight: 400, color: '#5f6368' }}>
              (Rail Movement Cell&apos;s &quot;Average Plant Detention Report&quot; for {month})
            </span>
          </label>
          <input type="file" accept="application/pdf"
            onChange={(e) => setExtractFile(e.target.files?.[0] || null)}
            style={{ fontSize: 13 }} />
          <button onClick={extractFromPdf} disabled={extracting || !extractFile}
            style={{ padding: '7px 16px', fontSize: 13, fontWeight: 700, background: '#6366f1', color: '#fff', border: 'none', borderRadius: 6, cursor: 'pointer' }}>
            {extracting ? 'Extracting…' : 'Extract & Preview'}
          </button>
          {extractWarnings.length > 0 && (
            <div style={{ width: '100%', fontSize: 12.5, color: '#92400e', background: '#fffbeb', border: '1px solid #fde68a', borderRadius: 6, padding: '8px 12px' }}>
              <strong>{extractWarnings.length} row(s) need attention:</strong>
              <ul style={{ margin: '4px 0 0', paddingLeft: 18 }}>
                {extractWarnings.map((w, i) => <li key={i}>{w}</li>)}
              </ul>
            </div>
          )}
        </div>

        {loading && <div style={{ padding: 40, textAlign: 'center', color: '#5f6368' }}>Loading…</div>}

        {!loading && (
          <>
            {/* ── Monthly detail values, grouped by plant/section ───────── */}
            {plantsInGrid.map((plant) => (
              <div key={plant} style={{ marginBottom: 18 }}>
                <div style={{ fontSize: 14, fontWeight: 700, color: '#1e3a8a', margin: '10px 0 4px' }}>{plant}</div>
                {SECTIONS.map((section) => {
                  const rows = rowsByPlantSection[`${plant}|${section}`];
                  if (!rows || !rows.length) return null;
                  return (
                    <div key={section} style={{ marginBottom: 8, border: '1px solid #dadce0', borderRadius: 6, overflow: 'auto' }}>
                      <table style={{ borderCollapse: 'collapse', width: '100%' }}>
                        <thead>
                          <tr>
                            <th style={{ ...TH, textAlign: 'left' }}>{section}</th>
                            <th style={{ ...TH, textAlign: 'left' }}>Commodity</th>
                            <th style={{ ...TH, textAlign: 'left' }}>Row</th>
                            <th style={TH}>{month} value (hrs)</th>
                          </tr>
                        </thead>
                        <tbody>
                          {rows.map((r) => (
                            <tr key={r.id}>
                              <td style={TD}></td>
                              <td style={{ ...TD, textAlign: 'left' }}>{r.commodity || ''}</td>
                              <td style={{ ...TD, textAlign: 'left', fontWeight: r.is_total ? 700 : 400 }}>{r.row_label}</td>
                              <td style={TD}><input value={r.value_hours} onChange={(e) => setGridValue(r.id, e.target.value)} style={cellInput} /></td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  );
                })}
              </div>
            ))}

            {/* ── Improvement summary ───────────────────────────────────── */}
            <div style={{ marginTop: 24 }}>
              <div style={{ fontSize: 15, fontWeight: 700, color: '#1e293b', marginBottom: 8 }}>
                Improvement in Average Detention per Wagon in Hrs (Upto {month})
              </div>
              <div style={{ border: '1px solid #dadce0', borderRadius: 8, overflow: 'auto' }}>
                <table style={{ borderCollapse: 'collapse', width: '100%' }}>
                  <thead>
                    <tr>
                      <th style={{ ...TH, textAlign: 'left' }}>Period</th>
                      {summaryPlants.map((p) => <th key={p} style={TH}>{p}</th>)}
                    </tr>
                  </thead>
                  <tbody>
                    {summaryLabels.map(({ code, label }) => (
                      <tr key={code}>
                        <td style={{ ...TD, textAlign: 'left', fontWeight: 600 }}>{label}</td>
                        {summaryPlants.map((p) => (
                          <td key={p} style={TD}>
                            <input value={s(summary[code]?.[p])} onChange={(e) => setSummaryValue(code, p, e.target.value)} style={cellInput} />
                          </td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </>
        )}
      </div>
    </div>
  );
}

export default function RakeDetentionEntryPage() {
  return (
    <RequireEditor>
      <RakeDetentionEntryInner />
    </RequireEditor>
  );
}
