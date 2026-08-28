'use client';

// Mirrors backend/page_templates/cover.html (and its .page1-* CSS in
// main.html) — see page_cover.py for what's dynamic (Report Month, the 6
// KPI figures) vs. the static background artwork. The background is the
// user-supplied coverPage.png (A4-proportioned; logo/title/"Prepared By"
// are baked into the image itself). Dynamic content is overlaid as text
// positioned into the image's own blank space — its lower-left corner has
// a faint decorative world-map watermark and nothing else printed there,
// which is where the Report Month line and the KPI honeycomb land.
// Positions are absolute + %-based (not flow-based) so they land in that
// blank area consistently regardless of render size (PDF vs. the live
// web-view's own container width) — coordinates were read directly off
// the reference image, not derived from any dynamic boundary.
const NAVY = '#000c48';
const ROYAL_BLUE = '#0047c8';
const ORE_RUST = '#b4530a';
const MOLTEN_RED = '#e8380d';
const GREEN = '#064e3b'; // colors.text_variance_green
const RED = '#9a3412'; // colors.text_variance_red

// stroke/fill use currentColor so each icon takes its hex's accent (blue
// for steel, rust for the Iron Ore hexes) from the wrapping <svg> style.
const KPI_ICONS = {
  'HOT METAL': (
    <>
      <path d="M7 3h10l-1.5 6H8.5L7 3Z" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinejoin="round" />
      <path d="M6 9h12l-1.2 9.5A2 2 0 0 1 14.8 20H9.2a2 2 0 0 1-2-1.5L6 9Z" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinejoin="round" />
    </>
  ),
  'CRUDE STEEL': (
    <>
      <path d="M5 8h14v8a3 3 0 0 1-3 3H8a3 3 0 0 1-3-3V8Z" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinejoin="round" />
      <path d="M8 8V6a1 1 0 0 1 1-1h6a1 1 0 0 1 1 1v2" fill="none" stroke="currentColor" strokeWidth="1.6" />
      <line x1="12" y1="11" x2="12" y2="16" stroke="currentColor" strokeWidth="1.6" />
    </>
  ),
  'FINISHED STEEL': (
    <>
      <circle cx="12" cy="12" r="8.5" fill="none" stroke="currentColor" strokeWidth="1.6" />
      <circle cx="12" cy="12" r="5" fill="none" stroke="currentColor" strokeWidth="1.6" />
      <circle cx="12" cy="12" r="1.5" fill="currentColor" />
    </>
  ),
  'SALEABLE STEEL': (
    <>
      <rect x="4" y="15" width="16" height="3.2" rx="0.6" fill="none" stroke="currentColor" strokeWidth="1.5" />
      <rect x="4" y="10.5" width="16" height="3.2" rx="0.6" fill="none" stroke="currentColor" strokeWidth="1.5" />
      <rect x="4" y="6" width="16" height="3.2" rx="0.6" fill="none" stroke="currentColor" strokeWidth="1.5" />
    </>
  ),
  'IRON ORE PRODUCTION': (
    <>
      <path d="M4 19h16L12 5 4 19Z" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinejoin="round" />
      <path d="M9.3 19 12 12.5 14.7 19" fill="none" stroke="currentColor" strokeWidth="1.3" />
    </>
  ),
  'IRON ORE SALES DESPATCH': (
    <>
      <path d="M3 6h10v9H3z" fill="none" stroke="currentColor" strokeWidth="1.6" />
      <path d="M13 9h4l3 3.4V15h-7z" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinejoin="round" />
      <circle cx="7" cy="17.3" r="1.5" fill="none" stroke="currentColor" strokeWidth="1.5" />
      <circle cx="16.4" cy="17.3" r="1.5" fill="none" stroke="currentColor" strokeWidth="1.5" />
    </>
  ),
};

// Flat-top hexagon honeycomb: 3 columns x 2 rows, middle column dropped
// half a cell. Order follows the kpis array — left: Hot Metal / Crude
// Steel; middle: the two Iron Ore Mines figures; right: Finished /
// Saleable Steel. Mirrors .page1-hex-{0..5} in main.html.
const HEX_CLIP = 'polygon(25% 0, 75% 0, 100% 50%, 75% 100%, 25% 100%, 0 50%)';
const HEX_POS = [
  { left: '0%', top: '0%' },
  { left: '0%', top: '40%' },
  { left: '30%', top: '20%' },
  { left: '30%', top: '60%' },
  { left: '60%', top: '0%' },
  { left: '60%', top: '40%' },
];

