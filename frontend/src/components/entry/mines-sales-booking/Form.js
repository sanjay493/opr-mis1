'use client';

import RequireEditor from '@/components/RequireEditor';
import React, { useState, useEffect, useCallback, useMemo } from 'react';
import { EntryPage, ContextBar, Field, Status, Section, SaveButton, Loading, cellClass, entryStyles as es } from '../EntryUI';

const API = process.env.NEXT_PUBLIC_API_URL || '';

// Iron ore sales to 3rd party, one FY at a time: months across, mine x item
// down. The same tables as the Iron Ore Mines Production & Despatch tab
// (repo.mines get_sales_booking_fy / save_sales_booking_fy):
//   plan            mine_booked_qty_plan_monthly, and the same figure into
//                   mine_despatch_plan_monthly (end use SALES)
//   booking_actual  mine_booked_qty_actual_monthly, by Rail / Road
//   despatch_actual mine_despatch_actual_monthly (end use SALES), by Rail / Road
const KINDS = [
  { id: 'plan', label: 'Plan (Sale Booking = Sale Despatch)', modes: false },
  { id: 'booking_actual', label: 'Actual Sale Booking', modes: true },
  { id: 'despatch_actual', label: 'Actual Sale Despatch', modes: true },
];
const MODES = [{ code: 'RAIL', name: 'Rail' }, { code: 'ROAD', name: 'Road' }];
const MON = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];

const now = new Date();
const CURRENT_FY = now.getMonth() >= 3 ? now.getFullYear() : now.getFullYear() - 1;
const FY_LIST = [];
for (let y = 2020; y <= CURRENT_FY + 1; y++) FY_LIST.push(y);
const fyLabel = (y) => `${y}-${String((y + 1) % 100).padStart(2, '0')}`;
const monLabel = (ym) => `${MON[Number(ym.slice(5, 7)) - 1]}'${ym.slice(2, 4)}`;

const cellKey = (kind, month, mine, material, mode) => `${kind}|${month}|${mine}|${material}|${mode || ''}`;
const s = (v) => (v === null || v === undefined ? '' : String(v));
function numOrNull(v) {
  const f = parseFloat(v);
  return Number.isNaN(f) ? null : f;
}
function sum(vals) {
  const xs = vals.filter((x) => x != null);
  return xs.length ? xs.reduce((a, b) => a + b, 0) : null;
}
const fmt = (v) => (v == null ? '' : String(Math.round(v * 1000) / 1000));

