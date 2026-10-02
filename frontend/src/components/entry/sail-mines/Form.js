'use client';

import RequireEditor from '@/components/RequireEditor';
import React, { useState, useEffect, useCallback } from 'react';
import { EntryPage, ContextBar, Field, Status, Section, SaveButton, Loading, cellClass, entryStyles as es } from '../EntryUI';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || '';

// Must match backend/page_sail_mines.py's SAIL_MINES_SECTIONS (items only —
// Total/Yield/SAIL rows there are computed, never entered).
// kind='production' sections get an Actual + Plan (APP) input per item;
// kind='flow' sections would get Actual only, but every despatch/sales
// section now carries its own Plan too (per direct instruction), so every
// section here is currently 'production'.
//
// "Iron Ore Mines Performance" (production+despatch) and "Sales of Iron
// Ore" were REMOVED from this form (per direct instruction, 2026-08-26):
// Iron Ore Production/Despatch moved to the mine-level Iron Ore Mines
// Production & Despatch form (/data-entry/mines-production-despatch,
// 11 mines' worth of detail) — page_sail_mines.py now rolls that up to
// group level itself (db.get_iron_ore_group_rollup_monthly) instead of
// reading sail_mines_monthly's iron_ore_prod/iron_ore_despatch sections.
// Sales of Iron Ore's Auction vs Despatch channel split has no mine-level
// equivalent and currently has NO entry path at all — its report table
// will keep showing whatever was already saved in sail_mines_monthly but
// can no longer be updated for new months until a replacement entry point
// is built.
const SECTIONS = [
  { key: 'coal_prod', title: 'Coal Mines Production', kind: 'production', items: ['Raw Coking Coal', 'Thermal Coal'] },
  { key: 'washery', title: 'Washery Performance', kind: 'production', items: ['Input Raw Coal', 'Clean Coal'] },
  { key: 'coal_despatch', title: 'Despatch of Clean Coal & Thermal Coal (incl. Middlings)', kind: 'production', items: ['Clean Coal', 'Thermal'] },
  { key: 'flux_prod', title: 'Flux Production (Limestone & Dolomite)', kind: 'production', items: ['Limestone', 'Dolomite'] },
  { key: 'flux_despatch', title: 'Flux Despatch (Limestone & Dolomite)', kind: 'production', items: ['Limestone', 'Dolomite'] },
];

const keyOf = (section, item) => `${section}|${item}`;
const thisMonth = () => new Date().toISOString().slice(0, 7);

