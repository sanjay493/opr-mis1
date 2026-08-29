'use client';

import RequireEditor from '@/components/RequireEditor';

import React, { useState, useCallback, useEffect, useMemo, useRef } from 'react';
import Link from 'next/link';
import GlobalNavbar from '@/components/GlobalNavbar';

const API = process.env.NEXT_PUBLIC_API_URL || '';

const PLANTS = [
  { code: 'BSP', label: 'Bhilai Steel Plant' },
  { code: 'DSP', label: 'Durgapur Steel Plant' },
  { code: 'RSP', label: 'Rourkela Steel Plant' },
  { code: 'BSL', label: 'Bokaro Steel Plant' },
  { code: 'ISP', label: 'IISCO Steel Plant' },
];

const UNIT_TYPES = [
  { code: 'BF', label: 'Blast Furnace' },
  { code: 'SMS', label: 'SMS (Converter/Caster)' },
  { code: 'MILL', label: 'Rolling Mill' },
  { code: 'COKE', label: 'Coke Oven' },
  { code: 'SINTER', label: 'Sinter Plant' },
  { code: 'GENERAL', label: 'Plant-Level General' },
];
const UNIT_TYPE_LABEL = Object.fromEntries(UNIT_TYPES.map(t => [t.code, t.label]));
const SHOP_OPTION_LABEL = {
  BF: 'Whole BF shop (all furnaces)',
  SMS: 'Whole SMS shop (converters + casters)',
  MILL: 'Whole mill shop (all mills)',
  COKE: 'Whole coke oven battery',
  SINTER: 'Whole sinter plant',
  GENERAL: 'Plant-wide',
};

// ---- timestamp / duration helpers -----------------------------------------

// 'YYYY-MM-DD HH:MM' <-> the 'YYYY-MM-DDTHH:MM' shape <input type="datetime-local"> needs.
const toInputTs = (ts) => (ts || '').replace(' ', 'T');
const toApiTs = (v) => (v || '').replace('T', ' ');

function parseTs(ts) {
  if (!ts) return null;
  const d = new Date(String(ts).replace(' ', 'T'));
  return Number.isNaN(d.getTime()) ? null : d;
}

// Whole hours (float) a breakdown spans. For an ongoing event, measured to "now".
function spanHours(startTs, endTs, isOngoing) {
  const s = parseTs(startTs);
  if (!s) return null;
  const e = isOngoing ? new Date() : parseTs(endTs);
  if (!e) return null;
  return Math.max(0, (e.getTime() - s.getTime()) / 3600000);
}

