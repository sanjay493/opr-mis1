'use client';

import React, { useState, useEffect, useMemo, useRef, useCallback } from 'react';
import GlobalNavbar from '@/components/GlobalNavbar';
import css from './highlights.module.css';

const API = process.env.NEXT_PUBLIC_API_URL || '';

// Display label → item_name in production_table
const ITEMS = [
  { label: 'Sinter',         key: 'Total Sinter' },
  { label: 'Hot Metal',      key: 'Hot Metal' },
  { label: 'Crude Steel',    key: 'Total Crude Steel' },
  { label: 'Saleable Steel', key: 'Saleable Steel' },
  { label: 'Pig Iron',       key: 'Pig Iron' },
  { label: 'Finished Steel', key: 'Finished Steel' },
];

const PLANTS_MAIN5 = ['BSP', 'DSP', 'RSP', 'BSL', 'ISP'];
const UNITS3       = ['ASP', 'SSP', 'VISL'];
const PLANTS_ALL8  = [...PLANTS_MAIN5, ...UNITS3];

const VIEWS = [
  { id: 'SAIL5', label: 'SAIL (5 Plants)' },
  { id: 'SAIL8', label: 'SAIL (8 Plants)' },
  { id: 'PLANT', label: 'Plant-wise' },
  { id: 'UNIT',  label: 'Unit-wise' },
];

const PERIOD_TYPES = [
  { id: 'month',   label: 'Monthly' },
  { id: 'quarter', label: 'Quarterly' },
  { id: 'half',    label: 'Half-Yearly' },
  { id: 'fy',      label: 'Financial Year' },
  { id: 'cy',      label: 'Calendar Year' },
  { id: 'custom',  label: 'Custom Range' },
];

// Scopes for the Records section — keys of /api/production-records
const RECORD_SCOPES = [
  { key: 'sail5', label: 'SAIL (5 Plants)', kind: 'Groups' },
  { key: 'all8',  label: 'SAIL (8 Plants)', kind: 'Groups' },
  ...PLANTS_MAIN5.map(p => ({ key: p, label: p, kind: 'Plants' })),
  ...UNITS3.map(p => ({ key: p, label: p, kind: 'Units' })),
];

// Items summarised in the "output" card
const KEY_ITEMS = [
  { label: 'Hot Metal',      key: 'Hot Metal' },
  { label: 'Crude Steel',    key: 'Total Crude Steel' },
  { label: 'Saleable Steel', key: 'Saleable Steel' },
];
// Crude-steel share bar, largest plant first
const SHARE_COLORS = ['#1a73e8', '#8ab4f8', '#34a853', '#fbbc04', '#9aa0a6', '#a142f4', '#f28b82', '#5f6368'];
// Record period types, in table-column order (order = spotlight tie-break)
const RECORD_KINDS = [
  { id: 'month',   label: 'Monthly peak',        head: 'Best Month',          order: 0 },
  { id: 'quarter', label: 'Quarterly peak',      head: 'Best Quarter',        order: 1 },
  { id: 'half',    label: 'Half-year peak',      head: 'Best Half',           order: 2 },
  { id: 'fy',      label: 'Financial-year peak', head: 'Best Financial Year', order: 3 },
  { id: 'cy',      label: 'Calendar-year peak',  head: 'Best Calendar Year',  order: 4 },
];

// ── Best-Period query (custom month window, top-5 FYs) ──────────────────────
const BP_SCOPES = [
  { id: 'sail5',  label: 'SAIL (5 Plants)' },
  { id: 'all8',   label: 'SAIL (8 Plants)' },
  { id: 'plants', label: 'Plant-wise (all 8)' },
];
// Months in financial-year order (Apr → Mar); value = calendar month number.
const FY_MONTH_ORDER = [4, 5, 6, 7, 8, 9, 10, 11, 12, 1, 2, 3];
const fyPos = (m) => (m >= 4 ? m - 4 : m + 8);
const monLbl = (m) => MONTH_LABEL[String(m).padStart(2, '0')];
const isRateKey = (k) => /\/day|\/d\)/i.test(k) || k.toUpperCase().startsWith('COB#');

const MONTH_LABEL = {
  '01': 'January', '02': 'February', '03': 'March', '04': 'April',
  '05': 'May', '06': 'June', '07': 'July', '08': 'August',
  '09': 'September', '10': 'October', '11': 'November', '12': 'December',
};

const QUARTERS = [
  { id: 1, label: 'Q1 (Apr–Jun)' },
  { id: 2, label: 'Q2 (Jul–Sep)' },
  { id: 3, label: 'Q3 (Oct–Dec)' },
  { id: 4, label: 'Q4 (Jan–Mar)' },
];
const HALVES = [
  { id: 1, label: 'H1 (Apr–Sep)' },
  { id: 2, label: 'H2 (Oct–Mar)' },
];

// FY months: April of fy_start … March of fy_start+1
const fyMonths = (fyStart) => [
  ...Array.from({ length: 9 }, (_, i) => `${fyStart}-${String(i + 4).padStart(2, '0')}`),
  ...Array.from({ length: 3 }, (_, i) => `${fyStart + 1}-${String(i + 1).padStart(2, '0')}`),
];
const cyMonths = (year) =>
  Array.from({ length: 12 }, (_, i) => `${year}-${String(i + 1).padStart(2, '0')}`);

const fyOfMonth = (m) => {
  const y = Number(m.slice(0, 4)), mo = Number(m.slice(5, 7));
  return mo >= 4 ? y : y - 1;
};
const shiftYear = (m, delta) => `${Number(m.slice(0, 4)) + delta}${m.slice(4)}`;
const fyLabel = (y) => `${y}-${String(y + 1).slice(2)}`;

// ── Records helpers ─────────────────────────────────────────────────────────
// Items reported for a records scope. Single-plant scopes report every
// unit/item of that plant (BF#1, SMS-2, URM …); group scopes carry only the
// summary items. Friendly labels are used where an item matches the summary
// list, raw names otherwise.
const recordItems = (records, scopeKey) => {
  const names = records?.[scopeKey]?.items;
  if (!names || !names.length) return ITEMS;
  return names.map(name => ITEMS.find(i => i.key === name) || { label: name, key: name });
};

