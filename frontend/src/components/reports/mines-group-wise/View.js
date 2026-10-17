'use client';

import React, { useEffect, useState, useCallback } from 'react';
import { ReportPage } from '../ReportUI';

const API = process.env.NEXT_PUBLIC_API_URL || '';

const MONTH_LABEL = {
  '01': 'Jan', '02': 'Feb', '03': 'Mar', '04': 'Apr', '05': 'May', '06': 'Jun',
  '07': 'Jul', '08': 'Aug', '09': 'Sep', '10': 'Oct', '11': 'Nov', '12': 'Dec',
};

const TH = {
  padding: '6px 8px', border: '1px solid #cbd5e1', fontWeight: 700,
  fontSize: 12, backgroundColor: '#1e3a5f', color: '#fff', whiteSpace: 'nowrap',
};
const TD = {
  padding: '5px 8px', border: '1px solid #dadce0', fontSize: 12,
  textAlign: 'right', whiteSpace: 'nowrap', fontVariantNumeric: 'tabular-nums',
};
const LBL_TD = { ...TD, textAlign: 'left' };

export default function MinesGroupWisePage() {
  const [fys, setFys] = useState([]);
  const [fyStart, setFyStart] = useState(null);
  const [inTonnes, setInTonnes] = useState(false);
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [downloading, setDownloading] = useState(false);

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
      const r = await fetch(`${API}/api/mines-group-wise?fy_start=${fyStart}`);
      if (!r.ok) throw new Error(await r.text());
      setData(await r.json());
    } catch (e) {
      setError(`Load failed: ${e.message}`); setData(null);
    } finally {
      setLoading(false);
    }
  }, [fyStart]);
  useEffect(() => { load(); }, [load]);

  const handlePrint = () => window.print();

  const handleExcel = async () => {
    setDownloading(true);
    try {
      const res = await fetch(`${API}/api/mines-group-wise/xlsx?fy_start=${fyStart}`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const blob = await res.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `IronOreMines_GroupWise_FY${data?.fy_label || fyStart}.xlsx`;
      document.body.appendChild(a); a.click(); a.remove();
      window.URL.revokeObjectURL(url);
    } catch (e) {
      setError(`Download failed: ${e.message}`);
    } finally {
      setDownloading(false);
    }
  };

  const fmt = (v) => {
    if (v == null) return '—';
    return inTonnes ? Math.round(v * 1000).toLocaleString('en-IN') : v.toFixed(2);
  };

  const monthHeader = (m) => `${MONTH_LABEL[m.slice(5)]}'${m.slice(2, 4)}`;

  // ── Generic section table: rows are Mine -> commodity[/destination], with
  // Mine Total / Group Total / SAIL Total rows. labelCols picks which
  // field(s) of a row to show (Commodity only for Production; Commodity +
  // Destination for Despatch). ──
  const renderSection = (section, months, labelCols, sectionTitle) => {
    if (!section) return null;
    return (
      <>
        <h3 style={{ fontSize: '1.05rem', fontWeight: 700, color: '#1e3a5f', margin: '4px 0 8px' }}>
          {sectionTitle} ({inTonnes ? 'Tonnes' : "'000 T"})
        </h3>
        <div className="mgw-wrap" style={{ overflowX: 'auto', border: '1px solid #dadce0', borderRadius: 8, marginBottom: 26 }}>
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead>
              <tr>
                <th rowSpan={2} style={{ ...TH, textAlign: 'left', verticalAlign: 'middle' }}>Group</th>
                <th rowSpan={2} style={{ ...TH, textAlign: 'left', verticalAlign: 'middle' }}>Mine</th>
                {labelCols.map((lc) => (
                  <th key={lc.header} rowSpan={2} style={{ ...TH, textAlign: 'left', verticalAlign: 'middle' }}>{lc.header}</th>
                ))}
                {months.map((m) => (
                  <th key={m} colSpan={2} style={{ ...TH, textAlign: 'center', borderLeft: '2px solid #64748b' }}>{monthHeader(m)}</th>
                ))}
                <th colSpan={2} style={{ ...TH, textAlign: 'center', borderLeft: '2px solid #64748b' }}>FY Total</th>
              </tr>
              <tr>
                {months.map((m) => (
                  <React.Fragment key={m}>
                    <th style={{ ...TH, backgroundColor: '#3e6494', fontWeight: 500, fontSize: 10.5, borderLeft: '2px solid #64748b' }}>Plan</th>
                    <th style={{ ...TH, backgroundColor: '#3e6494', fontWeight: 500, fontSize: 10.5 }}>Act</th>
                  </React.Fragment>
                ))}
                <th style={{ ...TH, backgroundColor: '#3e6494', fontWeight: 500, fontSize: 10.5, borderLeft: '2px solid #64748b' }}>Plan</th>
                <th style={{ ...TH, backgroundColor: '#3e6494', fontWeight: 500, fontSize: 10.5 }}>Act</th>
              </tr>
            </thead>
            <tbody>
              {section.groups.map((g) => {
                const groupRowSpan = g.mines.reduce((s, mn) => s + mn.rows.length + 1, 0);
                let groupCellUsed = false;
                return (
                  <React.Fragment key={g.group_code}>
                    {g.mines.map((mn) => {
                      const mineRowSpan = mn.rows.length || 0;
                      return (
                        <React.Fragment key={mn.mine_code}>
                          {mn.rows.map((row, ri) => (
                            <tr key={`${mn.mine_code}-${ri}`}>
                              {!groupCellUsed && (groupCellUsed = true) && (
                                <td rowSpan={groupRowSpan} style={{ ...LBL_TD, fontWeight: 700, verticalAlign: 'top', background: '#f8fafc' }}>
                                  {g.group_name}
                                </td>
                              )}
                              {ri === 0 && (
                                <td rowSpan={mineRowSpan} style={{ ...LBL_TD, fontWeight: 600, verticalAlign: 'top' }}>
                                  {mn.mine_name}
                                </td>
                              )}
                              {labelCols.map((lc) => (
                                <td key={lc.header} style={{ ...LBL_TD, color: '#6b7280' }}>{lc.get(row)}</td>
                              ))}
                              {months.map((m) => (
                                <React.Fragment key={m}>
                                  <td style={{ ...TD, color: '#6b7280', borderLeft: '2px solid #94a3b8' }}>{fmt(row.months[m].plan)}</td>
                                  <td style={{ ...TD, fontWeight: 500 }}>{fmt(row.months[m].actual)}</td>
                                </React.Fragment>
                              ))}
                              <td style={{ ...TD, fontWeight: 600, borderLeft: '2px solid #94a3b8' }}>{fmt(row.fy_total.plan)}</td>
                              <td style={{ ...TD, fontWeight: 700 }}>{fmt(row.fy_total.actual)}</td>
                            </tr>
                          ))}
                          <tr style={{ background: '#f1f5f9' }}>
                            {!groupCellUsed && (groupCellUsed = true) && (
                              <td rowSpan={groupRowSpan} style={{ ...LBL_TD, fontWeight: 700, verticalAlign: 'top', background: '#f8fafc' }}>
                                {g.group_name}
                              </td>
                            )}
                            {mineRowSpan === 0 && (
                              <td style={{ ...LBL_TD, fontWeight: 600 }}>{mn.mine_name}</td>
                            )}
                            <td colSpan={labelCols.length + (mineRowSpan === 0 ? 0 : 1)} style={{ ...LBL_TD, fontWeight: 700 }}>
                              {mineRowSpan === 0 ? '— (no data)' : `${mn.mine_name} Total`}
                            </td>
                            {months.map((m) => (
                              <React.Fragment key={m}>
                                <td style={{ ...TD, fontWeight: 600, borderLeft: '2px solid #94a3b8' }}>{fmt(mn.total.months[m].plan)}</td>
                                <td style={{ ...TD, fontWeight: 700 }}>{fmt(mn.total.months[m].actual)}</td>
                              </React.Fragment>
                            ))}
                            <td style={{ ...TD, fontWeight: 700, borderLeft: '2px solid #94a3b8' }}>{fmt(mn.total.fy_total.plan)}</td>
                            <td style={{ ...TD, fontWeight: 700 }}>{fmt(mn.total.fy_total.actual)}</td>
                          </tr>
                        </React.Fragment>
                      );
                    })}
                    <tr style={{ background: '#fef3c7', borderTop: '2px solid #f59e0b' }}>
                      <td colSpan={2 + labelCols.length} style={{ ...LBL_TD, fontWeight: 700, color: '#9a3412' }}>
                        {g.group_name} Total
                      </td>
                      {months.map((m) => (
                        <React.Fragment key={m}>
                          <td style={{ ...TD, fontWeight: 600, color: '#9a3412', borderLeft: '2px solid #94a3b8' }}>{fmt(g.total.months[m].plan)}</td>
                          <td style={{ ...TD, fontWeight: 700, color: '#9a3412' }}>{fmt(g.total.months[m].actual)}</td>
                        </React.Fragment>
                      ))}
                      <td style={{ ...TD, fontWeight: 700, color: '#9a3412', borderLeft: '2px solid #94a3b8' }}>{fmt(g.total.fy_total.plan)}</td>
                      <td style={{ ...TD, fontWeight: 700, color: '#9a3412' }}>{fmt(g.total.fy_total.actual)}</td>
                    </tr>
                  </React.Fragment>
                );
              })}
              <tr style={{ background: '#fde68a', borderTop: '3px double #b45309' }}>
                <td colSpan={2 + labelCols.length} style={{ ...LBL_TD, fontWeight: 700, color: '#78350f' }}>SAIL TOTAL</td>
                {months.map((m) => (
                  <React.Fragment key={m}>
                    <td style={{ ...TD, fontWeight: 700, color: '#78350f', borderLeft: '2px solid #94a3b8' }}>{fmt(section.sail_total.months[m].plan)}</td>
                    <td style={{ ...TD, fontWeight: 700, color: '#78350f' }}>{fmt(section.sail_total.months[m].actual)}</td>
                  </React.Fragment>
                ))}
                <td style={{ ...TD, fontWeight: 700, color: '#78350f', borderLeft: '2px solid #94a3b8' }}>{fmt(section.sail_total.fy_total.plan)}</td>
                <td style={{ ...TD, fontWeight: 700, color: '#78350f' }}>{fmt(section.sail_total.fy_total.actual)}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </>
    );
  };

  const sel = { padding: '7px 10px', fontSize: 14, border: '1px solid #d1d5db', borderRadius: 4 };
  const lbl = { fontSize: 13, fontWeight: 600, color: '#374151' };
  const hasAny = data && (data.production.sail_total.fy_total.actual != null || data.production.sail_total.fy_total.plan != null
    || data.despatch.sail_total.fy_total.actual != null || data.despatch.sail_total.fy_total.plan != null);

  return (
    <ReportPage
      maxWidth={1700}
      title={<>SAIL Iron Ore Mines — Mine &amp; Group-wise</>}
      description={<>FY {data?.fy_label || ''} · Production, Despatch (by Captive / Sales / Pellet Conversion) &amp; Reported Production · Plan vs Actual, month-wise</>}
    >
      <style>{`
        @media print {
          @page { size: A4 landscape; margin: 9mm; }
          .no-print { display: none !important; }
          .mgw-wrap { overflow: visible !important; border: none !important; }
          h3 { break-after: avoid; }
          table { break-inside: auto; }
          tr { break-inside: avoid; }
        }
      `}</style>

      <div className="no-print" style={{
        display: 'flex', gap: 10, alignItems: 'center', flexWrap: 'wrap',
        marginBottom: 16, border: '1px solid #dadce0', borderRadius: 8, padding: '13px 16px',
      }}>
        <label style={lbl}>FY</label>
        <select value={fyStart ?? ''} onChange={(e) => setFyStart(Number(e.target.value))} style={sel}>
          {fys.map((f) => <option key={f.fy_start} value={f.fy_start}>{f.label}</option>)}
        </select>

        <div style={{ display: 'flex', border: '1px solid #d1d5db', borderRadius: 6, overflow: 'hidden', marginLeft: 8 }}>
          {[{ on: false, t: "'000 T" }, { on: true, t: 'Tonnes' }].map(({ on, t }) => (
            <button key={t} type="button" onClick={() => setInTonnes(on)} style={{
              padding: '7px 13px', fontSize: 12.5, fontWeight: 600, border: 'none', cursor: 'pointer',
              background: inTonnes === on ? '#1a73e8' : '#fff', color: inTonnes === on ? '#fff' : '#374151',
            }}>{t}</button>
          ))}
        </div>

        <button type="button" onClick={handlePrint} disabled={!hasAny} className="no-print" style={{
          marginLeft: 10, padding: '7px 14px', fontSize: 12.5, fontWeight: 600, borderRadius: 6,
          border: '1px solid #d1d5db', background: '#fff', color: '#374151',
          cursor: hasAny ? 'pointer' : 'not-allowed', opacity: hasAny ? 1 : 0.5,
        }}>🖨 Print</button>
        <button type="button" onClick={handleExcel} disabled={!hasAny || downloading} style={{
          padding: '7px 14px', fontSize: 12.5, fontWeight: 600, borderRadius: 6,
          border: '1px solid #188038', background: '#e6f4ea', color: '#188038',
          cursor: hasAny && !downloading ? 'pointer' : 'not-allowed', opacity: hasAny && !downloading ? 1 : 0.5,
        }}>{downloading ? 'Preparing…' : '⬇ Excel'}</button>

        <span style={{ marginLeft: 'auto', fontSize: 13, color: '#5f6368' }}>{loading && '⟳ loading…'}</span>
      </div>

      {error && (
        <div style={{ padding: '10px 16px', borderRadius: 6, marginBottom: 14, fontSize: 14, background: '#fef2f2', color: '#991b1b', border: '1px solid #fca5a5' }}>
          {error}
        </div>
      )}

      {!loading && data && !hasAny ? (
        <div style={{ color: '#9ca3af', fontSize: 14, padding: '50px 0', textAlign: 'center', border: '2px dashed #dadce0', borderRadius: 8 }}>
          No iron-ore mines data for FY {data.fy_label}.
        </div>
      ) : data && (
        <>
          {renderSection(data.production, data.months, [
            { header: 'Commodity', get: (r) => r.material_name },
          ], 'Production')}

          {renderSection(data.despatch, data.months, [
            { header: 'Commodity', get: (r) => r.material_name },
            { header: 'Destination', get: (r) => r.end_use_name },
          ], 'Despatch')}

          {renderSection(data.reported_production, data.months, [
            { header: 'Component', get: (r) => r.material_name },
          ], 'Reported Production')}
        </>
      )}

      <div style={{ marginTop: 8, fontSize: 12, color: '#9ca3af' }}>
        Source: the same mine-level Iron Ore Mines Production &amp; Despatch entries as the &quot;Iron Ore Mines
        (Month-wise)&quot; tab, reshaped mine/group-wise with months as columns. Despatch Actual sums Rail+Road
        (this layout has no transport-mode split); Despatch Plan never had one. Reported Production = fresh
        Lump+Fines production + whichever legacy despatch counts toward it (Pellets: any destination; Dump
        Fines: Captive+Sales; Tailings: Sales only) — the same figure as the &quot;Mines Production
        Performance&quot; tab, shown here FY month-wise instead of one month at a time. Values in &apos;000
        tonnes (Tonnes view ×1000). Rows with no entry for a mine are omitted; a mine with no data anywhere
        still shows its Total row. FY Total sums the months that have data.
      </div>
    </ReportPage>
  );
}
