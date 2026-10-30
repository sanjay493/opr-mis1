'use client';

import { useState } from 'react';
import s from './ua.module.css';

const norm = (t) => t.replace(/\s+/g, ' ').trim();

// Chosen tags as removable chips plus a text box: Enter or comma adds the
// typed tag, Backspace on an empty box removes the last one. `suggestions`
// (tags already in use, then the standard ones) are one click away.
export default function TagInput({ value, onChange, suggestions = [], id }) {
  const [text, setText] = useState('');
  const has = (t) => value.some((v) => v.toLowerCase() === t.toLowerCase());

  const add = (raw) => {
    const t = norm(raw).slice(0, 48);
    if (t && !has(t)) onChange([...value, t]);
    setText('');
  };

  const onKeyDown = (e) => {
    if (e.key === 'Enter' || e.key === ',') {
      e.preventDefault();
      add(text);
    } else if (e.key === 'Backspace' && !text && value.length) {
      onChange(value.slice(0, -1));
    }
  };

  const offered = suggestions.filter((t) => !has(t)).slice(0, 14);
  return (
    <div>
      <div className={s.tagBox}>
        {value.map((t) => (
          <span key={t} className={s.tag}>
            #{t}
            <button type="button" className={s.tagX} aria-label={`Remove tag ${t}`}
                    onClick={() => onChange(value.filter((v) => v !== t))}>×</button>
          </span>
        ))}
        <input id={id} className={s.tagEntry} value={text} maxLength={48}
               placeholder={value.length ? 'Add another tag…' : 'Type a tag and press Enter'}
               onChange={(e) => setText(e.target.value.replace(',', ''))}
               onKeyDown={onKeyDown} onBlur={() => text && add(text)} />
      </div>
      {offered.length > 0 && (
        <div className={s.suggest}>
          <span>Add:</span>
          {offered.map((t) => <button key={t} type="button" onClick={() => add(t)}>+ {t}</button>)}
        </div>
      )}
    </div>
  );
}