function fmtDuration(hours) {
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

function fmtHrs(h) {
  if (h == null) return '—';
  return h.toLocaleString('en-IN', { maximumFractionDigits: 1 });
}

function nowLocalInput() {
  const d = new Date();
  d.setMinutes(d.getMinutes() - d.getTimezoneOffset());
  return d.toISOString().slice(0, 16); // 'YYYY-MM-DDTHH:MM'
}

function todayDateInput() {
  const d = new Date();
  d.setMinutes(d.getMinutes() - d.getTimezoneOffset());
  return d.toISOString().slice(0, 10); // 'YYYY-MM-DD'
}

// A stored timestamp with no time part ('YYYY-MM-DD', 10 chars) was entered
// in date-only mode.
const isDateOnlyTs = (ts) => !!ts && String(ts).trim().length <= 10;

function fmtDateShort(ts) {
  const d = parseTs(ts);
  if (!d) return ts || '—';
  return d.toLocaleString('en-IN', {
    day: '2-digit', month: 'short', year: '2-digit',
    ...(isDateOnlyTs(ts) ? {} : { hour: '2-digit', minute: '2-digit', hour12: false }),
  });
}

// ---- style tokens ---------------------------------------------------------

const S = {
  card: { background: '#fff', border: '1px solid #dadce0', borderRadius: 8 },
  label: { fontSize: 12, fontWeight: 700, color: '#5f6368', textTransform: 'uppercase', letterSpacing: '0.03em' },
  input: { padding: '9px 11px', fontSize: 14, border: '1px solid #d1d5db', borderRadius: 6, width: '100%', boxSizing: 'border-box', background: '#fff' },
  select: { padding: '9px 11px', fontSize: 14, border: '1px solid #d1d5db', borderRadius: 6, background: '#fff' },
  H: { padding: '10px 12px', textAlign: 'left', fontWeight: 700, color: '#5f6368', borderBottom: '1px solid #dadce0', fontSize: 12.5, backgroundColor: '#f8f9fa', whiteSpace: 'nowrap', textTransform: 'uppercase', letterSpacing: '0.02em' },
  TD: { padding: '10px 12px', borderBottom: '1px solid #f0f4f8', fontSize: 13.5, verticalAlign: 'top' },
  btnPrimary: { padding: '9px 22px', fontSize: 14, fontWeight: 700, background: '#1a73e8', color: '#fff', border: 'none', borderRadius: 6, cursor: 'pointer' },
  btnGhost: { padding: '9px 18px', fontSize: 14, fontWeight: 600, background: '#f1f3f4', color: '#374151', border: 'none', borderRadius: 6, cursor: 'pointer' },
  chip: { padding: '3px 9px', borderRadius: 999, fontSize: 11.5, fontWeight: 700, display: 'inline-block' },
};

function Notice({ type, text }) {
  if (!text) return null;
  const ok = type === 'success';
  return (
    <div style={{
      padding: '10px 16px', borderRadius: 6, marginBottom: 14, fontSize: 14,
      background: ok ? '#f0fdf4' : '#fef2f2',
      color: ok ? '#166534' : '#991b1b',
      border: `1px solid ${ok ? '#86efac' : '#fca5a5'}`,
    }}>
      {text}
    </div>
  );
}

function SegBtns({ options, value, onChange, allowClear }) {
  return (
    <div style={{ display: 'inline-flex', flexWrap: 'wrap', gap: 6 }}>
      {options.map(o => {
        const on = value === o.code;
        return (
          <button key={o.code} type="button"
            onClick={() => onChange(allowClear && on ? '' : o.code)}
            style={{
              padding: '7px 13px', fontSize: 13, fontWeight: 600, borderRadius: 6, cursor: 'pointer',
              border: on ? '1px solid #1a73e8' : '1px solid #d1d5db',
              background: on ? '#1a73e8' : '#fff',
              color: on ? '#fff' : '#5f6368',
            }}>
            {o.label}
          </button>
        );
      })}
    </div>
  );
}

// ---- add / edit form panel ----------------------------------------------

const isShopUnit = (name) => (name || '').trim().toLowerCase() === 'shop';
const smsNeedsSubtag = (d) => d.unit_type === 'SMS' && !isShopUnit(d.unit_name);

function emptyDraft(plant) {
  return {
    plant, unit_type: '', unit_name: '', sms_subtag: '',
    start_ts: '', end_ts: '', is_ongoing: false, date_only: false,
    cause: '', hours_lost_override: '',
  };
}

function draftFromRow(row) {
  return {
    plant: row.plant,
    unit_type: row.unit_type || '',
    unit_name: row.unit_name || '',
    sms_subtag: row.sms_subtag || '',
    start_ts: row.start_ts || '',
    end_ts: row.end_ts || '',
    is_ongoing: !!row.is_ongoing,
    date_only: isDateOnlyTs(row.start_ts) || (!row.start_ts && isDateOnlyTs(row.end_ts)),
    cause: row.cause || '',
    hours_lost_override: row.hours_lost_override != null ? String(row.hours_lost_override) : '',
  };
}

function validateDraft(d) {
  if (!d.unit_type) return 'Pick a unit type';
  if (!d.unit_name) return 'Pick a unit';
  if (smsNeedsSubtag(d) && !d.sms_subtag) return 'Choose Converter or Caster for a specific SMS unit';
  if (!d.start_ts) return d.date_only ? 'Start date is required' : 'Start date/time is required';
  if (!d.is_ongoing && !d.end_ts) return `End ${d.date_only ? 'date' : 'date/time'} is required unless the event is still ongoing`;
  if (!d.is_ongoing && d.end_ts && d.end_ts < d.start_ts) return 'End must not be before start';
  if (!d.cause.trim()) return 'Describe the cause';
  if (d.hours_lost_override !== '' && !(Number(d.hours_lost_override) >= 0)) return 'Hours override must be a positive number';
  return null;
}

function draftPayload(d) {
  return {
    plant: d.plant,
    unit_type: d.unit_type,
    unit_name: d.unit_name,
    sms_subtag: smsNeedsSubtag(d) ? d.sms_subtag : null,
    start_ts: d.start_ts,
    end_ts: d.is_ongoing ? null : d.end_ts,
    is_ongoing: d.is_ongoing,
    cause: d.cause.trim(),
    hours_lost_override: d.hours_lost_override === '' ? null : Number(d.hours_lost_override),
  };
}

function Field({ label, hint, children }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 5 }}>
      <span style={S.label}>{label}</span>
      {children}
      {hint && <span style={{ fontSize: 11.5, color: '#9aa0a6' }}>{hint}</span>}
    </div>
  );
}

