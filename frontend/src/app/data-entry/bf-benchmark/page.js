'use client';

import { Fragment, useEffect, useState, useCallback } from 'react';
import GlobalNavbar from '@/components/GlobalNavbar';
import RequireEditor from '@/components/RequireEditor';

const API = process.env.NEXT_PUBLIC_API_URL || '';

const MONTH_NAMES_FULL = [
  'January', 'February', 'March', 'April', 'May', 'June',
  'July', 'August', 'September', 'October', 'November', 'December',
];
const MONTH_NUM = {
  January: '01', February: '02', March: '03', April: '04',
  May: '05', June: '06', July: '07', August: '08',
  September: '09', October: '10', November: '11', December: '12',
};
const YEAR_RANGE_START = 2000;
const _now = new Date();
const CURRENT_FY_END_YEAR = (_now.getMonth() >= 3 ? _now.getFullYear() : _now.getFullYear() - 1) + 1;
const YEARS = Array.from(
  { length: CURRENT_FY_END_YEAR - YEAR_RANGE_START + 1 },
  (_, i) => String(YEAR_RANGE_START + i)
).reverse();

function defaultMonthYear() {
  const d = new Date(); d.setMonth(d.getMonth() - 1);
  return { monthName: MONTH_NAMES_FULL[d.getMonth()], year: String(d.getFullYear()) };
}

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

  const [editingBfId, setEditingBfId] = useState(null);
  const [editForm, setEditForm] = useState({ name: '', company: '', workingVolume: '', active: true });

  const [selectedBfId, setSelectedBfId] = useState('');
  const { monthName: defMonth, year: defYear } = defaultMonthYear();
  const [monthName, setMonthName] = useState(defMonth);
  const [year, setYear] = useState(defYear);
  const [entryValues, setEntryValues] = useState({});
  const [hmProduction, setHmProduction] = useState('');
  const [saving, setSaving] = useState(false);

  const reportMonth = `${year}-${MONTH_NUM[monthName]}`;

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
    fetch(`${API}/api/bf-benchmark/compare`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'include',
      body: JSON.stringify({
        bf_keys: sailBfs.map((b) => `sail:${b.plant}:${b.unit}`),
        months: [reportMonth],
      }),
    })
      .then((r) => (r.ok ? r.json() : null))
      .then((d) => {
        if (!d) return;
        const map = {};
        for (const row of d.rows) {
          const [, plant, unit] = row.bf_key.split(':');
          map[`${plant}:${unit}`] = row.working_volume_m3;
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
        body: JSON.stringify({ name: newName.trim(), company: newCompany.trim() }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Could not add BF.');
      setNewName(''); setNewCompany(''); setShowAddForm(false);
      await loadRegistry();
    } catch (err) {
      setError(err.message);
    }
  };

  const openEditBf = (bf) => {
    setError('');
    setEditingBfId(bf.id);
    setEditForm({
      name: bf.name, company: bf.company || '',
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

  const loadEntry = useCallback(async (bfId, rm) => {
    if (!bfId) { setEntryValues({}); setHmProduction(''); return; }
    setError('');
    try {
      const res = await fetch(`${API}/api/bf-benchmark/external-bfs/${bfId}/entry?report_month=${rm}`, { credentials: 'include' });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Could not load entry.');
      const pd = data.param_data || {};
      setEntryValues(pd);
      setHmProduction(pd.hot_metal_production ?? '');
    } catch (err) {
      setError(err.message);
    }
  }, []);

  useEffect(() => { loadEntry(selectedBfId, reportMonth); }, [selectedBfId, reportMonth, loadEntry]);

  const saveEntry = async () => {
    if (!selectedBfId) { setError('Select a non-SAIL BF first.'); return; }
    setSaving(true); setError(''); setNotice('');
    try {
      const param_data = {};
      for (const p of params) {
        if (p.static) continue;
        const v = entryValues[p.key];
        param_data[p.key] = v === '' || v === undefined || v === null ? null : parseFloat(v);
      }
      param_data.hot_metal_production = hmProduction === '' ? null : parseFloat(hmProduction);

      const res = await fetch(`${API}/api/bf-benchmark/external-bfs/${selectedBfId}/entry`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({ report_month: reportMonth, param_data }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Could not save entry.');
      setNotice(`Saved ${reportMonth} data.`);
    } catch (err) {
      setError(err.message);
    } finally {
      setSaving(false);
    }
  };

  const dynamicParams = params.filter((p) => !p.static);

  return (
    <>
      <GlobalNavbar />
      <main style={{ maxWidth: '900px', margin: '0 auto', padding: '32px 20px', height: 'calc(100vh - 72px)', overflowY: 'auto' }}>
        <h1 style={{ fontSize: '20pt', marginBottom: '4px' }}>Large BF Benchmarking — Data Entry</h1>
        <p style={{ color: '#5f6368', marginBottom: '20px' }}>
          Manage non-SAIL large BFs and their monthly figures, plus Working Volume for SAIL&apos;s 3 large BFs.
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
                    <label style={labelStyle}>Name</label>
                    <input style={inputStyle} value={newName} onChange={(e) => setNewName(e.target.value)} placeholder="e.g. G-BF" />
                  </div>
                  <div style={{ flex: 1 }}>
                    <label style={labelStyle}>Company</label>
                    <input style={inputStyle} value={newCompany} onChange={(e) => setNewCompany(e.target.value)} placeholder="e.g. Tata Steel" />
                  </div>
                  <button className="btn btn-primary" onClick={addBf}>Save</button>
                  <button className="btn btn-secondary" onClick={() => { setShowAddForm(false); setNewName(''); setNewCompany(''); }}>Cancel</button>
                </div>
              )}
              <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                <thead>
                  <tr style={{ textAlign: 'left', borderBottom: '2px solid #dadce0' }}>
                    <th style={{ padding: '6px 8px' }}>Name</th>
                    <th style={{ padding: '6px 8px' }}>Company</th>
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
                        <td style={{ padding: '6px 8px' }}>{bf.working_volume_m3 != null ? `${bf.working_volume_m3} m³` : '—'}</td>
                        <td style={{ padding: '6px 8px' }}>{bf.active ? 'Active' : 'Inactive'}</td>
                        <td style={{ padding: '6px 8px', textAlign: 'right' }}>
                          <button className="btn btn-secondary" onClick={() => openEditBf(bf)}>Edit</button>
                        </td>
                      </tr>
                      {editingBfId === bf.id && (
                        <tr style={{ borderBottom: '1px solid #e8eaed', background: '#f8f9fa' }}>
                          <td colSpan={5} style={{ padding: '12px' }}>
                            <div style={{ display: 'flex', gap: '8px', alignItems: 'flex-end', flexWrap: 'wrap' }}>
                              <div>
                                <label style={labelStyle}>Name</label>
                                <input style={inputStyle} value={editForm.name} onChange={(e) => setEditForm((f) => ({ ...f, name: e.target.value }))} />
                              </div>
                              <div>
                                <label style={labelStyle}>Company</label>
                                <input style={inputStyle} value={editForm.company} onChange={(e) => setEditForm((f) => ({ ...f, company: e.target.value }))} />
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
                    <tr><td colSpan={5} style={{ padding: '16px', textAlign: 'center', color: '#5f6368' }}>No non-SAIL BFs added yet.</td></tr>
                  )}
                </tbody>
              </table>
            </div>

            {/* Monthly entry */}
            <div style={cardStyle}>
              <h3 style={{ marginTop: 0, fontSize: '12pt' }}>Monthly Entry</h3>
              <div style={{ display: 'flex', gap: '8px', marginBottom: '16px' }}>
                <div style={{ flex: 2 }}>
                  <label style={labelStyle}>Non-SAIL BF</label>
                  <select style={selStyle} value={selectedBfId} onChange={(e) => setSelectedBfId(e.target.value)}>
                    <option value="">Select a BF…</option>
                    {externalBfs.filter((b) => b.active).map((b) => (
                      <option key={b.id} value={b.id}>{b.name}{b.company ? ` (${b.company})` : ''}</option>
                    ))}
                  </select>
                </div>
                <div>
                  <label style={labelStyle}>Month</label>
                  <select style={selStyle} value={monthName} onChange={(e) => setMonthName(e.target.value)}>
                    {MONTH_NAMES_FULL.map((m) => <option key={m} value={m}>{m}</option>)}
                  </select>
                </div>
                <div>
                  <label style={labelStyle}>Year</label>
                  <select style={selStyle} value={year} onChange={(e) => setYear(e.target.value)}>
                    {YEARS.map((y) => <option key={y} value={y}>{y}</option>)}
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
                    <div>
                      <label style={labelStyle}>Hot Metal Production (used to weight yearly averages)</label>
                      <input type="number" style={inputStyle} value={hmProduction} onChange={(e) => setHmProduction(e.target.value)} />
                    </div>
                  </div>
                  <button className="btn btn-primary" disabled={saving} onClick={saveEntry}>
                    {saving ? 'Saving…' : `Save ${reportMonth}`}
                  </button>
                </>
              ) : (
                <p style={{ color: '#5f6368' }}>Select a non-SAIL BF above to enter its monthly data.</p>
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
