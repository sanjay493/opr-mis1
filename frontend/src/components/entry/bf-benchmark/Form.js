'use client';

import { Fragment, useEffect, useState, useCallback } from 'react';
import { EntryPage, Status, entryStyles as es, wb } from '../EntryUI';
import RequireEditor from '@/components/RequireEditor';

const API = process.env.NEXT_PUBLIC_API_URL || '';

// Non-SAIL BFs only ever publish FY-level figures (no monthly breakdown
// exists for them), so entry is one FY at a time, not month+year.
const YEAR_RANGE_START = 2000;
const _now = new Date();
const CURRENT_FY_START = _now.getMonth() >= 3 ? _now.getFullYear() : _now.getFullYear() - 1;
const FY_START_YEARS = Array.from(
  { length: CURRENT_FY_START - YEAR_RANGE_START + 1 },
  (_, i) => YEAR_RANGE_START + i
).reverse();

function fyLabelOf(y) { return `${y}-${String((y + 1) % 100).padStart(2, '0')}`; }

// Styled to the shared workbench look (--ui-* tokens, see styles/wb.module.css)
const inputStyle = {
  padding: '7px 10px', font: '13.5px var(--ui-font)', color: 'var(--ui-text)', border: '1px solid var(--ui-border)',
  borderRadius: '4px', width: '100%', boxSizing: 'border-box', background: 'var(--ui-surface)',
};
const selStyle = { ...inputStyle, cursor: 'pointer' };
const labelStyle = { display: 'block', fontSize: '10.5px', fontWeight: 700, letterSpacing: '.05em', textTransform: 'uppercase', color: 'var(--ui-text-secondary)', marginBottom: '4px' };
const cardStyle = {
  border: '1px solid var(--ui-border)', borderRadius: 'var(--ui-radius)', padding: '14px 16px', marginBottom: '16px',
  backgroundColor: 'var(--ui-surface)',
};
const cardTitle = { margin: 0, fontSize: '14px', fontWeight: 700, color: 'var(--ui-text)' };

// Sentinel Furnace dropdown value that reveals a free-text input — plants
// blow furnaces in/out of service over time, so SAIL_BF_UNITS_BY_PLANT will
// drift; this is the escape hatch so a furnace missing from that curated
// list never blocks recording its Working Volume.
const CUSTOM_UNIT_OPTION = '__custom__';

