'use client';

import RequireEditor from '@/components/RequireEditor';

import React, { useMemo, useState } from 'react';
import Link from 'next/link';
import GlobalNavbar from '@/components/GlobalNavbar';
import { ENTRY_GROUPS } from '@/components/entry/entryGroups';
import ui from '@/styles/ui.module.css';
import h from './hub.module.css';

// Every data-entry destination in GlobalNavbar's "Data Entry" menu, grouped.
// The Manual Entry cards come from components/entry/entryGroups.js (one card
// per tabbed page, listing its tabs); the rest follow each page's own
// heading/subtitle. Keep in sync with the navbar when a page is added or
// removed.
const GROUPS = [
  {
    title: 'Manual Entry',
    sections: ENTRY_GROUPS.map((g) => ({
      title: g.title,
      icon: g.icon,
      link: g.route,
      description: `${g.tabs.length} tabs: ${g.tabs.map((t) => t.label).join(' · ')}`,
    })),
  },
  {
    title: 'Uploads & Extraction',
    sections: [
      { title: 'Production, Stock & Special Steel Upload', icon: '📤', link: '/upload',
        description: 'Upload plant Excel/PDF files, review the extracted production, techno and special steel data, then insert it. Also ABP plan upload.' },
      { title: 'Techno Upload', icon: '🔧', link: '/data-entry/techno',
        description: 'Upload each plant\'s techno files (Technopara, Flash PDF, OISCO, MCR, Morning Report…), preview and save; browse saved techno data.' },
      { title: 'Coal / CO2 / Power Uploads', icon: '🛢️', link: '/data-entry/uploads',
        description: 'All-5-plants-at-once report uploads: coal consumption, CO2/Water/PM EPI, and power.' },
      { title: 'Cost Trend Excel Extractor', icon: '📊', link: '/data-entry/cost-trend-extract',
        description: 'Upload an elementwise cost workbook to pull Variable and Fixed cost (Rs/T) for the Month or Till Month column.' },
      { title: 'Indian Steel Sector Performance (PIB)', icon: '🏗️', link: '/data-entry/steel-sector-performance',
        description: 'Paste the URL of the monthly PIB (Ministry of Steel) press release, or upload its PDF, to extract the sector figures.' },
    ],
  },
  {
    title: 'Stock & Operations',
    sections: [
      { title: 'Opening Stock', icon: '📦', link: '/data-entry/opening-stock',
        description: 'Manage opening stock values for all items and plants at the beginning of each month.' },
      { title: 'Inter-Plant Transfer (IPT)', icon: '🚚', link: '/data-entry/ipt',
        description: 'Track inter-plant transfers and movements between facilities.' },
      { title: 'Conversion', icon: '🔄', link: '/data-entry/conversion',
        description: 'Enter monthly conversion data for SAIL consolidated.' },
      { title: 'Capital Repair', icon: '🛠️', link: '/data-entry/capital-repair',
        description: 'Update unit, planned days and actual dates as Capital Repair jobs execute — feeds the Production Loss Analysis report.' },
      { title: 'Breakdown Entry', icon: '⚠️', link: '/data-entry/breakdown',
        description: 'Log unplanned equipment downtime, plant-wise and unit-wise. Every breakdown counts fully toward the Production Loss Analysis report.' },
      { title: 'Rakes Detention (Pages 1026-1040)', icon: '🚃', link: '/data-entry/rake-detention',
        description: 'Plant-wise rake detention from the SAIL Rail Movement Cell\'s Average Plant Detention Report — every figure entered directly.' },
    ],
  },
  {
    title: 'Annual Targets & Cost',
    sections: [
      { title: 'Techno-Economic (TE) Targets', icon: '🎯', link: '/data-entry/targets',
        description: 'Set annual techno-economic parameter targets by plant, shown as the Target column on techno reports.' },
      { title: 'TE Targets (Pages 30-38)', icon: '🎯', link: '/data-entry/annual-target',
        description: 'Entered once a year per FY; shown as the Target / Norm column on the month-wise techno pages.' },
      { title: 'Special Steel ABP (Page 24)', icon: '🎯', link: '/data-entry/special-steel-abp',
        description: 'Annual Business Plan target per plant for all 12 months of the FY — feeds the ABP columns on the SAIL Special Steel summary.' },
      { title: 'Cost Trend (Pages 3.61-3.63)', icon: '💰', link: '/data-entry/cost-trend',
        description: 'Variable / Fixed cost of Hot Metal, Crude Steel and Saleable Steel per plant, including SAIL 5 ISPs — history, month and till-month.' },
      { title: 'Annual Capacity', icon: '🏭', link: '/data-entry/annual-capacity',
        description: 'Rated annual capacity (\'000 T/yr) per plant/item, used for the Capacity and CU% columns on Plant Wise Performance.' },
    ],
  },
  {
    title: 'Dashboards',
    sections: [
      { title: 'Techno Summary', icon: '📈', link: '/data-entry/techno-summary',
        description: 'Techno performance summary for a financial year, comparing BF and SMS parameters across the 5 plants.' },
      { title: 'Coal Consumption', icon: '⛏️', link: '/data-entry/coal-consumption',
        description: 'Indigenous and imported coal consumption across all 5 plants, plus SAIL receipt / consumption / stock.' },
      { title: 'CO2 / Water / PM', icon: '🌫️', link: '/data-entry/co2-water-pm',
        description: 'Specific CO2 emission, water consumption and PM emission across all 5 plants.' },
    ],
  },
];

