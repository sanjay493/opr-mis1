'use client';

import React, { useState, useEffect, useMemo, useCallback } from 'react';
import GlobalNavbar from '@/components/GlobalNavbar';

const API = process.env.NEXT_PUBLIC_API_URL || '';

const MONTH_LABEL = {
  '01': 'January', '02': 'February', '03': 'March', '04': 'April', '05': 'May',
  '06': 'June', '07': 'July', '08': 'August', '09': 'September', '10': 'October',
  '11': 'November', '12': 'December',
};

// Production materials (only Lump & Fines are produced); despatch also moves
// legacy Dump Fines / Tailings / Pellets.
const PROD_MATS = ['LUMP', 'FINES'];
const DESP_MATS = ['LUMP', 'FINES', 'DUMP_FINES', 'TAILINGS', 'PELLETS'];
const MAT_LABEL = {
  LUMP: 'Lump', FINES: 'Fines', DUMP_FINES: 'Dump Fines',
  TAILINGS: 'Tailings', PELLETS: 'Pellets',
};

const TH = {
  padding: '7px 9px', border: '1px solid #cbd5e1', fontWeight: 700,
  fontSize: 12.5, backgroundColor: '#1e3a5f', color: '#fff', whiteSpace: 'nowrap',
};
const TD = {
  padding: '6px 9px', border: '1px solid #dadce0', fontSize: 12.5,
  textAlign: 'right', whiteSpace: 'nowrap', fontVariantNumeric: 'tabular-nums',
};

