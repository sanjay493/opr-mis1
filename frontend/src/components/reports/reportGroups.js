// Grouped report pages: each group is one route with a tab per report.
// A tab's `id` is the report's old route slug — /reports/<id> still exists
// and redirects to `${group.route}?tab=<id>` (see tabHref), so old links
// and bookmarks keep working. The reports themselves live in
// components/reports/<id>/View.js (loaded by ReportTabs).
//
// Plain data module (no 'use client') so the server-side redirect pages can
// import it too.

export const REPORT_GROUPS = [
  {
    id: 'production-analysis',
    route: '/reports/production-analysis',
    title: 'Production Reports',
    description: 'Month-wise production, trends, unit-wise queries and special steel plants performance.',
    icon: '📊',
    tabs: [
      { id: 'production-fy', label: 'Month-wise Production', description: 'All plants, all items — monthly actual/plan figures for a financial year.' },
      { id: 'production-trend', label: 'HM/CS/FS/Saleable Steel Trend', description: 'Year-wise trend of Hot Metal, Crude Steel, Finished Steel and Saleable Steel.' },
      { id: 'production-query', label: 'Unit-wise Production Query', description: 'Ad-hoc unit-wise production lookup across months.' },
      { id: 'production-items', label: 'Production Items (Month & Unit-wise)', description: 'Oven Pushing / Sinter / Hot Metal / Crude Steel / Pig Iron / Finished Steel / Saleable Steel.' },
      { id: 'special-steel-physical', label: 'Special Steel Plants Physical Performance', description: 'Multi-year history for ASP / SSP / VISP.' },
    ],
  },
  {
    id: 'special-steel-ipt',
    route: '/reports/special-steel-ipt',
    title: 'Special Steel, IPT & BF Benchmarking',
    description: 'Special steel orders vs actual, inter-plant transfers and large blast furnace benchmarking.',
    icon: '🔩',
    tabs: [
      { id: 'special-steel-fy', label: 'Special Steel (Order vs Actual, FY)', description: 'Special steel orders vs actual despatch, financial-year view.' },
      { id: 'ipt-fy', label: 'IPT (Plan vs Actual, FY)', description: 'Inter-plant transfer plan vs actual, financial-year view.' },
      { id: 'bf-benchmark', label: 'Large BF Benchmarking', description: 'SAIL vs external large blast furnaces benchmarking.' },
    ],
  },
  {
    id: 'mines',
    route: '/reports/mines',
    title: 'Iron Ore Mines',
    description: 'Mine-level production, despatch and sales, month-wise.',
    icon: '⛏️',
    tabs: [
      { id: 'iron-ore-mines', label: 'Iron Ore Mines (Month-wise)', description: 'Mine-level production, despatch and sales, month-wise.' },
    ],
  },
  {
    id: 'loss-breakdown',
    route: '/reports/loss-breakdown',
    title: 'Loss, Breakdown & Capital Repair',
    description: 'Production loss analysis, breakdown events and capital repair plan vs actual.',
    icon: '🛠️',
    tabs: [
      { id: 'production-loss-analysis', label: 'Production Loss Analysis', description: 'HM/CS/FS shortfall vs ABP explained by capital repair and breakdowns.' },
      { id: 'breakdown-analysis', label: 'Breakdown Analysis', description: 'Cross-plant breakdown events — filter, sort and chart.' },
      { id: 'capital-repair-calendar', label: 'Capital Repair Plan vs Actual', description: 'Gantt-style calendar: which months each unit was scheduled vs actually under repair.' },
    ],
  },
  {
    id: 'highlights-records',
    route: '/reports/highlights-records',
    title: 'Highlights & Records',
    description: 'Production highlights, major production summary, the monthly records matrix and best techno parameters.',
    icon: '🏆',
    tabs: [
      { id: 'highlights', label: 'Production Highlights', description: 'Best-ever and notable production highlights.' },
      { id: 'major-production', label: 'Major Production (Month & Till Month)', description: 'Major items, month and till-month figures.' },
      { id: 'records-matrix', label: 'Monthly Records Matrix', description: 'Month-wise best-ever record matrix across items.' },
      { id: 'techno-records', label: 'Best Techno Matrix', description: 'Month-wise best-ever Major 12 and BF-wise Iron Making techno parameters (lower is best for consumption rates).' },
    ],
  },
  {
    id: 'external',
    route: '/reports/external',
    title: 'External Reports',
    description: 'Reports formatted for submission outside SAIL MIS.',
    icon: '📮',
    tabs: [
      { id: 'new-facilities', label: 'New Facilities (Annexure-III)', description: 'New facilities annexure.' },
      { id: 'do-letter', label: 'Monthly DO Letter', description: 'Monthly DO letter with Annexure remarks.' },
      { id: 'jpc-report', label: 'JPC Monthly Report', description: 'JPC monthly report export.' },
      { id: 'one-page-report', label: '1-Page Report', description: 'Single-page summary report.' },
      { id: 'plant-performance-items', label: 'Plant Wise Performance (Excel)', description: 'Plant Wise Performance of Main Items, tonnage to 3 decimals, Excel download.' },
      { id: 'pmix-fy', label: 'Pmix Report (Year-wise)', description: 'Product-mix report, financial-year view.' },
      { id: 'sefi', label: 'SEFI Report', description: 'SEFI report.' },
      { id: 'steel-bulletin', label: 'Inputs for Steel Bulletin', description: 'Inputs feeding the Steel Bulletin.' },
    ],
  },
];

export function groupById(id) {
  return REPORT_GROUPS.find((g) => g.id === id);
}

export function tabHref(tabId) {
  const group = REPORT_GROUPS.find((g) => g.tabs.some((t) => t.id === tabId));
  return group ? `${group.route}?tab=${tabId}` : '/reports';
}
