'use client';

// Mirrors backend/page_templates/cover.html — see page_cover.py for what's
// dynamic (Report Month, the 4 KPI figures) vs. static branding chrome.
// Inline-styled (no shared .page1-* stylesheet), matching this app's newer
// report templates' convention.
const NAVY = '#0a1a4a';
const ACCENT = '#0284c7';
const GREEN = '#064e3b';
const RED = '#9a3412';
const EMBER = '#ea580c';

const KPI_ICONS = {
  'HOT METAL': (
    <>
      <path d="M7 3h10l-1.5 6H8.5L7 3Z" fill="none" stroke={ACCENT} strokeWidth="1.6" strokeLinejoin="round" />
      <path d="M6 9h12l-1.2 9.5A2 2 0 0 1 14.8 20H9.2a2 2 0 0 1-2-1.5L6 9Z" fill="none" stroke={ACCENT} strokeWidth="1.6" strokeLinejoin="round" />
    </>
  ),
  'CRUDE STEEL': (
    <>
      <path d="M5 8h14v8a3 3 0 0 1-3 3H8a3 3 0 0 1-3-3V8Z" fill="none" stroke={ACCENT} strokeWidth="1.6" strokeLinejoin="round" />
      <path d="M8 8V6a1 1 0 0 1 1-1h6a1 1 0 0 1 1 1v2" fill="none" stroke={ACCENT} strokeWidth="1.6" />
      <line x1="12" y1="11" x2="12" y2="16" stroke={ACCENT} strokeWidth="1.6" />
    </>
  ),
  'FINISHED STEEL': (
    <>
      <circle cx="12" cy="12" r="8.5" fill="none" stroke={ACCENT} strokeWidth="1.6" />
      <circle cx="12" cy="12" r="5" fill="none" stroke={ACCENT} strokeWidth="1.6" />
      <circle cx="12" cy="12" r="1.5" fill={ACCENT} />
    </>
  ),
  'SALEABLE STEEL': (
    <>
      <rect x="4" y="15" width="16" height="3.2" rx="0.6" fill="none" stroke={ACCENT} strokeWidth="1.5" />
      <rect x="4" y="10.5" width="16" height="3.2" rx="0.6" fill="none" stroke={ACCENT} strokeWidth="1.5" />
      <rect x="4" y="6" width="16" height="3.2" rx="0.6" fill="none" stroke={ACCENT} strokeWidth="1.5" />
    </>
  ),
};

const VALUE_ICONS = [
  ['Performance', (
    <>
      <polyline points="3,17 9,10 13,14 21,5" fill="none" stroke={ACCENT} strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
      <polyline points="15,5 21,5 21,11" fill="none" stroke={ACCENT} strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
    </>
  )],
  ['Efficiency', (
    <>
      <circle cx="12" cy="12" r="3" fill="none" stroke={ACCENT} strokeWidth="1.6" />
      <path d="M12 3v2.2M12 18.8V21M21 12h-2.2M5.2 12H3M18.4 5.6l-1.6 1.6M7.2 16.8l-1.6 1.6M18.4 18.4l-1.6-1.6M7.2 7.2 5.6 5.6" stroke={ACCENT} strokeWidth="1.6" strokeLinecap="round" />
    </>
  )],
  ['Sustainability', (
    <>
      <path d="M6 19c-2-6 1-13 12-14 1 8-3 13-12 14Z" fill="none" stroke={ACCENT} strokeWidth="1.6" strokeLinejoin="round" />
      <path d="M7 18c3-4 6-7 10-11" fill="none" stroke={ACCENT} strokeWidth="1.6" strokeLinecap="round" />
    </>
  )],
  ['People', (
    <>
      <circle cx="9" cy="8" r="3" fill="none" stroke={ACCENT} strokeWidth="1.6" />
      <path d="M3.5 19c.5-3.5 3-5.5 5.5-5.5s5 2 5.5 5.5" fill="none" stroke={ACCENT} strokeWidth="1.6" strokeLinecap="round" />
      <circle cx="17" cy="9" r="2.3" fill="none" stroke={ACCENT} strokeWidth="1.6" />
      <path d="M15.2 13.2c2.2-.3 4.4 1.3 5 4.3" fill="none" stroke={ACCENT} strokeWidth="1.6" strokeLinecap="round" />
    </>
  )],
  ['Growth', (
    <>
      <polyline points="3,16 9,10 13,13 21,4" fill="none" stroke={ACCENT} strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
      <polyline points="16,4 21,4 21,9" fill="none" stroke={ACCENT} strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
      <line x1="3" y1="20" x2="21" y2="20" stroke={ACCENT} strokeWidth="1.6" strokeLinecap="round" />
    </>
  )],
];

