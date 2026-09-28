'use client';

import RequireEditor from '@/components/RequireEditor';

import React from 'react';
import Link from 'next/link';
import GlobalNavbar from '@/components/GlobalNavbar';
import ui from '@/styles/ui.module.css';
import h from './hub.module.css';

const GROUPS = [
  {
    title: 'Production & Stock',
    sections: [
      {
        title: 'Production Data Entry',
        description: 'Enter actual production values for each item. Plan values come from the uploaded ABP and can also be edited.',
        icon: '📊',
        link: '/data-entry/production',
      },
      {
        title: 'Production Data Entry — Month Range',
        description: 'Enter or correct one plant/unit\'s actual production across several months at once, straight into production_table.',
        icon: '📈',
        link: '/data-entry/production-range',
      },
      {
        title: 'Opening Stock',
        description: 'Manage opening stock values for all items and plants at the beginning of each month.',
        icon: '📦',
        link: '/data-entry/opening-stock',
      },
      {
        title: 'Inter-Plant Transfer (IPT)',
        description: 'Track inter-plant transfers and movements between facilities.',
        icon: '🚚',
        link: '/data-entry/ipt',
      },
      {
        title: 'Conversion',
        description: 'Enter monthly conversion data for SAIL consolidated.',
        icon: '🔄',
        link: '/data-entry/conversion',
      },
    ],
  },
  {
    title: 'Techno-Economic',
    sections: [
      {
        title: 'Techno-Economic (TE) Targets',
        description: 'Set annual techno-economic parameter targets by plant, shown as the Target column on techno reports.',
        icon: '🎯',
        link: '/data-entry/targets',
      },
      {
        title: 'Techno Manual Entry',
        description: 'Enter techno-economic parameters manually for each plant.',
        icon: '⚙️',
        link: '/data-entry/techno-manual',
      },
      {
        title: 'SAIL Large BFs — Performance Snapshot',
        description: 'Month and Till Month figures for BSP BF-8, RSP BF-5 and ISP BF-5 in report order. Saves into the same techno data as Techno Manual Entry.',
        icon: '🏗️',
        link: '/data-entry/bf-large-snapshot',
      },
      {
        title: 'Techno Data Correction',
        description: 'Find one techno-economic parameter across a plant + month range and correct it inline.',
        icon: '🩹',
        link: '/data-entry/techno-correction',
      },
    ],
  },
  {
    title: 'Reference & Records',
    sections: [
      {
        title: 'Iron Ore Mines Production & Despatch',
        description: 'Enter mine-level fresh production (Lump/Fines) and despatch (all materials, incl. legacy Dump Fines/Pellets/Tailings) by Rail/Road to Captive, Sales, or Pellet Conversion.',
        icon: '⛏️',
        link: '/data-entry/mines-production-despatch',
      },
      {
        title: 'Special Steel Grade Clubbing',
        description: 'Combine near-duplicate quality grades into one report row for BSP/DSP/RSP/BSL.',
        icon: '🔗',
        link: '/data-entry/special-steel-grade-clubs',
      },
      {
        title: 'Ready Reckoner',
        description: 'Edit each plant\'s Unit-wise Capacity and Product Mix reference tables shown at the end of the report.',
        icon: '📋',
        link: '/data-entry/ready-reckoner',
      },
      {
        title: '5 ISPs Major Units Daily Records',
        description: 'Log a new best-ever daily production figure (with its date) for a major unit, shown in Annexure-3 of the report.',
        icon: '🏆',
        link: '/data-entry/major-unit-daily',
      },
    ],
  },
];

function DataEntryPageInner() {
  return (
    <>
      <GlobalNavbar />

      <main className={ui.page} style={{ maxWidth: 1400 }}>
        <div className={ui.pageHeader} style={{ marginBottom: 28 }}>
          <h1 className={ui.pageTitle}>Data Entry Hub</h1>
          <p className={ui.pageLead}>
            Access all data entry tools for production, inventory, transfers, and techno-economic parameters.
          </p>
        </div>

        {GROUPS.map((group) => (
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
