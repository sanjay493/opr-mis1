'use client';

import React, { useState } from 'react';
import Link from 'next/link';

export default function GlobalNavbar() {
  const [openDropdown, setOpenDropdown] = useState(null);

  const navItems = [
    {
      label: 'Data Entry',
      icon: '📋',
      submenu: [
        { label: 'Production Entry', link: '/data-entry', icon: '📊' },
        { label: 'Production, Stock & Special Steel Upload', link: '/upload', icon: '📤' },
        { label: 'Opening Stock', link: '/data-entry/opening-stock', icon: '📦' },
        { label: 'Conversion Data', link: '/data-entry/conversion', icon: '⚡' },
        { label: 'Techno Upload', link: '/data-entry/techno', icon: '🔧' },
        { label: 'Techno Manual Entry', link: '/data-entry/techno-manual', icon: '✏️' },
        { label: 'IPT Status', link: '/data-entry/ipt', icon: '↔️' },
        { label: 'TE Targets', link: '/data-entry/targets', icon: '🎯' }
      ]
    },
    {
      label: 'Reports',
      icon: '📄',
      submenu: [
        { label: 'OMI Generate', link: '/report', icon: '📈' },
        { label: 'Month-wise Production', link: '/reports/production-fy', icon: '📅' },
        { label: 'Production Records', link: '/records', icon: '📊' },
        { label: 'Plant-wise Techno', link: '/reports/techno-monthly', icon: '⚙️' },
        { label: 'Techno Dashboard', link: '/reports/techno-dashboard', icon: '🔬' },
        { label: 'Techno Verification', link: '/reports/techno-verification', icon: '✅' }
      ]
    },
    {
      label: 'To-Do',
      icon: '✅',
      submenu: [
        { label: 'Upcoming Jobs', link: '/todo', icon: '✅' },
        { label: 'Daily Work Log', link: '/worklog', icon: '📝' }
      ]
    }
  ];

  return (
    <nav style={{
      position: 'sticky',
      top: 0,
      zIndex: 100,
      borderBottom: '1px solid #dadce0',
      backgroundColor: '#ffffff',
      padding: '0'
    }}>
      <div style={{ maxWidth: '1600px', margin: '0 auto', padding: '0 32px' }}>
        <div style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          height: '72px'
        }}>
          {/* Logo & Brand */}
          <Link href="/" style={{ textDecoration: 'none', display: 'flex', alignItems: 'center', gap: '12px' }}>
            <div style={{
              width: '40px',
              height: '40px',
              borderRadius: '8px',
              backgroundColor: '#1a73e8',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              fontWeight: '900',
              fontSize: '22px',
              cursor: 'pointer'
            }}>
              📊
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '2px' }}>
              <span style={{ fontSize: '15pt', fontWeight: '900', letterSpacing: '-0.01em', color: '#202124' }}>
                SAIL MIS
              </span>
              <span style={{ fontSize: '9pt', color: '#5f6368', fontWeight: '600' }}>Portal</span>
            </div>
          </Link>

          {/* Desktop Navigation Menu */}
          <div style={{
            display: 'flex',
            gap: '32px',
            alignItems: 'center',
            marginLeft: '48px'
          }}>
            {navItems.map((item, idx) => (
              <div key={idx} style={{ position: 'relative', paddingBottom: item.submenu ? '8px' : '0' }}
                onMouseEnter={() => item.submenu && setOpenDropdown(idx)}
                onMouseLeave={() => item.submenu && setOpenDropdown(null)}
              >
                {item.submenu ? (
                  <div
                    style={{
                      cursor: 'pointer',
                      padding: '8px 12px',
                      borderRadius: '6px',
                      transition: 'all 0.2s ease',
                      display: 'flex',
                      alignItems: 'center',
                      gap: '6px',
                      color: openDropdown === idx ? '#1a73e8' : '#202124',
                      backgroundColor: openDropdown === idx ? 'rgba(26, 115, 232, 0.08)' : 'transparent'
                    }}
                  >
                    <span>{item.icon}</span>
                    <span style={{ fontSize: '12pt', fontWeight: '600' }}>{item.label}</span>
                    <svg
                      width="14"
                      height="14"
                      viewBox="0 0 24 24"
                      fill="none"
                      stroke="currentColor"
                      strokeWidth="2.5"
                      style={{
                        transform: openDropdown === idx ? 'rotate(180deg)' : 'rotate(0deg)',
                        transition: 'transform 0.2s ease'
                      }}
                    >
                      <polyline points="6 9 12 15 18 9"></polyline>
                    </svg>
                  </div>
                ) : (
                  <Link href={item.link} style={{ textDecoration: 'none' }}>
                    <div style={{
                      cursor: 'pointer',
                      padding: '8px 12px',
                      borderRadius: '6px',
                      transition: 'all 0.2s ease',
                      display: 'flex',
                      alignItems: 'center',
                      gap: '6px',
                      color: '#202124',
                      fontSize: '12pt',
                      fontWeight: '600'
                    }}
                    onMouseEnter={(e) => {
                      e.currentTarget.style.backgroundColor = 'rgba(26, 115, 232, 0.08)';
                      e.currentTarget.style.color = '#1a73e8';
                    }}
                    onMouseLeave={(e) => {
                      e.currentTarget.style.backgroundColor = 'transparent';
                      e.currentTarget.style.color = '#202124';
                    }}
                    >
                      <span>{item.icon}</span>
                      {item.label}
                    </div>
                  </Link>
                )}

                {/* Dropdown Menu */}
                {item.submenu && openDropdown === idx && (
                  <div style={{
                    position: 'absolute',
                    top: '100%',
                    left: '0',
                    backgroundColor: '#f8f9fa',
                    border: '1px solid #dadce0',
                    borderRadius: '8px',
                    overflow: 'hidden',
                    minWidth: '250px',
                    boxShadow: '0 1px 3px rgba(60,64,67,.3), 0 4px 8px 3px rgba(60,64,67,.15)'
                  }}
                  >
                    {item.submenu.map((subitem, subidx) => (
                      <Link key={subidx} href={subitem.link} style={{ textDecoration: 'none' }}>
                        <div style={{
                          padding: '13px 18px',
                          borderBottom: subidx < item.submenu.length - 1 ? '1px solid #e8eaed' : 'none',
                          color: '#202124',
                          cursor: 'pointer',
                          display: 'flex',
                          alignItems: 'center',
                          gap: '10px',
                          fontSize: '12pt',
                          transition: 'all 0.2s ease'
                        }}
                        onMouseEnter={(e) => {
                          e.currentTarget.style.backgroundColor = 'rgba(26, 115, 232, 0.1)';
                          e.currentTarget.style.color = '#1a73e8';
                          e.currentTarget.style.paddingLeft = '20px';
                        }}
                        onMouseLeave={(e) => {
                          e.currentTarget.style.backgroundColor = 'transparent';
                          e.currentTarget.style.color = '#202124';
                          e.currentTarget.style.paddingLeft = '16px';
                        }}
                        >
                          <span style={{ fontSize: '14px' }}>{subitem.icon}</span>
                          {subitem.label}
                        </div>
                      </Link>
                    ))}
                  </div>
                )}
              </div>
            ))}
          </div>

          {/* Status badge */}
          <div style={{
            marginLeft: 'auto',
            padding: '6px 14px',
            backgroundColor: '#f8f9fa',
            border: '1px solid #dadce0',
            borderRadius: '20px',
            fontSize: '10.5pt',
            color: '#188038',
            fontWeight: '600',
            display: 'flex',
            alignItems: 'center',
            gap: '6px'
          }}>
            <div style={{
              width: '6px',
              height: '6px',
              backgroundColor: '#188038',
              borderRadius: '50%',
              animation: 'pulse 2s cubic-bezier(0.4, 0, 0.6, 1) infinite'
            }} />
            Active
          </div>
        </div>
      </div>

      <style>{`
        @keyframes pulse {
          0%, 100% {
            opacity: 1;
          }
          50% {
            opacity: 0.5;
          }
        }
      `}</style>
    </nav>
  );
}
