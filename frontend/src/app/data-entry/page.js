'use client';

import React from 'react';
import Link from 'next/link';
import GlobalNavbar from '@/components/GlobalNavbar';

export default function DataEntryPage() {
  const sections = [
    {
      title: 'Production Data Entry',
      description: 'Enter actual production values for each item. Plan values come from the uploaded ABP and can also be edited.',
      icon: '📊',
      link: '/data-entry/production',
      color: '#0284c7',
      bgColor: 'rgba(2, 132, 199, 0.1)'
    },
    {
      title: 'Opening Stock',
      description: 'Manage opening stock values for all items and plants at the beginning of each month.',
      icon: '📦',
      link: '/data-entry/opening-stock',
      color: '#10b981',
      bgColor: 'rgba(16, 185, 129, 0.1)'
    },
    {
      title: 'Inter-Plant Transfer (IPT)',
      description: 'Track inter-plant transfers and movements between facilities.',
      icon: '🚚',
      link: '/data-entry/ipt',
      color: '#f59e0b',
      bgColor: 'rgba(245, 158, 11, 0.1)'
    },
    {
      title: 'Conversion',
      description: 'Enter monthly conversion data for SAIL consolidated.',
      icon: '🔄',
      link: '/data-entry/conversion',
      color: '#8b5cf6',
      bgColor: 'rgba(139, 92, 246, 0.1)'
    },
    {
      title: 'Opening Stock Targets',
      description: 'Set annual opening stock targets by plant.',
      icon: '🎯',
      link: '/data-entry/targets',
      color: '#ec4899',
      bgColor: 'rgba(236, 72, 153, 0.1)'
    },
    {
      title: 'Techno Manual Entry',
      description: 'Enter techno-economic parameters manually for each plant.',
      icon: '⚙️',
      link: '/data-entry/techno-manual',
      color: '#6366f1',
      bgColor: 'rgba(99, 102, 241, 0.1)'
    },
  ];

  return (
    <div style={{
      minHeight: '100vh',
      backgroundColor: '#f8fafc',
      display: 'flex',
      flexDirection: 'column'
    }}>
      <GlobalNavbar />

      <main style={{ flex: 1, padding: '40px 32px', overflowY: 'auto' }}>
        <div style={{ maxWidth: '1400px', margin: '0 auto' }}>
          {/* Header */}
          <div style={{ marginBottom: '48px' }}>
            <h1 style={{ fontSize: '28pt', fontWeight: '900', color: '#0f172a', margin: '0 0 12px 0' }}>
              Data Entry Hub
            </h1>
            <p style={{ fontSize: '11pt', color: '#64748b', margin: '0', lineHeight: '1.6' }}>
              Access all data entry tools for production, inventory, transfers, and techno-economic parameters.
            </p>
          </div>

          {/* Grid of sections */}
          <div style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(380px, 1fr))',
            gap: '24px'
          }}>
            {sections.map((section) => (
              <Link key={section.link} href={section.link} style={{ textDecoration: 'none' }}>
                <div style={{
                  height: '100%',
                  backgroundColor: '#fff',
                  border: '1px solid #e2e8f0',
                  borderRadius: '12px',
                  padding: '32px',
                  cursor: 'pointer',
                  transition: 'all 0.3s ease',
                  display: 'flex',
                  flexDirection: 'column',
                  gap: '16px',
                  ':hover': {
                    borderColor: section.color,
                    boxShadow: `0 4px 12px ${section.bgColor}`
                  }
                }}
                onMouseEnter={(e) => {
                  e.currentTarget.style.borderColor = section.color;
                  e.currentTarget.style.boxShadow = `0 4px 12px ${section.bgColor}`;
                  e.currentTarget.style.transform = 'translateY(-4px)';
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.borderColor = '#e2e8f0';
                  e.currentTarget.style.boxShadow = 'none';
                  e.currentTarget.style.transform = 'translateY(0)';
                }}
                >
                  {/* Icon */}
                  <div style={{
                    width: '56px',
                    height: '56px',
                    borderRadius: '12px',
                    backgroundColor: section.bgColor,
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    fontSize: '28px'
                  }}>
                    {section.icon}
                  </div>

                  {/* Title & Description */}
                  <div>
                    <h3 style={{
                      fontSize: '14pt',
                      fontWeight: '800',
                      margin: '0 0 8px 0',
                      color: '#0f172a'
                    }}>
                      {section.title}
                    </h3>
                    <p style={{
                      fontSize: '9.5pt',
                      color: '#64748b',
                      margin: '0',
                      lineHeight: '1.5'
                    }}>
                      {section.description}
                    </p>
                  </div>

                  {/* Footer link */}
                  <div style={{
                    marginTop: 'auto',
                    paddingTop: '16px',
                    borderTop: '1px solid rgba(51, 65, 85, 0.1)',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '6px',
                    fontSize: '10pt',
                    fontWeight: '600',
                    color: section.color
                  }}>
                    Access →
                  </div>
                </div>
              </Link>
            ))}
          </div>

          {/* Info Box */}
          <div style={{
            marginTop: '48px',
            padding: '24px',
            backgroundColor: 'rgba(2, 132, 199, 0.05)',
            border: '1px solid rgba(2, 132, 199, 0.2)',
            borderRadius: '8px'
          }}>
            <h3 style={{ fontSize: '11pt', fontWeight: '700', color: '#0c4a6e', margin: '0 0 8px 0' }}>
              💡 Tip
            </h3>
            <p style={{ fontSize: '9.5pt', color: '#0c4a6e', margin: '0', lineHeight: '1.6' }}>
              Data entered in these sections is cached automatically for faster access. Use the Report Engine to view and export compiled reports across all data sources.
            </p>
          </div>
        </div>
      </main>
    </div>
  );
}
