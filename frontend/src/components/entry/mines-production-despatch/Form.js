'use client';

import RequireEditor from '@/components/RequireEditor';
import React, { useState, useEffect, useCallback, useMemo } from 'react';
import { EntryPage, ContextBar, Field, Status, Section, SaveButton, Loading, cellClass, entryStyles as es } from '../EntryUI';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || '';

const thisMonth = () => new Date().toISOString().slice(0, 7);

// Despatch Actual is tracked per transport mode (Rail/Road); Despatch Plan
// is a single target per material x end-use with NO Rail/Road split (per
// direct instruction) — so they're two separate keyed maps, not one.
const despatchActualKey = (material, mode, endUse) => `${material}|${mode}|${endUse}`;
const despatchPlanKey = (material, endUse) => `${material}|${endUse}`;

// Booked Quantity — Sales to 3rd Party (implicitly SALES-only, no end-use
// dimension — booking a sale doesn't apply to Captive/Pellet Conversion).
// Same Actual-per-mode / Plan-with-no-mode-split shape as despatch.
const bookedQtyActualKey = (material, mode) => `${material}|${mode}`;

function MinesProductionDespatchPageInner() {
  const [masters, setMasters] = useState(null);      // {groups, mines, materials, end_uses, transport_modes}
  const [mastersError, setMastersError] = useState(null);
  const [mineCode, setMineCode] = useState('');
  const [reportMonth, setReportMonth] = useState(thisMonth());

  const [savedProd, setSavedProd] = useState({});     // material_code -> {actual, plan}
  const [editsProd, setEditsProd] = useState({});      // material_code -> {actual, plan} (strings)
  const [savedDesp, setSavedDesp] = useState({});      // despatchActualKey -> {actual}
  const [editsDesp, setEditsDesp] = useState({});
  const [savedDespPlan, setSavedDespPlan] = useState({}); // despatchPlanKey -> {plan}
  const [editsDespPlan, setEditsDespPlan] = useState({});
  const [savedBookedQty, setSavedBookedQty] = useState({}); // bookedQtyActualKey -> {actual}
  const [editsBookedQty, setEditsBookedQty] = useState({});
  const [savedBookedQtyPlan, setSavedBookedQtyPlan] = useState({}); // material_code -> {plan}
  const [editsBookedQtyPlan, setEditsBookedQtyPlan] = useState({});

  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [status, setStatus] = useState(null);

  // Load masters once (groups/mines/materials/end-uses are DB-backed, so
  // this reflects whatever's currently active without a frontend deploy).
  useEffect(() => {
    (async () => {
      try {
        const res = await fetch(`${API_BASE_URL}/api/mines-master`);
        if (!res.ok) throw new Error((await res.json()).detail || 'Failed to load mines master data');
        const json = await res.json();
        setMasters(json);
        const firstActive = (json.mines || []).find((m) => m.is_active);
        if (firstActive) setMineCode(firstActive.mine_code);
      } catch (err) {
        setMastersError(err.message);
      }
    })();
  }, []);

  const productionMaterials = useMemo(
    () => (masters?.materials || []).filter((m) => m.has_production),
    [masters]
  );

  const handleLoad = useCallback(async () => {
    if (!mineCode || !reportMonth) return;
    setLoading(true);
    setStatus(null);
    try {
      const res = await fetch(
        `${API_BASE_URL}/api/mines-production-despatch/monthly?report_month=${reportMonth}&mine_code=${mineCode}`
      );
      if (!res.ok) throw new Error((await res.json()).detail || 'Load failed');
      const json = await res.json();

      const nextSavedProd = {};
      const nextEditsProd = {};
      productionMaterials.forEach(({ material_code }) => {
        const cell = json.production?.[material_code];
        const actual = cell?.actual ?? null;
        const plan = cell?.plan ?? null;
        nextSavedProd[material_code] = { actual, plan };
        nextEditsProd[material_code] = { actual: actual != null ? String(actual) : '', plan: plan != null ? String(plan) : '' };
      });

      const nextSavedDesp = {};
      const nextEditsDesp = {};
      (masters.materials || []).forEach(({ material_code }) => {
        (masters.transport_modes || []).forEach(({ mode_code }) => {
          (masters.end_uses || []).forEach(({ end_use_code }) => {
            const cell = json.despatch?.[material_code]?.[mode_code]?.[end_use_code];
            const k = despatchActualKey(material_code, mode_code, end_use_code);
            const actual = cell?.actual ?? null;
            nextSavedDesp[k] = { actual };
            nextEditsDesp[k] = { actual: actual != null ? String(actual) : '' };
          });
        });
      });

      const nextSavedDespPlan = {};
      const nextEditsDespPlan = {};
      (masters.materials || []).forEach(({ material_code }) => {
        (masters.end_uses || []).forEach(({ end_use_code }) => {
          const plan = json.despatch_plan?.[material_code]?.[end_use_code] ?? null;
          const k = despatchPlanKey(material_code, end_use_code);
          nextSavedDespPlan[k] = { plan };
          nextEditsDespPlan[k] = { plan: plan != null ? String(plan) : '' };
        });
      });

      const nextSavedBookedQty = {};
      const nextEditsBookedQty = {};
      (masters.materials || []).forEach(({ material_code }) => {
        (masters.transport_modes || []).forEach(({ mode_code }) => {
          const cell = json.booked_qty?.[material_code]?.[mode_code];
          const k = bookedQtyActualKey(material_code, mode_code);
          const actual = cell?.actual ?? null;
          nextSavedBookedQty[k] = { actual };
          nextEditsBookedQty[k] = { actual: actual != null ? String(actual) : '' };
        });
      });

      const nextSavedBookedQtyPlan = {};
      const nextEditsBookedQtyPlan = {};
      (masters.materials || []).forEach(({ material_code }) => {
        const plan = json.booked_qty_plan?.[material_code] ?? null;
        nextSavedBookedQtyPlan[material_code] = { plan };
        nextEditsBookedQtyPlan[material_code] = { plan: plan != null ? String(plan) : '' };
      });

      setSavedProd(nextSavedProd);
      setEditsProd(nextEditsProd);
      setSavedDesp(nextSavedDesp);
      setEditsDesp(nextEditsDesp);
      setSavedDespPlan(nextSavedDespPlan);
      setEditsDespPlan(nextEditsDespPlan);
      setSavedBookedQty(nextSavedBookedQty);
      setEditsBookedQty(nextEditsBookedQty);
      setSavedBookedQtyPlan(nextSavedBookedQtyPlan);
      setEditsBookedQtyPlan(nextEditsBookedQtyPlan);
    } catch (err) {
      setStatus({ type: 'error', text: err.message });
      setSavedProd({}); setEditsProd({}); setSavedDesp({}); setEditsDesp({}); setSavedDespPlan({}); setEditsDespPlan({});
      setSavedBookedQty({}); setEditsBookedQty({}); setSavedBookedQtyPlan({}); setEditsBookedQtyPlan({});
    } finally {
      setLoading(false);
    }
  }, [mineCode, reportMonth, masters, productionMaterials]);

  useEffect(() => { if (masters) handleLoad(); }, [masters, handleLoad]);

  const handleProdChange = (material, field, value) =>
    setEditsProd((prev) => ({ ...prev, [material]: { ...prev[material], [field]: value } }));

  const handleDespActualChange = (material, mode, endUse, value) => {
    const k = despatchActualKey(material, mode, endUse);
    setEditsDesp((prev) => ({ ...prev, [k]: { actual: value } }));
  };

  const handleDespPlanChange = (material, endUse, value) => {
    const k = despatchPlanKey(material, endUse);
    setEditsDespPlan((prev) => ({ ...prev, [k]: { plan: value } }));
  };

  const handleBookedQtyActualChange = (material, mode, value) => {
    const k = bookedQtyActualKey(material, mode);
    setEditsBookedQty((prev) => ({ ...prev, [k]: { actual: value } }));
  };

  const handleBookedQtyPlanChange = (material, value) =>
    setEditsBookedQtyPlan((prev) => ({ ...prev, [material]: { plan: value } }));

  const isProdChanged = (material) => {
    const e = editsProd[material] || {};
    const s = savedProd[material] || {};
    return (e.actual ?? '') !== (s.actual != null ? String(s.actual) : '') || (e.plan ?? '') !== (s.plan != null ? String(s.plan) : '');
  };

  const isDespChanged = (material, mode, endUse) => {
    const k = despatchActualKey(material, mode, endUse);
    const e = editsDesp[k] || {};
    const s = savedDesp[k] || {};
    return (e.actual ?? '') !== (s.actual != null ? String(s.actual) : '');
  };

  const isDespPlanChanged = (material, endUse) => {
    const k = despatchPlanKey(material, endUse);
    const e = editsDespPlan[k] || {};
    const s = savedDespPlan[k] || {};
    return (e.plan ?? '') !== (s.plan != null ? String(s.plan) : '');
  };

  const isBookedQtyChanged = (material, mode) => {
    const k = bookedQtyActualKey(material, mode);
    const e = editsBookedQty[k] || {};
    const s = savedBookedQty[k] || {};
    return (e.actual ?? '') !== (s.actual != null ? String(s.actual) : '');
  };

  const isBookedQtyPlanChanged = (material) => {
    const e = editsBookedQtyPlan[material] || {};
    const s = savedBookedQtyPlan[material] || {};
    return (e.plan ?? '') !== (s.plan != null ? String(s.plan) : '');
  };

  const hasChanges = () =>
    productionMaterials.some(({ material_code }) => isProdChanged(material_code)) ||
    (masters?.materials || []).some(({ material_code }) =>
      (masters.transport_modes || []).some(({ mode_code }) =>
        (masters.end_uses || []).some(({ end_use_code }) => isDespChanged(material_code, mode_code, end_use_code)) ||
        isBookedQtyChanged(material_code, mode_code)
      ) ||
      (masters.end_uses || []).some(({ end_use_code }) => isDespPlanChanged(material_code, end_use_code)) ||
      isBookedQtyPlanChanged(material_code)
    );

  // Total Production (informational, computed client-side, never entered
  // directly): fresh Lump+Fines production ACTUAL + despatch ACTUAL of
  // every material flagged counts_in_total_production, per the schema's
  // derived-at-read-time convention (mirrors page_sail_mines.py's SAIL row).
  const totalProduction = useMemo(() => {
    if (!masters) return null;
    let total = 0, found = false;
    productionMaterials.forEach(({ material_code }) => {
      const v = savedProd[material_code]?.actual;
      if (v != null) { total += v; found = true; }
    });
    (masters.materials || []).filter((m) => m.counts_in_total_production && m.material_category === 'LEGACY').forEach(({ material_code }) => {
      (masters.transport_modes || []).forEach(({ mode_code }) => {
        (masters.end_uses || []).forEach(({ end_use_code }) => {
          const v = savedDesp[despatchActualKey(material_code, mode_code, end_use_code)]?.actual;
          if (v != null) { total += v; found = true; }
        });
      });
    });
    return found ? total : null;
  }, [masters, productionMaterials, savedProd, savedDesp]);

  const handleSave = async () => {
    setSaving(true);
    setStatus(null);
    const production = [];
    productionMaterials.forEach(({ material_code }) => {
      if (!isProdChanged(material_code)) return;
      const e = editsProd[material_code] || {};
      const actual = e.actual === '' ? null : parseFloat(e.actual);
      const plan = e.plan === '' ? null : parseFloat(e.plan);
      if ((e.actual !== '' && Number.isNaN(actual)) || (e.plan !== '' && Number.isNaN(plan))) return;
      production.push({ material_code, actual, plan });
    });
    const despatch = [];
    (masters.materials || []).forEach(({ material_code }) => {
      (masters.transport_modes || []).forEach(({ mode_code }) => {
        (masters.end_uses || []).forEach(({ end_use_code }) => {
          if (!isDespChanged(material_code, mode_code, end_use_code)) return;
          const k = despatchActualKey(material_code, mode_code, end_use_code);
          const e = editsDesp[k] || {};
          const actual = e.actual === '' ? null : parseFloat(e.actual);
          if (e.actual !== '' && Number.isNaN(actual)) return;
          despatch.push({ material_code, transport_mode: mode_code, end_use_code, actual });
        });
      });
    });
    const despatch_plan = [];
    (masters.materials || []).forEach(({ material_code }) => {
      (masters.end_uses || []).forEach(({ end_use_code }) => {
        if (!isDespPlanChanged(material_code, end_use_code)) return;
        const k = despatchPlanKey(material_code, end_use_code);
        const e = editsDespPlan[k] || {};
        const plan = e.plan === '' ? null : parseFloat(e.plan);
        if (e.plan !== '' && Number.isNaN(plan)) return;
        despatch_plan.push({ material_code, end_use_code, plan });
      });
    });
    const booked_qty = [];
    (masters.materials || []).forEach(({ material_code }) => {
      (masters.transport_modes || []).forEach(({ mode_code }) => {
        if (!isBookedQtyChanged(material_code, mode_code)) return;
        const k = bookedQtyActualKey(material_code, mode_code);
        const e = editsBookedQty[k] || {};
        const actual = e.actual === '' ? null : parseFloat(e.actual);
        if (e.actual !== '' && Number.isNaN(actual)) return;
        booked_qty.push({ material_code, transport_mode: mode_code, actual });
      });
    });
    const booked_qty_plan = [];
    (masters.materials || []).forEach(({ material_code }) => {
      if (!isBookedQtyPlanChanged(material_code)) return;
      const e = editsBookedQtyPlan[material_code] || {};
      const plan = e.plan === '' ? null : parseFloat(e.plan);
      if (e.plan !== '' && Number.isNaN(plan)) return;
      booked_qty_plan.push({ material_code, plan });
    });
    if (!production.length && !despatch.length && !despatch_plan.length && !booked_qty.length && !booked_qty_plan.length) {
      setStatus({ type: 'error', text: 'No changes to save.' });
      setSaving(false);
      return;
    }
    try {
      const res = await fetch(`${API_BASE_URL}/api/mines-production-despatch/monthly`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          report_month: reportMonth, mine_code: mineCode,
          production, despatch, despatch_plan, booked_qty, booked_qty_plan,
        }),
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

  // Number input for a table cell; `changed` marks unsaved edits.
  const numInput = (value, changed, onChange, label) => (
    <input type="number" step="any" value={value ?? ''} placeholder="–" aria-label={label}
           onChange={(ev) => onChange(ev.target.value)}
           className={cellClass({ changed, filled: value !== '' && value != null })} style={{ width: 92 }} />
  );

  if (mastersError) {
    return (
      <EntryPage>
        <Status status={{ type: 'error', text: `Failed to load mines master data: ${mastersError}` }} />
      </EntryPage>
    );
  }

  const selectedMine = masters?.mines?.find((m) => m.mine_code === mineCode);
  const dirty = hasChanges();

  return (
    <EntryPage
      maxWidth={1300}
      title="Iron Ore Mines — Production & Despatch Entry"
      description={<>
        Monthly fresh Lump/Fines production, and despatch of every material (fresh + legacy Dump Fines/Pellets/Tailings) by
        Rail/Road to Captive Plants, Sales, or Pellet Conversion Agents — per mine. Despatch Plan is one target per
        material/end-use (no Rail/Road split); only Actual despatch is tracked by mode.
      </>}
    >
      <ContextBar actions={<SaveButton dirty={!!masters && dirty} saving={saving} onClick={handleSave}>Save All</SaveButton>}>
        <Field label="Mine" htmlFor="mpd-mine">
          <select id="mpd-mine" className={es.control} style={{ minWidth: 200 }} value={mineCode} onChange={(e) => setMineCode(e.target.value)}>
            {(masters?.groups || []).map((g) => (
              <optgroup key={g.group_code} label={g.group_name}>
                {(masters.mines || []).filter((m) => m.group_code === g.group_code && m.is_active).map((m) => (
                  <option key={m.mine_code} value={m.mine_code}>{m.mine_name}</option>
                ))}
              </optgroup>
            ))}
          </select>
        </Field>
        <Field label="Report month" htmlFor="mpd-month">
          <input id="mpd-month" type="month" className={es.control} value={reportMonth} onChange={(e) => setReportMonth(e.target.value)} />
        </Field>
      </ContextBar>

      <Status status={status} />

      {(!masters || loading) && <Loading />}

      {masters && !loading && (
        <>
          {totalProduction != null && (
            <Status status={{ type: 'info', text: <>Total Production ({selectedMine?.mine_name}, {reportMonth}) = Fresh Lump+Fines production + all legacy despatch = <strong>{totalProduction.toLocaleString()}</strong></> }} />
          )}

          {/* Fresh production */}
          <Section title="Fresh Production">
            <table className={es.table}>
              <thead>
                <tr>
                  <th>Material</th>
                  <th className={es.c}>Actual ({reportMonth})</th>
                  <th className={es.c}>Plan ({reportMonth})</th>
                </tr>
              </thead>
              <tbody>
                {productionMaterials.map(({ material_code, material_name }) => {
                  const changed = isProdChanged(material_code);
                  const e = editsProd[material_code] || {};
                  return (
                    <tr key={material_code}>
                      <td className={es.itemCell}>{material_name}</td>
                      <td className={es.c}>{numInput(e.actual, changed, (v) => handleProdChange(material_code, 'actual', v), `${material_name} actual`)}</td>
                      <td className={es.c}>{numInput(e.plan, changed, (v) => handleProdChange(material_code, 'plan', v), `${material_name} plan`)}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </Section>

          {/* Despatch, one table per end-use. Actual is per Rail/Road;
              Plan is a single column (no mode split) per direct instruction. */}
          {(masters.end_uses || []).map((eu) => (
            <Section key={eu.end_use_code} title={`Despatch — ${eu.end_use_name}`}>
              <table className={es.table}>
                <thead>
                  <tr>
                    <th>Material</th>
                    {(masters.transport_modes || []).map((mode) => (
                      <th key={mode.mode_code} className={es.c}>{mode.mode_name} Actual</th>
                    ))}
                    <th className={es.c}>Plan (Rail+Road)</th>
                  </tr>
                </thead>
                <tbody>
                  {(masters.materials || []).map(({ material_code, material_name }) => {
                    const planChanged = isDespPlanChanged(material_code, eu.end_use_code);
                    const planEdit = editsDespPlan[despatchPlanKey(material_code, eu.end_use_code)] || {};
                    return (
                      <tr key={material_code}>
                        <td className={es.itemCell}>{material_name}</td>
                        {(masters.transport_modes || []).map((mode) => {
                          const changed = isDespChanged(material_code, mode.mode_code, eu.end_use_code);
                          const e = editsDesp[despatchActualKey(material_code, mode.mode_code, eu.end_use_code)] || {};
                          return (
                            <td key={mode.mode_code} className={es.c}>
                              {numInput(e.actual, changed, (v) => handleDespActualChange(material_code, mode.mode_code, eu.end_use_code, v), `${material_name} ${mode.mode_name} actual`)}
                            </td>
                          );
                        })}
                        <td className={es.c}>
                          {numInput(planEdit.plan, planChanged, (v) => handleDespPlanChange(material_code, eu.end_use_code, v), `${material_name} plan`)}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </Section>
          ))}

          {/* Booked Quantity — Sales to 3rd Party. Implicitly SALES-only
              (no end-use dimension — booking a sale does not apply to
              Captive/Pellet Conversion), same Rail/Road Actual + single
              Plan shape as the Despatch — Sales to 3rd Party table above. */}
          <Section title="Booked Quantity — Sales to 3rd Party">
            <table className={es.table}>
              <thead>
                <tr>
                  <th>Material</th>
                  {(masters.transport_modes || []).map((mode) => (
                    <th key={mode.mode_code} className={es.c}>{mode.mode_name} Actual</th>
                  ))}
                  <th className={es.c}>Plan (Rail+Road)</th>
                </tr>
              </thead>
              <tbody>
                {(masters.materials || []).map(({ material_code, material_name }) => {
                  const planChanged = isBookedQtyPlanChanged(material_code);
                  const planEdit = editsBookedQtyPlan[material_code] || {};
                  return (
                    <tr key={material_code}>
                      <td className={es.itemCell}>{material_name}</td>
                      {(masters.transport_modes || []).map((mode) => {
                        const changed = isBookedQtyChanged(material_code, mode.mode_code);
                        const e = editsBookedQty[bookedQtyActualKey(material_code, mode.mode_code)] || {};
                        return (
                          <td key={mode.mode_code} className={es.c}>
                            {numInput(e.actual, changed, (v) => handleBookedQtyActualChange(material_code, mode.mode_code, v), `${material_name} ${mode.mode_name} booked`)}
                          </td>
                        );
                      })}
                      <td className={es.c}>
                        {numInput(planEdit.plan, planChanged, (v) => handleBookedQtyPlanChange(material_code, v), `${material_name} booked plan`)}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </Section>
        </>
      )}
    </EntryPage>
  );
}

export default function MinesProductionDespatchPage() {
  return (
    <RequireEditor>
      <MinesProductionDespatchPageInner />
    </RequireEditor>
  );
}