export default function CoverTemplate({ data }) {
  const {
    bg_data_uri = '', month_display = '', month_short = '', kpis = [],
  } = data || {};

  return (
    <div style={{ position: 'relative', zIndex: 0, minHeight: '100%', overflow: 'hidden', fontFamily: "'Roboto', Arial, Helvetica, sans-serif" }}>

      {bg_data_uri && (
        <img src={bg_data_uri} alt="" style={{ position: 'absolute', inset: 0, width: '100%', height: '100%', objectFit: 'cover' }} />
      )}

      <div style={{ position: 'relative', zIndex: 1, minHeight: '100%', fontFamily: 'inherit' }}>

        <div style={{ position: 'absolute', top: '65%', left: '12%', width: '48%', fontSize: '38pt', fontWeight: 900, lineHeight: 1, letterSpacing: '-0.01em', color: MOLTEN_RED, whiteSpace: 'nowrap' }}>
          {month_display}
        </div>

        <div style={{ position: 'absolute', top: '72%', left: '8%', width: '44%' }}>
          <div style={{ fontSize: '9.5pt', fontWeight: 700, color: NAVY, textTransform: 'uppercase', letterSpacing: '0.02em', marginBottom: 0 }}>
            SAIL Performance at a Glance ({month_short})
            <span style={{ display: 'block', width: 36, height: 2, background: ROYAL_BLUE, marginTop: 3, marginBottom: 5 }} />
          </div>

          <div style={{ position: 'relative', width: '100%', aspectRatio: '3 / 2', marginTop: 6 }}>
            {kpis.map((k, i) => {
              const ore = k.kind === 'ore';
              const accent = ore ? ORE_RUST : ROYAL_BLUE;
              return (
              <div key={k.label} style={{ position: 'absolute', width: '40%', height: '40%', ...HEX_POS[i] }}>
                <div style={{ position: 'absolute', inset: 0, background: accent, clipPath: HEX_CLIP, filter: 'drop-shadow(0 2px 4px rgba(15,23,42,0.4))' }} />
                <div style={{ position: 'absolute', inset: 1.2, background: ore ? 'linear-gradient(155deg, #ffffff 42%, #fbe6d0)' : 'linear-gradient(155deg, #ffffff 45%, #e5edfb)', clipPath: HEX_CLIP, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', textAlign: 'center', padding: '0 9%' }}>
                  <svg viewBox="0 0 24 24" style={{ width: 15, height: 15, marginBottom: 1, color: accent }}>{KPI_ICONS[k.label]}</svg>
                  <div style={{ fontSize: '8.5pt', fontWeight: 700, color: NAVY, textTransform: 'capitalize', letterSpacing: '0.01em', lineHeight: 1.03 }}>{k.label}</div>
                  <div style={{ fontSize: '13pt', fontWeight: 800, color: accent, lineHeight: 1.28 }}>
                    {k.mt}<span style={{ fontSize: '8pt', fontWeight: 600, color: '#64748b', marginLeft: 1 }}>MT</span>
                  </div>
                  <div style={{ fontSize: '8.5pt', fontWeight: 700, color: '#475569', lineHeight: 1.15, whiteSpace: 'nowrap' }}>
                    APP {k.pct_ful}%
                    {k.growth_good === true && <span style={{ color: GREEN }}>{' · ▲'}{k.growth_abs}%</span>}
                    {k.growth_good === false && <span style={{ color: RED }}>{' · ▼'}{k.growth_abs}%</span>}
                  </div>
                </div>
              </div>
              );
            })}
          </div>
        </div>
      </div>

      <div style={{ position: 'absolute', left: 0, bottom: '0.8%', zIndex: 2, width: '100%', display: 'flex', justifyContent: 'center', gap: 8, fontSize: '6.5pt', color: NAVY }}>
        <span>MIS OPERATIONS</span><span>|</span><span>OMI &ndash; {month_short}</span><span>|</span><span>FOR INTERNAL CIRCULATION ONLY</span>
      </div>
    </div>
  );
}
