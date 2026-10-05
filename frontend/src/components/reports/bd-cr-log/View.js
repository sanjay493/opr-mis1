'use client';

// Breakdown & Capital Repair log — one plant at a time (plant sub-tabs), one
// table per unit (BF-1, SMS-2, …), each listing that unit's breakdowns (BD)
// and actual capital repairs (CR) month by month in start-date order. Data
// comes straight from the existing /api/breakdown and /api/capital-repair
// endpoints (breakdown_table / capital_repair_table); nothing new server-side.
// Capital repairs without actual dates (planned only) are left out, per
// direct instruction. BD hours follow the Breakdown Analysis tab's rule: the
// entered hours-lost override if any, else the start-to-end span.

import React, { useEffect, useMemo, useState } from 'react';
import { ReportPage } from '../ReportUI';
import {
  API_BASE, CURRENT_FY_END_YEAR, selStyle, pillStyle, ErrorBox, TabIntro,
} from '@/components/techno/shared';

const PLANTS = ['BSP', 'DSP', 'RSP', 'BSL', 'ISP'];
const PLANT_LABEL = {
  BSP: 'Bhilai Steel Plant', DSP: 'Durgapur Steel Plant', RSP: 'Rourkela Steel Plant',
  BSL: 'Bokaro Steel Plant', ISP: 'IISCO Steel Plant',
};
// Unit tables are ordered by unit type in this order, then by unit name.
const TYPE_ORDER = ['BF', 'SMS', 'SINTER', 'COKE', 'MILL', 'GENERAL', 'OTHER'];
const TYPE_LABEL = {
  BF: 'Blast Furnace', SMS: 'SMS', SINTER: 'Sinter Plant', COKE: 'Coke Oven',
  MILL: 'Rolling Mill', GENERAL: 'Plant-Level General', OTHER: 'Other',
};
const MON = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
const KIND_STYLE = {
  BD: { bg: '#fce8e6', fg: '#c5221f', label: 'BD' },
  CR: { bg: '#e8f0fe', fg: '#1a56c4', label: 'CR' },
};

function defaultFy() {
  const endYear = CURRENT_FY_END_YEAR;
  return `${endYear - 1}-${String(endYear % 100).padStart(2, '0')}`;
}

function fyOptions() {
  return Array.from({ length: 6 }, (_, i) => {
    const start = CURRENT_FY_END_YEAR - 1 - i;
    return `${start}-${String((start + 1) % 100).padStart(2, '0')}`;
  });
}

function parseTs(ts) {
  if (!ts) return null;
  const d = new Date(String(ts).replace(' ', 'T'));
  return Number.isNaN(d.getTime()) ? null : d;
}

// "03 Apr" or "03 Apr 06:00" when the stored value carries a time.
function fmtDate(ts) {
  const d = parseTs(ts);
  if (!d) return '';
  const base = `${String(d.getDate()).padStart(2, '0')} ${MON[d.getMonth()]}`;
  return String(ts).length > 10 ? `${base} ${String(ts).slice(11, 16)}` : base;
}

function fmtRange(start, end, ongoing) {
  if (ongoing) return `from ${fmtDate(start)} — ongoing`;
  if (!end || String(end).slice(0, 10) === String(start).slice(0, 10) && String(start).length <= 10) return fmtDate(start);
  return `${fmtDate(start)} – ${fmtDate(end)}`;
}

function fmtHours(hours) {
  if (hours == null) return '—';
  const totalMin = Math.round(hours * 60);
  const d = Math.floor(totalMin / 1440);
  const h = Math.floor((totalMin % 1440) / 60);
  const m = totalMin % 60;
  const parts = [];
  if (d) parts.push(`${d}d`);
  if (h) parts.push(`${h}h`);
  if (m && !d) parts.push(`${m}m`);
  return parts.join(' ') || '0m';
}

function spanHours(start, end, ongoing) {
  const s = parseTs(start);
  const e = ongoing ? new Date() : parseTs(end);
  if (!s || !e) return null;
  return Math.max(0, (e.getTime() - s.getTime()) / 3600000);
}

