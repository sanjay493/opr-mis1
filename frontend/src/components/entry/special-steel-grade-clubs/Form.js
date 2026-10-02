'use client';

import RequireEditor from '@/components/RequireEditor';

import React, { useState, useEffect, useCallback } from 'react';
import { EntryPage, ContextBar, Field, Section, entryStyles as es, wb } from '../EntryUI';

const API = process.env.NEXT_PUBLIC_API_URL || '';

const PLANTS = ['BSP', 'DSP', 'RSP', 'BSL'];

function Notice({ type, text, onClose }) {
  if (!text) return null;
  const cls = type === 'success' ? wb.alertSuccess : type === 'info' ? wb.alertInfo : wb.alertError;
  return (
    <div role={type === 'error' ? 'alert' : 'status'} className={`${wb.alert} ${cls}`}
         style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 8 }}>
      <span>{text}</span>
      {onClose && (
        <button type="button" onClick={onClose} aria-label="Dismiss" style={{
          background: 'none', border: 'none', cursor: 'pointer', fontSize: 18,
          color: 'inherit', opacity: 0.6, padding: '0 2px', lineHeight: 1,
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
    <EntryPage
      maxWidth={1000}
      title="Special Steel Grade Clubbing"
      description="Combine near-duplicate quality grades into one report row."
    >
      <ContextBar actions={loading ? <span className={es.ctxNote}>Loading…</span> : null}>
        <Field label="Plant" htmlFor="gc-plant">
          <select id="gc-plant" className={es.control} value={plant} onChange={e => setPlant(e.target.value)}>
            {PLANTS.map(p => <option key={p}>{p}</option>)}
          </select>
        </Field>
        <Field label="Product" htmlFor="gc-product">
          <select id="gc-product" className={es.control} style={{ minWidth: 260 }} value={product} onChange={e => setProduct(e.target.value)}>
            <option value="">Select a product…</option>
            {products.map(p => <option key={p} value={p}>{p}</option>)}
          </select>
        </Field>
      </ContextBar>

      {notice && <Notice type={notice.type} text={notice.text} onClose={() => setNotice(null)} />}

      {data && (
        <>
          {data.clubs.length > 0 && (
            <Section title={`Existing clubs (${data.clubs.length})`} flush={false}>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
                {data.clubs.map(club => (
                  <div key={club.label} style={{
                    border: '1px solid #c7dcfa', borderRadius: 6, background: 'var(--ui-primary-subtle)', padding: '10px 14px',
                  }}>
                    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 8 }}>
                      <div style={{ fontSize: 13.5, fontWeight: 700, color: 'var(--ui-primary)' }}>{club.label}</div>
                      <button type="button" onClick={() => ungroupClub(club.label)} disabled={busy}
                              className={`${wb.btn} ${wb.btnSm}`}>Ungroup All</button>
                    </div>
                    <div className={wb.chips}>
                      {club.members.map(m => (
                        <span key={m} className={wb.chip} style={{ paddingRight: 4, color: 'var(--ui-text)' }}>
                          {m}
                          <button type="button" onClick={() => unclub(m)} disabled={busy}
                                  title={`Remove "${m}" from this club`} aria-label={`Remove ${m} from this club`}
                                  style={{
                                    border: 'none', background: 'var(--ui-danger-bg)', color: 'var(--ui-danger)',
                                    borderRadius: '50%', width: 18, height: 18, lineHeight: '18px',
                                    fontSize: 12, cursor: busy ? 'default' : 'pointer', padding: 0,
                                  }}>×</button>
                        </span>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            </Section>
          )}

          <Section title={`Ungrouped grades (${data.ungrouped.length})`} sub="Select 2 or more to club them into one report row." flush={false}>
            <div style={{
              border: '1px solid var(--ui-border-subtle)', borderRadius: 6, padding: '10px 14px',
              display: 'flex', flexWrap: 'wrap', gap: '4px 16px', maxHeight: 320, overflowY: 'auto',
            }}>
              {data.ungrouped.map(g => (
                <label key={g} style={{ display: 'inline-flex', alignItems: 'center', gap: 6, fontSize: 13, cursor: 'pointer', padding: '3px 0' }}>
                  <input type="checkbox" checked={selected.has(g)} onChange={() => toggleGrade(g)}
                         style={{ cursor: 'pointer', accentColor: 'var(--ui-primary)' }} />
                  {g}
                </label>
              ))}
              {data.ungrouped.length === 0 && (
                <span className={wb.muted} style={{ fontSize: 13 }}>Every grade here is already clubbed.</span>
              )}
            </div>

            <div style={{ display: 'flex', gap: 10, alignItems: 'center', marginTop: 14, flexWrap: 'wrap' }}>
              <input type="text" className={wb.input} style={{ width: 'auto', minWidth: 320, flex: 1 }}
                     placeholder="Label (optional — auto-generated if left blank)" aria-label="Club label"
                     value={labelInput} onChange={e => setLabelInput(e.target.value)} />
              <button type="button" onClick={clubSelected} disabled={selected.size < 2 || busy}
                      className={`${wb.btn} ${wb.btnPrimary}`}>
                {busy ? 'Working…' : `Club Selected (${selected.size})`}
              </button>
            </div>
          </Section>
        </>
      )}

      {!data && !loading && product === '' && (
        <div className={wb.empty}>Pick a plant and product to see its quality grades.</div>
      )}
    </EntryPage>
  );
}

export default function SpecialSteelGradeClubsPage() {
  return (
    <RequireEditor>
      <SpecialSteelGradeClubsInner />
    </RequireEditor>
  );
}
