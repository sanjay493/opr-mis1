// Grouped report pages: each group is one route with a tab per report.
// A tab's `id` is the report's old route slug — /reports/<id> still exists
// and redirects to `${group.route}?tab=<id>` (see tabHref), so old links
// and bookmarks keep working. The reports themselves live in
// components/reports/<id>/View.js (loaded by ReportTabs).
//
// Tabs that share a `menu` name are shown in the tab strip as one dropdown
// (at the position of the first of them) instead of one tab each.
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
      { id: 'production-fy', label: 'Production', description: 'All plants, all items — actual/plan figures month-wise for a financial year, or year-wise for the last 12 financial years.' },
      { id: 'production-trend', label: 'HM/CS/FS/Saleable Steel Trend', description: 'Year-wise trend of Hot Metal, Crude Steel, Finished Steel and Saleable Steel.' },
      { id: 'production-query', label: 'Unit-wise Production Query', description: 'Ad-hoc unit-wise production lookup across months.' },
      { id: 'production-items', label: 'Production Items (Month & Unit-wise)', description: 'Oven Pushing / Sinter / Hot Metal / Crude Steel / Pig Iron / Finished Steel / Saleable Steel.' },
      { id: 'op-comparison', label: 'OP vs APP vs Actual', description: 'Production against the monthly Operating Plan and the Annual Plan, month and till month, plant-wise and SAIL.' },
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
      { id: 'mines-group-wise', label: 'Iron Ore Mines (Mine & Group-wise)', description: 'Mine-wise and group-wise Plan vs Actual, month-wise, for Production, Despatch (by Captive/Sales/Pellet Conversion) and Reported Production; Excel download.' },
      { id: 'mines-performance', label: 'Mines Production Performance', description: 'Mine, group and SAIL production, despatch, reported production and booked quantity against plan and last year (pages 5-6 layout); Excel and PDF download.' },
    ],
  },
  {
    id: 'cost-production',
    route: '/reports/cost-production',
    title: 'Cost of Production',
    description: 'BF Coke, Sinter, Hot Metal, Crude Steel and Saleable Steel cost of production, all plants, monthly or yearly.',
    icon: '💰',
    tabs: [
      { id: 'production-cost', label: 'Cost of Production (Monthly / Yearly)', description: 'Rs/T Total, Variable and Fixed cost of BF Coke, Sinter, Hot Metal, Crude Steel and Saleable Steel for every plant; Excel and PDF download.' },
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
      { id: 'bd-cr-log', label: 'Breakdown & CR Log', description: 'Per plant, unit by unit: every breakdown and actual capital repair, month by month in date order.' },
    ],
  },
  {
    id: 'highlights-records',
    route: '/reports/highlights-records',
    title: 'Highlights & Records',
    description: 'Production highlights, major production summary, the monthly records matrix, best techno parameters and unique activities.',
    icon: '🏆',
    tabs: [
      { id: 'highlights', label: 'Production Highlights', description: 'Best-ever and notable production highlights.' },
      { id: 'major-production', label: 'Major Production (Month & Till Month)', description: 'Major items, month and till-month figures.' },
      { id: 'records-matrix', label: 'Monthly Records Matrix', description: 'Month-wise best-ever record matrix across items.' },
      { id: 'techno-records', label: 'Best Techno Matrix', description: 'Month-wise best-ever Major 12 and BF-wise Iron Making techno parameters (lower is best for consumption rates).' },
      { id: 'unique-activities', label: 'Unique Activities', description: 'New unit start-ups, revivals after prolonged capital repair and other one-off milestones, searchable by text and tag.' },
    ],
  },
  {
    id: 'excel',
    route: '/reports/excel',
    title: 'Excel Report',
    description: 'Reports with Excel downloads: plant-wise performance of main items (APP & MoU) and the product-mix report.',
    icon: '📗',
    tabs: [
      { id: 'plant-performance-items', label: 'Plant Wise Performance (APP & MoU)', description: 'Plant Wise Performance of Main Items against APP and MoU; Excel and PDF download.' },
      { id: 'pmix-fy', label: 'Pmix Report (Year-wise)', description: 'Product-mix report, financial-year view.' },
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
      { id: 'steel-bulletin', menu: 'Routine Reports', label: 'Inputs for Steel Bulletin', description: 'Inputs feeding the Steel Bulletin.' },
      { id: 'cmd-monthly-report', menu: 'Routine Reports', label: 'CMD Monthly Activity Report', description: 'SAIL: Monthly Activity Report for the CMD Office (.docx) for any month, with editable significant events and areas of concern.' },
      { id: 'one-page-report', menu: 'Routine Reports', label: '1-Page Report', description: 'Single-page summary report.' },
      { id: 'do-letter', menu: 'Routine Reports', label: 'Monthly DO Letter', description: 'Monthly DO letter with Annexure remarks.' },
      { id: 'jpc-report', menu: 'Routine Reports', label: 'JPC Monthly Report', description: 'JPC monthly report export.' },
      { id: 'rmt-plan', menu: 'Routine Reports', label: 'RMT Production Plan', description: 'The RMT meeting monthly production plan: HM / Crude / Saleable Steel APP and OP against last month and last year, Oven Pushing, Sinter, Pig Iron, IPT requirement / availability and stock; PDF and Excel download.' },
      { id: 'board-note', label: 'Quarterly Board Note', description: 'Quarterly Board Note (production performance) for any FY and quarter, with editable narrative.' },
      { id: 'secretary-review', label: 'Secretary Review (PPTX)', description: 'Monthly Secretary Review operations deck (.pptx) with editable narrative.' },
      { id: 'sefi', label: 'SEFI Report', description: 'SEFI report.' },
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