// Capital repair rows mostly carry their unit only as free text (shop +
// equipment; unit_type/unit_name are empty on older rows). Map them onto the
// same units the breakdown log uses, so a unit's CRs share its BD table:
//   generic shop (BF / Mills / Sinter Plant)  -> unit = equipment (BF-4, NPM)
//   SMS shops                                 -> SMS-1/SMS-2 (roman or digit),
//                                                else the plant's single "SMS"
//   specific shop (HSM-2, SP-3, RMHP)         -> unit = shop, equipment as sub
const ROMAN = { I: 1, II: 2, III: 3, IV: 4 };
const GENERIC_SHOP = /^(bf|blast furnaces?|mills?|sinter plants?|coke ovens?)$/i;
function crUnit(r) {
  if (r.unit_type && r.unit_name) return { type: r.unit_type, name: r.unit_name, sub: r.equipment };
  const shop = (r.shop || '').trim();
  const equip = (r.equipment || '').trim();
  const typeOf = (txt) => (/^(bf|blast)/i.test(txt) ? 'BF' : /^sms|conv|caster|bof/i.test(txt) ? 'SMS'
    : /sinter|^sp\b|^sp-/i.test(txt) ? 'SINTER' : /coke/i.test(txt) ? 'COKE'
      : /mill|hsm|plate|wap|rhf/i.test(txt) ? 'MILL' : 'OTHER');
  if (/^sms/i.test(shop)) {
    const m = shop.match(/^sms[\s-]*([ivx]+|\d+)\b/i);
    const n = m ? (ROMAN[m[1].toUpperCase()] || Number(m[1])) : null;
    return { type: 'SMS', name: n ? `SMS-${n}` : 'SMS', sub: equip };
  }
  if (!shop || GENERIC_SHOP.test(shop)) return { type: typeOf(shop || equip), name: equip || shop || 'Unspecified', sub: '' };
  return { type: typeOf(shop), name: shop, sub: equip };
}

// Shop-level entries are stored with unit name "Shop".
const unitTitle = (u) => (u.name === 'Shop' ? `${TYPE_LABEL[u.type]} — whole shop` : u.name);

function monthKey(ts) { return String(ts).slice(0, 7); }
function monthLabel(ym) { return `${MON[Number(ym.slice(5, 7)) - 1]}'${ym.slice(2, 4)}`; }
const subtagLabel = (s) => (s ? `${s.charAt(0)}${s.slice(1).toLowerCase()}` : '');

// BD hours: the entered hours-lost override, else the start-to-end span. A
// same-day entry with dates only (no times) and no hours entered has no
// recorded duration - null, shown as "—" rather than a misleading "0m".
function bdHours(b) {
  if (b.hours_lost_override != null) return Number(b.hours_lost_override);
  const dateOnlySameDay = !b.is_ongoing && String(b.start_ts).length <= 10
    && String(b.end_ts || b.start_ts).slice(0, 10) === String(b.start_ts).slice(0, 10);
  return dateOnlySameDay ? null : spanHours(b.start_ts, b.end_ts, b.is_ongoing);
}

// Breakdowns + actual capital repairs -> [{ key, type, name, events: [...] }]
// one per unit, units ordered by type then name, events by start date.
// A breakdown linked to its capital repair (capital_repair_id - the plant
// logged the CR in the breakdown log too) is ONE event: a CR row in the CR's
// unit table, timed by the breakdown's exact date-times.
function buildUnits(breakdowns, repairs) {
  const units = new Map();
  const unitFor = (type, name) => {
    const t = TYPE_ORDER.includes(type) ? type : 'OTHER';
    const key = `${t}|${name}`;
    if (!units.has(key)) units.set(key, { key, type: t, name, events: [] });
    return units.get(key);
  };
  const crById = new Map(repairs.filter((r) => r.actual_start).map((r) => [r.id, r]));
  const linkedBd = new Map();                          // cr id -> its breakdown entry
  for (const b of breakdowns) {
    if (b.capital_repair_id != null && crById.has(b.capital_repair_id)) linkedBd.set(b.capital_repair_id, b);
  }
  for (const b of breakdowns) {
    if (!b.start_ts) continue;
    if (b.capital_repair_id != null && crById.has(b.capital_repair_id)) continue;   // shown as its CR
    const counted = bdHours(b);
    unitFor(b.unit_type, b.unit_name).events.push({
      kind: 'BD', id: `bd-${b.id}`, start: b.start_ts,
      dates: fmtRange(b.start_ts, b.end_ts, b.is_ongoing),
      sub: subtagLabel(b.sms_subtag), details: b.cause,
      duration: fmtHours(counted) + (b.is_ongoing ? ' so far' : ''),
      ongoing: !!b.is_ongoing,
    });
  }
  for (const r of repairs) {
    if (!r.actual_start) continue;                     // planned only — not listed
    const cu = crUnit(r);
    const s = parseTs(r.actual_start);
    const e = r.actual_ongoing ? new Date() : parseTs(r.actual_end);
    const days = s && e ? Math.max(1, Math.round((e - s) / 86400000) + 1) : null;
    const sub = [subtagLabel(r.sms_subtag), cu.sub && cu.sub !== cu.name ? cu.sub : ''].filter(Boolean).join(' · ');
    const b = linkedBd.get(r.id);
    if (b) {
      // The breakdown entry's exact date-times and hours, the CR's activity
      // plus the breakdown remark.
      unitFor(cu.type, cu.name).events.push({
        kind: 'CR', id: `cr-${r.id}`, start: b.start_ts, linked: true,
        dates: fmtRange(b.start_ts, b.end_ts, b.is_ongoing),
        sub, details: `${r.activity || 'Capital repair'} — ${b.cause}`,
        duration: fmtHours(bdHours(b)) + (b.is_ongoing ? ' so far' : ''),
        ongoing: !!b.is_ongoing,
      });
      continue;
    }
    unitFor(cu.type, cu.name).events.push({
      kind: 'CR', id: `cr-${r.id}`, start: r.actual_start,
      dates: fmtRange(r.actual_start, r.actual_end, r.actual_ongoing),
      sub, details: r.activity || 'Capital repair',
      duration: days != null ? `${days} day${days === 1 ? '' : 's'}${r.actual_ongoing ? ' so far' : ''}` : '—',
      ongoing: !!r.actual_ongoing,
    });
  }
  const list = [...units.values()].filter((u) => u.events.length);
  for (const u of list) u.events.sort((a, b) => String(a.start).localeCompare(String(b.start)));
  list.sort((a, b) => TYPE_ORDER.indexOf(a.type) - TYPE_ORDER.indexOf(b.type)
    || a.name.localeCompare(b.name, undefined, { numeric: true }));
  return list;
}

