// Grouped manual-entry pages: each group is one route with a tab per entry
// form. A tab's `id` is the form's old route slug — /data-entry/<id> still
// exists and redirects to `${group.route}?tab=<id>` (see tabHref), so old
// links and bookmarks keep working. The forms themselves live in
// components/entry/<id>/Form.js (loaded by EntryTabs).
//
// Plain data module (no 'use client') so the server-side redirect pages can
// import it too.

export const ENTRY_GROUPS = [
  {
    id: 'production-techno',
    route: '/data-entry/production-techno',
    title: 'Production & Techno Entry',
    description: 'Production actuals, techno-economic parameters and their corrections.',
    icon: '📊',
    tabs: [
      { id: 'production', label: 'Production Data Entry', description: 'Enter actual production values for each item; plan values come from the uploaded ABP.' },
      { id: 'production-range', label: 'Production — Month Range', description: 'Enter or correct one plant/unit\'s production across several months at once.' },
      { id: 'techno-manual', label: 'Techno Manual Entry', description: 'Enter techno-economic parameters manually for each plant and unit.' },
      { id: 'techno-correction', label: 'Techno Data Correction', description: 'Find one techno parameter across a month range and correct it inline.' },
      { id: 'bf-large-snapshot', label: 'SAIL Large BFs', description: 'Month and Till Month figures for BSP BF-8, RSP BF-5 and ISP BF-5.' },
      { id: 'key-parameters-manual', label: 'Key Parameters', description: 'CAPEX, Labour Productivity, Rake Detention, Demurrage, HM to PCM/Sand/Dry Pit, RLTIFR, Sinter Fe.' },
      { id: 'co2-water-pm-manual', label: 'CO2 / Water / PM', description: 'Enter CO2, water and PM figures when no EPI report is available, or correct a value.' },
    ],
  },
  {
    id: 'mines',
    route: '/data-entry/mines',
    title: 'Mines Entry',
    description: 'SAIL mines (coal, washery, flux) and iron ore mines production & despatch.',
    icon: '⛏️',
    tabs: [
      { id: 'sail-mines', label: 'SAIL Mines (Page 4.5)', description: 'Monthly actual and plan for coal mines, washery, coal despatch and flux.' },
      { id: 'mines-production-despatch', label: 'Iron Ore Mines Production & Despatch', description: 'Mine-level fresh production and despatch by rail/road to captive, sales or pellet conversion.' },
    ],
  },
  {
    id: 'special-steel-entry',
    route: '/data-entry/special-steel-entry',
    title: 'Special Steel Entry',
    description: 'ISP special steel entry, grade clubbing, and Special Steel Plants physical performance and IPT.',
    icon: '🔩',
    tabs: [
      { id: 'special-steel', label: 'Manual Entry (ISP)', description: 'ISP entry and corrections — other plants are auto-extracted from uploads.' },
      { id: 'special-steel-grade-clubs', label: 'Grade Clubbing', description: 'Combine near-duplicate quality grades into one report row.' },
      { id: 'special-steel-physical', label: 'Physical Performance', description: 'Multi-year history grid for ASP / SSP / VISP.' },
      { id: 'special-steel-ipt', label: 'IPT Requirement', description: 'Annual inter-plant-transfer requirement list for the Special Steel Plants.' },
    ],
  },
  {
    id: 'commentary',
    route: '/data-entry/commentary',
    title: 'Report Commentary & Market',
    description: 'Written highlights for the report, steel sales bulletin and market intelligence figures.',
    icon: '📝',
    tabs: [
      { id: 'key-highlights', label: 'Key Highlights & Variances', description: 'Major achievements, shortfalls and focus areas for the month.' },
      { id: 'steel-sales-highlights', label: 'Steel Sales (Page 3.05)', description: 'Month and YTD Key Performance Parameter bullets for Steel Sales Performance.' },
      { id: 'market-intel', label: 'Market Intelligence (Pages 2.41/2.42)', description: 'BigMint price series and India macro-economic figures, one month at a time.' },
    ],
  },
  {
    id: 'reference',
    route: '/data-entry/reference',
    title: 'Reference & Records',
    description: 'BF benchmarking, rail, ready reckoner and major-unit daily records.',
    icon: '📋',
    tabs: [
      { id: 'bf-benchmark', label: 'Large BF Benchmarking', description: 'Non-SAIL large BFs and their per-FY figures, plus SAIL BF working volume.' },
      { id: 'rail-report', label: 'Rail Production & Dispatch (Page 18.5)', description: 'One financial year at a time; running Apr-to-date cumulative for the open FY.' },
      { id: 'ready-reckoner', label: 'Ready Reckoner', description: 'Unit-wise capacity and product-mix reference tables.' },
      { id: 'major-unit-daily', label: '5 ISPs Major Units Daily Records', description: 'Best-ever daily production figures for major units (Annexure-3).' },
    ],
  },
];

export function groupById(id) {
  return ENTRY_GROUPS.find((g) => g.id === id);
}

export function tabHref(tabId) {
  const group = ENTRY_GROUPS.find((g) => g.tabs.some((t) => t.id === tabId));
  return group ? `${group.route}?tab=${tabId}` : '/data-entry';
}
