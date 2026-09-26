'use client';

// Helpers shared by the tabs of /reports/techno (Plant-wise Monthly,
// Dashboard, Custom Report, Verification, BF Furnace-wise).

export const API_BASE = process.env.NEXT_PUBLIC_API_URL || '';

export const MONTH_NAMES_FULL = [
  'January', 'February', 'March', 'April', 'May', 'June',
  'July', 'August', 'September', 'October', 'November', 'December',
];
// FY order (April first) for month pickers.
export const FY_MONTHS = [...MONTH_NAMES_FULL.slice(3), ...MONTH_NAMES_FULL.slice(0, 3)];
export const MONTH_NUM = {
  January: '01', February: '02', March: '03', April: '04',
  May: '05', June: '06', July: '07', August: '08',
  September: '09', October: '10', November: '11', December: '12',
};
export const MONTH_ABBR = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];

const YEAR_RANGE_START = 2000;
const _now = new Date();
// FY start year: Apr..Dec -> this calendar year; Jan..Mar -> previous calendar year
export const CURRENT_FY_END_YEAR = (_now.getMonth() >= 3 ? _now.getFullYear() : _now.getFullYear() - 1) + 1;
// Calendar years: 2000 through the current FY's end year (covers Jan-Mar
// report months that fall in the current FY but the next calendar year).
export const YEARS = Array.from(
  { length: CURRENT_FY_END_YEAR - YEAR_RANGE_START + 1 },
  (_, i) => String(YEAR_RANGE_START + i)
);
export const FY_END_YEARS = Array.from(
  { length: CURRENT_FY_END_YEAR - YEAR_RANGE_START }, // FY needs a start year too, so one fewer
  (_, i) => YEAR_RANGE_START + 1 + i
).reverse();

export function getDefaultPeriod() {
  const d = new Date(); d.setMonth(d.getMonth() - 1);
  return { monthName: MONTH_NAMES_FULL[d.getMonth()], year: String(d.getFullYear()) };
}

// "2026-07" -> "Jul'26"
export function monthLabel(ym) {
  const [y, m] = ym.split('-');
  return `${MONTH_ABBR[parseInt(m, 10) - 1]}'${y.slice(2)}`;
}

export function fmtNum(v, maxDigits = 3) {
  if (v === null || v === undefined || v === '') return '—';
  const n = Number(v);
  if (Number.isNaN(n)) return String(v);
  return n.toLocaleString('en-IN', { maximumFractionDigits: maxDigits });
}

export const cell = {
  padding: '7px 12px',
  fontSize: '10.5pt',
  borderBottom: '1px solid #e8eaed',
  whiteSpace: 'nowrap',
};

export const selStyle = {
  padding: '8px 12px', fontSize: '11pt', border: '1px solid #dadce0',
  borderRadius: '6px', backgroundColor: '#ffffff', color: '#202124', cursor: 'pointer',
};

export const th = (extra = {}) => ({
  ...cell, position: 'sticky', top: 0, zIndex: 2, backgroundColor: '#e8f0fe',
  fontWeight: 700, color: '#174ea6', textAlign: 'right', ...extra,
});

export function pillStyle(on) {
  return {
    padding: '6px 16px', fontSize: '10.5pt', fontWeight: 600,
    border: on ? '1px solid #1a73e8' : '1px solid #dadce0',
    borderRadius: '16px', cursor: 'pointer',
    backgroundColor: on ? '#1a73e8' : '#ffffff',
    color: on ? '#ffffff' : '#5f6368',
    transition: 'all 0.15s ease',
  };
}

export function segBtnStyle(active) {
  return {
    padding: '8px 20px', fontSize: '11pt', fontWeight: 600, border: 'none',
    cursor: 'pointer', backgroundColor: active ? '#1a73e8' : 'transparent',
    color: active ? '#ffffff' : '#5f6368',
  };
}

export function SegmentedToggle({ options, value, onChange }) {
  return (
    <div style={{
      display: 'inline-flex', border: '1px solid #dadce0', borderRadius: '6px',
      overflow: 'hidden', backgroundColor: '#ffffff',
    }}>
      {options.map(([v, lbl]) => (
        <button key={v} onClick={() => onChange(v)} style={segBtnStyle(value === v)}>{lbl}</button>
      ))}
    </div>
  );
}

export function ErrorBox({ children }) {
  if (!children) return null;
  return (
    <div style={{
      padding: '14px 18px', border: '1px solid #f28b82', borderRadius: '8px',
      backgroundColor: '#fce8e6', color: '#c5221f', fontSize: '11pt', marginBottom: '20px',
    }}>
      {children}
    </div>
  );
}

export function EmptyState({ children }) {
  return (
    <div style={{ padding: '40px', textAlign: 'center', color: '#5f6368', fontSize: '12pt' }}>
      {children}
    </div>
  );
}

export function TabIntro({ children }) {
  return (
    <p style={{ fontSize: '11pt', color: '#5f6368', margin: '0 0 20px' }}>{children}</p>
  );
}

export function ExportButtons({ onDownload, downloading, disabled }) {
  return (
    <div style={{ display: 'flex', gap: '10px' }}>
      {['excel', 'pdf'].map((kind) => (
        <button
          key={kind}
          onClick={() => onDownload(kind)}
          disabled={disabled || downloading !== null}
          style={{
            padding: '8px 18px', fontSize: '10.5pt', fontWeight: 700,
            border: '1px solid #1a73e8', borderRadius: '6px',
            cursor: disabled || downloading !== null ? 'not-allowed' : 'pointer',
            backgroundColor: '#ffffff',
            color: disabled || downloading !== null ? '#9aa0a6' : '#1a73e8',
          }}
        >
          {downloading === kind ? 'Generating…' : `⬇ ${kind === 'excel' ? 'Excel' : 'PDF'}`}
        </button>
      ))}
    </div>
  );
}

// Fetch a file (GET when body is undefined, JSON POST otherwise) and save it.
// Throws with the backend's `detail` message on failure.
export async function downloadFile(url, body, filename) {
  const res = body === undefined
    ? await fetch(url)
    : await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });
  if (!res.ok) {
    const b = await res.json().catch(() => ({}));
    throw new Error(b.detail || `HTTP ${res.status}`);
  }
  const blob = await res.blob();
  const objUrl = window.URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = objUrl;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  window.URL.revokeObjectURL(objUrl);
}
