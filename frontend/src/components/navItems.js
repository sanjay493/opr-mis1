// The navbar's menu (GlobalNavbar) and the extra account / admin links it
// shows by role. Plain data module so the sitemap (app/sitemap) draws the
// same tree; add a page here and both pick it up.

export const NAV_ITEMS = [
  {
    label: 'Data Entry',
    icon: '📋',
    groups: [
      {
        groupLabel: 'Manual Entry',
        children: [
          // Each is a tabbed page grouping several entry forms — see
          // components/entry/entryGroups.js for the tabs of each.
          { label: 'Production & Techno Entry', link: '/data-entry/production-techno', icon: '📊' },
          { label: 'Mines Entry', link: '/data-entry/mines', icon: '⛏️' },
          { label: 'Special Steel Entry', link: '/data-entry/special-steel-entry', icon: '🔩' },
          { label: 'Report Commentary & Market', link: '/data-entry/commentary', icon: '📝' },
          { label: 'Reference & Records', link: '/data-entry/reference', icon: '📋' },
        ]
      },
      {
        groupLabel: 'Uploads & Extraction',
        children: [
          { label: 'Production, Stock & Special Steel Upload', link: '/upload', icon: '📤' },
          { label: 'Techno Upload', link: '/data-entry/techno', icon: '🔧' },
          { label: 'Coal / CO2 / Power Uploads', link: '/data-entry/uploads', icon: '🛢️' },
          { label: 'Commentary & Market Upload', link: '/data-entry/commentary-market-upload', icon: '📝' },
        ]
      },
      {
        groupLabel: 'Stock & Transfers',
        children: [
          { label: 'Opening Stock', link: '/data-entry/opening-stock', icon: '📦' },
          { label: 'IPT Status', link: '/data-entry/ipt', icon: '↔️' },
          { label: 'Conversion Data', link: '/data-entry/conversion', icon: '⚡' },
          { label: 'Capital Repair', link: '/data-entry/capital-repair', icon: '🛠️' },
          { label: 'Breakdown Entry', link: '/data-entry/breakdown', icon: '⚠️' },
          { label: 'Rakes Detention (Pages 1026-1040)', link: '/data-entry/rake-detention', icon: '🚃' },
        ]
      },
      {
        groupLabel: 'Annual Targets',
        children: [
          { label: 'TE Targets', link: '/data-entry/targets', icon: '🎯' },
          { label: 'TE Targets (Pages 30-38)', link: '/data-entry/annual-target', icon: '🎯' },
          { label: 'Special Steel ABP (Page 24)', link: '/data-entry/special-steel-abp', icon: '🎯' },
          { label: 'Cost Trend (Pages 3.61-3.63)', link: '/data-entry/cost-trend', icon: '💰' },
          { label: 'Cost Trend Excel Extractor', link: '/data-entry/cost-trend-extract', icon: '📊' },
          { label: 'Annual Capacity', link: '/data-entry/annual-capacity', icon: '🏭' },
        ]
      },
      {
        groupLabel: 'Dashboards',
        children: [
          { label: 'Techno Summary', link: '/data-entry/techno-summary', icon: '📈' },
          { label: 'Coal Consumption', link: '/data-entry/coal-consumption', icon: '⛏️' },
          { label: 'CO2 / Water / PM', link: '/data-entry/co2-water-pm', icon: '🌫️' },
        ]
      },
      {
        groupLabel: 'External Sources',
        children: [
          { label: 'Indian Steel Sector Performance (PIB)', link: '/data-entry/steel-sector-performance', icon: '🏗️' },
        ]
      },
    ]
  },
  {
    label: 'Reports',
    icon: '📄',
    submenu: [
      { label: 'OMI Generate', link: '/report', icon: '📈' },
      { label: 'Production Reports', link: '/reports/production-analysis', icon: '📊' },
      { label: 'RMT Production Plan', link: '/reports/external?tab=rmt-plan', icon: '🗓️' },
      { label: 'Special Steel, IPT & BF Benchmarking', link: '/reports/special-steel-ipt', icon: '🔩' },
      { label: 'Iron Ore Mines', link: '/reports/mines', icon: '⛏️' },
      { label: 'Cost of Production', link: '/reports/cost-production', icon: '💰' },
      { label: 'Loss, Breakdown & Capital Repair', link: '/reports/loss-breakdown', icon: '🛠️' },
      { label: 'Techno Reports', link: '/reports/techno', icon: '⚙️' },
      { label: 'Excel Report', link: '/reports/excel', icon: '📗' },
      { label: 'ABP', link: '/reports/abp', icon: '🎯' },
    ]
  },
  {
    label: 'Highlights & Records',
    icon: '🏆',
    submenu: [
      { label: 'Highlights & Records', link: '/reports/highlights-records', icon: '🏆' },
      { label: 'Production Records', link: '/records', icon: '📊' },
    ]
  },
  {
    label: 'External Reports',
    icon: '📮',
    link: '/reports/external'
  },
  {
    label: 'Sitemap',
    icon: '🗺️',
    link: '/sitemap'
  },
  {
    label: 'To-Do',
    icon: '✅',
    submenu: [
      { label: 'Upcoming Jobs', link: '/todo', icon: '✅' },
      { label: 'Daily Work Log', link: '/worklog', icon: '📝' },
      { label: 'Missing Data Checklist', link: '/todo/missing-data', icon: '📋' }
    ]
  }
];

// The account dropdown's links (GlobalNavbar; the admin ones for admins only).
export const ACCOUNT_LINKS = [
  { label: 'My Profile', link: '/profile', icon: '👤' },
];
export const ADMIN_LINKS = [
  { label: 'Manage Users', link: '/admin/users', icon: '🛠️' },
  { label: 'Allowed Emails', link: '/admin/allowed-emails', icon: '✉️' },
  { label: 'Activity Log', link: '/admin/activity-log', icon: '📜' },
  { label: 'Backup & Restore', link: '/admin/backup', icon: '💾' },
  { label: 'Site Visits', link: '/admin/site-visits', icon: '🌐' },
];
