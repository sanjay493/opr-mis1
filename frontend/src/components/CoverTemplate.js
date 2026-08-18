'use client';

// Mirrors backend/page_templates/cover.html (and its .page1-* CSS in
// main.html) — see page_cover.py for what's dynamic (Report Month, the 4
// KPI figures) vs. the static background artwork. The background is the
// user-supplied coverPage.png (A4-proportioned; logo/title/"Prepared By"
// are baked into the image itself). Dynamic content is overlaid as text
// positioned into the image's own blank space — its lower-left corner has
// a faint decorative world-map watermark and nothing else printed there,
// which is where the Report Month line and the 2x2 KPI grid land.
// Positions are absolute + %-based (not flow-based) so they land in that
// blank area consistently regardless of render size (PDF vs. the live
// web-view's own container width) — coordinates were read directly off
// the reference image, not derived from any dynamic boundary.
const NAVY = '#000c48';
const ROYAL_BLUE = '#0047c8';
const MOLTEN_RED = '#e8380d';
const GREEN = '#064e3b';
const RED = '#9a3412';

const KPI_ICONS = {
  'HOT METAL': (
    <>
      <path d="M7 3h10l-1.5 6H8.5L7 3Z" fill="none" stroke={ROYAL_BLUE} strokeWidth="1.6" strokeLinejoin="round" />
      <path d="M6 9h12l-1.2 9.5A2 2 0 0 1 14.8 20H9.2a2 2 0 0 1-2-1.5L6 9Z" fill="none" stroke={ROYAL_BLUE} strokeWidth="1.6" strokeLinejoin="round" />
    </>
  ),
  'CRUDE STEEL': (
    <>
      <path d="M5 8h14v8a3 3 0 0 1-3 3H8a3 3 0 0 1-3-3V8Z" fill="none" stroke={ROYAL_BLUE} strokeWidth="1.6" strokeLinejoin="round" />
      <path d="M8 8V6a1 1 0 0 1 1-1h6a1 1 0 0 1 1 1v2" fill="none" stroke={ROYAL_BLUE} strokeWidth="1.6" />
      <line x1="12" y1="11" x2="12" y2="16" stroke={ROYAL_BLUE} strokeWidth="1.6" />
    </>
  ),
  'FINISHED STEEL': (
    <>
      <circle cx="12" cy="12" r="8.5" fill="none" stroke={ROYAL_BLUE} strokeWidth="1.6" />
      <circle cx="12" cy="12" r="5" fill="none" stroke={ROYAL_BLUE} strokeWidth="1.6" />
      <circle cx="12" cy="12" r="1.5" fill={ROYAL_BLUE} />
    </>
  ),
  'SALEABLE STEEL': (
    <>
      <rect x="4" y="15" width="16" height="3.2" rx="0.6" fill="none" stroke={ROYAL_BLUE} strokeWidth="1.5" />
      <rect x="4" y="10.5" width="16" height="3.2" rx="0.6" fill="none" stroke={ROYAL_BLUE} strokeWidth="1.5" />
      <rect x="4" y="6" width="16" height="3.2" rx="0.6" fill="none" stroke={ROYAL_BLUE} strokeWidth="1.5" />
    </>
  ),
};

export default function CoverTemplate({ data }) {
  const {
    bg_data_uri = '', month_display = '', month_short = '', kpis = [],
  } = data || {};

  return (
    <div style={{ position: 'relative', zIndex: 0, minHeight: '100%', overflow: 'hidden' }}>

      {bg_data_uri && (
        <img src={bg_data_uri} alt="" style={{ position: 'absolute', inset: 0, width: '100%', height: '100%', objectFit: 'cover' }} />
      )}

      <div style={{ position: 'relative', zIndex: 1, minHeight: '100%', fontFamily: 'inherit' }}>

        <div style={{ position: 'absolute', top: '70.5%', left: '4%', width: '48%', fontSize: '52pt', fontWeight: 900, lineHeight: 1, letterSpacing: '-0.01em', color: MOLTEN_RED, whiteSpace: 'nowrap' }}>
          {month_display}
        </div>

        <div style={{ position: 'absolute', top: '77%', left: '4%', width: '58%' }}>
          <div style={{ fontSize: '9.5pt', fontWeight: 700, color: NAVY, textTransform: 'uppercase', letterSpacing: '0.02em', marginBottom: 0 }}>
            SAIL Performance at a Glance ({month_short})
            <span style={{ display: 'block', width: 36, height: 2, background: ROYAL_BLUE, marginTop: 3, marginBottom: 5 }} />
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '5px 12px' }}>
            {kpis.map((k) => (
              <div key={k.label} style={{ background: 'rgba(255,255,255,0.72)', border: '1px solid transparent', borderImage: 'linear-gradient(to right, #e2e8f0, transparent) 1', borderRadius: 6, padding: '5px 10px', display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 6, boxShadow: '0 1px 3px rgba(0,0,0,0.06)' }}>
                <div style={{ flex: '1 1 auto', minWidth: 0 }}>
                  <svg width="14" height="14" viewBox="0 0 24 24" style={{ marginBottom: 1 }}>{KPI_ICONS[k.label]}</svg>
                  <div style={{ fontSize: '11.5pt', fontWeight: 700, letterSpacing: '0.02em', color: '#475569', textTransform: 'uppercase' }}>{k.label}</div>
                  <div style={{ fontSize: '11.5pt', fontWeight: 800, color: ROYAL_BLUE, lineHeight: 1 }}>
                    {k.mt} <span style={{ fontWeight: 600, color: '#64748b' }}>MT</span>
                  </div>
                </div>
                <div style={{ flex: '1 1 auto', textAlign: 'right', borderLeft: '1px dashed #e2e8f0', paddingLeft: 6, fontSize: '8.5pt', fontWeight: 700, color: '#475569', lineHeight: 1.45, whiteSpace: 'nowrap' }}>
                  <div>{k.pct_ful}% <span style={{ fontSize: '0.72em', fontWeight: 500 }}>of APP</span></div>
                  <div>CPLY:{' '}
                    {k.growth_good === true && <b style={{ color: GREEN }}>+{k.growth}%</b>}
                    {k.growth_good === false && <b style={{ color: RED }}>{k.growth}%</b>}
                    {k.growth_good == null && '—'}
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>

      <div style={{ position: 'absolute', left: 0, bottom: '0.8%', zIndex: 2, width: '100%', display: 'flex', justifyContent: 'center', gap: 8, fontSize: '6.5pt', color: NAVY }}>
        <span>MIS OPERATIONS</span><span>|</span><span>OMI &ndash; {month_short}</span><span>|</span><span>FOR INTERNAL CIRCULATION ONLY</span>
      </div>
    </div>
  );
}