export default function BdCrLogView() {
  const [plant, setPlant] = useState('BSP');
  const [fy, setFy] = useState(defaultFy());
  const [data, setData] = useState({});        // { [plant]: { breakdowns, repairs } } for the chosen FY
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  // All five plants for the FY at once, so every plant tab can show its count.
  useEffect(() => {
    let cancelled = false;
    const load = async () => {
      setLoading(true);
      setError(null);
      try {
        const entries = await Promise.all(PLANTS.map(async (p) => {
          const [bd, cr] = await Promise.all([
            fetch(`${API_BASE}/api/breakdown?plant=${p}&fy=${fy}`).then((r) => r.json()),
            fetch(`${API_BASE}/api/capital-repair?plant=${p}&fy=${fy}`).then((r) => r.json()),
          ]);
          return [p, { breakdowns: bd.rows || [], repairs: cr.rows || [] }];
        }));
        if (!cancelled) setData(Object.fromEntries(entries));
      } catch (e) {
        if (!cancelled) setError(e.message || 'Failed to load');
      } finally {
        if (!cancelled) setLoading(false);
      }
    };
    load();
    return () => { cancelled = true; };
  }, [fy]);

  const unitsByPlant = useMemo(() => Object.fromEntries(PLANTS.map((p) => [
    p, buildUnits(data[p]?.breakdowns || [], data[p]?.repairs || []),
  ])), [data]);
  const units = unitsByPlant[plant] || [];
  const countOf = (p) => (unitsByPlant[p] || []).reduce((n, u) => n + u.events.length, 0);

  return (
    <ReportPage title="Breakdown & Capital Repair Log"
      description="Each plant's breakdowns (BD) and actual capital repairs (CR), unit by unit, month by month in date order.">
      <TabIntro>
        One table per unit; each lists that unit&apos;s breakdowns and capital repairs in start-date order,
        grouped by the month they started. Capital repairs appear once they have actual dates (planned-only
        repairs are not listed). Breakdown hours are the entered hours lost, else the start-to-end span.
        A capital repair the plant also logged in the breakdown log (linked on the Breakdown entry form) is
        shown once, as the CR, timed by the breakdown entry&apos;s exact date-times (marked ⏱).
      </TabIntro>

      <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap', margin: '10px 0 12px' }}>
        <label style={{ fontSize: '9.5pt', color: '#5f6368' }}>
          FY{' '}
          <select style={selStyle} value={fy} onChange={(e) => setFy(e.target.value)}>
            {fyOptions().map((f) => <option key={f}>{f}</option>)}
          </select>
        </label>
        <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
          {PLANTS.map((p) => (
            <button key={p} type="button" style={pillStyle(p === plant)} onClick={() => setPlant(p)}
              title={PLANT_LABEL[p]}>
              {p} <span style={{ opacity: 0.75 }}>({countOf(p)})</span>
            </button>
          ))}
        </div>
        {loading && <span style={{ fontSize: '9pt', color: '#5f6368' }}>Loading…</span>}
      </div>

      {error && <ErrorBox>{error}</ErrorBox>}

      {!loading && !error && units.length === 0 && (
        <div style={{ padding: 30, textAlign: 'center', color: '#5f6368', border: '1px solid #dadce0', borderRadius: 8 }}>
          No breakdowns or capital repairs recorded for {plant} in {fy}.
        </div>
      )}

      {units.length > 0 && (
        <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', marginBottom: 14 }}>
          {units.map((u) => (
            <a key={u.key} href={`#unit-${plant}-${u.key}`} style={{
              fontSize: '8.5pt', padding: '3px 9px', borderRadius: 12, border: '1px solid #dadce0',
              color: '#202124', textDecoration: 'none', background: '#f8f9fa',
            }}>
              {unitTitle(u)} <span style={{ color: '#5f6368' }}>({u.events.length})</span>
            </a>
          ))}
        </div>
      )}

      {units.map((u) => <UnitTable key={u.key} plant={plant} unit={u} />)}
    </ReportPage>
  );
}