const TOTAL = GROUPS.reduce((n, g) => n + g.sections.length, 0);

function DataEntryPageInner() {
  const [query, setQuery] = useState('');

  const visible = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return GROUPS;
    return GROUPS
      .map((g) => ({
        ...g,
        sections: g.sections.filter((s) =>
          `${s.title} ${s.description}`.toLowerCase().includes(q)),
      }))
      .filter((g) => g.sections.length > 0);
  }, [query]);
  const shown = visible.reduce((n, g) => n + g.sections.length, 0);

  return (
    <>
      <GlobalNavbar />

      <main className={ui.page} style={{ '--page-max': '1400px' }}>
        <div className={ui.pageHeader}>
          <h1 className={ui.pageTitle}>Data Entry Hub</h1>
          <p className={ui.pageLead}>
            All data entry tools — production, stock, uploads, techno-economic parameters, special steel, report
            commentary and reference data.
          </p>
        </div>

        <div className={h.search}>
          <label htmlFor="hub-search" className={ui.srOnly}>Find a data entry page</label>
          <input
            id="hub-search"
            type="search"
            className="form-control"
            placeholder={`Filter ${TOTAL} pages — e.g. "coal", "targets", "special steel"`}
            value={query}
            onChange={(e) => setQuery(e.target.value)}
          />
          <span className={ui.meta} style={{ margin: 0 }} aria-live="polite">
            {query ? `${shown} of ${TOTAL} pages` : `${TOTAL} pages`}
          </span>
        </div>

        {visible.map((group) => (
          <section key={group.title} className={h.group} aria-labelledby={`hub-${group.title}`}>
            <h2 id={`hub-${group.title}`} className={h.groupTitle}>{group.title}</h2>
            <ul className={h.grid}>
              {group.sections.map((section) => (
                <li key={section.link}>
                  <Link href={section.link} className={h.card}>
                    <span className={h.icon} aria-hidden="true">{section.icon}</span>
                    <span className={h.body}>
                      <span className={h.title}>{section.title}</span>
                      <span className={h.desc}>{section.description}</span>
                    </span>
                  </Link>
                </li>
              ))}
            </ul>
          </section>
        ))}

        {shown === 0 && (
          <p className={ui.meta}>No page matches &quot;{query}&quot;.</p>
        )}

        <p className={h.tip}>
          <strong>Tip:</strong> Data entered in these sections is cached automatically for faster access. Use the Report
          Engine to view and export compiled reports across all data sources.
        </p>
      </main>
    </>
  );
}

export default function DataEntryPage() {
  return (
    <RequireEditor>
      <DataEntryPageInner />
    </RequireEditor>
  );
}