function BFInner() {
  const [params, setParams] = useState([]);
  const [sailBfs, setSailBfs] = useState([]);
  const [externalBfs, setExternalBfs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');

  const [sailMetaRows, setSailMetaRows] = useState([]); // [{plant, unit, working_volume_m3, updated_at}]
  const [sailUnitsByPlant, setSailUnitsByPlant] = useState({});
  const [editingSailKey, setEditingSailKey] = useState(null);
  const [sailWvDraft, setSailWvDraft] = useState('');

  const [showAddSailForm, setShowAddSailForm] = useState(false);
  const [newSailPlant, setNewSailPlant] = useState('');
  const [newSailUnit, setNewSailUnit] = useState('');       // dropdown selection, or CUSTOM_UNIT_OPTION
  const [newSailUnitCustom, setNewSailUnitCustom] = useState(''); // typed name when newSailUnit === CUSTOM_UNIT_OPTION
  const [newSailWv, setNewSailWv] = useState('');

  const [showAddForm, setShowAddForm] = useState(false);
  const [newName, setNewName] = useState('');
  const [newCompany, setNewCompany] = useState('');
  const [newLocation, setNewLocation] = useState('');

  const [editingBfId, setEditingBfId] = useState(null);
  const [editForm, setEditForm] = useState({ name: '', company: '', location: '', workingVolume: '', active: true });

  const [selectedBfId, setSelectedBfId] = useState('');
  const [fy, setFy] = useState(fyLabelOf(CURRENT_FY_START));
  const [entryValues, setEntryValues] = useState({});
  const [saving, setSaving] = useState(false);

  const loadRegistry = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const [pRes, bRes, sRes] = await Promise.all([
        fetch(`${API}/api/bf-benchmark/params`, { credentials: 'include' }),
        fetch(`${API}/api/bf-benchmark/external-bfs`, { credentials: 'include' }),
        fetch(`${API}/api/bf-benchmark/sail-meta`, { credentials: 'include' }),
      ]);
      const pData = await pRes.json();
      const bData = await bRes.json();
      const sData = await sRes.json();
      if (!pRes.ok) throw new Error(pData.detail || 'Could not load parameters.');
      if (!bRes.ok) throw new Error(bData.detail || 'Could not load non-SAIL BFs.');
      if (!sRes.ok) throw new Error(sData.detail || 'Could not load SAIL BF meta.');
      setParams(pData.params || []);
      setSailBfs(pData.sail_bfs || []);
      setExternalBfs(bData.external_bfs || []);
      setSailMetaRows(sData.sail_meta || []);
      setSailUnitsByPlant(sData.units_by_plant || {});
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { loadRegistry(); }, [loadRegistry]);

  const saveSailWv = async (plant, unit, wvOverride) => {
    setError(''); setNotice('');
    const raw = wvOverride !== undefined ? wvOverride : sailWvDraft;
    const wv = raw === '' ? null : parseFloat(raw);
    try {
      const res = await fetch(`${API}/api/bf-benchmark/sail-meta`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({ plant, unit, working_volume_m3: wv }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Could not save Working Volume.');
      await loadRegistry();
      setEditingSailKey(null);
      setNotice(`Working Volume saved for ${plant} ${unit}.`);
    } catch (err) {
      setError(err.message);
    }
  };

  const addSailMeta = async () => {
    if (!newSailPlant) { setError('Select a plant.'); return; }
    const unit = newSailUnit === CUSTOM_UNIT_OPTION ? newSailUnitCustom.trim() : newSailUnit;
    if (!unit) { setError(newSailUnit === CUSTOM_UNIT_OPTION ? 'Type the furnace name.' : 'Select a furnace.'); return; }
    if (sailMetaRows.some((r) => r.plant === newSailPlant && r.unit === unit)) {
      setError(`${newSailPlant} ${unit} is already listed below — edit it there instead.`);
      return;
    }
    await saveSailWv(newSailPlant, unit, newSailWv);
    setShowAddSailForm(false);
    setNewSailPlant(''); setNewSailUnit(''); setNewSailUnitCustom(''); setNewSailWv('');
  };

  const addBf = async () => {
    if (!newName.trim()) { setError('Name is required.'); return; }
    setError('');
    try {
      const res = await fetch(`${API}/api/bf-benchmark/external-bfs`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({ name: newName.trim(), company: newCompany.trim(), location: newLocation.trim() }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Could not add BF.');
      setNewName(''); setNewCompany(''); setNewLocation(''); setShowAddForm(false);
      await loadRegistry();
    } catch (err) {
      setError(err.message);
    }
  };

  const openEditBf = (bf) => {
    setError('');
    setEditingBfId(bf.id);
    setEditForm({
      name: bf.name, company: bf.company || '', location: bf.location || '',
      workingVolume: bf.working_volume_m3 ?? '', active: bf.active,
    });
  };

  const saveBf = async (id) => {
    setError('');
    try {
      const res = await fetch(`${API}/api/bf-benchmark/external-bfs/${id}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({
          name: editForm.name.trim(),
          company: editForm.company.trim(),
          location: editForm.location.trim(),
          working_volume_m3: editForm.workingVolume === '' ? null : parseFloat(editForm.workingVolume),
          active: editForm.active,
        }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Could not update BF.');
      setEditingBfId(null);
      await loadRegistry();
    } catch (err) {
      setError(err.message);
    }
  };

  const loadEntry = useCallback(async (bfId, forFy) => {
    if (!bfId) { setEntryValues({}); return; }
    setError('');
    try {
      const res = await fetch(`${API}/api/bf-benchmark/external-bfs/${bfId}/entry?fy=${forFy}`, { credentials: 'include' });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Could not load entry.');
      setEntryValues(data.param_data || {});
    } catch (err) {
      setError(err.message);
    }
  }, []);

  useEffect(() => { loadEntry(selectedBfId, fy); }, [selectedBfId, fy, loadEntry]);

  const saveEntry = async () => {
    if (!selectedBfId) { setError('Select a non-SAIL BF first.'); return; }
    setSaving(true); setError(''); setNotice('');
    try {
      const param_data = {};
      for (const p of params) {
        if (p.static || p.computed) continue;
        const v = entryValues[p.key];
        param_data[p.key] = v === '' || v === undefined || v === null ? null : parseFloat(v);
      }

      const res = await fetch(`${API}/api/bf-benchmark/external-bfs/${selectedBfId}/entry`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({ fy, param_data }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Could not save entry.');
      setNotice(`Saved FY ${fy} data.`);
    } catch (err) {
      setError(err.message);
    } finally {
      setSaving(false);
    }
  };

  const dynamicParams = params.filter((p) => !p.static && !p.computed);
  const computedParams = params.filter((p) => !p.static && p.computed);

  // Mirrors bf_benchmark_registry.compute_fuel_rate: Coke Rate + CDI
  // required, Nut Coke Rate optional (defaults to 0).
  const computeFuelRate = () => {
    const coke = parseFloat(entryValues.coke_rate);
    const cdi = parseFloat(entryValues.cdi);
    if (Number.isNaN(coke) || Number.isNaN(cdi)) return null;
    const nut = parseFloat(entryValues.nut_coke_rate);
    return coke + cdi + (Number.isNaN(nut) ? 0 : nut);
  };

  return (
    <EntryPage
      maxWidth={960}
      title="Large BF Benchmarking — Data Entry"
      description={<>
        Manage non-SAIL large BFs and their per-FY figures (non-SAIL BFs only publish Financial Year totals,
        not monthly ones), plus Working Volume for any SAIL blast furnace.
        See the comparison at <a href="/reports/special-steel-ipt?tab=bf-benchmark">Large BF Benchmarking</a>.
      </>}
    >
        <Status status={error ? { type: 'error', text: error } : null} />
        <Status status={notice ? { type: 'success', text: notice } : null} />
        {loading ? <p className={wb.muted}>Loading…</p> : (
          <>
            {/* SAIL BF Meta (Working Volume) — every SAIL furnace, not just
                the 3 flagship ones used in the comparison below. */}
            <div style={cardStyle}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <h3 style={cardTitle}>SAIL BF Meta — Working Volume</h3>
                {!showAddSailForm && (
                  <button className={`${wb.btn} ${wb.btnPrimary}`} onClick={() => setShowAddSailForm(true)}>+ Add Furnace</button>
                )}
              </div>
              <p style={{ color: 'var(--ui-text-secondary)', fontSize: '12px', margin: '4px 0 12px' }}>
                Every furnace here can be selected on the comparison report — Working Volume also groups them into
                Large / Medium / Small there ({sailBfs.map((b) => b.label).join(', ')} are the Large class).
              </p>
              {showAddSailForm && (
                <div style={{ display: 'flex', gap: '8px', marginBottom: '12px', alignItems: 'flex-end' }}>
                  <div>
                    <label style={labelStyle}>Plant</label>
                    <select
                      style={selStyle} value={newSailPlant}
                      onChange={(e) => { setNewSailPlant(e.target.value); setNewSailUnit(''); setNewSailUnitCustom(''); }}
                    >
                      <option value="">Select…</option>
                      {Object.keys(sailUnitsByPlant).map((p) => <option key={p} value={p}>{p}</option>)}
                    </select>
                  </div>
                  <div>
                    <label style={labelStyle}>Furnace</label>
                    <select
                      style={selStyle} value={newSailUnit} disabled={!newSailPlant}
                      onChange={(e) => setNewSailUnit(e.target.value)}
                    >
                      <option value="">Select…</option>
                      {(sailUnitsByPlant[newSailPlant] || [])
                        .filter((u) => !sailMetaRows.some((r) => r.plant === newSailPlant && r.unit === u))
                        .map((u) => <option key={u} value={u}>{u}</option>)}
                      <option value={CUSTOM_UNIT_OPTION}>Other — type furnace name…</option>
                    </select>
                  </div>
                  {newSailUnit === CUSTOM_UNIT_OPTION && (
                    <div>
                      <label style={labelStyle}>Furnace Name</label>
                      <input
                        style={{ ...inputStyle, width: '140px' }}
                        value={newSailUnitCustom} onChange={(e) => setNewSailUnitCustom(e.target.value)}
                        placeholder="e.g. BF-6" autoFocus
                      />
                    </div>
                  )}
                  <div>
                    <label style={labelStyle}>Working Volume (m³)</label>
                    <input
                      type="number" style={{ ...inputStyle, width: '140px' }}
                      value={newSailWv} onChange={(e) => setNewSailWv(e.target.value)} placeholder="m³"
                    />
                  </div>
                  <button className={`${wb.btn} ${wb.btnPrimary}`} onClick={addSailMeta}>Save</button>
                  <button
                    className={wb.btn}
                    onClick={() => {
                      setShowAddSailForm(false);
                      setNewSailPlant(''); setNewSailUnit(''); setNewSailUnitCustom(''); setNewSailWv('');
                    }}
                  >
                    Cancel
                  </button>
                </div>
              )}
              <div className={es.tableWrap} style={{ border: '1px solid var(--ui-border-subtle)', borderRadius: 6 }}><table className={es.table}>
                <thead>
                  <tr>
                    <th>Plant</th>
                    <th>Furnace</th>
                    <th>Working Volume</th>
                    <th></th>
                  </tr>
                </thead>
                <tbody>
                  {sailMetaRows.map((r) => {
                    const key = `${r.plant}:${r.unit}`;
                    return (
                      <tr key={key}>
                        <td>{r.plant}</td>
                        <td className={es.itemCell}>{r.unit}</td>
                        <td>
                          {editingSailKey === key ? (
                            <input
                              type="number" style={{ ...inputStyle, width: '140px', display: 'inline-block' }}
                              value={sailWvDraft} onChange={(e) => setSailWvDraft(e.target.value)}
                              placeholder="m³"
                            />
                          ) : (
                            <span>{r.working_volume_m3 ?? '—'} {r.working_volume_m3 != null ? 'm³' : ''}</span>
                          )}
                        </td>
                        <td className={es.r}>
                          {editingSailKey === key ? (
                            <>
                              <button className={`${wb.btn} ${wb.btnPrimary}`} style={{ marginRight: '6px' }} onClick={() => saveSailWv(r.plant, r.unit)}>Save</button>
                              <button className={wb.btn} onClick={() => setEditingSailKey(null)}>Cancel</button>
                            </>
                          ) : (
                            <button className={wb.btn} onClick={() => { setEditingSailKey(key); setSailWvDraft(r.working_volume_m3 ?? ''); }}>Edit</button>
                          )}
                        </td>
                      </tr>
                    );
                  })}
                  {sailMetaRows.length === 0 && (
                    <tr><td colSpan={4} style={{ padding: '16px', textAlign: 'center', color: 'var(--ui-text-secondary)' }}>No SAIL BF meta recorded yet.</td></tr>
                  )}
                </tbody>
              </table></div>
            </div>

            {/* Non-SAIL BF registry */}
            <div style={cardStyle}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <h3 style={cardTitle}>Non-SAIL Large BFs</h3>
                {!showAddForm && (
                  <button className={`${wb.btn} ${wb.btnPrimary}`} onClick={() => setShowAddForm(true)}>+ Add BF</button>
                )}
              </div>
              {showAddForm && (
                <div style={{ display: 'flex', gap: '8px', marginBottom: '12px', alignItems: 'flex-end' }}>
                  <div style={{ flex: 1 }}>
                    <label style={labelStyle}>Furnace Name</label>
                    <input style={inputStyle} value={newName} onChange={(e) => setNewName(e.target.value)} placeholder="e.g. BF-1" />
                  </div>
                  <div style={{ flex: 1 }}>
                    <label style={labelStyle}>Company</label>
                    <input style={inputStyle} value={newCompany} onChange={(e) => setNewCompany(e.target.value)} placeholder="e.g. JSW" />
                  </div>
                  <div style={{ flex: 1 }}>
                    <label style={labelStyle}>Location</label>
                    <input style={inputStyle} value={newLocation} onChange={(e) => setNewLocation(e.target.value)} placeholder="e.g. Vijaynagar" />
                  </div>
                  <button className={`${wb.btn} ${wb.btnPrimary}`} onClick={addBf}>Save</button>
                  <button className={wb.btn} onClick={() => { setShowAddForm(false); setNewName(''); setNewCompany(''); setNewLocation(''); }}>Cancel</button>
                </div>
              )}
              <div className={es.tableWrap} style={{ border: '1px solid var(--ui-border-subtle)', borderRadius: 6 }}><table className={es.table}>
                <thead>
                  <tr>
                    <th>Furnace</th>
                    <th>Company</th>
                    <th>Location</th>
                    <th>Working Volume</th>
                    <th>Status</th>
                    <th></th>
                  </tr>
                </thead>
                <tbody>
                  {externalBfs.map((bf) => (
                    <Fragment key={bf.id}>
                      <tr>
                        <td>{bf.name}</td>
                        <td>{bf.company || '—'}</td>
                        <td>{bf.location || '—'}</td>
                        <td>{bf.working_volume_m3 != null ? `${bf.working_volume_m3} m³` : '—'}</td>
                        <td>{bf.active ? 'Active' : 'Inactive'}</td>
                        <td className={es.r}>
                          <button className={wb.btn} onClick={() => openEditBf(bf)}>Edit</button>
                        </td>
                      </tr>
                      {editingBfId === bf.id && (
                        <tr style={{ background: 'var(--ui-bg-subtle)' }}>
                          <td colSpan={6} style={{ padding: '12px' }}>
                            <div style={{ display: 'flex', gap: '8px', alignItems: 'flex-end', flexWrap: 'wrap' }}>
                              <div>
                                <label style={labelStyle}>Furnace Name</label>
                                <input style={inputStyle} value={editForm.name} onChange={(e) => setEditForm((f) => ({ ...f, name: e.target.value }))} />
                              </div>
                              <div>
                                <label style={labelStyle}>Company</label>
                                <input style={inputStyle} value={editForm.company} onChange={(e) => setEditForm((f) => ({ ...f, company: e.target.value }))} />
                              </div>
                              <div>
                                <label style={labelStyle}>Location</label>
                                <input style={inputStyle} value={editForm.location} onChange={(e) => setEditForm((f) => ({ ...f, location: e.target.value }))} />
                              </div>
                              <div>
                                <label style={labelStyle}>Working Volume (m³)</label>
                                <input type="number" style={inputStyle} value={editForm.workingVolume} onChange={(e) => setEditForm((f) => ({ ...f, workingVolume: e.target.value }))} />
                              </div>
                              <label style={{ ...labelStyle, display: 'flex', alignItems: 'center', gap: '4px' }}>
                                <input type="checkbox" checked={editForm.active} onChange={(e) => setEditForm((f) => ({ ...f, active: e.target.checked }))} />
                                Active
                              </label>
                              <button className={`${wb.btn} ${wb.btnPrimary}`} onClick={() => saveBf(bf.id)}>Save</button>
                              <button className={wb.btn} onClick={() => setEditingBfId(null)}>Cancel</button>
                            </div>
                          </td>
                        </tr>
                      )}
                    </Fragment>
                  ))}
                  {externalBfs.length === 0 && (
                    <tr><td colSpan={6} style={{ padding: '16px', textAlign: 'center', color: 'var(--ui-text-secondary)' }}>No non-SAIL BFs added yet.</td></tr>
                  )}
                </tbody>
              </table></div>
            </div>

            {/* FY entry */}
            <div style={cardStyle}>
              <h3 style={{ ...cardTitle, marginBottom: 12 }}>Financial Year Entry</h3>
              <div style={{ display: 'flex', gap: '8px', marginBottom: '16px' }}>
                <div style={{ flex: 2 }}>
                  <label style={labelStyle}>Non-SAIL BF</label>
                  <select style={selStyle} value={selectedBfId} onChange={(e) => setSelectedBfId(e.target.value)}>
                    <option value="">Select a BF…</option>
                    {externalBfs.filter((b) => b.active).map((b) => (
                      <option key={b.id} value={b.id}>
                        {b.name}{b.company ? ` (${b.company}${b.location ? ` – ${b.location}` : ''})` : ''}
                      </option>
                    ))}
                  </select>
                </div>
                <div>
                  <label style={labelStyle}>Financial Year</label>
                  <select style={selStyle} value={fy} onChange={(e) => setFy(e.target.value)}>
                    {FY_START_YEARS.map((y) => <option key={y} value={fyLabelOf(y)}>{fyLabelOf(y)}</option>)}
                  </select>
                </div>
              </div>

              {selectedBfId ? (
                <>
                  <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '12px', marginBottom: '16px' }}>
                    {dynamicParams.map((p) => (
                      <div key={p.key}>
                        <label style={labelStyle}>{p.label} ({p.unit})</label>
                        <input
                          type="number" style={inputStyle}
                          value={entryValues[p.key] ?? ''}
                          onChange={(e) => setEntryValues((v) => ({ ...v, [p.key]: e.target.value }))}
                        />
                      </div>
                    ))}
                    {computedParams.map((p) => (
                      <div key={p.key}>
                        <label style={labelStyle}>{p.label} ({p.unit}) — auto-calculated</label>
                        <input
                          type="text" disabled style={{ ...inputStyle, backgroundColor: 'var(--ui-bg-subtle)', color: 'var(--ui-text-secondary)' }}
                          value={p.key === 'fuel_rate' ? (computeFuelRate() ?? '—') : '—'}
                        />
                      </div>
                    ))}
                  </div>
                  <button className={`${wb.btn} ${wb.btnSuccess}`} disabled={saving} onClick={saveEntry}>
                    {saving ? 'Saving…' : `Save FY ${fy}`}
                  </button>
                </>
              ) : (
                <p className={wb.muted}>Select a non-SAIL BF above to enter its FY data.</p>
              )}
            </div>
          </>
        )}
    </EntryPage>
  );
}

export default function BFBenchmarkEntryPage() {
  return (
    <RequireEditor>
      <BFInner />
    </RequireEditor>
  );
}