// Best-ever records for a scope:
// rows[itemKey] = { month, quarter, half, fy, cy }, each
// { best, second } where best/second = {period, total, end} | null —
// end = last month of the record period, used to flag fresh records.
// The per-period top-2 sets from the API always contain the global #1 and
// #2 (the global #2 is either the same period's runner-up or another
// period's #1), so sorting their union gives both.
const buildRecordRows = (records, scopeKey, items) => {
  const scope = records?.[scopeKey];
  if (!scope) return null;
  const qEnd = (fy, q) => (q === 4 ? `${fy + 1}-03` : `${fy}-${String(q * 3 + 3).padStart(2, '0')}`);
  const top2 = (arr) => {
    const sorted = [...arr].sort((a, b) => (b.total ?? -Infinity) - (a.total ?? -Infinity));
    return { best: sorted[0] ?? null, second: sorted[1] ?? null };
  };
  const out = {};
  items.forEach(({ key }) => {
    const monFlat = Object.values(scope.cal_months?.[key] || {}).flat()
      .filter(r => r.total != null)
      .map(r => ({ period: r.period, total: r.total, end: r.month }));

    const qFlat = Object.entries(scope.fy_quarters?.[key] || {}).flatMap(([label, rows]) =>
      (rows || []).filter(r => r.total != null).map(r => ({
        period: `${r.period} ${label}`,
        total: r.total,
        end: qEnd(r.fy_start, Number(label[1])),
      })));

    const hFlat = Object.entries(scope.fy_halves?.[key] || {}).flatMap(([label, rows]) =>
      (rows || []).filter(r => r.total != null).map(r => ({
        period: `${label} ${r.period}`,
        total: r.total,
        end: label.startsWith('H1') ? `${r.fy_start}-09` : `${r.fy_start + 1}-03`,
      })));

    const fyRows = (scope.top5_fy?.[key] || [])
      .map(r => ({ ...r, end: `${parseInt(r.period, 10) + 1}-03` }));
    const cyRows = (scope.top5_cy?.[key] || [])
      .map(r => ({ ...r, end: `${r.period}-12` }));

    out[key] = {
      month:   top2(monFlat),
      quarter: top2(qFlat),
      half:    top2(hFlat),
      fy:      { best: fyRows[0] ?? null, second: fyRows[1] ?? null },
      cy:      { best: cyRows[0] ?? null, second: cyRows[1] ?? null },
    };
  });
  return out;
};

// Flat list of best-ever records (one per item × period kind)
const buildRecordList = (rows, items) => {
  if (!rows) return [];
  const list = [];
  items.forEach(({ label, key }) => {
    RECORD_KINDS.forEach(({ id, label: kind, order }) => {
      const rec = rows[key]?.[id];
      if (rec?.best) list.push({ item: label, kind, order, best: rec.best, second: rec.second });
    });
  });
  return list;
};

// Records scope that matches the top View selector (no 3-unit group exists
// in the records API, so Unit-wise falls back to all 8 plants).
const VIEW_RECORD_SCOPE = { SAIL5: 'sail5', SAIL8: 'all8', PLANT: 'sail5', UNIT: 'all8' };