export default function CoverTemplate({ data }) {
  const {
    logo_data_uri = '', corner_image_data_uri = '', month_display = '', month_short = '', kpis = [], products = [],
  } = data || {};

  return (
    <div style={{ display: 'flex', flexDirection: 'column', minHeight: '100%', padding: '14mm 16mm 10mm', fontFamily: 'inherit', position: 'relative', zIndex: 0 }}>

      {corner_image_data_uri && (
        <img
          src={corner_image_data_uri}
          alt=""
          style={{
            position: 'absolute', top: '6mm', right: '16mm', width: '58mm', height: '32.5mm',
            objectFit: 'cover', borderRadius: 6, border: '1px solid #e2e8f0', boxShadow: '0 2px 6px rgba(15,23,42,0.18)',
          }}
        />
      )}

      <div style={{ display: 'flex', alignItems: 'center', gap: 14, marginBottom: '10mm' }}>
        {logo_data_uri && <img src={logo_data_uri} alt="SAIL" style={{ height: 46, width: 'auto', display: 'block' }} />}
        <div style={{ fontSize: '10.5pt', fontWeight: 700, color: NAVY, lineHeight: 1.25, textTransform: 'uppercase', borderLeft: `2px solid ${ACCENT}`, paddingLeft: 12 }}>
          Strengthening India<br />Through Steel
        </div>
      </div>

      <div style={{ width: 80, height: 6, background: `linear-gradient(90deg, ${NAVY}, ${EMBER})`, marginBottom: 14, borderRadius: 3 }} />
      <h1 style={{ fontSize: '34pt', fontWeight: 900, lineHeight: 1.05, margin: 0, textTransform: 'uppercase' }}>
        <div style={{ color: NAVY }}>Operations</div>
        <div style={{ color: ACCENT }}>Monthly</div>
        <div style={{ color: '#64748b', fontWeight: 700 }}>Informatics</div>
      </h1>
      <p style={{ fontSize: '13pt', fontWeight: 600, color: NAVY, letterSpacing: '0.08em', textTransform: 'uppercase', borderBottom: '1px solid #e2e8f0', paddingBottom: 12, margin: '6px 0 16px' }}>
        Operations Directorate
      </p>

      <div style={{ display: 'flex', gap: 32, marginBottom: '14mm' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <div style={{ width: 34, height: 34, borderRadius: '50%', background: NAVY, display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0 }}>
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none">
              <rect x="3" y="12" width="4" height="8" fill="#fff" />
              <rect x="10" y="7" width="4" height="13" fill="#fff" />
              <rect x="17" y="3" width="4" height="17" fill="#fff" />
            </svg>
          </div>
          <div>
            <div style={{ fontSize: '9pt', color: '#475569' }}>Prepared By</div>
            <div style={{ fontSize: '11.5pt', fontWeight: 700, color: NAVY }}>MIS Group</div>
          </div>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <div style={{ width: 34, height: 34, borderRadius: '50%', background: NAVY, display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0 }}>
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none">
              <rect x="3" y="5" width="18" height="16" rx="2" stroke="#fff" strokeWidth="1.8" />
              <line x1="3" y1="10" x2="21" y2="10" stroke="#fff" strokeWidth="1.8" />
              <line x1="7" y1="2.5" x2="7" y2="6.5" stroke="#fff" strokeWidth="1.8" />
              <line x1="17" y1="2.5" x2="17" y2="6.5" stroke="#fff" strokeWidth="1.8" />
            </svg>
          </div>
          <div>
            <div style={{ fontSize: '9pt', color: '#475569' }}>Report Month</div>
            <div style={{ fontSize: '11.5pt', fontWeight: 700, color: NAVY }}>{month_display}</div>
          </div>
        </div>
      </div>

      <div style={{ display: 'flex', alignItems: 'center', gap: 12, justifyContent: 'center', fontSize: '12pt', fontWeight: 700, color: NAVY, marginBottom: 12 }}>
        <span style={{ flex: '1 1 auto', maxWidth: 90, height: 1, background: '#e2e8f0' }} />
        <span style={{ width: 6, height: 6, borderRadius: '50%', background: ACCENT }} />
        <span>SAIL Performance at a Glance ({month_short})</span>
        <span style={{ width: 6, height: 6, borderRadius: '50%', background: ACCENT }} />
        <span style={{ flex: '1 1 auto', maxWidth: 90, height: 1, background: '#e2e8f0' }} />
      </div>

      <div style={{ display: 'flex', gap: 10, marginBottom: '14mm' }}>
        {kpis.map((k) => (
          <div key={k.label} style={{ flex: '1 1 0', background: '#f8fafc', border: '1px solid #e2e8f0', borderRadius: 8, padding: '12px 10px', textAlign: 'center' }}>
            <svg width="26" height="26" viewBox="0 0 24 24" style={{ marginBottom: 4 }}>{KPI_ICONS[k.label]}</svg>
            <div style={{ fontSize: '8pt', fontWeight: 700, letterSpacing: '0.04em', color: '#475569', marginBottom: 6 }}>{k.label}</div>
            <div style={{ fontSize: '20pt', fontWeight: 800, color: NAVY, lineHeight: 1 }}>{k.mt}</div>
            <div style={{ fontSize: '8pt', fontWeight: 600, color: '#64748b', marginBottom: 8 }}>MT</div>
            <div style={{ fontSize: '8pt', color: '#475569', borderTop: '1px dashed #e2e8f0', paddingTop: 6, marginTop: 2 }}>
              {k.pct_ful}% of APP<br />
              vs CPLY:{' '}
              {k.growth_good === true && <b style={{ color: GREEN }}>+{k.growth}%</b>}
              {k.growth_good === false && <b style={{ color: RED }}>{k.growth}%</b>}
              {k.growth_good == null && '—'}
            </div>
          </div>
        ))}
      </div>

      {products.length > 0 && (
        <>
          <div style={{ display: 'flex', alignItems: 'center', gap: 12, justifyContent: 'center', fontSize: '12pt', fontWeight: 700, color: NAVY, marginBottom: 12 }}>
            <span style={{ flex: '1 1 auto', maxWidth: 90, height: 1, background: '#e2e8f0' }} />
            <span style={{ width: 6, height: 6, borderRadius: '50%', background: EMBER }} />
            <span>Products of SAIL</span>
            <span style={{ width: 6, height: 6, borderRadius: '50%', background: EMBER }} />
            <span style={{ flex: '1 1 auto', maxWidth: 90, height: 1, background: '#e2e8f0' }} />
          </div>
          <div style={{ display: 'flex', gap: 8, marginBottom: '14mm' }}>
            {products.map((p) => (
              <div key={p.label} style={{ flex: '1 1 0', textAlign: 'center' }}>
                <img
                  src={p.img}
                  alt={p.label}
                  style={{ width: '100%', height: '20mm', objectFit: 'cover', borderRadius: 6, border: '1px solid #e2e8f0', display: 'block', marginBottom: 4 }}
                />
                <div style={{ fontSize: '7.5pt', fontWeight: 700, letterSpacing: '0.02em', color: '#475569' }}>{p.label}</div>
              </div>
            ))}
          </div>
        </>
      )}

      <div style={{ marginTop: 'auto', borderTop: `2px solid ${NAVY}`, paddingTop: 10 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 18, marginBottom: 10 }}>
          {VALUE_ICONS.map(([label, icon]) => (
            <div key={label} style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 4, flex: '0 0 auto' }}>
              <div style={{ width: 30, height: 30, borderRadius: '50%', border: `1.5px solid ${ACCENT}`, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                <svg width="14" height="14" viewBox="0 0 24 24">{icon}</svg>
              </div>
              <div style={{ fontSize: '6.5pt', fontWeight: 700, letterSpacing: '0.03em', color: '#475569' }}>{label.toUpperCase()}</div>
            </div>
          ))}
          <div style={{ marginLeft: 'auto', textAlign: 'right', fontSize: '9.5pt', fontWeight: 700, color: NAVY, lineHeight: 1.3 }}>
            Driving Excellence. Delivering Value.<br />
            Building a <b style={{ color: ACCENT }}>Stronger India</b>.
          </div>
        </div>
        <div style={{ display: 'flex', justifyContent: 'center', gap: 10, fontSize: '7.5pt', color: '#64748b', borderTop: '1px solid #e2e8f0', paddingTop: 8 }}>
          <span>MIS OPERATIONS</span><span>|</span><span>OMI &ndash; {month_short}</span><span>|</span><span>FOR INTERNAL CIRCULATION ONLY</span>
        </div>
      </div>
    </div>
  );
}
