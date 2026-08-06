'use client';

import RequireEditor from '@/components/RequireEditor';

import React, { useState, useEffect, useCallback } from 'react';
import GlobalNavbar from '@/components/GlobalNavbar';

const API = process.env.NEXT_PUBLIC_API_URL || '';

const PLANTS = ['BSP', 'DSP', 'RSP', 'BSL'];

const SEL = {
  padding: '6px 10px', border: '1px solid #cbd5e1',
  borderRadius: 6, fontSize: '0.85rem', backgroundColor: '#fff',
};
const BTN = (bg, disabled) => ({
  padding: '6px 18px', backgroundColor: disabled ? '#94a3b8' : bg,
  color: '#fff', border: 'none', borderRadius: 6, fontWeight: 700,
  fontSize: '0.85rem', cursor: disabled ? 'default' : 'pointer',
});
const LABEL_STYLE = { fontSize: 13, fontWeight: 600, color: '#374151' };

function Notice({ type, text, onClose }) {
  if (!text) return null;
  const ok = type === 'success';
  const info = type === 'info';
  return (
    <div style={{
      padding: '10px 16px', borderRadius: 6, marginBottom: 14, fontSize: 14,
      display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 8,
      background: ok ? '#f0fdf4' : info ? '#eff6ff' : '#fef2f2',
      color: ok ? '#166534' : info ? '#1e40af' : '#991b1b',
      border: `1px solid ${ok ? '#86efac' : info ? '#bfdbfe' : '#fca5a5'}`,
    }}>
      <span>{text}</span>
      {onClose && (
        <button onClick={onClose} style={{
          background: 'none', border: 'none', cursor: 'pointer', fontSize: 18,
          color: 'inherit', opacity: 0.5, padding: '0 2px', lineHeight: 1,
        }}>×</button>
      )}
    </div>
  );
}

