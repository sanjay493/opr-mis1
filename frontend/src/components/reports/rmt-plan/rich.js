import { Fragment } from 'react';

// RMT plan remarks markup, shared by the report view and the entry form:
// **bold**, [blue]…[/blue], [red]…[/red], [brown]…[/brown] (rust brown),
// nestable, and line breaks kept. An opening mark with no closing one stays
// literal text. Same rules as rmt_plan_pdf.runs on the backend.
//
// The hex values mirror colors_config.json rmt_remark_* (the browser does
// not read that file).
export const REMARK_COLORS = {
  blue: { label: 'Blue', hex: '#0070C0' },
  red: { label: 'Red', hex: '#FF0000' },
  brown: { label: 'Rust brown', hex: '#B7410E' },
};

const TOKEN = /\*\*|\[(\/?)(blue|red|brown)\]/g;

// [{ text, bold, color }] for one remark.
export function runs(text) {
  const out = [];
  let bold = false;
  const colors = [];
  let last = 0;
  const push = (s) => {
    if (s) out.push({ text: s, bold, color: colors[colors.length - 1] || null });
  };
  for (const m of text.matchAll(TOKEN)) {
    const [tok, close, name] = m;
    const rest = text.slice(m.index + tok.length);
    let act = null;
    if (tok === '**') {
      if (bold || rest.includes('**')) act = () => { bold = !bold; };
    } else if (close) {
      if (colors[colors.length - 1] === name) act = () => colors.pop();
    } else if (rest.includes(`[/${name}]`)) {
      act = () => colors.push(name);
    }
    if (!act) continue; // literal: stays in the text
    push(text.slice(last, m.index));
    act();
    last = m.index + tok.length;
  }
  push(text.slice(last));
  return out;
}

// The markup with every mark removed.
export function plain(text) {
  return runs(text).map((r) => r.text).join('');
}

// A remark rendered without injecting HTML.
export function Rich({ text }) {
  if (!text) return null;
  return runs(text).map((r, j) => {
    const lines = r.text.split('\n').map((line, i) => <Fragment key={i}>{i > 0 && <br />}{line}</Fragment>);
    const style = r.color ? { color: REMARK_COLORS[r.color].hex } : undefined;
    const inner = r.bold ? <b style={style}>{lines}</b> : <span style={style}>{lines}</span>;
    return <Fragment key={j}>{inner}</Fragment>;
  });
}

// Wraps the selected text of a textarea in `open`…`close` and reports the
// new value; with nothing selected the marks are inserted at the caret.
export function wrapSelection(el, open, close, onChange) {
  const { selectionStart: a, selectionEnd: b, value } = el;
  onChange(value.slice(0, a) + open + value.slice(a, b) + close + value.slice(b));
  requestAnimationFrame(() => {
    el.focus();
    el.setSelectionRange(a + open.length, b + open.length);
  });
}

// Removes every mark from the selected text (or the whole remark when
// nothing is selected).
export function clearSelection(el, onChange) {
  const { selectionStart: a, selectionEnd: b, value } = el;
  if (a === b) { onChange(value.replace(TOKEN, '')); return; }
  const mid = value.slice(a, b).replace(TOKEN, '');
  onChange(value.slice(0, a) + mid + value.slice(b));
  requestAnimationFrame(() => {
    el.focus();
    el.setSelectionRange(a, a + mid.length);
  });
}