function BreakdownForm({ plant, units, editRow, onDone, onCancel }) {
  const isEdit = !!editRow;
  const [draft, setDraft] = useState(() => (editRow ? draftFromRow(editRow) : emptyDraft(plant)));
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState(null);

  const set = (patch) => setDraft(d => ({ ...d, ...(typeof patch === 'function' ? patch(d) : patch) }));

  // Shops (BF Shop / SMS Shop — a whole-shop breakdown) are offered too, at
  // the end of the list.
  const unitOptions = useMemo(
    () => units.filter(u => u.unit_type === draft.unit_type)
               .sort((a, b) => (a.is_shop ? 1 : 0) - (b.is_shop ? 1 : 0) || a.sort_order - b.sort_order),
    [units, draft.unit_type],
  );

  // Date-only mode: <input type="date"> for both ends, timestamps stored as
  // 'YYYY-MM-DD'. Toggling truncates / pads the existing values.
  const setDateOnly = (on) => set(d => ({
    date_only: on,
    start_ts: on
      ? (d.start_ts || '').slice(0, 10)
      : ((d.start_ts || '').length === 10 ? `${d.start_ts} 00:00` : d.start_ts),
    end_ts: on
      ? (d.end_ts || '').slice(0, 10)
      : ((d.end_ts || '').length === 10 ? `${d.end_ts} 00:00` : d.end_ts),
  }));

  const liveSpan = spanHours(draft.start_ts, draft.end_ts, draft.is_ongoing);
  // for a resolved date-only event the loss report counts calendar days inclusive
  const dayCount = (draft.date_only && !draft.is_ongoing && draft.start_ts && draft.end_ts
    && draft.end_ts >= draft.start_ts)
    ? Math.round((parseTs(draft.end_ts) - parseTs(draft.start_ts)) / 86400000) + 1
    : null;
  const overrideNum = draft.hours_lost_override === '' ? null : Number(draft.hours_lost_override);
  const counted = overrideNum != null && overrideNum >= 0 ? overrideNum : liveSpan;

  const submit = async () => {
    const v = validateDraft(draft);
    if (v) { setErr(v); return; }
    setBusy(true); setErr(null);
    try {
      const url = isEdit ? `${API}/api/breakdown/${editRow.id}` : `${API}/api/breakdown`;
      const res = await fetch(url, {
        method: isEdit ? 'PATCH' : 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(draftPayload(draft)),
      });
      if (!res.ok) throw new Error(await res.text());
      onDone(isEdit ? 'Breakdown updated.' : 'Breakdown logged.');
    } catch (e) {
      setErr(e.message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div style={{ ...S.card, borderColor: isEdit ? '#f6c343' : '#1a73e8', borderWidth: 2, marginBottom: 20 }}>
      <div style={{
        padding: '12px 18px', background: isEdit ? '#fffbeb' : '#eff6ff',
        borderBottom: `1px solid ${isEdit ? '#fde68a' : '#bfdbfe'}`, borderRadius: '6px 6px 0 0',
        fontWeight: 700, fontSize: 14, color: isEdit ? '#92400e' : '#174ea6',
      }}>
        {isEdit ? `Edit breakdown #${editRow.id}` : 'Log a new breakdown'}
        <span style={{ float: 'right', fontWeight: 500, color: '#5f6368', fontSize: 12.5 }}>
          {PLANTS.find(p => p.code === draft.plant)?.label || draft.plant}
        </span>
      </div>

      <div style={{ padding: '18px' }}>
        {/* Section: Unit */}
        <div style={{ marginBottom: 18 }}>
          <div style={{ ...S.label, marginBottom: 8 }}>Unit affected</div>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 18, alignItems: 'flex-start' }}>
            <Field label="Unit type">
              <SegBtns options={UNIT_TYPES} value={draft.unit_type}
                onChange={(code) => set({ unit_type: code, unit_name: '', sms_subtag: '' })} />
            </Field>
            {draft.unit_type && (
              <Field label="Unit"
                hint={unitOptions.length === 0 ? 'No units registered for this type'
                  : (isShopUnit(draft.unit_name) ? 'Whole shop down — no single unit' : null)}>
                <select style={{ ...S.select, minWidth: 200 }} value={draft.unit_name}
                  onChange={e => set({
                    unit_name: e.target.value,
                    sms_subtag: isShopUnit(e.target.value) ? '' : draft.sms_subtag,
                  })}>
                  <option value="">— select —</option>
                  {unitOptions.map(u => (
                    <option key={u.unit_name} value={u.unit_name}>
                      {u.is_shop ? (SHOP_OPTION_LABEL[u.unit_type] || 'Whole shop (all units)') : u.unit_name}
                    </option>
                  ))}
                </select>
              </Field>
            )}
            {smsNeedsSubtag(draft) && (
              <Field label="Converter / Caster">
                <SegBtns
                  options={[{ code: 'CONVERTER', label: 'Converter' }, { code: 'CASTER', label: 'Caster' }]}
                  value={draft.sms_subtag} onChange={(code) => set({ sms_subtag: code })} />
              </Field>
            )}
          </div>
        </div>

        {/* Section: Time window */}
        <div style={{ marginBottom: 18 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 14, marginBottom: 8 }}>
            <div style={S.label}>Time window</div>
            <label style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 12.5, fontWeight: 600, color: '#5f6368' }}>
              <input type="checkbox" checked={draft.date_only} onChange={e => setDateOnly(e.target.checked)} />
              Date only (no time)
            </label>
          </div>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 18, alignItems: 'flex-start' }}>
            <Field label="Start">
              <div style={{ display: 'flex', gap: 6 }}>
                {draft.date_only ? (
                  <input type="date" style={{ ...S.input, width: 176, flexShrink: 0 }}
                    value={(draft.start_ts || '').slice(0, 10)}
                    onChange={e => set({ start_ts: e.target.value })} />
                ) : (
                  <input type="datetime-local" step="60" style={{ ...S.input, width: 232, flexShrink: 0 }}
                    value={toInputTs(draft.start_ts)}
                    onChange={e => set({ start_ts: toApiTs(e.target.value) })} />
                )}
                <button type="button" style={S.btnGhost}
                  onClick={() => set({ start_ts: draft.date_only ? todayDateInput() : toApiTs(nowLocalInput()) })}>
                  {draft.date_only ? 'today' : 'now'}
                </button>
              </div>
            </Field>
            <Field label="End"
              hint={draft.is_ongoing ? `Picking an end ${draft.date_only ? 'date' : 'time'} marks this resolved` : null}>
              <div style={{ display: 'flex', gap: 6 }}>
                {draft.date_only ? (
                  <input type="date" style={{ ...S.input, width: 176, flexShrink: 0 }}
                    value={(draft.end_ts || '').slice(0, 10)}
                    onChange={e => set({ end_ts: e.target.value, is_ongoing: e.target.value ? false : draft.is_ongoing })} />
                ) : (
                  <input type="datetime-local" step="60" style={{ ...S.input, width: 232, flexShrink: 0 }}
                    value={toInputTs(draft.end_ts)}
                    onChange={e => {
                      const v = e.target.value;
                      set({ end_ts: toApiTs(v), is_ongoing: v ? false : draft.is_ongoing });
                    }} />
                )}
                <button type="button" style={S.btnGhost}
                  onClick={() => set({
                    end_ts: draft.date_only ? todayDateInput() : toApiTs(nowLocalInput()),
                    is_ongoing: false,
                  })}>{draft.date_only ? 'today' : 'now'}</button>
              </div>
            </Field>
            <Field label="Status">
              <label style={{ display: 'flex', alignItems: 'center', gap: 7, fontSize: 13.5, color: '#374151', paddingTop: 8 }}>
                <input type="checkbox" checked={draft.is_ongoing}
                  onChange={e => set({ is_ongoing: e.target.checked, end_ts: e.target.checked ? '' : draft.end_ts })} />
                Still ongoing (not yet resolved)
              </label>
            </Field>
          </div>
          <div style={{ marginTop: 10, fontSize: 13, color: '#5f6368' }}>
            Duration:{' '}
            <strong style={{ color: liveSpan == null ? '#9aa0a6' : '#202124' }}>
              {liveSpan == null ? 'set start & end'
                : dayCount != null ? `${dayCount} day${dayCount === 1 ? '' : 's'}`
                : fmtDuration(liveSpan)}
            </strong>
            {liveSpan != null && (
              <span style={{ color: '#9aa0a6' }}>
                {' '}({fmtHrs(liveSpan)} h){draft.is_ongoing ? ' and counting' : ''}
                {dayCount != null && ' — counted inclusive by the loss report'}
              </span>
            )}
          </div>
        </div>

        {/* Section: Cause & impact */}
        <div style={{ marginBottom: 6 }}>
          <div style={{ ...S.label, marginBottom: 8 }}>Cause &amp; impact</div>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 18, alignItems: 'flex-start' }}>
            <Field label="Cause / description">
              <textarea style={{ ...S.input, width: 460, maxWidth: '100%', minHeight: 70, resize: 'vertical' }}
                value={draft.cause} onChange={e => set({ cause: e.target.value })}
                placeholder="e.g. Stove dome failure on BF-6; hot blast isolated for repair" />
            </Field>
            <Field label="Hours lost — override"
              hint={overrideNum != null
                ? 'Manual value used for Production Loss Analysis'
                : `Blank → full span (${liveSpan == null ? '?' : fmtHrs(liveSpan)} h) is used`}>
              <input type="number" min="0" step="0.5" style={{ ...S.input, width: 140 }}
                value={draft.hours_lost_override}
                onChange={e => set({ hours_lost_override: e.target.value })} placeholder="auto" />
            </Field>
            <Field label="Hours counted">
              <div style={{ fontSize: 18, fontWeight: 700, color: '#202124', paddingTop: 6 }}>
                {counted == null ? '—' : `${fmtHrs(counted)} h`}
              </div>
            </Field>
          </div>
        </div>

        {err && (
          <div style={{ marginTop: 14, padding: '9px 14px', borderRadius: 6, background: '#fef2f2', color: '#991b1b', border: '1px solid #fca5a5', fontSize: 13 }}>
            {err}
          </div>
        )}

        <div style={{ marginTop: 16, display: 'flex', gap: 10 }}>
          <button onClick={submit} disabled={busy} style={{ ...S.btnPrimary, opacity: busy ? 0.6 : 1 }}>
            {busy ? 'Saving…' : isEdit ? 'Save changes' : 'Log breakdown'}
          </button>
          <button onClick={onCancel} style={S.btnGhost}>Cancel</button>
        </div>
      </div>
    </div>
  );
}

