'use client';

import React from 'react';
import { useSailSmsParams, formatSailValue } from '@/hooks/useSailSmsParams';

/**
 * Component to display SAIL SMS parameters (Hot Metal Consumption, Scrap Consumption)
 * Shows data from DB if available, otherwise shows "calculated" values computed on-the-fly
 */
export default function SailSmsParamsDisplay({ apiBase, month, groupCode }) {
  const { sailParams, loading, error } = useSailSmsParams(apiBase, month);

  // Debug logging
  console.log('[SailSmsParamsDisplay] groupCode:', groupCode, 'month:', month, 'sailParams:', sailParams);

  // Only show for SMS group
  if (groupCode !== 'SMS') {
    console.log('[SailSmsParamsDisplay] Skipping - groupCode is not SMS:', groupCode);
    return null;
  }

  if (loading) {
    return (
      <div style={{ padding: '16px', textAlign: 'center', color: '#64748b', fontSize: '12px' }}>
        Loading SAIL SMS parameters...
      </div>
    );
  }

  if (error) {
    console.log('[SailSmsParamsDisplay] Error:', error);
    return (
      <div style={{ padding: '16px', textAlign: 'center', color: '#991b1b', fontSize: '12px',
                    backgroundColor: '#fef2f2', border: '1px solid #fca5a5', borderRadius: '4px',
                    marginTop: '24px', marginBottom: '24px' }}>
        Error loading SAIL SMS parameters: {error}
      </div>
    );
  }

  if (!sailParams || Object.keys(sailParams).length === 0) {
    console.log('[SailSmsParamsDisplay] No sailParams data available');
    return null;
  }

  console.log('[SailSmsParamsDisplay] Rendering with sailParams:', sailParams);

  return (
    <div style={{ marginTop: '24px', marginBottom: '24px' }}>
      <div style={{
        background: '#fef9c3', color: '#854d0e', padding: '12px 14px',
        borderRadius: '4px 4px 0 0', fontSize: '12px', fontWeight: '600',
        display: 'flex', justifyContent: 'space-between', alignItems: 'center'
      }}>
        <span>SAIL Consolidated (Weighted by Crude Steel Production)</span>
        <span style={{ fontSize: '10px', fontWeight: '500', opacity: 0.8 }}>
          Auto-calculated if not in DB
        </span>
      </div>

      <div style={{ overflowX: 'auto', border: '1px solid #e2e8f0', borderTop: 'none', borderRadius: '0 0 4px 4px' }}>
        <table style={{ borderCollapse: 'collapse', width: '100%', fontSize: '11px' }}>
          <thead>
            <tr style={{ backgroundColor: '#f1f5f9', borderBottom: '1px solid #e2e8f0' }}>
              <th style={{ padding: '8px 12px', textAlign: 'left', fontWeight: '600', color: '#475569' }}>
                Parameter
              </th>
              <th style={{ padding: '8px 12px', textAlign: 'right', fontWeight: '600', color: '#475569' }}>
                Monthly
              </th>
              <th style={{ padding: '8px 12px', textAlign: 'right', fontWeight: '600', color: '#475569' }}>
                YTD
              </th>
              <th style={{ padding: '8px 12px', textAlign: 'center', fontWeight: '600', color: '#475569' }}>
                Unit
              </th>
              <th style={{ padding: '8px 12px', textAlign: 'center', fontWeight: '600', color: '#475569' }}>
                Source
              </th>
            </tr>
          </thead>
          <tbody>
            {Object.entries(sailParams).map(([paramName, paramData], idx) => {
              const monthlyFormatted = formatSailValue(paramData, 'actual');
              const ytdFormatted = formatSailValue(paramData, 'till_month_actual');
              const source = paramData.source || 'unknown';
              const isCalculated = source === 'calculated';

              return (
                <tr
                  key={paramName}
                  style={{
                    backgroundColor: isCalculated ? '#fffbeb' : idx % 2 === 0 ? '#fff' : '#f8fafc',
                    borderBottom: '1px solid #e2e8f0',
                  }}
                >
                  <td style={{ padding: '8px 12px', color: '#1e293b', fontWeight: '500' }}>
                    {paramName}
                  </td>
                  <td style={{ padding: '8px 12px', textAlign: 'right', color: '#1e293b' }}>
                    {monthlyFormatted.value || '—'}
                  </td>
                  <td style={{ padding: '8px 12px', textAlign: 'right', color: '#1e293b' }}>
                    {ytdFormatted.value || '—'}
                  </td>
                  <td style={{ padding: '8px 12px', textAlign: 'center', color: '#64748b', fontSize: '10px' }}>
                    {paramData.unit || '—'}
                  </td>
                  <td style={{ padding: '8px 12px', textAlign: 'center' }}>
                    <span style={{
                      fontSize: '9px',
                      padding: '2px 6px',
                      borderRadius: '3px',
                      backgroundColor: isCalculated ? '#fef9c3' : '#dcfce7',
                      color: isCalculated ? '#854d0e' : '#166534',
                      fontWeight: '600',
                      whiteSpace: 'nowrap'
                    }}>
                      {isCalculated ? 'calculated' : 'from DB'}
                    </span>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      <div style={{
        fontSize: '9px',
        color: '#64748b',
        padding: '8px 12px',
        backgroundColor: '#f8fafc',
        borderRadius: '0 0 4px 4px',
        borderTop: '1px solid #e2e8f0',
      }}>
        <strong>Note:</strong> SAIL values are weighted averages of SMS shops using Crude Steel production as the weight factor.
        If marked as "calculated", the value is computed on-the-fly and not stored in the database.
      </div>
    </div>
  );
}