function MinesSalesBookingInner() {
  const [masters, setMasters] = useState(null);
  const [fy, setFy] = useState(CURRENT_FY);
  const [kind, setKind] = useState('plan');
  const [showAll, setShowAll] = useState(false);
  const [months, setMonths] = useState([]);
  const [saved, setSaved] = useState({});   // cellKey -> number | null
  const [edits, setEdits] = useState({});   // cellKey -> string
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [status, setStatus] = useState(null);

  useEffect(() => {
    fetch(`${API}/api/mines-master`).then((r) => r.json()).then(setMasters)
      .catch((err) => setStatus({ type: 'error', text: `Masters load failed: ${err.message}` }));
  }, []);

  const load = useCallback(async (fyStart) => {
    setLoading(true);
    setStatus(null);
    try {
      const res = await fetch(`${API}/api/mines-sales-booking?fy_start=${fyStart}`);
      if (!res.ok) throw new Error(await res.text());
      const d = await res.json();
      const next = {};
      KINDS.forEach((k) => (d[k.id] || []).forEach((r) => {
        next[cellKey(k.id, r.report_month, r.mine_code, r.material_code, k.modes ? r.transport_mode : null)] = r.qty;
      }));
      setMonths(d.months);
      setSaved(next);
      setEdits(Object.fromEntries(Object.entries(next).map(([key, v]) => [key, s(v)])));
    } catch (err) {
      setStatus({ type: 'error', text: `Load failed: ${err.message}` });
    } finally {
      setLoading(false);
    }
  }, []);

  // Deferred a tick so the load's own state updates don't run synchronously
  // inside the effect (react-hooks/set-state-in-effect).
  useEffect(() => {
    let cancelled = false;
    Promise.resolve().then(() => { if (!cancelled) load(fy); });
    return () => { cancelled = true; };
  }, [fy, load]);

  const isChanged = (key) => (edits[key] ?? '') !== s(saved[key]);
  const dirtyKeys = useMemo(
    () => Object.keys(edits).filter((key) => (edits[key] ?? '') !== s(saved[key])),
    [edits, saved],
  );
  const value = (key) => numOrNull(edits[key] ?? '');

  const kindDef = KINDS.find((k) => k.id === kind);
  const modes = kindDef.modes ? MODES.map((m) => m.code) : [null];

  // Mine x material rows: every active mine's items with a figure of any
  // kind in this FY (or all items when "Show all items" is ticked).
  const groups = useMemo(() => {
    if (!masters) return [];
    const used = new Set();
    Object.entries(edits).forEach(([key, v]) => {
      if (v !== '') { const [, , mine, material] = key.split('|'); used.add(`${mine}|${material}`); }
    });
    return masters.groups.map((g) => ({
      ...g,
      mines: masters.mines
        .filter((m) => m.group_code === g.group_code && (m.is_active || masters.materials.some((t) => used.has(`${m.mine_code}|${t.material_code}`))))
        .map((m) => ({
          ...m,
          materials: masters.materials.filter((t) => showAll || used.has(`${m.mine_code}|${t.material_code}`)),
        }))
        .filter((m) => m.materials.length),
    })).filter((g) => g.mines.length);
  }, [masters, edits, showAll]);

  const setCell = (key, v) => setEdits((prev) => ({ ...prev, [key]: v }));

  const save = async () => {
    setSaving(true);
    setStatus(null);
    try {
      let total = 0;
      for (const k of KINDS) {
        const entries = dirtyKeys.filter((key) => key.startsWith(`${k.id}|`)).map((key) => {
          const [, report_month, mine_code, material_code, mode] = key.split('|');
          return { report_month, mine_code, material_code, transport_mode: mode || null, qty: numOrNull(edits[key]) };
        });
        if (!entries.length) continue;
        const res = await fetch(`${API}/api/mines-sales-booking`, {
          method: 'POST', headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ kind: k.id, entries }),
        });
        if (!res.ok) throw new Error(`${k.label}: ${await res.text()}`);
        total += (await res.json()).saved;
      }
      setStatus({ type: 'success', text: `Saved ${total} cell${total === 1 ? '' : 's'}.` });
      await load(fy);
    } catch (err) {
      setStatus({ type: 'error', text: `Save failed: ${err.message}` });
    } finally {
      setSaving(false);
    }
  };

  const changeFy = (y) => {
    if (dirtyKeys.length && !window.confirm('Discard unsaved changes?')) return;
    setFy(y);
  };

  const pendingByKind = KINDS.map((k) => [k, dirtyKeys.filter((key) => key.startsWith(`${k.id}|`)).length])
    .filter(([, n]) => n);

  const rowCells = (mine, material, mode) => {
    const vals = months.map((m) => value(cellKey(kind, m, mine, material, mode)));
    return (
      <>
        {months.map((m) => {
          const key = cellKey(kind, m, mine, material, mode);
          const v = edits[key] ?? '';
          return (
            <td key={m} className={es.r}>
              <input value={v} inputMode="decimal" onChange={(e) => setCell(key, e.target.value)}
                     aria-label={`${mine} ${material}${mode ? ` ${mode}` : ''} ${monLabel(m)}`}
                     className={cellClass({ changed: isChanged(key), filled: v !== '' })} style={{ width: 64 }} />
            </td>
          );
        })}
        <td className={es.r} style={{ fontWeight: 600 }}>{fmt(sum(vals))}</td>
      </>
    );
  };

  const totalCells = (cellsOf) => {
    const vals = months.map((m) => sum(cellsOf(m)));
    return (
      <>
        {vals.map((v, i) => <td key={months[i]} className={es.r} style={{ fontWeight: 600 }}>{fmt(v)}</td>)}
        <td className={es.r} style={{ fontWeight: 700 }}>{fmt(sum(vals))}</td>
      </>
    );
  };

  const allCells = (m) => groups.flatMap((g) => g.mines.flatMap((mine) => mine.materials.flatMap((t) =>
    modes.map((mode) => value(cellKey(kind, m, mine.mine_code, t.material_code, mode))))));

  return (
    <EntryPage
      maxWidth={1500}
      title="Mines Sale Booking & Despatch (FY)"
      description={<>
        Iron ore sales to 3rd party, one financial year at a time, in &rsquo;000 T: months across, mine and item down.
        The Plan is both the sale booking plan and the sale despatch plan. Actual booking and actual sale despatch are
        entered by Rail and Road. Same figures as the Iron Ore Mines Production &amp; Despatch tab (booked quantity,
        and despatch to &ldquo;Sales to 3rd Party&rdquo;). Clearing a cell and saving removes its figure.
      </>}
    >
      <ContextBar actions={<SaveButton dirty={dirtyKeys.length > 0} saving={saving} onClick={save}>
        Save{dirtyKeys.length ? ` (${dirtyKeys.length})` : ''}</SaveButton>}>
        <Field label="Financial year" htmlFor="msb-fy">
          <select id="msb-fy" className={es.control} value={fy} onChange={(e) => changeFy(Number(e.target.value))}>
            {FY_LIST.map((y) => <option key={y} value={y}>{fyLabel(y)}</option>)}
          </select>
        </Field>
        <Field label="Enter" htmlFor="msb-kind">
          <select id="msb-kind" className={es.control} value={kind} onChange={(e) => setKind(e.target.value)}>
            {KINDS.map((k) => <option key={k.id} value={k.id}>{k.label}</option>)}
          </select>
        </Field>
        <Field label="Items">
          <label style={{ display: 'flex', alignItems: 'center', gap: 6, whiteSpace: 'nowrap' }}>
            <input type="checkbox" checked={showAll} onChange={(e) => setShowAll(e.target.checked)} />
            Show all items
          </label>
        </Field>
      </ContextBar>

      <Status status={status} />
      {pendingByKind.length > 0 && (
        <Status status={{ type: 'info', text: `Unsaved: ${pendingByKind.map(([k, n]) => `${k.label} ${n}`).join(', ')}. Save writes all of them.` }} />
      )}

      {(loading || !masters) && <Loading />}

      {!loading && masters && (
        <Section title={`${kindDef.label} — FY ${fyLabel(fy)}`}
                 sub={showAll ? 'All items of every mine.' : 'Items with a figure in this FY; tick "Show all items" to add one.'}>
          <table className={es.table}>
            <thead>
              <tr>
                <th>Mine / Item</th>
                {kindDef.modes && <th>Mode</th>}
                {months.map((m) => <th key={m} className={es.r}>{monLabel(m)}</th>)}
                <th className={es.r}>FY Total</th>
              </tr>
            </thead>
            <tbody>
              {groups.map((g) => (
                <React.Fragment key={g.group_code}>
                  <tr className={es.subRow}><td colSpan={months.length + (kindDef.modes ? 3 : 2)}>{g.group_name}</td></tr>
                  {g.mines.map((mine) => (
                    <React.Fragment key={mine.mine_code}>
                      {mine.materials.map((t) => (
                        kindDef.modes ? (
                          <React.Fragment key={t.material_code}>
                            {MODES.map((md, i) => (
                              <tr key={md.code}>
                                <td className={es.itemCell}>{i === 0 ? `${mine.mine_name} — ${t.material_name}` : ''}</td>
                                <td>{md.name}</td>
                                {rowCells(mine.mine_code, t.material_code, md.code)}
                              </tr>
                            ))}
                            <tr>
                              <td />
                              <td style={{ fontWeight: 600 }}>Total</td>
                              {totalCells((m) => MODES.map((md) => value(cellKey(kind, m, mine.mine_code, t.material_code, md.code))))}
                            </tr>
                          </React.Fragment>
                        ) : (
                          <tr key={t.material_code}>
                            <td className={es.itemCell}>{`${mine.mine_name} — ${t.material_name}`}</td>
                            {rowCells(mine.mine_code, t.material_code, null)}
                          </tr>
                        )
                      ))}
                    </React.Fragment>
                  ))}
                </React.Fragment>
              ))}
              {groups.length > 0 && (
                <tr>
                  <td className={es.itemCell}>SAIL Total</td>
                  {kindDef.modes && <td />}
                  {totalCells(allCells)}
                </tr>
              )}
              {groups.length === 0 && (
                <tr><td colSpan={months.length + (kindDef.modes ? 3 : 2)}>No figures for this FY yet — tick &ldquo;Show all items&rdquo; to enter them.</td></tr>
              )}
            </tbody>
          </table>
        </Section>
      )}
    </EntryPage>
  );
}

export default function MinesSalesBookingEntryPage() {
  return (
    <RequireEditor>
      <MinesSalesBookingInner />
    </RequireEditor>
  );
}
