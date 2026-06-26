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
        { label: 'Opening Stock', link: '/data-entry/opening-stock', icon: '📦' },
        { label: 'Conversion Data', link: '/data-entry/conversion', icon: '⚡' },
        { label: 'Techno Data', link: '/data-entry/techno', icon: '🔧' },
        { label: 'IPT Status', link: '/data-entry/ipt', icon: '↔️' },
        { label: 'TE Targets', link: '/data-entry/targets', icon: '🎯' }
      ]
    },
    {
      label: 'Reports',
      icon: '📄',
      submenu: [
        { label: 'OMI Generate', link: '/report', icon: '📈' },
        { label: 'Production Records', link: '/records', icon: '📊' },
        { label: 'Techno Dashboard', link: '/reports/techno-dashboard', icon: '🔬' }
      ]
    },
    {
      label: 'Data Upload',
      icon: '📤',
      link: '/upload'
    }
  ];

  return (
    <nav style={{
      position: 'sticky',
      top: 0,
      zIndex: 100,
      borderBottom: '1px solid rgba(51, 65, 85, 0.3)',
      backdropFilter: 'blur(10px)',
      backgroundColor: 'rgba(15, 23, 42, 0.95)',
      padding: '0',
      boxShadow: '0 1px 3px rgba(0, 0, 0, 0.1)'
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
              background: 'linear-gradient(135deg, #0284c7 0%, #6366f1 100%)',
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
              <span style={{ fontSize: '13pt', fontWeight: '900', letterSpacing: '-0.01em', color: '#f8fafc' }}>
                SAIL MIS
              </span>
              <span style={{ fontSize: '7.5pt', color: '#94a3b8', fontWeight: '600' }}>Portal</span>
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
              <div key={idx} style={{ position: 'relative' }}>
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
                      color: openDropdown === idx ? '#38bdf8' : '#cbd5e1',
                      backgroundColor: openDropdown === idx ? 'rgba(2, 132, 199, 0.1)' : 'transparent'
                    }}
                    onMouseEnter={() => setOpenDropdown(idx)}
                    onMouseLeave={() => setOpenDropdown(null)}
                  >
                    <span>{item.icon}</span>
                    <span style={{ fontSize: '10pt', fontWeight: '600' }}>{item.label}</span>
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
                      color: '#cbd5e1',
                      fontSize: '10pt',
                      fontWeight: '600'
                    }}
                    onMouseEnter={(e) => {
                      e.currentTarget.style.backgroundColor = 'rgba(2, 132, 199, 0.1)';
                      e.currentTarget.style.color = '#38bdf8';
                    }}
                    onMouseLeave={(e) => {
                      e.currentTarget.style.backgroundColor = 'transparent';
                      e.currentTarget.style.color = '#cbd5e1';
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
                    marginTop: '8px',
                    backgroundColor: '#1e293b',
                    border: '1px solid #334155',
                    borderRadius: '8px',
                    overflow: 'hidden',
                    minWidth: '220px',
                    boxShadow: '0 10px 25px rgba(0, 0, 0, 0.3)'
                  }}
                  onMouseEnter={() => setOpenDropdown(idx)}
                  onMouseLeave={() => setOpenDropdown(null)}
                  >
                    {item.submenu.map((subitem, subidx) => (
                      <Link key={subidx} href={subitem.link} style={{ textDecoration: 'none' }}>
                        <div style={{
                          padding: '12px 16px',
                          borderBottom: subidx < item.submenu.length - 1 ? '1px solid rgba(51, 65, 85, 0.3)' : 'none',
                          color: '#cbd5e1',
                          cursor: 'pointer',
                          display: 'flex',
                          alignItems: 'center',
                          gap: '10px',
                          fontSize: '9.5pt',
                          transition: 'all 0.2s ease'
                        }}
                        onMouseEnter={(e) => {
                          e.currentTarget.style.backgroundColor = 'rgba(2, 132, 199, 0.15)';
                          e.currentTarget.style.color = '#38bdf8';
                          e.currentTarget.style.paddingLeft = '20px';
                        }}
                        onMouseLeave={(e) => {
                          e.currentTarget.style.backgroundColor = 'transparent';
                          e.currentTarget.style.color = '#cbd5e1';
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
            backgroundColor: '#1e293b',
            border: '1px solid #334155',
            borderRadius: '20px',
            fontSize: '8.5pt',
            color: '#10b981',
            fontWeight: '600',
            display: 'flex',
            alignItems: 'center',
            gap: '6px'
          }}>
            <div style={{
              width: '6px',
              height: '6px',
              backgroundColor: '#10b981',
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