function SpecialSteelGradeClubsInner() {
  const [plant, setPlant]       = useState('RSP');
  const [products, setProducts] = useState([]);
  const [product, setProduct]   = useState('');
  const [data, setData]         = useState(null); // { ungrouped, clubs }
  const [selected, setSelected] = useState(new Set());
  const [labelInput, setLabelInput] = useState('');
  const [loading, setLoading]   = useState(false);
  const [busy, setBusy]         = useState(false);
  const [notice, setNotice]     = useState(null);

  // ── Load products whenever plant changes ──────────────────────────────────
  useEffect(() => {
    setProduct(''); setData(null); setSelected(new Set());
    fetch(`${API}/api/special-steel/products?plant=${encodeURIComponent(plant)}`)
      .then(r => r.json())
      .then(d => setProducts(d.products || []))
      .catch(e => setNotice({ type: 'error', text: `Failed to load products: ${e.message}` }));
  }, [plant]);

  // ── Load grades whenever product changes ──────────────────────────────────
  const loadGrades = useCallback(() => {
    if (!product) { setData(null); return; }
    setLoading(true); setSelected(new Set());
    fetch(`${API}/api/special-steel/grades?plant=${encodeURIComponent(plant)}&product=${encodeURIComponent(product)}`)
      .then(r => r.json())
      .then(d => setData(d))
      .catch(e => setNotice({ type: 'error', text: `Failed to load grades: ${e.message}` }))
      .finally(() => setLoading(false));
  }, [plant, product]);

  useEffect(() => { loadGrades(); }, [loadGrades]);

  const toggleGrade = (grade) => {
    setSelected(prev => {
      const next = new Set(prev);
      if (next.has(grade)) next.delete(grade); else next.add(grade);
      return next;
    });
  };

  const clubSelected = async () => {
    if (selected.size < 2) return;
    setBusy(true); setNotice(null);
    try {
      const res = await fetch(`${API}/api/special-steel/grade-clubs`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          plant, product, grades: [...selected],
          label: labelInput.trim() || undefined,
        }),
      });
      const d = await res.json();
      if (!res.ok) throw new Error(d.detail || 'Club failed');
      setNotice({ type: 'success', text: `Clubbed ${d.members.length} grades as "${d.label}".` });
      setLabelInput('');
      loadGrades();
    } catch (e) {
      setNotice({ type: 'error', text: e.message });
    } finally {
      setBusy(false);
    }
  };

  const unclub = async (grade) => {
    setBusy(true); setNotice(null);
    try {
      const res = await fetch(`${API}/api/special-steel/grade-clubs`, {
        method: 'DELETE', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ plant, product, grade }),
      });
      const d = await res.json();
      if (!res.ok) throw new Error(d.detail || 'Unclub failed');
      setNotice({ type: 'success', text: `Removed "${grade}" from its club.` });
      loadGrades();
    } catch (e) {
      setNotice({ type: 'error', text: e.message });
    } finally {
      setBusy(false);
    }
  };

  const ungroupClub = async (label) => {
    setBusy(true); setNotice(null);
    try {
      const res = await fetch(`${API}/api/special-steel/grade-clubs`, {
        method: 'DELETE', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ plant, product, label }),
      });
      const d = await res.json();
      if (!res.ok) throw new Error(d.detail || 'Ungroup failed');
      setNotice({ type: 'success', text: `Ungrouped "${label}" — ${d.ungrouped.length} grade(s) back to individual rows.` });
      loadGrades();
    } catch (e) {
      setNotice({ type: 'error', text: e.message });
    } finally {
      setBusy(false);
    }
  };

  return (
    <div style={{ height: '100vh', display: 'flex', flexDirection: 'column', overflow: 'hidden', background: '#ffffff', fontFamily: "-apple-system,BlinkMacSystemFont,'Segoe UI',Arial,sans-serif" }}>
      <GlobalNavbar />

      <div style={{ flex: 1, overflowY: 'auto', maxWidth: 1000, margin: '0 auto', padding: '22px 20px', width: '100%' }}>

        <div style={{ display: 'flex', alignItems: 'baseline', gap: 14, marginBottom: 18 }}>
          <h2 style={{ fontSize: '1.6rem', fontWeight: 700, color: '#202124', margin: 0 }}>
            Special Steel Grade Clubbing
          </h2>
          <span style={{ fontSize: 13, color: '#5f6368' }}>
            Combine near-duplicate quality grades into one report row
          </span>
        </div>

        <div style={{
          display: 'flex', gap: 10, alignItems: 'center', flexWrap: 'wrap',
          marginBottom: 18, background: '#f8fafc', border: '1px solid #e2e8f0',
          borderRadius: 8, padding: '14px 18px',
        }}>
          <label style={LABEL_STYLE}>Plant</label>
          <select value={plant} onChange={e => setPlant(e.target.value)} style={SEL}>
            {PLANTS.map(p => <option key={p}>{p}</option>)}
          </select>

          <label style={LABEL_STYLE}>Product</label>
          <select value={product} onChange={e => setProduct(e.target.value)} style={{ ...SEL, minWidth: 260 }}>
            <option value="">Select a product…</option>
            {products.map(p => <option key={p} value={p}>{p}</option>)}
          </select>

          {loading && <span style={{ fontSize: 13, color: '#5f6368' }}>Loading…</span>}
        </div>

        {notice && <Notice type={notice.type} text={notice.text} onClose={() => setNotice(null)} />}

        {data && (
          <>
            {data.clubs.length > 0 && (
              <div style={{ marginBottom: 18 }}>
                <div style={{ fontSize: 13, fontWeight: 700, color: '#202124', marginBottom: 8 }}>
                  Existing clubs ({data.clubs.length})
                </div>
                <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
                  {data.clubs.map(club => (
                    <div key={club.label} style={{
                      border: '1px solid #bfdbfe', borderRadius: 8, background: '#eff6ff',
                      padding: '10px 14px',
                    }}>
                      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 6 }}>
                        <div style={{ fontSize: 13, fontWeight: 700, color: '#1e40af' }}>
                          {club.label}
                        </div>
                        <button
                          onClick={() => ungroupClub(club.label)}
                          disabled={busy}
                          style={{
                            border: '1px solid #93c5fd', background: '#fff', color: '#1e40af',
                            borderRadius: 4, padding: '2px 10px', fontSize: 11.5, fontWeight: 600,
                            cursor: busy ? 'default' : 'pointer',
                          }}
                        >
                          Ungroup All
                        </button>
                      </div>
                      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
                        {club.members.map(m => (
                          <span key={m} style={{
                            display: 'inline-flex', alignItems: 'center', gap: 6,
                            background: '#fff', border: '1px solid #dbeafe', borderRadius: 14,
                            padding: '3px 6px 3px 10px', fontSize: 12.5, color: '#202124',
                          }}>
                            {m}
                            <button
                              onClick={() => unclub(m)}
                              disabled={busy}
                              title={`Remove "${m}" from this club`}
                              style={{
                                border: 'none', background: '#fee2e2', color: '#991b1b',
                                borderRadius: '50%', width: 18, height: 18, lineHeight: '18px',
                                fontSize: 12, cursor: busy ? 'default' : 'pointer', padding: 0,
                              }}
                            >×</button>
                          </span>
                        ))}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            <div>
              <div style={{ fontSize: 13, fontWeight: 700, color: '#202124', marginBottom: 8 }}>
                Ungrouped grades ({data.ungrouped.length}) — select 2+ to club
              </div>
              <div style={{
                border: '1px solid #e2e8f0', borderRadius: 8, padding: '10px 14px',
                display: 'flex', flexWrap: 'wrap', gap: '4px 16px', maxHeight: 320, overflowY: 'auto',
              }}>
                {data.ungrouped.map(g => (
                  <label key={g} style={{
                    display: 'inline-flex', alignItems: 'center', gap: 6,
                    fontSize: 13, color: '#202124', cursor: 'pointer', padding: '3px 0',
                  }}>
                    <input
                      type="checkbox"
                      checked={selected.has(g)}
                      onChange={() => toggleGrade(g)}
                      style={{ cursor: 'pointer' }}
                    />
                    {g}
                  </label>
                ))}
                {data.ungrouped.length === 0 && (
                  <span style={{ fontSize: 13, color: '#94a3b8' }}>Every grade here is already clubbed.</span>
                )}
              </div>

              <div style={{ display: 'flex', gap: 10, alignItems: 'center', marginTop: 14, flexWrap: 'wrap' }}>
                <input
                  type="text"
                  placeholder="Label (optional — auto-generated if left blank)"
                  value={labelInput}
                  onChange={e => setLabelInput(e.target.value)}
                  style={{ ...SEL, minWidth: 320 }}
                />
                <button
                  onClick={clubSelected}
                  disabled={selected.size < 2 || busy}
                  style={BTN('#1a73e8', selected.size < 2 || busy)}
                >
                  {busy ? 'Working…' : `Club Selected (${selected.size})`}
                </button>
              </div>
            </div>
          </>
        )}

        {!data && !loading && product === '' && (
          <p style={{ color: '#5f6368', fontSize: 14 }}>Pick a plant and product to see its quality grades.</p>
        )}
      </div>
    </div>
  );
}

export default function SpecialSteelGradeClubsPage() {
  return (
    <RequireEditor>
      <SpecialSteelGradeClubsInner />
    </RequireEditor>
  );
}