export default function IronOreMinesPage() {
  const [fys, setFys] = useState([]);
  const [fyStart, setFyStart] = useState(null);
  const [scope, setScope] = useState('SAIL');       // 'SAIL' | group_code | mine_code
  const [despMode, setDespMode] = useState('ALL');  // 'ALL' | 'RAIL' | 'ROAD'
  const [inTonnes, setInTonnes] = useState(false);
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    (async () => {
      try {
        const r = await fetch(`${API}/api/production-fys`);
        const d = await r.json();
        setFys(d.fys || []);
        if (d.fys?.length) setFyStart(d.fys[0].fy_start);
      } catch (e) {
        setError(`Could not load financial years: ${e.message}`);
      }
    })();
  }, []);

  const load = useCallback(async () => {
    if (fyStart == null) return;
    setLoading(true); setError(null);
    try {
      const r = await fetch(`${API}/api/iron-ore-mines/series?fy_start=${fyStart}`);
      if (!r.ok) throw new Error(await r.text());
      setData(await r.json());
    } catch (e) {
      setError(`Load failed: ${e.message}`); setData(null);
    } finally {
      setLoading(false);
    }
  }, [fyStart]);
  useEffect(() => { load(); }, [load]);

  const months = data?.months || [];
  const masters = data?.masters || { groups: [], mines: [], materials: [] };

  const scopeMatch = useCallback((row) => {
    if (scope === 'SAIL') return true;
    if (masters.groups.some(g => g.group_code === scope)) return row.group_code === scope;
    return row.mine_code === scope;
  }, [scope, masters.groups]);

  const scopeLabel = useMemo(() => {
    if (scope === 'SAIL') return 'SAIL Total';
    const g = masters.groups.find(x => x.group_code === scope);
    if (g) return g.group_name;
    const m = masters.mines.find(x => x.mine_code === scope);
    return m ? m.mine_name : scope;
  }, [scope, masters]);

  // ── Production: prod[month] = { LUMP:{plan,act}, FINES:{...}, total:{...} } ──
  const prod = useMemo(() => {
    const out = {};
    months.forEach(m => {
      out[m] = { total: { plan: null, act: null } };
      PROD_MATS.forEach(mat => { out[m][mat] = { plan: null, act: null }; });
    });
    (data?.production || []).filter(scopeMatch).forEach(r => {
      const cell = out[r.report_month]?.[r.material_code];
      if (!cell) return;
      if (r.actual != null) { cell.act = (cell.act ?? 0) + r.actual; out[r.report_month].total.act = (out[r.report_month].total.act ?? 0) + r.actual; }
      if (r.plan != null) { cell.plan = (cell.plan ?? 0) + r.plan; out[r.report_month].total.plan = (out[r.report_month].total.plan ?? 0) + r.plan; }
    });
    return out;
  }, [data, months, scopeMatch]);

  // ── Despatch: desp[month][mat] = actual (respecting mode filter); despPlan[month] ──
  const { desp, despPlan, despModeSplit } = useMemo(() => {
    const d = {}, dp = {}, ms = {};
    months.forEach(m => {
      d[m] = { total: null };
      DESP_MATS.forEach(mat => { d[m][mat] = null; });
      dp[m] = null;
      ms[m] = { RAIL: null, ROAD: null };
    });
    (data?.despatch || []).filter(scopeMatch).forEach(r => {
      if (r.actual == null) return;
      if (r.transport_mode === 'RAIL' || r.transport_mode === 'ROAD') {
        ms[r.report_month][r.transport_mode] = (ms[r.report_month][r.transport_mode] ?? 0) + r.actual;
      }
      if (despMode !== 'ALL' && r.transport_mode !== despMode) return;
      d[r.report_month][r.material_code] = (d[r.report_month][r.material_code] ?? 0) + r.actual;
      d[r.report_month].total = (d[r.report_month].total ?? 0) + r.actual;
    });
    (data?.despatch_plan || []).filter(scopeMatch).forEach(r => {
      if (r.plan != null) dp[r.report_month] = (dp[r.report_month] ?? 0) + r.plan;
    });
    return { desp: d, despPlan: dp, despModeSplit: ms };
  }, [data, months, scopeMatch, despMode]);

  // ── Per-mine FY totals (for the "mines summary" table) ──
  const minesInScope = useMemo(() => {
    if (scope === 'SAIL') return masters.mines;
    if (masters.groups.some(g => g.group_code === scope)) return masters.mines.filter(m => m.group_code === scope);
    return masters.mines.filter(m => m.mine_code === scope);
  }, [scope, masters]);

  const mineTotals = useMemo(() => {
    const out = {};
    minesInScope.forEach(m => {
      out[m.mine_code] = { prodPlan: null, prodAct: null, dRail: null, dRoad: null, dTotal: null };
    });
    (data?.production || []).forEach(r => {
      const t = out[r.mine_code]; if (!t) return;
      if (r.actual != null) t.prodAct = (t.prodAct ?? 0) + r.actual;
      if (r.plan != null) t.prodPlan = (t.prodPlan ?? 0) + r.plan;
    });
    (data?.despatch || []).forEach(r => {
      const t = out[r.mine_code]; if (!t || r.actual == null) return;
      if (r.transport_mode === 'RAIL') t.dRail = (t.dRail ?? 0) + r.actual;
      else if (r.transport_mode === 'ROAD') t.dRoad = (t.dRoad ?? 0) + r.actual;
      t.dTotal = (t.dTotal ?? 0) + r.actual;
    });
    return out;
  }, [data, minesInScope]);

  const showMinesSummary = scope === 'SAIL' || masters.groups.some(g => g.group_code === scope);

  // ── formatting ──
  const fmt = (v) => {
    if (v == null) return '—';
    return inTonnes ? Math.round(v * 1000).toLocaleString('en-IN') : v.toFixed(2);
  };
  const pct = (a, b) => (a == null || b == null || b === 0 ? '—' : `${(a / b * 100).toFixed(1)}%`);
  const pctColor = (a, b) => {
    if (a == null || b == null || b === 0) return '#6b7280';
    const p = a / b * 100;
    return p >= 100 ? '#188038' : p >= 90 ? '#b45309' : '#c5221f';
  };

  const sumCol = (obj, pick) => {
    let s = null;
    months.forEach(m => { const v = pick(obj[m]); if (v != null) s = (s ?? 0) + v; });
    return s;
  };

  const prodTotals = {
    LUMP: { plan: sumCol(prod, x => x?.LUMP?.plan), act: sumCol(prod, x => x?.LUMP?.act) },
    FINES: { plan: sumCol(prod, x => x?.FINES?.plan), act: sumCol(prod, x => x?.FINES?.act) },
    total: { plan: sumCol(prod, x => x?.total?.plan), act: sumCol(prod, x => x?.total?.act) },
  };
  const despTotals = Object.fromEntries(
    [...DESP_MATS, 'total'].map(k => [k, sumCol(desp, x => x?.[k])])
  );
  const despPlanTotal = sumCol(despPlan, x => x);
  const despRailTotal = sumCol(despModeSplit, x => x?.RAIL);
  const despRoadTotal = sumCol(despModeSplit, x => x?.ROAD);

  const hasAny =
    months.some(m => prod[m]?.total?.act != null || prod[m]?.total?.plan != null || desp[m]?.total != null);

  const monthHasData = (m) =>
    prod[m]?.total?.act != null || prod[m]?.total?.plan != null || desp[m]?.total != null || despPlan[m] != null;

  const handlePrint = () => window.print();

  const handleExcel = () => {
    const cv = (v) => (v == null ? '' : inTonnes ? String(Math.round(v * 1000)) : v.toFixed(3));
    const esc = (s) => (/[",\r\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s);
    const lines = [];
    lines.push([`Iron Ore Mines — ${scopeLabel} — FY ${data?.fy_label || ''}`]);
    lines.push([`Unit: ${inTonnes ? 'Tonnes' : "'000 T"}`]);
    lines.push([]);
    lines.push(['PRODUCTION', 'Lump Plan', 'Lump Act', 'Fines Plan', 'Fines Act', 'Total Plan', 'Total Act', '% Ach']);
    months.forEach(m => {
      const p = prod[m];
      lines.push([
        `${MONTH_LABEL[m.slice(5)]} ${m.slice(0, 4)}`,
        cv(p.LUMP.plan), cv(p.LUMP.act), cv(p.FINES.plan), cv(p.FINES.act),
        cv(p.total.plan), cv(p.total.act),
        p.total.plan ? (p.total.act / p.total.plan * 100).toFixed(1) : '',
      ]);
    });
    lines.push(['FY Total', cv(prodTotals.LUMP.plan), cv(prodTotals.LUMP.act),
      cv(prodTotals.FINES.plan), cv(prodTotals.FINES.act),
      cv(prodTotals.total.plan), cv(prodTotals.total.act),
      prodTotals.total.plan ? (prodTotals.total.act / prodTotals.total.plan * 100).toFixed(1) : '']);
    lines.push([]);
    lines.push([`DESPATCH (${despMode === 'ALL' ? 'Rail + Road' : despMode})`,
      ...DESP_MATS.map(x => MAT_LABEL[x]), 'Total', 'Plan', '% Ach', 'Rail', 'Road']);
    months.forEach(m => {
      lines.push([
        `${MONTH_LABEL[m.slice(5)]} ${m.slice(0, 4)}`,
        ...DESP_MATS.map(x => cv(desp[m][x])), cv(desp[m].total),
        cv(despPlan[m]), despPlan[m] ? (desp[m].total / despPlan[m] * 100).toFixed(1) : '',
        cv(despModeSplit[m].RAIL), cv(despModeSplit[m].ROAD),
      ]);
    });
    lines.push(['FY Total', ...DESP_MATS.map(x => cv(despTotals[x])), cv(despTotals.total),
      cv(despPlanTotal), despPlanTotal ? (despTotals.total / despPlanTotal * 100).toFixed(1) : '',
      cv(despRailTotal), cv(despRoadTotal)]);

    if (showMinesSummary) {
      lines.push([]);
      lines.push(['MINE (FY totals)', 'Prod Plan', 'Prod Act', 'Desp Rail', 'Desp Road', 'Desp Total']);
      minesInScope.forEach(mn => {
        const t = mineTotals[mn.mine_code];
        lines.push([mn.mine_name, cv(t.prodPlan), cv(t.prodAct), cv(t.dRail), cv(t.dRoad), cv(t.dTotal)]);
      });
    }

    const csv = lines.map(r => r.map(v => esc(String(v))).join(',')).join('\r\n');
    const blob = new Blob(['﻿' + csv], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `IronOreMines_${scopeLabel.replace(/[^a-z0-9]+/gi, '_')}_${data?.fy_label || ''}.csv`;
    document.body.appendChild(a); a.click(); document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };

  const sel = { padding: '7px 10px', fontSize: 14, border: '1px solid #d1d5db', borderRadius: 4 };
  const lbl = { fontSize: 13, fontWeight: 600, color: '#374151' };

  return (
    <div style={{ minHeight: '100vh', background: '#fff', fontFamily: "-apple-system,BlinkMacSystemFont,'Segoe UI',Arial,sans-serif" }}>
      <style>{`
        html, body { overflow-y: auto; overflow-x: hidden; }
        @media print {
          @page { size: A4 landscape; margin: 9mm; }
          .no-print { display: none !important; }
          .iom-wrap { overflow: visible !important; border: none !important; }
          h3 { break-after: avoid; }
          table { break-inside: auto; }
          tr { break-inside: avoid; }
        }
      `}</style>

      <div className="no-print"><GlobalNavbar /></div>

      <div style={{ maxWidth: 1500, margin: '0 auto', padding: '22px 20px' }}>
        <div style={{ display: 'flex', alignItems: 'baseline', gap: 14, marginBottom: 16, flexWrap: 'wrap' }}>
          <h2 style={{ fontSize: '1.6rem', fontWeight: 700, color: '#202124', margin: 0 }}>
            SAIL Iron Ore Mines — Month-wise
          </h2>
          <span style={{ fontSize: 13, color: '#5f6368' }}>
            {scopeLabel} · FY {data?.fy_label || ''} · Production &amp; Despatch (Lump, Fines, Dump Fines, Tailings, Pellets · Rail / Road)
          </span>
        </div>

        <div className="no-print" style={{
          display: 'flex', gap: 10, alignItems: 'center', flexWrap: 'wrap',
          marginBottom: 16, border: '1px solid #dadce0', borderRadius: 8, padding: '13px 16px',
        }}>
          <label style={lbl}>Scope</label>
          <select value={scope} onChange={e => setScope(e.target.value)} style={sel}>
            <option value="SAIL">SAIL Total (all mines)</option>
            {masters.groups.map(g => (
              <optgroup key={g.group_code} label={`── ${g.group_name} ──`}>
                <option value={g.group_code}>{g.group_name} (group total)</option>
                {masters.mines.filter(m => m.group_code === g.group_code).map(m => (
                  <option key={m.mine_code} value={m.mine_code}>&nbsp;&nbsp;{m.mine_name}</option>
                ))}
              </optgroup>
            ))}
          </select>

          <label style={{ ...lbl, marginLeft: 8 }}>FY</label>
          <select value={fyStart ?? ''} onChange={e => setFyStart(Number(e.target.value))} style={sel}>
            {fys.map(f => <option key={f.fy_start} value={f.fy_start}>{f.label}</option>)}
          </select>

          <label style={{ ...lbl, marginLeft: 8 }}>Despatch mode</label>
          <div style={{ display: 'flex', border: '1px solid #d1d5db', borderRadius: 6, overflow: 'hidden' }}>
            {['ALL', 'RAIL', 'ROAD'].map(md => (
              <button key={md} onClick={() => setDespMode(md)} style={{
                padding: '7px 13px', fontSize: 12.5, fontWeight: 600, border: 'none', cursor: 'pointer',
                background: despMode === md ? '#1a73e8' : '#fff', color: despMode === md ? '#fff' : '#374151',
              }}>{md === 'ALL' ? 'Rail + Road' : md === 'RAIL' ? 'Rail' : 'Road'}</button>
            ))}
          </div>

          <div style={{ display: 'flex', border: '1px solid #d1d5db', borderRadius: 6, overflow: 'hidden', marginLeft: 8 }}>
            {[{ on: false, t: "'000 T" }, { on: true, t: 'Tonnes' }].map(({ on, t }) => (
              <button key={t} onClick={() => setInTonnes(on)} style={{
                padding: '7px 13px', fontSize: 12.5, fontWeight: 600, border: 'none', cursor: 'pointer',
                background: inTonnes === on ? '#1a73e8' : '#fff', color: inTonnes === on ? '#fff' : '#374151',
              }}>{t}</button>
            ))}
          </div>

          <button onClick={handlePrint} disabled={!hasAny} className="no-print" style={{
            marginLeft: 10, padding: '7px 14px', fontSize: 12.5, fontWeight: 600, borderRadius: 6,
            border: '1px solid #d1d5db', background: '#fff', color: '#374151',
            cursor: hasAny ? 'pointer' : 'not-allowed', opacity: hasAny ? 1 : 0.5,
          }}>🖨 Print</button>
          <button onClick={handleExcel} disabled={!hasAny} style={{
            padding: '7px 14px', fontSize: 12.5, fontWeight: 600, borderRadius: 6,
            border: '1px solid #188038', background: '#e6f4ea', color: '#188038',
            cursor: hasAny ? 'pointer' : 'not-allowed', opacity: hasAny ? 1 : 0.5,
          }}>⬇ Excel</button>

          <span style={{ marginLeft: 'auto', fontSize: 13, color: '#5f6368' }}>{loading && '⟳ loading…'}</span>
        </div>

        {error && (
          <div style={{ padding: '10px 16px', borderRadius: 6, marginBottom: 14, fontSize: 14, background: '#fef2f2', color: '#991b1b', border: '1px solid #fca5a5' }}>
            {error}
          </div>
        )}

        {!loading && data && !hasAny ? (
          <div style={{ color: '#9ca3af', fontSize: 14, padding: '50px 0', textAlign: 'center', border: '2px dashed #dadce0', borderRadius: 8 }}>
            No iron-ore mines data for {scopeLabel} in FY {data.fy_label}.
          </div>
        ) : data && (
          <>
            {/* ── PRODUCTION ── */}
            <h3 style={{ fontSize: '1.05rem', fontWeight: 700, color: '#1e3a5f', margin: '4px 0 8px' }}>
              Production ({inTonnes ? 'Tonnes' : "'000 T"})
            </h3>
            <div className="iom-wrap" style={{ overflowX: 'auto', border: '1px solid #dadce0', borderRadius: 8, marginBottom: 22 }}>
              <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                <thead>
                  <tr>
                    <th rowSpan={2} style={{ ...TH, textAlign: 'left', verticalAlign: 'middle' }}>Month</th>
                    {['Lump', 'Fines', 'Total'].map((m, i) => (
                      <th key={m} colSpan={2} style={{ ...TH, textAlign: 'center', borderLeft: i > 0 ? '2px solid #64748b' : TH.border }}>{m}</th>
                    ))}
                    <th rowSpan={2} style={{ ...TH, textAlign: 'center', verticalAlign: 'middle', borderLeft: '2px solid #64748b' }}>% Ach<br />(Total)</th>
                  </tr>
                  <tr>
                    {['Lump', 'Fines', 'Total'].map((m, i) => (
                      <React.Fragment key={m}>
                        <th style={{ ...TH, backgroundColor: '#3e6494', fontWeight: 500, fontSize: 11, borderLeft: i > 0 ? '2px solid #64748b' : TH.border }}>Plan</th>
                        <th style={{ ...TH, backgroundColor: '#3e6494', fontWeight: 500, fontSize: 11 }}>Act</th>
                      </React.Fragment>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {months.map((m, i) => {
                    const p = prod[m];
                    return (
                      <tr key={m} style={{ background: i % 2 ? '#f8fafc' : '#fff', opacity: monthHasData(m) ? 1 : 0.4 }}>
                        <td style={{ ...TD, textAlign: 'left', fontWeight: 600 }}>
                          {MONTH_LABEL[m.slice(5)]} <span style={{ color: '#9ca3af', fontWeight: 400 }}>{m.slice(0, 4)}</span>
                        </td>
                        {['LUMP', 'FINES', 'total'].map((k, j) => (
                          <React.Fragment key={k}>
                            <td style={{ ...TD, color: '#6b7280', borderLeft: j > 0 ? '2px solid #94a3b8' : TD.border }}>{fmt(p[k].plan)}</td>
                            <td style={{ ...TD, fontWeight: k === 'total' ? 700 : 500 }}>{fmt(p[k].act)}</td>
                          </React.Fragment>
                        ))}
                        <td style={{ ...TD, fontWeight: 600, borderLeft: '2px solid #94a3b8', color: pctColor(p.total.act, p.total.plan) }}>
                          {pct(p.total.act, p.total.plan)}
                        </td>
                      </tr>
                    );
                  })}
                  <tr style={{ background: '#fff7ed', borderTop: '2px solid #f59e0b' }}>
                    <td style={{ ...TD, textAlign: 'left', fontWeight: 700, color: '#9a3412' }}>FY Total</td>
                    {['LUMP', 'FINES', 'total'].map((k, j) => (
                      <React.Fragment key={k}>
                        <td style={{ ...TD, fontWeight: 600, color: '#9a3412', borderLeft: j > 0 ? '2px solid #94a3b8' : TD.border }}>{fmt(prodTotals[k].plan)}</td>
                        <td style={{ ...TD, fontWeight: 700, color: '#9a3412' }}>{fmt(prodTotals[k].act)}</td>
                      </React.Fragment>
                    ))}
                    <td style={{ ...TD, fontWeight: 700, color: '#9a3412', borderLeft: '2px solid #94a3b8' }}>
                      {pct(prodTotals.total.act, prodTotals.total.plan)}
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>

            {/* ── DESPATCH ── */}
            <h3 style={{ fontSize: '1.05rem', fontWeight: 700, color: '#1e3a5f', margin: '4px 0 8px' }}>
              Despatch — {despMode === 'ALL' ? 'Rail + Road' : despMode === 'RAIL' ? 'Rail only' : 'Road only'} ({inTonnes ? 'Tonnes' : "'000 T"})
            </h3>
            <div className="iom-wrap" style={{ overflowX: 'auto', border: '1px solid #dadce0', borderRadius: 8, marginBottom: 22 }}>
              <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                <thead>
                  <tr>
                    <th style={{ ...TH, textAlign: 'left' }}>Month</th>
                    {DESP_MATS.map(x => <th key={x} style={TH}>{MAT_LABEL[x]}</th>)}
                    <th style={{ ...TH, borderLeft: '2px solid #64748b' }}>Total Desp.</th>
                    <th style={TH}>Plan</th>
                    <th style={TH}>% Ach</th>
                    <th style={{ ...TH, borderLeft: '2px solid #64748b' }}>Rail</th>
                    <th style={TH}>Road</th>
                  </tr>
                </thead>
                <tbody>
                  {months.map((m, i) => {
                    const dr = desp[m];
                    return (
                      <tr key={m} style={{ background: i % 2 ? '#f8fafc' : '#fff', opacity: monthHasData(m) ? 1 : 0.4 }}>
                        <td style={{ ...TD, textAlign: 'left', fontWeight: 600 }}>
                          {MONTH_LABEL[m.slice(5)]} <span style={{ color: '#9ca3af', fontWeight: 400 }}>{m.slice(0, 4)}</span>
                        </td>
                        {DESP_MATS.map(x => <td key={x} style={TD}>{fmt(dr[x])}</td>)}
                        <td style={{ ...TD, fontWeight: 700, borderLeft: '2px solid #94a3b8' }}>{fmt(dr.total)}</td>
                        <td style={{ ...TD, color: '#6b7280' }}>{fmt(despPlan[m])}</td>
                        <td style={{ ...TD, fontWeight: 600, color: pctColor(dr.total, despPlan[m]) }}>{pct(dr.total, despPlan[m])}</td>
                        <td style={{ ...TD, borderLeft: '2px solid #94a3b8' }}>{fmt(despModeSplit[m].RAIL)}</td>
                        <td style={TD}>{fmt(despModeSplit[m].ROAD)}</td>
                      </tr>
                    );
                  })}
                  <tr style={{ background: '#fff7ed', borderTop: '2px solid #f59e0b' }}>
                    <td style={{ ...TD, textAlign: 'left', fontWeight: 700, color: '#9a3412' }}>FY Total</td>
                    {DESP_MATS.map(x => <td key={x} style={{ ...TD, fontWeight: 600, color: '#9a3412' }}>{fmt(despTotals[x])}</td>)}
                    <td style={{ ...TD, fontWeight: 700, color: '#9a3412', borderLeft: '2px solid #94a3b8' }}>{fmt(despTotals.total)}</td>
                    <td style={{ ...TD, fontWeight: 600, color: '#9a3412' }}>{fmt(despPlanTotal)}</td>
                    <td style={{ ...TD, fontWeight: 700, color: '#9a3412' }}>{pct(despTotals.total, despPlanTotal)}</td>
                    <td style={{ ...TD, fontWeight: 600, color: '#9a3412', borderLeft: '2px solid #94a3b8' }}>{fmt(despRailTotal)}</td>
                    <td style={{ ...TD, fontWeight: 600, color: '#9a3412' }}>{fmt(despRoadTotal)}</td>
                  </tr>
                </tbody>
              </table>
            </div>
            <div style={{ fontSize: 11.5, color: '#9ca3af', marginTop: -14, marginBottom: 20 }}>
              Material columns follow the Rail/Road toggle; the Rail &amp; Road columns on the right always show the
              full split (all materials). Despatch Plan has no Rail/Road split.
            </div>

            {/* ── MINES SUMMARY (FY totals) ── */}
            {showMinesSummary && (
              <>
                <h3 style={{ fontSize: '1.05rem', fontWeight: 700, color: '#1e3a5f', margin: '4px 0 8px' }}>
                  Mines — FY totals ({inTonnes ? 'Tonnes' : "'000 T"})
                </h3>
                <div className="iom-wrap" style={{ overflowX: 'auto', border: '1px solid #dadce0', borderRadius: 8, marginBottom: 20 }}>
                  <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                    <thead>
                      <tr>
                        <th style={{ ...TH, textAlign: 'left' }}>Mine</th>
                        <th style={TH}>Group</th>
                        <th style={{ ...TH, borderLeft: '2px solid #64748b' }}>Prod. Plan</th>
                        <th style={TH}>Prod. Act</th>
                        <th style={TH}>Prod. % Ach</th>
                        <th style={{ ...TH, borderLeft: '2px solid #64748b' }}>Desp. Rail</th>
                        <th style={TH}>Desp. Road</th>
                        <th style={TH}>Desp. Total</th>
                      </tr>
                    </thead>
                    <tbody>
                      {minesInScope.map((mn, i) => {
                        const t = mineTotals[mn.mine_code];
                        const grp = masters.groups.find(g => g.group_code === mn.group_code);
                        return (
                          <tr key={mn.mine_code} style={{ background: i % 2 ? '#f8fafc' : '#fff' }}>
                            <td style={{ ...TD, textAlign: 'left', fontWeight: 600 }}>{mn.mine_name}</td>
                            <td style={{ ...TD, textAlign: 'left', color: '#6b7280' }}>{mn.group_code}</td>
                            <td style={{ ...TD, color: '#6b7280', borderLeft: '2px solid #94a3b8' }}>{fmt(t.prodPlan)}</td>
                            <td style={{ ...TD, fontWeight: 600 }}>{fmt(t.prodAct)}</td>
                            <td style={{ ...TD, color: pctColor(t.prodAct, t.prodPlan) }}>{pct(t.prodAct, t.prodPlan)}</td>
                            <td style={{ ...TD, borderLeft: '2px solid #94a3b8' }}>{fmt(t.dRail)}</td>
                            <td style={TD}>{fmt(t.dRoad)}</td>
                            <td style={{ ...TD, fontWeight: 600 }}>{fmt(t.dTotal)}</td>
                          </tr>
                        );
                      })}
                      <tr style={{ background: '#fff7ed', borderTop: '2px solid #f59e0b' }}>
                        <td style={{ ...TD, textAlign: 'left', fontWeight: 700, color: '#9a3412' }} colSpan={2}>{scopeLabel} Total</td>
                        <td style={{ ...TD, fontWeight: 600, color: '#9a3412', borderLeft: '2px solid #94a3b8' }}>
                          {fmt(minesInScope.reduce((s, mn) => (mineTotals[mn.mine_code].prodPlan != null ? (s ?? 0) + mineTotals[mn.mine_code].prodPlan : s), null))}
                        </td>
                        <td style={{ ...TD, fontWeight: 700, color: '#9a3412' }}>
                          {fmt(minesInScope.reduce((s, mn) => (mineTotals[mn.mine_code].prodAct != null ? (s ?? 0) + mineTotals[mn.mine_code].prodAct : s), null))}
                        </td>
                        <td style={TD}></td>
                        <td style={{ ...TD, fontWeight: 600, color: '#9a3412', borderLeft: '2px solid #94a3b8' }}>
                          {fmt(minesInScope.reduce((s, mn) => (mineTotals[mn.mine_code].dRail != null ? (s ?? 0) + mineTotals[mn.mine_code].dRail : s), null))}
                        </td>
                        <td style={{ ...TD, fontWeight: 600, color: '#9a3412' }}>
                          {fmt(minesInScope.reduce((s, mn) => (mineTotals[mn.mine_code].dRoad != null ? (s ?? 0) + mineTotals[mn.mine_code].dRoad : s), null))}
                        </td>
                        <td style={{ ...TD, fontWeight: 700, color: '#9a3412' }}>
                          {fmt(minesInScope.reduce((s, mn) => (mineTotals[mn.mine_code].dTotal != null ? (s ?? 0) + mineTotals[mn.mine_code].dTotal : s), null))}
                        </td>
                      </tr>
                    </tbody>
                  </table>
                </div>
              </>
            )}
          </>
        )}

        <div style={{ marginTop: 8, fontSize: 12, color: '#9ca3af' }}>
          Source: mine-level Iron Ore Mines Production &amp; Despatch entry (11 mines under JGoM / OGoM / CGoM).
          Production covers Lump &amp; Fines; Despatch also moves legacy Dump Fines, Tailings &amp; Pellets.
          Values stored in &apos;000 tonnes (Tonnes view ×1000). Dimmed rows have no entry yet.
          &quot;% Ach&quot; = Actual ÷ Plan. FY Total sums the months that have data.
        </div>
      </div>
    </div>
  );
}
