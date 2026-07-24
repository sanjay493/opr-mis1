'use client';

import React, { useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { useAuth, API_BASE_URL } from '@/providers/AuthProvider';

export default function GlobalNavbar() {
  const [openDropdown, setOpenDropdown] = useState(null);
  const { user, logout } = useAuth();
  const router = useRouter();

  const handleLogout = async () => {
    await logout();
    setOpenDropdown(null);
    router.push('/');
  };

  const navItems = [
    {
      label: 'Data Entry',
      icon: '📋',
      submenu: [
        { label: 'Data Entry Hub', link: '/data-entry', icon: '📋' },

        { type: 'group', groupLabel: 'Manual Entry' },
        { label: 'Production Data Entry', link: '/data-entry/production', icon: '📊' },
        { label: 'Special Steel Manual Entry (ISP)', link: '/data-entry/special-steel', icon: '🔩' },
        { label: 'Techno Manual Entry', link: '/data-entry/techno-manual', icon: '✏️' },
        { label: 'Legacy SMS / Crude Steel', link: '/data-entry/legacy-sms-crude', icon: '🗂️' },

        { type: 'group', groupLabel: 'Uploads & Extraction' },
        { label: 'Production, Stock & Special Steel Upload', link: '/upload', icon: '📤' },
        { label: 'Techno Upload', link: '/data-entry/techno', icon: '🔧' },

        { type: 'group', groupLabel: 'Stock & Transfers' },
        { label: 'Opening Stock', link: '/data-entry/opening-stock', icon: '📦' },
        { label: 'IPT Status', link: '/data-entry/ipt', icon: '↔️' },
        { label: 'Conversion Data', link: '/data-entry/conversion', icon: '⚡' },

        { type: 'group', groupLabel: 'Annual Targets' },
        { label: 'TE Targets', link: '/data-entry/targets', icon: '🎯' },
        { label: 'TE Targets (Pages 28-30)', link: '/data-entry/techno-page-targets', icon: '🎯' },

        { type: 'group', groupLabel: 'Dashboards' },
        { label: 'Techno Summary', link: '/data-entry/techno-summary', icon: '📈' },
      ]
    },
    {
      label: 'Reports',
      icon: '📄',
      submenu: [
        { label: 'OMI Generate', link: '/report', icon: '📈' },
        { label: 'Production Highlights', link: '/reports/highlights', icon: '✨' },
        { label: 'Major Production (Month & Till Month)', link: '/reports/major-production', icon: '🏭' },
        { label: 'New Facilities (Annexure-III)', link: '/reports/new-facilities', icon: '🆕' },
        { label: 'Month-wise Production', link: '/reports/production-fy', icon: '📅' },
        { label: 'Unit-wise Production Query', link: '/reports/production-query', icon: '🔍' },
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
                    overflowY: 'auto',
                    maxHeight: 'calc(100vh - 100px)',
                    minWidth: '280px',
                    boxShadow: '0 1px 3px rgba(60,64,67,.3), 0 4px 8px 3px rgba(60,64,67,.15)'
                  }}
                  >
                    {item.submenu.map((subitem, subidx) => {
                      if (subitem.type === 'group') {
                        return (
                          <div key={subidx} style={{
                            padding: '10px 18px 6px',
                            marginTop: subidx > 0 ? '4px' : '0',
                            fontSize: '9.5pt',
                            fontWeight: 700,
                            color: '#5f6368',
                            textTransform: 'uppercase',
                            letterSpacing: '0.04em',
                            backgroundColor: '#eef1f4',
                            borderTop: subidx > 0 ? '1px solid #e8eaed' : 'none',
                            borderBottom: '1px solid #e8eaed',
                          }}>
                            {subitem.groupLabel}
                          </div>
                        );
                      }
                      const nextIsGroupOrEnd = subidx === item.submenu.length - 1
                        || item.submenu[subidx + 1]?.type === 'group';
                      return (
                        <Link key={subidx} href={subitem.link} style={{ textDecoration: 'none' }}>
                          <div style={{
                            padding: '13px 18px',
                            borderBottom: nextIsGroupOrEnd ? 'none' : '1px solid #e8eaed',
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
                      );
                    })}
                  </div>
                )}
              </div>
            ))}
          </div>

          {/* Account menu */}
          <div
            style={{ position: 'relative', marginLeft: 'auto' }}
            onMouseEnter={() => setOpenDropdown('account')}
            onMouseLeave={() => setOpenDropdown(null)}
          >
            {user ? (
              <>
                <div style={{
                  cursor: 'pointer',
                  padding: '8px 12px',
                  borderRadius: '6px',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '6px',
                  color: openDropdown === 'account' ? '#1a73e8' : '#202124',
                  backgroundColor: openDropdown === 'account' ? 'rgba(26, 115, 232, 0.08)' : 'transparent',
                }}>
                  <span>👤</span>
                  <span style={{ fontSize: '12pt', fontWeight: '600' }}>{user.name || user.email}</span>
                  {user.role && (
                    <span style={{
                      fontSize: '8.5pt', fontWeight: 700, textTransform: 'uppercase',
                      padding: '2px 6px', borderRadius: '10px',
                      backgroundColor: user.role === 'admin' ? '#fce8e6' : '#e6f4ea',
                      color: user.role === 'admin' ? '#c5221f' : '#188038',
                    }}>
                      {user.role}
                    </span>
                  )}
                </div>
                {openDropdown === 'account' && (
                  <div style={{
                    position: 'absolute', top: '100%', right: 0,
                    backgroundColor: '#f8f9fa', border: '1px solid #dadce0', borderRadius: '8px',
                    overflow: 'hidden', minWidth: '200px', zIndex: 10,
                    boxShadow: '0 1px 3px rgba(60,64,67,.3), 0 4px 8px 3px rgba(60,64,67,.15)',
                  }}>
                    <Link href="/profile" style={{ textDecoration: 'none' }}>
                      <div style={{ padding: '12px 18px', color: '#202124', fontSize: '12pt', borderBottom: '1px solid #e8eaed' }}>
                        👤 My Profile
                      </div>
                    </Link>
                    {user.role === 'admin' && (
                      <>
                        <Link href="/admin/users" style={{ textDecoration: 'none' }}>
                          <div style={{ padding: '12px 18px', color: '#202124', fontSize: '12pt', borderBottom: '1px solid #e8eaed' }}>
                            🛠️ Manage Users
                          </div>
                        </Link>
                        <Link href="/admin/allowed-emails" style={{ textDecoration: 'none' }}>
                          <div style={{ padding: '12px 18px', color: '#202124', fontSize: '12pt', borderBottom: '1px solid #e8eaed' }}>
                            ✉️ Allowed Emails
                          </div>
                        </Link>
                        <Link href="/admin/activity-log" style={{ textDecoration: 'none' }}>
                          <div style={{ padding: '12px 18px', color: '#202124', fontSize: '12pt', borderBottom: '1px solid #e8eaed' }}>
                            📜 Activity Log
                          </div>
                        </Link>
                        <Link href="/admin/backup" style={{ textDecoration: 'none' }}>
                          <div style={{ padding: '12px 18px', color: '#202124', fontSize: '12pt', borderBottom: '1px solid #e8eaed' }}>
                            💾 Backup & Restore
                          </div>
                        </Link>
                      </>
                    )}
                    <div
                      onClick={handleLogout}
                      style={{ padding: '12px 18px', color: '#c5221f', fontSize: '12pt', cursor: 'pointer' }}
                    >
                      🚪 Log Out
                    </div>
                  </div>
                )}
              </>
            ) : (
              <div style={{ display: 'flex', gap: '8px' }}>
                <Link href="/login" style={{ textDecoration: 'none' }}>
                  <div style={{ padding: '8px 12px', fontSize: '12pt', fontWeight: 600, color: '#1a73e8', cursor: 'pointer' }}>
                    Log In
                  </div>
                </Link>
                <Link href="/register" style={{ textDecoration: 'none' }}>
                  <div className="btn btn-primary" style={{ margin: 0, padding: '8px 14px', fontSize: '11pt' }}>
                    Register
                  </div>
                </Link>
              </div>
            )}
          </div>

          {/* Status badge */}
          <div style={{
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