function UnitTable({ plant, unit }) {
  // Month groups in order, each with its rowspan and BD/CR counts.
  const groups = [];
  for (const ev of unit.events) {
    const ym = monthKey(ev.start);
    if (!groups.length || groups[groups.length - 1].ym !== ym) groups.push({ ym, events: [] });
    groups[groups.length - 1].events.push(ev);
  }
  const bd = unit.events.filter((e) => e.kind === 'BD').length;
  const cr = unit.events.length - bd;
  return (
    <section id={`unit-${plant}-${unit.key}`} style={{ marginBottom: 18, scrollMarginTop: 70 }}>
      <h3 style={{ fontSize: '11pt', fontWeight: 700, color: '#202124', margin: '0 0 6px' }}>
        {unitTitle(unit)}{' '}
        <span style={{ fontWeight: 400, fontSize: '9pt', color: '#5f6368' }}>
          {TYPE_LABEL[unit.type]} · {bd} breakdown{bd === 1 ? '' : 's'}, {cr} capital repair{cr === 1 ? '' : 's'}
        </span>
      </h3>
      <div style={{ border: '1px solid #dadce0', borderRadius: 8, overflowX: 'auto' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse', background: '#fff' }}>
          <thead>
            <tr style={{ background: '#f8f9fa', borderBottom: '1px solid #dadce0' }}>
              <th style={{ ...TH, width: 90 }}>Month</th>
              <th style={{ ...TH, width: 170 }}>Dates</th>
              <th style={{ ...TH, width: 50 }}>Type</th>
              <th style={TH}>Details</th>
              <th style={{ ...TH, width: 110, textAlign: 'right' }}>Duration</th>
            </tr>
          </thead>
          <tbody>
            {groups.map((g) => g.events.map((ev, i) => {
              const k = KIND_STYLE[ev.kind];
              const nBd = g.events.filter((e) => e.kind === 'BD').length;
              return (
                <tr key={ev.id} style={{ borderTop: i === 0 ? '1px solid #c4c7c5' : '1px solid #f1f3f4' }}>
                  {i === 0 && (
                    <td rowSpan={g.events.length} style={{ ...TD, fontWeight: 700, verticalAlign: 'top', background: '#fafafa' }}>
                      {monthLabel(g.ym)}
                      <div style={{ fontWeight: 400, fontSize: '8pt', color: '#5f6368' }}>
                        {nBd ? `${nBd} BD` : ''}{nBd && g.events.length - nBd ? ' · ' : ''}
                        {g.events.length - nBd ? `${g.events.length - nBd} CR` : ''}
                      </div>
                    </td>
                  )}
                  <td style={{ ...TD, whiteSpace: 'nowrap' }}>{ev.dates}</td>
                  <td style={{ ...TD, whiteSpace: 'nowrap' }}>
                    <span style={{
                      padding: '1px 7px', borderRadius: 10, fontSize: '8pt', fontWeight: 700,
                      background: k.bg, color: k.fg,
                    }}>{k.label}</span>
                    {ev.linked && (
                      <span title="Also logged in the breakdown log — dates and duration taken from that entry's exact times"
                        style={{ marginLeft: 4, fontSize: '8pt', color: '#5f6368' }}>⏱</span>
                    )}
                  </td>
                  <td style={TD}>
                    {ev.sub && <span style={{ color: '#5f6368', marginRight: 6 }}>[{ev.sub}]</span>}
                    {ev.details}
                  </td>
                  <td style={{ ...TD, textAlign: 'right', whiteSpace: 'nowrap', color: ev.ongoing ? '#b06000' : undefined }}>
                    {ev.duration}
                  </td>
                </tr>
              );
            }))}
          </tbody>
        </table>
      </div>
    </section>
  );
}

const TH = { padding: '8px 10px', textAlign: 'left', fontWeight: 700, fontSize: '9pt', color: '#5f6368' };
const TD = { padding: '6px 10px', fontSize: '9pt', color: '#202124', verticalAlign: 'top' };