export default function HighlightsPage() {
  const [fys, setFys]             = useState([]);
  const [view, setView]           = useState('SAIL5');
  const [periodType, setPeriodType] = useState('month');
  const [fyStart, setFyStart]     = useState(null);
  const [monthIdx, setMonthIdx]   = useState(0);   // 0 = April … 11 = March
  const [quarter, setQuarter]     = useState(1);
  const [half, setHalf]           = useState(1);
  const [cyYear, setCyYear]       = useState(null);
  const [customStart, setCustomStart] = useState(null);
  const [customEnd, setCustomEnd]     = useState(null);
  const [fyCache, setFyCache]     = useState({});  // fy_start -> /api/production-fy response
  const [error, setError]         = useState(null);
  const [inTonnes, setInTonnes]   = useState(false);
  const [records, setRecords]     = useState(null);   // /api/production-records response
  const [recordsError, setRecordsError] = useState(null);
  const [recordScope, setRecordScope]   = useState('sail5');
  const inflight = useRef(new Set());

  // Best-Period query state
  const [bpScope, setBpScope]     = useState('sail5');
  const [bpItems, setBpItems]     = useState('major');
  const [bpFrom, setBpFrom]       = useState(4);   // April
  const [bpTo, setBpTo]           = useState(9);   // September
  const [bpData, setBpData]       = useState(null);
  const [bpError, setBpError]     = useState(null);
  const [bpLoading, setBpLoading] = useState(false);
  const bpValid = fyPos(bpTo) >= fyPos(bpFrom);

  // ── FY list; default selection = period containing last month ──────────────
  useEffect(() => {
    (async () => {
      try {
        const r = await fetch(`${API}/api/production-fys`);
        const d = await r.json();
        const list = d.fys || [];
        setFys(list);
        if (list.length) {
          const now = new Date();
          const prev = new Date(now.getFullYear(), now.getMonth() - 1, 1);
          const prevKey = `${prev.getFullYear()}-${String(prev.getMonth() + 1).padStart(2, '0')}`;
          const prevFy = fyOfMonth(prevKey);
          const fy = list.some(f => f.fy_start === prevFy) ? prevFy : list[0].fy_start;
          setFyStart(fy);
          setCyYear(Number(prevKey.slice(0, 4)));
          setCustomStart(prevKey);
          setCustomEnd(prevKey);
          const idx = fyMonths(fy).indexOf(prevKey);
          if (idx >= 0) {
            setMonthIdx(idx);
            setQuarter(Math.floor(idx / 3) + 1);
            setHalf(idx < 6 ? 1 : 2);
          }
        }
      } catch (e) {
        setError(`Could not load financial years: ${e.message}`);
      }
    })();
  }, []);

  // ── Records (best-ever) data — one fetch, all scopes ────────────────────────
  useEffect(() => {
    (async () => {
      try {
        const r = await fetch(`${API}/api/production-records`);
        if (!r.ok) throw new Error(await r.text());
        setRecords(await r.json());
      } catch (e) {
        setRecordsError(`Could not load records: ${e.message}`);
      }
    })();
  }, []);

  // ── Best-Period query — refetch whenever the window / scope / items change ──
  useEffect(() => {
    if (!bpValid) { setBpData(null); setBpError(null); return; }
    let cancelled = false;
    setBpLoading(true); setBpError(null);
    fetch(`${API}/api/best-period-records?start_mon=${bpFrom}&end_mon=${bpTo}&scope=${bpScope}&items=${bpItems}`)
      .then(async r => { if (!r.ok) throw new Error(await r.text()); return r.json(); })
      .then(d => { if (!cancelled) setBpData(d); })
      .catch(e => { if (!cancelled) { setBpError(e.message); setBpData(null); } })
      .finally(() => { if (!cancelled) setBpLoading(false); });
    return () => { cancelled = true; };
  }, [bpScope, bpItems, bpFrom, bpTo, bpValid]);

  // Calendar-year options derived from FY list (each FY touches two years)
  const cyOptions = useMemo(() => {
    const s = new Set();
    fys.forEach(f => { s.add(f.fy_start); s.add(f.fy_start + 1); });
    return [...s].sort((a, b) => b - a);
  }, [fys]);

  // All months available across every FY, for the custom-range pickers
  const allMonths = useMemo(() => {
    const s = new Set();
    fys.forEach(f => fyMonths(f.fy_start).forEach(m => s.add(m)));
    return [...s].sort();
  }, [fys]);

  // ── Months of the selected period, and same period last year (CPLY) ────────
  const periodMonthList = useMemo(() => {
    if (periodType === 'custom') {
      if (!customStart || !customEnd) return [];
      const [s, e] = customStart <= customEnd ? [customStart, customEnd] : [customEnd, customStart];
      return allMonths.filter(m => m >= s && m <= e);
    }
    if (periodType === 'cy') return cyYear != null ? cyMonths(cyYear) : [];
    if (fyStart == null) return [];
    const all = fyMonths(fyStart);
    if (periodType === 'month')   return [all[monthIdx]];
    if (periodType === 'quarter') return all.slice((quarter - 1) * 3, quarter * 3);
    if (periodType === 'half')    return half === 1 ? all.slice(0, 6) : all.slice(6, 12);
    return all; // fy
  }, [periodType, fyStart, monthIdx, quarter, half, cyYear, customStart, customEnd, allMonths]);

  const cplyMonthList = useMemo(
    () => periodMonthList.map(m => shiftYear(m, -1)), [periodMonthList]);

  // ── Fetch every FY dataset the two periods touch ───────────────────────────
  const neededFys = useMemo(() => {
    const s = new Set([...periodMonthList, ...cplyMonthList].map(fyOfMonth));
    return [...s].sort();
  }, [periodMonthList, cplyMonthList]);

  useEffect(() => {
    neededFys.forEach(fy => {
      if (fyCache[fy] !== undefined || inflight.current.has(fy)) return;
      inflight.current.add(fy);
      (async () => {
        try {
          const r = await fetch(`${API}/api/production-fy?fy_start=${fy}`);
          if (!r.ok) throw new Error(await r.text());
          const d = await r.json();
          setFyCache(prev => ({ ...prev, [fy]: d }));
        } catch (e) {
          setError(`Load failed for FY ${fyLabel(fy)}: ${e.message}`);
          setFyCache(prev => ({ ...prev, [fy]: null }));
        } finally {
          inflight.current.delete(fy);
        }
      })();
    });
  }, [neededFys, fyCache]);

  const loading = neededFys.some(fy => fyCache[fy] === undefined);

  // ── Value lookup / aggregation ─────────────────────────────────────────────
  const look = useCallback((plant, item, kind, month) => {
    const d = fyCache[fyOfMonth(month)];
    if (!d) return null;
    const it = d.plants?.find(p => p.plant === plant)?.items?.find(i => i.item_name === item);
    return it?.[kind]?.[month] ?? null;
  }, [fyCache]);

  // Sum an item over plants × months; Conversion (plant 'SAIL') only ever adds
  // to Finished Steel, mirroring the Major Production page's SAIL Total.
  const aggregate = useCallback((plants, itemKey, kind, monthList, includeConversion) => {
    let sum = null;
    monthList.forEach(m => {
      plants.forEach(p => {
        const v = look(p, itemKey, kind, m);
        if (v != null) sum = (sum ?? 0) + v;
      });
      if (includeConversion && itemKey === 'Finished Steel') {
        const cv = look('SAIL', 'Conversion', kind, m);
        if (cv != null) sum = (sum ?? 0) + cv;
      }
    });
    return sum != null ? Math.round(sum * 1000) / 1000 : null;
  }, [look]);

  // ── Column groups for the active view ──────────────────────────────────────
  const groups = useMemo(() => {
    if (view === 'SAIL5') return [{ label: 'SAIL (5 Plants)', plants: PLANTS_MAIN5, conv: false }];
    if (view === 'SAIL8') return [{ label: 'SAIL (8 Plants + Conv.)', plants: PLANTS_ALL8, conv: true }];
    if (view === 'PLANT') return [
      ...PLANTS_MAIN5.map(p => ({ label: p, plants: [p], conv: false })),
      { label: 'Total (5 Plants)', plants: PLANTS_MAIN5, conv: false, isTotal: true },
    ];
    return [
      ...UNITS3.map(p => ({ label: p, plants: [p], conv: false })),
      { label: 'Total (3 Units)', plants: UNITS3, conv: false, isTotal: true },
    ];
  }, [view]);

  const singleGroup = groups.length === 1; // summary views also show CPLY value column

  // rows[item][group] = { plan, actual, ach, cply, growth }
  const rows = useMemo(() => {
    const out = {};
    ITEMS.forEach(({ key }) => {
      out[key] = groups.map(g => {
        const plan   = aggregate(g.plants, key, 'plan',   periodMonthList, g.conv);
        const actual = aggregate(g.plants, key, 'actual', periodMonthList, g.conv);
        const cply   = aggregate(g.plants, key, 'actual', cplyMonthList,   g.conv);
        const ach    = plan != null && plan !== 0 && actual != null ? (actual / plan) * 100 : null;
        const growth = cply != null && cply !== 0 && actual != null ? ((actual - cply) / cply) * 100 : null;
        return { plan, actual, ach, cply, growth };
      });
    });
    return out;
  }, [groups, aggregate, periodMonthList, cplyMonthList]);

  const hasAnyData = ITEMS.some(({ key }) =>
    rows[key].some(c => c.plan != null || c.actual != null));

  // ── Labels & formatting ─────────────────────────────────────────────────────
  const periodLabel = useMemo(() => {
    if (periodType === 'custom') {
      if (!customStart || !customEnd) return '';
      const [s, e] = customStart <= customEnd ? [customStart, customEnd] : [customEnd, customStart];
      const sLabel = `${MONTH_LABEL[s.slice(5)]} ${s.slice(0, 4)}`;
      const eLabel = `${MONTH_LABEL[e.slice(5)]} ${e.slice(0, 4)}`;
      return s === e ? sLabel : `${sLabel} – ${eLabel}`;
    }
    if (periodType === 'cy') return `Calendar Year ${cyYear ?? ''}`;
    if (fyStart == null) return '';
    if (periodType === 'month') {
      const m = fyMonths(fyStart)[monthIdx];
      return `${MONTH_LABEL[m.slice(5)]} ${m.slice(0, 4)}`;
    }
    if (periodType === 'quarter') return `${QUARTERS[quarter - 1].label} FY ${fyLabel(fyStart)}`;
    if (periodType === 'half')    return `${HALVES[half - 1].label} FY ${fyLabel(fyStart)}`;
    return `Financial Year ${fyLabel(fyStart)}`;
  }, [periodType, fyStart, monthIdx, quarter, half, cyYear, customStart, customEnd]);

  const fmt = (v) => {
    if (v == null) return '—';
    if (inTonnes) return Math.round(v * 1000).toLocaleString('en-IN');
    return v.toLocaleString('en-IN', { minimumFractionDigits: 3, maximumFractionDigits: 3 });
  };
  const fmtPct = (v) => (v == null ? '—' : `${v.toFixed(1)}%`);

  // ── Records for the spotlight's scope ───────────────────────────────────────
  const scopeItems = useMemo(() => recordItems(records, recordScope), [records, recordScope]);
  const recordRows = useMemo(() => buildRecordRows(records, recordScope, scopeItems), [records, recordScope, scopeItems]);

  // Months between the record period's end and the newest data month;
  // a record is "just set" when its period ended within the last 3 months.
  const monthsAgo = useCallback((end) => {
    const latest = records?.latest_month;
    if (!latest || !end) return null;
    return (Number(latest.slice(0, 4)) - Number(end.slice(0, 4))) * 12 +
           (Number(latest.slice(5, 7)) - Number(end.slice(5, 7)));
  }, [records]);
  const isFreshRecord = (rec) => {
    const ago = monthsAgo(rec?.end);
    return ago != null && ago >= 0 && ago <= 3;
  };

  const recordsHaveData = recordRows && scopeItems.some(({ key }) =>
    Object.values(recordRows[key] || {}).some(v => v?.best != null));

  const handlePrint = () => window.print();

  const handleDownloadExcel = () => {
    const csvVal = (v) => (v == null ? '' : inTonnes ? String(Math.round(v * 1000)) : v.toFixed(3));
    const escape = (s) => (/[",\r\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s);
    const header = ['Item'];
    groups.forEach(g => {
      header.push(`${g.label} Plan`, `${g.label} Actual`, `${g.label} % Ach`);
      if (singleGroup) header.push(`${g.label} CPLY`);
      header.push(`${g.label} Growth %`);
    });
    const body = ITEMS.map(({ label, key }) => {
      const row = [label];
      rows[key].forEach(c => {
        row.push(csvVal(c.plan), csvVal(c.actual), c.ach == null ? '' : c.ach.toFixed(1));
        if (singleGroup) row.push(csvVal(c.cply));
        row.push(c.growth == null ? '' : c.growth.toFixed(1));
      });
      return row;
    });
    const csv = [header, ...body].map(r => r.map(v => escape(String(v))).join(',')).join('\r\n');
    const blob = new Blob(['﻿' + csv], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `Highlights_${VIEWS.find(v => v.id === view).label.replace(/[^a-z0-9]+/gi, '_')}_${periodLabel.replace(/[^a-z0-9]+/gi, '_')}.csv`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };

  // ── Summary cards ───────────────────────────────────────────────────────────
  // Figures for the cards come from the single summary column, or the Total
  // column in the plant/unit-wise views.
  const sumIdx = Math.max(groups.findIndex(g => g.isTotal), 0);
  const keyStats = KEY_ITEMS.map(({ label, key }) => ({ label, ...(rows[key]?.[sumIdx] || {}) }));

  // Crude steel share of each plant in the selected period
  const sharePlants = view === 'UNIT' ? UNITS3 : view === 'SAIL8' ? PLANTS_ALL8 : PLANTS_MAIN5;
  const share = useMemo(() => {
    const vals = sharePlants
      .map(p => ({ plant: p, value: aggregate([p], 'Total Crude Steel', 'actual', periodMonthList, false) }))
      .filter(x => x.value != null && x.value > 0);
    const total = vals.reduce((a, x) => a + x.value, 0);
    return { total, rows: vals.map(x => ({ ...x, pct: total ? (x.value / total) * 100 : 0 })).sort((a, b) => b.value - a.value) };
  }, [sharePlants, aggregate, periodMonthList]);

  // ── YTD (FY start → end of the selected month/quarter/half) ────────────────
  const ytdMonthList = useMemo(() => {
    if (fyStart == null || !['month', 'quarter', 'half'].includes(periodType)) return null;
    const end = periodType === 'month' ? monthIdx : periodType === 'quarter' ? quarter * 3 - 1 : half * 6 - 1;
    return fyMonths(fyStart).slice(0, end + 1);
  }, [fyStart, periodType, monthIdx, quarter, half]);

  const ytd = useMemo(() => {
    if (!ytdMonthList || !singleGroup) return null;
    const g = groups[0];
    const cplyYtd = ytdMonthList.map(m => shiftYear(m, -1));
    const out = {};
    ITEMS.forEach(({ key }) => {
      const plan   = aggregate(g.plants, key, 'plan',   ytdMonthList, g.conv);
      const actual = aggregate(g.plants, key, 'actual', ytdMonthList, g.conv);
      const cply   = aggregate(g.plants, key, 'actual', cplyYtd,      g.conv);
      out[key] = {
        plan, actual,
        growth: cply != null && cply !== 0 && actual != null ? ((actual - cply) / cply) * 100 : null,
      };
    });
    return out;
  }, [ytdMonthList, singleGroup, groups, aggregate]);

  // ── Records: just-set count and most recent records (spotlight) ────────────
  const recordList = useMemo(() => buildRecordList(recordRows, scopeItems), [recordRows, scopeItems]);
  // The "Records just set" card follows the top View selector, not the spotlight's scope.
  const tileScope = VIEW_RECORD_SCOPE[view];
  const tileRecordList = useMemo(() => {
    const items = recordItems(records, tileScope);
    return buildRecordList(buildRecordRows(records, tileScope, items), items);
  }, [records, tileScope]);
  const freshRecords = tileRecordList.filter(r => isFreshRecord(r.best));
  const spotlight = [...recordList]
    .sort((a, b) => (b.best.end || '').localeCompare(a.best.end || '') || a.order - b.order)
    .slice(0, 4);

  // ── Small render helpers ────────────────────────────────────────────────────
  const pill = (v) => {
    if (v == null) return <span className={`${css.pill} ${css.pillNone}`}>—</span>;
    const cls = v >= 100 ? css.pillGood : v >= 95 ? css.pillMid : css.pillBad;
    return <span className={`${css.pill} ${cls}`}>{fmtPct(v)}</span>;
  };
  const growth = (v) => (v == null
    ? <span className={css.muted}>—</span>
    : <span className={v >= 0 ? css.up : css.down}>{v >= 0 ? '↑' : '↓'} {v >= 0 ? '+' : ''}{v.toFixed(2)}%</span>);
  const seg = (options, value, onChange, green) => (
    <div className={`${css.segmented} ${green ? css.segGreen : ''}`}>
      {options.map(o => (
        <button key={o.id} type="button" onClick={() => onChange(o.id)}
                className={`${css.segBtn} ${value === o.id ? css.segBtnActive : ''}`}>{o.label}</button>
      ))}
    </div>
  );
  const unitLabel = inTonnes ? 'T' : "'000 T";
  const scopeLabel = RECORD_SCOPES.find(x => x.key === recordScope)?.label;
  const tileScopeLabel = RECORD_SCOPES.find(x => x.key === tileScope)?.label;
  const changeView = (v) => { setView(v); setRecordScope(VIEW_RECORD_SCOPE[v]); };
  const groupCols = singleGroup ? 5 : 4;
  const ytdCols = ytd ? 3 : 0;

  return (
    <div className={css.page}>
      <style>{`
        html, body { overflow-y: auto; overflow-x: hidden; }
        @media print { @page { size: A4 landscape; margin: 10mm; } }
      `}</style>

      <div className={css.noPrint}><GlobalNavbar /></div>

      <div className={css.inner}>

        {/* ── Title ── */}
        <div className={css.titleRow}>
          <h1 className={css.title}>Production Highlights</h1>
          <span className={css.titleChip}>{VIEWS.find(v => v.id === view).label} · {periodLabel}</span>
        </div>

        {/* ── Toolbar ── */}
        <div className={`${css.toolbar} ${css.noPrint}`}>
          {seg(VIEWS, view, changeView)}
          <span className={css.toolLabel}>Period</span>
          <select className={css.select} value={periodType} onChange={e => setPeriodType(e.target.value)}>
            {PERIOD_TYPES.map(p => <option key={p.id} value={p.id}>{p.label}</option>)}
          </select>

          {periodType === 'custom' ? (
            <>
              <span className={css.toolLabel}>From</span>
              <select className={css.select} value={customStart ?? ''} onChange={e => setCustomStart(e.target.value)}>
                {allMonths.map(m => <option key={m} value={m}>{MONTH_LABEL[m.slice(5)]} {m.slice(0, 4)}</option>)}
              </select>
              <span className={css.toolLabel}>To</span>
              <select className={css.select} value={customEnd ?? ''} onChange={e => setCustomEnd(e.target.value)}>
                {allMonths.map(m => <option key={m} value={m}>{MONTH_LABEL[m.slice(5)]} {m.slice(0, 4)}</option>)}
              </select>
            </>
          ) : periodType === 'cy' ? (
            <select className={css.select} value={cyYear ?? ''} onChange={e => setCyYear(Number(e.target.value))}>
              {cyOptions.map(y => <option key={y} value={y}>{y}</option>)}
            </select>
          ) : (
            <>
              <select className={css.select} value={fyStart ?? ''} onChange={e => setFyStart(Number(e.target.value))}>
                {fys.map(f => <option key={f.fy_start} value={f.fy_start}>FY {f.label}</option>)}
              </select>
              {periodType === 'month' && (
                <select className={css.select} value={monthIdx} onChange={e => setMonthIdx(Number(e.target.value))}>
                  {fyStart != null && fyMonths(fyStart).map((m, i) => (
                    <option key={m} value={i}>{MONTH_LABEL[m.slice(5)]} {m.slice(0, 4)}</option>
                  ))}
                </select>
              )}
              {periodType === 'quarter' && (
                <select className={css.select} value={quarter} onChange={e => setQuarter(Number(e.target.value))}>
                  {QUARTERS.map(q => <option key={q.id} value={q.id}>{q.label}</option>)}
                </select>
              )}
              {periodType === 'half' && (
                <select className={css.select} value={half} onChange={e => setHalf(Number(e.target.value))}>
                  {HALVES.map(h => <option key={h.id} value={h.id}>{h.label}</option>)}
                </select>
              )}
            </>
          )}

          <span className={css.toolLabel}>Unit</span>
          {seg([{ id: false, label: "'000 T" }, { id: true, label: 'Tonnes' }], inTonnes, setInTonnes)}

          <span className={css.toolEnd}>
            {loading && <span className={css.loadingNote}>⟳ loading…</span>}
            <button type="button" className={css.btn} onClick={handlePrint} disabled={loading || !hasAnyData}>🖨 Print</button>
            <button type="button" className={`${css.btn} ${css.btnGreen}`} onClick={handleDownloadExcel} disabled={loading || !hasAnyData}>⬇ Excel</button>
          </span>
        </div>

        {error && <div className={css.error}>{error}</div>}

        {/* ── Summary cards ── */}
        {!loading && hasAnyData && (
          <div className={css.cards}>
            <div className={css.card}>
              <div className={css.cardHead}>
                <div>
                  <div className={css.eyebrow}>{periodLabel} · output</div>
                  <h2 className={css.cardTitle}>{groups[sumIdx].label}</h2>
                </div>
                <span className={css.cardIcon}>🏭</span>
              </div>
              <div className={css.miniStats}>
                {keyStats.map(k => (
                  <div key={k.label}>
                    <div className={css.miniLabel}>{k.label}</div>
                    <div className={css.miniValue}>{fmt(k.actual)}</div>
                    <div className={`${css.miniFoot} ${k.ach == null ? css.muted : k.ach >= 100 ? css.up : css.down}`}>
                      {k.ach == null ? 'no plan' : `${k.ach.toFixed(1)}% of plan`}
                    </div>
                    <div className={`${css.miniFoot} ${k.growth == null ? css.muted : k.growth >= 0 ? css.up : css.down}`}>
                      {k.growth == null ? 'no CPLY' : `${k.growth >= 0 ? '+' : ''}${k.growth.toFixed(1)}% vs CPLY`}
                    </div>
                  </div>
                ))}
              </div>
            </div>

            <div className={css.card}>
              <div className={css.cardHead}>
                <div>
                  <div className={css.eyebrow}>Leading crude steel share</div>
                  <h2 className={css.cardTitle}>{share.rows[0]?.plant ?? '—'}</h2>
                </div>
                <span className={`${css.cardIcon} ${css.iconGreen}`}>📊</span>
              </div>
              <div className={css.shareTop}>
                <span>Crude steel share · {periodLabel}</span>
                <span className={css.shareBig}>{share.rows[0] ? `${share.rows[0].pct.toFixed(1)}%` : '—'}</span>
              </div>
              <div className={css.shareBar}>
                {share.rows.map((r, i) => (
                  <span key={r.plant} title={`${r.plant}: ${fmt(r.value)} (${r.pct.toFixed(1)}%)`}
                        style={{ width: `${r.pct}%`, background: SHARE_COLORS[i % SHARE_COLORS.length] }} />
                ))}
              </div>
              <div className={css.shareLegend}>
                {share.rows.map((r, i) => (
                  <span key={r.plant}><i className={css.dot} style={{ background: SHARE_COLORS[i % SHARE_COLORS.length] }} />{r.plant} {r.pct.toFixed(1)}%</span>
                ))}
              </div>
              <div className={css.cardFoot}>
                <span>Total: <b>{fmt(share.total || null)}</b> {unitLabel}</span>
                <span>{share.rows.length} {view === 'UNIT' ? 'units' : 'plants'}</span>
              </div>
            </div>

            <div className={css.card}>
              <div className={css.cardHead}>
                <div>
                  <div className={css.eyebrow}>Records just set · {tileScopeLabel}</div>
                  <h2 className={css.cardTitle}>{freshRecords.length} new record{freshRecords.length === 1 ? '' : 's'}</h2>
                </div>
                <span className={`${css.cardIcon} ${css.iconAmber}`}>🏆</span>
              </div>
              <div className={css.milestone}>
                <span className={css.bigCount}>{freshRecords.length}</span>
                <div className={css.milestoneText}>
                  {freshRecords.length
                    ? <>Latest: <b>{freshRecords[0].item}</b> — {freshRecords[0].kind.toLowerCase()} of <b>{fmt(freshRecords[0].best.total)}</b> in {freshRecords[0].best.period}.</>
                    : 'No best-ever month, quarter, half or year was set in the last 3 months of data.'}
                  <br />Records whose period ended in the last 3 months of data{records?.latest_month ? ` (latest ${records.latest_month})` : ''}.
                </div>
              </div>
            </div>
          </div>
        )}

        {/* ── Highlights table ── */}
        <section className={css.section}>
          <div className={css.sectionHead}>
            <div>
              <h2 className={css.sectionTitle}>Production highlights: {VIEWS.find(v => v.id === view).label}</h2>
              <p className={css.sectionSub}>Plan vs actual for {periodLabel}, with growth over the corresponding period last year{ytd ? ' and FY-to-date' : ''}</p>
            </div>
            <div className={css.legend}>
              <span><i className={css.dot} style={{ background: 'var(--ui-success)' }} />≥100% of plan</span>
              <span><i className={css.dot} style={{ background: 'var(--ui-warning)' }} />95–99%</span>
              <span><i className={css.dot} style={{ background: 'var(--ui-danger)' }} />&lt;95%</span>
            </div>
          </div>

          {!loading && !hasAnyData ? (
            <div className={css.empty}>No production data for {periodLabel}.</div>
          ) : (
            <div className={css.tableWrap}>
              <table className={css.table}>
                <thead>
                  {!singleGroup && (
                    <tr>
                      <th className={css.left} />
                      {groups.map(g => (
                        <th key={g.label} colSpan={groupCols} className={`${css.thGroup} ${g.isTotal ? css.thGroupTotal : ''}`}>{g.label}</th>
                      ))}
                    </tr>
                  )}
                  <tr>
                    <th className={css.left}>Item</th>
                    {groups.map((g, idx) => (
                      <React.Fragment key={g.label}>
                        <th className={idx > 0 ? css.groupStart : ''}>Plan<span className={css.thSub}>({unitLabel})</span></th>
                        <th>Actual<span className={css.thSub}>{singleGroup ? periodLabel : `(${unitLabel})`}</span></th>
                        <th className={css.center}>% Ach</th>
                        {singleGroup && <th>CPLY<span className={css.thSub}>({unitLabel})</span></th>}
                        <th>Gr %<span className={css.thSub}>over CPLY</span></th>
                      </React.Fragment>
                    ))}
                    {ytd && (
                      <>
                        <th className={css.groupStart}>YTD plan<span className={css.thSub}>({unitLabel})</span></th>
                        <th>YTD actual<span className={css.thSub}>({unitLabel})</span></th>
                        <th>YTD Gr %<span className={css.thSub}>YoY</span></th>
                      </>
                    )}
                  </tr>
                </thead>
                <tbody>
                  {ITEMS.map(({ label, key }) => (
                    <tr key={key}>
                      <td className={`${css.left} ${css.itemCell}`}><span className={css.itemDot}>•</span>{label}</td>
                      {rows[key].map((c, idx) => {
                        const tot = groups[idx].isTotal ? css.totalCol : '';
                        return (
                          <React.Fragment key={groups[idx].label}>
                            <td className={`${css.plan} ${tot} ${idx > 0 ? css.groupStart : ''}`}>{fmt(c.plan)}</td>
                            <td className={`${css.actualCell} ${tot}`}>{fmt(c.actual)}</td>
                            <td className={`${css.center} ${tot}`}>{pill(c.ach)}</td>
                            {singleGroup && <td className={css.plan}>{fmt(c.cply)}</td>}
                            <td className={tot}>{growth(c.growth)}</td>
                          </React.Fragment>
                        );
                      })}
                      {ytd && (
                        <>
                          <td className={`${css.plan} ${css.groupStart}`}>{fmt(ytd[key].plan)}</td>
                          <td className={css.actualCell}>{fmt(ytd[key].actual)}</td>
                          <td>{growth(ytd[key].growth)}</td>
                        </>
                      )}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
          <div className={css.note}>
            Values stored in &apos;000 tonnes; the Tonnes view multiplies by 1000. Plan = AAP plan (production_plan_table);
            Actual = uploaded/entered production (production_table); months without data are skipped when summing.
            % Ach = Actual ÷ Plan. CPLY = actual of the corresponding period last year; Gr % = growth over CPLY.
            YTD = from April of the financial year to the end of the selected month, quarter or half.
            &quot;SAIL (5 Plants)&quot; sums BSP, DSP, RSP, BSL, ISP; &quot;Unit-wise&quot; covers ASP, SSP, VISL; &quot;SAIL (8 Plants)&quot; sums all
            eight plus Conversion (Finished Steel only). Quarters and halves follow the financial year (Q1 = Apr–Jun,
            H1 = Apr–Sep); Calendar Year = Jan–Dec.
          </div>
        </section>

        {/* ── Best-ever records ── */}
        <section className={css.section}>
          <div className={css.sectionHead}>
            <div>
              <h2 className={css.sectionTitle}>🏆 Best-ever records spotlight</h2>
              <p className={css.sectionSub}>{scopeLabel} · all-time highest production per period — most recent records first</p>
            </div>
          </div>
          <div className={`${css.scopeBar} ${css.noPrint}`}>
            {['Groups', 'Plants', 'Units'].map(kind => (
              <React.Fragment key={kind}>
                <span className={css.toolLabel}>{kind}</span>
                {seg(RECORD_SCOPES.filter(x => x.kind === kind).map(x => ({ id: x.key, label: x.label })), recordScope, setRecordScope, true)}
              </React.Fragment>
            ))}
          </div>

          {recordsError && <div className={css.warn}>{recordsError}</div>}

          {!records && !recordsError ? (
            <div className={css.empty}>⟳ Loading records…</div>
          ) : recordRows && !recordsHaveData ? (
            <div className={css.empty}>No production records for {scopeLabel}.</div>
          ) : recordRows && (
            <>
              <div className={css.spotlight}>
                {spotlight.map(r => {
                  const fresh = isFreshRecord(r.best);
                  return (
                    <div key={`${r.item}-${r.kind}`} className={`${css.spot} ${fresh ? css.spotFresh : ''}`}>
                      <span className={css.spotTag}>{fresh ? '★ New record' : 'All-time record'}</span>
                      <span className={css.spotKind}>{r.kind}</span>
                      <div className={css.spotItem}>{r.item}</div>
                      <div className={css.spotBox}>
                        <div className={css.miniLabel}>Record high achieved</div>
                        <div className={css.spotValue}>{fmt(r.best.total)}<span className={css.spotUnit}>{unitLabel}</span></div>
                        {r.second && r.second.total
                          ? <div className={css.spotGain}>+{(((r.best.total - r.second.total) / r.second.total) * 100).toFixed(1)}% over previous best</div>
                          : <div className={`${css.spotGain} ${css.muted}`}>first record of its kind</div>}
                      </div>
                      <div className={css.spotRows}>
                        <span>Set in</span><b>{r.best.period}</b>
                        <span>Previous best</span><b>{r.second ? `${fmt(r.second.total)} (${r.second.period})` : '—'}</b>
                      </div>
                    </div>
                  );
                })}
              </div>

              <div className={css.tableWrap}>
                <table className={css.table}>
                  <thead>
                    <tr>
                      <th className={css.left}>Item</th>
                      {RECORD_KINDS.map(k => <th key={k.id} className={css.center}>{k.head}</th>)}
                    </tr>
                  </thead>
                  <tbody>
                    {scopeItems.map(({ label, key }) => (
                      <tr key={key}>
                        <td className={`${css.left} ${css.itemCell}`}>{label}</td>
                        {RECORD_KINDS.map(({ id }) => {
                          const rec = recordRows[key]?.[id];
                          const best = rec?.best ?? null;
                          const fresh = best != null && isFreshRecord(best);
                          return (
                            <td key={id} className={`${css.center} ${css.recCell} ${fresh ? css.recFresh : ''}`}>
                              {best == null ? '—' : (
                                <>
                                  {fresh && <span className={css.newBadge}>★ NEW</span>}
                                  <span className={css.recBest}>{fmt(best.total)}</span>
                                  <span className={css.recPeriod}>{best.period}</span>
                                  {rec.second != null && (
                                    <span className={css.recSecond}>2nd · {fmt(rec.second.total)}<br />{rec.second.period}</span>
                                  )}
                                </>
                              )}
                            </td>
                          );
                        })}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </>
          )}
          <div className={css.note}>
            ★ NEW marks records just set — the record period ended within the last 3 months of available data.
            Each cell shows the all-time best and, below it, the 2nd best of that period type.
            All-time records from production_table (since Apr 2000), in &apos;000 tonnes (Tonnes view multiplies by 1000).
            Quarters/halves/years count only complete periods (3, 6 or 12 months of data). Groups sum the member plants and
            show the summary items; selecting a single plant/unit lists every item that plant reports (BF, SMS, mills …).
            Conversion is not included.
          </div>
        </section>

        {/* ── Best periods: custom month window, top-5 financial years ── */}
        <section className={css.section}>
          <div className={css.sectionHead}>
            <div>
              <h2 className={css.sectionTitle}>🥇 Best periods — {bpValid ? `${monLbl(bpFrom)}–${monLbl(bpTo)} window` : 'custom window'}</h2>
              <p className={css.sectionSub}>{bpValid ? 'Top 5 financial years by total production in the window' : 'Pick a valid window'}</p>
            </div>
          </div>
          <div className={`${css.scopeBar} ${css.noPrint}`}>
            <span className={css.toolLabel}>Scope</span>
            {seg(BP_SCOPES, bpScope, setBpScope, true)}
            <span className={css.toolLabel}>Items</span>
            {seg([{ id: 'major', label: 'Major' }, { id: 'all', label: 'All' }], bpItems, setBpItems, true)}
            <span className={css.toolLabel}>From</span>
            <select className={css.select} value={bpFrom} onChange={e => setBpFrom(Number(e.target.value))}>
              {FY_MONTH_ORDER.map(m => <option key={m} value={m}>{monLbl(m)}</option>)}
            </select>
            <span className={css.toolLabel}>To</span>
            <select className={css.select} value={bpTo} onChange={e => setBpTo(Number(e.target.value))}>
              {FY_MONTH_ORDER.map(m => <option key={m} value={m}>{monLbl(m)}</option>)}
            </select>
            {bpLoading && <span className={css.loadingNote}>⟳ loading…</span>}
          </div>

          {!bpValid && (
            <div className={css.warn}>
              The <b>To</b> month must not come before the <b>From</b> month within the financial year (order is Apr → Mar).
            </div>
          )}
          {bpError && <div className={css.warn}>{bpError}</div>}

          {bpValid && bpData && (() => {
            const cols = bpData.column_order || [];
            const rowsFlat = cols.flatMap(col =>
              Object.entries(bpData.results[col] || {}).map(([itemKey, ranks], i, arr) =>
                ({ col, itemKey, ranks, first: i === 0, span: arr.length })));
            if (rowsFlat.length === 0) {
              return <div className={css.empty}>No financial year has a complete {monLbl(bpFrom)}–{monLbl(bpTo)} window for this selection.</div>;
            }
            const showCol = bpScope === 'plants';
            return (
              <div className={css.tableWrap}>
                <table className={css.table}>
                  <thead>
                    <tr>
                      {showCol && <th className={css.left}>Plant</th>}
                      <th className={css.left}>Item</th>
                      {[1, 2, 3, 4, 5].map(n => <th key={n} className={css.center}>#{n} best FY</th>)}
                    </tr>
                  </thead>
                  <tbody>
                    {rowsFlat.map(({ col, itemKey, ranks, first, span }) => {
                      const label = ITEMS.find(x => x.key === itemKey)?.label || itemKey;
                      const val = (v) => (v == null ? '—'
                        : isRateKey(itemKey) ? Math.round(v).toLocaleString('en-IN') : fmt(v));
                      return (
                        <tr key={`${col}-${itemKey}`}>
                          {showCol && first && (
                            <td rowSpan={span} className={`${css.left} ${css.itemCell}`} style={{ verticalAlign: 'top', background: 'var(--ui-success-bg)' }}>{col}</td>
                          )}
                          <td className={`${css.left} ${css.itemCell}`}>{label}</td>
                          {[0, 1, 2, 3, 4].map(k => {
                            const r = ranks[k];
                            return (
                              <td key={k} className={`${css.center} ${css.recCell}`}>
                                {r ? <><span className={k === 0 ? css.rankFy : ''}>{val(r.total)}</span><span className={css.recPeriod}>{r.fy}</span></> : '—'}
                              </td>
                            );
                          })}
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            );
          })()}

          <div className={css.note}>
            Pick any month range in financial-year order (Apr → Mar — so e.g. Oct → Feb spans the year end).
            For every financial year with the <b>complete</b> window the top 5 FYs are listed. Tonnage items
            are the sum of every member plant&apos;s window total; rate items (Oven Pushing, COB#*) are the sum of
            each plant&apos;s own day-weighted average over the window — i.e. the SAIL nos/day, not a per-plant
            mean. Scope aggregates the member plants; &ldquo;Plant-wise&rdquo; ranks each plant/unit on its own. &ldquo;Major&rdquo; =
            Sinter, Hot Metal, Pig Iron, Crude Steel, Finished &amp; Saleable Steel, Oven Pushing; &ldquo;All&rdquo; =
            every item the scope reports. Values in &apos;000 tonnes (Tonnes view ×1000); Conversion not included.
          </div>
        </section>
      </div>
    </div>
  );
}
