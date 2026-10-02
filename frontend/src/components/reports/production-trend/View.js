'use client';

import React, { useState, useEffect } from 'react';
import { ReportPage, FilterBar, Field, Status, Toggle, Empty, entryStyles as es, reportStyles as rs } from '../ReportUI';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || '';

function fmt(v) {
  if (v == null) return '—';
  return Number(v).toLocaleString('en-IN', { maximumFractionDigits: 0 });
}

const cellBase = {
  padding: '9px 14px',
  fontSize: '10.5pt',
  borderBottom: '1px solid #e8eaed',
  whiteSpace: 'nowrap',
};

export default function ProductionTrendPage() {
  const [basis, setBasis] = useState('fy'); // 'fy' | 'cy'
  const [groups, setGroups] = useState([]);
  const [group, setGroup] = useState('sail5');
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    fetch(`${API_BASE}/api/production-trend/groups`)
      .then((r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        return r.json();
      })
      .then((d) => setGroups(d.groups || []))
      .catch((e) => setError(`Failed to load plant groups: ${e.message}`));
  }, []);

  useEffect(() => {
    setLoading(true);
    setError(null);
    fetch(`${API_BASE}/api/production-trend?basis=${basis}&group=${group}`)
      .then((r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        return r.json();
      })
      .then((d) => setData(d))
      .catch((e) => setError(`Failed to load production trend: ${e.message}`))
      .finally(() => setLoading(false));
  }, [basis, group]);

  const items = data?.items || [];
  const years = data?.years || [];

  return (
    <ReportPage
      fill
      maxWidth={1200}
      title="Hot Metal / Crude Steel / Finished Steel / Saleable Steel — Trend"
      description={<>Year-wise production for {data?.group_label || '…'}, {basis === 'fy' ? 'financial year' : 'calendar year'} basis (&apos;000 T)</>}
    >
        <FilterBar actions={loading ? <span className={es.ctxNote}>Loading…</span> : null}>
          <Field label="Basis">
            <Toggle label="Basis" value={basis} onChange={setBasis}
                    options={[{ id: 'fy', label: 'Financial Year' }, { id: 'cy', label: 'Calendar Year' }]} />
          </Field>
          <Field label="Plant" htmlFor="trend-group">
            <select id="trend-group" className={es.control} style={{ minWidth: 160 }} value={group} onChange={(e) => setGroup(e.target.value)}>
              {groups.map((g) => (
                <option key={g.value} value={g.value}>{g.label}</option>
              ))}
            </select>
          </Field>
        </FilterBar>

        <Status status={error ? { type: 'error', text: error } : null} />

        {!loading && !error && data && years.length === 0 && (
          <Empty>No data available for {data.group_label}.</Empty>
        )}

        {/* Table */}
        {data && years.length > 0 && (
          <div className={rs.grow}>
            <table style={{ borderCollapse: 'separate', borderSpacing: 0, width: '100%' }}>
              <thead>
                <tr>
                  <th style={{
                    ...cellBase,
                    position: 'sticky',
                    top: 0,
                    left: 0,
                    zIndex: 3,
                    backgroundColor: '#e8f0fe',
                    textAlign: 'left',
                    fontWeight: 700,
                    color: '#174ea6',
                    minWidth: '110px',
                    borderRight: '1px solid #dadce0',
                  }}>
                    {basis === 'fy' ? 'FY' : 'Year'}
                  </th>
                  {items.map((it) => (
                    <th key={it.key} style={{
                      ...cellBase,
                      position: 'sticky',
                      top: 0,
                      zIndex: 2,
                      backgroundColor: '#e8f0fe',
                      textAlign: 'right',
                      fontWeight: 700,
                      color: '#174ea6',
                      minWidth: '140px',
                    }}>
                      {it.item_name}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {years.map((row, idx) => {
                  const zebra = idx % 2 === 1 ? '#f8f9fa' : '#ffffff';
                  const isCurrent = idx === 0;
                  return (
                    <tr key={row.year_key}>
                      <td style={{
                        ...cellBase,
                        position: 'sticky',
                        left: 0,
                        zIndex: 1,
                        backgroundColor: isCurrent ? '#e8f0fe' : zebra,
                        fontWeight: 700,
                        color: '#202124',
                        borderRight: '1px solid #dadce0',
                      }}>
                        {row.year_label}
                      </td>
                      {items.map((it) => (
                        <td key={it.key} style={{
                          ...cellBase,
                          textAlign: 'right',
                          backgroundColor: isCurrent ? '#e8f0fe' : zebra,
                          color: row[it.key] == null ? '#bdc1c6' : '#202124',
                          fontVariantNumeric: 'tabular-nums',
                        }}>
                          {fmt(row[it.key])}
                        </td>
                      ))}
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
    </ReportPage>
  );
}