function SailMinesPageInner() {
  const [reportMonth, setReportMonth] = useState(thisMonth());
  const [saved, setSaved] = useState({});
  const [edits, setEdits] = useState({});
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [status, setStatus] = useState(null);

  const handleLoad = useCallback(async () => {
    setLoading(true);
    setStatus(null);
    try {
      const res = await fetch(`${API_BASE_URL}/api/sail-mines/monthly?report_month=${reportMonth}`);
      if (!res.ok) throw new Error((await res.json()).detail || 'Load failed');
      const json = await res.json();
      const entries = json.entries || {};
      const nextSaved = {};
      const nextEdits = {};
      SECTIONS.forEach(({ key: section, items }) => {
        items.forEach((item) => {
          const cell = entries[section]?.[item];
          const k = keyOf(section, item);
          const actual = cell?.actual ?? null;
          const plan = cell?.plan ?? null;
          nextSaved[k] = { actual, plan };
          nextEdits[k] = {
            actual: actual != null ? String(actual) : '',
            plan: plan != null ? String(plan) : '',
          };
        });
      });
      setSaved(nextSaved);
      setEdits(nextEdits);
    } catch (err) {
      setStatus({ type: 'error', text: err.message });
      setSaved({});
      setEdits({});
    } finally {
      setLoading(false);
    }
  }, [reportMonth]);

  useEffect(() => { handleLoad(); }, [handleLoad]);

  const handleChange = (section, item, field, value) => {
    const k = keyOf(section, item);
    setEdits((prev) => ({ ...prev, [k]: { ...prev[k], [field]: value } }));
  };

  const isChanged = (section, item) => {
    const k = keyOf(section, item);
    const e = edits[k] || {};
    const s = saved[k] || {};
    const sActual = s.actual != null ? String(s.actual) : '';
    const sPlan = s.plan != null ? String(s.plan) : '';
    return (e.actual ?? '') !== sActual || (e.plan ?? '') !== sPlan;
  };

  const hasChanges = () => SECTIONS.some(({ key: section, items }) => items.some((item) => isChanged(section, item)));

  const handleSave = async () => {
    setSaving(true);
    setStatus(null);
    const entries = [];
    SECTIONS.forEach(({ key: section, items }) => {
      items.forEach((item) => {
        if (!isChanged(section, item)) return;
        const e = edits[keyOf(section, item)] || {};
        const actual = e.actual === '' ? null : parseFloat(e.actual);
        const plan = e.plan === '' ? null : parseFloat(e.plan);
        if ((e.actual !== '' && Number.isNaN(actual)) || (e.plan !== '' && Number.isNaN(plan))) return;
        entries.push({ section, item, actual, plan });
      });
    });
    if (!entries.length) {
      setStatus({ type: 'error', text: 'No changes to save.' });
      setSaving(false);
      return;
    }
    try {
      const res = await fetch(`${API_BASE_URL}/api/sail-mines/monthly`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ report_month: reportMonth, entries }),
      });
      if (!res.ok) throw new Error((await res.json()).detail || 'Save failed');
      const result = await res.json();
      setStatus({ type: 'success', text: `Saved ${result.saved} value(s).` });
      await handleLoad();
    } catch (err) {
      setStatus({ type: 'error', text: `Save failed: ${err.message}` });
    } finally {
      setSaving(false);
    }
  };

  const dirty = hasChanges();
  const cellInput = (section, item, field, value, changed) => (
    <input type="number" step="any" value={value ?? ''} placeholder="–" aria-label={`${item} ${field}`}
           onChange={(ev) => handleChange(section, item, field, ev.target.value)}
           className={cellClass({ changed, filled: value !== '' && value != null })} />
  );

  return (
    <EntryPage
      title="SAIL Mines Entry — Page 4.5"
      description={<>
        Monthly Actual (and Plan, where the report shows an APP/%Fulfillment column) per item — Coal Mines Production,
        Washery, Coal Despatch, Flux Production/Despatch. The report cumulates April-&lt;report month&gt;
        from these monthly entries; Total and Yield rows are computed automatically. Iron Ore Production/Despatch now
        has its own mine-level form under Data Entry → Iron Ore Mines Production &amp; Despatch.
      </>}
    >
      <ContextBar actions={<SaveButton dirty={dirty} saving={saving} onClick={handleSave}>Save All</SaveButton>}>
        <Field label="Report month" htmlFor="sail-mines-month">
          <input id="sail-mines-month" type="month" className={es.control} value={reportMonth}
                 onChange={(e) => setReportMonth(e.target.value)} />
        </Field>
      </ContextBar>

      <Status status={status} />

      {loading && <Loading />}

      {!loading && SECTIONS.filter((s) => !s.hidden).map(({ key: section, title, kind, items, despatchSection }) => {
        const despatchDef = despatchSection ? SECTIONS.find((s) => s.key === despatchSection) : null;
        const despatchIsProduction = despatchDef?.kind === 'production';
        return (
          <Section key={section} title={title}>
            <table className={es.table}>
              <thead>
                <tr>
                  <th>Item</th>
                  <th className={es.c}>Actual ({reportMonth})</th>
                  {kind === 'production' && <th className={es.c}>Plan / APP ({reportMonth})</th>}
                  {despatchSection && <th className={es.c}>Despatch Actual ({reportMonth})</th>}
                  {despatchSection && despatchIsProduction && <th className={es.c}>Despatch Plan / APP ({reportMonth})</th>}
                </tr>
              </thead>
              <tbody>
                {items.map((item) => {
                  const changed = isChanged(section, item);
                  const e = edits[keyOf(section, item)] || {};
                  const dChanged = despatchSection && isChanged(despatchSection, item);
                  const dEdit = despatchSection ? (edits[keyOf(despatchSection, item)] || {}) : null;
                  return (
                    <tr key={item}>
                      <td className={es.itemCell}>{item}</td>
                      <td className={es.c}>{cellInput(section, item, 'actual', e.actual, changed)}</td>
                      {kind === 'production' && <td className={es.c}>{cellInput(section, item, 'plan', e.plan, changed)}</td>}
                      {despatchSection && <td className={es.c}>{cellInput(despatchSection, item, 'actual', dEdit.actual, dChanged)}</td>}
                      {despatchSection && despatchIsProduction && <td className={es.c}>{cellInput(despatchSection, item, 'plan', dEdit.plan, dChanged)}</td>}
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </Section>
        );
      })}
    </EntryPage>
  );
}

export default function SailMinesPage() {
  return (
    <RequireEditor>
      <SailMinesPageInner />
    </RequireEditor>
  );
}
