'use client';

import React, { useState, useEffect, useRef } from 'react';

// Typed entry is always 'dd/mm/yyyy' or 'dd/mm/yyyy HH:MM' (24 h) whatever the
// browser locale; the API keeps 'YYYY-MM-DD' / 'YYYY-MM-DD HH:MM'.

export function apiToDisplay(ts, withTime) {
  const m = /^(\d{4})-(\d{2})-(\d{2})(?:[ T](\d{2}):(\d{2}))?/.exec(ts || '');
  if (!m) return '';
  const date = `${m[3]}/${m[2]}/${m[1]}`;
  return withTime ? `${date} ${m[4] || '00'}:${m[5] || '00'}` : date;
}

// 'dd/mm/yyyy[ HH:MM]' -> API string, or null if incomplete / not a real date-time.
export function displayToApi(text, withTime) {
  const re = withTime ? /^(\d{2})\/(\d{2})\/(\d{4}) (\d{2}):(\d{2})$/ : /^(\d{2})\/(\d{2})\/(\d{4})$/;
  const m = re.exec(text);
  if (!m) return null;
  const [dd, mm, yyyy] = [Number(m[1]), Number(m[2]), Number(m[3])];
  const d = new Date(yyyy, mm - 1, dd);
  if (d.getFullYear() !== yyyy || d.getMonth() !== mm - 1 || d.getDate() !== dd) return null;
  const date = `${m[3]}-${m[2]}-${m[1]}`;
  if (!withTime) return date;
  if (Number(m[4]) > 23 || Number(m[5]) > 59) return null;
  return `${date} ${m[4]}:${m[5]}`;
}

// Re-insert the separators around whatever digits were typed.
function maskDigits(raw, withTime) {
  const d = raw.replace(/\D/g, '').slice(0, withTime ? 12 : 8);
  let out = d.slice(0, 2);
  if (d.length > 2) out += `/${d.slice(2, 4)}`;
  if (d.length > 4) out += `/${d.slice(4, 8)}`;
  if (d.length > 8) out += ` ${d.slice(8, 10)}`;
  if (d.length > 10) out += `:${d.slice(10, 12)}`;
  return out;
}

// Text box fixed to dd/mm/yyyy[ HH:MM], plus a calendar button that opens the
// native date picker (keeping any time already typed). onChange gets the API
// string, or '' while the entry is empty / incomplete / invalid.
export default function DateTimeText({ value, withTime = false, onChange, disabled, inputStyle, buttonStyle,
                                      inputClassName, buttonClassName, id }) {
  const [text, setText] = useState(() => apiToDisplay(value, withTime));
  const lastEmitted = useRef(value || '');
  const pickerRef = useRef(null);

  // Resync when the value changes from outside (now / today buttons, ongoing toggle).
  useEffect(() => {
    if ((value || '') !== lastEmitted.current) {
      lastEmitted.current = value || '';
      setText(apiToDisplay(value, withTime));
    }
  }, [value, withTime]);

  const emit = (api) => { lastEmitted.current = api; onChange(api); };

  const onType = (e) => {
    const t = maskDigits(e.target.value, withTime);
    setText(t);
    emit(displayToApi(t, withTime) || '');
  };

  const onPick = (e) => {
    const date = e.target.value; // 'YYYY-MM-DD'
    if (!date) return;
    const time = withTime ? (/ (\d{2}:\d{2})$/.exec(text)?.[1] || '00:00') : null;
    const api = time ? `${date} ${time}` : date;
    setText(apiToDisplay(api, withTime));
    emit(api);
  };

  const invalid = text !== '' && !displayToApi(text, withTime);
  return (
    <div style={{ display: 'flex', gap: 4, position: 'relative', flexShrink: 0 }}>
      <input type="text" inputMode="numeric" value={text} onChange={onType} disabled={disabled}
        id={id} className={inputClassName}
        placeholder={withTime ? 'dd/mm/yyyy hh:mm' : 'dd/mm/yyyy'}
        title={withTime ? 'dd/mm/yyyy HH:MM (24-hour)' : 'dd/mm/yyyy'}
        style={{ ...inputStyle, fontVariantNumeric: 'tabular-nums', ...(invalid ? { borderColor: '#f28b82' } : {}) }} />
      <button type="button" title="Pick from calendar" disabled={disabled} className={buttonClassName}
        style={{ cursor: disabled ? 'default' : 'pointer', ...buttonStyle }}
        onClick={() => { try { pickerRef.current?.showPicker(); } catch { pickerRef.current?.focus(); } }}>
        📅
      </button>
      <input ref={pickerRef} type="date" tabIndex={-1} aria-hidden="true" onChange={onPick}
        value={(value || '').slice(0, 10)}
        style={{ position: 'absolute', left: 0, bottom: 0, width: 1, height: 1, opacity: 0, pointerEvents: 'none' }} />
    </div>
  );
}
