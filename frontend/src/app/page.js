'use client';

import React from 'react';
import Link from 'next/link';

export default function LandingPage() {
  return (
    <main style={{
      minHeight: '100vh',
      backgroundColor: '#0f172a',
      fontFamily: 'system-ui, -apple-system, sans-serif',
      color: '#f8fafc',
      display: 'flex',
      flexDirection: 'column',
      alignItems: 'center',
      justifyContent: 'center',
      padding: '40px 20px',
      position: 'relative',
      overflow: 'hidden'
    }}>
      {/* Background soft radial blobs for premium aesthetics */}
      <div style={{
        position: 'absolute',
        width: '600px',
        height: '600px',
        borderRadius: '50%',
        background: 'radial-gradient(circle, rgba(2, 132, 199, 0.15) 0%, rgba(0,0,0,0) 70%)',
        top: '-10%',
        left: '-10%',
        zIndex: 0
      }} />
      <div style={{
        position: 'absolute',
        width: '600px',
        height: '600px',
        borderRadius: '50%',
        background: 'radial-gradient(circle, rgba(16, 185, 129, 0.1) 0%, rgba(0,0,0,0) 70%)',
        bottom: '-10%',
        right: '-10%',
        zIndex: 0
      }} />

      <div style={{ maxWidth: '1000px', width: '100%', zIndex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '40px' }}>
        
        {/* Portal Header */}
        <div style={{ textAlign: 'center' }}>
          <div style={{
            display: 'inline-flex',
            alignItems: 'center',
            gap: '8px',
            backgroundColor: '#1e293b',
            border: '1px solid #334155',
            padding: '6px 16px',
            borderRadius: '20px',
            fontSize: '0.85rem',
            color: '#38bdf8',
            fontWeight: '600',
            marginBottom: '16px'
          }}>
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
              <polygon points="5 3 19 12 5 21 5 3" />
            </svg>
            System Active • Version 1.0.0
          </div>
          
          <h1 style={{
            fontSize: '28pt',
            fontWeight: '900',
            letterSpacing: '-0.02em',
            margin: '0 0 12px 0',
            lineHeight: '1.2',
            background: 'linear-gradient(to right, #f8fafc, #94a3b8)',
            WebkitBackgroundClip: 'text',
            WebkitTextFillColor: 'transparent'
          }}>
            SAIL Operations Monthly Informatics (OMI)
          </h1>
          <p style={{
            fontSize: '11pt',
            color: '#94a3b8',
            maxWidth: '640px',
            margin: '0 auto',
            lineHeight: '1.5'
          }}>
            Interactive management portal to extract spreadsheet metrics, edit report page cells directly, save configurations, and compile publication-ready PDF reports.
          </p>
        </div>

        {/* Action Portal Cards */}
        <div style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(340px, 1fr))',
          gap: '24px',
          width: '100%'
        }}>
          
          {/* Card 1: Excel uploader */}
          <Link href="/upload" style={{ textDecoration: 'none' }}>
            <div style={{
              height: '100%',
              backgroundColor: '#1e293b',
              border: '1px solid #334155',
              borderRadius: '12px',
              padding: '30px',
              display: 'flex',
              flexDirection: 'column',
              gap: '20px',
              cursor: 'pointer',
              transition: 'all 0.3s ease',
              boxShadow: '0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06)'
            }}
            className="portal-card"
            >
              <div style={{
                width: '48px',
                height: '48px',
                borderRadius: '8px',
                backgroundColor: 'rgba(16, 185, 129, 0.1)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                color: '#10b981'
              }}>
                <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
                  <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
                  <polyline points="17 8 12 3 7 8" />
                  <line x1="12" y1="3" x2="12" y2="15" />
                </svg>
              </div>

              <div>
                <h3 style={{ fontSize: '14pt', fontWeight: '800', color: '#f1f5f9', margin: '0 0 8px 0' }}>
                  Excel Ingestion & Extraction
                </h3>
                <p style={{ fontSize: '9.5pt', color: '#94a3b8', lineHeight: '1.5', margin: 0 }}>
                  Upload raw plant spreadsheets (coordinate parsed for RSP), execute cell extractors, and dynamically populate database production & techno-economic tables.
                </p>
              </div>

              <div style={{
                marginTop: 'auto',
                display: 'inline-flex',
                alignItems: 'center',
                gap: '6px',
                fontSize: '9.5pt',
                color: '#10b981',
                fontWeight: '600'
              }}>
                Access Uploader
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
                  <line x1="5" y1="12" x2="19" y2="12" />
                  <polyline points="12 5 19 12 12 19" />
                </svg>
              </div>
            </div>
          </Link>

          {/* Card 2: Manual Data Entry */}
          <Link href="/data-entry" style={{ textDecoration: 'none' }}>
            <div style={{
              height: '100%',
              backgroundColor: '#1e293b',
              border: '1px solid #334155',
              borderRadius: '12px',
              padding: '30px',
              display: 'flex',
              flexDirection: 'column',
              gap: '20px',
              cursor: 'pointer',
              transition: 'all 0.3s ease',
              boxShadow: '0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06)'
            }}
            className="portal-card"
            >
              <div style={{
                width: '48px',
                height: '48px',
                borderRadius: '8px',
                backgroundColor: 'rgba(99, 102, 241, 0.1)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                color: '#6366f1'
              }}>
                <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
                  <rect x="3" y="3" width="18" height="18" rx="2"/>
                  <path d="M3 9h18M9 21V9"/>
                </svg>
              </div>

              <div>
                <h3 style={{ fontSize: '14pt', fontWeight: '800', color: '#f1f5f9', margin: '0 0 8px 0' }}>
                  Manual Data Entry
                </h3>
                <p style={{ fontSize: '9.5pt', color: '#94a3b8', lineHeight: '1.5', margin: 0 }}>
                  Directly enter or correct actual production values per plant and month. Items are pre-loaded from ABP plan targets for easy comparison.
                </p>
              </div>

              <div style={{
                marginTop: 'auto',
                display: 'inline-flex',
                alignItems: 'center',
                gap: '6px',
                fontSize: '9.5pt',
                color: '#6366f1',
                fontWeight: '600'
              }}>
                Open Entry Form
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
                  <line x1="5" y1="12" x2="19" y2="12" />
                  <polyline points="12 5 19 12 12 19" />
                </svg>
              </div>
            </div>
          </Link>

          {/* Card 3: Report Editor */}
          <Link href="/report" style={{ textDecoration: 'none' }}>
            <div style={{
              height: '100%',
              backgroundColor: '#1e293b',
              border: '1px solid #334155',
              borderRadius: '12px',
              padding: '30px',
              display: 'flex',
              flexDirection: 'column',
              gap: '20px',
              cursor: 'pointer',
              transition: 'all 0.3s ease',
              boxShadow: '0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06)'
            }}
            className="portal-card"
            >
              <div style={{
                width: '48px',
                height: '48px',
                borderRadius: '8px',
                backgroundColor: 'rgba(2, 132, 199, 0.1)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                color: '#0284c7'
              }}>
                <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
                  <path d="M14.5 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7.5L14.5 2z" />
                  <polyline points="14 2 14 8 20 8" />
                </svg>
              </div>

              <div>
                <h3 style={{ fontSize: '14pt', fontWeight: '800', color: '#f1f5f9', margin: '0 0 8px 0' }}>
                  Interactive Report Engine
                </h3>
                <p style={{ fontSize: '9.5pt', color: '#94a3b8', lineHeight: '1.5', margin: 0 }}>
                  Review compiled MIS pages, edit cells directly with live aggregates, save configs, and compile high-fidelity A4 layout PDF documents using WeasyPrint.
                </p>
              </div>

              <div style={{
                marginTop: 'auto',
                display: 'inline-flex',
                alignItems: 'center',
                gap: '6px',
                fontSize: '9.5pt',
                color: '#38bdf8',
                fontWeight: '600'
              }}>
                Open Report Engine
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
                  <line x1="5" y1="12" x2="19" y2="12" />
                  <polyline points="12 5 19 12 12 19" />
                </svg>
              </div>
            </div>
          </Link>

        </div>

        {/* Footer info */}
        <div style={{ fontSize: '0.75rem', color: '#64748b', textAlign: 'center', marginTop: '20px' }}>
          Steel Authority of India Limited • Operations Directorate • MIS Group
        </div>
      </div>
      
      {/* Inline styles for hover micro-animations */}
      <style>{`
        .portal-card:hover {
          transform: translateY(-4px);
          border-color: #38bdf8 !important;
          box-shadow: 0 10px 20px rgba(2, 132, 199, 0.15), 0 6px 6px rgba(0,0,0,0.2) !important;
        }
      `}</style>
    </main>
  );
}
