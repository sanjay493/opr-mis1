'use client';

import React from 'react';
import Link from 'next/link';
import GlobalNavbar from '@/components/GlobalNavbar';

export default function HomePage() {

  const featureHighlights = [
    {
      title: 'Production Data Entry',
      description: 'Enter or update actual production values per plant and month with ABP plan comparison',
      icon: '📋',
      link: '/data-entry',
      color: '#6366f1',
      bgColor: 'rgba(99, 102, 241, 0.1)'
    },
    {
      title: 'Excel Integration',
      description: 'Upload plant spreadsheets, execute extractors, and populate database tables automatically',
      icon: '📊',
      link: '/upload',
      color: '#10b981',
      bgColor: 'rgba(16, 185, 129, 0.1)'
    },
    {
      title: 'Report Engine',
      description: 'Review compiled pages, edit cells directly, and generate publication-ready PDF reports',
      icon: '📄',
      link: '/report',
      color: '#1a73e8',
      bgColor: 'rgba(2, 132, 199, 0.1)'
    }
  ];

  return (
    <main style={{
      height: '100vh',
      overflowY: 'auto',
      backgroundColor: '#ffffff',
      fontFamily: 'var(--ui-font)',
      color: '#202124'
    }}>
      {/* Global Navbar */}
      <GlobalNavbar />

      {/* Main Content */}
      <div style={{ position: 'relative', zIndex: 1 }}>
        {/* Hero Section */}
        <section style={{
          maxWidth: '1600px',
          margin: '0 auto',
          padding: '80px 32px 60px',
          textAlign: 'center'
        }}>
          <div style={{ marginBottom: '32px' }}>
            <h1 style={{
              fontSize: '42pt',
              fontWeight: '800',
              letterSpacing: '-0.02em',
              margin: '0 0 16px 0',
              color: '#202124',
              lineHeight: '1.1'
            }}>
              SAIL Operations Monthly Informatics
            </h1>
            <p style={{
              fontSize: '13pt',
              color: '#5f6368',
              maxWidth: '700px',
              margin: '0 auto',
              lineHeight: '1.6'
            }}>
              Comprehensive management portal for production data, inventory tracking, and publication-ready report generation
            </p>
          </div>

          {/* CTA Buttons */}
          <div style={{
            display: 'flex',
            gap: '16px',
            justifyContent: 'center',
            marginTop: '32px'
          }}>
            <Link href="/data-entry" style={{ textDecoration: 'none' }}>
              <button style={{
                padding: '12px 28px',
                borderRadius: '8px',
                border: 'none',
                backgroundColor: '#1a73e8',
                color: '#ffffff',
                fontWeight: '700',
                fontSize: '10pt',
                cursor: 'pointer',
                transition: 'all 0.15s ease',
                display: 'flex',
                alignItems: 'center',
                gap: '8px'
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.backgroundColor = '#1765cc';
                e.currentTarget.style.boxShadow = '0 1px 3px rgba(60,64,67,.3), 0 4px 8px 3px rgba(60,64,67,.15)';
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.backgroundColor = '#1a73e8';
                e.currentTarget.style.transform = 'translateY(0)';
                e.currentTarget.style.boxShadow = 'none';
              }}
              >
                <span>📋</span> Enter Production Data
              </button>
            </Link>

            <Link href="/report" style={{ textDecoration: 'none' }}>
              <button style={{
                padding: '12px 28px',
                borderRadius: '8px',
                border: '1px solid #dadce0',
                backgroundColor: 'transparent',
                color: '#202124',
                fontWeight: '700',
                fontSize: '10pt',
                cursor: 'pointer',
                transition: 'all 0.3s ease',
                display: 'flex',
                alignItems: 'center',
                gap: '8px'
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.backgroundColor = 'rgba(26, 115, 232, 0.08)';
                e.currentTarget.style.borderColor = '#1a73e8';
                e.currentTarget.style.color = '#1a73e8';
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.backgroundColor = 'transparent';
                e.currentTarget.style.borderColor = '#dadce0';
                e.currentTarget.style.color = '#202124';
                e.currentTarget.style.transform = 'translateY(0)';
              }}
              >
                <span>📄</span> View Reports
              </button>
            </Link>
          </div>
        </section>

        {/* Features Grid */}
        <section style={{
          maxWidth: '1600px',
          margin: '0 auto',
          padding: '60px 32px'
        }}>
          <div style={{ marginBottom: '40px' }}>
            <h2 style={{
              fontSize: '28pt',
              fontWeight: '900',
              margin: '0 0 12px 0',
              letterSpacing: '-0.01em'
            }}>
              Core Features
            </h2>
            <p style={{
              fontSize: '11pt',
              color: '#5f6368',
              margin: 0
            }}>
              Everything you need for comprehensive operations management
            </p>
          </div>

          <div style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(380px, 1fr))',
            gap: '24px'
          }}>
            {featureHighlights.map((feature, idx) => (
              <Link key={idx} href={feature.link} style={{ textDecoration: 'none' }}>
                <div style={{
                  height: '100%',
                  backgroundColor: '#f8f9fa',
                  border: '1px solid #dadce0',
                  borderRadius: '12px',
                  padding: '32px',
                  cursor: 'pointer',
                  transition: 'all 0.3s ease',
                  display: 'flex',
                  flexDirection: 'column',
                  gap: '16px'
                }}
                onMouseEnter={(e) => {
                  e.currentTarget.style.transform = 'translateY(-2px)';
                  e.currentTarget.style.borderColor = feature.color;
                  e.currentTarget.style.boxShadow = '0 1px 3px rgba(60,64,67,.3), 0 4px 8px 3px rgba(60,64,67,.15)';
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.transform = 'translateY(0)';
                  e.currentTarget.style.borderColor = '#dadce0';
                  e.currentTarget.style.boxShadow = 'none';
                }}
                >
                  <div style={{
                    width: '56px',
                    height: '56px',
                    borderRadius: '12px',
                    backgroundColor: feature.bgColor,
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    fontSize: '28px'
                  }}>
                    {feature.icon}
                  </div>
                  <div>
                    <h3 style={{
                      fontSize: '14pt',
                      fontWeight: '800',
                      margin: '0 0 8px 0',
                      color: '#202124'
                    }}>
                      {feature.title}
                    </h3>
                    <p style={{
                      fontSize: '9.5pt',
                      color: '#5f6368',
                      margin: 0,
                      lineHeight: '1.5'
                    }}>
                      {feature.description}
                    </p>
                  </div>
                  <div style={{
                    marginTop: 'auto',
                    paddingTop: '16px',
                    borderTop: '1px solid #e8eaed',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '6px',
                    fontSize: '10pt',
                    fontWeight: '600',
                    color: feature.color
                  }}>
                    Explore →
                  </div>
                </div>
              </Link>
            ))}
          </div>
        </section>

        {/* Info Section */}
        <section style={{
          maxWidth: '1600px',
          margin: '0 auto',
          padding: '60px 32px'
        }}>
          <div style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))',
            gap: '24px'
          }}>
            <div style={{
              backgroundColor: 'rgba(2, 132, 199, 0.1)',
              border: '1px solid rgba(2, 132, 199, 0.3)',
              borderRadius: '12px',
              padding: '24px',
              borderLeft: '4px solid #1a73e8'
            }}>
              <h4 style={{
                fontSize: '11pt',
                fontWeight: '800',
                margin: '0 0 8px 0',
                color: '#1a73e8'
              }}>
                🚀 Quick Start
              </h4>
              <p style={{
                fontSize: '9pt',
                color: '#5f6368',
                margin: 0,
                lineHeight: '1.6'
              }}>
                Upload spreadsheets, refine data directly in the system, and generate reports with a few clicks.
              </p>
            </div>

            <div style={{
              backgroundColor: 'rgba(16, 185, 129, 0.1)',
              border: '1px solid rgba(16, 185, 129, 0.3)',
              borderRadius: '12px',
              padding: '24px',
              borderLeft: '4px solid #10b981'
            }}>
              <h4 style={{
                fontSize: '11pt',
                fontWeight: '800',
                margin: '0 0 8px 0',
                color: '#10b981'
              }}>
                ✓ Data Integrity
              </h4>
              <p style={{
                fontSize: '9pt',
                color: '#5f6368',
                margin: 0,
                lineHeight: '1.6'
              }}>
                Compare actuals against ABP plans with instant % variance calculations for performance tracking.
              </p>
            </div>

            <div style={{
              backgroundColor: 'rgba(99, 102, 241, 0.1)',
              border: '1px solid rgba(99, 102, 241, 0.3)',
              borderRadius: '12px',
              padding: '24px',
              borderLeft: '4px solid #6366f1'
            }}>
              <h4 style={{
                fontSize: '11pt',
                fontWeight: '800',
                margin: '0 0 8px 0',
                color: '#818cf8'
              }}>
                📊 Professional Reports
              </h4>
              <p style={{
                fontSize: '9pt',
                color: '#5f6368',
                margin: 0,
                lineHeight: '1.6'
              }}>
                Generate publication-ready PDFs with customizable layouts and direct page content editing.
              </p>
            </div>
          </div>
        </section>

        {/* Footer */}
        <footer style={{
          borderTop: '1px solid #e8eaed',
          padding: '40px 32px',
          textAlign: 'center'
        }}>
          <p style={{ fontSize: '9pt', color: '#5f6368', margin: '0 0 8px 0' }}>
            SAIL Operations Directorate • MIS Group • Steel Authority of India Limited
          </p>
          <p style={{ fontSize: '8.5pt', color: '#9aa0a6', margin: 0 }}>
            Version 1.0.0 • Production Ready
          </p>
        </footer>
      </div>

      {/* Global Styles */}
      <style>{`
        @keyframes pulse {
          0%, 100% {
            opacity: 1;
          }
          50% {
            opacity: 0.5;
          }
        }

        * {
          scrollbar-width: thin;
          scrollbar-color: #dadce0 #ffffff;
        }

        ::-webkit-scrollbar {
          width: 6px;
          height: 6px;
        }

        ::-webkit-scrollbar-track {
          background: #ffffff;
        }

        ::-webkit-scrollbar-thumb {
          background: #dadce0;
          border-radius: 3px;
        }

        ::-webkit-scrollbar-thumb:hover {
          background: #dadce0;
        }

        @media (max-width: 1024px) {
          nav div:nth-child(1) {
            gap: 16px !important;
          }
        }
      `}</style>
    </main>
  );
}

