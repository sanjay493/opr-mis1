// The navbar's menu (GlobalNavbar) and the extra account / admin links it
// shows by role. Plain data module so the sitemap (app/sitemap) and the Data
// Entry hub (app/data-entry) draw the same tree; add a page here and all
// three pick it up. `desc` is the hub card's text and the sitemap tooltip.

export const NAV_ITEMS = [
  {
    label: 'Data Entry',
    icon: '📋',
    groups: [
      {
        groupLabel: 'Manual Entry',
        children: [
          // Each is a tabbed page grouping several entry forms — see
          // components/entry/entryGroups.js for the tabs of each (the hub
          // and sitemap list those tabs, so no `desc` here).
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
          { label: 'Production, Stock & Special Steel Upload', link: '/upload', icon: '📤',
            desc: 'Upload plant Excel/PDF files, review the extracted production, techno and special steel data, then insert it. Also ABP plan upload.' },
          { label: 'Techno Upload', link: '/data-entry/techno', icon: '🔧',
            desc: 'Upload each plant\'s techno files (Technopara, Flash PDF, OISCO, MCR, Morning Report…), preview and save; browse saved techno data.' },
          { label: 'Coal, CO2, Power, MoU & Rail Uploads', link: '/data-entry/uploads', icon: '🛢️',
            desc: 'All-5-plants-at-once report uploads: coal consumption, CO2/Water/PM EPI, power, MoU plan, and the Rail Logistics rake files.' },
          { label: 'Commentary & Market Upload', link: '/data-entry/commentary-market-upload', icon: '📝',
            desc: 'Upload the monthly CMO / BigMint deck PDF: Steel Sales month + YTD bullets (page 3.05) and the Key Prices chart (page 2.41).' },
          { label: 'Cost Trend Excel Extractor', link: '/data-entry/cost-trend-extract', icon: '📊',
            desc: 'Upload an elementwise cost workbook to pull Variable and Fixed cost (Rs/T) for the Month or Till Month column.' },
          { label: 'Indian Steel Sector Performance (PIB)', link: '/data-entry/steel-sector-performance', icon: '🏗️',
            desc: 'Paste the URL of the monthly PIB (Ministry of Steel) press release, or upload its PDF, to extract the sector figures.' },
        ]
      },
      {
        groupLabel: 'Stock & Transfers',
        children: [
          { label: 'Opening Stock', link: '/data-entry/opening-stock', icon: '📦',
            desc: 'Manage opening stock values for all items and plants at the beginning of each month.' },
          { label: 'Inter-Plant Transfer (IPT)', link: '/data-entry/ipt', icon: '↔️',
            desc: 'Track inter-plant transfers and movements between facilities.' },
          { label: 'Conversion Data', link: '/data-entry/conversion', icon: '⚡',
            desc: 'Enter monthly conversion data for SAIL consolidated.' },
        ]
      },
      {
        groupLabel: 'Repair & Breakdown',
        children: [
          { label: 'Capital Repair', link: '/data-entry/capital-repair', icon: '🛠️',
            desc: 'Update unit, planned days and actual dates as Capital Repair jobs execute — feeds the Production Loss Analysis report.' },
          { label: 'Breakdown Entry', link: '/data-entry/breakdown', icon: '⚠️',
            desc: 'Log unplanned equipment downtime, plant-wise and unit-wise. Every breakdown counts fully toward the Production Loss Analysis report.' },
        ]
      },
      {
        groupLabel: 'Rail Logistics',
        children: [
          { label: 'Monthly Rail Loading Entry (Page 40.05)', link: '/data-entry/reference?tab=rail-loading', icon: '🚆',
            desc: 'Rakes loaded in the month by commodity: iron ore by mines group, flux by mine, ports, coal, plant despatch and export.' },
          { label: 'Rake Despatch PDF & Iron Ore Rakes CSV Upload', link: '/data-entry/uploads#rail-logistics', icon: '📤',
            desc: 'Upload the Rail Movement Cell\'s Despatch Summary Report (PDF) and the mines\' rake record (u_rakes_rmg.csv).' },
          { label: 'Rakes Detention (Pages 1026-1040)', link: '/data-entry/rake-detention', icon: '🚃',
            desc: 'Plant-wise rake detention from the SAIL Rail Movement Cell\'s Average Plant Detention Report — every figure entered directly.' },
        ]
      },
      {
        groupLabel: 'Annual Targets & Cost',
        children: [
          { label: 'TE Annual Targets (Techno Reports)', link: '/data-entry/targets', icon: '🎯',
            desc: 'Set annual techno-economic parameter targets by plant, shown as the Target column on techno reports.' },
          { label: 'TE Targets (Pages 30-38)', link: '/data-entry/annual-target', icon: '🎯',
            desc: 'Entered once a year per FY; shown as the Target / Norm column on the month-wise techno pages.' },
          { label: 'Special Steel ABP (Page 24)', link: '/data-entry/special-steel-abp', icon: '🎯',
            desc: 'Annual Business Plan target per plant for all 12 months of the FY — feeds the ABP columns on the SAIL Special Steel summary.' },
          { label: 'Annual Capacity', link: '/data-entry/annual-capacity', icon: '🏭',
            desc: 'Rated annual capacity (\'000 T/yr) per plant/item, used for the Capacity and CU% columns on Plant Wise Performance.' },
          { label: 'Cost Trend (Pages 3.61-3.63)', link: '/data-entry/cost-trend', icon: '💰',
            desc: 'Variable / Fixed cost of Hot Metal, Crude Steel and Saleable Steel per plant, including SAIL 5 ISPs — history, month and till-month.' },
        ]
      },
      {
        groupLabel: 'Dashboards',
        children: [
          { label: 'Techno Summary', link: '/data-entry/techno-summary', icon: '📈',
            desc: 'Techno performance summary for a financial year, comparing BF and SMS parameters across the 5 plants.' },
          { label: 'Coal Consumption', link: '/data-entry/coal-consumption', icon: '⛏️',
            desc: 'Indigenous and imported coal consumption across all 5 plants, plus SAIL receipt / consumption / stock.' },
          { label: 'CO2 / Water / PM', link: '/data-entry/co2-water-pm', icon: '🌫️',
            desc: 'Specific CO2 emission, water consumption and PM emission across all 5 plants.' },
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
      { label: 'Rail Logistics', link: '/reports/logistics', icon: '🚆' },
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
