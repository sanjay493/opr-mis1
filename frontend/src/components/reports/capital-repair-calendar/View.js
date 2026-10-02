'use client';

import React, { useEffect, useState } from 'react';
import { ReportPage } from '../ReportUI';
import {
  API_BASE, CURRENT_FY_END_YEAR, selStyle, pillStyle, ErrorBox, TabIntro, ExportButtons, downloadFile,
} from '@/components/techno/shared';

const PLANTS = [
  { code: 'BSP', label: 'Bhilai Steel Plant' },
  { code: 'DSP', label: 'Durgapur Steel Plant' },
  { code: 'RSP', label: 'Rourkela Steel Plant' },
  { code: 'BSL', label: 'Bokaro Steel Plant' },
  { code: 'ISP', label: 'IISCO Steel Plant' },
];

function defaultFy() {
  const endYear = CURRENT_FY_END_YEAR;
  return `${endYear - 1}-${String(endYear % 100).padStart(2, '0')}`;
}

// Recent FYs, current first.
function fyOptions() {
  const endYear = CURRENT_FY_END_YEAR;
  return Array.from({ length: 6 }, (_, i) => {
    const start = endYear - 1 - i;
    return `${start}-${String((start + 1) % 100).padStart(2, '0')}`;
  });
}

export default function CapitalRepairCalendarView() {
  const [plant, setPlant] = useState('BSP');
  const [fy, setFy] = useState(defaultFy());
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [downloading, setDownloading] = useState(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    fetch(`${API_BASE}/api/capital-repair-calendar?plant=${plant}&fy=${fy}`)
      .then((r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        return r.json();
      })
      .then((d) => { if (!cancelled) setData(d); })
      .catch((e) => { if (!cancelled) setError(`Failed to load: ${e.message}`); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [plant, fy]);

  const handleDownload = async (kind) => {
    setDownloading(kind);
    try {
      await downloadFile(
        `${API_BASE}/api/capital-repair-calendar/${kind}?plant=${plant}&fy=${fy}`,
        undefined,
        `Capital_Repair_Calendar_${plant}_${fy}.${kind === 'excel' ? 'xlsx' : 'pdf'}`,
      );
    } catch (e) {
      setError(`Download failed: ${e.message}`);
    } finally {
      setDownloading(null);
    }
  };

  const months = data?.month_labels || [];
  const todayPos = todayPosition(data);
  const nCols = 1 + months.length;

  return (
    <ReportPage
      maxWidth={1600}
      title={<>Capital Repair — Plan vs Actual</>}
    >

        <TabIntro>
          One row per unit, Apr–Mar: when each repair was planned and when it actually ran, drawn
          to scale with the days in each month. Hover a bar for its dates.
        </TabIntro>

        <div style={{ display: 'flex', gap: '10px', alignItems: 'center', flexWrap: 'wrap', marginBottom: '16px' }}>
          <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap' }}>
            {PLANTS.map((p) => (
              <button key={p.code} title={p.label} onClick={() => setPlant(p.code)} style={pillStyle(plant === p.code)}>
                {p.code}
              </button>
            ))}
          </div>
          <select value={fy} onChange={(e) => setFy(e.target.value)} style={{ ...selStyle, marginLeft: '6px' }}>
            {fyOptions().map((f) => <option key={f} value={f}>FY {f}</option>)}
          </select>
          <div style={{ marginLeft: 'auto' }}>
            <ExportButtons onDownload={handleDownload} downloading={downloading} disabled={!data || loading} />
          </div>
        </div>

        <ErrorBox>{error}</ErrorBox>

        {data && (
          <div style={{
            display: 'flex', gap: '12px', flexWrap: 'wrap', alignItems: 'stretch', marginBottom: '16px',
            opacity: loading ? 0.5 : 1,
          }}>
            <StatTile label="Repairs planned" value={data.summary?.repairs} accent="#5f6368" />
            <StatTile label="Completed" value={data.summary?.done} accent="#188038" />
            <StatTile label="In progress" value={data.summary?.ongoing} accent="#1a73e8" />
            <StatTile label="Deferred" value={data.summary?.deferred} accent="#d93025" />
            <StatTile label="Yet to start" value={data.summary?.pending} accent="#b06000" />
            <div style={{
              marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: '18px', padding: '0 4px',
              fontSize: '10pt', color: '#5f6368', flexWrap: 'wrap',
            }}>
              <LegendItem swatch={<Swatch bar={PLAN_BAR} />}>Plan</LegendItem>
              <LegendItem swatch={<Swatch bar={ACTUAL_BAR} />}>Actual</LegendItem>
              <LegendItem swatch={<Swatch bar={ONGOING_BAR} />}>In progress</LegendItem>
              <LegendItem swatch={<span style={{ width: 2, height: 14, background: TODAY, display: 'inline-block' }} />}>
                Today
              </LegendItem>
            </div>
          </div>
        )}

        {loading && !data && <p style={{ color: '#5f6368', fontSize: '11pt' }}>Loading…</p>}

        {data && (
          // Scrolls inside its own window-high panel so the month header rows,
          // the current shop's bar and the Unit column stay in view.
          <div style={{
            overflow: 'auto', maxHeight: 'calc(100vh - 300px)', minHeight: '320px',
            border: '1px solid #e0e3e7', borderRadius: '12px', background: '#ffffff',
            boxShadow: '0 1px 2px rgba(60,64,67,.08), 0 2px 8px rgba(60,64,67,.06)',
            opacity: loading ? 0.5 : 1, transition: 'opacity .15s',
          }}>
            <table style={{
              borderCollapse: 'separate', borderSpacing: 0, width: '100%', minWidth: '1000px', tableLayout: 'fixed',
            }}>
              <colgroup>
                <col style={{ width: UNIT_W }} />
                {months.map((m) => <col key={m} />)}
              </colgroup>
              <thead>
                <tr>
                  <th rowSpan={2} style={{
                    ...headCell(0), left: 0, zIndex: 5, height: HEADER_H, textAlign: 'left',
                    padding: '0 16px 9px', verticalAlign: 'bottom', boxShadow: 'inset -1px 0 0 #e0e3e7',
                  }}>
                    Unit
                  </th>
                  {QUARTERS.map((q, qi) => (
                    <th key={q} colSpan={3} style={{
                      ...headCell(0), height: Q_H, fontSize: '8.5pt', letterSpacing: '.06em', color: '#80868b',
                      borderLeft: '1px solid #e0e3e7', background: qi % 2 ? QTR_SHADE_HEAD : '#ffffff',
                    }}>
                      {q}
                    </th>
                  ))}
                </tr>
                <tr>
                  {months.map((m, mi) => (
                    <th key={m} style={{
                      ...headCell(Q_H), height: HEADER_H - Q_H, borderLeft: '1px solid #e0e3e7',
                      background: Math.floor(mi / 3) % 2 ? QTR_SHADE_HEAD : '#ffffff',
                    }}>
                      <span style={todayPos?.index === mi ? {
                        background: TODAY, color: '#ffffff', borderRadius: '10px', padding: '2px 8px',
                      } : undefined}>
                        {m}
                      </span>
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {data.sections.map((sec) => (
                  <React.Fragment key={sec.shop}>
                    <tr>
                      <td colSpan={nCols} style={{
                        padding: 0, background: '#eef3fd', borderBottom: '1px solid #d2e3fc',
                        position: 'sticky', top: HEADER_H, zIndex: 3,
                      }}>
                        <span style={{
                          position: 'sticky', left: 0, display: 'inline-flex', alignItems: 'center', gap: '8px',
                          padding: '6px 16px', fontSize: '9.5pt', fontWeight: 800, color: '#174ea6',
                          letterSpacing: '.04em', textTransform: 'uppercase',
                        }}>
                          <span style={{ width: 4, height: 14, borderRadius: 2, background: '#1a73e8' }} />
                          {sec.shop}
                          <span style={{ fontWeight: 600, color: '#5f6368', textTransform: 'none', letterSpacing: 0 }}>
                            · {sec.rows.length} unit{sec.rows.length === 1 ? '' : 's'}
                          </span>
                        </span>
                      </td>
                    </tr>
                    {sec.rows.map((r, idx) => (
                      <tr key={`${sec.shop}-${r.unit}-${idx}`} className="crc-row">
                        <td className="crc-unit" style={{
                          position: 'sticky', left: 0, zIndex: 2, background: '#ffffff',
                          padding: '7px 12px 7px 16px', borderBottom: ROW_LINE,
                          boxShadow: 'inset -1px 0 0 #e0e3e7',
                        }}>
                          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                            <span style={{
                              fontSize: '10.5pt', fontWeight: 700, color: '#202124',
                              whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis',
                            }}>
                              {r.unit}
                            </span>
                            <StatusChip status={r.status} />
                          </div>
                          <div title={r.activity} style={{
                            fontSize: '8.5pt', color: '#80868b', marginTop: 1,
                            whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis',
                          }}>
                            {r.activity}
                          </div>
                        </td>
                        {r.months.map((m, mi) => (
                          <td key={mi} style={{
                            padding: '3px 0', borderBottom: ROW_LINE, borderLeft: '1px solid #f1f3f4',
                            position: 'relative', background: Math.floor(mi / 3) % 2 ? QTR_SHADE : '#ffffff',
                          }}>
                            {todayPos?.index === mi && (
                              <div style={{
                                position: 'absolute', top: 0, bottom: -1, left: `${todayPos.frac * 100}%`,
                                width: 2, marginLeft: -1, background: TODAY, opacity: 0.7,
                                zIndex: 1, pointerEvents: 'none',
                              }} />
                            )}
                            <Lane bars={m.plan_bars} kind="plan" label={m.plan_days} />
                            <Lane
                              bars={m.actual_bars} kind="actual"
                              label={m.actual_days ? `${m.actual_days} day${m.actual_days === 1 ? '' : 's'}` : ''}
                            />
                          </td>
                        ))}
                      </tr>
                    ))}
                  </React.Fragment>
                ))}
                {data.sections.length === 0 && (
                  <tr>
                    <td colSpan={nCols} style={{ padding: '48px', textAlign: 'center', color: '#5f6368' }}>
                      No Capital Repair rows for {data.plant_title}, FY {fy}.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
            <style>{HOVER_CSS}</style>
          </div>
        )}
    </ReportPage>
  );
}

const UNIT_W = 210;     // sticky Unit column width (px)
const Q_H = 24;         // quarter header row height (px)
const HEADER_H = 58;    // both header rows (px) - shop bars stick just below
const ROW_LINE = '1px solid #eceff1';
const TODAY = '#d93025';
const QTR_SHADE = '#fafbfd';         // alternate quarters, body
const QTR_SHADE_HEAD = '#f6f8fb';    // alternate quarters, header
const QUARTERS = ['Q1 · APR–JUN', 'Q2 · JUL–SEP', 'Q3 · OCT–DEC', 'Q4 · JAN–MAR'];
const HOVER_CSS = `
  .crc-row:hover td { background-color: #f5f9ff !important; }
  .crc-row:hover .crc-unit { box-shadow: inset 3px 0 0 #1a73e8, inset -1px 0 0 #e0e3e7; }
`;

const barBase = { position: 'absolute', top: 0, height: 8, borderRadius: 4 };
const PLAN_BAR = {
  background: 'linear-gradient(180deg, #fde68a, #f6c343)', boxShadow: 'inset 0 0 0 1px rgba(180,120,0,.25)',
};
const ACTUAL_BAR = {
  background: 'linear-gradient(180deg, #7fb2ff, #3b7ddd)', boxShadow: 'inset 0 0 0 1px rgba(20,60,140,.2)',
};
const ONGOING_BAR = {
  background: 'repeating-linear-gradient(135deg, #3b7ddd 0 5px, #7fb2ff 5px 10px)',
  boxShadow: 'inset 0 0 0 1px rgba(20,60,140,.2)',
};
const LANE_TEXT = { plan: '#8a5a00', actual: '#174ea6' };

// Where today falls: its month column and the fraction through that month.
function todayPosition(data) {
  if (!data?.today || !data?.months) return null;
  const [y, m, d] = data.today.split('-').map(Number);
  const index = data.months.indexOf(data.today.slice(0, 7));
  if (index < 0) return null;
  return { index, frac: (d - 0.5) / new Date(y, m, 0).getDate() };
}

function headCell(top) {
  return {
    position: 'sticky', top, zIndex: 4, background: '#ffffff', color: '#3c4043',
    fontSize: '9.5pt', fontWeight: 700, textAlign: 'center', whiteSpace: 'nowrap',
    borderBottom: '1px solid #e0e3e7', boxSizing: 'border-box', padding: 0,
  };
}

// One lane of a month cell (Plan on top, Actual below): the days as a small
// label over a bar drawn to scale - each [from, to, tooltip] is the fraction
// of the month covered. An edge that runs on into the next/previous month is
// squared off so a multi-month repair reads as one continuous bar.
function Lane({ bars, kind, label }) {
  return (
    <div style={{ padding: '1px 0' }}>
      <div style={{
        height: 12, color: LANE_TEXT[kind], fontSize: '7.5pt', fontWeight: 700, lineHeight: '12px',
        textAlign: 'center', whiteSpace: 'nowrap', fontVariantNumeric: 'tabular-nums',
      }}>
        {label}
      </div>
      <div style={{ position: 'relative', height: 8 }}>
        {(bars || []).map(([from, to, tip], i) => {
          const look = kind === 'plan' ? PLAN_BAR : (tip || '').includes('in progress') ? ONGOING_BAR : ACTUAL_BAR;
          const l = from <= 0 ? 0 : 4;
          const r = to >= 1 ? 0 : 4;
          return (
            <div key={i} title={tip} style={{
              ...barBase, ...look, left: `${from * 100}%`, width: `max(${(to - from) * 100}%, 3px)`,
              borderRadius: `${l}px ${r}px ${r}px ${l}px`,
            }} />
          );
        })}
      </div>
    </div>
  );
}

function Swatch({ bar }) {
  return <span style={{ ...bar, width: 26, height: 8, borderRadius: 4, display: 'inline-block' }} />;
}

function StatusChip({ status }) {
  if (!status) return null;
  const s = {
    ongoing: { text: 'In progress', bg: '#e8f0fe', fg: '#1967d2' },
    deferred: { text: 'Deferred', bg: '#fce8e6', fg: '#c5221f' },
    done: { text: 'Done', bg: '#e6f4ea', fg: '#188038' },
  }[status];
  if (!s) return null;
  return (
    <span style={{
      fontSize: '7.5pt', fontWeight: 700, padding: '1px 7px', borderRadius: '10px',
      background: s.bg, color: s.fg, whiteSpace: 'nowrap', flexShrink: 0,
    }}>
      {s.text}
    </span>
  );
}

function StatTile({ label, value, accent }) {
  return (
    <div style={{
      background: '#ffffff', border: '1px solid #e0e3e7', borderTop: `3px solid ${accent}`,
      borderRadius: '10px', padding: '8px 16px', minWidth: 130,
    }}>
      <div style={{
        fontSize: '17pt', fontWeight: 800, color: '#202124', lineHeight: 1.15, fontVariantNumeric: 'tabular-nums',
      }}>
        {value ?? '–'}
      </div>
      <div style={{ fontSize: '9pt', color: '#5f6368', fontWeight: 600 }}>{label}</div>
    </div>
  );
}

function LegendItem({ swatch, children }) {
  return (
    <span style={{ display: 'inline-flex', alignItems: 'center', gap: '6px' }}>
      {swatch}
      {children}
    </span>
  );
}