// ---- log table ----------------------------------------------------------

function StatusChip({ ongoing }) {
  return ongoing
    ? <span style={{ ...S.chip, background: '#fef3c7', color: '#92400e' }}>ONGOING</span>
    : <span style={{ ...S.chip, background: '#e6f4ea', color: '#188038' }}>RESOLVED</span>;
}

function SortHeader({ label, col, sort, setSort, style }) {
  const active = sort.col === col;
  return (
    <th style={{ ...S.H, cursor: 'pointer', ...style }}
      onClick={() => setSort(s => ({ col, dir: s.col === col && s.dir === 'asc' ? 'desc' : 'asc' }))}>
      {label}{active ? (sort.dir === 'asc' ? ' ▲' : ' ▼') : ''}
    </th>
  );
}

function BreakdownDataEntryPageInner() {
  const [plant, setPlant] = useState('BSP');
  const [rows, setRows] = useState([]);
  const [units, setUnits] = useState([]);
  const [loading, setLoading] = useState(false);
  const [status, setStatus] = useState(null);
  const [formMode, setFormMode] = useState(null); // null | 'add' | row object
  const [busyId, setBusyId] = useState(null);

  const [q, setQ] = useState('');
  const [typeFilter, setTypeFilter] = useState('');
  const [statusFilter, setStatusFilter] = useState('all'); // all | ongoing | resolved
  const [sort, setSort] = useState({ col: 'start_ts', dir: 'desc' });

  const formRef = useRef(null);

  useEffect(() => {
    fetch(`${API}/api/plant-units?plant_code=${encodeURIComponent(plant)}`)
      .then(res => res.json())
      .then(data => setUnits(data.units || []))
      .catch(() => setUnits([]));
  }, [plant]);

  const load = useCallback(async () => {
    setLoading(true); setStatus(null);
    try {
      const res = await fetch(`${API}/api/breakdown?plant=${encodeURIComponent(plant)}`);
      if (!res.ok) throw new Error(await res.text());
      const data = await res.json();
      setRows(data.rows || []);
    } catch (err) {
      setStatus({ type: 'error', text: `Load failed: ${err.message}` });
    } finally {
      setLoading(false);
    }
  }, [plant]);

  useEffect(() => { load(); }, [load]);

  const openForm = (mode) => {
    setFormMode(mode);
    setStatus(null);
    requestAnimationFrame(() => formRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' }));
  };

  const onFormDone = (msg) => {
    setFormMode(null);
    setStatus({ type: 'success', text: msg });
    load();
  };

  const handleDelete = async (row) => {
    if (!confirm(`Delete breakdown #${row.id} — ${row.unit_name}, ${fmtDateShort(row.start_ts)}?\nThis cannot be undone.`)) return;
    setBusyId(row.id); setStatus(null);
    try {
      const res = await fetch(`${API}/api/breakdown/${row.id}`, { method: 'DELETE' });
      if (!res.ok) throw new Error(await res.text());
      setStatus({ type: 'success', text: `Breakdown #${row.id} deleted.` });
      load();
    } catch (e) {
      setStatus({ type: 'error', text: e.message });
    } finally {
      setBusyId(null);
    }
  };

  const plantLabel = PLANTS.find(p => p.code === plant)?.label || plant;

  const enriched = useMemo(() => rows.map(r => {
    const span = spanHours(r.start_ts, r.end_ts, r.is_ongoing);
    const counted = r.hours_lost_override != null ? Number(r.hours_lost_override) : span;
    return { ...r, _span: span, _counted: counted };
  }), [rows]);

  const filtered = useMemo(() => {
    const needle = q.trim().toLowerCase();
    return enriched.filter(r => {
      if (typeFilter && r.unit_type !== typeFilter) return false;
      if (statusFilter === 'ongoing' && !r.is_ongoing) return false;
      if (statusFilter === 'resolved' && r.is_ongoing) return false;
      if (needle) {
        const hay = `${r.unit_name} ${r.unit_type} ${r.sms_subtag || ''} ${r.cause || ''}`.toLowerCase();
        if (!hay.includes(needle)) return false;
      }
      return true;
    });
  }, [enriched, q, typeFilter, statusFilter]);

  const sorted = useMemo(() => {
    const arr = [...filtered];
    const { col, dir } = sort;
    const mul = dir === 'asc' ? 1 : -1;
    arr.sort((a, b) => {
      let av, bv;
      if (col === 'unit_name') { av = a.unit_name || ''; bv = b.unit_name || ''; return av.localeCompare(bv) * mul; }
      if (col === 'unit_type') { av = a.unit_type || ''; bv = b.unit_type || ''; return av.localeCompare(bv) * mul; }
      if (col === 'duration') { av = a._span ?? -1; bv = b._span ?? -1; }
      else if (col === 'counted') { av = a._counted ?? -1; bv = b._counted ?? -1; }
      else { av = a.start_ts || ''; bv = b.start_ts || ''; return av.localeCompare(bv) * mul; }
      return (av - bv) * mul;
    });
    return arr;
  }, [filtered, sort]);

  const totals = useMemo(() => {
    const ongoing = enriched.filter(r => r.is_ongoing).length;
    const countedSum = enriched.reduce((s, r) => s + (r._counted || 0), 0);
    return { n: enriched.length, ongoing, countedSum };
  }, [enriched]);

  return (
    <div style={{ height: '100vh', display: 'flex', flexDirection: 'column', background: '#fff' }}>
      <GlobalNavbar />

      <div style={{ flex: 1, overflow: 'auto', maxWidth: 1500, margin: '0 auto', padding: '22px 20px', width: '100%', boxSizing: 'border-box' }}>

        <div style={{ marginBottom: 18, display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 16, flexWrap: 'wrap' }}>
          <div>
            <h2 style={{ fontSize: '1.6rem', fontWeight: 700, color: '#202124', margin: '0 0 4px' }}>
              Breakdown — Data Entry
            </h2>
            <span style={{ fontSize: 13, color: '#5f6368' }}>
              Log unplanned equipment downtime, plant-wise and unit-wise. Unlike Capital Repair (a pre-planned
              annual schedule), every breakdown here counts fully toward the Production Loss Analysis report.
            </span>
          </div>
          <Link href="/reports/breakdown-analysis" style={{
            fontSize: 13, fontWeight: 600, color: '#1a73e8', textDecoration: 'none',
            border: '1px solid #bfdbfe', background: '#eff6ff', borderRadius: 6, padding: '8px 14px', whiteSpace: 'nowrap',
          }}>
            📊 View Breakdown Analysis →
          </Link>
        </div>

        {/* Toolbar */}
        <div style={{
          display: 'flex', gap: 12, alignItems: 'center', flexWrap: 'wrap',
          marginBottom: 16, ...S.card, padding: '14px 18px',
        }}>
          <label style={{ fontSize: 13, fontWeight: 700, color: '#374151' }}>Plant</label>
          <select value={plant} onChange={e => { setPlant(e.target.value); setFormMode(null); }} style={S.select}>
            {PLANTS.map(p => <option key={p.code} value={p.code}>{p.code} — {p.label}</option>)}
          </select>

          <button onClick={() => openForm('add')} disabled={formMode === 'add'} style={{
            ...S.btnPrimary, opacity: formMode === 'add' ? 0.5 : 1,
            cursor: formMode === 'add' ? 'not-allowed' : 'pointer',
          }}>
            + Add Breakdown
          </button>

          <div style={{ marginLeft: 'auto', display: 'flex', gap: 18, alignItems: 'center', fontSize: 13, color: '#5f6368' }}>
            <span><strong style={{ color: '#202124' }}>{totals.n}</strong> event{totals.n !== 1 ? 's' : ''}</span>
            <span><strong style={{ color: totals.ongoing ? '#b45309' : '#202124' }}>{totals.ongoing}</strong> ongoing</span>
            <span><strong style={{ color: '#202124' }}>{fmtHrs(totals.countedSum)}</strong> h counted</span>
            {loading && <span>⟳</span>}
          </div>
        </div>

        <Notice type={status?.type} text={status?.text} />

        <div ref={formRef} />
        {formMode === 'add' && (
          <BreakdownForm key="add" plant={plant} units={units}
            onDone={onFormDone} onCancel={() => setFormMode(null)} />
        )}
        {formMode && formMode !== 'add' && (
          <BreakdownForm key={`edit-${formMode.id}`} plant={plant} units={units} editRow={formMode}
            onDone={onFormDone} onCancel={() => setFormMode(null)} />
        )}

        {/* Filters */}
        <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', alignItems: 'center', marginBottom: 10 }}>
          <input value={q} onChange={e => setQ(e.target.value)} placeholder="Search unit or cause…"
            style={{ ...S.input, width: 260 }} />
          <select value={typeFilter} onChange={e => setTypeFilter(e.target.value)} style={S.select}>
            <option value="">All unit types</option>
            {UNIT_TYPES.map(t => <option key={t.code} value={t.code}>{t.label}</option>)}
          </select>
          <div style={{ display: 'inline-flex', border: '1px solid #d1d5db', borderRadius: 6, overflow: 'hidden' }}>
            {[['all', 'All'], ['ongoing', 'Ongoing'], ['resolved', 'Resolved']].map(([v, lbl]) => (
              <button key={v} onClick={() => setStatusFilter(v)} style={{
                padding: '8px 14px', fontSize: 13, fontWeight: 600, border: 'none', cursor: 'pointer',
                background: statusFilter === v ? '#1a73e8' : '#fff',
                color: statusFilter === v ? '#fff' : '#5f6368',
              }}>{lbl}</button>
            ))}
          </div>
          {(q || typeFilter || statusFilter !== 'all') && (
            <>
              <button onClick={() => { setQ(''); setTypeFilter(''); setStatusFilter('all'); }} style={S.btnGhost}>
                Clear
              </button>
              <span style={{ fontSize: 12.5, color: '#5f6368' }}>{sorted.length} of {rows.length} shown</span>
            </>
          )}
        </div>

        {/* Table */}
        <div style={{ ...S.card, overflow: 'hidden' }}>
          <div style={{ overflowX: 'auto', maxHeight: 'calc(100vh - 360px)', overflowY: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13.5 }}>
              <thead>
                <tr style={{ position: 'sticky', top: 0, zIndex: 1 }}>
                  <SortHeader label="Unit" col="unit_name" sort={sort} setSort={setSort} />
                  <SortHeader label="Type" col="unit_type" sort={sort} setSort={setSort} />
                  <SortHeader label="Start" col="start_ts" sort={sort} setSort={setSort} />
                  <th style={S.H}>End</th>
                  <SortHeader label="Duration" col="duration" sort={sort} setSort={setSort} style={{ textAlign: 'right' }} />
                  <th style={{ ...S.H, minWidth: 260 }}>Cause</th>
                  <SortHeader label="Hrs counted" col="counted" sort={sort} setSort={setSort} style={{ textAlign: 'right' }} />
                  <th style={S.H}>Logged by</th>
                  <th style={{ ...S.H, textAlign: 'center' }}>Actions</th>
                </tr>
              </thead>
              <tbody>
                {sorted.length === 0 && (
                  <tr>
                    <td colSpan={9} style={{ padding: 28, textAlign: 'center', color: '#5f6368', fontSize: 14 }}>
                      {rows.length === 0
                        ? <>No breakdown events logged for {plantLabel}. Click <strong>+ Add Breakdown</strong>.</>
                        : 'No events match the current filters.'}
                    </td>
                  </tr>
                )}
                {sorted.map(row => {
                  const subtag = row.sms_subtag ? ` (${row.sms_subtag.charAt(0)}${row.sms_subtag.slice(1).toLowerCase()})` : '';
                  const overridden = row.hours_lost_override != null;
                  return (
                    <tr key={row.id} style={{ background: row.is_ongoing ? '#fffdf5' : '#fff' }}>
                      <td style={{ ...S.TD, fontWeight: 600 }}>{row.unit_name}{subtag}</td>
                      <td style={{ ...S.TD, color: '#5f6368' }} title={UNIT_TYPE_LABEL[row.unit_type] || ''}>{row.unit_type}</td>
                      <td style={{ ...S.TD, whiteSpace: 'nowrap' }}>{fmtDateShort(row.start_ts)}</td>
                      <td style={{ ...S.TD, whiteSpace: 'nowrap' }}>
                        {row.is_ongoing ? <StatusChip ongoing /> : fmtDateShort(row.end_ts)}
                      </td>
                      <td style={{ ...S.TD, textAlign: 'right', whiteSpace: 'nowrap', fontVariantNumeric: 'tabular-nums' }}>
                        {fmtDuration(row._span)}
                        {row.is_ongoing && <span style={{ color: '#b45309' }}> +</span>}
                      </td>
                      <td style={{ ...S.TD, whiteSpace: 'pre-wrap', maxWidth: 380 }}>{row.cause}</td>
                      <td style={{ ...S.TD, textAlign: 'right', fontVariantNumeric: 'tabular-nums' }}>
                        {fmtHrs(row._counted)}
                        {overridden && <span title="manual override" style={{ color: '#7c3aed', marginLeft: 3 }}>✎</span>}
                      </td>
                      <td style={{ ...S.TD, fontSize: 11.5, color: '#5f6368', whiteSpace: 'nowrap' }}>
                        {row.created_by || '—'}
                        {row.updated_by && row.updated_by !== row.created_by && (
                          <div style={{ color: '#9aa0a6' }}>edit: {row.updated_by}</div>
                        )}
                      </td>
                      <td style={{ ...S.TD, textAlign: 'center', whiteSpace: 'nowrap' }}>
                        <button onClick={() => openForm(row)}
                          style={{ ...S.btnGhost, padding: '5px 12px', background: '#eef2ff', color: '#3730a3' }}>Edit</button>
                        <button onClick={() => handleDelete(row)} disabled={busyId === row.id}
                          style={{ ...S.btnGhost, padding: '5px 12px', background: '#fef2f2', color: '#991b1b', marginLeft: 6 }}>
                          {busyId === row.id ? '…' : 'Delete'}
                        </button>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  );
}

export default function BreakdownDataEntryPage() {
  return (
    <RequireEditor>
      <BreakdownDataEntryPageInner />
    </RequireEditor>
  );
}
