'use client';

import { Fragment, useEffect, useState, useCallback } from 'react';
import GlobalNavbar from '@/components/GlobalNavbar';
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

const inputStyle = {
  padding: '7px 10px', fontSize: '10.5pt', border: '1px solid #dadce0',
  borderRadius: '6px', width: '100%', boxSizing: 'border-box',
};
const selStyle = { ...inputStyle, cursor: 'pointer' };
const labelStyle = { display: 'block', fontSize: '9pt', color: '#5f6368', marginBottom: '3px' };
const cardStyle = {
  border: '1px solid #dadce0', borderRadius: '8px', padding: '16px', marginBottom: '16px',
  backgroundColor: '#ffffff',
};

function BFInner() {
  const [params, setParams] = useState([]);
  const [sailBfs, setSailBfs] = useState([]);
  const [externalBfs, setExternalBfs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');

  const [sailMeta, setSailMeta] = useState({}); // "PLANT:UNIT" -> working_volume_m3
  const [editingSailKey, setEditingSailKey] = useState(null);
  const [sailWvDraft, setSailWvDraft] = useState('');

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
      const [pRes, bRes] = await Promise.all([
        fetch(`${API}/api/bf-benchmark/params`, { credentials: 'include' }),
        fetch(`${API}/api/bf-benchmark/external-bfs`, { credentials: 'include' }),
      ]);
      const pData = await pRes.json();
      const bData = await bRes.json();
      if (!pRes.ok) throw new Error(pData.detail || 'Could not load parameters.');
      if (!bRes.ok) throw new Error(bData.detail || 'Could not load non-SAIL BFs.');
      setParams(pData.params || []);
      setSailBfs(pData.sail_bfs || []);
      setExternalBfs(bData.external_bfs || []);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { loadRegistry(); }, [loadRegistry]);

  // SAIL Working Volume comes back per-BF via /compare in the report page;
  // this entry page only writes it, so seed the display from a lightweight
  // compare call over the current month for the 3 fixed SAIL BFs.
  useEffect(() => {
    if (sailBfs.length === 0) return;
    const thisMonth = new Date().toISOString().slice(0, 7);
    fetch(`${API}/api/bf-benchmark/compare`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'include',
      body: JSON.stringify({
        sail_bf_keys: sailBfs.map((b) => `${b.plant}:${b.unit}`),
        months: [thisMonth],
      }),
    })
      .then((r) => (r.ok ? r.json() : null))
      .then((d) => {
        if (!d || !d.periods || d.periods.length === 0) return;
        const map = {};
        for (const row of d.periods[0].rows) {
          const [plant, unit] = row.bf_key.split(':');
          map[`${plant}:${unit}`] = row.values.working_volume_m3;
        }
        setSailMeta(map);
      })
      .catch(() => {});
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sailBfs]);

  const saveSailWv = async (plant, unit) => {
    setError(''); setNotice('');
    try {
      const res = await fetch(`${API}/api/bf-benchmark/sail-meta`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({
          plant, unit,
          working_volume_m3: sailWvDraft === '' ? null : parseFloat(sailWvDraft),
        }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Could not save Working Volume.');
      setSailMeta((m) => ({ ...m, [`${plant}:${unit}`]: sailWvDraft === '' ? null : parseFloat(sailWvDraft) }));
      setEditingSailKey(null);
      setNotice('Working Volume saved.');
    } catch (err) {
      setError(err.message);
    }
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
    <>
      <GlobalNavbar />
      <main style={{ maxWidth: '900px', margin: '0 auto', padding: '32px 20px', height: 'calc(100vh - 72px)', overflowY: 'auto' }}>
        <h1 style={{ fontSize: '20pt', marginBottom: '4px' }}>Large BF Benchmarking — Data Entry</h1>
        <p style={{ color: '#5f6368', marginBottom: '20px' }}>
          Manage non-SAIL large BFs and their per-FY figures (non-SAIL BFs only publish Financial Year totals,
          not monthly ones), plus Working Volume for SAIL&apos;s 3 large BFs.
          See the comparison at <a href="/reports/bf-benchmark">Large BF Benchmarking</a>.
        </p>

        {error && <p style={{ color: '#d93025', marginBottom: '12px' }}>{error}</p>}
        {notice && <p style={{ color: '#188038', marginBottom: '12px' }}>{notice}</p>}
        {loading ? <p>Loading…</p> : (
          <>
            {/* SAIL BF Working Volumes */}
            <div style={cardStyle}>
              <h3 style={{ marginTop: 0, fontSize: '12pt' }}>SAIL BF Working Volumes</h3>
              <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                <tbody>
                  {sailBfs.map((b) => {
                    const key = `${b.plant}:${b.unit}`;
                    const val = sailMeta[key];
                    return (
                      <tr key={key} style={{ borderBottom: '1px solid #e8eaed' }}>
                        <td style={{ padding: '6px 8px', fontWeight: 600 }}>{b.label}</td>
                        <td style={{ padding: '6px 8px' }}>
                          {editingSailKey === key ? (
                            <input
                              type="number" style={{ ...inputStyle, width: '140px', display: 'inline-block' }}
                              value={sailWvDraft} onChange={(e) => setSailWvDraft(e.target.value)}
                              placeholder="m³"
                            />
                          ) : (
                            <span>{val ?? '—'} {val != null ? 'm³' : ''}</span>
                          )}
                        </td>
                        <td style={{ padding: '6px 8px', textAlign: 'right' }}>
                          {editingSailKey === key ? (
                            <>
                              <button className="btn btn-primary" style={{ marginRight: '6px' }} onClick={() => saveSailWv(b.plant, b.unit)}>Save</button>
                              <button className="btn btn-secondary" onClick={() => setEditingSailKey(null)}>Cancel</button>
                            </>
                          ) : (
                            <button className="btn btn-secondary" onClick={() => { setEditingSailKey(key); setSailWvDraft(val ?? ''); }}>Edit</button>
                          )}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>

            {/* Non-SAIL BF registry */}
            <div style={cardStyle}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <h3 style={{ marginTop: 0, fontSize: '12pt' }}>Non-SAIL Large BFs</h3>
                {!showAddForm && (
                  <button className="btn btn-primary" onClick={() => setShowAddForm(true)}>+ Add BF</button>
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
                  <button className="btn btn-primary" onClick={addBf}>Save</button>
                  <button className="btn btn-secondary" onClick={() => { setShowAddForm(false); setNewName(''); setNewCompany(''); setNewLocation(''); }}>Cancel</button>
                </div>
              )}
              <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                <thead>
                  <tr style={{ textAlign: 'left', borderBottom: '2px solid #dadce0' }}>
                    <th style={{ padding: '6px 8px' }}>Furnace</th>
                    <th style={{ padding: '6px 8px' }}>Company</th>
                    <th style={{ padding: '6px 8px' }}>Location</th>
                    <th style={{ padding: '6px 8px' }}>Working Volume</th>
                    <th style={{ padding: '6px 8px' }}>Status</th>
                    <th style={{ padding: '6px 8px' }}></th>
                  </tr>
                </thead>
                <tbody>
                  {externalBfs.map((bf) => (
                    <Fragment key={bf.id}>
                      <tr style={{ borderBottom: '1px solid #e8eaed' }}>
                        <td style={{ padding: '6px 8px' }}>{bf.name}</td>
                        <td style={{ padding: '6px 8px' }}>{bf.company || '—'}</td>
                        <td style={{ padding: '6px 8px' }}>{bf.location || '—'}</td>
                        <td style={{ padding: '6px 8px' }}>{bf.working_volume_m3 != null ? `${bf.working_volume_m3} m³` : '—'}</td>
                        <td style={{ padding: '6px 8px' }}>{bf.active ? 'Active' : 'Inactive'}</td>
                        <td style={{ padding: '6px 8px', textAlign: 'right' }}>
                          <button className="btn btn-secondary" onClick={() => openEditBf(bf)}>Edit</button>
                        </td>
                      </tr>
                      {editingBfId === bf.id && (
                        <tr style={{ borderBottom: '1px solid #e8eaed', background: '#f8f9fa' }}>
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
                              <button className="btn btn-primary" onClick={() => saveBf(bf.id)}>Save</button>
                              <button className="btn btn-secondary" onClick={() => setEditingBfId(null)}>Cancel</button>
                            </div>
                          </td>
                        </tr>
                      )}
                    </Fragment>
                  ))}
                  {externalBfs.length === 0 && (
                    <tr><td colSpan={6} style={{ padding: '16px', textAlign: 'center', color: '#5f6368' }}>No non-SAIL BFs added yet.</td></tr>
                  )}
                </tbody>
              </table>
            </div>

            {/* FY entry */}
            <div style={cardStyle}>
              <h3 style={{ marginTop: 0, fontSize: '12pt' }}>Financial Year Entry</h3>
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
                          type="text" disabled style={{ ...inputStyle, backgroundColor: '#f1f3f4', color: '#5f6368' }}
                          value={p.key === 'fuel_rate' ? (computeFuelRate() ?? '—') : '—'}
                        />
                      </div>
                    ))}
                  </div>
                  <button className="btn btn-primary" disabled={saving} onClick={saveEntry}>
                    {saving ? 'Saving…' : `Save FY ${fy}`}
                  </button>
                </>
              ) : (
                <p style={{ color: '#5f6368' }}>Select a non-SAIL BF above to enter its FY data.</p>
              )}
            </div>
          </>
        )}
      </main>
    </>
  );
}

export default function BFBenchmarkEntryPage() {
  return (
    <RequireEditor>
      <BFInner />
    </RequireEditor>
  );
}
